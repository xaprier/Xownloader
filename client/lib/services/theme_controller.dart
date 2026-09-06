import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Holds the app-wide [ThemeMode] and persists the user's choice.
class ThemeController extends ChangeNotifier {
  ThemeController(this._prefs);

  static const _storageKey = 'theme_mode';

  final SharedPreferences _prefs;
  ThemeMode _mode = ThemeMode.system;

  ThemeMode get mode => _mode;

  /// Restores the stored mode. Unknown or missing values fall back to system.
  Future<void> load() async {
    _mode = _decode(_prefs.getString(_storageKey));
    notifyListeners();
  }

  Future<void> setMode(ThemeMode mode) async {
    if (mode == _mode) return;
    _mode = mode;
    notifyListeners();
    await _prefs.setString(_storageKey, _encode(mode));
  }

  static ThemeMode _decode(String? value) {
    switch (value) {
      case 'light':
        return ThemeMode.light;
      case 'dark':
        return ThemeMode.dark;
      default:
        return ThemeMode.system;
    }
  }

  static String _encode(ThemeMode mode) {
    switch (mode) {
      case ThemeMode.light:
        return 'light';
      case ThemeMode.dark:
        return 'dark';
      case ThemeMode.system:
        return 'system';
    }
  }
}
