import 'package:flutter/widgets.dart';

/// UI copy for the app, in the user's chosen or device language.
///
/// Only two languages are supported. Server-provided text (error/warning
/// messages, media titles, uploader names) is never translated here — it
/// passes through as-is.
abstract class AppStrings {
  const AppStrings();

  /// Resolves the strings for [locale]; unsupported languages fall back to
  /// English.
  factory AppStrings.of(Locale locale) {
    return switch (locale.languageCode) {
      'tr' => const _TrStrings(),
      _ => const _EnStrings(),
    };
  }

  /// Languages this factory can resolve to, for the language picker.
  static const supportedLocales = [Locale('en'), Locale('tr')];

  // Chrome
  String get themeTooltip;
  String get themeSystem;
  String get themeLight;
  String get themeDark;
  String get languageTooltip;
  String get languageSystemLabel;
  String get languageEnglish;
  String get languageTurkish;

  // Composer
  String get downloadMediaHeading;
  String serverLabel(String url);
  String get urlFieldLabel;
  String get urlFieldHelper;
  String get clearUrlTooltip;
  String get enterUrlError;
  String get inspectUrlLabel;
  String get inspectingLabel;
  String itemLabel(int number, String mediaType);
  String get addToQueueLabel;
  String get submittingLabel;
  String get autoQualityLabel;
  String get autoAudioLabel;
  String get serverUnreachableError;

  // Supported-links panel
  String get supportedLinksTitle;
  String get supportedLinksFooter;
  String get linkKindPostOrReel;
  String get linkKindStoryOrHighlight;
  String get linkKindVideoOrShort;

  // Queue
  String get queueTitle;
  String get emptyQueueTitle;
  String get emptyQueueSubtitle;
  String get statusQueued;
  String get statusDownloading;
  String get statusCompleted;
  String get statusFailed;
  String get statusCancelled;
  String get cancelLabel;
  String get waitingForSlot;
  String get downloadFailedFallback;
  String get cancelledMessage;

  // Result actions
  String get copyLinkLabel;
  String get openLabel;
  String get linkCopiedMessage;
  String get couldNotOpenLinkMessage;

  // Duration formatting (fed into utils/duration_format.dart)
  String get unknownLengthLabel;
  String hourLabel(int value);
  String minuteLabel(int value);
  String secondLabel(int value);

  // About
  String get aboutFooterCta;
  String get aboutPageTitle;
  String get aboutTagline;
  String get aboutDescription;
  String get aboutDeveloperLabel;
  String get aboutRepositoryLabel;
  String aboutVersionLabel(String version);

  // Admin
  String get adminEntryTooltip;
  String get adminGateTitle;
  String get adminTokenFieldLabel;
  String get adminGateSubmitLabel;
  String get adminInvalidTokenError;
  String get adminSessionExpiredMessage;
  String get adminHomeTitle;
  String get adminSignOutTooltip;
  String get adminStatusTab;
  String get adminJobsTab;
  String get adminJobsTotalLabel;
  String get adminNoJobsMessage;
  String get adminDiskFreeLabel;
  String adminStorageFreeOfTotal(String free, String total);
  String adminRuntimeLabel(String key);
}

class _EnStrings extends AppStrings {
  const _EnStrings();

  @override
  String get themeTooltip => 'Theme';
  @override
  String get themeSystem => 'System';
  @override
  String get themeLight => 'Light';
  @override
  String get themeDark => 'Dark';
  @override
  String get languageTooltip => 'Language';
  @override
  String get languageSystemLabel => 'Device language';
  @override
  String get languageEnglish => 'English';
  @override
  String get languageTurkish => 'Türkçe';

  @override
  String get downloadMediaHeading => 'Download media';
  @override
  String serverLabel(String url) => 'Server: $url';
  @override
  String get urlFieldLabel => 'YouTube or Instagram URL';
  @override
  String get urlFieldHelper =>
      'youtube.com/watch · youtu.be · instagram.com/p · /reel · /stories';
  @override
  String get clearUrlTooltip => 'Clear';
  @override
  String get enterUrlError => 'Enter a YouTube or Instagram URL.';
  @override
  String get inspectUrlLabel => 'Inspect URL';
  @override
  String get inspectingLabel => 'Inspecting...';
  @override
  String itemLabel(int number, String mediaType) {
    final type = mediaType == 'video' ? 'video' : 'image';
    return 'Item $number · $type';
  }

  @override
  String get addToQueueLabel => 'Add to queue';
  @override
  String get submittingLabel => 'Submitting...';
  @override
  String get autoQualityLabel => 'Auto quality';
  @override
  String get autoAudioLabel => 'Auto audio';
  @override
  String get serverUnreachableError => 'Could not reach the download server.';

  @override
  String get supportedLinksTitle => 'SUPPORTED LINKS';
  @override
  String get supportedLinksFooter =>
      'Carousels and highlights let you pick which items to download.';
  @override
  String get linkKindPostOrReel => 'post or reel';
  @override
  String get linkKindStoryOrHighlight => 'story or highlight';
  @override
  String get linkKindVideoOrShort => 'video or short';

  @override
  String get queueTitle => 'QUEUE';
  @override
  String get emptyQueueTitle => 'Your queue is empty';
  @override
  String get emptyQueueSubtitle =>
      'Inspect a URL above to add the first download.';
  @override
  String get statusQueued => 'QUEUED';
  @override
  String get statusDownloading => 'DOWNLOADING';
  @override
  String get statusCompleted => 'COMPLETED';
  @override
  String get statusFailed => 'FAILED';
  @override
  String get statusCancelled => 'CANCELLED';
  @override
  String get cancelLabel => 'Cancel';
  @override
  String get waitingForSlot => 'Waiting for a free slot';
  @override
  String get downloadFailedFallback => 'The download failed.';
  @override
  String get cancelledMessage => 'You cancelled this download.';

  @override
  String get copyLinkLabel => 'Copy link';
  @override
  String get openLabel => 'Open';
  @override
  String get linkCopiedMessage => 'Link copied';
  @override
  String get couldNotOpenLinkMessage => 'Could not open the link';

  @override
  String get unknownLengthLabel => 'Unknown length';
  @override
  String hourLabel(int value) => '$value hour${value == 1 ? '' : 's'}';
  @override
  String minuteLabel(int value) => '$value minute${value == 1 ? '' : 's'}';
  @override
  String secondLabel(int value) => '$value second${value == 1 ? '' : 's'}';

  @override
  String get aboutFooterCta => 'About Xownloader';
  @override
  String get aboutPageTitle => 'About';
  @override
  String get aboutTagline => 'Your media, your server.';
  @override
  String get aboutDescription =>
      'Xownloader is a self-hosted media downloader. A Flutter client talks '
      'to your own backend, which fetches YouTube and Instagram media so no '
      'download ever routes through a third-party service.';
  @override
  String get aboutDeveloperLabel => 'Developer';
  @override
  String get aboutRepositoryLabel => 'Source code';
  @override
  String aboutVersionLabel(String version) => 'Version $version';

  @override
  String get adminEntryTooltip => 'Admin';
  @override
  String get adminGateTitle => 'Admin sign-in';
  @override
  String get adminTokenFieldLabel => 'Admin token';
  @override
  String get adminGateSubmitLabel => 'Continue';
  @override
  String get adminInvalidTokenError => 'Invalid admin token';
  @override
  String get adminSessionExpiredMessage => 'Your admin session is no longer valid.';
  @override
  String get adminHomeTitle => 'Admin';
  @override
  String get adminSignOutTooltip => 'Sign out';
  @override
  String get adminStatusTab => 'Status';
  @override
  String get adminJobsTab => 'Jobs';
  @override
  String get adminJobsTotalLabel => 'Total';
  @override
  String get adminNoJobsMessage => 'No jobs yet.';
  @override
  String get adminDiskFreeLabel => 'free';
  @override
  String adminStorageFreeOfTotal(String free, String total) => '$free free of $total';
  @override
  String adminRuntimeLabel(String key) {
    const labels = {
      'ready': 'Ready',
      'yt_dlp': 'yt-dlp',
      'ffmpeg': 'FFmpeg',
      'ffprobe': 'ffprobe',
      'output_directory': 'Output directory',
      'disk_reserve': 'Disk reserve',
      'instagram_configured': 'Instagram configured',
    };
    return labels[key] ?? key;
  }
}

class _TrStrings extends AppStrings {
  const _TrStrings();

  @override
  String get themeTooltip => 'Tema';
  @override
  String get themeSystem => 'Sistem';
  @override
  String get themeLight => 'Açık';
  @override
  String get themeDark => 'Koyu';
  @override
  String get languageTooltip => 'Dil';
  @override
  String get languageSystemLabel => 'Cihaz dili';
  @override
  String get languageEnglish => 'English';
  @override
  String get languageTurkish => 'Türkçe';

  @override
  String get downloadMediaHeading => 'Medya indir';
  @override
  String serverLabel(String url) => 'Sunucu: $url';
  @override
  String get urlFieldLabel => 'YouTube veya Instagram bağlantısı';
  @override
  String get urlFieldHelper =>
      'youtube.com/watch · youtu.be · instagram.com/p · /reel · /stories';
  @override
  String get clearUrlTooltip => 'Temizle';
  @override
  String get enterUrlError => 'Bir YouTube veya Instagram bağlantısı girin.';
  @override
  String get inspectUrlLabel => 'Bağlantıyı incele';
  @override
  String get inspectingLabel => 'İnceleniyor...';
  @override
  String itemLabel(int number, String mediaType) {
    final type = mediaType == 'video' ? 'video' : 'görsel';
    return '$number. öğe · $type';
  }

  @override
  String get addToQueueLabel => 'Kuyruğa ekle';
  @override
  String get submittingLabel => 'Gönderiliyor...';
  @override
  String get autoQualityLabel => 'Otomatik kalite';
  @override
  String get autoAudioLabel => 'Otomatik ses';
  @override
  String get serverUnreachableError => 'İndirme sunucusuna ulaşılamadı.';

  @override
  String get supportedLinksTitle => 'DESTEKLENEN BAĞLANTILAR';
  @override
  String get supportedLinksFooter =>
      'Karosel ve öne çıkanlarda hangi öğeleri indireceğinizi seçebilirsiniz.';
  @override
  String get linkKindPostOrReel => 'gönderi veya reel';
  @override
  String get linkKindStoryOrHighlight => 'hikaye veya öne çıkan';
  @override
  String get linkKindVideoOrShort => 'video veya kısa video';

  @override
  String get queueTitle => 'KUYRUK';
  @override
  String get emptyQueueTitle => 'Kuyruğunuz boş';
  @override
  String get emptyQueueSubtitle =>
      'İlk indirmeyi eklemek için yukarıdan bir bağlantı inceleyin.';
  @override
  String get statusQueued => 'SIRADA';
  @override
  String get statusDownloading => 'İNDİRİLİYOR';
  @override
  String get statusCompleted => 'TAMAMLANDI';
  @override
  String get statusFailed => 'BAŞARISIZ';
  @override
  String get statusCancelled => 'İPTAL EDİLDİ';
  @override
  String get cancelLabel => 'İptal';
  @override
  String get waitingForSlot => 'Boş sıra bekleniyor';
  @override
  String get downloadFailedFallback => 'İndirme başarısız oldu.';
  @override
  String get cancelledMessage => 'Bu indirmeyi iptal ettiniz.';

  @override
  String get copyLinkLabel => 'Bağlantıyı kopyala';
  @override
  String get openLabel => 'Aç';
  @override
  String get linkCopiedMessage => 'Bağlantı kopyalandı';
  @override
  String get couldNotOpenLinkMessage => 'Bağlantı açılamadı';

  @override
  String get unknownLengthLabel => 'Süre bilinmiyor';
  @override
  String hourLabel(int value) => '$value saat';
  @override
  String minuteLabel(int value) => '$value dakika';
  @override
  String secondLabel(int value) => '$value saniye';

  @override
  String get aboutFooterCta => 'Xownloader Hakkında';
  @override
  String get aboutPageTitle => 'Hakkında';
  @override
  String get aboutTagline => 'Medyanız, kendi sunucunuzda.';
  @override
  String get aboutDescription =>
      'Xownloader, kendi sunucunuzda barındırdığınız bir medya indiricidir. '
      'Flutter istemcisi yalnızca kendi sunucunuzla konuşur; YouTube ve '
      'Instagram medyası üçüncü taraf bir servisten geçmeden doğrudan '
      'sunucunuz tarafından indirilir.';
  @override
  String get aboutDeveloperLabel => 'Geliştirici';
  @override
  String get aboutRepositoryLabel => 'Kaynak kod';
  @override
  String aboutVersionLabel(String version) => 'Sürüm $version';

  @override
  String get adminEntryTooltip => 'Yönetici';
  @override
  String get adminGateTitle => 'Yönetici girişi';
  @override
  String get adminTokenFieldLabel => 'Yönetici anahtarı';
  @override
  String get adminGateSubmitLabel => 'Devam et';
  @override
  String get adminInvalidTokenError => 'Geçersiz yönetici anahtarı';
  @override
  String get adminSessionExpiredMessage => 'Yönetici oturumunuz artık geçerli değil.';
  @override
  String get adminHomeTitle => 'Yönetici';
  @override
  String get adminSignOutTooltip => 'Çıkış yap';
  @override
  String get adminStatusTab => 'Durum';
  @override
  String get adminJobsTab => 'İşler';
  @override
  String get adminJobsTotalLabel => 'Toplam';
  @override
  String get adminNoJobsMessage => 'Henüz iş yok.';
  @override
  String get adminDiskFreeLabel => 'boş';
  @override
  String adminStorageFreeOfTotal(String free, String total) => '$total üzerinden $free boş';
  @override
  String adminRuntimeLabel(String key) {
    const labels = {
      'ready': 'Hazır',
      'yt_dlp': 'yt-dlp',
      'ffmpeg': 'FFmpeg',
      'ffprobe': 'ffprobe',
      'output_directory': 'Çıktı dizini',
      'disk_reserve': 'Disk rezervi',
      'instagram_configured': 'Instagram yapılandırıldı',
    };
    return labels[key] ?? key;
  }
}
