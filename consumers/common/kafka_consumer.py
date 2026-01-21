from confluent_kafka import Consumer, KafkaError
import json

class BaseKafkaConsumer:
    def __init__(self, config: dict, topic: str):
        self.topic = topic
        self.consumer = Consumer(config)

    def start(self):
        self.consumer.subscribe([self.topic])
        print(f"[Kafka] Subscribed to topic: {self.topic}")

    def poll(self, timeout: float = 1.0):
        msg = self.consumer.poll(timeout)

        if msg is None:
            return None

        if msg.error():
            if msg.error().code() != KafkaError._PARTITION_EOF:
                print(f"[Kafka Error] {msg.error()}")
            return None

        try:
            return json.loads(msg.value().decode("utf-8"))
        except json.JSONDecodeError:
            print("[Kafka Warning] Invalid JSON")
            return None

    def close(self):
        self.consumer.close()
        print("[Kafka] Consumer closed")
