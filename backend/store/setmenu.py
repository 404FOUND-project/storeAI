"""세트 메뉴 추천: 주문(장바구니)에서 자주 같이 팔리는 메뉴 쌍을 Apriori 방식으로 분석."""
from collections import Counter, defaultdict
from itertools import combinations

from django.db import connection

SET_DISCOUNT = 500  # 세트 할인 금액(원)


def recommend_sets(store_id, top=10, min_support=0.002, min_lift=1.0):
    baskets = defaultdict(set)
    with connection.cursor() as c:
        c.execute(
            """SELECT i.sales_id, i.menu_id FROM sales_salesitem i
               JOIN sales_sales s ON s.id=i.sales_id WHERE s.store_id=%s""", [store_id])
        for sid, mid in c.fetchall():
            baskets[sid].add(mid)
        c.execute("SELECT id, name, price FROM store_menu WHERE store_id=%s", [store_id])
        menus = {m: (n, p) for m, n, p in c.fetchall()}

    all_orders = len(baskets)
    baskets = {k: v for k, v in baskets.items() if len(v) > 1}  # 2개 이상 담긴 주문만 분석
    total = len(baskets)
    if not total:
        return {"total_orders": all_orders, "multi_item_orders": 0, "sets": []}
    single, pair = Counter(), Counter()
    for items in baskets.values():
        single.update(items)
        pair.update(combinations(sorted(items), 2))

    # 주문당 메뉴 수가 적으면 lift가 구조적으로 1보다 낮게 나오므로, 무작위 기준값으로 보정
    sizes = [len(v) for v in baskets.values()]
    baseline = (sum(k * (k - 1) for k in sizes) / total) / (sum(sizes) / total) ** 2

    sets = []
    for (a, b), cnt in pair.items():
        if a not in menus or b not in menus:
            continue
        support = cnt / total
        if support < min_support:
            continue
        lift = support / ((single[a] / total) * (single[b] / total)) / baseline
        if lift < min_lift:
            continue
        price = menus[a][1] + menus[b][1]
        sets.append({
            "menus": [{"menu_id": a, "name": menus[a][0]}, {"menu_id": b, "name": menus[b][0]}],
            "orders_together": cnt,
            "support": round(support * 100, 2),
            "confidence": round(max(cnt / single[a], cnt / single[b]) * 100, 1),
            "lift": round(lift, 2),
            "total_price": price,
            "set_price": price - SET_DISCOUNT,
            "discount": SET_DISCOUNT,
        })
    sets.sort(key=lambda x: (x["lift"], x["orders_together"]), reverse=True)
    return {
        "total_orders": all_orders,
        "multi_item_orders": total,
        "sets": sets[:top],
    }
