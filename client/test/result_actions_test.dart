import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:xownloader/widgets/result_actions.dart';

void main() {
  final fileUri = Uri.parse('http://127.0.0.1:8000/api/v1/downloads/job-1/file');

  Widget host() => MaterialApp(
        home: Scaffold(body: ResultActions(fileUri: fileUri)),
      );

  testWidgets('offers copy and open actions', (tester) async {
    await tester.pumpWidget(host());

    expect(find.text('Copy link'), findsOneWidget);
    expect(find.text('Open'), findsOneWidget);
    expect(find.textContaining('File:'), findsNothing);
  });

  testWidgets('copy button writes the file URL to the clipboard',
      (tester) async {
    final calls = <MethodCall>[];
    tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
      SystemChannels.platform,
      (call) async {
        if (call.method == 'Clipboard.setData') calls.add(call);
        return null;
      },
    );
    addTearDown(() {
      tester.binding.defaultBinaryMessenger
          .setMockMethodCallHandler(SystemChannels.platform, null);
    });

    await tester.pumpWidget(host());
    await tester.tap(find.text('Copy link'));
    await tester.pump();

    expect(calls, hasLength(1));
    expect((calls.single.arguments as Map)['text'], fileUri.toString());
    expect(find.text('Link copied'), findsOneWidget);
  });
}
