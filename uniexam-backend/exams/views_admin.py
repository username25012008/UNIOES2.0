from django.contrib.auth import get_user_model
import json

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsAdminRole

from .models import Appeal, Attempt, DeletionRequest, Group, Subject, TeachingAssignment, log

User = get_user_model()
ROLES = ("student", "teacher", "observer", "admin")


def _u(u):
    return {"id": u.id, "student_id": u.student_id, "full_name": u.full_name, "role": u.role,
            "edu_group": u.edu_group, "is_active": u.is_active}


class Users(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        qs = User.objects.all().order_by("role", "full_name")
        p = request.query_params
        if p.get("role"):
            qs = qs.filter(role=p["role"])
        if p.get("group"):
            qs = qs.filter(edu_group=p["group"])
        return Response([_u(u) for u in qs])

    def post(self, request):
        d = request.data
        sid, role = str(d.get("student_id", "")), d.get("role")
        if role not in ROLES:
            return Response({"detail": "Неверная роль"}, status=400)
        if not (sid.isdigit() and len(sid) == 12):
            return Response({"detail": "ID должен состоять из 12 цифр"}, status=400)
        if User.objects.filter(student_id=sid).exists():
            return Response({"detail": "Пользователь с таким ID уже есть"}, status=400)
        pw, full_name, eg = d.get("password", ""), d.get("full_name", ""), d.get("edu_group", "")
        if not all(isinstance(x, str) for x in (pw, full_name, eg)):
            return Response({"detail": "Поля должны быть строками"}, status=400)
        try:
            validate_password(pw, User(student_id=sid, full_name=full_name))
        except DjangoValidationError as e:
            return Response({"detail": " ".join(e.messages)}, status=400)
        u = User.objects.create_user(sid, pw, full_name=full_name,
                                     role=role, edu_group=eg if role == "student" else "")
        log(request, "user_created", f"user:{u.id}", new=role)
        return Response(_u(u), status=201)


class UserDetail(APIView):
    permission_classes = [IsAdminRole]

    def patch(self, request, pk):
        u = get_object_or_404(User, pk=pk)
        old = {"edu_group": u.edu_group, "is_active": u.is_active, "role": u.role, "full_name": u.full_name}
        if "full_name" in request.data:
            name = str(request.data["full_name"]).strip()
            if not name:
                return Response({"detail": "ФИО не может быть пустым"}, status=400)
            u.full_name = name
        if "role" in request.data and request.data["role"] != u.role:
            if request.data["role"] not in ROLES:
                return Response({"detail": "Неверная роль"}, status=400)
            if u.id == request.user.id:
                return Response({"detail": "Нельзя менять собственную роль"}, status=400)
            u.role = request.data["role"]
            if u.role != "student":
                u.edu_group = ""
        if "edu_group" in request.data and not isinstance(request.data["edu_group"], str):
            return Response({"detail": "Группа должна быть строкой"}, status=400)
        if "edu_group" in request.data and u.role == "student":
            g = Group.objects.filter(name__iexact=request.data["edu_group"]).first() if request.data["edu_group"] else None
            if request.data["edu_group"] and not g:
                return Response({"detail": "Такой группы нет"}, status=400)
            u.edu_group = g.name if g else ""  # всегда каноническое название группы
        if "is_active" in request.data:
            if u.id == request.user.id:
                return Response({"detail": "Нельзя деактивировать себя"}, status=400)
            if not isinstance(request.data["is_active"], bool):
                return Response({"detail": "is_active должен быть true или false"}, status=400)
            u.is_active = request.data["is_active"]
        u.save()
        log(request, "user_updated", f"user:{u.id}", old,
            {"edu_group": u.edu_group, "is_active": u.is_active, "role": u.role, "full_name": u.full_name})
        return Response(_u(u))


class ResetPassword(APIView):
    """Сброс пароля по авторизованной процедуре: админ задаёт новый временный пароль, действие пишется в журнал."""
    permission_classes = [IsAdminRole]

    def post(self, request, pk):
        u = get_object_or_404(User, pk=pk)
        new = request.data.get("new_password", "")
        if not isinstance(new, str):
            return Response({"detail": "Пароль должен быть строкой"}, status=400)
        try:
            validate_password(new, u)
        except DjangoValidationError as e:
            return Response({"detail": " ".join(e.messages)}, status=400)
        u.set_password(new)
        u.save(update_fields=["password"])
        from users.views import revoke_user_tokens
        revoke_user_tokens(u)
        log(request, "password_reset", f"user:{u.id}")  # сам пароль в журнал не пишется
        return Response({"detail": "Пароль сброшен"})


class Subjects(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        return Response([{"id": s.id, "name": s.name} for s in Subject.objects.all()])

    def post(self, request):
        name = request.data.get("name", "").strip()
        if not name:
            return Response({"detail": "Введите название предмета"}, status=400)
        s, new = Subject.objects.get_or_create(name=name)
        if new:
            log(request, "subject_created", f"subject:{s.id}", new=name)
        return Response({"id": s.id, "name": s.name}, status=201 if new else 200)

    def delete(self, request, pk):
        s = get_object_or_404(Subject, pk=pk)
        log(request, "subject_deleted", f"subject:{s.id}", old=s.name)
        s.delete()
        return Response(status=204)


class Groups(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        counts = dict(User.objects.filter(role="student").values_list("edu_group").annotate(c=Count("id")))
        return Response([{"id": g.id, "name": g.name, "is_archived": g.is_archived, "students": counts.get(g.name, 0)}
                         for g in Group.objects.all()])

    def post(self, request):
        name = request.data.get("name", "").strip().upper()
        if not name:
            return Response({"detail": "Введите название группы"}, status=400)
        g, _ = Group.objects.get_or_create(name=name)
        log(request, "group_created", f"group:{g.id}", new=name)
        return Response({"id": g.id, "name": g.name}, status=201)


class Assignments(APIView):
    """Кто что преподаёт: преподаватель + предмет + группа."""
    permission_classes = [IsAdminRole]

    def get(self, request):
        return Response([{"id": a.id, "teacher": a.teacher.full_name or a.teacher.student_id, "teacher_id": a.teacher_id,
                          "subject": a.subject.name, "group": a.group.name}
                         for a in TeachingAssignment.objects.select_related("teacher", "subject", "group")])

    def post(self, request):
        d = request.data
        t = get_object_or_404(User, pk=d.get("teacher"), role="teacher")
        # можно передать несколько предметов и групп сразу: создаются все сочетания
        s_ids = d.get("subjects") or ([d["subject"]] if d.get("subject") else [])
        g_ids = d.get("groups") or ([d["group"]] if d.get("group") else [])
        if not s_ids or not g_ids:
            return Response({"detail": "Выберите хотя бы один предмет и одну группу"}, status=400)
        subjects, groups = Subject.objects.filter(pk__in=s_ids), Group.objects.filter(pk__in=g_ids)
        created = 0
        with transaction.atomic():
            for s in subjects:
                for g in groups:
                    a, new = TeachingAssignment.objects.get_or_create(teacher=t, subject=s, group=g)
                    if new:
                        created += 1
                        log(request, "assignment_created", f"assignment:{a.id}", new=f"{t.full_name} / {s.name} / {g.name}")
        if not created:
            return Response({"detail": "Все такие назначения уже существуют"}, status=400)
        return Response({"created": created}, status=201)

    def delete(self, request, pk):
        a = get_object_or_404(TeachingAssignment, pk=pk)
        log(request, "assignment_deleted", f"assignment:{a.id}", old=f"{a.teacher.full_name} / {a.subject.name} / {a.group.name}")
        a.delete()
        return Response(status=204)


class DeletionRequests(APIView):
    """Запросы преподавателей на удаление экзамена с результатами."""
    permission_classes = [IsAdminRole]

    def get(self, request):
        out = []
        reqs = DeletionRequest.objects.select_related("requested_by", "exam").annotate(n=Count("exam__attempts"))
        for r in reqs:
            n = r.n if r.exam_id else None
            out.append({"id": r.id, "exam": r.exam_title, "teacher": r.requested_by.full_name, "reason": r.reason,
                        "attempts": n, "status": r.status, "decision": r.decision, "created_at": r.created_at})
        return Response(out)

    @transaction.atomic
    def post(self, request):
        rid, approve, note = request.data.get("id"), request.data.get("approve"), request.data.get("decision", "")
        if not isinstance(rid, int) or isinstance(rid, bool) or not isinstance(approve, bool) or not isinstance(note, str):
            return Response({"detail": "Некорректные данные запроса"}, status=400)
        r = get_object_or_404(DeletionRequest, pk=rid, status="pending")
        r.status, r.decision, r.decided_by, r.decided_at = ("approved" if approve else "rejected"), note, request.user, timezone.now()
        r.save()
        if approve and r.exam:
            exam = r.exam
            n_att = exam.attempts.count()
            # Перед удалением в журнал пишется снимок итогов — след остаётся навсегда
            snap = [{"student": a.student.student_id, "status": a.status, "final": a.final_score, "original": a.original_score}
                    for a in Attempt.objects.filter(exam=exam).select_related("student")]
            Appeal.objects.filter(attempt__exam=exam).delete()
            Attempt.objects.filter(exam=exam).purge()  # ответы удаляются каскадом
            exam.delete()
            log(request, "exam_deleted_with_results", f"exam:{r.exam_title}",
                old=json.dumps(snap, ensure_ascii=False)[:20000], new=f"удалено работ: {n_att}")
        else:
            log(request, "exam_deletion_decided", f"request:{r.id}", new=r.status)
        return Response({"status": r.status})