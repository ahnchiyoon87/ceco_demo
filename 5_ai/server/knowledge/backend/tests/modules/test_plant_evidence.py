import io
import json

from backend.src.modules.operations import evidence


def test_live_state_exposes_operation_but_not_injected_fault_answer(monkeypatch):
    state = {"site": "AR-100", "device": "reactor-line-01", "seq": 42,
             "readings": {"IT-102": 10}, "commands": {"agitator_run": True},
             "interlock": False, "active_faults": [{"scenario": "bearing_wear"}]}
    monkeypatch.setattr(evidence, "urlopen", lambda *a, **k: io.BytesIO(json.dumps(state).encode()))
    result = evidence.live_state()
    assert result["commands"] == state["commands"]
    assert result["interlock"] is False
    assert result["seq"] == 42
    assert "active_faults" not in result
    assert "bearing_wear" not in json.dumps(result)
    assert result["retrieved_at"] and result["timestamp_note"]


def test_live_state_failure_does_not_invent_stopped_or_running(monkeypatch):
    def disconnected(*args, **kwargs):
        raise OSError("offline")
    monkeypatch.setattr(evidence, "urlopen", disconnected)
    result = evidence.live_state()
    assert result["status"] == "unavailable"
    assert "commands" not in result and "interlock" not in result
