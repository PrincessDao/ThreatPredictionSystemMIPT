import json
from kafka import KafkaConsumer

from api.models import Incident


def start_consumer():
    consumer = KafkaConsumer(
        "incidents_topic",
        bootstrap_servers="kafka:9092",
        value_deserializer=lambda x: json.loads(x.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id="incidents-group"
    )

    print("Kafka consumer started...")

    for message in consumer:
        try:
            event = message.value

            Incident.objects.create(
                payload=event.get("payload", {})
            )

            print("Saved incident")
        except Exception as e:
            print("Consumer error:", e)