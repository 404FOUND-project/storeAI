import 'package:flutter/material.dart';

import '../app.dart' show blue, ink, line, muted;
import '../core/network/backend_api.dart';
import '../widgets/backend_state.dart';

class RecommendationScreen extends StatefulWidget {
  final int? storeId;
  final bool storeLoading;
  final String? storeError;

  const RecommendationScreen({
    super.key,
    required this.storeId,
    required this.storeLoading,
    required this.storeError,
  });

  @override
  State<RecommendationScreen> createState() => _RecommendationScreenState();
}

class _RecommendationScreenState extends State<RecommendationScreen> {
  Future<Map<String, dynamic>>? _sets;
  Future<List<Map<String, dynamic>>>? _menus;
  Future<List<Map<String, dynamic>>>? _inventory;
  Future<Map<String, dynamic>>? _reorder;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void didUpdateWidget(covariant RecommendationScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.storeId != widget.storeId) _load();
  }

  void _load() {
    final id = widget.storeId;
    _sets = id == null ? null : BackendApi.instance.setRecommendations(id);
    _menus = id == null ? null : BackendApi.instance.menus(id);
    _inventory = id == null ? null : BackendApi.instance.inventory(id);
    _reorder = id == null
        ? null
        : BackendApi.instance.reorderRecommendations(id);
  }

  List<Map<String, dynamic>> _maps(dynamic value) => value is List
      ? value
            .whereType<Map>()
            .map((item) => Map<String, dynamic>.from(item))
            .toList()
      : const [];

  Future<void> _editMenu([Map<String, dynamic>? menu]) async {
    final name = TextEditingController(text: menu?['name']?.toString() ?? '');
    final category = TextEditingController(
      text: menu?['category']?.toString() ?? '',
    );
    final posCode = TextEditingController(
      text: menu?['pos_code']?.toString() ?? '',
    );
    final price = TextEditingController(text: menu?['price']?.toString() ?? '');
    final cost = TextEditingController(text: menu?['cost']?.toString() ?? '');
    final saved = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(menu == null ? '메뉴 등록' : '메뉴 수정'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              _input(name, '메뉴명'),
              _input(category, '카테고리'),
              _input(posCode, 'POS 코드'),
              _input(price, '판매가', number: true),
              _input(cost, '원가', number: true),
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
    if (saved != true) {
      for (final c in [name, category, posCode, price, cost]) {
        c.dispose();
      }
      return;
    }
    final storeId = widget.storeId;
    final parsedPrice = int.tryParse(price.text.trim());
    if (storeId == null ||
        name.text.trim().isEmpty ||
        parsedPrice == null ||
        parsedPrice <= 0) {
      for (final c in [name, category, posCode, price, cost]) {
        c.dispose();
      }
      _message('메뉴명과 0보다 큰 판매가를 입력해 주세요.');
      return;
    }
    final payload = <String, dynamic>{
      'name': name.text.trim(),
      'category': category.text.trim(),
      'pos_code': posCode.text.trim().isEmpty ? null : posCode.text.trim(),
      'price': parsedPrice,
      'cost': int.tryParse(cost.text.trim()),
      'is_active': menu?['is_active'] ?? true,
    };
    for (final c in [name, category, posCode, price, cost]) {
      c.dispose();
    }
    try {
      if (menu == null) {
        await BackendApi.instance.createMenu(storeId, payload);
      } else {
        await BackendApi.instance.updateMenu(
          storeId,
          int.parse(menu['id'].toString()),
          payload,
        );
      }
      if (mounted) setState(_load);
    } on BackendException catch (error) {
      _message(error.message);
    }
  }

  Future<void> _deleteMenu(Map<String, dynamic> menu) async {
    final id = widget.storeId;
    if (id == null) return;
    if (!await _confirm('이 메뉴를 삭제할까요?')) return;
    try {
      await BackendApi.instance.deleteMenu(
        id,
        int.parse(menu['id'].toString()),
      );
      if (mounted) setState(_load);
    } on BackendException catch (error) {
      _message(error.message);
    }
  }

  Future<void> _editInventory([Map<String, dynamic>? item]) async {
    final name = TextEditingController(
      text: item?['ingredient_name']?.toString() ?? '',
    );
    final quantity = TextEditingController(
      text: item?['quantity']?.toString() ?? '',
    );
    final unit = TextEditingController(text: item?['unit']?.toString() ?? '');
    final expiry = TextEditingController(
      text: item?['expiration_date']?.toString() ?? '',
    );
    final saved = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(item == null ? '재고 등록' : '재고 수정'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              _input(name, '재료명'),
              _input(quantity, '보유 수량', number: true),
              _input(unit, '단위'),
              _input(expiry, '유통기한 (YYYY-MM-DD)'),
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
    if (saved != true) {
      for (final c in [name, quantity, unit, expiry]) {
        c.dispose();
      }
      return;
    }
    final storeId = widget.storeId;
    final parsedQuantity = double.tryParse(quantity.text.trim());
    if (storeId == null ||
        name.text.trim().isEmpty ||
        parsedQuantity == null ||
        parsedQuantity < 0) {
      for (final c in [name, quantity, unit, expiry]) {
        c.dispose();
      }
      _message('재료명과 0 이상의 수량을 입력해 주세요.');
      return;
    }
    final payload = <String, dynamic>{
      'ingredient_name': name.text.trim(),
      'quantity': quantity.text.trim(),
      'unit': unit.text.trim(),
      'expiration_date': expiry.text.trim().isEmpty ? null : expiry.text.trim(),
    };
    for (final c in [name, quantity, unit, expiry]) {
      c.dispose();
    }
    try {
      if (item == null) {
        await BackendApi.instance.createInventory(storeId, payload);
      } else {
        await BackendApi.instance.updateInventory(
          storeId,
          int.parse(item['id'].toString()),
          payload,
        );
      }
      if (mounted) setState(_load);
    } on BackendException catch (error) {
      _message(error.message);
    }
  }

  Future<void> _deleteInventory(Map<String, dynamic> item) async {
    final id = widget.storeId;
    if (id == null) return;
    if (!await _confirm('이 재고 항목을 삭제할까요?')) return;
    try {
      await BackendApi.instance.deleteInventory(
        id,
        int.parse(item['id'].toString()),
      );
      if (mounted) setState(_load);
    } on BackendException catch (error) {
      _message(error.message);
    }
  }

  Future<bool> _confirm(String text) async =>
      await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          content: Text(text),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('취소'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('삭제'),
            ),
          ],
        ),
      ) ??
      false;

  Widget _input(
    TextEditingController controller,
    String label, {
    bool number = false,
  }) => Padding(
    padding: const EdgeInsets.only(bottom: 8),
    child: TextField(
      controller: controller,
      keyboardType: number
          ? const TextInputType.numberWithOptions(decimal: true)
          : TextInputType.text,
      decoration: InputDecoration(labelText: label),
    ),
  );

  void _message(String text) {
    if (mounted)
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
  }

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      const Text(
        '추천 및 재고',
        style: TextStyle(fontSize: 25, fontWeight: FontWeight.w800, color: ink),
      ),
      const SizedBox(height: 18),
      if (widget.storeLoading)
        const Center(child: CircularProgressIndicator())
      else if (widget.storeError != null)
        _card(Text(widget.storeError!, style: const TextStyle(color: muted)))
      else if (_sets == null)
        const BackendUnavailable(feature: '매장 추천')
      else ...[
        _title('함께 주문된 메뉴 세트'),
        FutureBuilder<Map<String, dynamic>>(
          future: _sets,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting)
              return _card(const Text('추천 조합을 불러오는 중입니다.'));
            if (snapshot.hasError)
              return _card(const Text('메뉴 조합 추천을 불러오지 못했습니다.'));
            final sets = _maps(snapshot.data?['sets']);
            if (sets.isEmpty) return _card(const Text('추천할 주문 조합 데이터가 없습니다.'));
            return Column(
              children: sets.map((set) {
                final names = _maps(set['menus'])
                    .map((menu) => menu['name']?.toString() ?? '')
                    .where((name) => name.isNotEmpty)
                    .join(' + ');
                return _card(
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        names.isEmpty ? '추천 세트' : names,
                        style: const TextStyle(
                          color: ink,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 5),
                      Text(
                        '함께 주문 ${set['orders_together'] ?? 0}회 · 지지도 ${set['support'] ?? 0}%',
                        style: const TextStyle(color: muted, fontSize: 11),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '세트 제안가 ${set['set_price'] ?? '-'}원 (할인 ${set['discount'] ?? 0}원)',
                        style: const TextStyle(
                          color: blue,
                          fontSize: 11,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                  ),
                );
              }).toList(),
            );
          },
        ),
        const SizedBox(height: 18),
        _titleAction('메뉴 관리', _editMenu),
        FutureBuilder<List<Map<String, dynamic>>>(
          future: _menus,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting)
              return _card(const Text('메뉴를 불러오는 중입니다.'));
            if (snapshot.hasError) return _card(const Text('메뉴를 불러오지 못했습니다.'));
            final items = snapshot.data ?? const [];
            if (items.isEmpty)
              return _card(const Text('등록된 메뉴가 없습니다. 메뉴를 추가해 주세요.'));
            return Column(
              children: items
                  .map(
                    (menu) => _managedRow(
                      menu['name']?.toString() ?? '메뉴',
                      '${menu['price'] ?? 0}원 · ${menu['category'] ?? '분류 없음'}',
                      Icons.restaurant_menu_outlined,
                      onEdit: () => _editMenu(menu),
                      onDelete: () => _deleteMenu(menu),
                    ),
                  )
                  .toList(),
            );
          },
        ),
        const SizedBox(height: 18),
        _titleAction('재고 현황', _editInventory),
        FutureBuilder<List<Map<String, dynamic>>>(
          future: _inventory,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting)
              return _card(const Text('재고 정보를 불러오는 중입니다.'));
            if (snapshot.hasError)
              return _card(const Text('재고 정보를 불러오지 못했습니다.'));
            final items = snapshot.data ?? const [];
            if (items.isEmpty)
              return _card(const Text('등록된 재고가 없습니다. 재고를 추가해 주세요.'));
            return Column(
              children: items
                  .map(
                    (item) => _managedRow(
                      item['ingredient_name']?.toString() ?? '재료',
                      '${item['quantity'] ?? 0} ${item['unit'] ?? ''} · ${item['stock_status'] ?? '상태 미확인'}',
                      Icons.inventory_2_outlined,
                      onEdit: () => _editInventory(item),
                      onDelete: () => _deleteInventory(item),
                    ),
                  )
                  .toList(),
            );
          },
        ),
        const SizedBox(height: 18),
        _title('발주 추천'),
        FutureBuilder<Map<String, dynamic>>(
          future: _reorder,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting)
              return _card(const Text('발주 수량을 계산하는 중입니다.'));
            if (snapshot.hasError)
              return _card(const Text('발주 추천을 불러오지 못했습니다.'));
            final data = snapshot.data ?? const <String, dynamic>{};
            final items = _maps(data['results']);
            if (items.isEmpty) return _card(const Text('발주 추천 데이터가 없습니다.'));
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (data['basis'] != null)
                  _card(
                    Text(
                      '산정 기준: ${data['basis']}',
                      style: const TextStyle(color: muted, fontSize: 10),
                    ),
                  ),
                ...items.map(
                  (item) => _row(
                    item['ingredient_name']?.toString() ?? '재료',
                    '권장 발주 ${item['recommended_order_qty'] ?? 0} ${item['unit'] ?? ''} · ${item['note'] ?? ''}',
                    item['stock_status'] == 'danger'
                        ? Icons.warning_amber_rounded
                        : Icons.shopping_cart_outlined,
                  ),
                ),
              ],
            );
          },
        ),
      ],
    ],
  );

  Widget _title(String value) => Padding(
    padding: const EdgeInsets.only(bottom: 9),
    child: Align(
      alignment: Alignment.centerLeft,
      child: Text(
        value,
        style: const TextStyle(
          color: ink,
          fontSize: 16,
          fontWeight: FontWeight.w800,
        ),
      ),
    ),
  );

  Widget _titleAction(String title, VoidCallback onAdd) => Padding(
    padding: const EdgeInsets.only(bottom: 9),
    child: Row(
      children: [
        Expanded(
          child: Text(
            title,
            style: const TextStyle(
              color: ink,
              fontSize: 16,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
        IconButton(
          onPressed: onAdd,
          tooltip: '추가',
          icon: const Icon(Icons.add_circle_outline, color: blue),
        ),
      ],
    ),
  );

  Widget _card(Widget child) => Container(
    width: double.infinity,
    margin: const EdgeInsets.only(bottom: 8),
    padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.circular(15),
      border: Border.all(color: line),
    ),
    child: child,
  );

  Widget _row(String title, String subtitle, IconData icon) => _card(
    Row(
      children: [
        Icon(icon, color: blue, size: 20),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(color: ink, fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 3),
              Text(
                subtitle,
                style: const TextStyle(color: muted, fontSize: 11),
              ),
            ],
          ),
        ),
      ],
    ),
  );

  Widget _managedRow(
    String title,
    String subtitle,
    IconData icon, {
    required VoidCallback onEdit,
    required VoidCallback onDelete,
  }) => _card(
    Row(
      children: [
        Icon(icon, color: blue, size: 20),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(color: ink, fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 3),
              Text(
                subtitle,
                style: const TextStyle(color: muted, fontSize: 11),
              ),
            ],
          ),
        ),
        IconButton(
          onPressed: onEdit,
          icon: const Icon(Icons.edit_outlined, size: 19, color: blue),
        ),
        IconButton(
          onPressed: onDelete,
          icon: const Icon(
            Icons.delete_outline,
            size: 19,
            color: Colors.redAccent,
          ),
        ),
      ],
    ),
  );
}
