enum DownloadStatus { queued, downloading, completed, failed, cancelled }

class DownloadJob {
  const DownloadJob({
    required this.id,
    required this.sourceUrl,
    required this.outputFormat,
    required this.status,
    required this.progressPercent,
    this.error,
    this.fileName,
    this.displayName,
    this.expiresAt,
  });

  final String id;
  final String sourceUrl;
  final String outputFormat;
  final DownloadStatus status;
  final double progressPercent;
  final String? error;
  final String? fileName;
  final String? displayName;
  final DateTime? expiresAt;

  factory DownloadJob.fromJson(Map<String, dynamic> json) {
    return DownloadJob(
      id: json['id'] as String,
      sourceUrl: json['source_url'] as String,
      outputFormat: json['output_format'] as String,
      status: DownloadStatus.values.byName(json['status'] as String),
      progressPercent: (json['progress_percent'] as num).toDouble(),
      error: json['error'] as String?,
      fileName: json['file_name'] as String?,
      displayName: json['display_name'] as String?,
      expiresAt: json['expires_at'] == null
          ? null
          : DateTime.parse(json['expires_at'] as String),
    );
  }
}
