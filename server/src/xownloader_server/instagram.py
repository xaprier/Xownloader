from __future__ import annotations

import asyncio
import json
import re
import socket
import urllib.error
import urllib.request
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from xownloader_server.errors import PolicyViolation, PreviewUnavailable
from xownloader_server.models import DownloadJob

_POST_URL = re.compile(r"instagram\.com/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)")
_B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
_APP_ID = "936619743392459"
_MEDIA_VIDEO = 2

FetchJson = Callable[[str], Awaitable[dict[str, Any]]]
FetchBytes = Callable[[str], Awaitable[bytes]]
Sleep = Callable[[float], Awaitable[None]]


class InstagramApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"HTTP {status}: {message}")
        self.status = status


def shortcode_from_url(value: str) -> str:
    match = _POST_URL.search(value)
    if not match:
        raise PolicyViolation(
            "Only single Instagram posts and reels are supported "
            "(a URL containing /p/, /reel/, or /tv/)"
        )
    return match.group(1)


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

    @staticmethod
    def _csrf_token(cookie: str) -> str:
        match = re.search(r"csrftoken=([^;]+)", cookie)
        return match.group(1) if match else ""

    async def inspect(self, source_url: Any) -> dict[str, Any]:
        item = await self._load_item(str(source_url))
        nodes = item.get("carousel_media") or [item]
        media_items = [self._media_item(index, node) for index, node in enumerate(nodes)]
        thumbnail = media_items[0]["thumbnail"] if media_items else None
        return {
            "provider": "instagram",
            "title": self._title(item),
            "uploader": (item.get("user") or {}).get("username"),
            "thumbnail": thumbnail,
            "duration_seconds": None,
            "media_items": media_items,
        }

    async def _load_item(self, source_url: str) -> dict[str, Any]:
        pk = shortcode_to_pk(shortcode_from_url(source_url))
        try:
            payload = await self._fetch_json(f"/api/v1/media/{pk}/info/")
        except InstagramApiError as error:
            raise self._preview_error(error) from error
        items = payload.get("items") or []
        if not items:
            raise PreviewUnavailable("Post not found or not public")
        return items[0]

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
        item = await self._load_item(str(job.source_url))
        job.title = self._title(item)
        nodes = item.get("carousel_media") or [item]

        selection = (
            job.media_selection if job.media_selection is not None else list(range(len(nodes)))
        )
        for index in selection:
            if index < 0 or index >= len(nodes):
                raise RuntimeError(
                    f"Selected media item {index} is out of range for this post "
                    f"({len(nodes)} items)"
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
        request = urllib.request.Request(
            "https://www.instagram.com" + path,
            headers={
                "x-ig-app-id": _APP_ID,
                "x-csrftoken": self._csrf,
                "x-requested-with": "XMLHttpRequest",
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"
                ),
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
