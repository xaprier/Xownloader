import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:xownloader/services/theme_controller.dart';

Future<ThemeController> _controller() async {
  final prefs = await SharedPreferences.getInstance();
  return ThemeController(prefs);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('defaults to system mode when nothing is stored', () async {
    SharedPreferences.setMockInitialValues({});
    final controller = await _controller();

    await controller.load();

    expect(controller.mode, ThemeMode.system);
  });

  test('load restores a previously stored mode', () async {
    SharedPreferences.setMockInitialValues({'theme_mode': 'dark'});
    final controller = await _controller();

    await controller.load();

    expect(controller.mode, ThemeMode.dark);
  });

  test('setMode updates the mode, notifies, and persists the choice', () async {
    SharedPreferences.setMockInitialValues({});
    final controller = await _controller();
    await controller.load();

    var notifications = 0;
    controller.addListener(() => notifications++);

    await controller.setMode(ThemeMode.light);

    expect(controller.mode, ThemeMode.light);
    expect(notifications, 1);

    final reloaded = await _controller();
    await reloaded.load();
    expect(reloaded.mode, ThemeMode.light);
  });

  test('ignores an unrecognised stored value and falls back to system',
      () async {
    SharedPreferences.setMockInitialValues({'theme_mode': 'sepia'});
    final controller = await _controller();

    await controller.load();

    expect(controller.mode, ThemeMode.system);
  });
}
