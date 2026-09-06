import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:xownloader/models/download_job.dart';
import 'package:xownloader/services/download_api.dart';

class FakeHttpClient extends http.BaseClient {
  FakeHttpClient(this.responseBody);

  final String responseBody;
  http.BaseRequest? lastRequest;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    lastRequest = request;
    return http.StreamedResponse(
      Stream.value(utf8.encode(responseBody)),
      202,
      headers: {'content-type': 'application/json'},
    );
  }
}

void main() {
  test('creates a download with the configured token and options', () async {
    final client = FakeHttpClient(_jobJson);
    final api = DownloadApi(
      baseUrl: 'http://localhost:8000/',
      token: 'client-token',
      client: client,
    );

    final job = await api.createDownload(
      sourceUrl: 'https://youtu.be/example',
      outputFormat: 'mp4',
      videoQuality: '720p',
      audioBitrate: '192K',
    );

    expect(job.status, DownloadStatus.queued);
    expect(
      client.lastRequest?.url.toString(),
      'http://localhost:8000/api/v1/downloads',
    );
    expect(client.lastRequest?.headers['authorization'], 'Bearer client-token');
    final request = client.lastRequest! as http.Request;
    expect(jsonDecode(request.body), {
      'source_url': 'https://youtu.be/example',
      'output_format': 'mp4',
      'video_quality': '720p',
      'audio_bitrate': '192K',
    });
  });
}

const _jobJson = '''
{
  "id": "00000000-0000-0000-0000-000000000001",
  "source_url": "https://youtu.be/example",
  "output_format": "mp4",
  "status": "queued",
  "progress_percent": 0
}
''';
