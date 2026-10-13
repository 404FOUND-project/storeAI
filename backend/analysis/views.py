from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["POST"])
def chatbot(request):
    question = request.data.get("question", "")

    if not question:
        return Response(
            {"error": "질문을 입력해 주세요."},
            status=400
        )

    answer = f"질문을 받았습니다: {question}"

    return Response({
        "question": question,
        "answer": answer
    })