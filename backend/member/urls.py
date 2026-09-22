from django.urls import path
from .views import LoginView, LogoutView, MeView, SignupView

# /member/ 하위 인증 경로
# name: reverse() URL 조회용 이름
urlpatterns = [
    path('signup/', SignupView.as_view(), name='signup'),
    path('login/', LoginView.as_view(), name='login'),
    path('me/', MeView.as_view(), name='me'),
    path('logout/', LogoutView.as_view(), name='logout'),
]
