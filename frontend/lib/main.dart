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
                // 휴대폰 프레임 내부에서 화면을 전환하도록 중첩 Navigator 사용
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
  int _aiAnalysisSection = 0;
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

  Map<String, dynamic>? _inventoryData;
  Map<String, dynamic>? _reorderData;
  bool _isInventoryLoading = false;
  String? _inventoryError;

  Map<String, dynamic>? _setRecommendationData;
  bool _isSetRecommendationLoading = false;
  String? _setRecommendationError;

  String get _salesGranularity {
    if (_salesPeriodIndex == 0) return 'day';
    if (_salesPeriodIndex == 1) return 'week';
    return 'month';
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

      final patternsDebug = results[1];

      debugPrint('===== PATTERNS DEBUG =====');
      debugPrint('PATTERNS KEYS: ${patternsDebug.keys.toList()}');

      final weekdayHourlyDebug = patternsDebug['weekday_hourly'];

      debugPrint('WEEKDAY HOURLY TYPE: ${weekdayHourlyDebug.runtimeType}');
      debugPrint('WEEKDAY HOURLY DATA: $weekdayHourlyDebug');

      if (weekdayHourlyDebug is Map) {
        final hoursDebug = weekdayHourlyDebug['hours'];
        debugPrint('HOURS TYPE: ${hoursDebug.runtimeType}');
        debugPrint(
          'HOURS COUNT: ${hoursDebug is List ? hoursDebug.length : "NOT LIST"}',
        );
        debugPrint('HOURS DATA: $hoursDebug');
      }

      debugPrint('===== END PATTERNS DEBUG =====');

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

  @override
  void initState() {
    super.initState();
    _businessService = BusinessDataService(token: widget.token);
    _loadBusinessData();
  }

  Future<void> _loadInventoryData(int storeId) async {
    if (!mounted) return;

    setState(() {
      _isInventoryLoading = true;
      _inventoryError = null;
    });

    try {
      final results = await Future.wait([
        _businessService.getInventory(storeId),
        _businessService.getReorderRecommendation(storeId),
      ]);

      if (!mounted) return;

      setState(() {
        _inventoryData = results[0];
        _reorderData = results[1];
        _isInventoryLoading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _inventoryError = error.toString();
        _isInventoryLoading = false;
      });
    }
  }

  Future<void> _loadSetRecommendationData(int storeId) async {
    if (!mounted) return;

    setState(() {
      _isSetRecommendationLoading = true;
      _setRecommendationError = null;
    });

    try {
      final result = await _businessService.getSetMenuRecommendation(storeId);

      if (!mounted) return;

      setState(() {
        _setRecommendationData = result;
        _isSetRecommendationLoading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _setRecommendationError = error.toString();
        _isSetRecommendationLoading = false;
      });
    }
  }

  Future<void> _loadBusinessData() async {
    try {
      final stores = await _businessService.getStores();

      if (stores.isEmpty) {
        throw Exception('???? ??? ??? ??? ????.');
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

      _loadInventoryData(storeId);
      _loadSetRecommendationData(storeId);
    } catch (error) {
      if (!mounted) return;

      setState(() {
        _isBusinessLoading = false;
        _businessError = error.toString();
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

      debugPrint('===== FORECAST DEBUG =====');
      debugPrint('result keys: ${result.keys.toList()}');
      debugPrint('forecast as_of: ${result['as_of']}');
      debugPrint('forecast target_dates: ${result['target_dates']}');

      final values = result['values'];
      if (values is List) {
        debugPrint('forecast values count: ${values.length}');
        for (final item in values.take(10)) {
          debugPrint('forecast item: $item');
        }
      } else {
        debugPrint('forecast values is not a List: ${values.runtimeType}');
      }

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

  Future<void> _loadReviewAnalysis() async {
    if (_storeId == null) return;

    setState(() {
      _isReviewLoading = true;
      _reviewError = null;
    });

    try {
      final result = await _businessService.getReviewAnalysis(_storeId!);
      if (!mounted) return;

      setState(() {
        _reviewData = result;
        _isReviewLoading = false;
      });
    } catch (error) {
      if (!mounted) return;

      setState(() {
        _reviewError = error.toString();
        _isReviewLoading = false;
      });
    }
  }

  void _changeTab(int destination) {
    setState(() {
      tab = destination;
    });

    if (destination == 1 && _storeId != null) {
      if (_salesData == null && !_isSalesLoading) {
        _loadSalesData();
      }
      if (!_isForecastLoading) {
        _loadSavedForecast();
      }
    }
    if (destination == 2 &&
        _storeId != null &&
        _reviewData == null &&
        !_isReviewLoading) {
      _loadReviewAnalysis();
    }
  }

  // 챗봇 아이콘 위치 초기값 (오른쪽, 아래쪽 기준)
  Offset chatbotOffset = const Offset(20, 80);

  final labels = ['홈', '매출 분석', 'AI 분석', '재고 및 발주', '마이'];
  final icons = [
    Icons.home_rounded,
    Icons.bar_chart_rounded,
    Icons.auto_awesome_rounded,
    Icons.inventory_2_rounded,
    Icons.person_outline_rounded,
  ];

  void openChatbot() {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      backgroundColor: Colors.transparent,
      barrierColor: const Color(0x990B1728),
      builder: (context) =>
          ChatbotSheet(onNavigate: (destination) => _changeTab(destination)),
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
                // 기본 앱 화면 레이아웃
                Column(
                  children: [
                    const SizedBox(height: 15),
                    header(),
                    Expanded(
                      child: SingleChildScrollView(
                        padding: const EdgeInsets.fromLTRB(18, 4, 18, 28),
                        child: showNotifications
                            ? notificationPage()
                            : (tab == 0 ? home() : otherPage()),
                      ),
                    ),
                    bottomNav(),
                  ],
                ),

                // 드래그 가능한 챗봇 플로팅 버튼
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

  String _formatWon(dynamic value) {
    if (value == null) return '데이터 없음';
    final number = num.tryParse(value.toString());
    if (number == null) return '데이터 없음';
    return '${number.toStringAsFixed(0).replaceAllMapped(RegExp(r'(\d)(?=(\d{3})+(?!\d))'), (match) => '${match[1]},')}원';
  }

  String _formatPercent(dynamic value) {
    if (value == null) return '비교 데이터 없음';
    final number = num.tryParse(value.toString());
    if (number == null) return '비교 데이터 없음';
    final sign = number > 0 ? '+' : '';
    return '$sign${number.toStringAsFixed(1)}%';
  }

  Widget home() {
    final data = _homeData;
    final daily = data?['daily_insights'] is Map
        ? Map<String, dynamic>.from(data!['daily_insights'])
        : <String, dynamic>{};
    final metrics = daily['metrics'] is Map
        ? Map<String, dynamic>.from(daily['metrics'])
        : <String, dynamic>{};

    final reviewRating = metrics['review_average_rating'];
    final reviewCount = metrics['review_count'];
    final forecast = data?['today_predicted_sales'];
    final change = data?['sales_change_percent'];

    final salesChangeForCondition = metrics['sales_change_percent'] is num
        ? (metrics['sales_change_percent'] as num).toDouble()
        : null;
    final reviewForCondition = reviewRating is num
        ? (reviewRating as num).toDouble()
        : null;
    final hasDailySales =
        metrics['sales'] != null && daily['status'] != 'INSUFFICIENT_DATA';

    final conditionBad =
        hasDailySales &&
        (salesChangeForCondition != null && salesChangeForCondition <= -10 ||
            reviewForCondition != null && reviewForCondition <= 2.5);
    final conditionCaution =
        hasDailySales &&
        !conditionBad &&
        (salesChangeForCondition == null ||
            salesChangeForCondition < 0 ||
            reviewForCondition != null && reviewForCondition < 3.5);

    final conditionColor = !hasDailySales
        ? const Color(0xFF718096)
        : conditionBad
        ? const Color(0xFFD94343)
        : conditionCaution
        ? const Color(0xFFE98A22)
        : const Color(0xFF287FF0);

    final conditionTitle = !hasDailySales
        ? '오늘의 가게 컨디션은 진단 불가예요.'
        : conditionBad
        ? '오늘의 가게 컨디션은 나쁨이에요.'
        : conditionCaution
        ? '오늘의 가게 컨디션은 주의예요.'
        : '오늘의 가게 컨디션은 좋음이에요!';

    final conditionDescription = !hasDailySales
        ? '운영 데이터를 더 모으면 진단할 수 있어요.'
        : conditionBad
        ? '매출과 리뷰 등 주요 운영 지표를 점검해 보세요.'
        : conditionCaution
        ? '일부 운영 지표를 확인해 보세요.'
        : '매출과 리뷰 흐름이 양호해요.';

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '안녕하세요, 사장님',
          style: const TextStyle(
            fontSize: 23,
            fontWeight: FontWeight.w800,
            color: ink,
          ),
        ),
        const SizedBox(height: 5),
        Text(
          _storeName ?? '매장 운영 현황을 확인해 보세요',
          style: const TextStyle(fontSize: 13, color: muted),
        ),
        const SizedBox(height: 18),

        if (_isBusinessLoading)
          const Center(
            child: Padding(
              padding: EdgeInsets.all(30),
              child: CircularProgressIndicator(),
            ),
          )
        else if (_businessError != null)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: line),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  '매장 데이터를 불러오지 못했습니다.',
                  style: TextStyle(fontWeight: FontWeight.w700, color: ink),
                ),
                const SizedBox(height: 8),
                Text(
                  _businessError!,
                  style: const TextStyle(fontSize: 12, color: muted),
                ),
                const SizedBox(height: 10),
                TextButton.icon(
                  onPressed: () {
                    setState(() {
                      _isBusinessLoading = true;
                      _businessError = null;
                    });
                    _loadBusinessData();
                  },
                  icon: const Icon(Icons.refresh),
                  label: const Text('다시 불러오기'),
                ),
              ],
            ),
          )
        else ...[
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(22),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  conditionColor,
                  Color.lerp(conditionColor, Colors.black, 0.12)!,
                ],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(24),
              boxShadow: [
                BoxShadow(
                  color: conditionColor.withValues(alpha: 0.20),
                  blurRadius: 18,
                  offset: const Offset(0, 8),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 7,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.22),
                        borderRadius: BorderRadius.circular(30),
                      ),
                      child: const Text(
                        'AI DAILY REPORT',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 11,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                    const Icon(
                      Icons.auto_awesome,
                      color: Colors.white,
                      size: 27,
                    ),
                  ],
                ),
                const SizedBox(height: 22),
                const Text(
                  '오늘의 가게 컨디션은',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  conditionTitle.replaceFirst('오늘의 가게 컨디션은 ', ''),
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 25,
                    height: 1.35,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  conditionDescription,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 13,
                    height: 1.5,
                  ),
                ),
                const SizedBox(height: 18),
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton.icon(
                    onPressed: () {
                      Navigator.of(context).push(
                        MaterialPageRoute<void>(
                          builder: (_) => const ReportScreen(),
                        ),
                      );
                    },
                    icon: const Icon(
                      Icons.arrow_forward,
                      color: Colors.white,
                      size: 18,
                    ),
                    label: const Text(
                      '리포트 확인',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    style: TextButton.styleFrom(
                      backgroundColor: Colors.white.withValues(alpha: 0.22),
                      padding: const EdgeInsets.symmetric(
                        horizontal: 17,
                        vertical: 10,
                      ),
                      shape: const StadiumBorder(),
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 22),
          section('매출 현황', '상세 보기', () => _changeTab(1)),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: metric(
                  '전일 매출',
                  _formatWon(data?['yesterday_sales']),
                  '실제 매출 데이터',
                  Icons.payments_rounded,
                  green,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: metric(
                  '오늘 예상 매출',
                  _formatWon(forecast),
                  forecast == null ? '저장된 예측 없음' : '저장된 예측 결과',
                  Icons.trending_up_rounded,
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
                  '전일 매출 증감률',
                  _formatPercent(change),
                  '전전일 대비',
                  Icons.show_chart_rounded,
                  const Color(0xFFB46C08),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: metric(
                  '리뷰 평균 평점',
                  reviewRating == null ? '데이터 없음' : '${reviewRating}점',
                  '${reviewCount ?? 0}개 · 테스트 리뷰 기준',
                  Icons.star_rounded,
                  blue,
                ),
              ),
            ],
          ),
          const SizedBox(height: 22),
          section('운영 인사이트', null, null),
          const SizedBox(height: 10),
          _insightList('잘된 점', daily['strengths'], green),
          _insightList('주의할 점', daily['cautions'], const Color(0xFFB46C08)),
          _insightList('운영 제안', daily['recommendations'], blue),
        ],
      ],
    );
  }

  Widget _insightList(String title, dynamic items, Color color) {
    final values = items is List
        ? items.map((item) => item.toString()).toList()
        : <String>[];

    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(17),
        border: Border.all(color: line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: TextStyle(
              color: color,
              fontWeight: FontWeight.w800,
              fontSize: 13,
            ),
          ),
          const SizedBox(height: 8),
          if (values.isEmpty)
            const Text(
              '해당 데이터가 없습니다.',
              style: TextStyle(color: muted, fontSize: 12),
            )
          else
            ...values.map(
              (value) => Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Text(
                  '• $value',
                  style: const TextStyle(color: ink, fontSize: 12, height: 1.5),
                ),
              ),
            ),
        ],
      ),
    );
  }

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

  Widget averageBarChart({
    required String title,
    required String subtitle,
    required List<Map<String, dynamic>> items,
    required String labelKey,
    required String valueKey,
    required Color barColor,
    required bool horizontalScroll,
    int labelInterval = 1,
  }) {
    final values = items.map((item) {
      final raw = item[valueKey];
      return raw is num ? raw.toDouble() : 0.0;
    }).toList();

    final maxValue = values.isEmpty
        ? 0.0
        : values.reduce((a, b) => a > b ? a : b);

    final bestIndex = values.isEmpty ? -1 : values.indexOf(maxValue);

    debugPrint('===== AVERAGE BAR CHART DEBUG =====');
    debugPrint('TITLE: $title');
    debugPrint('ITEM COUNT: ${items.length}');
    debugPrint('VALUES: $values');
    debugPrint('MAX VALUE: $maxValue');
    debugPrint('HORIZONTAL SCROLL: $horizontalScroll');
    debugPrint('BEST INDEX: $bestIndex');
    debugPrint('===== END CHART DEBUG =====');

    String compactWon(double value) {
      if (value == 0) return '0원';
      if (value >= 10000) {
        return '${(value / 10000).toStringAsFixed(1)}만';
      }
      if (value >= 1000) {
        return '${(value / 1000).toStringAsFixed(0)}천';
      }
      return '${value.toStringAsFixed(0)}원';
    }

    final bars = Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: List.generate(items.length, (index) {
        final value = values[index];
        final isBest = index == bestIndex && maxValue > 0;
        final ratio = maxValue > 0 ? value / maxValue : 0.0;
        final label = items[index][labelKey]?.toString() ?? '';

        return SizedBox(
          width: horizontalScroll ? 48 : null,
          height: horizontalScroll ? 155 : null,
          child: horizontalScroll
              ? Tooltip(
                  message: '$label\n평균 매출: ${value.toStringAsFixed(0)}원',
                  waitDuration: const Duration(milliseconds: 300),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      SizedBox(
                        height: 18,
                        child: Text(
                          value > 0 ? compactWon(value) : '',
                          style: TextStyle(
                            fontSize: 9,
                            color: isBest ? barColor : muted,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                      const SizedBox(height: 5),
                      Container(
                        width: 22,
                        height: 105 * ratio < 4 && value > 0 ? 4 : 105 * ratio,
                        decoration: BoxDecoration(
                          color: isBest
                              ? barColor
                              : barColor.withValues(alpha: 0.28),
                          borderRadius: const BorderRadius.vertical(
                            top: Radius.circular(5),
                          ),
                        ),
                      ),
                      const SizedBox(height: 7),
                      SizedBox(
                        height: 15,
                        child: Text(
                          index % labelInterval == 0 ? label : '',
                          style: const TextStyle(fontSize: 9, color: muted),
                        ),
                      ),
                    ],
                  ),
                )
              : Column(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    SizedBox(
                      height: 18,
                      child: FittedBox(
                        child: Text(
                          value > 0 ? compactWon(value) : '',
                          style: TextStyle(
                            fontSize: 9,
                            color: isBest ? barColor : muted,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 5),
                    Container(
                      width: 24,
                      height: 105 * ratio < 4 && value > 0 ? 4 : 105 * ratio,
                      decoration: BoxDecoration(
                        color: isBest
                            ? barColor
                            : barColor.withValues(alpha: 0.28),
                        borderRadius: const BorderRadius.vertical(
                          top: Radius.circular(5),
                        ),
                      ),
                    ),
                    const SizedBox(height: 7),
                    Text(
                      label,
                      style: TextStyle(
                        fontSize: 10,
                        color: isBest ? barColor : muted,
                        fontWeight: isBest ? FontWeight.w800 : FontWeight.w500,
                      ),
                    ),
                  ],
                ),
        );
      }),
    );

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(19),
        border: Border.all(color: line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w800,
              color: ink,
            ),
          ),
          const SizedBox(height: 4),
          Text(subtitle, style: const TextStyle(fontSize: 10, color: muted)),
          const SizedBox(height: 18),
          if (items.isEmpty)
            const SizedBox(
              height: 130,
              child: Center(
                child: Text(
                  '분석할 매출 데이터가 없습니다.',
                  style: TextStyle(fontSize: 12, color: muted),
                ),
              ),
            )
          else
            SizedBox(
              height: 155,
              child: horizontalScroll
                  ? SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: bars,
                    )
                  : Row(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: List.generate(items.length, (index) {
                        return Expanded(
                          child: SizedBox(
                            height: 155,
                            child: bars.children[index],
                          ),
                        );
                      }),
                    ),
            ),
        ],
      ),
    );
  }

  Widget chart() {
    return weeklyComparisonChart();
  }

  Widget weeklyComparisonChart() {
    final today = DateUtils.dateOnly(DateTime.now());
    final monday = today.subtract(
      Duration(days: today.weekday - DateTime.monday),
    );

    final dates = List.generate(
      7,
      (index) => monday.add(Duration(days: index)),
    );

    String dateKey(DateTime date) {
      final year = date.year.toString().padLeft(4, '0');
      final month = date.month.toString().padLeft(2, '0');
      final day = date.day.toString().padLeft(2, '0');
      return '$year-$month-$day';
    }

    final actualMap = <String, double>{};
    final rawDailySeries = _dailySalesData?['series'];

    if (rawDailySeries is List) {
      for (final item in rawDailySeries.whereType<Map>()) {
        final data = Map<String, dynamic>.from(item);
        final rawDate = data['period_start']?.toString();
        final date = rawDate == null ? null : DateTime.tryParse(rawDate);

        if (date != null) {
          actualMap[dateKey(date)] = (data['sales'] as num?)?.toDouble() ?? 0;
        }
      }
    }

    final forecastMap = <String, double>{};
    final rawForecastValues = _forecastData?['values'];

    if (rawForecastValues is List) {
      for (final item in rawForecastValues.whereType<Map>()) {
        final data = Map<String, dynamic>.from(item);

        if (data['metric'] != 'SALES' || data['granularity'] != 'DAILY') {
          continue;
        }

        final rawDate = data['target_date']?.toString();
        final date = rawDate == null ? null : DateTime.tryParse(rawDate);

        if (date != null && data['predicted_value'] is num) {
          forecastMap[dateKey(date)] = (data['predicted_value'] as num)
              .toDouble();
        }
      }
    }

    final actualValues = dates.map((date) {
      if (!date.isBefore(today)) return null;
      return actualMap[dateKey(date)];
    }).toList();

    final weeklyActualTotal = actualValues.fold<double>(
      0,
      (total, value) => total + (value ?? 0),
    );

    final forecastValues = dates.map((date) {
      return forecastMap[dateKey(date)];
    }).toList();

    final labels = ['월', '화', '수', '목', '금', '토', '일'];

    final hoveredIndex = _hoveredWeekIndex;
    final hoveredDate = hoveredIndex == null ? null : dates[hoveredIndex];

    String actualDescription(int index) {
      final date = dates[index];

      if (!date.isBefore(today)) return '집계 전';

      final value = actualValues[index];
      return value == null ? '매출 기록 없음' : _formatWon(value);
    }

    String forecastDescription(int index) {
      final value = forecastValues[index];
      return value == null ? '예측 데이터 없음' : _formatWon(value);
    }

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
            '이번 주 매출 합계',
            style: TextStyle(color: muted, fontSize: 12),
          ),
          const SizedBox(height: 5),
          Text(
            _formatWon(weeklyActualTotal),
            style: const TextStyle(
              color: ink,
              fontSize: 23,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              _chartLegend(blue, '실제 매출', dashed: false),
              const SizedBox(width: 18),
              _chartLegend(const Color(0xFFF59E0B), '예측 매출', dashed: true),
            ],
          ),
          const SizedBox(height: 12),
          LayoutBuilder(
            builder: (context, constraints) {
              return MouseRegion(
                onHover: (event) {
                  final index =
                      ((event.localPosition.dx / constraints.maxWidth) * 7)
                          .floor()
                          .clamp(0, 6);

                  if (_hoveredWeekIndex != index) {
                    setState(() {
                      _hoveredWeekIndex = index;
                    });
                  }
                },
                onExit: (_) {
                  setState(() {
                    _hoveredWeekIndex = null;
                  });
                },
                child: SizedBox(
                  height: 170,
                  width: double.infinity,
                  child: CustomPaint(
                    painter: WeeklySalesPainter(
                      actual: actualValues,
                      forecast: forecastValues,
                      todayIndex: today.difference(monday).inDays,
                      hoveredIndex: hoveredIndex ?? -1,
                    ),
                  ),
                ),
              );
            },
          ),
          Row(
            children: List.generate(7, (index) {
              return Expanded(
                child: Text(
                  '${labels[index]}\n${dates[index].month}/${dates[index].day}',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 10,
                    color: hoveredIndex == index ? blue : muted,
                    fontWeight: hoveredIndex == index
                        ? FontWeight.w800
                        : FontWeight.normal,
                  ),
                ),
              );
            }),
          ),
          if (hoveredDate != null) ...[
            const SizedBox(height: 12),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFFF5F8FF),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${hoveredDate.month}월 ${hoveredDate.day}일 (${labels[hoveredIndex!]})',
                    style: const TextStyle(
                      color: ink,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text('실제 매출: ${actualDescription(hoveredIndex)}'),
                  Text('예측 매출: ${forecastDescription(hoveredIndex)}'),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _chartLegend(Color color, String label, {required bool dashed}) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        CustomPaint(
          size: const Size(24, 10),
          painter: LegendLinePainter(color: color, dashed: dashed),
        ),
        const SizedBox(width: 6),
        Text(label, style: const TextStyle(fontSize: 11, color: muted)),
      ],
    );
  }

  Widget otherPage() {
    if (tab == 1) return salesPage();
    if (tab == 2) return aiAnalysisPage();
    if (tab == 3) return inventoryPage();
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

  Widget savedForecastCard() {
    final rawValues = _forecastData?['values'];
    final values = rawValues is List
        ? rawValues
              .whereType<Map>()
              .map((item) => Map<String, dynamic>.from(item))
              .where(
                (item) =>
                    item['metric'] == 'SALES' && item['granularity'] == 'day',
              )
              .toList()
        : <Map<String, dynamic>>[];

    values.sort(
      (a, b) => (a['target_date']?.toString() ?? '').compareTo(
        b['target_date']?.toString() ?? '',
      ),
    );

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(17),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '저장된 7일 매출 예측',
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w800,
              color: ink,
            ),
          ),
          const SizedBox(height: 5),
          const Text(
            '마지막으로 성공적으로 저장된 예측 결과',
            style: TextStyle(fontSize: 11, color: muted),
          ),
          const SizedBox(height: 14),
          if (_isForecastLoading)
            const Center(
              child: Padding(
                padding: EdgeInsets.all(16),
                child: CircularProgressIndicator(),
              ),
            )
          else if (_forecastError != null)
            Text(
              '예측 데이터를 불러오지 못했어요: $_forecastError',
              style: const TextStyle(fontSize: 12, color: muted),
            )
          else if (values.isEmpty)
            const Text(
              '저장된 일별 매출 예측 데이터가 없습니다.',
              style: TextStyle(fontSize: 12, color: muted),
            )
          else
            ...values.map((item) {
              final date = DateTime.tryParse(
                item['target_date']?.toString() ?? '',
              );
              final dateLabel = date == null
                  ? item['target_date']?.toString() ?? '-'
                  : '${date.month}월 ${date.day}일';

              final predicted = item['predicted_value'];
              final lower = item['lower_bound'];
              final upper = item['upper_bound'];
              final hasBounds = lower is num && upper is num;

              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Row(
                  children: [
                    SizedBox(
                      width: 75,
                      child: Text(
                        dateLabel,
                        style: const TextStyle(
                          fontSize: 12,
                          color: muted,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                    Expanded(
                      child: Text(
                        _formatWon(predicted),
                        style: const TextStyle(
                          fontSize: 13,
                          color: ink,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                    if (hasBounds)
                      Text(
                        '${_formatWon(lower)} ~ ${_formatWon(upper)}',
                        style: const TextStyle(fontSize: 10, color: muted),
                      ),
                  ],
                ),
              );
            }),
        ],
      ),
    );
  }

  Widget salesPage() {
    final patterns = _patternsData ?? <String, dynamic>{};

    final weekdayItems = patterns['weekday'] is List
        ? (patterns['weekday'] as List)
              .whereType<Map>()
              .map((item) => Map<String, dynamic>.from(item))
              .where((item) => item['avg_daily_sales'] is num)
              .toList()
        : <Map<String, dynamic>>[];

    final weekdayHourly = patterns['weekday_hourly'] is Map
        ? Map<String, dynamic>.from(patterns['weekday_hourly'])
        : <String, dynamic>{};

    final weekdayHourlyDays = (weekdayHourly['days'] as num?)?.toInt() ?? 0;

    final hourlyItems = weekdayHourly['hours'] is List
        ? (weekdayHourly['hours'] as List)
              .whereType<Map>()
              .map((item) => Map<String, dynamic>.from(item))
              .map(
                (item) => {
                  'hour': item['hour'],
                  'label': '${item['hour']}시',
                  'avg_sales': item['avg_sales'],
                },
              )
              .where(
                (item) =>
                    item['avg_sales'] is num && (item['avg_sales'] as num) > 0,
              )
              .toList()
        : <Map<String, dynamic>>[];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '매출 분석',
          style: TextStyle(
            fontSize: 25,
            fontWeight: FontWeight.w800,
            color: ink,
          ),
        ),
        const SizedBox(height: 5),
        const Text(
          '매장 실적과 변화를 한눈에',
          style: TextStyle(fontSize: 12, color: muted),
        ),
        const SizedBox(height: 18),

        if (_isSalesLoading)
          const Center(
            child: Padding(
              padding: EdgeInsets.all(24),
              child: CircularProgressIndicator(),
            ),
          )
        else if (_salesError != null)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: line),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  '매출 데이터를 불러오지 못했어요.',
                  style: TextStyle(fontWeight: FontWeight.w700, color: ink),
                ),
                const SizedBox(height: 8),
                Text(
                  _salesError!,
                  style: const TextStyle(fontSize: 11, color: muted),
                ),
                const SizedBox(height: 10),
                TextButton(
                  onPressed: _loadSalesData,
                  child: const Text('다시 시도'),
                ),
              ],
            ),
          )
        else if (_salesData == null)
          const Center(child: Text('매출 데이터를 불러오는 중입니다.'))
        else ...[
          chart(),

          const SizedBox(height: 22),

          section('매출 분석 인사이트', null, null),
          const SizedBox(height: 10),

          averageBarChart(
            title: '\uC694\uC77C\uBCC4 \uD3C9\uADE0 \uB9E4\uCD9C',
            subtitle: '\uCD5C\uADFC 30\uC77C \u00B7 \uC694\uC77C\uBCC4 \uD558\uB8E8 \uD3C9\uADE0 \uB9E4\uCD9C',
            items: weekdayItems,
            labelKey: 'weekday_name',
            valueKey: 'avg_daily_sales',
            barColor: green,
            horizontalScroll: false,
          ),

          const SizedBox(height: 12),

          averageBarChart(
            title: '\uC624\uB298\uACFC \uAC19\uC740 \uC694\uC77C\uC758 \uC2DC\uAC04\uB300\uBCC4 \uD3C9\uADE0 \uB9E4\uCD9C',
            subtitle:
                '\uCD5C\uADFC 30\uC77C \uC911 \uAC19\uC740 \uC694\uC77C $weekdayHourlyDays\uC77C \uAE30\uC900',
            items: hourlyItems,
            labelKey: 'label',
            valueKey: 'avg_sales',
            barColor: blue,
            horizontalScroll: true,
            labelInterval: 3,
          ),
        ],
      ],
    );
  }

  Widget aiAnalysisPage() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          margin: const EdgeInsets.only(bottom: 16),
          padding: const EdgeInsets.all(4),
          decoration: BoxDecoration(
            color: const Color(0xFFF4F7FB),
            borderRadius: BorderRadius.circular(14),
          ),
          child: Row(
            children: [
              _aiAnalysisTabButton('AI 리뷰 분석', 0),
              _aiAnalysisTabButton('세트메뉴 추천', 1),
            ],
          ),
        ),
        if (_aiAnalysisSection == 0)
          aiReviewAnalysisContent()
        else
          setRecommendationPage(),
      ],
    );
  }

  Widget _aiAnalysisTabButton(String label, int index) {
    final selected = _aiAnalysisSection == index;

    return Expanded(
      child: GestureDetector(
        onTap: () {
          setState(() {
            _aiAnalysisSection = index;
          });
        },
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 13, horizontal: 6),
          decoration: BoxDecoration(
            color: selected ? Colors.white : Colors.transparent,
            borderRadius: BorderRadius.circular(11),
          ),
          child: Text(
            label,
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w700,
              color: selected ? blue : muted,
            ),
          ),
        ),
      ),
    );
  }

  Widget aiReviewAnalysisContent() {
    final rawMenus = _reviewData?['menus'];
    final menus = rawMenus is List
        ? rawMenus
              .whereType<Map>()
              .map((item) => Map<String, dynamic>.from(item))
              .toList()
        : <Map<String, dynamic>>[];

    final rawCategories = _reviewData?['negative_categories'];
    final categories = rawCategories is List
        ? rawCategories
              .whereType<Map>()
              .map((item) => Map<String, dynamic>.from(item))
              .toList()
        : <Map<String, dynamic>>[];

    final rawSources = _reviewData?['sources'];
    final sources = rawSources is List
        ? rawSources.map((item) => item.toString()).toList()
        : <String>[];

    final totalReviews = menus.fold<int>(
      0,
      (sum, item) => sum + ((item['review_count'] as num?)?.toInt() ?? 0),
    );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'AI 운영 진단',
          style: TextStyle(
            fontSize: 25,
            fontWeight: FontWeight.w800,
            color: ink,
          ),
        ),
        const SizedBox(height: 5),
        const Text(
          '실제 분석 데이터에서 매장 운영의 점검 항목을 찾아요',
          style: TextStyle(fontSize: 12, color: muted),
        ),
        const SizedBox(height: 18),

        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(22),
            border: Border.all(color: line),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                '리뷰 분석 현황',
                style: TextStyle(fontSize: 12, color: muted),
              ),
              const SizedBox(height: 8),
              if (_isReviewLoading)
                const Center(
                  child: Padding(
                    padding: EdgeInsets.all(18),
                    child: CircularProgressIndicator(),
                  ),
                )
              else if (_reviewError != null)
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      '리뷰 분석 데이터를 불러오지 못했어요.',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: ink,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      _reviewError!,
                      style: const TextStyle(fontSize: 11, color: muted),
                    ),
                    const SizedBox(height: 10),
                    TextButton(
                      onPressed: _isReviewLoading ? null : _loadReviewAnalysis,
                      child: const Text('다시 불러오기'),
                    ),
                  ],
                )
              else if (_reviewData == null)
                const Text(
                  '리뷰 분석 데이터를 아직 불러오지 않았어요.',
                  style: TextStyle(fontSize: 13, color: muted),
                )
              else ...[
                Text(
                  menus.isEmpty
                      ? '분석 가능한 메뉴가 없어요.'
                      : '분석 기준을 충족한 메뉴 ${menus.length}개',
                  style: const TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w800,
                    color: ink,
                  ),
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(child: _metricCell('분석 메뉴', '${menus.length}개')),
                    Expanded(child: _metricCell('메뉴별 리뷰 합계', '$totalReviews건')),
                  ],
                ),
                if (sources.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  Text(
                    '데이터 출처: ${sources.join(', ')}',
                    style: const TextStyle(fontSize: 11, color: muted),
                  ),
                ],
              ],
            ],
          ),
        ),

        const SizedBox(height: 22),
        section('메뉴별 고객 반응', null, null),
        const SizedBox(height: 10),

        if (_isReviewLoading)
          const Text(
            '리뷰 데이터를 불러오는 중이에요.',
            style: TextStyle(fontSize: 12, color: muted),
          )
        else if (_reviewError != null)
          const Text(
            '리뷰 데이터를 확인할 수 없어요.',
            style: TextStyle(fontSize: 12, color: muted),
          )
        else if (_reviewData != null && menus.isEmpty)
          const Text(
            '메뉴별 리뷰가 최소 ${3}건 이상 쌓인 데이터가 없어 분석할 수 없습니다.',
            style: TextStyle(fontSize: 12, color: muted),
          )
        else
          ...menus.map((item) {
            final name = item['name']?.toString() ?? '이름 없는 메뉴';
            final count = (item['review_count'] as num?)?.toInt() ?? 0;
            final positive = (item['positive_ratio'] as num?)?.toDouble() ?? 0;
            final negative = (item['negative_ratio'] as num?)?.toDouble() ?? 0;
            final quantity = (item['quantity'] as num?)?.toInt() ?? 0;
            final flag = item['flag']?.toString();

            return Container(
              width: double.infinity,
              margin: const EdgeInsets.only(bottom: 10),
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: line),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          name,
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w800,
                            color: ink,
                          ),
                        ),
                      ),
                      if (flag == 'check_quality')
                        const Text(
                          '품질 점검 후보',
                          style: TextStyle(
                            fontSize: 10,
                            color: Color(0xFFE58A00),
                            fontWeight: FontWeight.w700,
                          ),
                        )
                      else if (flag == 'promote')
                        const Text(
                          '홍보 검토 후보',
                          style: TextStyle(
                            fontSize: 10,
                            color: blue,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  Text(
                    '판매 ${quantity}개 · 리뷰 $count건',
                    style: const TextStyle(fontSize: 11, color: muted),
                  ),
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          '긍정 ${(positive * 100).round()}%',
                          style: const TextStyle(
                            fontSize: 12,
                            color: Color(0xFF29966A),
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                      Expanded(
                        child: Text(
                          '부정 ${(negative * 100).round()}%',
                          style: const TextStyle(
                            fontSize: 12,
                            color: Color(0xFFE36B6B),
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 7),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(6),
                    child: Row(
                      children: [
                        Expanded(
                          flex: (positive * 1000).round().clamp(1, 1000),
                          child: Container(
                            height: 7,
                            color: const Color(0xFF55B88B),
                          ),
                        ),
                        Expanded(
                          flex: (negative * 1000).round().clamp(1, 1000),
                          child: Container(
                            height: 7,
                            color: const Color(0xFFE58A8A),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            );
          }),

        const SizedBox(height: 22),
        section('주요 부정 리뷰 유형', null, null),
        const SizedBox(height: 10),

        if (_isReviewLoading)
          const Text('분석 중이에요.', style: TextStyle(fontSize: 12, color: muted))
        else if (_reviewData == null ||
            _reviewError != null ||
            categories.isEmpty)
          const Text(
            '확인할 부정 리뷰 유형이 없습니다.',
            style: TextStyle(fontSize: 12, color: muted),
          )
        else
          ...categories.map((item) {
            final label =
                item['label']?.toString() ??
                item['category']?.toString() ??
                '기타';
            final count = (item['count'] as num?)?.toInt() ?? 0;

            return Container(
              margin: const EdgeInsets.only(bottom: 8),
              padding: const EdgeInsets.symmetric(horizontal: 15, vertical: 13),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: line),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      label,
                      style: const TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                        color: ink,
                      ),
                    ),
                  ),
                  Text(
                    '$count건',
                    style: const TextStyle(fontSize: 12, color: muted),
                  ),
                ],
              ),
            );
          }),

        if (_reviewData?['notice'] != null) ...[
          const SizedBox(height: 14),
          Text(
            _reviewData!['notice'].toString(),
            style: const TextStyle(fontSize: 11, color: muted, height: 1.5),
          ),
        ],
      ],
    );
  }

  Widget inventoryPage() {
    final inventory = List<dynamic>.from(
      (_inventoryData?['results'] as List?) ?? [],
    );
    final reorder = List<dynamic>.from(
      (_reorderData?['results'] as List?) ?? [],
    );

    int stockPriority(dynamic raw) {
      if (raw is! Map) return 4;
      final status = (raw['stock_status'] ?? raw['status'] ?? '').toString().trim().toLowerCase();
      final expiry = (raw['expiry_status'] ?? '').toString().trim().toLowerCase();
      if (status == 'danger' || status == 'critical' || status.contains('위험') || expiry == 'expired') return 0;
      if (status == 'low' || status == 'warning' || status.contains('부족') || expiry == 'expiring') return 1;
      final days = double.tryParse(raw['days_left']?.toString() ?? '');
      if (days != null && days <= 1) return 0;
      if (days != null && days <= 3) return 1;
      if (status == 'ok' || status == 'normal' || status == '정상') return 2;
      return 3;
    }
    double daysLeft(dynamic raw) {
      if (raw is! Map) return double.infinity;
      return double.tryParse(raw['days_left']?.toString() ?? '') ??
          double.infinity;
    }

    inventory.sort((a, b) {
      final priority = stockPriority(a).compareTo(stockPriority(b));
      if (priority != 0) return priority;
      return daysLeft(a).compareTo(daysLeft(b));
    });

    reorder.sort((a, b) {
      final priority = stockPriority(a).compareTo(stockPriority(b));
      if (priority != 0) return priority;
      return daysLeft(a).compareTo(daysLeft(b));
    });
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: 24),
        const Text(
          '재고 및 발주 관리',
          style: TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.w800,
            color: ink,
          ),
        ),
        const SizedBox(height: 5),
        const Text(
          '재료별 재고와 예상 소진 시점을 확인해요',
          style: TextStyle(fontSize: 12, color: muted),
        ),
        const SizedBox(height: 18),
        if (_isInventoryLoading)
          const Center(
            child: Padding(
              padding: EdgeInsets.all(20),
              child: CircularProgressIndicator(),
            ),
          )
        else if (_inventoryError != null)
          Text(
            '재고 데이터를 불러오지 못했어요: $_inventoryError',
            style: const TextStyle(fontSize: 12, color: muted),
          )
        else if (inventory.isEmpty)
          const Text(
            '등록된 재고 데이터가 없습니다.',
            style: TextStyle(fontSize: 12, color: muted),
          )
        else
          ...inventory.map((raw) {
            final item = Map<String, dynamic>.from(raw as Map);
            final name = item['ingredient_name']?.toString() ?? '재료';
            final quantity = item['quantity']?.toString() ?? '-';
            final unit = item['unit']?.toString() ?? '';
            final days = item['days_left']?.toString() ?? '-';
            final status = (item['stock_status'] ?? item['status'] ?? '').toString().trim().toLowerCase();
            final priority = stockPriority(item);
            final statusLabel = priority == 0
                ? '재고 위험'
                : priority == 1
                    ? '재고 부족'
                    : priority == 2
                        ? '정상'
                        : status.isEmpty
                            ? '상태 확인'
                            : status;
            return Container(
              margin: const EdgeInsets.only(bottom: 9),
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: line),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          name,
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w700,
                            color: ink,
                          ),
                        ),
                        const SizedBox(height: 5),
                        Text(
                          '현재 재고 $quantity$unit',
                          style: const TextStyle(fontSize: 12, color: muted),
                        ),
                      ],
                    ),
                  ),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(
                        statusLabel,
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                          color: priority <= 1 ? Colors.red : blue,
                        ),
                      ),
                      const SizedBox(height: 5),
                      Text(
                        '소진 예상 ${days}일',
                        style: const TextStyle(fontSize: 11, color: muted),
                      ),
                    ],
                  ),
                ],
              ),
            );
          }),
        const SizedBox(height: 22),
        const Text(
          'AI 발주 추천',
          style: TextStyle(
            fontSize: 17,
            fontWeight: FontWeight.w800,
            color: ink,
          ),
        ),
        const SizedBox(height: 5),
        const Text(
          '앞으로 필요한 재료 발주량을 확인해요',
          style: TextStyle(fontSize: 12, color: muted),
        ),
        const SizedBox(height: 12),
        if (_inventoryError != null)
          const Text(
            '발주 추천 데이터를 확인할 수 없습니다.',
            style: TextStyle(fontSize: 12, color: muted),
          )
        else if (reorder.isEmpty)
          const Text(
            '현재 추천할 발주 항목이 없습니다.',
            style: TextStyle(fontSize: 12, color: muted),
          )
        else
          ...reorder.map((raw) {
            final item = Map<String, dynamic>.from(raw as Map);
            final name = item['ingredient_name']?.toString() ?? '재료';
            final amount = item['recommended_order_qty']?.toString() ?? '-';
            final unit = item['unit']?.toString() ?? '';
            final note = item['note']?.toString() ?? '';
            return Container(
              margin: const EdgeInsets.only(bottom: 9),
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: const Color(0xFFF4F7FB),
                borderRadius: BorderRadius.circular(14),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    name,
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                      color: ink,
                    ),
                  ),
                  const SizedBox(height: 5),
                  Text(
                    '추천 발주량 $amount$unit',
                    style: const TextStyle(
                      fontSize: 13,
                      color: blue,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  if (note.isNotEmpty) ...[
                    const SizedBox(height: 4),
                    Text(
                      note,
                      style: const TextStyle(fontSize: 11, color: muted),
                    ),
                  ],
                ],
              ),
            );
          }),
      ],
    );
  }

  Widget _metricCell(String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontSize: 11, color: muted)),
        const SizedBox(height: 5),
        Text(
          value,
          style: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w800,
            color: ink,
          ),
        ),
      ],
    );
  }

  Widget setRecommendationPage() {
    String formatPrice(dynamic raw) {
      final text = (raw ?? '').toString().replaceAll(',', '').trim();
      if (text.isEmpty || text == '-') return '-';
      final number = num.tryParse(text);
      if (number == null) return text;
      return number.toStringAsFixed(0).replaceAllMapped(
        RegExp(r'(\d)(?=(\d{3})+(?!\d))'),
        (match) => '${match[1]},',
      );
    }

    final sets = (_setRecommendationData?['sets'] as List?) ?? [];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '세트메뉴 추천',
          style: TextStyle(
            fontSize: 25,
            fontWeight: FontWeight.w800,
            color: ink,
          ),
        ),
        const SizedBox(height: 5),
        const Text(
          '실제 주문 조합을 분석해 함께 판매하기 좋은 메뉴를 추천해요',
          style: TextStyle(fontSize: 12, color: muted),
        ),
        const SizedBox(height: 18),
        if (_isSetRecommendationLoading)
          const Center(
            child: Padding(
              padding: EdgeInsets.all(24),
              child: CircularProgressIndicator(),
            ),
          )
        else if (_setRecommendationError != null)
          Text(
            '추천 데이터를 불러오지 못했어요: $_setRecommendationError',
            style: const TextStyle(fontSize: 12, color: muted),
          )
        else if (sets.isEmpty)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: line),
            ),
            child: const Text(
              '아직 추천할 세트 조합이 없습니다.\n주문 데이터가 쌓이면 함께 주문된 메뉴를 분석해 추천해 드려요.',
              style: TextStyle(fontSize: 13, color: muted, height: 1.6),
            ),
          )
        else
          ...sets.asMap().entries.map((entry) {
            final index = entry.key;
            final item = Map<String, dynamic>.from(entry.value as Map);
            final menus = (item['menus'] as List?) ?? [];
            final names = menus
                .map((menu) {
                  return menu is Map ? (menu['name']?.toString() ?? '') : '';
                })
                .where((name) => name.isNotEmpty)
                .join(' + ');
            final support = item['support']?.toString() ?? '-';
            final confidence = item['confidence']?.toString() ?? '-';
            final price = formatPrice(item['total_price']);
            final setPrice = formatPrice(item['set_price']);
            final together = item['orders_together']?.toString() ?? '-';

            return Container(
              width: double.infinity,
              margin: const EdgeInsets.only(bottom: 12),
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: line),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '추천 조합 ${index + 1}',
                    style: const TextStyle(
                      fontSize: 11,
                      color: blue,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    names.isEmpty ? '메뉴 정보 없음' : names,
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w800,
                      color: ink,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      _metricCell('함께 주문', '$together건'),
                      _metricCell('연관도', '$support%'),
                      _metricCell('신뢰도', '$confidence%'),
                    ],
                  ),
                  const Divider(height: 22),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        '기존 합계 ${price}원',
                        style: const TextStyle(fontSize: 12, color: muted),
                      ),
                      Text(
                        '세트 제안 ${setPrice}원',
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w800,
                          color: blue,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            );
          }),
      ],
    );
  }

  Widget myPage() => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      const Text(
        '마이',
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
            CircleAvatar(
              backgroundColor: Colors.white,
              child: Text(
                ((widget.user['nickname'] ?? widget.user['username'] ?? '사')
                        .toString()
                        .isNotEmpty)
                    ? (widget.user['nickname'] ?? widget.user['username'])
                          .toString()
                          .substring(0, 1)
                    : '사',
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
                    '${widget.user['nickname'] ?? widget.user['username'] ?? '사장님'} 사장님',
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '아이디: ${widget.user['username'] ?? ''}',
                    style: const TextStyle(color: Colors.white70, fontSize: 11),
                  ),
                ],
              ),
            ),
            const Icon(Icons.chevron_right, color: Colors.white),
          ],
        ),
      ),
      const SizedBox(height: 22),
      section('데이터 연결', null, null),
      const SizedBox(height: 10),
      _settingsTile(Icons.link_rounded, '연결 상태', '4개 중 3개 연결됨'),
      const SizedBox(height: 12),
      InkWell(
        onTap: () async {
          await widget.onLogout();
        },
        borderRadius: BorderRadius.circular(15),
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.all(15),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(15),
            border: Border.all(color: line),
          ),
          child: const Row(
            children: [
              Icon(Icons.logout_rounded, color: Colors.red, size: 20),
              SizedBox(width: 12),
              Text(
                '로그아웃',
                style: TextStyle(
                  color: Colors.red,
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
        ),
      ),
      const SizedBox(height: 20),
      section('매장 관리', null, null),
      const SizedBox(height: 10),
      _settingsTile(Icons.store_outlined, '매장 정보 수정', '주소, 영업시간, 메뉴'),
      _settingsTile(
        Icons.upload_file_rounded,
        '데이터 연결 및 업로드',
        'POS, 리뷰, 재고 데이터',
      ),
      _settingsTile(Icons.notifications_none_rounded, '알림 설정', '매출 및 재고 알림'),
      _settingsTile(Icons.description_outlined, '보고서 설정', '주간 AI 운영 보고서'),
      const SizedBox(height: 20),
      section('서비스', null, null),
      _settingsTile(Icons.help_outline_rounded, '문의하기', '도움이 필요하신가요?'),
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
            onTap: () => _changeTab(i),
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

class ReportScreen extends StatelessWidget {
  const ReportScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: bg,
      body: SafeArea(
        child: Column(
          children: [
            // 상단 노치 영역(30px)을 비워 제목이 노치에 가려지지 않도록 함
            const SizedBox(height: 30),
            SizedBox(
              height: 54,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  const Text(
                    '오늘의 운영 리포트',
                    style: TextStyle(
                      color: ink,
                      fontSize: 19,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: IconButton(
                      onPressed: () => Navigator.of(context).pop(),
                      icon: const Icon(
                        Icons.chevron_left_rounded,
                        color: ink,
                        size: 30,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(18, 18, 18, 28),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      '2026년 11월 1일 일요일',
                      style: TextStyle(color: muted, fontSize: 12),
                    ),
                    const SizedBox(height: 20),
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(22),
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                          colors: [Color(0xFF4A96FF), Color(0xFF2676E8)],
                        ),
                        borderRadius: BorderRadius.circular(24),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                                decoration: BoxDecoration(
                                  color: Colors.white.withValues(alpha: 0.18),
                                  borderRadius: BorderRadius.circular(20),
                                ),
                                child: const Text(
                                  'AI DAILY REPORT',
                                  style: TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w800),
                                ),
                              ),
                              const Text(
                                '\uC11C\uC6B8 \u00B7 \uAC15\uC218\uD655\uB960 0%',
                                style: TextStyle(color: Colors.white70, fontSize: 12, fontWeight: FontWeight.w600),
                              ),
                            ],
                          ),
                          const SizedBox(height: 18),
                          const Text(
                            '\uC624\uB298 \uB0A0\uC528 \u00B7 \uCD5C\uC800 -2\u00B0C / \uCD5C\uACE0 4\u00B0C',
                            style: TextStyle(color: Colors.white70, fontSize: 13, fontWeight: FontWeight.w600),
                          ),
                          const SizedBox(height: 4),
                          const Text(
                            '\uB9D1\uACE0 \uC0B4\uC9DD \uC300\uC300\uD574\uC694! \u2600\uFE0F',
                            style: TextStyle(color: Colors.white, fontSize: 26, fontWeight: FontWeight.w800),
                          ),
                          const SizedBox(height: 18),
                          Container(
                            width: double.infinity,
                            padding: const EdgeInsets.all(14),
                            decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: 0.14),
                              borderRadius: BorderRadius.circular(16),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text(
                                  '\u2728 \uC624\uB298 \uC798 \uB098\uAC08 \uCD94\uCC9C \uBA54\uB274',
                                  style: TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w700),
                                ),
                                const SizedBox(height: 10),
                                Wrap(
                                  spacing: 6,
                                  runSpacing: 6,
                                  children: [
                                    for (final m in ['\u2615 \uB530\uB73B\uD55C \uC544\uBA54\uB9AC\uCE74\uB178', '\uD83E\uDD5B \uCE74\uD398\uB77C\uB5BC', '\uD83C\uDF6F \uBC14\uB2D0\uB77C\uB77C\uB5BC'])
                                      Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                                        decoration: BoxDecoration(
                                          color: Colors.white,
                                          borderRadius: BorderRadius.circular(20),
                                        ),
                                        child: Text(
                                          m,
                                          style: const TextStyle(color: Color(0xFF1E5EC2), fontSize: 12, fontWeight: FontWeight.w700),
                                        ),
                                      ),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 30),
                    const Text(
                      '오늘의 핵심 지표',
                      style: TextStyle(
                        color: ink,
                        fontSize: 20,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 15),
                    const Row(
                      children: [
                        Expanded(
                          child: _ReportMetric(
                            icon: Icons.payments_rounded,
                            label: '오늘 매출',
                            value: '₩428,500',
                            caption: '+12.8%',
                          ),
                        ),
                        SizedBox(width: 10),
                        Expanded(
                          child: _ReportMetric(
                            icon: Icons.shopping_bag_rounded,
                            label: '주문 건수',
                            value: '68건',
                            caption: '+8.2%',
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    const Row(
                      children: [
                        Expanded(
                          child: _ReportMetric(
                            icon: Icons.receipt_long_rounded,
                            label: '평균 주문 금액',
                            value: '₩6,301',
                          ),
                        ),
                        SizedBox(width: 10),
                        Expanded(
                          child: _ReportMetric(
                            icon: Icons.flag_rounded,
                            label: '목표 달성률',
                            value: '71.4%',
                            caption: '목표 ₩600,000',
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 28),
                    const Text(
                      'AI 운영 인사이트',
                      style: TextStyle(
                        color: ink,
                        fontSize: 20,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 12),
                    const _ReportInsight(
                      icon: Icons.wb_sunny_rounded,
                      title: '날씨에 맞는 메뉴를 준비해 보세요',
                      body: '따뜻한 음료 판매 흐름을 확인하고 라떼류 재고를 점검해 보세요.',
                    ),
                    const SizedBox(height: 10),
                    const _ReportInsight(
                      icon: Icons.access_time_rounded,
                      title: '오후 피크타임을 확인해 보세요',
                      body: '주문이 몰리는 시간대의 제조 동선과 인력 배치를 점검해 보세요.',
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ReportMetric extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final String? caption;

  const _ReportMetric({
    required this.icon,
    required this.label,
    required this.value,
    this.caption,
  });

  @override
  Widget build(BuildContext context) => Container(
    constraints: const BoxConstraints(minHeight: 140),
    padding: const EdgeInsets.all(15),
    decoration: BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.circular(19),
      border: Border.all(color: line),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: blue, size: 20),
        const SizedBox(height: 17),
        Text(label, style: const TextStyle(color: muted, fontSize: 11)),
        const SizedBox(height: 7),
        FittedBox(
          fit: BoxFit.scaleDown,
          alignment: Alignment.centerLeft,
          child: Text(
            value,
            style: const TextStyle(
              color: ink,
              fontSize: 21,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
        if (caption != null) ...[
          const SizedBox(height: 7),
          Text(
            caption!,
            style: const TextStyle(
              color: green,
              fontSize: 11,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ],
    ),
  );
}

class _ReportInsight extends StatelessWidget {
  final IconData icon;
  final String title;
  final String body;

  const _ReportInsight({
    required this.icon,
    required this.title,
    required this.body,
  });

  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    padding: const EdgeInsets.all(15),
    decoration: BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.circular(17),
      border: Border.all(color: line),
    ),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: blue, size: 20),
        const SizedBox(width: 11),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(
                  color: ink,
                  fontSize: 12,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 5),
              Text(
                body,
                style: const TextStyle(color: muted, fontSize: 11, height: 1.5),
              ),
            ],
          ),
        ),
      ],
    ),
  );
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

  const ChatbotSheet({super.key, required this.onNavigate});

  @override
  State<ChatbotSheet> createState() => _ChatbotSheetState();
}

class _ChatbotSheetState extends State<ChatbotSheet> {
  String? selectedCategory;
  String? selectedQuestion;
  bool showAllCategories = false;

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
        color: Color(0xFFF6F9FE),
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
        ],
      ),
    );
  }

  Widget _buildQuestionView() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _bubble('안녕하세요! 매출, 메뉴, 재고 등 궁금한 내용을 선택해 주세요.', isBot: true),
        const SizedBox(height: 18),
        if (selectedCategory == null) ...[
          const Text(
            '무엇이 궁금하세요?',
            style: TextStyle(
              color: muted,
              fontSize: 12,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 10),
          Column(
            children: categories.entries.map((entry) {
              return Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: SizedBox(
                  width: double.infinity,
                  child: OutlinedButton(
                    onPressed: () =>
                        setState(() => selectedCategory = entry.key),
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
                        Icon(entry.value, color: blue, size: 19),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            entry.key,
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
            }).toList(),
          ),
        ] else ...[
          Row(
            children: [
              const Text(
                '자주 묻는 질문',
                style: TextStyle(
                  color: ink,
                  fontSize: 13,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const Spacer(),
              TextButton(
                onPressed: () => setState(() => selectedCategory = null),
                child: const Text('카테고리 변경', style: TextStyle(fontSize: 10)),
              ),
            ],
          ),
          const SizedBox(height: 5),
          ...questions[selectedCategory]!.map(
            (question) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Material(
                color: Colors.white,
                borderRadius: BorderRadius.circular(13),
                child: InkWell(
                  onTap: () => setState(() => selectedQuestion = question),
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
            ),
          ),
        ],
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
                    Text(
                      answerFor(question),
                      style: const TextStyle(
                        color: ink,
                        fontSize: 12,
                        height: 1.7,
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
                            ? 2
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

class LegendLinePainter extends CustomPainter {
  final Color color;
  final bool dashed;

  LegendLinePainter({required this.color, required this.dashed});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 2.5
      ..strokeCap = StrokeCap.round;

    if (dashed) {
      const dashWidth = 4.0;
      const gap = 3.0;
      double x = 0;

      while (x < size.width) {
        canvas.drawLine(
          Offset(x, size.height / 2),
          Offset((x + dashWidth).clamp(0.0, size.width), size.height / 2),
          paint,
        );
        x += dashWidth + gap;
      }
    } else {
      canvas.drawLine(
        Offset(0, size.height / 2),
        Offset(size.width, size.height / 2),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant LegendLinePainter oldDelegate) {
    return oldDelegate.color != color || oldDelegate.dashed != dashed;
  }
}

class WeeklySalesPainter extends CustomPainter {
  final List<double?> actual;
  final List<double?> forecast;
  final int todayIndex;
  final int hoveredIndex;

  WeeklySalesPainter({
    required this.actual,
    required this.forecast,
    required this.todayIndex,
    required this.hoveredIndex,
  });

  @override
  void paint(Canvas canvas, Size size) {
    const actualColor = Color(0xFF3978D5);
    const forecastColor = Color(0xFFF59E0B);

    const left = 8.0;
    const right = 8.0;
    const top = 12.0;
    const bottom = 12.0;

    final chartWidth = size.width - left - right;
    final chartHeight = size.height - top - bottom;

    if (chartWidth <= 0 || chartHeight <= 0) return;

    final allValues = [
      ...actual.whereType<double>(),
      ...forecast.whereType<double>(),
    ];

    final maxValue = allValues.isEmpty
        ? 1.0
        : allValues.reduce((a, b) => a > b ? a : b);

    final scaleMax = maxValue <= 0 ? 1.0 : maxValue * 1.15;

    Offset pointAt(int index, double value) {
      final x = left + chartWidth * index / 6;
      final y = top + chartHeight * (1 - value / scaleMax);
      return Offset(x, y);
    }

    final gridPaint = Paint()
      ..color = const Color(0xFFEAEFF5)
      ..strokeWidth = 1;

    for (var i = 0; i < 4; i++) {
      final y = top + chartHeight * i / 3;
      canvas.drawLine(
        Offset(left, y),
        Offset(size.width - right, y),
        gridPaint,
      );
    }

    if (hoveredIndex >= 0 && hoveredIndex < 7) {
      final x = left + chartWidth * hoveredIndex / 6;

      final hoverPaint = Paint()
        ..color = const Color(0xFFB8C8DC)
        ..strokeWidth = 1;

      canvas.drawLine(
        Offset(x, top),
        Offset(x, size.height - bottom),
        hoverPaint,
      );
    }

    void drawSeries(List<double?> values, Color color, {required bool dashed}) {
      final linePaint = Paint()
        ..color = color
        ..strokeWidth = 2.5
        ..strokeCap = StrokeCap.round
        ..style = PaintingStyle.stroke;

      for (var i = 0; i < values.length - 1; i++) {
        final startValue = values[i];
        final endValue = values[i + 1];

        if (startValue == null || endValue == null) continue;

        final start = pointAt(i, startValue);
        final end = pointAt(i + 1, endValue);

        if (!dashed) {
          canvas.drawLine(start, end, linePaint);
        } else {
          final distance = (end - start).distance;
          const dashLength = 6.0;
          const gapLength = 4.0;

          var position = 0.0;

          while (position < distance) {
            final next = (position + dashLength).clamp(0.0, distance);

            final from = Offset(
              start.dx + (end.dx - start.dx) * position / distance,
              start.dy + (end.dy - start.dy) * position / distance,
            );

            final to = Offset(
              start.dx + (end.dx - start.dx) * next / distance,
              start.dy + (end.dy - start.dy) * next / distance,
            );

            canvas.drawLine(from, to, linePaint);
            position += dashLength + gapLength;
          }
        }
      }

      final dotPaint = Paint()
        ..color = color
        ..style = PaintingStyle.fill;

      for (var i = 0; i < values.length; i++) {
        final value = values[i];
        if (value == null) continue;

        canvas.drawCircle(pointAt(i, value), 3.5, dotPaint);
      }
    }

    drawSeries(forecast, forecastColor, dashed: true);

    drawSeries(actual, actualColor, dashed: false);
  }

  @override
  bool shouldRepaint(covariant WeeklySalesPainter oldDelegate) {
    return oldDelegate.actual != actual ||
        oldDelegate.forecast != forecast ||
        oldDelegate.todayIndex != todayIndex ||
        oldDelegate.hoveredIndex != hoveredIndex;
  }
}
