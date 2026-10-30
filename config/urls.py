from django.contrib import admin
from core.admin import teacher_admin
from django.urls import path, include
from django.contrib.auth.views import LoginView, LogoutView
from core.views import landing_view

urlpatterns = [
    # 1. Админка Django
    path("admin/", admin.site.urls),
    path("admin-teacher/", teacher_admin.urls),
    # 2. Вход для СОТРУДНИКОВ -> /staff-login/
    path(
        "staff-login/",
        LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    # 3. ВЫХОД ДЛЯ СОТРУДНИКОВ
    path("logout/", LogoutView.as_view(next_page="/"), name="logout"),
    # 4. ГЛАВНАЯ СТРАНИЦА (/) -> Страница выбора роли
    path("", landing_view, name="home"),
    # 5. ВСЕ ОСТАЛЬНЫЕ МАРШРУТЫ (включая student-login/)
    # Подключаем ПОСЛЕ '', но Django умный и сначала проверит точные совпадения из include
    path("", include("core.urls")),
]
