
import 'package:flutter/material.dart';

import '../app.dart' show blue, ink, muted;
import '../core/network/backend_api.dart';

class HomeScreen extends StatefulWidget {
  final ValueChanged<int> onNavigate;
  final int? storeId;
  final bool storeLoading;
  final String? storeError;

  const HomeScreen({
    super.key,
    required this.onNavigate,
    required this.storeId,
    required this.storeLoading,
    required this.storeError,
  });

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  Future<Map<String, dynamic>>? salesFuture;

  @override
  void initState() {
    super.initState();
    updateSalesFuture();
  }

  @override
  void didUpdateWidget(covariant HomeScreen oldWidget) {
    super.didUpdateWidget(oldWidget);

    if (oldWidget.storeId != widget.storeId) {
      updateSalesFuture();
    }
  }

  void updateSalesFuture() {
    salesFuture = widget.storeId == null
        ? null
        : BackendApi.instance.salesAnalysis(widget.storeId!);
  }

  String money(dynamic value) {
    final amount = num.tryParse(value?.toString() ?? '') ?? 0;
    return '₩${amount.toStringAsFixed(0)}';
  }

  Widget metricCard(String title, String value, IconData icon) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(15),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: const Color(0xFFE8EDF3)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: blue, size: 22),
            const SizedBox(height: 12),
            Text(
              title,
              style: const TextStyle(fontSize: 12, color: muted),
            ),
            const SizedBox(height: 5),
            Text(
              value,
              style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w800,
                color: ink,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget messageCard(String message, {IconData icon = Icons.info_outline}) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          Icon(icon, color: muted),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: const TextStyle(color: muted, height: 1.5),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '홈',
          style: TextStyle(
            fontSize: 25,
            fontWeight: FontWeight.w800,
            color: ink,
          ),
        ),
        const SizedBox(height: 18),
        if (widget.storeLoading)
          const Center(
            child: Padding(
              padding: EdgeInsets.all(30),
              child: CircularProgressIndicator(),
            ),
          )
        else if (widget.storeError != null)
          messageCard(widget.storeError!, icon: Icons.error_outline)
        else if (widget.storeId == null)
          messageCard(
            '등록된 매장이 없습니다. 매장을 등록한 후 이용해 주세요.',
          )
        else
          FutureBuilder<Map<String, dynamic>>(
            future: salesFuture,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const Center(
                  child: Padding(
                    padding: EdgeInsets.all(30),
                    child: CircularProgressIndicator(),
                  ),
                );
              }

              if (snapshot.hasError) {
                return messageCard(
                  snapshot.error is BackendException
                      ? (snapshot.error as BackendException).message
                      : '매출 정보를 불러오지 못했습니다.',
                  icon: Icons.error_outline,
                );
              }

              final data = snapshot.data ?? {};
              final summary = data['summary'] is Map
                  ? Map<String, dynamic>.from(data['summary'] as Map)
                  : <String, dynamic>{};

              final sales = summary['sales'] ?? 0;
              final orderCount = summary['order_count'] ?? 0;
              final averageTicket = summary['average_ticket'] ?? 0;
              final daysWithData = summary['days_with_data'] ?? 0;

              final hasData = (num.tryParse(sales.toString()) ?? 0) > 0 ||
                  (num.tryParse(orderCount.toString()) ?? 0) > 0;

              if (!hasData) {
                return messageCard('최근 매출 데이터가 없습니다.');
              }

              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    '최근 30일 매출',
                    style: TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w800,
                      color: ink,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      color: blue,
                      borderRadius: BorderRadius.circular(18),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          '총 매출',
                          style: TextStyle(
                            color: Colors.white70,
                            fontSize: 13,
                          ),
                        ),
                        const SizedBox(height: 7),
                        Text(
                          money(sales),
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 28,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          '매출 발생 $daysWithData일',
                          style: const TextStyle(
                            color: Colors.white70,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      metricCard(
                        '주문 수',
                        '$orderCount건',
                        Icons.receipt_long_rounded,
                      ),
                      const SizedBox(width: 10),
                      metricCard(
                        '평균 객단가',
                        money(averageTicket),
                        Icons.payments_outlined,
                      ),
                    ],
                  ),
                  const SizedBox(height: 20),
                  SizedBox(
                    width: double.infinity,
                    child: OutlinedButton(
                      onPressed: () => widget.onNavigate(1),
                      child: const Text('상세 매출 분석 보기'),
                    ),
                  ),
                ],
              );
            },
          ),
      ],
    );
  }
}
