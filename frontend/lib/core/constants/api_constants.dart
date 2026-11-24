class ApiConstants {
  const ApiConstants._();

  static const String baseUrl = 'http://127.0.0.1:8010';

  static const String signup = '/member/signup/';
  static const String login = '/member/login/';
  static const String me = '/member/me/';
  static const String logout = '/member/logout/';

  static const String notices = '/notices/';
  static const String chatbot = '/api/chatbot/';
  static const String stores = '/member/stores/';

  static String salesAnalysis(int storeId) =>
      '/sales/stores/$storeId/analysis/sales/';

  static String savedForecast(int storeId, int runId) =>
      '/sales/stores/$storeId/forecast/saved/?run_id=$runId';
}