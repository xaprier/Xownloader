import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

/// Shows the completed download URL with copy and open-in-browser actions.
class ResultActions extends StatelessWidget {
  const ResultActions({required this.fileUri, super.key});

  final Uri fileUri;

  Future<void> _copy(BuildContext context) async {
    await Clipboard.setData(ClipboardData(text: fileUri.toString()));
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Link copied')),
      );
    }
  }

  Future<void> _open(BuildContext context) async {
    final opened = await launchUrl(
      fileUri,
      mode: LaunchMode.externalApplication,
    );
    if (!opened && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not open the link')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SelectableText('File: $fileUri'),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          children: [
            OutlinedButton.icon(
              onPressed: () => _copy(context),
              icon: const Icon(Icons.copy),
              label: const Text('Copy link'),
            ),
            FilledButton.icon(
              onPressed: () => _open(context),
              icon: const Icon(Icons.open_in_new),
              label: const Text('Open'),
            ),
          ],
        ),
      ],
    );
  }
}
