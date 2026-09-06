/// Formats a duration in seconds as English words, e.g. `23 minutes 55 seconds`.
/// Returns `Unknown length` when the value is missing or not positive.
String formatDuration(int? totalSeconds) {
  if (totalSeconds == null || totalSeconds <= 0) return 'Unknown length';

  final hours = totalSeconds ~/ 3600;
  final minutes = (totalSeconds % 3600) ~/ 60;
  final seconds = totalSeconds % 60;

  final parts = <String>[
    if (hours > 0) _unit(hours, 'hour'),
    if (minutes > 0) _unit(minutes, 'minute'),
    if (seconds > 0) _unit(seconds, 'second'),
  ];
  return parts.join(' ');
}

String _unit(int value, String noun) => '$value $noun${value == 1 ? '' : 's'}';
