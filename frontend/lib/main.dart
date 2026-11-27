import 'package:flutter/material.dart';

import 'app.dart';
import 'core/network/business_data_service.dart';
import 'screens/ai_analysis_screen.dart';
import 'screens/home_screen.dart';
import 'screens/mypage_screen.dart';
import 'screens/notification_screen.dart';
import 'screens/recommendation_screen.dart';
import 'screens/sales_screen.dart';
import 'widgets/chatbot_sheet.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const StoreAiApp());
}

class StoreAiApp extends StatelessWidget {
  const StoreAiApp({super.key});

  @override
  Widget build(BuildContext context) {
    return const AppRoot();
  }
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

  late final BusinessDataService _businessService;
  bool _isBusinessLoading = true;
  String? _businessError;
  int? _storeId;
  String? _storeName;
  Map<String, dynamic>? _homeData;

  int _salesPeriodIndex = 1;
  bool _isSalesLoading = false;
  String? _salesError;
  Map<String, dynamic>? _salesData;
  Map<String, dynamic>? _patternsData;
  Map<String, dynamic>? _dailySalesData;
  int? _hoveredWeekIndex;
  Map<String, dynamic>? _forecastData;
  bool _isForecastLoading = false;
  String? _forecastError;
  Map<String, dynamic>? _reviewData;
  bool _isReviewLoading = false;
  String? _reviewError;

  String get _salesGranularity {
    if (_salesPeriodIndex == 0) return 'day';
    if (_salesPeriodIndex == 1) return 'week';
    return 'month';
  }

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
    _businessService = BusinessDataService(token: widget.token);
    _loadBusinessData();
  }

  Future<void> _loadBusinessData() async {
    setState(() {
      _isBusinessLoading = true;
      _businessError = null;
    });

    try {
      final stores = await _businessService.getStores();

      if (stores.isEmpty) {
        throw Exception('연결된 매장 정보가 없습니다.');
      }

      final store = stores.first;
      final storeId = int.parse(store['id'].toString());
      final homeData = await _businessService.getHome(storeId);

      if (!mounted) return;

      setState(() {
        _storeId = storeId;
        _storeName = store['name']?.toString();
        _homeData = homeData;
        _isBusinessLoading = false;
        _businessError = null;
      });

      await Future.wait([
        _loadSalesData(),
        _loadSavedForecast(),
      ]);
    } catch (error) {
      if (!mounted) return;

      setState(() {
        _isBusinessLoading = false;
        _businessError = error.toString();
      });
    }
  }

  Future<void> _loadSalesData() async {
    if (_storeId == null) return;

    setState(() {
      _isSalesLoading = true;
      _salesError = null;
    });

    try {
      final results = await Future.wait([
        _businessService.getSales(_storeId!, granularity: _salesGranularity),
        _businessService.getPatterns(_storeId!),
      ]);

      if (!mounted) return;

      setState(() {
        _salesData = results[0];
        if (_salesGranularity == 'day') {
          _dailySalesData = results[0];
        }
        _patternsData = results[1];
        _hoveredWeekIndex = null;
        _isSalesLoading = false;
      });
    } catch (error) {
      if (!mounted) return;

      setState(() {
        _salesError = error.toString();
        _isSalesLoading = false;
      });
    }
  }

  Future<void> _loadSavedForecast() async {
    if (_storeId == null) return;

    setState(() {
      _isForecastLoading = true;
      _forecastError = null;
    });

    try {
      final result = await _businessService.getSavedForecast(_storeId!);
      if (!mounted) return;

      setState(() {
        _forecastData = result;
        _isForecastLoading = false;
      });
    } catch (error) {
      if (!mounted) return;

      setState(() {
        _forecastError = error.toString();
        _isForecastLoading = false;
      });
    }
  }

  void _openChatbot() {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => ChatbotSheet(
        token: widget.token,
        storeId: _storeId,
      ),
    );
  }

  Widget _buildCurrentTab() {
    if (_isBusinessLoading && _homeData == null) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_businessError != null && _homeData == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                _businessError!,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _loadBusinessData,
                child: const Text('다시 시도'),
              ),
            ],
          ),
        ),
      );
    }

    switch (tab) {
      case 0:
        return HomeScreen(
          storeId: _storeId,
          storeName: _storeName,
          homeData: _homeData,
          onRefresh: _loadBusinessData,
        );
      case 1:
        return SalesScreen(
          storeId: _storeId,
          periodIndex: _salesPeriodIndex,
          isLoading: _isSalesLoading,
          error: _salesError,
          salesData: _salesData,
          patternsData: _patternsData,
          dailySalesData: _dailySalesData,
          hoveredWeekIndex: _hoveredWeekIndex,
          onPeriodChanged: (index) {
            setState(() {
              _salesPeriodIndex = index;
            });
            _loadSalesData();
          },
          onHoverWeek: (index) {
            setState(() {
              _hoveredWeekIndex = index;
            });
          },
        );
      case 2:
        return AiAnalysisScreen(
          storeId: _storeId,
          forecastData: _forecastData,
          isForecastLoading: _isForecastLoading,
          forecastError: _forecastError,
          reviewData: _reviewData,
          isReviewLoading: _isReviewLoading,
          reviewError: _reviewError,
          onRefreshForecast: _loadSavedForecast,
        );
      case 3:
        return RecommendationScreen(
          storeId: _storeId,
        );
      case 4:
      default:
        return MyPageScreen(
          token: widget.token,
          storeId: _storeId,
          storeName: _storeName,
          onLogout: widget.onLogout,
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
              readIds: readNotifications,
              allRead: notificationsRead,
              onMarkAllRead: () {
                setState(() {
                  notificationsRead = true;
                });
              },
              onToggleRead: (id) {
                setState(() {
                  if (!readNotifications.add(id)) {
                    readNotifications.remove(id);
                  }
                });
              },
              onClose: () {
                setState(() {
                  showNotifications = false;
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