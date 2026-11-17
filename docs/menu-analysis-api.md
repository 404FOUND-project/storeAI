# 메뉴 수익성·세트 추천 API

기준일: 2026-11-17 · 로컬 더미 DB에서 동작 확인. 로그인(Token) 필요, 본인 매장만.
**원가·단가·레시피는 시연용 가짜 값**입니다 (`manage.py seed_dummy_costs`로 생성).

## 수익성·인기 순위 `GET /store/{store_id}/menus/profitability/`

| 쿼리 | 설명 |
|---|---|
| days | 최근 N일만 집계. 없으면 전체 기간 |

판매량 순으로 정렬된 목록입니다.

```json
{
  "menu_id": 10, "name": "아메리카노", "price": 5000,
  "quantity": 1066, "revenue": 5330000,
  "avg_unit_cost": 504, "cost_total": 537264,
  "profit": 4792736, "margin_rate": 89.9,
  "popularity_rank": 1
}
```

- 원가가 없는 메뉴는 `avg_unit_cost`, `cost_total`, `profit`, `margin_rate`가 `null`.
- 원가는 `inventory_recipecostsnapshot`(팀원 원가 표)의 최신 값, 판매는 `sales_salesitem`을 읽습니다. 쓰지 않음.

## 세트 메뉴 추천 `GET /store/{store_id}/menus/set-recommend/`

| 쿼리 | 설명 |
|---|---|
| top | 상위 N개. 기본 10, 1~50 |

```json
{
  "total_orders": 3095, "multi_item_orders": 1785,
  "sets": [{
    "menus": [{"menu_id": 23, "name": "발로나 초코라떼"}, {"menu_id": 35, "name": "블루베리 판나코타"}],
    "orders_together": 8, "support": 0.45, "confidence": 10.5, "lift": 2.29,
    "total_price": 12700, "set_price": 12200, "discount": 500
  }]
}
```

- 메뉴가 2개 이상 담긴 주문만 분석(Apriori 방식), `lift` 높은 순.
- `support`·`confidence`는 %. 세트 가격은 합계 − 500원.

## 화면 연결 (Flutter, 아직 미연결)

- "세트 추천" 탭(`setRecommendationPage`)은 현재 하드코딩 값. 이 API의 `sets`로 교체하면 됨.
- 카드 제목 = 두 메뉴명, 큰 숫자 = `confidence`, 오른쪽 = `set_price`.
