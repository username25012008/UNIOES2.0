from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Group(models.Model):
    name = models.CharField(max_length=30, unique=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ExamType(models.TextChoices):
    TEST = "test", "Тест"
    WRITTEN = "written", "Письменный"


class ExamStatus(models.TextChoices):
    DRAFT = "draft", "Черновик"
    PUBLISHED = "published", "Опубликован"
    HIDDEN = "hidden", "Скрыт"
    ARCHIVED = "archived", "В архиве"


class Difficulty(models.TextChoices):
    EASY = "easy", "Лёгкий"
    MEDIUM = "medium", "Средний"
    HARD = "hard", "Сложный"


class QuestionType(models.TextChoices):
    SINGLE = "single", "Один ответ"
    MULTIPLE = "multiple", "Несколько ответов"
    WRITTEN = "written", "Развёрнутый ответ"


class Exam(models.Model):
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="exams"
    )
    title = models.CharField(max_length=200)
    subject = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    exam_type = models.CharField(max_length=10, choices=ExamType.choices, default=ExamType.TEST)
    groups = models.ManyToManyField(Group, related_name="exams", blank=True)

    duration_minutes = models.PositiveIntegerField(default=60)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    max_score = models.PositiveIntegerField(default=100)
    passing_score = models.PositiveIntegerField(default=55)

    randomize_questions = models.BooleanField(default=False)
    allow_multiple_attempts = models.BooleanField(default=False)
    allow_appeals = models.BooleanField(default=True)
    # Варианты: у каждого студента свой набор вопросов из банка (см. exams/variants.py)
    use_variants = models.BooleanField(default=False)
    variants_unique = models.BooleanField(default=True)  # «без повторов» между студентами (по возможности)
    variant_config = models.JSONField(default=dict, blank=True)  # {"easy": 5, "medium": 10, "hard": 5}
    show_results_immediately = models.BooleanField(default=True)
    results_published = models.BooleanField(default=False)  # преподаватель открыл результаты вручную

    status = models.CharField(max_length=10, choices=ExamStatus.choices, default=ExamStatus.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def clean(self):
        if self.start_at and self.end_at and self.end_at <= self.start_at:
            raise ValidationError("Время окончания должно быть позже времени начала")
        if self.passing_score > self.max_score:
            raise ValidationError("Проходной балл не может быть больше максимального")


class Question(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    question_type = models.CharField(
        max_length=10, choices=QuestionType.choices, default=QuestionType.SINGLE
    )
    # Список вариантов ответа, например ["A", "B", "C"]
    options = models.JSONField(default=list, blank=True)
    # Индексы правильных вариантов, например [1] или [0, 2]
    correct_answers = models.JSONField(default=list, blank=True)
    points = models.PositiveIntegerField(default=1)
    difficulty = models.CharField(
        max_length=10, choices=Difficulty.choices, default=Difficulty.MEDIUM
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.text[:60]


class ExamVariant(models.Model):
    """Персональный набор вопросов студента по экзамену (порядок = порядок в списке)."""
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="variants")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    question_ids = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["exam", "student"], name="one_variant_per_exam_student")]


# ───────── Прохождение экзамена, результаты, апелляции, журнал ─────────
class AttemptStatus(models.TextChoices):
    IN_PROGRESS = "in_progress", "В процессе"
    WAITING = "waiting", "Ожидает проверки"
    FINAL = "final", "Итог зафиксирован"


class AttemptQuerySet(models.QuerySet):
    """Массовые операции тоже не должны обходить защиту зафиксированных оценок."""
    PROTECTED = {"final_score", "original_score", "auto_score", "status", "student", "exam"}

    def update(self, **kwargs):
        if self.PROTECTED & kwargs.keys() and self.filter(status="final").exists():
            raise ValidationError("Зафиксированную оценку нельзя изменить напрямую")
        return super().update(**kwargs)

    def delete(self):
        if self.filter(status="final").exists():
            raise ValidationError("Зафиксированные результаты нельзя удалять напрямую")
        return super().delete()

    def purge(self):
        """Единственный путь удаления итогов: решение админа по запросу преподавателя (пишется в журнал)."""
        return super().delete()


class Attempt(models.Model):
    objects = AttemptQuerySet.as_manager()

    exam = models.ForeignKey(Exam, on_delete=models.PROTECT, related_name="attempts")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="attempts")
    started_at = models.DateTimeField(auto_now_add=True)
    deadline = models.DateTimeField()
    submitted_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=AttemptStatus.choices, default=AttemptStatus.IN_PROGRESS)
    auto_score = models.FloatField(default=0)
    final_score = models.FloatField(null=True, blank=True)
    original_score = models.FloatField(null=True, blank=True)  # сохраняется при пересмотре после апелляции
    extra_minutes = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-started_at"]
        constraints = [  # одна активная попытка на студента и экзамен (защита от гонки двух «start»)
            models.UniqueConstraint(fields=["exam", "student"], condition=models.Q(status="in_progress"),
                                    name="one_active_attempt"),
        ]
        indexes = [models.Index(fields=["status", "deadline"])]

    def delete(self, *args, **kwargs):
        raise ValidationError("Результаты нельзя удалять напрямую")

    def save(self, *args, **kwargs):
        # FR-16 / NFR-02: зафиксированную оценку напрямую менять нельзя
        if self.pk:
            old = Attempt.objects.filter(pk=self.pk).values("status", "final_score").first()
            if old and old["status"] == AttemptStatus.FINAL and old["final_score"] != self.final_score \
                    and not getattr(self, "_appeal_revision", False):
                raise ValidationError("Зафиксированную оценку нельзя изменить напрямую")
        super().save(*args, **kwargs)


class AttemptEvent(models.Model):
    """События контроля во время экзамена: выход из вкладки, из полноэкранного режима, попытки копирования."""
    attempt = models.ForeignKey(Attempt, on_delete=models.CASCADE, related_name="events")
    kind = models.CharField(max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


COUNTED_EVENTS = ("tab_hidden", "window_blur", "fullscreen_exit")  # считаются нарушениями
LOGGED_EVENTS = COUNTED_EVENTS + ("copy_attempt", "paste_attempt", "print_attempt", "devtools_key", "context_menu")


class AnswerQuerySet(models.QuerySet):
    """Массовые операции не должны менять ответы в зафиксированных работах."""

    def _guard(self):
        if self.filter(attempt__status="final").exists():
            raise ValidationError("Ответы в зафиксированной работе изменять нельзя")

    def update(self, **kwargs):
        self._guard()
        return super().update(**kwargs)

    def delete(self):
        self._guard()
        return super().delete()

    def bulk_create(self, objs, *a, **kw):
        ids = {o.attempt_id for o in objs}
        if Attempt.objects.filter(pk__in=ids, status="final").exists():
            raise ValidationError("Ответы в зафиксированной работе изменять нельзя")
        return super().bulk_create(objs, *a, **kw)

    def bulk_update(self, objs, *a, **kw):
        ids = {o.attempt_id for o in objs}
        if Attempt.objects.filter(pk__in=ids, status="final").exists():
            raise ValidationError("Ответы в зафиксированной работе изменять нельзя")
        return super().bulk_update(objs, *a, **kw)


class Answer(models.Model):
    objects = AnswerQuerySet.as_manager()

    attempt = models.ForeignKey(Attempt, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.PROTECT)
    selected = models.JSONField(default=list, blank=True)
    text = models.TextField(blank=True)
    points = models.FloatField(null=True, blank=True)
    feedback = models.TextField(blank=True)
    client_ts = models.BigIntegerField(default=0)  # метка клиента: старый запрос не затирает новый

    class Meta:
        unique_together = ("attempt", "question")

    def save(self, *args, **kwargs):
        if self.attempt_id and Attempt.objects.filter(pk=self.attempt_id, status="final").exists():
            raise ValidationError("Ответы в зафиксированной работе изменять нельзя")
        super().save(*args, **kwargs)


class AppealStatus(models.TextChoices):
    # студент → админ → учитель → админ → студент
    SUBMITTED = "submitted", "У администратора"
    REVIEW = "review", "У преподавателя"
    TEACHER_DONE = "teacher_done", "Решение на проверке у администратора"
    ACCEPTED = "accepted", "Принята"
    REJECTED = "rejected", "Отклонена"


class Appeal(models.Model):
    attempt = models.ForeignKey(Attempt, on_delete=models.PROTECT, related_name="appeals")
    question = models.ForeignKey(Question, null=True, blank=True, on_delete=models.SET_NULL)
    category = models.CharField(max_length=30)
    text = models.TextField()
    questions = models.ManyToManyField(Question, blank=True, related_name="+")  # вопросы, которые оспаривает студент
    during_exam = models.BooleanField(default=False)  # сообщение о технической проблеме во время экзамена
    status = models.CharField(max_length=12, choices=AppealStatus.choices, default=AppealStatus.SUBMITTED)
    admin_note = models.TextField(blank=True)  # комментарий админа при пересылке/возврате
    teacher_accept = models.BooleanField(null=True, blank=True)  # рекомендация преподавателя
    teacher_note = models.TextField(blank=True)
    teacher_new_score = models.FloatField(null=True, blank=True)
    teacher_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    teacher_at = models.DateTimeField(null=True, blank=True)
    decision = models.TextField(blank=True)  # итоговый ответ студенту
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class AuditLogQuerySet(models.QuerySet):
    """Журнал только дополняется — и через QuerySet тоже."""

    def update(self, **kwargs):
        raise ValidationError("Записи журнала нельзя изменять")

    def delete(self):
        raise ValidationError("Записи журнала нельзя удалять")

    def bulk_update(self, *a, **kw):
        raise ValidationError("Записи журнала нельзя изменять")


class AuditLog(models.Model):
    objects = AuditLogQuerySet.as_manager()

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=60)
    resource = models.CharField(max_length=120)
    previous_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):  # журнал только дополняется
        if self.pk:
            raise ValidationError("Записи журнала нельзя изменять")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Записи журнала нельзя удалять")


def log(request, action, resource, old="", new=""):
    AuditLog.objects.create(
        user=request.user if request.user.is_authenticated else None, action=action,
        resource=resource, previous_value=str(old), new_value=str(new),
        ip=request.META.get("REMOTE_ADDR"),
    )


# ───────── Предметы, назначения преподавателей, запросы на удаление ─────────
class Subject(models.Model):
    name = models.CharField(max_length=150, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class TeachingAssignment(models.Model):
    """Админ назначает: какой преподаватель ведёт какой предмет в какой группе."""
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assignments")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="assignments")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="assignments")

    class Meta:
        unique_together = ("teacher", "subject", "group")


class DeletionRequest(models.Model):
    exam = models.ForeignKey(Exam, null=True, on_delete=models.SET_NULL, related_name="deletion_requests")
    exam_title = models.CharField(max_length=200)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=10, default="pending")  # pending / approved / rejected
    decision = models.TextField(blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
