# Development

## Server

```bash
cd server
uv sync
cp .env.example .env
uv run pytest
uv run uvicorn xownloader_server.main:app --reload
```

`/health` is a liveness check. `/ready` reports whether `yt-dlp`, FFmpeg, ffprobe, the
output directory, and the configured disk reserve are usable. `/metrics` exposes basic
download counters for monitoring.

## Flutter client

Install the Flutter stable channel and follow `client/README.md`. Flutter is the single
client implementation for Android, iOS, Linux, macOS, Windows, and web.

The client server URL is configured in `client/.env` using the
`XOWNLOADER_SERVER_URL` variable. Copy `client/.env.example` before running or building.

```bash
cd client
cp .env.example .env
flutter pub get
flutter analyze
flutter test
flutter build web
flutter build linux
```

For web development, add the browser origin to `XOWNLOADER_CORS_ALLOWED_ORIGINS` in the
server `.env`. Do not use a wildcard CORS origin in a deployed environment.

For a production-like local run, set both `XOWNLOADER_CLIENT_API_TOKEN` and
`XOWNLOADER_ADMIN_API_TOKEN`; all protected API routes then require a Bearer token.

Keep local output in ignored directories. Do not use live provider downloads in automated
tests.
