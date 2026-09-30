"""IT 발송기(HANDOFF §2-3) — 승인된 작업 요청을 DMZ 게이트웨이에 HTTP POST 로 넣고 응답 ⓐ 를 기록한다.

정본은 PostgreSQL workflow·audit(추가 전용). 보낼 요청 = 마지막 사건이 approved 인 요청.
보내기 전에 'dispatched' 사건을 먼저 남긴다(발송한 요청은 다시 보내지 않는다 — 발송 직후 멈추면 결과는 업무 서비스가
ACK 시간 초과로 '결과 모름'으로 표시한다). 게이트웨이의 동기 응답이 첫 겹 ⓐ(경계 수용/거부 + 이유)다.
요청·ⓐ 사건은 Kafka request.events 에, 감사는 audit.copy 에 사본으로 낸다.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request

import psycopg
from confluent_kafka import Producer
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s dispatcher | %(message)s")
log = logging.getLogger("dispatcher")
GATEWAY = os.environ.get("GATEWAY_URL", "http://dmz-gateway:8088/requests")
TOKEN = os.environ["GATEWAY_CLIENT_TOKEN"]
DSN = (f"host={os.environ.get('PG_HOST', 'postgres')} dbname=plant user=dispatcher "
       f"password={os.environ['PG_DISPATCHER_PASSWORD']} connect_timeout=5")
producer = Producer({"bootstrap.servers": os.environ.get("KAFKA_BOOTSTRAP", "kafka:9092"), "linger.ms": 5})


def copy(topic: str, key: str, value: dict) -> None:
    producer.produce(topic, key=key, value=json.dumps(value, ensure_ascii=False, default=str))
    producer.poll(0)


def event(conn, jid: str, kind: str, status: str | None, reason: str | None, detail: dict) -> None:
    row = conn.execute("""INSERT INTO workflow.request_event(job_order_id, kind, status, reason, detail, source)
                          VALUES (%s,%s,%s,%s,%s,'dispatcher') RETURNING id, at""",
                       (jid, kind, status, reason, Jsonb(detail))).fetchone()
    conn.execute("""INSERT INTO audit.log(actor_type, actor_id, action, job_order_id, subject, detail)
                    VALUES ('system','it-dispatcher',%s,%s,%s,%s)""", (kind, jid, status, Jsonb({"reason": reason, **detail})))
    copy("request.events", jid, {"job_order_id": jid, "kind": kind, "status": status, "reason": reason, "at": row["at"], **detail})
    copy("audit.copy", jid, {"actor_type": "system", "actor_id": "it-dispatcher", "action": kind, "job_order_id": jid,
                             "status": status, "reason": reason, "at": row["at"]})


def post(req: dict) -> tuple[int, dict]:
    body = {"job_order_id": req["job_order_id"], "work_master_id": req["work_master_id"],
            "equipment_id": req["equipment_id"], "job_order_parameters": req["job_order_parameters"],
            "requester": req["requester"], "approver": req["approver"], "created_at": req["created_at"].timestamp()}
    if req.get("context"):
        body["context"] = req["context"]
    r = urllib.request.Request(GATEWAY, method="POST", data=json.dumps(body, ensure_ascii=False).encode(),
                               headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"})
    try:
        with urllib.request.urlopen(r, timeout=5) as resp:
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.load(e)
        except ValueError:
            return e.code, {"status": "REJECTED", "reason": f"HTTP_{e.code}"}
    except (OSError, ValueError) as e:
        return 0, {"status": "REJECTED", "reason": "GATEWAY_UNREACHABLE", "error": type(e).__name__}


ALIVE = __import__("pathlib").Path("/tmp/alive")   # compose healthcheck 가 수정 시각을 본다


def run() -> None:
    while True:
        try:
            with psycopg.connect(DSN, row_factory=dict_row, autocommit=True) as conn:
                log.info("업무 DB 연결")
                while True:
                    rows = conn.execute("""SELECT * FROM workflow.request_status WHERE last_kind = 'approved'
                                           ORDER BY created_at LIMIT 20""").fetchall()
                    for req in rows:
                        jid = req["job_order_id"]
                        event(conn, jid, "dispatched", None, None, {"gateway": GATEWAY})
                        t0 = time.time()
                        code, resp = post(req)
                        ok = resp.get("status") == "ACCEPTED"
                        event(conn, jid, "gateway_accepted" if ok else "gateway_rejected", resp.get("status"),
                              resp.get("reason"), {"http_status": code, "expires_at": resp.get("expires_at"),
                                                   "latency_ms": round(1000 * (time.time() - t0), 1)})
                        log.info("%s → 게이트웨이 %s %s %s", jid, code, resp.get("status"), resp.get("reason") or "")
                    producer.flush(2)
                    ALIVE.touch()   # healthcheck: 업무 DB 에 붙은 채 루프가 돈다
                    time.sleep(0.2)
        except psycopg.OperationalError as e:
            log.warning("업무 DB 연결 실패(다시 시도): %s", str(e).splitlines()[0])
            time.sleep(2)


if __name__ == "__main__":
    run()
