from django.urls import path
<<<<<<< HEAD
from rest_framework_simplejwt.views import TokenRefreshView
from .views import ChangePasswordView, GetUserInfoView, LoginView, LogoutView


class RefreshView(TokenRefreshView):
    throttle_scope = "refresh"


urlpatterns = [
    path("login/", LoginView.as_view()),
    path("logout/", LogoutView.as_view()),
    path("refresh/", RefreshView.as_view()),
    path("change-password/", ChangePasswordView.as_view()),
=======
from .views import GetUserInfoView, LoginView

urlpatterns = [
    path("login/", LoginView.as_view()),
>>>>>>> a76c1519b266e317dfa05201d78f67214b4b70dc
    path("getUserInfo/", GetUserInfoView.as_view()),
]