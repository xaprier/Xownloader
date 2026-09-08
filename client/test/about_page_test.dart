import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:xownloader/l10n/app_strings.dart';
import 'package:xownloader/l10n/app_strings_scope.dart';
import 'package:xownloader/pages/about_page.dart';

Widget _host() => AppStringsScope(
      strings: AppStrings.of(const Locale('en')),
      child: const MaterialApp(home: AboutPage()),
    );

void main() {
  testWidgets('shows the project name, developer, and repository link',
      (tester) async {
    await tester.pumpWidget(_host());

    expect(find.text('Xownloader'), findsOneWidget);
    expect(find.text('Seymen Kalkan'), findsOneWidget);
    expect(find.text('github.com/xaprier/Xownloader'), findsOneWidget);
    expect(find.textContaining('Version'), findsOneWidget);
  });
}
