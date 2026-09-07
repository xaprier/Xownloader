from __future__ import annotations

import asyncio
import json
import re
import socket
import urllib.error
import urllib.request
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from xownloader_server.errors import (
    PolicyViolation,
    PreviewUnavailable,
    ProviderContentUnavailable,
)
from xownloader_server.models import DownloadJob

_POST_URL = re.compile(r"instagram\.com/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)")
_HIGHLIGHT_URL = re.compile(r"instagram\.com/stories/highlights/(\d+)")
_STORY_ITEM_URL = re.compile(r"instagram\.com/stories/([^/?#]+)/(\d+)")
_STORY_USER_URL = re.compile(r"instagram\.com/stories/([^/?#]+)/?(?:$|[?#])")
_B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
_APP_ID = "936619743392459"
_MEDIA_VIDEO = 2
_DESKTOP_UA = "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"
# `web_profile_info` (the usual username -> id lookup) is hard rate-limited; the
# mobile `usernameinfo` endpoint is not, but it rejects a browser UA with
# "useragent mismatch", so that one call goes out with an app UA instead.
_MOBILE_UA = "Instagram 275.0.0.27.98 Android"


@dataclass(frozen=True)
class InstagramSource:
    kind: Literal["post", "story", "highlight"]
    shortcode: str | None = None
    username: str | None = None
    story_pk: str | None = None
    highlight_id: str | None = None


def parse_source(url: str) -> InstagramSource:
    match = _POST_URL.search(url)
    if match:
        return InstagramSource(kind="post", shortcode=match.group(1))
    match = _HIGHLIGHT_URL.search(url)
    if match:
        return InstagramSource(kind="highlight", highlight_id=match.group(1))
    match = _STORY_ITEM_URL.search(url)
    if match and match.group(1) != "highlights":
        return InstagramSource(kind="story", username=match.group(1), story_pk=match.group(2))
    match = _STORY_USER_URL.search(url)
    if match and match.group(1) != "highlights":
        return InstagramSource(kind="story", username=match.group(1))
    raise PolicyViolation("Unsupported Instagram URL — posts, reels, stories, and highlights only")


FetchJson = Callable[[str], Awaitable[dict[str, Any]]]
FetchBytes = Callable[[str], Awaitable[bytes]]
Sleep = Callable[[float], Awaitable[None]]


class InstagramApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"HTTP {status}: {message}")
        self.status = status


def shortcode_from_url(value: str) -> str:
    source = parse_source(value)
    if source.kind != "post":
        raise PolicyViolation(
            "Only single Instagram posts and reels are supported "
            "(a URL containing /p/, /reel/, or /tv/)"
        )
    return source.shortcode


def shortcode_to_pk(shortcode: str) -> int:
    pk = 0
    for char in shortcode:
        pk = pk * 64 + _B64.index(char)
    return pk


class InstagramAdapter:
    name = "instagram"

    def __init__(
        self,
        cookie: str,
        *,
        delay_seconds: float = 0.0,
        fetch_json: FetchJson | None = None,
        fetch_bytes: FetchBytes | None = None,
        sleep: Sleep | None = None,
    ) -> None:
        self._cookie = cookie
        self._csrf = self._csrf_token(cookie)
        self._delay_seconds = delay_seconds
        self._fetch_json = fetch_json or self._default_fetch_json
        self._fetch_bytes = fetch_bytes or self._default_fetch_bytes
        self._sleep = sleep or asyncio.sleep
        self._uid_cache: dict[str, str] = {}

    @staticmethod
    def _csrf_token(cookie: str) -> str:
        match = re.search(r"csrftoken=([^;]+)", cookie)
        return match.group(1) if match else ""

    async def inspect(self, source_url: Any) -> dict[str, Any]:
        nodes, title, uploader = await self._load(parse_source(str(source_url)))
        media_items = [self._media_item(index, node) for index, node in enumerate(nodes)]
        thumbnail = media_items[0]["thumbnail"] if media_items else None
        return {
            "provider": "instagram",
            "title": title,
            "uploader": uploader,
            "thumbnail": thumbnail,
            "duration_seconds": None,
            "media_items": media_items,
        }

    async def _load(self, source: InstagramSource) -> tuple[list[dict[str, Any]], str, str | None]:
        if source.kind == "post":
            return await self._load_post(source.shortcode)
        if source.kind == "highlight":
            return await self._load_highlight(source.highlight_id)
        return await self._load_story(source.username, source.story_pk)

    async def _load_post(self, shortcode: str) -> tuple[list[dict[str, Any]], str, str | None]:
        pk = shortcode_to_pk(shortcode)
        try:
            payload = await self._fetch_json(f"/api/v1/media/{pk}/info/")
        except InstagramApiError as error:
            raise self._preview_error(error) from error
        items = payload.get("items") or []
        if not items:
            raise PreviewUnavailable("Post not found or not public")
        item = items[0]
        nodes = item.get("carousel_media") or [item]
        return nodes, self._title(item), (item.get("user") or {}).get("username")

    async def _load_highlight(
        self, highlight_id: str
    ) -> tuple[list[dict[str, Any]], str, str | None]:
        try:
            payload = await self._fetch_json(
                f"/api/v1/feed/reels_media/?reel_ids=highlight%3A{highlight_id}"
            )
        except InstagramApiError as error:
            raise self._preview_error(error) from error
        reel = self._first_reel(payload)
        items = (reel or {}).get("items") or []
        if not items:
            raise ProviderContentUnavailable("This highlight is unavailable or was removed")
        return (
            items,
            reel.get("title") or "Highlight",
            (reel.get("user") or {}).get("username"),
        )

    @staticmethod
    def _first_reel(payload: dict[str, Any]) -> dict[str, Any] | None:
        reels = payload.get("reels_media")
        if reels:
            return reels[0]
        reels_map = payload.get("reels") or {}
        return next(iter(reels_map.values()), None)

    async def _load_story(
        self, username: str, story_pk: str | None
    ) -> tuple[list[dict[str, Any]], str, str | None]:
        uid = await self._resolve_uid(username)
        try:
            payload = await self._fetch_json(f"/api/v1/feed/reels_media/?reel_ids={uid}")
        except InstagramApiError as error:
            raise self._preview_error(error) from error
        reel = self._first_reel(payload)
        items = (reel or {}).get("items") or []
        if not items:
            raise ProviderContentUnavailable("No active stories, or they have expired")
        if story_pk is not None:
            items = [node for node in items if str(node.get("pk")) == story_pk]
            if not items:
                raise ProviderContentUnavailable("This story has expired or is no longer available")
        return items, f"Story by {username}", username

    async def _resolve_uid(self, username: str) -> str:
        cached = self._uid_cache.get(username)
        if cached:
            return cached
        try:
            payload = await self._fetch_json(f"/api/v1/users/{username}/usernameinfo/")
        except InstagramApiError as error:
            if error.status in (401, 403, 429):
                raise self._preview_error(error) from error
            raise ProviderContentUnavailable("This account's stories are not accessible") from error
        if payload.get("status") == "fail":
            raise ProviderContentUnavailable(
                "Instagram would not return this account right now, try again later"
            )
        user = payload.get("user") or (payload.get("data") or {}).get("user") or {}
        uid = user.get("pk") or user.get("id")
        if not uid:
            raise ProviderContentUnavailable("This account could not be found")
        resolved = str(uid)
        self._uid_cache[username] = resolved
        return resolved

    @staticmethod
    def _preview_error(error: InstagramApiError) -> PreviewUnavailable:
        if error.status in (401, 403):
            return PreviewUnavailable("Instagram session is invalid or expired")
        if error.status == 429:
            return PreviewUnavailable("Instagram rate limit reached, try later")
        # Instagram answers a deleted / private / malformed media id with 400 or 404.
        if error.status in (400, 404):
            return PreviewUnavailable("Post not found or not public")
        return PreviewUnavailable("The provider metadata could not be loaded")

    @staticmethod
    def _title(item: dict[str, Any]) -> str:
        caption = item.get("caption") or {}
        text = (caption.get("text") or "").strip()
        if text:
            return text.splitlines()[0][:120]
        username = (item.get("user") or {}).get("username")
        return f"Post by {username}" if username else "Instagram post"

    def _media_item(self, index: int, node: dict[str, Any]) -> dict[str, Any]:
        is_video = node.get("media_type") == _MEDIA_VIDEO or bool(node.get("video_versions"))
        image = self._best_image(node)
        duration = node.get("video_duration")
        return {
            "index": index,
            "type": "video" if is_video else "image",
            "thumbnail": image.get("url") if image else None,
            "width": (image or {}).get("width"),
            "height": (image or {}).get("height"),
            "duration_seconds": int(duration) if isinstance(duration, (int, float)) else None,
        }

    @staticmethod
    def _best_image(node: dict[str, Any]) -> dict[str, Any] | None:
        candidates = (node.get("image_versions2") or {}).get("candidates") or []
        if not candidates:
            return None
        return max(candidates, key=lambda candidate: candidate.get("width", 0))

    @staticmethod
    def _best_video(node: dict[str, Any]) -> str | None:
        versions = node.get("video_versions") or []
        return versions[0]["url"] if versions else None

    async def download(
        self,
        job: DownloadJob,
        output_directory: Path,
        progress_callback: Callable[[float], Awaitable[None]],
    ) -> list[Path]:
        output_directory.mkdir(parents=True, exist_ok=True)
        nodes, title, _uploader = await self._load(parse_source(str(job.source_url)))
        job.title = title

        selection = (
            job.media_selection if job.media_selection is not None else list(range(len(nodes)))
        )
        for index in selection:
            if index < 0 or index >= len(nodes):
                raise RuntimeError(
                    f"Selected media item {index} is out of range ({len(nodes)} items)"
                )

        paths: list[Path] = []
        for position, index in enumerate(selection):
            node = nodes[index]
            video_url = self._best_video(node)
            if video_url:
                url, extension = video_url, "mp4"
            else:
                image = self._best_image(node)
                if not image:
                    raise RuntimeError(f"Media item {index} has no downloadable file")
                url, extension = image["url"], "jpg"
            destination = output_directory / f"{job.id}_{index}.{extension}"
            data = await self._fetch_bytes(url)
            destination.write_bytes(data)
            paths.append(destination)
            await progress_callback((position + 1) / len(selection) * 100)
            if position + 1 < len(selection) and self._delay_seconds:
                await self._sleep(self._delay_seconds)
        return paths

    async def _default_fetch_json(self, path: str) -> dict[str, Any]:
        user_agent = _MOBILE_UA if "/usernameinfo/" in path else _DESKTOP_UA
        request = urllib.request.Request(
            "https://www.instagram.com" + path,
            headers={
                "x-ig-app-id": _APP_ID,
                "x-csrftoken": self._csrf,
                "x-requested-with": "XMLHttpRequest",
                "User-Agent": user_agent,
                "Referer": "https://www.instagram.com/",
                "Sec-Fetch-Site": "same-origin",
                "Cookie": self._cookie,
            },
        )
        return await asyncio.to_thread(self._read_json, request)

    @staticmethod
    def _read_json(request: urllib.request.Request) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:300]
            raise InstagramApiError(error.code, detail) from error
        except (urllib.error.URLError, socket.timeout) as error:
            raise InstagramApiError(0, str(getattr(error, "reason", error))) from error
        try:
            return json.loads(body)
        except json.JSONDecodeError as error:
            raise InstagramApiError(0, "response was not JSON (session issue?)") from error

    async def _default_fetch_bytes(self, url: str) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        return await asyncio.to_thread(self._read_bytes, request)

    @staticmethod
    def _read_bytes(request: urllib.request.Request) -> bytes:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()
