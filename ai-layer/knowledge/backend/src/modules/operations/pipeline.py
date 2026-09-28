"""Read-only pipeline health with explicit observation boundaries."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.request import urlopen

from fastapi import APIRouter
from .evidence import live_state, history

router = APIRouter(prefix='/api/operations', tags=['manufacturing-evidence'])


def flink_status():
    try:
        url = os.environ.get('SCADA_FLINK_URL', 'http://host.docker.internal:27081')
        with urlopen(url + '/jobs/overview', timeout=4) as response:
            jobs = json.load(response)['jobs']
        running = [job for job in jobs if job.get('state') == 'RUNNING']
        return {'key':'flink','name':'Flink 이상 탐지',
                'status':'available' if len(running) == 4 else 'degraded',
                'detail':f'{len(running)}/4 작업 RUNNING',
                'jobs':[{'name':j.get('name'), 'state':j.get('state')} for j in jobs],
                'boundary':'이 프로젝트의 SQL 3개 + ONNX 1개 작업 상태. 탐지 정확도 검증과 다릅니다.'}
    except (OSError, ValueError, KeyError, TypeError):
        return {'key':'flink','name':'Flink 이상 탐지','status':'unavailable','detail':'분석 작업 상태 조회 실패'}


def historian_status(state):
    if state.get('status') != 'available':
        return {'key':'history','name':'센서 이력 수집','status':'unavailable','detail':'조회 대상 공정 확인 불가'}
    import time
    stop = time.time_ns()
    tags = list(state.get('readings', {}))
    data = history(state['site'], state['device'], tags, stop-30_000_000_000, stop)
    latest = {}
    for row in data.get('rows', []):
        if row['tag'] not in latest or row['time'] > latest[row['tag']]['time']:
            latest[row['tag']] = row
    good = []
    for tag, row in latest.items():
        try:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(row['time'].replace('Z','+00:00'))).total_seconds()
            if row['quality'] == 'GOOD' and 0 <= age <= 15:
                good.append(tag)
        except (ValueError, TypeError):
            continue
    return {'key':'history','name':'센서 이력 수집',
            'status':'available' if tags and len(good) == len(tags) else 'degraded' if data['status'] in ('available','missing') else 'unavailable',
            'detail':f'{len(good)}/{len(tags)} 센서 · 15초 이내 GOOD',
            'source':'InfluxDB/process_raw','boundary':'최근 30초 이력에서 각 센서의 마지막 값과 품질을 확인합니다.'}


@router.get('/pipeline')
def pipeline_status():
    state = live_state()
    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(flink_status)
        stored = historian_status(state)
        analysis = future.result()
    return {'checked_at':datetime.now(timezone.utc).isoformat(), 'items':[
        {'key':'plant','name':'공정 상태 조회','status':state['status'],
         'detail':f"스캔 {state.get('seq', '—')}",
         'boundary':'시뮬레이터 API 조회 가능 여부. EdgeX·MQTT·Kafka 각 구간의 개별 정상 판정은 아닙니다.'},
        stored, analysis], 'notice':'관측 지점별 상태이며 전체 경로의 무손실 또는 AI 분석 성공을 보증하지 않습니다.'}
