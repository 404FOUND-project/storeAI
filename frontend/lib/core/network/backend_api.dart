
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

  void setToken(String? token) {
    _token = token;
  }

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (_token != null) 'Authorization': 'Token $_token',
      };

  Future<dynamic> _request(
    Future<http.Response> Function(Uri uri, Map<String, String> headers)
        request,
    String path,
  ) async {
    try {
      final response = await request(
        Uri.parse('${ApiConstants.baseUrl}$path'),
        _headers,
      ).timeout(const Duration(seconds: 8));

      final body =
          response.body.isEmpty ? null : jsonDecode(response.body);

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
      throw const BackendException(
        '백엔드에 연결되지 않았습니다. 서버 실행 상태를 확인해 주세요.',
      );
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

  // 이메일 기반 회원가입
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

  // 이메일 기반 로그인
  Future<Map<String, dynamic>> login({
    required String email,
    required String password,
  }) async {
    final body = await _request(
      (uri, headers) => http.post(
        uri,
        headers: headers,
        body: jsonEncode({
          'email': email,
          'password': password,
        }),
      ),
      ApiConstants.login,
    );

    final result = Map<String, dynamic>.from(body as Map);
    _token = result['token'] as String?;

    return result;
  }

  // 현재 로그인 사용자 조회
  Future<Map<String, dynamic>> currentUser() async {
    final body = await _request(
      (uri, headers) => http.get(uri, headers: headers),
      ApiConstants.me,
    );

    return Map<String, dynamic>.from(body as Map);
  }

  // 로그인 사용자의 소유 매장 조회
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

  // 매출 분석 조회 (기본 최근 30일, 일별)
  Future<Map<String, dynamic>> salesAnalysis(int storeId) async {
    final body = await _request(
      (uri, headers) => http.get(uri, headers: headers),
      ApiConstants.salesAnalysis(storeId),
    );

    return Map<String, dynamic>.from(body as Map);
  }

  // ??? ?? ?? ??
  Future<Map<String, dynamic>> savedForecast(
    int storeId, {
    int runId = 5,
  }) async {
    final body = await _request(
      (uri, headers) => http.get(uri, headers: headers),
      ApiConstants.savedForecast(storeId, runId),
    );

    return Map<String, dynamic>.from(body as Map);
  }

  // 로그아웃
  Future<void> logout() async {
    await _request(
      (uri, headers) => http.post(uri, headers: headers),
      ApiConstants.logout,
    );

    _token = null;
  }

  // 공지사항 조회
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

  // 챗봇 질문
  Future<String> askChatbot(String question, {int? storeId}) async {
    final body = await _request(
      (uri, headers) => http.post(
        uri,
        headers: headers,
        body: jsonEncode({'question': question, 'store_id': storeId}),
      ),
      ApiConstants.chatbot,
    );

    final result = Map<String, dynamic>.from(body as Map);

    return result['answer']?.toString() ??
        '백엔드에서 답변을 받지 못했습니다.';
  }

  Future<Map<String, dynamic>> answerFaq(String questionId, {int? storeId}) async {
    final query = 'id=${Uri.encodeQueryComponent(questionId)}'
        '${storeId == null ? '' : '&store_id=$storeId'}';
    final body = await _request(
      (uri, headers) => http.get(uri, headers: headers),
      '${ApiConstants.chatbot}faq/answer/?$query',
    );

    return Map<String, dynamic>.from(body as Map);
  }
  // 재고 목록 조회
  Future<Map<String, dynamic>> inventory(int storeId) async {
    final result = await _request(
      (uri, headers) => http.get(uri, headers: headers),
      ApiConstants.inventory(storeId),
    );

    return Map<String, dynamic>.from(result as Map);
  }

  // 발주 추천 조회
  Future<Map<String, dynamic>> inventoryReorder(
    int storeId, {
    int targetDays = 7,
  }) async {
    final result = await _request(
      (uri, headers) => http.get(uri, headers: headers),
      ApiConstants.inventoryReorder(
        storeId,
        targetDays: targetDays,
      ),
    );

    return Map<String, dynamic>.from(result as Map);
  }

  // 세트 메뉴 추천 조회
  Future<Map<String, dynamic>> setMenuRecommend(
    int storeId, {
    int top = 10,
  }) async {
    final result = await _request(
      (uri, headers) => http.get(uri, headers: headers),
      ApiConstants.setMenuRecommend(
        storeId,
        top: top,
      ),
    );

    return Map<String, dynamic>.from(result as Map);
  }
}
