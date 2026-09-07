import asyncio
import shutil
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse

from xownloader_server import __version__
from xownloader_server.auth import AuthService, require_admin_scope, require_client_scope
from xownloader_server.config import settings
from xownloader_server.errors import (
    InsufficientStorage,
    JobNotFound,
    PolicyViolation,
    PreviewUnavailable,
    ProviderContentUnavailable,
    QueueFull,
    RateLimitExceeded,
)
from xownloader_server.jobs import JobManager
from xownloader_server.models import DownloadJob, DownloadRequest, PreviewRequest, PreviewResponse
from xownloader_server.previews import PreviewService
from xownloader_server.registry import build_registry
from xownloader_server.runtime import check_runtime

app = FastAPI(
    title="Xownloader API",
    version=__version__,
    description="Server API for policy-controlled media downloads.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)
app.state.auth = AuthService(settings)


async def _cleanup_loop() -> None:
    while True:
        await asyncio.sleep(settings.cleanup_interval_minutes * 60)
        job_manager.cleanup_expired()


@asynccontextmanager
async def lifespan(_: FastAPI):
    cleanup_task = asyncio.create_task(_cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()
        await asyncio.gather(cleanup_task, return_exceptions=True)
        job_manager.close()


provider_registry = build_registry(settings)
job_manager = JobManager(settings, registry=provider_registry)
preview_service = PreviewService(settings, registry=provider_registry)
app.state.preview_service = preview_service
app.router.lifespan_context = lifespan


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "xownloader-server", "version": __version__}


@app.get("/ready", tags=["system"])
def readiness() -> dict[str, object]:
    runtime = check_runtime(settings)
    if not runtime["ready"]:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=runtime)
    return runtime


@app.get("/metrics", response_class=PlainTextResponse, tags=["system"])
def metrics(_: None = Depends(require_admin_scope)) -> PlainTextResponse:
    return PlainTextResponse(job_manager.metrics.prometheus())


@app.post("/api/v1/previews", response_model=PreviewResponse, tags=["previews"])
async def create_preview(
    request: Request,
    payload: PreviewRequest,
    _: None = Depends(require_client_scope),
) -> PreviewResponse:
    client_key = request.client.host if request.client else "unknown"
    try:
        return await app.state.preview_service.inspect(payload, client_key)
    except PolicyViolation as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except RateLimitExceeded as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(error),
            headers={"Retry-After": "60"},
        ) from error
    except ProviderContentUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=str(error),
        ) from error
    except PreviewUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error


@app.get("/api/v1/downloads", response_model=list[DownloadJob], tags=["downloads"])
def list_downloads(_: None = Depends(require_admin_scope)) -> list[DownloadJob]:
    return job_manager.list_jobs()


@app.get("/api/v1/admin/jobs", response_model=list[DownloadJob], tags=["admin"])
def admin_jobs(_: None = Depends(require_admin_scope)) -> list[DownloadJob]:
    return job_manager.list_jobs()


@app.get("/api/v1/admin/status", tags=["admin"])
def admin_status(_: None = Depends(require_admin_scope)) -> dict[str, object]:
    jobs = job_manager.list_jobs()
    disk = shutil.disk_usage(settings.download_directory)
    return {
        "runtime": check_runtime(settings),
        "jobs": {
            "total": len(jobs),
            "queued": sum(job.status.value == "queued" for job in jobs),
            "downloading": sum(job.status.value == "downloading" for job in jobs),
            "completed": sum(job.status.value == "completed" for job in jobs),
            "failed": sum(job.status.value == "failed" for job in jobs),
        },
        "storage": {"free_bytes": disk.free, "total_bytes": disk.total},
    }


@app.post(
    "/api/v1/downloads",
    response_model=DownloadJob,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["downloads"],
)
async def create_download(
    request: Request,
    payload: DownloadRequest,
    _: None = Depends(require_client_scope),
) -> DownloadJob:
    client_key = request.client.host if request.client else "unknown"
    try:
        return await job_manager.create_job(payload, client_key)
    except PolicyViolation as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except RateLimitExceeded as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(error),
            headers={"Retry-After": "60"},
        ) from error
    except QueueFull as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except InsufficientStorage as error:
        raise HTTPException(status_code=507, detail=str(error)) from error


@app.get("/api/v1/downloads/{job_id}", response_model=DownloadJob, tags=["downloads"])
def get_download(job_id: UUID, _: None = Depends(require_client_scope)) -> DownloadJob:
    try:
        return job_manager.get_job(job_id)
    except JobNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Download not found",
        ) from error


@app.delete("/api/v1/downloads/{job_id}", response_model=DownloadJob, tags=["downloads"])
async def cancel_download(
    job_id: UUID,
    _: None = Depends(require_client_scope),
) -> DownloadJob:
    try:
        return await job_manager.cancel_job(job_id)
    except JobNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Download not found",
        ) from error


def _download_response(job_id: UUID, index: int = 0) -> FileResponse:
    try:
        job = job_manager.get_job(job_id)
    except JobNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Download not found",
        ) from error
    if job.status.value != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Download is not ready")
    artifact = next((item for item in job.artifacts if item.index == index), None)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media item not found")
    if not artifact.file_path or not artifact.file_path.exists():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Download is not ready")
    return FileResponse(
        path=artifact.file_path,
        filename=artifact.display_name or artifact.file_name,
    )


@app.get("/api/v1/downloads/{job_id}/file", response_class=FileResponse, tags=["downloads"])
def download_file(job_id: UUID) -> FileResponse:
    # Unauthenticated: the unguessable job id is the capability, bounded by retention.
    return _download_response(job_id)


@app.get(
    "/api/v1/downloads/{job_id}/file/{filename}",
    response_class=FileResponse,
    tags=["downloads"],
)
def download_file_named(job_id: UUID, filename: str) -> FileResponse:
    # `filename` is decorative so downloaders save a friendly name; its value is ignored.
    return _download_response(job_id)


@app.get(
    "/api/v1/downloads/{job_id}/media/{index}",
    response_class=FileResponse,
    tags=["downloads"],
)
def download_media(job_id: UUID, index: int) -> FileResponse:
    return _download_response(job_id, index)


@app.get(
    "/api/v1/downloads/{job_id}/media/{index}/{filename}",
    response_class=FileResponse,
    tags=["downloads"],
)
def download_media_named(job_id: UUID, index: int, filename: str) -> FileResponse:
    # `filename` is decorative; the artifact is served by index.
    return _download_response(job_id, index)
