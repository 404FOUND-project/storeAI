import 'package:flutter/material.dart';

import '../app.dart' show blue, ink, line, muted;
import '../core/network/backend_api.dart';
import '../widgets/backend_state.dart';

class MyPageScreen extends StatefulWidget {
  final int? storeId;
  final bool storeLoading;
  final String? storeError;
  final Future<void> Function() onStoreChanged;

  const MyPageScreen({
    super.key,
    required this.storeId,
    required this.storeLoading,
    required this.storeError,
    required this.onStoreChanged,
  });

  @override
  State<MyPageScreen> createState() => _MyPageScreenState();
}

class _MyPageScreenState extends State<MyPageScreen> {
  late Future<Map<String, dynamic>> _user;
  Future<Map<String, dynamic>>? _store;

  @override
  void initState() {
    super.initState();
    _user = BackendApi.instance.currentUser();
    _loadStore();
  }

  @override
  void didUpdateWidget(covariant MyPageScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.storeId != widget.storeId) _loadStore();
  }

  void _loadStore() {
    _store = widget.storeId == null
        ? null
        : BackendApi.instance.storeDetail(widget.storeId!);
  }

  Future<void> _editStore([Map<String, dynamic>? store]) async {
    final name = TextEditingController(text: store?['name']?.toString() ?? '');
    final address = TextEditingController(
      text: store?['address']?.toString() ?? '',
    );
    final phone = TextEditingController(
      text: store?['phone']?.toString() ?? '',
    );
    final businessNumber = TextEditingController(
      text: store?['business_number']?.toString() ?? '',
    );

    final save = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(store == null ? '매장 등록' : '매장 정보 수정'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              _field(name, '매장명'),
              _field(address, '주소'),
              _field(phone, '전화번호'),
              _field(businessNumber, '사업자등록번호'),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('취소'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('저장'),
          ),
        ],
      ),
    );

    if (save != true) {
      name.dispose();
      address.dispose();
      phone.dispose();
      businessNumber.dispose();
      return;
    }
    if (name.text.trim().isEmpty) {
      name.dispose();
      address.dispose();
      phone.dispose();
      businessNumber.dispose();
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('매장명을 입력해 주세요.')));
      return;
    }

    final payload = {
      'name': name.text.trim(),
      'address': address.text.trim(),
      'phone': phone.text.trim(),
      'business_number': businessNumber.text.trim(),
    };
    name.dispose();
    address.dispose();
    phone.dispose();
    businessNumber.dispose();

    try {
      if (store == null) {
        await BackendApi.instance.registerStore(payload);
      } else {
        await BackendApi.instance.updateStore(widget.storeId!, payload);
      }
      await widget.onStoreChanged();
      if (!mounted) return;
      setState(_loadStore);
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('매장 정보가 저장되었습니다.')));
    } on BackendException catch (error) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(error.message)));
    }
  }

  Widget _field(TextEditingController controller, String label) => Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: TextField(
      controller: controller,
      decoration: InputDecoration(labelText: label),
    ),
  );

  @override
  Widget build(BuildContext context) => FutureBuilder<Map<String, dynamic>>(
    future: _user,
    builder: (context, snapshot) {
      if (snapshot.connectionState == ConnectionState.waiting) {
        return const Center(child: CircularProgressIndicator());
      }
      if (snapshot.hasError) return const BackendUnavailable(feature: '내 정보');

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
                        user['email']?.toString().isNotEmpty == true
                            ? user['email'].toString()
                            : username,
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
          _storeCard(),
          _settingsTile(
            Icons.analytics_outlined,
            '매출·리뷰 분석',
            '실제 매출과 리뷰 API에서 불러옵니다.',
          ),
          _settingsTile(
            Icons.inventory_2_outlined,
            '재고·발주 추천',
            '매장 재고와 저장된 예측 데이터에 연결되어 있습니다.',
          ),
        ],
      );
    },
  );

  Widget _storeCard() {
    if (widget.storeLoading)
      return _settingsTile(Icons.store_outlined, '매장 정보', '매장 정보를 불러오는 중입니다.');
    if (widget.storeId == null) {
      return Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(15),
          border: Border.all(color: line),
        ),
        child: Row(
          children: [
            const Icon(Icons.store_outlined, color: muted),
            const SizedBox(width: 12),
            const Expanded(
              child: Text(
                '등록된 매장이 없습니다.',
                style: TextStyle(color: ink, fontSize: 12),
              ),
            ),
            TextButton(
              onPressed: () => _editStore(),
              child: const Text('매장 등록'),
            ),
          ],
        ),
      );
    }

    return FutureBuilder<Map<String, dynamic>>(
      future: _store,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting)
          return _settingsTile(Icons.store_outlined, '매장 정보', '불러오는 중입니다.');
        if (snapshot.hasError)
          return _settingsTile(
            Icons.store_outlined,
            '매장 정보',
            widget.storeError ?? '정보를 불러오지 못했습니다.',
          );
        final store = snapshot.data ?? const <String, dynamic>{};
        final details = [store['address'], store['phone']]
            .where(
              (value) => value != null && value.toString().trim().isNotEmpty,
            )
            .join(' · ');
        return Container(
          margin: const EdgeInsets.only(bottom: 8),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(15),
            border: Border.all(color: line),
          ),
          child: Row(
            children: [
              const Icon(Icons.store_outlined, color: muted),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      store['name']?.toString() ?? '매장',
                      style: const TextStyle(
                        fontSize: 12,
                        color: ink,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      details.isEmpty ? '매장 정보' : details,
                      style: const TextStyle(fontSize: 10, color: muted),
                    ),
                  ],
                ),
              ),
              IconButton(
                onPressed: () => _editStore(store),
                icon: const Icon(Icons.edit_outlined, color: blue),
              ),
            ],
          ),
        );
      },
    );
  }

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
        Text('인증 사용 중', style: TextStyle(color: muted, fontSize: 10)),
      ],
    ),
  );
}
