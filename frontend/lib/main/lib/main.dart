import 'package:flutter/material.dart';

void main() => runApp(const CafeOnApp());

const blue = Color(0xFF3182F6);
const ink = Color(0xFF1B2B45);
const muted = Color(0xFF697386);
const line = Color(0xFFE8EBF0);
const bg = Color(0xFFF4F7FB);
const green = Color(0xFF15956F);

class CafeOnApp extends StatelessWidget {
  const CafeOnApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: '카페온',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          useMaterial3: true,
          scaffoldBackgroundColor: const Color(0xFF1E232A),
          colorScheme: ColorScheme.fromSeed(seedColor: blue),
        ),
        home: const PhoneFrameScreen(),
      );
}

class PhoneFrameScreen extends StatelessWidget {
  const PhoneFrameScreen({super.key});

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
                const CafeHome(),
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
  const CafeHome({super.key});

  @override
  State<CafeHome> createState() => _CafeHomeState();
}

class _CafeHomeState extends State<CafeHome> {
  int tab = 0;
  bool showNotifications = false;
  bool notificationsRead = false;
  final Set<int> readNotifications = {};
  
  // 챗봇 아이콘 위치 초기값 (오른쪽, 아래쪽 기준)
  Offset chatbotOffset = const Offset(20, 80);

  final labels = ['홈', '매출 분석', 'AI 분석', '세트 추천', '마이'];
  final icons = [
    Icons.home_rounded,
    Icons.bar_chart_rounded,
    Icons.auto_awesome_rounded,
    Icons.storefront_rounded,
    Icons.person_outline_rounded,
  ];

  void openChatbot() {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      backgroundColor: Colors.transparent,
      barrierColor: const Color(0x990B1728),
      builder: (context) => ChatbotSheet(
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
                          (chatbotOffset.dx - details.delta.dx)
                              .clamp(10.0, constraints.maxWidth - 70.0),
                          (chatbotOffset.dy - details.delta.dy)
                              .clamp(10.0, constraints.maxHeight - 140.0),
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
                width: 42,
                height: 42,
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
              icon: const Icon(
                Icons.notifications_none_rounded,
                color: ink,
              ),
              style: IconButton.styleFrom(
                backgroundColor: Colors.white,
              ),
            ),
            const SizedBox(width: 6),
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
          const Text('안녕하세요, 사장님 👋',
              style: TextStyle(
                  fontSize: 23, fontWeight: FontWeight.w800, color: ink)),
          const SizedBox(height: 5),
          const Text('오늘 가게 운영 현황을 확인해 보세요.',
              style: TextStyle(fontSize: 13, color: muted)),
          const SizedBox(height: 18),
          hero(),
          const SizedBox(height: 20),
          section('오늘의 매출', '상세 보기', () => setState(() => tab = 1)),
          const SizedBox(height: 10),
          Row(children: [
            Expanded(
                child: metric('오늘 매출', '₩428,500', '+12.8%',
                    Icons.payments_rounded, green)),
            const SizedBox(width: 10),
            Expanded(
                child: metric('주문 건수', '68건', '+8.2%',
                    Icons.shopping_bag_rounded, blue)),
          ]),
          const SizedBox(height: 10),
          Row(children: [
            Expanded(
                child: metric('평균 주문 금액', '₩6,301', '+3.4%',
                    Icons.receipt_long_rounded, const Color(0xFFB46C08))),
            const SizedBox(width: 10),
            Expanded(
                child: metric('목표 달성률', '71.4%', '목표 ₩600,000',
                    Icons.flag_rounded, blue)),
          ]),
          const SizedBox(height: 22),
          section('AI 운영 인사이트', '모두 보기',
              () => message('AI 운영 인사이트 목록을 준비 중이에요.')),
          const SizedBox(height: 10),
          insight(Icons.wb_sunny_rounded, const Color(0xFFB46C08),
              const Color(0xFFFFF6E5), '날씨에 맞는 메뉴를 준비해 보세요',
              '오늘은 따뜻한 음료 판매가 늘어날 수 있어요. 라떼류 재고를 확인해 보세요.',
              '날씨 분석'),
          const SizedBox(height: 10),
          insight(Icons.auto_awesome_rounded, blue,
              const Color(0xFFEEF6FF), '오후 2–4시 매출이 늘었어요',
              '최근 같은 시간대보다 매출이 12% 높아요. 주문 동선을 점검해 보세요.',
              'AI 인사이트'),
          const SizedBox(height: 20),
          section('매출 흐름', '주간 리포트', () => setState(() => tab = 1)),
          const SizedBox(height: 10),
          chart(),
          const SizedBox(height: 20),
          section('매장 상태', '종합 운영 진단 보기', () => setState(() => tab = 2)),
          const SizedBox(height: 10),
          Container(padding: const EdgeInsets.all(15), decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(18), border: Border.all(color: line)), child: const Column(children: [
            _StatusRow(label: '매출 흐름', value: '안정적이에요', color: green),
            Divider(height: 18, color: line),
            _StatusRow(label: '리뷰 만족도', value: '4.6 · 좋은 편', color: blue),
            Divider(height: 18, color: line),
            _StatusRow(label: '재고', value: '2개 품목 확인 필요', color: Color(0xFFB46C08)),
            Divider(height: 18, color: line),
            _StatusRow(label: '운영 진단', value: '주의 깊게 관찰', color: Color(0xFFB46C08)),
          ])),
        ],
      );

  Widget hero() => Container(
        width: double.infinity,
        padding: const EdgeInsets.all(21),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [Color(0xFF4A96FF), Color(0xFF2676E8)]),
          borderRadius: BorderRadius.circular(25),
          boxShadow: [
            BoxShadow(
                color: blue.withValues(alpha: 0.18),
                blurRadius: 20,
                offset: const Offset(0, 8))
          ],
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(30)),
              child: const Text('AI DAILY REPORT',
                  style: TextStyle(
                      color: Colors.white,
                      fontSize: 10,
                      fontWeight: FontWeight.w700)),
            ),
            const Spacer(),
            const Icon(Icons.auto_awesome_rounded,
                color: Colors.white, size: 25),
          ]),
          const SizedBox(height: 15),
          const Text('오늘의 가게 컨디션은',
              style: TextStyle(color: Colors.white, fontSize: 15)),
          const SizedBox(height: 3),
          const Text('좋음이에요!',
              style: TextStyle(
                  color: Colors.white,
                  fontSize: 27,
                  fontWeight: FontWeight.w800)),
          const SizedBox(height: 9),
          Text(
              '매출이 평소보다 좋은 흐름이에요.\n재고와 피크타임을 확인해 운영 효율을 높여 보세요.',
              style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.92),
                  fontSize: 12,
                  height: 1.6)),
          const SizedBox(height: 12),
          Align(
            alignment: Alignment.centerRight,
            child: TextButton.icon(
              onPressed: () => message('AI 리포트 상세 화면은 추후 연결할 예정이에요.'),
              style: TextButton.styleFrom(
                  foregroundColor: Colors.white,
                  backgroundColor: Colors.white.withValues(alpha: 0.18)),
              icon: const Icon(Icons.arrow_forward_rounded, size: 16),
              label: const Text('리포트 확인'),
            ),
          ),
        ]),
      );

  Widget metric(
          String title, String value, String caption, IconData icon, Color color) =>
      Container(
        padding: const EdgeInsets.all(15),
        decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(19),
            border: Border.all(color: line)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Icon(icon, color: color, size: 18),
            const SizedBox(width: 6),
            Expanded(
                child: Text(title,
                    style: const TextStyle(fontSize: 11, color: muted),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis)),
          ]),
          const SizedBox(height: 13),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(value,
                style: const TextStyle(
                    fontSize: 21, fontWeight: FontWeight.w800, color: ink)),
          ),
          const SizedBox(height: 5),
          Text(caption,
              style: TextStyle(
                  fontSize: 10,
                  color: caption.startsWith('+') ? green : muted,
                  fontWeight: FontWeight.w600)),
        ]),
      );

  Widget section(String title, String? action, VoidCallback? onTap) => Row(
        children: [
          Expanded(
              child: Text(title,
                  style: const TextStyle(
                      fontSize: 17, fontWeight: FontWeight.w800, color: ink))),
          if (action != null)
            TextButton(
              onPressed: onTap,
              style: TextButton.styleFrom(
                  foregroundColor: blue,
                  padding: const EdgeInsets.symmetric(horizontal: 4)),
              child: Text(action,
                  style: const TextStyle(
                      fontSize: 12, fontWeight: FontWeight.w700)),
            ),
        ],
      );

  Widget insight(IconData icon, Color color, Color background, String title,
          String body, String tag) =>
      Container(
        padding: const EdgeInsets.all(15),
        decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(19),
            border: Border.all(color: line)),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
                color: background, borderRadius: BorderRadius.circular(13)),
            child: Icon(icon, color: color, size: 21),
          ),
          const SizedBox(width: 12),
          Expanded(
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                Text(tag,
                    style: TextStyle(
                        color: color,
                        fontSize: 10,
                        fontWeight: FontWeight.w800)),
                const SizedBox(height: 4),
                Text(title,
                    style: const TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w800,
                        color: ink)),
                const SizedBox(height: 5),
                Text(body,
                    style: const TextStyle(
                        fontSize: 11, color: muted, height: 1.5)),
              ])),
        ]),
      );

  Widget chart() {
    const values = [0.36, 0.55, 0.42, 0.78, 0.62, 0.91, 0.70];
    const days = ['월', '화', '수', '목', '금', '토', '일'];
    return Container(
      padding: const EdgeInsets.fromLTRB(17, 17, 17, 14),
      decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: line)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('이번 주 매출 추이',
            style: TextStyle(color: muted, fontSize: 12)),
        const SizedBox(height: 5),
        const Text('₩2,845,000',
            style: TextStyle(
                color: ink, fontSize: 23, fontWeight: FontWeight.w800)),
        const SizedBox(height: 18),
        SizedBox(
          height: 110,
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: List.generate(values.length, (i) => Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 5),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    Expanded(
                      child: Align(
                        alignment: Alignment.bottomCenter,
                        child: FractionallySizedBox(
                          heightFactor: values[i],
                          child: Container(
                            decoration: BoxDecoration(
                              color: i == 5 ? blue : const Color(0xFFD9E8FF),
                              borderRadius: BorderRadius.circular(7),
                            ),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(days[i],
                        style: TextStyle(
                            fontSize: 10,
                            color: i == 5 ? blue : muted,
                            fontWeight: i == 5
                                ? FontWeight.w800
                                : FontWeight.normal)),
                  ],
                ),
              ),
            )),
          ),
        ),
      ]),
    );
  }

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
          border: Border(
            bottom: BorderSide(color: Color(0xFFE5E9F0)),
          ),
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
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.all(5),
            decoration: BoxDecoration(
              color: const Color(0xFFE8EDF4),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Row(
              children: ['오늘', '이번 주', '이번 달']
                  .asMap()
                  .entries
                  .map((entry) {
                final selected = entry.key == 1;

                return Expanded(
                  child: Container(
                    padding: const EdgeInsets.symmetric(vertical: 10),
                    decoration: BoxDecoration(
                      color: selected ? Colors.white : Colors.transparent,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Text(
                      entry.value,
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        color: selected ? ink : muted,
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),
          ),
          const SizedBox(height: 18),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF4A96FF), Color(0xFF2676E8)],
              ),
              borderRadius: BorderRadius.circular(20),
            ),
            child: const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '이번 주 총매출',
                  style: TextStyle(fontSize: 12, color: Colors.white70),
                ),
                SizedBox(height: 8),
                Text(
                  '₩2,845,000',
                  style: TextStyle(
                    fontSize: 27,
                    fontWeight: FontWeight.w800,
                    color: Colors.white,
                  ),
                ),
                SizedBox(height: 6),
                Text(
                  '지난주보다 12.8% 증가',
                  style: TextStyle(fontSize: 12, color: Colors.white),
                ),
              ],
            ),
          ),
          const SizedBox(height: 18),
          Row(
            children: [
              Expanded(
                child: metric(
                  '주문 건수',
                  '412건',
                  '+8.2%',
                  Icons.shopping_bag_rounded,
                  blue,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: metric(
                  '평균 주문 금액',
                  '₩6,905',
                  '+3.4%',
                  Icons.receipt_long_rounded,
                  green,
                ),
              ),
            ],
          ),
          const SizedBox(height: 22),
          section('매출 흐름', null, null),
          const SizedBox(height: 10),
          chart(),
          const SizedBox(height: 22),
          section('매출 분석 인사이트', null, null),
          const SizedBox(height: 10),
          insight(
            Icons.trending_up_rounded,
            green,
            const Color(0xFFE9F8F2),
            '매출이 상승하고 있어요',
            '이번 주 매출은 지난주보다 12.8% 높아요. 인기 시간대의 재고를 미리 확인해 보세요.',
            '긍정',
          ),
          const SizedBox(height: 10),
          insight(
            Icons.access_time_rounded,
            blue,
            const Color(0xFFEEF6FF),
            '토요일 매출이 가장 높아요',
            '요일별 매출을 비교해 피크타임에 인력을 효율적으로 배치해 보세요.',
            '요일 분석',
          ),
        ],
      );

  Widget aiAnalysisPage() => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    const Text('AI 운영 진단', style: TextStyle(fontSize: 25, fontWeight: FontWeight.w800, color: ink)),
    const SizedBox(height: 5), const Text('데이터로 매장의 다음 행동을 찾아요', style: TextStyle(fontSize: 12, color: muted)),
    const SizedBox(height: 18),
    Container(width: double.infinity, padding: const EdgeInsets.all(20), decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(22), border: Border.all(color: line)), child: const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('종합 운영 상태', style: TextStyle(fontSize: 12, color: muted)), SizedBox(height: 8), Text('주의 깊게 관찰해 주세요', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800, color: ink)), SizedBox(height: 14), Row(children: [Expanded(child: LinearProgressIndicator(value: .72, minHeight: 8, borderRadius: BorderRadius.all(Radius.circular(8)), color: Color(0xFFFFBD59), backgroundColor: line)), SizedBox(width: 12), Text('72/100', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800, color: ink))]), SizedBox(height: 12), Text('최근 매출, 리뷰, 운영 데이터를 종합한 예시 진단입니다.', style: TextStyle(fontSize: 11, color: muted, height: 1.5))])),
    const SizedBox(height: 22), section('주요 판단 근거', null, null), const SizedBox(height: 10),
    insight(Icons.bar_chart_rounded, blue, const Color(0xFFEEF6FF), '매출 변동성', '최근 4주간 변동 폭이 7% 커졌어요.', '주의'), const SizedBox(height: 10),
    insight(Icons.rate_review_rounded, const Color(0xFF8B6CE8), const Color(0xFFF2EDFF), '고객 반응', '대기 시간 관련 언급이 늘고 있어요.', '확인'), const SizedBox(height: 10),
    insight(Icons.location_on_outlined, green, const Color(0xFFE9F8F2), '상권 흐름', '평일 유동 인구는 비슷한 수준이에요.', '안정'),
    const SizedBox(height: 22), section('이번 주 우선 실행 항목', null, null), const SizedBox(height: 10), insight(Icons.check_circle_outline, blue, const Color(0xFFEEF6FF), '피크타임 주문 동선을 점검하세요', '혼잡 시간대의 대기 시간을 줄일 수 있도록 제조 순서를 확인해 보세요.', '실행 제안'),
  ]);

  Widget setRecommendationPage() => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    const Text('세트메뉴 추천', style: TextStyle(fontSize: 25, fontWeight: FontWeight.w800, color: ink)),
    const SizedBox(height: 5), const Text('실제 주문 조합에서 잘 맞는 메뉴를 찾아요', style: TextStyle(fontSize: 12, color: muted)),
    const SizedBox(height: 18), section('시간대별 추천', null, null), const SizedBox(height: 10),
    Wrap(spacing: 8, runSpacing: 8, children: ['전체','아침','점심','오후'].map((e) => Chip(label: Text(e), backgroundColor: e == '전체' ? blue : Colors.white, labelStyle: TextStyle(color: e == '전체' ? Colors.white : ink))).toList()),
    const SizedBox(height: 14), _recommendCard('아메리카노 + 버터 크루아상','함께 주문 1위','38%','두 메뉴 중 하나를 주문한 고객의 38%가 함께 선택했어요.','7,900원 제안'),
    const SizedBox(height: 14), section('다른 추천 조합', null, null), const SizedBox(height: 10), _recommendCard('카페라떼 + 버터 쿠키','오후 인기 조합','31%','오후 시간대에 함께 선택되는 조합이에요.','추천 조합'), const SizedBox(height: 10), _recommendCard('아메리카노 + 샌드위치','점심 추천 조합','27%','간단한 식사 메뉴와 음료를 함께 제안해 보세요.','추천 조합'),
  ]);

  Widget myPage() => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    const Text('마이', style: TextStyle(fontSize: 25, fontWeight: FontWeight.w800, color: ink)), const SizedBox(height: 18),
    Container(padding: const EdgeInsets.all(18), decoration: BoxDecoration(gradient: const LinearGradient(colors: [Color(0xFF4A96FF), Color(0xFF2676E8)]), borderRadius: BorderRadius.circular(20)), child: const Row(children: [CircleAvatar(backgroundColor: Colors.white, child: Text('김', style: TextStyle(color: blue, fontWeight: FontWeight.w800))), SizedBox(width: 12), Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('김서연 사장님', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w800)), SizedBox(height: 4), Text('오후의 커피 성수점', style: TextStyle(color: Colors.white70, fontSize: 11))])), Icon(Icons.chevron_right, color: Colors.white)])),
    const SizedBox(height: 22), section('데이터 연결', null, null), const SizedBox(height: 10), _settingsTile(Icons.link_rounded, '연결 상태', '4개 중 3개 연결됨'), const SizedBox(height: 20), section('매장 관리', null, null), const SizedBox(height: 10), _settingsTile(Icons.store_outlined, '매장 정보 수정', '주소, 영업시간, 메뉴'), _settingsTile(Icons.upload_file_rounded, '데이터 연결 및 업로드', 'POS, 리뷰, 재고 데이터'), _settingsTile(Icons.notifications_none_rounded, '알림 설정', '매출 및 재고 알림'), _settingsTile(Icons.description_outlined, '보고서 설정', '주간 AI 운영 보고서'), const SizedBox(height: 20), section('서비스', null, null), _settingsTile(Icons.help_outline_rounded, '문의하기', '도움이 필요하신가요?'),
  ]);

  Widget _progress(String label, double value, String percent) => Padding(padding: const EdgeInsets.symmetric(vertical: 8), child: Column(children: [Row(children: [Expanded(child: Text(label, style: const TextStyle(fontSize: 12, color: ink))), Text(percent, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: ink))]), const SizedBox(height: 7), ClipRRect(borderRadius: BorderRadius.circular(8), child: LinearProgressIndicator(value: value, minHeight: 6, color: blue, backgroundColor: line))]));

  Widget _recommendCard(String title, String tag, String percent, String body, String price) => Container(width: double.infinity, padding: const EdgeInsets.all(16), decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(18), border: Border.all(color: line)), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(tag, style: const TextStyle(fontSize: 10, color: blue, fontWeight: FontWeight.w800)), const SizedBox(height: 7), Text(title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: ink)), const SizedBox(height: 7), Text(body, style: const TextStyle(fontSize: 11, color: muted, height: 1.5)), const SizedBox(height: 12), Row(children: [Text(percent, style: const TextStyle(fontSize: 21, color: blue, fontWeight: FontWeight.w800)), const Spacer(), Text(price, style: const TextStyle(fontSize: 11, color: muted))])]));

  Widget _settingsTile(IconData icon, String title, String subtitle) => Container(margin: const EdgeInsets.only(bottom: 8), padding: const EdgeInsets.all(14), decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(15), border: Border.all(color: line)), child: Row(children: [Icon(icon, color: muted, size: 20), const SizedBox(width: 12), Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(title, style: const TextStyle(fontSize: 12, color: ink, fontWeight: FontWeight.w700)), const SizedBox(height: 3), Text(subtitle, style: const TextStyle(fontSize: 10, color: muted))])), const Icon(Icons.chevron_right_rounded, color: muted)]));

  Widget bottomNav() => Container(
        padding: const EdgeInsets.fromLTRB(7, 9, 7, 8),
        decoration: BoxDecoration(
            color: Colors.white, border: Border(top: BorderSide(color: line))),
        child: Row(
          children: List.generate(labels.length, (i) {
            final selected = tab == i;
            return Expanded(
              child: InkWell(
                onTap: () => setState(() => tab = i),
                borderRadius: BorderRadius.circular(13),
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 5),
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                    Icon(icons[i],
                        color: selected ? blue : const Color(0xFF9AA4B2),
                        size: 22),
                    const SizedBox(height: 4),
                    Text(labels[i],
                        style: TextStyle(
                            fontSize: 10,
                            color: selected ? blue : muted,
                            fontWeight: selected
                                ? FontWeight.w800
                                : FontWeight.w500)),
                  ]),
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
  const _StatusRow({required this.label, required this.value, required this.color});
  @override
  Widget build(BuildContext context) => Row(children: [Expanded(child: Text(label, style: const TextStyle(fontSize: 12, color: ink, fontWeight: FontWeight.w600))), Container(padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5), decoration: BoxDecoration(color: color.withValues(alpha: .10), borderRadius: BorderRadius.circular(20)), child: Text(value, style: TextStyle(fontSize: 10, color: color, fontWeight: FontWeight.w700)))]);
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
                  child: const Icon(Icons.auto_awesome_rounded,
                      color: Colors.white, size: 20),
                ),
                const SizedBox(width: 10),
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('AI 경영비서',
                          style: TextStyle(
                              color: ink,
                              fontSize: 16,
                              fontWeight: FontWeight.w800)),
                      SizedBox(height: 3),
                      Text('매장 운영에 필요한 정보를 빠르게 확인해 보세요.',
                          style: TextStyle(color: muted, fontSize: 9)),
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
        _bubble(
          '안녕하세요! 매출, 메뉴, 재고 등 궁금한 내용을 선택해 주세요.',
          isBot: true,
        ),
        const SizedBox(height: 18),
        if (selectedCategory == null) ...[
          const Text('무엇이 궁금하세요?',
              style: TextStyle(
                  color: muted, fontSize: 12, fontWeight: FontWeight.w800)),
          const SizedBox(height: 10),
          Column(
            children: categories.entries.map((entry) {
              return Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: SizedBox(
                  width: double.infinity,
                  child: OutlinedButton(
                    onPressed: () => setState(() => selectedCategory = entry.key),
                    style: OutlinedButton.styleFrom(
                      alignment: Alignment.centerLeft,
                      backgroundColor: Colors.white,
                      foregroundColor: ink,
                      side: const BorderSide(color: Color(0xFFDDE7F5)),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(14)),
                      padding: const EdgeInsets.symmetric(
                          horizontal: 12, vertical: 15),
                    ),
                    child: Row(
                      children: [
                        Icon(entry.value, color: blue, size: 19),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(entry.key,
                              style: const TextStyle(
                                  fontSize: 11, fontWeight: FontWeight.w700)),
                        ),
                        const Icon(Icons.chevron_right_rounded,
                            color: muted, size: 18),
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
              const Text('자주 묻는 질문',
                  style: TextStyle(
                      color: ink, fontSize: 13, fontWeight: FontWeight.w800)),
              const Spacer(),
              TextButton(
                onPressed: () => setState(() => selectedCategory = null),
                child: const Text('카테고리 변경',
                    style: TextStyle(fontSize: 10)),
              ),
            ],
          ),
          const SizedBox(height: 5),
          ...questions[selectedCategory]!.map((question) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Material(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(13),
                  child: InkWell(
                    onTap: () => setState(() => selectedQuestion = question),
                    borderRadius: BorderRadius.circular(13),
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 13, vertical: 14),
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(13),
                        border: Border.all(color: line),
                      ),
                      child: Row(
                        children: [
                          Expanded(
                            child: Text(question,
                                style: const TextStyle(
                                    fontSize: 11,
                                    color: ink,
                                    height: 1.4)),
                          ),
                          const Icon(Icons.chevron_right_rounded,
                              color: Color(0xFFADB8C8), size: 18),
                        ],
                      ),
                    ),
                  ),
                ),
              )),
        ],
      ],
    );
  }

  Widget _buildAnswerView() {
    final question = selectedQuestion!;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _bubble(
          '안녕하세요! 매출, 메뉴, 재고 등 궁금한 내용을 선택해 주세요.',
          isBot: true,
        ),
        const SizedBox(height: 14),
        Align(
          alignment: Alignment.centerRight,
          child: Container(
            constraints: const BoxConstraints(maxWidth: 300),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
            decoration: BoxDecoration(
              color: blue,
              borderRadius: BorderRadius.circular(16).copyWith(
                bottomRight: const Radius.circular(5),
              ),
            ),
            child: Text(question,
                style: const TextStyle(
                    color: Colors.white, fontSize: 12, height: 1.4)),
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
              child: const Icon(Icons.auto_awesome_rounded,
                  color: Colors.white, size: 15),
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
                    Text(answerFor(question),
                        style: const TextStyle(
                            color: ink, fontSize: 12, height: 1.7)),
                    const SizedBox(height: 13),
                    const Divider(height: 1, color: line),
                    const SizedBox(height: 8),
                    InkWell(
                      onTap: () {
                        final destination = selectedCategory == '매출 예측' ||
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
                            child: Text('관련 분석 확인하기',
                                style: TextStyle(
                                    color: blue,
                                    fontSize: 11,
                                    fontWeight: FontWeight.w800)),
                          ),
                          Icon(Icons.arrow_forward_rounded,
                              color: blue, size: 17),
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
                child: const Text('다른 질문 보기',
                    style: TextStyle(fontSize: 10)),
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
                child: const Text('처음으로',
                    style: TextStyle(fontSize: 10)),
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
            borderRadius: BorderRadius.circular(15).copyWith(
              bottomLeft: const Radius.circular(5),
            ),
          ),
          child: Text(text,
              style: const TextStyle(color: muted, fontSize: 11, height: 1.6)),
        ),
      );
}