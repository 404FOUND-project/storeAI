
import pandas as pd

# 1. 기존 메뉴별 판매 데이터 불러오기
df = pd.read_csv("lower_manhattan_menu_daily.csv")
df["ds"] = pd.to_datetime(df["ds"])

# 2. 메뉴별 판매 기록 일수 계산
menu_summary = (
    df.groupby("product_detail")["ds"]
    .nunique()
)

# 3. 150일 이상 기록된 메뉴만 선택
selected_menus = menu_summary[
    menu_summary >= 150
].index.tolist()

# 4. 전체 날짜 범위 생성
all_dates = pd.date_range(
    start=df["ds"].min(),
    end=df["ds"].max(),
    freq="D"
)

# 5. 선택한 메뉴의 날짜별 판매량을 표 형태로 변환
selected_df = df[
    df["product_detail"].isin(selected_menus)
]

daily_menu = selected_df.pivot_table(
    index="ds",
    columns="product_detail",
    values="y",
    aggfunc="sum",
    fill_value=0
)

# 6. 모든 날짜가 존재하도록 보정
daily_menu = daily_menu.reindex(
    all_dates,
    fill_value=0
)

daily_menu.index.name = "ds"

# 7. Prophet 검증에 사용할 세로형 데이터로 변환
result = daily_menu.reset_index().melt(
    id_vars="ds",
    var_name="product_detail",
    value_name="y"
)

# 8. 저장
result.to_csv(
    "lower_manhattan_menu_daily_51.csv",
    index=False
)

# 9. 결과 확인
print("===== 메뉴별 예측 데이터 생성 완료 =====")
print("선택 메뉴 수:", len(selected_menus))
print("전체 날짜 수:", len(all_dates))
print("전체 데이터 행 수:", len(result))
print("메뉴별 날짜 수:", result.groupby("product_detail").size().unique())

print("\n===== 데이터 미리보기 =====")
print(result.head(10))

print("\n저장 파일: lower_manhattan_menu_daily_51.csv")
