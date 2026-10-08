"""업무 서비스(HANDOFF §2-3) — Kafka 를 소비해 PLC 상태·작업 요청 결과를 정리한다. 설비에 명령하지 않는다.
분석 alert 의 묶기·억제·표시는 Alertmanager 가 한다(IT 수집기 alerts_to_alertmanager·status_to_alertmanager·alertmanager_to_display).

  sensor.alerts     → AI 사건 접수(consumer.persist_message)
  plant.status      → PLC 상태 기억(재관측), 정비 모드 켜기·끄기를 감사에 기록
  request.responses → OT 수신기 응답 ⓑⓒ 를 workflow 사건·감사로(같은 요청 ID)
  타이머(0.5 s)     → ACK 5 s(게이트웨이 수용 ⓐ 부터 수신 응답 ⓑ 까지, 넘으면 '결과 모름'), 만료 + 5 s(ⓑ 없음),
                      운전원 대기 60 + 30 + 5 s(ⓒ 없음), 재관측 10 s(PLC 수용부터 새 상태까지, 넘으면 command-disagree alert)
시간 값은 벽시계(17번 E18·E38). 늦게 온 응답은 사건으로 덧붙어 현재 상태(뷰)를 덮는다.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time

from confluent_kafka import Consumer, KafkaException, Producer

from .consumer import initialize_inbox, persist_message
from .plant_db import audit, plant_connection, request_event

log = logging.getLogger("business")
REG = json.load(open(os.environ.get("REGISTRY_TAGS", "/opt/ar100/registry/tags.json"), encoding="utf-8"))
WM = {w["work_master_id"]: w for w in json.load(open(os.environ.get("REGISTRY_WM", "/opt/ar100/registry/work_masters.ot.json"), encoding="utf-8"))}
ACK_S, REOBS_S, OP_WAIT_S, EXPIRY_S = 5.0, 10.0, 60.0, 30.0
SCALE = float(os.environ.get("PHYSICS_TIME_SCALE", "600"))   # 현장 정비 시간(설비 초) → 벽시계
ALIVE = __import__("pathlib").Path("/tmp/alive")   # compose healthcheck 가 수정 시각을 본다
BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
producer = Producer({"bootstrap.servers": BOOTSTRAP, "linger.ms": 5})
state: dict[tuple[str, str], object] = {}      # (asset, name) → 값 (PLC 상태 토픽)
lock = threading.Lock()


def now() -> float:
    return time.time()


def publish(topic: str, key: str, value: dict) -> None:
    producer.produce(topic, key=key, value=json.dumps(value, ensure_ascii=False, default=str))
    producer.poll(0)


def audited(conn, actor_type, actor_id, action, jid, subject, detail):
    audit(conn, actor_type, actor_id, action, jid, subject, detail)
    publish("audit.copy", jid or subject or action, {"actor_type": actor_type, "actor_id": actor_id, "action": action,
                                                       "job_order_id": jid, "subject": subject, "detail": detail, "at": now()})


# ── PLC 상태 ───────────────────────────────────────────────────────
def on_status(conn, s: dict) -> None:
    key = (s.get("asset"), s.get("name"))
    value = s.get("value")
    if s.get("kind") not in ("status", "state"):
        return
    with lock:
        prev = state.get(key)
        state[key] = value
    if key == ("PLC-01", "maintenance") and prev is not None and prev != value:
        op = state.get(("PLC-01", "maint_operator"))
        audited(conn, "human", f"operator-{op}" if op else "field-panel", "maintenance_on" if value else "maintenance_off",
                None, "PLC-01", {"maint_operator": op, "source": "plant.status"})


# ── 작업 요청 응답·타이머 ─────────────────────────────────────────
def known(conn, jid: str) -> bool:
    return conn.execute("SELECT 1 FROM workflow.request WHERE job_order_id = %s", (jid,)).fetchone() is not None


def on_response(conn, r: dict) -> None:
    jid = r.get("job_order_id")
    if not jid or not known(conn, jid):
        log.info("등록되지 않은 요청의 응답(기록 안 함): %s", jid)
        return
    request_event(conn, jid, r["stage"], r.get("status"), r.get("reason"), r, "ot-receiver")
    audited(conn, "system", "ot-receiver", f'response_{r["stage"]}', jid, r.get("status"), {"reason": r.get("reason")})


def _expectation(w: dict):
    """재관측 기대값을 작업 정의(등록부 생성본)에서 만든다: 스위치 = 고정값, 설정값 = 요청 파라미터, 정비 모드 켜기 = 참."""
    kind = w.get("kind")
    if kind == "switch":
        return (w["equipment_id"], w["command"], lambda req, v=bool(w["fixed_value"]): v)
    if kind == "setpoint":
        pid = w["parameters"][0]["id"]
        return (w["equipment_id"], w["command"],
                lambda req, pid=pid: next(p["value"] for p in req["job_order_parameters"] if p["id"] == pid))
    if kind == "maintenance_on":
        return ("PLC-01", "maintenance", lambda req: True)
    return None


EXPECT = {wid: e for wid, w in WM.items() if (e := _expectation(w))}   # 재관측: 작업 정의 → (설비, 상태 이름, 기대값)
FIELD_GRACE_S = 30.0   # 현장 정비: 설비 작업 시간(÷ 배속) + 이 여유 안에 정비팀 결과(field)가 없으면 결과 미확인


def same(current, expected) -> bool:
    if isinstance(expected, bool) or current is None:
        return current == expected
    try:
        return abs(float(current) - float(expected)) <= 0.6   # 설정값은 PLC 정수 레지스터로 반올림된다
    except (TypeError, ValueError):
        return False


def timers(conn) -> None:
    """진행 중 요청의 시간 판정. 각 판정은 한 번만 남긴다(사건 종류로 확인)."""
    rows = conn.execute("""
        SELECT r.job_order_id, r.work_master_id, r.job_order_parameters, r.created_at,
               jsonb_object_agg(e.kind || ':' || coalesce(e.status, ''), extract(epoch FROM e.at)) AS ev,
               max(CASE WHEN e.kind = 'gateway_accepted' THEN (e.detail ->> 'expires_at')::double precision END) AS expires_at
        FROM workflow.request r JOIN workflow.request_event e USING (job_order_id)
        WHERE r.created_at > now() - interval '15 minutes'
        GROUP BY r.job_order_id, r.work_master_id, r.job_order_parameters, r.created_at""").fetchall()
    t = now()
    for row in rows:
        jid, ev = row["job_order_id"], row["ev"]
        has = lambda prefix: any(k.startswith(prefix) for k in ev)
        at = lambda prefix: min((v for k, v in ev.items() if k.startswith(prefix)), default=None)
        # 판정이 끝난 요청(만료·미확인·재관측 일치·불일치). ACK 시간 초과는 늦은 응답이 올 수 있어 끝이 아니다
        final = has("expired_unconfirmed") or has("unconfirmed") or has("observed") or has("command_disagree")
        if final or has("gateway_rejected") or not has("gateway_accepted"):
            continue
        a = at("gateway_accepted")
        receipt = at("receipt:")
        if receipt is None:
            if row["expires_at"] and t > row["expires_at"] + 5:
                note(conn, jid, "expired_unconfirmed", "UNKNOWN", "만료 + 5 s 까지 수신 응답(ⓑ) 없음 — 결과 미확인")
            elif t - a > ACK_S and not has("ack_timeout"):
                note(conn, jid, "ack_timeout", "UNKNOWN", "ACK 5 s 안에 수신 응답(ⓑ) 없음 — 응답 없음(결과 모름). 다시 보내지 않는다")
            continue
        if (has("receipt:REJECTED") or has("operator:REJECTED") or has("operator:OPERATOR_REJECTED") or has("plc:REJECTED")
                or has("field:REJECTED")):
            continue
        wait = at("receipt:OPERATOR_WAIT")
        if wait is not None and not has("operator:") and t - wait > OP_WAIT_S + EXPIRY_S + 5:
            note(conn, jid, "unconfirmed", "UNKNOWN", "운전원 대기 뒤 60 + 30 + 5 s 안에 운전원·PLC 응답(ⓒ) 없음 — 결과 미확인")
            continue
        w = WM.get(row["work_master_id"], {})
        if w.get("kind") == "field":
            # 현장 정비: 정비팀 결과(field 단계)가 곧 재관측이다. 효과(설비 회복)는 AI 쪽 회복 판정이 따로 본다.
            accepted = at("receipt:AUTO_ACCEPTED") or at("operator:OPERATOR_ACCEPTED")
            done = next(((k, v) for k, v in ev.items() if k.startswith("field:")), None)
            if done:
                status = done[0].split(":", 1)[1]
                if status in ("DONE", "DONE_NO_FAULT"):
                    note(conn, jid, "observed", "OK" if status == "DONE" else "NO_FAULT_FOUND",
                         f"현장 정비 완료({w.get('field_task')}, {status})", {"task": w.get("field_task"), "field_status": status})
                elif not has("unconfirmed"):
                    note(conn, jid, "unconfirmed", "UNKNOWN" if status == "UNKNOWN" else "REJECTED",
                         f"현장 정비 결과: {status}", {"task": w.get("field_task"), "field_status": status})
            elif accepted and t - accepted > float(w.get("plant_duration_s", 0)) / SCALE + FIELD_GRACE_S:
                note(conn, jid, "unconfirmed", "UNKNOWN", "현장 정비 결과(field)가 시간 안에 오지 않음 — 결과 미확인. 다시 보내지 않는다")
            continue
        plc_ok = at("plc:ACCEPTED")
        if plc_ok is None:
            continue
        if row["work_master_id"] not in EXPECT:
            continue
        asset, name, want = EXPECT[row["work_master_id"]]
        expected = want(row)
        with lock:
            current = state.get((asset, name))
        if same(current, expected):
            note(conn, jid, "observed", "OK", f"재관측: {asset}/{name} = {current}", {"asset": asset, "name": name, "value": current})
        elif t - plc_ok > REOBS_S:
            note(conn, jid, "command_disagree", "DISAGREE",
                 f"PLC 수용 뒤 10 s 안에 {asset}/{name} 가 {expected} 로 보이지 않음(현재 {current})",
                 {"asset": asset, "name": name, "expected": expected, "current": current})
            # 명령 ≠ 상태 alert 는 분석 alert 와 같은 길(sensor.alerts)로 낸다 → 사건 접수·Alertmanager 묶기·표시·이력이 한 길
            publish("sensor.alerts", asset, {"ts": time.time_ns(), "site": REG["hierarchy"]["site"], "device": REG["hierarchy"]["line"],
                                             "tag": f"{asset}/{name}", "value": 0.0, "alert_type": "COMMAND_DISAGREE",
                                             "severity": "WARNING", "detector": "BUSINESS",
                                             "detail": f"작업 요청 {jid}: 명령 ≠ 상태(기대 {expected}, 현재 {current})"})


def note(conn, jid, kind, status, reason, detail=None):
    request_event(conn, jid, kind, status, reason, detail or {}, "business")
    audited(conn, "system", "business-service", kind, jid, status, {"reason": reason, **(detail or {})})
    publish("request.events", jid, {"job_order_id": jid, "kind": kind, "status": status, "reason": reason, "at": now()})
    log.info("%s %s %s", jid, kind, reason)


def intake_loop() -> None:
    """AI 사건 접수(AI DB). 요청 판정과 다른 스레드·연결로 돈다 — AI 승인이 사건 행을 잠근 동안(작업 요청 결과 대기)
    접수가 멈춰도 작업 요청의 시간 판정(ACK 5 s·만료·재관측)은 멈추지 않는다."""
    # 사건 접수는 자기 소비자 그룹(earliest, 처음부터 빠짐없이)으로 따로 소비한다
    intake = Consumer({"bootstrap.servers": BOOTSTRAP, "group.id": "ar100-ai-incidents-v1", "auto.offset.reset": "earliest",
                       "enable.auto.commit": False, "enable.auto.offset.store": False})
    intake.subscribe(["sensor.alerts"])
    while True:
        try:
            m = intake.poll(0.5)
            if m is None:
                continue
            if m.error():
                raise KafkaException(m.error())
            persist_message(m.topic(), m.partition(), m.offset(), m.value() or b"")
            intake.commit(message=m, asynchronous=False)
        except Exception:
            log.exception("사건 접수 오류 — 다시 시도")
            time.sleep(2)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
    initialize_inbox()
    threading.Thread(target=intake_loop, name="ai-intake", daemon=True).start()
    consumer = Consumer({"bootstrap.servers": BOOTSTRAP, "group.id": "ar100-business-v2", "auto.offset.reset": "latest",
                         "enable.auto.commit": False, "enable.auto.offset.store": False})
    consumer.subscribe(["plant.status", "request.responses"])
    last_tick = 0.0
    while True:
        try:
            with plant_connection(autocommit=True) as conn:
                log.info("공용 업무 DB 연결")
                while True:
                    m = consumer.poll(0.2)
                    if m is not None:
                        if m.error():
                            raise KafkaException(m.error())
                        v = json.loads(m.value() or b"{}")
                        {"plant.status": on_status, "request.responses": on_response}[m.topic()](conn, v)
                        consumer.commit(message=m, asynchronous=False)
                    if now() - last_tick >= 0.5:
                        timers(conn)
                        producer.poll(0)
                        last_tick = now()
                        ALIVE.touch()   # healthcheck: 업무 DB 에 붙은 채 타이머 루프가 돈다
        except Exception:
            log.exception("업무 서비스 오류 — 다시 연결")
            time.sleep(2)


if __name__ == "__main__":
    main()
