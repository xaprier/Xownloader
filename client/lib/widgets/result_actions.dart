import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

import '../l10n/app_strings_scope.dart';

/// Shows the completed download URL with copy and open-in-browser actions.
class ResultActions extends StatelessWidget {
  const ResultActions({required this.fileUri, super.key});

  final Uri fileUri;

  Future<void> _copy(BuildContext context) async {
    final strings = context.strings;
    await Clipboard.setData(ClipboardData(text: fileUri.toString()));
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(strings.linkCopiedMessage)),
      );
    }
  }

  Future<void> _open(BuildContext context) async {
    final strings = context.strings;
    final opened = await launchUrl(
      fileUri,
      mode: LaunchMode.externalApplication,
    );
    if (!opened && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(strings.couldNotOpenLinkMessage)),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final strings = context.strings;
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        OutlinedButton.icon(
          onPressed: () => _copy(context),
          style: OutlinedButton.styleFrom(visualDensity: VisualDensity.compact),
          icon: const Icon(Icons.link, size: 16),
          label: Text(strings.copyLinkLabel),
        ),
        FilledButton.icon(
          onPressed: () => _open(context),
          style: FilledButton.styleFrom(visualDensity: VisualDensity.compact),
          icon: const Icon(Icons.open_in_new, size: 16),
          label: Text(strings.openLabel),
        ),
      ],
    );
  }
}
