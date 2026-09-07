# Xownloader

Xownloader is a cross-platform media downloader built around a self-hosted backend.
It downloads YouTube media through `yt-dlp` and single public Instagram posts and
reels through a dedicated adapter. Instagram support requires a server-configured
account cookie; without one, Instagram URLs are rejected and YouTube is unaffected.

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
  (YouTube). Instagram serves the post's own media as-is.
- For an Instagram carousel, preview the media items, let the user pick a subset,
  and expose one file per selected item.
- Track download state and expose the resulting file(s) to the requesting client.
- Remove completed files after the configured retention period.
- Keep provider-specific integrations behind the server boundary.

Instagram profile, story, highlight, and comment retrieval are out of scope.

## Requirements

- Python 3.11 or newer
- `uv` for server dependency management
- `yt-dlp` and its runtime dependencies
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

The repository currently contains the initial monorepo structure, a policy-controlled
REST API foundation with SQLite job persistence, and a generated Flutter client starter.
The next implementation slice is authentication, progress reporting, and client
integration. Tests and client features should be added with each slice.

## License

No license has been selected yet. Do not redistribute this project until a license
and the applicable provider terms have been reviewed.
