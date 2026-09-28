"""Repair legacy qualified HMI IDs against the running FUXA tag registry.

Read-only preview by default. --apply backs up the complete project before
changing only unambiguous variableId references; never sends equipment commands.
"""
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


def repair(project):
    devices = project['devices']
    counts = Counter(tag['id'] for device in devices.values() for tag in device.get('tags', {}).values())
    changes = []
    def visit(value):
        if isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            old = value.get('variableId')
            device = devices.get(value.get('variableSrc'), {})
            for tag in device.get('tags', {}).values():
                if old == f"{device['id']}^~^{tag['id']}" and counts[tag['id']] == 1:
                    value['variableId'] = tag['id']
                    changes.append({'from': old, 'to': tag['id']})
                    break
            for child in value.values():
                visit(child)
    visit(project.get('hmi', {}))
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:27018')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    endpoint = args.url.rstrip('/') + '/api/project'
    original = urlopen(endpoint, timeout=15).read()
    project = json.loads(original)
    changes = repair(project)
    if args.apply and changes:
        backup = Path(__file__).parent / 'artifacts' / ('fuxa-before-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.json')
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(original)
        payload = json.dumps(project, ensure_ascii=False).encode()
        request = Request(endpoint, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
        with urlopen(request, timeout=30) as response:
            response.read()
        confirmed = json.load(urlopen(endpoint, timeout=15))
        if confirmed.get('hmi') != project.get('hmi'):
            raise RuntimeError('Readback differs; inspect saved backup before retrying')
        print('Verified HMI readback. Backup:', backup)
    print(json.dumps({'apply': args.apply, 'changes': changes}, ensure_ascii=False))


if __name__ == '__main__':
    main()
