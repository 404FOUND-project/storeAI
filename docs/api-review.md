| 검토 영역 | 결과 | 제안 |
|---|---|---|
| 현재 URL 충돌 | 중복·가림 충돌 발견 없음 | 신규 경로 연결 시 중첩 경로 검증 |
| 미구현 앱 | store, sales, inventory, review, analysis | serializer·API view·urls.py 및 루트 include 추가 |
| 모델/serializer 필드 | 구현된 회원·공지에서 잘못된 필드 참조 없음 | 공개 필드 제한 유지 |
| 메서드 범위 | 공지 상세는 PUT도 허용 | 의도에 따라 유지 또는 별도 변경 작업에서 제한 |
| 모델 정의 | Store.created_at 중복 선언, 시각 이름 불통일 | 후속 작업에서 정리·호환성 검토 |
| 실행 검증 | 가상환경 Python 실행 불가 | 실행 환경 복구 후 기존 테스트 실행 |

# API 코드 검토

2026-09-26 기준. 이번 작업은 docs/ Markdown만 변경했습니다. 아래는 관찰 결과와 후속 수정 제안이며 Python 코드를 수정하지 않았습니다.

## 확인 범위와 검증 한계

7개 앱의 models.py·views.py와 존재하는 member/notices의 serializers.py·urls.py, notices/permissions.py, config/settings.py·urls.py·test_settings.py, 마이그레이션·admin.py·앱 설정·테스트·기존 문서를 확인했습니다. Django/DRF 상속 동작 중 페이지네이션과 비밀번호 유사성 검증은 설치된 패키지 소스도 확인했습니다.

현재 루트 URLconf는 admin/, member/, notices/만 등록합니다. admin은 Django 관리 화면이므로 이번 JSON API 명세 범위에 포함하지 않습니다. drf-spectacular 설정은 있지만 schema/Swagger view의 URL은 등록되어 있지 않습니다.

backend/.venv/Scripts/python.exe --version 실행이 “Unable to create process”로 실패했습니다. 따라서 HTTP 실호출·테스트 실행·DB 마이그레이션 적용 상태를 검증했다고 주장하지 않습니다. 기존 member/tests.py와 notices/tests.py의 테스트 내용을 소스와 대조했습니다. 다른 5개 앱의 tests.py는 scaffold입니다.

후속 검증 명령(환경 복구 후 backend에서 실행):

```powershell
.venv\Scripts\python.exe manage.py test member notices --settings=config.test_settings
```

test_settings는 메모리 SQLite를 사용하므로 설정된 MySQL에 연결하지 않습니다.

## URL 구조와 충돌

- 현재 member의 signup/login/me/logout과 notices의 목록·정수 pk 상세 사이에 충돌은 없습니다.
- /store/ 및 그 하위 menus/sales/inventory/reviews/analysis 경로는 모두 미등록입니다. 현 상태는 URL 충돌이 아니라 구현 누락입니다.
- docs의 해당 경로들은 요청된 규칙에 맞춘 제안일 뿐 현재 동작하는 URL이 아닙니다. 아직 URL converter·파라미터 이름도 정해져 있지 않습니다.
- Store.owner의 related_name='stores'는 ORM 역참조입니다. URL을 복수형으로 만드는 설정이 아닙니다. 향후 경로는 /store/를 사용해야 합니다.
- notices 앱은 이미 /notices/로 정확히 연결되어 있습니다. 실제 상세 인자는 <int:pk>라 명세도 {pk}로 표기했습니다.
- 메뉴는 store.Menu입니다. 별도 메뉴 앱이나 루트 메뉴 URL을 전제하지 않습니다.

제안: /store/ 하위에 가게 CRUD와 menus 경로를 연결하고, /store/<int:store_id>/sales/·inventory/·reviews/·analysis/를 각 앱에 연결하세요. 상세 조회는 자원 PK와 store_id를 함께 필터링해야 합니다. 이는 향후 구현 제안이며 현재 동작이 아닙니다.

## 누락된 serializer·view·urls.py

| 앱 | 모델 | serializers.py | views.py | urls.py / 루트 연결 |
|---|---|---|---|---|
| member | User | 구현 | 4개 인증 view | 있음 / 연결됨 |
| notices | Notice | 구현 | 목록·생성, 상세·수정·삭제 | 있음 / 연결됨 |
| store | Store, Menu | 없음 | scaffold만 있음 | 없음 / 미연결 |
| sales | Sales, SalesItem | 없음 | scaffold만 있음 | 없음 / 미연결 |
| inventory | Inventory, MenuIngredient | 없음 | scaffold만 있음 | 없음 / 미연결 |
| review | Review | 없음 | scaffold만 있음 | 없음 / 미연결 |
| analysis | AnalysisResult | 없음 | scaffold만 있음 | 없음 / 미연결 |

제안: 각 앱에 공개할 필드·쓰기 권한·FK 검증을 명시한 serializer, API view, urls.py를 구현하고 루트 URLconf에 연결하세요. SalesItem·MenuIngredient의 독립 엔드포인트 여부도 결정해야 합니다. 현재 모델만 보고 중첩 요청/응답이 있다고 판단할 수 없습니다. 회원 정보 변경·탈퇴·비밀번호 변경/재설정도 현재 view와 URL이 없습니다.

## 모델과 serializer 필드 대조

회원·공지의 serializer가 참조하는 모델 필드는 모두 존재합니다. 모델의 모든 필드를 serializer에 노출하지 않는 것은 의도적인 공개 범위 제한으로 보이며 불일치 오류가 아닙니다.

| 위치 | 확인한 사실 | 명세 반영 / 제안 |
|---|---|---|
| member/serializers.py: SignupSerializer | username, password, nickname, phone만 선언; password write_only | 가입 응답은 username/nickname/phone, id·token 없음 |
| member/serializers.py: UserSerializer | id, username, nickname, phone만 읽기 전용 | 로그인 user·내 정보 응답에만 이 4개 필드 |
| member/serializers.py: LoginSerializer | 모델 저장용이 아닌 입력 검증 serializer | user는 검증 중 내부 값; view가 token/user 응답 구성 |
| notices/serializers.py | id/title/content/author/created_at/updated_at | author는 정수 PK 또는 null; author_id·중첩 사용자 아님 |
| 나머지 앱 | serializer 자체 없음 | 모델과 API 필드의 일치 여부를 평가할 계약 없음 |

password는 가입·로그인 serializer 모두 write_only=True, trim_whitespace=False입니다. 가입은 validate_password와 create_user를 사용하여 검증·해시 저장합니다. 공개 UserSerializer는 password를 선언하지 않습니다. 수정 제안 없이 현재 보호 동작을 문서에 반영했습니다.

유사성 검사용 User에 nickname을 넘기지만 기본 UserAttributeSimilarityValidator는 username/first_name/last_name/email을 비교합니다. nickname 유사성까지 요구한다면 후속 작업에서 user_attributes를 명시해야 합니다.

## 모델 정의와 관계에서 주의할 점

| 근거 | 현재 상태·영향 | 후속 수정 제안 |
|---|---|---|
| store/models.py: Store | created_at이 두 번 선언됨; Python 클래스의 마지막 선언만 유효하여 DB 필드는 하나 | 중복 선언 제거 |
| store/models.py: Store | 업종/카테고리 주석 아래 실제 category 필드 없음 | 주석 정리; 새 필드 추가는 별도 요구사항으로 결정 |
| 여러 models.py | Store/Notice/AnalysisResult는 created_at, Menu/Inventory/Review/Sales는 create_at; Menu/Inventory는 update_at, Notice는 updated_at | 현재 이름 그대로 사용. 통일 시 migration·클라이언트 호환성 검토 |
| sales/models.py: SalesItem | menu.store와 sales.store가 같다는 검증 없음 | 동일 가게 검증 추가 |
| inventory/models.py: MenuIngredient | menu.store와 inventory.store 일치 검증 및 조합 unique 제약 없음 | 가게 일치 검증, 중복 허용 정책 확정 |
| sales/models.py | total_amount 합산, 판매 시점 단가 확정 로직 없음 | 계산 주체·가격 정책과 트랜잭션 정의 |
| inventory/models.py | quantity·required_quantity의 음수/0 제한 명시 없음 | 업무 규칙에 맞는 검증 추가 |
| review/models.py | rating에 0~5 제한 없음; sentiment에 choices 없음 | 범위·허용값 검증 필요 여부 결정 |
| review/analysis models.py | keywords/result JSON 내부 스키마 없음 | 내부 필드를 추측하지 말고 스키마부터 정의 |

PositiveIntegerField/PositiveBigIntegerField는 이름만 보고 1 이상이라고 명세화하지 않았습니다. 0도 허용됩니다. 모델의 DecimalField 자릿수는 API의 JSON 숫자/문자열 직렬화 방식까지 정하지 않습니다.

FK 삭제 정책은 Store.owner 및 대부분의 가게 하위 관계가 CASCADE, SalesItem.menu가 PROTECT, Notice.author가 SET_NULL입니다. 판매 품목이 참조하는 메뉴를 삭제하려 하면 보호 예외가 발생할 수 있으며, 현재 해당 API가 없어 그 예외의 HTTP 응답도 정의되지 않았습니다.

제안: 향후 소유권 필터·삭제 보호 오류의 응답 정책을 view/serializer에 명시하세요. related_name과 FK의 _id DB 속성을 자동으로 API 응답에 추가해서는 안 됩니다.

## 명세와 실제 구현의 차이 및 별도 동작

- 이번 7개 명세는 GET/POST/PATCH/DELETE 중심입니다. 공지 상세는 RetrieveUpdateDestroyAPIView를 상속하고 메서드를 제한하지 않아 **PUT /notices/{pk}/도 실제 지원**합니다. 활성 관리자 토큰이 필요하며 title/content를 모두 입력해야 합니다. 성공 200과 응답 필드는 PATCH와 같고, 입력 누락 400·인증 실패 401·권한 부족 403·없는 객체 404가 적용됩니다. PUT을 막으려는 요구라면 후속 코드 변경에서 http_method_names 제한을 검토하세요.
- DRF가 기본 제공하는 OPTIONS, 조회 view의 HEAD는 이번 업무 API 표에서 생략했습니다.
- 공지 페이지네이션은 20개 고정이며 page=last도 DRF 기본 동작으로 허용됩니다. page를 빈 값으로 전달하면 기본 1로 처리됩니다. page_size·검색·정렬 변경 기능은 없습니다.
- 공개 공지 조회도 무효 토큰이 있으면 401입니다. 공지 변경은 작성자 본인에 한정되지 않으며 is_staff인 다른 관리자도 가능합니다.
- 회원가입과 로그인은 authentication_classes=[]로 인증 헤더를 무시합니다. 로그인 실패는 401이 아니라 serializer 검증 오류인 400입니다.
- 로그아웃·공지 삭제는 204이며 JSON {}나 null을 반환하지 않습니다.
- 미등록 URL의 404는 Django 응답입니다. 이를 DRF의 {"detail": ...}로 단정하지 않았습니다. 정상 매칭된 공지 상세에서 객체가 없을 때는 DRF 404입니다.
- 기존 문서의 공개 응답 필드·비밀번호 보호 설명은 구현과 일치했습니다. 이번에는 API별 12개 항목과 Query/Path 구분을 보완하고, 표를 맨 위로 이동했으며 미구현 앱을 분리했습니다.

## 문서 간 연결

[회원](auth-api.md) · [가게·메뉴](store-api.md) · [공지](notices-api.md) · [매출](sales-api.md) · [재고](inventory-api.md) · [리뷰](review-api.md) · [분석](analysis-api.md)
