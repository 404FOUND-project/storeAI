class ApiConstants {
  const ApiConstants._();

  // Override with --dart-define=API_BASE_URL=... when the backend host changes.
  static const baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://127.0.0.1:8001',
  );
  static const signup = '/member/signup/';
  static const login = '/member/login/';
  static const me = '/member/me/';
  static const logout = '/member/logout/';
  static const notices = '/notices/';
  static String notice(int noticeId) => '/notices/$noticeId/';
  static const chatbot = '/api/chatbot/';
  static const chatbotFaq = '/api/chatbot/faq/';
  static String chatbotFaqAnswer(String questionId, {int? storeId}) =>
      '/api/chatbot/faq/answer/?id=${Uri.encodeQueryComponent(questionId)}'
      '${storeId == null ? '' : '&store_id=$storeId'}';
  static const stores = '/member/stores/';
  static String store(int storeId) => '/store/$storeId/';
  static String salesAnalysis(int storeId) =>
      '/sales/stores/$storeId/analysis/sales/';
  static String savedForecast(int storeId, {int days = 7}) =>
      '/sales/stores/$storeId/forecast/saved/?days=$days';
  static String menus(int storeId) => '/store/$storeId/menus/';
  static String menu(int storeId, int menuId) =>
      '/store/$storeId/menus/$menuId/';
  static String menuProfitability(int storeId) =>
      '/store/$storeId/menus/profitability/?days=30';
  static String setRecommendations(int storeId) =>
      '/store/$storeId/menus/set-recommend/';
  static String reviewAnalysis(int storeId) =>
      '/store/$storeId/reviews/analysis/';
  static String inventory(int storeId) => '/store/$storeId/inventory/';
  static String reorderRecommendations(int storeId, {int targetDays = 7}) =>
      '/store/$storeId/inventory/reorder/?target_days=$targetDays';
}
