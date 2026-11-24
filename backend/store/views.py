from django.db.models import ProtectedError
from rest_framework import generics, permissions
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Menu, Store
from .serializers import MenuSerializer, MyStoreSerializer
from .utils import get_my_store


class _Auth:
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]


class StoreListView(_Auth, generics.ListAPIView):
    """GET /store/ : 내 매장 목록 (관리자는 전체)"""
    serializer_class = MyStoreSerializer

    def get_queryset(self):
        qs = Store.objects.all() if self.request.user.is_staff else Store.objects.filter(owner=self.request.user)
        return qs.order_by("id")


class StoreDetailView(_Auth, generics.RetrieveUpdateAPIView):
    """GET / PATCH /store/{id}/ : 내 매장 상세 조회·수정"""
    serializer_class = MyStoreSerializer

    def get_object(self):
        return get_my_store(self.request, self.kwargs["pk"])


class MenuListCreateView(_Auth, generics.ListCreateAPIView):
    """GET /store/{id}/menus/?category=커피&is_active=true : 메뉴 목록 / POST : 메뉴 등록"""
    serializer_class = MenuSerializer

    def get_queryset(self):
        store = get_my_store(self.request, self.kwargs["store_id"])
        qs = Menu.objects.filter(store=store).order_by("source_menu_id", "id")
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)
        active = self.request.query_params.get("is_active")
        if active in ("true", "false"):
            qs = qs.filter(is_active=(active == "true"))
        return qs

    def list(self, request, *args, **kwargs):
        data = self.get_serializer(self.get_queryset(), many=True).data
        return Response({"count": len(data), "results": data})

    def perform_create(self, serializer):
        serializer.save(store=get_my_store(self.request, self.kwargs["store_id"]))


class MenuDetailView(_Auth, generics.RetrieveUpdateDestroyAPIView):
    """GET / PATCH / DELETE /store/{id}/menus/{pk}/"""
    serializer_class = MenuSerializer

    def get_queryset(self):
        return Menu.objects.filter(store=get_my_store(self.request, self.kwargs["store_id"]))

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"error": "판매 기록이 있는 메뉴는 삭제할 수 없습니다. is_active를 false로 바꿔 판매 중지 처리하세요."},
                status=409,
            )


class MenuProfitabilityView(_Auth, APIView):
    """GET /store/{id}/menus/profitability/?days=30 : 메뉴별 원가·마진·판매량·인기 순위"""

    def get(self, request, store_id):
        from .profitability import menu_profitability
        store = get_my_store(request, store_id)
        try:
            days = int(request.query_params.get("days", 0)) or None
        except ValueError:
            days = None
        return Response(menu_profitability(store.id, days))


class SetMenuRecommendView(_Auth, APIView):
    """GET /store/{id}/menus/set-recommend/?top=10 : 자주 같이 주문되는 메뉴 조합 → 세트 추천(500원 할인)"""

    def get(self, request, store_id):
        from .setmenu import recommend_sets
        store = get_my_store(request, store_id)
        try:
            top = max(1, min(int(request.query_params.get("top", 10)), 50))
        except ValueError:
            top = 10
        return Response(recommend_sets(store.id, top))


class ReviewAnalysisView(_Auth, APIView):
    """GET /store/{id}/reviews/analysis/ : 메뉴별 판매량·긍부정 비율, 불만 카테고리, 점검/홍보 후보"""

    def get(self, request, store_id):
        from review.insights import analysis
        store = get_my_store(request, store_id)
        return Response(analysis(store.id))
