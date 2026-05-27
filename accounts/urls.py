from django.urls import path
from . import views

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("preferences/", views.preferences, name="preferences"),
    path("profile/", views.profile, name="profile"),
]
