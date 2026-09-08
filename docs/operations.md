# Server Operations

## Production prerequisites

Install Python 3.11 or newer, `uv`, `yt-dlp`, FFmpeg, and ffprobe. The server must have
write access to its download directory and enough free disk space for the configured
reserve plus the expected output size.

The container image (below) already bundles Python, the dependencies, and FFmpeg.

## Container

`server/Dockerfile` builds a self-contained image (multi-stage `uv` build, FFmpeg
bundled). `server/compose.yaml` runs it.

```bash
cd server
cp .env.example .env          # optional; the image has working defaults
docker compose up -d --build
curl -f http://localhost:8000/health
curl -s   http://localhost:8000/ready   # expect "ready": true
```

- Downloads and the SQLite database are bind-mounted to `server/data/` on the host, so
  the database-backup steps below apply to `server/data/xownloader.db` directly.
- The container process runs as UID/GID `1000:1000` so it can write the bind mount.
  If `server/data/` is owned by a different user, start it with that owner:
  `XOWNLOADER_UID=$(id -u) XOWNLOADER_GID=$(id -g) docker compose up -d`.
- The published host port defaults to `8000`. Set `XOWNLOADER_HOST_PORT` in `.env`
  when that port is taken, and point the reverse proxy at the same value.
- The container always binds `0.0.0.0` inside its network namespace; publish the port
  (`ports: "8000:8000"`) or place it behind a reverse proxy that terminates TLS.
- `.env` values still apply — set `XOWNLOADER_CLIENT_API_TOKEN`,
  `XOWNLOADER_ADMIN_API_TOKEN`, and `XOWNLOADER_CORS_ALLOWED_ORIGINS` for a real
  deployment. `XOWNLOADER_HOST`, `XOWNLOADER_DOWNLOAD_DIRECTORY`, and
  `XOWNLOADER_DATABASE_PATH` are fixed by compose and should not be overridden.
- `docker compose down` stops the server; the bind-mounted data survives.

## Instagram provider

The Instagram adapter authenticates via [instagrapi](https://github.com/subzeroid/instagrapi)
using a dedicated account's username and password
(`XOWNLOADER_INSTAGRAM_USERNAME` / `XOWNLOADER_INSTAGRAM_PASSWORD`). On first use
it logs in and writes a session file to `XOWNLOADER_INSTAGRAM_SESSION_PATH`
(default `data/instagram_session.json`, inside the bind-mounted `data/`
directory — it survives `docker compose down`/`up` without a separate volume).
Later requests reuse that session instead of logging in again.

This is intended for a self-hosted instance with few users. A shared account
used for high-volume automated access is more likely to hit a checkpoint,
two-factor prompt, or a block — use a dedicated account, and raise
`XOWNLOADER_INSTAGRAM_DOWNLOAD_DELAY_SECONDS` if downloads are being throttled.
If Instagram rejects the login (checkpoint, 2FA, or a stale session it cannot
refresh), the server does not crash: the Instagram provider stops accepting
requests for 5 minutes (returning `502` with "session is invalid or expired")
before it tries logging in again, so it does not hammer a flagged account.
Resolving a checkpoint or 2FA challenge requires signing into the account
manually (e.g. from a browser or the Instagram app) and is not automated.
`GET /ready` reports `instagram_configured` (username is set) but does not call
Instagram; login validity surfaces on the first real request.

Supported URL shapes: a post or reel (`/p/`, `/reel/`, `/tv/`), a highlight
(`/stories/highlights/<id>/`), a single story (`/stories/<user>/<pk>/`), and a
user's active stories (`/stories/<user>/`).

Error vs warning: a genuine failure (invalid session, network, Instagram rate
limit, malformed URL) returns `502`/`5xx`. A story, highlight, or post that is
expired, removed, private, or empty returns `410` — the client shows this as a
warning, not an error. If Instagram requests keep failing with the rate-limit
message, the account is being throttled; back off and retry later.

## Configuration

Copy `server/.env.example` to `server/.env` and set deployment-specific values. At minimum,
production deployments should set:

- `XOWNLOADER_ENVIRONMENT=production`
- `XOWNLOADER_CLIENT_API_TOKEN`
- `XOWNLOADER_ADMIN_API_TOKEN`
- `XOWNLOADER_DOWNLOAD_DIRECTORY`
- `XOWNLOADER_DATABASE_PATH`
- `XOWNLOADER_CORS_ALLOWED_ORIGINS`

Never use wildcard CORS or commit `.env` files. Keep client and admin tokens separate.
Terminate TLS at the deployment proxy or application gateway.

## Startup checks

- `GET /health` is a liveness check and confirms that the process responds.
- `GET /ready` is a readiness check and verifies yt-dlp, FFmpeg, ffprobe, output storage,
  and the configured disk reserve.
- `GET /metrics` exposes counters and requires admin authorization.
- `GET /api/v1/admin/status` reports runtime, queue, and storage state.

A deployment should remove the instance from traffic when `/ready` returns `503`.

## Database operations

The SQLite database is local operational state. Stop the server or otherwise coordinate
writes before taking a backup. Copy the database together with the download directory
metadata needed for recovery. Schema version migrations run during startup and fail fast
when a database is newer than the running server.

Before a migration:

```bash
cp "$XOWNLOADER_DATABASE_PATH" "$XOWNLOADER_DATABASE_PATH.bak"
```

Restore the backup if startup fails after a migration. Test backups by restoring them in a
separate environment; do not edit production files in place.

## Retention and cleanup

Completed files receive an expiration timestamp based on `XOWNLOADER_RETENTION_HOURS`.
The cleanup task retries expired files on later intervals when deletion fails and stores
attempt count and the last error in the job record. Investigate persistent failures as
storage or permission incidents.

## Incident checks

1. Check `/health` and `/ready`.
2. Inspect `/api/v1/admin/status` and `/metrics` with the admin token.
3. Check free disk and output directory permissions.
4. Check server logs for `download_failed` and `download_cleanup_failed` events.
5. Preserve the SQLite database and relevant logs before destructive cleanup.
