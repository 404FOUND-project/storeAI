"""선택형 챗봇: 사전 정의 질문·답변 + 관련 화면 이동 정보.

화면 번호(destination)는 Flutter 하단 탭 순서: 0 홈, 1 매출 분석, 2 AI 분석, 3 재고 및 발주, 4 마이
"""
from difflib import SequenceMatcher
import re
from datetime import timedelta

from django.db import connection
from django.utils import timezone


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
    ("메뉴 분석", 2, "AI 분석", [
        ("menu_top", "가장 많이 팔린 메뉴는 무엇인가요?", None),
        ("menu_together", "함께 주문되는 메뉴는 무엇인가요?", None),
        ("menu_new", "새롭게 추가하면 좋을 메뉴가 있나요?", "메뉴별 판매량과 원가 마진, 고객 반응을 함께 확인해 새 메뉴 도입 여부를 판단해 보세요."),
        ("menu_low", "판매가 저조한 메뉴를 알려주세요.", None),
    ]),
    ("재고 관리", 3, "재고 및 발주", [
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
    """질문 id -> 답변과 이동 화면 정보를 반환한다."""
    item = _BY_ID.get(qid)

    if not item:
        return None

    dest, dest_name, static = item

    # 매장 ID가 있으면 실제 데이터 조회를 우선한다.
    if store_id:
        dynamic_answer = _dynamic(qid, store_id)

        if dynamic_answer is not None:
            answer = dynamic_answer
        elif static is not None:
            answer = static
        else:
            answer = "아직 이 질문에 대한 매장 데이터 조회 기능이 연결되지 않았어요."
    else:
        answer = static or "매장 정보가 있어야 답변할 수 있어요."

    return {
        "answer": answer,
        "destination": dest,
        "destination_name": dest_name,
    }



def answer_freeform(question, store_id=None):
    """Match a free-form message to the closest existing FAQ without an API key."""
    normalized = re.sub(r"[^0-9a-z가-힣]", "", question.lower())
    if len(normalized) < 4:
        return None

    aliases = {
        "sales_month": ("이번달매출", "이달매출", "매출얼마", "매출현황", "월매출"),
        "sales_compare": ("지난달매출", "전월매출", "매출비교", "매출증감", "매출변화"),
        "sales_bestday": ("최고매출일", "매출높았던날", "매출가장높은날"),
        "sales_hour": ("시간대별매출", "시간별매출", "피크타임", "매출시간대"),
        "sales_goal": ("매출목표", "목표달성", "목표매출"),
        "pred_tomorrow": ("내일매출", "내일예상매출", "내일얼마"),
        "pred_weekday": ("이번주매출", "매출높은요일", "매출많은요일"),
        "pred_basis": ("예측기준", "예측데이터", "예측모델"),
        "pred_promo": ("프로모션", "할인언제", "매출올리려면"),
        "menu_top": ("인기메뉴", "베스트메뉴", "가장많이팔린메뉴"),
        "menu_together": ("함께주문", "같이팔리는메뉴", "메뉴조합"),
        "menu_new": ("신메뉴", "새메뉴", "추가할메뉴", "메뉴추천"),
        "menu_low": ("안팔리는메뉴", "판매저조", "저조한메뉴"),
        "stock_check": ("재고확인", "재고점검", "유통기한"),
        "stock_tomorrow": ("내일준비", "발주추천", "원재료추천"),
        "stock_alert": ("재고부족", "부족알림", "재고알림"),
        "stock_proper": ("적정재고", "재고수량"),
        "area_where": ("유동인구", "주변고객", "사람많은곳"),
        "area_trait": ("상권특징", "주변상권"),
        "area_rival": ("경쟁카페", "경쟁매장"),
        "area_menu": ("상권추천메뉴", "상권에맞는메뉴"),
        "review_worst": ("불만리뷰", "불만족리뷰", "불만사항"),
        "review_best": ("좋은리뷰", "긍정리뷰", "호평메뉴"),
        "review_taste": ("맛평가", "맛불만", "맛관련리뷰"),
        "review_sales_gap": ("리뷰안좋은메뉴", "리뷰가나쁜메뉴"),
        "review_promo": ("리뷰로메뉴추천", "리뷰기반추천"),
    }

    for question_id, phrases in aliases.items():
        if any(phrase in normalized for phrase in phrases):
            return answer_question(question_id, store_id)

    def bigrams(value):
        return {value[index:index + 2] for index in range(len(value) - 1)}

    query_grams = bigrams(normalized)
    best_id = None
    best_score = 0.0
    for category in _FAQ:
        for question_id, faq_question, _ in category[3]:
            candidate = re.sub(r"[^0-9a-z가-힣]", "", faq_question.lower())
            candidate_grams = bigrams(candidate)
            overlap = len(query_grams & candidate_grams) / max(len(query_grams), 1)
            similarity = SequenceMatcher(None, normalized, candidate).ratio()
            score = max(overlap * 0.82, similarity)
            if score > best_score:
                best_id, best_score = question_id, score

    if best_id is None or best_score < 0.30:
        return None
    return answer_question(best_id, store_id)
