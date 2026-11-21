import re

from django.core.exceptions import ValidationError


class ComplexPasswordValidator:
    """Минимум: заглавная и строчная буква, цифра и спецсимвол."""

    def validate(self, password, user=None):
        errors = []
        if not re.search(r"[A-ZА-ЯЁ]", password):
            errors.append("одну заглавную букву")
        if not re.search(r"[a-zа-яё]", password):
            errors.append("одну строчную букву")
        if not re.search(r"\d", password):
            errors.append("одну цифру")
        if not re.search(r"[^\w\s]|_", password):
            errors.append("один специальный символ (например !@#$%)")
        if errors:
            raise ValidationError("Пароль должен содержать " + ", ".join(errors) + ".", code="password_complexity")

    def get_help_text(self):
        return "Минимум 8 символов: заглавная и строчная буквы, цифра и спецсимвол."
