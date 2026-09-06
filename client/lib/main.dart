import 'dart:async';

import 'package:flutter/foundation.dart' show kIsWeb;
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

class _DownloadPageState extends State<DownloadPage> {
  final _urlController = TextEditingController();
  final List<DownloadJob> _jobs = [];
  MediaPreview? _preview;
  Timer? _pollTimer;
  StreamSubscription<String>? _shareSubscription;
  String _format = 'mp4';
  String? _quality;
  String? _audioBitrate;
  String? _error;
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    // The share-intent plugin has no web implementation.
    if (!kIsWeb) {
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
      setState(() => _error = 'Enter a YouTube URL.');
      return;
    }
    setState(() {
      _error = null;
      _submitting = true;
    });
    try {
      final preview = await widget.api.preview(sourceUrl);
      if (!mounted) return;
      setState(() => _preview = preview);
    } on DownloadApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
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
      _submitting = true;
    });
    try {
      final job = await widget.api.createDownload(
        sourceUrl: sourceUrl,
        outputFormat: _format,
        videoQuality: _quality,
        audioBitrate: _audioBitrate,
      );
      if (!mounted) return;
      setState(() {
        _jobs.insert(0, job);
        _preview = null;
        _quality = null;
        _audioBitrate = null;
        _format = 'mp4';
        _urlController.clear();
      });
      _ensurePolling();
    } on DownloadApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
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
    final active = _jobs.where(_isActive).toList();
    if (active.isEmpty) {
      _pollTimer?.cancel();
      _pollTimer = null;
      return;
    }
    for (final job in active) {
      try {
        final fresh = await widget.api.getDownload(job.id);
        if (!mounted) return;
        setState(() {
          final index = _jobs.indexWhere((j) => j.id == fresh.id);
          if (index != -1) _jobs[index] = fresh;
        });
      } on DownloadApiException catch (error) {
        if (mounted) setState(() => _error = error.message);
      }
    }
  }

  Future<void> _cancel(DownloadJob job) async {
    try {
      final cancelled = await widget.api.cancelDownload(job.id);
      if (!mounted) return;
      setState(() {
        final index = _jobs.indexWhere((j) => j.id == cancelled.id);
        if (index != -1) _jobs[index] = cancelled;
      });
    } on DownloadApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Xownloader'),
          actions: [ThemeModeMenu(controller: widget.themeController)],
          bottom: const TabBar(
            tabs: [Tab(text: 'Active'), Tab(text: 'Done')],
          ),
        ),
        body: TabBarView(
          children: [_buildActiveTab(context), _buildDoneTab(context)],
        ),
      ),
    );
  }

  Widget _tabShell({required List<Widget> children}) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 720),
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: children,
        ),
      ),
    );
  }

  Widget _buildActiveTab(BuildContext context) {
    final active = _jobs.where(_isActive).toList();
    return _tabShell(
      children: [
        ..._buildComposer(context),
        for (final job in active) ...[
          const SizedBox(height: 16),
          _JobStatusCard(
            job: job,
            api: widget.api,
            onCancel: () => _cancel(job),
          ),
        ],
      ],
    );
  }

  Widget _buildDoneTab(BuildContext context) {
    final done = _jobs.where((job) => !_isActive(job)).toList();
    if (done.isEmpty) {
      return _tabShell(
        children: const [
          Padding(
            padding: EdgeInsets.only(top: 48),
            child: Center(child: Text('No finished downloads yet.')),
          ),
        ],
      );
    }
    return _tabShell(
      children: [
        for (final job in done) ...[
          _JobStatusCard(job: job, api: widget.api, onCancel: () => _cancel(job)),
          const SizedBox(height: 16),
        ],
      ],
    );
  }

  List<Widget> _buildComposer(BuildContext context) {
    return [
      Text(
        'Download YouTube media',
        style: Theme.of(context).textTheme.headlineMedium,
      ),
      const SizedBox(height: 8),
      Text('Server: ${AppConfig.serverUrl}'),
      const SizedBox(height: 24),
      TextField(
        controller: _urlController,
        keyboardType: TextInputType.url,
        decoration: const InputDecoration(labelText: 'YouTube URL'),
        onSubmitted: (_) => _inspectUrl(),
      ),
      const SizedBox(height: 16),
      if (_preview == null)
        FilledButton.icon(
          onPressed: _submitting ? null : _inspectUrl,
          icon: _submitting
              ? const _ButtonSpinner()
              : const Icon(Icons.search),
          label: Text(_submitting ? 'Inspecting...' : 'Inspect URL'),
        )
      else ...[
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

class _JobStatusCard extends StatelessWidget {
  const _JobStatusCard({
    required this.job,
    required this.api,
    required this.onCancel,
  });

  final DownloadJob job;
  final DownloadApi api;
  final VoidCallback onCancel;

  @override
  Widget build(BuildContext context) {
    final active =
        job.status == DownloadStatus.queued ||
        job.status == DownloadStatus.downloading;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Job ${job.id}',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Text('Status: ${job.status.name}'),
            if (active) ...[
              const SizedBox(height: 8),
              LinearProgressIndicator(value: job.progressPercent / 100),
              Text('${job.progressPercent.toStringAsFixed(1)}%'),
              Align(
                alignment: Alignment.centerRight,
                child: TextButton.icon(
                  onPressed: onCancel,
                  icon: const Icon(Icons.cancel_outlined),
                  label: const Text('Cancel'),
                ),
              ),
            ],
            if (job.error != null) ...[
              const SizedBox(height: 8),
              _ErrorBanner(message: job.error!),
            ],
            if (job.status == DownloadStatus.completed) ...[
              const SizedBox(height: 8),
              ResultActions(
                fileUri: api.fileUri(job.id, displayName: job.displayName),
              ),
            ],
          ],
        ),
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
