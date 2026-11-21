from django.urls import path

from .views import (
    MenuQuantityForecastView, NextDaySalesForecastView, SalesComparisonView,
    SalesPatternView, SalesSeriesView,
)

app_name = 'sales'

urlpatterns = [
    path('stores/<int:store_id>/analysis/sales/', SalesSeriesView.as_view(), name='analysis-sales'),
    path('stores/<int:store_id>/analysis/patterns/', SalesPatternView.as_view(), name='analysis-patterns'),
    path('stores/<int:store_id>/analysis/comparison/', SalesComparisonView.as_view(), name='analysis-comparison'),
    path('stores/<int:store_id>/forecast/next-day/', NextDaySalesForecastView.as_view(), name='forecast-next-day'),
    path('stores/<int:store_id>/forecast/menu-quantity/', MenuQuantityForecastView.as_view(),
         name='forecast-menu-quantity'),
]
