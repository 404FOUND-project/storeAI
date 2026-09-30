| 기능 | Method | URL | 인증 | 구현 상태 |
|---|---|---|---|---|
| 회원가입 | POST | /member/signup/ | X | 구현 |
| 로그인 | POST | /member/login/ | X | 구현 |
| 내 정보 조회 | GET | /member/me/ | Token | 구현 |
| 로그아웃 | POST | /member/logout/ | Token | 구현 |

# 회원 인증 API

기준: `backend/member/{models,serializers,views,urls}.py`, `backend/config/{settings,urls}.py` (2026-09-26).

JSON 요청은 `Content-Type: application/json`, 인증은 `Authorization: Token <token>`을 사용합니다. 끝 슬래시를 포함합니다. 가입·로그인은 인증 헤더를 검사하지 않습니다. 내 정보·로그아웃은 세션 쿠키만으로 인증되지 않습니다. 예시의 ID·토큰·시각은 설명용이며, 프레임워크 오류 문구는 설치 버전·번역에 따라 달라질 수 있습니다.

## 실제 필드와 비밀번호 처리

| serializer | 필드 | 입력·출력 규칙 |
|---|---|---|
| SignupSerializer | username | 필수, 최대 150자, 중복 불가, Unicode 사용자명 검증 |
| SignupSerializer | password | 필수, 모델 기반 최대 128자, write_only=True, trim_whitespace=False |
| SignupSerializer | nickname | 선택, 최대 30자, 생략 시 빈 문자열 |
| SignupSerializer | phone | 선택, 최대 20자, 생략 시 빈 문자열, 별도 전화번호 형식 검증 없음 |
| UserSerializer | id, username, nickname, phone | 모두 읽기 전용 |
| LoginSerializer | username, password | 필수 문자열, password는 write_only=True, 공백 보존 |

`User`는 `AbstractUser`를 상속하며 `nickname`, `phone`을 추가합니다. 상속된 email, first_name, last_name, 권한·상태·로그인 시각 등의 모델 필드는 위 API에 노출되지 않습니다. 회원가입 응답에는 id도 없습니다. FK 입력은 없습니다.

가입은 `validate_password()`로 유사성·최소 8자·흔한 비밀번호·숫자로만 구성된 비밀번호를 검증합니다. 유사성 검사용 User에 username과 nickname을 전달하지만 기본 유사성 검증기의 비교 속성에 nickname은 포함되지 않습니다. `create_user()`가 비밀번호를 해시 저장합니다. 로그인은 `authenticate()`로 검증하며 비활성 계정도 거부합니다. 비밀번호 원문과 해시는 모든 성공 응답에서 제외됩니다. 비밀번호 오류 응답의 키는 입력 필드를 지칭하며 비밀번호 값을 반환하지 않습니다.

사용자당 토큰 하나를 재사용하며 자동 만료는 구현되어 있지 않습니다. 로그아웃은 해당 토큰을 삭제하므로 같은 토큰을 사용하는 모든 기기에 영향을 줍니다. 회원 정보 수정·탈퇴·비밀번호 변경/재설정은 미구현이며 URL도 정의되어 있지 않습니다.

## 회원가입

1. 기능명: 회원가입
2. Method: `POST`
3. URL: `/member/signup/`
4. 기능 설명: 사용자를 생성합니다. 토큰은 발급하지 않습니다.
5. 인증 필요 여부: X
6. Path Parameter: 없음
7. Query Parameter: 없음
8. Request Body JSON 예시:

```json
{
  "username": "storeowner",
  "password": "River!Cedar72Moon",
  "nickname": "사장님",
  "phone": "010-1234-5678"
}
```

9. 성공 Response JSON 예시:

```json
{
  "username": "storeowner",
  "nickname": "사장님",
  "phone": "010-1234-5678"
}
```

10. 성공 Status Code: 201 Created
11. 주요 실패 Response 예시:

```json
{
  "username": [
    "해당 사용자 이름은 이미 존재합니다."
  ]
}
```

```json
{
  "password": [
    "비밀번호가 너무 짧습니다. 최소 8 문자를 포함해야 합니다."
  ]
}
```

12. 실패 Status Code: 400: 필수값 누락·중복·길이/형식·비밀번호 검증 실패 또는 JSON 파싱 오류. 405: 미지원 메서드. 415: 파싱 시 미지원 미디어 타입.

## 로그인

1. 기능명: 로그인
2. Method: `POST`
3. URL: `/member/login/`
4. 기능 설명: 인증 후 기존 토큰을 재사용하거나 새 토큰을 생성합니다.
5. 인증 필요 여부: X
6. Path Parameter: 없음
7. Query Parameter: 없음
8. Request Body JSON 예시:

```json
{
  "username": "storeowner",
  "password": "River!Cedar72Moon"
}
```

9. 성공 Response JSON 예시:

```json
{
  "token": "<발급된 토큰>",
  "user": {
    "id": 1,
    "username": "storeowner",
    "nickname": "사장님",
    "phone": "010-1234-5678"
  }
}
```

10. 성공 Status Code: 200 OK
11. 주요 실패 Response 예시:

```json
{
  "non_field_errors": [
    "아이디 또는 비밀번호가 올바르지 않습니다."
  ]
}
```

필수값 누락은 해당 필드의 오류 배열입니다.

12. 실패 Status Code: 400: 누락·인증 실패·비활성 계정·JSON 파싱 오류. 405: 미지원 메서드. 415: 파싱 시 미지원 미디어 타입.

## 내 정보 조회

1. 기능명: 내 정보 조회
2. Method: `GET`
3. URL: `/member/me/`
4. 기능 설명: 토큰에 연결된 본인 정보만 반환합니다.
5. 인증 필요 여부: 필수: Token
6. Path Parameter: 없음 (사용자 ID를 받지 않음)
7. Query Parameter: 없음
8. Request Body JSON 예시:

없음 (본문을 보내지 않음)

9. 성공 Response JSON 예시:

```json
{
  "id": 1,
  "username": "storeowner",
  "nickname": "사장님",
  "phone": "010-1234-5678"
}
```

10. 성공 Status Code: 200 OK
11. 주요 실패 Response 예시:

```json
{
  "detail": "인증 자격 증명이 제공되지 않았습니다."
}
```

유효하지 않은 토큰·비활성 사용자도 detail 오류입니다.

12. 실패 Status Code: 401: 토큰 누락·무효·비활성 사용자. 405: 미지원 메서드.

## 로그아웃

1. 기능명: 로그아웃
2. Method: `POST`
3. URL: `/member/logout/`
4. 기능 설명: 인증에 사용된 토큰을 삭제합니다.
5. 인증 필요 여부: 필수: Token
6. Path Parameter: 없음
7. Query Parameter: 없음
8. Request Body JSON 예시:

없음 (본문을 보내지 않음)

9. 성공 Response JSON 예시:

없음. 204 응답은 JSON 객체나 null 없이 본문이 비어 있습니다.

10. 성공 Status Code: 204 No Content
11. 주요 실패 Response 예시:

```json
{
  "detail": "인증 자격 증명이 제공되지 않았습니다."
}
```

유효하지 않은 토큰·비활성 사용자도 detail 오류입니다.

12. 실패 Status Code: 401: 토큰 누락·무효·비활성 사용자·이미 로그아웃한 토큰. 405: 미지원 메서드.
