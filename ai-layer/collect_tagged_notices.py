"""Preserve missing dependency notices from exact upstream version tags.

Resolve each tag to a commit, download only named notice files, and verify
the resulting archive. No upstream code is executed or extracted.
"""
import hashlib
import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from zipfile import ZipFile, ZIP_DEFLATED


PACKAGES = [
    ('deepagents', '0.5.3', 'langchain-ai/deepagents', 'deepagents==0.5.3', ['LICENSE']),
    ('langchain-core', '1.2.30', 'langchain-ai/langchain', 'langchain-core==1.2.30', ['LICENSE']),
    ('langsmith', '0.7.32', 'langchain-ai/langsmith-sdk', 'v0.7.32', ['LICENSE']),
    ('sqlite-vec', '0.1.9', 'asg017/sqlite-vec', 'v0.1.9', ['LICENSE-MIT', 'LICENSE-APACHE']),
]


def read(url):
    with urlopen(Request(url, headers={'User-Agent': 'CECO-notice-collector'}), timeout=30) as response:
        return response.read()


def main():
    records, contents = [], {}
    for name, version, repo, tag, filenames in PACKAGES:
        ref_url = f'https://api.github.com/repos/{repo}/commits/{quote(tag, safe="")}'
        commit = json.loads(read(ref_url))['sha']
        record = dict(name=name, version=version, repository=repo, tag=tag,
                      commit=commit, commit_lookup_url=ref_url, files=[])
        for filename in filenames:
            url = f'https://raw.githubusercontent.com/{repo}/{commit}/{filename}'
            body = read(url)
            if not body.strip():
                raise RuntimeError(f'Empty notice: {url}')
            path = f'{name}-{version}/{filename}'
            contents[path] = body
            record['files'].append(dict(path=path, source_url=url,
                                        sha256=hashlib.sha256(body).hexdigest()))
        records.append(record)
    target = Path(__file__).resolve().parent.parent / 'docs/ai-work/backend-tagged-notices.zip'
    with ZipFile(target, 'w', ZIP_DEFLATED) as archive:
        for path, body in contents.items():
            archive.writestr(path, body)
        archive.writestr('tagged-inventory.json', json.dumps(records, indent=2))
    with ZipFile(target) as archive:
        saved = json.loads(archive.read('tagged-inventory.json'))
        for record in saved:
            for item in record['files']:
                assert hashlib.sha256(archive.read(item['path'])).hexdigest() == item['sha256']
    print(json.dumps({'packages': len(records), 'notice_files': len(contents),
                      'archive_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                      'verified': True}))


if __name__ == '__main__':
    main()
