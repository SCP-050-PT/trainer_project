import random
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError


class User(AbstractUser):
    """
    Кастомная модель пользователя.
    Роли: admin (методист), teacher (учитель-предметник).
    Ученики НЕ являются пользователями системы (входят по PIN).
    """

    class Role(models.TextChoices):
        ADMIN = "admin", "Администратор (Методист)"
        TEACHER = "teacher", "Учитель-предметник"

    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.TEACHER, verbose_name="Роль"
    )

    def is_admin(self):
        return self.role == self.Role.ADMIN

    def is_teacher(self):
        return self.role == self.Role.TEACHER

    class Meta:
        db_table = "users"
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class Subject(models.Model):
    """Предмет"""

    name = models.CharField(
        max_length=100, unique=True, verbose_name="Название предмета"
    )
    code = models.SlugField(max_length=20, unique=True, verbose_name="Код (slug)")

    class Meta:
        db_table = "subjects"
        verbose_name = "Предмет"
        verbose_name_plural = "Предметы"
        ordering = ["name"]

    def __str__(self):
        return self.name


class SchoolClass(models.Model):
    """
    Класс школы. Хранится как параллель (число) + литера (строка).
    Отображается в формате: 4 «Д», 7 «А».
    """

    parallel = models.PositiveSmallIntegerField(
        verbose_name="Параллель", help_text="Например: 4, 7, 10"
    )
    letter = models.CharField(
        max_length=5,
        blank=True,
        default="",
        verbose_name="Литера",
        help_text="Например: Д, А, Е",
    )

    # Связь с предметами через назначение учителей (опционально для фильтрации)
    subjects = models.ManyToManyField(
        Subject, related_name="classes", blank=True, verbose_name="Предметы в классе"
    )

    class Meta:
        db_table = "school_classes"
        verbose_name = "Класс"
        verbose_name_plural = "Классы"
        unique_together = ("parallel", "letter")
        ordering = ["parallel", "letter"]

    @property
    def display_name(self):
        if self.letter:
            return f'{self.parallel} "{self.letter}"'
        return str(self.parallel)

    def __str__(self):
        return self.display_name


class TeacherAssignment(models.Model):
    """Привязка учителя к предмету."""

    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="assignments",
        limit_choices_to={"role": User.Role.TEACHER},
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="teacher_assignments"
    )

    class Meta:
        db_table = "teacher_assignments"
        unique_together = ("teacher", "subject")
        verbose_name = "Назначение учителя"
        verbose_name_plural = "Назначения учителей"

    def __str__(self):
        return f"{self.teacher.username} -> {self.subject.name}"


class Student(models.Model):
    """
    Ученик. Входит по PIN. ФИО одной строкой.
    """

    full_name = models.CharField(max_length=255, verbose_name="ФИО")
    school_class = models.ForeignKey(
        SchoolClass,
        on_delete=models.CASCADE,
        related_name="students",
        verbose_name="Класс",
    )
    pin_code = models.CharField(
        max_length=5, unique=True, editable=False, verbose_name="PIN-код"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "students"
        verbose_name = "Ученик"
        verbose_name_plural = "Ученики"
        ordering = ["full_name"]
        indexes = [
            models.Index(fields=["pin_code"]),
            models.Index(fields=["full_name"]),
        ]

    def save(self, *args, **kwargs):
        if not self.pin_code:
            self.pin_code = self.generate_unique_pin()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_unique_pin():
        existing_pins = set(Student.objects.values_list("pin_code", flat=True))
        while True:
            pin = str(random.randint(10000, 99999))
            if pin not in existing_pins:
                return pin

    def __str__(self):
        return f"{self.full_name} ({self.school_class.display_name}) - {self.pin_code}"


class Question(models.Model):
    """Вопрос банка заданий."""

    class Type(models.TextChoices):
        SINGLE_CHOICE = "single_choice", "Одиночный выбор"
        MULTIPLE_CHOICE = "multiple_choice", "Множественный выбор"
        TEXT_INPUT = "text_input", "Ввод текста"
        NUMBER_INPUT = "number_input", "Ввод числа"

    class Difficulty(models.IntegerChoices):
        EASY = 1, "Лёгкий"
        MEDIUM = 2, "Средний"
        HARD = 3, "Сложный"

    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="questions"
    )
    grade_level = models.PositiveSmallIntegerField(
        verbose_name="Параллель", help_text="Для какого уровня: 4, 7, 9, 11"
    )
    topic = models.CharField(max_length=200, blank=True, default="")
    question_type = models.CharField(max_length=30, choices=Type.choices)
    difficulty = models.IntegerField(
        choices=Difficulty.choices, default=Difficulty.MEDIUM
    )
    text = models.TextField(verbose_name="Текст вопроса")
    image = models.ImageField(upload_to="question_images/", blank=True, null=True)
    explanation = models.TextField(blank=True, default="", verbose_name="Пояснение")
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_questions"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "questions"
        ordering = ["-created_at"]
        verbose_name = "Вопрос"
        verbose_name_plural = "Вопросы"

    def __str__(self):
        return f"[{self.get_difficulty_display()}] {self.text[:50]}..."


class AnswerOption(models.Model):
    """Вариант ответа для single/multiple choice."""

    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="options"
    )
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "answer_options"
        ordering = ["order", "id"]
        verbose_name = "Вариант ответа"
        verbose_name_plural = "Варианты ответов"

    def __str__(self):
        mark = "✓" if self.is_correct else "✗"
        return f"{mark} {self.text[:30]}"


class CorrectAnswer(models.Model):
    """Правильный ответ для text/number input."""

    question = models.OneToOneField(
        Question, on_delete=models.CASCADE, related_name="correct_answer"
    )
    value = models.CharField(max_length=500)
    alternative_values = models.JSONField(
        default=list, blank=True, help_text="Список синонимов"
    )

    class Meta:
        db_table = "correct_answers"
        verbose_name = "Правильный ответ"
        verbose_name_plural = "Правильные ответы"

    # БЫЛО: def check(self, user_answer: str) -> bool:
    # СТАЛО:
    def verify_answer(self, user_answer: str) -> bool:
        """Проверяет ответ ученика (без учёта регистра и пробелов)."""
        normalized = user_answer.strip().lower()
        correct_normalized = self.value.strip().lower()
        alts = [v.strip().lower() for v in self.alternative_values or []]
        return normalized == correct_normalized or normalized in alts

    def __str__(self):
        return f"Ответ: {self.value}"


class Test(models.Model):
    """Набор вопросов (шаблон теста)."""

    title = models.CharField(max_length=255)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="tests")
    grade_level = models.PositiveSmallIntegerField(help_text="Целевой параллель")
    questions = models.ManyToManyField(Question, related_name="tests", blank=True)
    time_limit_minutes = models.PositiveIntegerField(
        default=0, help_text="0 = без ограничения"
    )
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "tests"
        verbose_name = "Тест"
        verbose_name_plural = "Тесты"

    def __str__(self):
        return f"{self.title} ({self.subject.name}, {self.grade_level} кл.)"


class ExamRun(models.Model):
    """
    Назначение теста конкретному классу (гибридная модель из ТЗ).
    Учитель создает ExamRun -> Ученики проходят.
    """

    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name="exam_runs")
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE, related_name="exam_runs"
    )
    deadline = models.DateTimeField(
        null=True, blank=True, help_text="Дата окончания приема работ"
    )
    started_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        default="active",
        choices=[("active", "Активен"), ("finished", "Завершен")],
    )

    class Meta:
        db_table = "exam_runs"
        verbose_name = "Назначение экзамена"
        verbose_name_plural = "Назначения экзаменов"

    def __str__(self):
        return f"{self.test.title} -> {self.school_class.display_name}"


class Attempt(models.Model):
    """Попытка прохождения теста учеником."""

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="attempts"
    )
    exam_run = models.ForeignKey(
        ExamRun, on_delete=models.CASCADE, related_name="attempts"
    )
    score = models.FloatField(default=0, verbose_name="Балл")
    max_score = models.FloatField(default=0, verbose_name="Макс. балл")
    percentage = models.FloatField(default=0, verbose_name="% выполнения")
    stars = models.IntegerField(
        default=0, help_text="Количество звезд (если используется шкала)"
    )
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)

    class Meta:
        db_table = "attempts"
        ordering = ["-started_at"]

    def __str__(self):
        return (
            f"{self.student.full_name} - {self.exam_run.test.title}: {self.percentage}%"
        )


class AnswerAttempt(models.Model):
    """Логирование ответа на каждый вопрос (для статистики ошибок)."""

    attempt = models.ForeignKey(
        Attempt, on_delete=models.CASCADE, related_name="answers"
    )
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_option = models.ForeignKey(
        AnswerOption, on_delete=models.SET_NULL, null=True, blank=True
    )
    given_value = models.CharField(
        max_length=500, blank=True, null=True, help_text="Для текстовых/числовых"
    )
    is_correct = models.BooleanField(default=False)
    answered_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "answer_attempts"
        unique_together = ("attempt", "question")
