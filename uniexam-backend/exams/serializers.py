from rest_framework import serializers

from users.models import Role
from .models import TeachingAssignment, Exam, ExamStatus, ExamType, Group, Question, QuestionType


import re

_OPEN, _CLOSE = re.compile(r"<code(?:\s+lang=[\"']?[\w+#.-]{1,20}[\"']?)?\s*>", re.I), re.compile(r"</code>", re.I)


def check_code_tags(text):
    """Код оформляется как <code lang=python>…</code>; теги должны быть парными и не вложенными."""
    if not isinstance(text, str) or len(text) > 20000:
        raise serializers.ValidationError("Текст слишком длинный (до 20000 символов)")
    opens, closes = len(_OPEN.findall(text)), len(_CLOSE.findall(text))
    if opens != closes or len(re.findall(r"<code\b", text, re.I)) != opens:
        raise serializers.ValidationError("Теги кода должны быть парными: <code lang=python> … </code>")
    depth = 0
    for m in re.finditer(r"<code\b[^>]*>|</code>", text, re.I):
        depth += -1 if m.group(0).startswith("</") else 1
        if depth not in (0, 1):
            raise serializers.ValidationError("Теги <code> не могут быть вложенными")
    return text


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ["id", "name", "is_archived"]


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = [
            "id", "text", "question_type", "options",
            "correct_answers", "points", "difficulty", "order",
        ]

    def validate_text(self, v):
        return check_code_tags(v)

    def validate(self, attrs):
        for o in attrs.get("options", []) or []:
            check_code_tags(str(o))
        # При частичном обновлении берём недостающие значения из объекта
        inst = self.instance
        qtype = attrs.get("question_type", getattr(inst, "question_type", QuestionType.SINGLE))
        options = attrs.get("options", getattr(inst, "options", []))
        correct = attrs.get("correct_answers", getattr(inst, "correct_answers", []))

        if qtype == QuestionType.WRITTEN:
            attrs["options"] = []
            attrs["correct_answers"] = []
            return attrs

        options = [str(o).strip() for o in options]
        if len(options) < 2 or any(not o for o in options):
            raise serializers.ValidationError(
                {"options": "Нужно минимум 2 непустых варианта ответа"}
            )
        if not correct:
            raise serializers.ValidationError(
                {"correct_answers": "Укажите правильный ответ"}
            )
        if any((not isinstance(i, int)) or i < 0 or i >= len(options) for i in correct):
            raise serializers.ValidationError(
                {"correct_answers": "Правильный ответ должен быть среди вариантов"}
            )
        if qtype == QuestionType.SINGLE and len(correct) != 1:
            raise serializers.ValidationError(
                {"correct_answers": "Для вопроса с одним ответом выберите ровно один вариант"}
            )
        attrs["options"] = options
        attrs["correct_answers"] = sorted(set(correct))
        return attrs


class ExamSerializer(serializers.ModelSerializer):
    groups = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Group.objects.filter(is_archived=False), required=False
    )
    group_names = serializers.SerializerMethodField()
    teacher_name = serializers.CharField(source="teacher.full_name", read_only=True)
    questions_count = serializers.SerializerMethodField()
    questions_points = serializers.SerializerMethodField()
    difficulty_distribution = serializers.SerializerMethodField()
    has_results = serializers.SerializerMethodField()
    pending_deletion = serializers.SerializerMethodField()

    def get_has_results(self, obj):
        return obj.attempts.exists()

    def get_pending_deletion(self, obj):
        return obj.deletion_requests.filter(status="pending").exists()

    class Meta:
        model = Exam
        fields = [
            "id", "title", "subject", "description", "exam_type",
            "groups", "group_names", "teacher_name",
            "duration_minutes", "start_at", "end_at",
            "max_score", "passing_score",
            "randomize_questions", "allow_multiple_attempts",
            "allow_appeals", "show_results_immediately",
            "use_variants", "variants_unique", "variant_config",
            "status", "questions_count", "questions_points",
            "difficulty_distribution", "has_results", "pending_deletion", "created_at", "updated_at",
        ]
        # Статус меняется только через publish / hide / archive
        read_only_fields = ["status", "use_variants", "variants_unique", "variant_config", "created_at", "updated_at"]

    def get_group_names(self, obj):
        return [g.name for g in obj.groups.all()]

    def get_questions_count(self, obj):
        return obj.questions.count()

    def get_questions_points(self, obj):
        return sum(q.points for q in obj.questions.all())

    def get_difficulty_distribution(self, obj):
        dist = {"easy": 0, "medium": 0, "hard": 0}
        for q in obj.questions.all():
            dist[q.difficulty] = dist.get(q.difficulty, 0) + 1
        return dist

    def validate_duration_minutes(self, value):
        if value < 1 or value > 600:
            raise serializers.ValidationError("Длительность: от 1 до 600 минут")
        return value

    def validate(self, attrs):
        self._check_teaching(attrs)
        inst = self.instance
        start = attrs.get("start_at", getattr(inst, "start_at", None))
        end = attrs.get("end_at", getattr(inst, "end_at", None))
        max_score = attrs.get("max_score", getattr(inst, "max_score", 100))
        passing = attrs.get("passing_score", getattr(inst, "passing_score", 0))
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"end_at": "Время окончания должно быть позже времени начала"}
            )
        if passing > max_score:
            raise serializers.ValidationError(
                {"passing_score": "Проходной балл не может быть больше максимального"}
            )
        if inst and inst.exam_type != attrs.get("exam_type", inst.exam_type):
            if inst.questions.exists():
                raise serializers.ValidationError(
                    {"exam_type": "Нельзя менять тип экзамена, пока в нём есть вопросы"}
                )
        return attrs

    def _check_teaching(self, attrs):
        """Преподаватель может создавать экзамены только по своим предметам и группам."""
        user = self.context["request"].user
        if user.role != Role.TEACHER or not ("subject" in attrs or "groups" in attrs):
            return
        subject = attrs.get("subject", getattr(self.instance, "subject", None))
        mine = TeachingAssignment.objects.filter(teacher=user, subject__name=subject)
        if not mine.exists():
            raise serializers.ValidationError({"subject": "Этот предмет вам не назначен. Обратитесь к администратору"})
        allowed = set(mine.values_list("group_id", flat=True))
        groups = attrs.get("groups")
        if groups is not None and any(g.id not in allowed for g in groups):
            raise serializers.ValidationError({"groups": "Выбрана группа, которой вы не преподаёте этот предмет"})

    def check_publishable(self, exam):
        """Возвращает список причин, по которым экзамен нельзя опубликовать."""
        problems = []
        if not exam.questions.exists():
            problems.append("Добавьте хотя бы один вопрос")
        if not exam.groups.exists():
            problems.append("Выберите хотя бы одну группу")
        if exam.use_variants:
            from .variants import check_config, parse_config, VariantError
            try:
                problems += check_config(exam, parse_config(exam.variant_config))
            except VariantError as e:
                problems.append(str(e))
            return problems
        total = sum(q.points for q in exam.questions.all())
        if exam.questions.exists() and total != exam.max_score:
            problems.append(
                f"Сумма баллов вопросов ({total}) должна равняться максимальному баллу ({exam.max_score})"
            )
        return problems
