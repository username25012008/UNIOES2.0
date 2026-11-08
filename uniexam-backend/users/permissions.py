from rest_framework.permissions import BasePermission
from .models import Role


def has_role(*roles):
    class _HasRole(BasePermission):
        def has_permission(self, request, view):
            u = request.user
            return bool(u and u.is_authenticated and u.role in roles)
    return _HasRole


IsStudent = has_role(Role.STUDENT)
IsTeacher = has_role(Role.TEACHER)
IsObserver = has_role(Role.OBSERVER)
IsAdminRole = has_role(Role.ADMIN)
IsTeacherOrAdmin = has_role(Role.TEACHER, Role.ADMIN)

