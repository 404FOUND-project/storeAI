"""리뷰 집계 + 매출 연계 (규칙 기반). 감정이 있는 DUMMY 리뷰만 사용.
NAVER_API 글 제목은 감정 분석 대상이 아니라 제외."""
from collections import Counter

from review.models import Review

MIN_REVIEWS = 3  # 메뉴당 이 수 미만이면 '데이터 부족'
CAT = {"TASTE": "맛", "PRICE": "가격", "AMOUNT": "양", "SERVICE": "서비스", "ATMOSPHERE": "분위기", "ETC": "기타"}
NOTE = " ※ 더미(테스트) 리뷰 기준이며 실제 고객 의견이 아니에요. 매출과의 관계는 참고용이고 원인을 확정하지 않아요."


def _stats(store_id):
    """menu_id -> {name, pos, neg, neu, n}"""
    out = {}
    qs = Review.objects.filter(store_id=store_id, menu__isnull=False).exclude(sentiment="").select_related("menu")
    for r in qs:
        s = out.setdefault(r.menu_id, {"name": r.menu.name, "pos": 0, "neg": 0, "neu": 0, "n": 0})
        s[{"positive": "pos", "negative": "neg"}.get(r.sentiment, "neu")] += 1
        s["n"] += 1
    return out


def _sales(store_id):
    from store.profitability import menu_profitability
    return {m["menu_id"]: m["quantity"] for m in menu_profitability(store_id)}


def answer(qid, store_id):
    if not Review.objects.filter(store_id=store_id).exclude(sentiment="").exists():
        return "분석할 리뷰가 아직 없어요."
    if qid == "review_worst":
        c = Counter(Review.objects.filter(store_id=store_id, sentiment="negative").exclude(category="")
                    .values_list("category", flat=True))
        if not c:
            return "부정 리뷰가 없어요."
        return "부정 리뷰에서 많이 나온 불만은 " + ", ".join(f"{CAT[k]}({v}건)" for k, v in c.most_common(3)) + " 순이에요." + NOTE
    st = [s for s in _stats(store_id).values() if s["n"] >= MIN_REVIEWS]
    if not st:
        return f"메뉴별 리뷰가 {MIN_REVIEWS}건 이상 쌓이지 않아 분석 데이터가 부족해요."
    if qid == "review_best":
        top = sorted(st, key=lambda s: (s["pos"] / s["n"], s["n"]), reverse=True)[:3]
        return "긍정 리뷰 비율이 높은 메뉴는 " + ", ".join(f"{s['name']}({s['pos']}/{s['n']}건)" for s in top) + "예요." + NOTE
    if qid == "review_taste":
        c = Counter()
        for r in Review.objects.filter(store_id=store_id, sentiment="negative", category="TASTE", menu__isnull=False).select_related("menu"):
            c[r.menu.name] += 1
        if not c:
            return "맛에 대한 부정 리뷰가 없어요."
        return "맛 관련 부정 리뷰가 많은 메뉴는 " + ", ".join(f"{k}({v}건)" for k, v in c.most_common(3)) + "예요." + NOTE
    sales = _sales(store_id)
    ids = {mid: s for mid, s in _stats(store_id).items() if s["n"] >= MIN_REVIEWS}
    qtys = sorted(sales.get(m, 0) for m in ids)
    mid_q = qtys[len(qtys) // 2]
    if qid == "review_sales_gap":
        hit = [s["name"] + f"(판매 {sales.get(m, 0):,}개, 부정 {s['neg']}/{s['n']})" for m, s in ids.items()
               if sales.get(m, 0) >= mid_q and s["neg"] / s["n"] >= 0.4]
        return ("판매량은 높은데 부정 리뷰 비율이 높은 메뉴: " + ", ".join(hit[:3]) + ". 품질 점검을 검토해 보세요." if hit
                else "판매량은 높은데 부정 리뷰가 많은 메뉴는 없어요.") + NOTE
    if qid == "review_promo":
        hit = [s["name"] + f"(판매 {sales.get(m, 0):,}개, 긍정 {s['pos']}/{s['n']})" for m, s in ids.items()
               if sales.get(m, 0) < mid_q and s["pos"] / s["n"] >= 0.5]
        return ("판매량은 낮지만 긍정 반응이 좋은 메뉴: " + ", ".join(hit[:3]) + ". 홍보 강화를 검토해 보세요." if hit
                else "판매량이 낮으면서 긍정 반응이 높은 메뉴는 없어요.") + NOTE
    return None


def analysis(store_id):
    """프론트용 JSON: 메뉴별 판매량·긍부정 + 불만 카테고리 + 판매-반응 비교 (규칙 기반, 더미 리뷰면 source=DUMMY)"""
    st = _stats(store_id)
    sales = _sales(store_id)
    ok = {m: s for m, s in st.items() if s["n"] >= MIN_REVIEWS}
    qtys = sorted(sales.get(m, 0) for m in ok)
    mid_q = qtys[len(qtys) // 2] if qtys else 0
    menus = []
    for m, s in ok.items():
        q = sales.get(m, 0)
        menus.append({
            "menu_id": m, "name": s["name"], "quantity": q, "review_count": s["n"],
            "positive": s["pos"], "negative": s["neg"], "neutral": s["neu"],
            "positive_ratio": round(s["pos"] / s["n"], 2), "negative_ratio": round(s["neg"] / s["n"], 2),
            "flag": "check_quality" if q >= mid_q and s["neg"] / s["n"] >= 0.4
                    else "promote" if q < mid_q and s["pos"] / s["n"] >= 0.5 else None,
        })
    menus.sort(key=lambda x: -x["quantity"])
    cats = Counter(Review.objects.filter(store_id=store_id, sentiment="negative").exclude(category="")
                   .values_list("category", flat=True))
    sources = list(Review.objects.filter(store_id=store_id).values_list("source", flat=True).distinct())
    return {
        "min_reviews": MIN_REVIEWS, "sources": sources,
        "notice": NOTE.strip(),
        "negative_categories": [{"category": k, "label": CAT.get(k, k), "count": v} for k, v in cats.most_common()],
        "menus": menus,
    }
