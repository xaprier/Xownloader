import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:xownloader/services/locale_controller.dart';

Future<LocaleController> _controller() async {
  final prefs = await SharedPreferences.getInstance();
  return LocaleController(prefs);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('defaults to following the device language when nothing is stored',
      () async {
    SharedPreferences.setMockInitialValues({});
    final controller = await _controller();

    await controller.load();

    expect(controller.locale, isNull);
  });

  test('load restores a previously stored language', () async {
    SharedPreferences.setMockInitialValues({'app_locale': 'tr'});
    final controller = await _controller();

    await controller.load();

    expect(controller.locale, const Locale('tr'));
  });

  test('setLocale updates the choice, notifies, and persists it', () async {
    SharedPreferences.setMockInitialValues({});
    final controller = await _controller();
    await controller.load();

    var notifications = 0;
    controller.addListener(() => notifications++);

    await controller.setLocale(const Locale('tr'));

    expect(controller.locale, const Locale('tr'));
    expect(notifications, 1);

    final reloaded = await _controller();
    await reloaded.load();
    expect(reloaded.locale, const Locale('tr'));
  });

  test('setLocale(null) clears a stored choice back to device language',
      () async {
    SharedPreferences.setMockInitialValues({'app_locale': 'tr'});
    final controller = await _controller();
    await controller.load();

    await controller.setLocale(null);

    expect(controller.locale, isNull);
    final reloaded = await _controller();
    await reloaded.load();
    expect(reloaded.locale, isNull);
  });

  test('ignores an unrecognised stored value and follows the device language',
      () async {
    SharedPreferences.setMockInitialValues({'app_locale': 'fr'});
    final controller = await _controller();

    await controller.load();

    expect(controller.locale, isNull);
  });
}
