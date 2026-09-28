"""보고서 AI 층 표 생성(측정 도구): experiments/EXP-AI/score.json·cq_*.json 에서 다시 계산해 Markdown 조각을 만든다.
숫자를 손으로 옮기지 않는다.  python harness/tools/report_ai.py > reports/_gen/ai_layer.md
"""
import json, re
from collections import defaultdict

score = json.load(open("experiments/EXP-AI/score.json", encoding="utf-8"))
rows = [r for r in score["rows"] if r["outcome"] != "invalid"]
ARMS = {"A": "V1 원형", "B": "V1+고장 지식 문서", "C": "V2(그래프 원인분석·검색)"}
# 본 비교: SC1(1배속), SC2(60배속, 세 팔 같은 조건), SC3(본 실험). 1배속 SC2·지연 변형은 보조.
MAIN = {"SC1_bearing": "SC1 베어링", "SC2_heater_stuck@60배속": "SC2 히터 고착", "SC3_overpressure": "SC3 과압(새 고장)"}

agg = defaultdict(lambda: {"n": 0, "act": 0, "c_ok": 0, "c_n": 0, "t": []})
for r in rows:
    g = agg[(r["arm"], r["scenario"])]
    g["n"] += 1; g["act"] += bool(r["action_match"])
    if r["cause_score"]:
        g["c_ok"] += r["cause_score"][0]; g["c_n"] += r["cause_score"][1]
    if r["analysis_s"] is not None:
        g["t"].append(r["analysis_s"])


def cell(arm, sc, kind):
    g = agg.get((arm, sc))
    if not g or not g["n"]:
        return "미측정" if arm != "B" or sc != "SC3_overpressure" else "해당 없음(설계상 제외)"
    if kind == "act":
        return f"{g['act']}/{g['n']}"
    if kind == "cause":
        return f"{g['c_ok']}/{g['c_n']}" if g["c_n"] else "출력 없음"
    t = sorted(g["t"]); return f"{t[len(t)//2]:.1f}s" if t else "미측정"


print("| 시나리오 | 항목 | " + " | ".join(ARMS.values()) + " |")
print("|---|---|" + "---|" * len(ARMS))
for sc, label in MAIN.items():
    for kind, name in (("act", "조치 일치"), ("cause", "고장모드 상태 일치"), ("t", "분석 시간 중앙값")):
        print(f"| {label} | {name} | " + " | ".join(cell(a, sc, kind) for a in ARMS) + " |")

# 히터 고착 판별: C 의 FM-HEATER-STUCK-ON 상태, A·B 요약문에서 TT-102 부재 언급
heater = [r for r in rows if r["scenario"] == "SC2_heater_stuck@60배속" and r["arm"] == "C"]
ok = sum(1 for r in heater if r["cause_detail"] and r["cause_detail"]["FM-HEATER-STUCK-ON"][0] == "supported")
print(f"\n히터 고착 '관측으로 지지' — V2 {ok}/{len(heater)}. V1·B 는 고장모드 판정 출력 없음(요약문: 확정 불가).")
viol = sum(1 for r in rows if r["confirm_review"])
print(f"원인 확정 표현 후보 {viol}건 — 사람 확인 결과 전부 부정문(위반 0, decision-log #83).")

cq = {}
for arm in ("A", "C"):
    text = open("experiments/EXP-AI/cq_judgement.md", encoding="utf-8").read()
    m = re.search(r"\*\*합계:\*\* A answered (\d+) · partial (\d+) · no (\d+) / C answered (\d+) · partial (\d+) · no (\d+)", text)
print(f"\nCQ 15 — V1: 답함 {m.group(1)} · 일부 {m.group(2)} · 불가 {m.group(3)} / V2: 답함 {m.group(4)} · 일부 {m.group(5)} · 불가 {m.group(6)} (`experiments/EXP-AI/cq_judgement.md`)")
