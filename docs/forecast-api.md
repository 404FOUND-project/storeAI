# 매출 예측 대시보드 API

`GET /sales/stores/{store_id}/forecast/dashboard/`

- 인증: `Authorization: Token <token>` (기존 분석 API와 동일). 매장 소유자 또는 staff만 접근, 그 외는 404.
- 쿼리: `as_of` (선택, YYYY-MM-DD). 생략하면 오늘 이전의 마지막 매출일.
- 이 API는 **항상 200**을 반환한다. 예측이 없거나 날씨 수집이 실패해도 해당 블록이 `null`이고 `notices`에 이유가 담긴다.
- 모든 매출 데이터는 현재 **합성(dummy) 데이터**이다. `data_basis.sales_data_type == "synthetic_dummy"`일 때 화면에 "시연용 합성 데이터 기반" 표시를 해야 한다.

## 응답

```jsonc
{
  "store_id": 1,
  "as_of": "2026-11-21",            // 예측에 사용한 마지막 실제 매출일
  "target_date": "2026-11-22",      // "오늘" 예측 대상일
  "data_basis": {
    "sales_data_type": "synthetic_dummy",
    "note": "실제 POS가 아닌 합성 데이터로 학습·검증한 결과입니다."
  },
  "yesterday": { "date": "2026-11-21", "sales": 512300, "order_count": 52 },   // 없으면 null
  "today": {                                                                    // 예측이 없으면 null
    "date": "2026-11-22",
    "predicted_sales": 455000,
    "predicted_orders": 47,
    "range_80": { "low": 410000, "high": 505000 },                              // 없으면 null
    "change_vs_yesterday": { "amount": -57300, "pct": -11.2 },                  // 어제 실제가 없으면 null
    "model": { "name": "glm_cal", "version": "v1", "cv_wape_pct": 7.7 },
    "weather": { "basis": "short_forecast", "avg_temp_c": 6.1 },                // basis: short_forecast|mid_forecast|climatology|none, 없으면 null
    "published_at": "2026-11-22T19:40:00+09:00",
    "kind": "live"                                                              // live | backfill(과거 시점 재현)
  },
  "last_month": { "start": "2026-10-01", "end": "2026-10-31", "sales": 15277800, "order_count": 1583 },  // 직전 달력월, 없으면 null
  "hourly": {                                                                   // 없으면 null
    "date": "2026-11-22",
    "method": "daily_total_x_historical_hourly_share",
    "method_label": "일 예측값 × 과거 시간대 비중(단순 배분)",
    "hours": [
      { "hour": 9, "label": "09:00", "predicted_sales": 21000, "predicted_orders": 2.1, "is_peak": false, "is_low": true }
    ],
    "peak_hours": [13, 14, 12],
    "low_hours": [9, 21, 10]
  },
  "menus": {                                                                    // 없으면 null
    "date": "2026-11-22",
    "method": "...",
    "method_label": "...",
    "total_predicted_quantity": 80.4,
    "items": [
      { "rank": 1, "menu_id": 2, "menu_name": "아메리카노", "category": "커피", "price": 5000,
        "predicted_quantity": 7.9, "predicted_sales": 39500, "predicted_hot": 6.1, "predicted_ice": 1.8 }
    ]
  },
  "hot_ice": { "predicted_hot": 38.2, "predicted_ice": 14.0, "ice_share_pct": 26.8,
               "temperature_basis": "short_forecast" },                          // 없으면 null
  "insights": [
    { "id": "temp_ice_share", "title": "기온이 오르면 ICE 비중이 커집니다",
      "body": "...", "evidence": { "n_days": 669 }, "confidence": "medium", "is_synthetic": true }
  ],
  "comparison": [                                                                // 최근 예측 vs 실제, 오래된 순. 비어 있을 수 있음
    { "date": "2026-11-20", "predicted_sales": 470000, "actual_sales": 489100,
      "error": -19100, "error_pct": -3.9, "kind": "backfill" }
  ],
  "notices": ["단기예보를 아직 수집하지 못해 기온 정보 없이 예측했습니다."]      // 항상 배열
}
```

## 규칙

- 수치 필드는 `null`일 수 있다. `null`을 0으로 표시하지 않는다.
- 예측값과 실제값은 화면에서 시각적으로 구분한다(예: "예상" 배지, 점선/다른 색).
- `predicted_orders`, `predicted_quantity`, `predicted_hot` 등은 소수일 수 있다. 화면에서는 반올림해 표시한다.
- `kind == "backfill"`은 과거 시점에 그 날짜 이전 데이터만으로 재현한 예측이며, 실시간 발행분이 아니다.
