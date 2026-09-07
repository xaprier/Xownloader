from pathlib import Path

from fastapi.testclient import TestClient

from xownloader_server.main import app, job_manager
from xownloader_server.models import DownloadJob, JobArtifact, JobStatus, OutputFormat

client = TestClient(app)


def _completed_carousel_job(tmp_path: Path) -> DownloadJob:
    first = tmp_path / "a_0.jpg"
    first.write_bytes(b"one")
    third = tmp_path / "a_2.mp4"
    third.write_bytes(b"three")
    return DownloadJob(
        source_url="https://www.instagram.com/p/Cxxxx/",
        provider="instagram",
        output_format=OutputFormat.MP4,
        status=JobStatus.COMPLETED,
        title="Trip",
        file_name=first.name,
        file_path=first,
        display_name="Trip (1).jpg",
        artifacts=[
            JobArtifact(
                index=0,
                media_type="image",
                file_name=first.name,
                display_name="Trip (1).jpg",
                file_size_bytes=3,
                file_path=first,
            ),
            JobArtifact(
                index=2,
                media_type="video",
                file_name=third.name,
                display_name="Trip (3).mp4",
                file_size_bytes=5,
                file_path=third,
            ),
        ],
    )


def test_media_route_serves_artifact_by_index(tmp_path: Path) -> None:
    job = _completed_carousel_job(tmp_path)
    job_manager._jobs[job.id] = job
    try:
        first = client.get(f"/api/v1/downloads/{job.id}/media/0")
        assert first.status_code == 200
        assert first.content == b"one"

        third = client.get(f"/api/v1/downloads/{job.id}/media/2/Trip%20(3).mp4")
        assert third.status_code == 200
        assert third.content == b"three"
        from urllib.parse import unquote

        assert "Trip (3).mp4" in unquote(third.headers["content-disposition"])
    finally:
        job_manager._jobs.pop(job.id, None)


def test_media_route_unknown_index_is_not_found(tmp_path: Path) -> None:
    job = _completed_carousel_job(tmp_path)
    job_manager._jobs[job.id] = job
    try:
        response = client.get(f"/api/v1/downloads/{job.id}/media/5")
        assert response.status_code == 404
    finally:
        job_manager._jobs.pop(job.id, None)


def test_legacy_file_route_still_serves_primary(tmp_path: Path) -> None:
    job = _completed_carousel_job(tmp_path)
    job_manager._jobs[job.id] = job
    try:
        response = client.get(f"/api/v1/downloads/{job.id}/file")
        assert response.status_code == 200
        assert response.content == b"one"
    finally:
        job_manager._jobs.pop(job.id, None)
