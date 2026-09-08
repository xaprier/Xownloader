import 'package:flutter_test/flutter_test.dart';
import 'package:xownloader/models/admin_status.dart';

void main() {
  test('parses the /api/v1/admin/status shape', () {
    final status = AdminStatus.fromJson({
      'runtime': {
        'ready': true,
        'yt_dlp': true,
        'ffmpeg': true,
        'ffprobe': true,
        'output_directory': true,
        'disk_reserve': false,
        'instagram_configured': true,
      },
      'jobs': {
        'total': 5,
        'queued': 1,
        'downloading': 1,
        'completed': 2,
        'failed': 1,
      },
      'storage': {'free_bytes': 1024, 'total_bytes': 2048},
    });

    expect(status.runtime['ready'], true);
    expect(status.runtime['disk_reserve'], false);
    expect(status.jobCounts['total'], 5);
    expect(status.jobCounts['failed'], 1);
    expect(status.freeBytes, 1024);
    expect(status.totalBytes, 2048);
  });

  test('tolerates missing sections instead of throwing', () {
    final status = AdminStatus.fromJson(const {});

    expect(status.runtime, isEmpty);
    expect(status.jobCounts, isEmpty);
    expect(status.freeBytes, 0);
    expect(status.totalBytes, 0);
  });
}