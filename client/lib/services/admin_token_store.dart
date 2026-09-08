import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Persists the admin token. Abstract so tests inject an in-memory fake
/// instead of touching a real platform secure-storage channel.
abstract class AdminTokenStore {
  Future<String?> read();
  Future<void> write(String token);
  Future<void> delete();
}

class SecureAdminTokenStore implements AdminTokenStore {
  SecureAdminTokenStore({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  static const _key = 'xownloader_admin_token';

  final FlutterSecureStorage _storage;

  @override
  Future<String?> read() => _storage.read(key: _key);

  @override
  Future<void> write(String token) => _storage.write(key: _key, value: token);

  @override
  Future<void> delete() => _storage.delete(key: _key);
}