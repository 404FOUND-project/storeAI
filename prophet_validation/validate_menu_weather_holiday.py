
import pandas as pd
import numpy as np
import holidays
from prophet import Prophet
from sklearn.metrics import mean_absolute_error, mean_squared_error

# 1. 데이터 불러오기
sales = pd.read_csv("lower_manhattan_menu_daily_51.csv")
weather = pd.read_csv("new_york_weather.csv")

sales["ds"] = pd.to_datetime(sales["ds"])
weather["ds"] = pd.to_datetime(weather["ds"])

# 날씨 데이터 열 확인 및 이름 통일
weather = weather.rename(columns={
    "temperature_2m_mean": "temperature",
    "precipitation_sum": "precipitation"
})

# 2. 매출 데이터와 날씨 결합
df = sales.merge(weather, on="ds", how="left")

if df[["temperature", "precipitation"]].isnull().any().any():
    raise ValueError("날씨 데이터에 누락값이 있습니다.")

# 3. 미국 공휴일 생성
us_holidays = holidays.US(years=[2023])
holiday_dates = set(pd.to_datetime(list(us_holidays.keys())))

df["is_holiday"] = df["ds"].isin(holiday_dates).astype(int)

# 4. 학습 / 테스트 기간
train_end = pd.Timestamp("2023-05-24")
test_start = pd.Timestamp("2023-05-25")

results = []

# 5. 메뉴별 세 모델 검증
for menu in df["product_detail"].unique():

    menu_df = df[df["product_detail"] == menu].copy()
    menu_df = menu_df.sort_values("ds")

    train = menu_df[menu_df["ds"] <= train_end].copy()
    test = menu_df[menu_df["ds"] >= test_start].copy()

    if len(train) < 30 or len(test) == 0:
        continue

    actual = test["y"].values

    models = {
        "기본 Prophet": [],
        "공휴일 Prophet": ["is_holiday"],
        "공휴일+날씨 Prophet": [
            "is_holiday",
            "temperature",
            "precipitation"
        ]
    }

    for model_name, regressors in models.items():

        model = Prophet(
            weekly_seasonality=True,
            yearly_seasonality=False,
            daily_seasonality=False
        )

        for regressor in regressors:
            model.add_regressor(regressor)

        train_columns = ["ds", "y"] + regressors
        test_columns = ["ds"] + regressors

        model.fit(train[train_columns])

        forecast = model.predict(test[test_columns])

        predicted = np.maximum(forecast["yhat"].values, 0)

        mae = mean_absolute_error(actual, predicted)
        rmse = np.sqrt(mean_squared_error(actual, predicted))

        denominator = np.sum(np.abs(actual))
        wape = (
            np.sum(np.abs(actual - predicted)) / denominator * 100
            if denominator > 0 else np.nan
        )

        results.append({
            "메뉴": menu,
            "모델": model_name,
            "MAE": mae,
            "RMSE": rmse,
            "WAPE": wape
        })

    print(f"완료: {menu}")

# 6. 결과 저장
result_df = pd.DataFrame(results)

result_df.to_csv(
    "menu_weather_holiday_validation.csv",
    index=False,
    encoding="utf-8-sig"
)

# 7. 전체 모델 평균 성능 비교
summary = result_df.groupby("모델")[
    ["MAE", "RMSE", "WAPE"]
].mean().round(2)

print("\n===== 메뉴별 모델 평균 성능 비교 =====")
print(summary)

# 8. 메뉴별 WAPE 비교
pivot = result_df.pivot(
    index="메뉴",
    columns="모델",
    values="WAPE"
)

print("\n===== 메뉴별 WAPE 비교 =====")
print(pivot.round(2).to_string())

print("\n저장 완료: menu_weather_holiday_validation.csv")
