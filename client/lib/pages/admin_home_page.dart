import 'package:flutter/material.dart';

import '../l10n/app_strings_scope.dart';
import '../services/admin_api.dart';
import '../services/admin_token_store.dart';

/// Placeholder — Task 4 replaces this with the Status/Jobs/Metrics tabs.
/// Already accepts the optional [api] override Task 4's real version needs,
/// so Task 3's `AdminGatePage` (which passes it through on navigation) and
/// its tests compile against the final shape from the start.
class AdminHomePage extends StatelessWidget {
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
  Widget build(BuildContext context) {
    return Scaffold(appBar: AppBar(title: Text(context.strings.adminHomeTitle)));
  }
}