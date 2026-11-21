from django.contrib import admin

from .models import Exam, Group, Question


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ("title", "subject", "exam_type", "status", "teacher", "start_at")
    list_filter = ("status", "exam_type")
    search_fields = ("title", "subject")
    inlines = [QuestionInline]


admin.site.register(Group)
