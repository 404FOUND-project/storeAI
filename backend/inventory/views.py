from decimal import Decimal, InvalidOperation

from rest_framework import generics, permissions
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView

from store.utils import get_my_store

from .models import Inventory
from .serializers import InventorySerializer
from .stock_services import daily_usage_by_inventory, forecast_usage, recommend_order, stock_status

DEFAULT_TARGET_DAYS = 7
MAX_TARGET_DAYS = 60
STATUS_ORDER = {"danger": 0, "low": 1, "ok": 2, "no_usage": 3}


class StoreInventoryMixin:
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = InventorySerializer

    def get_store(self):
        return get_my_store(self.request, self.kwargs["store_id"])

    def get_queryset(self):
        return Inventory.objects.filter(store=self.get_store()).order_by("ingredient_name")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if getattr(self, "swagger_fake_view", False):
            return ctx
        ctx["usage"] = daily_usage_by_inventory(self.get_store())
        return ctx


class InventoryListCreateView(StoreInventoryMixin, generics.ListCreateAPIView):
    """GET: 재고 목록(상태 포함, 위험한 순) / POST: 재고 등록"""

    def list(self, request, *args, **kwargs):
        items = list(self.get_queryset())
        data = self.get_serializer(items, many=True).data
        data = sorted(data, key=lambda d: (STATUS_ORDER[d["stock_status"]], d["days_left"] or 0))
        return Response({"count": len(data), "results": data})

    def perform_create(self, serializer):
        serializer.save(store=self.get_store())


class InventoryDetailView(StoreInventoryMixin, generics.RetrieveUpdateDestroyAPIView):
    """GET / PATCH(PUT) / DELETE 재고 1건"""


class ReorderRecommendationView(APIView):
    """발주 추천.

    GET /store/{store_id}/inventory/reorder/?target_days=7
    target_days: 며칠치 재고를 확보할지 (기본 7, 최대 60)
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, store_id):
        store = get_my_store(request, store_id)
        try:
            target_days = int(request.query_params.get("target_days", DEFAULT_TARGET_DAYS))
        except ValueError:
            target_days = -1
        if not 1 <= target_days <= MAX_TARGET_DAYS:
            return Response(
                {"error": f"target_days는 1~{MAX_TARGET_DAYS} 사이 정수여야 합니다."}, status=400
            )

        series_map = forecast_usage(store)  # A의 예측(날짜별 사용량). 없으면 None -> 14일 평균 fallback
        if series_map:
            usage = {k: sum(v, Decimal(0)) / len(v) for k, v in series_map.items() if v}
        else:
            usage = daily_usage_by_inventory(store)
        results = []
        for inv in Inventory.objects.filter(store=store).order_by("ingredient_name"):
            per_day = usage.get(inv.id)
            qty, note = recommend_order(inv, per_day, target_days, series=(series_map or {}).get(inv.id))
            days_left, state = stock_status(inv.quantity, per_day)
            results.append({
                "inventory_id": inv.id,
                "ingredient_name": inv.ingredient_name,
                "unit": inv.unit,
                "quantity": str(inv.quantity),
                "daily_usage": round(float(per_day), 2) if per_day else None,
                "days_left": round(days_left, 1) if days_left is not None else None,
                "stock_status": state,
                "expiration_date": inv.expiration_date,
                "recommended_order_qty": str(qty),
                "note": note,
            })
        results.sort(key=lambda r: (STATUS_ORDER[r["stock_status"]], r["days_left"] or 0))
        return Response({
            "target_days": target_days,
            "basis": "A의 판매량 예측 합산" if series_map else "최근 14일 판매량 평균 (예측 연결 전 임시 방식)",
            "count": len(results),
            "results": results,
        })
