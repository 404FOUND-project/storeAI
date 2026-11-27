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
        'API 요청 실패 (${response.statusCode}): ${response.body}',
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
}

