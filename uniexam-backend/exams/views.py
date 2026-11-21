from django.db import transaction
from django.db.models import ProtectedError
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import Role
from users.permissions import IsTeacherOrAdmin

from .models import DeletionRequest, Exam, ExamStatus, Group, Question, TeachingAssignment, log
from .serializers import ExamSerializer, GroupSerializer, QuestionSerializer


def exams_for(user):
    """Учитель видит только свои экзамены, админ — все."""
    qs = Exam.objects.all()
    if user.role != Role.ADMIN:
        qs = qs.filter(teacher=user)
    return qs


class GroupListView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    def get(self, request):
        groups = Group.objects.filter(is_archived=False)
        return Response(GroupSerializer(groups, many=True).data)


class ExamViewSet(viewsets.ModelViewSet):
    serializer_class = ExamSerializer
    permission_classes = [IsTeacherOrAdmin]

    def get_queryset(self):
        qs = (
            exams_for(self.request.user)
            .select_related("teacher")
            .prefetch_related("groups", "questions")
            .annotate(n_attempts=Count("attempts", distinct=True),
                      n_pending=Count("deletion_requests", filter=Q(deletion_requests__status="pending"), distinct=True))
        )
        p = self.request.query_params
        if p.get("status"):
            qs = qs.filter(status=p["status"])
        if p.get("exam_type"):
            qs = qs.filter(exam_type=p["exam_type"])
        if p.get("search"):
            qs = qs.filter(Q(title__icontains=p["search"]) | Q(subject__icontains=p["search"]))
        return qs

    def perform_create(self, serializer):
        serializer.save(teacher=self.request.user)

    def perform_update(self, serializer):
        exam = serializer.instance
        if exam.status == ExamStatus.ARCHIVED:
            raise DRFValidationError({"detail": "Экзамен в архиве нельзя редактировать"})
        # Ключевые параметры нельзя менять, пока экзамен опубликован или по нему уже есть попытки
        locked = exam.status == ExamStatus.PUBLISHED or exam.attempts.exists()
        if locked:
            changed = [f for f in ("exam_type", "subject", "duration_minutes", "max_score", "passing_score",
                                   "randomize_questions", "allow_multiple_attempts")
                       if f in serializer.validated_data and serializer.validated_data[f] != getattr(exam, f)]
            if changed:
                why = "по нему уже есть попытки студентов" if exam.attempts.exists() else "он опубликован (сначала скройте его)"
                raise DRFValidationError({"detail": f"Нельзя изменить {', '.join(changed)}: {why}"})
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        exam = self.get_object()
        if exam.attempts.exists():
            # Есть сданные работы: удалить может только админ, по запросу преподавателя
            if request.user.role == Role.ADMIN:
                return Response({"detail": "Удаление экзамена с результатами выполняется через запрос преподавателя"}, status=400)
            if exam.deletion_requests.filter(status="pending").exists():
                return Response({"detail": "Запрос на удаление уже отправлен администратору"}, status=400)
            DeletionRequest.objects.create(exam=exam, exam_title=exam.title, requested_by=request.user,
                                           reason=request.data.get("reason", ""))
            log(request, "exam_deletion_requested", f"exam:{exam.id}", new=exam.title)
            return Response({"detail": "У экзамена есть результаты студентов. Запрос на удаление отправлен администратору.",
                             "requested": True}, status=status.HTTP_202_ACCEPTED)
        if exam.status == ExamStatus.PUBLISHED:
            return Response(
                {"detail": "Опубликованный экзамен нельзя удалить. Сначала скройте его."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        exam.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _set_status(self, request, new_status):
        exam = self.get_object()
        if exam.status == ExamStatus.ARCHIVED:
            return Response(
                {"detail": "Экзамен в архиве"}, status=status.HTTP_400_BAD_REQUEST
            )
        exam.status = new_status
        exam.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(exam).data)

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        exam = self.get_object()
        problems = self.get_serializer().check_publishable(exam)
        if problems:
            return Response(
                {"detail": "Экзамен нельзя опубликовать", "problems": problems},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return self._set_status(request, ExamStatus.PUBLISHED)

    @action(detail=True, methods=["post"])
    def hide(self, request, pk=None):
        return self._set_status(request, ExamStatus.HIDDEN)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        exam = self.get_object()
        exam.status = ExamStatus.ARCHIVED
        exam.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(exam).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def duplicate(self, request, pk=None):
        src = self.get_object()
        groups = list(src.groups.all())
        questions = list(src.questions.all())
        src.pk = None
        src.title = f"{src.title} (копия)"
        src.status = ExamStatus.DRAFT
        src.results_published = False
        src.teacher = request.user
        src.save()
        src.groups.set(groups)
        Question.objects.bulk_create(
            [
                Question(
                    exam=src, text=q.text, question_type=q.question_type,
                    options=q.options, correct_answers=q.correct_answers,
                    points=q.points, difficulty=q.difficulty, order=q.order,
                )
                for q in questions
            ]
        )
        return Response(self.get_serializer(src).data, status=status.HTTP_201_CREATED)


def check_editable(exam):
    if exam.attempts.exists():  # иначе можно «подкрутить» вопросы и ключи уже после сдачи
        raise DRFValidationError(
            {"detail": "По экзамену уже есть попытки студентов: вопросы и правильные ответы менять нельзя"})
    if exam.status == ExamStatus.PUBLISHED:
        raise DRFValidationError(
            {"detail": "Пока экзамен опубликован, вопросы менять нельзя. Сначала скройте его."}
        )
    if exam.status == ExamStatus.ARCHIVED:
        raise DRFValidationError({"detail": "Экзамен в архиве"})


class QuestionViewSet(viewsets.ModelViewSet):
    """Вопросы конкретного экзамена: /exams/<exam_id>/questions/"""

    serializer_class = QuestionSerializer
    permission_classes = [IsTeacherOrAdmin]

    def _exam(self):
        return get_object_or_404(exams_for(self.request.user), pk=self.kwargs["exam_pk"])

    def get_queryset(self):
        return self._exam().questions.all()

    def _check_editable(self, exam):
        check_editable(exam)
        exam.variants.all().delete()  # банк изменился — личные наборы формируются заново

    def perform_create(self, serializer):
        exam = self._exam()
        self._check_editable(exam)
        qtype = serializer.validated_data.get("question_type")
        is_written = qtype == "written"
        if (exam.exam_type == "written") != is_written:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                {"question_type": "Тип вопроса не подходит к типу экзамена"}
            )
        order = exam.questions.count() + 1
        serializer.save(exam=exam, order=serializer.validated_data.get("order") or order)

    def perform_update(self, serializer):
        self._check_editable(serializer.instance.exam)
        serializer.save()

    def perform_destroy(self, instance):
        self._check_editable(instance.exam)
        try:
            instance.delete()
        except ProtectedError:
            raise DRFValidationError({"detail": "На этот вопрос уже есть ответы студентов, удалить его нельзя"})


class TeachingInfoView(APIView):
    """Предметы и группы, которые ведёт текущий преподаватель (назначает админ)."""
    permission_classes = [IsTeacherOrAdmin]

    def get(self, request):
        qs = TeachingAssignment.objects.select_related("subject", "group").filter(group__is_archived=False)
        if request.user.role != Role.ADMIN:
            qs = qs.filter(teacher=request.user)
        out = {}
        for a in qs:
            out.setdefault(a.subject.name, {})[a.group.id] = a.group.name
        return Response([{"subject": s, "groups": [{"id": i, "name": n} for i, n in g.items()]} for s, g in out.items()])


class TeacherStatsView(APIView):
    permission_classes = [IsTeacherOrAdmin]

    def get(self, request):
        exams = exams_for(request.user)
        counts = dict(exams.values_list("status").annotate(c=Count("id")))
        group_ids = exams.values_list("groups", flat=True).distinct()
        now = timezone.now()
        upcoming = (
            exams.filter(status=ExamStatus.PUBLISHED, start_at__gte=now)
            .order_by("start_at")[:5]
            .prefetch_related("groups")
        )
        return Response(
            {
                "total_exams": exams.count(),
                "published": counts.get("published", 0),
                "draft": counts.get("draft", 0),
                "hidden": counts.get("hidden", 0),
                "archived": counts.get("archived", 0),
                # Студентов в группах учителя
                "total_students": request.user.__class__.objects.filter(
                    role=Role.STUDENT, edu_group__in=Group.objects.filter(
                        id__in=[g for g in group_ids if g]
                    ).values_list("name", flat=True)
                ).count(),
                "upcoming": ExamSerializer(upcoming, many=True).data,
            }
        )
