"""Place real generated speech and polished captions on the source video clock."""
import array, json, math, pathlib, re, subprocess, wave
import imageio_ffmpeg
from PIL import ImageFont

ROOT = pathlib.Path(__file__).resolve().parent
FF = imageio_ffmpeg.get_ffmpeg_exe()
D = json.loads((ROOT / 'narration.json').read_text(encoding='utf8'))
RATE = 48000
font = ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', 72)

def run(args):
    r = subprocess.run([FF, '-hide_banner', '-nostats', *args], capture_output=True)
    assert r.returncode == 0, r.stderr.decode(errors='replace')[-2000:]
    return r

def wrapped(text):
    if font.getlength(text) <= 1710:
        return [text]
    words = text.split(); options = []
    for split in range(1, len(words)):
        left, right = ' '.join(words[:split]), ' '.join(words[split:])
        a, b = font.getlength(left), font.getlength(right)
        if max(a, b) <= 1710:
            # Prefer a natural clause break when it does not create a short orphan.
            score = abs(a-b) + (0 if left.endswith((',', '.', '?')) else 400)
            options.append((score, [left, right]))
    assert options, ('Caption needs another sentence break', text)
    lines = min(options, key=lambda x:x[0])[1]
    assert all(font.getlength(line) <= 1720 for line in lines)
    return lines

def ass_time(s):
    n = round(s * 100)
    return f'{n//360000}:{n//6000%60:02}:{n//100%60:02}.{n%100:02}'

def srt_time(s):
    n = round(s * 1000)
    return f'{n//3600000:02}:{n//60000%60:02}:{n//1000%60:02},{n%1000:03}'

if __name__ == '__main__':
    audio = bytearray(round(D['duration_s'] * RATE) * 2)
    last_end = 0; rows = []; captions = []
    for c in D['cues']:
        raw = ROOT / 'audio' / f'{c["id"]:02}.mp3'
        a = json.loads(raw.with_suffix('.json').read_text(encoding='utf8'))['alignment']
        assert ''.join(a['characters']) == c['speech_text'], ('Unexpected alignment normalization', c['id'])
        letters = [i for i, ch in enumerate(a['characters']) if any(x.isalnum() for x in ch)]
        lo = max(0, a['character_start_times_seconds'][letters[0]] - .06)
        hi = a['character_end_times_seconds'][letters[-1]] + .10
        available = c['end'] - c['start'] - .40
        speed = max(1, (hi - lo) / available)
        assert speed <= 1.12, ('Rewrite rather than rush', c['id'], speed)
        placed = c['start'] + .25
        expected_len = (hi - lo) / speed
        af = (f'atrim=start={lo:.6f}:end={hi:.6f},asetpts=PTS-STARTPTS,'
              f'atempo={speed:.8f},afade=t=in:d=0.008,'
              f'afade=t=out:st={max(0,expected_len-.012):.6f}:d=0.012')
        pcm = run(['-v', 'error', '-i', str(raw), '-af', af, '-ar', str(RATE), '-ac', '1', '-f', 's16le', 'pipe:1']).stdout
        offset = round(placed * RATE) * 2
        actual_end = placed + len(pcm) / 2 / RATE
        assert placed >= last_end and actual_end <= c['end'] - .08, (c['id'], actual_end, c['end'])
        audio[offset:offset + len(pcm)] = pcm
        last_end = actual_end
        parts = list(re.finditer(r'[^.!?]+[.!?](?:\s+|$)', c['text']))
        assert ''.join(m.group() for m in parts) == c['text']
        for p in parts:
            display = p.group().strip()
            before = c['text'][:p.start()] + p.group()[:len(p.group()) - len(p.group().lstrip())]
            char_index = len(before.replace('AI', '에이아이').replace('30초', '삼십 초'))
            onset = placed + max(0, a['character_start_times_seconds'][char_index] - lo) / speed
            captions.append({'scene': c['scene'], 'parent_cue': c['id'], 'start': max(c['start'], onset - .12),
                             'end': c['end'] - .04, 'text': display, 'lines': wrapped(display)})
        rows.append({'id': c['id'], 'scene': c['scene'], 'source_window': [c['start'], c['end']],
                     'speech_start': placed, 'speech_end': actual_end,
                     'trim': [lo, hi], 'time_stretch': speed})
    for i, c in enumerate(captions[:-1]):
        c['end'] = min(c['end'], captions[i+1]['start'] - .01)
    unmastered = ROOT / 'narration-unmastered.wav'
    with wave.open(str(unmastered), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(audio)
    meter = run(['-i', str(unmastered), '-af', 'loudnorm=I=-16:TP=-1.5:LRA=7:print_format=json', '-f', 'null', '-'])
    info = meter.stderr.decode(errors='replace')
    m = re.search(r'\{\s*"input_i".*?\}', info, re.S); assert m, info[-1000:]
    loud = json.loads(m.group())
    (ROOT / 'loudness-pass1.json').write_text(json.dumps(loud, indent=2), encoding='utf8')
    filt = ('loudnorm=I=-16:TP=-1.5:LRA=7:linear=true:'
            f'measured_I={loud["input_i"]}:measured_TP={loud["input_tp"]}:'
            f'measured_LRA={loud["input_lra"]}:measured_thresh={loud["input_thresh"]}:'
            f'offset={loud["target_offset"]}:print_format=json')
    master = run(['-v', 'info', '-y', '-i', str(unmastered), '-af', filt,
                  '-ar', str(RATE), '-ac', '1', '-c:a', 'pcm_s16le', str(ROOT / 'narration.wav')])
    (ROOT / 'mastering.log').write_bytes(master.stderr)
    old_ass = pathlib.Path('D:/work/study/ceco_demo/experiments/BOOTH-20261013/natural-final/subtitles.ass').read_text(encoding='utf-8-sig')
    ass = [line for line in old_ass.splitlines() if not line.startswith('Dialogue:') or ',Caption,' not in line]
    srt = []
    for i, c in enumerate(captions, 1):
        lines = '\\N'.join(c['lines'])
        ass.append(f'Dialogue: 1,{ass_time(c["start"])},{ass_time(c["end"])},Caption,,0,0,0,,{{\\pos(960,987)}}{lines}')
        srt.append(f'{i}\n{srt_time(c["start"])} --> {srt_time(c["end"])}\n' + '\n'.join(c['lines']) + '\n')
    (ROOT / 'dub-subtitles.ass').write_text('\n'.join(ass) + '\n', encoding='utf8')
    (ROOT / 'dub-subtitles.srt').write_text('\n'.join(srt), encoding='utf8')
    (ROOT / 'sync.json').write_text(json.dumps({'duration_s': D['duration_s'], 'audio': rows, 'captions': captions,
        'caption_font': 'Malgun Gothic Bold', 'caption_px': 72, 'band': [0,900,1920,1080],
        'single_layer': True, 'original_ui_frames_preserved': True}, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({'segments': len(rows), 'captions': len(captions),
                     'maximum_time_stretch': max(x['time_stretch'] for x in rows), 'duration_s': D['duration_s']}), flush=True)
