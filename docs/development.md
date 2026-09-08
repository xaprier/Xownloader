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

To run the server in a container instead: `cd server && docker compose up -d --build`
(FFmpeg is bundled). See [operations.md](operations.md#container) for details.

Set `XOWNLOADER_INSTAGRAM_USERNAME` and `XOWNLOADER_INSTAGRAM_PASSWORD` to enable the
[instagrapi](https://github.com/subzeroid/instagrapi)-backed Instagram provider; see
[operations.md](operations.md#instagram-provider). Without them, Instagram URLs are rejected
and YouTube is unaffected.

## Flutter client

Install the Flutter stable channel and follow `client/README.md`. Flutter is the single
client implementation for Android, iOS, Linux, macOS, Windows, and web.

The client server URL is configured in `client/.env` using the
`XOWNLOADER_SERVER_URL` variable. Copy `client/.env.example` before running or building.
The value must include the scheme (`http://127.0.0.1:8000`, not `127.0.0.1:8000`) — a
scheme-less value parses as a URI scheme and the client cannot reach the server. On an
Android emulator use `http://10.0.2.2:8000`; a physical device or a distributed build
needs the machine's LAN address or the HTTPS deployment. `.env` is bundled at build time,
so a change needs a rebuild or a full restart, not a hot reload.

```bash
cd client
cp .env.example .env
flutter pub get
flutter analyze
flutter test
flutter build web
flutter build linux
```

The client theme (System/Light/Dark) is a local per-device preference stored with
`shared_preferences`; it is not server configuration. Regenerate launcher icons after
changing the brand art with `dart run flutter_launcher_icons` (config in
`client/flutter_launcher_icons.yaml`).

The client can run several downloads at once. The new-download composer and every job —
running or finished — share a single scrolling queue surface; job history is per-session
and not persisted. Pasting a YouTube URL offers format and quality options; an Instagram
carousel, highlight, or story set instead lists its media items with checkboxes so the
user picks which to download. Completed files are served from unauthenticated capability
URLs — `/api/v1/downloads/{id}/file` (and `/file/{name}`) for a single file, and
`/api/v1/downloads/{id}/media/{index}` (`.../media/{index}/{name}`) for one artifact of a
multi-item job. The unguessable job id plus retention expiry are the guard, and the
trailing name segment lets browsers and download managers save the file under its
original title.

An Instagram story or highlight that is expired, removed, or empty comes back from the
preview as `410`; the client shows that as an amber warning rather than a red error.

### Platform notes

- Cleartext HTTP is blocked by default on Android and iOS. It is permitted only for
  loopback and the Android emulator host (`10.0.2.2`) so a local `http://` server works
  in development. A deployed server must be reached over HTTPS.
- macOS builds require the `com.apple.security.network.client` entitlement (already set)
  to reach the server from the sandbox.
- `flutter build linux` produces a relocatable bundle. Installing it to a prefix
  (`cmake --install build/linux/x64/release -DCMAKE_INSTALL_PREFIX=/usr/local`) also
  installs the `.desktop` entry and hicolor icons for desktop-environment integration.

For web development, add the browser origin to `XOWNLOADER_CORS_ALLOWED_ORIGINS` in the
server `.env`. Do not use a wildcard CORS origin in a deployed environment.

For a production-like local run, set both `XOWNLOADER_CLIENT_API_TOKEN` and
`XOWNLOADER_ADMIN_API_TOKEN`; all protected API routes then require a Bearer token.

Keep local output in ignored directories. Do not use live provider downloads in automated
tests.

See [operations.md](operations.md) for production configuration, readiness, backups, and
incident checks.
