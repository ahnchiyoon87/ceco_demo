"""Generate only the requested narration; credentials stay in process memory."""
import argparse, base64, concurrent.futures, json, os, pathlib, time
import urllib.error, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
MANIFEST = json.loads((ROOT / 'narration.json').read_text(encoding='utf8'))

def generate(cue):
    number = cue['id']
    target = ROOT / 'audio' / f'{number:02}.mp3'
    meta = target.with_suffix('.json')
    if target.exists() and meta.exists():
        old = json.loads(meta.read_text(encoding='utf8'))
        if old['text'] == cue['speech_text'] and old['model_id'] == MANIFEST['model_id']:
            return {'id': number, 'cached': True}
        raise RuntimeError(f'Preserve existing generation {number}; archive before replacing')
    target.parent.mkdir(exist_ok=True)
    index = number - 1
    body = {'text': cue['speech_text'], 'model_id': MANIFEST['model_id'],
            'language_code': 'ko', 'voice_settings': MANIFEST['voice_settings'],
            'seed': 26101600 + number,
            'previous_text': MANIFEST['cues'][index - 1]['speech_text'] if index else '',
            'next_text': MANIFEST['cues'][index + 1]['speech_text'] if index + 1 < len(MANIFEST['cues']) else ''}
    url = 'https://api.elevenlabs.io/v1/text-to-speech/' + MANIFEST['voice_id'] + '/with-timestamps?output_format=mp3_44100_128'
    req = urllib.request.Request(url, data=json.dumps(body).encode('utf8'),
                                 headers={'xi-api-key': os.environ['ELEVENLABS_API_KEY'], 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=150) as response:
            result = json.load(response)
            request_id = response.headers.get('request-id')
            billed = response.headers.get('character-cost')
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read()).get('detail', {})
            status = detail.get('status', 'unknown') if isinstance(detail, dict) else 'validation'
        except Exception:
            status = 'unparsed'
        raise RuntimeError(f'ElevenLabs HTTP {e.code}, status {status}, cue {number}') from None
    audio = base64.b64decode(result.pop('audio_base64'))
    assert len(audio) > 1000 and result.get('alignment'), f'Missing sound/alignment: {number}'
    target.write_bytes(audio)
    meta.write_text(json.dumps({'id': number, 'text': cue['speech_text'],
        'model_id': MANIFEST['model_id'], 'voice_id': MANIFEST['voice_id'],
        'request_id': request_id, 'billed_characters': billed, **result}, ensure_ascii=False, indent=2), encoding='utf8')
    alignment = result['alignment']
    return {'id': number, 'audio_s': round(max(alignment['character_end_times_seconds']), 3), 'billed': billed}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('ids', nargs='*', type=int)
    args = parser.parse_args()
    cues = [c for c in MANIFEST['cues'] if not args.ids or c['id'] in args.ids]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for result in pool.map(generate, cues):
            print(json.dumps(result), flush=True)
