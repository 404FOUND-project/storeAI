import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import 'session_store.dart';

class ApiException implements Exception {
  final int statusCode;
  final String message;
  const ApiException(this.statusCode, this.message);
  @override
  String toString() => message;
}

class FaqQuestion {
  final String id;
  final String question;
  const FaqQuestion(this.id, this.question);
}

class FaqCategory {
  final String category;
  final int destination;
  final List<FaqQuestion> questions;
  const FaqCategory(this.category, this.destination, this.questions);
}

class FaqAnswer {
  final String answer;
  final int destination;
  const FaqAnswer(this.answer, this.destination);
}

class ApiClient {
  static String? _token;
  static final http.Client _http = http.Client();

  static String get baseUrl {
    const configured = String.fromEnvironment('API_BASE_URL');
    if (configured.isNotEmpty) return configured;
    return !kIsWeb && defaultTargetPlatform == TargetPlatform.android
        ? 'http://10.0.2.2:8000'
        : 'http://127.0.0.1:8000';
  }

  static Future<void> restoreSession() async {
    _token = await SessionStore.readToken();
  }

  static bool get hasSession => _token != null;

  static Future<dynamic> _request(
    String method,
    String path, {
    Map<String, String>? query,
    Object? body,
    bool authenticated = true,
  }) async {
    final uri = Uri.parse('$baseUrl$path').replace(queryParameters: query);
    final headers = <String, String>{'Accept': 'application/json'};
    if (body != null)
      headers['Content-Type'] = 'application/json; charset=utf-8';
    if (authenticated && _token != null) {
      headers['Authorization'] = 'Token $_token';
    }
    final request = http.Request(method, uri)..headers.addAll(headers);
    if (body != null) request.body = jsonEncode(body);
    final streamed = await _http
        .send(request)
        .timeout(const Duration(seconds: 15));
    final response = await http.Response.fromStream(streamed);
    if (response.statusCode == 204 || response.bodyBytes.isEmpty) return null;
    final decoded = jsonDecode(utf8.decode(response.bodyBytes));
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ApiException(response.statusCode, _errorMessage(decoded));
    }
    return decoded;
  }

  static String _errorMessage(dynamic data) {
    if (data is String) return data;
    if (data is Map) {
      for (final key in ['detail', 'error', 'non_field_errors', 'message']) {
        final value = data[key];
        if (value != null) return value is List ? value.join('\n') : '$value';
      }
      return data.entries
          .map(
            (e) =>
                '${e.key}: ${e.value is List ? (e.value as List).join(', ') : e.value}',
          )
          .join('\n');
    }
    return '요청을 처리하지 못했어요.';
  }

  static Future<Map<String, dynamic>> login(
    String username,
    String password,
  ) async {
    final result = Map<String, dynamic>.from(
      await _request(
        'POST',
        '/member/login/',
        authenticated: false,
        body: {'username': username, 'password': password},
      ) as Map,
    );
    _token = result['token'] as String;
    await SessionStore.writeToken(_token!);
    return result;
  }

  static Future<Map<String, dynamic>> signup({
    required String username,
    required String password,
    required String nickname,
    required String phone,
  }) async => Map<String, dynamic>.from(
    await _request(
      'POST',
      '/member/signup/',
      authenticated: false,
      body: {
        'username': username,
        'password': password,
        'nickname': nickname,
        'phone': phone,
      },
    ) as Map,
  );

  static Future<Map<String, dynamic>> me() async =>
      Map<String, dynamic>.from(await _request('GET', '/member/me/') as Map);

  static Future<void> logout() async {
    try {
      await _request('POST', '/member/logout/', body: {});
    } finally {
      _token = null;
      await SessionStore.clearToken();
    }
  }

  static Future<List<Map<String, dynamic>>> stores() async =>
      _asList(await _request('GET', '/store/'));

  static Future<Map<String, dynamic>> registerStore({
    required String name,
    required String address,
    String phone = '',
    String businessNumber = '',
  }) async => Map<String, dynamic>.from(
    await _request(
      'POST',
      '/member/stores/',
      body: {
        'name': name,
        'address': address,
        'phone': phone,
        'business_number': businessNumber,
      },
    ) as Map,
  );

  static Future<Map<String, dynamic>> store(int id) async =>
      Map<String, dynamic>.from(await _request('GET', '/store/$id/') as Map);

  static Future<Map<String, dynamic>> updateStore(
    int id,
    Map<String, dynamic> data,
  ) async => Map<String, dynamic>.from(
    await _request('PATCH', '/store/$id/', body: data) as Map,
  );

  static Future<List<Map<String, dynamic>>> menus(int storeId) async =>
      _asList(await _request('GET', '/store/$storeId/menus/'));

  static Future<List<Map<String, dynamic>>> menuProfitability(
    int storeId, {
    int days = 30,
  }) async => _asList(
    await _request(
      'GET',
      '/store/$storeId/menus/profitability/',
      query: {'days': '$days'},
    ),
  );

  static Future<Map<String, dynamic>> createMenu(
    int storeId,
    Map<String, dynamic> data,
  ) async => Map<String, dynamic>.from(
    await _request('POST', '/store/$storeId/menus/', body: data) as Map,
  );

  static Future<Map<String, dynamic>> updateMenu(
    int storeId,
    int menuId,
    Map<String, dynamic> data,
  ) async => Map<String, dynamic>.from(
    await _request('PATCH', '/store/$storeId/menus/$menuId/', body: data)
        as Map,
  );

  static Future<void> deleteMenu(int storeId, int menuId) async =>
      _request('DELETE', '/store/$storeId/menus/$menuId/');

  static Future<Map<String, dynamic>> setRecommendations(int storeId) async =>
      Map<String, dynamic>.from(
        await _request('GET', '/store/$storeId/menus/set-recommend/'),
      );

  static Future<List<Map<String, dynamic>>> inventory(int storeId) async =>
      _asList(await _request('GET', '/store/$storeId/inventory/'));

  static Future<Map<String, dynamic>> reorderRecommendations(
    int storeId, {
    int targetDays = 7,
  }) async => Map<String, dynamic>.from(
    await _request(
      'GET',
      '/store/$storeId/inventory/reorder/',
      query: {'target_days': '$targetDays'},
    ),
  );

  static Future<Map<String, dynamic>> createInventory(
    int storeId,
    Map<String, dynamic> data,
  ) async => Map<String, dynamic>.from(
    await _request('POST', '/store/$storeId/inventory/', body: data) as Map,
  );

  static Future<Map<String, dynamic>> updateInventory(
    int storeId,
    int inventoryId,
    Map<String, dynamic> data,
  ) async => Map<String, dynamic>.from(
    await _request(
      'PATCH',
      '/store/$storeId/inventory/$inventoryId/',
      body: data,
    ) as Map,
  );

  static Future<void> deleteInventory(int storeId, int inventoryId) async =>
      _request('DELETE', '/store/$storeId/inventory/$inventoryId/');

  static Future<Map<String, dynamic>> reviewAnalysis(int storeId) async =>
      Map<String, dynamic>.from(
        await _request('GET', '/store/$storeId/reviews/analysis/') as Map,
      );

  static Future<List<Map<String, dynamic>>> notices() async =>
      _asList(await _request('GET', '/notices/', authenticated: false));

  static Future<List<FaqCategory>> fetchFaq() async {
    final result =
        await _request('GET', '/api/chatbot/faq/', authenticated: false) as Map;
    return (result['categories'] as List)
        .map(
          (c) => FaqCategory(
            c['category'] as String,
            (c['destination'] as num).toInt(),
            (c['questions'] as List)
                .map(
                  (q) =>
                      FaqQuestion(q['id'] as String, q['question'] as String),
                )
                .toList(),
          ),
        )
        .toList();
  }

  static Future<FaqAnswer> fetchAnswer(String id, int storeId) async {
    final result = await _request(
      'GET',
      '/api/chatbot/faq/answer/',
      authenticated: false,
      query: {'id': id, 'store_id': '$storeId'},
    ) as Map;
    return FaqAnswer(
      result['answer'] as String,
      (result['destination'] as num).toInt(),
    );
  }

  static List<Map<String, dynamic>> _asList(dynamic data) {
    final items = data is Map && data['results'] is List
        ? data['results'] as List
        : data as List;
    return items.map((item) => Map<String, dynamic>.from(item as Map)).toList();
  }
}
