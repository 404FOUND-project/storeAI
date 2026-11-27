import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../constants/api_constants.dart';

class BackendException implements Exception {
  final String message;
  final int? statusCode;

  const BackendException(this.message, {this.statusCode});

  @override
  String toString() => message;
}

class BackendApi {
  BackendApi._();

  static final instance = BackendApi._();
  String? _token;

  bool get isAuthenticated => _token != null;

  Map<String, String> get _headers => {
    'Content-Type': 'application/json',
    if (_token != null) 'Authorization': 'Token ',
  };

  Future<dynamic> _request(
    Future<http.Response> Function(Uri uri, Map<String, String> headers)
    request,
    String path,
  ) async {
    try {
      final response = await request(
        Uri.parse(''),
        _headers,
      ).timeout(const Duration(seconds: 8));

      final body = response.body.isEmpty ? null : jsonDecode(response.body);

      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw BackendException(
          _messageFrom(body) ?? '백엔드 요청에 실패했습니다.',
          statusCode: response.statusCode,
        );
      }

      return body;
    } on BackendException {
      rethrow;
    } catch (_) {
      throw const BackendException('백엔드에 연결되지 않았습니다. 서버 실행 상태를 확인해 주세요.');
    }
  }

  String? _messageFrom(dynamic body) {
    if (body is String) return body;

    if (body is Map) {
      for (final key in [
        'detail',
        'error',
        'message',
        'email',
        'username',
        'password',
      ]) {
        final value = body[key];

        if (value != null) {
          return value is List ? value.join('\n') : value.toString();
        }
      }
    }

    return null;
  }

  List<Map<String, dynamic>> _asList(dynamic body) {
    final results = body is Map ? body['results'] : body;
    if (results is! List) return const [];
    return results
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .toList();
  }

  Future<Map<String, dynamic>> signup({
    required String email,
    required String password,
    required String nickname,
  }) async {
    final body = await _request(
      (uri, headers) => http.post(
        uri,
        headers: headers,
        body: jsonEncode({
          'email': email,
          'password': password,
          'nickname': nickname,
        }),
      ),
      ApiConstants.signup,
    );

    return Map<String, dynamic>.from(body as Map);
  }

  Future<Map<String, dynamic>> login({
    required String email,
    required String password,
  }) async {
    final body = await _request(
      (uri, headers) => http.post(
        uri,
        headers: headers,
        body: jsonEncode({'email': email, 'password': password}),
      ),
      ApiConstants.login,
    );

    final result = Map<String, dynamic>.from(body as Map);
    _token = result['token'] as String?;

    return result;
  }

  Future<Map<String, dynamic>> currentUser() async {
    final body = await _request(
      (uri, headers) => http.get(uri, headers: headers),
      ApiConstants.me,
    );

    return Map<String, dynamic>.from(body as Map);
  }

  Future<List<Map<String, dynamic>>> stores() async {
    final body = await _request(
      (uri, headers) => http.get(uri, headers: headers),
      ApiConstants.stores,
    );

    final results = body is Map ? body['results'] : body;

    if (results is! List) return const [];

    return results
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList();
  }

  Future<Map<String, dynamic>> registerStore(Map<String, dynamic> store) async {
    final body = await _request(
      (uri, headers) =>
          http.post(uri, headers: headers, body: jsonEncode(store)),
      ApiConstants.stores,
    );
    return Map<String, dynamic>.from(body as Map);
  }

  Future<Map<String, dynamic>> storeDetail(int storeId) async {
    final body = await _request(
      (uri, headers) => http.get(uri, headers: headers),
      ApiConstants.store(storeId),
    );
    return Map<String, dynamic>.from(body as Map);
  }

  Future<Map<String, dynamic>> updateStore(
    int storeId,
    Map<String, dynamic> store,
  ) async {
    final body = await _request(
      (uri, headers) =>
          http.patch(uri, headers: headers, body: jsonEncode(store)),
      ApiConstants.store(storeId),
    );
    return Map<String, dynamic>.from(body as Map);
  }

  Future<Map<String, dynamic>> salesAnalysis(int storeId) async {
    final body = await _request(
      (uri, headers) => http.get(uri, headers: headers),
      ApiConstants.salesAnalysis(storeId),
    );

    return Map<String, dynamic>.from(body as Map);
  }

  Future<Map<String, dynamic>> salesForecast(
    int storeId, {
    int days = 7,
  }) async {
    final body = await _request(
      (uri, headers) => http.get(uri, headers: headers),
      ApiConstants.savedForecast(storeId, days),
    );
    return Map<String, dynamic>.from(body as Map);
  }

  Future<List<Map<String, dynamic>>> menus(int storeId) async {
    final body = await _request(
      (uri, headers) => http.get(uri, headers: headers),
      ApiConstants.menus(storeId),
    );
    return _asList(body);
  }

  Future<Map<String, dynamic>> createMenu(
    int storeId,
    Map<String, dynamic> menu,
  ) async {
    final body = await _request(
      (uri, headers) =>
          http.post(uri, headers: headers, body: jsonEncode(menu)),
      ApiConstants.menus(storeId),
    );
    return Map<String, dynamic>.from(body as Map);
  }

  Future<Map<String, dynamic>> updateMenu(
    int storeId,
    int menuId,
    Map<String, dynamic> menu,
  ) async {
    final body = await _request(
      (uri, headers) =>
          http.patch(uri, headers: headers, body: jsonEncode(menu)),
      ApiConstants.menu(storeId, menuId),
    );
    return Map<String, dynamic>.from(body as Map);
  }

  Future<void> deleteMenu(int storeId, int menuId) async {
    await _request(
      (uri, headers) => http.delete(uri, headers: headers),
      ApiConstants.menu(storeId, menuId),
    );
  }

  Future<List<Map<String, dynamic>>> menuProfitability(int storeId) async {
    final body = await _request(
      (uri, headers) => http.get(uri, headers: headers),
      ApiConstants.menuProfitability(storeId),
    );
    return _asList(body);
  }

  Future<Map<String, dynamic>> setRecommendations(int storeId) async {
    final body = await _request(
      (uri, headers) => http.get(uri, headers: headers),
      ApiConstants.setRecommendations(storeId),
    );
    return Map<String, dynamic>.from(body as Map);
  }

  Future<Map<String, dynamic>> reviewAnalysis(int storeId) async {
    final body = await _request(
      (uri, headers) => http.get(uri, headers: headers),
      ApiConstants.reviewAnalysis(storeId),
    );
    return Map<String, dynamic>.from(body as Map);
  }

  Future<List<Map<String, dynamic>>> inventory(int storeId) async {
    final body = await _request(
      (uri, headers) => http.get(uri, headers: headers),
      ApiConstants.inventory(storeId),
    );
    return _asList(body);
  }

  Future<Map<String, dynamic>> createInventory(
    int storeId,
    Map<String, dynamic> item,
  ) async {
    final body = await _request(
      (uri, headers) =>
          http.post(uri, headers: headers, body: jsonEncode(item)),
      ApiConstants.inventory(storeId),
    );
    return Map<String, dynamic>.from(body as Map);
  }

  Future<Map<String, dynamic>> updateInventory(
    int storeId,
    int inventoryId,
    Map<String, dynamic> item,
  ) async {
    final body = await _request(
      (uri, headers) =>
          http.patch(uri, headers: headers, body: jsonEncode(item)),
      '/',
    );
    return Map<String, dynamic>.from(body as Map);
  }

  Future<void> deleteInventory(int storeId, int inventoryId) async {
    await _request(
      (uri, headers) => http.delete(uri, headers: headers),
      '/',
    );
  }

  Future<Map<String, dynamic>> reorderRecommendations(
    int storeId, {
    int targetDays = 7,
  }) async {
    final body = await _request(
      (uri, headers) => http.get(uri, headers: headers),
      ApiConstants.reorderRecommendations(storeId, targetDays: targetDays),
    );
    return Map<String, dynamic>.from(body as Map);
  }

  Future<void> logout() async {
    await _request(
      (uri, headers) => http.post(uri, headers: headers),
      ApiConstants.logout,
    );

    _token = null;
  }

  Future<List<Map<String, dynamic>>> notices() async {
    final body = await _request(
      (uri, headers) => http.get(uri, headers: headers),
      ApiConstants.notices,
    );

    final results = body is Map ? body['results'] : body;

    if (results is! List) return const [];

    return results
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList();
  }

  Future<Map<String, dynamic>> createNotice(Map<String, dynamic> notice) async {
    final body = await _request(
      (uri, headers) =>
          http.post(uri, headers: headers, body: jsonEncode(notice)),
      ApiConstants.notices,
    );
    return Map<String, dynamic>.from(body as Map);
  }

  Future<Map<String, dynamic>> updateNotice(
    int noticeId,
    Map<String, dynamic> notice,
  ) async {
    final body = await _request(
      (uri, headers) =>
          http.patch(uri, headers: headers, body: jsonEncode(notice)),
      ApiConstants.notice(noticeId),
    );
    return Map<String, dynamic>.from(body as Map);
  }

  Future<void> deleteNotice(int noticeId) async {
    await _request(
      (uri, headers) => http.delete(uri, headers: headers),
      ApiConstants.notice(noticeId),
    );
  }

  Future<List<Map<String, dynamic>>> chatbotFaq() async {
    final body = await _request(
      (uri, headers) => http.get(uri, headers: headers),
      ApiConstants.chatbotFaq,
    );
    final data = Map<String, dynamic>.from(body as Map);
    return _asList(data['categories']);
  }

  Future<Map<String, dynamic>> chatbotFaqAnswer(
    String questionId, {
    int? storeId,
  }) async {
    final body = await _request(
      (uri, headers) => http.get(uri, headers: headers),
      ApiConstants.chatbotFaqAnswer(questionId, storeId: storeId),
    );
    return Map<String, dynamic>.from(body as Map);
  }

  Future<String> askChatbot(String question) async {
    final body = await _request(
      (uri, headers) => http.post(
        uri,
        headers: headers,
        body: jsonEncode({'question': question}),
      ),
      ApiConstants.chatbot,
    );

    final result = Map<String, dynamic>.from(body as Map);

    return result['answer']?.toString() ?? '백엔드에서 답변을 받지 못했습니다.';
  }
}