"""Migrate only the latest-alert MQTT tag; back up and verify all other data."""
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
URL = 'http://127.0.0.1:27018/api/project'


def main():
    raw = urlopen(URL, timeout=15).read()
    before = json.loads(raw)
    after = copy.deepcopy(before)
    device = after['devices']['ALERTS']
    assert device['type'] == 'MQTTclient'
    tag = device['tags']['ActiveAlert']
    assert tag['address'] in ('scada/alerts/#', 'scada/hmi/latest-alert')
    tag.update(address='scada/hmi/latest-alert', type='raw',
               label='최근 분석 알람',
               description='최근 수신 이벤트: UTC 시각 / 심각도 / 센서 / 감지 유형. 현재 활성 여부와 다름.')
    # The driver subscribes using tag.address, not property.subscriptions.
    device['property'].pop('subscriptions', None)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = ROOT / 'docs/ai-work/uiux-20260923'
    backup = output / f'fuxa-alert-before-{stamp}.json'
    backup.write_bytes(raw)
    req = Request(URL, data=json.dumps(after, ensure_ascii=False).encode(),
                  headers={'Content-Type': 'application/json'}, method='POST')
    urlopen(req, timeout=30).read()
    confirmed = json.load(urlopen(URL, timeout=15))
    assert confirmed == after, 'Project readback differs; inspect backup'
    assert confirmed['devices']['AR100'] == before['devices']['AR100']
    assert confirmed['hmi'] == before['hmi']
    (output / 'fuxa-alert-deployment.json').write_text(json.dumps({
        'at': stamp, 'backup': backup.name, 'project_readback_matches': True,
        'modbus_preserved': True, 'hmi_preserved': True,
        'equipment_commands_sent': False, 'browser_verified': False,
    }, indent=2), encoding='utf-8')
    print('Latest-alert tag migrated; Modbus and HMI preserved.')


if __name__ == '__main__':
    main()
