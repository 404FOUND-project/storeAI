
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
def chatbot(request):
    question = request.data.get("question", "")

    if not isinstance(question, str) or not question.strip():
        return JsonResponse(
            {"error": "질문을 입력해 주세요."},
            status=400,
            json_dumps_params={"ensure_ascii": False},
        )

    if client is None:
        return JsonResponse(
            {"error": "backend/.env에서 OPENAI_API_KEY를 찾을 수 없습니다."},
            status=500,
            json_dumps_params={"ensure_ascii": False},
        )

    try:
        result = client.responses.create(
            model="gpt-4.1-mini",
            instructions=(
                "너는 소상공인 카페 사장님을 돕는 AI 경영비서야. "
                "한국어로 쉽고 친절하게 답변해. "
                "실제 매출 데이터가 제공되지 않았다면 매출 수치를 지어내지 마."
            ),
            input=question.strip(),
        )

        return JsonResponse(
            {
                "question": question.strip(),
                "answer": result.output_text,
            },
            json_dumps_params={"ensure_ascii": False},
        )

    except Exception as e:
        print(f"\nOpenAI 오류 유형: {type(e).__name__}")
        print(f"OpenAI 오류 내용: {e}\n")

        return JsonResponse(
            {
                "error_type": type(e).__name__,
                "error": str(e),
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
