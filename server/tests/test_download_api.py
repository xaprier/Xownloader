from fastapi.testclient import TestClient

from xownloader_server.main import app

client = TestClient(app)


def test_unknown_download_returns_not_found() -> None:
    response = client.get("/api/v1/downloads/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404


def test_non_youtube_download_is_rejected() -> None:
    response = client.post(
        "/api/v1/downloads",
        json={"source_url": "https://example.com/video", "output_format": "mp4"},
    )

    assert response.status_code == 400
    assert "Only YouTube" in response.json()["detail"]


def test_media_selection_is_rejected_for_youtube() -> None:
    response = client.post(
        "/api/v1/downloads",
        json={
            "source_url": "https://youtu.be/example",
            "output_format": "mp4",
            "media_selection": [0, 1],
        },
    )

    assert response.status_code == 400
    assert "Media selection is only valid for Instagram" in response.json()["detail"]
