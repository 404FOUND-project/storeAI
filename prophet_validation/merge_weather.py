
import pandas as pd

# 1. 매출 데이터 불러오기
sales = pd.read_csv("lower_manhattan_daily_sales.csv")
sales["ds"] = pd.to_datetime(sales["ds"])

# 2. 날씨 데이터 불러오기
weather = pd.read_csv("new_york_weather.csv")
weather["ds"] = pd.to_datetime(weather["ds"])

# 3. 날짜 기준으로 결합
merged = pd.merge(
    sales,
    weather,
    on="ds",
    how="inner"
)

# 4. 결합 결과 확인
print("===== 매출 + 날씨 데이터 =====")
print("매출 데이터:", len(sales))
print("날씨 데이터:", len(weather))
print("결합 데이터:", len(merged))

print("\n===== 데이터 앞부분 =====")
print(merged.head())

print("\n===== 결측치 확인 =====")
print(merged.isnull().sum())

# 5. 저장
merged.to_csv("lower_manhattan_sales_weather.csv", index=False)

print("\n파일 저장 완료: lower_manhattan_sales_weather.csv")
