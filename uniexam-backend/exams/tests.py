from datetime import timedelta
from django.utils import timezone
from rest_framework.test import APITestCase
from users.models import User
from .models import Exam, Group, Subject, TeachingAssignment


def mk(sid, role, **kw):
    return User.objects.create_user(student_id=sid, password="x", role=role, **kw)


class ExamApiTests(APITestCase):
    def setUp(self):
        self.g = Group.objects.create(name="SWE25-201")
        self.teacher = mk("100000000001", "teacher")
        self.other = mk("100000000004", "teacher")
        self.student = mk("546251100227", "student", edu_group="SWE25-201")
        subj = Subject.objects.create(name="CS")  # преподаватели создают экзамены только по назначенным предметам
        TeachingAssignment.objects.create(teacher=self.teacher, subject=subj, group=self.g)
        TeachingAssignment.objects.create(teacher=self.other, subject=subj, group=self.g)
        now = timezone.now()
        self.payload = {
            "title": "Algorithms", "subject": "CS", "exam_type": "test",
            "groups": [self.g.id], "duration_minutes": 45,
            "start_at": (now + timedelta(days=1)).isoformat(),
            "end_at": (now + timedelta(days=2)).isoformat(),
            "max_score": 10, "passing_score": 5,
        }

    def create(self):
        self.client.force_authenticate(self.teacher)
        r = self.client.post("/api/exams/", self.payload, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        return r.data["id"]

    def q(self, eid, **kw):
        d = {"text": "2+2?", "question_type": "single", "options": ["3", "4"],
             "correct_answers": [1], "points": 10, "difficulty": "easy"}
        d.update(kw)
        return self.client.post(f"/api/exams/{eid}/questions/", d, format="json")

    def test_student_forbidden(self):
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get("/api/exams/").status_code, 403)
        self.assertEqual(self.client.post("/api/exams/", self.payload, format="json").status_code, 403)

    def test_anonymous_unauthorized(self):
        self.assertIn(self.client.get("/api/exams/").status_code, (401, 403))

    def test_create_sets_owner_and_draft(self):
        eid = self.create()
        e = Exam.objects.get(id=eid)
        self.assertEqual(e.teacher, self.teacher)
        self.assertEqual(e.status, "draft")

    def test_status_not_writable_via_post(self):
        self.payload["status"] = "published"
        eid = self.create()
        self.assertEqual(Exam.objects.get(id=eid).status, "draft")

    def test_teacher_sees_only_own(self):
        eid = self.create()
        self.client.force_authenticate(self.other)
        self.assertEqual(len(self.client.get("/api/exams/").data), 0)
        self.assertEqual(self.client.get(f"/api/exams/{eid}/").status_code, 404)
        self.assertEqual(self.client.delete(f"/api/exams/{eid}/").status_code, 404)
        self.assertEqual(self.q(eid).status_code, 404)

    def test_date_validation(self):
        self.payload["end_at"] = self.payload["start_at"]
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.post("/api/exams/", self.payload, format="json").status_code, 400)

    def test_passing_over_max(self):
        self.payload["passing_score"] = 99
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.post("/api/exams/", self.payload, format="json").status_code, 400)

    def test_question_validation(self):
        eid = self.create()
        self.assertEqual(self.q(eid, options=["only"]).status_code, 400)
        self.assertEqual(self.q(eid, correct_answers=[5]).status_code, 400)
        self.assertEqual(self.q(eid, correct_answers=[0, 1]).status_code, 400)
        self.assertEqual(self.q(eid, question_type="written").status_code, 400)  # тип не подходит
        self.assertEqual(self.q(eid).status_code, 201)

    def test_publish_rules(self):
        eid = self.create()
        r = self.client.post(f"/api/exams/{eid}/publish/")
        self.assertEqual(r.status_code, 400)
        self.assertTrue(r.data["problems"])
        self.q(eid, points=3)  # сумма 3 != 10
        self.assertEqual(self.client.post(f"/api/exams/{eid}/publish/").status_code, 400)
        qid = Exam.objects.get(id=eid).questions.first().id
        self.client.patch(f"/api/exams/{eid}/questions/{qid}/", {"points": 10}, format="json")
        r = self.client.post(f"/api/exams/{eid}/publish/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["status"], "published")

    def test_published_protected(self):
        eid = self.create(); self.q(eid)
        self.client.post(f"/api/exams/{eid}/publish/")
        self.assertEqual(self.q(eid).status_code, 400)
        self.assertEqual(self.client.delete(f"/api/exams/{eid}/").status_code, 400)
        self.client.post(f"/api/exams/{eid}/hide/")
        self.assertEqual(Exam.objects.get(id=eid).status, "hidden")
        self.assertEqual(self.client.delete(f"/api/exams/{eid}/").status_code, 204)

    def test_duplicate(self):
        eid = self.create(); self.q(eid)
        r = self.client.post(f"/api/exams/{eid}/duplicate/")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["status"], "draft")
        self.assertEqual(r.data["questions_count"], 1)
        self.assertEqual(r.data["group_names"], ["SWE25-201"])
        self.assertEqual(Exam.objects.count(), 2)

    def test_archive_locks(self):
        eid = self.create()
        self.client.post(f"/api/exams/{eid}/archive/")
        self.assertEqual(self.client.patch(f"/api/exams/{eid}/", {"title": "x"}, format="json").status_code, 400)
        self.assertEqual(self.client.post(f"/api/exams/{eid}/publish/").status_code, 400)

    def test_stats(self):
        self.create()
        r = self.client.get("/api/teacher/stats/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["total_exams"], 1)
        self.assertEqual(r.data["draft"], 1)
        self.assertEqual(r.data["total_students"], 1)

    def test_written_flow(self):
        self.payload["exam_type"] = "written"
        eid = self.create()
        r = self.q(eid, question_type="written", options=[], correct_answers=[])
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self.q(eid).status_code, 400)
