import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from xownloader_server.config import Settings
from xownloader_server.jobs import JobManager
from xownloader_server.models import DownloadJob, JobStatus
from xownloader_server.repository import CURRENT_SCHEMA_VERSION, JobRepository


def test_v1_database_migrates_to_current_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "jobs.db"
    connection = sqlite3.connect(database_path)
    connection.executescript(
        """
        CREATE TABLE jobs (
            id TEXT PRIMARY KEY,
            source_url TEXT NOT NULL,
            provider TEXT NOT NULL,
            output_format TEXT NOT NULL,
            video_quality TEXT,
            audio_bitrate TEXT,
            status TEXT NOT NULL,
            progress_percent REAL NOT NULL,
            error TEXT,
            file_name TEXT,
            file_size_bytes INTEGER,
            created_at TEXT NOT NULL,
            completed_at TEXT,
            expires_at TEXT,
            file_path TEXT
        );
        PRAGMA user_version = 1;
        """
    )
    connection.close()

    repository = JobRepository(database_path)
    version = repository._connection.execute("PRAGMA user_version").fetchone()[0]

    assert version == CURRENT_SCHEMA_VERSION
    columns = {row[1] for row in repository._connection.execute("PRAGMA table_info(jobs)")}
    assert {"cleanup_attempts", "last_cleanup_error", "title", "display_name"} <= columns
    repository.close()


def test_persists_title_and_display_name(tmp_path: Path) -> None:
    from xownloader_server.models import OutputFormat

    repo = JobRepository(tmp_path / "jobs.db")
    job = DownloadJob(
        source_url="https://youtu.be/example",
        output_format=OutputFormat.MP4,
        title="Example Video",
        display_name="Example Video.mp4",
    )
    repo.save(job)
    repo.close()

    reopened = JobRepository(tmp_path / "jobs.db")
    loaded = reopened.get(job.id)
    assert loaded is not None
    assert loaded.title == "Example Video"
    assert loaded.display_name == "Example Video.mp4"
    reopened.close()


def test_cleanup_failure_is_persisted_for_retry(tmp_path: Path) -> None:
    database_path = tmp_path / "jobs.db"
    settings = Settings(
        download_directory=tmp_path,
        database_path=database_path,
        min_free_disk_mb=0,
    )
    repository = JobRepository(database_path)
    blocked_path = tmp_path / "blocked-output"
    blocked_path.mkdir()
    job = DownloadJob.model_validate(
        {
            "source_url": "https://youtu.be/example",
            "output_format": "mp4",
            "status": JobStatus.COMPLETED,
            "file_path": str(blocked_path),
            "expires_at": datetime.now(UTC) - timedelta(minutes=1),
        }
    )
    repository.save(job)
    manager = JobManager(settings, repository=repository)

    assert manager.cleanup_expired() == 0
    persisted = repository.get(job.id)
    assert persisted is not None
    assert persisted.cleanup_attempts == 1
    assert persisted.last_cleanup_error
    assert persisted.file_path == blocked_path
    manager.close()
