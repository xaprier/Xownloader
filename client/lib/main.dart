import 'dart:async';

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
  MediaPreview? _preview;
  DownloadJob? _job;
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
    _consumeInitialShare();
    _shareSubscription = const ShareIntentService().urlStream().listen(
      _applySharedUrl,
    );
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
      _job = null;
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

  Future<void> _startDownload() async {
    final sourceUrl = _urlController.text.trim();
    if (_preview == null) {
      await _inspectUrl();
      return;
    }
    setState(() {
      _error = null;
      _job = null;
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
      setState(() => _job = job);
      _startPolling(job.id);
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

  void _startPolling(String jobId) {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 1), (_) async {
      try {
        final job = await widget.api.getDownload(jobId);
        if (!mounted) return;
        setState(() => _job = job);
        if ({
          DownloadStatus.completed,
          DownloadStatus.failed,
          DownloadStatus.cancelled,
        }.contains(job.status)) {
          _pollTimer?.cancel();
        }
      } on DownloadApiException catch (error) {
        if (mounted) setState(() => _error = error.message);
      }
    });
  }

  Future<void> _cancelDownload() async {
    final job = _job;
    if (job == null) return;
    _pollTimer?.cancel();
    try {
      final cancelled = await widget.api.cancelDownload(job.id);
      if (mounted) setState(() => _job = cancelled);
    } on DownloadApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    final job = _job;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Xownloader'),
        actions: [ThemeModeMenu(controller: widget.themeController)],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 720),
          child: ListView(
            padding: const EdgeInsets.all(24),
            children: [
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
                      onChanged: (value) =>
                          setState(() => _audioBitrate = value),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                FilledButton.icon(
                  onPressed: _submitting ? null : _startDownload,
                  icon: _submitting
                      ? const _ButtonSpinner()
                      : const Icon(Icons.download),
                  label: Text(_submitting ? 'Submitting...' : 'Start download'),
                ),
              ],
              if (_error != null) ...[
                const SizedBox(height: 16),
                _ErrorBanner(message: _error!),
              ],
              if (job != null) ...[
                const SizedBox(height: 24),
                _JobStatusCard(
                  job: job,
                  api: widget.api,
                  onCancel: _cancelDownload,
                ),
              ],
            ],
          ),
        ),
      ),
    );
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
            if (preview.durationSeconds != null) '${preview.durationSeconds}s',
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
              ResultActions(fileUri: api.fileUri(job.id)),
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
