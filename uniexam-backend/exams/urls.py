from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views_flow as f
from . import views_admin as ad
from . import views_appeals as ap
from . import views_variants as vv
from .views import TeachingInfoView, ExamViewSet, GroupListView, QuestionViewSet, TeacherStatsView

router = DefaultRouter()
router.register("exams", ExamViewSet, basename="exam")

question_list = QuestionViewSet.as_view({"get": "list", "post": "create"})
question_detail = QuestionViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)

urlpatterns = [
    path("exams/questions/template/", vv.QuestionTemplate.as_view()),
    path("exams/<int:exam_pk>/questions/import/", vv.QuestionImport.as_view()),
    path("exams/<int:pk>/variants/", vv.VariantsView.as_view()),
    path("exams/<int:exam_pk>/questions/", question_list),
    path("exams/<int:exam_pk>/questions/<int:pk>/", question_detail),
    path("teacher/teaching/", TeachingInfoView.as_view()),
    path("admin/users/", ad.Users.as_view()),
    path("admin/users/<int:pk>/", ad.UserDetail.as_view()),
    path("admin/users/<int:pk>/reset-password/", ad.ResetPassword.as_view()),
    path("admin/subjects/", ad.Subjects.as_view()),
    path("admin/subjects/<int:pk>/", ad.Subjects.as_view()),
    path("admin/groups/", ad.Groups.as_view()),
    path("admin/assignments/", ad.Assignments.as_view()),
    path("admin/assignments/<int:pk>/", ad.Assignments.as_view()),
    path("admin/deletion-requests/", ad.DeletionRequests.as_view()),
    path("groups/", GroupListView.as_view()),
    path("teacher/stats/", TeacherStatsView.as_view()),
    path("student/exams/", f.StudentExams.as_view()),
    path("student/exams/<int:pk>/start/", f.StartExam.as_view()),
    path("student/attempts/<int:pk>/", f.AttemptView.as_view()),
    path("student/attempts/<int:pk>/answer/", f.SaveAnswer.as_view()),
    path("student/attempts/<int:pk>/event/", f.AttemptEventView.as_view()),
    path("student/attempts/<int:pk>/submit/", f.SubmitAttempt.as_view()),
    path("student/results/", f.StudentResults.as_view()),
    path("student/results/<int:pk>/", f.StudentResults.as_view()),
    path("student/appeals/", ap.StudentAppeals.as_view()),
    path("admin/appeals/", ap.AdminAppeals.as_view()),
    path("teacher/appeals/", ap.TeacherAppeals.as_view()),
    path("teacher/grading/", f.WrittenGrading.as_view()),
    path("teacher/results/", f.TeacherResults.as_view()),
    path("admin/audit/", f.AuditLogView.as_view()),
    path("observer/overview/", f.ObserverOverview.as_view()),
    path("", include(router.urls)),
]
