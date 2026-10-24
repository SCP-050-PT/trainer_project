from django.shortcuts import render
from functools import wraps
from django.shortcuts import redirect


def student_required(view_func):
    """
    Декоратор для страниц ученика.
    Проверяет наличие student_id в сессии.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if "student_id" not in request.session:
            return redirect("student_login")
        return view_func(request, *args, **kwargs)

    return wrapper


def landing_view(request):
    """Главная страница — выбор роли."""
    return render(request, "landing.html")
