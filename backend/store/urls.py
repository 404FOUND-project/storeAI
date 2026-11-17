from django.urls import path

from .views import MenuDetailView, SetMenuRecommendView, MenuProfitabilityView, MenuListCreateView, StoreDetailView, StoreListView

# /store/ 하위 경로
urlpatterns = [
    path('', StoreListView.as_view(), name='store-list'),
    path('<int:pk>/', StoreDetailView.as_view(), name='store-detail'),
    path('<int:store_id>/menus/', MenuListCreateView.as_view(), name='menu-list'),
    path('<int:store_id>/menus/<int:pk>/', MenuDetailView.as_view(), name='menu-detail'),
    path("<int:store_id>/menus/profitability/", MenuProfitabilityView.as_view(), name="menu-profitability"),
    path("<int:store_id>/menus/set-recommend/", SetMenuRecommendView.as_view(), name="set-recommend"),
]
