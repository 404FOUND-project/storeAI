# 리뷰 분석 API

**구현됨** (2026-11-24, 로컬 더미 DB로 확인). 로그인 필요, 본인 매장만 조회.

`GET /store/{store_id}/reviews/analysis/`

응답 예시 (값은 더미 리뷰 기준):
```json
{
  "min_reviews": 3,
  "sources": ["DUMMY"],
  "notice": "※ 더미(테스트) 리뷰 기준이며 실제 고객 의견이 아니에요. ...",
  "negative_categories": [{"category": "TASTE", "label": "맛", "count": 27}],
  "menus": [{
    "menu_id": 10, "name": "아메리카노", "quantity": 1066, "review_count": 6,
    "positive": 4, "negative": 2, "neutral": 0,
    "positive_ratio": 0.67, "negative_ratio": 0.33,
    "flag": null
  }]
}
```
- `flag`: `check_quality`(판매 많은데 부정 40%↑), `promote`(판매 적은데 긍정 50%↑), `null`
- 메뉴당 리뷰 3건 미만은 제외. 네이버 블로그 글(제목만)은 감정 분석에서 제외.
- 규칙 기반 집계이며 매출과의 인과관계를 확정하지 않음.
- 챗봇 문장형 답변은 `POST /chat/faq/answer/` (`review_*` 질문).
- 리뷰 CRUD(목록·등록·수정·삭제)는 미구현.
