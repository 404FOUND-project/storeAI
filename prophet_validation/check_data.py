import pandas as pd

df = pd.read_csv("coffee-shop-sales-revenue.csv", sep="|")

print("\n===== 데이터 크기 =====")
print(df.shape)

print("\n===== 컬럼 이름 =====")
print(df.columns.tolist())

print("\n===== 데이터 앞부분 =====")
print(df.head())

print("\n===== 지점 목록 =====")
print(df["store_location"].unique())

print("\n===== 날짜 범위 =====")
print(df["transaction_date"].min())
print(df["transaction_date"].max())