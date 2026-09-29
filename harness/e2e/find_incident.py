"""[측정 도구] /incidents 응답(stdin)에서 교반기 이상 사건(열린 상태, t0-5 초 이후) id 를 찾아 출력. 없으면 빈 출력.
  curl -s $API/incidents | python harness/e2e/find_incident.py <t0_epoch_s>
(regression.sh 안에 인라인으로 두었던 코드 — 셸이 괄호를 잘못 읽어 문법 오류, #130)"""
import json, sys
t0 = float(sys.argv[1])
items = json.load(sys.stdin)
items = items.get("items", items) if isinstance(items, dict) else items
for x in items:
    if ("mixer-current-vibration" in (x.get("correlation_key") or "") and x.get("status") in ("received", "awaiting_review", "unresolved")
            and x.get("last_ts", 0) / 1e9 >= t0 - 5):
        print(x["id"]); break
