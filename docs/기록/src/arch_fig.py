# -*- coding: utf-8 -*-
"""ceco_demo 시스템_아키텍처 전체 그림. 상세판(상자 안 구성 전부)과 간단판(번호 · 이름 · 제품만)을 같은 배치에서 만든다.
배치: 열(A · S · R · M · X)과 띠(B0~B5, 그 사이 라우터 막대 두 개). 상자 높이는 안쪽 줄 수로, 띠 높이는 가장 긴 열로 정한다.
연결 경로는 배치가 끝난 뒤 상자 좌표로 계산한다(route). route 에 없는 연결은 상자 위 작은 표로 그린다.
"""
import html, re

COLS = dict(A=(40, 360), S=(470, 700), SL=(470, 340), SR=(830, 340), R=(1230, 380), M=(1660, 330), X=(2050, 300))
W = 2380
LH = 18.5
HEAD = 60
GAP = 28
BAND_TOP = 52
BAND_BOT = 26
BAND_GAP = 12
BAR_H = 66
FONT = 12.5
SMALL = ("prov", "kinit", "submit", "seed")

BANDS = [  # id, 이름, 설명, 배경, 테두리, 글자, 오른쪽 끝까지
 ("B0", "0 · 현장", "기계와 가상 정비팀 (진짜 공장 대신 물리 계산)", "#f3f1ec", "#b9ae98", "#6b604a", True),
 ("B1", "1 · 제어", "PLC — 마지막 안전장치", "#fbf3e2", "#d6a64f", "#8a6410", True),
 ("B2", "2 · OT 공장 망 (ot-net · 외부 차단)", "밖과 끊겨도 계측 · 화면 · 제어 · 안전이 혼자 돈다", "#fcefe2", "#cf8a45", "#9a5a1c", True),
 ("R1", None, None, None, None, None, True),
 ("B3", "3 · DMZ 완충 망 (dmz-net · 외부 차단)", "공장과 사무실이 만나는 유일한 곳 · 여기서는 아무 데도 먼저 연결하지 않음", "#f0ecf8", "#8a76bf", "#5b4691", True),
 ("R2", None, None, None, None, None, True),
 ("B4", "4 · IT 데이터 (it-net)", "장부 · 검사 · 묶기 · 기록 · 감시 (점선 상자는 감시 프로필 = make up-full 에서만)", "#e7f3f6", "#3f8ea3", "#1f6378", True),
 ("B5", "5 · 업무 · AI (it-net)", "판단은 사람이 · 제안과 계산은 AI와 엔진이 · 설비에 직접 닿는 연결 없음", "#ebeffa", "#5a6fbf", "#394b98", False),
]
BAR_TEXT = {
 "R1": ("⑨ 구역 라우터 (iptables 한 대 · 상태 기반 · 허용 밖은 세고 버림)",
        "OT → DMZ 새 연결 2: 1883 브리지 · 9090 감시   |   호스트 → OT 6: 37018 · 37080 · 37082 · 37083 · 37880 · 37443   |   DMZ → OT 새 연결 없음(응답만)"),
 "R2": ("⑨ 같은 구역 라우터",
        "IT → DMZ 새 연결 4: 1883 수집기 · 8086 사본 조회 · 9090 감시 연합 · 8088 요청 게이트웨이   |   DMZ → IT · IT → OT 새 연결 없음"),
}

# key: (띠, 열, 순서, [왼쪽 줄], [오른쪽 줄] 또는 None, 옵션)
BOX = {
 "sim": ("B0", "S", 0, [
   "**설비 8대** TK-101 · R-101 · HX-101",
   "  HX-102 · ST-103 · P-101 · CV-101 · M-101",
   "**계측 17점** 액위 · 온도 · 압력 · 유량",
   "  전류 · 진동 · pH · 전도도 · 차압",
   "**물리** 스캔 1초 · 배속 600 · 소구간 5초",
   "  냉각수 30 m³/h · 20 ℃ · 릴리프 7.5 barg",
   "**Modbus** 계측 HR0..37 · 순번 HR24",
   "  코일 0..3 · 설정값 HR100..102",
  ], [
   "**:8080 강사 API** (instructor) 고장 주입",
   "  고장 12종 · 열화 6종은 정비로만 회복",
   "**:8081 현장 패널** (field) 모드 · 기동/정지",
   "  정비 키 · 인터록 리셋 · 비상정지",
   "**:8082 가상 정비팀** (crew, 수신기만)",
   "  현장 작업 8종 · 안전 확인 · 격리(LOTO)",
   "  소견 DONE · DONE_NO_FAULT · REJECTED",
   "  같은 작업 지시 ID는 한 번만 수행",
  ], {}),
 "plc": ("B1", "S", 0, [
   "**태스크 100 ms** · 슬레이브 :502",
   "**읽기** FC3 HR0..37 · 패널 HR300..308",
   "**쓰기** FC15 코일 4 · FC16 설정값 3",
   "**엣지 채널** %MW0 시각 · %MW10 운전원",
   "  · %MW20 외부 요청",
   "**모드** LOCAL · REMOTE_MANUAL · REMOTE_AUTO",
   "  정비 모드 RETAIN · 해제는 현장 키만",
  ], [
   "**검사 3** 모드 · 정비 · 인터록 · 범위",
   "  만료 · 요청 해시 중복(최근 8)",
   "**고압 인터록** PT-101 ≥ 6.5 → 펌프 정지",
   "  리셋은 ≤ 5.2 barg에서만",
   "**건조 운전 방지** LT-101 < 5 %",
   "**되읽기 감시** 전류 < 1.0 A가 5초면 정지",
   "**ACK** 코드 0~11 · 생산 스케줄 1일 주기",
  ], {}),
 "edge": ("B2", "S", 0, [
   "**수집·명령 탭** 250 ms 폴링",
   "  FC4 0..37 계측 · FC3 100..118 상태·ACK",
   "  쓰기 %MW0 시각(1초) · %MW10 · %MW20",
   "**UNS 발행** 값 · 품질 · 출처 시각 · 순번",
   "  변화량 · 최대 간격 보고 · 상태 retain",
   "**운전원 명령** 5초 넘음 · retain 거부",
   "**끊김 버퍼** 디스크 72,000건",
   "**편집기** 읽기 전용 · 기동마다 재배포",
  ], [
   "**OT 수신기 탭** (검사 2) · MQTT 5",
   "  스키마 재검사 · 만료 · 모드 · 정비",
   "  REMOTE_AUTO → 바로 실행",
   "  REMOTE_MANUAL → 운전원 대기 60초",
   "  정비 모드: 제어 거부 · 현장 작업만",
   "**실행** 설비 명령 → %MW20(PLC)",
   "  현장 작업 → 정비팀 :8082 (60초)",
   "**응답** 수신 ⓑ · PLC 결과 · field 단계",
  ], {}),
 "hub": ("B2", "S", 1, [
   "**:1883** 익명 거부 · 계정 5 (ACL)",
   "`AR-100/reaction/{라인}/{설비}/…`",
   "  tag · status · ack · state ← edge",
   "  cmd/operator ← fuxa",
   "  cmd/request ← 수신기",
   "  request/pending · decision (운전원)",
   "**대기열** 72,000건 · 32 MiB · 세션 1시간",
  ], [
   "**DMZ 브리지** (허브가 엶) · MQTT 5",
   "  계정 bridge-ot · 세션 3600초",
   "  out QoS1: tag · status · ack · state",
   "    · response",
   "  in: request/in(QoS1) · alert/display(Q0)",
   "  브리지 in에는 ACL이 걸리지 않음",
   "**$SYS** 10초 · 영속 저장 60초",
  ], {}),
 "fuxa": ("B2", "R", 0, [
   "**태그 51** (구독 39 · 발행 12)",
   "**화면 1장** 요소 63",
   "**알람 18** = 규격 14 + 상태 4",
   "**운전원 명령 10종** → cmd/operator",
   "**받은 요청** 목록 · 수락/거부 결정",
   "**분석 경고** alert/display (참고)",
   "**로그인** admin · operator · 손님은 보기",
   "**DAQ** SQLite 7일 · 계정 fuxa",
  ], None, {}),
 "gate": ("B2", "R", 1, [
   "**:1882 → fuxa:1881** 역방향 프록시",
   "basic_auth 계정 plant · 없으면 401",
   "FUXA 손님 토큰을 밖에서 차단",
   "호스트 37018 → 라우터 21881",
  ], None, {}),
 "prov": ("B2", "R", 2, ["1회 · 계정 · 태그 51 · 알람 18"], None, {}),
 "hubx": ("B2", "M", 0, [
   "계정 ot-exporter",
   "$SYS 7종 구독 (QoS 0)",
   "→ mosquitto_sys 지표",
   ":4195 /metrics",
  ], None, {}),
 "otag": ("B2", "M", 1, [
   "--agent 모드 · zone=ot",
   "15초: edge · exporter",
   "→ DMZ 감시 remote_write",
  ], None, {}),
 "gw": ("B3", "A", 0, [
   "**검사 1** POST /requests :8088",
   "토큰(Bearer) → 401",
   "스키마 → 400/422",
   "허용 작업 16 · 설비 · 범위",
   "요청자 ai-ops/ai · mes-01/mes",
   "승인자 operator-01·02 · planner-01",
   "나이 10초 · 미래 2초 → TOO_OLD",
   "중복 ID 35초 기억 → 409",
   "브로커 끊김 → 503 즉시",
   "**통과** 만료 +30초 · QoS 1 · MQTT 5",
   "  PUBACK 2초 → 202 / 없으면 503",
  ], None, {}),
 "dmzb": ("B3", "S", 0, [
   "**:1883** 익명 금지 · 계정 6 (ACL)",
   "**bridge-ot** 계측 · 상태 · ACK",
   "  · 통신 상태 · 응답을 씀",
   "  request/in · alert/display를 읽음",
   "**gateway** request/in 쓰기만",
   "**대기열** 72,000건 · 32 MiB",
  ], [
   "**it-collector** reaction · response 읽기",
   "  alert/display 하나에만 씀",
   "**dmz-loader** reaction 읽기",
   "**viewer · dmz-exporter** $SYS",
   "**나가는 연결 없음** (모두 들어옴)",
   "**저장** 영속 · 끊긴 세션 1시간 뒤 삭제",
  ], {}),
 "loader": ("B3", "R", 0, [
   "구독 tag · status · state (QoS 1)",
   "계정 dmz-loader · 버퍼 32 MiB",
   "BAD(값 없음)는 행 없음 → 공백",
   "process_raw · plc_status 행",
   "500건 또는 1초 묶음 → :8086",
   "$SYS 지표 (계정 dmz-exporter)",
  ], None, {}),
 "dmzi": ("B3", "R", 1, [
   "org ar100 · 버킷 plant_raw · 7일",
   "쓰기: 적재기 토큰만",
   "읽기 전용 계정 it-reader",
   "조회: ㉙ AI (라우터 경유)",
   "Grafana 연결은 쓰는 패널 0",
   "호스트 37087",
  ], None, {}),
 "dmzp": ("B3", "M", 0, [
   "15초: loader · gateway · influx",
   "OT agent remote_write 받음",
   "IT가 /federate로 가져감",
   "보관 2시간 · zone=dmz",
  ], None, {}),
 "am": ("B4", "A", 0, [
   "**공정 alert** asset · rule로 묶음",
   "  대기 0초 · 간격 5초 · 반복 24시간",
   "  새 묶음 · 해제 → ⑯ 웹훅",
   "**억제 4** 정비 중 · PLC 정지",
   "  운전 꺼짐 · 인프라 장애",
   "**인프라 경보** 로그만(default)",
  ], None, {}),
 "flink": ("B4", "A", 1, [
   "**잡 4** · 병렬도 1 · 슬롯 4",
   "① 규격 USL/LSL 17태그 (CRITICAL)",
   "② Z-Score 60샘플 · |z|>3.5",
   "  최근 5번 중 3번 (WARNING)",
   "③ CEP IT-102>9.6A 뒤 10초 안",
   "  VT-101>7.1 mm/s (CRITICAL)",
   "④ ONNX 오토인코더 17태그×10스텝",
   "  기여 센서 상위 3 (WARNING)",
   "**결측** 선형 보간 · 20초 넘으면 LOCF",
   "**출력** clean · score · alerts",
   "**체크포인트** 10초 · ZK 고가용성",
  ], None, {"y_of": "kafka"}),
 "zk": ("B4", "A", 2, [
   ":2181 · 힙 64 MB",
   "Flink 잡 관리자 복구 기록",
   "잡 목록 · 최신 체크포인트 위치",
  ], None, {}),
 "trainer": ("B4", "A", 3, [
   "정상 데이터 21,600 표본 합성",
   "17태그 × 10스텝 · 은닉 64 → 16",
   "임계 99.5 백분위 × 1.15",
   "model.onnx → 공유 볼륨",
  ], None, {}),
 "submit": ("B4", "A", 4, ["SQL 3 + ONNX 1 · 4개 실행 중이면 건너뜀"], None, {}),
 "coll": ("B4", "S", 0, [
   "**스트림 7** · :4195",
   "① DMZ MQTT → raw · status · responses",
   "  raw에는 GOOD만 · 키 = 설비",
   "③ alerts.display → alert/display",
   "④ sensor.alerts → Alertmanager",
   "  끝 = 마지막 + 60초",
  ], [
   "⑤ plant.status → 억제 상태",
   "⑥ AM 웹훅 → PG 묶음 · 사건 → display",
   "⑦ approved → 게이트웨이 POST",
   "  재시도 0 · 응답 ⓐ → PG · 사본",
   "⑧ MES 흉내 /orders → PG → approved",
   "**PG 계정** ops · dispatcher · mes",
  ], {}),
 "kafka": ("B4", "S", 1, [
   "**토픽 10** · 복제 1 · lz4 · 자동 생성 끔",
   "`sensor.telemetry.raw` 6P · 7일",
   "`sensor.telemetry.clean` 6P · 7일",
   "`sensor.anomaly.score` 3P · 7일",
   "`sensor.alerts` 3P · 7일",
   "`plant.status` 3P · 7일",
  ], [
   "`alerts.display` 1P · 7일",
   "`request.approved` 3P · 30일",
   "`request.events` 3P · 30일",
   "`request.responses` 3P · 30일",
   "`audit.copy` 1P · 30일",
   "**정본은 PG** · Kafka는 통로 · 사본",
  ], {}),
 "pg": ("B4", "S", 2, [
   "**plant** registry: 설비 9 · 신호 17",
   "  작업 정의 16",
   "  workflow: 요청 · 사건 · MOC",
   "  alert: event · group · audit.log",
   "  enterprise: 사실값 20 · work_order",
   "**ai** 사건 · 대응안 · 분석 · 수신함",
  ], [
   "**추가 전용 5표** 트리거 + 권한 회수",
   "  (요청 · 사건 · MOC · 경보 · 감사)",
   "**계정** ops · dispatcher · mes",
   "  ai_app · reader(SELECT만)",
   "**AI** 사실값 읽기 · 작업 이력 추가만",
   "**접속** :5432 · 호스트 37532",
  ], {}),
 "kinit": ("B4", "R", 0, ["1회 · 토픽 10 · 7일 6개 · 30일 4개"], None, {}),
 "hist": ("B4", "R", 1, [
   "it-history (옛 수집기 스트림 ②)",
   "Kafka clean · score · alerts 구독",
   "→ IT InfluxDB 라인 프로토콜",
   "1초 또는 1,000건 묶음",
  ], None, {"y_of": "kafka"}),
 "iti": ("B4", "R", 2, [
   "bucket process · 보존 30일",
   "정제값 · 이상 점수 · alert 이력",
   "Grafana 01~03 화면이 읽음",
   "AI는 쓰지 않음 · 호스트 37086",
  ], None, {}),
 "prom": ("B4", "M", 0, [
   "10초 · job 7 · 보관 7일",
   "DMZ /federate (OT·DMZ 지표)",
   "경보 규칙 10 → Alertmanager",
   "공정 센서값은 담지 않음",
  ], None, {}),
 "graf": ("B4", "M", 1, [
   "01 공정 트렌드 (8패널)",
   "02 ML 이상 (4) · 03 알람 (2)",
   "04 인프라 (6) · 익명 Viewer",
   "원천 IT Influx · Prometheus",
   "호스트 37030",
  ], None, {}),
 "kexp": ("B4", "M", 2, ["컨슈머 랙 · 오프셋 · :9308"], None, {}),
 "cadv": ("B4", "M", 3, ["CPU · 메모리 · 네트워크"], None, {}),
 "seed": ("B5", "A", 0, ["1회 · 묶음 A·B·C · 매뉴얼 임베딩"], None, {}),
 "graph": ("B5", "A", 1, [
   "**묶음 C** 279노드 · 469관계",
   "증상 3 · 고장 유형 13 · 원인 28",
   "경보 서명 11 · 점검 13",
   "**결정 3** · 대안 14 · 규칙 6",
   "**KPI 5** · 손익 식(IMPACTS) 48",
   "정비 단계 63 · 작업 정의 14",
   "매뉴얼 절 51 · 벡터 1536차원",
   "호스트 37474 · 37687",
  ], None, {}),
 "ai": ("B5", "S", 0, [
   "**사건** 경보 묶음 3종 · 30초 정숙 분리",
   "**자동 분석** 경보 3건 · 15초 정숙",
   "  + 한계 이탈 경보가 있을 때",
   "**에이전트** gpt-6-luna",
   "  근거 도구 7개 모두 호출",
   "  관측 · 매뉴얼 · 온톨로지 · 선례",
   "**결정 엔진** (LLM 아님)",
   "  손익 식 × 사실값 × 관측",
   "  규칙 제외 · 순위 · 뒤집힘 표",
  ], [
   "**조치 카드** 5분 유효 · 사람 승인",
   "  승인 때 손익 · 규칙 다시 계산",
   "**실행기** 1초마다 한 단계씩",
   "  control → PLC · field → 정비팀",
   "  operator → 대기 · wait → 설비 시간",
   "  고장 없음 → 멈춤 · 격리 해제",
   "**회복** 기준 30초 연속 유지",
   "**보고서** → 작업 이력 WO-…",
   "**접속** :8000 · 호스트 38000",
  ], {}),
 "host": ("B5", "S", 1, [
   "**127.0.0.1 공개 포트만**",
   "  AI 화면 38180 · AI API 38000",
   "  FUXA 37018 · 강사 37080 · 패널 37082",
  ], [
   "**make up** (기본) · **up-full** (감시)",
   "**시험** tests/verify.py · e2e 7경우",
   "  s1 · s1v · s2 · s2v · s3 · s3v · s2m",
  ], {}),
 "web": ("B5", "R", 0, [
   "공정 대시보드(냉각수 포함)",
   "이상 대응 · AI 검토",
   "정비 계획 카드 · 진행 · 보고서",
   "설비 지식 스튜디오(그래프)",
   "FUXA 운전원 창",
   "/api → knowledge:8000 · 2초 갱신",
   "호스트 38180",
  ], None, {}),
 "bus": ("B5", "M", 0, [
   "**소비자 2** · 0.5초 타이머",
   "sensor.alerts → AI 사건",
   "ACK 5초 없음 = 결과 모름",
   "만료 + 5초 = 미확인",
   "운전원 대기 95초 초과",
   "PLC 수용 뒤 10초 재관측",
   "현장 작업: 정비팀 결과로",
   "명령≠상태 → sensor.alerts",
   "**다시 보내지 않음**",
  ], None, {}),
 "llm": ("B5", "X", 0, [
   "**API 직접** (LiteLLM 폐기)",
   "gpt-6-luna 원인 분석",
   "  도구 호출 · 구조화 출력",
   "text-embedding-3-small",
   "  1536차원",
   "**키** 5_ai/server/.env.local",
   "  (git 제외)",
  ], None, {}),
}


def tw(t, size=FONT):
    w, mono = 0.0, False
    for part in re.split(r"(`)", t):
        if part == "`":
            mono = not mono
            continue
        for ch in part.replace("**", ""):
            w += size * (1.0 if ord(ch) > 0x1100 else (0.6 if mono else 0.56))
    return w


def esc(t):
    return html.escape(t, quote=True)


def rich(x, y, t, size=FONT, fill="#24313a"):
    ind = 0
    while t.startswith("  "):
        ind, t = ind + 12, t[2:]
    out = [f'<text x="{x + ind}" y="{y}" font-size="{size}" fill="{fill}">']
    bold = mono = False
    for tok in re.split(r"(\*\*|`)", t):
        if tok == "**":
            bold = not bold
            continue
        if tok == "`":
            mono = not mono
            continue
        if not tok:
            continue
        a = ""
        if bold:
            a += ' font-weight="700" fill="#14212a"'
        if mono:
            a += ' font-family="JetBrains Mono,Consolas,monospace" font-size="11.4" fill="#1f5f78"'
        out.append(f"<tspan{a}>{esc(tok)}</tspan>")
    out.append("</text>")
    return "".join(out)


class Box:
    def __init__(s, x, y, w, h):
        s.x, s.y, s.w, s.h = x, y, w, h
    r = property(lambda s: s.x + s.w)
    b = property(lambda s: s.y + s.h)
    cx = property(lambda s: s.x + s.w / 2)
    cy = property(lambda s: s.y + s.h / 2)


def fam(col):
    return "S" if col in ("S", "SL", "SR") else col


def layout(compact):
    hbox = {}
    for k, (band, col, order, left, right, opt) in BOX.items():
        n = max(len(left), len(right) if right else 0)
        if compact:
            hbox[k] = 50 if k in SMALL else 62
        else:
            hbox[k] = (34 + n * LH + 10) if k in SMALL else (HEAD + n * LH + 12)
    B, bands, y = {}, {}, 10
    for bid, *_ in BANDS:
        if bid.startswith("R"):
            bands[bid] = (y, y + BAR_H)
            y += BAR_H + BAND_GAP
            continue
        top = y
        groups = {}
        for k, v in BOX.items():
            if v[0] == bid:
                groups.setdefault((fam(v[1]), v[2]), []).append(k)
        fy = {}
        # 순서가 같으면 가운데 척추(S)를 먼저 놓아 y_of 가 참조할 수 있게 한다
        for (f, order), ks in sorted(groups.items(), key=lambda kv: (kv[0][1], kv[0][0] != "S")):
            yy = fy.get(f, top + BAND_TOP)
            for k in ks:
                ref = BOX[k][5].get("y_of")
                if ref and ref in B:
                    yy = max(yy, B[ref].y)
            for k in ks:
                x, w = COLS[BOX[k][1]]
                B[k] = Box(x, yy, w, hbox[k])
            fy[f] = max(B[k].b for k in ks) + GAP
        bottom = max(B[k].b for ks in groups.values() for k in ks)
        bands[bid] = (top, bottom + BAND_BOT)
        y = bottom + BAND_BOT + BAND_GAP
    return B, bands, y


def svg(PART, L, COL, CIRC, compact=False, idp="a"):
    B, bands, H = layout(compact)
    g = lambda k: B[k]
    R = {}
    gapv = lambda b1, b2: (bands[b1][1] + bands[b2][0]) / 2
    sim, plc, edge, hub, fuxa, gate, prov, hubx, otag = (B[k] for k in ("sim", "plc", "edge", "hub", "fuxa", "gate", "prov", "hubx", "otag"))
    gw, dmzb, loader, dmzi, dmzp = (B[k] for k in ("gw", "dmzb", "loader", "dmzi", "dmzp"))
    am, flink, zk, trainer, submit, coll, kafka, pg, kinit, hist, iti, prom, graf, kexp, cadv = (B[k] for k in (
        "am", "flink", "zk", "trainer", "submit", "coll", "kafka", "pg", "kinit", "hist", "iti", "prom", "graf", "kexp", "cadv"))
    seed, graph, ai, host, web, bus, llm = (B[k] for k in ("seed", "graph", "ai", "host", "web", "bus", "llm"))
    X1, X2 = 800, 1000

    def hz(a, b, gx, dy=0, pref=None):
        """a 의 오른쪽(또는 왼쪽) 변에서 b 로 가는 가로선. 높이가 겹치면 곧게, 아니면 열 사이 틈 gx 로 꺾는다."""
        lo, hi = max(a.y, b.y), min(a.b, b.b)
        left_to_right = a.r <= b.x
        ax = a.r if left_to_right else a.x
        bxx = b.x if left_to_right else b.r
        if hi - lo > 24 + dy:
            y = (pref if pref is not None and lo + 8 < pref < hi - 8 else lo + min(32, (hi - lo) / 2)) + dy
            return [(ax, y), (bxx, y)]
        ya, yb = a.y + 30 + dy, b.y + 30 + dy
        return [(ax, ya), (gx, ya), (gx, yb), (bxx, yb)]

    R["modbus_sim"] = [(X1, plc.y), (X1, sim.b)]
    R["modbus_plc"] = [(X1, edge.y), (X1, plc.b)]
    R["edge_mqtt"] = [(X1, edge.b), (X1, hub.y)]
    R["recv_mqtt"] = [(X2, edge.b), (X2, hub.y)]
    R["recv_crew"] = [(edge.r, edge.y + 40), (1190, edge.y + 40), (1190, sim.cy), (sim.r, sim.cy)]
    R["fuxa_mqtt"] = [(fuxa.x, fuxa.b - 26), (1200, fuxa.b - 26), (1200, hub.y + 40), (hub.r, hub.y + 40)]
    R["gate_fuxa"] = [(gate.cx, gate.y), (gate.cx, fuxa.b)]
    R["prov_fuxa"] = [(prov.r, prov.cy), (1635, prov.cy), (1635, fuxa.y + 30), (fuxa.r, fuxa.y + 30)]
    R["bridge_out"] = [(X1, hub.b), (X1, dmzb.y)]
    R["bridge_in"] = [(X2, hub.b), (X2, dmzb.y)]
    R["gw_pub"] = hz(gw, dmzb, 435)
    R["loader_sub"] = hz(loader, dmzb, 1200)
    R["loader_write"] = [(loader.cx, loader.b), (loader.cx, dmzi.y)]
    R["coll_sub"] = [(X1, coll.y), (X1, dmzb.b)]
    R["coll_disp"] = [(X2, coll.y), (X2, dmzb.b)]
    yc = coll.y + min(100, coll.h - 14)
    R["coll_gw"] = [(coll.x, yc), (452, yc), (452, gw.b - 30), (gw.r, gw.b - 30)]
    R["prom_fed"] = [(prom.cx, prom.y), (prom.cx, dmzp.b)]
    R["coll_kafka"] = [(X1, coll.b), (X1, kafka.y)]
    R["flink_kafka"] = hz(flink, kafka, 435)
    R["flink_zk"] = [(flink.cx, flink.b), (flink.cx, zk.y)]
    R["hist_kafka"] = hz(hist, kafka, 1212, pref=max(hist.y, kafka.y) + 40)
    R["hist_iti"] = [(hist.cx, hist.b), (hist.cx, iti.y)]
    R["coll_am"] = hz(coll, am, 440)
    R["am_coll"] = hz(am, coll, 448, dy=22)
    R["coll_pg"] = [(coll.r, coll.b - 18), (1186, coll.b - 18), (1186, pg.y + 30), (pg.r, pg.y + 30)]
    R["kinit_kafka"] = [(kinit.x, kinit.cy), (1206, kinit.cy), (1206, kafka.y + 18), (kafka.r, kafka.y + 18)]
    g45 = gapv("B4", "B5")
    R["bus_kafka"] = [(bus.x + 40, bus.y), (bus.x + 40, g45 - 6), (1218, g45 - 6), (1218, kafka.b - 26), (kafka.r, kafka.b - 26)]
    R["bus_pg"] = [(bus.x + 90, bus.y), (bus.x + 90, g45 + 6), (1196, g45 + 6), (1196, pg.cy + 20), (pg.r, pg.cy + 20)]
    R["ai_pg"] = [(X1, ai.y), (X1, pg.b)]
    R["ai_kafka"] = [(ai.x, ai.y + 30), (428, ai.y + 30), (428, kafka.b - 30), (kafka.x, kafka.b - 30)]
    R["ai_graph"] = hz(ai, graph, 440, dy=20)
    R["ai_llm"] = [(1120, ai.y), (1120, g45 + 18), (2215, g45 + 18), (2215, llm.y)]
    R["web_ai"] = hz(web, ai, 1200)
    R["host_it"] = [(host.r, host.y + 30), (web.cx, host.y + 30), (web.cx, web.b)]
    R["graf_prom"] = [(graf.cx, graf.y), (graf.cx, prom.b)]
    R["graf_iti"] = [(graf.x, graf.b - 24), (1640, graf.b - 24), (1640, iti.y + 30), (iti.r, iti.y + 30)]
    R["trainer_flink"] = [(trainer.x, trainer.cy), (24, trainer.cy), (24, flink.b - 40), (flink.x, flink.b - 40)]
    R["submit_flink"] = [(submit.x, submit.cy), (16, submit.cy), (16, flink.b - 24), (flink.x, flink.b - 24)]
    R["seed_graph"] = [(seed.cx, seed.b), (seed.cx, graph.y)]
    LP = {"recv_crew": 3, "coll_gw": 3, "fuxa_mqtt": 3, "prov_fuxa": 3, "ai_kafka": 3, "bus_kafka": 4, "bus_pg": 4, "ai_llm": 2, "coll_am": 0.72, "am_coll": 0.28,
          "coll_pg": 3, "kinit_kafka": 3, "graf_iti": 3, "trainer_flink": 3, "submit_flink": 3, "host_it": 2}
    PORT = {"bridge_out": "1883", "bridge_in": "1883", "coll_sub": "1883", "coll_disp": "1883", "coll_gw": "8088", "prom_fed": "9090"}

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H:.0f}" role="img" aria-label="ceco_demo 전체 아키텍처{"(간단)" if compact else "(상세)"}: 부품 {len(PART)}개 · 연결 {len(L)}개" class="arch{" arch-o" if compact else ""}">', "<defs>"]
    for k, col in COL.items():
        o.append(f'<marker id="{idp}-{k}" viewBox="0 0 10 10" refX="8.6" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{col}"/></marker>')
    o.append("</defs>")
    o.append(f'<rect width="{W}" height="{H:.0f}" fill="#ffffff"/>')
    xext = COLS["X"][0] - 22
    for bid, name, desc, bg, bd, fg, full in BANDS:
        y0, y1 = bands[bid]
        if bid.startswith("R"):
            o.append(f'<rect x="8" y="{y0}" width="{W - 16}" height="{y1 - y0}" rx="8" fill="#23292e"/>')
            continue
        x1 = W - 8 if full else xext - 10
        o.append(f'<rect x="8" y="{y0}" width="{x1 - 8}" height="{y1 - y0}" rx="14" fill="{bg}" stroke="{bd}" stroke-width="1.4"/>')
    y5 = bands["B5"][0]
    o.append(f'<rect x="{xext}" y="{y5}" width="{W - 8 - xext}" height="{bands["B5"][1] - y5}" rx="14" fill="#f4f5f6" stroke="#9aa3aa" stroke-width="1.4" stroke-dasharray="6 4"/>')
    o.append(f'<text x="{(xext + W - 8) / 2}" y="{y5 + 30}" font-size="17" font-weight="700" fill="#4b5963" text-anchor="middle">밖 (인터넷)</text>')

    def shorten(p, which, d):
        p = list(p)
        (x0, y0), (x1, y1) = (p[-2], p[-1]) if which == "end" else (p[1], p[0])
        ln = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 or 1
        nx, ny = x1 - (x1 - x0) / ln * d, y1 - (y1 - y0) / ln * d
        if which == "end":
            p[-1] = (nx, ny)
        else:
            p[0] = (nx, ny)
        return p

    STY = dict(data=("", 2.4), cmd=("", 3.2), alert=("7 4", 2.4), api=("", 1.8), mon=("2 4", 1.6), once=("9 5", 1.6), human=("", 1.8))
    drawn = [x for x in L.values() if x["key"] in R]
    for x in drawn:
        o.append(f'<polyline points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in R[x["key"]])}" fill="none" stroke="#ffffff" stroke-width="8" stroke-linejoin="round" opacity="0.9"/>')
    for x in drawn:
        p = R[x["key"]]
        arrow = {"fwd": "end", "back": "start", "both": "both"}[x["dir"]]
        for wch in ("start", "end"):
            if arrow in (wch, "both"):
                p = shorten(p, wch, 7 if wch == "start" else 1.5)
        dash, wd = STY[x["kind"]]
        m = (f' marker-end="url(#{idp}-{x["kind"]})"' if arrow in ("end", "both") else "") + (f' marker-start="url(#{idp}-{x["kind"]})"' if arrow in ("start", "both") else "")
        da = f' stroke-dasharray="{dash}"' if dash else ""
        o.append(f'<polyline points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in p)}" fill="none" stroke="{COL[x["kind"]]}" stroke-width="{wd}" stroke-linejoin="round"{da}{m}/>')
    for x in drawn:
        if x["kind"] in ("once", "human"):
            continue
        sx, sy = R[x["key"]][0]
        o.append(f'<circle cx="{sx}" cy="{sy}" r="5.2" fill="{COL[x["kind"]]}" stroke="#fff" stroke-width="1.5"/>')
    # 라우터 막대 글자(선 위)
    for bid in ("R1", "R2"):
        y0, y1 = bands[bid]
        t1, t2 = BAR_TEXT[bid]
        o.append(f'<text x="24" y="{y0 + 26}" font-size="15" font-weight="800" fill="#ffffff" paint-order="stroke" stroke="#23292e" stroke-width="6">{esc(t1)}</text>')
        o.append(f'<text x="24" y="{y0 + 50}" font-size="12.5" fill="#e6ecee" paint-order="stroke" stroke="#23292e" stroke-width="6">{esc(t2)}</text>')
    # 상자
    overflow = []
    for k, (band, col, order, left, right, opt) in BOX.items():
        bx = B[k]
        no, title, prod, zone, kind = PART[k]
        stroke, dash, fill = "#9aa7ae", "", "#ffffff"
        if kind == "once":
            stroke, dash, fill = "#8f989f", "6 4", "#fbfcfc"
        elif kind == "mon":
            stroke, dash, fill = "#7d8890", "2 3", "#fbfcfc"
        elif kind == "ext":
            stroke, dash, fill = "#5a6fbf", "4 3", "#f7f8fd"
        da = f' stroke-dasharray="{dash}"' if dash else ""
        o.append(f'<rect x="{bx.x}" y="{bx.y}" width="{bx.w}" height="{bx.h:.0f}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="1.5"{da}/>')
        small = k in SMALL
        ttl = CIRC[no] + " " + title
        o.append(f'<text x="{bx.x + 14}" y="{bx.y + 24}" font-size="{15 if small else 17}" font-weight="800" fill="#14212a">{esc(ttl)}</text>')
        if small:
            o.append(f'<text x="{bx.r - 12}" y="{bx.y + 24}" font-size="11.5" fill="#6b7780" text-anchor="end">{esc(prod.split(" · ")[-1])}</text>')
            if not compact:
                for i, t in enumerate(left):
                    o.append(rich(bx.x + 14, bx.y + 30 + (i + 1) * LH, t, 12, "#4b5963"))
                    if tw(t, 12) > bx.w - 28:
                        overflow.append((k, t))
            else:
                o.append(f'<text x="{bx.x + 14}" y="{bx.y + 42}" font-size="12" fill="#4b5963">{esc(prod)}</text>')
            if tw(ttl, 15) + tw(prod.split(" · ")[-1], 11.5) > bx.w - 36:
                overflow.append((k, "제목+제품 겹침"))
            continue
        o.append(f'<text x="{bx.x + 14}" y="{bx.y + 43}" font-size="12.5" fill="#4b5963">{esc(prod)}</text>')
        if tw(ttl, 17) > bx.w - 24 - (110 if k in ("gw", "edge", "plc") else 0):
            overflow.append((k, "제목 넘침"))
        if compact:
            continue
        o.append(f'<line x1="{bx.x + 10}" y1="{bx.y + 52}" x2="{bx.r - 10}" y2="{bx.y + 52}" stroke="#e1e6e9" stroke-width="1"/>')
        colw = bx.w if not right else (bx.w - 20) / 2
        for ci, lst in enumerate([left] + ([right] if right else [])):
            x0 = bx.x + 14 + ci * (colw + 10)
            for i, t in enumerate(lst):
                if not t:
                    continue
                o.append(rich(x0, bx.y + HEAD + 8 + i * LH, t))
                ind = (len(t) - len(t.lstrip(" "))) // 2 * 12
                if tw(t.strip()) + ind > colw - 22:
                    overflow.append((k, t))
        if right:
            xm = bx.x + 14 + colw + 2
            o.append(f'<line x1="{xm}" y1="{bx.y + 62}" x2="{xm}" y2="{bx.b - 10}" stroke="#eef1f3" stroke-width="1"/>')
    # 띠 제목
    for bid, name, desc, bg, bd, fg, full in BANDS:
        if bid.startswith("R"):
            continue
        y0 = bands[bid][0]
        o.append(f'<text x="24" y="{y0 + 30}" font-size="19" font-weight="800" fill="{fg}" paint-order="stroke" stroke="{bg}" stroke-width="8" stroke-linejoin="round">{esc(name)}<tspan font-size="14" font-weight="400" fill="#4b5963" dx="12">{esc(desc)}</tspan></text>')
    # 검사 표시
    for k, t in (("gw", "검사 1"), ("edge", "검사 2 · 수신기"), ("plc", "검사 3 · PLC")):
        bx = B[k]
        w = 16 + tw(t, 12)
        o.append(f'<g><rect x="{bx.r - w - 10:.1f}" y="{bx.y + 9}" width="{w:.1f}" height="21" rx="5" fill="#d1343f"/><text x="{bx.r - w / 2 - 10:.1f}" y="{bx.y + 24}" font-size="12" font-weight="700" fill="#ffffff" text-anchor="middle">{esc(t)}</text></g>')
    # 라우터를 지나는 포트
    for k, p in PORT.items():
        pts = R[k]
        x = pts[0][0] if pts[0][0] == pts[1][0] else None
        segs = list(zip(pts, pts[1:]))
        for (ax, ay), (bx_, by_) in segs:
            if ax == bx_:
                for bid in ("R1", "R2"):
                    y0, y1 = bands[bid]
                    if min(ay, by_) < y0 and max(ay, by_) > y1:
                        o.append(f'<text x="{ax + 8}" y="{y1 - 8}" font-size="12" font-weight="700" fill="#ffe08a" font-family="JetBrains Mono,Consolas,monospace">{p}</text>')
    # 선 번호 표
    for x in drawn:
        p = R[x["key"]]
        segs = list(zip(p, p[1:]))
        sel = LP.get(x["key"])
        if isinstance(sel, int):
            (ax, ay), (bx_, by_) = segs[sel - 1]
            mx, my = (ax + bx_) / 2, (ay + by_) / 2
        elif isinstance(sel, float):
            (ax, ay), (bx_, by_) = max(segs, key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1]))
            mx, my = ax + (bx_ - ax) * sel, ay + (by_ - ay) * sel
        else:
            s = max(segs, key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1]))
            mx, my = (s[0][0] + s[1][0]) / 2, (s[0][1] + s[1][1]) / 2
        lab = f"C{x['no']}"
        w = 12 + tw(lab, 11)
        col = COL[x["kind"]]
        filled = x["kind"] == "cmd"
        o.append(f'<g><rect x="{mx - w / 2:.1f}" y="{my - 10:.1f}" width="{w:.1f}" height="20" rx="10" fill="{col if filled else "#ffffff"}" stroke="{col}" stroke-width="1.3"/>'
                 f'<text x="{mx:.1f}" y="{my + 4.5:.1f}" font-size="11" font-weight="700" fill="{"#ffffff" if filled else col}" text-anchor="middle" font-family="JetBrains Mono,Consolas,monospace">{lab}</text></g>')
    # 그리지 않은 연결: 상자 위 작은 표
    tags = {}
    for x in L.values():
        if x["key"] in R:
            continue
        bs = x["b"] if isinstance(x["b"], list) else [x["b"]]
        for b in bs:
            tags.setdefault(b, []).append((f"C{x['no']}", x["kind"]))
        tags.setdefault(x["a"], []).append((f"C{x['no']} " + ("긁음" if "scrape" in x["key"] else "부름"), x["kind"]))
    for k, lst in tags.items():
        bx = g(k)
        cx = bx.r - 6
        if k in ("gw", "edge", "plc"):
            pass
        for t, kind in reversed(lst):
            w = 12 + tw(t, 10.5)
            col = COL[kind]
            o.append(f'<g><rect x="{cx - w:.1f}" y="{bx.y - 10}" width="{w:.1f}" height="18" rx="9" fill="#ffffff" stroke="{col}" stroke-width="1.1"{" stroke-dasharray=\"2 2\"" if kind == "mon" else ""}/>'
                     f'<text x="{cx - w / 2:.1f}" y="{bx.y + 3.5}" font-size="10.5" font-weight="700" fill="{col}" text-anchor="middle">{esc(t)}</text></g>')
            cx -= w + 4
        if cx < bx.x:
            overflow.append((k, "작은 표가 상자 폭을 넘음"))
    o.append("</svg>")
    return "\n".join(o), set(R), overflow, (W, H)
