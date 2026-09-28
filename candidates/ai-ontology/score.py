"""시나리오 결과를 사전 등록 정답(ontology/v2/answer-key.yaml)과 대조한다. 정답은 바꾸지 않는다.

    python score.py a1 [a2 ...]     # run ID 들 → /experiments/EXP-AI/raw/score_<runs>.json
"""
import fnmatch
import glob
import json
import os
import sys

import yaml

REPO = os.environ.get("REPO", "/repo")


def main():
    runs = sys.argv[1:]
    key = yaml.safe_load(open(f"{REPO}/ontology/v2/answer-key.yaml", encoding="utf-8"))["scenarios"]
    rows = []
    for run in runs:
        for f in sorted(glob.glob(f"/experiments/EXP-AI/raw/*_{run}.json")):
            r = json.load(open(f, encoding="utf-8"))
            if "result" not in r:
                rows.append({"scenario": r["scenario"], "run": run, "error": r.get("error")})
                continue
            k = key[r["scenario"]]
            got = {c["id"]: c["status"] for c in r["result"]["candidates"]}
            cause_hits = sum(1 for fm, st in k["causes"].items() if got.get(fm) == st)
            extra = sorted(set(got) - set(k["causes"]))
            confirmed_ok = r["result"]["confirmed_cause"] is None
            top = [x["sid"] for x in r["result"]["sections"]]
            req_ok = all(s in top for s in k["sections_required"])
            forb = [s for s in top for pat in k["sections_forbidden"] if fnmatch.fnmatch(s, pat)]
            rows.append({"scenario": r["scenario"], "run": run,
                         "causes": f"{cause_hits if confirmed_ok else 0}/{len(k['causes'])}",
                         "cause_mismatch": {fm: [st, got.get(fm)] for fm, st in k["causes"].items() if got.get(fm) != st},
                         "extra_failure_modes": extra, "confirmed_cause_ok": confirmed_ok,
                         "sections_top3": top, "sections_ok": req_ok and not forb, "sections_forbidden_hit": forb,
                         "action": r["result"]["action"], "action_ok": r["result"]["action"] == k["action"],
                         "infer_ms": r["infer_ms"], "t_trigger_s": r["t_trigger_s"]})
    out = f"/experiments/EXP-AI/raw/score_{'_'.join(runs)}.json"
    json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main()
