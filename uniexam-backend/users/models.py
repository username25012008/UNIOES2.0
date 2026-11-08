from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.core.validators import RegexValidator
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, student_id, password=None, **extra):
        if not student_id:
            raise ValueError("Student id обязателен")
        user = self.model(student_id=student_id, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

        def create_superuser(self, student_id, password=None, **extra):
            extra.setdefault("is_staff", True)
            extra.setdefault("is_superuser", True)
            extra.setdefault("role", Role.ADMIN)
            return self.create_user(student_id, password, **extra)

class Role(models.TextChoices):
    STUDENT = "student", "Студент"
    TEACHER = "teacher", "Учитель"
    OBSERVER = "observer", "Наблюдатель"
    ADMIN = "admin", "Админ"

class User(AbstractBaseUser, PermissionsMixin):
    student_id = models.CharField(
        max_length=12, unique=True,
        validators=[RegexValidator(r"^\d{12}$", "Student id должен состоять из 12 цифр")],
    )
    full_name = models.CharField(max_length=150, blank=True)
    short_name = models.CharField(max_length=60, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    image = models.URLField(null=True, blank=True)

    edu_faculty = models.CharField(max_length=100, blank=True)
    edu_group = models.CharField(max_length=50, blank=True)
    edu_level = models.CharField(max_length=30, blank=True)
    edu_semester_id = models.IntegerField(null=True, blank=True)
    edu_speciality = models.CharField(max_length=150, blank=True)

    person_id = models.IntegerField(null=True, blank=True)
    organization_id = models.IntegerField(default=1)
    language_id = models.IntegerField(default=3)
    notification_count = models.IntegerField(default=0)
    identity_verified = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    USERNAME_FIELD = "student_id"
    objects = UserManager()

    def __str__(self):
        return self.student_id
    
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)

    @property
    def is_student(self):
        return self.role == Role.STUDENT