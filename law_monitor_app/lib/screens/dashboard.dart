// 儀表板 — 法規追蹤總覽

import 'package:flutter/material.dart';
import '../api/client.dart';

class Dashboard extends StatefulWidget {
  const Dashboard({super.key});

  @override
  State<Dashboard> createState() => _DashboardState();
}

class _DashboardState extends State<Dashboard> {
  List<TrackedLaw>? _laws;
  bool _loading = true;
  String? _error;
  int _indexSize = 0;
  int _changedRecent = 0;

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
      final status = await ApiClient.getStatus();
      final tracked = await ApiClient.getTracked();
      setState(() {
        _indexSize = status['index_size'] as int? ?? 0;
        _changedRecent = status['changed_recent_7d'] as int? ?? 0;
        _laws = (tracked['tracked'] as List?)
                ?.map((e) => TrackedLaw.fromJson(e as Map<String, dynamic>))
                .toList()
            ??
            [];
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Future<void> _runCheck() async {
    try {
      final result = await ApiClient.check();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('查核完成：${result['checked']} 部，'
              '${result['changed']} 部有異動'),
          behavior: SnackBarBehavior.floating,
        ),
      );
      _load();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('查核失敗：$e'),
          backgroundColor: Colors.red,
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('法規異動監控'),
        actions: [
          IconButton(
            icon: const Icon(Icons.search),
            onPressed: () => Navigator.pushNamed(context, '/search'),
            tooltip: '搜尋法規',
          ),
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () => Navigator.pushNamed(context, '/settings'),
            tooltip: '設定',
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _buildError(theme)
              : RefreshIndicator(
                  onRefresh: _load,
                  child: _buildContent(theme),
                ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _runCheck,
        icon: const Icon(Icons.refresh),
        label: const Text('執行查核'),
      ),
    );
  }

  Widget _buildError(ThemeData theme) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.cloud_off, size: 64, color: Colors.red),
            const SizedBox(height: 16),
            Text(
              '無法連線至 API',
              style: theme.textTheme.headlineSmall,
            ),
            const SizedBox(height: 8),
            Text(
              '請確認 Tailscale 已連線，且在設定中輸入正確的 API 網址。\n'
              '錯誤：$_error',
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 24),
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
    final green = Colors.green.shade600;
    final yellow = Colors.orange.shade600;
    final red = Colors.red.shade600;

    // 統計
    final greenCount =
        _laws?.where((l) => l.statusColor == 'green').length ?? 0;
    final yellowCount =
        _laws?.where((l) => l.statusColor == 'yellow').length ?? 0;
    final redCount =
        _laws?.where((l) => l.statusColor == 'red').length ?? 0;

    return CustomScrollView(
      slivers: [
        // 摘要卡片
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceAround,
                      children: [
                        _statItem(
                          '${_laws?.length ?? 0}',
                          '追蹤中',
                          Colors.blue,
                        ),
                        _statItem('$greenCount', '無異動', green),
                        _statItem('$yellowCount', '待確認', yellow),
                        _statItem('$redCount', '有異動', red),
                      ],
                    ),
                    const Divider(height: 24),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                      children: [
                        Text('索引：$_indexSize 筆',
                            style: theme.textTheme.bodySmall),
                        Text('近 7 天異動：$_changedRecent 部',
                            style: theme.textTheme.bodySmall),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),

        // 法規列表
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Text(
              '追蹤法規',
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
        ),
        if (_laws != null && _laws!.isNotEmpty)
          SliverList(
            delegate: SliverChildBuilderDelegate(
              (context, index) {
                final law = _laws![index];
                Color dotColor;
                switch (law.statusColor) {
                  case 'green':
                    dotColor = green;
                    break;
                  case 'yellow':
                    dotColor = yellow;
                    break;
                  default:
                    dotColor = red;
                }
                return _buildLawCard(law, dotColor, theme);
              },
              childCount: _laws!.length,
            ),
          ),
        const SliverPadding(padding: EdgeInsets.only(bottom: 80)),
      ],
    );
  }

  Widget _statItem(String value, String label, Color color) {
    return Column(
      children: [
        Text(
          value,
          style: TextStyle(
            fontSize: 28,
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
        Text(label, style: const TextStyle(fontSize: 12)),
      ],
    );
  }

  Widget _buildLawCard(TrackedLaw law, Color dotColor, ThemeData theme) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Card(
        child: InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: () => Navigator.pushNamed(context, '/detail', arguments: {
            'pcode': law.pcode,
            'name': law.name,
          }),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Container(
                  width: 12,
                  height: 12,
                  decoration: BoxDecoration(
                    color: dotColor,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        law.name,
                        style: theme.textTheme.bodyLarge?.copyWith(
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          _pill(law.level, Colors.grey.shade600),
                          const SizedBox(width: 8),
                          _pill(law.frequencyLabel, Colors.blue.shade600),
                          if (law.abolished) ...[
                            const SizedBox(width: 8),
                            _pill('廢止', Colors.red.shade600),
                          ],
                        ],
                      ),
                    ],
                  ),
                ),
                const Icon(Icons.chevron_right, color: Colors.grey),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _pill(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        text,
        style: TextStyle(fontSize: 11, color: color),
      ),
    );
  }
}
