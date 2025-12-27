from django.urls import path
from . import views


urlpatterns = [
    path('', views.home, name='home'),
    path('tournament/', views.tournament, name='tournament'),
    path('club/<int:club_id>/', views.club, name='club'),
    path('match/<int:match_id>/', views.match, name='match'),
    path('tournament/<int:tournament_id>/', views.tournament, name='tournament'),

]

