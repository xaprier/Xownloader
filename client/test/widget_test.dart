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

ThemeMode? _appThemeMode(WidgetTester tester) =>
    tester.widget<MaterialApp>(find.byType(MaterialApp)).themeMode;

String _jobJson(String id, String status, num progress, {String? displayName}) =>
    jsonEncode({
      'id': id,
      'source_url': 'https://youtu.be/example',
      'output_format': 'mp4',
      'status': status,
      'progress_percent': progress,
      'display_name': ?displayName,
    });

const _previewJson = '''
{
  "source_url": "https://youtu.be/example",
  "provider": "youtube",
  "title": "Example video",
  "thumbnail": null,
  "uploader": "Example channel",
  "duration_seconds": 123,
  "allowed_output_formats": ["mp4", "mp3"],
  "allowed_video_qualities": ["480p", "720p"],
  "allowed_audio_bitrates": ["128K", "192K"]
}
''';

/// Fake transport: previews succeed, each POST creates a new queued job, and
/// GETs report the job as `downloading` or, when [completeImmediately], as
/// `completed`.
class _QueueFakeClient extends http.BaseClient {
  _QueueFakeClient({this.completeImmediately = false});

  final bool completeImmediately;
  int _created = 0;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final path = request.url.path;
    var status = 200;
    String body;

    if (path.endsWith('/api/v1/previews')) {
      body = _previewJson;
    } else if (request.method == 'POST' && path.endsWith('/api/v1/downloads')) {
      _created++;
      status = 202;
      body = _jobJson('job-$_created', 'queued', 0);
    } else if (request.method == 'DELETE') {
      body = _jobJson(path.split('/').last, 'cancelled', 0);
    } else if (request.method == 'GET' && path.contains('/api/v1/downloads/')) {
      final id = path.split('/').last;
      body = completeImmediately
          ? _jobJson(id, 'completed', 100, displayName: 'Example video.mp4')
          : _jobJson(id, 'downloading', 40);
    } else {
      body = '{}';
    }

    return http.StreamedResponse(
      Stream.value(utf8.encode(body)),
      status,
      headers: {'content-type': 'application/json'},
    );
  }
}

Future<void> _inspectAndQueue(WidgetTester tester, String url) async {
  await tester.enterText(find.byType(TextField), url);
  await tester.tap(find.text('Inspect URL'));
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 20));
  await tester.tap(find.text('Add to queue'));
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 20));
}

void main() {
  testWidgets('shows the configured server URL', (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(MyApp(themeController: await _loadedController()));

    expect(find.text('Server: http://127.0.0.1:8000'), findsOneWidget);
  });

  testWidgets('shows the branded title and the supported-links hint', (
    tester,
  ) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(MyApp(themeController: await _loadedController()));

    expect(
      find.image(const AssetImage('assets/icon/logo_mark.png')),
      findsOneWidget,
    );
    expect(find.text('SUPPORTED LINKS'), findsOneWidget);
    expect(
      find.textContaining('pick which items to download'),
      findsOneWidget,
    );
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

  testWidgets('queues each inspected URL under its media title', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final api = DownloadApi(baseUrl: 'http://x', client: _QueueFakeClient());
    await tester.pumpWidget(
      MyApp(themeController: await _loadedController(), api: api),
    );

    await _inspectAndQueue(tester, 'https://youtu.be/a');
    await _inspectAndQueue(tester, 'https://youtu.be/b');

    // both cards show the preview title, not the job id
    expect(find.text('Example video'), findsNWidgets(2));
    expect(find.textContaining('job-'), findsNothing);
    final field = tester.widget<TextField>(find.byType(TextField));
    expect(field.controller!.text, '');

    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('active and completed downloads render on the same page',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    final api = DownloadApi(
      baseUrl: 'http://x',
      client: _QueueFakeClient(completeImmediately: true),
    );
    await tester.pumpWidget(
      MyApp(themeController: await _loadedController(), api: api),
    );

    await _inspectAndQueue(tester, 'https://youtu.be/a');
    await tester.pump(const Duration(seconds: 1));
    await tester.pump(const Duration(milliseconds: 20));

    // no tabs anymore
    expect(find.text('Done'), findsNothing);
    // completed card: server display name + a COMPLETED badge + copy action
    expect(find.text('Example video.mp4'), findsOneWidget);
    expect(find.text('COMPLETED'), findsOneWidget);
    expect(find.text('Copy link'), findsOneWidget);

    await tester.pumpWidget(const SizedBox());
  });
}
