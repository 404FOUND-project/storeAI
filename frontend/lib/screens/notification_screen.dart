import 'package:flutter/material.dart';

import '../app.dart' show blue, ink, muted, line;
import '../core/network/backend_api.dart';
import '../widgets/backend_state.dart';

class NotificationScreen extends StatefulWidget {
  final bool notificationsRead;
  final Set<int> readNotifications;
  final VoidCallback onBack;
  final VoidCallback onReadAll;
  final ValueChanged<int> onRead;

  const NotificationScreen({
    super.key,
    required this.notificationsRead,
    required this.readNotifications,
    required this.onBack,
    required this.onReadAll,
    required this.onRead,
  });

  @override
  State<NotificationScreen> createState() => _NotificationScreenState();
}

class _NotificationScreenState extends State<NotificationScreen> {
  late Future<List<Map<String, dynamic>>> _notices;

  @override
  void initState() {
    super.initState();
    _notices = BackendApi.instance.notices();
  }

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Row(
        children: [
          IconButton(
            onPressed: widget.onBack,
            icon: const Icon(Icons.chevron_left_rounded, size: 27),
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(),
          ),
          const SizedBox(width: 10),
          const Expanded(
            child: Text(
              '공지사항',
              style: TextStyle(
                fontSize: 25,
                fontWeight: FontWeight.w800,
                color: ink,
              ),
            ),
          ),
          TextButton(onPressed: widget.onReadAll, child: const Text('모두 읽음')),
        ],
      ),
      const SizedBox(height: 18),
      FutureBuilder<List<Map<String, dynamic>>>(
        future: _notices,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return const BackendUnavailable(feature: '공지사항');
          }
          final notices = snapshot.data ?? const [];
          if (notices.isEmpty) {
            return const Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text('등록된 공지사항이 없습니다.', style: TextStyle(color: muted)),
              ),
            );
          }
          return Column(
            children: notices
                .asMap()
                .entries
                .map((entry) => _noticeItem(entry.key, entry.value))
                .toList(),
          );
        },
      ),
    ],
  );

  Widget _noticeItem(int index, Map<String, dynamic> notice) => InkWell(
    onTap: () => widget.onRead(index),
    child: Container(
      padding: const EdgeInsets.symmetric(vertical: 15),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: line)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.campaign_outlined, color: blue, size: 26),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  notice['title']?.toString() ?? '제목 없음',
                  style: const TextStyle(
                    color: ink,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 5),
                Text(
                  notice['content']?.toString() ?? '',
                  style: const TextStyle(
                    color: muted,
                    fontSize: 11,
                    height: 1.5,
                  ),
                ),
                const SizedBox(height: 7),
                Text(
                  notice['created_at']?.toString() ?? '',
                  style: const TextStyle(color: muted, fontSize: 9),
                ),
              ],
            ),
          ),
          if (!widget.notificationsRead &&
              !widget.readNotifications.contains(index))
            const Icon(Icons.circle, color: blue, size: 6),
        ],
      ),
    ),
  );
}
