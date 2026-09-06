import asyncio
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from xownloader_server import __version__
from xownloader_server.config import settings
from xownloader_server.errors import (
    InsufficientStorage,
    JobNotFound,
    PolicyViolation,
    QueueFull,
    RateLimitExceeded,
)
from xownloader_server.jobs import JobManager
from xownloader_server.models import DownloadJob, DownloadRequest

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


async def _cleanup_loop() -> None:
    while True:
        await asyncio.sleep(settings.cleanup_interval_minutes * 60)
        job_manager.cleanup_expired()


@asynccontextmanager
async def lifespan(_: FastAPI):
    cleanup_task = asyncio.create_task(_cleanup_loop())
    yield
    cleanup_task.cancel()
    await asyncio.gather(cleanup_task, return_exceptions=True)


job_manager = JobManager(settings)
app.router.lifespan_context = lifespan


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "xownloader-server", "version": __version__}


@app.get("/api/v1/downloads", response_model=list[DownloadJob], tags=["downloads"])
def list_downloads() -> list[DownloadJob]:
    return job_manager.list_jobs()


@app.post(
    "/api/v1/downloads",
    response_model=DownloadJob,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["downloads"],
)
async def create_download(request: Request, payload: DownloadRequest) -> DownloadJob:
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
def get_download(job_id: UUID) -> DownloadJob:
    try:
        return job_manager.get_job(job_id)
    except JobNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Download not found",
        ) from error


@app.delete("/api/v1/downloads/{job_id}", response_model=DownloadJob, tags=["downloads"])
async def cancel_download(job_id: UUID) -> DownloadJob:
    try:
        return await job_manager.cancel_job(job_id)
    except JobNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Download not found",
        ) from error


@app.get("/api/v1/downloads/{job_id}/file", response_class=FileResponse, tags=["downloads"])
def download_file(job_id: UUID) -> FileResponse:
    try:
        job = job_manager.get_job(job_id)
    except JobNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Download not found",
        ) from error
    if job.status.value != "completed" or not job.file_path or not job.file_path.exists():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Download is not ready")
    return FileResponse(path=job.file_path, filename=job.file_name)
