"""Fit the actual recording without speeding through clicks or sensor recovery."""
import math


def fit(meta):
    from script_ko import polished
    plans=polished(meta['storyboard'])
    for shot in meta['scenes']:
        key=shot['id']
        segments=shot.get('segments') or [{'start':shot['start'],'end':shot['end']}]
        segments=[dict(s) for s in segments]
        # These tails are verified static reading pauses after the real action.
        trim={'sources':2,'knowledge_build':3,'knowledge_review':2,'normal':2}.get(key,0)
        if trim and segments[-1]['end']-segments[-1]['start']>trim+4:
            segments[-1]['end']-=trim
        if key=='ontology':
            segments[-1]['end']=min(segments[-1]['end'],shot['start']+shot['caption_split_actual_s']+6)
        shot['segments']=segments
    fitted=[]
    for plan,shot in zip(plans,meta['scenes']):
        key,_,title,captions=plan
        actual=sum(s['end']-s['start'] for s in shot['segments'])
        # Retain continuous, real-time physical deterioration and recovery.
        ceiling=1 if key in ('fault','recovery') else 1.10
        duration=max(math.ceil(actual/ceiling),len(captions)*4)
        if key=='approval':
            duration=max(duration,math.ceil(shot['approval_offset_s'])+4)
        fitted.append((key,duration,title,captions))
    total=sum(s[1] for s in fitted)
    if total>300:
        raise RuntimeError(f'{total}s: trim unchanged waiting, preserve all meaningful actions.')
    meta['storyboard']=fitted
    meta['human_pacing']={'maximum_speed':1.10,'continuous_real_time':['fault','recovery'],
                         'trimmed':'unchanged reading tails and long model waiting only'}
    return meta
