import json
import random
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import Role
from users.permissions import IsAdminRole, IsObserver, IsStudent, IsTeacherOrAdmin

from .variants import VariantError, questions_for_attempt, variant_for
from .models import (COUNTED_EVENTS, LOGGED_EVENTS, Answer, Appeal, AppealStatus, Attempt, AttemptEvent,
                     AttemptStatus, AuditLog, Exam, ExamStatus, log)

CATEGORIES = {"wrong_question", "wrong_answer", "ambiguous", "technical", "other"}
MAX_TEXT = 20000
MAX_EVENTS = 200
MAX_BULK_ANSWERS = 500


def paginate(request, qs, default=50, maximum=200):
    try:
        limit = min(max(int(request.query_params.get("limit", default)), 1), maximum)
        offset = max(int(request.query_params.get("offset", 0)), 0)
    except ValueError:
        limit, offset = default, 0
    return qs.count(), qs[offset:offset + limit]


def _grade_label(pct):
    return "5" if pct >= 90 else "4" if pct >= 75 else "3" if pct >= 55 else "2"


def _visible(a):
    """Результат виден студенту: итог зафиксирован и (настройка «показывать сразу» или преподаватель открыл)."""
    e = a.exam
    return a.status == AttemptStatus.FINAL and (e.show_results_immediately or e.results_published)


def _result(a):
    mx, vis = a.exam.max_score, _visible(a)
    s = a.final_score if vis else None
    pct = round(s / mx * 100) if s is not None and mx else None
    return {"id": a.id, "exam_title": a.exam.title, "subject": a.exam.subject,
            "exam_type": a.exam.exam_type, "date": a.submitted_at, "status": a.status,
            "hidden": a.status == AttemptStatus.FINAL and not vis,  # итог есть, но ещё не опубликован
            "score": s, "max_score": mx, "percent": pct,
            "passed": None if s is None else s >= a.exam.passing_score,
            "grade": None if pct is None else _grade_label(pct),
            "original_score": a.original_score if vis else None,
            "allow_appeals": a.exam.allow_appeals,
            "appealed": a.appeals.filter(during_exam=False).exists()}  # апелляция на экзамен — одна


def _to_int_set(v):
    try:
        return {int(x) for x in v if not isinstance(x, bool)}
    except (TypeError, ValueError):
        return set()


@transaction.atomic
def _finish(attempt_id):
    """Завершение попытки: автопроверка тестов (FR-10), письменные — преподавателю (FR-11).
    Повторный вызов безопасен: уже завершённая попытка не трогается."""
    a = Attempt.objects.select_for_update().select_related("exam").get(pk=attempt_id)
    if a.status != AttemptStatus.IN_PROGRESS:
        return a
    total, has_written = 0, False
    for ans in a.answers.select_related("question"):
        q = ans.question
        if q.question_type == "written":
            has_written = True
            continue
        ok = _to_int_set(ans.selected) == _to_int_set(q.correct_answers)
        ans.points = q.points if ok else 0
        ans.save(update_fields=["points"])
        total += ans.points
    if a.exam.exam_type == "written" or a.exam.questions.filter(question_type="written").exists():
        has_written = True
    a.auto_score, a.submitted_at = total, timezone.now()
    if has_written:
        a.status = AttemptStatus.WAITING
    else:
        a.status, a.final_score = AttemptStatus.FINAL, total
    a.save()
    return a


def finalize_expired(student=None, exams=None):
    """Завершает все просроченные попытки (вызывается фоновой командой и «лениво» при чтении)."""
    qs = Attempt.objects.filter(status=AttemptStatus.IN_PROGRESS, deadline__lt=timezone.now())
    if student:
        qs = qs.filter(student=student)
    if exams is not None:
        qs = qs.filter(exam__in=exams)
    n = 0
    for pk in list(qs.values_list("id", flat=True)):
        _finish(pk)
        n += 1
    return n


def _group_exams(user):
    return Exam.objects.filter(status=ExamStatus.PUBLISHED, groups__name__iexact=user.edu_group)


class StudentExams(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        finalize_expired(request.user)
        now = timezone.now()
        mine = Attempt.objects.filter(student=request.user).order_by("-started_at")
        exams = (_group_exams(request.user).distinct().select_related("teacher")
                 .annotate(q_count=Count("questions", distinct=True))
                 .prefetch_related(Prefetch("attempts", queryset=mine, to_attr="mine")))
        out = []
        for e in exams:
            last = e.mine[0] if e.mine else None
            in_window = e.start_at <= now <= e.end_at
            retry = bool(last and last.status != AttemptStatus.IN_PROGRESS
                         and e.allow_multiple_attempts and in_window)
            if last and last.status == AttemptStatus.IN_PROGRESS:
                st = "in_progress"
            elif last and not retry:
                st = "completed"
            else:
                st = "upcoming" if now < e.start_at else "closed" if now > e.end_at else "available"
            out.append({"id": e.id, "title": e.title, "subject": e.subject, "exam_type": e.exam_type,
                        "teacher": e.teacher.full_name, "duration": e.duration_minutes,
                        "questions": sum(e.variant_config.values()) if e.use_variants else e.q_count,
                        "start_at": e.start_at, "end_at": e.end_at, "state": st, "retry": retry,
                        "attempts": len(e.mine), "attempt_id": last.id if last else None})
        return Response(out)


class StartExam(APIView):
    permission_classes = [IsStudent]

    def post(self, request, pk):
        e = get_object_or_404(_group_exams(request.user).distinct(), pk=pk)
        now = timezone.now()
        finalize_expired(request.user)
        active = Attempt.objects.filter(exam=e, student=request.user, status=AttemptStatus.IN_PROGRESS).first()
        if active:
            return Response({"attempt_id": active.id})
        if Attempt.objects.filter(exam=e, student=request.user).exists() and not e.allow_multiple_attempts:
            return Response({"detail": "Вы уже сдавали этот экзамен"}, status=400)
        if not e.start_at <= now <= e.end_at:
            return Response({"detail": "Экзамен сейчас недоступен"}, status=400)
        if not e.questions.exists():
            return Response({"detail": "В экзамене нет вопросов"}, status=400)
        if e.use_variants:
            try:
                variant_for(e, request.user)  # личный набор вопросов фиксируется до начала попытки
            except VariantError as ex:
                return Response({"detail": str(ex)}, status=400)
        try:
            with transaction.atomic():  # уникальное ограничение защищает от двух одновременных «start»
                a = Attempt.objects.create(exam=e, student=request.user,
                                           deadline=min(now + timedelta(minutes=e.duration_minutes), e.end_at))
        except IntegrityError:
            a = Attempt.objects.get(exam=e, student=request.user, status=AttemptStatus.IN_PROGRESS)
            return Response({"attempt_id": a.id})
        log(request, "attempt_started", f"exam:{e.id}")
        return Response({"attempt_id": a.id}, status=201)


def _mine(request, pk):
    return get_object_or_404(Attempt.objects.select_related("exam"), pk=pk, student=request.user)


class AttemptView(APIView):
    permission_classes = [IsStudent]

    def get(self, request, pk):
        a = _mine(request, pk)
        if a.status == AttemptStatus.IN_PROGRESS and timezone.now() > a.deadline:
            a = _finish(a.id)  # FR-07: время вышло — завершаем
        if a.status != AttemptStatus.IN_PROGRESS:
            return Response({"id": a.id, "status": a.status})
        qs = questions_for_attempt(a)
        if a.exam.randomize_questions:  # у каждой попытки свой порядок (Fisher–Yates по seed попытки)
            random.Random(a.id).shuffle(qs)
        saved = {x.question_id: x for x in a.answers.all()}
        out = []
        for q in qs:
            opts = [{"i": i, "text": t} for i, t in enumerate(q.options)]
            if a.exam.randomize_questions:
                random.Random(f"{a.id}:{q.id}").shuffle(opts)  # варианты тоже перемешиваются; i — исходный индекс
            s = saved.get(q.id)
            out.append({"id": q.id, "text": q.text, "type": q.question_type, "options": opts,
                        "difficulty": q.difficulty, "points": q.points,
                        "selected": s.selected if s else [], "text_answer": s.text if s else ""})
        return Response({"id": a.id, "status": a.status, "title": a.exam.title, "exam_type": a.exam.exam_type,
                         "remaining": max(0, int((a.deadline - timezone.now()).total_seconds())),
                         "allow_appeals": a.exam.allow_appeals, "questions": out})


def _clean_answer(a, d):
    """Проверяет один ответ. Возвращает (question, selected, text, ts) или строку с ошибкой."""
    if not isinstance(d, dict):
        return "Недопустимый формат ответа"
    qid = d.get("question")
    q = next((x for x in questions_for_attempt(a) if x.id == qid), None) if type(qid) is int else None
    if not q:
        return "Вопрос не найден"
    ts = d.get("ts", 0)
    if type(ts) is not int or ts < 0:
        return "Недопустимая метка времени"
    sel, text = d.get("selected", []), d.get("text", "")
    if q.question_type == "written":
        if not isinstance(text, str) or len(text) > MAX_TEXT:
            return f"Ответ должен быть текстом до {MAX_TEXT} символов"
        sel = []
    else:
        if (not isinstance(sel, list) or any(type(x) is not int or not 0 <= x < len(q.options) for x in sel)
                or len(set(sel)) != len(sel)
                or (q.question_type == "single" and len(sel) > 1)):
            return "Недопустимый формат ответа"
        text = ""
    return q, sorted(sel), text, ts


def _store_answer(a, q, sel, text, ts):
    """Сохраняет ответ; запрос с более старой меткой не затирает более новый (порядок доставки не гарантирован)."""
    ans, created = Answer.objects.select_for_update().get_or_create(
        attempt=a, question=q, defaults={"selected": sel, "text": text, "client_ts": ts})
    if not created and ts >= ans.client_ts:
        ans.selected, ans.text, ans.client_ts = sel, text, ts
        ans.save(update_fields=["selected", "text", "client_ts"])
    return ans


def _open_for_saving(a):
    """Приём ответов — до дедлайна плюс небольшой запас на сетевую задержку последней отправки."""
    grace = timedelta(seconds=settings.EXAM_GRACE_SECONDS)
    return a.status == AttemptStatus.IN_PROGRESS and timezone.now() <= a.deadline + grace


class SaveAnswer(APIView):
    permission_classes = [IsStudent]

    @transaction.atomic
    def put(self, request, pk):  # FR-06: автосохранение
        a = _mine(request, pk)
        a = Attempt.objects.select_for_update().get(pk=a.pk)
        if not _open_for_saving(a):
            return Response({"detail": "Экзамен завершён"}, status=400)
        r = _clean_answer(a, request.data)
        if isinstance(r, str):
            return Response({"detail": r}, status=400)
        _store_answer(a, *r)
        return Response({"saved": True})


class AttemptEventView(APIView):
    """Фиксирует события контроля. После лимита нарушений экзамен завершается автоматически."""
    permission_classes = [IsStudent]

    def post(self, request, pk):
        a = _mine(request, pk)
        kind = request.data.get("kind")
        if kind not in LOGGED_EVENTS:
            return Response({"detail": "Неизвестное событие"}, status=400)
        limit = settings.EXAM_MAX_VIOLATIONS
        if a.status != AttemptStatus.IN_PROGRESS:
            return Response({"violations": 0, "max": limit, "terminate": False})
        if a.events.count() >= MAX_EVENTS:  # защита от переполнения таблицы
            return Response({"violations": a.events.filter(kind__in=COUNTED_EVENTS).count(), "max": limit,
                             "terminate": False})
        AttemptEvent.objects.create(attempt=a, kind=kind)
        n = a.events.filter(kind__in=COUNTED_EVENTS).count()
        terminate = n >= limit
        if terminate:
            a = _finish(a.id)
            log(request, "attempt_terminated_violations", f"attempt:{a.id}", new=f"нарушений: {n}")
        return Response({"violations": n, "max": limit, "terminate": terminate})


class SubmitAttempt(APIView):
    permission_classes = [IsStudent]

    def post(self, request, pk):
        a = _mine(request, pk)
        bulk = request.data.get("answers")
        if bulk is not None:
            # Итоговая пачка ответов с клиента: ничего не теряется, даже если автосохранение отстало
            if not isinstance(bulk, list) or len(bulk) > MAX_BULK_ANSWERS:
                return Response({"detail": "Недопустимый список ответов"}, status=400)
            with transaction.atomic():
                locked = Attempt.objects.select_for_update().get(pk=a.pk)
                if _open_for_saving(locked):
                    cleaned = [_clean_answer(locked, x) for x in bulk]
                    bad = next((c for c in cleaned if isinstance(c, str)), None)
                    if bad:
                        return Response({"detail": bad}, status=400)
                    for c in cleaned:
                        _store_answer(locked, *c)
        if a.status == AttemptStatus.IN_PROGRESS:
            a = _finish(a.id)
            log(request, "attempt_submitted", f"attempt:{a.id}", new=a.final_score)
        return Response({"status": a.status, "result": _result(a) if _visible(a) else None})


class StudentResults(APIView):
    permission_classes = [IsStudent]

    def get(self, request, pk=None):
        finalize_expired(request.user)
        if pk is None:
            qs = (Attempt.objects.filter(student=request.user).exclude(status=AttemptStatus.IN_PROGRESS)
                  .select_related("exam"))
            return Response([_result(a) for a in qs])
        a = _mine(request, pk)
        data = _result(a)
        data["questions"] = [{"id": q.id, "n": i + 1, "text": q.text}  # для выбора вопросов в апелляции
                             for i, q in enumerate(questions_for_attempt(a))]
        if _visible(a):
            data["answers"] = [{"question": x.question.text, "points": x.points, "max": x.question.points,
                                "answer": x.text or x.selected, "feedback": x.feedback}
                               for x in a.answers.select_related("question")]
        return Response(data)


class WrittenGrading(APIView):
    """Ручная проверка письменных ответов (FR-11, FR-13)."""
    permission_classes = [IsTeacherOrAdmin]

    def get(self, request):
        written = Prefetch("answers", queryset=Answer.objects.filter(question__question_type="written")
                           .select_related("question"))
        qs = (Attempt.objects.filter(status=AttemptStatus.WAITING, exam__teacher=request.user)
              .select_related("student", "exam").prefetch_related(written))
        total, page = paginate(request, qs, default=30)
        return Response([{"id": a.id, "student": a.student.full_name, "group": a.student.edu_group,
                          "exam": a.exam.title, "submitted_at": a.submitted_at,
                          "answers": [{"id": x.id, "question": x.question.text, "max": x.question.points,
                                       "answer": x.text} for x in a.answers.all()]} for a in page])

    @transaction.atomic
    def post(self, request):
        a = get_object_or_404(Attempt.objects.select_for_update(), pk=request.data.get("attempt"),
                              status=AttemptStatus.WAITING, exam__teacher=request.user)
        grades = request.data.get("grades")
        if not isinstance(grades, list) or not all(isinstance(g, dict) for g in grades):
            return Response({"detail": "Некорректный список оценок"}, status=400)
        written_ids = set(a.answers.filter(question__question_type="written").values_list("id", flat=True))
        got = {g.get("id") for g in grades}
        if got != written_ids:
            return Response({"detail": "Нужно оценить все письменные ответы (и только их)"}, status=400)
        for g in grades:
            if type(g.get("id")) is not int:
                return Response({"detail": "Некорректный id ответа"}, status=400)
            x = get_object_or_404(a.answers.select_related("question"), pk=g["id"])
            pts = g.get("points")
            if isinstance(pts, bool) or not isinstance(pts, (int, float)) or pts != pts:
                return Response({"detail": "Баллы должны быть числом"}, status=400)
            pts = float(pts)
            if not 0 <= pts <= x.question.points:
                return Response({"detail": f"Баллы должны быть от 0 до {x.question.points}"}, status=400)
            x.points, x.feedback = pts, str(g.get("feedback", ""))[:2000]
            x.save()
        a.final_score = sum(x.points or 0 for x in a.answers.all())
        a.status = AttemptStatus.FINAL
        a.save()
        log(request, "written_graded", f"attempt:{a.id}", new=a.final_score)
        return Response({"final_score": a.final_score})


class TeacherResults(APIView):
    """Результаты студентов по экзаменам преподавателя + публикация результатов."""
    permission_classes = [IsTeacherOrAdmin]

    def _exams(self, request):
        qs = Exam.objects.all()
        return qs if request.user.role == Role.ADMIN else qs.filter(teacher=request.user)

    def get(self, request):
        finalize_expired(exams=self._exams(request))
        qs = (Attempt.objects.filter(exam__in=self._exams(request)).exclude(status=AttemptStatus.IN_PROGRESS)
              .select_related("student", "exam").order_by("-submitted_at")
              .annotate(n_viol=Count("events", filter=Q(events__kind__in=COUNTED_EVENTS), distinct=True)))
        p = request.query_params
        if p.get("exam"):
            if not p["exam"].isdigit():
                return Response({"detail": "Некорректный exam"}, status=400)
            qs = qs.filter(exam_id=int(p["exam"]))
        if p.get("group"):
            qs = qs.filter(student__edu_group__iexact=p["group"])
        total, page = paginate(request, qs)
        rows = []
        for a in page:
            mx, s = a.exam.max_score, a.final_score
            rows.append({"id": a.id, "student": a.student.full_name, "student_id": a.student.student_id,
                         "group": a.student.edu_group, "exam": a.exam.title, "exam_id": a.exam_id,
                         "status": a.status, "score": s, "max_score": mx,
                         "percent": round(s / mx * 100) if s is not None and mx else None,
                         "passed": None if s is None else s >= a.exam.passing_score,
                         "revised": a.original_score is not None, "violations": a.n_viol, "submitted_at": a.submitted_at,
                         "published": a.exam.results_published or a.exam.show_results_immediately})
        exams = [{"id": e.id, "title": e.title, "results_published": e.results_published,
                  "show_immediately": e.show_results_immediately} for e in self._exams(request)]
        return Response({"count": total, "results": rows, "exams": exams})

    def post(self, request):  # опубликовать результаты экзамена
        if type(request.data.get("exam")) is not int:
            return Response({"detail": "Не указан экзамен"}, status=400)
        e = get_object_or_404(self._exams(request), pk=request.data["exam"])
        if e.attempts.filter(status=AttemptStatus.WAITING).exists():
            return Response({"detail": "Есть непроверенные письменные работы"}, status=400)
        e.results_published = True
        e.save(update_fields=["results_published", "updated_at"])
        log(request, "results_published", f"exam:{e.id}", new=e.title)
        return Response({"results_published": True})


class AuditLogView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        qs, p = AuditLog.objects.select_related("user"), request.query_params
        if p.get("action"):
            qs = qs.filter(action=p["action"])
        if p.get("user"):
            qs = qs.filter(Q(user__full_name__icontains=p["user"]) | Q(user__student_id__icontains=p["user"]))
        if p.get("role"):
            qs = qs.filter(user__role=p["role"])
        from django.utils.dateparse import parse_date
        for key, lookup in (("date_from", "created_at__date__gte"), ("date_to", "created_at__date__lte")):
            if p.get(key):
                d = parse_date(p[key]) if len(p[key]) == 10 else None
                if not d:
                    return Response({"detail": f"{key}: формат ГГГГ-ММ-ДД"}, status=400)
                qs = qs.filter(**{lookup: d})
        total, page = paginate(request, qs)
        return Response({"count": total, "results": [
            {"id": l.id, "user": l.user.full_name if l.user else "—", "role": l.user.role if l.user else "",
             "action": l.action, "resource": l.resource, "previous": l.previous_value,
             "new": l.new_value, "ip": l.ip, "created_at": l.created_at} for l in page]})


class ObserverOverview(APIView):
    """Только чтение (наблюдатель)."""
    permission_classes = [IsObserver]

    def get(self, request):
        finalize_expired()
        now = timezone.now()
        return Response({
            "active_exams": Exam.objects.filter(status="published", start_at__lte=now, end_at__gte=now).count(),
            "in_progress": Attempt.objects.filter(status="in_progress").count(),
            "submitted": Attempt.objects.exclude(status="in_progress").count(),
            "appeals_open": Appeal.objects.filter(status__in=["submitted", "review", "teacher_done"]).count()})
