
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../constants/api_constants.dart';

class BusinessDataService {
  final String token;

  BusinessDataService({required this.token});

  static const Duration _timeout = Duration(seconds: 20);

  Future<dynamic> get(String path) async {
    final uri = Uri.parse('${ApiConstants.baseUrl}$path');

    final response = await http
        .get(
          uri,
          headers: {
            'Authorization': 'Token $token',
            'Content-Type': 'application/json',
          },
        )
        .timeout(_timeout);

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception(
        'API 요청 실패 (${response.statusCode}): ${utf8.decode(response.bodyBytes)}',
      );
    }

    return jsonDecode(utf8.decode(response.bodyBytes));
  }

  Future<List<Map<String, dynamic>>> getStores() async {
    final data = await get('/store/');

    final List<dynamic> items;

    if (data is List) {
      items = data;
    } else if (data is Map && data['results'] is List) {
      items = data['results'] as List;
    } else {
      throw Exception('매장 목록 응답 형식이 올바르지 않습니다.');
    }

    return items
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .toList();
  }

  Future<Map<String, dynamic>> getHome(int storeId) async {
    final data = await get('/sales/stores/$storeId/home/');
    return Map<String, dynamic>.from(data);
  }

  Future<Map<String, dynamic>> getSales(
    int storeId, {
    String granularity = 'day',
  }) async {
    final data = await get(
      '/sales/stores/$storeId/analysis/sales/?granularity=$granularity',
    );
    return Map<String, dynamic>.from(data);
  }

  Future<Map<String, dynamic>> getPatterns(int storeId) async {
    final data = await get('/sales/stores/$storeId/analysis/patterns/');
    return Map<String, dynamic>.from(data);
  }

  Future<Map<String, dynamic>> getReviewAnalysis(int storeId) async {
    final data = await get('/store/$storeId/reviews/analysis/');
    return Map<String, dynamic>.from(data);
  }

  Future<Map<String, dynamic>> getSavedForecast(int storeId) async {
    final data = await get('/sales/stores/$storeId/forecast/7-days/');
    return Map<String, dynamic>.from(data);
  }

  Future<Map<String, dynamic>> getMonthlyReport(int storeId) async {
    final data = await get(
      '/sales/stores/$storeId/analysis/monthly-report/',
    );
    return Map<String, dynamic>.from(data);
  }

  // 재고 목록 조회
  Future<Map<String, dynamic>> getInventory(int storeId) async {
    final data = await get(ApiConstants.inventory(storeId));
    return Map<String, dynamic>.from(data);
  }

  // 발주 추천 조회
  Future<Map<String, dynamic>> getReorderRecommendation(
    int storeId, {
    int targetDays = 7,
  }) async {
    final data = await get(
      ApiConstants.inventoryReorder(
        storeId,
        targetDays: targetDays,
      ),
    );
    return Map<String, dynamic>.from(data);
  }

  // 실제 주문 기반 세트 메뉴 추천 조회
  Future<Map<String, dynamic>> getSetMenuRecommendation(
    int storeId, {
    int top = 10,
  }) async {
    final data = await get(
      ApiConstants.setMenuRecommend(
        storeId,
        top: top,
      ),
    );
    return Map<String, dynamic>.from(data);
  }

  // 서버에서 챗봇 FAQ 카테고리와 질문 목록 조회
  Future<Map<String, dynamic>> getFaq() async {
    final data = await get('/api/chatbot/faq/');
    return Map<String, dynamic>.from(data);
  }

  // 선택한 FAQ 질문의 실제 답변 조회
  Future<Map<String, dynamic>> getFaqAnswer(
    String questionId, {
    int? storeId,
  }) async {
    final encodedId = Uri.encodeQueryComponent(questionId);

    final storeQuery =
        storeId == null ? '' : '&store_id=$storeId';

    final data = await get(
      '/api/chatbot/faq/answer/?id=$encodedId$storeQuery',
    );

    return Map<String, dynamic>.from(data);
  }

  Future<String> askChatbot(String question) async {
    final uri = Uri.parse('${ApiConstants.baseUrl}/api/chatbot/');
    final response = await http.post(uri, headers: {
      'Authorization': 'Token $token',
      'Content-Type': 'application/json',
    }, body: jsonEncode({'question': question})).timeout(_timeout);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('챗봇 요청 실패 (${response.statusCode}): ${utf8.decode(response.bodyBytes)}');
    }
    final result = jsonDecode(utf8.decode(response.bodyBytes));
    if (result is! Map) throw Exception('챗봇 응답 형식이 올바르지 않습니다.');
    return result['answer']?.toString() ?? '답변을 받지 못했습니다.';
  }

}
