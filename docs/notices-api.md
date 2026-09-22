# 공지사항 API

## 1. 공통 규칙

- 개발 기본 주소: `http://127.0.0.1:8000`
- 기본 경로: `/notices/`
- 요청 본문: JSON, `Content-Type: application/json`
- 인증 헤더: `Authorization: Token <로그인으로 발급된 토큰>`
- 관리자 기준: 활성 사용자이며 `is_staff=True`
- URL 끝의 `/` 포함
- 등록 즉시 공개, 임시저장·비공개 상태 없음
- 삭제는 DB에서 실제 삭제

| 기능 | 메서드 | 경로 | 권한 | 성공 코드 |
| --- | --- | --- | --- | --- |
| 목록 | GET | `/notices/` | 누구나 | 200 |
| 상세 | GET | `/notices/{id}/` | 누구나 | 200 |
| 등록 | POST | `/notices/` | 관리자 | 201 |
| 전체 수정 | PUT | `/notices/{id}/` | 관리자 | 200 |
| 부분 수정 | PATCH | `/notices/{id}/` | 관리자 | 200 |
| 삭제 | DELETE | `/notices/{id}/` | 관리자 | 204 |

관리자는 다른 관리자가 등록한 공지도 수정·삭제할 수 있습니다. 공개 조회에는 토큰이 필요 없지만, 잘못된 토큰을 헤더에 포함하면 401을 반환합니다. 관리자 화면 로그인 세션만으로 API를 변경할 수 없으며 별도로 토큰을 전달해야 합니다.

## 2. 공지사항 필드

| 필드 | 타입 | 입력 | 규칙 |
| --- | --- | --- | --- |
| id | integer | 읽기 전용 | 공지사항 식별자 |
| title | string | 등록·PUT 필수 | 최대 200자, 빈 값·공백만 입력 불가 |
| content | string | 등록·PUT 필수 | 본문, 빈 값·공백만 입력 불가 |
| author | integer 또는 null | 읽기 전용 | 최초 작성 관리자 ID, 계정 삭제 시 null |
| created_at | string | 읽기 전용 | 최초 등록 시각, ISO 8601 |
| updated_at | string | 읽기 전용 | 마지막 저장 시각, ISO 8601 |

제목과 본문의 앞뒤 공백은 제거합니다. 읽기 전용 필드를 요청에 포함해도 무시하며, 작성자는 인증된 사용자로 지정합니다. 수정 시 최초 작성자는 유지합니다. 본문은 문자열로 저장하므로 화면에서 표시할 때 HTML로 직접 삽입하지 말고 텍스트로 렌더링합니다. 현재 별도 본문 길이 제한은 없습니다.

## 3. 목록 조회

### 요청

`GET /notices/?page=1`

| 쿼리 | 타입 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| page | integer | 아니요 | 1 | 페이지 번호, 1부터 시작 |

페이지당 20개 고정입니다. 등록 시각 내림차순이며 같은 시각이면 ID 내림차순입니다. 현재 검색·필터·페이지 크기 변경은 지원하지 않습니다.

### 성공 응답 — 200 OK

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "title": "서비스 점검 안내",
      "content": "9월 21일 오전 2시부터 3시까지 점검 예정입니다.",
      "author": 1,
      "created_at": "2026-09-20T10:00:00+09:00",
      "updated_at": "2026-09-20T10:00:00+09:00"
    }
  ]
}
```

`count`는 전체 공지 수입니다. `next`, `previous`는 다음·이전 페이지의 전체 URL이며 없으면 null입니다. 공지가 없으면 `count: 0`, `results: []`를 반환합니다. 존재하지 않거나 잘못된 페이지 번호는 404입니다.

## 4. 상세 조회

### 요청

`GET /notices/1/`

`1` 자리에 조회할 공지사항 ID를 지정합니다. 요청 본문은 없습니다.

### 성공 응답 — 200 OK

```json
{
  "id": 1,
  "title": "서비스 점검 안내",
  "content": "9월 21일 오전 2시부터 3시까지 점검 예정입니다.",
  "author": 1,
  "created_at": "2026-09-20T10:00:00+09:00",
  "updated_at": "2026-09-20T10:00:00+09:00"
}
```

해당 공지가 없으면 404입니다. 작성자 계정이 삭제되어도 공지는 유지되며 `author`가 null이 됩니다. 작성자의 전화번호·비밀번호 등은 제공하지 않습니다.

## 5. 등록

### 요청

`POST /notices/`

```http
Content-Type: application/json
Authorization: Token <관리자 토큰>
```

```json
{
  "title": "서비스 점검 안내",
  "content": "9월 21일 오전 2시부터 3시까지 점검 예정입니다."
}
```

### 성공 응답 — 201 Created

상세 조회와 동일한 구조로 생성된 공지를 반환합니다. `author`는 요청 토큰의 사용자 ID, `created_at`과 `updated_at`은 서버가 기록한 시각입니다.

### 입력 오류 — 400 Bad Request

예시 (문구는 Django/DRF 버전에 따라 달라질 수 있음):

```json
{"title": ["이 필드는 필수 항목입니다."]}
```

필수 필드 누락, 빈 문자열, 공백만 있는 문자열, 제목 200자 초과 등이 해당됩니다. 오류는 `title` 또는 `content`를 키로 하는 배열입니다.

## 6. 수정

### 전체 수정 — PUT /notices/1/

관리자 인증 헤더와 `title`, `content`를 모두 전달합니다.

```json
{
  "title": "서비스 점검 시간 변경",
  "content": "점검 시간이 오전 3시부터 4시로 변경되었습니다."
}
```

### 부분 수정 — PATCH /notices/1/

관리자 인증 헤더와 변경할 필드만 전달합니다.

```json
{"title": "서비스 점검 완료"}
```

### 성공 응답 — 200 OK

상세 조회와 동일한 구조의 수정된 공지를 반환합니다. 부분 수정에서 빠진 필드는 기존 값을 유지합니다. `author`, `created_at`은 유지하고 `updated_at`은 저장 시각으로 갱신합니다.

PUT에서 제목 또는 본문이 빠지면 400입니다. PATCH라도 전달한 값이 빈 문자열이면 400입니다. 해당 공지가 없으면 404입니다.

## 7. 삭제

### 요청

`DELETE /notices/1/`

```http
Authorization: Token <관리자 토큰>
```

요청 본문은 없습니다.

### 성공 응답 — 204 No Content

응답 본문 없이 공지를 삭제합니다. 삭제 후 상세 조회나 재삭제는 404입니다.

## 8. 오류 및 권한

| 코드 | 조건 |
| --- | --- |
| 400 | 필드 검증 실패 또는 잘못된 JSON |
| 401 | 변경 요청의 토큰 누락, 잘못된·폐기된 토큰, 비활성 사용자 토큰 |
| 403 | 일반 회원의 등록·수정·삭제 요청 |
| 404 | 없는 공지 ID 또는 없는 페이지 |
| 405 | 해당 경로에서 지원하지 않는 메서드 |
| 415 | 지원하지 않는 본문 형식 |

공개 조회도 잘못된 인증 헤더를 전달하면 401입니다. 변경 요청은 권한 검사 후 공지 조회를 수행하므로 일반 회원이 없는 공지에 접근해도 403입니다.

필드 오류 이외의 일반 오류 구조:

```json
{"detail": "오류 설명"}
```

## 9. 실행·관리자 준비·테스트

환경 변수와 MySQL 연결을 준비한 뒤 `backend`에서 실행합니다.

```powershell
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py createsuperuser
.venv\Scripts\python.exe manage.py runserver
```

마이그레이션은 `notices_notice` 및 미적용 인증 토큰 테이블 등을 생성합니다. 사용자 계정은 기존 `member.User`를 사용합니다. 관리자 계정이 이미 있으면 새로 생성할 필요가 없습니다.

관리자 사용 순서:

1. 관리자 계정으로 `POST /member/login/` 호출
2. 응답의 `token` 보관
3. 공지 등록·수정·삭제 시 `Authorization: Token <token>` 전달

브라우저의 `/admin/`에서도 공지 등록·검색·수정·삭제가 가능합니다. 관리자 화면에서 등록할 때도 로그인한 관리자가 최초 작성자로 기록됩니다.

MySQL에 접근하지 않는 전체 인증·공지 테스트:

```powershell
.venv\Scripts\python.exe manage.py test member notices --settings=config.test_settings
```

관련 문서: [회원 인증 API](auth-api.md)
