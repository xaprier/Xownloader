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

class _StubClient extends http.BaseClient {
  _StubClient(this.previewBody, this.jobBody);

  final String previewBody;
  final String jobBody;
  http.Request? lastDownloadRequest;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final isDownload =
        request.method == 'POST' && request.url.path.endsWith('/api/v1/downloads');
    if (isDownload) lastDownloadRequest = request as http.Request;
    final body = isDownload ? jobBody : previewBody;
    return http.StreamedResponse(
      Stream.value(utf8.encode(body)),
      isDownload ? 202 : 200,
      headers: {'content-type': 'application/json'},
    );
  }
}

void main() {
  testWidgets(
    'carousel preview shows one checkbox per item and submits the selection',
    (tester) async {
      // The default 800x600 test surface is too short to lay out the
      // carousel's checkbox rows plus the always-visible Inspect URL button
      // without scrolling; a taller surface keeps this test scroll-free.
      tester.view.physicalSize = const Size(800, 1400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      SharedPreferences.setMockInitialValues({});
      final client = _StubClient(_previewJson, _jobJson);
      final api = DownloadApi(baseUrl: 'http://localhost:8000', client: client);

      await tester.pumpWidget(
        MyApp(
          themeController: await _loadedController(),
          localeController: await _loadedLocaleController(),
          api: api,
        ),
      );

      await tester.enterText(
        find.byType(TextField),
        'https://www.instagram.com/p/Cxxxx/',
      );
      await tester.tap(find.text('Inspect URL'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 20));

      expect(find.byType(CheckboxListTile), findsNWidgets(3));

      await tester.tap(find.byType(CheckboxListTile).at(1));
      await tester.pump();

      await tester.tap(find.text('Add to queue'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 20));

      final body =
          jsonDecode(client.lastDownloadRequest!.body) as Map<String, dynamic>;
      expect(body['media_selection'], [0, 2]);

      await tester.pumpWidget(const SizedBox());
    },
  );
}

const _previewJson = '''
{
  "source_url": "https://www.instagram.com/p/Cxxxx/",
  "provider": "instagram",
  "title": "Trip",
  "thumbnail": null,
  "uploader": "nasa",
  "duration_seconds": null,
  "media_items": [
    {"index": 0, "type": "image", "thumbnail": null, "width": null, "height": null, "duration_seconds": null},
    {"index": 1, "type": "video", "thumbnail": null, "width": null, "height": null, "duration_seconds": 8},
    {"index": 2, "type": "image", "thumbnail": null, "width": null, "height": null, "duration_seconds": null}
  ],
  "allowed_output_formats": [],
  "allowed_video_qualities": [],
  "allowed_audio_bitrates": []
}
''';

const _jobJson = '''
{
  "id": "00000000-0000-0000-0000-000000000001",
  "source_url": "https://www.instagram.com/p/Cxxxx/",
  "output_format": "mp4",
  "status": "queued",
  "progress_percent": 0,
  "artifacts": []
}
''';
