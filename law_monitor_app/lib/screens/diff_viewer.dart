// 新舊條文對照檢視器 — 完整 diff 頁面

import 'package:flutter/material.dart';
import '../api/client.dart';

class DiffViewer extends StatefulWidget {
  final String pcode;
  final String name;

  const DiffViewer({
    super.key,
    required this.pcode,
    required this.name,
  });

  @override
  State<DiffViewer> createState() => _DiffViewerState();
}

class _DiffViewerState extends State<DiffViewer> {
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
      appBar: AppBar(
        title: const Text('新舊條文對照'),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(32),
          child: Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Text(
              widget.name,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ),
        ),
      ),
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

    final allItems = [
      ...r.modified.map((e) => ('🔶 修正', e)),
      ...r.added.map((e) => ('🟢 新增', e)),
      ...r.removed.map((e) => ('🔴 刪除', e)),
    ];

    if (allItems.isEmpty) {
      return const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.check_circle, size: 64, color: Colors.green),
            SizedBox(height: 16),
            Text('目前無異動', style: TextStyle(fontSize: 18)),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: allItems.length,
      itemBuilder: (context, index) {
        final (label, item) = allItems[index];
        return _buildDiffCard(label, item, theme);
      },
    );
  }

  Widget _buildDiffCard(String label, DiffItem item, ThemeData theme) {
    final isModified = item.kind == '修正';
    final isAdded = item.kind == '新增';
    final isRemoved = item.kind == '刪除';

    Color accentColor;
    if (isAdded) {
      accentColor = const Color(0xFF2F7D4F);
    } else if (isRemoved) {
      accentColor = const Color(0xFFB4452B);
    } else {
      accentColor = const Color(0xFFB4882B);
    }

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 標題
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            decoration: BoxDecoration(
              color: accentColor.withValues(alpha: 0.08),
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(12),
                topRight: Radius.circular(12),
              ),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 3,
                  ),
                  decoration: BoxDecoration(
                    color: accentColor.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    '第${item.no}條',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 14,
                      color: accentColor,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  '（${item.kind}）',
                  style: TextStyle(
                    fontSize: 12,
                    color: accentColor,
                  ),
                ),
              ],
            ),
          ),

          // 內容
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (isModified && item.old != null && item.new_ != null)
                  _buildModifiedBody(item, theme)
                else ...[
                  if (isAdded && item.new_ != null)
                    _buildTextBlock('新條文', item.new_!, Colors.green, theme)
                  else if (isRemoved && item.old != null)
                    _buildTextBlock('舊條文', item.old!, Colors.red, theme),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildModifiedBody(DiffItem item, ThemeData theme) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildTextBlock('修正條文', item.new_!, Colors.green, theme),
        const SizedBox(height: 12),
        _buildTextBlock('現行條文', item.old!, Colors.red, theme),
      ],
    );
  }

  Widget _buildTextBlock(
    String label,
    String text,
    Color color,
    ThemeData theme,
  ) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                color: color,
                shape: BoxShape.circle,
              ),
            ),
            const SizedBox(width: 6),
            Text(
              label,
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.bold,
                color: color.withValues(alpha: 0.8),
              ),
            ),
          ],
        ),
        const SizedBox(height: 6),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.3),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: color.withValues(alpha: 0.3),
            ),
          ),
          child: SelectableText(
            text,
            style: TextStyle(
              fontSize: 13,
              height: 1.5,
              color: theme.colorScheme.onSurface,
            ),
          ),
        ),
      ],
    );
  }
}
