from django.urls import path

from .views import InventoryDetailView, InventoryListCreateView, ReorderRecommendationView

# /store/<store_id>/inventory/ 하위 경로
urlpatterns = [
    path('', InventoryListCreateView.as_view(), name='inventory-list'),
    path('reorder/', ReorderRecommendationView.as_view(), name='inventory-reorder'),
    path('<int:pk>/', InventoryDetailView.as_view(), name='inventory-detail'),
]
