from __future__ import annotations

import asyncio
import logging
import re
import time
import urllib.request
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from instagrapi.exceptions import (
    ChallengeRequired,
    ClientError,
    LoginRequired,
    NotFoundError,
    PleaseWaitFewMinutes,
    RateLimitError,
    TwoFactorRequired,
)
from instagrapi.types import Highlight, Media, Resource, Story

from xownloader_server.errors import (
    PolicyViolation,
    PreviewUnavailable,
    ProviderContentUnavailable,
)
from xownloader_server.models import DownloadJob

logger = logging.getLogger(__name__)

_POST_URL = re.compile(r"instagram\.com/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)")
_HIGHLIGHT_URL = re.compile(r"instagram\.com/stories/highlights/(\d+)")
_STORY_ITEM_URL = re.compile(r"instagram\.com/stories/([^/?#]+)/(\d+)")
_STORY_USER_URL = re.compile(r"instagram\.com/stories/([^/?#]+)/?(?:$|[?#])")

_SESSION_COOLDOWN_SECONDS = 300.0


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


def shortcode_from_url(value: str) -> str:
    source = parse_source(value)
    if source.kind != "post":
        raise PolicyViolation(
            "Only single Instagram posts and reels are supported "
            "(a URL containing /p/, /reel/, or /tv/)"
        )
    return source.shortcode


@dataclass(frozen=True)
class MediaNode:
    is_video: bool
    download_url: str
    thumbnail_url: str
    width: int | None
    height: int | None
    duration_seconds: float | None


class InstagrapiClient(Protocol):
    def load_settings(self, path: Path) -> object: ...
    def dump_settings(self, path: Path) -> None: ...
    def login(self, username: str, password: str, verification_code: str = "") -> bool: ...
    def totp_generate_code(self, seed: str) -> str: ...
    def media_pk_from_code(self, code: str) -> str: ...
    def media_info(self, media_pk: str) -> Media: ...
    def user_id_from_username(self, username: str) -> str: ...
    def user_stories(self, user_id: str) -> list[Story]: ...
    def highlight_info(self, highlight_pk: str) -> Highlight: ...


ClientFactory = Callable[[], InstagrapiClient]
Clock = Callable[[], float]
FetchBytes = Callable[[str], Awaitable[bytes]]
Sleep = Callable[[float], Awaitable[None]]


class InstagramSessionManager:
    def __init__(
        self,
        username: str,
        password: str,
        session_path: Path,
        *,
        client_factory: ClientFactory,
        totp_seed: str | None = None,
        cooldown_seconds: float = _SESSION_COOLDOWN_SECONDS,
        clock: Clock = time.monotonic,
    ) -> None:
        self._username = username
        self._password = password
        self._session_path = session_path
        self._client_factory = client_factory
        # Instagram displays the TOTP setup key in space-separated groups; strip
        # them so a pasted-as-shown seed still base32-decodes correctly.
        self._totp_seed = totp_seed.replace(" ", "") if totp_seed else None
        self._cooldown_seconds = cooldown_seconds
        self._clock = clock
        self._client: InstagrapiClient | None = None
        self._authenticated = False
        self._cooldown_until: float | None = None

    def ensure_ready(self) -> InstagrapiClient:
        if self._authenticated and self._client is not None:
            return self._client
        if self._cooldown_until is not None:
            if self._clock() < self._cooldown_until:
                logger.warning(
                    "instagram_login_cooldown_active",
                    extra={"retry_after_seconds": self._cooldown_until - self._clock()},
                )
                raise PreviewUnavailable("Instagram session is invalid or expired")
            self._cooldown_until = None
        client = self._client_factory()
        if self._session_path.exists():
            try:
                client.load_settings(self._session_path)
            except (OSError, ValueError):
                pass
        try:
            verification_code = (
                client.totp_generate_code(self._totp_seed) if self._totp_seed else ""
            )
            client.login(self._username, self._password, verification_code=verification_code)
        except (ClientError, ValueError) as error:
            self._cooldown_until = self._clock() + self._cooldown_seconds
            logger.warning(
                "instagram_login_failed",
                extra={
                    "error_type": type(error).__name__,
                    "error": str(error),
                    "cooldown_seconds": self._cooldown_seconds,
                },
            )
            raise PreviewUnavailable("Instagram session is invalid or expired") from error
        try:
            self._session_path.parent.mkdir(parents=True, exist_ok=True)
            client.dump_settings(self._session_path)
        except OSError as error:
            # Login already succeeded — an unwritable session path means this
            # process must log in again next restart, not that this request
            # should fail.
            logger.warning(
                "instagram_session_persist_failed",
                extra={"path": str(self._session_path), "error": str(error)},
            )
        self._client = client
        self._authenticated = True
        logger.info("instagram_login_succeeded", extra={"username": self._username})
        return client

    def invalidate(self) -> None:
        self._authenticated = False
        self._cooldown_until = self._clock() + self._cooldown_seconds
        logger.info("instagram_session_invalidated")


class InstagramAdapter:
    name = "instagram"

    def __init__(
        self,
        username: str,
        password: str,
        session_path: Path,
        *,
        totp_seed: str | None = None,
        delay_seconds: float = 0.0,
        client_factory: ClientFactory | None = None,
        fetch_bytes: FetchBytes | None = None,
        sleep: Sleep | None = None,
        session_manager: InstagramSessionManager | None = None,
    ) -> None:
        self._delay_seconds = delay_seconds
        self._fetch_bytes = fetch_bytes or self._default_fetch_bytes
        self._sleep = sleep or asyncio.sleep
        self._session = session_manager or InstagramSessionManager(
            username,
            password,
            session_path,
            client_factory=client_factory or self._default_client_factory,
            totp_seed=totp_seed,
        )

    @staticmethod
    def _default_client_factory() -> InstagrapiClient:
        from instagrapi import Client

        return Client()

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

    async def _load(self, source: InstagramSource) -> tuple[list[MediaNode], str, str | None]:
        if source.kind == "post":
            return await asyncio.to_thread(self._load_post_sync, source.shortcode)
        if source.kind == "highlight":
            return await asyncio.to_thread(self._load_highlight_sync, source.highlight_id)
        return await asyncio.to_thread(self._load_story_sync, source.username, source.story_pk)

    def _load_post_sync(self, shortcode: str) -> tuple[list[MediaNode], str, str | None]:
        client = self._session.ensure_ready()
        try:
            pk = client.media_pk_from_code(shortcode)
            media = client.media_info(pk)
        except NotFoundError as error:
            raise PreviewUnavailable("Post not found or not public") from error
        except (LoginRequired, ChallengeRequired, TwoFactorRequired) as error:
            self._session.invalidate()
            raise PreviewUnavailable("Instagram session is invalid or expired") from error
        except (PleaseWaitFewMinutes, RateLimitError) as error:
            raise PreviewUnavailable("Instagram rate limit reached, try later") from error
        except ClientError as error:
            raise PreviewUnavailable("The provider metadata could not be loaded") from error
        nodes = self._media_nodes(media)
        return nodes, self._title(media), media.user.username

    def _load_highlight_sync(self, highlight_id: str) -> tuple[list[MediaNode], str, str | None]:
        client = self._session.ensure_ready()
        try:
            highlight = client.highlight_info(highlight_id)
        except NotFoundError as error:
            raise ProviderContentUnavailable(
                "This highlight is unavailable or was removed"
            ) from error
        except (LoginRequired, ChallengeRequired, TwoFactorRequired) as error:
            self._session.invalidate()
            raise PreviewUnavailable("Instagram session is invalid or expired") from error
        except (PleaseWaitFewMinutes, RateLimitError) as error:
            raise PreviewUnavailable("Instagram rate limit reached, try later") from error
        except ClientError as error:
            raise PreviewUnavailable("The provider metadata could not be loaded") from error
        if not highlight.items:
            raise ProviderContentUnavailable("This highlight is unavailable or was removed")
        nodes = [self._story_node(item) for item in highlight.items]
        return nodes, highlight.title or "Highlight", highlight.user.username

    def _load_story_sync(
        self, username: str, story_pk: str | None
    ) -> tuple[list[MediaNode], str, str | None]:
        client = self._session.ensure_ready()
        try:
            user_id = client.user_id_from_username(username)
        except NotFoundError as error:
            raise ProviderContentUnavailable("This account could not be found") from error
        except (LoginRequired, ChallengeRequired, TwoFactorRequired) as error:
            self._session.invalidate()
            raise PreviewUnavailable("Instagram session is invalid or expired") from error
        except (PleaseWaitFewMinutes, RateLimitError) as error:
            raise PreviewUnavailable("Instagram rate limit reached, try later") from error
        except ClientError as error:
            raise ProviderContentUnavailable("This account's stories are not accessible") from error

        try:
            stories = client.user_stories(user_id)
        except (LoginRequired, ChallengeRequired, TwoFactorRequired) as error:
            self._session.invalidate()
            raise PreviewUnavailable("Instagram session is invalid or expired") from error
        except (PleaseWaitFewMinutes, RateLimitError) as error:
            raise PreviewUnavailable("Instagram rate limit reached, try later") from error
        except ClientError as error:
            raise ProviderContentUnavailable("This account's stories are not accessible") from error

        if not stories:
            raise ProviderContentUnavailable("No active stories, or they have expired")
        if story_pk is not None:
            stories = [item for item in stories if str(item.pk) == story_pk]
            if not stories:
                raise ProviderContentUnavailable(
                    "This story has expired or is no longer available"
                )
        nodes = [self._story_node(item) for item in stories]
        return nodes, f"Story by {username}", username

    @staticmethod
    def _media_nodes(media: Media) -> list[MediaNode]:
        if media.resources:
            return [InstagramAdapter._resource_node(r) for r in media.resources]
        return [InstagramAdapter._single_media_node(media)]

    @staticmethod
    def _resource_node(resource: Resource) -> MediaNode:
        is_video = bool(resource.video_url)
        thumbnail = str(resource.thumbnail_url)
        return MediaNode(
            is_video=is_video,
            download_url=str(resource.video_url) if is_video else thumbnail,
            thumbnail_url=thumbnail,
            width=None,
            height=None,
            duration_seconds=None,
        )

    @staticmethod
    def _story_node(story: Story) -> MediaNode:
        is_video = bool(story.video_url)
        thumbnail = str(story.thumbnail_url)
        return MediaNode(
            is_video=is_video,
            download_url=str(story.video_url) if is_video else thumbnail,
            thumbnail_url=thumbnail,
            width=None,
            height=None,
            duration_seconds=story.video_duration if is_video else None,
        )

    @staticmethod
    def _single_media_node(media: Media) -> MediaNode:
        is_video = bool(media.video_url)
        thumbnail = str(media.thumbnail_url)
        dims = media.dimensions
        return MediaNode(
            is_video=is_video,
            download_url=str(media.video_url) if is_video else thumbnail,
            thumbnail_url=thumbnail,
            width=dims.width if dims else None,
            height=dims.height if dims else None,
            duration_seconds=media.video_duration if is_video else None,
        )

    @staticmethod
    def _title(media: Media) -> str:
        text = (media.caption_text or "").strip()
        if text:
            return text.splitlines()[0][:120]
        username = media.user.username if media.user else None
        return f"Post by {username}" if username else "Instagram post"

    @staticmethod
    def _media_item(index: int, node: MediaNode) -> dict[str, Any]:
        duration = node.duration_seconds
        return {
            "index": index,
            "type": "video" if node.is_video else "image",
            "thumbnail": node.thumbnail_url,
            "width": node.width,
            "height": node.height,
            "duration_seconds": int(duration) if duration is not None else None,
        }

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
            extension = "mp4" if node.is_video else "jpg"
            destination = output_directory / f"{job.id}_{index}.{extension}"
            data = await self._fetch_bytes(node.download_url)
            destination.write_bytes(data)
            paths.append(destination)
            await progress_callback((position + 1) / len(selection) * 100)
            if position + 1 < len(selection) and self._delay_seconds:
                await self._sleep(self._delay_seconds)
        return paths

    async def _default_fetch_bytes(self, url: str) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        return await asyncio.to_thread(self._read_bytes, request)

    @staticmethod
    def _read_bytes(request: urllib.request.Request) -> bytes:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()
