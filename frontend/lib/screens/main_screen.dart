import 'package:flutter/material.dart';

import '../app.dart' show blue, ink, muted, line, bg;
import '../core/network/backend_api.dart';
import '../widgets/chatbot_sheet.dart';
import 'home_screen.dart';
import 'sales_screen.dart';
import 'ai_analysis_screen.dart';
import 'recommendation_screen.dart';
import 'mypage_screen.dart';
import 'notification_screen.dart';

class MainScreen extends StatefulWidget {
  const MainScreen({super.key});

  @override
  State<MainScreen> createState() => _MainScreenState();
}

class _MainScreenState extends State<MainScreen> {
  int tab = 0;
  bool showNotifications = false;
  bool notificationsRead = false;
  final Set<int> readNotifications = {};

  int? storeId;
  bool storeLoading = true;
  String? storeError;

  Offset chatbotOffset = const Offset(20, 80);

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
    loadStores();
  }

  Future<void> loadStores() async {
    try {
      final stores = await BackendApi.instance.stores();

      if (!mounted) return;

      if (stores.isEmpty) {
        setState(() {
          storeId = null;
          storeLoading = false;
          storeError = null;
        });
        return;
      }

      final firstStoreId = int.tryParse(stores.first['id'].toString());

      if (firstStoreId == null) {
        throw const BackendException('매장 정보를 확인할 수 없습니다.');
      }

      setState(() {
        storeId = firstStoreId;
        storeLoading = false;
        storeError = null;
      });
    } catch (e) {
      if (!mounted) return;

      setState(() {
        storeId = null;
        storeLoading = false;
        storeError = e is BackendException ? e.message : '매장 정보를 불러오지 못했습니다.';
      });
    }
  }

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
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: bg,
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            return Stack(
              children: [
                Column(
                  children: [
                    const SizedBox(height: 15),
                    header(),
                    Expanded(
                      child: SingleChildScrollView(
                        padding: const EdgeInsets.fromLTRB(18, 4, 18, 28),
                        child: showNotifications
                            ? NotificationScreen(
                                notificationsRead: notificationsRead,
                                readNotifications: readNotifications,
                                onBack: () =>
                                    setState(() => showNotifications = false),
                                onReadAll: () =>
                                    setState(() => notificationsRead = true),
                                onRead: (index) => setState(
                                  () => readNotifications.add(index),
                                ),
                              )
                            : (tab == 0
                                  ? HomeScreen(
                                      onNavigate: (destination) =>
                                          setState(() => tab = destination),
                                      storeId: storeId,
                                      storeLoading: storeLoading,
                                      storeError: storeError,
                                    )
                                  : otherPage()),
                      ),
                    ),
                    bottomNav(),
                  ],
                ),

                Positioned(
                  right: chatbotOffset.dx,
                  bottom: chatbotOffset.dy,
                  child: GestureDetector(
                    onPanUpdate: (details) {
                      setState(() {
                        chatbotOffset = Offset(
                          (chatbotOffset.dx - details.delta.dx).clamp(
                            10.0,
                            constraints.maxWidth - 70.0,
                          ),
                          (chatbotOffset.dy - details.delta.dy).clamp(
                            10.0,
                            constraints.maxHeight - 140.0,
                          ),
                        );
                      });
                    },
                    child: FloatingActionButton(
                      onPressed: openChatbot,
                      backgroundColor: blue,
                      foregroundColor: Colors.white,
                      elevation: 5,
                      shape: const CircleBorder(),
                      child: const Icon(
                        Icons.chat_bubble_outline_rounded,
                        size: 25,
                      ),
                    ),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  Widget header() => Padding(
    padding: const EdgeInsets.fromLTRB(20, 10, 20, 12),
    child: Row(
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(14),
          child: Image.asset(
            'assets/icon.png',
            width: 50,
            height: 50,
            fit: BoxFit.cover,
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
        const SizedBox(width: 6),
        const CircleAvatar(
          backgroundColor: Color(0xFFE3EEFF),
          child: Icon(Icons.person_rounded, color: blue),
        ),
      ],
    ),
  );

  Widget otherPage() {
    if (tab == 1) {
      return SalesScreen(
        storeId: storeId,
        storeLoading: storeLoading,
        storeError: storeError,
      );
    }
    if (tab == 2) {
      return AiAnalysisScreen(
        storeId: storeId,
        storeLoading: storeLoading,
        storeError: storeError,
      );
    }
    if (tab == 3) {
      return RecommendationScreen(
        storeId: storeId,
        storeLoading: storeLoading,
        storeError: storeError,
      );
    }
    return MyPageScreen(
      storeId: storeId,
      storeLoading: storeLoading,
      storeError: storeError,
      onStoreChanged: loadStores,
    );
  }

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
}
