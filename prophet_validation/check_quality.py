
import pandas as pd

# 원본 데이터 읽기
df = pd.read_csv("coffee-shop-sales-revenue.csv", sep="|")

# Lower Manhattan 추출
branch = df[df["store_location"] == "Lower Manhattan"].copy()

branch["transaction_date"] = pd.to_datetime(
    branch["transaction_date"]
)

branch["revenue"] = (
    branch["transaction_qty"] * branch["unit_price"]
)

# 일별 매출 집계
daily = branch.groupby("transaction_date").agg(
    daily_revenue=("revenue", "sum"),
    transaction_count=("transaction_id", "count")
)

# 전체 날짜 범위 확인
all_dates = pd.date_range(
    daily.index.min(),
    daily.index.max(),
    freq="D"
)

missing_dates = all_dates.difference(daily.index)

print("===== 날짜 확인 =====")
print("전체 날짜 수:", len(all_dates))
print("매출 기록이 있는 날짜:", len(daily))
print("누락 날짜:", list(missing_dates))

print("\n===== 매출 확인 =====")
print("0원 매출 날짜:", (daily["daily_revenue"] == 0).sum())
print("음수 매출 날짜:", (daily["daily_revenue"] < 0).sum())
print("최소 일별 매출:", daily["daily_revenue"].min())
print("최대 일별 매출:", daily["daily_revenue"].max())

print("\n===== 거래 및 수량 확인 =====")
print("0 이하 판매 수량:", (branch["transaction_qty"] <= 0).sum())
print("0 이하 단가:", (branch["unit_price"] <= 0).sum())
print("0 이하 거래 건수 날짜:", (daily["transaction_count"] <= 0).sum())

print("\n===== 메뉴별 판매량 확인 =====")
menu_counts = branch.groupby("product_detail")[
    "transaction_qty"
].sum()

print("메뉴 종류:", len(menu_counts))
print("판매량이 가장 적은 메뉴:", menu_counts.idxmin())
print("최소 메뉴 판매량:", menu_counts.min())
print("판매량이 가장 많은 메뉴:", menu_counts.idxmax())
print("최대 메뉴 판매량:", menu_counts.max())
