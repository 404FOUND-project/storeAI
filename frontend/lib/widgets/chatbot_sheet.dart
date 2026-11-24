import 'package:flutter/material.dart';

import '../app.dart' show blue, ink, muted, line;
import '../core/network/backend_api.dart';

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
  String? selectedQuestionId;
  int? selectedFaqDestination;
  bool showAllCategories = false;
  late final Future<List<Map<String, dynamic>>> _faqFuture;
  List<Map<String, dynamic>> _faqData = const [];

  @override
  void initState() {
    super.initState();
    _faqFuture = BackendApi.instance.chatbotFaq();
    _faqFuture
        .then((items) {
          if (mounted) setState(() => _faqData = items);
        })
        .catchError((_) {});
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

  List<Map<String, dynamic>> _visibleCategories() => _faqData.isNotEmpty
      ? _faqData
      : categories.entries
            .map((entry) => {'category': entry.key, 'icon': entry.value})
            .toList();

  List<Map<String, dynamic>> _visibleQuestions() {
    final category = _faqData.where(
      (item) => item['category'] == selectedCategory,
    );
    if (category.isNotEmpty && category.first['questions'] is List) {
      return (category.first['questions'] as List)
          .whereType<Map>()
          .map((item) => Map<String, dynamic>.from(item))
          .toList();
    }
    return (questions[selectedCategory] ?? const <String>[])
        .map((question) => {'question': question})
        .toList();
  }

  IconData _categoryIcon(Map<String, dynamic> category, int index) {
    final icon = category['icon'];
    if (icon is IconData) return icon;
    const icons = [
      Icons.bar_chart_rounded,
      Icons.auto_awesome_rounded,
      Icons.storefront_outlined,
      Icons.inventory_2_outlined,
      Icons.rate_review_outlined,
      Icons.location_on_outlined,
    ];
    return icons[index % icons.length];
  }

  Future<String> _answerFor(String question) async {
    final id = selectedQuestionId;
    if (id != null) {
      try {
        final result = await BackendApi.instance.chatbotFaqAnswer(
          id,
          storeId: widget.storeId,
        );
        final destination = result['destination'];
        if (destination is num) {
          selectedFaqDestination = destination.toInt();
        }
        final answer = result['answer']?.toString();
        if (answer != null && answer.isNotEmpty) return answer;
      } catch (_) {
        // Use the free-text chatbot API if the selected FAQ has no answer.
      }
    }
    return BackendApi.instance.askChatbot(question);
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
            children: _visibleCategories().asMap().entries.map((indexed) {
              final entry = indexed.value;
              final label = entry['category']?.toString() ?? '';
              return Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: SizedBox(
                  width: double.infinity,
                  child: OutlinedButton(
                    onPressed: () => setState(() => selectedCategory = label),
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
                          _categoryIcon(entry, indexed.key),
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
                onPressed: () => setState(() {
                  selectedCategory = null;
                  selectedQuestionId = null;
                  selectedFaqDestination = null;
                }),
                child: const Text('카테고리 변경', style: TextStyle(fontSize: 10)),
              ),
            ],
          ),
          const SizedBox(height: 5),
          ..._visibleQuestions().map((questionData) {
            final question = questionData['question']?.toString() ?? '';
            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Material(
                color: Colors.white,
                borderRadius: BorderRadius.circular(13),
                child: InkWell(
                  onTap: () => setState(() {
                    selectedQuestion = question;
                    selectedQuestionId = questionData['id']?.toString();
                    selectedFaqDestination = null;
                  }),
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
      ],
    );
  }

  int _fallbackDestination() {
    final category = selectedCategory ?? '';
    if (category.contains('매출') && !category.contains('예측')) return 1;
    if (category.contains('메뉴')) return 3;
    if (category.contains('재고')) return 4;
    return 2;
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
                      future: _answerFor(question),
                      builder: (context, snapshot) {
                        if (snapshot.connectionState ==
                            ConnectionState.waiting) {
                          return const Padding(
                            padding: EdgeInsets.all(8),
                            child: Center(child: CircularProgressIndicator()),
                          );
                        }
                        return Text(
                          snapshot.hasError
                              ? '백엔드에 연결되지 않았습니다. 서버와 OPENAI_API_KEY 설정을 확인해 주세요.'
                              : snapshot.data ?? '답변이 없습니다.',
                          style: const TextStyle(
                            color: ink,
                            fontSize: 12,
                            height: 1.7,
                          ),
                        );
                      },
                    ),
                    const SizedBox(height: 13),
                    const Divider(height: 1, color: line),
                    const SizedBox(height: 8),
                    InkWell(
                      onTap: () {
                        final destination =
                            selectedFaqDestination ?? _fallbackDestination();
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
                  selectedQuestionId = null;
                  selectedFaqDestination = null;
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
                  selectedQuestionId = null;
                  selectedFaqDestination = null;
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
