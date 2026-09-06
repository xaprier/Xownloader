import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from xownloader_server.config import Settings
from xownloader_server.errors import JobNotFound, QueueFull
from xownloader_server.metrics import Metrics
from xownloader_server.models import DownloadJob, DownloadRequest, JobStatus
from xownloader_server.naming import build_display_name
from xownloader_server.policy import ServerPolicy
from xownloader_server.providers import ProgressCallback, ProviderAdapter, YtDlpAdapter
from xownloader_server.rate_limit import RateLimiter
from xownloader_server.repository import JobRepository

logger = logging.getLogger(__name__)


class JobManager:
    def __init__(
        self,
        settings: Settings,
        adapter: ProviderAdapter | None = None,
        repository: JobRepository | None = None,
    ) -> None:
        self.settings = settings
        self.policy = ServerPolicy(settings)
        self.adapter = adapter or YtDlpAdapter()
        self.repository = repository or JobRepository(settings.database_path)
        self.metrics = Metrics()
        self.rate_limiter = RateLimiter(settings.rate_limit_requests_per_minute)
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_downloads)
        self._jobs: dict[UUID, DownloadJob] = {
            job.id: job for job in self.repository.list_jobs()
        }
        self._tasks: dict[UUID, asyncio.Task[None]] = {}
        self._recover_interrupted_jobs()

    def _recover_interrupted_jobs(self) -> None:
        for job in self._jobs.values():
            if job.status not in {JobStatus.QUEUED, JobStatus.DOWNLOADING}:
                continue
            job.status = JobStatus.FAILED
            job.error = "Download interrupted by a server restart"
            job.completed_at = datetime.now(UTC)
            self.repository.save(job)

    def list_jobs(self) -> list[DownloadJob]:
        return self.repository.list_jobs()

    def get_job(self, job_id: UUID) -> DownloadJob:
        try:
            return self._jobs[job_id]
        except KeyError as error:
            raise JobNotFound from error

    async def create_job(self, request: DownloadRequest, client_key: str) -> DownloadJob:
        self.rate_limiter.check(client_key)
        self.policy.validate_request(request)
        self.policy.ensure_disk_capacity()
        queued_count = sum(job.status == JobStatus.QUEUED for job in self._jobs.values())
        if queued_count >= self.settings.max_queue_size:
            raise QueueFull("The download queue is full")

        job = DownloadJob(
            source_url=request.source_url,
            output_format=request.output_format,
            video_quality=request.video_quality,
            audio_bitrate=request.audio_bitrate,
        )
        self._jobs[job.id] = job
        self.repository.save(job)
        self.metrics.increment("downloads_created_total")
        logger.info("download_queued", extra={"job_id": str(job.id), "provider": job.provider})
        self._tasks[job.id] = asyncio.create_task(self._run(job))
        return job

    async def cancel_job(self, job_id: UUID) -> DownloadJob:
        job = self.get_job(job_id)
        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()
        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.now(UTC)
        self.repository.save(job)
        return job

    def cleanup_expired(self, now: datetime | None = None) -> int:
        current_time = now or datetime.now(UTC)
        removed = 0
        for job in self._jobs.values():
            if not job.expires_at or job.expires_at > current_time or not job.file_path:
                continue
            path = Path(job.file_path)
            if path.exists():
                try:
                    path.unlink()
                    removed += 1
                except OSError as error:
                    job.cleanup_attempts += 1
                    job.last_cleanup_error = str(error)
                    self.repository.save(job)
                    logger.exception("download_cleanup_failed", extra={"job_id": str(job.id)})
                    continue
            job.file_path = None
            job.last_cleanup_error = None
            self.repository.save(job)
        return removed

    def close(self) -> None:
        self.repository.close()

    async def _run(self, job: DownloadJob) -> None:
        try:
            async with self._semaphore:
                job.status = JobStatus.DOWNLOADING
                self.repository.save(job)
                job.file_path = await self.adapter.download(
                    job,
                    self.settings.download_directory,
                    self._progress_callback(job),
                )
                job.file_name = Path(job.file_path).name
                job.file_size_bytes = Path(job.file_path).stat().st_size
                job.title = self._read_info_title(job)
                job.display_name = build_display_name(
                    job.title, job.output_format, fallback=job.file_name
                )
                try:
                    self.policy.ensure_file_size(job.file_size_bytes)
                except Exception:
                    Path(job.file_path).unlink(missing_ok=True)
                    raise
                job.status = JobStatus.COMPLETED
                job.progress_percent = 100
                job.completed_at = datetime.now(UTC)
                job.expires_at = job.completed_at + timedelta(hours=self.settings.retention_hours)
                self.repository.save(job)
                self.metrics.increment("downloads_completed_total")
                logger.info("download_completed", extra={"job_id": str(job.id)})
        except asyncio.CancelledError:
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now(UTC)
            self.repository.save(job)
            self.metrics.increment("downloads_cancelled_total")
            logger.info("download_cancelled", extra={"job_id": str(job.id)})
        except Exception as error:  # noqa: BLE001
            job.status = JobStatus.FAILED
            job.error = str(error)
            job.completed_at = datetime.now(UTC)
            self.repository.save(job)
            self.metrics.increment("downloads_failed_total")
            logger.exception("download_failed", extra={"job_id": str(job.id)})

    def _read_info_title(self, job: DownloadJob) -> str | None:
        info_path = self.settings.download_directory / f"{job.id}.info.json"
        title: str | None = None
        if info_path.exists():
            try:
                data = json.loads(info_path.read_text())
                value = data.get("title")
                title = str(value) if value else None
            except (OSError, ValueError):
                title = None
            finally:
                info_path.unlink(missing_ok=True)
        return title

    def _progress_callback(self, job: DownloadJob) -> ProgressCallback:
        async def update(progress_percent: float) -> None:
            job.progress_percent = max(0, min(progress_percent, 100))
            self.repository.save(job)

        return update