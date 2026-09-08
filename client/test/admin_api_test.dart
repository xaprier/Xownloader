import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:xownloader/services/admin_api.dart';
import 'package:xownloader/services/download_api.dart';

class FakeHttpClient extends http.BaseClient {
  FakeHttpClient(this.statusCode, this.responseBody);

  final int statusCode;
  final String responseBody;
  http.BaseRequest? lastRequest;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    lastRequest = request;
    return http.StreamedResponse(
      Stream.value(utf8.encode(responseBody)),
      statusCode,
      headers: {'content-type': 'application/json'},
    );
  }
}

void main() {
  test('fetchStatus sends the admin token and parses the response', () async {
    final client = FakeHttpClient(200, _statusJson);
    final api = AdminApi(baseUrl: 'http://host:8000', token: 'secret', client: client);

    final status = await api.fetchStatus();

    expect(client.lastRequest?.url.toString(), 'http://host:8000/api/v1/admin/status');
    expect(client.lastRequest?.headers['authorization'], 'Bearer secret');
    expect(status.jobCounts['total'], 3);
  });

  test('fetchJobs parses a list of jobs', () async {
    final client = FakeHttpClient(200, _jobsJson);
    final api = AdminApi(baseUrl: 'http://host:8000', token: 'secret', client: client);

    final jobs = await api.fetchJobs();

    expect(client.lastRequest?.url.toString(), 'http://host:8000/api/v1/admin/jobs');
    expect(jobs, hasLength(1));
    expect(jobs.single.id, 'job-1');
  });

  test('fileUri builds a plain path without a display name', () {
    final api = AdminApi(baseUrl: 'http://host:8000', token: 'secret');
    expect(
      api.fileUri('job-1').toString(),
      'http://host:8000/api/v1/downloads/job-1/file',
    );
  });

  test('mediaUri encodes the display name', () {
    final api = AdminApi(baseUrl: 'http://host:8000', token: 'secret');
    expect(
      api.mediaUri('job-1', 2, displayName: 'my video.mp4').toString(),
      'http://host:8000/api/v1/downloads/job-1/media/2/my%20video.mp4',
    );
  });

  test('a non-2xx response throws DownloadApiException with the server detail', () async {
    final client = FakeHttpClient(401, '{"detail":"A valid API token is required"}');
    final api = AdminApi(baseUrl: 'http://host:8000', token: 'bad', client: client);

    await expectLater(
      api.fetchStatus(),
      throwsA(
        isA<DownloadApiException>()
            .having((e) => e.statusCode, 'statusCode', 401)
            .having((e) => e.message, 'message', 'A valid API token is required'),
      ),
    );
  });

  test('a non-JSON error body still throws with a generic message', () async {
    final client = FakeHttpClient(500, 'internal server error');
    final api = AdminApi(baseUrl: 'http://host:8000', token: 'secret', client: client);

    await expectLater(
      api.fetchJobs(),
      throwsA(
        isA<DownloadApiException>()
            .having((e) => e.statusCode, 'statusCode', 500)
            .having((e) => e.message, 'message', 'The server returned an error'),
      ),
    );
  });
}

const _statusJson = '''
{
  "runtime": {"ready": true},
  "jobs": {"total": 3, "queued": 1, "downloading": 0, "completed": 2, "failed": 0},
  "storage": {"free_bytes": 1024, "total_bytes": 2048}
}
''';

const _jobsJson = '''
[
  {
    "id": "job-1",
    "source_url": "https://youtu.be/x",
    "output_format": "mp4",
    "status": "completed",
    "progress_percent": 100,
    "artifacts": []
  }
]
''';