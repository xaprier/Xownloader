import sqlite3
from datetime import datetime
from pathlib import Path
from threading import Lock
from uuid import UUID

from xownloader_server.models import DownloadJob

CURRENT_SCHEMA_VERSION = 2


class JobRepository:
    def __init__(self, database_path: Path) -> None:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(database_path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = Lock()
        self._initialize()

    def _initialize(self) -> None:
        with self._connection:
            version = self._connection.execute("PRAGMA user_version").fetchone()[0]
            if version > CURRENT_SCHEMA_VERSION:
                raise RuntimeError("Database schema is newer than this server version")
            if version == 0:
                self._connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS jobs (
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
                    file_path TEXT,
                    cleanup_attempts INTEGER NOT NULL DEFAULT 0,
                    last_cleanup_error TEXT
                    )
                    """
                )
            if version == 1:
                self._connection.execute(
                    "ALTER TABLE jobs ADD COLUMN cleanup_attempts INTEGER NOT NULL DEFAULT 0"
                )
                self._connection.execute("ALTER TABLE jobs ADD COLUMN last_cleanup_error TEXT")
            self._connection.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")

    def save(self, job: DownloadJob) -> None:
        values = (
            str(job.id),
            str(job.source_url),
            job.provider,
            job.output_format.value,
            job.video_quality,
            job.audio_bitrate,
            job.status.value,
            job.progress_percent,
            job.error,
            job.file_name,
            job.file_size_bytes,
            job.created_at.isoformat(),
            self._serialize_datetime(job.completed_at),
            self._serialize_datetime(job.expires_at),
            str(job.file_path) if job.file_path else None,
            job.cleanup_attempts,
            job.last_cleanup_error,
        )
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO jobs (
                    id, source_url, provider, output_format, video_quality, audio_bitrate,
                    status, progress_percent, error, file_name, file_size_bytes, created_at,
                    completed_at, expires_at, file_path, cleanup_attempts, last_cleanup_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status,
                    progress_percent=excluded.progress_percent,
                    error=excluded.error,
                    file_name=excluded.file_name,
                    file_size_bytes=excluded.file_size_bytes,
                    completed_at=excluded.completed_at,
                    expires_at=excluded.expires_at,
                    file_path=excluded.file_path,
                    cleanup_attempts=excluded.cleanup_attempts,
                    last_cleanup_error=excluded.last_cleanup_error
                """,
                values,
            )

    def get(self, job_id: UUID) -> DownloadJob | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM jobs WHERE id = ?", (str(job_id),)
            ).fetchone()
        return self._from_row(row) if row else None

    def list_jobs(self) -> list[DownloadJob]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC"
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    @staticmethod
    def _serialize_datetime(value: datetime | None) -> str | None:
        return value.isoformat() if value else None

    @staticmethod
    def _from_row(row: sqlite3.Row) -> DownloadJob:
        return DownloadJob.model_validate(
            {
                "id": row["id"],
                "source_url": row["source_url"],
                "provider": row["provider"],
                "output_format": row["output_format"],
                "video_quality": row["video_quality"],
                "audio_bitrate": row["audio_bitrate"],
                "status": row["status"],
                "progress_percent": row["progress_percent"],
                "error": row["error"],
                "file_name": row["file_name"],
                "file_size_bytes": row["file_size_bytes"],
                "created_at": row["created_at"],
                "completed_at": row["completed_at"],
                "expires_at": row["expires_at"],
                "file_path": row["file_path"],
                "cleanup_attempts": row["cleanup_attempts"],
                "last_cleanup_error": row["last_cleanup_error"],
            }
        )
