
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from django.http import JsonResponse
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from store.models import Store

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None


def get_user_store(request, requested_store_id=None):
    """로그인한 사용자가 소유한 매장만 반환한다."""
    stores = Store.objects.filter(owner=request.user).order_by("id")

    if requested_store_id not in (None, ""):
        try:
            store_id = int(requested_store_id)
        except (TypeError, ValueError):
            return None, JsonResponse(
                {"error": "올바르지 않은 매장 ID입니다."},
                status=400,
                json_dumps_params={"ensure_ascii": False},
            )

        store = stores.filter(id=store_id).first()
        if store is None:
            return None, JsonResponse(
                {"error": "해당 매장을 조회할 권한이 없거나 매장이 존재하지 않습니다."},
                status=403,
                json_dumps_params={"ensure_ascii": False},
            )
        return store, None

    store = stores.first()
    if store is None:
        return None, JsonResponse(
            {"error": "등록된 매장이 없습니다. 먼저 매장을 등록해 주세요."},
            status=404,
            json_dumps_params={"ensure_ascii": False},
        )

    return store, None


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def chatbot(request):
    from datetime import timedelta

    from django.db.models import Count, Sum
    from django.utils import timezone
    from sales.models import Sales, SalesItem

    question = request.data.get("question", "")
    if not isinstance(question, str) or not question.strip():
        return JsonResponse(
            {"error": "질문을 입력해 주세요."},
            status=400,
            json_dumps_params={"ensure_ascii": False},
        )

    question = question.strip()

    store, error_response = get_user_store(
        request, request.data.get("store_id")
    )
    if error_response:
        return error_response

    try:
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        week_start = today - timedelta(days=6)
        month_start = today.replace(day=1)
        previous_month_end = month_start - timedelta(days=1)
        previous_month_start = previous_month_end.replace(day=1)

        def summarize(queryset):
            values = queryset.aggregate(
                order_count=Count("id"),
                total_sales=Sum("total_amount"),
            )
            count = int(values["order_count"] or 0)
            total = (
                int(values["total_sales"])
                if values["total_sales"] is not None
                else None
            )
            return {
                "count": count,
                "total": total,
                "average": round(total / count)
                if count and total is not None else None,
            }

        def period(start, end):
            return Sales.objects.filter(
                store=store,
                sold_at__date__gte=start,
                sold_at__date__lte=end,
            )

        today_data = summarize(
            Sales.objects.filter(store=store, sold_at__date=today)
        )
        yesterday_data = summarize(
            Sales.objects.filter(store=store, sold_at__date=yesterday)
        )
        week_data = summarize(period(week_start, today))
        month_data = summarize(period(month_start, today))
        previous_month_data = summarize(
            period(previous_month_start, previous_month_end)
        )

        menu_rows = (
            SalesItem.objects.filter(
                sales__store=store,
                sales__sold_at__date__gte=today - timedelta(days=29),
                sales__sold_at__date__lte=today,
            )
            .values("menu__name")
            .annotate(quantity=Sum("quantity"))
            .order_by("-quantity", "menu__name")[:5]
        )
        menus = [
            (row["menu__name"], int(row["quantity"]))
            for row in menu_rows
        ]

        def won(value):
            return (
                f"{value:,}원"
                if value is not None
                else "확인할 매출 기록이 없습니다."
            )

        q = question.lower()

        unavailable_keywords = (
            "재고", "발주", "날씨", "리뷰", "후기",
            "상권", "유동인구", "폐업", "미래", "예측",
            "경쟁 매장", "경쟁점",
        )

        if any(word in q for word in unavailable_keywords):
            answer = (
                "현재 연결된 데이터는 매장 주문 및 메뉴 판매 기록입니다. "
                "질문하신 정보는 연결된 데이터가 없어 정확하게 확인할 수 없습니다."
            )

        elif any(word in q for word in (
            "인기 메뉴", "잘 팔리는", "많이 팔린 메뉴",
            "판매량", "메뉴 순위", "베스트 메뉴",
        )):
            if not menus:
                answer = "최근 30일간 등록된 메뉴 판매 기록이 없어 인기 메뉴를 확인할 수 없어요."
            else:
                lines = [
                    f"{i}. {name}: {quantity:,}개"
                    for i, (name, quantity) in enumerate(menus, 1)
                ]
                answer = (
                    "최근 30일간 실제 주문 기록 기준 메뉴 판매량이에요.\n"
                    + "\n".join(lines)
                )

        elif "어제" in q:
            if not yesterday_data["count"]:
                answer = "어제 등록된 주문 기록이 없어요. 매출이 0원이었다고 단정할 수는 없습니다."
            else:
                answer = (
                    f"어제 매출은 {won(yesterday_data['total'])}이에요.\n"
                    f"주문 수: {yesterday_data['count']:,}건\n"
                    f"평균 객단가: {won(yesterday_data['average'])}"
                )

        elif "지난달" in q:
            if not previous_month_data["count"]:
                answer = "지난달 등록된 주문 기록이 없어 매출을 확인할 수 없어요."
            else:
                answer = (
                    f"지난달 매출은 {won(previous_month_data['total'])}이에요.\n"
                    f"주문 수: {previous_month_data['count']:,}건\n"
                    f"평균 객단가: {won(previous_month_data['average'])}"
                )

        elif any(word in q for word in ("오늘", "금일")):
            if not today_data["count"]:
                answer = "오늘 등록된 주문 기록이 아직 없어요. 매출이 0원이라고 단정할 수는 없습니다."
            else:
                answer = (
                    f"오늘 매출은 {won(today_data['total'])}이에요.\n"
                    f"주문 수: {today_data['count']:,}건\n"
                    f"평균 객단가: {won(today_data['average'])}"
                )

        elif any(word in q for word in ("이번 달", "이번달", "월간")):
            if not month_data["count"]:
                answer = "이번 달 등록된 주문 기록이 없어 매출을 확인할 수 없어요."
            else:
                answer = (
                    f"이번 달 누적 매출은 {won(month_data['total'])}이에요.\n"
                    f"주문 수: {month_data['count']:,}건\n"
                    f"평균 객단가: {won(month_data['average'])}"
                )

        elif any(word in q for word in (
            "객단가", "평균 구매", "평균 주문 금액",
        )):
            if week_data["average"] is None:
                answer = "최근 7일간 주문 기록이 없어 평균 객단가를 계산할 수 없어요."
            else:
                answer = (
                    f"최근 7일간 평균 객단가는 {won(week_data['average'])}입니다.\n"
                    f"총 {week_data['count']:,}건의 주문을 기준으로 계산했어요."
                )

        elif any(word in q for word in ("주문 수", "주문 건수", "몇 건")):
            if not week_data["count"]:
                answer = "최근 7일간 등록된 주문 기록이 없어요."
            else:
                answer = f"최근 7일간 총 {week_data['count']:,}건의 주문이 등록되어 있어요."

        elif any(word in q for word in ("매출", "판매 금액", "얼마")):
            if not week_data["count"]:
                answer = "최근 7일간 등록된 주문 기록이 없어 매출을 확인할 수 없어요."
            else:
                answer = (
                    f"최근 7일간 매출은 {won(week_data['total'])}이에요.\n"
                    f"주문 수: {week_data['count']:,}건\n"
                    f"평균 객단가: {won(week_data['average'])}"
                )

        else:
            answer = (
                f"{store.name} 매장 기준으로 안내해 드릴게요.\n\n"
                f"오늘 매출: {won(today_data['total'])}\n"
                f"최근 7일 매출: {won(week_data['total'])}\n"
                f"이번 달 누적 매출: {won(month_data['total'])}\n"
                f"최근 7일 주문 수: {week_data['count']:,}건\n"
                f"최근 7일 평균 객단가: {won(week_data['average'])}\n\n"
                "인기 메뉴, 오늘 매출, 어제 매출, 객단가 등을 질문해 주세요."
            )

        return JsonResponse(
            {
                "question": question,
                "answer": answer,
                "store_id": store.id,
                "store_name": store.name,
            },
            json_dumps_params={"ensure_ascii": False},
        )

    except Exception as e:
        print(f"\n챗봇 DB 조회 오류: {type(e).__name__}: {e}\n")
        return JsonResponse(
            {
                "error_type": type(e).__name__,
                "error": "챗봇 답변을 만드는 중 오류가 발생했습니다.",
            },
            status=500,
            json_dumps_params={"ensure_ascii": False},
        )
def faq_api(request):
    """GET /api/chatbot/faq/ : 카테고리별 선택형 질문 목록"""
    from .faq import faq_list

    return JsonResponse(
        {"categories": faq_list()},
        json_dumps_params={"ensure_ascii": False},
    )


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def faq_answer_api(request):
    """로그인 사용자의 소유 매장에 대한 FAQ 답변"""
    store, error_response = get_user_store(
        request,
        request.query_params.get("store_id"),
    )

    if error_response:
        return error_response

    from .faq import answer_question

    result = answer_question(
        request.query_params.get("id", ""),
        store.id,
    )

    if result is None:
        return JsonResponse(
            {"error": "알 수 없는 질문입니다."},
            status=404,
            json_dumps_params={"ensure_ascii": False},
        )

    result["store_id"] = store.id
    result["store_name"] = store.name

    return JsonResponse(
        result,
        json_dumps_params={"ensure_ascii": False},
    )
