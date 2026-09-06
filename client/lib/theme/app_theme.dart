import 'package:flutter/material.dart';

/// Xownloader brand colour, taken from the app icon mark.
const brandSeed = Color(0xFFF5721E);

ThemeData _theme(Brightness brightness) {
  return ThemeData(
    colorScheme: ColorScheme.fromSeed(
      seedColor: brandSeed,
      brightness: brightness,
    ),
    inputDecorationTheme: const InputDecorationTheme(
      border: OutlineInputBorder(),
    ),
  );
}

final ThemeData lightTheme = _theme(Brightness.light);
final ThemeData darkTheme = _theme(Brightness.dark);
