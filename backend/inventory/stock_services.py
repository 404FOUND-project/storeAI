"""재고 계산 로직 (재고 API와 챗봇이 함께 사용).

재고 부족 기준: Inventory 모델에 안전재고 필드가 없으므로,
"최근 N일 판매량으로 계산한 하루 평균 사용량" 대비 "남은 일수"로 판단한다.
"""
import math
from datetime import timedelta
from decimal import Decimal

from django.db import connection
from django.db.models import Sum
from django.utils import timezone

from sales.models import SalesItem

from .models import MenuIngredient

USAGE_WINDOW_DAYS = 14   # 하루 평균 사용량 계산에 쓰는 최근 일수
DANGER_DAYS = 1          # 남은 일수가 이 값 미만이면 danger
LOW_DAYS = 3             # 남은 일수가 이 값 미만이면 low
EXPIRING_DAYS = 3        # 유통기한이 이 일수 이내면 expiring


def _recipe_usage(store, window):
    """팀원 레시피 표(inventory_recipe/recipeitem)로 계산. 표가 없으면 None.

    기준일은 매장의 가장 최근 판매일(주문 데이터가 오래됐어도 계산되게 함).
    """
    if "inventory_recipeitem" not in connection.introspection.table_names():
        return None
    with connection.cursor() as c:
        c.execute("SELECT MAX(sold_at) FROM sales_sales WHERE store_id=%s", [store.id])
        last = c.fetchone()[0]
        if last is None:
            return {}
        since = last - timedelta(days=window)
        c.execute(
            """SELECT i.menu_id, COALESCE(i.serving_temperature,'STANDARD'), SUM(i.quantity)
               FROM sales_salesitem i JOIN sales_sales s ON s.id=i.sales_id
               WHERE s.store_id=%s AND s.sold_at>=%s GROUP BY 1,2""", [store.id, since])
        sold = c.fetchall()
        c.execute("SELECT id, menu_id, variant, yield_quantity FROM inventory_recipe WHERE is_active=1")
        recipes = {(m, v): (rid, y) for rid, m, v, y in c.fetchall()}
        c.execute("SELECT recipe_id, ingredient_id, quantity_base FROM inventory_recipeitem")
        items = {}
        for rid, ing, qty in c.fetchall():
            items.setdefault(rid, []).append((ing, qty))
        c.execute("SELECT id, ingredient_id FROM inventory_inventory WHERE store_id=%s AND ingredient_id IS NOT NULL", [store.id])
        inv_of = {ing: inv for inv, ing in c.fetchall()}
    usage = {}
    for menu_id, temp, qty in sold:
        rid, y = recipes.get((menu_id, temp)) or recipes.get((menu_id, "STANDARD")) or (None, 1)
        for ing, per in items.get(rid, []):
            inv = inv_of.get(ing)
            if inv:
                usage[inv] = usage.get(inv, Decimal(0)) + Decimal(qty) * Decimal(per) / Decimal(y or 1) / window
    return usage


def daily_usage_by_inventory(store, today=None, window=USAGE_WINDOW_DAYS):
    """재고 ID -> 하루 평균 사용량(Decimal). 판매 기록 x 메뉴별 레시피 사용량으로 계산."""
    recipe_usage = _recipe_usage(store, window)
    if recipe_usage is not None:
        return recipe_usage
    today = today or timezone.localdate()
    since = today - timedelta(days=window)
    sold = {
        r["menu_id"]: r["q"]
        for r in SalesItem.objects.filter(
            sales__store=store, sales__sold_at__date__gte=since,
        ).values("menu_id").annotate(q=Sum("quantity"))
    }
    usage = {}
    for mi in MenuIngredient.objects.filter(menu__store=store):
        q = sold.get(mi.menu_id, 0)
        if q:
            usage[mi.inventory_id] = (
                usage.get(mi.inventory_id, Decimal(0))
                + Decimal(q) * mi.required_quantity / window
            )
    return usage


def stock_status(quantity, per_day):
    """(남은 일수, 재고 상태) 반환."""
    if not per_day or per_day <= 0:
        return None, "no_usage"
    days_left = float(Decimal(quantity) / per_day)
    if days_left < DANGER_DAYS:
        return days_left, "danger"
    if days_left < LOW_DAYS:
        return days_left, "low"
    return days_left, "ok"


def expiry_status(expiration_date, today=None):
    """(유통기한까지 남은 일수, 유통기한 상태) 반환."""
    if expiration_date is None:
        return None, "none"
    today = today or timezone.localdate()
    days = (expiration_date - today).days
    if days < 0:
        return days, "expired"
    if days <= EXPIRING_DAYS:
        return days, "expiring"
    return days, "ok"


def recommend_order(inv, per_day, target_days, today=None, series=None):
    """권장 발주량 계산.

    필요량 = 하루 사용량 x min(목표 일수, 유통기한까지 남은 일수) - 현재 재고
    유통기한 안에 다 못 쓸 양은 발주하지 않도록 상한을 둔다.
    series 가 있으면(A의 예측: 날짜별 예상 사용량 목록) 목표 기간(cover일)만큼 앞에서부터 합산해 필요량으로 쓴다.
    예측이 cover일보다 짧으면 모자란 날은 per_day 로 채운다. series 가 없으면 per_day x cover (14일 평균 fallback).
    """
    days_left, _ = stock_status(inv.quantity, per_day)
    exp_days, exp_state = expiry_status(inv.expiration_date, today)
    if not per_day or per_day <= 0:
        return Decimal(0), "사용 기록이 없어 발주량을 계산하지 않았습니다."
    cover = target_days
    note = f"{target_days}일치 확보 기준"
    if exp_days is not None and exp_days < cover:
        cover = max(exp_days, 0)
        note = f"유통기한({exp_days}일 남음) 안에 쓸 수 있는 양까지만 계산"
    if series:
        used = series[:cover]
        total = sum(used, Decimal(0)) + per_day * Decimal(max(cover - len(used), 0))
        note += f" (예측 {len(used)}일 합산" + (f" + 부족한 {cover - len(used)}일은 평균으로 보충)" if len(used) < cover else ")")
        need = total - inv.quantity
    else:
        need = per_day * Decimal(cover) - inv.quantity
    qty = Decimal(math.ceil(need)) if need > 0 else Decimal(0)
    if qty == 0:
        note = "현재 재고로 충분합니다. " + note
    return qty, note


def usage_series_from_forecast(store, forecast):
    """A의 메뉴별 예상 판매량 -> 재고 ID별 '날짜별 예상 사용량' 목록(날짜 오름차순, Decimal).

    forecast: 예측 결과 목록. 항목 형식(A와 확정 예정, 아래는 현재 가정)
      {"menu_id", "base_date", "target_date", "predicted_quantity_hot", "predicted_quantity_ice"}  (A 제안 형식) 또는
      {"menu_id": 2 또는 "pos_code": "...", "target_date": "2026-11-18",
       "quantity": 120, "serving_temperature": "HOT"/"ICE"(선택), "base_date": "2026-11-17"(선택)}
    - HOT/ICE가 있으면 그 온도의 레시피를 쓰고, 없으면 STANDARD, 그것도 없으면 있는 레시피를 씁니다.
    - 같은 날짜의 여러 행(온도별 등)은 합산합니다. 평균은 내지 않습니다.
    - 발주 목표 기간 합산은 recommend_order(series=...)가 합니다.
    """
    if not forecast:
        return {}
    with connection.cursor() as c:
        c.execute("SELECT id, pos_code FROM store_menu WHERE store_id=%s", [store.id])
        by_pos = {pos: mid for mid, pos in c.fetchall() if pos}
        c.execute("SELECT id, menu_id, variant FROM inventory_recipe WHERE is_active=1")
        recipes = {}
        for rid, mid, variant in c.fetchall():
            recipes[(mid, variant)] = rid
        c.execute("SELECT recipe_id, ingredient_id, quantity_base FROM inventory_recipeitem")
        items = {}
        for rid, ing, qty in c.fetchall():
            items.setdefault(rid, []).append((ing, qty))
        c.execute("SELECT id, ingredient_id FROM inventory_inventory WHERE store_id=%s AND ingredient_id IS NOT NULL", [store.id])
        inv_of = {ing: inv for inv, ing in c.fetchall()}

    def recipe_for(menu_id, temp):
        for variant in (temp, "STANDARD"):
            if variant and (menu_id, variant) in recipes:
                return recipes[(menu_id, variant)]
        return next((rid for (m, _), rid in recipes.items() if m == menu_id), None)

    # A가 주는 형식(predicted_quantity_hot / predicted_quantity_ice)을 온도별 행으로 펼침
    rows = []
    for row in forecast:
        if "predicted_quantity_hot" in row or "predicted_quantity_ice" in row:
            for temp, key in (("HOT", "predicted_quantity_hot"), ("ICE", "predicted_quantity_ice")):
                if row.get(key):
                    rows.append({**row, "quantity": row[key], "serving_temperature": temp})
        else:
            rows.append(row)

    per_date = {}  # inv_id -> {date: usage}
    for row in rows:
        menu_id = row.get("menu_id") or by_pos.get(row.get("pos_code"))
        if menu_id is None:
            continue
        qty = Decimal(str(row.get("quantity") or 0))
        day = str(row.get("target_date"))
        for ing, per in items.get(recipe_for(menu_id, row.get("serving_temperature")), []):
            inv = inv_of.get(ing)
            if inv:
                d = per_date.setdefault(inv, {})
                d[day] = d.get(day, Decimal(0)) + qty * Decimal(per)
    return {inv: [d[k] for k in sorted(d)] for inv, d in per_date.items()}


def forecast_usage(store):
    """A의 예측(sales_forecast 표)으로 만든 {재고 ID: 날짜별 예상 사용량 목록}.

    매장 메뉴의 '가장 최근 base_date' 예측만 사용하고, 오늘 이후 날짜만 씁니다.
    예측이 없으면 None -> 호출한 쪽이 14일 평균(daily_usage_by_inventory)을 임시 fallback으로 씁니다.
    """
    from django.utils import timezone

    from sales.models import SalesForecast

    qs = SalesForecast.objects.filter(menu__store=store)
    latest = qs.order_by("-base_date").values_list("base_date", flat=True).first()
    if latest is None:
        return None
    rows = qs.filter(base_date=latest, target_date__gt=latest).values(
        "menu_id", "base_date", "target_date", "predicted_quantity_hot", "predicted_quantity_ice")
    series = usage_series_from_forecast(store, [
        {**r, "base_date": str(r["base_date"]), "target_date": str(r["target_date"])} for r in rows])
    return series or None
