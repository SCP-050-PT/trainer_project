from functools import wraps
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Avg
from datetime import datetime

# Импорты моделей
from .models import (
    Student,
    SchoolClass,
    ExamRun,
    Attempt,
    AnswerAttempt,
    Question,
    AnswerOption,
    CorrectAnswer,
    Subject,
    User,
)
from .utils.importer import parse_student_file, create_students_from_import

# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================


def student_required(view_func):
    """
    Декоратор для страниц ученика.
    Проверяет наличие student_id в сессии.
    Если нет - редиректит на главную (вход ученика).
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if "student_id" not in request.session:
            return redirect("home")  # home = path('', student_login_view)
        return view_func(request, *args, **kwargs)

    return wrapper


# ==========================================
# ДЛЯ УЧЕНИКА
# ==========================================


def student_login_view(request):
    """Страница входа ученика: Выбор класса + PIN."""
    # Если ученик уже вошел, кидаем его сразу в кабинет
    if "student_id" in request.session:
        return redirect("student_dashboard")

    classes = SchoolClass.objects.all().order_by("parallel", "letter")
    error = None

    if request.method == "POST":
        class_id = request.POST.get("school_class")
        pin = request.POST.get("pin_code")

        try:
            # Ищем ученика по классу и PIN
            student = Student.objects.get(school_class_id=class_id, pin_code=pin)

            # Сохраняем данные в сессию
            request.session["student_id"] = student.id
            request.session["student_name"] = student.full_name

            return redirect("student_dashboard")
        except Student.DoesNotExist:
            error = "Неверный класс или PIN-код."

    return render(
        request, "core/student/login.html", {"classes": classes, "error": error}
    )


@student_required  # <-- Заменили @login_required на наш декоратор
def student_dashboard(request):
    """Кабинет ученика: список доступных тестов."""
    student_id = request.session.get("student_id")
    student = get_object_or_404(Student, id=student_id)

    # Получаем активные ExamRun для класса этого ученика
    available_exams = ExamRun.objects.filter(
        school_class=student.school_class, status="active"
    ).select_related("test", "test__subject")

    # Исключаем уже пройденные (если нужно разрешить пересдачи - убери фильтр ниже)
    passed_exam_ids = Attempt.objects.filter(student=student).values_list(
        "exam_run_id", flat=True
    )
    available_exams = available_exams.exclude(id__in=passed_exam_ids)

    return render(
        request,
        "core/student/dashboard.html",
        {"student": student, "exams": available_exams},
    )


@student_required
def take_test(request, exam_run_id):
    """Прохождение теста."""
    student_id = request.session.get("student_id")
    student = get_object_or_404(Student, id=student_id)

    # Проверяем, что экзамен относится к классу ученика
    exam_run = get_object_or_404(
        ExamRun, id=exam_run_id, school_class=student.school_class
    )

    # Создаем попытку (или берем существующую незавершенную)
    attempt, created = Attempt.objects.get_or_create(
        student=student, exam_run=exam_run, defaults={"is_completed": False}
    )

    # Если попытка уже завершена, показываем результат
    if attempt.is_completed:
        return redirect("student_result", attempt_id=attempt.id)

    questions = exam_run.test.questions.all()

    if request.method == "POST":
        correct_count = 0
        max_points = questions.count()

        for q in questions:
            ans_key = f"answer_{q.id}"
            user_val = request.POST.get(ans_key)

            is_correct = False
            option_obj = None

            if q.question_type in ["single_choice", "multiple_choice"]:
                try:
                    opt_id = int(user_val)
                    option_obj = AnswerOption.objects.get(id=opt_id, question=q)
                    is_correct = option_obj.is_correct
                except (ValueError, TypeError, AnswerOption.DoesNotExist):
                    pass
            else:
                # Text/Input
                ca = getattr(q, "correct_answer", None)
                if ca and user_val:
                    is_correct = ca.verify_answer(user_val)

            # Логируем ответ
            AnswerAttempt.objects.update_or_create(
                attempt=attempt,
                question=q,
                defaults={
                    "selected_option": option_obj,
                    "given_value": user_val if not option_obj else "",
                    "is_correct": is_correct,
                },
            )

            if is_correct:
                correct_count += 1

        # Обновляем результат попытки
        attempt.score = correct_count
        attempt.max_score = max_points
        attempt.percentage = (
            round((correct_count / max_points) * 100, 2) if max_points > 0 else 0
        )

        # Расчет звезд
        if attempt.percentage >= 90:
            attempt.stars = 5
        elif attempt.percentage >= 75:
            attempt.stars = 4
        elif attempt.percentage >= 50:
            attempt.stars = 3
        elif attempt.percentage >= 30:
            attempt.stars = 2
        else:
            attempt.stars = 1

        attempt.finished_at = datetime.now()
        attempt.is_completed = True
        attempt.save()

        return redirect("student_result", attempt_id=attempt.id)

    return render(
        request,
        "core/student/test.html",
        {"exam_run": exam_run, "questions": questions, "attempt": attempt},
    )


@student_required
def student_logout(request):
    """Выход ученика (очистка сессии)."""
    if "student_id" in request.session:
        del request.session["student_id"]
        del request.session["student_name"]
    return redirect("home")


@student_required
def student_result(request, attempt_id):
    """Экран результатов для ученика."""
    # Получаем попытку по ID, проверяя, что она принадлежит текущему ученику
    attempt = get_object_or_404(
        Attempt, id=attempt_id, student_id=request.session.get("student_id")
    )

    # Получаем все ответы этой попытки с деталями вопросов
    answers = attempt.answers.select_related("question", "selected_option")

    return render(
        request, "core/student/result.html", {"attempt": attempt, "answers": answers}
    )


# ==========================================
# ДЛЯ УЧИТЕЛЯ / АДМИНА (RBAC)
# ==========================================


@login_required  # Здесь оставляем стандартный Django-декоратор
def dashboard_view(request):
    """Главная страница после входа сотрудника."""
    user = request.user
    context = {}

    if user.is_admin():
        # Статистика по всей школе
        context["total_students"] = Student.objects.count()
        context["total_tests_taken"] = Attempt.objects.filter(is_completed=True).count()
        avg_pct = Attempt.objects.filter(is_completed=True).aggregate(
            Avg("percentage")
        )["percentage__avg"]
        context["avg_percentage"] = round(avg_pct, 1) if avg_pct else 0
    else:
        # Статистика по своим классам (упрощенно пока)
        # TODO: Реализовать точную фильтрацию через TeacherAssignment -> SchoolClass
        context["message"] = "Добро пожаловать в кабинет учителя!"
        context["total_students"] = Student.objects.count()  # Заглушка
        context["total_tests_taken"] = Attempt.objects.filter(is_completed=True).count()

    return render(request, "core/dashboard.html", context)


@login_required
def import_students_view(request):
    """Импорт списка учеников."""
    # Показываем только те классы, которые доступны пользователю
    # Для админа - все, для учителя - свои (пока показываем все для теста)
    classes = SchoolClass.objects.all()

    if request.method == "POST":
        file_obj = request.FILES.get("file")
        class_id = request.POST.get("school_class")

        if not file_obj or not class_id:
            messages.error(request, "Выберите файл и класс.")
            return redirect("import_students")

        school_class = get_object_or_404(SchoolClass, id=class_id)

        try:
            # Используем наши новые функции
            data = parse_student_file(file_obj, school_class)
            created, skipped = create_students_from_import(data, school_class)

            msg = f"Успешно добавлено: {created} учеников."
            if skipped:
                msg += f" Пропущено (дубликаты): {skipped}."

            messages.success(request, msg)

            # Опционально: редирект на страницу просмотра списка учеников этого класса
            # return redirect('student_list', class_id=school_class.id)

        except Exception as e:
            messages.error(request, str(e))

        return redirect("import_students")

    return render(request, "core/import_students.html", {"classes": classes})
