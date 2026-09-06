# Xownloader

Xownloader is a cross-platform media downloader built around a self-hosted backend.
The first release focuses on downloading YouTube media through `yt-dlp`; Instagram
support is planned as a later feature and is intentionally outside the initial scope.

## Project shape

```text
server/   Python API and download worker built around yt-dlp
client/   Flutter application for Android, iOS, Linux, macOS, Windows, and web
docs/     Architecture, development, and operational documentation
```

The Flutter client communicates with the server instead of running `yt-dlp` directly.
This keeps download policy, output formats, storage, authentication, and cleanup in one
place while allowing one client codebase to target mobile and desktop platforms.

## Initial scope

- Accept a YouTube URL from the Flutter client.
- Let the server select the available format according to its configuration.
- Track download state and expose the resulting file to the requesting client.
- Remove completed files after the configured retention period.
- Keep provider-specific integrations behind the server boundary.

Instagram is a post-MVP integration. Its API, authentication, legal, and provider
limitations will be reviewed before implementation.

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

See [docs/architecture.md](docs/architecture.md) for the system architecture. Keep
changes focused, validate them with the relevant tests and linters, and use dedicated
branches with reviewed merges for repository contributions.

## Development status

The repository currently contains the initial monorepo structure, a minimal API health
check, and a generated Flutter client starter. The next implementation slice is the YouTube
download lifecycle: request validation, job state, `yt-dlp` execution, file delivery,
and retention cleanup. Tests and client features should be added with each slice.

## License

No license has been selected yet. Do not redistribute this project until a license
and the applicable provider terms have been reviewed.
