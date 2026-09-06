from pathlib import Path

import pytest

from xownloader_server.config import Settings
from xownloader_server.jobs import JobManager
from xownloader_server.models import DownloadRequest, JobStatus


class FakeAdapter:
    name = "youtube"

    async def download(self, job, output_directory: Path) -> Path:
        output_path = output_directory / f"{job.id}.mp4"
        output_directory.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"test media")
        return output_path


@pytest.mark.asyncio
async def test_job_manager_completes_and_sets_retention(tmp_path: Path) -> None:
    settings = Settings(
        download_directory=tmp_path,
        database_path=tmp_path / "jobs.db",
        min_free_disk_mb=0,
        retention_hours=12,
        max_file_size_mb=1,
    )
    manager = JobManager(settings, adapter=FakeAdapter())
    job = await manager.create_job(
        DownloadRequest.model_validate({"source_url": "https://youtu.be/example"}),
        client_key="test-client",
    )
    await manager._tasks[job.id]

    completed_job = manager.get_job(job.id)
    assert completed_job.status == JobStatus.COMPLETED
    assert completed_job.file_size_bytes == len(b"test media")
    assert completed_job.expires_at is not None

    restarted_manager = JobManager(settings, adapter=FakeAdapter())
    persisted_job = restarted_manager.get_job(job.id)
    assert persisted_job.status == JobStatus.COMPLETED
    assert persisted_job.file_name == completed_job.file_name

    removed = manager.cleanup_expired(completed_job.expires_at)
    assert removed == 1
    assert completed_job.file_path is None
