from django.urls import path

from .views import SavedSalesForecastView, SalesSeriesView

app_name = "sales"

urlpatterns = [
    path("stores/<int:store_id>/analysis/sales/", SalesSeriesView.as_view(), name="analysis-sales"),
    path("stores/<int:store_id>/forecast/saved/", SavedSalesForecastView.as_view(), name="saved-sales-forecast"),
]
