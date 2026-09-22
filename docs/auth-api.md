# 회원 인증 API

## 1. 공통 규칙

- 개발 기본 주소: `http://127.0.0.1:8000`
- 기본 경로: `/member/`
- 요청 본문: JSON, `Content-Type: application/json`
- 인증 헤더: `Authorization: Token <로그인으로 발급된 토큰>`
- URL 끝의 `/` 포함
- 오류 메시지 문구는 Django/DRF 버전에 따라 달라질 수 있음

| 기능 | 메서드 | 경로 | 인증 | 성공 코드 |
| --- | --- | --- | --- | --- |
| 회원가입 | POST | `/member/signup/` | 불필요 | 201 |
| 로그인 | POST | `/member/login/` | 불필요 | 200 |
| 내 정보 | GET | `/member/me/` | 토큰 필수 | 200 |
| 로그아웃 | POST | `/member/logout/` | 토큰 필수 | 204 |

가입과 로그인은 인증 헤더를 검사하지 않습니다. 내 정보와 로그아웃은 토큰 인증을 사용하며, Django 관리자 화면의 세션 쿠키만으로는 호출할 수 없습니다.

## 2. 회원가입

### 요청

`POST /member/signup/`

| 필드 | 타입 | 필수 | 규칙 |
| --- | --- | --- | --- |
| username | string | 예 | 최대 150자, 중복 불가, 문자·숫자 및 `@ . + - _` 허용 |
| password | string | 예 | 최소 8자, 흔한 비밀번호·숫자 전용·사용자 정보와 유사한 비밀번호 거절 |
| nickname | string | 아니요 | 최대 30자, 기본값 빈 문자열 |
| phone | string | 아니요 | 최대 20자, 기본값 빈 문자열, 전화번호 형식 별도 검증 없음 |

비밀번호의 앞뒤 공백은 보존합니다. 다른 문자열 필드는 앞뒤 공백을 제거합니다. 필수 필드는 빈 문자열을 허용하지 않습니다. 닉네임과 전화번호는 중복을 허용합니다. `is_staff`, `is_superuser` 등 선언하지 않은 필드는 무시하므로 가입 요청으로 관리자 권한을 얻을 수 없습니다.

```json
{
  "username": "storeowner",
  "password": "River!Cedar72Moon",
  "nickname": "사장님",
  "phone": "010-1234-5678"
}
```

### 성공 응답 — 201 Created

```json
{
  "username": "storeowner",
  "nickname": "사장님",
  "phone": "010-1234-5678"
}
```

비밀번호는 해시로 저장하며 응답에서 제외합니다. 회원가입 시 토큰을 발급하지 않으므로 이후 로그인 API를 호출합니다.

### 실패 응답 — 400 Bad Request

필드별 오류 배열을 반환합니다. 예시:

```json
{"username": ["해당 사용자 이름은 이미 존재합니다."]}
```

```json
{"password": ["비밀번호가 너무 짧습니다. 최소 8 문자를 포함해야 합니다."]}
```

필수 값 누락, 잘못된 아이디 형식, 길이 제한 위반도 해당 필드에 오류를 반환합니다.

## 3. 로그인

### 요청

`POST /member/login/`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| username | string | 예 | 가입한 아이디 |
| password | string | 예 | 가입한 비밀번호, 앞뒤 공백 보존 |

```json
{"username": "storeowner", "password": "River!Cedar72Moon"}
```

### 성공 응답 — 200 OK

```json
{
  "token": "발급된 토큰",
  "user": {
    "id": 1,
    "username": "storeowner",
    "nickname": "사장님",
    "phone": "010-1234-5678"
  }
}
```

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| token | string | 후속 요청의 인증 헤더에 전달할 토큰 |
| user.id | integer | 사용자 DB 식별자 |
| user.username | string | 로그인 아이디 |
| user.nickname | string | 닉네임 |
| user.phone | string | 전화번호 |

### 실패 응답 — 400 Bad Request

존재하지 않는 아이디, 잘못된 비밀번호, 비활성 계정은 동일한 오류를 반환합니다.

```json
{"non_field_errors": ["아이디 또는 비밀번호가 올바르지 않습니다."]}
```

필수 값 누락은 `username`, `password` 필드별 오류 배열을 반환합니다.

## 4. 내 정보

### 요청

`GET /member/me/`

```http
Authorization: Token <발급된 토큰>
```

요청 본문과 사용자 ID는 필요 없습니다. 토큰에 연결된 사용자만 조회합니다.

### 성공 응답 — 200 OK

```json
{
  "id": 1,
  "username": "storeowner",
  "nickname": "사장님",
  "phone": "010-1234-5678"
}
```

### 실패 응답 — 401 Unauthorized

토큰 누락, 잘못된 토큰, 삭제된 토큰, 비활성 사용자 토큰으로 요청한 경우입니다. 응답 형태:

```json
{"detail": "인증 자격 증명이 제공되지 않았습니다."}
```

`detail` 문구는 실패 사유에 따라 달라집니다.

## 5. 로그아웃

### 요청

`POST /member/logout/`

```http
Authorization: Token <발급된 토큰>
```

요청 본문은 필요 없습니다.

### 성공 응답 — 204 No Content

응답 본문 없이 인증 토큰을 삭제합니다. 클라이언트에서도 보관한 토큰을 제거합니다.

### 실패 응답 — 401 Unauthorized

내 정보 API와 동일한 인증 실패 조건입니다. 로그아웃한 토큰으로 다시 로그아웃을 요청해도 401입니다.

## 6. 토큰 동작 및 공통 오류

- 사용자당 하나의 토큰 유지, 반복 로그인 시 기존 토큰 재사용
- 자동 만료 없음, 로그아웃 후 로그인 시 새 토큰 발급
- 로그아웃 시 동일 토큰을 사용하는 모든 기기의 인증 해제
- 운영 환경에서 HTTPS 사용 및 클라이언트 토큰 안전 보관
- 잘못된 JSON: 400, 지원하지 않는 메서드: 405, 지원하지 않는 본문 형식: 415
- 일반 오류 응답: `{"detail": "오류 설명"}`

## 7. 실행 및 검증

환경 변수와 MySQL 연결을 설정한 후 `backend`에서 실행합니다.

```powershell
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py runserver
```

마이그레이션은 인증 토큰 테이블과 설치된 앱의 미적용 테이블을 생성합니다. 현재 가상환경의 Python 실행 경로가 유효해야 합니다.

MySQL에 접근하지 않는 테스트:

```powershell
.venv\Scripts\python.exe manage.py test member --settings=config.test_settings
```

다음 단계: [공지사항 API](notices-api.md)
