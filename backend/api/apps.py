from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"

    def ready(self):
        # Запуск Kafka consumer при старте Django
        from backend.kafka import run_kafka_consumer
        run_kafka_consumer()