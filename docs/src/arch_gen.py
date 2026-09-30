# -*- coding: utf-8 -*-
"""docs/시스템_아키텍처.html 생성기. 부품·선을 한 곳에 정의하고 그림과 본문을 같은 번호로 만든다."""
import html, math, pathlib, re, sys

OUT = pathlib.Path(sys.argv[1])

# ── 부품: id, 이름, 제품, 구역, x, y, w, h, 도우미 여부 ──
N = [
 ("sim", "가상설비", "Python · 물리 계산(배속 600)", "plant", 20, 420, 130, 76, False),
 ("plc", "PLC", "OpenPLC Runtime v4.2.4", "ot", 180, 440, 130, 56, False),
 ("edge", "엣지 게이트웨이", "Node-RED 5.0.7 · 수집·명령 탭 + OT 수신기 탭", "ot", 180, 262, 130, 92, False),
 ("hub", "OT 허브", "Mosquitto 2.1.2 (MQTT)", "ot", 350, 280, 126, 56, False),
 ("fuxa", "운전원 화면", "FUXA 1.3.4 (SCADA/HMI)", "ot", 350, 520, 126, 56, False),
 ("gate", "화면 관문", "Caddy 2.11.4 (계정 확인)", "ot", 350, 660, 126, 56, False),
 ("hubx", "허브 지표 변환", "Bento 1.21.2 ($SYS → 지표)", "ot", 180, 110, 130, 56, False),
 ("otag", "OT 감시", "Prometheus 3.13.4 (agent)", "ot", 350, 110, 126, 56, False),
 ("router", "구역 라우터", "iptables (허용 경로만 넘김)", "router", 0, 0, 0, 0, False),
 ("dmzb", "DMZ 브로커", "Mosquitto 2.1.2 (MQTT)", "dmz", 580, 290, 160, 56, False),
 ("loader", "DMZ 적재기", "Bento 1.21.2", "dmz", 580, 170, 160, 56, False),
 ("dmzi", "DMZ 원시 사본", "InfluxDB 2.9.1 (7일)", "dmz", 580, 60, 160, 56, False),
 ("gw", "DMZ 요청 게이트웨이", "Node-RED 5.0.7 (편집기 없음)", "dmz", 580, 470, 160, 56, False),
 ("dmzp", "DMZ 감시", "Prometheus 3.13.4", "dmz", 580, 640, 160, 56, False),
 ("kafka", "Kafka", "Apache Kafka 4.3.1 (토픽 10개)", "it", 1000, 300, 150, 56, False),
 ("coll", "IT 수집기", "Bento 1.21.2 · 스트림 ①~⑧", "it", 830, 250, 150, 176, False),
 ("flink", "Flink", "Flink 2.2.1 (잡 관리자 + 작업자)", "it", 1190, 300, 150, 56, False),
 ("zk", "ZooKeeper", "3.9.5 (Flink 복구 기록)", "it", 1190, 190, 150, 56, False),
 ("trainer", "모델 학습기", "Python (기동 때 ONNX 생성)", "it", 1190, 410, 150, 56, True),
 ("iti", "IT 결과 저장", "InfluxDB 2.9.1", "it", 1000, 60, 150, 56, False),
 ("pg", "업무 DB", "PostgreSQL 18.6 (plant · ai)", "it", 1000, 520, 150, 56, False),
 ("graf", "Grafana", "Grafana 13.2.3 (그래프 4장)", "it", 830, 60, 150, 56, False),
 ("prom", "IT 감시", "Prometheus 3.13.4", "it", 830, 640, 150, 56, False),
 ("am", "Alertmanager", "v0.34.1 (묶기·억제)", "it", 830, 520, 150, 56, False),
 ("kexp", "Kafka 지표", "kafka-exporter 1.10.0", "it", 1190, 520, 150, 56, False),
 ("cadv", "컨테이너 지표", "cAdvisor 0.60.6", "it", 1190, 640, 150, 56, False),
 ("graph", "온톨로지 그래프", "Neo4j 5.26 Community", "it", 1000, 920, 150, 56, False),
 ("ai", "AI 업무 도우미", "FastAPI 백엔드(에이전트·검색·승인)", "it", 1000, 800, 150, 64, False),
 ("web", "AI 화면", "nginx 1.28 + Vue 화면", "it", 830, 800, 150, 64, False),
 ("bus", "업무 서비스", "Python (사건 접수·요청 판정)", "it", 1190, 800, 150, 64, False),
 ("llm", "LiteLLM", "GCP (LLM·임베딩)", "out", 1374, 800, 110, 64, False),
 ("host", "사람·시험 도구", "호스트 127.0.0.1 공개 포트", "host", 620, 1040, 180, 56, False),
 ("prov", "화면 넣기", "fuxa-provisioner (1회)", "ot", 180, 660, 130, 56, True),
 ("kinit", "토픽 만들기", "kafka-init (1회)", "it", 1000, 410, 150, 56, True),
 ("submit", "잡 제출", "flink-job-submitter (1회)", "it", 1190, 60, 150, 56, True),
 ("seed", "그래프 채우기", "graph-seed (1회)", "it", 1190, 920, 150, 56, True),
]
NODE = {n[0]: dict(zip(["id", "name", "prod", "zone", "x", "y", "w", "h", "helper"], n)) for n in N}
for i, n in enumerate(N, 1):
    NODE[n[0]]["no"] = i
RX = 507    # 라우터 막대(OT|DMZ) 가운데
RX2 = 796   # 라우터 막대(DMZ|IT) 가운데. 같은 라우터 한 대를 두 번 그린다
TAGONLY = {"otag_scrape", "dmzp_scrape", "prom_scrape"}   # 감시 긁기는 선 대신 대상 상자에 작은 표

# ── 선: id, 연 쪽, 받는 쪽(목록이면 부채꼴), 방향(fwd: 연 쪽→받는 쪽, back, both, file), 종류, 경유점, 라벨 위치 ──
L = [
 ("modbus_sim", "plc", "sim", "both", "data", [], None),
 ("modbus_plc", "edge", "plc", "both", "data", [], None),
 ("edge_mqtt", "edge", "hub", "both", "data", [(330, 294)], (330, 277)),
 ("recv_mqtt", "edge", "hub", "both", "req", [(330, 326)], (330, 346)),
 ("fuxa_mqtt", "fuxa", "hub", "both", "data", [], None),
 ("gate_fuxa", "gate", "fuxa", "both", "data", [], None),
 ("hubx_sys", "hubx", "hub", "back", "mon", [], None),
 ("otag_scrape", "otag", ["edge", "hubx"], "back", "mon", [], None),
 ("bridge_out", "hub", "dmzb", "fwd", "data", [(RX, 300)], (550, 300)),
 ("bridge_in", "hub", "dmzb", "back", "req", [(RX, 326)], (550, 326)),
 ("otag_rw", "otag", "dmzp", "fwd", "mon", [(RX, 150), (548, 150), (548, 680)], (548, 600)),
 ("loader_sub", "loader", "dmzb", "back", "data", [], None),
 ("loader_write", "loader", "dmzi", "fwd", "data", [], None),
 ("gw_pub", "gw", "dmzb", "fwd", "req", [], None),
 ("dmzp_scrape", "dmzp", ["loader", "gw", "dmzi"], "back", "mon", [], None),
 ("coll_sub", "coll", "dmzb", "back", "data", [(RX2, 300)], (760, 300)),
 ("coll_disp", "coll", "dmzb", "fwd", "data", [(RX2, 330)], (760, 330)),
 ("coll_gw", "coll", "gw", "both", "req", [(RX2, 400), (760, 400), (760, 498)], (760, 450)),
 ("graf_dmzi", "graf", "dmzi", "back", "data", [(RX2, 80)], (760, 80)),
 ("ai_dmzi", "ai", "dmzi", "back", "data", [(1015, 782), (812, 782), (812, 106), (RX2, 106)], (812, 740)),
 ("prom_fed", "prom", "dmzp", "back", "mon", [(RX2, 668)], (760, 668)),
 ("coll_kafka", "coll", "kafka", "both", "data", [], None),
 ("flink_kafka", "flink", "kafka", "both", "data", [], (1170, 288)),
 ("flink_zk", "flink", "zk", "both", "data", [], None),
 ("coll_iti", "coll", "iti", "fwd", "data", [], None),
 ("coll_am", "coll", "am", "fwd", "data", [(870, 470)], None),
 ("am_coll", "am", "coll", "fwd", "data", [(940, 470)], None),
 ("coll_pg", "coll", "pg", "both", "data", [(985, 380), (985, 548)], (985, 470)),
 ("bus_kafka", "bus", "kafka", "both", "data", [(1166, 834), (1166, 340)], (1166, 700)),
 ("bus_pg", "bus", "pg", "both", "data", [], None),
 ("ai_pg", "ai", "pg", "both", "data", [], (1075, 690)),
 ("ai_kafka", "ai", "kafka", "fwd", "req", [(1158, 812), (1158, 330)], (1158, 620)),
 ("ai_graph", "ai", "graph", "both", "data", [], None),
 ("ai_flink", "ai", "flink", "back", "data", [(1174, 824), (1174, 318)], (1174, 760)),
 ("ai_llm", "ai", "llm", "both", "data", [(1120, 884), (1350, 884), (1350, 832)], None),
 ("web_ai", "web", "ai", "both", "data", [], None),
 ("graf_iti", "graf", "iti", "back", "data", [], None),
 ("graf_prom", "graf", "prom", "back", "mon", [(822, 96), (822, 676)], (822, 600)),
 ("prom_scrape", "prom", ["kexp", "cadv", "coll", "flink", "iti"], "back", "mon", [], None),
 ("prom_am", "prom", "am", "fwd", "mon", [], None),
 ("kexp_kafka", "kexp", "kafka", "back", "mon", [(1182, 548), (1182, 348)], (1182, 470)),
 ("trainer_flink", "trainer", "flink", "file", "file", [], None),
 ("host_router", "host", "gate", "both", "data", [(RX, 1068), (486, 1068), (486, 688)], (486, 900)),
 ("host_it", "host", "web", "both", "data", [(905, 1068)], (905, 1022)),
 ("mes_coll", "host", "coll", "fwd", "req", [(994, 1060), (994, 444), (950, 444)], (994, 700)),
 ("prov_fuxa", "prov", "fuxa", "fwd", "file", [], None),
 ("kinit_kafka", "kinit", "kafka", "fwd", "file", [], None),
 ("submit_flink", "submit", "flink", "fwd", "file", [(1346, 88), (1346, 328)], (1346, 200)),
 ("seed_graph", "seed", "graph", "fwd", "file", [], None),
]
LINE = {}
for i, l in enumerate(L, 1):
    LINE[l[0]] = dict(zip(["id", "a", "b", "dir", "kind", "via", "lp"], l)); LINE[l[0]]["no"] = i

# 라우터를 지나는 선의 포트 표시
PORT = {"bridge_out": "1883", "bridge_in": "1883", "otag_rw": "9090", "coll_sub": "1883", "coll_disp": "1883", "coll_gw": "8088",
        "graf_dmzi": "8086", "ai_dmzi": "8086", "prom_fed": "9090", "host_router": "21881"}


def n(i): return f'<span class="nref">{NODE[i]["no"]}</span>'
def nn(i): return f'{n(i)} {NODE[i]["name"]}'
def l(i): return f'<a class="lref l-{LINE[i]["kind"]}" href="#l{LINE[i]["no"]}">L{LINE[i]["no"]}</a>'
def sub(t):
    t = re.sub(r"\{n:(\w+)\}", lambda m: n(m.group(1)), t)
    t = re.sub(r"\{nn:(\w+)\}", lambda m: nn(m.group(1)), t)
    return re.sub(r"\{l:(\w+)\}", lambda m: l(m.group(1)), t)


# ═════════ 그림 ═════════
W, H = 1500, 1110
svg = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="시스템 전체 그림: 부품 {len(N)}개와 선 {len(L)}개" class="arch">']
svg.append('<defs>')
for k in ("data", "req", "mon", "file"):
    svg.append(f'<marker id="ar-{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
               f'<path d="M0,0 L10,5 L0,10 z" class="mk-{k}"/></marker>')
svg.append('</defs>')
Z = [("plant", 8, 20, 152, 1000, "현장"), ("ot", 168, 20, 318, 1000, "OT · 공장 망 (ot-net, 외부 차단)"),
     ("dmz", 530, 20, 246, 1000, "DMZ · 완충 망 (dmz-net, 외부 차단)"), ("it", 816, 20, 536, 1000, "IT · 사무 망 (it-net)"),
     ("out", 1360, 20, 134, 1000, "밖(인터넷)")]
for z, x, y, w, h, t in Z:
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" class="zone z-{z}"/>')
    svg.append(f'<text x="{x+12}" y="1008" class="zlabel zl-{z}">{t}</text>')
for rx in (RX, RX2):
    svg.append(f'<rect x="{rx-14}" y="24" width="28" height="1060" rx="6" class="routerbar"/>')
    svg.append(f'<g transform="translate({rx+5},560) rotate(-90)"><text class="rlabel" text-anchor="middle">'
               f'{NODE["router"]["no"]}  구역 라우터 (한 대 · 허용 경로만 넘김)</text></g>')
svg.append('<rect x="822" y="772" width="526" height="222" rx="8" class="aigroup"/>')
svg.append('<text x="832" y="988" class="glabel">AI 층 (5_ai)</text>')


def center(i):
    d = NODE[i]; return (d["x"] + d["w"] / 2, d["y"] + d["h"] / 2)


def clip(i, p, q):
    """p(상자 안) → q 방향 선이 상자 i 테두리와 만나는 점"""
    d = NODE[i]; x0, y0, x1, y1 = d["x"], d["y"], d["x"] + d["w"], d["y"] + d["h"]
    dx, dy = q[0] - p[0], q[1] - p[1]; ts = []
    for t in ((x0 - p[0]) / dx if dx else None, (x1 - p[0]) / dx if dx else None,
              (y0 - p[1]) / dy if dy else None, (y1 - p[1]) / dy if dy else None):
        if t is not None and t > 0:
            xx, yy = p[0] + t * dx, p[1] + t * dy
            if x0 - .5 <= xx <= x1 + .5 and y0 - .5 <= yy <= y1 + .5:
                ts.append(t)
    t = min(ts); return (p[0] + t * dx, p[1] + t * dy)


def anchor_for(i, toward):
    """경유점이 있을 때 상자 쪽 시작점: 경유점의 y(또는 x)가 상자 범위 안이면 그 높이(가로)로 맞춘다"""
    d = NODE[i]; cx, cy = center(i)
    if d["y"] <= toward[1] <= d["y"] + d["h"]:
        return (cx, toward[1])
    if d["x"] <= toward[0] <= d["x"] + d["w"]:
        return (toward[0], cy)
    return (cx, cy)


def draw(line, b, idx_in_fan):
    a = line["a"]; via = line["via"]
    first = via[0] if via else center(b)
    last = via[-1] if via else center(a)
    pa = anchor_for(a, first); pb = anchor_for(b, last)
    pts = [clip(a, pa, first)] + via + [clip(b, pb, last)]
    k = line["kind"]; d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    ms = f' marker-start="url(#ar-{k})"' if line["dir"] in ("both", "back") else ""
    me = f' marker-end="url(#ar-{k})"' if line["dir"] in ("both", "fwd", "file") else ""
    out = [f'<path d="{d}" class="ln ln-{k}"{ms}{me}/>']
    if line["dir"] != "file":  # 연 쪽 표시 ●: 시작점에서 선을 따라 조금 안쪽(화살촉이 있으면 그 뒤)
        (x0, y0), (x1, y1) = pts[0], pts[1]
        L_ = math.hypot(x1 - x0, y1 - y0) or 1
        off = min(13, L_ / 2) if line["dir"] in ("both", "back") else 0
        cx, cy = x0 + (x1 - x0) * off / L_, y0 + (y1 - y0) * off / L_
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4.2" class="opener op-{k}"/>')
    if idx_in_fan == 0:
        segs = list(zip(pts, pts[1:])); s = max(segs, key=lambda s: math.hypot(s[1][0] - s[0][0], s[1][1] - s[0][1]))
        mx, my = ((s[0][0] + s[1][0]) / 2, (s[0][1] + s[1][1]) / 2) if not line["lp"] else line["lp"]
        t = f"L{line['no']}"; w = 9 + 7 * len(t)
        out.append(f'<g class="lt lt-{k}"><rect x="{mx - w/2:.1f}" y="{my - 9:.1f}" width="{w}" height="18" rx="9"/>'
                   f'<text x="{mx:.1f}" y="{my + 4:.1f}" text-anchor="middle">{t}</text></g>')
    return out


labels, tags = [], []
for line in L:
    ln = LINE[line[0]]; bs = ln["b"] if isinstance(ln["b"], list) else [ln["b"]]
    if ln["id"] in TAGONLY:
        for b in bs + [ln["a"]]:
            d = NODE[b]; src = b == ln["a"]; t = f"L{ln['no']}" + (" 긁음" if src else ""); w = 10 + 6.8 * len(f"L{ln['no']}") + (24 if src else 0)
            x, y = d["x"] + d["w"] - w + 6, d["y"] - 8
            tags.append(f'<g class="lt lt-mon"><rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="16" rx="8"/>'
                        f'<text x="{x + w/2:.1f}" y="{y + 12}" text-anchor="middle">{t}</text></g>')
        continue
    for j, b in enumerate(bs):
        labels.extend(draw(ln, b, j))
SHORT = {"sim": "물리 계산 · 배속 600", "plc": "OpenPLC v4.2.4", "edge": "Node-RED 5.0.7", "hub": "Mosquitto 2.1.2",
         "fuxa": "FUXA 1.3.4", "gate": "Caddy 2.11.4", "hubx": "Bento ($SYS → 지표)", "otag": "Prometheus agent",
         "dmzb": "Mosquitto 2.1.2", "loader": "Bento 1.21.2", "dmzi": "InfluxDB 2.9.1 · 7일", "gw": "Node-RED 5.0.7",
         "dmzp": "Prometheus 3.13.4", "kafka": "Kafka 4.3.1 · 토픽 10", "coll": "Bento 1.21.2", "flink": "Flink 2.2.1",
         "zk": "ZooKeeper 3.9.5", "trainer": "Python → ONNX", "iti": "InfluxDB 2.9.1", "pg": "PostgreSQL 18.6",
         "graf": "Grafana 13.2.3", "prom": "Prometheus 3.13.4", "am": "Alertmanager 0.34.1", "kexp": "kafka-exporter 1.10",
         "cadv": "cAdvisor 0.60.6", "graph": "Neo4j 5.26", "ai": "FastAPI 백엔드", "web": "nginx + Vue", "bus": "Python",
         "llm": "GCP 게이트웨이", "host": "127.0.0.1 공개 포트", "prov": "fuxa-provisioner", "kinit": "kafka-init",
         "submit": "flink-job-submitter", "seed": "graph-seed"}
svg.extend(x for x in labels if x.startswith("<path"))
for key, d in NODE.items():
    if key == "router":
        continue
    cls = "node helper" if d["helper"] else "node"
    svg.append(f'<g class="{cls} nz-{d["zone"]}"><rect x="{d["x"]}" y="{d["y"]}" width="{d["w"]}" height="{d["h"]}" rx="7"/>'
               f'<circle cx="{d["x"]+2}" cy="{d["y"]+2}" r="11" class="nb"/>'
               f'<text x="{d["x"]+2}" y="{d["y"]+6}" text-anchor="middle" class="nbt">{d["no"]}</text>'
               f'<text x="{d["x"]+18}" y="{d["y"]+22}" class="nt">{d["name"]}</text>'
               f'<text x="{d["x"]+10}" y="{d["y"]+40}" class="np">{html.escape(SHORT.get(key, d["prod"]))}</text></g>')
st = ["① DMZ → Kafka", "② Kafka → IT 저장", "③ 표시 → DMZ", "④ alert → Alertmanager", "⑤ 설비 상태 → 억제",
      "⑥ Alertmanager → 기록·표시", "⑦ 발송(요청)", "⑧ MES 흉내 요청자"]
for i, s in enumerate(st):
    svg.append(f'<text x="840" y="{312 + i*14.5}" class="{"npr" if i in (6, 7) else "np"}">{s}</text>')
svg.append('<text x="190" y="326" class="np">수집·명령 탭</text><text x="190" y="342" class="npr">OT 수신기 탭</text>')
svg.extend(x for x in labels if not x.startswith("<path"))
svg.extend(tags)
for k, p in PORT.items():
    pt = next((v for v in LINE[k]["via"] if v[0] in (RX, RX2)), None)
    assert pt, k
    svg.append(f'<text x="{pt[0]}" y="{pt[1]-5}" text-anchor="middle" class="port">{p}</text>')
for key, t, dx, dy in (("gw", "검사 1", 104, -9), ("edge", "검사 2", 76, 72), ("plc", "검사 3", 76, -9)):
    d = NODE[key]; x, y = d["x"] + dx, d["y"] + dy
    svg.append(f'<g class="chk"><rect x="{x}" y="{y}" width="52" height="18" rx="4"/><text x="{x+26}" y="{y+13}" text-anchor="middle">{t}</text></g>')
svg.append('</svg>')
SVG = "\n".join(svg)

# ═════════ 본문 ═════════
P = {}  # 부품 설명
P["sim"] = "반응 공정 한 줄(탱크 TK-101, 반응기 R-101, 히터 HX-101, 냉각기 HX-102, 펌프 P-101, 밸브 CV-101, 교반기 M-101)을 물리식으로 흉내 낸다. 설비 시간 600배속이라 고장 결과가 10초 안에 나온다. PLC에게는 Modbus 장치로 보이고, 강사용 고장 주입 API(Basic 인증)와 현장 패널(정비 모드·인터록 리셋 버튼)을 따로 연다. 계측값 12개(LT·TT·PT·FT·IT·VT·pH·CT)."
P["plc"] = "기계 바로 옆의 제어기. 100 ms 주기로 가상설비를 읽고 쓴다. 운전 모드(LOCAL · REMOTE_MANUAL · REMOTE_AUTO)와 정비 모드, 고압 인터록(PT-101 6.5 barg에서 펌프 정지, 운전원이 리셋해야 풀림), 설정값 범위, 건조 운전 방지를 여기서 지킨다. 운전원 명령 채널과 외부 요청 채널을 따로 받고, 외부 요청은 만료 시각·요청 해시까지 확인한다(검사 3)."
P["edge"] = "Node-RED 한 개에 탭 두 개. 수집·명령 탭은 PLC를 250 ms마다 두 블록으로 읽어 UNS 토픽(품질·출처 시각·스캔 순번 포함)으로 내고, 운전원·외부 요청 명령을 PLC 채널에 쓴다. 끊기면 디스크에 모아 두었다가 다시 보낸다. OT 수신기 탭은 밖에서 온 작업 요청을 스키마로 다시 검사하고 PLC 모드·정비·만료를 보고 받을지 정한다(검사 2): REMOTE_AUTO면 바로 명령, REMOTE_MANUAL이면 운전원 대기 60초, 그 밖은 거부. 편집기는 로그인해도 읽기 전용이다. 흐름은 등록부에서 생성해 기동마다 다시 배포한다."
P["hub"] = "공장 안 MQTT 브로커. 모든 공장 부품이 여기에만 연결한다. 계정마다 읽기·쓰기 토픽이 ACL로 정해져 있다. DMZ로 가는 브리지(MQTT 5)를 이 브로커가 연다. DMZ가 끊겨도 공장 안(엣지·화면·PLC)은 계속 돈다."
P["fuxa"] = "운전원 화면. OT 허브의 UNS를 구독해 값을 보이고, 공정 알람(규격·인터록)을 스스로 판정한다. 운전원 명령을 …/cmd/operator 로 보내고, 받은 요청 목록에서 수락·거부를 누른다. 분석 경고(참고)는 IT에서 내려온 표시 토픽을 보여 준다. 화면은 등록부에서 자동 생성한다."
P["gate"] = "FUXA 앞 문지기. 계정(Basic 인증)이 없으면 401로 막는다. FUXA는 설정으로 끌 수 없는 손님 토큰을 늘 발급하므로(2026년 무인증 취약점 권고가 반복된 경로) 화면 자체를 관문 뒤에 둔다."
P["hubx"] = "OT 허브의 $SYS 토픽(연결 수·버린 메시지 수·브리지 상태)을 Prometheus 지표로 바꾼다."
P["otag"] = "OT 안 지표를 긁어(엣지·허브 지표) DMZ 감시로 밀어 보낸다(remote_write). OT가 먼저 연결하는 원칙을 감시에도 지킨다."
P["router"] = "세 망을 잇는 유일한 컨테이너. OT·DMZ 망은 외부 차단(internal)이라 각 구역은 자기 망 안의 라우터 주소로 연결하고, 라우터가 허용 목록의 포트만 목적지로 넘긴다(DNAT). 새 연결은 OT→DMZ 둘, IT→DMZ 넷, 호스트→공개 포트만 허용한다. DMZ→OT, DMZ→IT, IT→OT 새 연결은 없고 응답만 되돌아간다(상태 기반). 나머지는 세고 버린다."
P["dmzb"] = "완충지대의 MQTT 브로커. 공장 브리지가 올려 준 계측·상태·응답을 IT가 가져가고, IT가 넣은 요청·표시를 공장 브리지가 가져간다. 양쪽 모두 이 브로커로 먼저 연결해 오며, 이 브로커는 어디에도 연결을 열지 않는다."
P["loader"] = "DMZ 브로커의 계측값·PLC 상태를 DMZ 원시 사본에 적는다. 품질 BAD(결측)는 행을 만들지 않아 공백으로 남긴다. 같은 Bento에서 DMZ 브로커 $SYS 지표도 낸다."
P["dmzi"] = "OT 원시값의 사본(7일). IT의 Grafana와 AI는 이 사본을 읽기 전용 계정으로 조회만 한다. IT 결과는 여기 쓰지 않는다."
P["gw"] = "밖에서 오는 작업 요청의 첫 관문(검사 1). 토큰, 스키마, 허용 작업 ID·설비·파라미터 범위, 요청자 ID·종류, 승인자, 요청 나이(10초), 중복을 본다. 통과하면 만료 시각(30초)을 붙여 MQTT 5 메시지 만료와 함께 DMZ 요청 토픽에 QoS 1로 올리고, 브로커 확인(PUBACK)을 2초 기다린다. 브로커가 없으면 바로 BROKER_UNAVAILABLE로 거부한다. 공장 상태는 보지 않는다. 편집기는 없다."
P["dmzp"] = "DMZ 부품 지표를 모으고 OT 에이전트가 보낸 지표를 받는다. IT 감시가 /federate로 가져간다."
P["kafka"] = "사무 쪽 데이터의 통로(번호 매긴 장부). 토픽: sensor.telemetry.raw · clean, sensor.anomaly.score, sensor.alerts, plant.status, alerts.display, request.approved, request.events, request.responses, audit.copy. 계측은 7일, 요청·감사는 30일 보관한다. 정본은 PostgreSQL이고 Kafka는 통로·사본이다."
P["coll"] = "IT 쪽 연결을 도맡는 Bento 한 개, 스트림 여덟 개. ① DMZ 브로커 → Kafka ② Flink 결과 → IT 저장 ③ 표시할 경고 → DMZ 브로커 ④ 분석 alert → Alertmanager ⑤ 설비 상태 → 억제 상태 ⑥ Alertmanager 알림 → 기록·표시 ⑦ 승인된 요청 → DMZ 게이트웨이(발송) ⑧ MES 흉내 요청자. 모든 연결을 IT가 연다."
P["flink"] = "흘러가는 계측을 바로 검사한다. 1계층 규칙(규격 이탈), Z-Score(잡음), CEP(전류→진동 순서 패턴), 2계층 ONNX 오토인코더(상관 붕괴·드리프트, 기여 센서 역추적). 결측은 보간해 clean에 싣되 원시에는 공백을 남긴다. 잡 4개."
P["zk"] = "Flink 잡 관리자가 재시작 뒤 잡을 되살리도록 상태를 적어 둔다."
P["trainer"] = "기동 때 정상 운전 데이터로 오토인코더를 학습해 ONNX 파일을 만들고 끝난다. Flink가 파일로 읽는다."
P["iti"] = "Flink 결과(정제값·이상 점수·alert 이력)를 저장한다. Grafana 공정·이상 화면이 읽는다."
P["pg"] = "업무 정본. DATABASE plant에 등록부(registry), 작업 요청·승인·응답(workflow, 추가 전용), 분석 alert와 ISA-18.2 상태(alert), 감사(audit, UPDATE·DELETE 거부). DATABASE ai에 사건·대응안. 계정을 서비스마다 나눴다(ops · dispatcher · mes · ai_app · reader)."
P["graf"] = "그래프 4장(공정 · 이상 · 경보 · 인프라). IT 결과 저장, DMZ 원시 사본, IT 감시를 읽는다."
P["prom"] = "IT 부품 지표를 긁고, DMZ 감시를 /federate로 가져와 세 구역을 한곳에서 본다. 인프라 경보 규칙(수집기 입력 멈춤, 브리지 끊김, 랙, 체크포인트 실패 등)을 평가해 Alertmanager로 보낸다. 공정 데이터는 담지 않는다."
P["am"] = "경보를 묶고 억제한다. 공정 분석 alert는 (설비, 규칙)으로 묶어 새 묶음·해제만 IT 수집기에 알린다. 정비 모드(Out of Service), PLC 정지, 설비 운전 꺼짐(Suppressed by Design) 동안 해당 alert를 억제한다(ISA-18.2)."
P["kexp"] = "Kafka 컨슈머 랙·오프셋을 지표로 낸다."
P["cadv"] = "컨테이너별 CPU·메모리 지표를 낸다."
P["graph"] = "설비·센서·고장 모드·매뉴얼의 관계(온톨로지). AI가 원인 후보를 찾을 때 쓴다."
P["ai"] = "AI 업무 도우미. 사건을 보고 증거(DMZ 원시 사본, 온톨로지, 매뉴얼 의미 검색)를 모아 대응안을 만든다. 사람이 승인하면 작업 요청 한 건을 업무 DB에 기록하고 승인 토픽에 알린 뒤 결과 사건을 기다려 읽기만 한다. 설비에 닿는 연결은 없다."
P["web"] = "AI 업무 화면. 사건·대응안·승인·요청 진행을 보여 준다. /api를 AI 업무 도우미로 넘긴다."
P["bus"] = "사건 접수와 요청 판정. sensor.alerts를 AI 사건으로 접수하고, 작업 요청의 시간 판정을 한다: ACK 5초 안 응답 없음(결과 모름), 만료+5초 미확인, 운전원 대기 초과, PLC 수용 뒤 10초 안 재관측(일치 observed / 불일치 command_disagree). 요청을 다시 보내지는 않는다."
P["llm"] = "LLM과 임베딩(text-embedding-3-small, 1536차원)을 내주는 GCP 게이트웨이. 키는 저장소 밖 파일에만 있다."
P["host"] = "사람과 시험 도구. 127.0.0.1 공개 포트로만 들어온다. OT·DMZ 화면은 라우터를 거친다."
P["prov"] = "기동 때 등록부에서 만든 FUXA 화면(장치 1, 뷰 1, 요소 58)을 넣고 끝난다."
P["kinit"] = "기동 때 Kafka 토픽 10개를 보존 기간과 함께 만들고 끝난다."
P["submit"] = "기동 때 Flink 잡 4개(SQL 3 + ONNX 1)를 제출하고 끝난다."
P["seed"] = "기동 때 온톨로지와 매뉴얼 색인을 Neo4j에 넣고 끝난다."

LD = {}  # 선 설명: (프로토콜·포트·계정, 실어 나르는 것)
LD["modbus_sim"] = ("Modbus TCP 502, 100 ms", "PLC가 계측 12점·스캔 순번·설비 시각·현장 패널을 읽고(FC3), 구동기(코일)·설정값을 쓴다.")
LD["modbus_plc"] = ("Modbus TCP 502, 250 ms", "엣지가 계측 블록(FC4)과 상태·ACK 블록(FC3)을 읽고, 운전원 채널·외부 요청 채널·시각 동기(1초)를 쓴다.")
LD["edge_mqtt"] = ("MQTT 3.1.1, 계정 edge", "올림: UNS 계측·상태·ACK·통신 상태·수업용 edgex/telemetry. 내림: …/cmd/operator, …/cmd/request.")
LD["recv_mqtt"] = ("MQTT 5, 계정 ot-receiver, 세션 1시간", "내림: 요청 AR-100/request/in, PLC 상태, 운전원 결정, PLC 요청 ACK. 올림: 응답 AR-100/response/…, …/cmd/request, 받은 요청 목록.")
LD["fuxa_mqtt"] = ("MQTT, 계정 fuxa", "내림: UNS 값, 분석 경고 표시, 받은 요청 목록. 올림: 운전원 명령, 요청 수락·거부.")
LD["gate_fuxa"] = ("HTTP 1881 (역방향 프록시, 소켓 포함)", "관문을 통과한 화면 요청만 FUXA에 넘긴다.")
LD["hubx_sys"] = ("MQTT $SYS 구독", "허브의 연결 수·버린 메시지·브리지 상태.")
LD["otag_scrape"] = ("HTTP 긁기 15초 (그림: 대상 상자의 회색 작은 표)", "엣지 /metrics(끊김 버퍼 건수 등), 허브 지표 변환 :4195.")
LD["bridge_out"] = ("MQTT 5 브리지, 라우터 1883, 계정 bridge-ot, 세션 1시간", "올림(out): 계측 tag, 상태 status, ACK, 통신 상태 state, 요청 응답 response. DMZ가 끊기면 허브에 쌓였다가 이어서 보낸다.")
LD["bridge_in"] = ("L" + "{bo}" + "와 같은 연결", "내림(in): 작업 요청 AR-100/request/in(QoS 1, 만료 붙음)과 분석 경고 표시 AR-100/alert/display. 연결은 OT가 열었지만 데이터는 DMZ → OT로 흐른다.")
LD["otag_rw"] = ("HTTP remote_write, 라우터 9090", "OT 지표를 DMZ 감시로 밀어 보낸다.")
LD["loader_sub"] = ("MQTT 구독, clean_session, 메모리 버퍼 32 MiB", "계측·상태·통신 상태.")
LD["loader_write"] = ("HTTP 8086", "원시 사본 행(태그·값·품질·출처 시각).")
LD["gw_pub"] = ("MQTT 5, 계정 gateway, QoS 1", "검사를 통과한 요청 + expires_at. 메시지 만료 30초. PUBACK 2초 안 없으면 거부 응답.")
LD["dmzp_scrape"] = ("HTTP 긁기 15초 (그림: 대상 상자의 회색 작은 표)", "적재기 :4195, 게이트웨이 :8088/metrics(수용·거부 건수, 브로커 연결), DMZ 원시 사본.")
LD["coll_sub"] = ("MQTT 구독, 라우터 1883, 계정 it-collector", "계측·상태·통신 상태·ACK·요청 응답을 가져가 Kafka로(스트림 ①).")
LD["coll_disp"] = ("MQTT 발행, 라우터 1883", "표시할 분석 경고를 AR-100/alert/display 하나에만 쓴다(스트림 ③).")
LD["coll_gw"] = ("HTTP POST /requests, 라우터 8088, Bearer 토큰", "승인된 요청을 보내고 같은 연결로 수용·거부와 이유를 받는다(첫 응답 ⓐ, 스트림 ⑦). 다시 보내지 않는다.")
LD["graf_dmzi"] = ("HTTP 8086 조회, 라우터", "원시 사본을 그래프로.")
LD["ai_dmzi"] = ("HTTP 8086 조회, 라우터, 읽기 전용 계정", "사건 증거용 원시값.")
LD["prom_fed"] = ("HTTP /federate, 라우터 9090", "DMZ·OT 지표를 IT로 가져온다.")
LD["coll_kafka"] = ("Kafka 9092", "쓰기: raw·plant.status·request.responses·alerts.display·request.events·audit.copy. 읽기: Flink 결과, sensor.alerts, plant.status, alerts.display, request.approved.")
LD["flink_kafka"] = ("Kafka 9092", "읽기: sensor.telemetry.raw. 쓰기: clean, anomaly.score, sensor.alerts.")
LD["flink_zk"] = ("ZooKeeper 2181", "잡 관리자 복구 기록.")
LD["coll_iti"] = ("HTTP 8086", "정제값·이상 점수·alert 이력(스트림 ②).")
LD["coll_am"] = ("HTTP POST /api/v2/alerts", "분석 alert(라벨: 설비·규칙·태그·심각도, 끝 = 마지막 + 60초)와 억제 상태(스트림 ④⑤).")
LD["am_coll"] = ("HTTP webhook → it-collector:4195/alertmanager_to_display/alertmanager", "새 묶음·해제·억제 시작/해제만 알린다(스트림 ⑥이 받음).")
LD["coll_pg"] = ("PostgreSQL 5432, 계정 ops · dispatcher · mes", "⑥ alert 묶음·사건 기록, ⑦ dispatched·게이트웨이 응답·감사, ⑧ MES 요청·승인·감사.")
LD["bus_kafka"] = ("Kafka 9092", "읽기: sensor.alerts(사건 접수), plant.status, request.responses. 쓰기: request.events·audit.copy 사본, 명령≠상태 alert(sensor.alerts).")
LD["bus_pg"] = ("PostgreSQL 5432, 계정 ops(plant) · ai_app(ai)", "요청 판정 사건·감사, AI 사건 접수.")
LD["ai_pg"] = ("PostgreSQL 5432, 계정 ai_app", "사건·대응안(ai), 작업 요청·승인·감사 기록과 결과 사건 읽기(plant).")
LD["ai_kafka"] = ("Kafka 9092, acks=all, 5초", "승인 기록이 끝난 요청의 ID를 request.approved에 낸다. 못 내면 not_dispatched로 남기고 보내지 않는다.")
LD["ai_graph"] = ("Bolt 7687", "온톨로지 조회.")
LD["ai_flink"] = ("HTTP 8081", "탐지 잡 상태 조회.")
LD["ai_llm"] = ("HTTPS(인터넷)", "대응안 생성, 매뉴얼 임베딩·검색.")
LD["web_ai"] = ("HTTP /api (nginx 프록시)", "화면 ↔ 업무 도우미.")
LD["graf_iti"] = ("HTTP 8086", "정제값·이상 점수·alert 이력.")
LD["graf_prom"] = ("HTTP 9090", "인프라 그래프.")
LD["prom_scrape"] = ("HTTP 긁기 10초 (그림: 대상 상자의 회색 작은 표)", "Kafka 지표, 컨테이너 지표, IT 수집기 :4195, Flink :9249, IT 결과 저장.")
LD["prom_am"] = ("HTTP 9093", "인프라 경보(로그 전용 수신자).")
LD["kexp_kafka"] = ("Kafka 9092", "랙·오프셋 조회.")
LD["trainer_flink"] = ("파일(공유 볼륨)", "학습한 ONNX 모델과 정규화 값.")
LD["host_router"] = ("라우터 공개 포트 → OT·DMZ", "화면 관문 21881 → 1882. 같은 방식으로 강사 API 28080·현장 패널 28081 → 가상설비, 엣지 편집기 21880, PLC API 28443, OT MQTT 21883, DMZ MQTT 1883, DMZ 원시 사본 8086.")
LD["host_it"] = ("IT 공개 포트", "AI 화면. 같은 방식으로 Grafana, AI API, Kafka, Flink 화면, IT 결과 저장, 업무 DB, IT 감시, Alertmanager, Neo4j에도 들어온다(그림에는 AI 화면만).")
LD["mes_coll"] = ("HTTP POST /mes_requester/orders (IT 망 안에서, 예: docker compose exec it-collector wget …)", "MES 생산 지시(작업 ID·설비·파라미터·계획 담당). 스트림 ⑧이 요청·승인으로 기록하고 승인 토픽에 낸다.")
LD["prov_fuxa"] = ("HTTP(1회)", "등록부에서 만든 화면 프로젝트.")
LD["kinit_kafka"] = ("Kafka 관리 명령(1회)", "토픽 10개 생성.")
LD["submit_flink"] = ("HTTP 8081(1회)", "SQL 잡 3개 + ONNX 잡 1개 제출.")
LD["seed_graph"] = ("Bolt(1회)", "온톨로지·매뉴얼 색인.")
LD["bridge_in"] = (f'L{LINE["bridge_out"]["no"]}과 같은 연결(그림에서는 방향별로 나눠 그림)', LD["bridge_in"][1])
assert set(LD) == set(LINE), set(LINE) ^ set(LD)
assert set(P) == set(NODE), set(NODE) ^ set(P)

DIRW = {"fwd": "연 쪽 → 받는 쪽", "back": "받는 쪽 → 연 쪽", "both": "양쪽", "file": "파일 전달"}
KINDW = {"data": "데이터", "req": "작업 요청 길", "mon": "감시", "file": "기동·파일"}

# 네 흐름(단계 번호)
FLOWS = [
 ("f1", "흐름 1 · 계측: 현장 값이 화면과 기록까지", [
  "{nn:sim}이 물리 계산으로 값을 만든다. {nn:plc}가 {l:modbus_sim}으로 100 ms마다 읽는다.",
  "{nn:edge}가 {l:modbus_plc}으로 250 ms마다 두 블록을 읽고, 새 스캔일 때만 UNS 토픽(값·품질·출처 시각 ns·스캔 순번)으로 {l:edge_mqtt}를 거쳐 {nn:hub}에 낸다.",
  "{nn:fuxa}가 {l:fuxa_mqtt}로 같은 값을 받아 화면에 보이고 공정 알람을 판정한다. 여기까지는 공장 안이라 DMZ가 끊겨도 돈다.",
  "{nn:hub}가 연 브리지 {l:bridge_out}로 값이 {nn:dmzb}에 올라간다. 라우터 1883만 열려 있다.",
  "{nn:loader}가 {l:loader_sub}로 받아 {l:loader_write}로 {nn:dmzi}에 적는다(7일, 결측은 공백).",
  "{nn:coll} 스트림 ①이 {l:coll_sub}로 같은 값을 가져가 {l:coll_kafka}로 Kafka sensor.telemetry.raw(키 = 설비)와 plant.status에 쓴다.",
  "{nn:flink}가 {l:flink_kafka}로 raw를 읽어 보간한 clean, 이상 점수, alert를 다시 Kafka에 쓴다.",
  "{nn:coll} 스트림 ②가 결과를 {l:coll_iti}로 {nn:iti}에 적고, {nn:graf}가 {l:graf_iti}와 {l:graf_dmzi}로 그린다.",
 ]),
 ("f2", "흐름 2 · 경보: 이상을 찾아 묶고 화면과 AI로", [
  "{nn:flink}가 규칙·Z-Score·CEP·오토인코더로 이상을 찾아 {l:flink_kafka}로 sensor.alerts에 쓴다.",
  "{nn:coll} 스트림 ④가 alert를 라벨(설비·규칙)을 붙여 {l:coll_am}로 {nn:am}에 넣는다. 스트림 ⑤는 plant.status에서 정비 모드·PLC 정지·설비 꺼짐을 억제 상태로 넣는다.",
  "{nn:am}이 (설비, 규칙)으로 묶고 억제 규칙을 적용한 뒤, 새 묶음·해제만 {l:am_coll}로 알린다.",
  "{nn:coll} 스트림 ⑥이 {l:coll_pg}로 {nn:pg}에 묶음(ACTIVE/CLEARED)과 사건(DISPLAYED · OUT_OF_SERVICE · SUPPRESSED_BY_DESIGN)을 적고, 새 묶음만 Kafka alerts.display로 낸다.",
  "{nn:coll} 스트림 ③이 {l:coll_disp}로 {nn:dmzb}의 AR-100/alert/display에 쓰고, 허브 브리지 {l:bridge_in}이 그것을 공장 안으로 가져간다.",
  "{nn:fuxa}가 {l:fuxa_mqtt}로 받아 '분석 경고(참고)'에 보인다. 공정 알람과 따로 보인다.",
  "같은 sensor.alerts를 {nn:bus}가 {l:bus_kafka}로 읽어 AI 사건으로 접수한다({l:bus_pg}). {nn:ai}가 사건을 연다.",
 ]),
 ("f3", "흐름 3 · 작업 요청: 승인된 요청이 설비에 닿고 결과가 돌아오기까지", [
  "{nn:ai}에서 사람이 대응안을 승인하면, 요청 한 건과 승인 사건·감사를 {l:ai_pg}로 {nn:pg}에 적는다(요청자 ai-ops, 종류 ai). MES 흉내는 {l:mes_coll}로 {nn:coll} 스트림 ⑧에 지시를 넣고, 같은 방식으로 적힌다(mes-01, 종류 mes, 승인자 planner-01).",
  "기록이 끝나면 요청 ID를 {l:ai_kafka}로 Kafka request.approved에 낸다(스트림 ⑧은 {l:coll_kafka}로 낸다).",
  "{nn:coll} 스트림 ⑦이 승인 토픽을 읽고, 마지막 사건이 approved인 요청만 dispatched를 먼저 적은 뒤 {l:coll_gw}로 {nn:gw}에 POST한다. 같은 승인이 다시 와도 다시 보내지 않는다.",
  "<b>검사 1</b> · {nn:gw}가 토큰·스키마·허용 작업·범위·요청자 ID와 종류·승인자·나이·중복을 본다. 거부면 이유를 바로 돌려주고, 통과면 {l:gw_pub}로 {nn:dmzb}에 올린 뒤 202와 만료 시각을 돌려준다. 스트림 ⑦이 이것을 첫 응답 ⓐ로 적는다.",
  "{nn:hub}의 브리지 {l:bridge_in}이 요청을 공장 안으로 가져온다. 30초가 지나면 브로커가 스스로 버린다.",
  "<b>검사 2</b> · {nn:edge}의 OT 수신기 탭이 {l:recv_mqtt}로 받아 스키마를 다시 보고, PLC 모드·정비·만료로 받을지 정한다. REMOTE_AUTO면 바로 명령, REMOTE_MANUAL이면 {nn:fuxa} 받은 요청 목록에 올려 운전원을 60초 기다린다. 결정은 응답 ⓑ로 낸다.",
  "<b>검사 3</b> · 엣지가 {l:modbus_plc}로 PLC 외부 요청 채널에 코드·값·만료·해시를 쓴다. {nn:plc}가 모드·인터록·범위·만료를 다시 보고 수용·거부 ACK를 낸다(응답 ⓒ).",
  "응답 ⓑⓒ는 {l:bridge_out} → {l:coll_sub} → Kafka request.responses → {nn:bus}로 가서 {nn:pg}에 적힌다. {nn:bus}가 PLC 수용 뒤 10초 안에 설비 상태가 바뀌었는지 재관측한다(observed / command_disagree). {nn:ai}는 이 사건을 읽기만 한다.",
  "실측(2026-09-30, REMOTE_AUTO 온도 설정 요청): 승인 0 s → dispatched 0.01 → 게이트웨이 수용 0.03 → OT 수신 0.25 → PLC 수용 0.26 → 재관측 일치 0.46 s.",
 ]),
 ("f4", "흐름 4 · 운전원 조작: 화면 버튼이 기계를 움직이기까지", [
  "사람이 {l:host_router}로 {nn:gate}에 계정을 대고 들어오면, 관문이 {l:gate_fuxa}로 {nn:fuxa} 화면을 넘긴다.",
  "운전원이 버튼을 누르면 {nn:fuxa}가 {l:fuxa_mqtt}로 …/cmd/operator에 명령(코드·값)을 낸다.",
  "{nn:edge} 수집·명령 탭이 {l:edge_mqtt}로 받아 {l:modbus_plc}로 PLC 운전원 채널에 코드·값을 쓰고 순번을 올린다.",
  "{nn:plc}가 모드(REMOTE_AUTO면 운전원 조작 거부)·정비·인터록·범위를 보고 수용·거부 ACK를 내고, 수용이면 {l:modbus_sim}으로 기계를 움직인다.",
  "ACK와 새 값이 흐름 1의 길로 {nn:fuxa}에 돌아와 화면이 바뀐다. 고압 인터록이 걸리면 펌프가 멈추고, 운전원이 {nn:sim} 현장 패널 또는 화면에서 리셋해야 풀린다.",
 ]),
]


def esc(t): return t


rows_nodes = []
for key, d in NODE.items():
    helper = ' <span class="tag">기동 때 1회</span>' if d["helper"] else ""
    zone = {"plant": "현장", "ot": "OT", "dmz": "DMZ", "it": "IT", "out": "밖", "host": "호스트", "router": "구역 사이"}[d["zone"]]
    rel = [f'L{x["no"]}' for x in LINE.values() if x["a"] == key or x["b"] == key or (isinstance(x["b"], list) and key in x["b"])]
    rows_nodes.append(f'<article class="part pz-{d["zone"]}" id="p{d["no"]}"><header><span class="pnum">{d["no"]}</span>'
                      f'<h3>{d["name"]}</h3><span class="zone-chip zc-{d["zone"]}">{zone}</span>{helper}</header>'
                      f'<p class="prod">{html.escape(d["prod"])}</p><p>{sub(P[key])}</p>'
                      f'<p class="rel">닿는 선: {" · ".join(rel) if rel else "없음"}</p></article>')

rows_lines = []
for key, x in LINE.items():
    bs = x["b"] if isinstance(x["b"], list) else [x["b"]]
    opener = nn(x["a"]) if x["dir"] != "file" else nn(x["a"])
    to = ", ".join(nn(b) for b in bs)
    pr, what = LD[key]
    rows_lines.append(f'<li class="line lk-{x["kind"]}" id="l{x["no"]}"><span class="lnum l-{x["kind"]}">L{x["no"]}</span>'
                      f'<div><p class="ends">{"●" if x["dir"]!="file" else "○"} {opener} <span class="arrow">→</span> {to}</p>'
                      f'<p class="meta"><span>{KINDW[x["kind"]]}</span><span>데이터: {DIRW[x["dir"]]}</span><span class="mono">{html.escape(pr)}</span></p>'
                      f'<p>{sub(what)}</p></div></li>')

flows_html = []
for fid, title, steps in FLOWS:
    lis = "".join(f"<li>{sub(s)}</li>" for s in steps)
    flows_html.append(f'<section class="flow" id="{fid}"><h3>{title}</h3><ol>{lis}</ol></section>')

TPL = pathlib.Path(sys.argv[2]).read_text(encoding="utf-8")
out = (TPL.replace("{{SVG}}", SVG).replace("{{PARTS}}", "\n".join(rows_nodes)).replace("{{LINES}}", "\n".join(rows_lines))
       .replace("{{FLOWS}}", "\n".join(flows_html)).replace("{{NP}}", str(len(N))).replace("{{NL}}", str(len(L))))
out = sub(out)
OUT.write_text(out, encoding="utf-8")
print("parts", len(N), "lines", len(L), "bytes", len(out.encode()))
