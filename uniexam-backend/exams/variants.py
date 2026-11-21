"""Варианты экзамена: у каждого студента свой набор вопросов из банка.

Алгоритм: для каждого уровня сложности студент получает k вопросов с наименьшим числом уже выданных
копий (случайно среди равных). Пока вопросов в банке хватает на всех (студентов × k ≤ размер банка)
повторов нет совсем; если не хватает — повторы распределяются максимально равномерно.
Внутри одного варианта вопрос никогда не повторяется."""
import random
from collections import Counter

from django.db import transaction

from users.models import Role, User

from .models import Exam, ExamVariant, Question

LEVELS = ("easy", "medium", "hard")
LEVEL_NAMES = {"easy": "лёгких", "medium": "средних", "hard": "сложных"}
MAX_PER_LEVEL = 500


class VariantError(Exception):
    pass


def parse_config(cfg):
    """{'easy': 5, 'medium': 10} → полный словарь по трём уровням; бросает VariantError."""
    if not isinstance(cfg, dict):
        raise VariantError("Укажите, сколько вопросов каждого уровня попадёт в вариант")
    out = {}
    for lv in LEVELS:
        v = cfg.get(lv, 0)
        if type(v) is not int or not 0 <= v <= MAX_PER_LEVEL:
            raise VariantError(f"Количество вопросов уровня «{lv}» — целое число от 0 до {MAX_PER_LEVEL}")
        out[lv] = v
    if not sum(out.values()):
        raise VariantError("В варианте должен быть хотя бы один вопрос")
    return out


def students_of(exam):
    names = [g.name for g in exam.groups.all()]
    qs = User.objects.none()
    for n in names:
        qs = qs | User.objects.filter(role=Role.STUDENT, is_active=True, edu_group__iexact=n)
    return list(qs.distinct().order_by("edu_group", "full_name", "id"))


def pools(exam):
    out = {lv: [] for lv in LEVELS}
    for q in exam.questions.all():
        if q.difficulty in out:
            out[q.difficulty].append(q)
    return out


def check_config(exam, cfg):
    """Список проблем (пусто — конфигурация выполнима). Баллы внутри уровня должны быть одинаковыми,
    а сумма баллов варианта — равна максимальному баллу экзамена."""
    problems, total = [], 0
    pl = pools(exam)
    for lv in LEVELS:
        k = cfg.get(lv, 0)
        if not k:
            continue
        if len(pl[lv]) < k:
            problems.append(f"Нужно {k} {LEVEL_NAMES[lv]} вопросов, а в банке только {len(pl[lv])}")
            continue
        pts = {q.points for q in pl[lv]}
        if len(pts) > 1:
            problems.append(f"У {LEVEL_NAMES[lv]} вопросов разные баллы ({', '.join(map(str, sorted(pts)))}): "
                            "задайте одинаковые, чтобы сумма была равна во всех вариантах")
        total += k * (next(iter(pts)) if pts else 0)
    if not problems and total != exam.max_score:
        problems.append(f"Сумма баллов варианта ({total}) должна равняться максимальному баллу ({exam.max_score})")
    return problems


def _pick(pool, k, usage, unique, rng):
    if unique:
        ranked = sorted(pool, key=lambda q: (usage[q.id], rng.random()))
        chosen = ranked[:k]
    else:
        chosen = rng.sample(pool, k)
    for q in chosen:
        usage[q.id] += 1
    return chosen


def build(exam, students, cfg, unique, usage=None, rng=None):
    """Возвращает {student_id: [question_id, ...]}."""
    rng = rng or random.Random()
    usage = usage if usage is not None else Counter()
    pl = pools(exam)
    order = list(students)
    rng.shuffle(order)
    res = {}
    for st in order:
        ids = []
        for lv in LEVELS:
            if cfg.get(lv):
                ids += [q.id for q in _pick(pl[lv], cfg[lv], usage, unique, rng)]
        res[st.id] = ids
    return res


def stats(exam):
    used = Counter()
    for v in exam.variants.all():
        used.update(v.question_ids)
    shared = sum(1 for n in used.values() if n > 1)
    return {"students": exam.variants.count(), "questions_used": len(used),
            "repeated_questions": shared, "fully_unique": shared == 0}


@transaction.atomic
def generate(exam, cfg, unique):
    """Пересоздаёт варианты всем студентам выбранных групп."""
    exam.variants.all().delete()
    students = students_of(exam)
    if not students:
        raise VariantError("В выбранных группах нет активных студентов")
    data = build(exam, students, cfg, unique)
    ExamVariant.objects.bulk_create([ExamVariant(exam=exam, student_id=sid, question_ids=ids)
                                     for sid, ids in data.items()])
    exam.use_variants, exam.variants_unique, exam.variant_config = True, unique, cfg
    exam.save(update_fields=["use_variants", "variants_unique", "variant_config"])
    return stats(exam)


def variant_for(exam, student):
    """Вариант студента; если его ещё нет (студента добавили позже или банк менялся) — выдаётся сейчас
    с учётом уже выданных вопросов."""
    v = ExamVariant.objects.filter(exam=exam, student=student).first()
    if v:
        return v
    cfg = parse_config(exam.variant_config)
    problems = check_config(exam, cfg)
    if problems:
        raise VariantError("Вариант невозможно сформировать: " + "; ".join(problems))
    usage = Counter()
    for other in exam.variants.all():
        usage.update(other.question_ids)
    ids = build(exam, [student], cfg, exam.variants_unique, usage)[student.id]
    v, _ = ExamVariant.objects.get_or_create(exam=exam, student=student, defaults={"question_ids": ids})
    return v


def questions_for_attempt(attempt):
    """Вопросы, которые видит студент в этой попытке (в порядке варианта)."""
    exam = attempt.exam
    if not exam.use_variants:
        return list(exam.questions.all())
    v = ExamVariant.objects.filter(exam=exam, student=attempt.student).first()
    by_id = {q.id: q for q in exam.questions.filter(pk__in=v.question_ids)} if v else {}
    return [by_id[i] for i in (v.question_ids if v else []) if i in by_id]
