from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl


class OutputFormat(StrEnum):
    MP4 = "mp4"
    MP3 = "mp3"


class JobStatus(StrEnum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DownloadRequest(BaseModel):
    source_url: HttpUrl
    output_format: OutputFormat = OutputFormat.MP4
    video_quality: str | None = Field(default=None, pattern=r"^[0-9]{3,4}p$")
    audio_bitrate: str | None = Field(default=None, pattern=r"^[0-9]{2,3}K$")


class PreviewRequest(BaseModel):
    source_url: HttpUrl


class PreviewResponse(BaseModel):
    source_url: HttpUrl
    provider: str
    title: str
    thumbnail: HttpUrl | None = None
    uploader: str | None = None
    duration_seconds: int | None = None
    allowed_output_formats: list[OutputFormat]
    allowed_video_qualities: list[str]
    allowed_audio_bitrates: list[str]


class DownloadJob(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source_url: HttpUrl
    provider: str = "youtube"
    output_format: OutputFormat
    video_quality: str | None = None
    audio_bitrate: str | None = None
    status: JobStatus = JobStatus.QUEUED
    progress_percent: float = 0
    error: str | None = None
    title: str | None = None
    display_name: str | None = None
    file_name: str | None = None
    file_size_bytes: int | None = None
    cleanup_attempts: int = 0
    last_cleanup_error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    expires_at: datetime | None = None
    file_path: Path | None = Field(default=None, exclude=True)