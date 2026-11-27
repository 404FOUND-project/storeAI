from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Sum
from django.db.models.functions import ExtractHour, TruncDate
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import permissions, serializers
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView

from store.models import Store
from sales.ml.boundary import clamp_as_of, default_as_of, local_today
from sales.ml.forecast_engine import generate_forecasts

from .models import ForecastRun, ForecastValue, Sales, SalesItem
from .services import analytics, queries
from .services.daily_insights import build_daily_insights
from .services.monthly_report import build_monthly_report

MAX_RANGE_DAYS = 1100

# Default look-back (inclusive days) per granularity when `start` is omitted.
DEFAULT_LOOKBACK_DAYS = {
    "day": 30,
    "week": 84,
    "month": 365,
}


class RangeSerializer(serializers.Serializer):
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)


class SalesSeriesSerializer(RangeSerializer):
    granularity = serializers.ChoiceField(
        choices=("day", "week", "month"),
        default="day",
    )


class AsOfSerializer(serializers.Serializer):
    as_of = serializers.DateField(required=False)


class ForecastRunQuerySerializer(serializers.Serializer):
    run_id = serializers.IntegerField(required=False, min_value=1)


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
        start = params.get("start") or end - timedelta(
            days=DEFAULT_LOOKBACK_DAYS[granularity] - 1
        )

        if start > end:
            raise serializers.ValidationError({
                "start": "start는 end보다 늦을 수 없습니다."
            })

        if (end - start).days + 1 > MAX_RANGE_DAYS:
            raise serializers.ValidationError({
                "start": f"조회 기간은 최대 {MAX_RANGE_DAYS}일입니다."
            })

        return start, end


class HomeSummaryView(StoreAnalysisView):
    """GET /sales/stores/<store_id>/home/"""

    def get(self, request, store_id):
        store = self.get_store(store_id)

        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        day_before_yesterday = today - timedelta(days=2)

        daily = queries.daily_totals(
            store,
            yesterday - timedelta(days=7),
            yesterday,
        )

        yesterday_sales = daily.get(
            yesterday, {}
        ).get("sales", 0)

        previous_sales = daily.get(
            day_before_yesterday, {}
        ).get("sales", 0)

        comparison = analytics._change(
            yesterday_sales,
            previous_sales,
        )

        daily_insights = build_daily_insights(
            store,
            yesterday,
            daily,
        )

        today_forecast = (
            ForecastValue.objects
            .filter(
                run__store=store,
                run__status=ForecastRun.Status.COMPLETED,
                series_key="daily:sales",
                granularity=ForecastValue.Granularity.DAILY,
                metric=ForecastValue.Metric.SALES,
                target_date=today,
            )
            .select_related("run")
            .order_by("-run__generated_at", "-run_id")
            .first()
        )

        return Response({
            "store_id": store.pk,
            "today": today.isoformat(),
            "yesterday_sales": yesterday_sales,
            "day_before_yesterday_sales": previous_sales,
            "sales_change_amount": comparison["change"],
            "sales_change_percent": comparison["change_pct"],
            "today_predicted_sales": (
                today_forecast.predicted_value
                if today_forecast else None
            ),
            "forecast_run_id": (
                today_forecast.run_id
                if today_forecast else None
            ),
            "forecast_status": (
                "AVAILABLE"
                if today_forecast else "UNAVAILABLE"
            ),
            "daily_insights": daily_insights,
        })


class SalesSummaryView(StoreAnalysisView):
    """GET /sales/summary/"""

    def get(self, request):
        user = request.user
        stores = Store.objects.all() if user.is_staff else Store.objects.filter(owner=user)
        store = stores.order_by("pk").first()

        if store is None:
            return Response({
                "store_id": None,
                "today": timezone.localdate().isoformat(),
                "yesterday_sales": 0,
                "day_before_yesterday_sales": 0,
                "sales_change_amount": 0,
                "sales_change_percent": 0.0,
                "today_predicted_sales": None,
                "forecast_run_id": None,
                "forecast_status": "UNAVAILABLE",
                "daily_insights": [],
            })

        return HomeSummaryView().get(request, store.pk)


class SalesSeriesView(StoreAnalysisView):
    """GET /sales/stores/<store_id>/analysis/sales/"""

    def get(self, request, store_id):
        store = self.get_store(store_id)
        params = self.parse(SalesSeriesSerializer, request)

        latest = queries.latest_sales_date(store)

        if latest is None:
            return Response({
                "store_id": store.pk,
                "granularity": params["granularity"],
                "start": None,
                "end": None,
                "summary": analytics.summarize({}),
                "series": [],
            })

        start, end = self.resolve_range(
            params,
            latest,
            params["granularity"],
        )

        daily = queries.daily_totals(store, start, end)

        return Response({
            "store_id": store.pk,
            "granularity": params["granularity"],
            "start": start.isoformat(),
            "end": end.isoformat(),
            "summary": analytics.summarize(daily),
            "series": analytics.rollup(
                daily,
                params["granularity"],
                start,
                end,
            ),
        })


class SalesPatternView(StoreAnalysisView):
    """GET /sales/stores/<store_id>/analysis/patterns/"""

    def get(self, request, store_id):
        store = self.get_store(store_id)
        params = self.parse(RangeSerializer, request)

        latest = queries.latest_sales_date(store)
        today = timezone.localdate()
        today_weekday = today.weekday()

        if latest is None:
            return Response({
                "store_id": store.pk,
                "start": None,
                "end": None,
                "days_with_data": 0,
                "weekday": [],
                "hourly": [],
                "weekday_hourly": {
                    "weekday": today_weekday,
                    "days": 0,
                    "hours": [],
                },
            })

        start, end = self.resolve_range(params, today, "day")

        daily = queries.daily_totals(store, start, end)
        hourly = queries.hourly_totals(store, start, end)

        calendar_days = {
            weekday: sum(
                1
                for offset in range((end - start).days + 1)
                if (start + timedelta(days=offset)).weekday() == weekday
            )
            for weekday in range(7)
        }

        weekday_hourly = queries.weekday_hourly_totals(
            store, start, end, today_weekday
        )

        return Response({
            "store_id": store.pk,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "days_with_data": len(daily),
            "weekday": analytics.weekday_pattern(daily, calendar_days),
            "hourly": analytics.hourly_pattern(hourly, len(daily)),
            "weekday_hourly": weekday_hourly,
        })


class SalesComparisonView(StoreAnalysisView):
    """GET /sales/stores/<store_id>/analysis/comparison/"""

    def get(self, request, store_id):
        store = self.get_store(store_id)
        params = self.parse(AsOfSerializer, request)

        latest = queries.latest_sales_date(store)

        if latest is None:
            return Response(
                {
                    "store_id": store.pk,
                    "detail": "매출 데이터가 없습니다.",
                },
                status=404,
            )

        as_of = params.get("as_of") or latest

        daily = queries.daily_totals(
            store,
            as_of - timedelta(days=62),
            as_of,
        )

        result = analytics.compare(daily, as_of)
        result["store_id"] = store.pk

        return Response(result)


class MonthlyReportView(StoreAnalysisView):
    """GET /sales/stores/<store_id>/analysis/monthly-report/"""

    def get(self, request, store_id):
        store = self.get_store(store_id)
        report = build_monthly_report(store, request.query_params)
        report["store_id"] = store.pk
        return Response(report)


class ForecastView(StoreAnalysisView):
    """Shared handling for operational forecasts."""

    def resolve_as_of(self, store, params):
        requested = params.get("as_of") or default_as_of()
        return clamp_as_of(requested)

    def run_forecast(self, store, as_of):
        try:
            return generate_forecasts(
                store.pk,
                as_of=as_of,
                persist=False,
            )
        except ValueError as exc:
            raise serializers.ValidationError({
                "detail": str(exc)
            }) from exc


def _forecast_value(values, granularity, metric, target_date):
    return next(
        (
            item
            for item in values
            if item["granularity"] == granularity
            and item["metric"] == metric
            and item["target_date"] == target_date
        ),
        None,
    )


def _latest_saved_forecast(store, as_of=None):
    runs = ForecastRun.objects.filter(
        store=store,
        status=ForecastRun.Status.COMPLETED,
    )

    if as_of is not None:
        runs = runs.filter(as_of=as_of)

    run = runs.order_by("-generated_at", "-pk").first()
    if run is None:
        return None

    records = (
        ForecastValue.objects
        .filter(run=run)
        .select_related("menu")
        .order_by(
            "target_date",
            "granularity",
            "target_hour",
            "series_key",
        )
    )

    values = [
        {
            "series_key": item.series_key,
            "granularity": item.granularity,
            "metric": item.metric,
            "target_date": item.target_date.isoformat(),
            "target_hour": item.target_hour,
            "menu_id": item.menu_id,
            "menu_name": item.menu.name if item.menu_id else None,
            "serving_temperature": item.serving_temperature,
            "predicted_value": float(item.predicted_value),
            "lower_bound": (
                float(item.lower_bound)
                if item.lower_bound is not None else None
            ),
            "upper_bound": (
                float(item.upper_bound)
                if item.upper_bound is not None else None
            ),
        }
        for item in records
    ]

    metadata = run.metadata or {}
    metrics = run.metrics or {}
    target_dates = metadata.get("target_dates") or sorted({
        item["target_date"] for item in values
    })

    return {
        "run_id": run.pk,
        "status": run.status,
        "store_id": store.pk,
        "as_of": run.as_of.isoformat(),
        "target_dates": target_dates,
        "metadata": metadata,
        "metrics": metrics,
        "values": values,
    }


class NextDaySalesForecastView(ForecastView):
    """GET /sales/stores/<store_id>/forecast/next-day/"""

    def get(self, request, store_id):
        store = self.get_store(store_id)
        params = self.parse(AsOfSerializer, request)

        as_of = (
            clamp_as_of(params["as_of"])
            if params.get("as_of")
            else None
        )

        result = _latest_saved_forecast(store, as_of=as_of)

        if result is None or not result["target_dates"]:
            return Response(
                {"detail": "저장된 예측 결과가 없습니다."},
                status=404,
            )

        target_date = result["target_dates"][0]
        values = result["values"]

        sales = _forecast_value(values, "DAILY", "SALES", target_date)
        orders = _forecast_value(values, "DAILY", "ORDERS", target_date)
        quantity = _forecast_value(values, "DAILY", "QUANTITY", target_date)

        if sales is None or orders is None:
            return Response(
                {
                    "detail": (
                        "저장된 다음 날 매출 또는 "
                        "주문 수 예측값이 없습니다."
                    )
                },
                status=404,
            )

        return Response({
            "store_id": store.pk,
            "as_of": result["as_of"],
            "target_date": target_date,
            "method": "operational_forecast",
            "predicted_sales": sales["predicted_value"],
            "predicted_order_count": orders["predicted_value"],
            "predicted_quantity": (
                quantity["predicted_value"]
                if quantity else None
            ),
            "predicted_sales_lower": sales["lower_bound"],
            "predicted_sales_upper": sales["upper_bound"],
            "predicted_order_count_lower": orders["lower_bound"],
            "predicted_order_count_upper": orders["upper_bound"],
            "model_metrics": result["metrics"].get("daily", {}),
            "forecast_run_id": result["run_id"],
        })


class MenuQuantityForecastView(ForecastView):
    """GET /sales/stores/<store_id>/forecast/menu-quantity/"""

    def get(self, request, store_id):
        store = self.get_store(store_id)
        params = self.parse(AsOfSerializer, request)

        as_of = (
            clamp_as_of(params["as_of"])
            if params.get("as_of")
            else None
        )

        result = _latest_saved_forecast(store, as_of=as_of)

        if result is None or not result["target_dates"]:
            return Response(
                {"detail": "저장된 예측 결과가 없습니다."},
                status=404,
            )

        target_date = result["target_dates"][0]

        menus = [
            {
                "menu_id": item["menu_id"],
                "menu_name": item["menu_name"],
                "serving_temperature": item["serving_temperature"],
                "expected_quantity": item["predicted_value"],
                "expected_quantity_rounded": int(
                    item["predicted_value"] + 0.5
                ),
                "lower_bound": item["lower_bound"],
                "upper_bound": item["upper_bound"],
            }
            for item in result["values"]
            if item["granularity"] == "MENU"
            and item["metric"] == "QUANTITY"
            and item["target_date"] == target_date
        ]

        return Response({
            "store_id": store.pk,
            "as_of": result["as_of"],
            "target_date": target_date,
            "total_expected_quantity": sum(
                item["expected_quantity"]
                for item in menus
            ),
            "menus": menus,
            "forecast_run_id": result["run_id"],
        })


class SevenDayForecastView(ForecastView):
    """
    GET: 저장된 최신 7일 예측 조회
    POST: 새 예측 실행 및 DB 저장
    """

    def get(self, request, store_id):
        store = self.get_store(store_id)

        today = local_today()
        monday = today - timedelta(days=today.weekday())
        as_of = clamp_as_of(monday - timedelta(days=1))

        with transaction.atomic():
            Store.objects.select_for_update().get(pk=store.pk)
            result = _latest_saved_forecast(store, as_of=as_of)

            if result is None:
                generate_forecasts(
                    store.pk,
                    as_of=as_of,
                    persist=True,
                )
                result = _latest_saved_forecast(store, as_of=as_of)

        if result is None:
            return Response(
                {
                    "detail": "예측 결과를 생성하거나 조회하지 못했습니다."
                },
                status=500,
            )

        return Response({
            "store_id": store.pk,
            "as_of": result["as_of"],
            "target_dates": result["target_dates"],
            "metadata": result["metadata"],
            "metrics": result["metrics"],
            "values": result["values"],
            "forecast_run_id": result["run_id"],
        })

    def post(self, request, store_id):
        store = self.get_store(store_id)
        params = self.parse(AsOfSerializer, request)
        as_of = self.resolve_as_of(store, params)

        try:
            result = generate_forecasts(
                store.pk,
                as_of=as_of,
                persist=True,
            )
        except ValueError as exc:
            raise serializers.ValidationError({
                "detail": str(exc)
            }) from exc

        return Response({
            "store_id": store.pk,
            "as_of": result["as_of"],
            "target_dates": result["target_dates"],
            "metadata": result["metadata"],
            "metrics": result["metrics"],
            "values": result["values"],
            "forecast_run_id": result["run_id"],
        })


class SavedForecastView(StoreAnalysisView):
    """GET /sales/stores/<store_id>/forecast/saved/?run_id="""

    def get(self, request, store_id):
        store = self.get_store(store_id)
        params = self.parse(ForecastRunQuerySerializer, request)

        runs = ForecastRun.objects.filter(
            store=store,
            status=ForecastRun.Status.COMPLETED,
        )

        if params.get("run_id"):
            run = get_object_or_404(runs, pk=params["run_id"])
        else:
            run = runs.order_by("-generated_at", "-pk").first()

        if run is None:
            return Response(
                {
                    "store_id": store.pk,
                    "detail": "완료된 예측 결과가 없습니다.",
                },
                status=404,
            )

        records = (
            ForecastValue.objects
            .filter(run=run)
            .select_related("menu")
            .order_by(
                "target_date",
                "granularity",
                "target_hour",
                "series_key",
            )
        )

        values = [
            {
                "series_key": item.series_key,
                "granularity": item.granularity,
                "metric": item.metric,
                "target_date": item.target_date.isoformat(),
                "target_hour": item.target_hour,
                "menu_id": item.menu_id,
                "menu_name": item.menu.name if item.menu_id else None,
                "serving_temperature": item.serving_temperature,
                "predicted_value": item.predicted_value,
                "lower_bound": item.lower_bound,
                "upper_bound": item.upper_bound,
            }
            for item in records
        ]

        return Response({
            "store_id": store.pk,
            "run": {
                "id": run.pk,
                "as_of": run.as_of.isoformat(),
                "generated_at": run.generated_at.isoformat(),
                "model_version": run.model_version,
                "status": run.status,
                "metrics": run.metrics,
                "metadata": run.metadata,
            },
            "target_dates": sorted({
                item["target_date"] for item in values
            }),
            "value_count": len(values),
            "values": values,
        })


class ForecastAccuracyView(StoreAnalysisView):
    """GET /sales/stores/<store_id>/forecast/accuracy/?run_id="""

    @staticmethod
    def _metrics(pairs):
        if not pairs:
            return None

        errors = [
            predicted - actual
            for predicted, actual in pairs
        ]
        absolute_errors = [
            abs(error)
            for error in errors
        ]
        actual_total = sum(
            abs(actual)
            for _, actual in pairs
        )

        return {
            "sample_count": len(pairs),
            "mae": round(
                sum(absolute_errors) / len(pairs),
                4,
            ),
            "rmse": round(
                (
                    sum(error ** 2 for error in errors)
                    / len(pairs)
                ) ** 0.5,
                4,
            ),
            "wape_percent": (
                round(
                    sum(absolute_errors) / actual_total * 100,
                    4,
                )
                if actual_total else None
            ),
            "bias_percent": (
                round(
                    sum(errors) / actual_total * 100,
                    4,
                )
                if actual_total else None
            ),
        }

    def get(self, request, store_id):
        store = self.get_store(store_id)
        params = self.parse(ForecastRunQuerySerializer, request)

        runs = ForecastRun.objects.filter(
            store=store,
            status=ForecastRun.Status.COMPLETED,
        )

        run_id = params.get("run_id")
        if run_id:
            run = get_object_or_404(runs, pk=run_id)
        else:
            run = runs.order_by("-generated_at", "-pk").first()

        if run is None:
            return Response(
                {
                    "store_id": store.pk,
                    "detail": "완료된 예측 결과가 없습니다.",
                },
                status=404,
            )

        cutoff = default_as_of()

        forecast_rows = list(
            ForecastValue.objects
            .filter(run=run)
            .select_related("menu")
            .order_by(
                "target_date",
                "granularity",
                "target_hour",
                "series_key",
            )
        )

        eligible = [
            row
            for row in forecast_rows
            if row.target_date <= cutoff
        ]

        dates = sorted({
            row.target_date
            for row in eligible
        })

        if not dates:
            return Response({
                "store_id": store.pk,
                "run_id": run.pk,
                "model_version": run.model_version,
                "as_of": run.as_of.isoformat(),
                "actual_data_through": cutoff.isoformat(),
                "status": "NO_ACTUALS_YET",
                "message": "아직 비교할 실제 매출 데이터가 없습니다.",
                "comparison_count": 0,
                "metrics": {},
                "comparisons": [],
            })

        daily_actual = {}
        daily_rows = (
            Sales.objects.filter(
                store=store,
                sold_at__date__gte=dates[0],
                sold_at__date__lte=dates[-1],
            )
            .annotate(day=TruncDate("sold_at"))
            .values("day")
            .annotate(
                sales=Sum("total_amount"),
                orders=Count("id"),
            )
        )
        for item in daily_rows:
            daily_actual[item["day"]] = {
                "SALES": int(item["sales"] or 0),
                "ORDERS": int(item["orders"] or 0),
            }

        daily_quantity_rows = (
            SalesItem.objects.filter(
                sales__store=store,
                sales__sold_at__date__gte=dates[0],
                sales__sold_at__date__lte=dates[-1],
            )
            .annotate(day=TruncDate("sales__sold_at"))
            .values("day")
            .annotate(quantity=Sum("quantity"))
        )
        for item in daily_quantity_rows:
            daily_actual.setdefault(
                item["day"], {}
            )["QUANTITY"] = int(item["quantity"] or 0)

        hourly_actual = {}
        hourly_rows = (
            Sales.objects.filter(
                store=store,
                sold_at__date__gte=dates[0],
                sold_at__date__lte=dates[-1],
            )
            .annotate(
                day=TruncDate("sold_at"),
                hour=ExtractHour("sold_at"),
            )
            .values("day", "hour")
            .annotate(
                sales=Sum("total_amount"),
                orders=Count("id"),
            )
        )
        for item in hourly_rows:
            hourly_actual[(item["day"], item["hour"])] = {
                "SALES": int(item["sales"] or 0),
                "ORDERS": int(item["orders"] or 0),
            }

        for day in daily_actual:
            for hour in range(8, 22):
                hourly_actual.setdefault(
                    (day, hour),
                    {
                        "SALES": 0,
                        "ORDERS": 0,
                    },
                )

        menu_actual = {}
        menu_rows = (
            SalesItem.objects.filter(
                sales__store=store,
                sales__sold_at__date__gte=dates[0],
                sales__sold_at__date__lte=dates[-1],
            )
            .annotate(day=TruncDate("sales__sold_at"))
            .values(
                "day",
                "menu_id",
                "serving_temperature",
            )
            .annotate(quantity=Sum("quantity"))
        )
        for item in menu_rows:
            menu_actual[(
                item["day"],
                item["menu_id"],
                item["serving_temperature"],
            )] = int(item["quantity"] or 0)

        comparisons = []
        pairs_by_key = {}

        for row in eligible:
            actual_val = None
            if row.granularity == ForecastValue.Granularity.DAILY:
                actual_val = daily_actual.get(row.target_date, {}).get(row.metric)
            elif row.granularity == ForecastValue.Granularity.HOURLY:
                actual_val = hourly_actual.get((row.target_date, row.target_hour), {}).get(row.metric)
            elif row.granularity == ForecastValue.Granularity.MENU:
                actual_val = menu_actual.get(
                    (row.target_date, row.menu_id, row.serving_temperature)
                )

            if actual_val is None:
                continue

            pred_val = float(row.predicted_value)
            actual_float = float(actual_val)
            abs_err = round(abs(pred_val - actual_float), 4)

            comparisons.append({
                "series_key": row.series_key,
                "granularity": row.granularity,
                "metric": row.metric,
                "target_date": row.target_date.isoformat(),
                "target_hour": row.target_hour,
                "menu_id": row.menu_id,
                "menu_name": row.menu.name if row.menu_id else None,
                "serving_temperature": row.serving_temperature,
                "predicted_value": pred_val,
                "actual_value": actual_float,
                "absolute_error": abs_err,
            })

            group_key = f"{row.granularity.lower()}:{row.metric.lower()}"
            pairs_by_key.setdefault(group_key, []).append((pred_val, actual_float))

        metrics_summary = {
            key: self._metrics(pairs)
            for key, pairs in pairs_by_key.items()
        }

        return Response({
            "store_id": store.pk,
            "run_id": run.pk,
            "model_version": run.model_version,
            "as_of": run.as_of.isoformat(),
            "actual_data_through": cutoff.isoformat(),
            "status": "COMPLETED",
            "comparison_count": len(comparisons),
            "metrics": metrics_summary,
            "comparisons": comparisons,
        })