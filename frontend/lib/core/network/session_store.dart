import 'session_store_memory.dart'
    if (dart.library.html) 'session_store_web.dart'
    as platform;

class SessionStore {
  static Future<String?> readToken() => platform.readToken();
  static Future<void> writeToken(String token) => platform.writeToken(token);
  static Future<void> clearToken() => platform.clearToken();
}
