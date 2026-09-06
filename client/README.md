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
