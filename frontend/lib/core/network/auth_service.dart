import 'dart:convert';

import 'package:http/http.dart' as http;

import '../constants/api_constants.dart';

class AuthService {
  static const Duration _timeout = Duration(seconds: 15);

  Future<void> signup({
    required String email,
    required String password,
    String nickname = '',
    String phone = '',
  }) async {
    final response = await http
        .post(
          Uri.parse('${ApiConstants.baseUrl}${ApiConstants.signup}'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'email': email,
            'password': password,
            'nickname': nickname,
            'phone': phone,
          }),
        )
        .timeout(_timeout);

    if (response.statusCode != 201) {
      throw Exception(_errorMessage(response));
    }
  }

  Future> login({
    required String email,
    required String password,
  }) async {
    final response = await http
        .post(
          Uri.parse('${ApiConstants.baseUrl}${ApiConstants.login}'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'email': email,
            'password': password,
          }),
        )
        .timeout(_timeout);

    if (response.statusCode != 200) {
      throw Exception(_errorMessage(response));
    }

    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future> getMe(String token) async {
    final response = await http
        .get(
          Uri.parse('${ApiConstants.baseUrl}${ApiConstants.me}'),
          headers: {
            'Authorization': 'Token $token',
            'Content-Type': 'application/json',
          },
        )
        .timeout(_timeout);

    if (response.statusCode != 200) {
      throw Exception(_errorMessage(response));
    }

    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<void> logout(String token) async {
    final response = await http
        .post(
          Uri.parse('${ApiConstants.baseUrl}${ApiConstants.logout}'),
          headers: {
            'Authorization': 'Token $token',
            'Content-Type': 'application/json',
          },
        )
        .timeout(_timeout);

    if (response.statusCode != 204) {
      throw Exception(_errorMessage(response));
    }
  }

  String _errorMessage(http.Response response) {
    try {
      final data = jsonDecode(response.body);

      if (data is Map) {
        return data.entries
            .map((entry) => '${entry.key}: ${entry.value}')
            .join('\n');
      }

      return data.toString();
    } catch (_) {
      return '서버 오류가 발생했습니다. (${response.statusCode})';
    }
  }
}