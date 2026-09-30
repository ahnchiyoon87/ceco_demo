"""Postgres transaction tests; synthetic verification events, no plant control."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.src.modules.operations.api import Alarm, initialize, ingest, get_incident, connection


def test_concurrent_delivery_is_one_incident_and_one_event():
    initialize()
    alarm = Alarm(ts=1, site=f"verification-{uuid4()}", device="probe", tag="VT-101",
                  value=8, alert_type="CEP_BEARING", severity="CRITICAL",
                  detector="TIER1_CEP", detail="Synthetic integration probe")
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: ingest(alarm), range(8)))
        assert sum(not row["duplicate"] for row in results) == 1
        ids = {str(row["incident"]["id"]) for row in results}
        assert len(ids) == 1
        detail = get_incident(ids.pop())
        assert detail["incident"]["status"] == "received"
        assert len(detail["events"]) == 1
        assert detail["events"][0]["payload"] == alarm.model_dump()
    finally:
        with connection() as conn:
            conn.execute("DELETE FROM manufacturing_alarm_links WHERE incident_id IN (SELECT id FROM manufacturing_incidents WHERE site=%s)", (alarm.site,))
            conn.execute("DELETE FROM manufacturing_events WHERE incident_id IN (SELECT id FROM manufacturing_incidents WHERE site=%s)", (alarm.site,))
            conn.execute("DELETE FROM manufacturing_incidents WHERE site=%s", (alarm.site,))


def test_invalid_reading_is_not_accepted():
    with pytest.raises(ValidationError):
        Alarm(ts=1, site="probe", device="probe", tag="probe", value=float("nan"),
              alert_type="probe", severity="probe", detector="probe", detail="probe")


def test_correlation_preserves_evidence_and_separates_unknown_causes():
    initialize()
    # Distinct historical synthetic event time keeps live simulation cases separate.
    start = 1_000_000_000_000 + (uuid4().int % 1_000_000) * 1_000_000_000_000
    base = dict(ts=start, site="AR-100", device="reactor-line-01", tag="IT-102",
                value=10.1, alert_type="THRESHOLD_USL", severity="CRITICAL",
                detector="TIER1_RULE", detail=f"verification-{uuid4()}")
    ids = set()
    def send(**updates):
        result = ingest(Alarm(**(base | updates)))
        ids.add(result["incident"]["id"])
        return result
    try:
        first = send()
        second = send(ts=start+5_000_000_000, tag="VT-101", alert_type="CEP_BEARING", detector="TIER1_CEP")
        assert second["correlated"] and second["incident"]["id"] == first["incident"]["id"]
        late = send(ts=start-2_000_000_000, value=10.2)
        assert late["incident"]["id"] == first["incident"]["id"]
        assert late["incident"]["alarm_count"] == 3
        ml = send(ts=start+6_000_000_000, tag="MULTIVARIATE", alert_type="ML_AUTOENCODER")
        assert ml["incident"]["id"] != first["incident"]["id"]
        next_episode = send(ts=start+60_000_000_000)
        assert next_episode["incident"]["id"] != first["incident"]["id"]
        other_device = send(device="different-device")
        assert other_device["incident"]["id"] != first["incident"]["id"]
        assert len(get_incident(str(first["incident"]["id"]))["events"]) == 3
    finally:
        with connection() as conn:
            for uid in ids:
                conn.execute("DELETE FROM manufacturing_alarm_links WHERE incident_id=%s", (uid,))
                conn.execute("DELETE FROM manufacturing_events WHERE incident_id=%s", (uid,))
                conn.execute("DELETE FROM manufacturing_incidents WHERE id=%s", (uid,))
