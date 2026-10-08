# -*- coding: utf-8 -*-
"""마스터_가이드의 전체 아키텍처 그림(위 → 아래) SVG 생성기.
부품 번호 ①~㊲는 아래 box() 가 정본이다. 좌표는 손으로 정한 4열 격자:
  L 70–330 · S(척추) 420–720 · R 790–1000 · M(감시 레일) 1040–1180
사용: python master_arch_svg.py > arch.svg
"""
import html

W, H = 1200, 1905
CIRC = {i: chr(0x2460 + i - 1) for i in range(1, 21)}
CIRC.update({i: chr(0x3251 + i - 21) for i in range(21, 36)})
CIRC[36] = chr(0x32B1)
CIRC[37] = chr(0x32B2)

ZONES = [  # id, y0, y1, 이름, 설명, 배경, 테두리
    ("z0", 10, 132, "0 · 현장", "기계와 정비팀", "#f3f1ec", "#b9ae98"),
    ("z1", 140, 252, "1 · 제어", "PLC — 마지막 안전장치", "#fbf3e2", "#d6a64f"),
    ("z2", 260, 640, "2 · OT 공장 망", "외부와 끊겨도 혼자 돈다", "#fcefe2", "#cf8a45"),
    ("z3", 710, 990, "3 · DMZ 완충지대", "공장과 사무실이 만나는 유일한 곳", "#f0ecf8", "#8a76bf"),
    ("z4", 1060, 1512, "4 · IT 데이터 파이프라인", "기록·분석·경보", "#e7f3f6", "#3f8ea3"),
    ("z5", 1520, 1895, "5 · 업무 · AI", "판단은 사람, 제안은 AI", "#ebeffa", "#5a6fbf"),
]

ZDARK = dict(z0="#6b604a", z1="#8a6414", z2="#9a5a1c", z3="#5b4691", z4="#1f6378", z5="#394b98")
C = dict(data="#1f6f8b", req="#d1343f", disp="#7b4fc9", mon="#7d8890", once="#8f989f", human="#2b2f33")

# 부품: no, x, y, w, h, 제목, 제품, 설명, 모양(normal/once/ext/pill)
B = {}
def box(key, no, x, y, w, h, title, prod="", desc="", kind="normal", badge=""):
    B[key] = dict(no=no, x=x, y=y, w=w, h=h, title=title, prod=prod, desc=desc, kind=kind, badge=badge)

box("sim", 1, 420, 45, 300, 72, "현장 설비", "물리 모델 · 정비팀", "설비 8대 · 센서 17개 · Modbus 장치")
box("plc", 2, 420, 172, 300, 68, "PLC", "OpenPLC", "100 ms 스캔 · 운전 · 명령 검사 · 인터록")
box("edge", 3, 420, 296, 300, 100, "엣지 게이트웨이", "Node-RED", "", badge="⌁⑧")
box("hub", 4, 420, 452, 300, 88, "OT 허브 (공장 게시판)", "Mosquitto · MQTT", "UNS 토픽 · 계정별 ACL · 끊김 대기열 7.2만 건")
box("oper", 0, 800, 272, 190, 30, "운전원 (브라우저)", kind="pill")
box("gate", 6, 790, 330, 210, 64, "화면 관문", "Caddy", "계정 없으면 401")
box("fuxa", 5, 790, 452, 210, 88, "운전원 화면", "FUXA · SCADA/HMI", "값 보기 · 버튼 · 공정 알람")
box("prov", 34, 800, 574, 190, 50, "화면 넣기", "기동 때 1회", kind="once")
box("hubx", 7, 1040, 452, 140, 60, "허브 지표 변환", "Bento", badge="⌁⑧", kind="mon")
box("otmon", 8, 1040, 552, 140, 64, "OT 감시", "Prometheus agent", kind="mon")

box("gw", 13, 70, 755, 260, 90, "요청 게이트웨이", "Node-RED", "검사 1 · 30초 만료 도장", badge="⌁⑭")
box("dmzb", 10, 420, 755, 300, 90, "DMZ 브로커 (우편함)", "Mosquitto · MQTT", "먼저 연결하지 않고 받기만")
box("loader", 11, 790, 755, 210, 62, "DMZ 적재기", "Bento", badge="⌁⑭")
box("dmzinf", 12, 790, 880, 210, 72, "DMZ 원시 사본", "InfluxDB · 7일 보관", badge="⌁⑭")
box("dmzmon", 14, 1040, 760, 140, 64, "DMZ 감시", "Prometheus", kind="mon")

box("mes", 0, 70, 1098, 260, 44, "생산계획(MES) 흉내 지시", "스트림 ⑧ 입력", kind="reqpill")
box("coll", 16, 420, 1080, 300, 100, "IT 수집기", "Bento · 스트림 ①③~⑧", "모든 연결을 IT 쪽에서 연다", badge="⌁㉔")
box("am", 25, 790, 1088, 210, 76, "Alertmanager", "경보 묶기 · 억제", "정비 중·꺼진 설비 경보 접기")
box("itmon", 24, 1040, 1088, 140, 76, "IT 감시", "Prometheus", "세 구역 지표 모음", kind="mon")
box("flink", 17, 70, 1232, 260, 98, "Flink (실시간 검사관)", "잡 관리자 + 작업자", "규칙 · Z-Score · CEP · ONNX", badge="⌁㉔")
box("kafka", 15, 420, 1232, 300, 98, "Kafka (번호 매긴 장부)", "토픽 10개 · 디스크 보관", "계측 7일 · 요청·감사 30일")
box("itinf", 20, 790, 1232, 210, 62, "결과 저장·이력 적재", "InfluxDB 30일 · ㉑ Bento", badge="", kind="mon")
box("kexp", 26, 1040, 1232, 140, 48, "Kafka 지표", "kafka-exporter", badge="⌁㉔", kind="mon")
box("cadv", 27, 1040, 1292, 140, 48, "컨테이너 지표", "cAdvisor", badge="⌁㉔", kind="mon")
box("zk", 18, 70, 1360, 125, 50, "ZooKeeper", "Flink 복구 기록")
box("train", 19, 205, 1360, 125, 50, "모델 학습기", "기동 때 1회", kind="once")
box("submit", 36, 70, 1420, 125, 50, "잡 제출", "기동 때 1회", kind="once")
box("topics", 35, 205, 1420, 125, 50, "토픽 만들기", "기동 때 1회", kind="once")
box("graf", 23, 790, 1342, 210, 66, "Grafana", "그래프 4장", "공정·이상·경보·인프라", kind="mon")

box("biz", 31, 70, 1566, 260, 86, "업무 서비스", "Python", "사건 접수 · 요청·정비 결과 판정")
box("ai", 29, 420, 1566, 300, 86, "AI 업무 도우미", "FastAPI · 에이전트 · 판단 엔진", "원인 분석 · 정비 계획 · 단계 실행")
box("pg", 22, 790, 1566, 210, 86, "업무 DB (정본)", "PostgreSQL", "요청·승인·감사 · 기업 숫자")
box("neo", 28, 70, 1724, 230, 70, "온톨로지 그래프", "Neo4j", "설비·고장·매뉴얼·정비 대안")
box("seed", 37, 70, 1814, 230, 50, "그래프 채우기", "기동 때 1회", kind="once")
box("aiweb", 30, 420, 1724, 300, 70, "AI 화면", "Vue + nginx", "사건 · 정비 계획 카드 · 승인")
box("staff", 0, 480, 1830, 180, 30, "담당자 (브라우저)", kind="pill")
box("llm", 32, 1030, 1724, 160, 70, "OpenAI", "밖 · 인터넷", "gpt-6-luna · 임베딩", kind="ext")

# 선: 종류, 점들, 화살(start/end/both), 연 쪽(start/end/None), 라벨[(x,y,글,정렬)]
E = []
def line(kind, pts, arrow="end", dot="start", labels=(), width=None):
    E.append(dict(kind=kind, pts=pts, arrow=arrow, dot=dot, labels=list(labels), width=width))

# 현장·제어
line("data", [(570, 172), (570, 117)], "both", "start", [(580, 150, "Modbus TCP · 100 ms", "start")])
line("data", [(660, 296), (660, 240)], "both", "start", [(670, 284, "Modbus · 250 ms", "start")])
line("req", [(480, 296), (480, 240)], "end", "start", [(470, 284, "요청 쓰기 → PLC (검사 3)", "end")])
line("req", [(420, 330), (380, 330), (380, 88), (420, 88)], "both", "start", [(372, 180, "정비 작업 지시", "end"), (372, 196, "→ 정비팀 · 소견", "end")])
# 엣지 ↔ 허브
line("data", [(660, 396), (660, 452)], "both", "start", [(670, 420, "값 발행 · 명령 받기", "start")])
line("req", [(480, 452), (480, 396)], "end", "end", [(470, 428, "요청 받기 (MQTT 5)", "end")])
# 사람 → 관문 → FUXA
line("human", [(895, 302), (895, 330)], "end", "start")
line("human", [(895, 394), (895, 452)], "both", "start", [(905, 428, "HTTP", "start")])
line("data", [(790, 478), (720, 478)], "both", "start", [(755, 470, "구독·명령", "middle")])
line("disp", [(720, 518), (790, 518)], "end", "end", [(755, 534, "분석 경고", "middle")])
line("once", [(895, 578), (895, 540)], "end", "start")
# OT 감시
line("mon", [(1040, 470), (1020, 470), (1020, 432), (705, 432), (705, 452)], "start", "start", [(960, 426, "허브 상태($SYS) 구독", "end")])
line("mon", [(1110, 552), (1110, 512)], "start", "start", [(1118, 537, "긁기", "start")])
line("mon", [(1110, 616), (1110, 760)], "end", "start", [(1102, 738, "remote_write", "end")])
# 브리지(연결 1개, OT 허브가 연다)
line("data", [(660, 540), (660, 755)], "end", "start", [(670, 600, "브리지 out", "start"), (670, 616, "계측·상태·응답", "start")])
line("disp", [(570, 755), (570, 540)], "end", "end", [(578, 600, "in", "start"), (578, 616, "분석 경고", "start")])
line("req", [(480, 755), (480, 540)], "end", "end", [(470, 600, "브리지 in", "end"), (470, 616, "작업 요청(30초 만료)", "end")])
# DMZ 안
line("req", [(330, 800), (420, 800)], "end", "start", [(375, 792, "QoS 1", "middle")])
line("data", [(790, 786), (720, 786)], "start", "start", [(755, 778, "구독", "middle")])
line("data", [(895, 817), (895, 880)], "end", "start", [(905, 852, "원시값 기록", "start")])
# IT → DMZ (모두 IT가 연다)
line("data", [(660, 1080), (660, 845)], "start", "start", [(670, 930, "구독: 계측·상태·응답", "start")])
line("disp", [(570, 1080), (570, 845)], "end", "start", [(578, 960, "분석 경고 표시 발행", "start")])
line("req", [(460, 1080), (460, 960), (200, 960), (200, 845)], "end", "start",
     [(210, 900, "HTTP POST", "start"), (210, 916, "승인된 요청만", "start")])
line("data", [(1000, 1396), (1015, 1396), (1015, 916), (1000, 916)], "start", "start", [(1010, 968, "원시 사본 조회", "end")])
line("mon", [(1110, 1088), (1110, 824)], "start", "start", [(1118, 960, "federate", "start")])
# IT 안
line("req", [(330, 1120), (420, 1120)], "end", "start")
line("data", [(660, 1180), (660, 1232)], "both", "start", [(670, 1208, "쓰기 · 읽기", "start")])
line("req", [(480, 1232), (480, 1180)], "end", "end", [(470, 1210, "승인 토픽 읽기", "end")])
line("data", [(330, 1282), (420, 1282)], "both", "start", [(375, 1274, "raw", "middle"), (375, 1298, "결과", "middle")])
line("data", [(720, 1110), (790, 1110)], "end", "start", [(755, 1102, "넣기", "middle")])
line("data", [(790, 1146), (720, 1146)], "end", "start", [(755, 1162, "알림", "middle")])
line("data", [(720, 1262), (790, 1262)], "end", "end", [(755, 1254, "결과", "middle")])
line("data", [(895, 1342), (895, 1294)], "start", "start")
line("mon", [(1040, 1126), (1000, 1126)], "end", "start")
line("mon", [(1000, 1360), (1028, 1360), (1028, 1180), (1070, 1180), (1070, 1164)], "start", "start")
line("data", [(132, 1330), (132, 1362)], "both", "start")
line("once", [(267, 1362), (267, 1330)], "end", "start", [(275, 1350, "ONNX", "start")])
line("once", [(70, 1444), (52, 1444), (52, 1300), (70, 1300)], "end", "start")
line("once", [(330, 1444), (392, 1444), (392, 1316), (420, 1316)], "end", "start")
# 업무·AI
line("data", [(440, 1330), (440, 1500), (300, 1500), (300, 1566)], "both", "end", [(432, 1492, "alert·응답 읽기, 사본 쓰기", "end")])
line("req", [(570, 1566), (570, 1330)], "end", "start", [(578, 1460, "승인된 요청 ID", "start"), (578, 1476, "(request.approved)", "start")])
line("data", [(720, 1608), (790, 1608)], "both", "start")
line("data", [(720, 1174), (746, 1174), (746, 1586), (790, 1586)], "end", "start", [(740, 1420, "경보·요청 기록", "end")])
line("data", [(700, 1566), (700, 1542), (1015, 1542), (1015, 1396)], "start", "start", [(1008, 1534, "AI도 원시 사본 조회", "end")])
line("data", [(200, 1652), (200, 1684), (895, 1684), (895, 1652)], "both", "start", [(210, 1700, "판정·사건 기록", "start")])
line("data", [(420, 1636), (386, 1636), (386, 1759), (300, 1759)], "both", "start")
line("data", [(570, 1724), (570, 1652)], "both", "start")
line("human", [(570, 1830), (570, 1794)], "end", "start")
line("data", [(706, 1652), (706, 1706), (1110, 1706), (1110, 1724)], "both", "start", [(1000, 1720, "HTTPS · 인터넷", "end")])
line("once", [(185, 1818), (185, 1794)], "end", "start")

ROUTERS = [  # y0, y1, 제목, 설명, 구멍[(x0,x1,글)] — 글은 구멍 오른쪽 흰 글씨
    (650, 700, "⑨ 구역 라우터 (방화벽)", "OT → DMZ 새 연결만 · 반대 방향은 차단",
     [(466, 674, "1883 · MQTT 브리지 = OT 허브가 연 연결 1개"), (1090, 1130, "9090")]),
    (1000, 1050, "⑨ 구역 라우터 (방화벽)", "IT → DMZ 새 연결만 · DMZ→IT, IT→OT 차단",
     [(446, 474, "8088"), (556, 674, "1883"), (1003, 1027, "8086"), (1090, 1130, "9090")]),
]
ROUTER_PORT_NOTE = []

def esc(t): return html.escape(t, quote=True)

def text(x, y, t, size=13, weight=400, fill="#1d2830", anchor="start", extra=""):
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{extra}>{esc(t)}</text>'

out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="CECO 데모 전체 아키텍처: 현장에서 AI까지 위에서 아래로" class="arch">']
out.append('<defs>')
for k, col in C.items():
    out.append(f'<marker id="a-{k}" viewBox="0 0 10 10" refX="8.6" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{col}"/></marker>')
out.append('</defs>')
out.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')

for zid, y0, y1, name, desc, bg, bd in ZONES:
    out.append(f'<rect x="6" y="{y0}" width="{W-12}" height="{y1-y0}" rx="14" fill="{bg}" stroke="{bd}" stroke-width="1.4"/>')
    out.append(f'<text x="22" y="{y0 + 27}" font-size="17" font-weight="700" fill="{ZDARK[zid]}">{esc(name)}<tspan font-size="13" font-weight="400" fill="#4b5963" dx="10">{esc(desc)}</tspan></text>')

# 선(후광 먼저, 그다음 선)
def pts_str(p): return " ".join(f"{x},{y}" for x, y in p)
STY = dict(data=("", 2.2), req=("", 3.0), disp=("7 4", 2.2), mon=("2 4", 1.6), once=("9 5", 1.5), human=("", 1.6))
for e in E:
    out.append(f'<polyline points="{pts_str(e["pts"])}" fill="none" stroke="#ffffff" stroke-width="7" stroke-linejoin="round" opacity="0.9"/>')
def shorten(p, which, d):
    p = list(p)
    if which == "end": (x0, y0), (x1, y1) = p[-2], p[-1]
    else: (x0, y0), (x1, y1) = p[1], p[0]
    L = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 or 1
    nx, ny = x1 - (x1 - x0) / L * d, y1 - (y1 - y0) / L * d
    if which == "end": p[-1] = (nx, ny)
    else: p[0] = (nx, ny)
    return p
for e in E:
    p = e["pts"]
    for w in ("start", "end"):
        if e["arrow"] in (w, "both"):
            p = shorten(p, w, 7 if e["dot"] == w else 1.5)
    e["draw"] = p
for e in E:
    dash, wd = STY[e["kind"]]
    col = C[e["kind"]]
    m = ""
    if e["arrow"] in ("end", "both"): m += f' marker-end="url(#a-{e["kind"]})"'
    if e["arrow"] in ("start", "both"): m += f' marker-start="url(#a-{e["kind"]})"'
    da = f' stroke-dasharray="{dash}"' if dash else ""
    out.append(f'<polyline points="{pts_str(e["draw"])}" fill="none" stroke="{col}" stroke-width="{wd}" stroke-linejoin="round"{da}{m}/>')

# 라우터 막대(선 위에 그려 구멍으로 통과를 보인다)
for y0, y1, lt, rt, holes in ROUTERS:
    out.append(f'<rect x="6" y="{y0}" width="{W-12}" height="{y1-y0}" rx="6" fill="#23292e"/>')
    for hx0, hx1, ht in holes:
        out.append(f'<rect x="{hx0}" y="{y0-2}" width="{hx1-hx0}" height="{y1-y0+4}" rx="4" fill="#ffffff" stroke="#23292e" stroke-width="1.2"/>')
        if ht:
            out.append(text(hx1 + 6, (y0 + y1) / 2 + 5, ht, 12, 700, "#ffe08a"))
    out.append(text(22, y0 + 21, lt, 14, 700, "#ffffff"))
    out.append(text(22, y0 + 40, rt, 12.5, 400, "#dfe5e8"))
# 라우터 구멍 사이로 지나가는 선을 다시 그림
for e in E:
    xs = [p[0] for p in e["pts"]]; ys = [p[1] for p in e["pts"]]
    for (a, b) in zip(e["pts"], e["pts"][1:]):
        if a[0] == b[0]:
            for y0, y1, *_ in ROUTERS:
                lo, hi = min(a[1], b[1]), max(a[1], b[1])
                if lo < y0 and hi > y1:
                    dash, wd = STY[e["kind"]]
                    da = f' stroke-dasharray="{dash}"' if dash else ""
                    out.append(f'<line x1="{a[0]}" y1="{y0-2}" x2="{a[0]}" y2="{y1+2}" stroke="{C[e["kind"]]}" stroke-width="{wd}"{da}/>')
for x, y, t, anc in ROUTER_PORT_NOTE:
    out.append(text(x, y, t, 11.5, 700, "#23292e", anc))

# 연 쪽 표시 ●
def endpoint(e, which):
    return e["pts"][0] if which == "start" else e["pts"][-1]
for e in E:
    if e["dot"]:
        x, y = endpoint(e, e["dot"])
        out.append(f'<circle cx="{x}" cy="{y}" r="5" fill="{C[e["kind"]]}" stroke="#fff" stroke-width="1.5"/>')

# 상자
for k, b in B.items():
    x, y, w, h = b["x"], b["y"], b["w"], b["h"]
    kind = b["kind"]
    if kind == "pill":
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h/2}" fill="#2b2f33"/>')
        out.append(text(x + w / 2, y + h / 2 + 5, b["title"], 13, 700, "#ffffff", "middle"))
        continue
    if kind == "reqpill":
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="#fff5f5" stroke="{C["req"]}" stroke-width="1.6" stroke-dasharray="6 3"/>')
        out.append(text(x + 14, y + 19, b["title"], 13.5, 700, C["req"]))
        out.append(text(x + 14, y + 36, b["prod"], 12, 400, "#5a6872"))
        continue
    stroke, sw, dash, fill = "#9aa7ae", 1.3, "", "#ffffff"
    if kind == "once": stroke, dash, fill = "#8f989f", "6 4", "#fbfcfc"
    if kind == "ext": stroke, dash, fill = "#5a6fbf", "4 3", "#f7f8fd"
    if kind == "mon": stroke, dash, fill = "#aab4ba", "2 3", "#f6f8f9"
    da = f' stroke-dasharray="{dash}"' if dash else ""
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{da} filter="url(#none)"/>')
    tx = x + 12
    ty = y + 22
    num = CIRC.get(b["no"], "")
    small = w <= 160
    tsize = 13.5 if small else 15
    out.append(text(tx, ty, f"{num} {b['title']}" if num else b["title"], tsize, 700, "#1d2830"))
    if b["prod"]:
        out.append(text(tx, ty + 18 if h >= 56 else ty + 17, b["prod"], 12 if small else 12.5, 400, "#4b5963"))
    if b["desc"] and k != "edge":
        out.append(text(tx, ty + 36, b["desc"], 12 if small else 12.5, 400, "#1f6f8b" if not small else "#4b5963"))
    if b["badge"]:
        out.append(text(x + w - 8, (y + h - 7) if small else (y + 17), b["badge"], 12, 700, "#7d8890", "end"))
# 엣지 안의 두 탭
e = B["edge"]
out.append(f'<rect x="432" y="340" width="134" height="46" rx="6" fill="#fff4f4" stroke="{C["req"]}" stroke-width="1.2"/>')
out.append(text(499, 359, "OT 수신기 탭", 12.5, 700, C["req"], "middle"))
out.append(text(499, 376, "검사 2", 12, 400, C["req"], "middle"))
out.append(f'<rect x="574" y="340" width="134" height="46" rx="6" fill="#eef6f9" stroke="{C["data"]}" stroke-width="1.2"/>')
out.append(text(641, 359, "수집·명령 탭", 12.5, 700, C["data"], "middle"))
out.append(text(641, 376, "디스크 버퍼 7.2만 건", 12, 400, C["data"], "middle"))

# 선 라벨(흰 바탕)
for e in E:
    for (x, y, t, anc) in e["labels"]:
        out.append(text(x, y, t, 12, 600, C[e["kind"]] if e["kind"] != "mon" else "#5f6a71", anc,
                        ' paint-order="stroke" stroke="#ffffff" stroke-width="4" stroke-linejoin="round"'))

out.append('<circle cx="1015" cy="1542" r="3.5" fill="#1f6f8b"/>')
out.append('</svg>')
print("\n".join(out))
