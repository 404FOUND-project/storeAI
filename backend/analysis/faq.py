"""선택형 챗봇: 사전 정의 질문·답변 + 관련 화면 이동 정보.

화면 번호(destination)는 Flutter 하단 탭 순서: 0 홈, 1 매출 분석, 2 AI 분석, 3 세트 추천, 4 마이
"""
from datetime import timedelta

from django.db import connection
from django.utils import timezone

DEMO = "(시연용 더미 데이터 기준) "

# (카테고리, 이동 화면 번호, 이동 화면 이름, [(질문 id, 질문, 정적 답변 또는 None=서버 계산)])
_FAQ = [
    ("이번 달 매출", 1, "매출 분석", [
        ("sales_month", "이번 달 현재까지 매출은 얼마인가요?", None),
        ("sales_compare", "지난달 같은 기간보다 매출이 얼마나 변했나요?", "지난달 같은 기간과 비교한 매출 증감은 매출 분석 화면에서 요일별 매출과 주문 건수와 함께 확인할 수 있어요."),
        ("sales_bestday", "이번 달 매출이 가장 높았던 날은 언제인가요?", None),
        ("sales_hour", "시간대별 매출은 어떻게 다른가요?", None),
        ("sales_goal", "이번 달 매출 목표를 달성할 수 있을까요?", "남은 영업일과 하루 평균 매출을 함께 고려해 목표 달성 가능성을 확인해 보세요. 목표 매출 기능은 아직 연결되지 않았어요."),
    ]),
    ("매출 예측", 1, "매출 분석", [
        ("pred_tomorrow", "내일 매출은 얼마나 예상되나요?", "예측 모델은 아직 연결되지 않았어요. 최근 매출, 요일, 날씨, 공휴일 데이터를 활용할 예정이에요."),
        ("pred_weekday", "이번 주 매출이 가장 높을 요일은 언제인가요?", None),
        ("pred_basis", "매출 예측은 어떤 데이터를 기반으로 하나요?", "과거 POS 매출, 주문 건수, 요일, 날씨, 공휴일 같은 변수를 활용해요."),
        ("pred_promo", "매출을 높이려면 언제 프로모션을 해야 하나요?", "매출이 낮은 시간대에 세트 메뉴나 디저트 추가 할인 같은 부담 적은 프로모션을 시험해 보세요. 전후의 주문 수와 객단가를 비교하는 것이 좋아요."),
    ]),
    ("메뉴 분석", 3, "세트 추천", [
        ("menu_top", "가장 많이 팔린 메뉴는 무엇인가요?", None),
        ("menu_together", "함께 주문되는 메뉴는 무엇인가요?", None),
        ("menu_new", "새롭게 추가하면 좋을 메뉴가 있나요?", "메뉴별 판매량과 원가 마진, 고객 반응을 함께 확인해 새 메뉴 도입 여부를 판단해 보세요."),
        ("menu_low", "판매가 저조한 메뉴를 알려주세요.", None),
    ]),
    ("재고 관리", 4, "마이", [
        ("stock_check", "재고 확인이 필요한 메뉴가 있나요?", None),
        ("stock_tomorrow", "내일 준비할 원재료를 추천해 주세요.", "발주 추천 화면에서 권장 발주량을 확인할 수 있어요. 예상 주문량 연동은 준비 중이에요."),
        ("stock_alert", "재고 부족을 미리 알 수 있나요?", "가능해요. 재고 수량과 일평균 사용량으로 남은 일수를 계산해 부족·위험 상태를 표시해요."),
        ("stock_proper", "판매량 기준으로 적정 재고를 알려주세요.", "적정 재고는 최근 14일 평균 사용량과 목표 보유 일수로 계산해요. 발주 추천 화면에서 품목별로 볼 수 있어요."),
    ]),
    ("고객 리뷰", 2, "AI 분석", [
        ("review_worst", "고객들이 가장 불만족스러워하는 점이 뭐예요?", None),
        ("review_best", "가장 반응이 좋은 메뉴는 뭐예요?", None),
        ("review_taste", "맛에 대한 부정 평가가 많은 메뉴가 있나요?", None),
        ("review_sales_gap", "판매량은 높은데 리뷰가 좋지 않은 메뉴가 있나요?", None),
        ("review_promo", "이번 달 어떤 메뉴를 집중 홍보하면 좋을까요?", None),
    ]),
    ("주변 상권 분석", 2, "AI 분석", [
        ("area_where", "주변에 카페 고객이 많은 장소는 어디인가요?", "주변 대학, 지하철역, 오피스의 위치와 유동 인구 데이터를 함께 보면 고객 유입 가능성을 분석할 수 있어요. 상권 데이터는 아직 연결되지 않았어요."),
        ("area_trait", "우리 가게 주변 상권의 특징은 무엇인가요?", "주변 시설, 경쟁 카페 수, 주요 고객층, 시간대별 수요를 함께 살펴보는 것이 좋아요. 상권 데이터는 아직 연결되지 않았어요."),
        ("area_rival", "주변 경쟁 카페를 분석해 주세요.", "주변 카페의 위치, 메뉴 가격, 리뷰 키워드를 비교할 수 있어요. 상권 데이터가 연결되지 않아 실제 분석 결과는 아니에요."),
        ("area_menu", "상권에 맞는 추천 메뉴가 있나요?", "상권과 메뉴별 판매량, 원가를 함께 확인해 매장에 맞는 메뉴를 검토해 보세요."),
    ]),
]

_BY_ID = {q[0]: (cat[1], cat[2], q[2]) for cat in _FAQ for q in cat[3]}


def faq_list():
    return [
        {"category": c, "destination": d, "destination_name": dn,
         "questions": [{"id": q[0], "question": q[1]} for q in qs]}
        for c, d, dn, qs in _FAQ
    ]


def _fetch(sql, params=()):
    with connection.cursor() as c:
        c.execute(sql, params)
        return c.fetchall()


def _dynamic(qid, store_id):
    from store.profitability import menu_profitability
    from store.setmenu import recommend_sets

    if qid.startswith("review_"):
        from review.insights import answer
        return answer(qid, store_id)
    if qid == "sales_month":
        # 한국 시간 기준, 주문이 있는 가장 최근 달
        month, total, n = _fetch(
            f"SELECT DATE_FORMAT(DATE_ADD(sold_at, INTERVAL 9 HOUR),'%%Y-%%m') m, SUM(total_amount), COUNT(*) FROM sales_sales "
            "WHERE store_id=%s GROUP BY m ORDER BY m DESC LIMIT 1", [store_id])[0] if _fetch(
            "SELECT 1 FROM sales_sales WHERE store_id=%s LIMIT 1", [store_id]) else (None, 0, 0)
        if not n:
            return "주문 기록이 아직 없어요."
        return f"주문 기록이 있는 가장 최근 달({month})의 매출은 {int(total):,}원, 주문은 {n:,}건이에요."
    if qid == "sales_bestday":
        rows = _fetch(
            "SELECT DATE(DATE_ADD(sold_at, INTERVAL 9 HOUR)), SUM(total_amount) FROM sales_sales WHERE store_id=%s GROUP BY 1 ORDER BY 2 DESC LIMIT 1",
            [store_id])
        return f"전체 기간 중 매출이 가장 높았던 날은 {rows[0][0]}(약 {int(rows[0][1]):,}원)이에요." if rows else "주문 기록이 없어요."
    if qid == "pred_weekday":
        names = ["일", "월", "화", "수", "목", "금", "토"]
        rows = _fetch(
            "SELECT DAYOFWEEK(DATE_ADD(sold_at, INTERVAL 9 HOUR)), SUM(total_amount) FROM sales_sales WHERE store_id=%s GROUP BY 1 ORDER BY 2 DESC LIMIT 1",
            [store_id])
        return f"과거 주문 기준으로 매출이 가장 높은 요일은 {names[rows[0][0] - 1]}요일이에요." if rows else "주문 기록이 없어요."
    if qid == "sales_hour":
        rows = _fetch(
            "SELECT HOUR(DATE_ADD(sold_at, INTERVAL 9 HOUR)), SUM(total_amount) FROM sales_sales WHERE store_id=%s GROUP BY 1 ORDER BY 2 DESC LIMIT 3",
            [store_id])
        if not rows:
            return "주문 기록이 없어요."
        return "매출이 높은 시간대는 " + ", ".join(f"{h}시" for h, _ in rows) + " 순이에요."
    if qid == "menu_top":
        top = menu_profitability(store_id)[:3]
        if not top or not top[0]["quantity"]:
            return "판매 기록이 없어요."
        return "가장 많이 팔린 메뉴는 " + ", ".join(f"{m['name']}({m['quantity']:,}개)" for m in top) + " 순이에요."
    if qid == "menu_low":
        sold = [m for m in menu_profitability(store_id) if m["quantity"]][-3:]
        if not sold:
            return "판매 기록이 없어요."
        return "판매가 적은 메뉴는 " + ", ".join(f"{m['name']}({m['quantity']:,}개)" for m in sold) + "예요."
    if qid == "menu_together":
        sets = recommend_sets(store_id, 3)["sets"]
        if not sets:
            return "함께 주문되는 조합을 찾을 만큼 주문이 쌓이지 않았어요."
        return "자주 함께 주문되는 조합은 " + ", ".join(
            " + ".join(m["name"] for m in s["menus"]) + f"({s['set_price']:,}원 세트)" for s in sets) + "예요."
    if qid == "stock_check":
        soon = timezone.localdate() + timedelta(days=7)
        rows = _fetch(
            "SELECT ingredient_name FROM inventory_inventory WHERE store_id=%s AND expiration_date<=%s ORDER BY expiration_date LIMIT 5",
            [store_id, soon])
        if not rows:
            return "유통기한이 7일 안에 끝나는 재료는 없어요."
        return "유통기한이 7일 안에 끝나는 재료는 " + ", ".join(r[0] for r in rows) + "예요. 재고 화면에서 부족 여부도 확인해 보세요."
    return None


def answer_question(qid, store_id=None):
    """질문 id -> {"answer", "destination", "destination_name"}. 모르는 id면 None."""
    item = _BY_ID.get(qid)
    if not item:
        return None
    dest, dest_name, static = item
    answer = static
    if answer is None and store_id:
        answer = _dynamic(qid, store_id)
        if answer:
            answer = DEMO + answer
    if answer is None:
        answer = "이 질문은 매장 정보(store_id)가 있어야 데이터로 답할 수 있어요."
    return {"answer": answer, "destination": dest, "destination_name": dest_name}
