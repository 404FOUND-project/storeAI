
"""Rule-based daily store operation insights."""
from sales.services import queries


def _build_review_metrics(store, target_date):
    """Return dummy-review rating metrics for the target day or last 30 days."""
    from datetime import timedelta

    from django.db.models import Avg, Count
    from review.models import Review

    base = Review.objects.filter(store=store, source="DUMMY")
    target_reviews = base.filter(reviewed_at__date=target_date)

    if target_reviews.exists():
        reviews = target_reviews
        period = "TARGET_DATE"
    else:
        start_date = target_date - timedelta(days=29)
        reviews = base.filter(
            reviewed_at__date__gte=start_date,
            reviewed_at__date__lte=target_date,
        )
        period = "LAST_30_DAYS"

    result = reviews.aggregate(
        average_rating=Avg("rating"),
        review_count=Count("id"),
    )

    average = result["average_rating"]
    return {
        "review_average_rating": (
            round(float(average), 1) if average is not None else None
        ),
        "review_count": result["review_count"],
        "review_period": period,
    }


def build_daily_insights(store, target_date, daily):
    """Build a concise operational diagnosis using existing sales data."""
    from datetime import timedelta

    previous_date = target_date - timedelta(days=7)
    current = daily.get(target_date)
    previous = daily.get(previous_date)
    review_metrics = _build_review_metrics(store, target_date)

    if not current:
        return {
            "status": "INSUFFICIENT_DATA",
            "summary": "어제 매출 기록이 없어 운영 상태를 진단하기 어려워요.",
            "strengths": [],
            "cautions": ["어제 매출 데이터가 확인되지 않았어요."],
            "recommendations": [
                "매출 데이터가 정상적으로 등록되었는지 확인해 주세요."
            ],
            "metrics": {
                "sales": None,
                "sales_change_percent": None,
                "orders": None,
                **review_metrics,
            },
        }

    strengths = []
    cautions = []
    recommendations = []
    sales_change_pct = None

    if previous:
        base_sales = previous["sales"]
        if base_sales > 0:
            sales_change_pct = round(
                (current["sales"] - base_sales) / base_sales * 100, 1
            )

            if sales_change_pct >= 10:
                strengths.append(
                    f"매출이 전주 같은 요일보다 {sales_change_pct}% 증가했어요."
                )
            elif sales_change_pct <= -10:
                cautions.append(
                    f"매출이 전주 같은 요일보다 {abs(sales_change_pct)}% 감소했어요."
                )
                recommendations.append(
                    "매출이 감소한 시간대와 메뉴를 확인해 운영 상황을 점검해 보세요."
                )
            else:
                strengths.append(
                    "매출이 전주 같은 요일과 비슷한 수준을 유지했어요."
                )
        else:
            cautions.append(
                "비교 기준일의 매출이 0원이어서 매출 증감률을 계산하지 않았어요."
            )
    else:
        cautions.append(
            "전주 같은 요일의 매출 데이터가 없어 매출 추세 비교는 제한돼요."
        )

    # Compare menu quantities only when both dates have sales data.
    menu_daily, menu_names = queries.menu_daily_quantities(
        store, previous_date, target_date
    )

    menu_changes = []
    if previous:
        for menu_id, by_date in menu_daily.items():
            before = by_date.get(previous_date, 0)
            now = by_date.get(target_date, 0)
            name = menu_names.get(menu_id, "이름 없는 메뉴")

            if now > before:
                menu_changes.append((now - before, name, before, now))
            elif before >= 2 and now <= before * 0.7:
                menu_changes.append((now - before, name, before, now))

    increased = [item for item in menu_changes if item[0] > 0]
    decreased = [item for item in menu_changes if item[0] < 0]

    if increased:
        _, name, before, now = max(increased)
        strengths.append(
            f"{name} 판매량이 전주 같은 요일보다 {now - before}개 늘었어요."
        )

    if decreased:
        _, name, before, now = min(decreased)
        cautions.append(
            f"{name} 판매량이 전주 같은 요일보다 {before - now}개 줄었어요."
        )
        recommendations.append(
            f"{name}의 판매 추이와 고객 반응을 확인해 보세요."
        )

    # Check hourly concentration. This is a distribution observation,
    # not proof that the concentration caused a sales change.
    hourly = queries.hourly_totals(store, target_date, target_date)
    total_hourly_sales = sum(row["sales"] for row in hourly.values())

    peak_hour = None
    peak_share = None

    if total_hourly_sales > 0:
        peak_hour, peak_row = max(
            hourly.items(), key=lambda item: item[1]["sales"]
        )
        peak_share = round(
            peak_row["sales"] / total_hourly_sales * 100, 1
        )

        if peak_share >= 45:
            cautions.append(
                f"{peak_hour}시 시간대에 하루 매출의 {peak_share}%가 집중됐어요."
            )
            recommendations.append(
                f"{peak_hour}시 전후의 재고와 인력 배치를 미리 점검해 보세요."
            )

    # 실제로 확인된 운영 신호 중 우선순위가 높은 항목을 한 줄 진단으로 제공한다.
    if sales_change_pct is not None and sales_change_pct <= -10:
        summary = (
            f"어제 매출이 전주 같은 요일보다 {abs(sales_change_pct)}% 감소했어요. "
            "매출이 줄어든 시간대와 메뉴를 우선 점검해 보세요."
        )
    elif peak_share is not None and peak_share >= 45:
        summary = (
            f"어제는 {peak_hour}시에 하루 매출의 {peak_share}%가 집중됐어요. "
            "해당 시간대의 재고와 인력 배치를 확인해 보세요."
        )
    elif decreased:
        _, name, before, now = min(decreased)
        summary = (
            f"어제 {name} 판매량이 전주 같은 요일보다 {before - now}개 줄었어요. "
            "판매 추이와 고객 반응을 살펴보세요."
        )
    elif sales_change_pct is not None and sales_change_pct >= 10:
        summary = (
            f"어제 매출이 전주 같은 요일보다 {sales_change_pct}% 증가했어요. "
            "매출 상승에 기여한 메뉴와 시간대를 확인해 보세요."
        )
    elif increased:
        _, name, before, now = max(increased)
        summary = (
            f"어제 {name} 판매량이 전주 같은 요일보다 {now - before}개 늘었어요. "
            "판매 흐름이 이어지는지 살펴보세요."
        )
    elif previous and sales_change_pct is not None:
        summary = (
            f"어제 매출은 {current['sales']:,}원, 주문은 {current['orders']:,}건으로 "
            "전주 같은 요일과 큰 차이 없는 흐름이에요."
        )
    else:
        summary = (
            f"어제 매출은 {current['sales']:,}원, 주문은 {current['orders']:,}건이에요. "
            "전주 같은 요일 비교 데이터가 없어 추세 판단은 보류했어요."
        )

    if not recommendations:
        recommendations.append(
            "현재 확인된 데이터에서 특별한 운영 조정 신호는 나타나지 않았어요."
        )

    status = "AVAILABLE" if previous else "PARTIAL"

    return {
        "status": status,
        "summary": summary,
        "strengths": strengths,
        "cautions": cautions,
        "recommendations": recommendations,
        "metrics": {
            "sales": current["sales"],
            "sales_change_percent": sales_change_pct,
            "orders": current["orders"],
            **review_metrics,
            "previous_weekday_sales": (
                previous["sales"] if previous else None
            ),
            "peak_hour": peak_hour,
            "peak_hour_sales_share_percent": peak_share,
        },
    }

