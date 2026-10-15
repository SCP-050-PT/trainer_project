from django.urls import path
from . import views

urlpatterns = [
    # --- ДЛЯ УЧЕНИКА ---
    # Вход ученика обрабатывается в config/urls.py как главная страница ('')
    # Кабинет ученика (список тестов)
    path("student-dashboard/", views.student_dashboard, name="student_dashboard"),
    # Прохождение конкретного теста
    path("take-test/<int:exam_run_id>/", views.take_test, name="take_test"),
    # Результат теста (Вот эта функция нужна! Мы добавим её ниже)
    path("result/<int:attempt_id>/", views.student_result, name="student_result"),
    # Выход ученика
    path("student-logout/", views.student_logout, name="student_logout"),
    # --- ДЛЯ УЧИТЕЛЯ / АДМИНА ---
    # Дашборд сотрудника
    path("dashboard/", views.dashboard_view, name="dashboard"),
    # Импорт списков учеников
    path("import-students/", views.import_students_view, name="import_students"),
]
