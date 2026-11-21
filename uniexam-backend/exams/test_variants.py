import io
import json
from collections import Counter
from datetime import timedelta

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from openpyxl import Workbook, load_workbook
from rest_framework.test import APITestCase

from users.models import User

from .models import Exam, ExamVariant, Group, Question, Subject, TeachingAssignment


def mk(sid, role, **kw):
    return User.objects.create_user(student_id=sid, password="Passw0rd!x", role=role, full_name=sid, **kw)


class VariantBase(APITestCase):
    def setUp(self):
        cache.clear()
        self.g1, self.g2 = Group.objects.create(name="G1"), Group.objects.create(name="G2")
        self.teacher, self.other = mk("100000000001", "teacher"), mk("100000000002", "teacher")
        sub = Subject.objects.create(name="Programming")
        for g in (self.g1, self.g2):
            TeachingAssignment.objects.create(teacher=self.teacher, subject=sub, group=g)
        self.students = [mk(f"5462511002{i:02d}", "student", edu_group="G1" if i < 3 else "G2") for i in range(6)]
        now = timezone.now()
        self.exam = Exam.objects.create(
            teacher=self.teacher, title="Py", subject="Programming", exam_type="test", duration_minutes=30,
            start_at=now - timedelta(hours=1), end_at=now + timedelta(days=1), max_score=8, passing_score=4)
        self.exam.groups.add(self.g1, self.g2)

    def bank(self, easy=0, medium=0, hard=0):
        for lv, n, pts in (("easy", easy, 1), ("medium", medium, 2), ("hard", hard, 3)):
            for i in range(n):
                Question.objects.create(exam=self.exam, text=f"{lv}-{i}", options=["a", "b"], correct_answers=[0],
                                        difficulty=lv, points=pts, order=1)

    def gen(self, easy=2, medium=1, hard=1, unique=True):
        self.client.force_authenticate(self.teacher)
        # 2*1 + 1*2 + 1*3 = 7; чтобы сумма была 8 — добавляем лёгкий
        return self.client.post(f"/api/exams/{self.exam.id}/variants/",
                                {"config": {"easy": easy, "medium": medium, "hard": hard}, "unique": unique}, format="json")


class VariantTests(VariantBase):
    def test_unique_when_bank_is_large_enough(self):
        self.bank(easy=18, medium=6, hard=6)  # 6 студентов × (3 лёгких + 1 средний + 1 сложный) = 18/6/6
        r = self.gen(easy=3, medium=1, hard=1)  # 3 + 2 + 3 = 8
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data["fully_unique"])
        all_ids = [i for v in ExamVariant.objects.filter(exam=self.exam) for i in v.question_ids]
        self.assertEqual(len(all_ids), 30)
        self.assertEqual(len(set(all_ids)), 30)  # ни одного общего вопроса
        for v in ExamVariant.objects.filter(exam=self.exam):
            self.assertEqual(len(set(v.question_ids)), len(v.question_ids))
            levels = Counter(Question.objects.get(pk=i).difficulty for i in v.question_ids)
            self.assertEqual(dict(levels), {"easy": 3, "medium": 1, "hard": 1})

    def test_minimal_repeats_when_bank_is_small(self):
        self.bank(easy=4, medium=6, hard=6)  # лёгких 6×3=18 > 4
        r = self.gen(easy=3, medium=1, hard=1)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertFalse(r.data["fully_unique"])
        self.assertIn("не хватает", r.data["warning"])
        use = Counter(i for v in ExamVariant.objects.all() for i in v.question_ids
                      if Question.objects.get(pk=i).difficulty == "easy")
        self.assertLessEqual(max(use.values()) - min(use.values()), 1)  # равномерно
        for v in ExamVariant.objects.all():
            self.assertEqual(len(set(v.question_ids)), len(v.question_ids))  # у одного студента без дублей

    def test_unique_switch_off_allows_repeats(self):
        self.bank(easy=18, medium=6, hard=6)
        r = self.gen(easy=3, medium=1, hard=1, unique=False)
        self.assertEqual(r.status_code, 201)
        self.exam.refresh_from_db()
        self.assertFalse(self.exam.variants_unique)

    def test_config_validation(self):
        self.bank(easy=2, medium=1, hard=1)
        r = self.gen(easy=5, medium=1, hard=1)
        self.assertEqual(r.status_code, 400)
        self.assertTrue(any("только 2" in p for p in r.data["problems"]))
        self.assertEqual(self.gen(easy=0, medium=0, hard=0).status_code, 400)
        self.client.force_authenticate(self.teacher)
        for cfg in ({"easy": "3"}, {"easy": -1}, [], None):
            self.assertEqual(self.client.post(f"/api/exams/{self.exam.id}/variants/", {"config": cfg}, format="json").status_code, 400)
        self.assertEqual(self.client.post(f"/api/exams/{self.exam.id}/variants/", {"config": {"easy": 1}, "unique": "yes"}, format="json").status_code, 400)

    def test_points_sum_must_match(self):
        self.bank(easy=6, medium=6, hard=6)
        r = self.gen(easy=1, medium=1, hard=1)  # 1+2+3=6 != 8
        self.assertEqual(r.status_code, 400)
        self.assertTrue(any("8" in p for p in r.data["problems"]))

    def test_student_gets_only_own_variant_and_can_only_answer_it(self):
        self.bank(easy=18, medium=6, hard=6)
        self.gen(easy=3, medium=1, hard=1)
        Exam.objects.filter(pk=self.exam.pk).update(status="published")
        st = self.students[0]
        self.client.force_authenticate(st)
        aid = self.client.post(f"/api/student/exams/{self.exam.id}/start/").data["attempt_id"]
        qs = self.client.get(f"/api/student/attempts/{aid}/").data["questions"]
        mine = ExamVariant.objects.get(exam=self.exam, student=st).question_ids
        self.assertEqual([q["id"] for q in qs], mine)
        foreign = Question.objects.exclude(pk__in=mine).first()
        r = self.client.put(f"/api/student/attempts/{aid}/answer/", {"question": foreign.id, "selected": [0]}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.client.put(f"/api/student/attempts/{aid}/answer/", {"question": mine[0], "selected": [0]}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get("/api/student/exams/").data[0]["questions"], 5)

    def test_late_student_gets_variant_avoiding_used_questions(self):
        self.bank(easy=21, medium=7, hard=7)
        self.gen(easy=3, medium=1, hard=1)
        Exam.objects.filter(pk=self.exam.pk).update(status="published")
        late = mk("546251100299", "student", edu_group="G1")
        self.client.force_authenticate(late)
        self.assertEqual(self.client.post(f"/api/student/exams/{self.exam.id}/start/").status_code, 201)
        mine = set(ExamVariant.objects.get(exam=self.exam, student=late).question_ids)
        used = {i for v in ExamVariant.objects.exclude(student=late) for i in v.question_ids}
        self.assertFalse(mine & used)

    def test_editing_bank_resets_variants_and_publish_checks_them(self):
        self.bank(easy=18, medium=6, hard=6)
        self.gen(easy=3, medium=1, hard=1)
        self.client.force_authenticate(self.teacher)
        q = Question.objects.filter(exam=self.exam).first()
        self.assertEqual(self.client.delete(f"/api/exams/{self.exam.id}/questions/{q.id}/").status_code, 204)
        self.assertEqual(ExamVariant.objects.filter(exam=self.exam).count(), 0)
        self.assertEqual(self.client.post(f"/api/exams/{self.exam.id}/publish/").status_code, 200)
        self.client.post(f"/api/exams/{self.exam.id}/hide/")
        Question.objects.filter(exam=self.exam, difficulty="hard").delete()
        r = self.client.post(f"/api/exams/{self.exam.id}/publish/")
        self.assertEqual(r.status_code, 400)

    def test_only_owner_and_state(self):
        self.bank(easy=18, medium=6, hard=6)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f"/api/exams/{self.exam.id}/variants/").status_code, 404)
        self.assertEqual(self.gen(easy=3, medium=1, hard=1).status_code, 201)
        r = self.client.get(f"/api/exams/{self.exam.id}/variants/")
        self.client.force_authenticate(self.teacher)
        r = self.client.get(f"/api/exams/{self.exam.id}/variants/")
        self.assertEqual((r.data["enabled"], len(r.data["variants"]), r.data["students_total"]), (True, 6, 6))
        self.assertEqual(self.client.delete(f"/api/exams/{self.exam.id}/variants/").status_code, 204)
        self.exam.refresh_from_db()
        self.assertFalse(self.exam.use_variants)


class ImportTests(VariantBase):
    def up(self, name, data, content_type="application/octet-stream"):
        self.client.force_authenticate(self.teacher)
        f = SimpleUploadedFile(name, data if isinstance(data, bytes) else data.encode(), content_type=content_type)
        return self.client.post(f"/api/exams/{self.exam.id}/questions/import/", {"file": f}, format="multipart")

    def test_json_import_with_code(self):
        rows = [{"text": "Что выведет?\n<code lang=python>\nprint(1+1)\n</code>", "type": "single",
                 "difficulty": "easy", "points": 2, "options": ["1", "2"], "correct": [2]},
                {"text": "Выберите", "type": "multiple", "difficulty": "сложный", "points": 3,
                 "options": ["a", "b", "c"], "correct": [1, 3]}]
        r = self.up("q.json", json.dumps(rows))
        self.assertEqual(r.status_code, 201, r.data)
        q = Question.objects.filter(exam=self.exam).order_by("id")
        self.assertEqual([x.correct_answers for x in q], [[1], [0, 2]])
        self.assertIn("<code lang=python>", q[0].text)
        self.assertEqual(q[1].difficulty, "hard")

    def test_xlsx_import_and_template_roundtrip(self):
        self.client.force_authenticate(self.teacher)
        t = self.client.get("/api/exams/questions/template/?type=xlsx")
        self.assertEqual(t.status_code, 200)
        ws = load_workbook(io.BytesIO(t.content)).active
        rows = list(ws.iter_rows(values_only=True))
        self.assertEqual(rows[0], ("text", "type", "difficulty", "points", "options", "correct"))
        # шаблон содержит письменный вопрос, поэтому для теста его убираем
        wb = Workbook()
        w = wb.active
        w.append(rows[0])
        w.append(rows[1])
        w.append(rows[2])
        buf = io.BytesIO()
        wb.save(buf)
        r = self.up("q.xlsx", buf.getvalue())
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Question.objects.filter(exam=self.exam).count(), 2)
        self.assertEqual(self.client.get("/api/exams/questions/template/?type=json").status_code, 200)

    def test_all_or_nothing_with_row_numbers(self):
        rows = [{"text": "ok", "options": ["a", "b"], "correct": [1]},
                {"text": "bad", "options": ["a", "b"], "correct": [5]},
                {"text": "x <code>без закрытия", "options": ["a", "b"], "correct": [1]},
                {"text": "", "options": ["a", "b"], "correct": [1]}]
        r = self.up("q.json", json.dumps(rows))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(len(r.data["problems"]), 3)
        self.assertTrue(r.data["problems"][0].startswith("Строка 2"))
        self.assertEqual(Question.objects.filter(exam=self.exam).count(), 0)

    def test_bad_files(self):
        self.assertEqual(self.up("q.txt", "x").status_code, 400)
        self.assertEqual(self.up("q.json", "{oops").status_code, 400)
        self.assertEqual(self.up("q.json", "[]").status_code, 400)
        self.assertEqual(self.up("q.xlsx", b"not a zip").status_code, 400)
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.post(f"/api/exams/{self.exam.id}/questions/import/", {}, format="multipart").status_code, 400)
        self.client.force_authenticate(self.other)
        f = SimpleUploadedFile("q.json", b"[]")
        self.assertEqual(self.client.post(f"/api/exams/{self.exam.id}/questions/import/", {"file": f}, format="multipart").status_code, 404)

    def test_locked_after_attempts_or_publish(self):
        Exam.objects.filter(pk=self.exam.pk).update(status="published")
        self.assertEqual(self.up("q.json", '[{"text":"a","options":["a","b"],"correct":[1]}]').status_code, 400)


class MathTests(VariantBase):
    def test_formulas_pass_through_unchanged(self):
        self.client.force_authenticate(self.teacher)
        url = f"/api/exams/{self.exam.id}/questions/"
        text = "Найдите $\\frac{a}{b}$ и $$\\sum_{i=1}^{n} i$$ <code lang=python>print('$')</code>"
        r = self.client.post(url, {"question_type": "single", "options": ["$x^2$", "$\\sqrt{x}$"], "correct_answers": [0],
                                   "points": 1, "text": text}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        q = Question.objects.get(pk=r.data["id"])
        self.assertEqual((q.text, q.options[0]), (text, "$x^2$"))
        rows = json.dumps([{"text": "$\\frac{1}{2}$ равно?", "options": ["0.5", "2"], "correct": [1]}])
        up = SimpleUploadedFile("m.json", rows.encode())
        self.assertEqual(self.client.post(f"/api/exams/{self.exam.id}/questions/import/", {"file": up}, format="multipart").status_code, 201)
        self.assertTrue(Question.objects.filter(text="$\\frac{1}{2}$ равно?").exists())


class CodeTagTests(VariantBase):
    def test_manual_question_code_tags(self):
        self.client.force_authenticate(self.teacher)
        url = f"/api/exams/{self.exam.id}/questions/"
        base = {"question_type": "single", "options": ["a", "b"], "correct_answers": [0], "points": 1}
        ok = self.client.post(url, {**base, "text": "x\n<code lang=python>\nprint(1)\n</code>"}, format="json")
        self.assertEqual(ok.status_code, 201, ok.data)
        for bad in ("<code lang=python>print(1)", "<code><code>x</code></code>", "</code>x"):
            self.assertEqual(self.client.post(url, {**base, "text": bad}, format="json").status_code, 400, bad)
