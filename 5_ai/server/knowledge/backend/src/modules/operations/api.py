"""Durable incident intake. No equipment action is authorized by this API."""
from __future__ import annotations

import hashlib
import json
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field
from fastapi import APIRouter, HTTPException, Query

from ..process_runtime.checkpointer import checkpoint_postgres_uri

router = APIRouter(prefix="/api/operations", tags=["manufacturing"])


class Alarm(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    ts: int = Field(gt=0, description="Original SCADA timestamp in nanoseconds")
    site: str = Field(min_length=1, max_length=100)
    device: str = Field(min_length=1, max_length=100)
    tag: str = Field(min_length=1, max_length=100)
    value: float
    alert_type: str = Field(min_length=1, max_length=100)
    severity: str = Field(min_length=1, max_length=50)
    detector: str = Field(min_length=1, max_length=100)
    detail: str = Field(max_length=10000)


def connection():
    uri = checkpoint_postgres_uri()
    if not uri:
        raise HTTPException(503, "업무 DB가 구성되지 않았습니다.")
    try:
        return psycopg.connect(uri, row_factory=dict_row, connect_timeout=5)
    except psycopg.Error as exc:
        raise HTTPException(503, "업무 DB에 연결할 수 없습니다. 사건을 저장하지 못했습니다.") from exc


def initialize():
    with connection() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(72401931)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS manufacturing_incidents (
                id uuid PRIMARY KEY,
                alarm_key text NOT NULL UNIQUE,
                site text NOT NULL,
                device text NOT NULL,
                status text NOT NULL DEFAULT 'received',
                revision integer NOT NULL DEFAULT 1,
                alarm jsonb NOT NULL,
                created_at timestamptz NOT NULL DEFAULT now()
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS manufacturing_events (
                id bigserial PRIMARY KEY,
                incident_id uuid NOT NULL REFERENCES manufacturing_incidents(id),
                kind text NOT NULL,
                payload jsonb NOT NULL,
                created_at timestamptz NOT NULL DEFAULT now()
            )
        """)
        conn.execute("ALTER TABLE manufacturing_incidents ADD COLUMN IF NOT EXISTS correlation_key text")
        conn.execute("CREATE INDEX IF NOT EXISTS manufacturing_events_incident_id_idx ON manufacturing_events(incident_id,id DESC)")
        conn.execute("ALTER TABLE manufacturing_incidents ADD COLUMN IF NOT EXISTS first_ts bigint")
        conn.execute("ALTER TABLE manufacturing_incidents ADD COLUMN IF NOT EXISTS last_ts bigint")
        conn.execute("ALTER TABLE manufacturing_incidents ADD COLUMN IF NOT EXISTS alarm_count integer NOT NULL DEFAULT 1")
        conn.execute("ALTER TABLE manufacturing_incidents ADD COLUMN IF NOT EXISTS review_revision integer")
        # Existing pending proposals retain the old conservative version boundary.
        conn.execute("UPDATE manufacturing_incidents SET review_revision=revision WHERE review_revision IS NULL")
        conn.execute("ALTER TABLE manufacturing_incidents ALTER COLUMN review_revision SET DEFAULT 1")
        conn.execute("ALTER TABLE manufacturing_incidents ALTER COLUMN review_revision SET NOT NULL")
        conn.execute("""CREATE TABLE IF NOT EXISTS manufacturing_alarm_links (
            alarm_key text PRIMARY KEY, incident_id uuid NOT NULL REFERENCES manufacturing_incidents(id)
        )""")
        conn.execute("""INSERT INTO manufacturing_alarm_links SELECT alarm_key, id FROM manufacturing_incidents
                        ON CONFLICT DO NOTHING""")


def correlation_key(alarm: Alarm) -> str:
    # Explicit educational AR-100 mapping, not a general diagnosis rule.
    # Unknown multivariate alarms are intentionally NOT assigned to the mixer.
    group = f"{alarm.tag}:{alarm.alert_type}"
    if (alarm.site == "AR-100" and alarm.device == "reactor-line-01"
            and alarm.tag in {"IT-102", "VT-101"}
            and alarm.alert_type in {"CEP_BEARING", "THRESHOLD_USL", "ZSCORE"}):
        group = "mixer-current-vibration-v1"
    return json.dumps([alarm.site, alarm.device, group], separators=(",", ":"))


@router.post("/incidents")
def ingest(alarm: Alarm):
    payload = alarm.model_dump()
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    key = hashlib.sha256(canonical.encode()).hexdigest()
    group = correlation_key(alarm)
    gap_ns = 30_000_000_000  # Educational quiet-gap policy; not equipment safety threshold.
    with connection() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (group,))
        row = conn.execute("""SELECT i.* FROM manufacturing_alarm_links l
            JOIN manufacturing_incidents i ON i.id=l.incident_id WHERE l.alarm_key=%s""", (key,)).fetchone()
        if row:
            return {"incident": row, "duplicate": True, "correlated": False}
        row = conn.execute("""SELECT * FROM manufacturing_incidents
            WHERE correlation_key=%s AND status NOT IN ('closed','rejected')
            AND first_ts <= %s AND last_ts >= %s
            ORDER BY last_ts DESC LIMIT 1 FOR UPDATE""", (group, alarm.ts+gap_ns, alarm.ts-gap_ns)).fetchone()
        correlated = row is not None
        if correlated:
            known_signature = conn.execute("""SELECT 1 FROM manufacturing_events
                WHERE incident_id=%s AND kind IN ('alarm_received','alarm_correlated')
                AND payload->>'tag'=%s AND payload->>'alert_type'=%s
                AND payload->>'detector'=%s AND payload->>'severity'=%s LIMIT 1""",
                (row["id"], alarm.tag, alarm.alert_type, alarm.detector, alarm.severity)).fetchone()
            review_change = not known_signature or alarm.ts < row["first_ts"]
            row = conn.execute("""UPDATE manufacturing_incidents
                SET first_ts=LEAST(first_ts,%s), last_ts=GREATEST(last_ts,%s),
                    alarm_count=alarm_count+1, revision=revision+1,
                    review_revision=review_revision+%s
                WHERE id=%s RETURNING *""", (alarm.ts, alarm.ts, int(review_change), row["id"])).fetchone()
        else:
            row = conn.execute("""
                INSERT INTO manufacturing_incidents(id, alarm_key, site, device, alarm, correlation_key, first_ts, last_ts)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *
            """, (uuid4(), key, alarm.site, alarm.device, Jsonb(payload), group, alarm.ts, alarm.ts)).fetchone()
        row = conn.execute("""
            INSERT INTO manufacturing_alarm_links(alarm_key, incident_id) VALUES (%s,%s)
            RETURNING incident_id
        """, (key, row["id"])).fetchone()
        conn.execute("INSERT INTO manufacturing_events(incident_id, kind, payload) VALUES (%s, %s, %s)",
                     (row["incident_id"], "alarm_correlated" if correlated else "alarm_received", Jsonb(payload)))
        incident = conn.execute("SELECT * FROM manufacturing_incidents WHERE id=%s", (row["incident_id"],)).fetchone()
        return {"incident": incident, "duplicate": False, "correlated": correlated}


@router.get("/incidents")
def list_incidents():
    with connection() as conn:
        rows = conn.execute("SELECT * FROM manufacturing_incidents ORDER BY created_at DESC LIMIT 100").fetchall()
    return {"items": rows, "limit": 100}


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: str):
    from uuid import UUID
    try:
        uid = UUID(incident_id)
    except ValueError as exc:
        raise HTTPException(422, "올바른 사건 ID가 아닙니다.") from exc
    with connection() as conn:
        row = conn.execute("SELECT * FROM manufacturing_incidents WHERE id=%s", (uid,)).fetchone()
        if not row:
            raise HTTPException(404, "사건을 찾을 수 없습니다.")
        events = conn.execute("SELECT * FROM manufacturing_events WHERE incident_id=%s ORDER BY id", (uid,)).fetchall()
    return {"incident": row, "events": events}


@router.get("/incidents/{incident_id}/events")
def list_events(incident_id: UUID, before_id: int | None = Query(None, gt=0),
                limit: int = Query(30, ge=1, le=100)):
    """Stable cursor pagination: new events cannot shift older pages."""
    with connection() as conn:
        if not conn.execute("SELECT 1 FROM manufacturing_incidents WHERE id=%s", (incident_id,)).fetchone():
            raise HTTPException(404, "사건을 찾을 수 없습니다.")
        rows = conn.execute("""SELECT * FROM manufacturing_events WHERE incident_id=%s
            AND (%s::bigint IS NULL OR id < %s) ORDER BY id DESC LIMIT %s""",
            (incident_id, before_id, before_id, limit+1)).fetchall()
    items = rows[:limit]
    return {"items": items, "has_more": len(rows)>limit,
            "next_before_id": items[-1]["id"] if len(rows)>limit else None}
