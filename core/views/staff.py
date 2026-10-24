from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Avg
from ..models import Student, SchoolClass, ExamRun, Attempt
from ..utils.importer import parse_student_file, create_students_from_import


@login_required
def dashboard_view(request):
    """Главная страница после входа сотрудника."""
    total_students = Student.objects.count()
    completed = Attempt.objects.filter(is_completed=True)
    total_attempts = completed.count()
    avg = completed.aggregate(Avg("percentage"))["percentage__avg"] or 0
    active_runs = ExamRun.objects.filter(status="active").count()

    recent = Attempt.objects.filter(is_completed=True).select_related("student", "exam_run__test").order_by("-finished_at")[:8]

    return render(
        request,
        "core/dashboard.html",
        {
            "total_students": total_students,
            "total_attempts": total_attempts,
            "avg_percentage": round(avg, 1),
            "active_runs": active_runs,
            "recent": recent,
        },
    )


@login_required
def import_students_view(request):
    """Импорт списка учеников."""
    classes = SchoolClass.objects.all()

    if request.method == "POST":
        file_obj = request.FILES.get("file")
        class_id = request.POST.get("school_class")

        if not file_obj or not class_id:
            messages.error(request, "Выберите файл и класс.")
            return redirect("import_students")

        school_class = get_object_or_404(SchoolClass, id=class_id)

        try:
            data = parse_student_file(file_obj, school_class)
            created, skipped = create_students_from_import(data, school_class)

            msg = f"Успешно добавлено: {created} учеников."
            if skipped:
                msg += f" Пропущено (дубликаты): {skipped}."

            messages.success(request, msg)
        except Exception as e:
            messages.error(request, str(e))

        return redirect("import_students")

    return render(request, "core/import_students.html", {"classes": classes})


@login_required
def student_list_view(request):
    """Список учеников с поиском и экспортом."""
    query = request.GET.get("q", "").strip()
    class_id = request.GET.get("class", "")

    students = Student.objects.select_related("school_class").all()

    if query:
        students = students.filter(full_name__icontains=query)
    if class_id:
        students = students.filter(school_class_id=class_id)

    classes = SchoolClass.objects.all().order_by("parallel", "letter")

    return render(
        request,
        "core/student_list.html",
        {
            "students": students,
            "classes": classes,
            "query": query,
            "selected_class": class_id,
        },
    )


@login_required
def export_students_csv(request):
    """Экспорт списка учеников в CSV."""
    import csv
    from django.http import HttpResponse

    query = request.GET.get("q", "").strip()
    class_id = request.GET.get("class", "")

    students = Student.objects.select_related("school_class").all()
    if query:
        students = students.filter(full_name__icontains=query)
    if class_id:
        students = students.filter(school_class_id=class_id)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="students.csv"'
    response.write("\ufeff")  # BOM для Excel

    writer = csv.writer(response)
    writer.writerow(["ФИО", "Класс", "PIN"])

    for s in students:
        writer.writerow([s.full_name, s.school_class.display_name, s.pin_code])

    return response


@login_required
def assign_test_view(request):
    """Назначение теста (ExamRun) классу."""
    from ..models import Test

    subjects = get_teacher_subjects(request.user)
    tests = Test.objects.filter(is_active=True, subject__in=subjects).select_related("subject")
    classes = get_teacher_classes(request.user).order_by("parallel", "letter")

    if request.method == "POST":
        test_id = request.POST.get("test")
        class_id = request.POST.get("school_class")
        deadline = request.POST.get("deadline") or None

        if not test_id or not class_id:
            messages.error(request, "Выберите тест и класс.")
            return redirect("assign_test")

        test = get_object_or_404(Test, id=test_id)
        school_class = get_object_or_404(SchoolClass, id=class_id)

        ExamRun.objects.create(
            test=test,
            school_class=school_class,
            deadline=deadline,
            status="active",
        )
        messages.success(request, f"Тест «{test.title}» назначен классу {school_class.display_name}.")
        return redirect("assign_test")

    return render(
        request,
        "core/assign_test.html",
        {"tests": tests, "classes": classes},
    )


@login_required
def exam_list_view(request):
    """Список назначенных тестов."""
    exams = ExamRun.objects.select_related("test", "test__subject", "school_class").order_by("-started_at")
    return render(request, "core/exam_list.html", {"exams": exams})


@login_required
def close_exam_view(request, exam_id):
    """Закрыть назначение теста."""
    exam = get_object_or_404(ExamRun, id=exam_id)
    exam.status = "finished"
    exam.save()
    messages.success(request, f"Тест «{exam.test.title}» для класса {exam.school_class.display_name} закрыт.")
    return redirect("exam_list")


@login_required
def exam_run_list_view(request):
    """Список назначенных тестов."""
    runs = ExamRun.objects.select_related("test", "test__subject", "school_class").order_by("-started_at")
    return render(request, "core/exam_run_list.html", {"runs": runs})


@login_required
def close_exam_run(request, run_id):
    """Закрыть назначение (status = finished)."""
    if request.method != "POST":
        return redirect("exam_run_list")
    run = get_object_or_404(ExamRun, id=run_id)
    run.status = "finished"
    run.save(update_fields=["status"])
    messages.success(request, f"Тест «{run.test.title}» для {run.school_class.display_name} закрыт.")
    return redirect("exam_run_list")


@login_required
def class_list_view(request):
    """Список классов с количеством учеников."""
    from django.db.models import Count
    classes = SchoolClass.objects.annotate(student_count=Count("students")).order_by("parallel", "letter")
    return render(request, "core/class_list.html", {"classes": classes})


@login_required
def exam_run_stats_view(request, run_id):
    """Статистика по конкретному назначению."""
    run = get_object_or_404(ExamRun, id=run_id)
    attempts = Attempt.objects.filter(exam_run=run, is_completed=True).select_related("student")
    avg = attempts.aggregate(Avg("percentage"))["percentage__avg"] or 0
    return render(request, "core/exam_run_stats.html", {
        "run": run,
        "attempts": attempts,
        "avg": round(avg, 1),
        "passed": attempts.count(),
    })


@login_required
def class_detail_view(request, class_id):
    """Детали класса — список учеников."""
    school_class = get_object_or_404(SchoolClass, id=class_id)
    students = Student.objects.filter(school_class=school_class).order_by("full_name")
    return render(request, "core/class_detail.html", {
        "school_class": school_class,
        "students": students,
    })


@login_required
def create_class_view(request):
    """Создание класса (для админа)."""
    if not request.user.is_admin():
        messages.error(request, "Только администратор может создавать классы.")
        return redirect("class_list")

    if request.method == "POST":
        parallel = request.POST.get("parallel")
        letter = request.POST.get("letter", "").strip()
        if parallel:
            SchoolClass.objects.get_or_create(parallel=int(parallel), letter=letter)
            messages.success(request, "Класс создан.")
            return redirect("class_list")
    return render(request, "core/create_class.html")


def get_teacher_subjects(user):
    """Предметы учителя. Админ видит все."""
    if user.is_admin():
        from ..models import Subject
        return Subject.objects.all()
    return [a.subject for a in user.assignments.all()]


def get_teacher_classes(user):
    """Классы. Админ видит все, учитель — все (пока нет привязки класс-учитель)."""
    return SchoolClass.objects.all()


@login_required
def instruction_view(request):
    """Короткая инструкция для учителя/админа."""
    return render(request, "core/instruction.html")


@login_required
def teacher_list_view(request):
    """Список учителей (только админ)."""
    if not request.user.is_admin():
        messages.error(request, "Доступ только для администратора.")
        return redirect("dashboard")
    teachers = User.objects.filter(role=User.Role.TEACHER).prefetch_related("assignments__subject")
    return render(request, "core/teacher_list.html", {"teachers": teachers})


@login_required
def create_teacher_view(request):
    """Создание учителя + привязка к предмету."""
    if not request.user.is_admin():
        return redirect("dashboard")
    from ..models import Subject, TeacherAssignment
    subjects = Subject.objects.all()

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        subject_id = request.POST.get("subject")
        if username and password:
            user = User.objects.create_user(username=username, password=password, role=User.Role.TEACHER)
            if subject_id:
                TeacherAssignment.objects.get_or_create(teacher=user, subject_id=subject_id)
            messages.success(request, f"Учитель {username} создан.")
            return redirect("teacher_list")
    return render(request, "core/create_teacher.html", {"subjects": subjects})
