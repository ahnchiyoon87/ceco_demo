"""Repeat real-LLM cooling maintenance after a successful recorded run.

Waits for recording to finish before taking the shared single-run lock. Captures
plant state BEFORE the standard E2E tool's teardown reset so reset cannot prove
recovery. The video encoder may run concurrently; no scenarios overlap.
"""
import json
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests'/'e2e'))
import maintenance_scenarios as M

record_path=Path(sys.argv[1])
deadline=time.monotonic()+900
while not record_path.exists():
    if time.monotonic()>deadline:
        raise SystemExit('Recorded verification was not completed; repeat was not started.')
    time.sleep(3)
filmed=json.loads(record_path.read_text(encoding='utf-8'))
if filmed['report']['outcome']!='recovered':
    raise SystemExit('The filmed run did not recover.')
lock=M.single_instance()
original_save=M.save

def save_before_reset(record):
    record['state_before_teardown']=M.plant()
    return original_save(record)

M.save=save_before_reset
try:
    record=M.run('s1')
    valid=(record.get('report',{}).get('outcome')=='recovered'
           and record.get('chosen_matches_truth') is True
           and not record.get('state_before_teardown',{}).get('active_faults',{'unknown':True}))
    report={'passed':valid,'report':record.get('report'),'state_before_teardown':record.get('state_before_teardown'),'elapsed_s':record.get('elapsed_s')}
    (ROOT/'experiments'/'BOOTH-20261013'/'repeat-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('REPEAT VERIFIED' if valid else 'REPEAT FAILED',flush=True)
    if not valid:
        raise SystemExit(1)
finally:
    lock.close()
