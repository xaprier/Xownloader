import 'package:flutter_test/flutter_test.dart';
import 'package:xownloader/utils/byte_format.dart';

void main() {
  test('formats bytes with the right unit and precision', () {
    expect(formatBytes(0), '0 B');
    expect(formatBytes(512), '512 B');
    expect(formatBytes(1024), '1.0 KB');
    expect(formatBytes(1536), '1.5 KB');
    expect(formatBytes(1024 * 1024), '1.0 MB');
    expect(formatBytes(1024 * 1024 * 1024), '1.0 GB');
    expect(formatBytes((1.5 * 1024 * 1024 * 1024).round()), '1.5 GB');
  });
}