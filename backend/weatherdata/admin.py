from django.contrib import admin

from .models import WeatherCollectionRun, WeatherDatum, WeatherForecastPublication, WeatherLocation

for _m in (WeatherLocation, WeatherCollectionRun, WeatherDatum):
    admin.site.register(_m)


@admin.register(WeatherForecastPublication)
class WeatherForecastPublicationAdmin(admin.ModelAdmin):
    list_display = ("id",)  # 기본 문자열 표시가 오류라 id만 표시
