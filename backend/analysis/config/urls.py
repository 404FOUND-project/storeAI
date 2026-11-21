
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('member/', include('member.urls')),
    path('notices/', include('notices.urls')),
    path('sales/', include('sales.urls')),
    path('api/chatbot/', include('analysis.urls')),
]