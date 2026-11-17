"""메뉴별 원가·마진·판매량·인기 순위 계산 (팀원 더미 데이터 테이블을 읽기만 함)."""
from datetime import timedelta

from django.db import connection
from django.utils import timezone


def _rows(sql, params=()):
    with connection.cursor() as c:
        c.execute(sql, params)
        return c.fetchall()


def menu_profitability(store_id, days=None):
    # 메뉴·변형(STANDARD/HOT/ICE)별 최신 원가
    cost = {}
    for menu_id, variant, final_cost in _rows(
        """SELECT s.menu_id, r.variant, s.final_cost
           FROM inventory_recipecostsnapshot s
           JOIN inventory_recipe r ON r.id = s.recipe_id
           WHERE s.status='COMPLETE' ORDER BY s.as_of"""
    ):
        cost[(menu_id, variant)] = float(final_cost)

    sql = """SELECT i.menu_id, COALESCE(i.serving_temperature,'STANDARD'),
                    SUM(i.quantity), SUM(i.quantity*i.unit_price)
             FROM sales_salesitem i JOIN sales_sales s ON s.id=i.sales_id
             WHERE s.store_id=%s"""
    params = [store_id]
    if days:
        sql += " AND s.sold_at >= %s"
        params.append(timezone.now() - timedelta(days=days))
    sql += " GROUP BY 1,2"

    menus = {
        m: {"menu_id": m, "name": n, "price": p, "quantity": 0, "revenue": 0, "cost_total": 0.0, "no_cost_qty": 0}
        for m, n, p in _rows("SELECT id, name, price FROM store_menu WHERE store_id=%s", [store_id])
    }
    for menu_id, variant, qty, revenue in _rows(sql, params):
        if menu_id not in menus:
            continue
        m = menus[menu_id]
        unit = cost.get((menu_id, variant), cost.get((menu_id, "STANDARD")))
        m["quantity"] += int(qty)
        m["revenue"] += int(revenue)
        if unit is None:
            m["no_cost_qty"] += int(qty)
        else:
            m["cost_total"] += unit * int(qty)

    result = []
    for m in menus.values():
        known_qty = m["quantity"] - m["no_cost_qty"]
        has_cost = known_qty > 0
        profit = m["revenue"] - m["cost_total"] if has_cost and not m["no_cost_qty"] else None
        result.append({
            "menu_id": m["menu_id"], "name": m["name"], "price": m["price"],
            "quantity": m["quantity"], "revenue": m["revenue"],
            "avg_unit_cost": round(m["cost_total"] / known_qty) if has_cost else None,
            "cost_total": round(m["cost_total"]) if has_cost else None,
            "profit": round(profit) if profit is not None else None,
            "margin_rate": round(profit / m["revenue"] * 100, 1) if profit is not None and m["revenue"] else None,
        })
    result.sort(key=lambda x: x["quantity"], reverse=True)
    for rank, r in enumerate(result, 1):
        r["popularity_rank"] = rank
    return result
