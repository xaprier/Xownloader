# Development

## Server

```bash
cd server
uv sync
cp .env.example .env
uv run pytest
uv run uvicorn xownloader_server.main:app --reload
```

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

Keep local output in ignored directories. Do not use live provider downloads in automated
tests.
