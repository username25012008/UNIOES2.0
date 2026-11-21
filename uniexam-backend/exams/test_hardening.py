from datetime import timedelta

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from users.models import User

from .models import Answer, Attempt, AuditLog, Exam, Question, log
from .test_flow import FlowBase, mk

GOOD = "Str0ng!pass"


class PasswordPolicyTests(FlowBase):
    def post_user(self, pw):
        self.client.force_authenticate(self.admin)
        return self.client.post("/api/admin/users/", {"student_id": "999999999999", "role": "student",
                                                       "full_name": "Test", "password": pw}, format="json")

    def test_weak_passwords_rejected_at_creation(self):
        for bad in ("Sh0rt!a", "alllowercase1!", "ALLUPPERCASE1!", "NoDigitsHere!", "NoSpecial123", "Ab1!", 12345678):
            self.assertEqual(self.post_user(bad).status_code, 400, bad)
        self.assertEqual(self.post_user(GOOD).status_code, 201)

    def test_change_and_reset_use_policy(self):
        self.client.force_authenticate(self.student)
        r = self.client.post("/api/auth/change-password/", {"old_password": "Passw0rd!x", "new_password": "weakpass1"},
                             format="json")
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/api/auth/change-password/", {"old_password": "Passw0rd!x", "new_password": [1]},
                             format="json")
        self.assertEqual(r.status_code, 400)
        self.client.force_authenticate(self.admin)
        r = self.client.post(f"/api/admin/users/{self.student.id}/reset-password/", {"new_password": "nodigits!Aa"},
                             format="json")
        self.assertEqual(r.status_code, 400)


class TokenTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.u = mk("200000000001", "student")

    def login(self, pw="Passw0rd!x"):
        return APIClient().post("/api/auth/login/", {"student_id": "200000000001", "password": pw}, format="json")

    def test_refresh_rotation_blacklists_old_token(self):
        refresh = self.login().data["refresh"]
        c = APIClient()
        r1 = c.post("/api/auth/refresh/", {"refresh": refresh}, format="json")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(c.post("/api/auth/refresh/", {"refresh": refresh}, format="json").status_code, 401)

    def test_logout_revokes_refresh(self):
        refresh = self.login().data["refresh"]
        c = APIClient()
        self.assertEqual(c.post("/api/auth/logout/", {"refresh": refresh}, format="json").status_code, 200)
        self.assertEqual(c.post("/api/auth/refresh/", {"refresh": refresh}, format="json").status_code, 401)

    def test_password_change_revokes_old_tokens(self):
        d = self.login().data
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION="Bearer " + d["token"])
        r = c.post("/api/auth/change-password/", {"old_password": "Passw0rd!x", "new_password": GOOD}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(c.get("/api/auth/getUserInfo/").status_code, 401)  # старый access отозван
        self.assertEqual(APIClient().post("/api/auth/refresh/", {"refresh": d["refresh"]}, format="json").status_code, 401)
        self.assertEqual(self.login(GOOD).status_code, 200)

    def test_lockout_counter(self):
        for _ in range(5):
            self.assertEqual(self.login("bad").status_code, 401)
        self.assertEqual(self.login("Passw0rd!x").status_code, 429)


class ExamHardeningTests(FlowBase):
    def test_late_save_within_grace_ok_after_grace_rejected(self):
        aid = self.start()
        Attempt.objects.filter(pk=aid).update(deadline=timezone.now() - timedelta(seconds=2))
        self.assertEqual(self.answer(aid, self.q1, selected=[1]).status_code, 200)
        Attempt.objects.filter(pk=aid).update(deadline=timezone.now() - timedelta(seconds=60))
        self.assertEqual(self.answer(aid, self.q1, selected=[0]).status_code, 400)

    def test_older_timestamp_does_not_overwrite_newer(self):
        aid = self.start()
        self.answer(aid, self.q1, selected=[1], ts=200)
        self.answer(aid, self.q1, selected=[0], ts=100)
        self.assertEqual(Answer.objects.get(attempt_id=aid, question=self.q1).selected, [1])
        self.answer(aid, self.q1, selected=[2], ts=300)
        self.assertEqual(Answer.objects.get(attempt_id=aid, question=self.q1).selected, [2])

    def test_submit_with_bulk_answers(self):
        aid = self.start()
        r = self.client.post(f"/api/student/attempts/{aid}/submit/", {"answers": [
            {"question": self.q1.id, "selected": [1], "ts": 1},
            {"question": self.q2.id, "selected": [0, 2], "ts": 1}]}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Attempt.objects.get(pk=aid).final_score, 10)

    def test_bulk_answers_validated(self):
        aid = self.start()
        for bad in ("x", [1], [{"question": 9999, "selected": [0]}], [{"question": self.q1.id, "selected": [9]}]):
            r = self.client.post(f"/api/student/attempts/{aid}/submit/", {"answers": bad}, format="json")
            self.assertEqual(r.status_code, 400, bad)
        self.assertEqual(Attempt.objects.get(pk=aid).status, "in_progress")

    def test_queryset_guards(self):
        aid = self.finish()
        with self.assertRaises(ValidationError):
            Answer.objects.filter(attempt_id=aid).update(points=99)
        with self.assertRaises(ValidationError):
            Answer.objects.filter(attempt_id=aid).delete()
        log(type("R", (), {"user": self.admin, "META": {}})(), "x", "y")
        with self.assertRaises(ValidationError):
            AuditLog.objects.all().update(action="hacked")
        with self.assertRaises(ValidationError):
            AuditLog.objects.all().delete()

    def test_event_spam_is_capped(self):
        aid = self.start()
        for _ in range(250):
            Attempt.objects.get(pk=aid)  # no-op, keep loop cheap
        from .views_flow import MAX_EVENTS
        from .models import AttemptEvent
        AttemptEvent.objects.bulk_create([AttemptEvent(attempt_id=aid, kind="copy_attempt") for _ in range(MAX_EVENTS)])
        self.client.post(f"/api/student/attempts/{aid}/event/", {"kind": "copy_attempt"}, format="json")
        self.assertEqual(AttemptEvent.objects.filter(attempt_id=aid).count(), MAX_EVENTS)

    def test_written_result_hidden_until_published(self):
        self.exam.exam_type, self.exam.show_results_immediately = "written", False
        self.exam.save()
        a = Attempt.objects.create(exam=self.exam, student=self.student, deadline=timezone.now(),
                                   status="final", final_score=7, submitted_at=timezone.now())
        self.client.force_authenticate(self.student)
        r = self.client.get("/api/student/results/")
        self.assertIsNone(r.data[0]["score"])
        self.exam.results_published = True
        self.exam.save()
        self.assertEqual(self.client.get("/api/student/results/").data[0]["score"], 7)

    def test_garbage_input_gives_400_not_500(self):
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.post("/api/student/appeals/", {"attempt": "abc", "text": "x"}, format="json").status_code, 400)
        self.client.force_authenticate(self.teacher)
        for url, body in (("/api/teacher/appeals/", {"id": "x"}), ("/api/teacher/appeals/", {"id": 1, "accept": "no"}),
                          ("/api/teacher/results/", {"exam": "x"})):
            self.assertEqual(self.client.post(url, body, format="json").status_code, 400, (url, body))
        self.assertEqual(self.client.get("/api/teacher/results/?exam=abc").status_code, 400)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get("/api/admin/audit/?date_from=oops").status_code, 400)
        self.assertEqual(self.client.patch(f"/api/admin/users/{self.s2.id}/", {"is_active": "false"}, format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/auth/login/", [1, 2], format="json").status_code, 400)
