// 法規明細 — 查核歷史 + 異動列表

import 'package:flutter/material.dart';
import '../api/client.dart';

class DetailScreen extends StatefulWidget {
  final String pcode;
  final String name;

  const DetailScreen({
    super.key,
    required this.pcode,
    required this.name,
  });

  @override
  State<DetailScreen> createState() => _DetailScreenState();
}

class _DetailScreenState extends State<DetailScreen> {
  DiffReport? _report;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final json = await ApiClient.getDiff(widget.pcode);
      setState(() {
        _report = DiffReport.fromJson(json['report'] as Map<String, dynamic>);
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(widget.name)),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _buildError(theme)
              : _buildContent(theme),
    );
  }

  Widget _buildError(ThemeData theme) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, size: 48, color: Colors.red),
            const SizedBox(height: 16),
            Text('$_error', textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _load,
              icon: const Icon(Icons.refresh),
              label: const Text('重試'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildContent(ThemeData theme) {
    if (_report == null) return const SizedBox.shrink();
    final r = _report!;

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // 摘要
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                children: [
                  Text(
                    '${r.name}　新舊條文對照',
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      _verChip('新版', r.newDate, Colors.green),
                      const Padding(
                        padding: EdgeInsets.symmetric(horizontal: 8),
                        child: Icon(Icons.arrow_forward, size: 16),
                      ),
                      _verChip('舊版', r.oldDate, Colors.orange),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    '${r.changedCount} 條異動 · ${r.unchangedCount} 條未變',
                    style: theme.textTheme.bodySmall,
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // 操作按鈕
          Row(
            children: [
              Expanded(
                child: FilledButton.icon(
                  onPressed: () => Navigator.pushNamed(
                    context,
                    '/diff',
                    arguments: {'pcode': widget.pcode, 'name': widget.name},
                  ),
                  icon: const Icon(Icons.compare_arrows),
                  label: const Text('完整對照'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _load,
                  icon: const Icon(Icons.refresh),
                  label: const Text('重新整理'),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // 異動列表
          if (r.modified.isNotEmpty) ...[
            _sectionTitle('🔶 修正條文 (${r.modified.length})', theme),
            ...r.modified.map((item) => _diffItemCard(item, theme)),
          ],
          if (r.added.isNotEmpty) ...[
            _sectionTitle('🟢 新增條文 (${r.added.length})', theme),
            ...r.added.map((item) => _diffItemCard(item, theme)),
          ],
          if (r.removed.isNotEmpty) ...[
            _sectionTitle('🔴 刪除條文 (${r.removed.length})', theme),
            ...r.removed.map((item) => _diffItemCard(item, theme)),
          ],
          if (r.changedCount == 0)
            const Padding(
              padding: EdgeInsets.all(32),
              child: Center(
                child: Text('目前無異動', style: TextStyle(color: Colors.grey)),
              ),
            ),
        ],
      ),
    );
  }

  Widget _verChip(String label, String date, Color color) {
    final d = date.length == 8
        ? '${date.substring(0, 4)}-${date.substring(4, 6)}-${date.substring(6, 8)}'
        : date;
    return Chip(
      avatar: Icon(Icons.circle, size: 8, color: color),
      label: Text('$label $d', style: const TextStyle(fontSize: 11)),
      visualDensity: VisualDensity.compact,
    );
  }

  Widget _sectionTitle(String title, ThemeData theme) {
    return Padding(
      padding: const EdgeInsets.only(top: 12, bottom: 8),
      child: Text(
        title,
        style: theme.textTheme.titleSmall?.copyWith(
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  Widget _diffItemCard(DiffItem item, ThemeData theme) {
    Color kindColor;
    switch (item.kind) {
      case '修正':
        kindColor = const Color(0xFFB4882B);
        break;
      case '新增':
        kindColor = const Color(0xFF2F7D4F);
        break;
      default:
        kindColor = const Color(0xFFB4452B);
    }

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: kindColor.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    '第${item.no}條',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 13,
                      color: kindColor,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  '（${item.kind}）',
                  style: TextStyle(fontSize: 12, color: kindColor),
                ),
              ],
            ),
            if (item.charDiffSummary != null &&
                item.charDiffSummary!.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                item.charDiffSummary!,
                style: const TextStyle(fontSize: 11, color: Colors.grey),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: Colors.green.withValues(alpha: 0.05),
                      borderRadius: BorderRadius.circular(4),
                      border: Border.all(
                        color: Colors.green.withValues(alpha: 0.2),
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '新',
                          style: TextStyle(
                            fontSize: 10,
                            color: Colors.green.shade700,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          _truncText(item.new_ ?? ''),
                          style: const TextStyle(fontSize: 11),
                          maxLines: 3,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(width: 4),
                Expanded(
                  child: Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: Colors.red.withValues(alpha: 0.05),
                      borderRadius: BorderRadius.circular(4),
                      border: Border.all(
                        color: Colors.red.withValues(alpha: 0.2),
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '舊',
                          style: TextStyle(
                            fontSize: 10,
                            color: Colors.red.shade700,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          _truncText(item.old ?? ''),
                          style: const TextStyle(fontSize: 11),
                          maxLines: 3,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  String _truncText(String s) {
    if (s.length <= 150) return s;
    return '${s.substring(0, 150)}…';
  }
}
