# AI 경영비서 챗봇 API

기준일: 2026-11-10 · 구현·테스트 확인됨 (로컬 더미 DB + 실제 Mindlogic Gateway 호출)

## POST /api/chatbot/

매장 DB(매출·메뉴·재고·리뷰)를 요약해 AI에게 함께 전달하고 답변을 받습니다. 인증은 아직 없습니다(기존과 동일).

### 요청 (JSON)

| 필드 | 필수 | 설명 |
|---|---|---|
| question | 필수 | 질문 (최대 1000자) |
| history | 선택 | 이전 대화. `[{"role":"user"\|"assistant","content":"..."}]`. 마지막 10개만 사용 |
| store_id | 선택 | 없으면 가장 먼저 등록된 매장 |

```json
{
  "question": "오늘 매출이 왜 떨어졌을까?",
  "history": [
    {"role": "user", "content": "이번 주 인기 메뉴는?"},
    {"role": "assistant", "content": "아메리카노입니다..."}
  ]
}
```

### 응답

성공 `200`: `{"answer": "...", "store_id": 1}`

실패: `{"error": "사용자에게 보여줄 메시지"}`

| 상태 | 의미 |
|---|---|
| 400 | 질문이 비었거나 너무 김 / JSON 형식 오류 |
| 404 | 등록된 매장 없음 |
| 429 | AI 호출 한도 초과 |
| 502 | AI 서버 오류 또는 빈 응답 |
| 503 | API 키 미설정 / AI 서버 연결 실패 |
| 504 | AI 응답 시간 초과(60초) |

### 대화 맥락 유지 방법
서버는 대화를 저장하지 않습니다. 앱이 매번 지금까지의 `history`를 함께 보내면 됩니다.
성공한 답변마다 `{"role":"user",...}`, `{"role":"assistant",...}` 두 개를 목록 끝에 추가하세요.

### Flutter(Dio) 예시

```dart
final res = await dio.post('/api/chatbot/', data: {
  'question': question,
  'history': history, // List<Map<String, String>>
});
final answer = res.data['answer'];
```
오류 시 Dio는 예외를 던지므로 `e.response?.data['error']`를 화면에 보여주면 됩니다.

### 챗봇이 참고하는 데이터 / 아직 없는 것
- 참고함: 일별·요일별·시간대별 매출, 메뉴별 판매량·원가율, 재고 소진 예상일·유통기한, 리뷰 평점·감성·키워드
- 아직 없음: **날씨**, **주변 상권·경쟁 카페** (AI가 "연결되지 않았다"고 답하도록 설정됨)

## 로컬 테스트 방법
`backend` 폴더에서: `python manage.py seed_dummy` → `python manage.py runserver` → 브라우저에서 `http://127.0.0.1:8000/chat/`
(`.env`에 `USE_LOCAL_DB=1`, `AI_GATEWAY_API_KEY=...` 필요. `USE_LOCAL_DB=1`이면 공유 DB가 아닌 내 PC의 `local_dummy.sqlite3`를 사용합니다.)
