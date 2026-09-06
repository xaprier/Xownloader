from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from xownloader_server.config import Settings
from xownloader_server.main import app
from xownloader_server.models import PreviewRequest
from xownloader_server.previews import PreviewService


class FakePreviewAdapter:
    async def inspect(self, source_url):
        return {
            "title": "Example video",
            "thumbnail": "https://i.ytimg.com/vi/example/maxresdefault.jpg",
            "uploader": "Example channel",
            "duration": 123,
        }


@pytest.mark.asyncio
async def test_preview_returns_metadata_and_policy_options(tmp_path: Path) -> None:
    service = PreviewService(
        Settings(download_directory=tmp_path, min_free_disk_mb=0),
        adapter=FakePreviewAdapter(),
    )

    preview = await service.inspect(
        PreviewRequest.model_validate({"source_url": "https://youtu.be/example"}),
        client_key="test-client",
    )

    assert preview.title == "Example video"
    assert preview.uploader == "Example channel"
    assert preview.duration_seconds == 123
    assert "mp4" in preview.allowed_output_formats
    assert "mp3" in preview.allowed_output_formats
    assert "720p" in preview.allowed_video_qualities


def test_preview_rejects_non_youtube_url() -> None:
    response = TestClient(app).post(
        "/api/v1/previews",
        json={"source_url": "https://example.com/video"},
    )

    assert response.status_code == 400
    assert "Only YouTube" in response.json()["detail"]
