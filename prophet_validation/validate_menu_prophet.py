
import pandas as pd
import numpy as np
from prophet import Prophet
from sklearn.metrics import mean_absolute_error, mean_squared_error

# 1. 데이터 불러오기
df = pd.read_csv("lower_manhattan_menu_daily_51.csv")
df["ds"] = pd.to_datetime(df["ds"])

# 2. 검증 기간 설정
train_end = pd.Timestamp("2023-05-24")
test_start = pd.Timestamp("2023-05-25")

results = []
predictions = []

# 3. 메뉴별 반복 검증
for menu in df["product_detail"].unique():

    menu_df = df[df["product_detail"] == menu].copy()
    menu_df = menu_df.sort_values("ds")

    train = menu_df[menu_df["ds"] <= train_end].copy()
    test = menu_df[menu_df["ds"] >= test_start].copy()

    if len(train) < 30 or len(test) == 0:
        continue

    # Prophet 학습
    model = Prophet(
        weekly_seasonality=True,
        yearly_seasonality=False,
        daily_seasonality=False
    )

    model.fit(train[["ds", "y"]])

    # 테스트 기간 예측
    future = test[["ds"]].copy()
    forecast = model.predict(future)

    predicted = np.maximum(forecast["yhat"].values, 0)
    actual = test["y"].values

    # Prophet 평가
    prophet_mae = mean_absolute_error(actual, predicted)
    prophet_rmse = np.sqrt(mean_squared_error(actual, predicted))
    prophet_wape = (
        np.sum(np.abs(actual - predicted)) / np.sum(np.abs(actual)) * 100
        if np.sum(np.abs(actual)) > 0 else np.nan
    )

    # 요일별 평균 판매량 기준 모델
    train["weekday"] = train["ds"].dt.day_of_week
    weekday_avg = train.groupby("weekday")["y"].mean()

    baseline_predicted = (
        test["ds"].dt.day_of_week.map(weekday_avg).fillna(0).values
    )

    baseline_mae = mean_absolute_error(actual, baseline_predicted)
    baseline_rmse = np.sqrt(mean_squared_error(actual, baseline_predicted))
    baseline_wape = (
        np.sum(np.abs(actual - baseline_predicted)) / np.sum(np.abs(actual)) * 100
        if np.sum(np.abs(actual)) > 0 else np.nan
    )

    results.append({
        "메뉴": menu,
        "Prophet_MAE": prophet_mae,
        "Prophet_RMSE": prophet_rmse,
        "Prophet_WAPE": prophet_wape,
        "기준모델_MAE": baseline_mae,
        "기준모델_RMSE": baseline_rmse,
        "기준모델_WAPE": baseline_wape,
        "Prophet_우세": prophet_wape < baseline_wape
    })

    for date, actual_value, predicted_value in zip(
        test["ds"], actual, predicted
    ):
        predictions.append({
            "날짜": date,
            "메뉴": menu,
            "실제판매량": actual_value,
            "예측판매량": predicted_value
        })

    print(f"완료: {menu}")

# 4. 결과 저장
result_df = pd.DataFrame(results)
prediction_df = pd.DataFrame(predictions)

result_df.to_csv(
    "menu_prophet_validation_summary.csv",
    index=False,
    encoding="utf-8-sig"
)

prediction_df.to_csv(
    "menu_prophet_validation_predictions.csv",
    index=False,
    encoding="utf-8-sig"
)

# 5. 전체 성능 요약
print("\n===== 메뉴별 Prophet 검증 완료 =====")
print("검증 메뉴 수:", len(result_df))
print("Prophet이 기준 모델보다 우수한 메뉴 수:",
      result_df["Prophet_우세"].sum())

print("\n===== 메뉴별 평균 성능 =====")
print(result_df[[
    "Prophet_MAE",
    "Prophet_RMSE",
    "Prophet_WAPE",
    "기준모델_MAE",
    "기준모델_RMSE",
    "기준모델_WAPE"
]].mean().round(2))

print("\n===== Prophet이 우수한 메뉴 =====")
print(
    result_df[result_df["Prophet_우세"]][
        ["메뉴", "Prophet_WAPE", "기준모델_WAPE"]
    ].to_string(index=False)
)

print("\n저장 완료:")
print("- menu_prophet_validation_summary.csv")
print("- menu_prophet_validation_predictions.csv")
