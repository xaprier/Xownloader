import 'package:flutter/widgets.dart';

import 'app_strings.dart';

/// Exposes the resolved [AppStrings] to the widget tree below [MyApp] so any
/// widget can read `context.strings` without threading it through
/// constructors.
class AppStringsScope extends InheritedWidget {
  const AppStringsScope({required this.strings, required super.child, super.key});

  final AppStrings strings;

  static AppStrings of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<AppStringsScope>();
    assert(scope != null, 'AppStringsScope.of() called with no AppStringsScope ancestor');
    return scope!.strings;
  }

  @override
  bool updateShouldNotify(AppStringsScope oldWidget) =>
      oldWidget.strings.runtimeType != strings.runtimeType;
}

extension AppStringsContext on BuildContext {
  AppStrings get strings => AppStringsScope.of(this);
}
