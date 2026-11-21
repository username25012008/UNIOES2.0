"""Банк вопросов: импорт из Excel/JSON, шаблоны файлов и генерация вариантов."""
import io
import json

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsTeacherOrAdmin

from . import variants as V
from .models import Question, log
from .serializers import QuestionSerializer
from .views import check_editable, exams_for

MAX_ROWS, MAX_FILE = 2000, 2 * 1024 * 1024
LEVEL_ALIASES = {"easy": "easy", "лёгкий": "easy", "легкий": "easy", "medium": "medium", "средний": "medium",
                 "hard": "hard", "сложный": "hard"}
TYPE_ALIASES = {"single": "single", "один": "single", "multiple": "multiple", "несколько": "multiple",
                "written": "written", "развёрнутый": "written", "развернутый": "written"}
HEADERS = {"text": "text", "текст": "text", "вопрос": "text", "type": "type", "тип": "type",
           "difficulty": "difficulty", "level": "difficulty", "сложность": "difficulty", "уровень": "difficulty",
           "points": "points", "баллы": "points", "options": "options", "варианты": "options",
           "correct": "correct", "правильные": "correct", "правильный": "correct"}

SAMPLE = [
    {"text": "Что выведет код?\n<code lang=python>\nprint(2 ** 3)\n</code>", "type": "single",
     "difficulty": "easy", "points": 1, "options": ["6", "8", "9"], "correct": [2]},
    {"text": "Какие из типов изменяемые?", "type": "multiple", "difficulty": "medium", "points": 2,
     "options": ["list", "tuple", "dict", "str"], "correct": [1, 3]},
    {"text": "Чему равен корень уравнения $2x + 6 = 0$? Формулы LaTeX: $x^2$, $$\\frac{a}{b}$$", "type": "single",
     "difficulty": "easy", "points": 1, "options": ["$-3$", "$3$", "$\\frac{1}{3}$"], "correct": [1]},
    {"text": "Объясните разницу между списком и кортежем.", "type": "written", "difficulty": "hard",
     "points": 5, "options": [], "correct": []},
]


def _split(v):
    if isinstance(v, list):
        return [str(x).strip() for x in v]
    return [x.strip() for x in str(v or "").replace("\r", "").split("\n") if x.strip()] if "\n" in str(v or "") \
        else [x.strip() for x in str(v or "").split("|") if x.strip()]


def _correct(v):
    if isinstance(v, list):
        raw = v
    elif isinstance(v, (int, float)) and not isinstance(v, bool):
        raw = [v]
    else:
        raw = [x for x in str(v or "").replace(";", ",").split(",") if x.strip()]
    out = []
    for x in raw:
        try:
            f = float(x)
        except (TypeError, ValueError):
            raise ValueError(f"«{x}» — не номер варианта")
        if f != int(f) or isinstance(x, bool):
            raise ValueError(f"«{x}» — не номер варианта")
        out.append(int(f))
    return out


def _read_rows(f):
    name = (f.name or "").lower()
    raw = f.read()
    if name.endswith(".json"):
        try:
            data = json.loads(raw.decode("utf-8-sig"))
        except (ValueError, UnicodeDecodeError):
            raise ValueError("Файл не является корректным JSON (UTF-8)")
        if isinstance(data, dict):
            data = data.get("questions")
        if not isinstance(data, list) or not all(isinstance(x, dict) for x in data):
            raise ValueError("JSON должен быть списком вопросов (или объектом с ключом questions)")
        return [{HEADERS.get(str(k).strip().lower(), k): v for k, v in x.items()} for x in data]
    if name.endswith(".xlsx"):
        from openpyxl import load_workbook
        try:
            ws = load_workbook(io.BytesIO(raw), read_only=True, data_only=True).active
        except Exception:
            raise ValueError("Не удалось прочитать Excel-файл (нужен .xlsx)")
        it = ws.iter_rows(values_only=True)
        head = next(it, None)
        if not head:
            raise ValueError("Файл пустой")
        cols = [HEADERS.get(str(h).strip().lower()) if h is not None else None for h in head]
        if "text" not in cols:
            raise ValueError("В первой строке нужна колонка text (или «текст»)")
        return [{c: v for c, v in zip(cols, row) if c} for row in it if any(x not in (None, "") for x in row)]
    raise ValueError("Поддерживаются файлы .xlsx и .json")


def _convert(row, exam):
    """Одна строка файла → поля вопроса (индексы вариантов 1-based → 0-based)."""
    qtype = TYPE_ALIASES.get(str(row.get("type") or "single").strip().lower())
    if not qtype:
        raise ValueError("Неизвестный тип (single / multiple / written)")
    if exam.exam_type == "written" and qtype != "written" or exam.exam_type != "written" and qtype == "written":
        raise ValueError("Тип вопроса не подходит к типу экзамена")
    lvl = LEVEL_ALIASES.get(str(row.get("difficulty") or "medium").strip().lower())
    if not lvl:
        raise ValueError("Неизвестная сложность (easy / medium / hard)")
    pts = row.get("points", 1)
    pts = 1 if pts in (None, "") else pts
    if isinstance(pts, float) and pts == int(pts):
        pts = int(pts)
    if type(pts) is not int or not 1 <= pts <= 1000:
        raise ValueError("Баллы — целое число от 1")
    text = str(row.get("text") or "").strip()
    if not text:
        raise ValueError("Пустой текст вопроса")
    opts = _split(row.get("options")) if qtype != "written" else []
    cor = [c - 1 for c in _correct(row.get("correct"))] if qtype != "written" else []
    return {"text": text, "question_type": qtype, "difficulty": lvl, "points": pts,
            "options": opts, "correct_answers": cor}


class QuestionImport(APIView):
    """Загрузка вопросов из Excel/JSON. Всё или ничего: при любой ошибке не сохраняется ни один вопрос."""
    permission_classes = [IsTeacherOrAdmin]
    parser_classes = [MultiPartParser]

    @transaction.atomic
    def post(self, request, exam_pk):
        exam = get_object_or_404(exams_for(request.user), pk=exam_pk)
        check_editable(exam)
        f = request.FILES.get("file")
        if not f:
            return Response({"detail": "Прикрепите файл"}, status=400)
        if f.size > MAX_FILE:
            return Response({"detail": "Файл больше 2 МБ"}, status=400)
        try:
            rows = _read_rows(f)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)
        if not rows:
            return Response({"detail": "В файле нет вопросов"}, status=400)
        if len(rows) > MAX_ROWS:
            return Response({"detail": f"Не более {MAX_ROWS} вопросов за раз"}, status=400)
        ready, problems = [], []
        for n, row in enumerate(rows, start=2 if f.name.lower().endswith(".xlsx") else 1):
            try:
                data = _convert(row, exam)
                ser = QuestionSerializer(data=data)
                if not ser.is_valid():
                    msg = "; ".join(f"{k}: {' '.join(map(str, v))}" for k, v in ser.errors.items())
                    raise ValueError(msg)
                ready.append(ser.validated_data)
            except ValueError as e:
                problems.append(f"Строка {n}: {e}")
        if problems:
            return Response({"detail": "Файл не загружен: исправьте ошибки", "problems": problems[:50]}, status=400)
        start = exam.questions.count()
        Question.objects.bulk_create([Question(exam=exam, order=start + i + 1, **d) for i, d in enumerate(ready)])
        exam.variants.all().delete()
        log(request, "questions_imported", f"exam:{exam.id}", new=len(ready))
        return Response({"imported": len(ready)}, status=201)


class QuestionTemplate(APIView):
    permission_classes = [IsTeacherOrAdmin]

    def get(self, request):
        fmt = request.query_params.get("type", "xlsx")
        if fmt == "json":
            r = HttpResponse(json.dumps(SAMPLE, ensure_ascii=False, indent=2), content_type="application/json")
            r["Content-Disposition"] = 'attachment; filename="questions_template.json"'
            return r
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(["text", "type", "difficulty", "points", "options", "correct"])
        for x in SAMPLE:
            ws.append([x["text"], x["type"], x["difficulty"], x["points"], "\n".join(x["options"]),
                       ",".join(map(str, x["correct"]))])
        ws.append(["Подсказка: options — по одному варианту в строке ячейки (или через |), correct — номера "
                   "правильных вариантов с 1 через запятую. Код в тексте: <code lang=python> … </code>."])
        for col, w in zip("ABCDEF", (60, 12, 12, 8, 30, 10)):
            ws.column_dimensions[col].width = w
        buf = io.BytesIO()
        wb.save(buf)
        r = HttpResponse(buf.getvalue(),
                         content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        r["Content-Disposition"] = 'attachment; filename="questions_template.xlsx"'
        return r


class VariantsView(APIView):
    """GET — состояние и список вариантов, POST — сформировать, DELETE — отключить варианты."""
    permission_classes = [IsTeacherOrAdmin]

    def _exam(self, request, pk):
        return get_object_or_404(exams_for(request.user), pk=pk)

    def get(self, request, pk):
        e = self._exam(request, pk)
        pl = V.pools(e)
        rows = []
        if e.use_variants:
            names = {u.id: u for u in V.students_of(e)}
            for v in e.variants.all():
                u = names.get(v.student_id)
                rows.append({"student": u.full_name if u else f"#{v.student_id}", "group": u.edu_group if u else "",
                             "questions": len(v.question_ids), "question_ids": v.question_ids})
        return Response({"enabled": e.use_variants, "unique": e.variants_unique, "config": e.variant_config,
                         "pool": {lv: len(pl[lv]) for lv in V.LEVELS},
                         "students_total": len(V.students_of(e)),
                         "stats": V.stats(e) if e.use_variants else None, "variants": rows})

    def post(self, request, pk):
        e = self._exam(request, pk)
        check_editable(e)  # как и для вопросов: после попыток/публикации менять нельзя
        d = request.data
        unique = d.get("unique", True)
        if not isinstance(unique, bool):
            return Response({"detail": "unique должен быть true/false"}, status=400)
        try:
            cfg = V.parse_config(d.get("config"))
            problems = V.check_config(e, cfg)
            if problems:
                return Response({"detail": "Варианты сформировать нельзя", "problems": problems}, status=400)
            st = V.generate(e, cfg, unique)
        except V.VariantError as ex:
            return Response({"detail": str(ex)}, status=400)
        log(request, "variants_generated", f"exam:{e.id}", new=json.dumps(cfg))
        st["warning"] = None if st["fully_unique"] or not unique else (
            f"Вопросов в банке не хватает: {st['repeated_questions']} вопросов попали сразу нескольким студентам "
            "(повторы распределены равномерно). Добавьте вопросы, чтобы их не было.")
        return Response(st, status=201)

    def delete(self, request, pk):
        e = self._exam(request, pk)
        check_editable(e)
        e.variants.all().delete()
        e.use_variants, e.variant_config = False, {}
        e.save(update_fields=["use_variants", "variant_config"])
        return Response(status=204)
