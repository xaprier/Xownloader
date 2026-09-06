import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:xownloader/main.dart';
import 'package:xownloader/services/theme_controller.dart';

Future<ThemeController> _loadedController() async {
  final prefs = await SharedPreferences.getInstance();
  final controller = ThemeController(prefs);
  await controller.load();
  return controller;
}

ThemeMode? _appThemeMode(WidgetTester tester) =>
    tester.widget<MaterialApp>(find.byType(MaterialApp)).themeMode;

void main() {
  testWidgets('shows the configured server URL', (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(MyApp(themeController: await _loadedController()));

    expect(find.text('Server: http://127.0.0.1:8000'), findsOneWidget);
  });

  testWidgets('starts in the mode the controller reports', (tester) async {
    SharedPreferences.setMockInitialValues({'theme_mode': 'light'});
    await tester.pumpWidget(MyApp(themeController: await _loadedController()));

    expect(_appThemeMode(tester), ThemeMode.light);
  });

  testWidgets('theme menu switches the app to dark mode', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final controller = await _loadedController();
    await tester.pumpWidget(MyApp(themeController: controller));
    expect(_appThemeMode(tester), ThemeMode.system);

    await tester.tap(find.byKey(const Key('theme-menu')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Dark').last);
    await tester.pumpAndSettle();

    expect(controller.mode, ThemeMode.dark);
    expect(_appThemeMode(tester), ThemeMode.dark);
  });
}
