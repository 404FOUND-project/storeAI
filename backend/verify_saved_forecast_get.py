from rest_framework.test import APIRequestFactory, force_authenticate
from member.models import User
from sales.models import ForecastRun
from sales.views import (
    HomeSummaryView,
    NextDaySalesForecastView,
    MenuQuantityForecastView,
    SevenDayForecastView,
)

user = User.objects.get(pk=2)
factory = APIRequestFactory()
before = ForecastRun.objects.filter(store_id=1).count()

checks = [
    ("/home/", HomeSummaryView),
    ("/forecast/next-day/", NextDaySalesForecastView),
    ("/forecast/menu-quantity/", MenuQuantityForecastView),
    ("/forecast/7-days/", SevenDayForecastView),
]

for path, view in checks:
    request = factory.get(path)
    force_authenticate(request, user=user)
    response = view.as_view()(request, store_id=1)
    data = response.data
    print(f"{path} HTTP={response.status_code}")
    print(f"RUN_ID={data.get('forecast_run_id')}")
    print(f"TARGET_DATE={data.get('target_date')}")
    print(f"TARGET_DATES={data.get('target_dates')}")
    print(f"MENU_ROWS={len(data.get('menus', []))}")
    print(f"VALUE_ROWS={len(data.get('values', []))}")
    if response.status_code != 200:
        print(f"DETAIL={data}")

after = ForecastRun.objects.filter(store_id=1).count()
print(f"DB_BEFORE={before}")
print(f"DB_AFTER={after}")
print(f"DB_UNCHANGED={before == after}")
