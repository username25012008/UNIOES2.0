<<<<<<< HEAD
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
=======
from django.contrib.auth import authenticate
>>>>>>> a76c1519b266e317dfa05201d78f67214b4b70dc
from django.contrib.auth.models import update_last_login
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .permissions import IsTeacherOrAdmin
from .serializers import LoginSerializer, UserInfoSerializer


class LoginView(APIView):
    permission_classes = [AllowAny]
<<<<<<< HEAD
    throttle_scope = "login"  # лимит по IP
=======
>>>>>>> a76c1519b266e317dfa05201d78f67214b4b70dc

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

<<<<<<< HEAD
        sid = serializer.validated_data["student_id"]
        key = f"login_fail:{sid}"
        if (cache.get(key) or 0) >= settings.LOGIN_MAX_FAILS:  # лимит по аккаунту
            return Response({"message": "Слишком много попыток входа. Попробуйте через 15 минут"},
                            status=status.HTTP_429_TOO_MANY_REQUESTS)
=======
>>>>>>> a76c1519b266e317dfa05201d78f67214b4b70dc
        user = authenticate(
            request,
            username=serializer.validated_data["student_id"],
            password=serializer.validated_data["password"],
        )

        if user is None:
<<<<<<< HEAD
            cache.add(key, 0, settings.LOGIN_LOCK_SECONDS)  # атомарный счётчик
            try:
                cache.incr(key)
            except ValueError:
                cache.set(key, 1, settings.LOGIN_LOCK_SECONDS)
=======
>>>>>>> a76c1519b266e317dfa05201d78f67214b4b70dc
            return Response(
                {"message": "Неверный student id или пароль"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

<<<<<<< HEAD
        cache.delete(key)
=======
>>>>>>> a76c1519b266e317dfa05201d78f67214b4b70dc
        update_last_login(None, user)
        refresh = RefreshToken.for_user(user)
        refresh["role"] = user.role  # роль внутри JWT

        return Response(
            {
                "token": str(refresh.access_token),
<<<<<<< HEAD
                "refresh": str(refresh),
=======
>>>>>>> a76c1519b266e317dfa05201d78f67214b4b70dc
                "user": UserInfoSerializer(user).data,
                "isTestAccount": False,
                "testAccountInfo": None,
            },
            status=status.HTTP_200_OK,
        )


<<<<<<< HEAD
def revoke_user_tokens(user):
    """Отзывает все refresh-токены пользователя (смена/сброс пароля, выход)."""
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
    for t in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=t)


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        from rest_framework_simplejwt.exceptions import TokenError
        raw = request.data.get("refresh")
        if isinstance(raw, str):
            try:
                RefreshToken(raw).blacklist()
            except TokenError:
                pass
        return Response({"detail": "Выход выполнен"})


=======
>>>>>>> a76c1519b266e317dfa05201d78f67214b4b70dc
class GetUserInfoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserInfoSerializer(request.user).data)


<<<<<<< HEAD
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        old, new = request.data.get("old_password", ""), request.data.get("new_password", "")
        if not isinstance(old, str) or not isinstance(new, str):
            return Response({"detail": "Пароль должен быть строкой"}, status=400)
        if not request.user.check_password(old):
            return Response({"detail": "Текущий пароль неверный"}, status=400)
        try:
            validate_password(new, request.user)
        except DjangoValidationError as e:
            return Response({"detail": " ".join(e.messages)}, status=400)
        request.user.set_password(new)
        request.user.save(update_fields=["password"])
        revoke_user_tokens(request.user)
        from exams.models import log
        log(request, "password_changed", f"user:{request.user.id}")
        return Response({"detail": "Пароль изменён"})

=======
class ExamCreateView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    def post(self, request):
        # здесь будет логика создания экзамена
        return Response({"message": "Экзамен создан"}, status=status.HTTP_201_CREATED)
>>>>>>> a76c1519b266e317dfa05201d78f67214b4b70dc
