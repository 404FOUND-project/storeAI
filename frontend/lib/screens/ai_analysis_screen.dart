import 'package:flutter/material.dart';

import '../app.dart' show blue, ink, line, muted;
import '../core/network/backend_api.dart';
import '../widgets/backend_state.dart';

class AiAnalysisScreen extends StatefulWidget {
  final int? storeId;
  final bool storeLoading;
  final String? storeError;

  const AiAnalysisScreen({
    super.key,
    required this.storeId,
    required this.storeLoading,
    required this.storeError,
  });

  @override
  State<AiAnalysisScreen> createState() => _AiAnalysisScreenState();
}

class _AiAnalysisScreenState extends State<AiAnalysisScreen> {
  Future<Map<String, dynamic>>? _reviews;
  Future<Map<String, dynamic>>? _forecast;
  Future<List<Map<String, dynamic>>>? _profitability;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void didUpdateWidget(covariant AiAnalysisScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.storeId != widget.storeId) _load();
  }

  void _load() {
    final id = widget.storeId;
    _reviews = id == null ? null : BackendApi.instance.reviewAnalysis(id);
    _forecast = id == null ? null : BackendApi.instance.salesForecast(id);
    _profitability = id == null
        ? null
        : BackendApi.instance.menuProfitability(id);
  }

  List<Map<String, dynamic>> _maps(dynamic value) => value is List
      ? value
            .whereType<Map>()
            .map((item) => Map<String, dynamic>.from(item))
            .toList()
      : const [];

  @override
  Widget build(BuildContext context) {
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
        const SizedBox(height: 18),
        if (widget.storeLoading)
          const Center(child: CircularProgressIndicator())
        else if (widget.storeError != null)
          _message(widget.storeError!)
        else if (_reviews == null)
          const BackendUnavailable(feature: '매장 분석')
        else ...[
          _sectionTitle('리뷰 분석'),
          FutureBuilder<Map<String, dynamic>>(
            future: _reviews,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return _message('리뷰 데이터를 불러오는 중입니다.');
              }
              if (snapshot.hasError) return _message('리뷰 분석을 불러오지 못했습니다.');
              final data = snapshot.data ?? const <String, dynamic>{};
              final categories = _maps(data['negative_categories']);
              final menus = _maps(data['menus']);
              if (categories.isEmpty && menus.isEmpty) {
                return _message('분석할 리뷰 데이터가 아직 없습니다.');
              }
              return Column(
                children: [
                  if (data['notice'] != null)
                    _card(
                      Text(
                        data['notice'].toString(),
                        style: const TextStyle(
                          color: muted,
                          fontSize: 11,
                          height: 1.5,
                        ),
                      ),
                    ),
                  ...categories.map(
                    (item) => _rowCard(
                      item['label']?.toString() ??
                          item['category']?.toString() ??
                          '기타',
                      '부정 리뷰 ${item['count'] ?? 0}건',
                      Icons.rate_review_outlined,
                    ),
                  ),
                  ...menus.map(
                    (item) => _rowCard(
                      item['name']?.toString() ?? '메뉴',
                      '리뷰 ${item['review_count'] ?? 0}건 · 긍정 ${((item['positive_ratio'] as num? ?? 0) * 100).round()}%',
                      item['flag'] == 'check_quality'
                          ? Icons.warning_amber_rounded
                          : Icons.thumb_up_alt_outlined,
                    ),
                  ),
                ],
              );
            },
          ),
          const SizedBox(height: 18),
          _sectionTitle('저장된 매출 예측'),
          FutureBuilder<Map<String, dynamic>>(
            future: _forecast,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return _message('예측 데이터를 불러오는 중입니다.');
              }
              if (snapshot.hasError) return _message('예측 데이터를 불러오지 못했습니다.');
              final data = snapshot.data ?? const <String, dynamic>{};
              final series = _maps(data['series']);
              if (series.isEmpty) return _message('저장된 예측 데이터가 없습니다.');
              return Column(
                children: series
                    .map(
                      (item) => _rowCard(
                        item['date']?.toString() ?? '',
                        '예상 판매 ${item['predicted_quantity'] ?? 0}개',
                        Icons.auto_graph_rounded,
                      ),
                    )
                    .toList(),
              );
            },
          ),
          const SizedBox(height: 18),
          _sectionTitle('메뉴별 수익성'),
          FutureBuilder<List<Map<String, dynamic>>>(
            future: _profitability,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return _message('수익성 데이터를 불러오는 중입니다.');
              }
              if (snapshot.hasError) return _message('수익성 데이터를 불러오지 못했습니다.');
              final items = snapshot.data ?? const [];
              if (items.isEmpty) return _message('수익성 데이터가 아직 없습니다.');
              return Column(
                children: items
                    .map(
                      (item) => _rowCard(
                        item['name']?.toString() ?? '메뉴',
                        item['profit'] == null
                            ? '원가 데이터가 필요합니다.'
                            : '이익 ${item['profit']}원 · 마진 ${item['margin_rate'] ?? '-'}%',
                        Icons.insights_rounded,
                      ),
                    )
                    .toList(),
              );
            },
          ),
        ],
      ],
    );
  }

  Widget _sectionTitle(String title) => Padding(
    padding: const EdgeInsets.only(bottom: 9),
    child: Align(
      alignment: Alignment.centerLeft,
      child: Text(
        title,
        style: const TextStyle(
          color: ink,
          fontSize: 16,
          fontWeight: FontWeight.w800,
        ),
      ),
    ),
  );

  Widget _card(Widget child) => Container(
    width: double.infinity,
    margin: const EdgeInsets.only(bottom: 8),
    padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.circular(15),
      border: Border.all(color: line),
    ),
    child: child,
  );

  Widget _rowCard(String title, String subtitle, IconData icon) => _card(
    Row(
      children: [
        Icon(icon, color: blue, size: 20),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(color: ink, fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 3),
              Text(
                subtitle,
                style: const TextStyle(color: muted, fontSize: 11),
              ),
            ],
          ),
        ),
      ],
    ),
  );

  Widget _message(String message) =>
      _card(Text(message, style: const TextStyle(color: muted, fontSize: 12)));
}
