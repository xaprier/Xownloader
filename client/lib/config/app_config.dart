import 'package:flutter_dotenv/flutter_dotenv.dart';

class AppConfig {
  const AppConfig._();

  /// Keep in sync with the `version:` line in pubspec.yaml — shown on the
  /// About page. There is no runtime way to read it back from the package.
  static const String version = '2.0.0';

  static String get serverUrl => dotenv.isInitialized
      ? dotenv.env['XOWNLOADER_SERVER_URL'] ?? 'http://127.0.0.1:8000'
      : 'http://127.0.0.1:8000';

  static String? get clientApiToken =>
      dotenv.isInitialized ? dotenv.env['XOWNLOADER_CLIENT_API_TOKEN'] : null;
}
