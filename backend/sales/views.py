from datetime import timedelta

from django.db.models import Count, Max, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import permissions
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView

from store.utils import get_my_store

from .models import Sales, SalesForecast


class SalesSeriesView(APIView):
    """Owner-scoped daily sales summary used by the Flutter home and sales pages."""

    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, store_id):
        store = get_my_store(request, store_id)
        end = timezone.localdate()
        start = end - timedelta(days=29)
        rows = list(
            Sales.objects.filter(
                store=store,
                sold_at__date__gte=start,
                sold_at__date__lte=end,
            )
            .annotate(day=TruncDate("sold_at"))
            .values("day")
            .annotate(sales=Sum("total_amount"), order_count=Count("id"))
            .order_by("day")
        )
        by_day = {row["day"]: row for row in rows}
        series = []
        cursor = start
        while cursor <= end:
            row = by_day.get(cursor)
            series.append({
                "period_start": cursor.isoformat(),
                "sales": int(row["sales"] or 0) if row else 0,
                "order_count": int(row["order_count"] or 0) if row else 0,
            })
            cursor += timedelta(days=1)

        total_sales = sum(int(row["sales"] or 0) for row in rows)
        total_orders = sum(int(row["order_count"] or 0) for row in rows)
        return Response({
            "store_id": store.pk,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "summary": {
                "sales": total_sales,
                "order_count": total_orders,
                "average_ticket": round(total_sales / total_orders) if total_orders else 0,
                "days_with_data": sum(1 for row in rows if row["sales"]),
            },
            "series": series,
        })


class SavedSalesForecastView(APIView):
    """Return the latest persisted menu forecast for the authenticated store."""

    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, store_id):
        store = get_my_store(request, store_id)
        try:
            days = int(request.query_params.get("days", 7))
        except (TypeError, ValueError):
            days = 7
        days = max(1, min(days, 31))

        today = timezone.localdate()
        latest_base_date = SalesForecast.objects.filter(
            menu__store=store,
            base_date__lte=today,
        ).aggregate(value=Max("base_date"))["value"]

        if latest_base_date is None:
            return Response({
                "store_id": store.pk,
                "base_date": None,
                "days": days,
                "summary": {"predicted_quantity": 0},
                "series": [],
                "results": [],
            })

        end_date = today + timedelta(days=days - 1)
        rows = list(
            SalesForecast.objects.filter(
                menu__store=store,
                base_date=latest_base_date,
                target_date__gte=today,
                target_date__lte=end_date,
            )
            .select_related("menu")
            .order_by("target_date", "menu__name")
        )

        results = []
        daily = {}
        for row in rows:
            quantity = row.predicted_quantity_hot + row.predicted_quantity_ice
            results.append({
                "menu_id": row.menu_id,
                "menu_name": row.menu.name,
                "target_date": row.target_date.isoformat(),
                "predicted_quantity_hot": row.predicted_quantity_hot,
                "predicted_quantity_ice": row.predicted_quantity_ice,
                "predicted_quantity": quantity,
            })
            daily[row.target_date] = daily.get(row.target_date, 0) + quantity

        series = [
            {"date": day.isoformat(), "predicted_quantity": daily.get(day, 0)}
            for day in (today + timedelta(days=offset) for offset in range(days))
        ]
        return Response({
            "store_id": store.pk,
            "base_date": latest_base_date.isoformat(),
            "days": days,
            "summary": {
                "predicted_quantity": sum(item["predicted_quantity"] for item in results),
            },
            "series": series,
            "results": results,
        })
