# Xownloader Server

The server is a FastAPI application. It will own URL validation, `yt-dlp` execution,
job state, file delivery, and retention cleanup. The current slice exposes only a health
endpoint while the download lifecycle is implemented incrementally.

```bash
uv sync
cp .env.example .env
uv run pytest
uv run uvicorn xownloader_server.main:app --reload
```
