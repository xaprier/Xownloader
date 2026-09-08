import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:xownloader/l10n/app_strings.dart';
import 'package:xownloader/l10n/app_strings_scope.dart';
import 'package:xownloader/pages/admin_gate_page.dart';
import 'package:xownloader/pages/admin_home_page.dart';
import 'package:xownloader/services/admin_api.dart';
import 'package:xownloader/services/admin_token_store.dart';

class FakeAdminTokenStore implements AdminTokenStore {
  String? stored = 'a-token';

  @override
  Future<String?> read() async => stored;

  @override
  Future<void> write(String token) async => stored = token;

  @override
  Future<void> delete() async => stored = null;
}

/// Routes each admin endpoint to its own canned response, or a fixed
/// [statusCode] for every request when non-200.
class _RoutingClient extends http.BaseClient {
  _RoutingClient({this.statusCode = 200});
  final int statusCode;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    if (statusCode != 200) {
      return http.StreamedResponse(
        Stream.value(utf8.encode('{"detail":"A valid API token is required"}')),
        statusCode,
        headers: {'content-type': 'application/json'},
      );
    }
    final path = request.url.path;
    final body = path.endsWith('/admin/jobs') ? _jobsJson : _statusJson;
    return http.StreamedResponse(
      Stream.value(utf8.encode(body)),
      200,
      headers: {'content-type': 'application/json'},
    );
  }
}

Widget _host(AdminTokenStore store, {int statusCode = 200}) => AppStringsScope(
      strings: AppStrings.of(const Locale('en')),
      child: MaterialApp(
        home: AdminHomePage(
          tokenStore: store,
          token: 'a-token',
          api: AdminApi(
            baseUrl: 'http://host',
            token: 'a-token',
            client: _RoutingClient(statusCode: statusCode),
          ),
        ),
      ),
    );

void main() {
  testWidgets('Status tab shows job count tiles, disk percent, and storage line',
      (tester) async {
    // The default 800x600 test surface is too short to lay out the runtime
    // panel, the count-tile grid, and the disk card without scrolling.
    tester.view.physicalSize = const Size(800, 1400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(_host(FakeAdminTokenStore()));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 20));

    expect(find.text('3'), findsOneWidget); // total jobs tile
    expect(find.text('50%'), findsOneWidget); // 1024 free of 2048 total
    expect(find.textContaining('KB'), findsWidgets); // storage line
  });

  testWidgets('Jobs tab lists jobs with a status badge and a copy action',
      (tester) async {
    await tester.pumpWidget(_host(FakeAdminTokenStore()));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 20));

    await tester.tap(find.text('Jobs'));
    await tester.pumpAndSettle();

    expect(find.text('https://youtu.be/x'), findsOneWidget);
    expect(find.text('COMPLETED'), findsOneWidget);
    expect(find.text('Copy link'), findsOneWidget);
    expect(find.text('Open'), findsOneWidget);
  });

  testWidgets('a 401 clears the stored token and returns to the gate',
      (tester) async {
    final store = FakeAdminTokenStore();
    await tester.pumpWidget(_host(store, statusCode: 401));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 20));

    expect(store.stored, isNull);
    expect(find.byType(AdminGatePage), findsOneWidget);
    expect(find.text('Your admin session is no longer valid.'), findsOneWidget);
  });

  testWidgets('sign out clears the token and pops the page', (tester) async {
    final store = FakeAdminTokenStore();
    await tester.pumpWidget(
      AppStringsScope(
        strings: AppStrings.of(const Locale('en')),
        child: MaterialApp(
          home: Builder(
            builder: (context) => Scaffold(
              body: Center(
                child: TextButton(
                  onPressed: () => Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => AdminHomePage(
                        tokenStore: store,
                        token: 'a-token',
                        api: AdminApi(
                          baseUrl: 'http://host',
                          token: 'a-token',
                          client: _RoutingClient(),
                        ),
                      ),
                    ),
                  ),
                  child: const Text('open'),
                ),
              ),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();
    await tester.pump(const Duration(milliseconds: 20));

    await tester.tap(find.byTooltip('Sign out'));
    await tester.pumpAndSettle();

    expect(store.stored, isNull);
    expect(find.text('open'), findsOneWidget);
  });
}

const _statusJson = '''
{
  "runtime": {"ready": true, "ffmpeg": false},
  "jobs": {"total": 3, "queued": 1, "downloading": 0, "completed": 2, "failed": 0},
  "storage": {"free_bytes": 1024, "total_bytes": 2048}
}
''';

const _jobsJson = '''
[
  {
    "id": "job-1",
    "source_url": "https://youtu.be/x",
    "output_format": "mp4",
    "status": "completed",
    "progress_percent": 100,
    "artifacts": []
  }
]
''';