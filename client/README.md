# Flutter Client

This directory contains the single Flutter client for Android, iOS, Linux, macOS,
Windows, and web.

## Configuration

Copy the environment template before running the application:

```bash
cp .env.example .env
```

Set `XOWNLOADER_SERVER_URL` to the server API origin, **with the scheme** — use
`http://127.0.0.1:8000`, not `127.0.0.1:8000`. An Android emulator reaches the host at
`http://10.0.2.2:8000`; a physical device or a distributed build needs a LAN address or
the HTTPS deployment. `.env` is bundled at build time, so a change needs a rebuild or a
full restart. Do not commit `.env`.

Set `XOWNLOADER_CLIENT_API_TOKEN` when the server runs in production. The client uses
the token for download creation, status polling, cancellation, and file retrieval.

The screen uses a preview-first flow. Inspect loads metadata without creating a job: for
YouTube the user then picks MP4/MP3, video quality, and audio bitrate; for an Instagram
carousel, highlight, or story set it lists the media items with checkboxes so the user
picks which to download. Progress polling, cancellation, and per-file result links follow
submission. A failed request shows a red error; an expired or empty Instagram story or
highlight shows an amber warning instead.

## Admin

The About page's admin icon opens a read-only operational view: runtime status
(yt-dlp/FFmpeg/disk/Instagram readiness) with job counts and disk usage, and the full
list of every user's jobs (with the same copy-link/open actions as the main queue). It
requires an admin API token — the same one set via
`XOWNLOADER_ADMIN_API_TOKEN` on the server — entered once and stored via
`flutter_secure_storage` (the platform keychain/keystore), never baked into the build
the way `XOWNLOADER_CLIENT_API_TOKEN` is. A `401` from any admin request clears the
stored token and returns to the sign-in screen. No job cancellation or other mutating
action is exposed here yet.

## Share intent

Android is configured to receive `text/plain` shares from YouTube and other apps. A
shared HTTP(S) URL is placed into the URL field and inspected automatically; downloading
still requires explicit confirmation in the preview screen.

iOS requires a native Share Extension target because Flutter Runner alone cannot appear
as a share destination. The required Xcode setup is documented in
`ios/Share Extension/README.md`.

Install the Flutter stable channel, then run:

```bash
flutter create --org com.xaprier --project-name xownloader .
flutter pub get
flutter test
```

Useful local checks are:

```bash
flutter analyze
flutter test
flutter build web
flutter build linux
```

Android builds additionally require the Android SDK. Other release targets may require
their platform-specific toolchains. The client should call the server API and keep
provider and retention logic out of Dart.
