import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from django.http import JsonResponse
from rest_framework.decorators import api_view

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None


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
