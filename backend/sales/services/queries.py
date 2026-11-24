
"""Read-only database access for sales analysis and forecasting.

Every date here is a calendar date in the project time zone (TIME_ZONE, KST),
never UTC: an order sold at 23:30 KST belongs to that KST day.
"""
from collections import defaultdict
from datetime import datetime, time, timedelta

from django.db.models import Count, Max, Sum
from django.db.models.functions import ExtractHour, TruncDate
from django.utils import timezone

from sales.models import Sales, SalesItem


def _bounds(start, end):
    """Inclusive local dates -> aware half-open [lo, hi) datetimes."""
    tz = timezone.get_current_timezone()
    lo = datetime.combine(start, time.min, tzinfo=tz) if start else None
    hi = datetime.combine(end + timedelta(days=1), time.min, tzinfo=tz) if end else None
    return lo, hi


def _sales_qs(store, start=None, end=None):
    qs = Sales.objects.filter(store=store)
    lo, hi = _bounds(start, end)
    if lo is not None:
        qs = qs.filter(sold_at__gte=lo)
    if hi is not None:
        qs = qs.filter(sold_at__lt=hi)
    return qs


def latest_sales_date(store):
    """Local date of the store's most recent sale, or None when it has none."""
    latest = Sales.objects.filter(store=store).aggregate(m=Max("sold_at"))["m"]
    return timezone.localtime(latest).date() if latest else None


def daily_totals(store, start=None, end=None):
    """{date: {"sales": int, "orders": int}} for days that have at least one order."""
    rows = (
        _sales_qs(store, start, end)
        .annotate(day=TruncDate("sold_at"))
        .values("day")
        .annotate(sales=Sum("total_amount"), orders=Count("id"))
        .order_by("day")
    )
    return {r["day"]: {"sales": int(r["sales"] or 0), "orders": r["orders"]} for r in rows}


def hourly_totals(store, start=None, end=None):
    """{hour(0-23): {"sales": int, "orders": int}} summed over the range."""
    rows = (
        _sales_qs(store, start, end)
        .annotate(hour=ExtractHour("sold_at"))
        .values("hour")
        .annotate(sales=Sum("total_amount"), orders=Count("id"))
        .order_by("hour")
    )
    return {r["hour"]: {"sales": int(r["sales"] or 0), "orders": r["orders"]} for r in rows}


def menu_daily_quantities(store, start=None, end=None):
    """({menu_id: {date: quantity}}, {menu_id: name}) from order lines."""
    qs = SalesItem.objects.filter(sales__store=store)
    lo, hi = _bounds(start, end)
    if lo is not None:
        qs = qs.filter(sales__sold_at__gte=lo)
    if hi is not None:
        qs = qs.filter(sales__sold_at__lt=hi)
    rows = (
        qs.annotate(day=TruncDate("sales__sold_at"))
        .values("menu_id", "menu__name", "day")
        .annotate(qty=Sum("quantity"))
    )
    daily = defaultdict(dict)
    names = {}
    for r in rows:
        daily[r["menu_id"]][r["day"]] = int(r["qty"] or 0)
        names[r["menu_id"]] = r["menu__name"]
    return dict(daily), names
