"""Read license files from checksum-verified PyPI sdists; never execute/extract.

Only supplements missing installed-wheel license texts at exact versions.
"""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent.parent / 'docs' / 'ai-work'
with zipfile.ZipFile(ROOT / 'backend-python-notices.zip') as archive:
    inventory = json.loads(archive.read('inventory.json'))
report = []
with zipfile.ZipFile(ROOT / 'backend-source-notices.zip', 'w', zipfile.ZIP_DEFLATED) as out:
    for package in inventory['packages']:
        name, version = package['name'], package['version']
        if package['files'] or name == 'ontology-studio-backend':
            continue
        with urllib.request.urlopen(f'https://pypi.org/pypi/{name}/{version}/json', timeout=30) as response:
            data = json.load(response)
        sdist = next((x for x in data['urls'] if x['packagetype'] == 'sdist'), None)
        if sdist is None:
            report.append({'name': name, 'version': version, 'notice_files': [],
                           'status': 'exact version has no PyPI sdist'})
            continue
        with urllib.request.urlopen(sdist['url'], timeout=30) as response:
            raw = response.read()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != sdist['digests']['sha256']:
            raise RuntimeError(f'Checksum mismatch: {name}')
        files = []
        with tarfile.open(fileobj=io.BytesIO(raw), mode='r:*') as source:
            for member in source.getmembers():
                leaf = Path(member.name).name.lower()
                if not member.isfile() or not leaf.startswith(('license', 'licence', 'copying', 'notice')):
                    continue
                content = source.extractfile(member).read()
                safe = member.name.replace('../', '__/')
                target = f'{name}-{version}/{safe}'
                out.writestr(target, content)
                files.append({'path': target, 'sha256': hashlib.sha256(content).hexdigest()})
        report.append({'name': name, 'version': version, 'sdist_url': sdist['url'],
                       'sdist_sha256': digest, 'notice_files': files})
    out.writestr('source-inventory.json', json.dumps(report, indent=2))
print(json.dumps([{'name': r['name'], 'version': r['version'], 'files': len(r['notice_files'])} for r in report]))
