/// Formats a duration in seconds as words, e.g. `23 minutes 55 seconds`.
/// Returns [unknownLabel] when the value is missing or not positive.
///
/// The unit/label callbacks default to English so existing callers (and
/// tests) that don't pass an [AppStrings] keep their current behavior;
/// localized call sites pass `strings.hourLabel` etc.
String formatDuration(
  int? totalSeconds, {
  String unknownLabel = 'Unknown length',
  String Function(int value) hourLabel = _defaultHour,
  String Function(int value) minuteLabel = _defaultMinute,
  String Function(int value) secondLabel = _defaultSecond,
}) {
  if (totalSeconds == null || totalSeconds <= 0) return unknownLabel;

  final hours = totalSeconds ~/ 3600;
  final minutes = (totalSeconds % 3600) ~/ 60;
  final seconds = totalSeconds % 60;

  final parts = <String>[
    if (hours > 0) hourLabel(hours),
    if (minutes > 0) minuteLabel(minutes),
    if (seconds > 0) secondLabel(seconds),
  ];
  return parts.join(' ');
}

String _defaultHour(int value) => '$value hour${value == 1 ? '' : 's'}';
String _defaultMinute(int value) => '$value minute${value == 1 ? '' : 's'}';
String _defaultSecond(int value) => '$value second${value == 1 ? '' : 's'}';
