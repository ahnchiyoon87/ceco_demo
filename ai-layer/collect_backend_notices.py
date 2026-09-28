"""Inventory installed Python distribution notices; run in the knowledge image.

Only reads installed package metadata/license files. No environment, prompts,
keys, uploaded documents, or database contents are read. Output is an evidence
bundle, not a declaration of complete redistribution compliance.
"""
import hashlib
from importlib.metadata import distributions
import json
from pathlib import Path
import re
import sys
import zipfile

output = Path(sys.argv[1])
entries = []
with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
    for dist in sorted(distributions(), key=lambda d: d.metadata.get('Name', '').lower()):
        name = dist.metadata.get('Name', 'unnamed')
        entry = {'name': name, 'version': dist.version,
                 'license_expression': dist.metadata.get('License-Expression'),
                 'license_declared': dist.metadata.get('License'), 'files': []}
        prefix = re.sub(r'[^a-zA-Z0-9_.-]', '_', name) + '-' + dist.version
        for item in dist.files or []:
            filename = Path(str(item)).name.lower()
            license_directory = any('license' in part.lower() for part in Path(str(item)).parts[:-1])
            if not (license_directory or filename.startswith(('license', 'licence', 'copying', 'notice')) or
                    filename in {'copyright', 'authors'}):
                continue
            path = Path(dist.locate_file(item))
            if not path.is_file():
                continue
            data = path.read_bytes()
            archive_path = prefix + '/' + str(item).replace('\\', '/').replace('../', '__/')
            archive.writestr(archive_path, data)
            entry['files'].append({'path': archive_path, 'sha256': hashlib.sha256(data).hexdigest()})
        entries.append(entry)
    report = {'scope': 'Installed Python distributions in the knowledge image only',
              'not_covered': ['OS packages', 'other container images', 'company-owned source authorization'],
              'packages': entries,
              'without_license_files': [x['name'] for x in entries if not x['files']]}
    archive.writestr('inventory.json', json.dumps(report, ensure_ascii=False, indent=2))
print(json.dumps({'distributions': len(entries),
                  'with_notice_files': sum(bool(x['files']) for x in entries),
                  'without_license_files': report['without_license_files']}))
