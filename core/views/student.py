from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .common import student_required
from ..models import Student, SchoolClass, ExamRun, Attempt, AnswerAttempt, Question, AnswerOption

@student_required
def student_dashboard(request):
    """Кабинет ученика: список доступных тестов."""
    student_id = request.session.get("student_id")
    student = get_object_or_404(Student, id=student_id)

    available_exams = ExamRun.objects.filter(
        school_class=student.school_class, status="active"
    ).select_related("test", "test__subject")

    passed_exam_ids = Attempt.objects.filter(student=student).values_list(
        "exam_run_id", flat=True
    )
    available_exams = available_exams.exclude(id__in=passed_exam_ids)

    from ..models import Test
    practice_tests = Test.objects.filter(is_active=True, grade_level=student.school_class.parallel)[:10]

    return render(
        request,
        "core/student/dashboard.html",
        {"student": student, "exams": available_exams, "practice_tests": practice_tests},
    )


def student_login_view(request):
    """Страница входа ученика: Выбор класса + PIN."""
    if "student_id" in request.session:
        return redirect("student_dashboard")

    classes = SchoolClass.objects.all().order_by("parallel", "letter")
    error = None

    if request.method == "POST":
        class_id = request.POST.get("school_class")
        pin = request.POST.get("pin_code")

        try:
            student = Student.objects.get(school_class_id=class_id, pin_code=pin)
            request.session["student_id"] = student.id
            request.session["student_name"] = student.full_name
            return redirect("student_dashboard")
        except Student.DoesNotExist:
            error = "Неверный класс или PIN-код."

    return render(
        request, "core/student/login.html", {"classes": classes, "error": error}
    )


def student_logout(request):
    """Выход ученика."""
    request.session.pop("student_id", None)
    request.session.pop("student_name", None)
    return redirect("home")


@student_required
def take_test(request, exam_run_id):
    """Прохождение теста."""
    student_id = request.session.get("student_id")
    student = get_object_or_404(Student, id=student_id)

    exam_run = get_object_or_404(
        ExamRun, id=exam_run_id, school_class=student.school_class
    )

    attempt, created = Attempt.objects.get_or_create(
        student=student, exam_run=exam_run, defaults={"is_completed": False}
    )

    if attempt.is_completed:
        return redirect("student_result", attempt_id=attempt.id)

    questions = exam_run.test.questions.all()

    if request.method == "POST":
        correct_count = 0
        max_points = questions.count()

        for q in questions:
            is_correct = False
            option_obj = None
            given_value = None

            if q.question_type == "single_choice":
                ans_key = f"answer_{q.id}"
                user_val = request.POST.get(ans_key)
                try:
                    opt_id = int(user_val)
                    option_obj = AnswerOption.objects.get(id=opt_id, question=q)
                    is_correct = option_obj.is_correct
                except (ValueError, TypeError, AnswerOption.DoesNotExist):
                    pass
            elif q.question_type == "multiple_choice":
                selected = request.POST.getlist(f"answer_{q.id}")
                correct_opts = set(q.options.filter(is_correct=True).values_list("id", flat=True))
                selected_ids = set()
                for s in selected:
                    try:
                        selected_ids.add(int(s))
                    except ValueError:
                        pass
                is_correct = selected_ids == correct_opts and len(selected_ids) > 0
                given_value = ",".join(selected)
            else:
                # text / number
                given_value = request.POST.get(f"answer_{q.id}", "").strip()
                ca = getattr(q, "correct_answer", None)
                if ca and hasattr(ca, "verify_answer"):
                    is_correct = ca.verify_answer(given_value)
                elif ca and given_value.lower() == ca.value.lower():
                    is_correct = True

            AnswerAttempt.objects.update_or_create(
                attempt=attempt,
                question=q,
                defaults={
                    "selected_option": option_obj,
                    "given_value": given_value,
                    "is_correct": is_correct,
                },
            )
            if is_correct:
                correct_count += 1

        attempt.score = correct_count
        attempt.max_score = max_points
        attempt.percentage = (correct_count / max_points * 100) if max_points else 0
        attempt.is_completed = True
        attempt.save()

        return redirect("student_result", attempt_id=attempt.id)

    return render(
        request,
        "core/student/test.html",
        {"exam_run": exam_run, "questions": questions, "attempt": attempt},
    )


@student_required
def student_result(request, attempt_id):
    """Результат теста."""
    student_id = request.session.get("student_id")
    attempt = get_object_or_404(Attempt, id=attempt_id, student_id=student_id)
    answers = attempt.answers.select_related("question", "selected_option").all()

    return render(request, "core/student/result.html", {
        "attempt": attempt,
        "answers": answers,
    })


def practice_test(request, test_id):
    """Режим тренировки — без сохранения результата."""
    from ..models import Test
    test = get_object_or_404(Test, id=test_id, is_active=True)
    questions = test.questions.all()

    result = None
    if request.method == "POST":
        correct = 0
        total = questions.count()
        details = []
        for q in questions:
            is_correct = False
            if q.question_type == "single_choice":
                val = request.POST.get(f"answer_{q.id}")
                try:
                    opt = AnswerOption.objects.get(id=int(val), question=q)
                    is_correct = opt.is_correct
                except:
                    pass
            elif q.question_type == "multiple_choice":
                selected = set(int(x) for x in request.POST.getlist(f"answer_{q.id}") if x.isdigit())
                correct_ids = set(q.options.filter(is_correct=True).values_list("id", flat=True))
                is_correct = selected == correct_ids and selected
            else:
                val = request.POST.get(f"answer_{q.id}", "").strip()
                from ..models import CorrectAnswer
                ca = CorrectAnswer.objects.filter(question=q).first()
                is_correct = bool(ca and val.lower() == ca.value.lower())
            if is_correct:
                correct += 1
            details.append((q, is_correct))
        result = {"correct": correct, "total": total, "pct": round(correct/total*100) if total else 0, "details": details}

    return render(request, "core/student/practice.html", {"test": test, "questions": questions, "result": result})
