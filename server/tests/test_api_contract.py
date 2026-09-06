from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from xownloader_server.auth import AuthService
from xownloader_server.config import Settings
from xownloader_server.main import app


@pytest.fixture
def production_client() -> Iterator[TestClient]:
    previous_auth = app.state.auth
    app.state.auth = AuthService(
        Settings(
            environment="production",
            client_api_token=SecretStr("client-token"),
            admin_api_token=SecretStr("admin-token"),
        )
    )
    try:
        yield TestClient(app)
    finally:
        app.state.auth = previous_auth


def test_client_token_can_read_a_job(production_client: TestClient) -> None:
    response = production_client.get(
        "/api/v1/downloads/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": "Bearer client-token"},
    )

    assert response.status_code == 404


def test_client_token_cannot_read_admin_status(production_client: TestClient) -> None:
    response = production_client.get(
        "/api/v1/admin/status",
        headers={"Authorization": "Bearer client-token"},
    )

    assert response.status_code == 401


def test_admin_token_can_read_admin_status(production_client: TestClient) -> None:
    response = production_client.get(
        "/api/v1/admin/status",
        headers={"Authorization": "Bearer admin-token"},
    )

    assert response.status_code == 200
    assert {"runtime", "jobs", "storage"} <= response.json().keys()


def test_production_route_rejects_missing_token(production_client: TestClient) -> None:
    response = production_client.get(
        "/api/v1/downloads/00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_completed_file_downloads_without_auth_and_uses_display_name(
    production_client: TestClient, tmp_path
) -> None:
    from xownloader_server.main import job_manager
    from xownloader_server.models import DownloadJob, JobStatus, OutputFormat

    media = tmp_path / "opaque.mp4"
    media.write_bytes(b"movie bytes")
    job = DownloadJob(
        source_url="https://youtu.be/example",
        output_format=OutputFormat.MP4,
        status=JobStatus.COMPLETED,
        title="My Great Video",
        display_name="My Great Video.mp4",
        file_name="opaque.mp4",
        file_path=media,
    )
    job_manager._jobs[job.id] = job
    try:
        from urllib.parse import unquote

        resp = production_client.get(f"/api/v1/downloads/{job.id}/file")
        assert resp.status_code == 200
        assert "My Great Video.mp4" in unquote(resp.headers["content-disposition"])
        assert resp.content == b"movie bytes"

        nested = production_client.get(
            f"/api/v1/downloads/{job.id}/file/whatever-name.mp4"
        )
        assert nested.status_code == 200
        assert nested.content == b"movie bytes"

        missing = production_client.get(
            "/api/v1/downloads/00000000-0000-0000-0000-000000000000/file"
        )
        assert missing.status_code == 404
    finally:
        job_manager._jobs.pop(job.id, None)
