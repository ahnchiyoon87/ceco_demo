"""Kafka intake: commit only after durable ingestion or explicit quarantine."""
from __future__ import annotations

import json
import logging
import os

from confluent_kafka import Consumer, KafkaException
from pydantic import ValidationError

from .api import Alarm, connection, initialize, ingest

log = logging.getLogger(__name__)


def initialize_inbox():
    initialize()
    with connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS manufacturing_inbox (
                topic text NOT NULL, partition_id integer NOT NULL, offset_id bigint NOT NULL,
                status text NOT NULL CHECK (status IN ('accepted', 'rejected')),
                incident_id uuid REFERENCES manufacturing_incidents(id),
                raw_payload bytea NOT NULL, error text,
                created_at timestamptz NOT NULL DEFAULT now(),
                PRIMARY KEY(topic, partition_id, offset_id)
            )
        """)


def persist_message(topic: str, partition: int, offset: int, raw: bytes):
    incident_id, error = None, None
    try:
        alarm = Alarm.model_validate_json(raw)
    except ValidationError as exc:
        # Retain raw bytes and validation details for correction/replay; no silent drop.
        error = json.dumps(exc.errors(include_input=False, include_url=False), ensure_ascii=False)
    else:
        incident_id = ingest(alarm)["incident"]["id"]
    with connection() as conn:
        conn.execute("""
            INSERT INTO manufacturing_inbox(topic, partition_id, offset_id, status,
                                           incident_id, raw_payload, error)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (topic, partition_id, offset_id) DO NOTHING
        """, (topic, partition, offset, "rejected" if error else "accepted", incident_id, raw, error))
    return "rejected" if error else "accepted"


def main():
    logging.basicConfig(level=logging.INFO)
    initialize_inbox()
    consumer = Consumer({
        "bootstrap.servers": os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
        "group.id": "ar100-ai-incidents-v1",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
        "enable.auto.offset.store": False,
    })
    consumer.subscribe(["sensor.alerts"])
    try:
        while True:
            message = consumer.poll(1.0)
            if message is None:
                continue
            if message.error():
                raise KafkaException(message.error())
            result = persist_message(message.topic(), message.partition(), message.offset(), message.value() or b"")
            consumer.commit(message=message, asynchronous=False)
            log.info("%s %s/%s/%s", result, message.topic(), message.partition(), message.offset())
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
