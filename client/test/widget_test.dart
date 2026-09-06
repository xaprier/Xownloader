import 'package:flutter_test/flutter_test.dart';

import 'package:xownloader/main.dart';

void main() {
  testWidgets('shows the configured server URL', (WidgetTester tester) async {
    await tester.pumpWidget(const MyApp());

    expect(find.text('Server: http://127.0.0.1:8000'), findsOneWidget);
  });
}
