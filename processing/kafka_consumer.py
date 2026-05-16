import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kafka import KafkaConsumer
from config.settings import KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC_RAW, DATA_PROCESSED_PATH
from config.logging_config import setup_logger

logger = setup_logger("kafka_consumer")


def consume_papers(max_messages: int = 500, timeout_ms: int = 10000) -> list[dict]:
    print(f"Demarrage consommation depuis '{KAFKA_TOPIC_RAW}'...")

    consumer = KafkaConsumer(
        KAFKA_TOPIC_RAW,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id="scientific-graph-consumer",
        consumer_timeout_ms=timeout_ms
    )

    papers = []

    for message in consumer:
        papers.append(message.value)
        if len(papers) % 100 == 0:
            print(f"  {len(papers)} messages consommes...")
        if len(papers) >= max_messages:
            break

    consumer.close()

    print(f"Consommation terminee — {len(papers)} papers recus")
    logger.info(f"Consumer termine — {len(papers)} messages recus")
    return papers


if __name__ == "__main__":
    print("Demarrage Kafka Consumer...")
    papers = consume_papers()
    print(f"Total recu : {len(papers)} papers")