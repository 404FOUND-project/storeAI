| 기능 | Method | URL | 인증 | 구현 상태 |
|---|---|---|---|---|
| 리뷰 목록 조회 | GET | /store/{store_id}/reviews/ (제안) | 미정 | 미구현 |
| 리뷰 상세 조회 | GET | /store/{store_id}/reviews/{review_id}/ (제안) | 미정 | 미구현 |
| 리뷰 등록 | POST | /store/{store_id}/reviews/ (제안) | 미정 | 미구현 |
| 리뷰 부분 수정 | PATCH | /store/{store_id}/reviews/{review_id}/ (제안) | 미정 | 미구현 |
| 리뷰 삭제 | DELETE | /store/{store_id}/reviews/{review_id}/ (제안) | 미정 | 미구현 |

# 리뷰 API

## 현재 구현 상태

**미구현.** `backend/review/models.py`에는 모델이 있지만 `views.py`는 기본 scaffold뿐입니다. `serializers.py`, `urls.py`가 없고 `backend/config/urls.py`에도 연결되지 않았습니다. 기준일: 2026-09-26.

요약표와 아래 URL·Method는 사용자가 지정한 URL 규칙에 맞춘 **구현 후보**이며 실제 등록된 API가 아닙니다. 요청·응답·권한·성공 코드는 확정하지 않습니다. 모델의 null/blank/default는 DB·모델 정보이며 API 입력 필수 여부로 단정할 수 없습니다.

## 실제 모델 필드

### Review

| 필드 | 모델 타입 | 현재 제약·관계 |
|---|---|---|
| id | BigAutoField | 자동 PK |
| store | FK → Store | 필수, CASCADE, 역참조 reviews; DB 속성 store_id |
| content | TextField | 필수 |
| rating | DecimalField(2,1) | null=True, blank=True; 0~5 제한 없음 |
| sentiment | CharField(10) | blank=True; choices 없음 |
| keywords | JSONField | null=True, blank=True; 내부 스키마 없음 |
| reviewed_at | DateTimeField | null=True, blank=True; 실제 리뷰 작성 시각 |
| create_at | DateTimeField | auto_now_add=True |

작성자 User·Menu FK, 플랫폼, 답글 필드는 없습니다. sentiment 주석에 positive/negative/neutral이 있지만 choices 또는 검증은 없습니다. keywords가 반드시 문자열 배열이라는 보장도 없습니다. AI 감정 분석·리뷰 수집 view는 없습니다.

ForeignKey 필드 이름과 DB의 `_id` 속성은 구분해야 합니다. serializer가 없으므로 DB 속성을 그대로 Request/Response 키로 확정할 수 없습니다. 역참조도 자동으로 API에 노출되지 않습니다.

## API별 상세 — 모두 미구현

## 리뷰 목록 조회

1. 기능명: 리뷰 목록 조회
2. Method: `GET (제안)`
3. URL: `/store/{store_id}/reviews/`
4. 기능 설명: 미구현. 모델만 존재하며 해당 HTTP 처리 로직이 없습니다.
5. 인증 필요 여부: 미정: 인증·권한 view 없음
6. Path Parameter: store_id: 해당 모델 PK를 사용할 제안 파라미터 (현재 URL converter 없음)
7. Query Parameter: 미정: 필터·정렬·페이지네이션 구현 없음
8. Request Body JSON 예시:

정의 없음 — serializer가 없어 실제 Request JSON 예시를 확정할 수 없습니다.

9. 성공 Response JSON 예시:

정의 없음 — view/serializer가 없어 실제 성공 Response JSON이 없습니다.

10. 성공 Status Code: 없음 (미구현)
11. 주요 실패 Response 예시:

제안 경로 요청은 현재 URLconf에서 매칭되지 않아 Django 404가 됩니다. DRF JSON 오류 계약은 없으며 현재 DEBUG 설정에서는 HTML 404가 반환될 수 있습니다.

12. 실패 Status Code: 404 Not Found (경로 미등록). 업무 오류의 상태 코드는 미정.

## 리뷰 상세 조회

1. 기능명: 리뷰 상세 조회
2. Method: `GET (제안)`
3. URL: `/store/{store_id}/reviews/{review_id}/`
4. 기능 설명: 미구현. 모델만 존재하며 해당 HTTP 처리 로직이 없습니다.
5. 인증 필요 여부: 미정: 인증·권한 view 없음
6. Path Parameter: store_id: 해당 모델 PK를 사용할 제안 파라미터 (현재 URL converter 없음); review_id: 해당 모델 PK를 사용할 제안 파라미터 (현재 URL converter 없음)
7. Query Parameter: 미정: 필터·정렬·페이지네이션 구현 없음
8. Request Body JSON 예시:

정의 없음 — serializer가 없어 실제 Request JSON 예시를 확정할 수 없습니다.

9. 성공 Response JSON 예시:

정의 없음 — view/serializer가 없어 실제 성공 Response JSON이 없습니다.

10. 성공 Status Code: 없음 (미구현)
11. 주요 실패 Response 예시:

제안 경로 요청은 현재 URLconf에서 매칭되지 않아 Django 404가 됩니다. DRF JSON 오류 계약은 없으며 현재 DEBUG 설정에서는 HTML 404가 반환될 수 있습니다.

12. 실패 Status Code: 404 Not Found (경로 미등록). 업무 오류의 상태 코드는 미정.

## 리뷰 등록

1. 기능명: 리뷰 등록
2. Method: `POST (제안)`
3. URL: `/store/{store_id}/reviews/`
4. 기능 설명: 미구현. 모델만 존재하며 해당 HTTP 처리 로직이 없습니다.
5. 인증 필요 여부: 미정: 인증·권한 view 없음
6. Path Parameter: store_id: 해당 모델 PK를 사용할 제안 파라미터 (현재 URL converter 없음)
7. Query Parameter: 미정: 필터·정렬·페이지네이션 구현 없음
8. Request Body JSON 예시:

정의 없음 — serializer가 없어 실제 Request JSON 예시를 확정할 수 없습니다.

9. 성공 Response JSON 예시:

정의 없음 — view/serializer가 없어 실제 성공 Response JSON이 없습니다.

10. 성공 Status Code: 없음 (미구현)
11. 주요 실패 Response 예시:

제안 경로 요청은 현재 URLconf에서 매칭되지 않아 Django 404가 됩니다. DRF JSON 오류 계약은 없으며 현재 DEBUG 설정에서는 HTML 404가 반환될 수 있습니다.

12. 실패 Status Code: 404 Not Found (경로 미등록). 업무 오류의 상태 코드는 미정.

## 리뷰 부분 수정

1. 기능명: 리뷰 부분 수정
2. Method: `PATCH (제안)`
3. URL: `/store/{store_id}/reviews/{review_id}/`
4. 기능 설명: 미구현. 모델만 존재하며 해당 HTTP 처리 로직이 없습니다.
5. 인증 필요 여부: 미정: 인증·권한 view 없음
6. Path Parameter: store_id: 해당 모델 PK를 사용할 제안 파라미터 (현재 URL converter 없음); review_id: 해당 모델 PK를 사용할 제안 파라미터 (현재 URL converter 없음)
7. Query Parameter: 미정: 필터·정렬·페이지네이션 구현 없음
8. Request Body JSON 예시:

정의 없음 — serializer가 없어 실제 Request JSON 예시를 확정할 수 없습니다.

9. 성공 Response JSON 예시:

정의 없음 — view/serializer가 없어 실제 성공 Response JSON이 없습니다.

10. 성공 Status Code: 없음 (미구현)
11. 주요 실패 Response 예시:

제안 경로 요청은 현재 URLconf에서 매칭되지 않아 Django 404가 됩니다. DRF JSON 오류 계약은 없으며 현재 DEBUG 설정에서는 HTML 404가 반환될 수 있습니다.

12. 실패 Status Code: 404 Not Found (경로 미등록). 업무 오류의 상태 코드는 미정.

## 리뷰 삭제

1. 기능명: 리뷰 삭제
2. Method: `DELETE (제안)`
3. URL: `/store/{store_id}/reviews/{review_id}/`
4. 기능 설명: 미구현. 모델만 존재하며 해당 HTTP 처리 로직이 없습니다.
5. 인증 필요 여부: 미정: 인증·권한 view 없음
6. Path Parameter: store_id: 해당 모델 PK를 사용할 제안 파라미터 (현재 URL converter 없음); review_id: 해당 모델 PK를 사용할 제안 파라미터 (현재 URL converter 없음)
7. Query Parameter: 미정: 필터·정렬·페이지네이션 구현 없음
8. Request Body JSON 예시:

정의 없음 — serializer가 없어 실제 Request JSON 예시를 확정할 수 없습니다.

9. 성공 Response JSON 예시:

정의 없음 — view/serializer가 없어 실제 성공 Response JSON이 없습니다.

10. 성공 Status Code: 없음 (미구현)
11. 주요 실패 Response 예시:

제안 경로 요청은 현재 URLconf에서 매칭되지 않아 Django 404가 됩니다. DRF JSON 오류 계약은 없으며 현재 DEBUG 설정에서는 HTML 404가 반환될 수 있습니다.

12. 실패 Status Code: 404 Not Found (경로 미등록). 업무 오류의 상태 코드는 미정.

## 별도 구현 제안

store는 URL store_id로 지정하는 방안을 권장합니다. store_id 본문 중복 여부·관계 응답 키는 serializer 구현 시 확정하세요. rating 범위, sentiment 허용값, keywords 구조와 AI 산출 필드의 읽기 전용 여부를 결정해야 합니다. 모델 필드만으로 분석 기능이 구현되었다고 간주할 수 없습니다.

공통적으로 serializer·view·urls.py를 작성하고 루트 URLconf에 연결해야 합니다. 추가 필드나 중첩 JSON 구조는 현재 명세가 아닙니다. 관련 검토: [API 검토](api-review.md).
