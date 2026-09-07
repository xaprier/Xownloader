import pytest

from xownloader_server.errors import PolicyViolation, PreviewUnavailable
from xownloader_server.instagram import (
    InstagramAdapter,
    InstagramApiError,
    InstagramSource,
    parse_source,
    shortcode_from_url,
    shortcode_to_pk,
)
from xownloader_server.models import DownloadJob

_PHOTO = {
    "items": [
        {
            "code": "Cphoto",
            "media_type": 1,
            "taken_at": 1700000000,
            "user": {"username": "nasa", "full_name": "NASA"},
            "caption": {"text": "Hello world\nsecond line"},
            "image_versions2": {
                "candidates": [
                    {"url": "https://cdn.example/small.jpg", "width": 320, "height": 320},
                    {"url": "https://cdn.example/big.jpg", "width": 1080, "height": 1080},
                ]
            },
            "carousel_media": None,
        }
    ]
}

_VIDEO = {
    "items": [
        {
            "code": "Cvideo",
            "media_type": 2,
            "taken_at": 1700000001,
            "user": {"username": "nasa", "full_name": "NASA"},
            "caption": {"text": "Launch"},
            "image_versions2": {
                "candidates": [
                    {"url": "https://cdn.example/cover.jpg", "width": 720, "height": 1280}
                ]
            },
            "video_versions": [
                {"url": "https://cdn.example/video.mp4", "width": 720, "height": 1280}
            ],
            "video_duration": 12.5,
            "carousel_media": None,
        }
    ]
}

_CAROUSEL = {
    "items": [
        {
            "code": "Ccar",
            "media_type": 8,
            "taken_at": 1700000002,
            "user": {"username": "nasa", "full_name": "NASA"},
            "caption": {"text": "Trip"},
            "carousel_media": [
                {
                    "media_type": 1,
                    "image_versions2": {
                        "candidates": [
                            {"url": "https://cdn.example/1.jpg", "width": 1080, "height": 1080}
                        ]
                    },
                },
                {
                    "media_type": 2,
                    "image_versions2": {
                        "candidates": [
                            {"url": "https://cdn.example/2cover.jpg", "width": 720, "height": 720}
                        ]
                    },
                    "video_versions": [
                        {"url": "https://cdn.example/2.mp4", "width": 720, "height": 720}
                    ],
                    "video_duration": 8.0,
                },
                {
                    "media_type": 1,
                    "image_versions2": {
                        "candidates": [
                            {"url": "https://cdn.example/3.jpg", "width": 1080, "height": 1350}
                        ]
                    },
                },
            ],
        }
    ]
}


def _adapter(payload, *, error=None):
    async def fetch_json(path):
        if error is not None:
            raise error
        return payload

    async def fetch_bytes(url):
        return b""

    async def sleep(_seconds):
        return None

    return InstagramAdapter(
        "sessionid=abc; csrftoken=xyz",
        fetch_json=fetch_json,
        fetch_bytes=fetch_bytes,
        sleep=sleep,
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


def test_shortcode_to_pk_is_deterministic():
    assert shortcode_to_pk("B") == 1
    assert shortcode_to_pk("BA") == 64


@pytest.mark.asyncio
async def test_inspect_photo():
    meta = await _adapter(_PHOTO).inspect("https://www.instagram.com/p/Cphoto/")
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
    meta = await _adapter(_VIDEO).inspect("https://www.instagram.com/reel/Cvideo/")
    assert meta["media_items"][0]["type"] == "video"
    assert meta["media_items"][0]["duration_seconds"] == 12
    assert meta["thumbnail"] == "https://cdn.example/cover.jpg"


@pytest.mark.asyncio
async def test_load_dispatches_post_to_media_info():
    adapter = _adapter(_CAROUSEL)
    nodes, title, uploader = await adapter._load(parse_source("https://www.instagram.com/p/Ccar/"))
    assert [n.get("media_type") for n in nodes] == [1, 2, 1]
    assert title == "Trip"
    assert uploader == "nasa"


@pytest.mark.asyncio
async def test_inspect_carousel_enumerates_items():
    meta = await _adapter(_CAROUSEL).inspect("https://www.instagram.com/p/Ccar/")
    assert [m["type"] for m in meta["media_items"]] == ["image", "video", "image"]
    assert [m["index"] for m in meta["media_items"]] == [0, 1, 2]
    assert meta["media_items"][1]["duration_seconds"] == 8
    assert meta["thumbnail"] == "https://cdn.example/1.jpg"


@pytest.mark.asyncio
async def test_inspect_maps_login_error_to_preview_unavailable():
    adapter = _adapter(None, error=InstagramApiError(403, "login_required"))
    with pytest.raises(PreviewUnavailable, match="session is invalid"):
        await adapter.inspect("https://www.instagram.com/p/Cphoto/")


@pytest.mark.asyncio
async def test_inspect_maps_rate_limit_error():
    adapter = _adapter(None, error=InstagramApiError(429, "wait"))
    with pytest.raises(PreviewUnavailable, match="rate limit"):
        await adapter.inspect("https://www.instagram.com/p/Cphoto/")


@pytest.mark.asyncio
async def test_inspect_maps_not_found_error():
    adapter = _adapter(None, error=InstagramApiError(404, "missing"))
    with pytest.raises(PreviewUnavailable, match="not found"):
        await adapter.inspect("https://www.instagram.com/p/Cphoto/")


@pytest.mark.asyncio
async def test_inspect_maps_400_media_unavailable_to_not_found():
    # Instagram returns HTTP 400 for a deleted / private / bad media id.
    adapter = _adapter(
        None,
        error=InstagramApiError(400, '{"message":"Media not found or unavailable"}'),
    )
    with pytest.raises(PreviewUnavailable, match="not found or not public"):
        await adapter.inspect("https://www.instagram.com/p/Cphoto/")


def _download_adapter(payload=_CAROUSEL, byte_body=None):
    async def fetch_json(path):
        return payload

    async def fetch_bytes(url):
        return byte_body(url) if byte_body else b"x"

    async def sleep(_seconds):
        return None

    return InstagramAdapter(
        "sessionid=abc; csrftoken=xyz",
        fetch_json=fetch_json,
        fetch_bytes=fetch_bytes,
        sleep=sleep,
    )


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
    adapter = _download_adapter(byte_body=lambda url: b"bytes:" + url.encode())
    job = _carousel_job()
    progress = []
    paths = await adapter.download(job, tmp_path, _record(progress))

    assert [p.name for p in paths] == [
        f"{job.id}_0.jpg",
        f"{job.id}_1.mp4",
        f"{job.id}_2.jpg",
    ]
    assert paths[0].read_bytes() == b"bytes:https://cdn.example/1.jpg"
    assert paths[1].read_bytes() == b"bytes:https://cdn.example/2.mp4"
    assert progress[-1] == 100
    assert job.title == "Trip"


@pytest.mark.asyncio
async def test_download_only_selected_indices(tmp_path):
    adapter = _download_adapter()
    job = _carousel_job(media_selection=[0, 2])
    paths = await adapter.download(job, tmp_path, _record([]))
    assert [p.name for p in paths] == [f"{job.id}_0.jpg", f"{job.id}_2.jpg"]


@pytest.mark.asyncio
async def test_download_rejects_out_of_range_selection(tmp_path):
    adapter = _download_adapter()
    job = _carousel_job(media_selection=[0, 9])
    with pytest.raises(RuntimeError, match="media item 9"):
        await adapter.download(job, tmp_path, _record([]))


_HIGHLIGHT = {
    "reels_media": [
        {
            "id": "highlight:18107691199400742",
            "title": "Summer",
            "user": {"username": "nbakolej"},
            "items": [
                {
                    "pk": "111",
                    "media_type": 1,
                    "image_versions2": {
                        "candidates": [
                            {"url": "https://cdn.example/h1.jpg", "width": 1080, "height": 1920}
                        ]
                    },
                },
                {
                    "pk": "222",
                    "media_type": 2,
                    "image_versions2": {
                        "candidates": [
                            {"url": "https://cdn.example/h2c.jpg", "width": 720, "height": 1280}
                        ]
                    },
                    "video_versions": [
                        {"url": "https://cdn.example/h2.mp4", "width": 720, "height": 1280}
                    ],
                    "video_duration": 5.0,
                },
            ],
        }
    ]
}

_HIGHLIGHT_URL_STR = "https://www.instagram.com/stories/highlights/18107691199400742/"


@pytest.mark.asyncio
async def test_inspect_highlight_enumerates_items():
    meta = await _adapter(_HIGHLIGHT).inspect(_HIGHLIGHT_URL_STR)
    assert meta["title"] == "Summer"
    assert meta["uploader"] == "nbakolej"
    assert [m["type"] for m in meta["media_items"]] == ["image", "video"]
    assert meta["media_items"][1]["duration_seconds"] == 5


@pytest.mark.asyncio
async def test_download_highlight_selected_items(tmp_path):
    adapter = _download_adapter(payload=_HIGHLIGHT)
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
    from xownloader_server.errors import ProviderContentUnavailable

    adapter = _adapter({"reels_media": []})
    with pytest.raises(ProviderContentUnavailable, match="highlight is unavailable"):
        await adapter.inspect(_HIGHLIGHT_URL_STR)


_STORY_REEL = {
    "reels_media": [
        {
            "id": "38074396807",
            "user": {"username": "nbakolej"},
            "items": [
                {
                    "pk": "3980885535123917366",
                    "media_type": 1,
                    "image_versions2": {
                        "candidates": [
                            {"url": "https://cdn.example/s1.jpg", "width": 1080, "height": 1920}
                        ]
                    },
                },
                {
                    "pk": "3980885535123917999",
                    "media_type": 2,
                    "image_versions2": {
                        "candidates": [
                            {"url": "https://cdn.example/s2c.jpg", "width": 720, "height": 1280}
                        ]
                    },
                    "video_versions": [
                        {"url": "https://cdn.example/s2.mp4", "width": 720, "height": 1280}
                    ],
                    "video_duration": 9.0,
                },
            ],
        }
    ]
}
_PROFILE = {"user": {"pk": "38074396807", "username": "nbakolej"}}
_STORY_ALL = "https://www.instagram.com/stories/nbakolej/"
_STORY_ONE = "https://www.instagram.com/stories/nbakolej/3980885535123917366/"


def _story_adapter(*, profile=_PROFILE, reel=_STORY_REEL, profile_error=None):
    calls = {"profile": 0, "reels": 0, "profile_path": None}

    async def fetch_json(path):
        if "usernameinfo" in path:
            calls["profile"] += 1
            calls["profile_path"] = path
            if profile_error is not None:
                raise profile_error
            return profile
        if "reels_media" in path:
            calls["reels"] += 1
            return reel
        raise AssertionError(f"unexpected path {path}")

    async def fetch_bytes(url):
        return b"s"

    async def sleep(_seconds):
        return None

    adapter = InstagramAdapter(
        "sessionid=abc; csrftoken=xyz",
        fetch_json=fetch_json,
        fetch_bytes=fetch_bytes,
        sleep=sleep,
    )
    return adapter, calls


@pytest.mark.asyncio
async def test_inspect_story_all_active_items():
    adapter, _ = _story_adapter()
    meta = await adapter.inspect(_STORY_ALL)
    assert meta["title"] == "Story by nbakolej"
    assert meta["uploader"] == "nbakolej"
    assert [m["type"] for m in meta["media_items"]] == ["image", "video"]


@pytest.mark.asyncio
async def test_inspect_story_single_item_filters_by_pk():
    adapter, _ = _story_adapter()
    meta = await adapter.inspect(_STORY_ONE)
    assert [m["index"] for m in meta["media_items"]] == [0]
    assert meta["media_items"][0]["type"] == "image"


@pytest.mark.asyncio
async def test_story_uid_is_resolved_via_usernameinfo_and_cached():
    adapter, calls = _story_adapter()
    await adapter.inspect(_STORY_ALL)
    await adapter.inspect(_STORY_ALL)
    assert calls["profile"] == 1
    assert calls["reels"] == 2
    assert "/api/v1/users/nbakolej/usernameinfo/" in calls["profile_path"]


@pytest.mark.asyncio
async def test_inspect_story_expired_raises_content_unavailable():
    from xownloader_server.errors import ProviderContentUnavailable

    adapter, _ = _story_adapter(reel={"reels_media": []})
    with pytest.raises(ProviderContentUnavailable, match="expired"):
        await adapter.inspect(_STORY_ALL)


@pytest.mark.asyncio
async def test_inspect_story_missing_pk_raises_content_unavailable():
    from xownloader_server.errors import ProviderContentUnavailable

    adapter, _ = _story_adapter()
    with pytest.raises(ProviderContentUnavailable, match="no longer available"):
        await adapter.inspect("https://www.instagram.com/stories/nbakolej/999999/")


@pytest.mark.asyncio
async def test_inspect_story_private_account_raises_content_unavailable():
    from xownloader_server.errors import ProviderContentUnavailable

    adapter, _ = _story_adapter(profile_error=InstagramApiError(404, "not found"))
    with pytest.raises(ProviderContentUnavailable, match="not accessible"):
        await adapter.inspect(_STORY_ALL)


@pytest.mark.asyncio
async def test_inspect_story_session_error_stays_preview_unavailable():
    adapter, _ = _story_adapter(profile_error=InstagramApiError(403, "login_required"))
    with pytest.raises(PreviewUnavailable, match="session is invalid"):
        await adapter.inspect(_STORY_ALL)


@pytest.mark.asyncio
async def test_download_story_single_item(tmp_path):
    adapter, _ = _story_adapter()
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
