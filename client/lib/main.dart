import 'dart:async';

import 'package:flutter/foundation.dart'
    show TargetPlatform, defaultTargetPlatform, kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'config/app_config.dart';
import 'models/download_job.dart';
import 'models/media_preview.dart';
import 'services/download_api.dart';
import 'services/share_intent_service.dart';
import 'services/theme_controller.dart';
import 'theme/app_theme.dart';
import 'utils/duration_format.dart';
import 'widgets/result_actions.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await dotenv.load(fileName: '.env', isOptional: true);
  final themeController = ThemeController(await SharedPreferences.getInstance());
  await themeController.load();
  runApp(
    MyApp(
      themeController: themeController,
      api: DownloadApi(
        baseUrl: AppConfig.serverUrl,
        token: AppConfig.clientApiToken,
      ),
    ),
  );
}

class MyApp extends StatelessWidget {
  const MyApp({required this.themeController, super.key, this.api});

  final ThemeController themeController;
  final DownloadApi? api;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: themeController,
      builder: (context, _) {
        return MaterialApp(
          title: 'Xownloader',
          theme: lightTheme,
          darkTheme: darkTheme,
          themeMode: themeController.mode,
          home: DownloadPage(
            themeController: themeController,
            api:
                api ??
                DownloadApi(
                  baseUrl: AppConfig.serverUrl,
                  token: AppConfig.clientApiToken,
                ),
          ),
        );
      },
    );
  }
}

/// AppBar control that cycles through and selects the app [ThemeMode].
class ThemeModeMenu extends StatelessWidget {
  const ThemeModeMenu({required this.controller, super.key});

  final ThemeController controller;

  @override
  Widget build(BuildContext context) {
    return PopupMenuButton<ThemeMode>(
      key: const Key('theme-menu'),
      icon: Icon(switch (controller.mode) {
        ThemeMode.system => Icons.brightness_auto,
        ThemeMode.light => Icons.light_mode,
        ThemeMode.dark => Icons.dark_mode,
      }),
      tooltip: 'Theme',
      initialValue: controller.mode,
      onSelected: controller.setMode,
      itemBuilder: (context) => const [
        PopupMenuItem(
          value: ThemeMode.system,
          child: ListTile(
            leading: Icon(Icons.brightness_auto),
            title: Text('System'),
          ),
        ),
        PopupMenuItem(
          value: ThemeMode.light,
          child: ListTile(leading: Icon(Icons.light_mode), title: Text('Light')),
        ),
        PopupMenuItem(
          value: ThemeMode.dark,
          child: ListTile(leading: Icon(Icons.dark_mode), title: Text('Dark')),
        ),
      ],
    );
  }
}

class DownloadPage extends StatefulWidget {
  const DownloadPage({
    required this.api,
    required this.themeController,
    super.key,
  });

  final DownloadApi api;
  final ThemeController themeController;

  @override
  State<DownloadPage> createState() => _DownloadPageState();
}

/// A download job paired with the media title we already knew when it was
/// queued. The server only fills in the title once the job completes, so this
/// keeps the card readable from the moment it appears.
class _QueuedJob {
  const _QueuedJob(this.job, this.previewTitle);

  final DownloadJob job;
  final String? previewTitle;

  _QueuedJob withJob(DownloadJob updated) => _QueuedJob(updated, previewTitle);

  String get displayTitle =>
      job.displayName ?? previewTitle ?? _shortSourceLabel(job.sourceUrl);
}

String _shortSourceLabel(String url) {
  final uri = Uri.tryParse(url);
  if (uri == null) return url;
  final segments = uri.pathSegments.where((s) => s.isNotEmpty).toList();
  final id = uri.queryParameters['v'] ??
      (segments.isNotEmpty ? segments.last : null);
  return id == null || id.isEmpty ? url : '$id · ${uri.host}';
}

class _DownloadPageState extends State<DownloadPage> {
  final _urlController = TextEditingController();
  final List<_QueuedJob> _jobs = [];
  MediaPreview? _preview;
  Timer? _pollTimer;
  StreamSubscription<String>? _shareSubscription;
  Set<int> _selectedMedia = {};
  String _format = 'mp4';
  String? _quality;
  String? _audioBitrate;
  String? _error;
  String? _warning;
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    // Share intents only exist on mobile; the plugin has no desktop or web side.
    final mobile = !kIsWeb &&
        (defaultTargetPlatform == TargetPlatform.android ||
            defaultTargetPlatform == TargetPlatform.iOS);
    if (mobile) {
      _consumeInitialShare();
      _shareSubscription = const ShareIntentService().urlStream().listen(
        _applySharedUrl,
      );
    }
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _shareSubscription?.cancel();
    _urlController.dispose();
    super.dispose();
  }

  Future<void> _inspectUrl() async {
    final sourceUrl = _urlController.text.trim();
    if (sourceUrl.isEmpty) {
      setState(() => _error = 'Enter a YouTube or Instagram URL.');
      return;
    }
    setState(() {
      _error = null;
      _warning = null;
      _submitting = true;
    });
    try {
      final preview = await widget.api.preview(sourceUrl);
      if (!mounted) return;
      setState(() {
        _preview = preview;
        _selectedMedia = preview.mediaItems == null
            ? {}
            : preview.mediaItems!.map((item) => item.index).toSet();
      });
    } on DownloadApiException catch (error) {
      if (!mounted) return;
      setState(() {
        if (error.statusCode == 410) {
          _warning = error.message;
        } else {
          _error = error.message;
        }
      });
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Could not reach the download server.');
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _consumeInitialShare() async {
    final url = await const ShareIntentService().initialUrl();
    if (url != null && mounted) _applySharedUrl(url);
  }

  void _applySharedUrl(String url) {
    _urlController.text = url;
    _urlController.selection = TextSelection.collapsed(offset: url.length);
    _inspectUrl();
  }

  bool _isActive(DownloadJob job) =>
      job.status == DownloadStatus.queued ||
      job.status == DownloadStatus.downloading;

  Future<void> _addToQueue() async {
    final sourceUrl = _urlController.text.trim();
    if (_preview == null) {
      await _inspectUrl();
      return;
    }
    setState(() {
      _error = null;
      _warning = null;
      _submitting = true;
    });
    try {
      final isCarousel = _preview!.isCarouselCapable;
      final job = await widget.api.createDownload(
        sourceUrl: sourceUrl,
        outputFormat: _format,
        videoQuality: isCarousel ? null : _quality,
        audioBitrate: isCarousel ? null : _audioBitrate,
        mediaSelection: isCarousel ? _orderedSelection() : null,
      );
      if (!mounted) return;
      final title = _preview?.title;
      setState(() {
        _jobs.insert(0, _QueuedJob(job, title));
        _preview = null;
        _selectedMedia = {};
        _quality = null;
        _audioBitrate = null;
        _format = 'mp4';
        _warning = null;
        _urlController.clear();
      });
      _ensurePolling();
    } on DownloadApiException catch (error) {
      if (!mounted) return;
      setState(() {
        if (error.statusCode == 410) {
          _warning = error.message;
        } else {
          _error = error.message;
        }
      });
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Could not reach the download server.');
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  void _ensurePolling() {
    _pollTimer ??= Timer.periodic(
      const Duration(seconds: 1),
      (_) => _refreshActive(),
    );
  }

  Future<void> _refreshActive() async {
    final active = _jobs.where((entry) => _isActive(entry.job)).toList();
    if (active.isEmpty) {
      _pollTimer?.cancel();
      _pollTimer = null;
      return;
    }
    for (final entry in active) {
      try {
        final fresh = await widget.api.getDownload(entry.job.id);
        if (!mounted) return;
        setState(() => _replaceJob(fresh));
      } on DownloadApiException catch (error) {
        if (mounted) setState(() => _error = error.message);
      }
    }
  }

  Future<void> _cancel(DownloadJob job) async {
    try {
      final cancelled = await widget.api.cancelDownload(job.id);
      if (!mounted) return;
      setState(() => _replaceJob(cancelled));
    } on DownloadApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    }
  }

  void _replaceJob(DownloadJob updated) {
    final index = _jobs.indexWhere((entry) => entry.job.id == updated.id);
    if (index != -1) _jobs[index] = _jobs[index].withJob(updated);
  }

  List<int> _orderedSelection() {
    final items = _preview?.mediaItems ?? const [];
    return [
      for (final item in items)
        if (_selectedMedia.contains(item.index)) item.index,
    ];
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        titleSpacing: 12,
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Image.asset(
              'assets/icon/logo_mark.png',
              height: 26,
              filterQuality: FilterQuality.medium,
            ),
            const SizedBox(width: 10),
            const Text('Xownloader'),
          ],
        ),
        actions: [ThemeModeMenu(controller: widget.themeController)],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 720),
          child: ListView(
            padding: const EdgeInsets.all(24),
            children: [
              ..._buildComposer(context),
              const SizedBox(height: 28),
              _QueueSection(
                jobs: _jobs,
                api: widget.api,
                onCancel: _cancel,
              ),
            ],
          ),
        ),
      ),
    );
  }

  List<Widget> _buildComposer(BuildContext context) {
    return [
      Text(
        'Download media',
        style: Theme.of(context).textTheme.headlineMedium,
      ),
      const SizedBox(height: 8),
      Text('Server: ${AppConfig.serverUrl}'),
      const SizedBox(height: 24),
      TextField(
        controller: _urlController,
        keyboardType: TextInputType.url,
        decoration: const InputDecoration(
          labelText: 'YouTube or Instagram URL',
          helperText:
              'youtube.com/watch · youtu.be · instagram.com/p · /reel · /stories',
          helperMaxLines: 2,
        ),
        onSubmitted: (_) => _inspectUrl(),
      ),
      const SizedBox(height: 16),
      if (_preview == null) ...[
        const _SupportedLinks(),
        const SizedBox(height: 16),
        FilledButton.icon(
          onPressed: _submitting ? null : _inspectUrl,
          icon: _submitting
              ? const _ButtonSpinner()
              : const Icon(Icons.search),
          label: Text(_submitting ? 'Inspecting...' : 'Inspect URL'),
        ),
      ]
      else if (_preview!.isCarouselCapable) ...[
        _PreviewCard(preview: _preview!),
        const SizedBox(height: 8),
        for (final item in _preview!.mediaItems!)
          CheckboxListTile(
            value: _selectedMedia.contains(item.index),
            onChanged: (checked) => setState(() {
              if (checked ?? false) {
                _selectedMedia.add(item.index);
              } else {
                _selectedMedia.remove(item.index);
              }
            }),
            title: Text('Item ${item.index + 1} · ${item.type}'),
            subtitle: item.durationSeconds != null
                ? Text(formatDuration(item.durationSeconds))
                : null,
            secondary: Icon(
              item.type == 'video' ? Icons.videocam : Icons.image,
            ),
          ),
        const SizedBox(height: 16),
        FilledButton.icon(
          onPressed: (_submitting || _selectedMedia.isEmpty)
              ? null
              : _addToQueue,
          icon: _submitting
              ? const _ButtonSpinner()
              : const Icon(Icons.playlist_add),
          label: Text(_submitting ? 'Submitting...' : 'Add to queue'),
        ),
      ] else ...[
        _PreviewCard(preview: _preview!),
        const SizedBox(height: 16),
        Wrap(
          spacing: 16,
          runSpacing: 16,
          children: [
            DropdownButton<String>(
              value: _format,
              items: _preview!.allowedOutputFormats
                  .map(
                    (format) => DropdownMenuItem(
                      value: format,
                      child: Text(format.toUpperCase()),
                    ),
                  )
                  .toList(),
              onChanged: (value) => setState(() => _format = value!),
            ),
            DropdownButton<String?>(
              value: _quality,
              items: [
                const DropdownMenuItem(
                  value: null,
                  child: Text('Auto quality'),
                ),
                ..._preview!.allowedVideoQualities.map(
                  (quality) => DropdownMenuItem(
                    value: quality,
                    child: Text(quality),
                  ),
                ),
              ],
              onChanged: (value) => setState(() => _quality = value),
            ),
            DropdownButton<String?>(
              value: _audioBitrate,
              items: [
                const DropdownMenuItem(
                  value: null,
                  child: Text('Auto audio'),
                ),
                ..._preview!.allowedAudioBitrates.map(
                  (bitrate) => DropdownMenuItem(
                    value: bitrate,
                    child: Text(bitrate),
                  ),
                ),
              ],
              onChanged: (value) => setState(() => _audioBitrate = value),
            ),
          ],
        ),
        const SizedBox(height: 16),
        FilledButton.icon(
          onPressed: _submitting ? null : _addToQueue,
          icon: _submitting
              ? const _ButtonSpinner()
              : const Icon(Icons.playlist_add),
          label: Text(_submitting ? 'Submitting...' : 'Add to queue'),
        ),
      ],
      if (_error != null) ...[
        const SizedBox(height: 16),
        _ErrorBanner(message: _error!),
      ],
      if (_warning != null) ...[
        const SizedBox(height: 16),
        _WarningBanner(message: _warning!),
      ],
    ];
  }
}

class _PreviewCard extends StatelessWidget {
  const _PreviewCard({required this.preview});

  final MediaPreview preview;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        leading: preview.thumbnail == null
            ? const Icon(Icons.video_library)
            : Image.network(
                preview.thumbnail!,
                width: 96,
                fit: BoxFit.cover,
                // Provider thumbnail hosts send no CORS headers, so the CanvasKit
                // web renderer cannot read the bytes. Fall back to an <img> element.
                webHtmlElementStrategy: WebHtmlElementStrategy.fallback,
                errorBuilder: (context, error, stackTrace) {
                  return const Icon(Icons.broken_image);
                },
                loadingBuilder: (context, child, progress) {
                  if (progress == null) return child;
                  return const SizedBox(
                    width: 96,
                    height: 54,
                    child: Center(
                      child: SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                    ),
                  );
                },
              ),
        title: Text(preview.title),
        subtitle: Text(
          [
            if (preview.uploader != null) preview.uploader!,
            if (preview.durationSeconds != null)
              formatDuration(preview.durationSeconds),
          ].join(' - '),
        ),
      ),
    );
  }
}

/// The list of downloads, grouped visually into one "queue" surface.
class _QueueSection extends StatelessWidget {
  const _QueueSection({
    required this.jobs,
    required this.api,
    required this.onCancel,
  });

  final List<_QueuedJob> jobs;
  final DownloadApi api;
  final void Function(DownloadJob) onCancel;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;

    if (jobs.isEmpty) {
      return _EmptyQueueFrame(
        child: Column(
          children: [
            Icon(Icons.inbox_outlined, color: scheme.onSurfaceVariant),
            const SizedBox(height: 8),
            Text(
              'Your queue is empty',
              style: Theme.of(context).textTheme.titleSmall,
            ),
            const SizedBox(height: 2),
            Text(
              'Inspect a URL above to add the first download.',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: scheme.onSurfaceVariant,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      );
    }

    return Container(
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 14),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.only(left: 2, bottom: 10),
            child: Row(
              children: [
                Text(
                  'QUEUE',
                  style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    fontWeight: FontWeight.w700,
                    letterSpacing: 1.2,
                    color: scheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(width: 8),
                _CountPill(count: jobs.length),
              ],
            ),
          ),
          for (var i = 0; i < jobs.length; i++) ...[
            if (i > 0) const SizedBox(height: 10),
            _JobCard(
              entry: jobs[i],
              api: api,
              onCancel: () => onCancel(jobs[i].job),
            ),
          ],
        ],
      ),
    );
  }
}

class _CountPill extends StatelessWidget {
  const _CountPill({required this.count});

  final int count;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 1),
      decoration: BoxDecoration(
        color: scheme.primary.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        '$count',
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
          fontWeight: FontWeight.w700,
          color: scheme.primary,
        ),
      ),
    );
  }
}

({Color color, IconData icon, String label}) _statusStyle(
  DownloadStatus status,
  ColorScheme scheme,
) {
  return switch (status) {
    DownloadStatus.queued => (
      color: scheme.onSurfaceVariant,
      icon: Icons.schedule,
      label: 'QUEUED',
    ),
    DownloadStatus.downloading => (
      color: const Color(0xFF3B82F6),
      icon: Icons.download,
      label: 'DOWNLOADING',
    ),
    DownloadStatus.completed => (
      color: const Color(0xFF22C55E),
      icon: Icons.check_circle,
      label: 'COMPLETED',
    ),
    DownloadStatus.failed => (
      color: scheme.error,
      icon: Icons.error_outline,
      label: 'FAILED',
    ),
    DownloadStatus.cancelled => (
      color: scheme.outline,
      icon: Icons.block,
      label: 'CANCELLED',
    ),
  };
}

class _StatusBadge extends StatelessWidget {
  const _StatusBadge({required this.status});

  final DownloadStatus status;

  @override
  Widget build(BuildContext context) {
    final style = _statusStyle(status, Theme.of(context).colorScheme);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: style.color.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(style.icon, size: 13, color: style.color),
          const SizedBox(width: 4),
          Text(
            style.label,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: style.color,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.6,
            ),
          ),
        ],
      ),
    );
  }
}

class _JobCard extends StatelessWidget {
  const _JobCard({required this.entry, required this.api, required this.onCancel});

  final _QueuedJob entry;
  final DownloadApi api;
  final VoidCallback onCancel;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final job = entry.job;
    final style = _statusStyle(job.status, scheme);

    return Container(
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: scheme.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: scheme.outlineVariant),
      ),
      child: IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Container(width: 4, color: style.color),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(14, 12, 12, 12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            entry.displayTitle,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: Theme.of(context).textTheme.titleSmall
                                ?.copyWith(fontWeight: FontWeight.w600),
                          ),
                        ),
                        const SizedBox(width: 10),
                        _StatusBadge(status: job.status),
                      ],
                    ),
                    ..._detail(context, job),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  List<Widget> _detail(BuildContext context, DownloadJob job) {
    final scheme = Theme.of(context).colorScheme;
    final muted = Theme.of(context).textTheme.bodySmall?.copyWith(
      color: scheme.onSurfaceVariant,
    );

    switch (job.status) {
      case DownloadStatus.downloading:
        return [
          const SizedBox(height: 12),
          ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              value: job.progressPercent / 100,
              minHeight: 6,
            ),
          ),
          const SizedBox(height: 6),
          Row(
            children: [
              Text('${job.progressPercent.toStringAsFixed(0)}%', style: muted),
              const Spacer(),
              _CancelButton(onCancel: onCancel),
            ],
          ),
        ];
      case DownloadStatus.queued:
        return [
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(child: Text('Waiting for a free slot', style: muted)),
              _CancelButton(onCancel: onCancel),
            ],
          ),
        ];
      case DownloadStatus.failed:
        return [
          const SizedBox(height: 10),
          _ErrorBanner(message: job.error ?? 'The download failed.'),
        ];
      case DownloadStatus.cancelled:
        return [
          const SizedBox(height: 6),
          Text('You cancelled this download.', style: muted),
        ];
      case DownloadStatus.completed:
        final artifacts = job.artifacts;
        if (artifacts.length <= 1) {
          final only = artifacts.isEmpty ? null : artifacts.first;
          return [
            const SizedBox(height: 12),
            ResultActions(
              fileUri: only == null
                  ? api.fileUri(job.id, displayName: job.displayName)
                  : api.mediaUri(
                      job.id,
                      only.index,
                      displayName: only.displayName,
                    ),
            ),
          ];
        }
        return [
          const SizedBox(height: 12),
          for (final artifact in artifacts) ...[
            Text(
              artifact.displayName,
              style: Theme.of(context).textTheme.bodySmall,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 4),
            ResultActions(
              fileUri: api.mediaUri(
                job.id,
                artifact.index,
                displayName: artifact.displayName,
              ),
            ),
            const SizedBox(height: 10),
          ],
        ];
    }
  }
}

class _CancelButton extends StatelessWidget {
  const _CancelButton({required this.onCancel});

  final VoidCallback onCancel;

  @override
  Widget build(BuildContext context) {
    return TextButton.icon(
      onPressed: onCancel,
      style: TextButton.styleFrom(
        visualDensity: VisualDensity.compact,
        foregroundColor: Theme.of(context).colorScheme.onSurfaceVariant,
      ),
      icon: const Icon(Icons.close, size: 16),
      label: const Text('Cancel'),
    );
  }
}

/// A quiet outlined panel for the empty-queue placeholder.
/// Quiet reference panel shown before the first inspect, so a new user knows
/// which links work.
class _SupportedLinks extends StatelessWidget {
  const _SupportedLinks();

  static const _rows = <(String, String, String)>[
    ('YouTube', 'video or short', 'youtube.com/watch?v=… · youtu.be/…'),
    ('Instagram', 'post or reel', 'instagram.com/p/… · instagram.com/reel/…'),
    ('Instagram', 'story or highlight', 'instagram.com/stories/…'),
  ];

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final text = Theme.of(context).textTheme;
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: scheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'SUPPORTED LINKS',
            style: text.labelSmall?.copyWith(
              fontWeight: FontWeight.w700,
              letterSpacing: 1.1,
              color: scheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 10),
          for (final (provider, what, example) in _rows)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text.rich(
                    TextSpan(
                      children: [
                        TextSpan(
                          text: provider,
                          style: text.bodyMedium?.copyWith(
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        TextSpan(
                          text: '  $what',
                          style: text.bodyMedium?.copyWith(
                            color: scheme.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Text(
                    example,
                    style: text.bodySmall?.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
          Text(
            'Carousels and highlights let you pick which items to download.',
            style: text.bodySmall?.copyWith(color: scheme.onSurfaceVariant),
          ),
        ],
      ),
    );
  }
}

class _EmptyQueueFrame extends StatelessWidget {
  const _EmptyQueueFrame({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: Theme.of(context).colorScheme.outlineVariant,
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 32, horizontal: 24),
        child: Center(child: child),
      ),
    );
  }
}

class _ButtonSpinner extends StatelessWidget {
  const _ButtonSpinner();

  @override
  Widget build(BuildContext context) {
    return const SizedBox(
      width: 18,
      height: 18,
      child: CircularProgressIndicator(strokeWidth: 2),
    );
  }
}

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: scheme.errorContainer,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.error_outline, color: scheme.onErrorContainer, size: 20),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              message,
              style: TextStyle(color: scheme.onErrorContainer),
            ),
          ),
        ],
      ),
    );
  }
}

class _WarningBanner extends StatelessWidget {
  const _WarningBanner({required this.message});

  final String message;

  // M3 has no amber scheme slot; fixed amber pair, legible in both themes.
  static const _bg = Color(0xFFFFF3CD);
  static const _fg = Color(0xFF664D03);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: _bg,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.warning_amber_rounded, color: _fg, size: 20),
          const SizedBox(width: 8),
          Expanded(
            child: Text(message, style: const TextStyle(color: _fg)),
          ),
        ],
      ),
    );
  }
}
