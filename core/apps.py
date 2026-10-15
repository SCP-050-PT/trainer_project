from django.apps import AppConfig


from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Тренажёр"  # <--- Вот сюда попадет название группы в админке
