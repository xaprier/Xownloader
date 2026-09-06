import 'package:flutter_dotenv/flutter_dotenv.dart';

class AppConfig {
  const AppConfig._();

    static String get serverUrl => dotenv.isInitialized
      ? dotenv.env['XOWNLOADER_SERVER_URL'] ?? 'http://127.0.0.1:8000'
      : 'http://127.0.0.1:8000';
}