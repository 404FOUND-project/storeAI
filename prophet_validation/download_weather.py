
import pandas as pd
import urllib.request
import urllib.parse
import json

# Lower Manhattan 대표 좌표
# 실제 매장 주소가 확인되지 않았으므로 지역 대표 좌표를 사용
latitude = 40.7075
longitude = -74.0113

# Open-Meteo 과거 날씨 API
url = "https://archive-api.open-meteo.com/v1/archive"

params = {
    "latitude": latitude,
    "longitude": longitude,
    "start_date": "2023-01-01",
    "end_date": "2023-06-30",
    "daily": "temperature_2m_mean,precipitation_sum",
    "timezone": "America/New_York"
}

request_url = url + "?" + urllib.parse.urlencode(params)

# API 요청
request = urllib.request.Request(
    request_url,
    headers={"User-Agent": "storeAI-weather-validation"}
)

with urllib.request.urlopen(request) as response:
    data = json.loads(response.read().decode("utf-8"))

# 날씨 데이터 정리
weather = pd.DataFrame({
    "ds": data["daily"]["time"],
    "temperature": data["daily"]["temperature_2m_mean"],
    "precipitation": data["daily"]["precipitation_sum"]
})

# 날짜 형식 변환
weather["ds"] = pd.to_datetime(weather["ds"])

# CSV 저장
weather.to_csv("new_york_weather.csv", index=False)

# 결과 확인
print("===== 뉴욕 과거 날씨 데이터 =====")
print("데이터 수:", len(weather))
print("시작 날짜:", weather["ds"].min())
print("마지막 날짜:", weather["ds"].max())

print("\n===== 날씨 데이터 앞부분 =====")
print(weather.head())

print("\n===== 결측치 확인 =====")
print(weather.isnull().sum())

print("\n파일 저장 완료: new_york_weather.csv")
