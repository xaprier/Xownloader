import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:xownloader/main.dart';
import 'package:xownloader/services/locale_controller.dart';
import 'package:xownloader/services/theme_controller.dart';

/// None of the other widget tests ever force a non-English locale (the
/// suite pins the platform locale to English for determinism — see
/// flutter_test_config.dart), so a bug specific to Turkish only shows up
/// here. This caught a real crash: without `flutter_localizations`
/// registered, MaterialApp(locale: Locale('tr')) has no delegate that
/// supports 'tr', so MaterialLocalizations.of(context) returns null and any
/// TextField throws a null-check error the moment it builds its decoration.
void main() {
  testWidgets('the Turkish UI renders and the URL field works without crashing',
      (tester) async {
    SharedPreferences.setMockInitialValues({'app_locale': 'tr'});
    final prefs = await SharedPreferences.getInstance();
    final themeController = ThemeController(prefs);
    await themeController.load();
    final localeController = LocaleController(prefs);
    await localeController.load();
    expect(localeController.locale, const Locale('tr'));

    await tester.pumpWidget(
      MyApp(themeController: themeController, localeController: localeController),
    );
    await tester.pump();

    expect(tester.takeException(), isNull);
    expect(find.text('Bağlantıyı incele'), findsOneWidget);

    await tester.enterText(find.byType(TextField), 'https://youtu.be/example');
    await tester.pump();

    expect(tester.takeException(), isNull);
  });
}
