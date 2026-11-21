from datetime import timedelta

from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import permissions, serializers
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView

from store.models import Store

from .services import analytics, forecasting, queries

MAX_RANGE_DAYS = 1100
# Default look-back (inclusive days) per granularity when `start` is omitted.
DEFAULT_LOOKBACK_DAYS = {"day": 30, "week": 84, "month": 365}


class RangeSerializer(serializers.Serializer):
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)


class SalesSeriesSerializer(RangeSerializer):
    granularity = serializers.ChoiceField(choices=("day", "week", "month"), default="day")


class AsOfSerializer(serializers.Serializer):
    as_of = serializers.DateField(required=False)


class StoreAnalysisView(APIView):
    """Base for owner-scoped, read-only store analytics endpoints."""

    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_store(self, store_id):
        store = get_object_or_404(Store, pk=store_id)
        user = self.request.user
        # Other owners' stores look non-existent instead of revealing they exist.
        if not (user.is_staff or store.owner_id == user.id):
            raise Http404
        return store

    @staticmethod
    def parse(serializer_class, request):
        serializer = serializer_class(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    @staticmethod
    def resolve_range(params, latest, granularity="day"):
        end = params.get("end") or latest
        start = params.get("start") or end - timedelta(days=DEFAULT_LOOKBACK_DAYS[granularity] - 1)
        if start > end:
            raise serializers.ValidationError({"start": "start는 end보다 늦을 수 없습니다."})
        if (end - start).days + 1 > MAX_RANGE_DAYS:
            raise serializers.ValidationError({"start": f"조회 기간은 최대 {MAX_RANGE_DAYS}일입니다."})
        return start, end


class SalesSeriesView(StoreAnalysisView):
    """GET /sales/stores/<store_id>/analysis/sales/?granularity=day|week|month&start=&end="""

    def get(self, request, store_id):
        store = self.get_store(store_id)
        params = self.parse(SalesSeriesSerializer, request)
        latest = queries.latest_sales_date(store)
        if latest is None:
            return Response({"store_id": store.pk, "granularity": params["granularity"],
                             "start": None, "end": None, "summary": analytics.summarize({}), "series": []})
        start, end = self.resolve_range(params, latest, params["granularity"])
        daily = queries.daily_totals(store, start, end)
        return Response({
            "store_id": store.pk,
            "granularity": params["granularity"],
            "start": start.isoformat(),
            "end": end.isoformat(),
            "summary": analytics.summarize(daily),
            "series": analytics.rollup(daily, params["granularity"], start, end),
        })


class SalesPatternView(StoreAnalysisView):
    """GET /sales/stores/<store_id>/analysis/patterns/?start=&end= — weekday and hourly sales."""

    def get(self, request, store_id):
        store = self.get_store(store_id)
        params = self.parse(RangeSerializer, request)
        latest = queries.latest_sales_date(store)
        if latest is None:
            return Response({"store_id": store.pk, "start": None, "end": None, "days_with_data": 0,
                             "weekday": [], "hourly": []})
        start, end = self.resolve_range(params, latest, "month")
        daily = queries.daily_totals(store, start, end)
        hourly = queries.hourly_totals(store, start, end)
        return Response({
            "store_id": store.pk,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "days_with_data": len(daily),
            "weekday": analytics.weekday_pattern(daily),
            "hourly": analytics.hourly_pattern(hourly, len(daily)),
        })


class SalesComparisonView(StoreAnalysisView):
    """GET /sales/stores/<store_id>/analysis/comparison/?as_of= — day/week/month-over-period changes."""

    def get(self, request, store_id):
        store = self.get_store(store_id)
        params = self.parse(AsOfSerializer, request)
        latest = queries.latest_sales_date(store)
        if latest is None:
            return Response({"store_id": store.pk, "detail": "매출 데이터가 없습니다."}, status=404)
        as_of = params.get("as_of") or latest
        # 62 days covers the previous month's matching range plus both weeks.
        daily = queries.daily_totals(store, as_of - timedelta(days=62), as_of)
        result = analytics.compare(daily, as_of)
        result["store_id"] = store.pk
        return Response(result)


class ForecastView(StoreAnalysisView):
    """Shared handling: `as_of` defaults to the latest sales date; later data is never read."""

    def resolve_as_of(self, store, params):
        latest = queries.latest_sales_date(store)
        if latest is None:
            raise forecasting.InsufficientHistory("매출 데이터가 없어 예측할 수 없습니다.")
        return params.get("as_of") or latest

    def handle_exception(self, exc):
        if isinstance(exc, forecasting.InsufficientHistory):
            return Response({"detail": str(exc)}, status=422)
        return super().handle_exception(exc)


class NextDaySalesForecastView(ForecastView):
    """GET /sales/stores/<store_id>/forecast/next-day/?as_of= — next-day sales and order count."""

    def get(self, request, store_id):
        store = self.get_store(store_id)
        params = self.parse(AsOfSerializer, request)
        as_of = self.resolve_as_of(store, params)
        history_start = as_of - timedelta(days=forecasting.INDEX_WINDOW_DAYS + forecasting.INTERVAL_BACKTEST_DAYS)
        daily = queries.daily_totals(store, history_start, as_of)
        result = forecasting.forecast_next_day(daily, as_of)
        result["store_id"] = store.pk
        return Response(result)


class MenuQuantityForecastView(ForecastView):
    """GET /sales/stores/<store_id>/forecast/menu-quantity/?as_of= — next-day expected quantity per menu."""

    def get(self, request, store_id):
        store = self.get_store(store_id)
        params = self.parse(AsOfSerializer, request)
        as_of = self.resolve_as_of(store, params)
        history_start = as_of - timedelta(
            days=forecasting.INDEX_WINDOW_DAYS + forecasting.MENU_SHARE_WINDOW_DAYS + forecasting.MENU_BACKTEST_DAYS
        )
        menu_daily, names = queries.menu_daily_quantities(store, history_start, as_of)
        result = forecasting.forecast_menu_quantities(menu_daily, names, as_of)
        result["store_id"] = store.pk
        return Response(result)
