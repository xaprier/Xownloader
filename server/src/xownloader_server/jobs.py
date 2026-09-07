import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from xownloader_server.config import Settings
from xownloader_server.errors import JobNotFound, QueueFull
from xownloader_server.metrics import Metrics
from xownloader_server.models import DownloadJob, DownloadRequest, JobArtifact, JobStatus
from xownloader_server.naming import (
    build_artifact_display_name,
    build_display_name,
    media_type_for_extension,
)
from xownloader_server.policy import ServerPolicy
from xownloader_server.providers import ProgressCallback, ProviderAdapter
from xownloader_server.rate_limit import RateLimiter
from xownloader_server.registry import ProviderRegistry, build_registry
from xownloader_server.repository import JobRepository

logger = logging.getLogger(__name__)


class JobManager:
    def __init__(
        self,
        settings: Settings,
        adapter: ProviderAdapter | None = None,
        repository: JobRepository | None = None,
        registry: ProviderRegistry | None = None,
    ) -> None:
        self.settings = settings
        if registry is not None:
            self.registry = registry
        elif adapter is not None:
            self.registry = ProviderRegistry.with_adapters({adapter.name: adapter})
        else:
            self.registry = build_registry(settings)
        self.policy = ServerPolicy(settings, registry=self.registry)
        self.repository = repository or JobRepository(settings.database_path)
        self.metrics = Metrics()
        self.rate_limiter = RateLimiter(settings.rate_limit_requests_per_minute)
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_downloads)
        self._jobs: dict[UUID, DownloadJob] = {job.id: job for job in self.repository.list_jobs()}
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
        provider = self.policy.validate_request(request)
        self.policy.ensure_disk_capacity()
        queued_count = sum(job.status == JobStatus.QUEUED for job in self._jobs.values())
        if queued_count >= self.settings.max_queue_size:
            raise QueueFull("The download queue is full")

        job = DownloadJob(
            source_url=request.source_url,
            provider=provider,
            output_format=request.output_format,
            video_quality=request.video_quality,
            audio_bitrate=request.audio_bitrate,
            media_selection=request.media_selection,
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
            if not job.expires_at or job.expires_at > current_time:
                continue
            targets = list(job.artifacts)
            paths = [Path(a.file_path) for a in targets if a.file_path]
            if not paths and job.file_path:
                paths = [Path(job.file_path)]
            if not paths:
                continue
            failed = False
            for path in paths:
                if path.exists():
                    try:
                        path.unlink()
                        removed += 1
                    except OSError as error:
                        job.cleanup_attempts += 1
                        job.last_cleanup_error = str(error)
                        self.repository.save(job)
                        logger.exception("download_cleanup_failed", extra={"job_id": str(job.id)})
                        failed = True
                        break
            if failed:
                continue
            for artifact in targets:
                artifact.file_path = None
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
                adapter = self.registry.adapter_for(job.provider)
                paths = await adapter.download(
                    job,
                    self.settings.download_directory,
                    self._progress_callback(job),
                )
                if not paths:
                    raise RuntimeError("The provider produced no output files")
                if job.title is None:
                    job.title = self._read_info_title(job)
                job.artifacts = self._build_artifacts(job, paths)
                self._mirror_primary_artifact(job)
                try:
                    for artifact in job.artifacts:
                        self.policy.ensure_file_size(artifact.file_size_bytes or 0)
                except Exception:
                    for artifact in job.artifacts:
                        if artifact.file_path:
                            Path(artifact.file_path).unlink(missing_ok=True)
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

    def _build_artifacts(self, job: DownloadJob, paths: list[Path]) -> list[JobArtifact]:
        total = len(paths)
        artifacts: list[JobArtifact] = []
        for position, path in enumerate(paths):
            resolved = Path(path)
            extension = resolved.suffix.lstrip(".") or "bin"
            index = self._artifact_index(job, position, resolved)
            if total == 1:
                display_name = build_display_name(
                    job.title, job.output_format, fallback=resolved.name
                )
            else:
                display_name = build_artifact_display_name(
                    job.title, extension, index, total, fallback=resolved.name
                )
            artifacts.append(
                JobArtifact(
                    index=index,
                    media_type=media_type_for_extension(extension),
                    file_name=resolved.name,
                    display_name=display_name,
                    file_size_bytes=resolved.stat().st_size,
                    file_path=resolved,
                )
            )
        return artifacts

    @staticmethod
    def _artifact_index(job: DownloadJob, position: int, path: Path) -> int:
        # Instagram names files "<job id>_<original index>.<ext>"; keep that index
        # so the client's selection maps to the same capability URL.
        stem = path.stem
        marker = f"{job.id}_"
        if stem.startswith(marker):
            tail = stem[len(marker) :]
            if tail.isdigit():
                return int(tail)
        return position

    @staticmethod
    def _mirror_primary_artifact(job: DownloadJob) -> None:
        primary = job.artifacts[0]
        job.file_path = primary.file_path
        job.file_name = primary.file_name
        job.display_name = primary.display_name
        job.file_size_bytes = primary.file_size_bytes

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
