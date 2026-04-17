from threading import Thread
from .consumers import start_consumer


def run_kafka_consumer():
    thread = Thread(target=start_consumer, daemon=True)
    thread.start()
    return thread