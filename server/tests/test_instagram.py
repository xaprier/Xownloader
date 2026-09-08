from datetime import datetime, timezone
from pathlib import Path

import pytest
from instagrapi.exceptions import (
    ChallengeRequired,
    LoginRequired,
    MediaNotFound,
    PleaseWaitFewMinutes,
    UserNotFound,
)
from instagrapi.types import Highlight, Media, MediaDimensions, Resource, Story, UserShort

from xownloader_server.errors import PolicyViolation, PreviewUnavailable, ProviderContentUnavailable
from xownloader_server.instagram import (
    InstagramAdapter,
    InstagramSource,
    parse_source,
    shortcode_from_url,
)
from xownloader_server.models import DownloadJob

_NOW = datetime.now(timezone.utc)
_USER = UserShort(pk="1", username="nasa")


def _media(**overrides):
    fields = dict(
        pk="1",
        id="1_1",
        code="Cphoto",
        taken_at=_NOW,
        media_type=1,
        user=_USER,
        like_count=0,
        caption_text="",
        usertags=[],
        sponsor_tags=[],
        thumbnail_url="https://cdn.example/big.jpg",
    )
    fields.update(overrides)
    return Media(**fields)


def _story(**overrides):
    fields = dict(
        pk="111",
        id="111_1",
        code="s1",
        taken_at=_NOW,
        media_type=1,
        user=_USER,
        sponsor_tags=[],
        mentions=[],
        links=[],
        hashtags=[],
        locations=[],
        stickers=[],
        thumbnail_url="https://cdn.example/s1.jpg",
    )
    fields.update(overrides)
    return Story(**fields)


def _highlight(**overrides):
    fields = dict(
        pk="999",
        id="highlight:999",
        latest_reel_media=0,
        cover_media={},
        user=_USER,
        title="Summer",
        created_at=_NOW,
        is_pinned_highlight=False,
        media_count=1,
        items=[],
    )
    fields.update(overrides)
    return Highlight(**fields)


class FakeInstagrapiClient:
    def __init__(
        self,
        *,
        media=None,
        media_error=None,
        user_id="123",
        user_id_error=None,
        stories=None,
        stories_error=None,
        highlight=None,
        highlight_error=None,
    ):
        self._media = media
        self._media_error = media_error
        self._user_id = user_id
        self._user_id_error = user_id_error
        self._stories = stories if stories is not None else []
        self._stories_error = stories_error
        self._highlight = highlight
        self._highlight_error = highlight_error
        self.login_calls = 0

    def load_settings(self, path):
        return None

    def dump_settings(self, path):
        return None

    def login(self, username, password, verification_code=""):
        self.login_calls += 1
        return True

    def totp_generate_code(self, seed):
        return "totp-for-" + seed

    def media_pk_from_code(self, code):
        return "pk-" + code

    def media_info(self, media_pk):
        if self._media_error is not None:
            raise self._media_error
        return self._media

    def user_id_from_username(self, username):
        if self._user_id_error is not None:
            raise self._user_id_error
        return self._user_id

    def user_stories(self, user_id):
        if self._stories_error is not None:
            raise self._stories_error
        return self._stories

    def highlight_info(self, highlight_pk):
        if self._highlight_error is not None:
            raise self._highlight_error
        return self._highlight


class _ReadySession:
    """A session manager stand-in that skips real login/disk I/O entirely —
    InstagramSessionManager's own login/cooldown/persistence behavior is
    covered by test_instagram_session.py; these tests only exercise what
    InstagramAdapter does with an already-authenticated client."""

    def __init__(self, client):
        self._client = client
        self.invalidated = False

    def ensure_ready(self):
        return self._client

    def invalidate(self):
        self.invalidated = True


def _adapter(client, *, fetch_bytes=None, sleep=None, delay_seconds=0.0):
    async def default_fetch_bytes(url):
        return b"x"

    async def default_sleep(_seconds):
        return None

    return InstagramAdapter(
        "nasa",
        "hunter2",
        Path("unused"),  # never touched: session_manager below bypasses it
        delay_seconds=delay_seconds,
        session_manager=_ReadySession(client),
        fetch_bytes=fetch_bytes or default_fetch_bytes,
        sleep=sleep or default_sleep,
    )


def test_shortcode_from_url_accepts_post_reel_tv():
    assert shortcode_from_url("https://www.instagram.com/p/Cabc-1/") == "Cabc-1"
    assert shortcode_from_url("https://instagram.com/reel/Cdef_2/?hl=en") == "Cdef_2"
    assert shortcode_from_url("https://www.instagram.com/tv/Cghi3/") == "Cghi3"


def test_parse_source_classifies_every_url_form():
    assert parse_source("https://www.instagram.com/p/Cabc-1/") == InstagramSource(
        kind="post", shortcode="Cabc-1"
    )
    assert parse_source("https://instagram.com/reel/Cdef_2/?hl=en") == InstagramSource(
        kind="post", shortcode="Cdef_2"
    )
    assert parse_source(
        "https://www.instagram.com/stories/highlights/18107691199400742/"
    ) == InstagramSource(kind="highlight", highlight_id="18107691199400742")
    assert parse_source(
        "https://www.instagram.com/stories/nbakolej/3980885535123917366/"
    ) == InstagramSource(kind="story", username="nbakolej", story_pk="3980885535123917366")
    assert parse_source("https://www.instagram.com/stories/nbakolej/") == InstagramSource(
        kind="story", username="nbakolej"
    )


def test_parse_source_rejects_unsupported_urls():
    for url in (
        "https://www.instagram.com/nasa/",
        "https://www.instagram.com/explore/tags/space/",
        "https://www.instagram.com/stories/",
        "https://example.com/p/abc/",
    ):
        with pytest.raises(PolicyViolation):
            parse_source(url)


def test_shortcode_from_url_still_rejects_non_posts():
    assert shortcode_from_url("https://www.instagram.com/p/Cabc-1/") == "Cabc-1"
    with pytest.raises(PolicyViolation):
        shortcode_from_url("https://www.instagram.com/stories/nasa/12345/")


@pytest.mark.asyncio
async def test_inspect_photo():
    media = _media(
        caption_text="Hello world\nsecond line",
        dimensions=MediaDimensions(width=1080, height=1080),
    )
    meta = await _adapter(FakeInstagrapiClient(media=media)).inspect(
        "https://www.instagram.com/p/Cphoto/"
    )
    assert meta["provider"] == "instagram"
    assert meta["title"] == "Hello world"
    assert meta["uploader"] == "nasa"
    assert meta["thumbnail"] == "https://cdn.example/big.jpg"
    assert meta["media_items"] == [
        {
            "index": 0,
            "type": "image",
            "thumbnail": "https://cdn.example/big.jpg",
            "width": 1080,
            "height": 1080,
            "duration_seconds": None,
        }
    ]


@pytest.mark.asyncio
async def test_inspect_video():
    media = _media(
        code="Cvideo",
        caption_text="Launch",
        media_type=2,
        thumbnail_url="https://cdn.example/cover.jpg",
        video_url="https://cdn.example/video.mp4",
        video_duration=12.5,
        dimensions=MediaDimensions(width=720, height=1280),
    )
    meta = await _adapter(FakeInstagrapiClient(media=media)).inspect("https://www.instagram.com/reel/Cvideo/")
    assert meta["media_items"][0]["type"] == "video"
    assert meta["media_items"][0]["duration_seconds"] == 12
    assert meta["thumbnail"] == "https://cdn.example/cover.jpg"


@pytest.mark.asyncio
async def test_inspect_carousel_enumerates_items():
    r1 = Resource(pk="r1", media_type=1, thumbnail_url="https://cdn.example/1.jpg")
    r2 = Resource(
        pk="r2",
        media_type=2,
        thumbnail_url="https://cdn.example/2cover.jpg",
        video_url="https://cdn.example/2.mp4",
    )
    r3 = Resource(pk="r3", media_type=1, thumbnail_url="https://cdn.example/3.jpg")
    media = _media(code="Ccar", caption_text="Trip", media_type=8, resources=[r1, r2, r3])
    meta = await _adapter(FakeInstagrapiClient(media=media)).inspect("https://www.instagram.com/p/Ccar/")
    assert [m["type"] for m in meta["media_items"]] == ["image", "video", "image"]
    assert [m["index"] for m in meta["media_items"]] == [0, 1, 2]
    assert meta["media_items"][1]["duration_seconds"] is None
    assert meta["thumbnail"] == "https://cdn.example/1.jpg"


@pytest.mark.asyncio
async def test_inspect_maps_login_error_to_preview_unavailable():
    adapter = _adapter(FakeInstagrapiClient(media_error=LoginRequired("nope")))
    with pytest.raises(PreviewUnavailable, match="session is invalid"):
        await adapter.inspect("https://www.instagram.com/p/Cphoto/")
    assert adapter._session.invalidated is True


@pytest.mark.asyncio
async def test_inspect_maps_rate_limit_error():
    adapter = _adapter(FakeInstagrapiClient(media_error=PleaseWaitFewMinutes("wait")))
    with pytest.raises(PreviewUnavailable, match="rate limit"):
        await adapter.inspect("https://www.instagram.com/p/Cphoto/")


@pytest.mark.asyncio
async def test_inspect_maps_not_found_error():
    adapter = _adapter(FakeInstagrapiClient(media_error=MediaNotFound(media_pk="1")))
    with pytest.raises(PreviewUnavailable, match="not found or not public"):
        await adapter.inspect("https://www.instagram.com/p/Cphoto/")


def _download_adapter(client, fetch_bytes=None):
    return _adapter(client, fetch_bytes=fetch_bytes)


def _record(sink):
    async def progress(percent):
        sink.append(percent)

    return progress


def _carousel_job(**extra):
    return DownloadJob.model_validate(
        {
            "source_url": "https://www.instagram.com/p/Ccar/",
            "provider": "instagram",
            "output_format": "mp4",
            **extra,
        }
    )


@pytest.mark.asyncio
async def test_download_all_carousel_items(tmp_path):
    r1 = Resource(pk="r1", media_type=1, thumbnail_url="https://cdn.example/1.jpg")
    r2 = Resource(
        pk="r2",
        media_type=2,
        thumbnail_url="https://cdn.example/2cover.jpg",
        video_url="https://cdn.example/2.mp4",
    )
    r3 = Resource(pk="r3", media_type=1, thumbnail_url="https://cdn.example/3.jpg")
    media = _media(code="Ccar", caption_text="Trip", media_type=8, resources=[r1, r2, r3])

    async def fetch_bytes(url):
        return b"bytes:" + url.encode()

    adapter = _download_adapter(FakeInstagrapiClient(media=media), fetch_bytes=fetch_bytes)
    job = _carousel_job()
    progress = []
    paths = await adapter.download(job, tmp_path, _record(progress))

    assert [p.name for p in paths] == [f"{job.id}_0.jpg", f"{job.id}_1.mp4", f"{job.id}_2.jpg"]
    assert paths[0].read_bytes() == b"bytes:https://cdn.example/1.jpg"
    assert paths[1].read_bytes() == b"bytes:https://cdn.example/2.mp4"
    assert progress[-1] == 100
    assert job.title == "Trip"


@pytest.mark.asyncio
async def test_download_only_selected_indices(tmp_path):
    r1 = Resource(pk="r1", media_type=1, thumbnail_url="https://cdn.example/1.jpg")
    r3 = Resource(pk="r3", media_type=1, thumbnail_url="https://cdn.example/3.jpg")
    media = _media(code="Ccar", media_type=8, resources=[r1, r3])
    adapter = _download_adapter(FakeInstagrapiClient(media=media))
    job = _carousel_job(media_selection=[0])
    paths = await adapter.download(job, tmp_path, _record([]))
    assert [p.name for p in paths] == [f"{job.id}_0.jpg"]


@pytest.mark.asyncio
async def test_download_rejects_out_of_range_selection(tmp_path):
    media = _media(
        code="Ccar",
        media_type=8,
        resources=[Resource(pk="r1", media_type=1, thumbnail_url="https://cdn.example/1.jpg")],
    )
    adapter = _download_adapter(FakeInstagrapiClient(media=media))
    job = _carousel_job(media_selection=[0, 9])
    with pytest.raises(RuntimeError, match="media item 9"):
        await adapter.download(job, tmp_path, _record([]))


_HIGHLIGHT_URL_STR = "https://www.instagram.com/stories/highlights/18107691199400742/"


@pytest.mark.asyncio
async def test_inspect_highlight_enumerates_items():
    s1 = _story(pk="111", thumbnail_url="https://cdn.example/h1.jpg")
    s2 = _story(
        pk="222",
        media_type=2,
        thumbnail_url="https://cdn.example/h2c.jpg",
        video_url="https://cdn.example/h2.mp4",
        video_duration=5.0,
    )
    highlight = _highlight(user=UserShort(pk="9", username="nbakolej"), items=[s1, s2])
    meta = await _adapter(FakeInstagrapiClient(highlight=highlight)).inspect(_HIGHLIGHT_URL_STR)
    assert meta["title"] == "Summer"
    assert meta["uploader"] == "nbakolej"
    assert [m["type"] for m in meta["media_items"]] == ["image", "video"]
    assert meta["media_items"][1]["duration_seconds"] == 5


@pytest.mark.asyncio
async def test_download_highlight_selected_items(tmp_path):
    s1 = _story(pk="111", thumbnail_url="https://cdn.example/h1.jpg")
    s2 = _story(
        pk="222",
        media_type=2,
        thumbnail_url="https://cdn.example/h2c.jpg",
        video_url="https://cdn.example/h2.mp4",
        video_duration=5.0,
    )
    highlight = _highlight(items=[s1, s2])
    adapter = _download_adapter(FakeInstagrapiClient(highlight=highlight))
    job = DownloadJob.model_validate(
        {
            "source_url": _HIGHLIGHT_URL_STR,
            "provider": "instagram",
            "output_format": "mp4",
            "media_selection": [1],
        }
    )
    paths = await adapter.download(job, tmp_path, _record([]))
    assert [p.name for p in paths] == [f"{job.id}_1.mp4"]
    assert job.title == "Summer"


@pytest.mark.asyncio
async def test_inspect_highlight_removed_raises_content_unavailable():
    adapter = _adapter(FakeInstagrapiClient(highlight=_highlight(items=[])))
    with pytest.raises(ProviderContentUnavailable, match="highlight is unavailable"):
        await adapter.inspect(_HIGHLIGHT_URL_STR)


_STORY_ALL = "https://www.instagram.com/stories/nbakolej/"
_STORY_ONE = "https://www.instagram.com/stories/nbakolej/3980885535123917366/"


def _story_items():
    return [
        _story(pk="3980885535123917366", thumbnail_url="https://cdn.example/s1.jpg"),
        _story(
            pk="3980885535123917999",
            media_type=2,
            thumbnail_url="https://cdn.example/s2c.jpg",
            video_url="https://cdn.example/s2.mp4",
            video_duration=9.0,
        ),
    ]


@pytest.mark.asyncio
async def test_inspect_story_all_active_items():
    adapter = _adapter(FakeInstagrapiClient(stories=_story_items()))
    meta = await adapter.inspect(_STORY_ALL)
    assert meta["title"] == "Story by nbakolej"
    assert meta["uploader"] == "nbakolej"
    assert [m["type"] for m in meta["media_items"]] == ["image", "video"]


@pytest.mark.asyncio
async def test_inspect_story_single_item_filters_by_pk():
    adapter = _adapter(FakeInstagrapiClient(stories=_story_items()))
    meta = await adapter.inspect(_STORY_ONE)
    assert [m["index"] for m in meta["media_items"]] == [0]
    assert meta["media_items"][0]["type"] == "image"


@pytest.mark.asyncio
async def test_inspect_story_expired_raises_content_unavailable():
    adapter = _adapter(FakeInstagrapiClient(stories=[]))
    with pytest.raises(ProviderContentUnavailable, match="expired"):
        await adapter.inspect(_STORY_ALL)


@pytest.mark.asyncio
async def test_inspect_story_missing_pk_raises_content_unavailable():
    adapter = _adapter(FakeInstagrapiClient(stories=_story_items()))
    with pytest.raises(ProviderContentUnavailable, match="no longer available"):
        await adapter.inspect("https://www.instagram.com/stories/nbakolej/999999/")


@pytest.mark.asyncio
async def test_inspect_story_private_account_raises_content_unavailable():
    adapter = _adapter(FakeInstagrapiClient(user_id_error=UserNotFound(username="nbakolej")))
    with pytest.raises(ProviderContentUnavailable, match="could not be found"):
        await adapter.inspect(_STORY_ALL)


@pytest.mark.asyncio
async def test_inspect_story_session_error_stays_preview_unavailable():
    adapter = _adapter(FakeInstagrapiClient(user_id_error=LoginRequired("nope")))
    with pytest.raises(PreviewUnavailable, match="session is invalid"):
        await adapter.inspect(_STORY_ALL)


@pytest.mark.asyncio
async def test_inspect_story_challenge_required_stays_preview_unavailable():
    adapter = _adapter(FakeInstagrapiClient(stories_error=ChallengeRequired("checkpoint")))
    with pytest.raises(PreviewUnavailable, match="session is invalid"):
        await adapter.inspect(_STORY_ALL)


@pytest.mark.asyncio
async def test_download_story_single_item(tmp_path):
    adapter = _adapter(FakeInstagrapiClient(stories=_story_items()))
    job = DownloadJob.model_validate(
        {
            "source_url": _STORY_ONE,
            "provider": "instagram",
            "output_format": "mp4",
        }
    )
    paths = await adapter.download(job, tmp_path, _record([]))
    assert [p.name for p in paths] == [f"{job.id}_0.jpg"]
    assert job.title == "Story by nbakolej"
