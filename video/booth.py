"""Record the real cooling maintenance pipeline and produce a booth film within five minutes.

Requires the running CECO stack, Playwright/Chromium, Pillow and imageio-ffmpeg.
No mocked responses, database cleanup or post-repair fault reset are used.
    python video/booth.py            # sources -> reviewed ontology -> cooling recovery
    python video/booth.py --render experiments/BOOTH-20261013/<run>/timeline.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import subprocess
import sys
import time
import human
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests' / 'e2e'))
import maintenance_scenarios as M

URL = f"http://localhost:{M.V.ENV['PORT_AI_WEB']}" if 'PORT_AI_WEB' in M.V.ENV else 'http://localhost:38180'
DEST = ROOT / 'docs' / 'video'
KST = timezone(timedelta(hours=9))
# Each caption is deliberately short enough to read while following the screen.
SCENES = [
    ('normal', 20, '01  정상 운전', [
        '냉각수 필터가 막혔을 때, 어떻게 정상으로 되돌리는지 살펴봅니다.',
        '반응기에서 생기는 열은 냉각수가 밖으로 빼냅니다.',
        '온도와 물의 흐름을 센서로 측정해 화면에 표시합니다.']),
    ('fault', 20, '02  냉각 성능 저하', [
        '냉각수 필터에 찌꺼기가 쌓이는 상황을 재현합니다.',
        '필터가 막히면 물이 줄고, 반응기 온도가 올라갑니다.',
        '물의 흐름과 필터 앞뒤의 압력 차이가 원인을 찾는 단서입니다.']),
    ('pipeline', 22, '03  센서에서 이상 탐지까지', [
        '센서값은 현장 제어기와 수집기를 거쳐 중간 구역으로 전달됩니다.',
        '원본 기록을 보관하고, 분석 시스템이 이상 징후를 찾습니다.',
        '센서 이력 수집과 이상 탐지 작업의 연결 상태를 확인합니다.']),
    ('incident', 18, '04  하나의 사건으로 접수', [
        '같은 문제에서 발생한 여러 경보를 하나의 사건으로 묶습니다.',
        '담당자는 이 사건에서 분석과 정비의 진행 상황을 확인합니다.']),
    ('analysis', 40, '05  AI가 근거를 조사', [
        'AI는 경보가 발생한 당시의 센서값부터 확인합니다.',
        '설비의 연결 관계를 살펴보고, 이 설비에 맞는 정비 매뉴얼을 찾습니다.',
        '온도 상승과 유량 감소, 압력 차이 상승을 함께 살펴봅니다.',
        '모은 근거로 가능한 원인을 비교하고 정비 계획을 작성합니다.']),
    ('causes', 30, '06  원인 후보를 비교', [
        'AI의 정비 계획입니다. 센서 관측과 맞는 원인과 맞지 않는 원인을 비교합니다.',
        '물의 흐름이 줄고 필터의 압력 차이가 커져, 필터 막힘을 의심합니다.',
        '원인을 좁힌 뒤, 실제 정비에서 확인한 소견으로 판단을 확인합니다.']),
    ('options', 30, '07  정비 방법을 선택', [
        '고치는 방법을 비교합니다. 생산 영향과 정비 비용도 함께 봅니다.',
        '예비 필터로 전환하고 막힌 필터를 세척하면, 운전을 유지하며 정비할 수 있습니다.',
        '선택한 방법에 따라 작업 순서와 회복 확인 기준을 정합니다.']),
    ('approval', 15, '08  담당자가 확인하고 승인', [
        '담당자가 계획의 근거와 작업 순서를 확인한 뒤 승인합니다.',
        '승인된 작업 요청이 현장으로 전달되고 정비가 시작됩니다.']),
    ('repair', 25, '09  현장 정비를 실행', [
        '정비팀이 예비 필터로 전환하고, 막힌 필터를 분리해 세척합니다.',
        '작업 상태와 현장에서 확인한 소견이 화면으로 돌아옵니다.',
        '작업이 끝나면 실제 센서값이 회복되는지 확인합니다.']),
    ('recovery', 35, '10  안정적인 회복을 확인', [
        '작업 후 온도와 냉각수 흐름을 다시 관찰합니다.',
        '온도가 목표 범위로 내려오고, 물의 흐름이 기준 이상인지 확인합니다.',
        '정상 조건이 30초 이상 유지되어야 회복으로 판정합니다.']),
    ('report', 30, '11  작업 결과를 기록', [
        '회복이 확인되면, 무엇을 발견하고 고쳤는지 작업 보고서에 남깁니다.',
        '정비 전후 센서값과 예상했던 비용, 실제 결과를 비교합니다.',
        '이 기록은 다음 이상 상황에서 원인과 대응 방법을 검토할 근거가 됩니다.']),
    ('final', 15, '12  정상 운전으로 복귀', [
        '필터 막힘을 감지하고 원인을 찾아 정비한 뒤, 정상 운전으로 돌아왔습니다.',
        '사람이 확인하고 승인하면, 시스템이 작업을 연결하고 결과를 기록합니다.']),
]
assert sum(s[1] for s in SCENES) == 300


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding='utf-8')


async def poll(fn, predicate, timeout=420):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = await asyncio.to_thread(fn)
        if predicate(value):
            return value
        await asyncio.sleep(2)
    raise RuntimeError('실제 파이프라인 상태 대기 시간 초과')


async def record(knowledge=False, continue_ready=False):
    lock = M.single_instance()
    run_dir = ROOT / 'experiments' / 'BOOTH-20261013' / datetime.now(KST).strftime('run-%H%M%S')
    run_dir.mkdir(parents=True)
    result = {'scenario': 's1', 'fault': 'strainer_fouling', 'truth': 'FM-CW-STRAINER-CLOG', 'recorded_at': datetime.now(KST).isoformat()}
    pipeline = M.api('/api/operations/pipeline')
    if not pipeline.get('items') or not all(x['status'] == 'available' for x in pipeline['items']):
        raise RuntimeError(f'수집 경로 미준비: {pipeline}')
    if continue_ready:
        current=M.plant()
        assert not current['active_faults'] and not current.get('execution_active'),'직전 정비가 끝난 정상 상태만 이어서 녹화할 수 있습니다.'
        assert abs(current['readings']['TT-101']-current['commands']['temp_sp_c'])<=3 and current['readings']['FT-103']>=20,'온도·유량 정상 조건 확인 필요'
    else:
        await asyncio.to_thread(M.prepare)
    result['before'] = M.plant()
    timeline = []
    errors = []
    browser_actions = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(viewport={'width': 1920, 'height': 900}, record_video_dir=str(run_dir), record_video_size={'width': 1920, 'height': 900}, locale='ko-KR', timezone_id='Asia/Seoul')
        await human.install(context)
        page = await context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('request', lambda r: browser_actions.append({'method':r.method,'path':r.url.split(URL)[-1]}) if r.method=='POST' and ('/api/operations/' in r.url or '/simulation/fault' in r.url) else None)
        origin = time.monotonic()
        video = page.video
        await page.goto(URL, wait_until='networkidle')
        # Presentation-only: keep the existing process diagram from covering the card on scroll.
        await page.add_style_tag(content='.process-flow{position:relative!important;top:auto!important}html{scroll-behavior:smooth}')
        await page.get_by_text('공정 상태 수신 중', exact=True).wait_for()

        async def scene(key):
            if timeline:
                timeline[-1]['end'] = time.monotonic() - origin
            timeline.append({'id': key, 'start': time.monotonic() - origin})
            if key in ['causes','options','approval','repair','report']:
                box=await page.locator('.portal-response').bounding_box()
                if box:
                    x=int(box['x'])//2*2
                    timeline[-1]['focus_rect']=[x,0,min(1920-x,int(box['width'])+12)//2*2,700]
            print(f'SCENE {key}', flush=True)

        async def hold(seconds):
            await page.wait_for_timeout(seconds * 1000)

        async def focus(selector):
            loc = page.locator(selector).filter(visible=True).first
            await loc.wait_for(state='visible', timeout=30000)
            await human.focus(page,loc)

        async def stage(name):
            await page.locator(f'.process-flow g[role=button][aria-label^="{name}"]').click()
            await hold(1)

        if knowledge:
            from knowledge_story import film
            result['knowledge'],shot_details=await film(page,run_dir,scene,hold,focus,origin,M,URL)
            for shot in timeline:
                shot.update(shot_details.get(shot['id'],{}))
        await scene('normal')
        await human.click(page,page.locator('.portal-sidebar button').filter(has_text='운영 현황'))
        await focus('.key-readings')
        await hold(7)
        result['normal_state']=M.plant()
        await scene('fault')
        fault_at = time.time()
        await human.select(page,page.locator('#simulation-scenario'),value='strainer_fouling')
        await human.click(page,page.get_by_role('button', name='이상 발생', exact=True))
        await page.get_by_text('냉각수 필터 막힘이 발생했습니다.', exact=False).wait_for()
        await focus('.key-readings')
        await hold(17)
        result['fault_state'] = M.plant()
        await page.screenshot(path=str(run_dir / '02-fault.png'))
        await scene('pipeline')
        await human.click(page,page.locator('.pipeline-details > summary'))
        await focus('.pipeline-status')
        await hold(4)
        result['pipeline'] = M.api('/api/operations/pipeline')
        await human.click(page,page.locator('.pipeline-details > summary'))
        incident = await asyncio.to_thread(M.wait_incident, 'thermal', fault_at)
        result['incident'] = incident
        await scene('incident')
        await page.locator('.process-flow').wait_for()
        await focus('.guided-incident')
        await hold(5)
        await scene('analysis')
        await focus('.simple-trace')
        analysis_start=timeline[-1]['start']
        await hold(8)
        analysis_initial_end=time.monotonic()-origin
        run = await asyncio.to_thread(M.wait_run, incident['id'], since=fault_at)
        analysis_final_start=time.monotonic()-origin
        result['runs'] = [run]
        if run['status'] != 'awaiting_review':
            write_json(run_dir / 'failed-run.json', result)
            raise RuntimeError(f"AI 분석 미완료: {run['status']}")
        proposal = next(x for x in M.proposals(incident['id']) if x['origin'].split(':')[1] == run['id'] and x['status'] == 'pending')
        result['first_proposal'] = proposal
        if proposal['body']['action'] != 'maintenance_plan' or 'FM-CW-STRAINER-CLOG' not in proposal['plan'].get('treats', []):
            write_json(run_dir / 'failed-run.json', result)
            raise RuntimeError('실제 AI 계획이 냉각수 필터 막힘의 근본 정비와 일치하지 않습니다.')
        await hold(6)
        if analysis_final_start-analysis_initial_end>8:
            timeline[-1]['segments']=[{'start':analysis_start,'end':analysis_initial_end},{'start':max(analysis_initial_end,analysis_final_start-2),'end':time.monotonic()-origin}]
        await scene('causes')
        await human.click(page,page.locator('.guide-details > summary').last)
        await focus('.plan-card')
        await hold(3)
        await focus('.plan-card section:has(h5:text("원인 판단"))')
        await hold(10)
        await page.screenshot(path=str(run_dir / '06-causes.png'))
        await scene('options')
        await focus('.plan-card section:has(h5:text("대안 손익 비교"))')
        await hold(6)
        await focus('.plan-card section:has(h5:text("정비 단계"))')
        await hold(4)
        await scene('approval')
        for detail in await page.locator('.guide-details[open]').all():
            await human.click(page,detail.locator(':scope > summary'))
        await focus('.guide-approval')
        await human.fill(page,page.locator('#guided-review-note'),'센서 변화와 판단 근거를 확인했습니다. 예비 필터 전환과 막힌 필터 세척을 승인합니다.')
        await hold(3)
        approval_at = time.monotonic()
        await human.click(page,page.get_by_role('button', name='정비 승인', exact=True))
        timeline[-1]['approval_offset_s'] = time.monotonic() - origin - timeline[-1]['start']
        await hold(2)
        await scene('repair')
        await focus('.guide-repair')
        def current():
            return next(x for x in M.proposals(incident['id']) if x['id'] == proposal['id'])
        current_p = await poll(current, lambda x: (x.get('result') or {}).get('plan_state', {}).get('phase') == 'verify' or x['status'] in ('resolved', 'unresolved'))
        if current_p['status'] == 'unresolved':
            write_json(run_dir / 'failed-run.json', current_p)
            raise RuntimeError('정비 실패: 승인 재전송 없이 기록을 확인해야 합니다.')
        result['repair_wall_s'] = time.monotonic() - approval_at
        await scene('recovery')
        await focus('.key-readings')
        done = await poll(current, lambda x: x['status'] in ('resolved', 'unresolved'))
        result['final'] = done
        result['report'] = M.report(done)
        result['after'] = M.plant()
        result['chosen_matches_truth'] = 'FM-CW-STRAINER-CLOG' in done['plan'].get('treats', [])
        result['elapsed_s'] = time.time() - fault_at
        # No fault-clear here: the actual maintenance must have removed the fault.
        if done['status'] != 'resolved' or result['report'].get('outcome') != 'recovered' or result['after']['active_faults']:
            write_json(run_dir / 'failed-run.json', result)
            raise RuntimeError('현장 정비 후 실제 회복 기준 미충족')
        await hold(3)
        await page.screenshot(path=str(run_dir / '10-recovery.png'))
        await scene('report')
        await focus('.guide-report')
        await hold(3)
        await human.click(page,page.locator('.guide-details > summary').last)
        await focus('.plan-card .report')
        await hold(6)
        await page.screenshot(path=str(run_dir / '11-report.png'))
        await scene('final')
        for detail in await page.locator('.guide-details[open]').all():
            await human.click(page,detail.locator(':scope > summary'))
        await focus('.key-readings')
        await hold(5)
        await page.screenshot(path=str(run_dir / '12-normal.png'))
        timeline[-1]['end'] = time.monotonic() - origin
        await context.close()
        result['browser_errors'] = errors
        result['browser_actions'] = browser_actions
        result['presentation_actions']=human.actions
        assert not any(x['path'].endswith('/analyze') for x in browser_actions),'Normal flow must analyze automatically'
        assert sum(x['path'].endswith('/decision') for x in browser_actions)==1,'Exactly one human approval is required'
        raw = await video.path()
        await browser.close()
    lock.close()
    write_json(run_dir / 'verification.json', result)
    meta = {'raw': str(raw), 'scenes': timeline, 'verification': str(run_dir / 'verification.json')}
    if knowledge:
        from knowledge_story import INTRO
        durations={'normal':10,'fault':24,'pipeline':8,'incident':8,'analysis':32,'causes':16,'options':14,'approval':14,'repair':20,'recovery':36,'report':14,'final':8}
        meta['storyboard']=INTRO+[(key,durations[key],f'{idx:02}  '+title.split('  ',1)[-1],captions) for idx,(key,_,title,captions) in enumerate(SCENES,6)]
        for idx,item in enumerate(meta['storyboard']):
            if item[0]=='normal':
                meta['storyboard'][idx]=('normal',10,'06  하나의 포털에서 설비 확인',[
                    '같은 포털에서 설비 상태를 실시간으로 확인하고, 제어 패널도 바로 열 수 있습니다.'])
        # Keep the sensor recovery continuous, including its real hold counter.
        recovery=next(s for s in timeline if s['id']=='recovery')
        actual_recovery=math.ceil(recovery['end']-recovery['start'])
        if actual_recovery>36:
            meta['storyboard']=[(k,max(d,actual_recovery) if k=='recovery' else d,t,c) for k,d,t,c in meta['storyboard']]
        from pacing import fit
        meta=fit(meta)
    write_json(run_dir / 'timeline.json', meta)
    print(f'RECOVERY VERIFIED: {run_dir}', flush=True)
    return run_dir / 'timeline.json'


def ass_time(seconds):
    centis = round(seconds * 100)
    return f'{centis//360000}:{centis//6000%60:02}:{centis//100%60:02}.{centis%100:02}'


def srt_time(seconds):
    millis = round(seconds * 1000)
    return f'{millis//3600000:02}:{millis//60000%60:02}:{millis//1000%60:02},{millis%1000:03}'


def render(timeline_path, captions_only=False, prepare_only=False):
    import imageio_ffmpeg
    from PIL import ImageFont
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    meta = json.loads(timeline_path.read_text(encoding='utf-8'))
    run_dir = timeline_path.parent
    DEST.mkdir(parents=True, exist_ok=True)
    final = DEST / 'ceco-booth-5min.mp4'
    ass = ['[Script Info]', 'ScriptType: v4.00+', 'PlayResX: 1920', 'PlayResY: 1080', 'WrapStyle: 0', '', '[V4+ Styles]',
           'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
           'Style: Caption,Malgun Gothic,72,&H00FFFFFF,&H00FFFFFF,&H00101C28,&H00101C28,-1,0,0,0,100,100,0,0,1,0,0,5,90,90,0,1',
           'Style: Chapter,Malgun Gothic,16,&H00CCE8F0,&H00FFFFFF,&H00101C28,&H00101C28,-1,0,0,0,100,100,0,0,1,0,0,1,40,40,7,1',
           'Style: Note,Malgun Gothic,14,&H00C9C9C9,&H00FFFFFF,&H00101C28,&H00101C28,0,0,0,0,100,100,0,0,1,0,0,3,40,40,8,1',
           '', '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    srt = []
    pos = 0
    chapters = []
    cues = []
    caption_font = ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', 72)
    parts = []
    from script_ko import polished
    storyboard=polished(meta.get('storyboard',SCENES))
    previous=json.loads((DEST/'ceco-booth-5min.timeline.json').read_text(encoding='utf-8')) if captions_only else None
    if captions_only:
        assert Path(previous['source']).resolve()==timeline_path.resolve(),'자막만 편집할 때는 기존 원본 타임라인을 사용하세요.'
        assert len(previous['chapters'])==len(storyboard)
    assert len(storyboard)==len(meta['scenes'])
    total_duration=sum(s[1] for s in storyboard)
    assert 0<total_duration<=300
    for idx, ((key, duration, title, captions), shot) in enumerate(zip(storyboard, meta['scenes']), 1):
        assert key == shot['id']
        segments=shot.get('segments') or [{'start':shot['start'],'end':shot['end']}]
        raw_source=shot.get('raw',meta['raw'])
        actual = sum(s['end']-s['start'] for s in segments)
        # Keep real-time motion when shorter; extend only the final verified frame.
        speed = max(1.0, actual / duration)
        if meta.get('human_pacing'):
            assert speed<=1.12,(key,'Pointer and scrolling must stay close to filmed speed',speed)
        part = run_dir / f'part-{idx:02}.mp4'
        frames = duration * 25
        view=''
        if shot.get('focus_rect'):
            x,y,w,h=shot['focus_rect']
            assert 0<=x and 0<=y and 0<w<=1920-x and 0<h<=900-y
            view=f'crop={w}:{h}:{x}:{y},scale=1920:900:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=1920:900:(ow-iw)/2:(oh-ih)/2:color=0x101c28,'
        vf = f'setpts=(PTS-STARTPTS)/{speed:.9f},fps=25:start_time=0,tpad=stop_mode=clone:stop_duration={duration},trim=end_frame={frames},setpts=N/(25*TB),{view}pad=1920:1080:0:0:color=0x101c28' 
        # Disable B-frame reordering: this bundled Windows encoder otherwise
        # omits 40 ms from each MP4's duration despite encoding all frames.
        if captions_only:
            old=previous['chapters'][idx-1]
            assert old.get('focus_rect')==shot.get('focus_rect'),'화면 확대 영역이 변경되어 장면을 다시 인코딩해야 합니다.'
            assert part.exists() and (old['id'],old['duration'],old['actual_s'],old['speed'])==(key,duration,round(actual,2),round(speed,3)),'원본 장면이 변경되어 다시 인코딩해야 합니다.'
        elif len(segments)>1:
            selected=run_dir/f'selected-{idx:02}.mp4'
            filters=[]
            for si,segment in enumerate(segments):
                filters.append(f"[0:v]trim=start={segment['start']}:end={segment['end']},setpts=PTS-STARTPTS[v{si}]")
            filters.append(''.join(f'[v{si}]' for si in range(len(segments)))+f'concat=n={len(segments)}:v=1:a=0[out]')
            with (run_dir/f'select-{idx:02}.log').open('w',encoding='utf-8') as log:
                subprocess.run([ff,'-y','-i',raw_source,'-filter_complex',';'.join(filters),'-map','[out]','-an','-c:v','libx264','-bf','0','-preset','veryfast','-crf','18','-threads','4',str(selected)],stdout=log,stderr=log,check=True)
            source=str(selected);source_start=0
        else:source=raw_source;source_start=segments[0]['start']
        if not captions_only:
            cmd = [ff, '-y', '-ss', str(source_start), '-t', str(actual), '-i', source, '-vf', vf, '-an', '-frames:v', str(frames), '-r', '25', '-fps_mode', 'cfr', '-c:v', 'libx264', '-bf', '0', '-preset', 'veryfast', '-crf', '19', '-pix_fmt', 'yuv420p', '-threads', '4', str(part)]
            with (run_dir / f'encode-{idx:02}.log').open('w', encoding='utf-8') as log:
                subprocess.run(cmd, stdout=log, stderr=log, check=True)
        parts.append(part)
        note = '가상 공정 · 실제 실행 화면'
        if shot.get('focus_rect'):note+=' · 화면 확대'
        if len(segments)>1:
            note+=' · 대기 구간 생략'
        if speed > 1.05:
            note += f' · {speed:.1f}배속 편집'
        elif actual < duration - 1:
            note += ' · 마지막 화면 유지'
        ass.append(f'Dialogue: 0,{ass_time(pos)},{ass_time(pos+duration)},Chapter,,0,0,0,,{title}')
        ass.append(f'Dialogue: 0,{ass_time(pos)},{ass_time(pos+duration)},Note,,0,0,0,,{note}')
        bounds = [c * duration / len(captions) for c in range(len(captions)+1)]
        if key == 'approval':
            # Approval must have happened before the caption describes execution.
            # The actual filmed approval offset defines this boundary.
            boundary = max(2, math.ceil(shot.get('approval_offset_s', 9.2)/speed))
            assert boundary<=duration-2,'승인 뒤 자막을 읽을 시간을 확보하도록 장면을 다시 편집하세요.'
            bounds = [0, boundary, duration]
        elif 'caption_split_actual_s' in shot:
            assert len(captions)==2
            boundary=max(3,math.ceil(shot['caption_split_actual_s']/speed))
            assert boundary<=duration-3,'실제 동작 뒤 자막을 읽을 시간을 확보하도록 장면을 다시 편집하세요.'
            bounds=[0,boundary,duration]
        for c_idx, caption in enumerate(captions):
            start = pos + bounds[c_idx]
            end = pos + bounds[c_idx+1]
            # Explicit line break keeps the subtitle comfortably within the reserved band.
            words = caption.split(' ')
            split = min(range(1,len(words)), key=lambda n: abs(caption_font.getlength(' '.join(words[:n]))-caption_font.getlength(' '.join(words[n:])))) if '\n' not in caption and caption_font.getlength(caption) > 1720 else 0
            text = caption.replace('\n',r'\N') if '\n' in caption else ' '.join(words[:split]) + r'\N' + ' '.join(words[split:]) if split else caption
            assert len(text.split(r'\N'))<=2
            assert all(caption_font.getlength(line) <= 1720 for line in text.split(r'\N'))
            ass.append(f'Dialogue: 1,{ass_time(start)},{ass_time(end)},Caption,,0,0,0,,{{\\pos(960,987)}}{text}')
            srt.extend([str(len(srt)//4+1), f'{srt_time(start)} --> {srt_time(end)}', text.replace(r'\N','\n'), ''])
            cues.append({'scene': key, 'start': round(start, 3), 'end': round(end, 3), 'text': caption})
        chapters.append({'id':key,'start':pos,'duration':duration,'title':title,'actual_s':round(actual,2),'speed':round(speed,3),'captions':captions,'focus_rect':shot.get('focus_rect')})
        pos += duration
        print(f'{"CAPTION" if captions_only else "ENCODE"} {idx}/{len(storyboard)} {key}', flush=True)
    subtitle_path = run_dir / 'subtitles.ass'
    subtitle_path.write_text('\n'.join(ass), encoding='utf-8-sig')
    (DEST / 'subtitles').mkdir(exist_ok=True)
    (DEST / 'subtitles' / 'ceco-booth-5min.srt').write_text('\n'.join(srt), encoding='utf-8-sig')
    (DEST/'ceco-booth-5min-script.txt').write_text('\n\n'.join(
        f"[{srt_time(cue['start']).split(',')[0]}–{srt_time(cue['end']).split(',')[0]}]\n{cue['text']}" for cue in cues),encoding='utf-8-sig')
    playlist = run_dir / 'concat.txt'
    playlist.write_text('\n'.join("file '"+part.as_posix()+"'" for part in parts), encoding='utf-8')
    if prepare_only:
        return subtitle_path
    # Run from the ASS directory to avoid Windows drive-colon escaping in the filter.
    with (run_dir / 'final-encode.log').open('w', encoding='utf-8') as log:
        subprocess.run([ff,'-y','-f','concat','-safe','0','-i',str(playlist),'-vf','ass=subtitles.ass','-an','-r','25','-fps_mode','cfr','-c:v','libx264','-bf','0','-preset','veryfast','-crf','19','-pix_fmt','yuv420p','-threads','4','-t',str(total_duration),'-movflags','+faststart',str(final)],cwd=run_dir,stdout=log,stderr=log,check=True)
    write_json(DEST / 'ceco-booth-5min.timeline.json', {'duration_s':total_duration,'source':str(timeline_path),'chapters':chapters,'cues':cues,'layout':{'process_bottom_px':900,'caption_band_top_px':900,'caption_band_bottom_px':1080,'caption_font_px':72,'caption_alignment':'center','caption_anchor_px':[960,987],'visual_center_px':[960,990],'single_burned_caption':True}})
    print(f'VIDEO {final} ({final.stat().st_size/1e6:.1f} MB)',flush=True)
    return final


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--render',type=Path)
    ap.add_argument('--record-only',action='store_true')
    ap.add_argument('--captions-only',action='store_true')
    ap.add_argument('--knowledge',action='store_true',default=True)
    ap.add_argument('--continue-ready',action='store_true',help='직전 검증에서 정상 복구한 설비를 초기화 없이 이어서 녹화')
    ap.add_argument('--maintenance-only',action='store_false',dest='knowledge')
    args = ap.parse_args()
    timeline = args.render or asyncio.run(record(knowledge=args.knowledge,continue_ready=args.continue_ready))
    if not args.record_only:
        render(timeline.resolve(),captions_only=args.captions_only)
