import 'dart:async';

import 'package:flutter/material.dart';

import '../config/app_config.dart';
import '../l10n/app_strings_scope.dart';
import '../models/admin_status.dart';
import '../models/download_job.dart';
import '../services/admin_api.dart';
import '../services/admin_token_store.dart';
import '../services/download_api.dart';
import '../utils/byte_format.dart';
import '../widgets/result_actions.dart';
import '../widgets/status_badge.dart';
import 'admin_gate_page.dart';

class AdminHomePage extends StatefulWidget {
  const AdminHomePage({
    required this.tokenStore,
    required this.token,
    this.api,
    super.key,
  });

  final AdminTokenStore tokenStore;
  final String token;
  final AdminApi? api;

  @override
  State<AdminHomePage> createState() => _AdminHomePageState();
}

class _AdminHomePageState extends State<AdminHomePage> {
  late final AdminApi _api =
      widget.api ?? AdminApi(baseUrl: AppConfig.serverUrl, token: widget.token);

  Future<AdminStatus>? _statusFuture;
  Future<List<DownloadJob>>? _jobsFuture;
  bool _signedOut = false;

  @override
  void initState() {
    super.initState();
    _statusFuture = _guarded(_api.fetchStatus());
    _jobsFuture = _guarded(_api.fetchJobs());
  }

  /// Runs [future]; on a 401, clears the stored token and swaps this page
  /// for the gate (with a "session expired" message) exactly once, even if
  /// both requests come back 401 at the same time. A 401 does not rethrow:
  /// this page is being replaced, so the returned future is left
  /// permanently pending instead — nothing is left around to treat it as an
  /// unhandled rejection, and any FutureBuilder still attached simply stays
  /// in its loading state for the instant before the page is gone. Any
  /// other error (network, 5xx) does rethrow, so the tab's own FutureBuilder
  /// can show it.
  Future<T> _guarded<T>(Future<T> future) async {
    try {
      return await future;
    } on DownloadApiException catch (error) {
      if (error.statusCode == 401) {
        _handleSessionExpired();
        return Completer<T>().future;
      }
      rethrow;
    }
  }

  void _handleSessionExpired() {
    if (_signedOut || !mounted) return;
    _signedOut = true;
    final message = context.strings.adminSessionExpiredMessage;
    widget.tokenStore.delete();
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (_) => AdminGatePage(tokenStore: widget.tokenStore, initialError: message),
      ),
    );
  }

  Future<void> _signOut() async {
    await widget.tokenStore.delete();
    if (mounted) Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final strings = context.strings;
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: Text(strings.adminHomeTitle),
          actions: [
            IconButton(
              icon: const Icon(Icons.logout),
              tooltip: strings.adminSignOutTooltip,
              onPressed: _signOut,
            ),
          ],
          bottom: TabBar(
            tabs: [
              Tab(text: strings.adminStatusTab),
              Tab(text: strings.adminJobsTab),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            _StatusTab(future: _statusFuture!),
            _JobsTab(
              future: _jobsFuture!,
              api: _api,
              onRefresh: () async {
                setState(() => _jobsFuture = _guarded(_api.fetchJobs()));
                await _jobsFuture;
              },
            ),
          ],
        ),
      ),
    );
  }
}

class _StatusTab extends StatelessWidget {
  const _StatusTab({required this.future});

  final Future<AdminStatus> future;

  @override
  Widget build(BuildContext context) {
    final strings = context.strings;
    return FutureBuilder<AdminStatus>(
      future: future,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return Center(child: Text(strings.serverUnreachableError));
        }
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        final status = snapshot.data!;
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _RuntimePanel(runtime: status.runtime),
            const SizedBox(height: 20),
            _JobCountGrid(counts: status.jobCounts),
            const SizedBox(height: 20),
            _DiskUsageCard(freeBytes: status.freeBytes, totalBytes: status.totalBytes),
          ],
        );
      },
    );
  }
}

class _RuntimePanel extends StatelessWidget {
  const _RuntimePanel({required this.runtime});

  final Map<String, bool> runtime;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final strings = context.strings;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: scheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final entry in runtime.entries)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 6),
              child: Row(
                children: [
                  Icon(
                    entry.value ? Icons.check_circle : Icons.error_outline,
                    size: 18,
                    color: entry.value ? const Color(0xFF22C55E) : scheme.error,
                  ),
                  const SizedBox(width: 10),
                  Text(strings.adminRuntimeLabel(entry.key)),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _JobCountGrid extends StatelessWidget {
  const _JobCountGrid({required this.counts});

  final Map<String, int> counts;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final strings = context.strings;

    Color colorFor(DownloadStatus status) => jobStatusStyle(status, scheme, strings).color;
    IconData iconFor(DownloadStatus status) => jobStatusStyle(status, scheme, strings).icon;

    final tiles = [
      (scheme.primary, Icons.list_alt, strings.adminJobsTotalLabel, counts['total'] ?? 0),
      (
        colorFor(DownloadStatus.queued),
        iconFor(DownloadStatus.queued),
        strings.statusQueued,
        counts['queued'] ?? 0,
      ),
      (
        colorFor(DownloadStatus.downloading),
        iconFor(DownloadStatus.downloading),
        strings.statusDownloading,
        counts['downloading'] ?? 0,
      ),
      (
        colorFor(DownloadStatus.completed),
        iconFor(DownloadStatus.completed),
        strings.statusCompleted,
        counts['completed'] ?? 0,
      ),
      (
        colorFor(DownloadStatus.failed),
        iconFor(DownloadStatus.failed),
        strings.statusFailed,
        counts['failed'] ?? 0,
      ),
    ];

    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 12,
      crossAxisSpacing: 12,
      childAspectRatio: 2.6,
      children: [
        for (final (color, icon, label, value) in tiles)
          _StatTile(color: color, icon: icon, label: label, value: value),
      ],
    );
  }
}

class _StatTile extends StatelessWidget {
  const _StatTile({
    required this.color,
    required this.icon,
    required this.label,
    required this.value,
  });

  final Color color;
  final IconData icon;
  final String label;
  final int value;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withValues(alpha: 0.28)),
      ),
      child: Row(
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  '$value',
                  style: text.titleLarge?.copyWith(fontWeight: FontWeight.w700, color: color),
                ),
                Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: text.labelSmall?.copyWith(color: color),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _DiskUsageCard extends StatelessWidget {
  const _DiskUsageCard({required this.freeBytes, required this.totalBytes});

  final int freeBytes;
  final int totalBytes;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final text = Theme.of(context).textTheme;
    final strings = context.strings;

    final usedBytes = totalBytes > freeBytes ? totalBytes - freeBytes : 0;
    final usedFraction = totalBytes > 0 ? usedBytes / totalBytes : 0.0;
    final freePercent = totalBytes > 0 ? (100 - usedFraction * 100).round() : 0;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: scheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text(
                '$freePercent%',
                style: text.headlineMedium?.copyWith(fontWeight: FontWeight.w700),
              ),
              const SizedBox(width: 6),
              Text(
                strings.adminDiskFreeLabel,
                style: text.bodyMedium?.copyWith(color: scheme.onSurfaceVariant),
              ),
            ],
          ),
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              value: usedFraction.clamp(0.0, 1.0),
              minHeight: 8,
              backgroundColor: scheme.surfaceContainerHighest,
              color: usedFraction > 0.9 ? scheme.error : scheme.primary,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            strings.adminStorageFreeOfTotal(formatBytes(freeBytes), formatBytes(totalBytes)),
            style: text.bodySmall?.copyWith(color: scheme.onSurfaceVariant),
          ),
        ],
      ),
    );
  }
}

class _JobsTab extends StatelessWidget {
  const _JobsTab({required this.future, required this.api, required this.onRefresh});

  final Future<List<DownloadJob>> future;
  final AdminApi api;
  final Future<void> Function() onRefresh;

  @override
  Widget build(BuildContext context) {
    final strings = context.strings;
    return FutureBuilder<List<DownloadJob>>(
      future: future,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return Center(child: Text(strings.serverUnreachableError));
        }
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        final jobs = snapshot.data!;
        if (jobs.isEmpty) {
          return Center(child: Text(strings.adminNoJobsMessage));
        }
        return RefreshIndicator(
          onRefresh: onRefresh,
          child: ListView.builder(
            padding: const EdgeInsets.all(16),
            itemCount: jobs.length,
            itemBuilder: (context, index) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: _AdminJobCard(job: jobs[index], api: api),
            ),
          ),
        );
      },
    );
  }
}

class _AdminJobCard extends StatelessWidget {
  const _AdminJobCard({required this.job, required this.api});

  final DownloadJob job;
  final AdminApi api;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final style = jobStatusStyle(job.status, scheme, context.strings);

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
                            job.sourceUrl,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: Theme.of(
                              context,
                            ).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w600),
                          ),
                        ),
                        const SizedBox(width: 10),
                        StatusBadge(status: job.status),
                      ],
                    ),
                    ..._detail(context),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  List<Widget> _detail(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final strings = context.strings;
    final muted = Theme.of(
      context,
    ).textTheme.bodySmall?.copyWith(color: scheme.onSurfaceVariant);

    switch (job.status) {
      case DownloadStatus.downloading:
        return [
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              value: job.progressPercent / 100,
              minHeight: 6,
            ),
          ),
          const SizedBox(height: 4),
          Text('${job.progressPercent.toStringAsFixed(0)}%', style: muted),
        ];
      case DownloadStatus.queued:
        return [const SizedBox(height: 6), Text(strings.waitingForSlot, style: muted)];
      case DownloadStatus.failed:
        return [
          const SizedBox(height: 8),
          Text(job.error ?? strings.downloadFailedFallback, style: muted),
        ];
      case DownloadStatus.cancelled:
        return [const SizedBox(height: 6), Text(strings.cancelledMessage, style: muted)];
      case DownloadStatus.completed:
        final artifacts = job.artifacts;
        if (artifacts.length <= 1) {
          final only = artifacts.isEmpty ? null : artifacts.first;
          return [
            const SizedBox(height: 10),
            ResultActions(
              fileUri: only == null
                  ? api.fileUri(job.id, displayName: job.displayName)
                  : api.mediaUri(job.id, only.index, displayName: only.displayName),
            ),
          ];
        }
        return [
          const SizedBox(height: 10),
          for (final artifact in artifacts) ...[
            Text(
              artifact.displayName,
              style: muted,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 4),
            ResultActions(
              fileUri: api.mediaUri(job.id, artifact.index, displayName: artifact.displayName),
            ),
            const SizedBox(height: 8),
          ],
        ];
    }
  }
}
