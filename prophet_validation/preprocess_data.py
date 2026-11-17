
import pandas as pd

# 1. 원본 데이터 읽기
df = pd.read_csv("coffee-shop-sales-revenue.csv", sep="|")

# 2. 날짜 형식 변환
df["transaction_date"] = pd.to_datetime(df["transaction_date"])

# 3. Lower Manhattan 지점만 추출
branch = df[df["store_location"] == "Lower Manhattan"].copy()

# 4. 거래별 매출 계산
branch["revenue"] = (
    branch["transaction_qty"] * branch["unit_price"]
)

# 5. 일별 총매출 집계
daily_sales = (
    branch.groupby("transaction_date", as_index=False)["revenue"]
    .sum()
    .rename(columns={
        "transaction_date": "ds",
        "revenue": "y"
    })
)

# 6. 메뉴별 일일 판매량 집계
menu_daily = (
    branch.groupby(
        ["transaction_date", "product_detail"],
        as_index=False
    )["transaction_qty"]
    .sum()
    .rename(columns={
        "transaction_date": "ds",
        "transaction_qty": "y"
    })
)

# 7. 결과 저장
daily_sales.to_csv("lower_manhattan_daily_sales.csv", index=False)
menu_daily.to_csv("lower_manhattan_menu_daily.csv", index=False)

# 8. 결과 확인
print("===== Lower Manhattan 데이터 =====")
print("거래 건수:", len(branch))
print("판매 메뉴 수:", branch["product_detail"].nunique())
print("일별 매출 데이터:", len(daily_sales))
print("메뉴별 판매 데이터:", len(menu_daily))

print("\n===== 일별 총매출 앞부분 =====")
print(daily_sales.head())

print("\n===== 메뉴별 판매량 앞부분 =====")
print(menu_daily.head())
