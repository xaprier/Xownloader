import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Holds the user's language choice and persists it. `null` means "follow
/// the device language" — the app's actual default, restricted to the
/// languages we support.
class LocaleController extends ChangeNotifier {
  LocaleController(this._prefs);

  static const _storageKey = 'app_locale';

  final SharedPreferences _prefs;
  Locale? _locale;

  /// The explicit choice, or `null` when following the device language.
  Locale? get locale => _locale;

  /// Restores the stored choice. Missing or unrecognised values mean
  /// "follow the device language".
  Future<void> load() async {
    _locale = _decode(_prefs.getString(_storageKey));
    notifyListeners();
  }

  Future<void> setLocale(Locale? locale) async {
    if (locale == _locale) return;
    _locale = locale;
    notifyListeners();
    if (locale == null) {
      await _prefs.remove(_storageKey);
    } else {
      await _prefs.setString(_storageKey, locale.languageCode);
    }
  }

  static Locale? _decode(String? value) {
    switch (value) {
      case 'en':
        return const Locale('en');
      case 'tr':
        return const Locale('tr');
      default:
        return null;
    }
  }
}
