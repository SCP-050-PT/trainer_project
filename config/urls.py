from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.views import LoginView, LogoutView

# Импортируем нашу view для входа ученика
from core.views import student_login_view

urlpatterns = [
    # 1. Админка Django
    path("admin/", admin.site.urls),
    # 2. Вход для СОТРУДНИКОВ (Учителя/Админы)
    # Используем стандартную форму логина Django, но указываем свой шаблон
    path(
        "staff-login/",
        LoginView.as_view(
            template_name="registration/login.html",
            redirect_authenticated_user=True,  # Если уже залогинен - редирект на дашборд
        ),
        name="login",
    ),
    # 3. Выход сотрудников
    path("logout/", LogoutView.as_view(next_page="/"), name="logout"),
    # 4. ГЛАВНАЯ СТРАНИЦА (/) -> Вход для УЧЕНИКА
    # Этот маршрут ДОЛЖЕН быть последним среди основных путей, чтобы не перехватывать админку
    path("", student_login_view, name="home"),
    # 5. Остальные пути приложения core (dashboard, тесты и т.д.)
    # Ставим include ПОСЛЕ корневого пути ''
    path("", include("core.urls")),
]
