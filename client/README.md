# Flutter Client

This directory contains the single Flutter client for Android, iOS, Linux, macOS,
Windows, and web.

## Configuration

Copy the environment template before running the application:

```bash
cp .env.example .env
```

Set `XOWNLOADER_SERVER_URL` to the server API origin. The default points to a local
development server at `http://127.0.0.1:8000`. Do not commit `.env`.

Set `XOWNLOADER_CLIENT_API_TOKEN` when the server runs in production. The client uses
the token for download creation, status polling, cancellation, and file retrieval.

The current screen uses a preview-first flow: Enter/Inspect loads YouTube metadata and
server-approved options without creating a job. The user then selects MP4/MP3, video
quality, and audio bitrate before explicitly starting the download. Progress polling,
error display, cancellation, and the completed file URL are supported after submission.

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
