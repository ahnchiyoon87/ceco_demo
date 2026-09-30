"""Kafka alert → AI 사건 접수(commit 은 저장·격리 뒤에만). 소비 루프는 업무 서비스(business.py)가 돈다."""
from __future__ import annotations

import json

from pydantic import ValidationError

from .api import Alarm, connection, initialize, ingest



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
