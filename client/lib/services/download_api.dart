import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/download_job.dart';

class DownloadApiException implements Exception {
  const DownloadApiException(this.statusCode, this.message);

  final int statusCode;
  final String message;

  @override
  String toString() => message;
}

class DownloadApi {
  DownloadApi({required String baseUrl, this.token, http.Client? client})
    : _baseUrl = baseUrl.replaceFirst(RegExp(r'/$'), ''),
      _client = client ?? http.Client();

  final String _baseUrl;
  final String? token;
  final http.Client _client;

  Future<DownloadJob> createDownload({
    required String sourceUrl,
    required String outputFormat,
    String? videoQuality,
    String? audioBitrate,
  }) async {
    final payload = <String, dynamic>{
      'source_url': sourceUrl,
      'output_format': outputFormat,
    };
    if (videoQuality != null) payload['video_quality'] = videoQuality;
    if (audioBitrate != null) payload['audio_bitrate'] = audioBitrate;
    final response = await _client.post(
      _uri('/api/v1/downloads'),
      headers: _headers,
      body: jsonEncode(payload),
    );
    return _jobResponse(response);
  }

  Future<DownloadJob> getDownload(String jobId) async {
    final response = await _client.get(
      _uri('/api/v1/downloads/$jobId'),
      headers: _headers,
    );
    return _jobResponse(response);
  }

  Future<DownloadJob> cancelDownload(String jobId) async {
    final response = await _client.delete(
      _uri('/api/v1/downloads/$jobId'),
      headers: _headers,
    );
    return _jobResponse(response);
  }

  Uri fileUri(String jobId) => _uri('/api/v1/downloads/$jobId/file');

  Map<String, String> get _headers => {
    'Content-Type': 'application/json',
    if (token?.isNotEmpty ?? false) 'Authorization': 'Bearer $token',
  };

  Uri _uri(String path) => Uri.parse('$_baseUrl$path');

  DownloadJob _jobResponse(http.Response response) {
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw DownloadApiException(
        response.statusCode,
        body['detail']?.toString() ?? 'The server returned an error',
      );
    }
    return DownloadJob.fromJson(body);
  }
}
