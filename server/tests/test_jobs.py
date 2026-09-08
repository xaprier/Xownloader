import json
from pathlib import Path

import pytest

from xownloader_server.config import Settings
from xownloader_server.jobs import JobManager
from xownloader_server.models import DownloadRequest, JobStatus


class FakeAdapter:
    name = "youtube"

    async def download(self, job, output_directory: Path, progress_callback) -> list[Path]:
        await progress_callback(25)
        output_directory.mkdir(parents=True, exist_ok=True)
        output_path = output_directory / f"{job.id}.mp4"
        output_path.write_bytes(b"test media")
        await progress_callback(100)
        return [output_path]


class InfoJsonAdapter:
    name = "youtube"

    async def download(self, job, output_directory: Path, progress_callback) -> list[Path]:
        output_directory.mkdir(parents=True, exist_ok=True)
        (output_directory / f"{job.id}.info.json").write_text(
            json.dumps({"title": "My Great Video"})
        )
        output_path = output_directory / f"{job.id}.mp4"
        output_path.write_bytes(b"test media")
        await progress_callback(100)
        return [output_path]


class CarouselAdapter:
    name = "instagram"

    async def download(self, job, output_directory: Path, progress_callback) -> list[Path]:
        output_directory.mkdir(parents=True, exist_ok=True)
        job.title = "Trip to Rome"
        paths = []
        for index in job.media_selection or [0, 1, 2]:
            path = output_directory / f"{job.id}_{index}.jpg"
            path.write_bytes(b"img-" + str(index).encode())
            paths.append(path)
        await progress_callback(100)
        return paths


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
    assert completed_job.progress_percent == 100
    assert completed_job.file_size_bytes == len(b"test media")
    assert completed_job.expires_at is not None

    restarted_manager = JobManager(settings, adapter=FakeAdapter())
    persisted_job = restarted_manager.get_job(job.id)
    assert persisted_job.status == JobStatus.COMPLETED
    assert persisted_job.file_name == completed_job.file_name

    removed = manager.cleanup_expired(completed_job.expires_at)
    assert removed == 1
    assert completed_job.file_path is None


@pytest.mark.asyncio
async def test_carousel_job_produces_one_artifact_per_selected_index(tmp_path: Path) -> None:
    from pydantic import SecretStr

    settings = Settings(
        download_directory=tmp_path,
        database_path=tmp_path / "jobs.db",
        min_free_disk_mb=0,
        retention_hours=12,
        max_file_size_mb=1,
        instagram_username="nasa",
        instagram_password=SecretStr("hunter2"),
    )
    manager = JobManager(settings, adapter=CarouselAdapter())
    job = await manager.create_job(
        DownloadRequest.model_validate(
            {
                "source_url": "https://www.instagram.com/p/Cxxxx/",
                "media_selection": [0, 2],
            }
        ),
        client_key="test-client",
    )
    await manager._tasks[job.id]

    completed = manager.get_job(job.id)
    assert completed.status == JobStatus.COMPLETED
    assert [a.index for a in completed.artifacts] == [0, 2]
    assert completed.artifacts[0].display_name == "Trip to Rome (1).jpg"
    assert completed.artifacts[1].display_name == "Trip to Rome (3).jpg"
    assert completed.file_name == completed.artifacts[0].file_name
    assert completed.provider == "instagram"

    removed = manager.cleanup_expired(completed.expires_at)
    assert removed == 2
    assert manager.get_job(job.id).artifacts[0].file_path is None
    manager.close()


@pytest.mark.asyncio
async def test_job_manager_records_title_and_removes_info_json(tmp_path: Path) -> None:
    settings = Settings(
        download_directory=tmp_path,
        database_path=tmp_path / "jobs.db",
        min_free_disk_mb=0,
        retention_hours=12,
        max_file_size_mb=1,
    )
    manager = JobManager(settings, adapter=InfoJsonAdapter())
    job = await manager.create_job(
        DownloadRequest.model_validate({"source_url": "https://youtu.be/example"}),
        client_key="test-client",
    )
    await manager._tasks[job.id]

    completed = manager.get_job(job.id)
    assert completed.title == "My Great Video"
    assert completed.display_name == "My Great Video.mp4"
    assert not (tmp_path / f"{job.id}.info.json").exists()
    manager.close()


@pytest.mark.asyncio
async def test_job_manager_display_name_falls_back_without_info_json(
    tmp_path: Path,
) -> None:
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

    completed = manager.get_job(job.id)
    assert completed.title is None
    assert completed.display_name == completed.file_name
    manager.close()
