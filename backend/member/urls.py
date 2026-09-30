from django.urls import path
from .views import LoginView, LogoutView, MeView, SignupView
from .views import (
    AdminMemberDetailView, AdminMemberListView, AdminMemberStoreView,
    StoreRegistrationView,
)

# /member/ 하위 인증 경로
# name: reverse() URL 조회용 이름
urlpatterns = [
    path('signup/', SignupView.as_view(), name='signup'),
    path('login/', LoginView.as_view(), name='login'),
    path('me/', MeView.as_view(), name='me'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('stores/', StoreRegistrationView.as_view(), name='member-store-register'),
    path('admin/members/', AdminMemberListView.as_view(), name='admin-member-list'),
    path('admin/members/<int:pk>/', AdminMemberDetailView.as_view(),
         name='admin-member-detail'),
    path('admin/members/<int:member_pk>/stores/<int:pk>/',
         AdminMemberStoreView.as_view(), name='admin-member-store-detail'),
]
