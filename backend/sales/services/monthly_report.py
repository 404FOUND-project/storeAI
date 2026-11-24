import csv
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path

from django.db.models import Avg, Count, F, Sum
from django.db.models.functions import ExtractHour, ExtractWeekDay, TruncDate
from django.utils import timezone

from sales.models import Sales, SalesItem, ForecastValue
from review.models import Review


def month_bounds(year, month):
    start = date(year, month, 1)
    end = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    return start, end


def aware_bounds(start, end):
    return (
        timezone.make_aware(datetime.combine(start, time.min)),
        timezone.make_aware(datetime.combine(end, time.min)),
    )


def sales_daily(store, start, end):
    lower, upper = aware_bounds(start, end)
    rows = (
        Sales.objects.filter(store=store, sold_at__gte=lower, sold_at__lt=upper)
        .annotate(day=TruncDate("sold_at"))
        .values("day")
        .annotate(sales=Sum("total_amount"), orders=Count("id"))
        .order_by("day")
    )
    return {
        row["day"]: {
            "sales": int(row["sales"] or 0),
            "orders": int(row["orders"] or 0),
        }
        for row in rows
    }


def menu_summary(store, start, end):
    lower, upper = aware_bounds(start, end)
    rows = list(
        SalesItem.objects.filter(
            sales__store=store,
            sales__sold_at__gte=lower,
            sales__sold_at__lt=upper,
        )
        .values("menu_id", "menu__name")
        .annotate(
            total_quantity=Sum("quantity"),
            revenue=Sum(F("quantity") * F("unit_price")),
        )
        .order_by("-revenue")
    )
    total = sum(int(row["revenue"] or 0) for row in rows)
    items = [
        {
            "menu_id": row["menu_id"],
            "menu_name": row["menu__name"] or "삭제된 메뉴",
            "quantity": int(row["total_quantity"] or 0),
            "revenue": int(row["revenue"] or 0),
            "share_percent": round(int(row["revenue"] or 0) / total * 100, 1) if total else None,
        }
        for row in rows
    ]
    return {
        "items": items,
        "top": items[:5],
        "low": sorted(items, key=lambda item: item["revenue"])[:5],
        "total_item_revenue": total,
    }


def patterns(store, start, end):
    lower, upper = aware_bounds(start, end)
    qs = Sales.objects.filter(store=store, sold_at__gte=lower, sold_at__lt=upper)
    weekday_names = {
        1: "일요일", 2: "월요일", 3: "화요일", 4: "수요일",
        5: "목요일", 6: "금요일", 7: "토요일",
    }
    weekdays = (
        qs.annotate(day=ExtractWeekDay("sold_at"))
        .values("day")
        .annotate(sales=Sum("total_amount"), orders=Count("id"))
        .order_by("day")
    )
    hours = (
        qs.annotate(hour=ExtractHour("sold_at"))
        .values("hour")
        .annotate(sales=Sum("total_amount"), orders=Count("id"))
        .order_by("hour")
    )
    return {
        "weekday": [
            {"weekday": weekday_names.get(r["day"], "기타"),
             "sales": int(r["sales"] or 0), "orders": r["orders"]}
            for r in weekdays
        ],
        "hourly": [
            {"hour": r["hour"], "sales": int(r["sales"] or 0), "orders": r["orders"]}
            for r in hours
        ],
    }


def forecast_summary(store, start, end, actuals):
    rows = (
        ForecastValue.objects.filter(
            run__store=store,
            run__status="COMPLETED",
            granularity="DAILY",
            metric="SALES",
            target_date__gte=start,
            target_date__lt=end,
            run__as_of__lt=F("target_date"),
        )
        .values("target_date", "predicted_value", "run_id", "run__generated_at")
        .order_by("target_date", "-run__generated_at")
    )
    selected = {}
    for row in rows:
        selected.setdefault(row["target_date"], row)

    items = []
    for day, row in selected.items():
        if day not in actuals:
            continue
        predicted = float(row["predicted_value"])
        actual = actuals[day]["sales"]
        items.append({
            "date": day.isoformat(),
            "predicted_sales": round(predicted, 1),
            "actual_sales": actual,
            "absolute_error": round(abs(predicted - actual), 1),
            "run_id": row["run_id"],
        })

    if not items:
        return {
            "status": "NO_DATA", "sample_count": 0, "items": [],
            "message": "해당 월에 비교 가능한 저장 예측이 없습니다. 새 예측은 실행하지 않았습니다.",
        }

    error = sum(item["absolute_error"] for item in items)
    actual_total = sum(item["actual_sales"] for item in items)
    return {
        "status": "AVAILABLE",
        "sample_count": len(items),
        "mae": round(error / len(items), 1),
        "wape_percent": round(error / actual_total * 100, 1) if actual_total else None,
        "items": items,
    }


def review_summary(store, start, end):
    lower, upper = aware_bounds(start, end)
    qs = Review.objects.filter(
        store=store, source="DUMMY",
        reviewed_at__gte=lower, reviewed_at__lt=upper,
    )
    stats = qs.aggregate(count=Count("id"), average=Avg("rating"))
    sentiments = {
        row["sentiment"]: row["count"]
        for row in qs.values("sentiment").annotate(count=Count("id"))
    }
    categories = [
        {"category": row["category"], "count": row["count"]}
        for row in qs.exclude(category="").values("category")
        .annotate(count=Count("id")).order_by("-count")
    ]
    keywords = Counter()
    for value in qs.values_list("keywords", flat=True):
        if isinstance(value, list):
            keywords.update(str(v).strip() for v in value if str(v).strip())

    return {
        "status": "AVAILABLE" if stats["count"] else "NO_DATA",
        "review_count": stats["count"],
        "average_rating": round(float(stats["average"]), 1) if stats["average"] is not None else None,
        "sentiment_counts": sentiments,
        "category_counts": categories,
        "top_keywords": [
            {"keyword": key, "count": count}
            for key, count in keywords.most_common(10)
        ],
        "notice": "더미(테스트) 리뷰 기준이며 실제 고객 의견이나 만족도를 의미하지 않습니다.",
    }


def weather_summary(store, start, end, actuals):
    try:
        from weatherdata.models import WeatherDatum
    except ImportError:
        return {"status": "NO_DATA", "observed_daily_averages": {}}

    lower, upper = aware_bounds(start, end)
    rows = WeatherDatum.objects.filter(
        collection_run__location__store=store,
        collection_run__source_type="observed",
        collection_run__dataset_type="asos_daily",
        collection_run__status="succeeded",
        valid_at__gte=lower,
        valid_at__lt=upper,
        quality_status="valid",
        value_numeric__isnull=False,
    ).values("valid_at", "variable", "value_numeric")

    values = defaultdict(list)
    daily = defaultdict(dict)
    for row in rows:
        day = timezone.localtime(row["valid_at"]).date()
        variable = row["variable"]
        number = float(row["value_numeric"])
        values[variable].append(number)
        daily[day][variable] = number

    averages = {
        key: round(sum(nums) / len(nums), 2)
        for key, nums in values.items() if nums
    }
    correlations = {}
    for variable in ("avg_temperature", "precipitation", "precipitation_amount"):
        matched = [
            (daily[day][variable], actuals[day]["sales"])
            for day in daily if variable in daily[day] and day in actuals
        ]
        if len(matched) >= 3:
            xs, ys = zip(*matched)
            mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
            dx = sum((x - mx) ** 2 for x in xs) ** 0.5
            dy = sum((y - my) ** 2 for y in ys) ** 0.5
            correlations[variable] = (
                round(sum((x - mx) * (y - my) for x, y in matched) / (dx * dy), 3)
                if dx and dy else None
            )

    return {
        "status": "AVAILABLE" if averages else "NO_DATA",
        "observed_daily_averages": averages,
        "sales_correlations": correlations,
        "matched_days": len(set(daily) & set(actuals)),
        "notice": "관측 날씨만 사용합니다. 통계적 관계는 인과관계를 의미하지 않습니다.",
    }


def csv_rows(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def calendar_summary(start, end):
    root = Path(__file__).resolve().parents[3]
    holiday_file = root / "data" / "holidays" / "404dabang_holidays.csv"
    academic_file = root / "docs" / "source" / "daily_academic_features.csv"

    holidays = []
    for row in csv_rows(holiday_file):
        raw = row.get("locdate") or row.get("date") or ""
        try:
            day = date.fromisoformat(raw[:10]) if "-" in raw else datetime.strptime(raw, "%Y%m%d").date()
        except ValueError:
            continue
        if start <= day < end and row.get("isHoliday", "").lower() in ("true", "1", "y"):
            holidays.append({
                "date": day.isoformat(),
                "name": row.get("dateName", ""),
                "classification": row.get("holiday_classification", ""),
            })

    academic = []
    for row in csv_rows(academic_file):
        try:
            day = date.fromisoformat(row.get("date", "")[:10])
        except ValueError:
            continue
        if start <= day < end:
            signals = {
                key: value for key, value in row.items()
                if key not in ("date",) and value not in ("", "0", "False", "false")
            }
            if signals:
                academic.append({"date": day.isoformat(), "signals": signals})

    return {"holidays": holidays, "academic_calendar": academic}


def build_monthly_report(store, year, month):
    start, end = month_bounds(year, month)
    previous_start = (start - timedelta(days=1)).replace(day=1)
    actuals = sales_daily(store, start, end)
    previous = sales_daily(store, previous_start, start)

    total = sum(row["sales"] for row in actuals.values())
    orders = sum(row["orders"] for row in actuals.values())
    previous_total = sum(row["sales"] for row in previous.values())
    previous_orders = sum(row["orders"] for row in previous.values())

    def change(current, old):
        return round((current - old) / old * 100, 1) if old else None

    sales = {
        "total_sales": total,
        "order_count": orders,
        "average_ticket": round(total / orders) if orders else None,
        "recorded_sales_days": len(actuals),
        "previous_month_sales": previous_total,
        "previous_month_order_count": previous_orders,
        "sales_change_percent": change(total, previous_total),
        "order_change_percent": change(orders, previous_orders),
        "daily": [
            {"date": day.isoformat(), **row}
            for day, row in sorted(actuals.items())
        ],
        "patterns": patterns(store, start, end),
        "notice": "매출 기록이 없는 날짜는 휴무일 또는 0원 매출로 간주하지 않습니다.",
    }

    menus = menu_summary(store, start, end)
    forecast = forecast_summary(store, start, end, actuals)
    reviews = review_summary(store, start, end)
    weather = weather_summary(store, start, end, actuals)
    calendar = calendar_summary(start, end)

    insights = []
    if menus["top"]:
        top = menus["top"][0]
        insights.append({
            "type": "FACT",
            "title": "매출 상위 메뉴",
            "detail": f'{top["menu_name"]}: {top["revenue"]:,}원',
        })
    if forecast["status"] == "NO_DATA":
        insights.append({
            "type": "LIMITATION",
            "title": "예측 성과 평가 불가",
            "detail": forecast["message"],
        })
    if reviews["status"] == "AVAILABLE":
        insights.append({
            "type": "LIMITATION",
            "title": "리뷰 데이터 기준",
            "detail": f'월간 더미 리뷰 {reviews["review_count"]}건 기준입니다.',
        })

    return {
        "store_id": store.id,
        "store_name": store.name,
        "year": year,
        "month": month,
        "period_start": start.isoformat(),
        "period_end": (end - timedelta(days=1)).isoformat(),
        "sales": sales,
        "menus": menus,
        "forecast": forecast,
        "reviews": reviews,
        "weather": weather,
        "calendar": calendar,
        "insights": insights,
    }
