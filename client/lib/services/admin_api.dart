import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/admin_status.dart';
import '../models/download_job.dart';
import 'download_api.dart';

/// Talks to the server's admin-scoped endpoints. Separate from [DownloadApi]
/// because the credential and its lifecycle are different: the client token
/// is baked in at build time, but the admin token is entered at runtime and
/// only exists once someone signs in through the admin gate.
class AdminApi {
  AdminApi({required String baseUrl, required this.token, http.Client? client})
    : _baseUrl = baseUrl.replaceFirst(RegExp(r'/$'), ''),
      _client = client ?? http.Client();

  final String _baseUrl;
  final String token;
  final http.Client _client;

  Future<AdminStatus> fetchStatus() async {
    final response = await _client.get(_uri('/api/v1/admin/status'), headers: _headers);
    _checkOk(response);
    return AdminStatus.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  Future<List<DownloadJob>> fetchJobs() async {
    final response = await _client.get(_uri('/api/v1/admin/jobs'), headers: _headers);
    _checkOk(response);
    final list = jsonDecode(response.body) as List<dynamic>;
    return list
        .map((item) => DownloadJob.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  /// The raw Prometheus exposition text — not parsed or charted.
  Future<String> fetchMetricsText() async {
    final response = await _client.get(_uri('/metrics'), headers: _headers);
    _checkOk(response);
    return response.body;
  }

  Map<String, String> get _headers => {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer $token',
  };

  Uri _uri(String path) => Uri.parse('$_baseUrl$path');

  void _checkOk(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) return;
    var message = 'The server returned an error';
    try {
      final body = jsonDecode(response.body) as Map<String, dynamic>;
      if (body['detail'] != null) message = body['detail'].toString();
    } on FormatException {
      // The error body wasn't JSON (e.g. a plain-text 5xx) — keep the
      // generic message rather than letting the decode failure propagate.
    }
    throw DownloadApiException(response.statusCode, message);
  }
}