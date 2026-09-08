import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Pins the platform locale to English for every test in this directory so
/// widget assertions on English copy don't depend on the host machine's
/// actual locale (this app now resolves its default language from it).
Future<void> testExecutable(FutureOr<void> Function() testMain) async {
  TestWidgetsFlutterBinding.ensureInitialized();
  TestWidgetsFlutterBinding.instance.platformDispatcher.localeTestValue =
      const Locale('en', 'US');
  return testMain();
}
