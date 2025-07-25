from django.urls import path
from . import views

urlpatterns = [
    path('generate/', views.generate_words, name='generate_words'),
    path('audio/', views.generate_audio, name='generate_audio'),
    path('health/', views.health_check, name='health_check'),
    
    # Corpus endpoints
    path('corpora/', views.list_corpora, name='list_corpora'),
    
    # Community features
    path('track-copy/', views.track_copy, name='track_copy'),
    path('add-definition/', views.add_definition, name='add_definition'),
    path('vote-definition/', views.vote_definition, name='vote_definition'),
    path('word/<str:word>/definitions/', views.get_word_definitions, name='get_word_definitions'),
]