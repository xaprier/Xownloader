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
  Future<String>? _metricsFuture;
  bool _signedOut = false;

  @override
  void initState() {
    super.initState();
    _statusFuture = _guarded(_api.fetchStatus());
    _jobsFuture = _guarded(_api.fetchJobs());
    _metricsFuture = _guarded(_api.fetchMetricsText());
  }

  /// Runs [future]; on a 401, clears the stored token and swaps this page
  /// for the gate (with a "session expired" message) exactly once, even if
  /// more than one of the three requests comes back 401 at the same time.
  /// A 401 does not rethrow: this page is being replaced, so the returned
  /// future is left permanently pending instead — nothing is left around to
  /// treat it as an unhandled rejection, and any FutureBuilder still
  /// attached simply stays in its loading state for the instant before
  /// the page is gone. Any other error (network, 5xx) does rethrow, so the
  /// tab's own FutureBuilder can show it.
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
      length: 3,
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
              Tab(text: strings.adminMetricsTab),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            _StatusTab(future: _statusFuture!),
            _JobsTab(
              future: _jobsFuture!,
              onRefresh: () async {
                setState(() => _jobsFuture = _guarded(_api.fetchJobs()));
                await _jobsFuture;
              },
            ),
            _MetricsTab(future: _metricsFuture!),
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
            for (final entry in status.runtime.entries)
              ListTile(
                leading: Icon(
                  entry.value ? Icons.check_circle : Icons.error_outline,
                  color: entry.value ? Colors.green : Theme.of(context).colorScheme.error,
                ),
                title: Text(strings.adminRuntimeLabel(entry.key)),
              ),
            const Divider(),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Wrap(
                spacing: 16,
                runSpacing: 8,
                children: [
                  _countChip(strings.adminJobsTotalLabel, status.jobCounts['total']),
                  _countChip(strings.statusQueued, status.jobCounts['queued']),
                  _countChip(strings.statusDownloading, status.jobCounts['downloading']),
                  _countChip(strings.statusCompleted, status.jobCounts['completed']),
                  _countChip(strings.statusFailed, status.jobCounts['failed']),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Text(
                strings.adminStorageFreeOfTotal(
                  formatBytes(status.freeBytes),
                  formatBytes(status.totalBytes),
                ),
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _countChip(String label, int? value) => Chip(label: Text('$label: ${value ?? 0}'));
}

class _JobsTab extends StatelessWidget {
  const _JobsTab({required this.future, required this.onRefresh});

  final Future<List<DownloadJob>> future;
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
            itemCount: jobs.length,
            itemBuilder: (context, index) {
              final job = jobs[index];
              return ListTile(
                title: Text(job.sourceUrl, maxLines: 1, overflow: TextOverflow.ellipsis),
                subtitle: Text(job.status.name),
                trailing: job.status == DownloadStatus.downloading
                    ? Text('${job.progressPercent.toStringAsFixed(0)}%')
                    : null,
              );
            },
          ),
        );
      },
    );
  }
}

class _MetricsTab extends StatelessWidget {
  const _MetricsTab({required this.future});

  final Future<String> future;

  @override
  Widget build(BuildContext context) {
    final strings = context.strings;
    return FutureBuilder<String>(
      future: future,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return Center(child: Text(strings.serverUnreachableError));
        }
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        return SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: SelectableText(
              snapshot.data!,
              style: const TextStyle(fontFamily: 'monospace'),
            ),
          ),
        );
      },
    );
  }
}