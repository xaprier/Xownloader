class MediaPreview {
  const MediaPreview({
    required this.sourceUrl,
    required this.provider,
    required this.title,
    required this.allowedOutputFormats,
    required this.allowedVideoQualities,
    required this.allowedAudioBitrates,
    this.thumbnail,
    this.uploader,
    this.durationSeconds,
  });

  final String sourceUrl;
  final String provider;
  final String title;
  final String? thumbnail;
  final String? uploader;
  final int? durationSeconds;
  final List<String> allowedOutputFormats;
  final List<String> allowedVideoQualities;
  final List<String> allowedAudioBitrates;

  factory MediaPreview.fromJson(Map<String, dynamic> json) {
    return MediaPreview(
      sourceUrl: json['source_url'] as String,
      provider: json['provider'] as String,
      title: json['title'] as String,
      thumbnail: json['thumbnail'] as String?,
      uploader: json['uploader'] as String?,
      durationSeconds: json['duration_seconds'] as int?,
      allowedOutputFormats: List<String>.from(
        json['allowed_output_formats'] as List<dynamic>,
      ),
      allowedVideoQualities: List<String>.from(
        json['allowed_video_qualities'] as List<dynamic>,
      ),
      allowedAudioBitrates: List<String>.from(
        json['allowed_audio_bitrates'] as List<dynamic>,
      ),
    );
  }
}
