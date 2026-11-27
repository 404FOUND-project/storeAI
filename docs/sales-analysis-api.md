# 매출 분석·예측 API

구현 위치: `backend/sales/` (`urls.py`, `views.py`, `services/queries.py`, `services/analytics.py`, `services/forecasting.py`). 루트 URL은 `sales/`로 연결됩니다 (`backend/analysis/config/urls.py`).

## 공통

- 인증: `Authorization: Token <key>` (로그인 API로 발급). 인증 없음 → 401.
- 권한: 매장 소유자 또는 관리자(`is_staff`). 다른 사람의 매장은 존재 여부를 숨기려고 404를 반환합니다.
- 날짜는 모두 KST 달력 날짜입니다 (23:30 KST 주문은 그 KST 날짜의 매출).
- 읽기 전용입니다. DB에 쓰거나 새 테이블을 만들지 않습니다 (예측은 저장하지 않고 요청 시 계산).
- 매출 = `Sales.total_amount` 합, 주문 건수 = `Sales` 행 수, 객단가 = 매출 ÷ 주문 건수 (원 단위 반올림).
- 매출 행이 없는 날은 "데이터 없음"이며 0원으로 취급하지 않습니다 (`days_with_data`로 확인).

## 분석

| Method | URL | 설명 |
|---|---|---|
| GET | `/sales/stores/{store_id}/analysis/sales/` | 일·주·월별 매출, 주문 건수, 객단가 |
| GET | `/sales/stores/{store_id}/analysis/patterns/` | 요일별·시간대별 매출 |
| GET | `/sales/stores/{store_id}/analysis/comparison/` | 전일·전주·전월 대비 변화 |

### `analysis/sales/`
- `granularity`: `day`(기본) / `week`(월요일 시작 ISO 주) / `month`
- `start`, `end`: `YYYY-MM-DD`(양끝 포함). 생략 시 `end`는 최근 매출일, `start`는 일 30일·주 84일·월 365일 전. 최대 1100일, `start > end`는 400.
- 요청 범위에 걸쳐 잘린 주·월은 `is_partial: true`.
- 응답: `summary`(`sales`, `order_count`, `average_ticket`, `days_with_data`)와 `series[]`(`period_start`, `period_end`, `is_partial`, 같은 지표).

### `analysis/patterns/`
- `start`, `end`: 기본은 최근 365일.
- `weekday[]`: 요일(월=0)별 `avg_daily_sales`, `avg_daily_orders`, `average_ticket`, 합계, `days_with_data`.
- `hourly[]`: 시간(0~23, 매출이 있는 시간만)별 합계, 하루 평균, 객단가, `sales_share_pct`.

### `analysis/comparison/`
- `as_of`: 기준일(기본: 최근 매출일). 다음 4개 블록을 반환하며 각 블록에 `sales`, `order_count`, `average_ticket`의 `current`/`base`/`change`/`change_pct`가 있습니다.
  - `day_vs_previous_day`: 기준일 vs 전일
  - `day_vs_same_weekday_last_week`: 기준일 vs 7일 전(전주 동요일)
  - `week_vs_previous_week`: 최근 7일 vs 그 이전 7일
  - `month_to_date_vs_previous_month`: 이달 1일~기준일 vs 전월 1일~같은 일자(전월이 짧으면 말일까지)
- 비교 기간에 데이터가 없으면 `change_pct`는 `null`이고 `note`에 사유가 표시됩니다.

## 예측

| Method | URL | 설명 |
|---|---|---|
| GET | `/sales/stores/{store_id}/forecast/next-day/` | 다음 날 매출·주문 건수 |
| GET | `/sales/stores/{store_id}/forecast/menu-quantity/` | 다음 날 메뉴별 예상 주문량 |

- `as_of`: 예측 기준일(기본: 최근 매출일). **`as_of` 이후 데이터는 읽지 않으며**, 예측 대상일은 `as_of + 1일`입니다.
- 과거 데이터가 부족하면 422 (최근 12주 중 28일 미만, 또는 직전 14일 중 7일 미만).

### 방법
요일 지수(최근 12주 요일별 평균) × 최근 수준(직전 14일을 요일 보정한 평균). 비교한 단순 방법(지난주 같은 요일, 요일 평균, 지수평활) 중 하루 앞 백테스트가 가장 정확해 선택했습니다. 메뉴별 수량은 "최근 8주 메뉴 비중 × 총수량 예측"입니다.

### 응답 (`next-day`)
`predicted_sales`, `predicted_order_count`, `predicted_average_ticket`, 각 `*_range_80`(최근 56일 백테스트 오차로 만든 경험적 80% 범위), `sales_backtest`/`orders_backtest`(최근 56일 WAPE·MAE).

### 응답 (`menu-quantity`)
`total_expected_quantity`, `menus[]`(`menu_id`, `menu_name`, `expected_quantity`, `expected_quantity_rounded`), `backtest`(최근 28일 메뉴 합산 WAPE).

### 정확도 (이 저장소의 합성 매출 `sales_dummy_v1_final`, 2025-04-01~2026-10-31 하루 앞 예측 579일)

| 대상 | WAPE |
|---|---|
| 일 매출 | 10.7% |
| 일 주문 건수 | 8.6% |
| 메뉴별 일 수량 (27개 메뉴 합산, 최근 28일) | 약 47~50% |

- 80% 범위의 실제 포함률(2026년 304일, 사후 검증): 77.6%.

### 한계
- **합성 데이터 기준 수치입니다.** 실제 고객 행동에 대한 검증이 아닙니다.
- 공휴일·학사일정은 DB에 없어 입력하지 않았습니다. 평일 공휴일 26일은 WAPE 24.1%로 과대 예측(+24.1%)하고 다른 날은 10.2%입니다.
- 메뉴별 일 판매량은 1.5~7.4개의 작은 정수라 메뉴 단위 오차가 큽니다. 합계 수량이 더 안정적입니다.
- 날씨는 사용하지 않았습니다 (HOT/ICE 예측은 별도 기능).
