import json
from datetime import timedelta

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APITestCase

from users.models import User

from .models import (Answer, Appeal, Attempt, AttemptStatus, AuditLog, DeletionRequest, Exam, Group, Question,
                     Subject, TeachingAssignment)
from .views_flow import finalize_expired


def mk(sid, role, **kw):
    return User.objects.create_user(student_id=sid, password="Passw0rd!x", role=role, full_name=sid, **kw)


class FlowBase(APITestCase):
    def setUp(self):
        cache.clear()
        self.g = Group.objects.create(name="SWE25-201")
        self.teacher, self.t2 = mk("100000000001", "teacher"), mk("100000000005", "teacher")
        self.admin = mk("100000000003", "admin")
        self.student = mk("546251100227", "student", edu_group="swe25-201")  # регистр не должен мешать
        self.s2 = mk("546251100228", "student", edu_group="SWE25-201")
        now = timezone.now()
        self.exam = Exam.objects.create(
            teacher=self.teacher, title="DB", subject="CS", exam_type="test", duration_minutes=30,
            start_at=now - timedelta(hours=1), end_at=now + timedelta(days=1), max_score=10, passing_score=5,
            status="published")
        self.exam.groups.add(self.g)
        self.q1 = Question.objects.create(exam=self.exam, text="2+2", options=["3", "4", "5"], correct_answers=[1], points=5, order=1)
        self.q2 = Question.objects.create(exam=self.exam, text="Prime", question_type="multiple", options=["2", "4", "7"],
                                          correct_answers=[0, 2], points=5, order=2)

    def start(self, user=None, exam=None):
        self.client.force_authenticate(user or self.student)
        r = self.client.post(f"/api/student/exams/{(exam or self.exam).id}/start/")
        self.assertIn(r.status_code, (200, 201), r.data)
        return r.data["attempt_id"]

    def answer(self, aid, q, **body):
        return self.client.put(f"/api/student/attempts/{aid}/answer/", {"question": q.id, **body}, format="json")

    def finish(self, correct=True):
        aid = self.start()
        self.answer(aid, self.q1, selected=[1])
        self.answer(aid, self.q2, selected=[0, 2] if correct else [0])
        self.client.post(f"/api/student/attempts/{aid}/submit/")
        return aid


class AttemptFlowTests(FlowBase):
    def test_student_sees_exam_case_insensitive_group(self):
        self.client.force_authenticate(self.student)
        self.assertEqual(len(self.client.get("/api/student/exams/").data), 1)

    def test_start_is_idempotent_and_db_blocks_duplicates(self):
        a1, a2 = self.start(), self.start()
        self.assertEqual(a1, a2)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Attempt.objects.create(exam=self.exam, student=self.student, deadline=timezone.now())

    def test_answer_validation(self):
        aid = self.start()
        for bad in ({"selected": "abc"}, {"selected": [99]}, {"selected": [1, 1]}, {"selected": [True]},
                    {"selected": {"a": 1}}, {"selected": [-1]}):
            self.assertEqual(self.answer(aid, self.q2, **bad).status_code, 400, bad)
        self.assertEqual(self.answer(aid, self.q1, selected=[0, 1]).status_code, 400)  # single: не более одного
        self.assertEqual(self.answer(aid, self.q1, selected=[1]).status_code, 200)

    def test_autograde_and_submit(self):
        aid = self.finish()
        a = Attempt.objects.get(pk=aid)
        self.assertEqual((a.status, a.final_score), ("final", 10))
        self.assertEqual(self.finish_again_status(aid), 200)  # повторная сдача безопасна

    def finish_again_status(self, aid):
        return self.client.post(f"/api/student/attempts/{aid}/submit/").status_code

    def test_partial_multiple_is_wrong(self):
        aid = self.finish(correct=False)
        self.assertEqual(Attempt.objects.get(pk=aid).final_score, 5)

    def test_cannot_answer_after_submit(self):
        aid = self.finish()
        self.assertEqual(self.answer(aid, self.q1, selected=[0]).status_code, 400)

    def test_cannot_open_foreign_attempt(self):
        aid = self.start()
        self.client.force_authenticate(self.s2)
        self.assertEqual(self.client.get(f"/api/student/attempts/{aid}/").status_code, 404)

    def test_expired_attempts_are_finalized(self):
        aid = self.start()
        self.answer(aid, self.q1, selected=[1])
        Attempt.objects.filter(pk=aid).update(deadline=timezone.now() - timedelta(minutes=1))
        self.assertEqual(finalize_expired(), 1)
        a = Attempt.objects.get(pk=aid)
        self.assertEqual((a.status, a.final_score), ("final", 5))

    def test_corrupt_stored_answer_does_not_crash_grading(self):
        aid = self.start()
        Answer.objects.create(attempt_id=aid, question=self.q2, selected="garbage")
        self.client.post(f"/api/student/attempts/{aid}/submit/")
        self.assertEqual(Attempt.objects.get(pk=aid).status, "final")

    def test_shuffle_per_attempt(self):
        for i in range(8):
            Question.objects.create(exam=self.exam, text=f"q{i}", options=["a", "b", "c", "d"], correct_answers=[0], points=1, order=3 + i)
        self.exam.randomize_questions = True
        self.exam.save()
        orders = []
        for u in (self.student, self.s2):
            aid = self.start(u)
            data = self.client.get(f"/api/student/attempts/{aid}/").data
            orders.append([q["id"] for q in data["questions"]])
            self.assertEqual(orders[-1], [q["id"] for q in self.client.get(f"/api/student/attempts/{aid}/").data["questions"]])
        self.assertNotEqual(orders[0], orders[1])

    def test_multiple_attempts_flag(self):
        self.finish()
        self.assertEqual(self.client.post(f"/api/student/exams/{self.exam.id}/start/").status_code, 400)
        self.exam.allow_multiple_attempts = True
        self.exam.save()
        row = self.client.get("/api/student/exams/").data[0]
        self.assertEqual((row["state"], row["retry"]), ("available", True))
        self.assertEqual(self.client.post(f"/api/student/exams/{self.exam.id}/start/").status_code, 201)


class ResultsAndGradeProtectionTests(FlowBase):
    def test_hidden_results_until_published(self):
        self.exam.show_results_immediately = False
        self.exam.save()
        self.finish()
        self.client.force_authenticate(self.student)
        row = self.client.get("/api/student/results/").data[0]
        self.assertTrue(row["hidden"])
        self.assertIsNone(row["score"])
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.post("/api/teacher/results/", {"exam": self.exam.id}, format="json").status_code, 200)
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get("/api/student/results/").data[0]["score"], 10)

    def test_teacher_results_endpoint_scoped(self):
        self.finish()
        self.client.force_authenticate(self.teacher)
        d = self.client.get("/api/teacher/results/").data
        self.assertEqual((d["count"], d["results"][0]["score"], d["results"][0]["passed"]), (1, 10, True))
        self.client.force_authenticate(self.t2)
        self.assertEqual(self.client.get("/api/teacher/results/").data["count"], 0)
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get("/api/teacher/results/").status_code, 403)

    def test_final_grade_cannot_be_changed_or_deleted(self):
        aid = self.finish()
        a = Attempt.objects.get(pk=aid)
        a.final_score = 1
        with self.assertRaises(ValidationError):
            a.save()
        with self.assertRaises(ValidationError):
            Attempt.objects.filter(pk=aid).update(final_score=1)
        with self.assertRaises(ValidationError):
            Attempt.objects.filter(pk=aid).delete()
        with self.assertRaises(ValidationError):
            a.delete()
        with self.assertRaises(ValidationError):
            Answer.objects.filter(attempt=a).first().save()
        self.assertEqual(Attempt.objects.get(pk=aid).final_score, 10)

    def test_django_admin_is_read_only_for_results(self):
        from django.contrib import admin
        m = admin.site._registry[Attempt]
        self.assertFalse(m.has_change_permission(None) or m.has_delete_permission(None) or m.has_add_permission(None))


class AppealTests(FlowBase):
    """Цепочка: студент → админ → учитель → админ → студент; одна апелляция на экзамен."""

    def appeal(self, aid, **kw):
        self.client.force_authenticate(self.student)
        body = {"attempt": aid, "questions": [self.q1.id], "category": "wrong_answer", "text": "Ключ неверный", **kw}
        return self.client.post("/api/student/appeals/", body, format="json")

    def admin_do(self, pid, action, note=""):
        self.client.force_authenticate(self.admin)
        return self.client.post("/api/admin/appeals/", {"id": pid, "action": action, "note": note}, format="json")

    def teacher_do(self, pid, who=None, **kw):
        self.client.force_authenticate(who or self.teacher)
        body = {"id": pid, "accept": True, "decision": "Ключ ошибочный", **kw}
        return self.client.post("/api/teacher/appeals/", body, format="json")

    def test_rules(self):
        aid = self.start()
        self.assertEqual(self.appeal(aid).status_code, 400)  # во время экзамена — только technical
        self.assertEqual(self.appeal(aid, category="technical").status_code, 201)  # не считается как «одна апелляция»
        self.client.post(f"/api/student/attempts/{aid}/submit/")
        other_exam = Exam.objects.create(teacher=self.teacher, title="O", subject="CS", start_at=timezone.now(),
                                         end_at=timezone.now() + timedelta(days=1))
        fq = Question.objects.create(exam=other_exam, text="чужой", order=1)
        self.assertEqual(self.appeal(aid, questions=[fq.id]).status_code, 400)  # вопрос чужого экзамена
        self.assertEqual(self.appeal(aid, category="bogus").status_code, 400)
        self.assertEqual(self.appeal(aid, questions=[self.q1.id, self.q2.id]).status_code, 201)
        self.assertEqual(self.appeal(aid, questions=[self.q2.id]).status_code, 400)  # вторая апелляция запрещена

    def test_window_expired(self):
        aid = self.finish()
        a = Attempt.objects.get(pk=aid)
        a.submitted_at = timezone.now() - timedelta(days=30)
        a._appeal_revision = True
        a.save()
        self.assertEqual(self.appeal(aid).status_code, 400)

    def test_full_chain_and_original_score_kept(self):
        aid = self.finish(correct=False)  # 5 из 10
        pid = self.appeal(aid).data["id"]
        # учитель ещё ничего не видит: апелляция у администратора
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.get("/api/teacher/appeals/").data, [])
        self.assertEqual(self.teacher_do(pid).status_code, 409)
        self.assertEqual(self.admin_do(pid, "approve").status_code, 409)  # пропустить этапы нельзя
        self.assertEqual(self.admin_do(pid, "forward", "проверьте").status_code, 200)
        self.client.force_authenticate(self.teacher)
        self.assertEqual(len(self.client.get("/api/teacher/appeals/").data), 1)
        self.assertEqual(self.teacher_do(pid, new_score=10).status_code, 200)
        # решение учителя ещё не меняет оценку и не показывается студенту
        self.assertEqual(Attempt.objects.get(pk=aid).final_score, 5)
        self.client.force_authenticate(self.student)
        row = self.client.get("/api/student/appeals/").data[0]
        self.assertEqual((row["status"], row["decision"]), ("teacher_done", ""))
        self.assertEqual(self.admin_do(pid, "approve", "согласовано").status_code, 200)
        a = Attempt.objects.get(pk=aid)
        self.assertEqual((a.final_score, a.original_score), (10, 5))
        self.client.force_authenticate(self.student)
        row = self.client.get("/api/student/appeals/").data[0]
        self.assertEqual(row["status"], "accepted")
        self.assertIn("Ключ ошибочный", row["decision"])
        self.assertEqual(self.admin_do(pid, "approve").status_code, 409)  # решение окончательное
        self.assertTrue(AuditLog.objects.filter(action="grade_revised_after_appeal").exists())

    def test_admin_rejects_at_first_step(self):
        aid = self.finish()
        pid = self.appeal(aid).data["id"]
        self.assertEqual(self.admin_do(pid, "reject").status_code, 400)  # нужна причина
        self.assertEqual(self.admin_do(pid, "reject", "Не по существу").status_code, 200)
        self.client.force_authenticate(self.student)
        row = self.client.get("/api/student/appeals/").data[0]
        self.assertEqual((row["status"], row["decision"]), ("rejected", "Не по существу"))
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.get("/api/teacher/appeals/").data, [])  # учителю не уходила

    def test_admin_returns_teacher_decision(self):
        aid = self.finish(correct=False)
        pid = self.appeal(aid).data["id"]
        self.admin_do(pid, "forward")
        self.teacher_do(pid, new_score=10)
        self.assertEqual(self.admin_do(pid, "return").status_code, 400)
        self.assertEqual(self.admin_do(pid, "return", "Обоснуйте подробнее").status_code, 200)
        self.assertEqual(Appeal.objects.get(pk=pid).status, "review")
        self.assertEqual(Attempt.objects.get(pk=aid).final_score, 5)
        self.assertEqual(self.teacher_do(pid, accept=False, decision="Ответ верный").status_code, 200)
        self.assertEqual(self.admin_do(pid, "approve").status_code, 200)
        self.assertEqual(Appeal.objects.get(pk=pid).status, "rejected")
        self.assertEqual(Attempt.objects.get(pk=aid).final_score, 5)

    def test_permissions_and_validation(self):
        aid = self.finish()
        pid = self.appeal(aid).data["id"]
        self.admin_do(pid, "forward")
        self.assertEqual(self.teacher_do(pid, who=self.t2).status_code, 403)  # чужой преподаватель
        self.assertEqual(self.teacher_do(pid, decision=" ").status_code, 400)
        self.assertEqual(self.teacher_do(pid, new_score=999).status_code, 400)
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.post("/api/admin/appeals/", {"id": pid, "action": "approve"}, format="json").status_code, 403)
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get("/api/admin/appeals/").status_code, 403)


class EditLockTests(FlowBase):
    def test_exam_locked_after_attempts(self):
        self.finish()
        self.client.force_authenticate(self.teacher)
        self.client.post(f"/api/exams/{self.exam.id}/hide/")  # «спрятать и подправить» больше не работает
        qurl = f"/api/exams/{self.exam.id}/questions/"
        self.assertEqual(self.client.patch(f"{qurl}{self.q1.id}/", {"correct_answers": [0]}, format="json").status_code, 400)
        self.assertEqual(self.client.post(qurl, {"text": "n", "question_type": "single", "options": ["a", "b"], "correct_answers": [0], "points": 1}, format="json").status_code, 400)
        self.assertEqual(self.client.delete(f"{qurl}{self.q1.id}/").status_code, 400)  # было 500
        for field, val in (("duration_minutes", 5), ("max_score", 99)):
            self.assertEqual(self.client.patch(f"/api/exams/{self.exam.id}/", {field: val}, format="json").status_code, 400, field)
        self.assertEqual(self.client.patch(f"/api/exams/{self.exam.id}/", {"title": "Новое имя"}, format="json").status_code, 200)

    def test_published_exam_key_params_locked(self):
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.patch(f"/api/exams/{self.exam.id}/", {"duration_minutes": 5}, format="json").status_code, 400)


class DeletionTests(FlowBase):
    def test_request_then_admin_approves_with_audit_snapshot(self):
        self.finish()
        self.client.force_authenticate(self.teacher)
        self.client.post(f"/api/exams/{self.exam.id}/hide/")
        r = self.client.delete(f"/api/exams/{self.exam.id}/")
        self.assertEqual(r.status_code, 202)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.delete(f"/api/exams/{self.exam.id}/").status_code, 400)  # админ не удаляет напрямую
        rid = DeletionRequest.objects.get().id
        self.client.post("/api/admin/deletion-requests/", {"id": rid, "approve": True}, format="json")
        self.assertFalse(Exam.objects.filter(pk=self.exam.id).exists())
        log = AuditLog.objects.get(action="exam_deleted_with_results")
        self.assertEqual(json.loads(log.previous_value)[0]["final"], 10)


class AuthTests(FlowBase):
    def test_login_lockout_and_refresh(self):
        for _ in range(5):
            self.assertEqual(self.client.post("/api/auth/login/", {"student_id": self.student.student_id, "password": "bad"}, format="json").status_code, 401)
        self.assertEqual(self.client.post("/api/auth/login/", {"student_id": self.student.student_id, "password": "Passw0rd!x"}, format="json").status_code, 429)

    def test_refresh_token_flow(self):
        r = self.client.post("/api/auth/login/", {"student_id": self.student.student_id, "password": "Passw0rd!x"}, format="json")
        self.assertIn("refresh", r.data)
        r2 = self.client.post("/api/auth/refresh/", {"refresh": r.data["refresh"]}, format="json")
        self.assertEqual(r2.status_code, 200)
        self.assertIn("access", r2.data)

    def test_change_and_reset_password(self):
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.post("/api/auth/change-password/", {"old_password": "no", "new_password": "NewPassw0rd!1"}, format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/auth/change-password/", {"old_password": "Passw0rd!x", "new_password": "123"}, format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/auth/change-password/", {"old_password": "Passw0rd!x", "new_password": "NewPassw0rd!1"}, format="json").status_code, 200)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(f"/api/admin/users/{self.student.id}/reset-password/", {"new_password": "Another#Pass42"}, format="json").status_code, 200)
        self.student.refresh_from_db()
        self.assertTrue(self.student.check_password("Another#Pass42"))
        self.assertTrue(AuditLog.objects.filter(action="password_reset").exists())

    def test_admin_edits_name_and_role_and_logs(self):
        self.client.force_authenticate(self.admin)
        r = self.client.patch(f"/api/admin/users/{self.s2.id}/", {"full_name": "Новое Имя", "role": "observer"}, format="json")
        self.assertEqual((r.status_code, r.data["role"], r.data["edu_group"]), (200, "observer", ""))
        self.assertEqual(self.client.patch(f"/api/admin/users/{self.admin.id}/", {"role": "student"}, format="json").status_code, 400)


class ProctoringTests(FlowBase):
    def event(self, aid, kind):
        return self.client.post(f"/api/student/attempts/{aid}/event/", {"kind": kind}, format="json")

    def test_events_counted_and_exam_terminated_at_limit(self):
        aid = self.start()
        self.answer(aid, self.q1, selected=[1])
        self.assertEqual(self.event(aid, "bogus").status_code, 400)
        self.assertEqual(self.event(aid, "copy_attempt").data["violations"], 0)  # только журнал, не нарушение
        self.assertEqual(self.event(aid, "tab_hidden").data["violations"], 1)
        self.assertEqual(self.event(aid, "fullscreen_exit").data["violations"], 2)
        r = self.event(aid, "window_blur")
        self.assertTrue(r.data["terminate"])
        a = Attempt.objects.get(pk=aid)
        self.assertEqual((a.status, a.final_score), ("final", 5))  # ответы засчитаны, экзамен завершён
        self.assertTrue(AuditLog.objects.filter(action="attempt_terminated_violations").exists())

    def test_teacher_sees_violations_and_foreign_student_cannot_report(self):
        aid = self.start()
        self.event(aid, "tab_hidden")
        self.client.post(f"/api/student/attempts/{aid}/submit/")
        self.client.force_authenticate(self.s2)
        self.assertEqual(self.event(aid, "tab_hidden").status_code, 404)
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.get("/api/teacher/results/").data["results"][0]["violations"], 1)
