from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import ChangePasswordView, GetUserInfoView, LoginView, LogoutView


class RefreshView(TokenRefreshView):
    throttle_scope = "refresh"


urlpatterns = [
    path("login/", LoginView.as_view()),
    path("logout/", LogoutView.as_view()),
    path("refresh/", RefreshView.as_view()),
    path("change-password/", ChangePasswordView.as_view()),
    path("getUserInfo/", GetUserInfoView.as_view()),
]