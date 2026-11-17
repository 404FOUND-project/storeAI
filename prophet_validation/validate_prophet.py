
import pandas as pd
from prophet import Prophet
from sklearn.metrics import mean_absolute_error, mean_squared_error
import numpy as np

# 1. 일별 매출 데이터 불러오기
df = pd.read_csv("lower_manhattan_daily_sales.csv")
df["ds"] = pd.to_datetime(df["ds"])

# 2. 학습 데이터와 테스트 데이터 분리
# 앞의 80%로 학습하고 뒤의 20%로 검증
split_index = int(len(df) * 0.8)

train = df.iloc[:split_index].copy()
test = df.iloc[split_index:].copy()

print("===== 데이터 분리 =====")
print("전체 데이터:", len(df))
print("학습 데이터:", len(train))
print("테스트 데이터:", len(test))
print("학습 기간:", train["ds"].min(), "~", train["ds"].max())
print("테스트 기간:", test["ds"].min(), "~", test["ds"].max())

# 3. Prophet 모델 생성 및 학습
model = Prophet(
    weekly_seasonality=True,
    yearly_seasonality=False,
    daily_seasonality=False
)

model.fit(train)

# 4. 테스트 기간 예측
future = test[["ds"]].copy()
forecast = model.predict(future)

# 5. 실제값과 예측값 비교
result = test[["ds", "y"]].copy()
result["predicted"] = forecast["yhat"].values

# 매출 예측값이 음수가 되지 않도록 처리
result["predicted"] = result["predicted"].clip(lower=0)

# 6. 성능 지표 계산
mae = mean_absolute_error(result["y"], result["predicted"])
rmse = np.sqrt(mean_squared_error(result["y"], result["predicted"]))
wape = (
    np.abs(result["y"] - result["predicted"]).sum()
    / result["y"].sum()
) * 100

print("\n===== Prophet 기본 모델 성능 =====")
print(f"MAE: {mae:.2f}")
print(f"RMSE: {rmse:.2f}")
print(f"WAPE: {wape:.2f}%")

# 7. 예측 결과 저장
result.to_csv("prophet_basic_result.csv", index=False)

print("\n===== 예측 결과 앞부분 =====")
print(result.head(10))

print("\n결과 저장 완료: prophet_basic_result.csv")
