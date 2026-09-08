import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:xownloader/main.dart';
import 'package:xownloader/services/download_api.dart';
import 'package:xownloader/services/locale_controller.dart';
import 'package:xownloader/services/theme_controller.dart';

Future<ThemeController> _loadedController() async {
  final prefs = await SharedPreferences.getInstance();
  final controller = ThemeController(prefs);
  await controller.load();
  return controller;
}

Future<LocaleController> _loadedLocaleController() async {
  final prefs = await SharedPreferences.getInstance();
  final controller = LocaleController(prefs);
  await controller.load();
  return controller;
}

String _previewJson(String title) => jsonEncode({
      'source_url': 'https://youtu.be/x',
      'provider': 'youtube',
      'title': title,
      'thumbnail': null,
      'uploader': null,
      'duration_seconds': null,
      'allowed_output_formats': ['mp4'],
      'allowed_video_qualities': ['720p'],
      'allowed_audio_bitrates': ['128K'],
    });

class _CountingPreviewClient extends http.BaseClient {
  int previewCalls = 0;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    previewCalls++;
    final body = (request as http.Request).body;
    final title = body.contains('youtu.be/b') ? 'Video B' : 'Video A';
    return http.StreamedResponse(
      Stream.value(utf8.encode(_previewJson(title))),
      200,
      headers: {'content-type': 'application/json'},
    );
  }
}

Future<void> _pumpAfterInspect(WidgetTester tester) async {
  await tester.tap(find.text('Inspect URL'));
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 20));
}

void main() {
  testWidgets(
    'Inspect URL stays available after a preview and re-fetches a changed URL',
    (tester) async {
      SharedPreferences.setMockInitialValues({});
      final client = _CountingPreviewClient();
      final api = DownloadApi(baseUrl: 'http://localhost:8000', client: client);

      await tester.pumpWidget(
        MyApp(
          themeController: await _loadedController(),
          localeController: await _loadedLocaleController(),
          api: api,
        ),
      );

      await tester.enterText(find.byType(TextField), 'https://youtu.be/a');
      await _pumpAfterInspect(tester);
      expect(find.text('Video A'), findsOneWidget);
      // The bug this guards against: the Inspect button used to disappear
      // once a preview was showing, so a second URL could never be inspected.
      expect(find.text('Inspect URL'), findsOneWidget);
      expect(client.previewCalls, 1);

      // Typing a different URL and inspecting again must fetch a new preview.
      await tester.enterText(find.byType(TextField), 'https://youtu.be/b');
      await _pumpAfterInspect(tester);
      expect(find.text('Video B'), findsOneWidget);
      expect(find.text('Video A'), findsNothing);
      expect(client.previewCalls, 2);

      // Re-inspecting the exact same URL that's already previewed must not
      // send another request.
      await _pumpAfterInspect(tester);
      expect(client.previewCalls, 2);

      await tester.pumpWidget(const SizedBox());
    },
  );
}
