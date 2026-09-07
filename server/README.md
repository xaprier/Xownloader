# Xownloader Server

The server is a FastAPI application. It owns URL validation, provider execution, job
state, file delivery, and retention cleanup. A `ProviderRegistry` picks the provider from
the URL host: YouTube through `yt-dlp`, and Instagram (posts, reels, carousels, stories,
highlights) through a direct HTTP adapter that needs `XOWNLOADER_INSTAGRAM_COOKIE`.
Provider adapters stay behind the shared, provider-neutral API models.

## API resources

- `GET /health` checks service availability.
- `GET /ready` checks runtime dependencies, output storage, and disk reserve.
- `GET /metrics` exposes basic Prometheus-compatible job counters.
- `POST /api/v1/previews` inspects a URL without creating a job; returns output options
  for YouTube, or the list of media items for an Instagram carousel, highlight, or story
  set. Returns `410` when an Instagram story or highlight is expired, removed, or empty.
- `POST /api/v1/downloads` validates a request and queues a job; an Instagram request may
  carry `media_selection` (the item indices to download).
- `GET /api/v1/downloads` lists persisted job state.
- `GET /api/v1/downloads/{id}` returns job status, progress, and retention metadata,
  including one `artifacts` entry per output file.
- `DELETE /api/v1/downloads/{id}` cancels a queued or active job.
- `GET /api/v1/downloads/{id}/file` returns the first completed file;
  `GET /api/v1/downloads/{id}/media/{index}` returns one artifact of a multi-item job.
- `GET /api/v1/admin/jobs` lists all jobs for administrators.
- `GET /api/v1/admin/status` exposes runtime, queue, and storage status for administrators.

## Access control

There is no end-user login in the initial design. In development, an unset token keeps
local use simple. In production, clients must send `Authorization: Bearer <client-token>`
and administrators must use the separate `XOWNLOADER_ADMIN_API_TOKEN`. The admin token
also has client scope; the client token cannot access admin endpoints.

The API enforces a configurable request rate limit, queue size, concurrent download
count, output format and bitrate/quality allowlist, maximum file size, and minimum free
disk space. Job metadata is stored in SQLite at `XOWNLOADER_DATABASE_PATH`, so status and
retention metadata survive a server restart. Interrupted active jobs are marked failed
for explicit client recovery. Completed files receive an expiration time and a server
cleanup task removes them after the configured retention period.

The server reads `yt-dlp` progress output and persists job progress. SQLite uses a schema
version so incompatible future database changes can fail fast instead of corrupting state.
The current schema tracks cleanup attempts and the last cleanup error; periodic cleanup
retries expired files without stopping when one file is temporarily unavailable.

```bash
uv sync
cp .env.example .env
uv run pytest
uv run uvicorn xownloader_server.main:app --reload
```

Copy `.env.example` to `.env` before starting the server. The `XOWNLOADER_*` settings
control capacity, retention, disk boundaries, and output policy without changing code.
