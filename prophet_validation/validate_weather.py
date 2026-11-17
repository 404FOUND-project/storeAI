
import pandas as pd
import numpy as np
from prophet import Prophet
from prophet.make_holidays import make_holidays_df
from sklearn.metrics import mean_absolute_error, mean_squared_error

# 1. 매출 + 날씨 데이터 불러오기
df = pd.read_csv("lower_manhattan_sales_weather.csv")
df["ds"] = pd.to_datetime(df["ds"])

# 2. 학습 데이터와 테스트 데이터 분리
split_index = int(len(df) * 0.8)
train = df.iloc[:split_index].copy()
test = df.iloc[split_index:].copy()

# 3. 미국 공휴일 데이터 생성
us_holidays = make_holidays_df(
    year_list=[2023],
    country="US"
)

# 4. 날씨 변수를 추가한 Prophet 모델 생성
model = Prophet(
    holidays=us_holidays,
    weekly_seasonality=True,
    yearly_seasonality=False,
    daily_seasonality=False
)

# 5. 날씨 변수를 외부 회귀 변수로 등록
model.add_regressor("temperature")
model.add_regressor("precipitation")

# 6. 모델 학습
model.fit(train[[
    "ds",
    "y",
    "temperature",
    "precipitation"
]])

# 7. 테스트 기간 예측
future = test[[
    "ds",
    "temperature",
    "precipitation"
]].copy()

forecast = model.predict(future)

# 8. 예측 결과 정리
result = test[["ds", "y"]].copy()
result["predicted"] = forecast["yhat"].values
result["predicted"] = result["predicted"].clip(lower=0)

# 9. 성능 지표 계산
mae = mean_absolute_error(result["y"], result["predicted"])
rmse = np.sqrt(mean_squared_error(result["y"], result["predicted"]))
wape = (
    np.abs(result["y"] - result["predicted"]).sum()
    / result["y"].sum()
) * 100

print("===== 공휴일 + 날씨 Prophet 성능 =====")
print(f"MAE: {mae:.2f}")
print(f"RMSE: {rmse:.2f}")
print(f"WAPE: {wape:.2f}%")

# 10. 결과 저장
result.to_csv("prophet_weather_result.csv", index=False)

print("\n===== 예측 결과 앞부분 =====")
print(result.head(10))

print("\n결과 저장 완료: prophet_weather_result.csv")
