"""Read-only capture of the actual browser-approved simulated stop."""
import json
from pathlib import Path
from urllib.request import urlopen

base = 'http://127.0.0.1:28000/api/operations'
run_id = 'e1a6d524-fdb4-4891-94cc-1cdb80005f41'
def get(path):
    with urlopen(base + path, timeout=20) as response:
        return json.load(response)
trace = get('/analysis/' + run_id + '/trace')
incident_id = trace['run']['incident_id']
report = dict(trace=trace, proposals=get('/incidents/' + incident_id + '/proposals'),
              events=get('/incidents/' + incident_id + '/events'), plant=get('/plant'))
Path(__file__).with_name('browser-approved-stop.json').write_text(
    json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
proposal = next(p for p in report['proposals']['items'] if p['origin'].split(':')[1] == run_id)
assert proposal['result']['status'] == 'stop_verified'
assert proposal['decision']['decision'] == 'approve'
assert proposal['result']['observations'][-1]['commands']['agitator_run'] is False
print(json.dumps({'incident':incident_id, 'run':run_id, 'status':proposal['result']['status'],
                  'analysis_seq':proposal['evidence']['analysis_plant_state']['seq'],
                  'after_seq':proposal['result']['observations'][-1]['seq']}))
