from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from xownloader_server.config import Settings
from xownloader_server.main import app
from xownloader_server.models import PreviewRequest
from xownloader_server.previews import PreviewService
from xownloader_server.registry import ProviderRegistry


class FakeYouTubeAdapter:
    name = "youtube"

    async def inspect(self, source_url):
        return {
            "provider": "youtube",
            "title": "Example video",
            "uploader": "Example channel",
            "thumbnail": "https://i.ytimg.com/vi/example/maxresdefault.jpg",
            "duration_seconds": 123,
            "media_items": None,
        }


class FakeInstagramAdapter:
    name = "instagram"

    async def inspect(self, source_url):
        return {
            "provider": "instagram",
            "title": "Trip",
            "uploader": "nasa",
            "thumbnail": "https://cdn.example/1.jpg",
            "duration_seconds": None,
            "media_items": [
                {
                    "index": 0,
                    "type": "image",
                    "thumbnail": "https://cdn.example/1.jpg",
                    "width": 1080,
                    "height": 1080,
                    "duration_seconds": None,
                },
                {
                    "index": 1,
                    "type": "video",
                    "thumbnail": "https://cdn.example/2.jpg",
                    "width": 720,
                    "height": 720,
                    "duration_seconds": 8,
                },
            ],
        }


@pytest.mark.asyncio
async def test_youtube_preview_returns_policy_options_and_no_media_items(tmp_path: Path) -> None:
    service = PreviewService(
        Settings(download_directory=tmp_path, min_free_disk_mb=0),
        registry=ProviderRegistry.with_adapters({"youtube": FakeYouTubeAdapter()}),
    )
    preview = await service.inspect(
        PreviewRequest.model_validate({"source_url": "https://youtu.be/example"}),
        client_key="test-client",
    )
    assert preview.provider == "youtube"
    assert preview.title == "Example video"
    assert preview.duration_seconds == 123
    assert preview.media_items is None
    assert "mp4" in preview.allowed_output_formats
    assert "720p" in preview.allowed_video_qualities


@pytest.mark.asyncio
async def test_instagram_preview_returns_media_items_and_empty_policy_lists(tmp_path: Path) -> None:
    service = PreviewService(
        Settings(
            download_directory=tmp_path,
            min_free_disk_mb=0,
            instagram_cookie=SecretStr("sessionid=abc; csrftoken=xyz"),
        ),
        registry=ProviderRegistry.with_adapters({"instagram": FakeInstagramAdapter()}),
    )
    preview = await service.inspect(
        PreviewRequest.model_validate({"source_url": "https://www.instagram.com/p/Cxxxx/"}),
        client_key="test-client",
    )
    assert preview.provider == "instagram"
    assert [m.index for m in preview.media_items] == [0, 1]
    assert preview.media_items[1].type == "video"
    assert preview.allowed_output_formats == []
    assert preview.allowed_video_qualities == []


def test_preview_rejects_unsupported_host() -> None:
    response = TestClient(app).post(
        "/api/v1/previews",
        json={"source_url": "https://example.com/video"},
    )
    assert response.status_code == 400
    assert "Only YouTube" in response.json()["detail"]


def test_preview_rejects_instagram_when_server_has_no_cookie() -> None:
    response = TestClient(app).post(
        "/api/v1/previews",
        json={"source_url": "https://www.instagram.com/p/Cxxxx/"},
    )
    assert response.status_code == 400
    assert "Instagram is not configured" in response.json()["detail"]


class _UnavailableAdapter:
    name = "instagram"

    async def inspect(self, source_url):
        from xownloader_server.errors import ProviderContentUnavailable

        raise ProviderContentUnavailable("This story has expired or is no longer available")


@pytest.mark.asyncio
async def test_content_unavailable_propagates_from_preview_service(tmp_path: Path) -> None:
    from xownloader_server.errors import ProviderContentUnavailable

    service = PreviewService(
        Settings(download_directory=tmp_path, min_free_disk_mb=0),
        registry=ProviderRegistry.with_adapters({"instagram": _UnavailableAdapter()}),
    )
    with pytest.raises(ProviderContentUnavailable):
        await service.inspect(
            PreviewRequest.model_validate(
                {"source_url": "https://www.instagram.com/stories/nasa/123/"}
            ),
            client_key="k",
        )


def test_preview_route_maps_content_unavailable_to_410(monkeypatch) -> None:
    from xownloader_server import main
    from xownloader_server.errors import ProviderContentUnavailable

    async def _raise(_payload, _client_key):
        raise ProviderContentUnavailable("No active stories, or they have expired")

    monkeypatch.setattr(main.app.state.preview_service, "inspect", _raise)
    response = TestClient(main.app).post(
        "/api/v1/previews",
        json={"source_url": "https://www.instagram.com/stories/nasa/"},
    )
    assert response.status_code == 410
    assert "expired" in response.json()["detail"]
