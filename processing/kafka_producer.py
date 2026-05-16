import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kafka import KafkaProducer
from config.settings import KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC_RAW, DATA_PROCESSED_PATH
from config.logging_config import setup_logger

logger = setup_logger("kafka_producer")


def create_producer() -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8") if k else None,
        acks="all",
        retries=3
    )


def send_papers(input_file: str = None) -> int:
    if input_file is None:
        input_file = os.path.join(DATA_PROCESSED_PATH, "cleaned_papers.json")

    print(f"Chargement : {input_file}")
    with open(input_file, "r", encoding="utf-8") as f:
        papers = json.load(f)

    print(f"{len(papers)} papers a envoyer vers Kafka topic '{KAFKA_TOPIC_RAW}'...")

    producer = create_producer()
    sent = 0

    for paper in papers:
        arxiv_id = paper.get("arxiv_id", "")
        try:
            producer.send(
                topic=KAFKA_TOPIC_RAW,
                key=arxiv_id,
                value=paper
            )
            sent += 1
            if sent % 100 == 0:
                print(f"  {sent}/{len(papers)} envoyes...")
        except Exception as e:
            logger.error(f"Erreur envoi {arxiv_id} : {e}")

    producer.flush()
    producer.close()

    print(f"Termine — {sent} papers envoyes vers Kafka.")
    logger.info(f"Producer termine — {sent} messages envoyes")
    return sent


if __name__ == "__main__":
    print("Demarrage Kafka Producer...")
    send_papers()