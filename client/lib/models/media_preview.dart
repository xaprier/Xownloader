class PreviewMediaItem {
  const PreviewMediaItem({
    required this.index,
    required this.type,
    this.thumbnail,
    this.width,
    this.height,
    this.durationSeconds,
  });

  final int index;
  final String type;
  final String? thumbnail;
  final int? width;
  final int? height;
  final int? durationSeconds;

  factory PreviewMediaItem.fromJson(Map<String, dynamic> json) {
    return PreviewMediaItem(
      index: json['index'] as int,
      type: json['type'] as String,
      thumbnail: json['thumbnail'] as String?,
      width: json['width'] as int?,
      height: json['height'] as int?,
      durationSeconds: json['duration_seconds'] as int?,
    );
  }
}

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
    this.mediaItems,
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
  final List<PreviewMediaItem>? mediaItems;

  bool get isCarouselCapable => mediaItems != null;

  factory MediaPreview.fromJson(Map<String, dynamic> json) {
    final rawItems = json['media_items'] as List<dynamic>?;
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
      mediaItems: rawItems
          ?.map((item) => PreviewMediaItem.fromJson(item as Map<String, dynamic>))
          .toList(),
    );
  }
}
