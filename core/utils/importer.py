import openpyxl
import csv
from io import StringIO
from ..models import Student, SchoolClass
import random


def parse_student_file(file_obj, school_class: SchoolClass):
    """
    Парсит Excel (.xlsx) или CSV.
    Ожидает колонки: ФИО (или Имя Фамилия Отчество).
    Возвращает список словарей [{'full_name': ...}]
    """
    students_data = []
    filename = file_obj.name.lower()

    try:
        if filename.endswith(".csv"):
            content = file_obj.read().decode("utf-8-sig")  # Поддержка BOM Windows Excel
            reader = csv.reader(StringIO(content))
            headers = next(reader)

            # Ищем индекс колонки с ФИО
            fio_idx = None
            for i, h in enumerate(headers):
                if any(kw in str(h).lower() for kw in ["фио", "имя", "name", "ученик"]):
                    fio_idx = i
                    break

            if fio_idx is None:
                raise ValueError(
                    "Не найдена колонка с ФИО. Проверьте заголовки таблицы."
                )

            for row in reader:
                if len(row) > fio_idx and row[fio_idx].strip():
                    students_data.append({"full_name": row[fio_idx].strip()})

        elif filename.endswith(".xlsx") or filename.endswith(".xls"):
            wb = openpyxl.load_workbook(file_obj, read_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                return []

            headers = rows[0]
            fio_idx = None
            for i, h in enumerate(headers):
                if h and any(
                    kw in str(h).lower() for kw in ["фио", "имя", "name", "ученик"]
                ):
                    fio_idx = i
                    break

            if fio_idx is None:
                raise ValueError("Не найдена колонка с ФИО в Excel")

            for row in rows[1:]:
                val = row[fio_idx]
                if val and str(val).strip():
                    students_data.append({"full_name": str(val).strip()})
        else:
            raise ValueError("Поддерживаются только файлы .csv и .xlsx")

    except Exception as e:
        raise ValueError(f"Ошибка чтения файла: {str(e)}")

    return students_data


def create_students_from_import(students_data, school_class: SchoolClass):
    """
    Создает объекты Student в БД.
    Генерирует уникальные PIN коды.
    """
    created_count = 0
    skipped_count = 0

    # Получаем все существующие PINы сразу, чтобы не делать запрос в цикле на каждую проверку
    existing_pins = set(Student.objects.values_list("pin_code", flat=True))

    for item in students_data:
        full_name = item["full_name"]

        # Проверка дубликата ФИО в этом классе (опционально, можно убрать если нужны тезки)
        exists = Student.objects.filter(
            school_class=school_class, full_name=full_name
        ).exists()
        if exists:
            skipped_count += 1
            continue

        # Генерация уникального PIN
        while True:
            pin = str(random.randint(10000, 99999))
            if pin not in existing_pins:
                break

        existing_pins.add(pin)  # Добавляем новый PIN в множество памяти

        Student.objects.create(
            full_name=full_name, school_class=school_class, pin_code=pin
        )
        created_count += 1

    return created_count, skipped_count
