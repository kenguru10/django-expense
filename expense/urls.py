from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('auth/', views.auth_view, name='auth'),
    path('family/', views.family_view, name='family'),
]