
import pandas as pd
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error

# 1. 데이터 불러오기
df = pd.read_csv("lower_manhattan_daily_sales.csv")
df["ds"] = pd.to_datetime(df["ds"])

# 2. 기존과 동일하게 학습/테스트 분리
split_index = int(len(df) * 0.8)
train = df.iloc[:split_index].copy()
test = df.iloc[split_index:].copy()

# 3. 학습 데이터의 요일별 평균 매출 계산
weekday_avg = train.groupby(
    train["ds"].dt.day_of_week
)["y"].mean()

# 4. 테스트 날짜의 요일에 맞춰 평균 매출 예측
result = test[["ds", "y"]].copy()
result["baseline_predicted"] = (
    result["ds"].dt.day_of_week.map(weekday_avg)
)

# 5. Prophet 결과 불러오기
prophet_result = pd.read_csv("prophet_basic_result.csv")
prophet_result["ds"] = pd.to_datetime(prophet_result["ds"])

result = result.merge(
    prophet_result[["ds", "predicted"]],
    on="ds",
    how="left"
)

# 6. 성능 계산 함수
def calculate_metrics(actual, predicted):
    mae = mean_absolute_error(actual, predicted)
    rmse = np.sqrt(mean_squared_error(actual, predicted))
    wape = (
        np.abs(actual - predicted).sum()
        / actual.sum()
    ) * 100

    return mae, rmse, wape

# 7. 두 모델 비교
baseline_metrics = calculate_metrics(
    result["y"],
    result["baseline_predicted"]
)

prophet_metrics = calculate_metrics(
    result["y"],
    result["predicted"]
)

print("===== 모델 성능 비교 =====")
print(
    f"요일별 평균 예측 | "
    f"MAE: {baseline_metrics[0]:.2f} | "
    f"RMSE: {baseline_metrics[1]:.2f} | "
    f"WAPE: {baseline_metrics[2]:.2f}%"
)

print(
    f"Prophet 기본 모델 | "
    f"MAE: {prophet_metrics[0]:.2f} | "
    f"RMSE: {prophet_metrics[1]:.2f} | "
    f"WAPE: {prophet_metrics[2]:.2f}%"
)

# 8. 결과 저장
result.to_csv("baseline_comparison.csv", index=False)

print("\n비교 결과 저장 완료: baseline_comparison.csv")
