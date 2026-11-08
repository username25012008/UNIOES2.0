from django.contrib.auth import authenticate
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

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            request,
            username=serializer.validated_data["student_id"],
            password=serializer.validated_data["password"],
        )

        if user is None:
            return Response(
                {"message": "Неверный student id или пароль"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        update_last_login(None, user)
        refresh = RefreshToken.for_user(user)
        refresh["role"] = user.role  # роль внутри JWT

        return Response(
            {
                "token": str(refresh.access_token),
                "user": UserInfoSerializer(user).data,
                "isTestAccount": False,
                "testAccountInfo": None,
            },
            status=status.HTTP_200_OK,
        )


class GetUserInfoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserInfoSerializer(request.user).data)


class ExamCreateView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    def post(self, request):
        # здесь будет логика создания экзамена
        return Response({"message": "Экзамен создан"}, status=status.HTTP_201_CREATED)