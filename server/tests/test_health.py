from fastapi.testclient import TestClient

from xownloader_server.main import app

client = TestClient(app)


def test_health_returns_service_status() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_reports_runtime_dependencies() -> None:
    response = client.get("/ready")

    assert response.status_code in {200, 503}
    payload = response.json()
    assert "yt_dlp" in payload.get("detail", payload)
    assert "disk_reserve" in payload.get("detail", payload)


def test_metrics_exposes_download_counters() -> None:
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "downloads_created_total" in response.text
