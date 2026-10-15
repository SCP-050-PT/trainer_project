from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User,
    Subject,
    SchoolClass,
    TeacherAssignment,
    Student,
    Question,
    AnswerOption,
    CorrectAnswer,
    Test,
    ExamRun,
    Attempt,
    AnswerAttempt,
)


@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "role", "is_staff")
    fieldsets = BaseUserAdmin.fieldsets + (("Дополнительно", {"fields": ("role",)}),)
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Дополнительно", {"fields": ("role",)}),
    )


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    prepopulated_fields = {"code": ("name",)}


@admin.register(SchoolClass)
class SchoolClassAdmin(admin.ModelAdmin):
    list_display = ("display_name", "parallel", "letter")
    search_fields = ("parallel", "letter")


@admin.register(TeacherAssignment)
class TeacherAssignmentAdmin(admin.ModelAdmin):
    list_display = ("teacher", "subject")
    raw_id_fields = ("teacher", "subject")


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("full_name", "school_class", "pin_code", "created_at")
    readonly_fields = ("pin_code",)  # PIN генерируется автоматически
    search_fields = ("full_name", "pin_code")
    list_filter = ("school_class",)
    actions = ["export_students_csv"]

    def export_students_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="students.csv"'
        writer = csv.writer(response)
        writer.writerow(["ФИО", "Класс", "PIN"])
        for s in queryset:
            writer.writerow([s.full_name, s.school_class.display_name, s.pin_code])
        return response

    export_students_csv.short_description = "Экспорт выбранных учеников в CSV"


class AnswerOptionInline(admin.TabularInline):
    model = AnswerOption
    extra = 1


class CorrectAnswerInline(admin.StackedInline):
    model = CorrectAnswer
    extra = 0


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
        "short_text",
        "subject",
        "grade_level",
        "difficulty",
        "question_type",
    )
    list_filter = ("subject", "grade_level", "difficulty", "question_type")
    inlines = [AnswerOptionInline, CorrectAnswerInline]

    def short_text(self, obj):
        return f"{obj.text[:50]}..." if len(obj.text) > 50 else obj.text

    short_text.short_description = "Текст"


@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "subject",
        "grade_level",
        "time_limit_minutes",
        "is_active",
    )
    filter_horizontal = ("questions",)


@admin.register(ExamRun)
class ExamRunAdmin(admin.ModelAdmin):
    list_display = ("test", "school_class", "status", "deadline", "started_at")
    list_filter = ("status", "school_class__parallel")


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "exam_run",
        "percentage",
        "stars",
        "started_at",
        "is_completed",
    )
    readonly_fields = ("score", "max_score", "percentage", "stars")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_admin():
            return qs
        # Учителя видят только свои классы (реализация RBAC на уровне запроса)
        return qs.filter(exam_run__school_class__in=request.user.assignments.all())


@admin.register(AnswerAttempt)
class AnswerAttemptAdmin(admin.ModelAdmin):
    list_display = ("attempt", "question", "is_correct", "answered_at")
    raw_id_fields = ("attempt", "question")
