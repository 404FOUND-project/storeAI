
from django.urls import path
from .views import chatbot, faq_answer_api, faq_api

urlpatterns = [
    path('faq/', faq_api, name='chatbot_faq'),
    path('faq/answer/', faq_answer_api, name='chatbot_faq_answer'),
    path('', chatbot, name='chatbot'),
]