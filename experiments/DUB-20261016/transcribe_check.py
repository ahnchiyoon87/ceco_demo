"""Independently transcribe the actual mixed speech for omissions and timing."""
import difflib, json, os, pathlib, re, subprocess, urllib.request, urllib.error, uuid
import imageio_ffmpeg
ROOT = pathlib.Path(__file__).resolve().parent
cache = ROOT / 'asr.json'
if not cache.exists():
    mp3 = ROOT / 'narration-asr.mp3'
    r = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-v', 'error', '-y', '-i', str(ROOT/'narration.wav'),
                        '-ac', '1', '-ar', '24000', '-c:a', 'libmp3lame', '-b:a', '96k', str(mp3)], capture_output=True)
    assert r.returncode == 0
    boundary = '----CECO' + uuid.uuid4().hex
    body = bytearray()
    for name, value in {'model_id':'scribe_v2', 'language_code':'kor', 'tag_audio_events':'false', 'diarize':'false'}.items():
        body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="narration.mp3"\r\nContent-Type: audio/mpeg\r\n\r\n'.encode())
    body.extend(mp3.read_bytes()); body.extend(f'\r\n--{boundary}--\r\n'.encode())
    req = urllib.request.Request('https://api.elevenlabs.io/v1/speech-to-text', data=bytes(body),
        headers={'xi-api-key':os.environ['ELEVENLABS_API_KEY'], 'Content-Type':f'multipart/form-data; boundary={boundary}'})
    try:
        with urllib.request.urlopen(req,timeout=180) as response: result=json.load(response)
    except urllib.error.HTTPError as e:
        print('ASR HTTP failure',e.code);raise SystemExit(1)
    cache.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
result=json.loads(cache.read_text(encoding='utf8'))
d=json.loads((ROOT/'narration.json').read_text(encoding='utf8'));rows=[]
def norm(text):
    return re.sub(r'[^가-힣a-z0-9]','',text.lower().replace('AI','에이아이').replace('ai','에이아이').replace('30','삼십').replace('삼 십','삼십'))
for c in d['cues']:
    heard=''.join(w['text'] for w in result['words'] if w['type']=='word' and c['start'] <= (w['start']+w['end'])/2 < c['end'])
    ratio=difflib.SequenceMatcher(None,norm(c['speech_text']),norm(heard)).ratio()
    row={'id':c['id'],'expected':c['speech_text'],'transcribed':heard,'similarity':round(ratio,4)};rows.append(row)
    print(json.dumps(row,ensure_ascii=False),flush=True)
(ROOT/'asr-comparison.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
