# Xownloader Server

The server is a FastAPI application. It owns URL validation, `yt-dlp` execution, job
state, file delivery, and retention cleanup. YouTube is the first provider; provider
adapters keep future integrations such as Instagram outside the shared API models.

## API resources

- `GET /health` checks service availability.
- `POST /api/v1/downloads` validates a YouTube request and queues a job.
- `GET /api/v1/downloads` lists in-memory job state.
- `GET /api/v1/downloads/{id}` returns job status, progress, and retention metadata.
- `DELETE /api/v1/downloads/{id}` cancels a queued or active job.
- `GET /api/v1/downloads/{id}/file` returns a completed file.

The API enforces a configurable request rate limit, queue size, concurrent download
count, output format and bitrate/quality allowlist, maximum file size, and minimum free
disk space. Job metadata is stored in SQLite at `XOWNLOADER_DATABASE_PATH`, so status and
retention metadata survive a server restart. Interrupted active jobs are marked failed
for explicit client recovery. Completed files receive an expiration time and a server
cleanup task removes them after the configured retention period.

```bash
uv sync
cp .env.example .env
uv run pytest
uv run uvicorn xownloader_server.main:app --reload
```

Copy `.env.example` to `.env` before starting the server. The `XOWNLOADER_*` settings
control capacity, retention, disk boundaries, and output policy without changing code.
