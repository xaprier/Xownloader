import pytest

from xownloader_server.errors import PolicyViolation, PreviewUnavailable
from xownloader_server.instagram import (
    InstagramAdapter,
    InstagramApiError,
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


def test_shortcode_from_url_rejects_profile_and_stories():
    with pytest.raises(PolicyViolation):
        shortcode_from_url("https://www.instagram.com/nasa/")
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
