import secrets

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from users.models import User

DEMO = [("100000000001", "teacher", "Преподаватель"), ("100000000002", "observer", "Наблюдатель"),
        ("100000000003", "admin", "Администратор"), ("546251100227", "student", "Студент")]


class Command(BaseCommand):
    help = "Создаёт демо-пользователей со случайными паролями (только DJANGO_DEBUG=1)"

    def handle(self, *args, **opts):
        if not settings.DEBUG:
            raise CommandError("Демо-пользователи создаются только в режиме разработки")
        for sid, role, name in DEMO:
            if User.objects.filter(student_id=sid).exists():
                continue
            pw = secrets.token_urlsafe(9)
            User.objects.create_user(sid, pw, role=role, full_name=name)
            self.stdout.write(f"{role:9} {sid}  пароль: {pw}")
