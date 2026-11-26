class ApiConstants {
  const ApiConstants._();

  // Run Django locally with: python backend/manage.py runserver 127.0.0.1:8000
  static const baseUrl = 'http://127.0.0.1:8010';
  static const signup = '/member/signup/';
  static const login = '/member/login/';
  static const me = '/member/me/';
  static const logout = '/member/logout/';
  static const notices = '/notices/';
  static const chatbot = '/api/chatbot/';
  static const stores = '/member/stores/';
  static String salesAnalysis(int storeId) =>
    '/sales/stores/$storeId/analysis/sales/';

  static String savedForecast(int storeId, int runId) =>
    '/sales/stores/$storeId/forecast/saved/?run_id=$runId';
  // 재고 목록
  static String inventory(int storeId) =>
      '/store/$storeId/inventory/';

  // 발주 추천
  static String inventoryReorder(int storeId, {int targetDays = 7}) =>
      '/store/$storeId/inventory/reorder/?target_days=$targetDays';

  // 세트 메뉴 추천
  static String setMenuRecommend(int storeId, {int top = 10}) =>
      '/store/$storeId/menus/set-recommend/?top=$top';
}
