class AdminStatus {
  const AdminStatus({
    required this.runtime,
    required this.jobCounts,
    required this.freeBytes,
    required this.totalBytes,
  });

  final Map<String, bool> runtime;
  final Map<String, int> jobCounts;
  final int freeBytes;
  final int totalBytes;

  factory AdminStatus.fromJson(Map<String, dynamic> json) {
    final runtimeJson = json['runtime'] as Map<String, dynamic>? ?? const {};
    final jobsJson = json['jobs'] as Map<String, dynamic>? ?? const {};
    final storageJson = json['storage'] as Map<String, dynamic>? ?? const {};
    return AdminStatus(
      runtime: runtimeJson.map((key, value) => MapEntry(key, value == true)),
      jobCounts: jobsJson.map(
        (key, value) => MapEntry(key, (value as num?)?.toInt() ?? 0),
      ),
      freeBytes: (storageJson['free_bytes'] as num?)?.toInt() ?? 0,
      totalBytes: (storageJson['total_bytes'] as num?)?.toInt() ?? 0,
    );
  }
}