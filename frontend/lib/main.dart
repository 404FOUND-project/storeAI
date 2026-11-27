import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'core/network/auth_service.dart';
import 'core/network/business_data_service.dart';
import 'features/auth/login_screen.dart';

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
  Map<String, dynamic>? _user;
  String? _token;
  bool _isCheckingLogin = true;

  @override
  void initState() {
    super.initState();
    _checkLogin();
  }

  // 앱 실행 시 저장된 토큰 확인
  Future<void> _checkLogin() async {
    final prefs = await SharedPreferences.getInstance();
    final savedToken = prefs.getString('auth_token');

    if (savedToken != null) {
      try {
        final user = await AuthService().getMe(savedToken);

        if (!mounted) return;

        setState(() {
          _token = savedToken;
          _user = user;
        });
      } catch (_) {
        await prefs.remove('auth_token');
      }
    }

    if (!mounted) return;

    setState(() {
      _isCheckingLogin = false;
    });
  }

  // 로그인 성공 처리
  Future<void> _handleLoginSuccess(Map<String, dynamic> result) async {
    final token = result['token'];
    final user = result['user'];

    if (token is! String || user is! Map) {
      throw Exception('로그인 응답 형식이 올바르지 않습니다.');
    }

    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('auth_token', token);

    if (!mounted) return;

    setState(() {
      _token = token;
      _user = Map<String, dynamic>.from(user);
    });
  }

  // 로그아웃 처리
  Future<void> _handleLogout() async {
    final token = _token;

    if (token != null) {
      try {
        await AuthService().logout(token);
      } catch (_) {
        // 서버 연결에 실패해도 앱에서는 로그아웃 처리
      }
    }

    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('auth_token');

    if (!mounted) return;

    setState(() {
      _user = null;
      _token = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '카페온',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xFF1E232A),
        colorScheme: ColorScheme.fromSeed(seedColor: blue),
      ),
      home: _isCheckingLogin
          ? const Scaffold(body: Center(child: CircularProgressIndicator()))
          : _user == null || _token == null
          ? LoginPhoneFrameScreen(
              child: LoginScreen(onLoginSuccess: _handleLoginSuccess),
            )
          : PhoneFrameScreen(
              user: _user!,
              token: _token!,
              onLogout: _handleLogout,
            ),
    );
  }
}

class PhoneFrameScreen extends StatelessWidget {
  final Map<String, dynamic> user;
  final String token;
  final Future<void> Function() onLogout;

  const PhoneFrameScreen({
    super.key,
    required this.user,
    required this.token,
    required this.onLogout,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF181C24),
      body: Center(
        child: Container(
          width: 390,
          height: 800,
          decoration: BoxDecoration(
            color: Colors.black,
            borderRadius: BorderRadius.circular(40),
            border: Border.all(color: const Color(0xFF3A4252), width: 10),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.5),
                blurRadius: 30,
                offset: const Offset(0, 10),
              ),
            ],
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(30),
            child: Stack(
              children: [
                Navigator(
                  onGenerateRoute: (settings) => MaterialPageRoute<void>(
                    settings: settings,
                    builder: (_) =>
                        CafeHome(user: user, token: token, onLogout: onLogout),
                  ),
                ),
                Positioned(
                  top: 0,
                  left: 0,
                  right: 0,
                  height: 30,
                  child: IgnorePointer(
                    child: Center(
                      child: Container(
                        width: 110,
                        height: 22,
                        decoration: const BoxDecoration(
                          color: Colors.black,
                          borderRadius: BorderRadius.vertical(
                            bottom: Radius.circular(14),
                          ),
                        ),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Container(
                              width: 10,
                              height: 10,
                              decoration: const BoxDecoration(
                                color: Color(0xFF111418),
                                shape: BoxShape.circle,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class LoginPhoneFrameScreen extends StatelessWidget {
  final Widget child;

  const LoginPhoneFrameScreen({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF181C24),
      body: Center(
        child: Container(
          width: 390,
          height: 800,
          decoration: BoxDecoration(
            color: Colors.black,
            borderRadius: BorderRadius.circular(40),
            border: Border.all(color: const Color(0xFF3A4252), width: 10),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.5),
                blurRadius: 30,
                offset: const Offset(0, 10),
              ),
            ],
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(30),
            child: Stack(
              children: [
                Positioned.fill(child: child),
                Positioned(
                  top: 0,
                  left: 0,
                  right: 0,
                  height: 30,
                  child: IgnorePointer(
                    child: Center(
                      child: Container(
                        width: 110,
                        height: 22,
                        decoration: const BoxDecoration(
                          color: Colors.black,
                          borderRadius: BorderRadius.vertical(
                            bottom: Radius.circular(14),
                          ),
                        ),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Container(
                              width: 10,
                              height: 10,
                              decoration: const BoxDecoration(
                                color: Color(0xFF111418),
                                shape: BoxShape.circle,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class CafeHome extends StatefulWidget {
  final Map<String, dynamic> user;
  final String token;
  final Future<void> Function() onLogout;

  const CafeHome({
    super.key,
    required this.user,
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

  // 챗봇 아이콘 위치 초기값 (오른쪽, 아래쪽 기준)
  Offset chatbotOffset = const Offset(20, 80);

  @override
  void initState() {
    super.initState();
    _businessService = BusinessDataService(token: widget.token);
    _loadBusinessData();
  }

  Future<void> _loadBusinessData() async {
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
        _businessService.getSales(_storeId!, granularity: 'day'),
        _businessService.getPatterns(_storeId!),
      ]);

      if (!mounted) return;

      setState(() {
        _salesData = results[0];
        _dailySalesData = results[0];
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