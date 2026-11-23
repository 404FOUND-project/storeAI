
from datetime import timedelta

from django.db.models import Count, Sum
from django.db.models.functions import ExtractHour, TruncDate
from django.http import Http404
from django.shortcuts import get_object_or_404

from rest_framework import permissions, serializers
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView

from store.models import Store

from sales.ml.boundary import clamp_as_of, default_as_of
from sales.ml.forecast_engine import generate_forecasts

from .models import ForecastRun, ForecastValue, Sales, SalesItem
from .services import analytics, forecasting, queries
from django.utils import timezone

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

        # 한국 시간 기준 날짜
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        day_before_yesterday = today - timedelta(days=2)

        # 최근 2일 실제 매출 조회
        daily = queries.daily_totals(
            store,
            day_before_yesterday,
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

        # 가장 최근 성공적으로 저장된 예측 실행
        latest_run = (
            ForecastRun.objects
            .filter(
                store=store,
                status=ForecastRun.Status.COMPLETED,
            )
            .order_by("-generated_at", "-pk")
            .first()
        )

        today_forecast = None

        if latest_run is not None:
            today_forecast = (
                ForecastValue.objects
                .filter(
                    run=latest_run,
                    series_key="daily:sales",
                    granularity=ForecastValue.Granularity.DAILY,
                    metric=ForecastValue.Metric.SALES,
                    target_date=today,
                )
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
                latest_run.pk if latest_run else None
            ),
            "forecast_status": (
                "AVAILABLE"
                if today_forecast else "UNAVAILABLE"
            ),
        })

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

        if latest is None:
            return Response({
                "store_id": store.pk,
                "start": None,
                "end": None,
                "days_with_data": 0,
                "weekday": [],
                "hourly": [],
            })

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

        # 62 days covers the previous month's matching range plus both weeks.
        daily = queries.daily_totals(
            store,
            as_of - timedelta(days=62),
            as_of,
        )

        result = analytics.compare(daily, as_of)
        result["store_id"] = store.pk

        return Response(result)


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


class NextDaySalesForecastView(ForecastView):
    """GET /sales/stores/<store_id>/forecast/next-day/"""

    def get(self, request, store_id):
        store = self.get_store(store_id)
        params = self.parse(AsOfSerializer, request)

        result = self.run_forecast(
            store,
            self.resolve_as_of(store, params),
        )

        target_date = result["target_dates"][0]
        values = result["values"]

        sales = _forecast_value(
            values, "DAILY", "SALES", target_date
        )
        orders = _forecast_value(
            values, "DAILY", "ORDERS", target_date
        )
        quantity = _forecast_value(
            values, "DAILY", "QUANTITY", target_date
        )

        if sales is None or orders is None:
            raise serializers.ValidationError({
                "detail": "다음 날 매출 및 주문 수 예측값을 생성하지 못했습니다."
            })

        return Response({
            "store_id": store.pk,
            "as_of": result["as_of"],
            "target_date": target_date,
            "method": "operational_forecast",
            "predicted_sales": sales["predicted_value"],
            "predicted_order_count": orders["predicted_value"],
            "predicted_quantity": (
                quantity["predicted_value"] if quantity else None
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

        result = self.run_forecast(
            store,
            self.resolve_as_of(store, params),
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
                item["expected_quantity"] for item in menus
            ),
            "menus": menus,
            "forecast_run_id": result["run_id"],
        })


class SevenDayForecastView(ForecastView):
    """GET: 예측 계산 / POST: 새 예측 생성 및 저장"""

    def get(self, request, store_id):
        store = self.get_store(store_id)
        params = self.parse(AsOfSerializer, request)

        result = self.run_forecast(
            store,
            self.resolve_as_of(store, params),
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
            run = get_object_or_404(
                runs,
                pk=params["run_id"],
            )
        else:
            run = runs.order_by(
                "-generated_at",
                "-pk",
            ).first()

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
        params = self.parse(
            ForecastRunQuerySerializer,
            request,
        )

        runs = ForecastRun.objects.filter(
            store=store,
            status=ForecastRun.Status.COMPLETED,
        )

        run_id = params.get("run_id")

        if run_id:
            run = get_object_or_404(runs, pk=run_id)
        else:
            run = runs.order_by(
                "-generated_at",
                "-pk",
            ).first()

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

        # Do not compare dates that have not yet occurred.
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

        # --------------------------------------------------
        # Daily actuals: sales and orders
        # --------------------------------------------------
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

        # --------------------------------------------------
        # Daily actuals: total item quantity
        # --------------------------------------------------
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

        # --------------------------------------------------
        # Hourly actuals: sales and orders
        # --------------------------------------------------
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
            hourly_actual[
                (item["day"], item["hour"])
            ] = {
                "SALES": int(item["sales"] or 0),
                "ORDERS": int(item["orders"] or 0),
            }

        # On dates with actual sales data, fill missing operating hours
        # with zero sales and zero orders.
        for day in daily_actual:
            for hour in range(8, 22):
                hourly_actual.setdefault(
                    (day, hour),
                    {
                        "SALES": 0,
                        "ORDERS": 0,
                    },
                )

        # --------------------------------------------------
        # Menu actuals: preserve HOT / ICE / UNKNOWN separately.
        # --------------------------------------------------
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
            menu_actual[
                (
                    item["day"],
                    item["menu_id"],
                    item["serving_temperature"],
                )
            ] = int(item["quantity"] or 0)

        # --------------------------------------------------
        # Compare predictions with actuals
        # --------------------------------------------------
        comparisons = []
        metric_pairs = {}

        for row in eligible:
            actual = None

            if row.granularity == ForecastValue.Granularity.DAILY:
                actual = daily_actual.get(
                    row.target_date, {}
                ).get(row.metric)

            elif row.granularity == ForecastValue.Granularity.HOURLY:
                actual = hourly_actual.get(
                    (row.target_date, row.target_hour), {}
                ).get(row.metric)

            elif row.granularity == ForecastValue.Granularity.MENU:
                menu_key = (
                    row.target_date,
                    row.menu_id,
                    row.serving_temperature,
                )

                actual = menu_actual.get(menu_key)

                # No sales record for an active menu means zero sales.
                # Inactive menus without sales records are excluded.
                if (
                    actual is None
                    and row.menu_id
                    and row.menu
                    and row.menu.is_active
                ):
                    actual = 0

            if actual is None:
                continue

            predicted = float(row.predicted_value)
            actual = float(actual)

            key = f"{row.granularity}:{row.metric}"

            metric_pairs.setdefault(
                key, []
            ).append((predicted, actual))

            comparisons.append({
                "series_key": row.series_key,
                "granularity": row.granularity,
                "metric": row.metric,
                "target_date": row.target_date.isoformat(),
                "target_hour": row.target_hour,
                "menu_id": row.menu_id,
                "menu_name": (
                    row.menu.name if row.menu_id else None
                ),
                "serving_temperature": row.serving_temperature,
                "predicted_value": predicted,
                "actual_value": actual,
                "error": round(predicted - actual, 4),
                "absolute_error": round(
                    abs(predicted - actual),
                    4,
                ),
            })

        # --------------------------------------------------
        # Accuracy metrics
        # --------------------------------------------------
        metrics = {
            key: self._metrics(pairs)
            for key, pairs in metric_pairs.items()
        }

        return Response({
            "store_id": store.pk,
            "run_id": run.pk,
            "model_version": run.model_version,
            "as_of": run.as_of.isoformat(),
            "actual_data_through": cutoff.isoformat(),
            "status": (
                "COMPARED"
                if comparisons
                else "NO_MATCHING_ACTUALS"
            ),
            "comparison_count": len(comparisons),
            "metrics": metrics,
            "comparisons": comparisons,
        })
