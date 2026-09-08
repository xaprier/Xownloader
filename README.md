# Xownloader

Xownloader is a cross-platform media downloader built around a self-hosted backend.
It downloads YouTube media through `yt-dlp`, and public Instagram posts, reels,
stories, and highlights through [instagrapi](https://github.com/subzeroid/instagrapi).
Instagram support requires a server-configured account (username, password, and a
TOTP seed if the account has two-factor authentication); without one, Instagram URLs
are rejected and YouTube is unaffected.

## Project shape

```text
server/   Python API and download worker built around yt-dlp
client/   Flutter application for Android, iOS, Linux, macOS, Windows, and web
docs/     Architecture, development, and operational documentation
```

The Flutter client communicates with the server instead of running `yt-dlp` directly.
This keeps download policy, output formats, storage, authentication, and cleanup in one
place while allowing one client codebase to target mobile and desktop platforms.

## Scope

- Accept a YouTube or Instagram URL from the Flutter client; the server picks the
  provider from the URL host.
- Let the server select the available format according to its configuration
  (YouTube). Instagram serves the source media as-is.
- Instagram: a single post or reel, a highlight, a single story, or a user's
  active stories. For carousels, highlights, and story sets the preview lists the
  items so the user picks which to download, one file per selected item.
- When an Instagram story or highlight is expired, removed, or empty, the preview
  returns `410` and the client shows it as a warning rather than an error.
- Track download state and expose the resulting file(s) to the requesting client.
- Remove completed files after the configured retention period.
- Keep provider-specific integrations behind the server boundary.

Instagram profile feeds and comment retrieval are out of scope.

## Requirements

- Python 3.11 or newer
- `uv` for server dependency management
- `yt-dlp` and its runtime dependencies (YouTube); `instagrapi` (Instagram) — both
  installed as server dependencies via `uv sync`
- Flutter stable channel for the client

The current development machine has Python, `uv`, and Flutter. Android builds additionally
require the Android SDK; platform-specific toolchains may be required for other targets.

## Quick start: server

```bash
cd server
uv sync
cp .env.example .env
uv run uvicorn xownloader_server.main:app --reload
```

The API is then available at `http://127.0.0.1:8000`. The health endpoint is
`GET /health`, and the OpenAPI document is available at `/docs`.

Or run it in a container (FFmpeg bundled):

```bash
cd server
docker compose up -d --build
```

## Client setup

The Flutter client lives in `client/` and targets mobile, desktop, and web platforms.
See `client/README.md` for client setup and validation commands.

## Server connection

The client reads the server base URL from `client/.env`. Start with the committed
template:

```bash
cd client
cp .env.example .env
flutter pub get
```

Set `XOWNLOADER_SERVER_URL` to the reachable API origin, for example
`http://127.0.0.1:8000`. The `.env` file is local configuration and must not be
committed. The server's own settings remain in `server/.env`.

## Configuration and cleanup

Server configuration is environment-based. In particular, the output directory,
allowed media policy, and retention period are server-owned settings. Downloaded
files must be treated as temporary data and cleaned by the server according to that
policy rather than by either client.

See [docs/architecture.md](docs/architecture.md) and [docs/operations.md](docs/operations.md)
for architecture and production operations. Keep
changes focused, validate them with the relevant tests and linters, and use dedicated
branches with reviewed merges for repository contributions.

## Development status

Version 2.x: YouTube plus Instagram posts, reels, carousels, stories, and highlights,
with token-scoped auth, SQLite job persistence, progress reporting, retention cleanup,
and a Flutter client for all targets. The Flutter client also includes a read-only admin
surface (runtime status with job counts and disk usage, all-user job list) reachable
from the About page, gated by a runtime-entered admin token stored in the platform's
secure storage.

## License

MIT — see [LICENSE](LICENSE). Using the YouTube and Instagram providers remains
subject to those platforms' own terms of service.
