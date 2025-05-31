from django.urls import path
from . import views

urlpatterns = [
    path('generate/', views.generate_words, name='generate_words'),
    path('health/', views.health_check, name='health_check'),
]
