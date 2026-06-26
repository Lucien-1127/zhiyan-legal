// 搜尋與新增追蹤法規

import 'package:flutter/material.dart';
import '../api/client.dart';

class SearchScreen extends StatefulWidget {
  const SearchScreen({super.key});

  @override
  State<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends State<SearchScreen> {
  final _controller = TextEditingController();
  List<LawSearchResult>? _results;
  List<TrackedLaw>? _tracked;
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadTracked();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _loadTracked() async {
    try {
      final json = await ApiClient.getTracked();
      setState(() {
        _tracked = (json['tracked'] as List?)
                ?.map(
                    (e) => TrackedLaw.fromJson(e as Map<String, dynamic>))
                .toList() ??
            [];
      });
    } catch (_) {}
  }

  Future<void> _search() async {
    final keyword = _controller.text.trim();
    if (keyword.isEmpty) return;
    setState(() {
      _loading = true;
      _error = null;
      _results = null;
    });
    try {
      final json = await ApiClient.search(keyword);
      setState(() {
        _results = (json['results'] as List?)
                ?.map((e) =>
                    LawSearchResult.fromJson(e as Map<String, dynamic>))
                .toList() ??
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

  bool _isTracked(String pcode) {
    return _tracked?.any((t) => t.pcode == pcode) ?? false;
  }

  Future<void> _addTrack(String pcode, String name) async {
    try {
      await ApiClient.addTracking(pcode, 7);
      await _loadTracked();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('已加入追蹤：$name'),
          behavior: SnackBarBehavior.floating,
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('加入失敗：$e'),
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
      appBar: AppBar(title: const Text('搜尋法規')),
      body: Column(
        children: [
          // 搜尋欄
          Padding(
            padding: const EdgeInsets.all(16),
            child: TextField(
              controller: _controller,
              decoration: InputDecoration(
                hintText: '輸入法規名稱…',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _controller.text.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: () {
                          _controller.clear();
                          setState(() => _results = null);
                        },
                      )
                    : null,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                filled: true,
              ),
              onSubmitted: (_) => _search(),
              textInputAction: TextInputAction.search,
            ),
          ),

          // 結果
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                    ? Center(child: Text('$_error'))
                    : _results == null
                        ? _buildHint(theme)
                        : _results!.isEmpty
                            ? const Center(child: Text('找不到符合的法規'))
                            : _buildResults(theme),
          ),
        ],
      ),
    );
  }

  Widget _buildHint(ThemeData theme) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.search, size: 48, color: Colors.grey.shade400),
          const SizedBox(height: 16),
          Text(
            '輸入法規名稱關鍵字搜尋',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '例如：毒品、勞動、公司、刑法',
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildResults(ThemeData theme) {
    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      itemCount: _results!.length,
      itemBuilder: (context, index) {
        final law = _results![index];
        final tracked = _isTracked(law.pcode);
        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: ListTile(
            leading: CircleAvatar(
              backgroundColor: law.level == '法律'
                  ? Colors.blue.withValues(alpha: 0.15)
                  : Colors.orange.withValues(alpha: 0.15),
              child: Text(
                law.level == '法律' ? '法' : '令',
                style: TextStyle(
                  color: law.level == '法律' ? Colors.blue : Colors.orange,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            title: Text(law.name),
            subtitle: Text(
              '${law.level} · 修正 ${law.modifiedDate}${law.abolished ? ' · 已廢止' : ''}',
              style: const TextStyle(fontSize: 12),
            ),
            trailing: tracked
                ? const Chip(
                    label: Text('已追蹤', style: TextStyle(fontSize: 11)),
                    visualDensity: VisualDensity.compact,
                  )
                : FilledButton.tonalIcon(
                    onPressed: law.abolished
                        ? null
                        : () => _addTrack(law.pcode, law.name),
                    icon: const Icon(Icons.add, size: 16),
                    label: const Text('追蹤', style: TextStyle(fontSize: 12)),
                  ),
          ),
        );
      },
    );
  }
}
