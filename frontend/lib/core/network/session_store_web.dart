import 'dart:html' as html;

const _key = 'storeai.auth_token';

Future<String?> readToken() async => html.window.sessionStorage[_key];
Future<void> writeToken(String token) async {
  html.window.sessionStorage[_key] = token;
}

Future<void> clearToken() async {
  html.window.sessionStorage.remove(_key);
}
