// API 客戶端 — 連線至 regulation_api

import 'dart:convert';
import 'dart:io';

class ApiClient {
  static String _baseUrl = 'http://100.68.234.34:80/api';

  static void setBaseUrl(String url) {
    _baseUrl = url.endsWith('/api') ? url : '$url/api';
  }

  static String get baseUrl => _baseUrl;

  static Future<Map<String, dynamic>> _get(String path) async {
    final url = Uri.parse('$_baseUrl$path');
    final client = HttpClient();
    client.connectionTimeout = const Duration(seconds: 10);
    try {
      final req = await client.getUrl(url);
      req.headers.set('Accept', 'application/json');
      final resp = await req.close();
      final body = await resp.transform(utf8.decoder).join();
      if (resp.statusCode != 200) {
        throw HttpException('HTTP ${resp.statusCode}: $body');
      }
      return json.decode(body) as Map<String, dynamic>;
    } finally {
      client.close();
    }
  }

  static Future<Map<String, dynamic>> _post(String path) async {
    final url = Uri.parse('$_baseUrl$path');
    final client = HttpClient();
    client.connectionTimeout = const Duration(seconds: 10);
    try {
      final req = await client.postUrl(url);
      req.headers.set('Accept', 'application/json');
      req.headers.set('Content-Type', 'application/json');
      req.write('{}');
      final resp = await req.close();
      final body = await resp.transform(utf8.decoder).join();
      if (resp.statusCode != 200) {
        throw HttpException('HTTP ${resp.statusCode}: $body');
      }
      return json.decode(body) as Map<String, dynamic>;
    } finally {
      client.close();
    }
  }

  // ── API 方法 ──────────────────────────

  static Future<Map<String, dynamic>> getStatus() => _get('/status');

  static Future<Map<String, dynamic>> getTracked() => _get('/tracked');

  static Future<Map<String, dynamic>> check() => _post('/check?official=true');

  static Future<Map<String, dynamic>> sync({bool force = false}) =>
      _post('/sync?force=$force');

  static Future<Map<String, dynamic>> search(String keyword) =>
      _get('/search?keyword=${Uri.encodeComponent(keyword)}');

  static Future<Map<String, dynamic>> getDiff(String pcode) =>
      _get('/diff/$pcode');

  static Future<Map<String, dynamic>> getHistory({int days = 7}) =>
      _get('/history?days=$days');

  static Future<Map<String, dynamic>> addTracking(
      String pcode, int frequency) async {
    final url = Uri.parse('$_baseUrl/tracked/add');
    final client = HttpClient();
    client.connectionTimeout = const Duration(seconds: 10);
    try {
      final req = await client.postUrl(url);
      req.headers.set('Accept', 'application/json');
      req.headers.set('Content-Type', 'application/json');
      req.write(json.encode({
        'pcode': pcode,
        'frequency': frequency,
      }));
      final resp = await req.close();
      final body = await resp.transform(utf8.decoder).join();
      if (resp.statusCode != 200) {
        throw HttpException('HTTP ${resp.statusCode}: $body');
      }
      return json.decode(body) as Map<String, dynamic>;
    } finally {
      client.close();
    }
  }

  static Future<Map<String, dynamic>> removeTracking(String pcode) async {
    final url = Uri.parse('$_baseUrl/tracked/$pcode');
    final client = HttpClient();
    client.connectionTimeout = const Duration(seconds: 10);
    try {
      final req = await client.deleteUrl(url);
      req.headers.set('Accept', 'application/json');
      final resp = await req.close();
      final body = await resp.transform(utf8.decoder).join();
      if (resp.statusCode != 200) {
        throw HttpException('HTTP ${resp.statusCode}: $body');
      }
      return json.decode(body) as Map<String, dynamic>;
    } finally {
      client.close();
    }
  }

  static Future<Map<String, dynamic>> getDiffAll() => _get('/diff/all');
}

// ── Model 類別 ──────────────────────────

class TrackedLaw {
  final String pcode;
  final String name;
  final String level;
  final String baselineVersion;
  final String currentVersion;
  final int frequencyDays;
  final String lastCheckedAt;
  final bool abolished;

  TrackedLaw({
    required this.pcode,
    required this.name,
    required this.level,
    required this.baselineVersion,
    required this.currentVersion,
    required this.frequencyDays,
    required this.lastCheckedAt,
    this.abolished = false,
  });

  factory TrackedLaw.fromJson(Map<String, dynamic> json) {
    return TrackedLaw(
      pcode: json['pcode'] as String? ?? '',
      name: json['name'] as String? ?? '',
      level: json['level'] as String? ?? '',
      baselineVersion: json['baseline_version'] as String? ?? '',
      currentVersion: json['current_version'] as String? ?? '',
      frequencyDays: json['frequency_days'] as int? ?? 7,
      lastCheckedAt: json['last_checked_at'] as String? ?? '',
      abolished: json['abolished'] as bool? ?? false,
    );
  }

  /// 狀態燈號
  /// green: baseline == current (無異動)
  /// yellow: 尚未檢查
  /// red: baseline != current (有異動) 或已廢止
  String get statusColor {
    if (abolished) return 'red';
    if (baselineVersion.isEmpty) return 'yellow';
    if (currentVersion.isEmpty) return 'yellow';
    if (baselineVersion == currentVersion) return 'green';
    return 'red';
  }

  String get frequencyLabel {
    if (frequencyDays == 7) return '每週';
    if (frequencyDays == 30) return '每月';
    if (frequencyDays == 90) return '每季';
    return '每$frequencyDays天';
  }
}

class LawSearchResult {
  final String pcode;
  final String name;
  final String level;
  final String modifiedDate;
  final bool abolished;

  LawSearchResult({
    required this.pcode,
    required this.name,
    required this.level,
    required this.modifiedDate,
    this.abolished = false,
  });

  factory LawSearchResult.fromJson(Map<String, dynamic> json) {
    return LawSearchResult(
      pcode: json['pcode'] as String? ?? '',
      name: json['name'] as String? ?? '',
      level: json['level'] as String? ?? '',
      modifiedDate: json['modifiedDate'] as String? ?? '',
      abolished: json['abolished'] as bool? ?? false,
    );
  }
}

class DiffReport {
  final String name;
  final String pcode;
  final int changedCount;
  final int unchangedCount;
  final String newDate;
  final String oldDate;
  final List<DiffItem> modified;
  final List<DiffItem> added;
  final List<DiffItem> removed;

  DiffReport({
    required this.name,
    required this.pcode,
    required this.changedCount,
    required this.unchangedCount,
    required this.newDate,
    required this.oldDate,
    required this.modified,
    required this.added,
    required this.removed,
  });

  factory DiffReport.fromJson(Map<String, dynamic> json) {
    return DiffReport(
      name: json['name'] as String? ?? '',
      pcode: json['pcode'] as String? ?? '',
      changedCount: json['changed_count'] as int? ?? 0,
      unchangedCount: json['unchanged_count'] as int? ?? 0,
      newDate: json['new_date'] as String? ?? '',
      oldDate: json['old_date'] as String? ?? '',
      modified: (json['modified'] as List? ?? [])
          .map((e) => DiffItem.fromJson(e as Map<String, dynamic>, '修正'))
          .toList(),
      added: (json['added'] as List? ?? [])
          .map((e) => DiffItem.fromJson(e as Map<String, dynamic>, '新增'))
          .toList(),
      removed: (json['removed'] as List? ?? [])
          .map((e) => DiffItem.fromJson(e as Map<String, dynamic>, '刪除'))
          .toList(),
    );
  }
}

class DiffItem {
  final String no;
  final String? old;
  final String? new_;
  final String? charDiffSummary;
  final String kind;

  DiffItem({
    required this.no,
    this.old,
    this.new_,
    this.charDiffSummary,
    required this.kind,
  });

  factory DiffItem.fromJson(Map<String, dynamic> json, String kind) {
    return DiffItem(
      no: json['no'] as String? ?? '',
      old: json['old'] as String?,
      new_: json['new'] as String?,
      charDiffSummary: json['char_diff_summary'] as String?,
      kind: kind,
    );
  }
}
