# 재고·발주 추천 API

기준일: 2026-11-17 · 로컬 더미 DB에서 동작 확인. 모든 API는 **로그인(Token) 필요**, 본인 매장만 접근 가능.

| 기능 | Method | URL |
|---|---|---|
| 재고 목록 조회 | GET | /store/{store_id}/inventory/ |
| 재고 등록 | POST | /store/{store_id}/inventory/ |
| 재고 상세·수정·삭제 | GET / PATCH / DELETE | /store/{store_id}/inventory/{id}/ |
| 발주 추천 | GET | /store/{store_id}/inventory/reorder/?target_days=7 |

## 재고 목록 `GET /store/{store_id}/inventory/`

응답: `{"count": 16, "results": [...]}`

```json
{
  "id": 11, "ingredient_name": "우유", "quantity": "5000.00", "unit": "ml",
  "expiration_date": "2026-12-01",
  "daily_usage": 4537.14, "days_left": 1.1, "stock_status": "low",
  "days_to_expiry": 14, "expiry_status": "ok"
}
```

- `stock_status`: `low`(남은 일수 3일 미만) / `ok` / `no_usage`(사용 기록 없음)
- `expiry_status`: `ok` / `expiring`(3일 이내) / `expired`
- 등록·수정 가능 필드: `ingredient_name`, `quantity`, `unit`, `expiration_date`

## 발주 추천 `GET /store/{store_id}/inventory/reorder/`

| 쿼리 | 설명 |
|---|---|
| target_days | 며칠치 재고를 확보할지. 기본 7, 1~60. 범위 밖이면 400 |

```json
{
  "target_days": 7,
  "basis": "최근 14일 판매량 평균 (예측 연결 전 임시 방식)",
  "count": 16,
  "results": [{
    "inventory_id": 11, "ingredient_name": "우유", "unit": "ml", "quantity": "5000.00",
    "daily_usage": 4537.14, "days_left": 1.1, "stock_status": "low",
    "expiration_date": "2026-12-01",
    "recommended_order_qty": "26761",
    "note": "7일치 확보 기준"
  }]
}
```

- 계산: `하루 사용량 × min(목표 일수, 유통기한까지 남은 일수) − 현재 재고`. 유통기한 안에 못 쓸 양은 추천하지 않음.
- 하루 사용량: `메뉴 판매량 × 레시피 재료량`. 기본은 최근 14일 평균.
- A의 예측 표 `sales_forecast`에 값이 있으면 그 합산으로 대신 계산하고 `basis`가 바뀜.
- 정렬: 부족한 재료가 위로.
- 재고 항목이 재료(`ingredient`)와 연결돼 있어야 사용량이 계산됨. 연결이 없으면 `no_usage`.
