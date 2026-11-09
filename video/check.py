"""Decode the complete film, check browser playback, and extract review frames."""
import json
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'docs'/'video'
OUT=ROOT/'experiments'/'BOOTH-20261013'/'video-quality'
OUT.mkdir(parents=True,exist_ok=True)
video=DEST/'ceco-booth-5min.mp4'
ff=imageio_ffmpeg.get_ffmpeg_exe()
decoded=subprocess.run([ff,'-v','error','-i',str(video),'-map','0:v:0','-f','null','-'],capture_output=True,text=True,encoding='utf-8')
(OUT/'decode.log').write_text(decoded.stderr,encoding='utf-8')
if decoded.returncode or decoded.stderr.strip():
    raise RuntimeError('Full video decode failed: '+decoded.stderr[-1200:])

timeline=json.loads((DEST/'ceco-booth-5min.timeline.json').read_text(encoding='utf-8'))
source=json.loads(Path(timeline['source']).read_text(encoding='utf-8'))
verification=json.loads(Path(source['verification']).read_text(encoding='utf-8'))
assert verification['report']['outcome']=='recovered'
assert verification['report']['recovery']['held_s']>=verification['report']['recovery']['hold_s']>=30
assert not verification['after']['active_faults']
assert not verification['browser_errors']
if 'knowledge' in verification:
    knowledge=verification['knowledge']
    assert knowledge['build_status']=='candidate'
    assert knowledge['publication']['status']=='published' and not knowledge['publication']['duplicate']
    assert len([x for x in knowledge['source_tools'] if x=='read_registered_source'])>=2
    assert 'read_extracted_structure' in knowledge['source_tools']
    assert [c['id'] for c in timeline['chapters'][:5]]==['documents','sources','knowledge_build','knowledge_review','ontology']
    assert timeline['chapters'][4]['start']+timeline['chapters'][4]['duration']==sum(c['duration'] for c in timeline['chapters'][:5])
if 'ontology_retake' in verification:
    retake=verification['ontology_retake']
    assert retake['read_only'] and not retake['browser_errors'] and not retake['writes']
    assert retake['graph_counts']['nodes']==verification['knowledge']['graph_counts']['nodes']
    assert retake['graph_counts']['edges']==verification['knowledge']['graph_counts']['relationships']
for chapter,shot in zip(timeline['chapters'],source['scenes']):
    assert chapter['id']==shot['id']
    # Descriptions of publication, selection and approval must follow the filmed action.
    event=shot.get('approval_offset_s') if shot['id']=='approval' else shot.get('caption_split_actual_s')
    if event is not None:
        actual=sum(s['end']-s['start'] for s in shot.get('segments',[shot]))
        speed=max(1,actual/chapter['duration'])
        cues=[c for c in timeline['cues'] if c['scene']==chapter['id']]
        assert cues[1]['start']-chapter['start']+0.02>=event/speed,chapter['id']
for chapter in timeline['chapters']:
    if source.get('human_pacing'):
        assert chapter['speed']<=1.10,chapter
        if chapter['id'] in ['fault','recovery']:
            assert chapter['speed']==1 and chapter['actual_s']<=chapter['duration'],chapter
    chapter_cues=[c for c in timeline['cues'] if c['scene']==chapter['id']]
    assert chapter_cues and abs(chapter_cues[0]['start']-chapter['start'])<0.002
    assert abs(chapter_cues[-1]['end']-(chapter['start']+chapter['duration']))<0.002
    assert all(chapter['start']<=c['start']<c['end']<=chapter['start']+chapter['duration'] for c in chapter_cues)
assert all(abs(a['end']-b['start'])<0.002 for a,b in zip(timeline['cues'],timeline['cues'][1:]))
assert timeline['layout']['caption_band_top_px']>=timeline['layout']['process_bottom_px']
layout_checks=[]
if timeline['layout'].get('caption_alignment')=='center':
    layout_folder=OUT/'caption-layout'
    layout_folder.mkdir(exist_ok=True)
    left,top,right,bottom=0,timeline['layout']['caption_band_top_px'],1920,timeline['layout']['caption_band_bottom_px']
    target=((left+right)/2,(top+bottom)/2)
    for idx,cue in enumerate(timeline['cues'],1):
        timestamp=(cue['start']+cue['end'])/2
        frame=layout_folder/f'caption-{idx:02}.png'
        subprocess.run([ff,'-y','-v','error','-ss',str(timestamp),'-i',str(video),'-frames:v','1',str(frame)],capture_output=True,check=True)
        band=Image.open(frame).convert('RGB').crop((left,top,right,bottom))
        # Main captions are white. Muted chapter and edit notes are excluded.
        mask=Image.new('L',band.size)
        mask.putdata([255 if min(rgb)>=230 and max(rgb)-min(rgb)<=16 else 0 for rgb in band.get_flattened_data()])
        # Compression can make muted footer glyphs almost white. Their rows are
        # only ~14px high; retain full main text lines (including any overflow).
        rows=[y for y in range(mask.height) if mask.crop((0,y,mask.width,y+1)).getbbox()]
        groups=[]
        for y in rows:
            if not groups or y>groups[-1][-1]+2:groups.append([y])
            else:groups[-1].append(y)
        main_rows={y for group in groups if group[-1]-group[0]+1>=24 for y in range(group[0],group[-1]+1)}
        for y in range(mask.height):
            if y not in main_rows:mask.paste(0,(0,y,mask.width,y+1))
        box=mask.getbbox()
        assert box is not None,idx
        assert box[0]>=80 and box[2]<=1840 and box[1]>=12 and box[3]<=160,(idx,box)
        center=((box[0]+box[2])/2,top+(box[1]+box[3])/2)
        assert abs(center[0]-target[0])<=8 and abs(center[1]-target[1])<=8,(idx,center)
        layout_checks.append({'cue':idx,'at':timestamp,'ink_bounds_in_band':box,'visual_center':center})
    (layout_folder/'result.json').write_text(json.dumps({'passed':True,'target':target,'cues':layout_checks},ensure_ascii=False,indent=2),encoding='utf-8')
samples=[round(c['start']+c['duration']/2) for c in timeline['chapters']]
font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',22)
sheet=Image.new('RGB',(1280,((len(samples)+1)//2)*396),'#101c28')
draw=ImageDraw.Draw(sheet)
for idx,seconds in enumerate(samples):
    frame=OUT/f'frame-{seconds:03}.png'
    r=subprocess.run([ff,'-y','-v','error','-ss',str(seconds),'-i',str(video),'-frames:v','1',str(frame)],capture_output=True,text=True,encoding='utf-8')
    if r.returncode:
        raise RuntimeError(r.stderr)
    im=Image.open(frame).convert('RGB')
    im.thumbnail((640,360))
    x,y=(idx%2)*640,(idx//2)*396
    sheet.paste(im,(x,y+36))
    draw.text((x+12,y+5),f'{seconds//60:02}:{seconds%60:02}',font=font,fill='white')
sheet.save(DEST/'ceco-booth-preview.jpg',quality=93)

html=OUT/'playback.html'
html.write_text('<!doctype html><meta charset="utf-8"><title>CECO video playback check</title><body style="margin:0;background:#101c28"><video controls muted style="width:100vw" src="'+video.as_uri()+'"></video>',encoding='utf-8')
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1920,'height':1080})
    page.goto(html.as_uri())
    page.wait_for_function('document.querySelector("video").readyState>=2',timeout=45000)
    info=page.evaluate('''() => {const v=document.querySelector('video');return {duration:v.duration,width:v.videoWidth,height:v.videoHeight,readyState:v.readyState,error:v.error?{code:v.error.code,message:v.error.message}:null}}''')
    assert 0<timeline['duration_s']<=300
    assert abs(info['duration']-timeline['duration_s'])<0.1,info
    assert (info['width'],info['height'])==(1920,1080),info
    assert not info['error'],info
    page.evaluate('document.querySelector("video").play()')
    page.wait_for_timeout(1200)
    assert page.evaluate('document.querySelector("video").currentTime')>0.5
    page.evaluate('(t)=>{const v=document.querySelector("video");v.pause();v.currentTime=t}',timeline['duration_s']-1)
    page.wait_for_function('document.querySelector("video").readyState>=2')
    page.wait_for_timeout(500)
    assert page.evaluate('document.querySelector("video").currentTime')>=timeline['duration_s']-1
    browser.close()
assert not (DEST/'ceco-booth-5min.srt').exists(), 'A matching sidecar can cause duplicate captions.'
text=(DEST/'subtitles'/'ceco-booth-5min.srt').read_text(encoding='utf-8-sig')
info.update({'full_decode_passed':True,'start_and_end_browser_playback':True,'subtitle_cues':len(re.findall(r' --> ',text)),'subtitle_timeline_no_overlap':True,'captions_follow_all_chapters':True,'chapter_count':len(timeline['chapters']),'caption_font_px':timeline['layout']['caption_font_px'],'process_not_covered':True,'matching_sidecar_absent':True,'file_size_bytes':video.stat().st_size,'samples':samples,'captions_follow_actual_actions':True,'actual_recovery_verified':True,'work_order':verification['report']['work_order_id'],'knowledge_publication_verified':'knowledge' in verification,'all_captions_centered_in_band':bool(layout_checks),'all_captions_inside_band':bool(layout_checks),'caption_layout_frames':len(layout_checks)})
(OUT/'result.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(info,ensure_ascii=False,indent=2))
