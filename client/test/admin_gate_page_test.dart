import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:xownloader/l10n/app_strings.dart';
import 'package:xownloader/l10n/app_strings_scope.dart';
import 'package:xownloader/pages/admin_gate_page.dart';
import 'package:xownloader/services/admin_api.dart';
import 'package:xownloader/services/admin_token_store.dart';

class FakeAdminTokenStore implements AdminTokenStore {
  String? stored;

  @override
  Future<String?> read() async => stored;

  @override
  Future<void> write(String token) async => stored = token;

  @override
  Future<void> delete() async => stored = null;
}

class _RespondingClient extends http.BaseClient {
  _RespondingClient(this.statusCode);
  final int statusCode;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    String body;
    if (statusCode != 200) {
      body = '{"detail":"A valid API token is required"}';
    } else if (request.url.path.endsWith('/admin/jobs')) {
      body = '[]';
    } else if (request.url.path.endsWith('/metrics')) {
      body = '';
    } else {
      body = '{"runtime":{},"jobs":{},"storage":{"free_bytes":0,"total_bytes":0}}';
    }
    return http.StreamedResponse(
      Stream.value(body.codeUnits),
      statusCode,
      headers: {'content-type': 'application/json'},
    );
  }
}

Widget _host(AdminTokenStore store, int responseStatusCode) => AppStringsScope(
      strings: AppStrings.of(const Locale('en')),
      child: MaterialApp(
        home: AdminGatePage(
          tokenStore: store,
          apiBuilder: (token) => AdminApi(
            baseUrl: 'http://host',
            token: token,
            client: _RespondingClient(responseStatusCode),
          ),
        ),
      ),
    );

void main() {
  testWidgets('a valid token is stored and navigates to the admin home page',
      (tester) async {
    final store = FakeAdminTokenStore();
    await tester.pumpWidget(_host(store, 200));

    await tester.enterText(find.byType(TextField), 'good-token');
    await tester.tap(find.text('Continue'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 20));

    expect(store.stored, 'good-token');
    expect(find.text('Admin'), findsWidgets); // AdminHomePage's AppBar title
  });

  testWidgets('an invalid token shows an error and stores nothing',
      (tester) async {
    final store = FakeAdminTokenStore();
    await tester.pumpWidget(_host(store, 401));

    await tester.enterText(find.byType(TextField), 'bad-token');
    await tester.tap(find.text('Continue'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 20));

    expect(store.stored, isNull);
    expect(find.text('Invalid admin token'), findsOneWidget);
  });

  testWidgets('shows the initialError message when provided', (tester) async {
    final store = FakeAdminTokenStore();
    await tester.pumpWidget(
      AppStringsScope(
        strings: AppStrings.of(const Locale('en')),
        child: MaterialApp(
          home: AdminGatePage(
            tokenStore: store,
            initialError: 'Your admin session is no longer valid.',
          ),
        ),
      ),
    );

    expect(find.text('Your admin session is no longer valid.'), findsOneWidget);
  });
}