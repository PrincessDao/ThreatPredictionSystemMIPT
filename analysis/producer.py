import json
import time
import pandas as pd
from kafka import KafkaProducer


TOPIC = "incidents_topic"
KAFKA_SERVER = "kafka:9092"
DATA_PATH = "incidents_2000.xlsx"


producer = KafkaProducer(
    bootstrap_servers=KAFKA_SERVER,
    value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
    acks="all",
    retries=3
)


def load_data(path: str) -> pd.DataFrame:
    df = pd.read_excel(path)
    df.columns = [c.strip() for c in df.columns]
    return df


def build_event(row: pd.Series) -> dict:
    return {
        "event_type": "incident",
        "payload": row.to_dict()
    }


def main():
    df = load_data(DATA_PATH)

    if df.empty:
        print("Нет данных для отправки")
        return

    print(f"Loaded {len(df)} rows. Starting stream...")

    while True:
        row = df.sample(1).iloc[0]
        event = build_event(row)

        try:
            producer.send(TOPIC, value=event)
            producer.flush()
            print("Sent event")
        except Exception as e:
            print("Kafka error:", e)

        time.sleep(2)


if __name__ == "__main__":
    main()