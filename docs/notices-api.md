| 기능 | Method | URL | 인증 | 구현 상태 |
|---|---|---|---|---|
| 공지 목록 | GET | /notices/ | X | 구현 |
| 공지 상세 | GET | /notices/{pk}/ | X | 구현 |
| 공지 등록 | POST | /notices/ | Token + is_staff | 구현 |
| 공지 부분 수정 | PATCH | /notices/{pk}/ | Token + is_staff | 구현 |
| 공지 삭제 | DELETE | /notices/{pk}/ | Token + is_staff | 구현 |

# 공지사항 API

기준: `backend/notices/{models,serializers,views,urls,permissions}.py`, `backend/config/{settings,urls}.py` (2026-09-26).

요청 본문은 JSON입니다. 변경 요청은 `Authorization: Token <token>`과 활성 관리자(`is_staff=True`)가 필요합니다. 작성자 본인 여부는 검사하지 않아 다른 관리자의 공지도 변경할 수 있습니다. 조회는 공개이나 잘못된 토큰을 전달하면 인증 단계에서 401입니다. 세션 쿠키만으로는 API 인증이 되지 않습니다. 예시 ID·시각은 설명용이며 프레임워크 오류 문구는 버전·번역에 따라 달라질 수 있습니다.

요청 범위에 맞춰 GET·POST·PATCH·DELETE를 상세화했습니다. 실제 `RetrieveUpdateDestroyAPIView`는 PUT 전체 수정도 허용합니다. 이 추가 동작은 [검토 문서](api-review.md)에 별도로 기록했습니다.

## 실제 모델·serializer 필드

| 필드 | 타입 | 입력 규칙 |
|---|---|---|
| id | 정수 | 자동 PK, 읽기 전용 |
| title | 문자열 | 최대 200자, 생성 시 필수 |
| content | 문자열 | 생성 시 필수, 별도 최대 길이 없음 |
| author | 정수 또는 null | User FK, 읽기 전용, 작성자 삭제 시 SET_NULL |
| created_at | ISO 8601 문자열 | auto_now_add, 읽기 전용 |
| updated_at | ISO 8601 문자열 | auto_now, 읽기 전용 |

title·content는 공백을 제거하며 빈 문자열을 허용하지 않습니다. PATCH에서는 생략 가능합니다. 읽기 전용 필드 입력은 무시됩니다. 작성자는 서버가 `request.user`로 지정합니다. 응답 키는 `author`이며 `author_id`가 아닙니다. author는 사용자 PK만 반환하고 사용자 객체는 포함하지 않습니다. store·menu 관계는 없으므로 store_id·menu_id를 보내지 않습니다.

## 공지 목록

1. 기능명: 공지 목록
2. Method: `GET`
3. URL: `/notices/`
4. 기능 설명: created_at 내림차순, 동률이면 id 내림차순. 페이지당 20개 고정. 검색·필터·페이지 크기 변경 미지원.
5. 인증 필요 여부: X (잘못된 토큰 전달 시 401)
6. Path Parameter: 없음
7. Query Parameter: page: 선택, 기본 1, 양의 정수 또는 DRF 기본값 last(마지막 페이지). 잘못된 값·없는 페이지는 404.
8. Request Body JSON 예시:

없음

9. 성공 Response JSON 예시:

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "title": "서비스 점검 안내",
      "content": "9월 27일 오전 2시부터 점검합니다.",
      "author": 1,
      "created_at": "2026-09-26T10:00:00+09:00",
      "updated_at": "2026-09-26T10:00:00+09:00"
    }
  ]
}
```

next·previous는 다음·이전 페이지의 절대 URL 또는 null입니다. 비어 있으면 count=0, results=[]입니다.

10. 성공 Status Code: 200 OK
11. 주요 실패 Response 예시:

```json
{
  "detail": "유효하지 않은 페이지."
}
```

```json
{
  "detail": "유효하지 않은 토큰."
}
```

12. 실패 Status Code: 404: 잘못된/없는 페이지. 401: 무효 토큰. 405: 미지원 메서드.

## 공지 상세

1. 기능명: 공지 상세
2. Method: `GET`
3. URL: `/notices/{pk}/`
4. 기능 설명: 공지 한 건을 조회합니다.
5. 인증 필요 여부: X (잘못된 토큰 전달 시 401)
6. Path Parameter: pk: 필수 정수, Notice.id. 실제 URL converter는 <int:pk>.
7. Query Parameter: 없음
8. Request Body JSON 예시:

없음

9. 성공 Response JSON 예시:

```json
{
  "id": 1,
  "title": "서비스 점검 안내",
  "content": "9월 27일 오전 2시부터 점검합니다.",
  "author": 1,
  "created_at": "2026-09-26T10:00:00+09:00",
  "updated_at": "2026-09-26T10:00:00+09:00"
}
```

10. 성공 Status Code: 200 OK
11. 주요 실패 Response 예시:

```json
{
  "detail": "찾을 수 없습니다."
}
```

```json
{
  "detail": "유효하지 않은 토큰."
}
```

12. 실패 Status Code: 404: 없는 공지 또는 경로 불일치. 401: 무효 토큰. 405: 미지원 메서드.

## 공지 등록

1. 기능명: 공지 등록
2. Method: `POST`
3. URL: `/notices/`
4. 기능 설명: 공지를 생성하며 인증된 관리자를 author로 저장합니다.
5. 인증 필요 여부: 필수: Token + is_staff=True
6. Path Parameter: 없음
7. Query Parameter: 없음
8. Request Body JSON 예시:

```json
{
  "title": "서비스 점검 안내",
  "content": "9월 27일 오전 2시부터 점검합니다."
}
```

9. 성공 Response JSON 예시:

```json
{
  "id": 1,
  "title": "서비스 점검 안내",
  "content": "9월 27일 오전 2시부터 점검합니다.",
  "author": 1,
  "created_at": "2026-09-26T10:00:00+09:00",
  "updated_at": "2026-09-26T10:00:00+09:00"
}
```

10. 성공 Status Code: 201 Created
11. 주요 실패 Response 예시:

```json
{
  "title": [
    "이 필드는 필수 항목입니다."
  ]
}
```

```json
{
  "detail": "인증 자격 증명이 제공되지 않았습니다."
}
```

```json
{
  "detail": "이 작업을 수행할 권한(permission)이 없습니다."
}
```

12. 실패 Status Code: 400: 입력 검증/JSON 오류. 401: 인증 실패. 403: 인증된 일반 회원. 405: 미지원 메서드. 415: 파싱 시 미지원 미디어 타입.

## 공지 부분 수정

1. 기능명: 공지 부분 수정
2. Method: `PATCH`
3. URL: `/notices/{pk}/`
4. 기능 설명: 전달한 title·content만 수정합니다. author·created_at은 유지하고 updated_at을 갱신합니다.
5. 인증 필요 여부: 필수: Token + is_staff=True
6. Path Parameter: pk: 필수 정수, Notice.id
7. Query Parameter: 없음
8. Request Body JSON 예시:

```json
{
  "title": "서비스 점검 완료"
}
```

9. 성공 Response JSON 예시:

```json
{
  "id": 1,
  "title": "서비스 점검 완료",
  "content": "9월 27일 오전 2시부터 점검합니다.",
  "author": 1,
  "created_at": "2026-09-26T10:00:00+09:00",
  "updated_at": "2026-09-26T11:00:00+09:00"
}
```

10. 성공 Status Code: 200 OK
11. 주요 실패 Response 예시:

```json
{
  "title": [
    "이 필드는 blank일 수 없습니다."
  ]
}
```

```json
{
  "detail": "인증 자격 증명이 제공되지 않았습니다."
}
```

```json
{
  "detail": "이 작업을 수행할 권한(permission)이 없습니다."
}
```

```json
{
  "detail": "찾을 수 없습니다."
}
```

12. 실패 Status Code: 400: 입력 검증/JSON 오류. 401: 인증 실패. 403: 일반 회원. 404: 없는 공지. 405: 미지원 메서드. 415: 파싱 시 미지원 미디어 타입.

## 공지 삭제

1. 기능명: 공지 삭제
2. Method: `DELETE`
3. URL: `/notices/{pk}/`
4. 기능 설명: 공지를 DB에서 삭제합니다. 삭제 후 조회·재삭제는 404입니다.
5. 인증 필요 여부: 필수: Token + is_staff=True
6. Path Parameter: pk: 필수 정수, Notice.id
7. Query Parameter: 없음
8. Request Body JSON 예시:

없음

9. 성공 Response JSON 예시:

없음. 204 응답은 JSON 없이 본문이 비어 있습니다.

10. 성공 Status Code: 204 No Content
11. 주요 실패 Response 예시:

```json
{
  "detail": "인증 자격 증명이 제공되지 않았습니다."
}
```

```json
{
  "detail": "이 작업을 수행할 권한(permission)이 없습니다."
}
```

```json
{
  "detail": "찾을 수 없습니다."
}
```

12. 실패 Status Code: 401: 인증 실패. 403: 일반 회원. 404: 없는 공지. 405: 미지원 메서드.


권한 검사는 객체 조회보다 먼저 실행되어 일반 회원이 없는 공지를 수정·삭제해도 403입니다. 정수가 아닌 pk 등 URL 자체가 매칭되지 않는 404는 DRF JSON 대신 Django HTML 응답일 수 있습니다.
