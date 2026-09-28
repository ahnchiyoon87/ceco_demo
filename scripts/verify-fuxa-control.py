"""Exercise the virtual AR-100 FUXA control API and restore its initial state.

This is an API test, not a browser click or real PLC safety validation.
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


def state():
    return json.load(urlopen('http://127.0.0.1:27080/state', timeout=5))


def write(value):
    request = Request('http://127.0.0.1:27018/api/setTagValue',
                      data=json.dumps({'tags':[{'id':'AgitatorRun','value':int(value)}]}).encode(),
                      headers={'Content-Type':'application/json'}, method='POST')
    with urlopen(request, timeout=10) as response:
        response.read()


def wait(value, after):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        result = state()
        if result['seq'] > after and result['commands']['agitator_run'] == value:
            return {'seq':result['seq'],'agitator_run':result['commands']['agitator_run'],
                    'current':result['readings']['IT-102'],'vibration':result['readings']['VT-101']}
        time.sleep(.5)
    raise RuntimeError('Command state was not observed on a new scan')


def main():
    initial = state()
    assert initial['site']=='AR-100' and initial['device']=='reactor-line-01', 'Unexpected simulator'
    assert not initial['interlock'], 'Interlock active; do not run this test'
    original = bool(initial['commands']['agitator_run'])
    if not original:
        raise RuntimeError('Mixer already stopped; do not start it merely to test')
    report = {'at':datetime.now(timezone.utc).isoformat(), 'scope':'FUXA API to virtual simulator; no browser click'}
    try:
        write(False)
        report['stopped'] = wait(False, initial['seq'])
    finally:
        prior = state()['seq']
        write(original)
        report['restored'] = wait(original, prior)
        output = Path(__file__).resolve().parents[1] / 'docs/ai-work/uiux-20260923/fuxa-control-verification.json'
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__ == '__main__':
    main()
