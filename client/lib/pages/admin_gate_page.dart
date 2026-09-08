import 'package:flutter/material.dart';

import '../config/app_config.dart';
import '../l10n/app_strings_scope.dart';
import '../services/admin_api.dart';
import '../services/admin_token_store.dart';
import '../services/download_api.dart';
import 'admin_home_page.dart';

class AdminGatePage extends StatefulWidget {
  const AdminGatePage({
    required this.tokenStore,
    this.initialError,
    this.apiBuilder,
    super.key,
  });

  final AdminTokenStore tokenStore;
  final String? initialError;
  /// Overridable for tests; defaults to a real [AdminApi] against the
  /// configured server.
  final AdminApi Function(String token)? apiBuilder;

  @override
  State<AdminGatePage> createState() => _AdminGatePageState();
}

class _AdminGatePageState extends State<AdminGatePage> {
  final _controller = TextEditingController();
  bool _submitting = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _error = widget.initialError;
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  AdminApi _buildApi(String token) =>
      widget.apiBuilder?.call(token) ??
      AdminApi(baseUrl: AppConfig.serverUrl, token: token);

  Future<void> _submit() async {
    final strings = context.strings;
    final token = _controller.text.trim();
    if (token.isEmpty) {
      setState(() => _error = strings.adminInvalidTokenError);
      return;
    }
    setState(() {
      _error = null;
      _submitting = true;
    });
    try {
      await _buildApi(token).fetchStatus();
      await widget.tokenStore.write(token);
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => AdminHomePage(
            tokenStore: widget.tokenStore,
            token: token,
            api: widget.apiBuilder?.call(token),
          ),
        ),
      );
    } on DownloadApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.statusCode == 401
            ? strings.adminInvalidTokenError
            : error.message;
      });
    } catch (_) {
      if (mounted) setState(() => _error = strings.serverUnreachableError);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final strings = context.strings;
    return Scaffold(
      appBar: AppBar(title: Text(strings.adminGateTitle)),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: _controller,
                  obscureText: true,
                  decoration: InputDecoration(labelText: strings.adminTokenFieldLabel),
                  onSubmitted: (_) => _submit(),
                ),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: _submitting ? null : _submit,
                  child: Text(strings.adminGateSubmitLabel),
                ),
                if (_error != null) ...[
                  const SizedBox(height: 16),
                  Text(
                    _error!,
                    style: TextStyle(color: Theme.of(context).colorScheme.error),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}