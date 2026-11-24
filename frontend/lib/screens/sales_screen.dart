
import 'package:flutter/material.dart';

import '../app.dart' show blue, ink, muted;
import '../core/network/backend_api.dart';

class SalesScreen extends StatefulWidget {
  final int? storeId;
  final bool storeLoading;
  final String? storeError;

  const SalesScreen({
    super.key,
    required this.storeId,
    required this.storeLoading,
    required this.storeError,
  });

  @override
  State<SalesScreen> createState() => _SalesScreenState();
}

class _SalesScreenState extends State<SalesScreen> {
  Future<Map<String, dynamic>>? salesFuture;

  @override
  void initState() {
    super.initState();
    updateSalesFuture();
  }

  @override
  void didUpdateWidget(covariant SalesScreen oldWidget) {
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

  String displayDate(dynamic value) {
    if (value == null) return '-';

    final date = DateTime.tryParse(value.toString());
    if (date == null) return value.toString();

    return '${date.year}.${date.month.toString().padLeft(2, '0')}.'
        '${date.day.toString().padLeft(2, '0')}';
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
          '매출 분석',
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
          messageCard('등록된 매장이 없습니다. 매장을 등록한 후 이용해 주세요.')
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
                      : '매출 분석 정보를 불러오지 못했습니다.',
                  icon: Icons.error_outline,
                );
              }

              final data = snapshot.data ?? {};
              final summary = data['summary'] is Map
                  ? Map<String, dynamic>.from(data['summary'] as Map)
                  : <String, dynamic>{};

              final rawSeries = data['series'];
              final series = rawSeries is List
                  ? rawSeries
                      .whereType<Map>()
                      .map((item) => Map<String, dynamic>.from(item))
                      .toList()
                  : <Map<String, dynamic>>[];

              if (series.isEmpty) {
                return messageCard('조회할 매출 데이터가 없습니다.');
              }

              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(18),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: const Color(0xFFE8EDF3)),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          '조회 기간',
                          style: TextStyle(fontSize: 12, color: muted),
                        ),
                        const SizedBox(height: 5),
                        Text(
                          '${displayDate(data['start'])} ~ '
                          '${displayDate(data['end'])}',
                          style: const TextStyle(
                            color: ink,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        const Divider(height: 24),
                        _summaryRow('총 매출', money(summary['sales'])),
                        _summaryRow(
                          '총 주문 수',
                          '${summary['order_count'] ?? 0}건',
                        ),
                        _summaryRow(
                          '평균 객단가',
                          money(summary['average_ticket']),
                        ),
                        _summaryRow(
                          '매출 발생 일수',
                          '${summary['days_with_data'] ?? 0}일',
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 20),
                  const Text(
                    '일별 매출 내역',
                    style: TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w800,
                      color: ink,
                    ),
                  ),
                  const SizedBox(height: 10),
                  ...series.reversed.map((item) {
                    return Container(
                      margin: const EdgeInsets.only(bottom: 9),
                      padding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 14,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(14),
                        border: Border.all(
                          color: const Color(0xFFE8EDF3),
                        ),
                      ),
                      child: Row(
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  displayDate(item['period_start']),
                                  style: const TextStyle(
                                    fontSize: 14,
                                    fontWeight: FontWeight.w700,
                                    color: ink,
                                  ),
                                ),
                                const SizedBox(height: 5),
                                Text(
                                  '${item['order_count'] ?? 0}건 주문',
                                  style: const TextStyle(
                                    fontSize: 12,
                                    color: muted,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          Text(
                            money(item['sales']),
                            style: const TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w800,
                              color: blue,
                            ),
                          ),
                        ],
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

  Widget _summaryRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: muted, fontSize: 13)),
          Text(
            value,
            style: const TextStyle(
              color: ink,
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}
