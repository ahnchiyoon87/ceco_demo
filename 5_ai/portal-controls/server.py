"""Human portal controls for the local virtual plant; no AI tools or crew access.

The browser uses one origin. Simulator credentials remain here and requests use
the existing host-published human endpoint, not a new IT-to-OT firewall rule.
"""
from __future__ import annotations

import base64
import json
import hmac
import os
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CATALOG = [
    {'id': 'strainer_fouling', 'title': '냉각수 필터 막힘', 'group': '냉각 계통', 'description': '냉각수가 줄고 반응기 온도가 올라갑니다.'},
    {'id': 'jacket_fouling', 'title': '냉각 코일 스케일', 'group': '냉각 계통', 'description': '물은 흐르지만 열을 충분히 빼내지 못합니다.'},
    {'id': 'bearing_wear', 'title': '교반기 베어링 마모', 'group': '회전 기계', 'description': '전류와 진동이 증가합니다.'},
    {'id': 'shaft_misalignment', 'title': '교반기 축 정렬 불량', 'group': '회전 기계', 'description': '축의 정렬이 어긋나 진동이 증가합니다.'},
    {'id': 'pt_drift', 'title': '압력계 오지시', 'group': '압력·배출', 'description': '압력계가 높게 표시해 인터록이 작동합니다.'},
    {'id': 'outlet_valve_stick', 'title': '배출 밸브 고착', 'group': '압력·배출', 'description': '제품이 빠져나가지 못해 실제 압력이 올라갑니다.'},
]
SIMULATOR = os.environ.get('SIMULATOR_URL', '').rstrip('/')
KNOWLEDGE = os.environ.get('KNOWLEDGE_URL', 'http://knowledge:8000').rstrip('/')
USER = os.environ.get('SIMULATOR_USER', '')
PASSWORD = os.environ.get('SIMULATOR_PASSWORD', '')
TOKEN = os.environ.get('PORTAL_CONTROL_TOKEN', '')
FUXA = os.environ.get('FUXA_URL', '').rstrip('/')
GATE_USER = os.environ.get('HMI_GATE_USER', '')
GATE_PASSWORD = os.environ.get('HMI_GATE_PASSWORD', '')
OPERATOR_PASSWORD = os.environ.get('FUXA_OPERATOR_PASSWORD', '')
MUTATION_LOCK = threading.Lock()


class ControlError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def upstream(path, body=None, *, simulator=True):
    headers = {}
    if simulator:
        if not (SIMULATOR and USER and PASSWORD):
            raise ControlError(503, '설비 연결 설정을 확인해 주세요.')
        headers['Authorization'] = 'Basic ' + base64.b64encode(f'{USER}:{PASSWORD}'.encode()).decode()
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers['Content-Type'] = 'application/json'
    request = urllib.request.Request((SIMULATOR if simulator else KNOWLEDGE) + path, data=data, headers=headers)
    try:
        # One attempt. A timed-out write may have reached the virtual plant.
        with urllib.request.urlopen(request, timeout=8) as response:
            return json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise ControlError(503, '설비 응답을 확인하지 못했습니다. 상태를 다시 확인한 뒤 조작해 주세요.') from None


def execution_active():
    items = upstream('/api/operations/incidents', simulator=False).get('items', [])
    return any(x['status'] in {'executing', 'observing'} for x in items)


def operator_session():
    """Issue the ordinary FUXA operator session; never expose configured passwords."""
    if not (FUXA and GATE_USER and GATE_PASSWORD and OPERATOR_PASSWORD):
        raise ControlError(503, '제어 패널 연결 설정을 확인해 주세요.')
    request = urllib.request.Request(FUXA + '/api/signin',
        data=json.dumps({'username': 'operator', 'password': OPERATOR_PASSWORD}).encode(),
        headers={'Content-Type': 'application/json',
                 'Authorization': 'Basic ' + base64.b64encode(f'{GATE_USER}:{GATE_PASSWORD}'.encode()).decode()})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            user = json.load(response)['data']
        if user.get('username') != 'operator' or user.get('groups') != 2 or not isinstance(user.get('token'), str) or not user['token']:
            raise ValueError('Unexpected operator session')
        safe_user = {key: user[key] for key in ('username', 'fullname', 'groups', 'info', 'token') if key in user}
        safe_user['infoRoles'] = json.loads(user.get('info') or '{}').get('roles')
        return {'user': safe_user}
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, TypeError, AttributeError):
        raise ControlError(503, '제어 패널에 연결하지 못했습니다. 잠시 후 다시 연결해 주세요.') from None


def plant_state():
    state = upstream('/state')
    working = execution_active()
    return {'active_faults': list(state['active_faults']), 'execution_active': working,
            'readings': {k: state['readings'][k] for k in ['TT-101', 'FT-103', 'VT-101', 'PT-101', 'PT-102']},
            'commands': state['commands'], 'seq': state['seq']}


def mutate(path, body):
    if path not in {'/fault', '/reset'}:
        raise ControlError(404, '지원하지 않는 조작입니다.')
    if path == '/fault' and (set(body) != {'scenario'} or not isinstance(body['scenario'], str)
                            or body['scenario'] not in {x['id'] for x in CATALOG}):
        raise ControlError(400, '화면에 표시된 이상 중 하나를 선택해 주세요.')
    if path == '/reset' and body:
        raise ControlError(400, '초기화 요청 형식이 올바르지 않습니다.')
    with MUTATION_LOCK:
        if execution_active():
            raise ControlError(409, '정비·회복 확인이 진행 중입니다. 결과를 확인한 뒤 다시 시작해 주세요.')
        if path == '/fault':
            if upstream('/state')['active_faults']:
                raise ControlError(409, '이미 이상이 발생해 있습니다. 대시보드에서 처리하거나 초기화 후 다시 시작해 주세요.')
            result = upstream('/fault', body)
            return {'started': result['injected']}
        if path == '/reset':
            result = upstream('/fault/clear', {})
            return {'cleared': result['cleared']}
        raise ControlError(404, '지원하지 않는 조작입니다.')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # No request bodies, credentials, or exception dumps in HTTP logs.
        print(f'portal-controls {self.command} {self.path.split("?")[0]}', flush=True)

    def reply(self, status, body):
        data = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def allowed(self):
        if not TOKEN or not hmac.compare_digest(self.headers.get('X-Portal-Token', ''), TOKEN):
            raise ControlError(403, '포털을 통해 접속해 주세요.')
        if self.headers.get('X-CECO-Portal') != 'interactive':
            raise ControlError(403, '포털의 설비 화면에서 조작해 주세요.')
        # Nginx compares Origin with the actual portal host before forwarding.
        if self.command == 'POST' and self.headers.get('X-Portal-Same-Origin') != '1':
            raise ControlError(403, '다른 사이트에서 보낸 조작은 받지 않습니다.')

    def do_GET(self):
        try:
            if self.path == '/healthz':
                return self.reply(200, {'status': 'available'})
            self.allowed()
            if self.path == '/catalog':
                return self.reply(200, {'items': CATALOG})
            if self.path == '/state':
                return self.reply(200, plant_state())
            raise ControlError(404, '지원하지 않는 조회입니다.')
        except ControlError as exc:
            self.reply(exc.status, {'detail': exc.message})

    def do_POST(self):
        try:
            self.allowed()
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 1024 or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ControlError(400, '조작 요청 형식이 올바르지 않습니다.')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ControlError(400, '조작 요청 형식이 올바르지 않습니다.')
            if self.path == '/operator-session':
                if body:
                    raise ControlError(400, '제어 패널 연결 요청 형식이 올바르지 않습니다.')
                return self.reply(200, operator_session())
            self.reply(200, mutate(self.path, body))
        except (ValueError, TypeError):
            self.reply(400, {'detail': '조작 요청 형식이 올바르지 않습니다.'})
        except ControlError as exc:
            self.reply(exc.status, {'detail': exc.message})


if __name__ == '__main__':
    if not (SIMULATOR and USER and PASSWORD and TOKEN and TOKEN != 'CHANGE_ME'):
        raise SystemExit('Portal simulator connection is not configured.')
    ThreadingHTTPServer(('0.0.0.0', 8090), Handler).serve_forever()
