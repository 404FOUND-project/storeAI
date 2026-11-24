import 'package:flutter/material.dart';

import 'core/network/backend_api.dart';
import 'screens/auth_screen.dart';

void main() => runApp(const CafeOnApp());

const blue = Color(0xFF3182F6);
const ink = Color(0xFF1B2B45);
const muted = Color(0xFF697386);
const line = Color(0xFFE8EBF0);
const bg = Color(0xFFF4F7FB);
const green = Color(0xFF15956F);

class CafeOnApp extends StatefulWidget {
  const CafeOnApp({super.key});

  @override
  State<CafeOnApp> createState() => _CafeOnAppState();
}

class _CafeOnAppState extends State<CafeOnApp> {
  bool authenticated = false;

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: '카페온',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      useMaterial3: true,
      scaffoldBackgroundColor: bg,
      colorScheme: ColorScheme.fromSeed(seedColor: blue),
    ),
    home: authenticated
        ? const CafeHome()
        : AuthScreen(
            onAuthenticated: () => setState(() => authenticated = true),
          ),
  );
}

class CafeHome extends StatefulWidget {
  const CafeHome({super.key});

  @override
  State<CafeHome> createState() => _CafeHomeState();
}

class _CafeHomeState extends State<CafeHome> {
  int tab = 0;
  bool showNotifications = false;
  bool notificationsRead = false;
  final Set<int> readNotifications = {};
  int? storeId;
  Map<String, dynamic>? currentUser;
  Future<Map<String, dynamic>>? salesFuture;
  Future<Map<String, dynamic>>? reviewsFuture;
  Future<Map<String, dynamic>>? forecastFuture;
  Future<List<Map<String, dynamic>>>? profitabilityFuture;
  Future<Map<String, dynamic>>? setsFuture;
  Future<Map<String, dynamic>>? reorderFuture;
  Future<List<Map<String, dynamic>>>? inventoryFuture;
  final labels = ['홈', '매출 분석', 'AI 분석', '세트 추천', '마이'];
  final icons = [
    Icons.home_rounded,
    Icons.bar_chart_rounded,
    Icons.auto_awesome_rounded,
    Icons.storefront_rounded,
    Icons.person_outline_rounded,
  ];

  @override
  void initState() {
    super.initState();
    _loadStoreData();
  }

  Future<void> _loadStoreData() async {
    try {
      final user = await BackendApi.instance.currentUser();
      final stores = await BackendApi.instance.stores();
      final id = stores.isEmpty ? null : int.tryParse('${stores.first['id']}');
      if (!mounted) return;
      setState(() {
        currentUser = user;
        storeId = id;
        if (id != null) {
          salesFuture = BackendApi.instance.salesAnalysis(id);
          reviewsFuture = BackendApi.instance.reviewAnalysis(id);
          forecastFuture = BackendApi.instance.salesForecast(id);
          profitabilityFuture = BackendApi.instance.menuProfitability(id);
          setsFuture = BackendApi.instance.setRecommendations(id);
          reorderFuture = BackendApi.instance.reorderRecommendations(id);
          inventoryFuture = BackendApi.instance.inventory(id);
        }
      });
    } catch (_) {
      if (mounted) setState(() {});
    }
  }

  int _asInt(dynamic value) =>
      value is num ? value.round() : int.tryParse('$value') ?? 0;
  String _currency(dynamic value) => '₩${_asInt(value)}';

  void openChatbot() {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      backgroundColor: Colors.transparent,
      barrierColor: const Color(0x990B1728),
      builder: (context) => ChatbotSheet(
        storeId: storeId,
        onNavigate: (destination) => setState(() => tab = destination),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    floatingActionButton: FloatingActionButton(
      onPressed: openChatbot,
      backgroundColor: blue,
      foregroundColor: Colors.white,
      elevation: 5,
      shape: const CircleBorder(),
      child: const Icon(Icons.chat_bubble_outline_rounded, size: 25),
    ),
    body: SafeArea(
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 760),
          child: Column(
            children: [
              header(),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(18, 8, 18, 24),

                  child: showNotifications
                      ? notificationPage()
                      : (tab == 0 ? home() : otherPage()),
                ),
              ),
              bottomNav(),
            ],
          ),
        ),
      ),
    ),
  );

  Widget header() => Padding(
    padding: const EdgeInsets.fromLTRB(20, 14, 20, 12),
    child: Row(
      children: [
        Container(
          width: 42,
          height: 42,
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [Color(0xFF4A96FF), Color(0xFF2676E8)],
            ),
            borderRadius: BorderRadius.circular(14),
          ),
          child: const Icon(
            Icons.coffee_rounded,
            color: Colors.white,
            size: 24,
          ),
        ),
        const SizedBox(width: 10),
        const Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '카페온',
                style: TextStyle(
                  fontSize: 21,
                  fontWeight: FontWeight.w800,
                  color: ink,
                ),
              ),
              Text(
                'AI 카페 운영 매니저',
                style: TextStyle(fontSize: 12, color: muted),
              ),
            ],
          ),
        ),
        IconButton(
          onPressed: () {
            setState(() {
              showNotifications = true;
            });
          },
          icon: const Icon(Icons.notifications_none_rounded, color: ink),
          style: IconButton.styleFrom(backgroundColor: Colors.white),
        ),
        const CircleAvatar(
          backgroundColor: Color(0xFFE3EEFF),
          child: Icon(Icons.person_rounded, color: blue),
        ),
      ],
    ),
  );

  Widget home() => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      const Text(
        '안녕하세요, 사장님 👋',
        style: TextStyle(fontSize: 23, fontWeight: FontWeight.w800, color: ink),
      ),
      const SizedBox(height: 5),
      const Text(
        '오늘 가게 운영 현황을 확인해 보세요.',
        style: TextStyle(fontSize: 13, color: muted),
      ),
      const SizedBox(height: 18),
      hero(),
      const SizedBox(height: 20),
      section('오늘의 매출', '상세 보기', () => setState(() => tab = 1)),
      const SizedBox(height: 10),
      FutureBuilder<Map<String, dynamic>>(
        future: salesFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting)
            return const Center(child: CircularProgressIndicator());
          if (snapshot.hasError) return Text(snapshot.error.toString());
          final summary = snapshot.data?['summary'] as Map? ?? const {};
          return Column(
            children: [
              Row(
                children: [
                  Expanded(
                    child: metric(
                      'Sales (30 days)',
                      _currency(summary['sales']),
                      '${summary['days_with_data'] ?? 0} days with data',
                      Icons.payments_rounded,
                      green,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: metric(
                      'Orders',
                      '${_asInt(summary['order_count'])}',
                      'last 30 days',
                      Icons.shopping_bag_rounded,
                      blue,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(
                    child: metric(
                      'Average ticket',
                      _currency(summary['average_ticket']),
                      'per order',
                      Icons.receipt_long_rounded,
                      const Color(0xFFB46C08),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: metric(
                      'Store',
                      storeId?.toString() ?? 'Not linked',
                      'from your account',
                      Icons.storefront_rounded,
                      blue,
                    ),
                  ),
                ],
              ),
            ],
          );
        },
      ),
      const SizedBox(height: 22),
      section('AI 운영 인사이트', '모두 보기', () => message('AI 운영 인사이트 목록을 준비 중이에요.')),
      const SizedBox(height: 10),
      insight(
        Icons.wb_sunny_rounded,
        const Color(0xFFB46C08),
        const Color(0xFFFFF6E5),
        '날씨에 맞는 메뉴를 준비해 보세요',
        '오늘은 따뜻한 음료 판매가 늘어날 수 있어요. 라떼류 재고를 확인해 보세요.',
        '날씨 분석',
      ),
      const SizedBox(height: 10),
      insight(
        Icons.auto_awesome_rounded,
        blue,
        const Color(0xFFEEF6FF),
        '오후 2–4시 매출이 늘었어요',
        '최근 같은 시간대보다 매출이 12% 높아요. 주문 동선을 점검해 보세요.',
        'AI 인사이트',
      ),
      const SizedBox(height: 20),
      section('매출 흐름', '주간 리포트', () => setState(() => tab = 1)),
      const SizedBox(height: 10),
      chart(),
      const SizedBox(height: 20),
      section('매장 상태', '종합 운영 진단 보기', () => setState(() => tab = 2)),
      const SizedBox(height: 10),
      Container(
        padding: const EdgeInsets.all(15),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: line),
        ),
        child: const Column(
          children: [
            _StatusRow(label: '매출 흐름', value: '안정적이에요', color: green),
            Divider(height: 18, color: line),
            _StatusRow(label: '리뷰 만족도', value: '4.6 · 좋은 편', color: blue),
            Divider(height: 18, color: line),
            _StatusRow(
              label: '재고',
              value: '2개 품목 확인 필요',
              color: Color(0xFFB46C08),
            ),
            Divider(height: 18, color: line),
            _StatusRow(
              label: '운영 진단',
              value: '주의 깊게 관찰',
              color: Color(0xFFB46C08),
            ),
          ],
        ),
      ),
    ],
  );

  Widget hero() => FutureBuilder<Map<String, dynamic>>(
    future: salesFuture,
    builder: (context, snapshot) {
      final summary = snapshot.data?['summary'] as Map? ?? const {};
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.all(21),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF4A96FF), Color(0xFF2676E8)],
          ),
          borderRadius: BorderRadius.circular(25),
          boxShadow: [
            BoxShadow(
              color: blue.withValues(alpha: 0.18),
              blurRadius: 20,
              offset: const Offset(0, 8),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Text(
                  'STORE OVERVIEW',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                Spacer(),
                Icon(Icons.auto_awesome_rounded, color: Colors.white, size: 25),
              ],
            ),
            const SizedBox(height: 15),
            Text(
              snapshot.connectionState == ConnectionState.waiting
                  ? 'Loading store data'
                  : 'Recent sales',
              style: const TextStyle(color: Colors.white, fontSize: 15),
            ),
            const SizedBox(height: 3),
            Text(
              snapshot.hasError
                  ? 'API unavailable'
                  : _currency(summary['sales']),
              style: const TextStyle(
                color: Colors.white,
                fontSize: 27,
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 9),
            Text(
              snapshot.hasError
                  ? snapshot.error.toString()
                  : 'Last 30 days ? ${summary['order_count'] ?? 0} orders',
              style: const TextStyle(color: Colors.white, fontSize: 12),
            ),
          ],
        ),
      );
    },
  );

  Widget metric(
    String title,
    String value,
    String caption,
    IconData icon,
    Color color,
  ) => Container(
    padding: const EdgeInsets.all(15),
    decoration: BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.circular(19),
      border: Border.all(color: line),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(icon, color: color, size: 18),
            const SizedBox(width: 6),
            Expanded(
              child: Text(
                title,
                style: const TextStyle(fontSize: 11, color: muted),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
        const SizedBox(height: 13),
        FittedBox(
          fit: BoxFit.scaleDown,
          alignment: Alignment.centerLeft,
          child: Text(
            value,
            style: const TextStyle(
              fontSize: 21,
              fontWeight: FontWeight.w800,
              color: ink,
            ),
          ),
        ),
        const SizedBox(height: 5),
        Text(
          caption,
          style: TextStyle(
            fontSize: 10,
            color: caption.startsWith('+') ? green : muted,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    ),
  );

  Widget section(String title, String? action, VoidCallback? onTap) => Row(
    children: [
      Expanded(
        child: Text(
          title,
          style: const TextStyle(
            fontSize: 17,
            fontWeight: FontWeight.w800,
            color: ink,
          ),
        ),
      ),
      if (action != null)
        TextButton(
          onPressed: onTap,
          style: TextButton.styleFrom(
            foregroundColor: blue,
            padding: const EdgeInsets.symmetric(horizontal: 4),
          ),
          child: Text(
            action,
            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
          ),
        ),
    ],
  );

  Widget insight(
    IconData icon,
    Color color,
    Color background,
    String title,
    String body,
    String tag,
  ) => Container(
    padding: const EdgeInsets.all(15),
    decoration: BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.circular(19),
      border: Border.all(color: line),
    ),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: background,
            borderRadius: BorderRadius.circular(13),
          ),
          child: Icon(icon, color: color, size: 21),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                tag,
                style: TextStyle(
                  color: color,
                  fontSize: 10,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                title,
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w800,
                  color: ink,
                ),
              ),
              const SizedBox(height: 5),
              Text(
                body,
                style: const TextStyle(fontSize: 11, color: muted, height: 1.5),
              ),
            ],
          ),
        ),
      ],
    ),
  );

  Widget chart() => FutureBuilder<Map<String, dynamic>>(
    future: salesFuture,
    builder: (context, snapshot) {
      final series =
          (snapshot.data?['series'] as List?)?.cast<Map>() ?? const <Map>[];
      if (series.isEmpty)
        return _apiCard(
          snapshot.hasError
              ? snapshot.error.toString()
              : 'No recent sales data',
        );
      final recent = series.length > 7
          ? series.sublist(series.length - 7)
          : series;
      final maxValue = recent
          .map((e) => _asInt(e['sales']))
          .fold<int>(1, (a, b) => a > b ? a : b);
      return Container(
        padding: const EdgeInsets.fromLTRB(17, 17, 17, 14),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: line),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Recent daily sales',
              style: TextStyle(color: muted, fontSize: 12),
            ),
            const SizedBox(height: 5),
            Text(
              _currency(recent.fold<int>(0, (a, e) => a + _asInt(e['sales']))),
              style: const TextStyle(
                color: ink,
                fontSize: 23,
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 18),
            SizedBox(
              height: 110,
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: recent.map((item) {
                  final value = _asInt(item['sales']);
                  return Expanded(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 4),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.end,
                        children: [
                          Expanded(
                            child: Align(
                              alignment: Alignment.bottomCenter,
                              child: FractionallySizedBox(
                                heightFactor: value / maxValue,
                                child: Container(
                                  decoration: BoxDecoration(
                                    color: blue,
                                    borderRadius: BorderRadius.circular(7),
                                  ),
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            '${item['period_start']}'.split('-').last,
                            style: const TextStyle(fontSize: 10, color: muted),
                          ),
                        ],
                      ),
                    ),
                  );
                }).toList(),
              ),
            ),
          ],
        ),
      );
    },
  );

  Widget quick(IconData icon, String label, int destination) => InkWell(
    onTap: () => setState(() => tab = destination),
    borderRadius: BorderRadius.circular(17),
    child: Container(
      padding: const EdgeInsets.symmetric(vertical: 17, horizontal: 5),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(17),
        border: Border.all(color: line),
      ),
      child: Column(
        children: [
          Icon(icon, color: blue, size: 23),
          const SizedBox(height: 7),
          Text(
            label,
            style: const TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w700,
              color: ink,
            ),
          ),
        ],
      ),
    ),
  );

  Widget otherPage() {
    if (tab == 1) return salesPage();
    if (tab == 2) return aiAnalysisPage();
    if (tab == 3) return setRecommendationPage();
    return myPage();
  }

  Widget notificationPage() => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Row(
        children: [
          IconButton(
            onPressed: () {
              setState(() {
                showNotifications = false;
              });
            },
            icon: const Icon(Icons.chevron_left_rounded, size: 27),
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(),
          ),
          const SizedBox(width: 10),
          const Expanded(
            child: Text(
              '알림',
              style: TextStyle(
                fontSize: 25,
                fontWeight: FontWeight.w800,
                color: ink,
              ),
            ),
          ),
          TextButton(
            onPressed: () {
              setState(() {
                notificationsRead = true;
              });
            },
            child: const Text(
              '모두 읽음',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w700,
                color: blue,
              ),
            ),
          ),
        ],
      ),
      const SizedBox(height: 25),
      const Text(
        '오늘',
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w700,
          color: muted,
        ),
      ),
      const SizedBox(height: 8),

      notificationItem(
        icon: Icons.warning_amber_rounded,
        iconColor: const Color(0xFFE58A00),
        iconBg: const Color(0xFFFFF5E5),
        title: '매출 이상 징후를 확인해 주세요',
        description: '목요일 오후 매출이 최근 평균보다 18% 낮아요.',
        time: '10분 전',
        index: 0,
      ),
      notificationItem(
        icon: Icons.inventory_2_outlined,
        iconColor: const Color(0xFFFF5B66),
        iconBg: const Color(0xFFFFF0F1),
        title: '우유 재고가 곧 부족해요',
        description: '현재 판매 속도라면 내일 오후 소진될 수 있어요.',
        time: '1시간 전',
        index: 1,
      ),
      notificationItem(
        icon: Icons.description_outlined,
        iconColor: const Color(0xFF438EFF),
        iconBg: const Color(0xFFEDF5FF),
        title: '주간 AI 보고서가 완성됐어요',
        description: '이번 주 우선 실행 항목 3개를 확인해 보세요.',
        time: '어제',
        index: 2,
      ),
      notificationItem(
        icon: Icons.storefront_outlined,
        iconColor: const Color(0xFF438EFF),
        iconBg: const Color(0xFFEDF5FF),
        title: '새로운 세트 조합을 찾았어요',
        description: '함께 주문되는 메뉴를 분석해 세트 구성을 제안했어요.',
        time: '어제',
        index: 3,
      ),
    ],
  );

  Widget notificationItem({
    required IconData icon,
    required Color iconColor,
    required Color iconBg,
    required String title,
    required String description,
    required String time,
    required int index,
  }) {
    return InkWell(
      onTap: () {
        setState(() {
          readNotifications.add(index);
        });
      },
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 15),
        decoration: const BoxDecoration(
          border: Border(bottom: BorderSide(color: Color(0xFFE5E9F0))),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 34,
              height: 34,
              decoration: BoxDecoration(
                color: iconBg,
                borderRadius: BorderRadius.circular(11),
              ),
              child: Icon(icon, size: 17, color: iconColor),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w800,
                      color: ink,
                    ),
                  ),
                  const SizedBox(height: 5),
                  Text(
                    description,
                    style: const TextStyle(
                      fontSize: 10,
                      color: muted,
                      height: 1.5,
                    ),
                  ),
                  const SizedBox(height: 9),
                  Text(
                    time,
                    style: const TextStyle(
                      fontSize: 9,
                      color: Color(0xFF9AA5B5),
                    ),
                  ),
                ],
              ),
            ),
            if (!notificationsRead && !readNotifications.contains(index))
              Container(
                margin: const EdgeInsets.only(top: 4, left: 8),
                width: 5,
                height: 5,
                decoration: const BoxDecoration(
                  color: Color(0xFF438EFF),
                  shape: BoxShape.circle,
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget salesPage() => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      const Text(
        'Sales analysis',
        style: TextStyle(fontSize: 25, fontWeight: FontWeight.w800, color: ink),
      ),
      const SizedBox(height: 16),
      FutureBuilder<Map<String, dynamic>>(
        future: salesFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting)
            return const Center(child: CircularProgressIndicator());
          if (snapshot.hasError) return _apiCard(snapshot.error.toString());
          final data = snapshot.data ?? const <String, dynamic>{};
          final summary = data['summary'] as Map? ?? const {};
          final rows = (data['series'] as List?)?.cast<Map>() ?? const <Map>[];
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [Color(0xFF4A96FF), Color(0xFF2676E8)],
                  ),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Last 30 days sales',
                      style: TextStyle(color: Colors.white70),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      _currency(summary['sales']),
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 27,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    Text(
                      '${_asInt(summary['order_count'])} orders / average ${_currency(summary['average_ticket'])}',
                      style: const TextStyle(color: Colors.white),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              chart(),
              const SizedBox(height: 16),
              ...rows.reversed
                  .take(14)
                  .map(
                    (r) => _settingsTile(
                      Icons.bar_chart_rounded,
                      '${r['period_start']}',
                      '${_currency(r['sales'])} ? ${r['order_count']} orders',
                    ),
                  ),
            ],
          );
        },
      ),
    ],
  );

  Widget aiAnalysisPage() => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      const Text(
        'AI analysis',
        style: TextStyle(fontSize: 25, fontWeight: FontWeight.w800, color: ink),
      ),
      const SizedBox(height: 16),
      _apiSection('Review insights', reviewsFuture, (data) {
        final categories =
            (data['negative_categories'] as List?)?.cast<Map>() ??
            const <Map>[];
        final menus = (data['menus'] as List?)?.cast<Map>() ?? const <Map>[];
        return Column(
          children: [
            if (data['notice'] != null) _apiCard('${data['notice']}'),
            ...categories.map(
              (r) => _settingsTile(
                Icons.rate_review_outlined,
                '${r['label'] ?? r['category']}',
                'negative reviews: ${r['count']}',
              ),
            ),
            ...menus.map(
              (r) => _settingsTile(
                Icons.insights_rounded,
                '${r['name']}',
                'reviews ${r['review_count']} ? positive ${((r['positive_ratio'] as num? ?? 0) * 100).round()}% ? sold ${r['quantity']}',
              ),
            ),
          ],
        );
      }),
      const SizedBox(height: 18),
      _apiSection('Saved sales forecast', forecastFuture, (data) {
        final rows = (data['series'] as List?)?.cast<Map>() ?? const <Map>[];
        return Column(
          children: rows
              .map(
                (r) => _settingsTile(
                  Icons.auto_graph_rounded,
                  '${r['date']}',
                  'predicted quantity: ${r['predicted_quantity']}',
                ),
              )
              .toList(),
        );
      }),
      const SizedBox(height: 18),
      FutureBuilder<List<Map<String, dynamic>>>(
        future: profitabilityFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting)
            return const Center(child: CircularProgressIndicator());
          if (snapshot.hasError) return _apiCard(snapshot.error.toString());
          final rows = snapshot.data ?? const [];
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              section('Menu profitability', null, null),
              ...rows.map(
                (r) => _settingsTile(
                  Icons.payments_outlined,
                  '${r['name']}',
                  'sold ${r['quantity']} ? profit ${r['profit'] ?? 'cost missing'} ? margin ${r['margin_rate'] ?? '-'}%',
                ),
              ),
            ],
          );
        },
      ),
    ],
  );

  Widget _apiCard(String text) => Container(
    width: double.infinity,
    margin: const EdgeInsets.only(bottom: 8),
    padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.circular(15),
      border: Border.all(color: line),
    ),
    child: Text(text, style: const TextStyle(fontSize: 11, color: muted)),
  );

  Widget _apiSection(
    String title,
    Future<Map<String, dynamic>>? future,
    Widget Function(Map<String, dynamic>) content,
  ) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      section(title, null, null),
      const SizedBox(height: 8),
      FutureBuilder<Map<String, dynamic>>(
        future: future,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting)
            return const Center(child: CircularProgressIndicator());
          if (snapshot.hasError) return _apiCard(snapshot.error.toString());
          return content(snapshot.data ?? const <String, dynamic>{});
        },
      ),
    ],
  );

  Widget setRecommendationPage() => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      const Text(
        'Set menu recommendations',
        style: TextStyle(fontSize: 25, fontWeight: FontWeight.w800, color: ink),
      ),
      const SizedBox(height: 16),
      _apiSection('Pairs from actual orders', setsFuture, (data) {
        final rows = (data['sets'] as List?)?.cast<Map>() ?? const <Map>[];
        return Column(
          children: rows.map((r) {
            final menus = (r['menus'] as List?)?.cast<Map>() ?? const <Map>[];
            return _recommendCard(
              menus.map((m) => '${m['name']}').join(' + '),
              'together ${r['orders_together']} orders',
              '${r['confidence']}%',
              'support ${r['support']}% ? lift ${r['lift']}',
              '${_currency(r['set_price'])}',
            );
          }).toList(),
        );
      }),
      const SizedBox(height: 18),
      _apiSection('Inventory reorder suggestions', reorderFuture, (data) {
        final rows = (data['results'] as List?)?.cast<Map>() ?? const <Map>[];
        return Column(
          children: rows
              .map(
                (r) => _settingsTile(
                  Icons.inventory_2_outlined,
                  '${r['ingredient_name']}',
                  'stock ${r['quantity']} ${r['unit']} ? order ${r['recommended_order_qty']} ? ${r['note']}',
                ),
              )
              .toList(),
        );
      }),
      const SizedBox(height: 18),
      FutureBuilder<List<Map<String, dynamic>>>(
        future: inventoryFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting)
            return const Center(child: CircularProgressIndicator());
          if (snapshot.hasError) return _apiCard(snapshot.error.toString());
          final rows = snapshot.data ?? const [];
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              section('Inventory', null, null),
              ...rows.map(
                (r) => _settingsTile(
                  Icons.inventory_2_rounded,
                  '${r['ingredient_name']}',
                  '${r['quantity']} ${r['unit']} ? ${r['stock_status']}',
                ),
              ),
            ],
          );
        },
      ),
    ],
  );

  Widget myPage() => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      const Text(
        'My account',
        style: TextStyle(fontSize: 25, fontWeight: FontWeight.w800, color: ink),
      ),
      const SizedBox(height: 18),
      Container(
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [Color(0xFF4A96FF), Color(0xFF2676E8)],
          ),
          borderRadius: BorderRadius.circular(20),
        ),
        child: Row(
          children: [
            const CircleAvatar(
              backgroundColor: Colors.white,
              child: Icon(Icons.person, color: blue),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${currentUser?['nickname'] ?? currentUser?['username'] ?? ''}',
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  Text(
                    '${currentUser?['email'] ?? ''}',
                    style: const TextStyle(color: Colors.white70, fontSize: 11),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
      const SizedBox(height: 20),
      section('Store and API status', null, null),
      const SizedBox(height: 10),
      _settingsTile(
        Icons.store_outlined,
        'Store ID: ${storeId ?? 'not linked'}',
        'loaded from the signed-in account',
      ),
      _settingsTile(
        Icons.link_rounded,
        'Backend APIs',
        storeId == null
            ? 'No store is assigned to this account'
            : 'sales ? reviews ? recommendations ? inventory',
      ),
    ],
  );

  Widget _progress(String label, double value, String percent) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 8),
    child: Column(
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                label,
                style: const TextStyle(fontSize: 12, color: ink),
              ),
            ),
            Text(
              percent,
              style: const TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w800,
                color: ink,
              ),
            ),
          ],
        ),
        const SizedBox(height: 7),
        ClipRRect(
          borderRadius: BorderRadius.circular(8),
          child: LinearProgressIndicator(
            value: value,
            minHeight: 6,
            color: blue,
            backgroundColor: line,
          ),
        ),
      ],
    ),
  );

  Widget _recommendCard(
    String title,
    String tag,
    String percent,
    String body,
    String price,
  ) => Container(
    width: double.infinity,
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.circular(18),
      border: Border.all(color: line),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          tag,
          style: const TextStyle(
            fontSize: 10,
            color: blue,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 7),
        Text(
          title,
          style: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w800,
            color: ink,
          ),
        ),
        const SizedBox(height: 7),
        Text(
          body,
          style: const TextStyle(fontSize: 11, color: muted, height: 1.5),
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Text(
              percent,
              style: const TextStyle(
                fontSize: 21,
                color: blue,
                fontWeight: FontWeight.w800,
              ),
            ),
            const Spacer(),
            Text(price, style: const TextStyle(fontSize: 11, color: muted)),
          ],
        ),
      ],
    ),
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
            const Icon(Icons.chevron_right_rounded, color: muted),
          ],
        ),
      );

  Widget bottomNav() => Container(
    padding: const EdgeInsets.fromLTRB(7, 9, 7, 8),
    decoration: BoxDecoration(
      color: Colors.white,
      border: Border(top: BorderSide(color: line)),
    ),
    child: Row(
      children: List.generate(labels.length, (i) {
        final selected = tab == i;
        return Expanded(
          child: InkWell(
            onTap: () => setState(() => tab = i),
            borderRadius: BorderRadius.circular(13),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 5),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    icons[i],
                    color: selected ? blue : const Color(0xFF9AA4B2),
                    size: 22,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    labels[i],
                    style: TextStyle(
                      fontSize: 10,
                      color: selected ? blue : muted,
                      fontWeight: selected ? FontWeight.w800 : FontWeight.w500,
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      }),
    ),
  );

  void message(String text) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
}

class _StatusRow extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  const _StatusRow({
    required this.label,
    required this.value,
    required this.color,
  });
  @override
  Widget build(BuildContext context) => Row(
    children: [
      Expanded(
        child: Text(
          label,
          style: const TextStyle(
            fontSize: 12,
            color: ink,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      Container(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
        decoration: BoxDecoration(
          color: color.withValues(alpha: .10),
          borderRadius: BorderRadius.circular(20),
        ),
        child: Text(
          value,
          style: TextStyle(
            fontSize: 10,
            color: color,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
    ],
  );
}

class ChatbotSheet extends StatefulWidget {
  final ValueChanged<int> onNavigate;
  final int? storeId;

  const ChatbotSheet({super.key, required this.onNavigate, this.storeId});

  @override
  State<ChatbotSheet> createState() => _ChatbotSheetState();
}

class _ChatbotSheetState extends State<ChatbotSheet> {
  String? selectedCategory;
  String? selectedQuestion;
  bool showAllCategories = false;
  late final Future<List<Map<String, dynamic>>> faqFuture;
  final TextEditingController questionController = TextEditingController();

  @override
  void initState() {
    super.initState();
    faqFuture = BackendApi.instance.chatbotFaq();
  }

  @override
  void dispose() {
    questionController.dispose();
    super.dispose();
  }

  Future<String> _answerFromBackend(String question) async {
    final categories = await BackendApi.instance.chatbotFaq();
    for (final category in categories) {
      final rawQuestions = category['questions'];
      if (rawQuestions is! List) continue;
      for (final item in rawQuestions.whereType<Map>()) {
        if (item['question']?.toString() == question && item['id'] != null) {
          final result = await BackendApi.instance.chatbotFaqAnswer(
            item['id'].toString(),
            storeId: widget.storeId,
          );
          return result['answer']?.toString() ?? 'No answer returned.';
        }
      }
    }
    return BackendApi.instance.askChatbot(question);
  }

  void _sendQuestion() {
    final text = questionController.text.trim();
    if (text.isEmpty) return;
    setState(() {
      selectedCategory = null;
      selectedQuestion = text;
    });
    questionController.clear();
  }

  final Map<String, IconData> categories = const {
    '이번 달 매출': Icons.bar_chart_rounded,
    '매출 예측': Icons.auto_awesome_rounded,
    '메뉴 분석': Icons.storefront_outlined,
    '재고 관리': Icons.inventory_2_outlined,
    '주변 상권 분석': Icons.location_on_outlined,
  };

  final Map<String, List<String>> questions = const {
    '이번 달 매출': [
      '이번 달 현재까지 매출은 얼마인가요?',
      '지난달 같은 기간보다 매출이 얼마나 변했나요?',
      '이번 달 매출이 가장 높았던 날은 언제인가요?',
      '시간대별 매출은 어떻게 다른가요?',
      '이번 달 매출 목표를 달성할 수 있을까요?',
    ],
    '매출 예측': [
      '내일 매출은 얼마나 예상되나요?',
      '이번 주 매출이 가장 높을 요일은 언제인가요?',
      '매출 예측은 어떤 데이터를 기반으로 하나요?',
      '매출을 높이려면 언제 프로모션을 해야 하나요?',
    ],
    '메뉴 분석': [
      '가장 많이 팔린 메뉴는 무엇인가요?',
      '함께 주문되는 메뉴는 무엇인가요?',
      '새롭게 추가하면 좋을 메뉴가 있나요?',
      '판매가 저조한 메뉴를 알려주세요.',
    ],
    '재고 관리': [
      '재고 확인이 필요한 메뉴가 있나요?',
      '내일 준비할 원재료를 추천해 주세요.',
      '재고 부족을 미리 알 수 있나요?',
      '판매량 기준으로 적정 재고를 알려주세요.',
    ],
    '주변 상권 분석': [
      '주변에 카페 고객이 많은 장소는 어디인가요?',
      '우리 가게 주변 상권의 특징은 무엇인가요?',
      '주변 경쟁 카페를 분석해 주세요.',
      '상권에 맞는 추천 메뉴가 있나요?',
    ],
  };

  String answerFor(String question) {
    if (question.contains('현재까지 매출')) {
      return '시연용 데이터 기준으로 이번 달 현재까지 매출은 2,482만원이에요. 실제 POS 연동 시 최신 수치로 바뀌도록 연결할 수 있어요.';
    }
    if (question.contains('지난달')) {
      return '시연용 예시에서는 지난달 같은 기간보다 매출이 12% 증가했어요. 요일별 매출과 주문 건수를 함께 확인하면 변화 원인을 파악하는 데 도움이 돼요.';
    }
    if (question.contains('가장 높았던 날')) {
      return '예시 데이터에서는 토요일 매출이 가장 높게 나타나요. 실제 데이터 연결 후 날짜별 매출을 비교해 확인할 수 있어요.';
    }
    if (question.contains('시간대별')) {
      return '일반적으로 점심 이후와 저녁 시간대의 매출을 나누어 보면 피크타임을 파악할 수 있어요. 실제 시간대별 주문 데이터를 연결하면 가게에 맞는 결과를 제공할 수 있어요.';
    }
    if (question.contains('목표')) {
      return '현재 예시 목표 달성률은 71.4%예요. 남은 영업일과 하루 평균 매출을 함께 고려해 목표 달성 가능성을 확인해 보세요.';
    }
    if (question.contains('내일 매출')) {
      return '시연용 답변이에요. 최근 매출, 요일, 날씨, 공휴일 데이터를 연결하면 내일 예상 매출과 예측 범위를 계산할 수 있어요.';
    }
    if (question.contains('요일')) {
      return '현재 예시 주간 데이터에서는 토요일 매출이 가장 높아요. 실제 매장 데이터로 요일별 패턴을 학습하면 더 정확한 예측이 가능해요.';
    }
    if (question.contains('기반')) {
      return '매출 예측에는 과거 POS 매출, 주문 건수, 요일, 날씨, 공휴일과 같은 변수를 활용할 수 있어요. 현재 화면은 예시 데이터이며 모델 연동은 별도 작업이에요.';
    }
    if (question.contains('프로모션')) {
      return '매출이 상대적으로 낮은 시간대에 세트 메뉴나 디저트 추가 할인처럼 부담이 적은 프로모션을 시험해 보세요. 진행 전후의 주문 수와 객단가를 비교하는 것이 좋아요.';
    }
    if (question.contains('많이 팔린 메뉴')) {
      return '실제 메뉴별 판매량 데이터가 아직 연결되지 않았어요. POS 주문 내역을 연동하면 판매량과 매출액 기준으로 인기 메뉴를 정리할 수 있어요.';
    }
    if (question.contains('함께 주문')) {
      return '아메리카노와 쿠키처럼 함께 주문되는 메뉴 조합을 분석할 수 있어요. 현재는 예시이며, 실제 주문 내역을 연결하면 연관 구매 결과를 계산할 수 있어요.';
    }
    if (question.contains('추가하면')) {
      return '메뉴별 판매량과 원가, 고객 반응을 함께 확인해 새로운 메뉴 도입 여부를 판단해 보세요.';
    }
    if (question.contains('저조한')) {
      return '메뉴별 판매량과 이익률 데이터가 연결되면 판매가 저조한 메뉴를 찾을 수 있어요. 판매량만이 아니라 재료비와 폐기량도 함께 확인하는 것을 추천해요.';
    }
    if (question.contains('재고 확인')) {
      return '현재는 실시간 재고 데이터가 연결되지 않았어요. 재고 수량과 최근 판매 속도를 연결하면 부족 가능성이 높은 품목을 우선 표시할 수 있어요.';
    }
    if (question.contains('원재료')) {
      return '최근 판매량과 예약·날씨 정보를 바탕으로 원재료 준비량을 추천할 수 있어요. 현재는 실제 재고와 판매 데이터가 연결되지 않아 구체적인 수량은 예측하지 않아요.';
    }
    if (question.contains('미리 알')) {
      return '가능해요. 재고 수량, 일평균 사용량, 납품 소요일을 연결하면 재고가 기준치 아래로 내려갈 때 알림을 표시하도록 구현할 수 있어요.';
    }
    if (question.contains('적정 재고')) {
      return '적정 재고는 최근 판매량과 납품 소요일, 안전 재고를 기준으로 계산할 수 있어요. 실제 원재료별 사용량 데이터가 연결되면 품목별로 추천할 수 있어요.';
    }
    if (question.contains('장소')) {
      return '주변 대학, 지하철역, 오피스와 같은 시설의 위치와 유동 인구 관련 데이터를 함께 살펴보면 고객 유입 가능성을 분석할 수 있어요.';
    }
    if (question.contains('상권의 특징')) {
      return '상권 분석에서는 주변 시설, 경쟁 카페 수, 주요 고객층과 시간대별 수요를 함께 살펴보는 것이 좋아요. 실제 위치와 상권 데이터 연결 후 매장에 맞는 분석을 제공할 수 있어요.';
    }
    if (question.contains('경쟁 카페')) {
      return '주변 카페의 위치, 메뉴 가격, 리뷰 키워드와 평점을 비교해 볼 수 있어요. 현재는 상권 데이터가 연결되지 않아 실제 경쟁 매장 분석 결과는 아니에요.';
    }
    return '주변 상권과 메뉴별 판매량, 원가를 함께 확인해 매장에 맞는 운영 방안을 검토해 보세요. 이 화면의 답변은 시연용 예시이며 실제 데이터 분석 결과는 아니에요.';
  }

  @override
  Widget build(BuildContext context) {
    final height = MediaQuery.of(context).size.height;
    return Container(
      height: height * 0.84,
      decoration: const BoxDecoration(
        color: const Color(0xFFF6F9FE),
        borderRadius: BorderRadius.vertical(top: Radius.circular(25)),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        children: [
          const SizedBox(height: 8),
          Container(
            width: 42,
            height: 4,
            decoration: BoxDecoration(
              color: const Color(0xFFCDD5E0),
              borderRadius: BorderRadius.circular(8),
            ),
          ),
          Container(
            padding: const EdgeInsets.fromLTRB(16, 12, 12, 13),
            decoration: const BoxDecoration(
              color: Colors.white,
              border: Border(bottom: BorderSide(color: line)),
            ),
            child: Row(
              children: [
                Container(
                  width: 35,
                  height: 35,
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [Color(0xFF4A96FF), Color(0xFF2676E8)],
                    ),
                    borderRadius: BorderRadius.circular(11),
                  ),
                  child: const Icon(
                    Icons.auto_awesome_rounded,
                    color: Colors.white,
                    size: 20,
                  ),
                ),
                const SizedBox(width: 10),
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'AI 경영비서',
                        style: TextStyle(
                          color: ink,
                          fontSize: 16,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      SizedBox(height: 3),
                      Text(
                        '매장 운영에 필요한 정보를 빠르게 확인해 보세요.',
                        style: TextStyle(color: muted, fontSize: 9),
                      ),
                    ],
                  ),
                ),
                IconButton(
                  onPressed: () => Navigator.pop(context),
                  icon: const Icon(Icons.close_rounded),
                  style: IconButton.styleFrom(
                    backgroundColor: const Color(0xFFF0F3F7),
                    foregroundColor: muted,
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(14, 15, 14, 24),
              child: selectedQuestion == null
                  ? _buildQuestionView()
                  : _buildAnswerView(),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 8, 14, 14),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: questionController,
                    textInputAction: TextInputAction.send,
                    onSubmitted: (_) => _sendQuestion(),
                    decoration: InputDecoration(
                      hintText: 'Ask the AI assistant',
                      filled: true,
                      fillColor: Colors.white,
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 14,
                        vertical: 12,
                      ),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(22),
                        borderSide: const BorderSide(color: line),
                      ),
                      enabledBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(22),
                        borderSide: const BorderSide(color: line),
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton.filled(
                  onPressed: _sendQuestion,
                  icon: const Icon(Icons.send_rounded),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildQuestionView() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _bubble(
          'Hello! Choose a FAQ or type a question about your store.',
          isBot: true,
        ),
        const SizedBox(height: 18),
        FutureBuilder<List<Map<String, dynamic>>>(
          future: faqFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting)
              return const Center(child: CircularProgressIndicator());
            if (snapshot.hasError)
              return Text(
                'FAQ API error: ${snapshot.error}',
                style: const TextStyle(color: muted, fontSize: 12),
              );
            final categories = snapshot.data ?? const [];
            if (selectedCategory == null) {
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Choose a topic',
                    style: TextStyle(
                      color: muted,
                      fontSize: 12,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 10),
                  ...categories.asMap().entries.map((entry) {
                    final category = entry.value;
                    final label = category['category']?.toString() ?? '';
                    const icons = [
                      Icons.bar_chart_rounded,
                      Icons.auto_awesome_rounded,
                      Icons.storefront_outlined,
                      Icons.inventory_2_outlined,
                      Icons.rate_review_outlined,
                      Icons.location_on_outlined,
                    ];
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: SizedBox(
                        width: double.infinity,
                        child: OutlinedButton(
                          onPressed: () =>
                              setState(() => selectedCategory = label),
                          style: OutlinedButton.styleFrom(
                            alignment: Alignment.centerLeft,
                            backgroundColor: Colors.white,
                            foregroundColor: ink,
                            side: const BorderSide(color: Color(0xFFDDE7F5)),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(14),
                            ),
                            padding: const EdgeInsets.symmetric(
                              horizontal: 12,
                              vertical: 15,
                            ),
                          ),
                          child: Row(
                            children: [
                              Icon(
                                icons[entry.key % icons.length],
                                color: blue,
                                size: 19,
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  label,
                                  style: const TextStyle(
                                    fontSize: 11,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                              ),
                              const Icon(
                                Icons.chevron_right_rounded,
                                color: muted,
                                size: 18,
                              ),
                            ],
                          ),
                        ),
                      ),
                    );
                  }),
                ],
              );
            }
            final category = categories
                .where((item) => item['category'] == selectedCategory)
                .firstOrNull;
            final questions =
                (category?['questions'] as List?)?.whereType<Map>().toList() ??
                const <Map>[];
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        selectedCategory!,
                        style: const TextStyle(
                          color: ink,
                          fontSize: 13,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                    TextButton(
                      onPressed: () => setState(() => selectedCategory = null),
                      child: const Text('Change category'),
                    ),
                  ],
                ),
                ...questions.map((item) {
                  final question = item['question']?.toString() ?? '';
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Material(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(13),
                      child: InkWell(
                        onTap: () =>
                            setState(() => selectedQuestion = question),
                        borderRadius: BorderRadius.circular(13),
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 13,
                            vertical: 14,
                          ),
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(13),
                            border: Border.all(color: line),
                          ),
                          child: Row(
                            children: [
                              Expanded(
                                child: Text(
                                  question,
                                  style: const TextStyle(
                                    fontSize: 11,
                                    color: ink,
                                    height: 1.4,
                                  ),
                                ),
                              ),
                              const Icon(
                                Icons.chevron_right_rounded,
                                color: Color(0xFFADB8C8),
                                size: 18,
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  );
                }),
              ],
            );
          },
        ),
      ],
    );
  }

  Widget _buildAnswerView() {
    final question = selectedQuestion!;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _bubble('안녕하세요! 매출, 메뉴, 재고 등 궁금한 내용을 선택해 주세요.', isBot: true),
        const SizedBox(height: 14),
        Align(
          alignment: Alignment.centerRight,
          child: Container(
            constraints: const BoxConstraints(maxWidth: 300),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
            decoration: BoxDecoration(
              color: blue,
              borderRadius: BorderRadius.circular(16)
                  .copyWith(bottomRight: const Radius.circular(5)),
            ),
            child: Text(
              question,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 12,
                height: 1.4,
              ),
            ),
          ),
        ),
        const SizedBox(height: 14),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 25,
              height: 25,
              decoration: BoxDecoration(
                color: blue,
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(
                Icons.auto_awesome_rounded,
                color: Colors.white,
                size: 15,
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: Colors.white,
                  border: Border.all(color: line),
                  borderRadius: BorderRadius.circular(15),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    FutureBuilder<String>(
                      future: _answerFromBackend(question),
                      builder: (context, snapshot) => Text(
                        snapshot.connectionState == ConnectionState.waiting
                            ? 'Loading answer...'
                            : snapshot.hasError
                            ? 'Chatbot API error: ${snapshot.error}'
                            : snapshot.data ?? 'No answer returned.',
                        style: const TextStyle(
                          color: ink,
                          fontSize: 12,
                          height: 1.7,
                        ),
                      ),
                    ),
                    const SizedBox(height: 13),
                    const Divider(height: 1, color: line),
                    const SizedBox(height: 8),
                    InkWell(
                      onTap: () {
                        final destination =
                            selectedCategory == '매출 예측' ||
                                selectedCategory == '이번 달 매출'
                            ? 1
                            : selectedCategory == '메뉴 분석'
                            ? 3
                            : selectedCategory == '재고 관리'
                            ? 4
                            : 2;
                        Navigator.pop(context);
                        widget.onNavigate(destination);
                      },
                      child: const Row(
                        children: [
                          Expanded(
                            child: Text(
                              '관련 분석 확인하기',
                              style: TextStyle(
                                color: blue,
                                fontSize: 11,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                          ),
                          Icon(
                            Icons.arrow_forward_rounded,
                            color: blue,
                            size: 17,
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 18),
        Center(
          child: Wrap(
            spacing: 8,
            children: [
              OutlinedButton(
                onPressed: () => setState(() {
                  selectedQuestion = null;
                }),
                style: OutlinedButton.styleFrom(
                  backgroundColor: Colors.white,
                  side: const BorderSide(color: line),
                  foregroundColor: muted,
                  shape: const StadiumBorder(),
                ),
                child: const Text('다른 질문 보기', style: TextStyle(fontSize: 10)),
              ),
              OutlinedButton(
                onPressed: () => setState(() {
                  selectedQuestion = null;
                  selectedCategory = null;
                }),
                style: OutlinedButton.styleFrom(
                  backgroundColor: Colors.white,
                  side: const BorderSide(color: line),
                  foregroundColor: muted,
                  shape: const StadiumBorder(),
                ),
                child: const Text('처음으로', style: TextStyle(fontSize: 10)),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _bubble(String text, {required bool isBot}) => Align(
    alignment: Alignment.centerLeft,
    child: Container(
      constraints: const BoxConstraints(maxWidth: 310),
      padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border.all(color: line),
        borderRadius: BorderRadius.circular(15)
            .copyWith(bottomLeft: const Radius.circular(5)),
      ),
      child: Text(
        text,
        style: const TextStyle(color: muted, fontSize: 11, height: 1.6),
      ),
    ),
  );
}
