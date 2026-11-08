from django.contrib import admin
from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("student_id", "full_name", "role", "is_active")
    list_filter = ("role", "is_active")
    search_fields = ("student_id", "full_name")