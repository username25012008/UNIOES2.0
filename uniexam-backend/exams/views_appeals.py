"""Апелляции: студент → администратор → преподаватель → администратор → студент.

Студент подаёт одну апелляцию на попытку (сообщение о технической проблеме во время экзамена не считается).
Администратор либо отклоняет её сразу, либо пересылает преподавателю. Преподаватель даёт рекомендацию
(принять / отклонить, при необходимости новый балл) — оценка в этот момент НЕ меняется. Администратор
подтверждает рекомендацию (тогда оценка пересматривается) либо возвращает её преподавателю."""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsAdminRole, IsStudent, IsTeacher

from .models import Appeal, AppealStatus as S, Attempt, AttemptStatus, log
from .variants import questions_for_attempt
from .views_flow import CATEGORIES, _mine, paginate

MAX_QUESTIONS = 50
TEXT_LIMIT = 2000
STAGE = {S.SUBMITTED: "У администратора", S.REVIEW: "У преподавателя",
         S.TEACHER_DONE: "На проверке у администратора", S.ACCEPTED: "Принята", S.REJECTED: "Отклонена"}


def _text(d, key, required=False):
    v = d.get(key, "")
    if not isinstance(v, str):
        return None
    v = v.strip()
    return v if v or not required else None


def _numbers(a):
    allowed = {q.id: i + 1 for i, q in enumerate(questions_for_attempt(a))}
    return allowed


class StudentAppeals(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        out = []
        for p in (Appeal.objects.filter(attempt__student=request.user)
                  .select_related("attempt__exam").prefetch_related("questions")):
            num = _numbers(p.attempt)
            final = p.status in (S.ACCEPTED, S.REJECTED)
            out.append({"id": p.id, "attempt": p.attempt_id, "exam": p.attempt.exam.title,
                        "questions": [num.get(q.id) for q in p.questions.all() if q.id in num],
                        "category": p.category, "text": p.text, "status": p.status, "stage": STAGE[p.status],
                        "decision": p.decision if final else "", "created_at": p.created_at})
        return Response(out)

    @transaction.atomic
    def post(self, request):
        d = request.data
        if type(d.get("attempt")) is not int:
            return Response({"detail": "Не указана попытка"}, status=400)
        a = get_object_or_404(Attempt.objects.select_for_update().select_related("exam"),
                              pk=d["attempt"], student=request.user)
        text, cat = _text(d, "text"), d.get("category", "other")
        if text is None:
            return Response({"detail": "Текст должен быть строкой"}, status=400)
        if not a.exam.allow_appeals:
            return Response({"detail": "Для этого экзамена апелляции отключены"}, status=400)
        if cat not in CATEGORIES:
            return Response({"detail": "Неверная категория"}, status=400)
        if not text or len(text) > TEXT_LIMIT:
            return Response({"detail": f"Опишите причину (до {TEXT_LIMIT} символов)"}, status=400)
        during = a.status == AttemptStatus.IN_PROGRESS
        if during:
            if cat != "technical":
                return Response({"detail": "Апелляцию по содержанию можно подать после завершения экзамена"}, status=400)
        else:
            if a.submitted_at and timezone.now() > a.submitted_at + timedelta(days=settings.APPEAL_WINDOW_DAYS):
                return Response({"detail": f"Срок подачи апелляции ({settings.APPEAL_WINDOW_DAYS} дн.) истёк"}, status=400)
            if a.appeals.filter(during_exam=False).exists():
                return Response({"detail": "Апелляцию по этому экзамену можно подать только один раз"}, status=400)
        ids = d.get("questions", [] if d.get("question") is None else [d["question"]])
        if (not isinstance(ids, list) or len(ids) > MAX_QUESTIONS
                or any(type(i) is not int for i in ids)):
            return Response({"detail": "Некорректный список вопросов"}, status=400)
        allowed = {q.id: q for q in questions_for_attempt(a)}
        if any(i not in allowed for i in set(ids)):
            return Response({"detail": "Вопрос не относится к вашему варианту этого экзамена"}, status=400)
        p = Appeal.objects.create(attempt=a, category=cat, text=text, during_exam=during)
        p.questions.set([allowed[i] for i in set(ids)])
        log(request, "appeal_submitted", f"appeal:{p.id}")
        return Response({"id": p.id}, status=201)


def _row(p, with_teacher=True):
    a = p.attempt
    num = _numbers(a)
    r = {"id": p.id, "student": a.student.full_name, "group": a.student.edu_group,
         "exam": a.exam.title, "teacher": a.exam.teacher.full_name, "category": p.category, "text": p.text,
         "questions": [{"n": num.get(q.id), "text": q.text} for q in p.questions.all()],
         "score": a.final_score, "max_score": a.exam.max_score, "status": p.status, "stage": STAGE[p.status],
         "admin_note": p.admin_note, "decision": p.decision, "created_at": p.created_at}
    if with_teacher:
        r.update({"teacher_accept": p.teacher_accept, "teacher_note": p.teacher_note,
                  "teacher_new_score": p.teacher_new_score})
    return r


def _base():
    return Appeal.objects.select_related("attempt__exam__teacher", "attempt__student").prefetch_related("questions")


class AdminAppeals(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        qs = _base()
        st = request.query_params.get("status")
        if st in {s.value for s in S}:
            qs = qs.filter(status=st)
        elif st == "todo":  # требуют действия администратора
            qs = qs.filter(status__in=[S.SUBMITTED, S.TEACHER_DONE])
        total, page = paginate(request, qs)
        return Response({"total": total, "results": [_row(p) for p in page]})

    @transaction.atomic
    def post(self, request):
        d = request.data
        if type(d.get("id")) is not int or d.get("action") not in ("forward", "reject", "approve", "return"):
            return Response({"detail": "Некорректный запрос"}, status=400)
        note = _text(d, "note")
        if note is None or len(note) > TEXT_LIMIT:
            return Response({"detail": "Комментарий должен быть текстом"}, status=400)
        p = get_object_or_404(Appeal.objects.select_for_update(), pk=d["id"])
        act, now = d["action"], timezone.now()
        if act in ("forward", "reject") and p.status != S.SUBMITTED:
            return Response({"detail": "Апелляция уже не на первом этапе"}, status=409)
        if act in ("approve", "return") and p.status != S.TEACHER_DONE:
            return Response({"detail": "Решение преподавателя ещё не получено"}, status=409)
        if act in ("reject", "return") and not note:
            return Response({"detail": "Укажите причину"}, status=400)

        if act == "forward":
            p.status, p.admin_note = S.REVIEW, note
        elif act == "reject":
            p.status, p.decision, p.decided_by, p.decided_at = S.REJECTED, note, request.user, now
        elif act == "return":
            p.status, p.admin_note = S.REVIEW, note
            p.teacher_accept = p.teacher_new_score = None
            p.teacher_note = ""
        else:  # approve: рекомендация преподавателя становится решением
            if p.teacher_accept and p.teacher_new_score is not None:
                a = Attempt.objects.select_for_update().select_related("exam").get(pk=p.attempt_id)
                if a.status != AttemptStatus.FINAL:
                    return Response({"detail": "Оценка ещё не зафиксирована"}, status=400)
                if a.original_score is None:
                    a.original_score = a.final_score
                old, a.final_score, a._appeal_revision = a.final_score, p.teacher_new_score, True
                a.save()
                log(request, "grade_revised_after_appeal", f"attempt:{a.id}", old, a.final_score)
            p.status = S.ACCEPTED if p.teacher_accept else S.REJECTED
            p.decision = p.teacher_note + (f"\n\nКомментарий администратора: {note}" if note else "")
            p.decided_by, p.decided_at = request.user, now
        p.save()
        log(request, f"appeal_{act}", f"appeal:{p.id}", new=p.status)
        return Response({"status": p.status})


class TeacherAppeals(APIView):
    """Преподаватель видит только апелляции, которые администратор переслал ему (и уже обработанные им)."""
    permission_classes = [IsTeacher]

    def get(self, request):
        qs = _base().filter(attempt__exam__teacher=request.user).filter(
            Q(status__in=[S.REVIEW, S.TEACHER_DONE]) | Q(teacher_by=request.user))
        total, page = paginate(request, qs)
        return Response([_row(p) for p in page])

    @transaction.atomic
    def post(self, request):
        d = request.data
        if type(d.get("id")) is not int:
            return Response({"detail": "Не указана апелляция"}, status=400)
        accept, reason = d.get("accept"), d.get("decision", "")
        if not isinstance(accept, bool) or not isinstance(reason, str):
            return Response({"detail": "Некорректные данные решения"}, status=400)
        reason = reason.strip()
        p = get_object_or_404(Appeal.objects.select_for_update().select_related("attempt__exam"), pk=d["id"])
        if p.attempt.exam.teacher_id != request.user.id:
            return Response(status=403)
        if p.status != S.REVIEW:
            return Response({"detail": "Апелляция сейчас не у вас на рассмотрении"}, status=409)
        if not reason or len(reason) > TEXT_LIMIT:
            return Response({"detail": "Укажите обоснование решения"}, status=400)
        new = d.get("new_score")
        if accept and new is not None:
            if isinstance(new, bool) or not isinstance(new, (int, float)) or new != new:
                return Response({"detail": "Недопустимый балл"}, status=400)
            new = float(new)
            if not 0 <= new <= p.attempt.exam.max_score:
                return Response({"detail": "Недопустимый балл"}, status=400)
        else:
            new = None
        p.teacher_accept, p.teacher_note, p.teacher_new_score = accept, reason, new
        p.teacher_by, p.teacher_at, p.status = request.user, timezone.now(), S.TEACHER_DONE
        p.save()
        log(request, "appeal_teacher_decision", f"appeal:{p.id}", new="accept" if accept else "reject")
        return Response({"status": p.status})
