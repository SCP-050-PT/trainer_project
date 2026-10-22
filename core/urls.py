from django.urls import path
from . import views

urlpatterns = [
    # --- ДЛЯ УЧЕНИКА ---
    # 1. Вход ученика (выбор класса + PIN) — ЭТОГО НЕ ХВАТАЛО!
    path("student-login/", views.student_login_view, name="student_login"),
    # 2. Кабинет ученика (список тестов)
    path("student-dashboard/", views.student_dashboard, name="student_dashboard"),
    # 3. Прохождение конкретного теста
    path("take-test/<int:exam_run_id>/", views.take_test, name="take_test"),
    # 4. Результат теста
    path("result/<int:attempt_id>/", views.student_result, name="student_result"),
    # 5. Выход ученика
    path("student-logout/", views.student_logout, name="student_logout"),
    # --- ДЛЯ УЧИТЕЛЯ / АДМИНА ---
    # 6. Дашборд сотрудника
    path("dashboard/", views.dashboard_view, name="dashboard"),
    # 7. Импорт списков учеников
    path("import-students/", views.import_students_view, name="import_students"),
]
