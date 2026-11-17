
import pandas as pd

# 1. 메뉴별 일일 판매량 데이터 불러오기
df = pd.read_csv("lower_manhattan_menu_daily.csv")
df["ds"] = pd.to_datetime(df["ds"])

print("===== 전체 데이터 확인 =====")
print("전체 기록 수:", len(df))
print("메뉴 종류:", df["product_detail"].nunique())
print("날짜 수:", df["ds"].nunique())

# 2. 메뉴별 판매 기록 확인
menu_summary = df.groupby("product_detail").agg(
    판매기록일수=("ds", "count"),
    총판매량=("y", "sum"),
    평균일판매량=("y", "mean"),
    최소판매량=("y", "min"),
    최대판매량=("y", "max")
).sort_values("총판매량", ascending=False)

print("\n===== 판매량 상위 10개 메뉴 =====")
print(menu_summary.head(10))

print("\n===== 판매량 하위 10개 메뉴 =====")
print(menu_summary.tail(10))

# 3. 메뉴별 기록 일수 분포
print("\n===== 메뉴별 판매 기록 일수 =====")
print(menu_summary["판매기록일수"].describe())

# 4. 판매 기록이 없는 날짜 확인
all_dates = pd.date_range(
    df["ds"].min(),
    df["ds"].max(),
    freq="D"
)

missing_counts = {}

for menu in df["product_detail"].unique():
    menu_dates = df.loc[
        df["product_detail"] == menu, "ds"
    ]

    missing_counts[menu] = len(
        all_dates.difference(menu_dates)
    )

missing_summary = pd.Series(missing_counts)

print("\n===== 메뉴별 판매 기록 누락 날짜 =====")
print("누락 날짜가 가장 적은 메뉴:", missing_summary.idxmin())
print("최소 누락 일수:", missing_summary.min())
print("누락 날짜가 가장 많은 메뉴:", missing_summary.idxmax())
print("최대 누락 일수:", missing_summary.max())

print("\n===== 메뉴별 누락 날짜 상위 10개 =====")
print(missing_summary.sort_values(ascending=False).head(10))

# 5. 결과 저장
menu_summary.to_csv("menu_data_summary.csv", encoding="utf-8-sig")

print("\n분석 결과 저장 완료: menu_data_summary.csv")

# 6. 판매 기록이 150일 이상인 메뉴 확인
reliable_menus = menu_summary[
    menu_summary["판매기록일수"] >= 150
]

print("\n===== 판매 기록 150일 이상 메뉴 =====")
print("메뉴 수:", len(reliable_menus))
print(reliable_menus.index.tolist())

print("\n===== 판매 기록 150일 미만 메뉴 =====")
print(
    menu_summary[
        menu_summary["판매기록일수"] < 150
    ].index.tolist()
)