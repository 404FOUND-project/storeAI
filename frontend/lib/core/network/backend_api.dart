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

  Future<Map<String, dynamic>> signup({
    required String username,
    required String password,
    required String nickname,
  }) async {
    final body = await _request(
      (uri, headers) => http.post(
        uri,
        headers: headers,
        body: jsonEncode({
          'username': username,
          'password': password,
          'nickname': nickname,
        }),
      ),
      ApiConstants.signup,
    );
    return Map<String, dynamic>.from(body as Map);
  }

  Future<Map<String, dynamic>> login({
    required String username,
    required String password,
  }) async {
    final body = await _request(
      (uri, headers) => http.post(
        uri,
        headers: headers,
        body: jsonEncode({'username': username, 'password': password}),
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
