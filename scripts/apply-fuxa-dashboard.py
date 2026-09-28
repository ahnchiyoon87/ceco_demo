"""Back up and update HMI only; preserve runtime devices, settings and data."""
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
URL = 'http://127.0.0.1:27018/api/project'


def validate(project, devices):
    view = project['hmi']['views'][0]
    ET.fromstring(view['svgcontent'])
    for key, item in view['items'].items():
        prop = item['property']
        tags = devices[prop['variableSrc']]['tags']
        assert any(t['id'] == prop['variableId'] for t in tags.values()), key
        assert f'id="{key}"' in view['svgcontent'], key
    return len(view['items'])


def main():
    incoming = json.loads((ROOT / 'fuxa/project.json').read_text(encoding='utf-8'))
    raw = urlopen(URL, timeout=15).read()
    existing = json.loads(raw)
    count = validate(incoming, existing['devices'])
    output = ROOT / 'docs/ai-work/uiux-20260923'
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = output / f'fuxa-runtime-before-{stamp}.json'
    backup.write_bytes(raw)
    # Retain unrelated views. Only replace this project's known AR-100 view.
    target = incoming['hmi']['views'][0]
    views = existing['hmi']['views']
    assert any(v['id'] == target['id'] for v in views), 'Target view missing; do not replace another project'
    existing['hmi']['views'] = [target if v['id'] == target['id'] else v for v in views]
    # Apply the dashboard's responsive zoom while retaining other layout settings.
    existing['hmi'].setdefault('layout', {})['zoom'] = incoming['hmi']['layout']['zoom']
    request = Request(URL, data=json.dumps(existing, ensure_ascii=False).encode(),
                      headers={'Content-Type':'application/json'}, method='POST')
    with urlopen(request, timeout=30) as response:
        response.read()
    confirmed = json.load(urlopen(URL, timeout=15))
    assert confirmed['hmi'] == existing['hmi'], 'HMI readback differs; inspect backup'
    assert confirmed['devices'] == existing['devices'], 'Device definitions changed; inspect backup'
    (output / 'fuxa-deployment.json').write_text(json.dumps({
        'at':stamp,'backup':backup.name,'bindings_validated':count,
        'hmi_readback_matches':True,'devices_preserved':True,
        'equipment_commands_sent':False,'browser_verified':False,
    }, indent=2), encoding='utf-8')
    print(f'HMI saved and read back; {count} bindings validated. Devices preserved. Backup: {backup}')


if __name__ == '__main__':
    main()
