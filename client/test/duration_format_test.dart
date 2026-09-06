import 'package:flutter_test/flutter_test.dart';
import 'package:xownloader/utils/duration_format.dart';

void main() {
  test('formats common durations in words', () {
    expect(formatDuration(1435), '23 minutes 55 seconds');
    expect(formatDuration(3665), '1 hour 1 minute 5 seconds');
    expect(formatDuration(3600), '1 hour');
    expect(formatDuration(60), '1 minute');
    expect(formatDuration(119), '1 minute 59 seconds');
    expect(formatDuration(45), '45 seconds');
  });

  test('treats missing or non-positive input as unknown', () {
    expect(formatDuration(null), 'Unknown length');
    expect(formatDuration(0), 'Unknown length');
    expect(formatDuration(-5), 'Unknown length');
  });
}
