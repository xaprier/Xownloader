import 'package:receive_sharing_intent/receive_sharing_intent.dart';

class ShareIntentService {
  const ShareIntentService();

  Future<String?> initialUrl() async {
    try {
      final media = await ReceiveSharingIntent.instance.getInitialMedia();
      await ReceiveSharingIntent.instance.reset();
      return _urlFrom(media);
    } catch (_) {
      return null;
    }
  }

  Stream<String> urlStream() async* {
    try {
      await for (final media
          in ReceiveSharingIntent.instance.getMediaStream()) {
        final url = _urlFrom(media);
        if (url != null) yield url;
      }
    } catch (_) {
      return;
    }
  }

  String? _urlFrom(List<SharedMediaFile> media) {
    for (final item in media) {
      final value = item.path.trim();
      if (_isHttpUrl(value)) return value;
      final message = item.message?.trim();
      if (message != null && _isHttpUrl(message)) return message;
    }
    return null;
  }

  bool _isHttpUrl(String value) {
    final uri = Uri.tryParse(value);
    return uri != null && (uri.scheme == 'http' || uri.scheme == 'https');
  }
}
