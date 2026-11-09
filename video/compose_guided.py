"""Keep the verified knowledge introduction and use the final portal recording.

Each shot retains its original recording, timestamps, publication/approval offsets,
and verification. This edits two real runs; it never recreates equipment events.
"""
import argparse
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def compose(knowledge_path, operations_path, output):
    knowledge, operations = read(knowledge_path), read(operations_path)
    kv, ov = read(Path(knowledge['verification'])), read(Path(operations['verification']))
    assert kv['knowledge']['publication']['status'] == 'published'
    assert not kv['knowledge']['publication']['duplicate']
    assert ov['report']['outcome'] == 'recovered' and ov['report']['recovery']['held_s'] >= 30
    assert not ov['after']['active_faults'] and not ov['browser_errors']
    assert not any(x['path'].endswith('/analyze') for x in ov['browser_actions'])
    assert sum(x['path'].endswith('/decision') for x in ov['browser_actions']) == 1
    shots = [dict(s, raw=s.get('raw', knowledge['raw'])) for s in knowledge['scenes'][:5]]
    shots += [dict(s, raw=s.get('raw', operations['raw'])) for s in operations['scenes']]
    for shot in shots:
        if shot['id'] in ['causes','options','approval','repair','recovery','report']:
            shot['focus_rect']=[960,0,960,700]
    assert [s['id'] for s in shots] == [s[0] for s in knowledge['storyboard']]
    output.mkdir(parents=True, exist_ok=True)
    verification = dict(ov, knowledge=kv['knowledge'], source_recordings={
        'knowledge': str(knowledge_path.resolve()), 'operations': str(operations_path.resolve())})
    vp = output / 'verification.json'
    vp.write_text(json.dumps(verification, ensure_ascii=False, indent=2), encoding='utf-8')
    metadata = dict(operations, scenes=shots, storyboard=knowledge['storyboard'], verification=str(vp.resolve()),
                    source_recordings=verification['source_recordings'])
    path = output / 'timeline.json'
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    return path


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--knowledge-source', type=Path, required=True)
    ap.add_argument('--operations-source', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    print(compose(args.knowledge_source, args.operations_source, args.output))
