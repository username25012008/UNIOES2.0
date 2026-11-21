import time
import jwt  # PyJWT, ставится вместе с simplejwt
from django.conf import settings
from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    student_id = serializers.RegexField(
        r"^\d{12}$",
        error_messages={"invalid": "Student id должен состоять из 12 цифр"},
    )
    password = serializers.CharField(write_only=True)


class UserInfoSerializer(serializers.Serializer):
    role = serializers.CharField()
    eduFaculty = serializers.CharField(source="edu_faculty")
    eduGroup = serializers.CharField(source="edu_group")
    eduLevel = serializers.CharField(source="edu_level")
    eduSemesterId = serializers.IntegerField(source="edu_semester_id")
    eduSpeciality = serializers.CharField(source="edu_speciality")
    email = serializers.EmailField()
    entityName = serializers.SerializerMethodField()
    fullName = serializers.CharField(source="full_name")
    hemisId = serializers.CharField(source="student_id")
    id = serializers.IntegerField()
    identityVerificationToken = serializers.SerializerMethodField()
    identityVerificationUrl = serializers.SerializerMethodField()
    identityVerified = serializers.BooleanField(source="identity_verified")
    image = serializers.CharField()
    languageId = serializers.IntegerField(source="language_id")
    lastAccessTime = serializers.SerializerMethodField()
    notificationCount = serializers.SerializerMethodField()
    organizationId = serializers.IntegerField(source="organization_id")
    password = serializers.SerializerMethodField()
    personId = serializers.IntegerField(source="person_id")
    phoneNumber = serializers.CharField(source="phone_number")
    shortName = serializers.CharField(source="short_name")
    studentId = serializers.IntegerField(source="id")
    username = serializers.CharField(source="student_id")

    def get_entityName(self, obj):
            return {
                "student": "studentuser",
                "teacher": "teacheruser",
                "observer": "observeruser",
                "admin": "adminuser",
            }.get(obj.role, "studentuser")

    def get_password(self, obj):
        return None  # пароль никогда не отдаём

    def get_notificationCount(self, obj):
        return str(obj.notification_count)

    def get_lastAccessTime(self, obj):
        if not obj.last_login:
            return None
        return obj.last_login.astimezone().strftime("%d.%m.%Y %H:%M:%S")

    def _make_token(self, obj):
        now = int(time.time())
        payload = {
            "student_id": obj.student_id,
            "organization_id": str(obj.organization_id),
            "purpose": "identity_verification",
            "iat": now,
            "nbf": now,
            "exp": now + 86400,  # 24 часа
            "iss": "Next.Lms.IdentityVerification",
            "aud": "Next.Lms.IdentityVerification",
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    def get_identityVerificationToken(self, obj):
        return self._make_token(obj)

    def get_identityVerificationUrl(self, obj):
        return f"/identity/verify-redirect?token={self._make_token(obj)}"