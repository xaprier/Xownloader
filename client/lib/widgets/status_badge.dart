import 'package:flutter/material.dart';

import '../l10n/app_strings.dart';
import '../l10n/app_strings_scope.dart';
import '../models/download_job.dart';

/// The color/icon/label for a [DownloadStatus], shared by the main queue and
/// the admin job list so both read the same status language.
({Color color, IconData icon, String label}) jobStatusStyle(
  DownloadStatus status,
  ColorScheme scheme,
  AppStrings strings,
) {
  return switch (status) {
    DownloadStatus.queued => (
      color: scheme.onSurfaceVariant,
      icon: Icons.schedule,
      label: strings.statusQueued,
    ),
    DownloadStatus.downloading => (
      color: const Color(0xFF3B82F6),
      icon: Icons.download,
      label: strings.statusDownloading,
    ),
    DownloadStatus.completed => (
      color: const Color(0xFF22C55E),
      icon: Icons.check_circle,
      label: strings.statusCompleted,
    ),
    DownloadStatus.failed => (
      color: scheme.error,
      icon: Icons.error_outline,
      label: strings.statusFailed,
    ),
    DownloadStatus.cancelled => (
      color: scheme.outline,
      icon: Icons.block,
      label: strings.statusCancelled,
    ),
  };
}

class StatusBadge extends StatelessWidget {
  const StatusBadge({required this.status, super.key});

  final DownloadStatus status;

  @override
  Widget build(BuildContext context) {
    final style = jobStatusStyle(
      status,
      Theme.of(context).colorScheme,
      context.strings,
    );
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
