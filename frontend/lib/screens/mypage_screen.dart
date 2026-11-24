import 'package:flutter/material.dart';

import '../app.dart' show blue, ink, line, muted;
import '../core/network/backend_api.dart';
import '../widgets/backend_state.dart';

class MyPageScreen extends StatefulWidget {
  const MyPageScreen({super.key});

  @override
  State<MyPageScreen> createState() => _MyPageScreenState();
}

class _MyPageScreenState extends State<MyPageScreen> {
  late Future<Map<String, dynamic>> _user;

  @override
  void initState() {
    super.initState();
    _user = BackendApi.instance.currentUser();
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<Map<String, dynamic>>(
    future: _user,
    builder: (context, snapshot) {
      if (snapshot.connectionState == ConnectionState.waiting) {
        return const Center(child: CircularProgressIndicator());
      }
      if (snapshot.hasError) {
        return const BackendUnavailable(feature: '내 정보');
      }
      final user = snapshot.data!;
      final nickname = user['nickname']?.toString().trim() ?? '';
      final username = user['username']?.toString() ?? '';
      final displayName = nickname.isEmpty ? username : nickname;
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '마이페이지',
            style: TextStyle(
              fontSize: 25,
              fontWeight: FontWeight.w800,
              color: ink,
            ),
          ),
          const SizedBox(height: 18),
          Container(
            padding: const EdgeInsets.all(18),
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                colors: [Color(0xFF4A96FF), Color(0xFF2676E8)],
              ),
              borderRadius: BorderRadius.all(Radius.circular(20)),
            ),
            child: Row(
              children: [
                CircleAvatar(
                  backgroundColor: Colors.white,
                  child: Text(
                    displayName.isEmpty ? '?' : displayName.characters.first,
                    style: const TextStyle(
                      color: blue,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        displayName,
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        username,
                        style: const TextStyle(
                          color: Colors.white70,
                          fontSize: 11,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 22),
          const BackendConnectionStatus(),
          const SizedBox(height: 18),
          _settingsTile(Icons.store_outlined, '매장 정보', '백엔드 매장 API 연결 대기 중'),
          _settingsTile(
            Icons.upload_file_rounded,
            '데이터 연결 및 업로드',
            'POS, 리뷰, 재고 API 연결 대기 중',
          ),
          _settingsTile(
            Icons.notifications_none_rounded,
            '알림 설정',
            '설정 API 연결 대기 중',
          ),
        ],
      );
    },
  );

  Widget _settingsTile(IconData icon, String title, String subtitle) =>
      Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(15),
          border: Border.all(color: line),
        ),
        child: Row(
          children: [
            Icon(icon, color: muted, size: 20),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      fontSize: 12,
                      color: ink,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    subtitle,
                    style: const TextStyle(fontSize: 10, color: muted),
                  ),
                ],
              ),
            ),
          ],
        ),
      );
}

class BackendConnectionStatus extends StatelessWidget {
  const BackendConnectionStatus({super.key});

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.circular(15),
      border: Border.all(color: line),
    ),
    child: const Row(
      children: [
        Icon(Icons.cloud_done_outlined, color: Color(0xFF15956F)),
        SizedBox(width: 10),
        Text(
          '백엔드 연결됨',
          style: TextStyle(color: ink, fontWeight: FontWeight.w700),
        ),
        Spacer(),
        Text('인증 사용자 확인 완료', style: TextStyle(color: muted, fontSize: 10)),
      ],
    ),
  );
}
