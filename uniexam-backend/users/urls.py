from django.urls import path
from .views import GetUserInfoView, LoginView

urlpatterns = [
    path("login/", LoginView.as_view()),
    path("getUserInfo/", GetUserInfoView.as_view()),
]