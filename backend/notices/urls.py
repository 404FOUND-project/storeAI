from django.urls import path

from .views import NoticeDetailView, NoticeListCreateView

app_name = 'notices'

urlpatterns = [
    path('', NoticeListCreateView.as_view(), name='list'),
    path('<int:pk>/', NoticeDetailView.as_view(), name='detail'),
]
