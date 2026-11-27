from rest_framework.test import APIRequestFactory, force_authenticate
from member.models import User
from sales.views import NextDaySalesForecastView, MenuQuantityForecastView, SevenDayForecastView

user = User.objects.get(pk=2)
factory = APIRequestFactory()

checks = [
    ("/forecast/next-day/", NextDaySalesForecastView, ("target_date", "predicted_sales", "predicted_order_count")),
    ("/forecast/menu-quantity/", MenuQuantityForecastView, ("target_date", "menus", "total_expected_quantity")),
    ("/forecast/7-days/", SevenDayForecastView, ("target_dates", "values", "metadata")),
]

for path, view, expected in checks:
    request = factory.get(path)
    force_authenticate(request, user=user)
    response = view.as_view()(request, store_id=1)
    data = response.data
    print("\nAPI:", path, "HTTP:", response.status_code)
    print("FIELDS:", {key: key in data for key in expected})
    if "values" in data:
        print("FORECAST_VALUES:", len(data["values"]))
    if "menus" in data:
        print("MENU_ROWS:", len(data["menus"]))
    if response.status_code != 200:
        print("DETAIL:", data)
