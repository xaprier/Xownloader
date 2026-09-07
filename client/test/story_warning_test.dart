import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:xownloader/main.dart';
import 'package:xownloader/services/download_api.dart';
import 'package:xownloader/services/theme_controller.dart';

Future<ThemeController> _loadedController() async {
  final prefs = await SharedPreferences.getInstance();
  final controller = ThemeController(prefs);
  await controller.load();
  return controller;
}

class _GoneClient extends http.BaseClient {
  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    return http.StreamedResponse(
      Stream.value(
        utf8.encode(
          '{"detail":"This story has expired or is no longer available"}',
        ),
      ),
      410,
      headers: {'content-type': 'application/json'},
    );
  }
}

void main() {
  testWidgets('a 410 preview shows an amber warning, not a red error', (
    tester,
  ) async {
    SharedPreferences.setMockInitialValues({});
    final api = DownloadApi(baseUrl: 'http://localhost:8000', client: _GoneClient());

    await tester.pumpWidget(
      MyApp(themeController: await _loadedController(), api: api),
    );

    await tester.enterText(
      find.byType(TextField),
      'https://www.instagram.com/stories/nbakolej/123/',
    );
    await tester.tap(find.text('Inspect URL'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 20));

    expect(find.textContaining('expired'), findsOneWidget);
    expect(find.byIcon(Icons.warning_amber_rounded), findsOneWidget);
    expect(find.byIcon(Icons.error_outline), findsNothing);

    await tester.pumpWidget(const SizedBox());
  });
}
