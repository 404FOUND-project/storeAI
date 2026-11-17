
import pandas as pd
import numpy as np
from prophet import Prophet
from prophet.make_holidays import make_holidays_df
from sklearn.metrics import mean_absolute_error, mean_squared_error

# 1. 일별 매출 데이터 불러오기
df = pd.read_csv("lower_manhattan_daily_sales.csv")
df["ds"] = pd.to_datetime(df["ds"])

# 2. 학습 데이터와 테스트 데이터 분리
split_index = int(len(df) * 0.8)
train = df.iloc[:split_index].copy()
test = df.iloc[split_index:].copy()

# 3. 미국 공휴일 데이터 생성
# Lower Manhattan은 미국 뉴욕에 있으므로 미국 공휴일 사용
years = [2023]

us_holidays = make_holidays_df(
    year_list=years,
    country="US"
)

print("===== 미국 공휴일 데이터 =====")
print(us_holidays.to_string(index=False))

# 4. 공휴일을 적용한 Prophet 모델 생성
model = Prophet(
    holidays=us_holidays,
    weekly_seasonality=True,
    yearly_seasonality=False,
    daily_seasonality=False
)

# 5. 모델 학습
model.fit(train)

# 6. 테스트 기간 예측
future = test[["ds"]].copy()
forecast = model.predict(future)

# 7. 예측 결과 정리
result = test[["ds", "y"]].copy()
result["predicted"] = forecast["yhat"].values
result["predicted"] = result["predicted"].clip(lower=0)

# 8. 성능 지표 계산
mae = mean_absolute_error(result["y"], result["predicted"])
rmse = np.sqrt(mean_squared_error(result["y"], result["predicted"]))
wape = (
    np.abs(result["y"] - result["predicted"]).sum()
    / result["y"].sum()
) * 100

print("\n===== 공휴일 적용 Prophet 성능 =====")
print(f"MAE: {mae:.2f}")
print(f"RMSE: {rmse:.2f}")
print(f"WAPE: {wape:.2f}%")

# 9. 결과 저장
result.to_csv("prophet_holiday_result.csv", index=False)

print("\n결과 저장 완료: prophet_holiday_result.csv")
