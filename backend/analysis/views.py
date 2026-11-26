
from django.http import JsonResponse

from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from store.models import Store


def get_user_store(request, requested_store_id=None):
    """로그인한 사용자가 소유한 매장만 반환한다."""

    stores = Store.objects.filter(
        owner=request.user
    ).order_by("id")

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
    question = request.data.get("question", "")

    if not isinstance(question, str) or not question.strip():
        return JsonResponse(
            {"error": "질문을 입력해 주세요."},
            status=400,
            json_dumps_params={"ensure_ascii": False},
        )

    store, error_response = get_user_store(
        request,
        request.data.get("store_id"),
    )

    if error_response:
        return error_response

    from .faq import answer_freeform

    matched = answer_freeform(
        question.strip(),
        store.id,
    )

    if matched:
        answer = matched["answer"]
        source = "store_data_faq"
    else:
        answer = (
            f"{store.name}의 매장 데이터를 바탕으로 답변할 수 있는 "
            "질문을 찾지 못했어요.\n\n"
            "매출, 매출 예측, 메뉴, 재고, 리뷰 관련 질문을 "
            "구체적으로 입력해 주세요."
        )
        source = "faq"

    return JsonResponse(
        {
            "question": question.strip(),
            "answer": answer,
            "store_id": store.id,
            "store_name": store.name,
            "source": source,
        },
        json_dumps_params={"ensure_ascii": False},
    )


def faq_api(request):
    """GET /api/chatbot/faq/ : 선택형 질문 목록"""

    from .faq import faq_list

    return JsonResponse(
        {"categories": faq_list()},
        json_dumps_params={"ensure_ascii": False},
    )


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def faq_answer_api(request):
    """GET /api/chatbot/faq/answer/ : 로그인 사용자의 매장별 FAQ 답변"""

    store, error_response = get_user_store(
        request,
        request.GET.get("store_id"),
    )

    if error_response:
        return error_response

    from .faq import answer_question

    result = answer_question(
        request.GET.get("id", ""),
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
