"""Export MP4 and AVI with one caption layer and the synchronized real narration."""
import hashlib, json, pathlib, re, shutil, subprocess
import imageio_ffmpeg
ROOT=pathlib.Path(__file__).resolve().parent
FF=imageio_ffmpeg.get_ffmpeg_exe()
D=json.loads((ROOT/'narration.json').read_text(encoding='utf8'))
SYNC=json.loads((ROOT/'sync.json').read_text(encoding='utf8'))
DEST=pathlib.Path(D['source_video']).parent
stem='ceco-booth-5min-dub-anchiyoon-v5'
mp4=DEST/(stem+'.mp4');avi=DEST/(stem+'.avi')

def run(args,log):
    with (ROOT/log).open('wb') as f:
        r=subprocess.run([FF,'-hide_banner','-nostats',*args],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
    assert r.returncode==0, f'{log}: ffmpeg exited {r.returncode}'

def inspect(path):
    r=subprocess.run([FF,'-hide_banner','-i',str(path)],capture_output=True)
    t=r.stderr.decode(errors='replace')
    match=re.search(r'Duration: (\d+):(\d+):([\d.]+)',t);assert match,t[-1000:]
    h,m,s=map(float,match.groups());return h*3600+m*60+s,t

if __name__=='__main__':
    assert not mp4.exists() and not avi.exists(), 'Preserve existing output'
    meta=';FFMETADATA1\ntitle=CECO 설비 이상 대응 데모 — 안치윤v5 더빙\ncomment=실제 실행 영상·윤문 한국어 내레이션·중앙 자막 1겹\n'
    for c in D['chapters']:
        meta+=f'[CHAPTER]\nTIMEBASE=1/1000\nSTART={round(c["start"]*1000)}\nEND={round((c["start"]+c["duration"])*1000)}\ntitle={c["title"]}\n'
    (ROOT/'chapters.ffmetadata').write_text(meta,encoding='utf8')
    # Erase only the original dedicated caption band, then draw the revised layer.
    vf='drawbox=x=0:y=900:w=1920:h=180:color=0x101c28:t=fill,ass=dub-subtitles.ass'
    print('Rendering captioned MP4 + AAC narration',flush=True)
    run(['-n','-i',D['source_video'],'-i',str(ROOT/'narration.wav'),'-i','chapters.ffmetadata',
         '-map','0:v:0','-map','1:a:0','-map_metadata','2','-map_chapters','2',
         '-vf',vf,'-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',
         '-c:a','aac','-b:a','192k','-ar','48000','-ac','2','-t','281',
         '-movflags','+faststart',str(mp4)],'render-mp4.log')
    print('Rendering AVI + MPEG-4/XVID + MP3 narration',flush=True)
    run(['-n','-i',str(mp4),'-map','0:v:0','-map','0:a:0','-map_metadata','-1',
         '-c:v','mpeg4','-vtag','XVID','-q:v','3','-pix_fmt','yuv420p',
         '-c:a','libmp3lame','-b:a','160k','-ar','48000','-ac','2',str(avi)],'render-avi.log')
    files=[]
    for path,codec in [(mp4,'h264'),(avi,'mpeg4')]:
        seconds,header=inspect(path)
        assert abs(seconds-281)<.15 and '1920x1080' in header and '25 fps' in header
        assert codec in header and 'Audio:' in header and '48000 Hz' in header
        print('Full audiovisual decode:',path.name,flush=True)
        run(['-v','error','-i',str(path),'-f','null','-'],'decode-'+path.suffix[1:]+'.log')
        assert not (ROOT/('decode-'+path.suffix[1:]+'.log')).read_bytes()
        files.append({'file':str(path),'duration_s':seconds,'bytes':path.stat().st_size,
                      'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'full_decode':'PASS'})
    srt=DEST/'subtitles'/(stem+'.srt');assert not srt.exists();shutil.copy2(ROOT/'dub-subtitles.srt',srt)
    script=DEST/'ceco-booth-5min-dub-script.txt';assert not script.exists()
    script.write_text('CECO 데모 — 안치윤v5 더빙 대본\n4분 41초 / 한국어 / 화면과 음성에 맞춘 윤문본\n\n'+
        '\n\n'.join(f'{int(c["start"])//60:02}:{int(c["start"])%60:02}  {c["text"]}' for c in D['cues'])+'\n',encoding='utf8')
    # Measure the encoded delivery, not just the intermediate WAV.
    run(['-i',str(mp4),'-vn','-af','loudnorm=I=-16:TP=-1.5:LRA=7:print_format=json','-f','null','-'],'delivery-loudness.log')
    text=(ROOT/'delivery-loudness.log').read_text(encoding='utf8',errors='replace')
    measure=json.loads(re.search(r'\{\s*"input_i".*?\}',text,re.S).group())
    assert abs(float(measure['input_i'])+16)<1.0 and float(measure['input_tp'])<=-.8,measure
    qa=ROOT/'qa';qa.mkdir(exist_ok=True)
    for name,at in [('opening',2.0),('knowledge',32.0),('approval',194.5),('recovery',236.0),('ending',278.0)]:
        run(['-v','error','-y','-ss',str(at),'-i',str(mp4),'-frames:v','1',str(qa/(name+'.png'))],'frame-'+name+'.log')
    report={'files':files,'source_video':D['source_video'],'source_sha256':hashlib.sha256(pathlib.Path(D['source_video']).read_bytes()).hexdigest(),
            'voice_name':D['voice_name'],'voice_id':D['voice_id'],'model_id':D['model_id'],
            'speech_segments':40,'captions':len(SYNC['captions']),'caption_layers':1,'caption_font_px':72,
            'max_time_stretch':max(x['time_stretch'] for x in SYNC['audio']),
            'original_ui_timing_preserved':True,'overlapping_speech':False,'loudness':measure,
            'asr_comparison':'asr-comparison.json','script':str(script),'subtitles':str(srt),
            'visual_qa':'pending','direct_listening':'not performed; audio input unavailable; independent ASR used'}
    (ROOT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'files':files,'loudness_lufs':measure['input_i'],'true_peak_dbtp':measure['input_tp']},ensure_ascii=False),flush=True)
