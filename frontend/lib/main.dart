import 'package:flutter/material.dart';

import 'app.dart';
import 'core/network/backend_api.dart';
import 'screens/ai_analysis_screen.dart';
import 'screens/home_screen.dart';
import 'screens/mypage_screen.dart';
import 'screens/notification_screen.dart';
import 'screens/recommendation_screen.dart';
import 'screens/sales_screen.dart';
import 'widgets/chatbot_sheet.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const CafeOnApp());
}

class CafeHome extends StatefulWidget {
  final String token;
  final VoidCallback onLogout;

  const CafeHome({
    super.key,
    required this.token,
    required this.onLogout,
  });

  @override
  State<CafeHome> createState() => _CafeHomeState();
}

class _CafeHomeState extends State<CafeHome> {
  int tab = 0;
  bool showNotifications = false;
  bool notificationsRead = false;
  final Set<int> readNotifications = {};

  bool _storeLoading = true;
  String? _storeError;
  int? _storeId;

  final labels = ['홈', '매출 분석', 'AI 분석', '세트 추천', '마이'];
  final icons = [
    Icons.home_rounded,
    Icons.bar_chart_rounded,
    Icons.auto_awesome_rounded,
    Icons.storefront_rounded,
    Icons.person_outline_rounded,
  ];

  Offset chatbotOffset = const Offset(20, 80);

  @override
  void initState() {
    super.initState();
    _loadStores();
  }

  Future<void> _loadStores() async {
    setState(() {
      _storeLoading = true;
      _storeError = null;
    });

    try {
      final stores = await BackendApi.instance.stores();
      if (!mounted) return;

      if (stores.isEmpty) {
        setState(() {
          _storeId = null;
          _storeLoading = false;
          _storeError = '연결된 매장 정보가 없습니다.';
        });
        return;
      }

      final firstStore = stores.first;
      final parsedId = int.tryParse(firstStore['id'].toString());

      setState(() {
        _storeId = parsedId;
        _storeLoading = false;
        _storeError = null;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _storeLoading = false;
        _storeError = error.toString();
      });
    }
  }

  void _openChatbot() {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => ChatbotSheet(
        onNavigate: (index) {
          setState(() {
            tab = index;
          });
        },
        storeId: _storeId,
      ),
    );
  }

  Widget _buildCurrentTab() {
    switch (tab) {
      case 0:
        return HomeScreen(
          onNavigate: (index) {
            setState(() {
              tab = index;
            });
          },
          storeId: _storeId,
          storeLoading: _storeLoading,
          storeError: _storeError,
        );
      case 1:
        return SalesScreen(
          storeId: _storeId,
          storeLoading: _storeLoading,
          storeError: _storeError,
        );
      case 2:
        return AiAnalysisScreen(
          storeId: _storeId,
          storeLoading: _storeLoading,
          storeError: _storeError,
        );
      case 3:
        return RecommendationScreen(
          storeId: _storeId,
          storeLoading: _storeLoading,
          storeError: _storeError,
        );
      case 4:
      default:
        return MyPageScreen(
          storeId: _storeId,
          storeLoading: _storeLoading,
          storeError: _storeError,
          onStoreChanged: _loadStores,
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
          SafeArea(child: _buildCurrentTab()),
          if (showNotifications)
            NotificationScreen(
              notificationsRead: notificationsRead,
              readNotifications: readNotifications,
              onBack: () {
                setState(() {
                  showNotifications = false;
                });
              },
              onReadAll: () {
                setState(() {
                  notificationsRead = true;
                });
              },
              onRead: (id) {
                setState(() {
                  if (!readNotifications.add(id)) {
                    readNotifications.remove(id);
                  }
                });
              },
            ),
          Positioned(
            right: chatbotOffset.dx,
            bottom: chatbotOffset.dy,
            child: GestureDetector(
              onPanUpdate: (details) {
                setState(() {
                  chatbotOffset = Offset(
                    (chatbotOffset.dx - details.delta.dx).clamp(8.0, 320.0),
                    (chatbotOffset.dy - details.delta.dy).clamp(8.0, 640.0),
                  );
                });
              },
              child: FloatingActionButton(
                onPressed: _openChatbot,
                child: const Icon(Icons.smart_toy_rounded),
              ),
            ),
          ),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: tab,
        onDestinationSelected: (index) {
          setState(() {
            tab = index;
          });
        },
        destinations: List.generate(
          labels.length,
          (index) => NavigationDestination(
            icon: Icon(icons[index]),
            label: labels[index],
          ),
        ),
      ),
    );
  }
}