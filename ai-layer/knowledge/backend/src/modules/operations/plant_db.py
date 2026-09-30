"""공용 업무 DB(PostgreSQL DATABASE plant: registry·workflow·alert·audit) 연결.

AI 층 자체 표(사건·대응안)는 DATABASE ai(DB_* 환경변수)에 있고, 작업 요청·감사의 정본은 여기다(HANDOFF §2-3 업무 서비스).
계정은 서비스마다 다르다(PLANT_DB_USER: 업무 서비스 = ops, AI 업무 도우미 = ai_app).
"""
from __future__ import annotations

import json
import os

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


def plant_dsn() -> str:
    return (f"host={os.environ.get('PLANT_DB_HOST', os.environ.get('DB_HOST', 'postgres'))} "
            f"port={os.environ.get('PLANT_DB_PORT', '5432')} dbname={os.environ.get('PLANT_DB_NAME', 'plant')} "
            f"user={os.environ['PLANT_DB_USER']} password={os.environ['PLANT_DB_PASSWORD']} connect_timeout=5")


def plant_connection(autocommit: bool = False):
    return psycopg.connect(plant_dsn(), row_factory=dict_row, autocommit=autocommit)


def audit(conn, actor_type: str, actor_id: str, action: str, job_order_id: str | None, subject: str | None, detail: dict) -> None:
    """추가 전용 감사 기록(주체 = 사람·시스템·AI, AI 는 별도 ID)."""
    conn.execute("""INSERT INTO audit.log(actor_type, actor_id, action, job_order_id, subject, detail)
                    VALUES (%s,%s,%s,%s,%s,%s)""",
                 (actor_type, actor_id, action, job_order_id, subject, Jsonb(json.loads(json.dumps(detail, default=str)))))


def request_event(conn, job_order_id: str, kind: str, status: str | None, reason: str | None, detail: dict, source: str):
    return conn.execute("""INSERT INTO workflow.request_event(job_order_id, kind, status, reason, detail, source)
                           VALUES (%s,%s,%s,%s,%s,%s) RETURNING id, at""",
                        (job_order_id, kind, status, reason, Jsonb(json.loads(json.dumps(detail, default=str))), source)).fetchone()
