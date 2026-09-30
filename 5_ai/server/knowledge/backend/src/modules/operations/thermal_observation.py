"""Durable, read-only post-action observation. This module never sends commands."""
import asyncio
import logging
import math
import time
from copy import deepcopy

from psycopg.types.json import Jsonb

BAND_C = 1.0
HOLD_S = 30
MAX_GAP_S = 6
TIMEOUT_S = 900


def start(state, now):
    return {"status":"observing", "site":state["site"], "device":state["device"],
            "target":state["commands"]["temp_sp_c"], "started":now, "last_at":None,
            "last_seq":None, "within_since":None, "held_s":0, "samples":[],
            "reason":"냉각 명령 반영 후 실제 온도를 관측합니다."}


def observe(track, state, now):
    result = deepcopy(track)
    if result["status"] not in {"observing", "unknown"}:
        return result
    if now-result["started"] >= TIMEOUT_S:
        result.update(status="timeout", reason="15분 내 온도 범위 유지를 확인하지 못했습니다. 추가 점검이 필요합니다.")
        return result
    temperature = state.get("readings", {}).get("TT-101")
    seq = state.get("seq")
    if (state.get("status") != "available" or type(temperature) not in (float,int)
            or not math.isfinite(temperature) or type(seq) is not int):
        result.update(status="unknown", within_since=None, held_s=0, reason="새 온도 관측을 확인하지 못했습니다.")
        return result
    if ((state.get("site"),state.get("device")) != (result["site"],result["device"])
            or (result["last_seq"] is not None and seq < result["last_seq"])):
        result.update(status="interrupted", reason="설비 식별 또는 스캔 번호가 변경되어 관측을 종료했습니다.")
        return result
    if state.get("commands",{}).get("temp_sp_c") != result["target"]:
        result.update(status="interrupted", reason="목표 온도가 변경되어 이전 승인 조건의 관측을 종료했습니다.")
        return result
    if state.get("commands",{}).get("cooler_enable") is not True:
        result.update(status="interrupted", reason="냉각 명령이 변경되어 관측을 종료했습니다.")
        return result
    if state.get("interlock") is True:
        result.update(status="interrupted", reason="고압 인터록이 발동되어 정상 회복으로 판정하지 않습니다.")
        return result
    gap = result["last_at"] is not None and now-result["last_at"] > MAX_GAP_S
    if seq == result["last_seq"]:
        if gap:
            result.update(status="unknown",within_since=None,held_s=0,reason="스캔 갱신이 없어 유지 시간을 확인할 수 없습니다.")
        return result
    inside = abs(temperature-result["target"]) <= BAND_C
    since = (now if gap or result["within_since"] is None else result["within_since"]) if inside else None
    held = now-since if since is not None else 0
    result.update(status="temperature_stable" if held>=HOLD_S else "observing", last_at=now,
                  last_seq=seq, within_since=since, held_s=held,
                  samples=(result["samples"]+[{"at":now,"value":temperature,"seq":seq}])[-200:],
                  reason="목표 ±1°C에서 새 관측값이 30초 이어졌습니다. 원인 제거·정비 완료는 아닙니다." if held>=HOLD_S else "실제 온도와 목표 범위 유지 시간을 관측 중입니다.")
    return result


def tick():
    from .actions import connection, event
    from .evidence import live_state
    with connection() as conn:
        pending = conn.execute("SELECT id,incident_id FROM manufacturing_proposals WHERE status='observing'").fetchall()
    if not pending:
        return
    state = live_state()
    observed_at = time.time()
    for item in pending:
        with connection() as conn:
            conn.execute("SET LOCAL lock_timeout = '2s'")
            conn.execute("SET LOCAL statement_timeout = '5s'")
            incident = conn.execute("SELECT id,review_revision FROM manufacturing_incidents WHERE id=%s FOR UPDATE",(item["incident_id"],)).fetchone()
            proposal = conn.execute("SELECT * FROM manufacturing_proposals WHERE id=%s FOR UPDATE",(item["id"],)).fetchone()
            if proposal["status"] != "observing":
                continue
            result = proposal["result"]
            track = result["thermal_observation"]
            now = time.time()
            if incident["review_revision"] != track.get("review_revision"):
                updated = {**track,"status":"interrupted","reason":"새 알람 등으로 검토 기준이 변경되어 기존 조치의 회복 판정을 중단했습니다."}
            else:
                updated = observe(track,state if now-observed_at<=MAX_GAP_S else {"status":"unavailable"},now)
            if updated == track:
                continue
            result["thermal_observation"] = updated
            terminal = updated["status"] not in {"observing","unknown"}
            final = ("awaiting_maintenance" if updated["status"]=="temperature_stable" else "unresolved") if terminal else "observing"
            if terminal:
                result["status"] = updated["status"]
                result["reason"] = updated["reason"]
            conn.execute("UPDATE manufacturing_proposals SET result=%s,status=%s,completed_at=CASE WHEN %s THEN now() ELSE NULL END WHERE id=%s",(Jsonb(result),final,terminal,item["id"]))
            if terminal:
                conn.execute("UPDATE manufacturing_incidents SET status=%s,revision=revision+1,review_revision=review_revision+1 WHERE id=%s",(final,item["incident_id"]))
            event(conn,item["incident_id"],"thermal_observation",{"proposal_id":str(item["id"]),"status":updated["status"],"temperature":updated["samples"][-1] if updated["samples"] else None,"held_s":updated["held_s"],"reason":updated["reason"]})


async def run(stop):
    while not stop.is_set():
        try:
            await asyncio.to_thread(tick)
        except Exception:
            logging.getLogger(__name__).exception("Thermal observation read/persistence failed; no command is retried")
        try:
            await asyncio.wait_for(stop.wait(),timeout=2)
        except asyncio.TimeoutError:
            pass
