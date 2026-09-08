import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../config/app_config.dart';
import '../l10n/app_strings_scope.dart';

const _repositoryUrl = 'https://github.com/xaprier/Xownloader';
const _developerUrl = 'https://github.com/xaprier';

/// A quiet, single-column page: what the project is, who built it, and
/// where the source lives. Reachable from the footer link on the download
/// screen.
class AboutPage extends StatelessWidget {
  const AboutPage({super.key});

  @override
  Widget build(BuildContext context) {
    final strings = context.strings;
    final scheme = Theme.of(context).colorScheme;
    final text = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(title: Text(strings.aboutPageTitle)),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 480),
          child: ListView(
            padding: const EdgeInsets.all(24),
            children: [
              Row(
                children: [
                  Image.asset(
                    'assets/icon/logo_mark.png',
                    height: 44,
                    filterQuality: FilterQuality.medium,
                  ),
                  const SizedBox(width: 14),
                  Text('Xownloader', style: text.headlineSmall),
                ],
              ),
              const SizedBox(height: 10),
              Text(
                strings.aboutTagline,
                style: text.titleMedium?.copyWith(
                  color: scheme.primary,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 18),
              Text(
                strings.aboutDescription,
                style: text.bodyMedium?.copyWith(height: 1.5),
              ),
              const SizedBox(height: 28),
              _InfoRow(
                label: strings.aboutDeveloperLabel,
                value: 'Seymen Kalkan',
                onTap: () => _open(_developerUrl),
              ),
              const Divider(height: 1),
              _InfoRow(
                label: strings.aboutRepositoryLabel,
                value: 'github.com/xaprier/Xownloader',
                onTap: () => _open(_repositoryUrl),
                trailing: const Icon(Icons.open_in_new, size: 16),
              ),
              const Divider(height: 1),
              _InfoRow(
                label: strings.aboutVersionLabel(AppConfig.version),
              ),
            ],
          ),
        ),
      ),
    );
  }

  static Future<void> _open(String url) => launchUrl(
        Uri.parse(url),
        mode: LaunchMode.externalApplication,
      );
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({required this.label, this.value, this.onTap, this.trailing});

  final String label;
  final String? value;
  final VoidCallback? onTap;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final text = Theme.of(context).textTheme;

    final row = Padding(
      padding: const EdgeInsets.symmetric(vertical: 14),
      child: Row(
        children: [
          Expanded(
            child: value == null
                ? Text(label, style: text.bodyMedium)
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        label,
                        style: text.labelSmall?.copyWith(
                          color: scheme.onSurfaceVariant,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(value!, style: text.bodyMedium),
                    ],
                  ),
          ),
          ?trailing,
        ],
      ),
    );

    if (onTap == null) return row;
    return InkWell(onTap: onTap, child: row);
  }
}
