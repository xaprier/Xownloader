import json
import sqlite3
from datetime import datetime
from pathlib import Path
from threading import Lock
from uuid import UUID

from xownloader_server.models import DownloadJob, JobArtifact
from xownloader_server.naming import media_type_for_extension

CURRENT_SCHEMA_VERSION = 4

_JOB_ARTIFACTS_DDL = """
CREATE TABLE IF NOT EXISTS job_artifacts (
    job_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    media_type TEXT NOT NULL,
    file_name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    file_size_bytes INTEGER,
    file_path TEXT,
    PRIMARY KEY (job_id, idx)
)
"""


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
                self._create_latest_schema()
            else:
                if version < 2:
                    self._connection.execute(
                        "ALTER TABLE jobs ADD COLUMN cleanup_attempts INTEGER NOT NULL DEFAULT 0"
                    )
                    self._connection.execute("ALTER TABLE jobs ADD COLUMN last_cleanup_error TEXT")
                if version < 3:
                    self._connection.execute("ALTER TABLE jobs ADD COLUMN title TEXT")
                    self._connection.execute("ALTER TABLE jobs ADD COLUMN display_name TEXT")
                if version < 4:
                    self._connection.execute("ALTER TABLE jobs ADD COLUMN media_selection TEXT")
                    self._connection.execute(_JOB_ARTIFACTS_DDL)
            self._connection.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")

    def _create_latest_schema(self) -> None:
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
            title TEXT,
            display_name TEXT,
            file_name TEXT,
            file_size_bytes INTEGER,
            created_at TEXT NOT NULL,
            completed_at TEXT,
            expires_at TEXT,
            file_path TEXT,
            cleanup_attempts INTEGER NOT NULL DEFAULT 0,
            last_cleanup_error TEXT,
            media_selection TEXT
            )
            """
        )
        self._connection.execute(_JOB_ARTIFACTS_DDL)

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
            job.title,
            job.display_name,
            job.file_name,
            job.file_size_bytes,
            job.created_at.isoformat(),
            self._serialize_datetime(job.completed_at),
            self._serialize_datetime(job.expires_at),
            str(job.file_path) if job.file_path else None,
            job.cleanup_attempts,
            job.last_cleanup_error,
            json.dumps(job.media_selection) if job.media_selection is not None else None,
        )
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO jobs (
                    id, source_url, provider, output_format, video_quality, audio_bitrate,
                    status, progress_percent, error, title, display_name, file_name,
                    file_size_bytes, created_at, completed_at, expires_at, file_path,
                    cleanup_attempts, last_cleanup_error, media_selection
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status,
                    progress_percent=excluded.progress_percent,
                    error=excluded.error,
                    title=excluded.title,
                    display_name=excluded.display_name,
                    file_name=excluded.file_name,
                    file_size_bytes=excluded.file_size_bytes,
                    completed_at=excluded.completed_at,
                    expires_at=excluded.expires_at,
                    file_path=excluded.file_path,
                    cleanup_attempts=excluded.cleanup_attempts,
                    last_cleanup_error=excluded.last_cleanup_error,
                    media_selection=excluded.media_selection
                """,
                values,
            )
            self._connection.execute("DELETE FROM job_artifacts WHERE job_id = ?", (str(job.id),))
            self._connection.executemany(
                """
                INSERT INTO job_artifacts (
                    job_id, idx, media_type, file_name, display_name,
                    file_size_bytes, file_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        str(job.id),
                        artifact.index,
                        artifact.media_type,
                        artifact.file_name,
                        artifact.display_name,
                        artifact.file_size_bytes,
                        str(artifact.file_path) if artifact.file_path else None,
                    )
                    for artifact in job.artifacts
                ],
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

    def _from_row(self, row: sqlite3.Row) -> DownloadJob:
        raw_selection = row["media_selection"]
        job = DownloadJob.model_validate(
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
                "title": row["title"],
                "display_name": row["display_name"],
                "file_name": row["file_name"],
                "file_size_bytes": row["file_size_bytes"],
                "created_at": row["created_at"],
                "completed_at": row["completed_at"],
                "expires_at": row["expires_at"],
                "file_path": row["file_path"],
                "cleanup_attempts": row["cleanup_attempts"],
                "last_cleanup_error": row["last_cleanup_error"],
                "media_selection": json.loads(raw_selection) if raw_selection else None,
            }
        )
        job.artifacts = self._load_artifacts(row["id"], job)
        return job

    def _load_artifacts(self, job_id: str, job: DownloadJob) -> list[JobArtifact]:
        rows = self._connection.execute(
            "SELECT idx, media_type, file_name, display_name, file_size_bytes, file_path "
            "FROM job_artifacts WHERE job_id = ? ORDER BY idx",
            (job_id,),
        ).fetchall()
        if rows:
            return [
                JobArtifact(
                    index=r["idx"],
                    media_type=r["media_type"],
                    file_name=r["file_name"],
                    display_name=r["display_name"],
                    file_size_bytes=r["file_size_bytes"],
                    file_path=Path(r["file_path"]) if r["file_path"] else None,
                )
                for r in rows
            ]
        if job.file_name or job.file_path:
            name = job.file_name or (job.file_path.name if job.file_path else "download")
            extension = Path(name).suffix.lstrip(".") or "bin"
            return [
                JobArtifact(
                    index=0,
                    media_type=media_type_for_extension(extension),
                    file_name=name,
                    display_name=job.display_name or name,
                    file_size_bytes=job.file_size_bytes,
                    file_path=job.file_path,
                )
            ]
        return []
