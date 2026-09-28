"""Explicit instructor verification: real simulator stop and restoration.

Run inside the knowledge container. Records an integration-test proposal, never
an AI-generated diagnosis. Requires a real existing incident ID as its argument.
"""
import json
import sys
import time
from uuid import UUID

from pymodbus.client import ModbusTcpClient
from backend.src.modules.operations.actions import Proposal, Decision, create_proposal, decide
from backend.src.modules.operations.evidence import incident_evidence, live_state


uid = UUID(sys.argv[1])
before = live_state()
assert before["status"] == "available"
assert before["commands"]["agitator_run"] is True, "Test requires a running mixer; do not change its initial state implicitly."
result = None
try:
    evidence = incident_evidence(str(uid))
    proposal = create_proposal(uid, Proposal(
        expected_revision=evidence["revision"],
        summary="Instructor integration verification of approval, simulator stop, and observation. This is not an AI diagnosis.",
        action="stop_mixer", citations=["AR100-MIXER-RESPONSE"],
        uncertainties=["Stopping does not prove the cause or complete maintenance."]), evidence, origin="instructor-live-integration-test")
    result = decide(proposal["id"], Decision(decision="approve", note="Instructor-authorized simulator integration verification"))
    assert result["proposal"]["result"]["status"] == "stop_verified", result["proposal"]["result"]
    replay = decide(proposal["id"], Decision(decision="approve", note="Instructor-authorized simulator integration verification"))
    assert replay["replayed"]
finally:
    # Test harness restoration, deliberately not exposed as an autonomous agent tool.
    with ModbusTcpClient("host.docker.internal", port=27002, timeout=3, retries=0) as client:
        response = client.write_coil(1, before["commands"]["agitator_run"], slave=1)
        assert not response.isError(), "Could not restore simulator mixer state"
    restored = None
    for _ in range(12):
        time.sleep(.5)
        restored = live_state()
        if restored.get("status") == "available" and restored["commands"]["agitator_run"] == before["commands"]["agitator_run"]:
            break
    assert restored["commands"]["agitator_run"] == before["commands"]["agitator_run"]
    print(json.dumps({"verification": "real-simulator-action-no-LLM", "before": before,
                      "decision_result": result, "restored": restored}, ensure_ascii=False, default=str))
