from django.urls import path

from .views import (
    HomeSummaryView,
    MonthlyReportView,
    SalesSummaryView,
    MenuQuantityForecastView,
    NextDaySalesForecastView,
    SalesComparisonView,
    ForecastAccuracyView,
    SalesPatternView,
    SalesSeriesView,
    SevenDayForecastView,
    SavedForecastView,
)

app_name = 'sales'

urlpatterns = [
    path('summary/', SalesSummaryView.as_view(), name='sales-summary'),
    path('stores/<int:store_id>/analysis/sales/', SalesSeriesView.as_view(), name='analysis-sales'),
    path('stores/<int:store_id>/analysis/patterns/', SalesPatternView.as_view(), name='analysis-patterns'),
    path('stores/<int:store_id>/analysis/comparison/', SalesComparisonView.as_view(), name='analysis-comparison'),
    path('stores/<int:store_id>/analysis/monthly-report/', MonthlyReportView.as_view(), name='analysis-monthly-report'),
    path('stores/<int:store_id>/forecast/next-day/', NextDaySalesForecastView.as_view(), name='forecast-next-day'),
    path('stores/<int:store_id>/forecast/menu-quantity/', MenuQuantityForecastView.as_view(),
         name='forecast-menu-quantity'),
    path('stores/<int:store_id>/forecast/7-days/', SevenDayForecastView.as_view(), name='forecast-seven-days'),
    path('stores/<int:store_id>/forecast/saved/', SavedForecastView.as_view(), name='forecast-saved'),
    path('stores/<int:store_id>/forecast/accuracy/', ForecastAccuracyView.as_view(), name='forecast-accuracy'),
    path(
        'stores/<int:store_id>/home/',
        HomeSummaryView.as_view(),
        name='home-summary',
    ),
]