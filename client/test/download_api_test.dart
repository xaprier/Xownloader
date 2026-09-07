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
    expect(client.lastRequest?.url.toString(), 'http://localhost:8000/api/v1/downloads');
    expect(client.lastRequest?.headers['authorization'], 'Bearer client-token');
    final request = client.lastRequest! as http.Request;
    expect(jsonDecode(request.body), {
      'source_url': 'https://youtu.be/example',
      'output_format': 'mp4',
      'video_quality': '720p',
      'audio_bitrate': '192K',
    });
  });

  test('fileUri builds a plain path without a display name', () {
    final api = DownloadApi(baseUrl: 'http://host:8000');
    expect(
      api.fileUri('job-1').toString(),
      'http://host:8000/api/v1/downloads/job-1/file',
    );
  });

  test('fileUri appends an encoded display name segment', () {
    final api = DownloadApi(baseUrl: 'http://host:8000');
    expect(
      api.fileUri('job-1', displayName: 'My Video.mp4').toString(),
      'http://host:8000/api/v1/downloads/job-1/file/My%20Video.mp4',
    );
  });

  test('createDownload includes media_selection when provided', () async {
    final client = FakeHttpClient(_jobJson);
    final api = DownloadApi(baseUrl: 'http://localhost:8000/', client: client);

    await api.createDownload(
      sourceUrl: 'https://www.instagram.com/p/Cxxxx/',
      outputFormat: 'mp4',
      mediaSelection: [0, 2],
    );

    final request = client.lastRequest! as http.Request;
    expect(jsonDecode(request.body), {
      'source_url': 'https://www.instagram.com/p/Cxxxx/',
      'output_format': 'mp4',
      'media_selection': [0, 2],
    });
  });

  test('mediaUri builds an indexed capability path', () {
    final api = DownloadApi(baseUrl: 'http://host:8000');
    expect(
      api.mediaUri('job-1', 2, displayName: 'Trip (3).mp4').toString(),
      'http://host:8000/api/v1/downloads/job-1/media/2/Trip%20(3).mp4',
    );
    expect(
      api.mediaUri('job-1', 0).toString(),
      'http://host:8000/api/v1/downloads/job-1/media/0',
    );
  });

  test('parses a preview with instagram media items', () async {
    final client = FakeHttpClient(_instagramPreviewJson);
    final api = DownloadApi(baseUrl: 'http://localhost:8000/', client: client);

    final preview = await api.preview('https://www.instagram.com/p/Cxxxx/');

    expect(preview.provider, 'instagram');
    expect(preview.mediaItems, isNotNull);
    expect(preview.mediaItems!.map((m) => m.type).toList(), ['image', 'video']);
  });

  test('previews a URL before creating a download', () async {
    final client = FakeHttpClient(_previewJson);
    final api = DownloadApi(
      baseUrl: 'http://localhost:8000/',
      token: 'client-token',
      client: client,
    );

    final preview = await api.preview('https://youtu.be/example');

    expect(preview.title, 'Example video');
    expect(client.lastRequest?.url.toString(), 'http://localhost:8000/api/v1/previews');
    expect(client.lastRequest?.headers['authorization'], 'Bearer client-token');
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

const _instagramPreviewJson = '''
{
  "source_url": "https://www.instagram.com/p/Cxxxx/",
  "provider": "instagram",
  "title": "Trip",
  "thumbnail": null,
  "uploader": "nasa",
  "duration_seconds": null,
  "media_items": [
    {"index": 0, "type": "image", "thumbnail": null, "width": 1080, "height": 1080, "duration_seconds": null},
    {"index": 1, "type": "video", "thumbnail": null, "width": 720, "height": 720, "duration_seconds": 8}
  ],
  "allowed_output_formats": [],
  "allowed_video_qualities": [],
  "allowed_audio_bitrates": []
}
''';

const _previewJson = '''
{
  "source_url": "https://youtu.be/example",
  "provider": "youtube",
  "title": "Example video",
  "thumbnail": null,
  "uploader": "Example channel",
  "duration_seconds": 123,
  "allowed_output_formats": ["mp4", "mp3"],
  "allowed_video_qualities": ["480p", "720p"],
  "allowed_audio_bitrates": ["128K", "192K"]
}
''';
