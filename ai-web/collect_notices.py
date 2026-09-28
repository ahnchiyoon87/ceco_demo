"""Collect installed production npm package notices without network or secrets.

Run after npm ci, before the production build. Preserve verbatim license texts.
This inventory does not cover backend/container or separately owned source code.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
lock = json.loads((ROOT / 'package-lock.json').read_text(encoding='utf-8'))
parts = ['ASSEMBLY frontend third-party notices',
         'Installed production dependencies from package-lock.json.',
         'Backend/container packages and company-owned reused source are outside this file.\n']
missing = []
count = 0
for relative, meta in sorted(lock['packages'].items()):
    if not relative or meta.get('dev'):
        continue
    directory = ROOT / relative
    package = json.loads((directory / 'package.json').read_text(encoding='utf-8'))
    files = sorted(p for p in directory.iterdir() if p.is_file() and
                   p.name.lower().split('.')[0] in {'license', 'licence', 'copying', 'notice'})
    if not files:
        missing.append(relative)
        continue
    count += 1
    parts += ['=' * 72, f"{package['name']} {package['version']}",
              'Declared license: ' + str(package.get('license', meta.get('license', 'not declared')))]
    for path in files:
        parts += [f'--- {path.name} ---', path.read_text(encoding='utf-8')]
if missing:
    raise SystemExit('Missing license texts; output not updated: ' + ', '.join(missing))
output = ROOT / 'public' / 'THIRD-PARTY-NOTICES.txt'
output.parent.mkdir(exist_ok=True)
output.write_text('\n\n'.join(parts) + '\n', encoding='utf-8')
print(json.dumps({'packages': count, 'output': str(output), 'missing': missing}))
