"""Collect read-only, bounded diagnostics without keys or document content."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def fetch(path):
    start = time.monotonic()
    try:
        with urlopen('http://127.0.0.1:28180' + path, timeout=25) as response:
            data = json.load(response)
        return {'status':'ok', 'duration_ms':round((time.monotonic()-start)*1000), 'data':data}
    except Exception as exc:
        return {'status':'failed','duration_ms':round((time.monotonic()-start)*1000), 'error_type':type(exc).__name__}


def main():
    report = {'at':datetime.now(timezone.utc).isoformat(), 'checks':{}}
    for path in ('/healthz','/api/operations/pipeline','/api/operations/model-status'):
        report['checks'][path] = fetch(path)
    cases = fetch('/api/operations/incidents')
    if cases['status'] == 'ok':
        items = cases['data']['items']
        report['recent_incident_count'] = len(items)
        report['latest_runs'] = []
        for incident in items[:6]:
            result = fetch('/api/operations/incidents/' + incident['id'] + '/analysis')
            if result['status'] != 'ok':
                report['latest_runs'].append({'incident_id':incident['id'],'read_status':'failed'})
            elif result['data']['items']:
                run = result['data']['items'][0]
                report['latest_runs'].append({key:run.get(key) for key in ('id','incident_id','status','model','created_at','updated_at','error')})
    else:
        report['incidents'] = cases
    output = ROOT / 'docs/ai-work/uiux-20260923/diagnostics.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(output)
    print(json.dumps({path:value['status'] for path,value in report['checks'].items()}))


if __name__ == '__main__':
    main()
