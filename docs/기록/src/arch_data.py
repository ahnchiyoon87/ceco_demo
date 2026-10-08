# -*- coding: utf-8 -*-
"""ceco_demo 마스터 가이드 2부(시스템 아키텍처 상세)의 데이터: 부품 37개 · 연결 51개 · 설명(쉬운 말 + 기술 세부) · 흐름.
번호 ①~㊲은 마스터_가이드(master_arch_svg.py)와 같다. 값은 2026-10-07 작업 사본(커밋 e060538 + 미커밋 변경)의 코드에서 확인했다.
"""

CIRC = {i: chr(0x2460 + i - 1) for i in range(1, 21)}
CIRC.update({i: chr(0x3251 + i - 21) for i in range(21, 36)})
CIRC.update({36: chr(0x32B1), 37: chr(0x32B2)})

# key: (번호, 이름, 그림 둘째 줄(제품), 구역, 종류)
# 구역: plant · ctrl · ot · router · dmz · it · biz · ext · host     종류: normal · once · mon(감시 프로필) · ext
PART = {
 "sim":     (1,  "가상설비", "Python · 물리 계산 · 배속 600", "plant", "normal"),
 "plc":     (2,  "PLC", "OpenPLC Runtime v4.2.4", "ctrl", "normal"),
 "edge":    (3,  "엣지 게이트웨이", "Node-RED 5.0.7 · 탭 2개", "ot", "normal"),
 "hub":     (4,  "OT 허브 (공장 게시판)", "Mosquitto 2.1.2 · MQTT", "ot", "normal"),
 "fuxa":    (5,  "운전원 화면", "FUXA 1.3.4 · SCADA/HMI", "ot", "normal"),
 "gate":    (6,  "화면 관문", "Caddy 2.11.4", "ot", "normal"),
 "hubx":    (7,  "허브 지표 변환", "Bento 1.21.2 · 감시 프로필", "ot", "mon"),
 "otag":    (8,  "OT 감시", "Prometheus agent · 감시 프로필", "ot", "mon"),
 "router":  (9,  "구역 라우터", "iptables · 세 망을 잇는 유일한 컨테이너", "router", "normal"),
 "dmzb":    (10, "DMZ 브로커 (우편함)", "Mosquitto 2.1.2 · MQTT", "dmz", "normal"),
 "loader":  (11, "DMZ 적재기", "Bento 1.21.2", "dmz", "normal"),
 "dmzi":    (12, "DMZ 원시 사본", "InfluxDB 2.9.1 · 7일", "dmz", "normal"),
 "gw":      (13, "DMZ 요청 게이트웨이", "Node-RED 5.0.7 · 편집기 없음", "dmz", "normal"),
 "dmzp":    (14, "DMZ 감시", "Prometheus 3.13.4 · 감시 프로필", "dmz", "mon"),
 "kafka":   (15, "Kafka (번호 매긴 장부)", "Apache Kafka 4.3.1 · KRaft", "it", "normal"),
 "coll":    (16, "IT 수집기", "Bento 1.21.2 · 스트림 7개", "it", "normal"),
 "flink":   (17, "Flink (실시간 검사관)", "Flink 2.2.1 · 잡 관리자 + 작업자", "it", "normal"),
 "zk":      (18, "ZooKeeper", "3.9.5 · Flink 복구 기록", "it", "normal"),
 "trainer": (19, "모델 학습기", "Python · torch → ONNX · 기동 때 1회", "it", "once"),
 "iti":     (20, "IT 결과 저장", "InfluxDB 2.9.1 · 감시 프로필", "it", "mon"),
 "hist":    (21, "IT 이력 적재기", "Bento 1.21.2 · 감시 프로필", "it", "mon"),
 "pg":      (22, "업무 DB (정본)", "PostgreSQL 18.6", "it", "normal"),
 "graf":    (23, "Grafana", "13.2.3 · 감시 프로필", "it", "mon"),
 "prom":    (24, "IT 감시", "Prometheus 3.13.4 · 감시 프로필", "it", "mon"),
 "am":      (25, "Alertmanager", "v0.34.1 · 기본 기동", "it", "normal"),
 "kexp":    (26, "Kafka 지표", "kafka-exporter 1.10.0", "it", "mon"),
 "cadv":    (27, "컨테이너 지표", "cAdvisor 0.60.6", "it", "mon"),
 "graph":   (28, "온톨로지 그래프", "Neo4j 5.26 Community", "biz", "normal"),
 "ai":      (29, "AI 업무 도우미", "knowledge · FastAPI + LangGraph", "biz", "normal"),
 "web":     (30, "AI 화면", "nginx 1.28 + Vue", "biz", "normal"),
 "bus":     (31, "업무 서비스", "business · Python", "biz", "normal"),
 "llm":     (32, "OpenAI", "밖(인터넷) · API 직접 호출", "ext", "ext"),
 "host":    (33, "사람 · 시험 도구", "호스트 127.0.0.1 공개 포트", "host", "normal"),
 "prov":    (34, "화면 넣기", "fuxa-provisioner · 기동 때 1회", "ot", "once"),
 "kinit":   (35, "토픽 만들기", "kafka-init · 기동 때 1회", "it", "once"),
 "submit":  (36, "잡 제출", "flink-job-submitter · 기동 때 1회", "it", "once"),
 "seed":    (37, "그래프 채우기", "graph-seed · 기동 때 1회", "biz", "once"),
}
NO = {k: v[0] for k, v in PART.items()}
assert sorted(NO.values()) == list(range(1, 38))
ZONE_NAME = {"plant": "현장", "ctrl": "제어", "ot": "OT 공장 망", "router": "구역 사이", "dmz": "DMZ", "it": "IT", "biz": "업무 · AI", "ext": "밖(인터넷)", "host": "호스트"}
MASTER_ALIAS = {"otmon": "otag", "dmzinf": "dmzi", "dmzmon": "dmzp", "itinf": "iti", "itmon": "prom", "train": "trainer",
                "topics": "kinit", "neo": "graph", "aiweb": "web", "biz": "bus"}

# ═════════════ 연결: (키, 여는 쪽, 받는 쪽(목록이면 여러 곳), 종류, 데이터 방향) ═════════════
# 종류: data · cmd(요청·명령·실행) · alert(경보 표시) · api(조회·호출) · mon(감시) · once(기동 1회) · human(사람)
LINES = [
 ("modbus_sim", "plc", "sim", "data", "both"),
 ("modbus_plc", "edge", "plc", "data", "both"),
 ("edge_mqtt", "edge", "hub", "data", "both"),
 ("recv_mqtt", "edge", "hub", "cmd", "both"),
 ("recv_crew", "edge", "sim", "cmd", "both"),
 ("fuxa_mqtt", "fuxa", "hub", "data", "both"),
 ("gate_fuxa", "gate", "fuxa", "data", "both"),
 ("hubx_sys", "hubx", "hub", "mon", "back"),
 ("otag_scrape", "otag", ["edge", "hubx"], "mon", "back"),
 ("bridge_out", "hub", "dmzb", "data", "fwd"),
 ("bridge_in", "hub", "dmzb", "cmd", "back"),
 ("otag_rw", "otag", "dmzp", "mon", "fwd"),
 ("loader_sub", "loader", "dmzb", "data", "back"),
 ("loader_write", "loader", "dmzi", "data", "fwd"),
 ("gw_pub", "gw", "dmzb", "cmd", "fwd"),
 ("dmzp_scrape", "dmzp", ["loader", "gw", "dmzi"], "mon", "back"),
 ("coll_sub", "coll", "dmzb", "data", "back"),
 ("coll_disp", "coll", "dmzb", "alert", "fwd"),
 ("coll_gw", "coll", "gw", "cmd", "both"),
 ("graf_dmzi", "graf", "dmzi", "api", "back"),
 ("ai_dmzi", "ai", "dmzi", "api", "back"),
 ("prom_fed", "prom", "dmzp", "mon", "back"),
 ("coll_kafka", "coll", "kafka", "data", "both"),
 ("flink_kafka", "flink", "kafka", "data", "both"),
 ("flink_zk", "flink", "zk", "data", "both"),
 ("hist_kafka", "hist", "kafka", "data", "back"),
 ("hist_iti", "hist", "iti", "data", "fwd"),
 ("coll_am", "coll", "am", "alert", "fwd"),
 ("am_coll", "am", "coll", "alert", "fwd"),
 ("coll_pg", "coll", "pg", "data", "both"),
 ("bus_kafka", "bus", "kafka", "data", "both"),
 ("bus_pg", "bus", "pg", "data", "both"),
 ("ai_pg", "ai", "pg", "data", "both"),
 ("ai_kafka", "ai", "kafka", "cmd", "fwd"),
 ("ai_graph", "ai", "graph", "api", "both"),
 ("ai_flink", "ai", "flink", "api", "back"),
 ("ai_llm", "ai", "llm", "api", "both"),
 ("web_ai", "web", "ai", "api", "both"),
 ("graf_iti", "graf", "iti", "api", "back"),
 ("graf_prom", "graf", "prom", "mon", "back"),
 ("prom_scrape", "prom", ["kexp", "cadv", "coll", "flink", "iti"], "mon", "back"),
 ("prom_am", "prom", "am", "mon", "fwd"),
 ("kexp_kafka", "kexp", "kafka", "mon", "back"),
 ("trainer_flink", "trainer", "flink", "once", "fwd"),
 ("host_router", "host", ["gate", "sim", "edge", "plc", "hub", "dmzb", "dmzi"], "human", "both"),
 ("host_it", "host", "web", "human", "both"),
 ("mes_coll", "host", "coll", "cmd", "fwd"),
 ("prov_fuxa", "prov", "fuxa", "once", "fwd"),
 ("kinit_kafka", "kinit", "kafka", "once", "fwd"),
 ("submit_flink", "submit", "flink", "once", "fwd"),
 ("seed_graph", "seed", "graph", "once", "fwd"),
]
L = {}
for i, (k, a, b, kind, d) in enumerate(LINES, 1):
    L[k] = dict(key=k, no=i, a=a, b=b, kind=kind, dir=d)
assert len(L) == 51

# ═════════════ 부품 설명: (쉬운 말, 기술 세부 [(항목, 값)], 상세) ═════════════
D = {}
D["sim"] = (
 "진짜 공장 대신 컴퓨터가 반응 공정 한 줄(탱크 · 반응기 · 히터 · 냉각 재킷 · 펌프 · 밸브 · 교반기 · 냉각수 스트레이너)을 물리식으로 흉내 냅니다. 설비 시간이 600배 빠르게 흘러, 고장 결과가 몇 초 안에 보입니다. 설비 옆의 조작 패널과, 현장에 나가 정비하는 가상 정비팀도 이 안에 있습니다.",
 [("서비스", "plant-sim · 망 ot-net(외부 차단)"), ("제품", "Python 자체 구현(Modbus 슬레이브 + HTTP 3개)"),
  ("포트", "Modbus 502(PLC만) · 8080 강사 API · 8081 현장 패널 · 8082 정비팀. 호스트에는 37080 · 37082만(라우터 경유), 8082는 열지 않음"),
  ("코드", "0_plant/simulator/ — sim.py · plant.py · plant.yaml · 등록부 shared/registry/equipment.yaml")],
 "<p><b>설비 8대</b>: TK-101(탱크) · R-101(반응기) · HX-101(히터) · HX-102(냉각 재킷) · ST-103(냉각수 스트레이너) · P-101(펌프) · CV-101(밸브) · M-101(교반기). <b>계측 17점</b>(액위 · 온도 · 압력 2계기 · 유량 3 · 전류 · 진동 · pH · 전도도 · 냉각수 공급/회수 온도 · 스트레이너 차압)을 Modbus 레지스터 HR0..37(float32)로 내고, 스캔 순번(HR24)과 설비 시각(HR26)도 냅니다. 구동기는 코일 0..3, 설정값은 HR100..102, 현장 패널은 HR300..308입니다. 스캔 1초, 배속 600, 계산 소구간 5초. 냉각수 30 m³/h · 20 ℃, 압력 릴리프 7.5 barg(제어와 무관한 물리 상한).</p>"
 "<p><b>세 개의 문.</b> 강사 API(8080, instructor 계정): 고장 주입 12종(열화 6종은 저절로 낫지 않고 맞는 정비로만 회복) · 시나리오 3개와 변형 · 전체 초기화. 현장 패널(8081, field 계정): 운전 모드 · 현장 기동/정지 · 정비 키 · 인터록 리셋 · 비상정지. 가상 정비팀(8082, crew 계정, OT 수신기만 앎): 현장 작업 8종을 받아 작업 전 안전 확인 → 격리(LOTO) → 작업 → 소견을 돌려줍니다(DONE · DONE_NO_FAULT · REJECTED). 같은 작업 지시 ID는 한 번만 수행하고, 원인과 다른 정비를 하면 「부품 정상」(DONE_NO_FAULT)을 답합니다.</p>")
D["plc"] = (
 "기계 바로 옆의 제어 컴퓨터입니다. 0.1초마다 설비를 읽고 움직이며, 위험하면 누가 무엇을 시키든 스스로 멈춥니다. 사람이 화면에서 누른 명령과 밖에서 온 작업 요청을 따로 받아 각각 다시 검사합니다(검사 3).",
 [("서비스", "plc · 망 ot-net"), ("제품", "OpenPLC Runtime v4.2.4 (IEC 61131-3 ST 프로그램)"), ("포트", "502(엣지용 Modbus 슬레이브) · 편집 API 호스트 37443(라우터 경유)"),
  ("저장", "볼륨 plc-data(정비 모드는 RETAIN으로 재시작 뒤에도 유지)"), ("코드", "1_control/plc-openplc/main.st.tmpl → project/ (등록부에서 생성)")],
 "<p><b>주기 100 ms.</b> 가상설비를 FC3로 HR0..37과 패널 HR300..308을 읽고, FC15로 코일 4개, FC16으로 설정값 3개를 씁니다. 엣지에는 Modbus 슬레이브(502)로 보이며, 운전원 채널(%MW10) · 외부 요청 채널(%MW20) · 시각 동기(%MW0)를 받습니다.</p>"
 "<p><b>지키는 것.</b> 운전 모드 LOCAL · REMOTE_MANUAL · REMOTE_AUTO와 정비 모드(해제는 현장 키만). 고압 인터록: PT-101 ≥ 6.5 barg면 펌프 정지, 리셋은 ≤ 5.2 barg에서 운전원이 해야 풀림(인터록은 PT-101만 봄). 건조 운전 방지(LT-101 &lt; 5 %), 되읽기 감시(구동 명령 중 전류 &lt; 1.0 A가 5초면 정지), 현장 통신 3초 · 시각 동기 5초 감시, 설정값 범위. 외부 요청은 만료 시각과 요청 해시(최근 8개 중복 거름)까지 확인합니다. 결과는 ACK 코드 0~11로 냅니다. 설비 1일 주기의 생산 스케줄도 PLC 안에 있습니다(수동 조작 뒤 300초 보류).</p>")
D["edge"] = (
 "공장의 통역사이자 접수 창구입니다. PLC의 숫자를 0.25초마다 읽어 공장 게시판에 이름 붙은 값으로 올리고, 운전원 명령은 PLC에 전합니다. 밖에서 온 작업 요청은 여기서 한 번 더 검사해(검사 2) 받을지 정하고, 받은 일은 PLC나 가상 정비팀에 넘깁니다.",
 [("서비스", "edge · 망 ot-net"), ("제품", "Node-RED 5.0.7 + node-red-contrib-modbus 5.60.2 · 탭 2개(수집·명령 / OT 수신기)"), ("포트", "1880(/metrics) · 편집기 호스트 37880(로그인해도 읽기 전용)"),
  ("저장", "볼륨 edge-data(끊김 버퍼)"), ("코드", "2_ot/edge-nodered/ — src/*.js · 흐름은 등록부에서 생성(generate.py), 기동마다 재배포")],
 "<p><b>수집·명령 탭.</b> 250 ms마다 FC4 0..37(계측 38워드)과 FC3 100..118(상태 · ACK)을 읽어, 새 스캔일 때만 UNS 토픽에 값 · 품질 · 출처 시각(ns) · 스캔 순번을 붙여 올립니다(변화량 · 최대 간격 보고, 상태는 retain, 48초마다 전체 재발행). 운전원 명령(5초 넘었거나 retain이면 거부)을 %MW10에 쓰고, 1초마다 시각을 %MW0에 씁니다. 게시판이 끊기면 디스크에 72,000건까지 모았다가 다시 보냅니다. MQTT 3.1.1, 계정 edge, 생존 알림 <code>EDGE-01/state/node</code>(retain).</p>"
 "<p><b>OT 수신기 탭(검사 2).</b> MQTT 5, 계정 ot-receiver, 세션 1시간. 받은 요청을 스키마로 다시 검사하고 PLC 모드 · 정비 · 만료로 판단합니다: REMOTE_AUTO면 바로 실행, REMOTE_MANUAL이면 운전원 대기 60초(결정은 10초 안에 받아야 함), LOCAL · PLC 불통이면 거부. 정비 모드에서는 제어 요청을 거부하고, 현장 작업은 오히려 정비 모드여야 받습니다(MAINTENANCE_REQUIRED). 설비 명령은 %MW20(외부 요청 채널)에, 현장 작업(WM-FLD-…)은 가상 정비팀 :8082로 보내고(60초 제한) 소견을 <code>field</code> 단계 응답으로 올립니다. 응답이 없으면 결과 미확인으로 올리고 다시 보내지 않습니다.</p>")
D["hub"] = (
 "공장 안의 게시판입니다. MQTT를 쓰는 공장 부품(엣지 · 수신기 · 운전원 화면)은 모두 여기에만 연결하고, 계정마다 읽고 쓸 수 있는 칸이 정해져 있습니다. DMZ로 가는 연결(브리지)도 이 게시판이 먼저 엽니다. DMZ가 끊겨도 공장 안은 계속 돕니다.",
 [("서비스", "ot-hub · 망 ot-net"), ("제품", "Eclipse Mosquitto 2.1.2"), ("포트", "1883 · 호스트 37083(viewer 계정용, 라우터 경유)"),
  ("저장", "볼륨 ot-hub-data(영속 저장 60초마다)"), ("계정", "edge · ot-receiver · fuxa · viewer · ot-exporter (익명 거부, ACL 파일)"), ("코드", "2_ot/factory-broker-mosquitto/ — mosquitto.conf · acl")],
 "<p>토픽 뿌리는 <code>AR-100/reaction/{라인}/{설비}/…</code>(ISA-95식 UNS)입니다. edge는 tag · status · ack · state와 수업용 <code>edgex/telemetry</code>를 쓰고 cmd를 읽습니다. ot-receiver는 <code>AR-100/request/in</code>을 읽고 cmd/request · request/pending · <code>AR-100/response/#</code>를 씁니다. fuxa는 UNS 전체를 읽고 cmd/operator와 request/decision을 쓰며 <code>AR-100/alert/display</code>를 읽습니다. 대기열 72,000건 · 32 MiB, 끊긴 세션은 1시간 뒤 삭제, $SYS 10초.</p>"
 "<p><b>DMZ 브리지</b>(이 게시판이 엶): MQTT 5, 계정 bridge-ot, 세션 3600초. 올림(out, QoS 1): tag · status · ack · state · response. 내림(in): <code>AR-100/request/in</code>(QoS 1) · <code>AR-100/alert/display</code>(QoS 0). 브리지로 들어온 메시지에는 위 ACL이 걸리지 않고 브리지의 토픽 필터로만 거릅니다.</p>")
D["fuxa"] = (
 "운전원이 보는 공장 안 화면입니다. 값과 알람을 보이고, 운전원이 버튼으로 설비를 조작하거나, 밖에서 온 작업 요청을 수락 · 거부합니다. 사무실 쪽의 「분석 경고」도 참고로 따로 보여 줍니다.",
 [("서비스", "fuxa · 망 ot-net"), ("제품", "FUXA 1.3.4 (Node 힙 128 MB)"), ("포트", "1881(관문 뒤에서만)"),
  ("저장", "볼륨 fuxa-appdata · fuxa-db (DAQ SQLite 7일)"), ("계정", "admin · operator 로그인, 손님은 보기만, MQTT 계정 fuxa(clientId fuxa-hmi)"), ("코드", "2_ot/hmi-fuxa/ — build_project.py → project.json(등록부에서 생성)")],
 "<p>태그 51개(구독 39 · 발행 12), 화면 1장(요소 63), 알람 18개(규격 14 + 상태 4). 운전원 명령 10종을 <code>…/cmd/operator</code>로 보내고, 받은 요청 목록(<code>request/pending</code>)에서 수락 · 거부를 <code>request/decision</code>으로 냅니다. 공정 알람은 FUXA가 스스로 판정하고, 분석 경고(<code>alert/display</code>)는 참고로만 보입니다.</p>")
D["gate"] = (
 "운전원 화면 앞의 문지기입니다. 계정이 없으면 화면을 아예 보여 주지 않습니다.",
 [("서비스", "hmi-gate · 망 ot-net"), ("제품", "Caddy 2.11.4"), ("포트", "1882 → fuxa:1881 · 호스트 37018 → 라우터 21881 → 1882"), ("계정", "basic_auth 계정 plant(비밀번호는 기동 때 해시)"), ("코드", "2_ot/hmi-gate-caddy/Caddyfile")],
 "<p>FUXA는 설정으로 끌 수 없는 손님(guest) 읽기 토큰을 발급하므로, 화면 자체를 관문 뒤에 두어 계정 없는 접속을 401로 막습니다. 웹소켓도 같은 역방향 프록시로 넘깁니다(Caddy 기본 동작). 관리 API는 localhost:2019(상태 확인용).</p>")
D["hubx"] = (
 "공장 게시판의 건강 상태(연결 수 · 버린 메시지 · 브리지 상태)를 감시 장치가 읽을 수 있는 숫자로 바꿉니다. 기본 기동에서는 꺼져 있습니다.",
 [("서비스", "ot-hub-exporter · 프로필 monitoring · 망 ot-net"), ("제품", "Bento 1.21.2 · 계정 ot-exporter"), ("포트", "4195(/metrics)")],
 "<p>$SYS 토픽 7종(연결 · 수신 · 송신 · 저장 · 버림 · 브리지 · 가동 시간)을 QoS 0으로 구독해 <code>mosquitto_sys{topic}</code> 지표로 냅니다.</p>")
D["otag"] = (
 "공장 안 부품의 건강 지표를 모아 DMZ의 감시 장치로 밀어 보냅니다. 공장이 먼저 연결한다는 원칙을 감시에도 지킵니다. 기본 기동에서는 꺼져 있습니다.",
 [("서비스", "ot-agent · 프로필 monitoring · 망 ot-net"), ("제품", "Prometheus 3.13.4 --agent 모드"), ("코드", "shared/monitoring-prometheus/ot-agent.yml")],
 "<p>15초마다 edge:1880 · ot-hub-exporter:4195 · 자기 자신을 긁어, 라벨 zone=ot를 붙여 라우터 9090을 거쳐 DMZ 감시에 remote_write합니다.</p>")
D["router"] = (
 "세 구역(공장 · 완충 · 사무)을 잇는 <b>유일한 길목</b>이자 방화벽입니다. 허락된 방향과 포트만 넘기고 나머지는 세어서 버립니다. 공장과 완충 구역의 망은 바깥과 끊겨(internal) 있어서, 모든 구역 간 연결은 반드시 이 라우터를 지납니다.",
 [("서비스", "router · 망 ot-net + dmz-net + it-net (세 망에 모두 붙은 유일한 컨테이너)"), ("제품", "iptables (NET_ADMIN · ip_forward), 주소 .10.2 · .20.2 · .30.2"), ("코드", "shared/network-router/rules.sh")],
 "<p><b>새 연결 허용 목록.</b> OT → DMZ 두 가지: 1883(허브 브리지) · 9090(OT 감시 remote_write). IT → DMZ 네 가지: 1883(수집기) · 8086(원시 사본 조회) · 9090(감시 연합) · 8088(요청 게이트웨이). 호스트 → OT 여섯 가지(관문 21881 · 강사 API 28080 · 현장 패널 28081 · OT MQTT 21883 · 엣지 편집기 21880 · PLC 편집 28443, 출발지 IT 게이트웨이 주소만)와 호스트 → DMZ(MQTT · 원시 사본). DMZ → OT · DMZ → IT · IT → OT로는 새 연결이 없고, 이미 열린 연결의 응답만 돌아갑니다(상태 기반). 구역마다 별칭 주소로 받아 목적지로 넘기고(DNAT + MASQUERADE), 허용 밖은 구역별로 세어 버리며 1분마다 차단 건수를 기록합니다.</p>")
D["dmzb"] = (
 "공장과 사무실 사이 완충지대의 우편함입니다. 공장이 올린 값을 사무실이 가져가고, 사무실이 넣은 요청과 경고를 공장이 가져갑니다. 양쪽 모두 이 우편함으로 <b>먼저 찾아오고</b>, 우편함은 어디에도 먼저 연결하지 않습니다.",
 [("서비스", "dmz-broker · 망 dmz-net(외부 차단)"), ("제품", "Eclipse Mosquitto 2.1.2"), ("포트", "1883 · 호스트 37084"),
  ("저장", "볼륨 dmz-broker-data"), ("계정", "bridge-ot · dmz-loader · gateway · it-collector · viewer · dmz-exporter (익명 금지, ACL)"), ("코드", "3_dmz/dmz-broker-mosquitto/ — mosquitto.conf · acl")],
 "<p>bridge-ot: 계측 · 상태 · ACK · 통신 상태 · 응답을 쓰고, <code>AR-100/request/in</code> · <code>AR-100/alert/display</code>를 읽음. gateway: <code>AR-100/request/in</code> 쓰기만. it-collector: <code>AR-100/reaction/#</code> · <code>AR-100/response/#</code> 읽기, <code>AR-100/alert/display</code> 하나에만 쓰기. dmz-loader: <code>AR-100/reaction/#</code> 읽기. 대기열 72,000건 · 32 MiB, 끊긴 세션 1시간 뒤 삭제.</p>")
D["loader"] = (
 "우편함의 계측값과 설비 상태를 받아 완충지대의 기록장(원시 사본)에 적습니다. 값이 빠진 순간은 일부러 빈칸으로 남깁니다.",
 [("서비스", "dmz-loader · 망 dmz-net"), ("제품", "Bento 1.21.2 · 스트림 2개 · 메모리 64 MiB"), ("포트", "4195(/metrics)"), ("계정", "dmz-loader(MQTT) · 적재기 토큰(InfluxDB) · dmz-exporter($SYS)")],
 "<p>tag · status · state를 QoS 1, 깨끗한 세션으로 구독(메모리 버퍼 32 MiB)해 <code>process_raw</code>(값 · 순번 · 출처 시각)와 <code>plc_status</code> 행으로 500건 또는 1초 묶음으로 씁니다. 품질 BAD(값 null)는 행을 만들지 않아 공백으로 남고, STALE은 기록됩니다. 둘째 스트림은 DMZ 브로커 $SYS 7종을 지표로 냅니다.</p>")
D["dmzi"] = (
 "공장 원시값의 7일치 사본입니다. 사무실의 화면과 AI는 공장에 직접 묻지 않고 이 사본을 <b>읽기만</b> 합니다.",
 [("서비스", "dmz-influx · 망 dmz-net"), ("제품", "InfluxDB 2.9.1 · org ar100 · 버킷 plant_raw · 7일"), ("포트", "8086 · 호스트 37087"),
  ("저장", "볼륨 dmz-influx-data · config (쓰기 캐시 32 MB)"), ("계정", "쓰기: 적재기 토큰만 · 읽기: v1 계정 it-reader(InfluxQL 매핑 자동 생성)")],
 "<p>IT 결과는 여기 쓰지 않습니다. AI 업무 도우미가 사건 증거(첫 경보 시점 값)를, Grafana가 연결 설정을 갖고 있지만 현재 이 연결을 쓰는 Grafana 패널은 없습니다.</p>")
D["gw"] = (
 "밖(AI · 생산계획)에서 오는 작업 요청의 첫 관문입니다(검사 1). 신분증 · 서식 · 허용 작업 · 범위 · 요청자 · 승인자 · 나이 · 중복을 보고, 통과한 요청에만 30초 유효 도장을 찍어 우편함에 넣습니다. 공장 상태는 보지 않습니다.",
 [("서비스", "dmz-gateway · 망 dmz-net"), ("제품", "Node-RED 5.0.7 (편집기 없음, httpAdminRoot false)"), ("포트", "8088 — POST /requests · /health · /metrics"),
  ("계정", "Bearer 토큰(IT 발송기) · MQTT 계정 gateway"), ("코드", "3_dmz/gateway-nodered/src/check.js · 허용 목록은 등록부에서 생성해 이미지에 넣음(바꾸면 다시 빌드)")],
 "<p><b>검사 1 순서와 거부 사유</b>: 토큰(길이와 무관한 비교) → UNAUTHORIZED 401 · 스키마 → SCHEMA_INVALID 400/422 · 허용 작업 16개(설비 명령 8 + 현장 정비 8)와 설비 · 파라미터 → NOT_ALLOWED · EQUIPMENT_MISMATCH · PARAMETER_MISSING · PARAMETER_RANGE · 요청자 ID와 종류(ai-ops/ai · mes-01/mes) → REQUESTER_NOT_ALLOWED · 승인자(operator-01 · 02 · planner-01) → APPROVER_NOT_ALLOWED · 나이 10초 초과 또는 2초 미래 → TOO_OLD · 같은 요청 ID 35초 기억 → DUPLICATE 409 · 브로커 끊김 → BROKER_UNAVAILABLE 503(즉시). 통과하면 expires_at(+30초)을 붙여 MQTT 5 메시지 만료와 함께 QoS 1로 발행하고, PUBACK을 2초 기다려 202(수용) 또는 503을 돌려줍니다.</p>")
D["dmzp"] = (
 "완충지대 부품들의 건강 지표를 모으고, 공장 쪽 감시가 보낸 지표도 받아 둡니다. 사무실 감시가 이것을 통째로 가져갑니다. 기본 기동에서는 꺼져 있습니다.",
 [("서비스", "dmz-prom · 프로필 monitoring · 망 dmz-net"), ("제품", "Prometheus 3.13.4 · 보관 2시간"), ("포트", "9090")],
 "<p>15초마다 dmz-loader:4195 · dmz-gateway:8088 · dmz-influx · 자신을 긁고(zone=dmz), OT 감시의 remote_write를 받습니다. IT 감시가 라우터 9090으로 /federate해 갑니다.</p>")
D["kafka"] = (
 "사무실 쪽 데이터의 <b>번호 매긴 장부</b>입니다. 들어온 순서대로 적고, 누가 읽어도 지우지 않아 여러 서비스가 각자 읽습니다. 다만 정본(최종 기록)은 업무 DB이고, 장부는 통로이자 사본입니다.",
 [("서비스", "kafka · 망 it-net"), ("제품", "Apache Kafka 4.3.1 · KRaft 단일 노드 · 힙 128~384 MB"), ("포트", "9092(안) · 호스트 37092"),
  ("저장", "볼륨 kafka-data"), ("코드", "4_it/stream-kafka/create-topics.sh")],
 "<p>토픽 10개, 복제 1, lz4 압축, 자동 생성 끔. 7일: <code>sensor.telemetry.raw</code>(6P) · <code>sensor.telemetry.clean</code>(6P) · <code>sensor.anomaly.score</code>(3P) · <code>sensor.alerts</code>(3P) · <code>plant.status</code>(3P) · <code>alerts.display</code>(1P). 30일: <code>request.approved</code> · <code>request.events</code> · <code>request.responses</code>(각 3P) · <code>audit.copy</code>(1P). 누가 쓰고 읽는지는 <a href=\"#dict\">데이터 사전</a>에 있습니다.</p>")
D["coll"] = (
 "사무실 쪽에서 연결을 도맡는 일꾼입니다. 우편함에서 값을 가져와 장부에 넣고, 경보를 묶음 장치에 넘기고, 승인된 요청을 관문에 보내는 등 일곱 가지 일을 합니다. 모든 연결을 사무실 쪽이 먼저 엽니다.",
 [("서비스", "it-collector · 망 it-net"), ("제품", "Bento 1.21.2 · 스트림 7개 · 메모리 96 MiB"), ("포트", "4195(/metrics · 웹훅 · MES 흉내 입력)"), ("계정", "DMZ MQTT it-collector · PG ops · dispatcher · mes"), ("코드", "4_it/collector-bento/streams/")],
 "<p>① DMZ 브로커 → Kafka raw(품질 GOOD만, 키 = 설비) · plant.status · request.responses(키 = 요청 ID). ③ alerts.display → DMZ <code>AR-100/alert/display</code>(QoS 1, retain). ④ sensor.alerts → Alertmanager(라벨: source · alertname · rule · asset · tag · severity · detector, 끝 = 마지막 + 60초). ⑤ plant.status → 억제 상태(정비 · PLC 정지 · 설비 꺼짐). ⑥ Alertmanager 웹훅 → PG 묶음 · 사건 기록 → 새 묶음만 alerts.display. ⑦ request.approved → 마지막 사건이 approved인 요청만 dispatched를 먼저 적고 게이트웨이에 POST(제한 5초, 재시도 0) → 응답 ⓐ를 PG · request.events · audit.copy에. ⑧ MES 흉내 요청자: <code>/mes_requester/orders</code> → PG 요청 · 승인 → request.approved. 옛 스트림 ②(Flink 결과 → IT InfluxDB)는 ㉑로 옮겼고 번호는 비워 둡니다.</p>")
D["flink"] = (
 "흘러가는 계측값을 그 자리에서 검사하는 검사관입니다. 규격을 넘는지, 갑자기 튀는지, 위험한 순서(전류가 오른 뒤 진동이 오름)가 나타나는지, 여러 센서의 평소 관계가 깨졌는지를 네 가지 방법으로 봅니다.",
 [("서비스", "flink-jobmanager + flink-taskmanager · 망 it-net"), ("제품", "Apache Flink 2.2.1 (+ ONNX Runtime) · JM 576 MB · TM 832 MB"), ("포트", "8081(웹 · REST, 호스트 37081) · 9249(지표)"),
  ("저장", "볼륨 flink-checkpoints · model-store(읽기 전용)"), ("코드", "4_it/detection-flink/ — sql/ · onnx-job/src/main/java/org/uengine/iiot/OnnxScorer.java · conf/config.yaml · sql/tag_limits.csv · submit-jobs.sh")],
 "<p><b>잡 4개</b>(병렬도 1, 슬롯 4, 체크포인트 10초 EXACTLY_ONCE, ZooKeeper 고가용성). ① 규격: 원시값을 tag_limits.csv(17행)와 비교해 USL 초과 · LSL 미만이면 THRESHOLD_USL/LSL(CRITICAL). ② Z-Score: 태그별 최근 60샘플(30개 이상일 때)에서 |z| &gt; 3.5가 최근 5샘플 중 3번 이상이면 ZSCORE(WARNING). ③ CEP: IT-102 &gt; 9.6 A 뒤 10초 안에 VT-101 &gt; 7.1 mm/s면 CEP_BEARING(CRITICAL). ④ ONNX 오토인코더: 17태그 × 10스텝을 스캔 순번으로 맞춰(1.5초 기다린 뒤 LOCF) 재구성 오차가 임계를 넘으면 ML_AUTOENCODER(WARNING)와 기여 상위 3센서. 결측은 선형 보간(20초 넘으면 LOCF)해 clean에 싣되 원시에는 공백을 남깁니다.</p>")
D["zk"] = (
 "검사관(Flink)의 관리자가 다시 시작될 때 하던 일을 되살릴 수 있게 메모를 적어 둡니다.",
 [("서비스", "zookeeper · 망 it-net"), ("제품", "ZooKeeper 3.9.5 · 힙 64 MB"), ("포트", "2181"), ("저장", "볼륨 zookeeper-data · datalog")],
 "<p>Flink 잡 관리자의 고가용성 기록(경로 /flink, 클러스터 /ar100): 잡 목록과 최신 체크포인트 위치.</p>")
D["trainer"] = (
 "기동할 때 한 번, 「정상 운전」 데이터를 만들어 평소 센서들의 관계를 배우고, 그 결과(모델 파일)를 검사관에게 넘기고 끝납니다.",
 [("서비스", "model-trainer · 1회(restart no)"), ("제품", "Python · torch → ONNX"), ("저장", "볼륨 model-store(model.onnx · model_meta.json)"), ("코드", "4_it/ml-trainer/ — train.py · train.yaml")],
 "<p>가상설비의 물리식으로 정상 운전 21,600 표본(워밍업 1,800)을 만들어 17태그 × 10스텝(입력 170차원) 오토인코더(은닉 64 → 16, 60 epoch, batch 256)를 학습하고, 정상 오차 99.5 백분위 × 1.15를 임계로 저장합니다.</p>")
D["iti"] = (
 "검사관의 결과(정리된 값 · 이상 점수 · 경보 이력)를 30일 보관하는 기록장입니다. 그래프 화면이 읽습니다. 기본 기동에서는 꺼져 있습니다.",
 [("서비스", "it-influx · 프로필 monitoring · 망 it-net"), ("제품", "InfluxDB 2.9.1 · bucket process · 30일"), ("포트", "8086 · 호스트 37086")],
 "<p>㉑ 이력 적재기가 쓰고 Grafana 01~03 화면이 읽습니다. AI는 이 저장소를 쓰지 않습니다(AI 증거는 ⑫ DMZ 원시 사본).</p>")
D["hist"] = (
 "장부에 적힌 검사관의 결과를 결과 기록장(IT InfluxDB)으로 옮겨 적습니다. 기본 기동에서는 꺼져 있습니다.",
 [("서비스", "it-history · 프로필 monitoring · 망 it-net"), ("제품", "Bento 1.21.2"), ("코드", "4_it/history-bento/kafka_to_it_influx.yaml")],
 "<p>Kafka clean · anomaly.score · alerts를 그룹 it-collector-influx(옛 이름 유지), 최신부터 구독해 라인 프로토콜로 process · anomaly · alerts 측정값을 1초 또는 1,000건 묶음으로 씁니다. 원래 IT 수집기의 스트림 ②였습니다.</p>")
D["pg"] = (
 "업무의 <b>정본</b>(최종 기록)입니다. 설비 등록부, 작업 요청과 승인과 결과, 경보 묶음, 감사 기록, 회사 시스템의 사실값, AI의 사건 기록이 여기 있습니다. 한 번 적은 요청 · 사건 · 감사 기록은 고치거나 지울 수 없습니다.",
 [("서비스", "postgres · 망 it-net"), ("제품", "PostgreSQL 18.6"), ("포트", "5432 · 호스트 37532"), ("저장", "볼륨 pg-data"),
  ("계정", "ops · dispatcher · mes · ai_app · reader(SELECT만)"), ("코드", "4_it/db-postgres/init/ — 00_roles.sh · 10_schema.sql · 20_registry.sql · 30_enterprise.sql")],
 "<p><b>DATABASE plant</b>: registry(설비 9 · 신호 17 · 작업 정의 16) · workflow(request · request_event · moc_record, 뷰 request_status) · alert(alert_event · alert_group) · audit.log · enterprise(fact: MES 8 · ERP 7 · CMMS 5 = 사실값 20개, work_order). <b>DATABASE ai</b>(소유자 ai_app): 사건 · 사건 이벤트 · 알람 연결 · 수신함 · 대응안 · 분석 실행 · 지식 빌드 기록.</p>"
 "<p><b>추가 전용 5표</b>(request · request_event · moc_record · alert_event · audit.log): 트리거 <code>audit.append_only</code>가 수정 · 삭제를 거부하고 권한도 회수했습니다. 권한: ops = workflow · alert_event 추가, alert_group 추가·수정, 감사 추가 / dispatcher = request_event · 감사 추가 / mes = request · request_event · 감사 추가 / ai_app = workflow 추가, alert 읽기, 감사 추가, enterprise.fact 읽기, enterprise.work_order 추가.</p>")
D["graf"] = (
 "공정 값 · 이상 점수 · 경보 이력 · 시스템 건강을 그래프 네 장으로 보여 주는 화면입니다. 기본 기동에서는 꺼져 있습니다(AI 화면의 공정 대시보드가 기본 화면).",
 [("서비스", "grafana · 프로필 monitoring · 망 it-net"), ("제품", "Grafana 13.2.3 · 익명 Viewer · 폴더 AR-100"), ("포트", "3000 · 호스트 37030")],
 "<p>01 공정 트렌드(8패널: 레벨 · 온도 · 압력 · 유량 · 전류 · 진동 · pH/전도도 · 실측 vs 보간) · 02 ML 이상(4패널) · 03 알람 이력(2패널) · 04 인프라(6패널: Kafka 랙 · 유입률 · 체크포인트 · 실패·재시작 · MQTT 연결 · 컨테이너 CPU). 원천: IT InfluxDB · Prometheus. DMZ 원시 사본 연결(<code>dmz-raw</code>)은 등록돼 있지만 쓰는 패널이 없습니다. 냉각수 계통 5태그 패널도 아직 없습니다.</p>")
D["prom"] = (
 "사무실 쪽 부품과, DMZ에서 가져온 공장 · 완충지대 지표까지 한곳에 모아 시스템이 건강한지 봅니다. 공정 값이 아니라 시스템을 봅니다. 기본 기동에서는 꺼져 있습니다.",
 [("서비스", "prometheus · 프로필 monitoring · 망 it-net"), ("제품", "Prometheus 3.13.4 · 보관 7일"), ("포트", "9090 · 호스트 37090"), ("코드", "shared/monitoring-prometheus/it.yml · rules.yml")],
 "<p>10초마다 job 7개(자신 · federate-dmz · kafka · flink JM/TM :9249 · it-influx · it-collector · cadvisor). 규칙 그룹 pipeline-health 10개: KafkaConsumerLagHigh(&gt;5000, 2분) · FlinkCheckpointFailing · FlinkJobRestarting · MosquittoBridgeDown · CollectorInputStalled · MosquittoClientDisconnectSpike · MosquittoMessagesDropped · EdgeStoreAndForwardBacklog · TelemetryIngestStalled · PipelineServiceDown → Alertmanager.</p>")
D["am"] = (
 "같은 경보가 수십 번 울리지 않게 묶고, 정비 중이거나 일부러 꺼 둔 설비의 경보는 눌러 둡니다. 새 묶음이 생기거나 풀릴 때만 알립니다. 기본 기동에 포함됩니다.",
 [("서비스", "alertmanager · 망 it-net"), ("제품", "Alertmanager v0.34.1"), ("포트", "9093 · 호스트 37093"), ("저장", "볼륨 alertmanager-data"), ("코드", "shared/monitoring-prometheus/alertmanager.yml")],
 "<p>공정 경로(source=plant|plant-state): 수신자 plant(웹훅 → IT 수집기 ⑥, 해제 알림 포함), 묶기 [asset · rule · alertname], 대기 0초 · 간격 5초 · 반복 24시간. 인프라 경로: 수신자 default(로그만), 묶기 [alertname · tier]. 억제 규칙 4개: OutOfService(정비 모드) · PlantStopped(PLC 정지) → 공정 경보 전체, SuppressedByDesign(설비 운전 꺼짐) → 같은 설비, PipelineServiceDown → 같은 tier의 warning(ISA-18.2의 억제 개념).</p>")
D["kexp"] = (
 "장부를 읽는 쪽이 얼마나 밀려 있는지(랙)를 숫자로 냅니다. 기본 기동에서는 꺼져 있습니다.",
 [("서비스", "kafka-exporter · 프로필 monitoring"), ("제품", "kafka-exporter 1.10.0"), ("포트", "9308")], "<p>컨슈머 랙 · 토픽 오프셋을 IT 감시에 냅니다.</p>")
D["cadv"] = (
 "컨테이너마다 CPU · 메모리 · 네트워크를 얼마나 쓰는지 숫자로 냅니다. 기본 기동에서는 꺼져 있습니다.",
 [("서비스", "cadvisor · 프로필 monitoring"), ("제품", "cAdvisor 0.60.6")], "<p>IT 감시가 10초마다 긁습니다.</p>")
D["graph"] = (
 "설비 · 센서 · 증상 · 고장 · 원인 · 매뉴얼 · 정비 방법 · 업무 지표가 어떻게 이어지는지 적은 <b>지식 지도</b>(온톨로지)입니다. AI는 여기서 원인 후보와 정비 대안, 대안별 손익 식, 해서는 안 되는 규칙을 찾습니다. 회사의 실제 숫자(사실값)는 여기 넣지 않고 업무 DB에서 이름으로 읽습니다.",
 [("서비스", "graph · 망 it-net"), ("제품", "Neo4j 5.26 Community · 힙 256 MB · 페이지 캐시 32 MB"), ("포트", "7474 · 7687 · 호스트 37474 · 37687"), ("저장", "볼륨 graph-data · graph-logs")],
 "<p>묶음 A(110노드 · 142관계) · B(45 · 53) · C(279 · 469, 생성기 기준 집계). C의 주요 노드: 정비 단계 63 · 매뉴얼 절 51 · 원인 28 · 입력 20 · 대안 14 · 작업 정의 14 · 고장 유형 13 · 점검 13 · 경보 서명 11 · 규칙 6 · KPI 5 · 부서 4 · 증상 3 · 결정 3. 관계: 단계 63 · 작업 정의 사용 58 · 손익(IMPACTS) 48 · 입력 35 · 처치 18. 결정 3개: 냉각 회복(대안 5 · 규칙 2) · 교반기 수리(대안 5 · 규칙 3: 진동 영역 D 대기 금지 · 예비 베어링 없음 · 배치 이미 정지) · 압력 대응(대안 4 · 규칙 1: 인터록 우회 금지). KPI 5개(BSC): 생산 손실 · 납기 지연 · 품질 · 정비 비용 · 설비·안전 위험. 매뉴얼 절에는 임베딩 벡터(1536차원)가 붙어 있습니다.</p>")
D["ai"] = (
 "AI 업무 도우미입니다. 경보가 모여 사건이 되면 스스로 조사를 시작해 원인을 판단하고, 정비 대안들의 득실을 계산해 <b>조치 카드</b>를 만듭니다. 사람이 승인하면 정비 계획을 한 단계씩 작업 요청으로 보내고, 회복을 확인한 뒤 작업 보고서를 씁니다. 설비에 직접 닿는 연결은 없습니다.",
 [("서비스", "knowledge · 망 it-net"), ("제품", "Python · FastAPI + LangGraph · 모델 gpt-6-luna(Responses API) · 임베딩 text-embedding-3-small"), ("포트", "8000 · 호스트 38000"),
  ("저장", "볼륨 knowledge-data · uploads · output · 기록은 PG ai DB"), ("코드", "5_ai/server/knowledge/backend/src/modules/operations/ — agent.py · decision.py · maintenance.py · actions.py · evidence.py · api.py · 그래프 채우기 5_ai/server/seed_graph.py")],
 "<p><b>사건과 자동 분석.</b> 경보를 묶음 3종(교반기 전류·진동 · 반응기 열·냉각 · 반응기 압력)으로 사건에 묶고, 30초 조용하면 다른 사건으로 나눕니다. 새 종류의 경보가 15초 동안 더 붙지 않고, 경보 3건 이상 · 마지막 경보 30초 안 · 한계 이탈 경보(THRESHOLD_USL/LSL · CEP_BEARING)가 있으면 스스로 분석을 시작합니다(<code>AI_AUTO_ANALYZE=1</code>). 화면의 「AI 분석」 버튼도 있습니다.</p>"
 "<p><b>에이전트</b>(조사 → 사람 검토 → 실행). 도구 7개(사건 경보 · 설비 문서 · 센서 관측(첫 경보 시점 스냅샷 포함) · 고장 온톨로지 추적 · 매뉴얼 절 검색(벡터 상위 10 중 그래프에 연결된 절 우선 3) · 선례(이 사건 것만 근거) · 정비 대안 평가)를 반드시 모두 불러야 하고, 빠지면 게시하지 않습니다. 요약은 [관측] · [원인 판단] · [대안 비교] · [정비 계획] · [승인 시 영향] 다섯 머리로 쓰고, 조치 카드는 5분 동안만 유효합니다.</p>"
 "<p><b>결정 엔진</b>(LLM이 아닌 계산). 증상에 걸린 결정의 대안 · 규칙 · 손익 식 · 단계를 그래프에서 읽고, 사실값 20개와 관측값으로 KPI별 손익(만원)을 계산합니다. 규칙이 EXCLUDE면 손익 1위라도 빼고, 원인이 좁혀졌을 때만 원인 맞춤 정비를 후보로 올립니다. 순위 · 권고안 · 차선과 「사실값 하나가 얼마가 되면 권고가 뒤집히는지」(뒤집힘 표)를 냅니다. 승인할 때 같은 계산을 다시 해서 통과해야 실행합니다.</p>"
 "<p><b>정비 계획 실행기</b>(1초마다). 단계 종류 넷: control(PLC 작업 요청, 결과 한도 60초) · field(가상 정비팀 작업, 한도 = 설비 시간 ÷ 600 + 60초) · operator(운전원이 할 일, 조건이 참이 되기를 최대 180초 대기) · wait(설비 시간 대기). 운전원 대기가 걸리면 한도에 95초를 더합니다. 단계마다 요청 ID <code>ai-…</code>를 새로 만들고, 결과가 불명확하면 다시 보내지 않고 멈춥니다. 정비팀이 「고장 없음」이라 답하면 멈추고(cause_mismatch), 격리 중이었다면 정리 단계 <code>WM-FLD-LOTO-RELEASE</code>를 거쳐 설비를 정지 상태로 넘깁니다. 회복 기준을 30초 연속 만족하면(한도: 냉각·교반 180초, 압력 240초) 보고서(단계 · 소견 · 전후 값 · KPI 예상 대비 실적)를 쓰고 작업 번호 <code>WO-yymmdd-…</code>를 enterprise.work_order에 남깁니다.</p>")
D["web"] = (
 "AI 업무 화면입니다. 공정 대시보드, 사건과 AI의 분석 · 조치 카드 · 승인/반려 · 정비 진행 · 보고서, 설비 지식을 편집하는 스튜디오를 보여 줍니다.",
 [("서비스", "web · 망 it-net"), ("제품", "nginx 1.28 + Vue(node 24로 빌드)"), ("포트", "8080 · 호스트 38180"), ("코드", "5_ai/web/ — src/App.vue · src/features/operations/MaintenancePlanCard.vue · nginx.conf")],
 "<p>화면 셋: 공정 대시보드(냉각수 계통 FT-103 · PDT-103 · TT-103 · TT-104 · PT-102 포함) · 이상 대응 · AI 검토(사건 최근 100건, 탭: AI 분석·검토·결과 / 센서·매뉴얼 근거 / 전체 처리 이력) · 설비 지식 스튜디오(자료 · 후보 · 검토 / 관계 그래프 / 연결 현황). 정비 계획 카드: 권고안 · 원인 판단 표 · 대안 손익 비교 · 뒤집히는 조건 · 정비 단계 · 회복 기준 · 계산에 쓴 사실값. 운전원 제어 창은 FUXA를 끼워 보여 줍니다. 2초마다 갱신, <code>/api</code>는 knowledge:8000으로 넘김(읽기 60초, 재시도 안 함).</p>")
D["bus"] = (
 "경보를 AI 사건으로 접수하고, 작업 요청이 정말 실행됐는지 시간을 재며 판정하는 업무 담당입니다. 결과를 모르는 요청을 다시 보내지는 않습니다.",
 [("서비스", "business · 망 it-net"), ("제품", "Python · Kafka 소비자 2개"), ("계정", "PG ops(plant) · ai_app(ai)"), ("코드", "5_ai/server/knowledge/backend/src/modules/operations/business.py")],
 "<p>소비자 <code>ar100-ai-incidents-v1</code>(처음부터): sensor.alerts → AI 사건 접수(원본은 수신함에 보존). 소비자 <code>ar100-business-v2</code>(최신부터): plant.status · request.responses. 0.5초 타이머로 판정: ACK 5초 안 응답 없음 → 결과 모름 · 만료 + 5초 → 미확인 · 운전원 대기 60 + 30 + 5 = 95초 초과 · PLC 수용 뒤 10초 안에 설비 상태가 바뀌었는지 재관측(일치 observed / 불일치 command_disagree, 불일치는 sensor.alerts로 경보). 현장 작업은 정비팀 결과(DONE · DONE_NO_FAULT)가 재관측을 대신하고, 설비 시간 ÷ 600 + 30초 안에 없으면 미확인. 정비 모드 켜기 · 끄기도 감사에 남깁니다.</p>")
D["llm"] = (
 "글을 읽고 추론하는 외부 AI 서비스(OpenAI)입니다. 원인 분석 에이전트와 매뉴얼 의미 검색에만 씁니다. 손익 계산 · 규칙 판정 · 승인은 LLM이 하지 않습니다.",
 [("위치", "밖(인터넷), api.openai.com 직접 호출(중계 LiteLLM은 10-06에 폐기)"), ("모델", "gpt-6-luna(Responses API, 도구 호출 · 구조화 출력, 추론 노력 medium, 제한 90초 · 재시도 0) · text-embedding-3-small 1536차원"),
  ("키", "5_ai/server/.env.local의 OPENAI_API_KEY(git 제외) → knowledge · graph-seed에만")],
 "<p>키가 없으면 그래프 채우기는 임베딩을 건너뛰고 끝나지만, 빈 벡터가 남아 있으면 실패로 끝나 AI 업무 도우미가 뜨지 않습니다.</p>")
D["host"] = (
 "사람과 시험 도구가 들어오는 자리입니다. 모든 공개 포트는 같은 PC(127.0.0.1)에만 열리고, 공장 · 완충지대 화면은 라우터를 거쳐서만 들어옵니다.",
 [("공개 포트", "AI 화면 38180 · AI API 38000 · FUXA 37018 · 강사 API 37080 · 현장 패널 37082 · OT MQTT 37083 · 엣지 37880 · PLC 37443 · DMZ MQTT 37084 · DMZ 사본 37087 · Kafka 37092 · Flink 37081 · PG 37532 · Alertmanager 37093 · Neo4j 37474/37687 (감시 프로필: Grafana 37030 · Prometheus 37090 · IT Influx 37086)"),
  ("명령", "make up(기본) · make up-full(감시 포함) · make scenario-1 … 3v · make verify"), ("시험", "tests/verify.py(전 계층) · tests/e2e/maintenance_scenarios.py(정비 시나리오 7개)")],
 "<p>정비 시나리오 7개: s1 스트레이너 막힘 · s1v 재킷 스케일 · s2 베어링 마모(반려 후 재분석 옵션) · s2v 축 정렬 불량 · s3 압력계 드리프트 · s3v 배출 밸브 고착 · s2m 원인 불일치 훈련. MES 흉내 지시는 IT 망 안에서 IT 수집기의 <code>/mes_requester/orders</code>로 넣습니다(호스트 공개 포트 없음).</p>")
D["prov"] = (
 "기동할 때 운전원 화면에 계정과 화면 설정을 넣고 끝나는 도우미입니다.",
 [("서비스", "fuxa-provisioner · 1회"), ("제품", "python:3.12-slim")],
 "<p>admin 비밀번호 교체 · operator 생성 · MQTT 계정을 장치 보안 저장소에 넣고, <code>POST /api/project</code>로 화면(태그 51 · 알람 18)을 올립니다.</p>")
D["kinit"] = (
 "기동할 때 장부의 칸(토픽 10개)을 보존 기간과 함께 만들고 끝나는 도우미입니다.",
 [("서비스", "kafka-init · 1회"), ("코드", "4_it/stream-kafka/create-topics.sh")],
 "<p>이미 있으면 건너뜁니다(멱등). 7일 6개 · 30일 4개, 파티션 6 · 3 · 1, lz4. IT 수집기와 이력 적재기가 이 도우미의 완료를 기다렸다 뜹니다.</p>")
D["submit"] = (
 "기동할 때 검사관(Flink)에게 검사 일 4가지를 맡기고 끝나는 도우미입니다.",
 [("서비스", "flink-job-submitter · 1회"), ("코드", "4_it/detection-flink/submit-jobs.sh")],
 "<p>SQL 잡 3개 + ONNX 잡 1개를 8081로 제출합니다. 4개가 이미 실행 중이면 건너뛰고, 일부만 실행 중이면 실패로 멈춥니다.</p>")
D["seed"] = (
 "기동할 때 지식 지도를 채우고 매뉴얼에 검색용 벡터를 붙인 뒤 끝나는 도우미입니다. 성공해야 AI 업무 도우미가 뜹니다.",
 [("서비스", "graph-seed · 1회(멱등)"), ("제품", "ceco-ai-knowledge 이미지")],
 "<p>묶음 A · B · C를 지문(digest)과 함께 게시하고, 이전 판 고장 온톨로지의 개체 · 관계를 정리하고, 매뉴얼 절과 개체에 임베딩을 붙입니다. 빠진 벡터나 0 벡터가 남으면 실패로 끝납니다.</p>")
assert set(D) == set(PART), set(D) ^ set(PART)

# ═════════════ 연결 설명: (프로토콜 · 포트 · 계정, 실어 나르는 것) ═════════════
C = {}
C["modbus_sim"] = ("Modbus TCP 502, 100 ms", "PLC가 FC3로 계측 HR0..37 · 스캔 순번 · 설비 시각 · 현장 패널 HR300..308을 읽고, FC15로 코일 4개(구동기), FC16으로 설정값 3개를 쓴다.")
C["modbus_plc"] = ("Modbus TCP 502, 250 ms", "엣지가 FC4 0..37(계측 38워드)과 FC3 100..118(상태 · ACK)을 읽고, %MW10 운전원 채널 · %MW20 외부 요청 채널 · %MW0 시각(1초)을 쓴다.")
C["edge_mqtt"] = ("MQTT 3.1.1, 계정 edge", "올림: UNS 계측 tag · status · ack · state · 수업용 edgex/telemetry · 생존 알림. 내림: …/cmd/operator, …/cmd/request.")
C["recv_mqtt"] = ("MQTT 5, 계정 ot-receiver, 세션 1시간", "내림: <code>AR-100/request/in</code> · PLC 상태 · ACK · 운전원 결정. 올림: 응답 <code>AR-100/response/…</code>(수신 ⓑ · field 단계) · …/cmd/request · 받은 요청 목록.")
C["recv_crew"] = ("HTTP POST /tasks 8082, OT 망 안, Basic 계정 crew, 제한 60초", "현장 정비 작업 지시를 보내고 같은 연결로 소견(DONE · DONE_NO_FAULT · REJECTED, 작업 시간)을 받는다. 응답이 없으면 결과 미확인으로 올리고 다시 보내지 않는다.")
C["fuxa_mqtt"] = ("MQTT, 계정 fuxa(clientId fuxa-hmi)", "내림: UNS 전체 · 분석 경고 · 받은 요청 목록. 올림: 운전원 명령 · 요청 수락/거부.")
C["gate_fuxa"] = ("HTTP 1882 → 1881 역방향 프록시(웹소켓 포함)", "관문을 통과한 화면 요청만 FUXA로.")
C["hubx_sys"] = ("MQTT $SYS 구독 QoS 0, 계정 ot-exporter", "허브의 연결 · 수신 · 송신 · 저장 · 버림 · 브리지 · 가동 시간.")
C["otag_scrape"] = ("HTTP 긁기 15초", "edge:1880/metrics(끊김 버퍼 건수 등) · ot-hub-exporter:4195.")
C["bridge_out"] = ("MQTT 5 브리지, 라우터 1883, 계정 bridge-ot, 세션 3600초", "올림(QoS 1): tag · status · ack · state · response. DMZ가 끊기면 허브에 72,000건까지 쌓였다가 이어서 보낸다.")
C["bridge_in"] = ("C10과 같은 연결(그림은 방향별로 나눔)", "내림: <code>AR-100/request/in</code>(QoS 1, 만료 붙음) · <code>AR-100/alert/display</code>(QoS 0). 연결은 OT가 열었지만 데이터는 DMZ → OT로 흐른다.")
C["otag_rw"] = ("HTTP remote_write, 라우터 9090", "OT 지표(zone=ot)를 DMZ 감시로 밀어 보낸다.")
C["loader_sub"] = ("MQTT QoS 1, 깨끗한 세션, 계정 dmz-loader, 버퍼 32 MiB", "계측 · 상태 · 통신 상태.")
C["loader_write"] = ("HTTP 8086, 적재기 토큰", "process_raw · plc_status 행, 500건 또는 1초 묶음.")
C["gw_pub"] = ("MQTT 5, 계정 gateway, QoS 1, 메시지 만료 30초", "검사 1을 통과한 요청 + expires_at. PUBACK 2초 안 없으면 503.")
C["dmzp_scrape"] = ("HTTP 긁기 15초", "dmz-loader:4195 · dmz-gateway:8088/metrics(요청 결과별 건수 · 브로커 연결) · dmz-influx.")
C["coll_sub"] = ("MQTT, 라우터 1883, 계정 it-collector", "계측 · 상태 · 통신 상태 · ACK · 요청 응답을 가져가 Kafka로(스트림 ①).")
C["coll_disp"] = ("MQTT, 라우터 1883, QoS 1 retain", "표시할 분석 경고를 <code>AR-100/alert/display</code> 하나에만 쓴다(스트림 ③).")
C["coll_gw"] = ("HTTP POST /requests, 라우터 8088, Bearer, 제한 5초, 재시도 0", "승인된 요청을 보내고 같은 연결로 수용 · 거부와 이유를 받는다(응답 ⓐ, 스트림 ⑦).")
C["graf_dmzi"] = ("HTTP 8086 조회, 라우터, 계정 it-reader", "연결 설정만 있고 이 연결을 쓰는 패널은 없다.")
C["ai_dmzi"] = ("HTTP 8086 InfluxQL, 라우터, 읽기 전용 계정 it-reader", "사건 증거용 원시값(첫 경보 시점 · 사건 창).")
C["prom_fed"] = ("HTTP /federate, 라우터 9090", "DMZ · OT 지표를 IT 감시로 가져온다.")
C["coll_kafka"] = ("Kafka 9092", "쓰기: raw · plant.status · request.responses · alerts.display · request.events · audit.copy · request.approved(⑧). 읽기: sensor.alerts · plant.status · alerts.display · request.approved.")
C["flink_kafka"] = ("Kafka 9092, 그룹 flink-tier1 · flink-tier2-onnx", "읽기: sensor.telemetry.raw. 쓰기: clean · anomaly.score · sensor.alerts.")
C["flink_zk"] = ("ZooKeeper 2181", "잡 관리자 복구 기록.")
C["hist_kafka"] = ("Kafka 9092, 그룹 it-collector-influx, 최신부터", "읽기: clean · anomaly.score · sensor.alerts.")
C["hist_iti"] = ("HTTP 8086 /api/v2/write", "정제값 · 이상 점수 · alert 이력(라인 프로토콜).")
C["coll_am"] = ("HTTP POST /api/v2/alerts", "분석 alert(라벨 7개, 끝 = 마지막 + 60초, 스트림 ④)와 억제 상태(끝 + 86400초, 스트림 ⑤).")
C["am_coll"] = ("HTTP 웹훅 → it-collector:4195/alertmanager_to_display/alertmanager", "새 묶음 · 해제만 알린다(스트림 ⑥이 받음).")
C["coll_pg"] = ("PostgreSQL 5432, 계정 ops · dispatcher · mes", "⑥ 경보 묶음 · 사건, ⑦ dispatched · 응답 ⓐ · 감사, ⑧ MES 요청 · 승인 · 감사.")
C["bus_kafka"] = ("Kafka 9092", "읽기: sensor.alerts(사건 접수) · plant.status · request.responses. 쓰기: request.events · audit.copy 사본, 명령≠상태 경보(sensor.alerts).")
C["bus_pg"] = ("PostgreSQL 5432, 계정 ops(plant) · ai_app(ai)", "요청 판정 사건 · 감사, AI 사건 접수.")
C["ai_pg"] = ("PostgreSQL 5432, 계정 ai_app", "사건 · 대응안 · 분석 기록(ai), 작업 요청 · 승인 · 감사 기록과 결과 사건 읽기(plant), 사실값 읽기 · 작업 이력 추가(enterprise).")
C["ai_kafka"] = ("Kafka 9092, acks=all, 제한 5초", "승인 기록이 끝난 요청 ID를 request.approved에. 정비 계획은 단계마다 한 건. 못 내면 not_dispatched로 남기고 보내지 않는다.")
C["ai_graph"] = ("Bolt 7687", "고장 온톨로지 추적 · 매뉴얼 벡터 검색 · 결정 엔진 조회(대안 · 손익 식 · 규칙 · 단계).")
C["ai_flink"] = ("HTTP 8081", "탐지 잡 상태(4개 RUNNING이면 정상).")
C["ai_llm"] = ("HTTPS(인터넷), OpenAI Responses API · 임베딩", "원인 분석 에이전트(도구 호출 · 구조화 출력), 매뉴얼 의미 검색 임베딩.")
C["web_ai"] = ("HTTP /api (nginx → knowledge:8000)", "화면 ↔ 업무 도우미. 읽기 60초, 재시도 안 함.")
C["graf_iti"] = ("HTTP 8086", "정제값 · 이상 점수 · alert 이력.")
C["graf_prom"] = ("HTTP 9090", "인프라 그래프.")
C["prom_scrape"] = ("HTTP 긁기 10초", "kafka-exporter:9308 · cAdvisor · it-collector:4195 · Flink :9249 · it-influx.")
C["prom_am"] = ("HTTP 9093", "인프라 경보 10종(수신자 default = 로그만).")
C["kexp_kafka"] = ("Kafka 9092", "랙 · 오프셋 조회.")
C["trainer_flink"] = ("파일(공유 볼륨 model-store)", "model.onnx · model_meta.json(정규화 값 · 임계).")
C["host_router"] = ("호스트 127.0.0.1 공개 포트 → 라우터 → OT · DMZ", "37018 관문 · 37080 강사 API · 37082 현장 패널 · 37083 OT MQTT · 37880 엣지 편집기 · 37443 PLC 편집 · 37084 DMZ MQTT · 37087 DMZ 사본. 정비팀 8082는 열지 않는다.")
C["host_it"] = ("호스트 공개 포트(IT)", "AI 화면 38180. 같은 방식으로 AI API · Kafka · Flink · PG · Alertmanager · Neo4j(감시 프로필이면 Grafana · Prometheus · IT Influx).")
C["mes_coll"] = ("HTTP POST /mes_requester/orders (IT 망 안에서)", "MES 생산 지시(작업 ID · 설비 · 파라미터 · 계획 담당). 스트림 ⑧이 요청 · 승인으로 기록하고 승인 토픽에 낸다.")
C["prov_fuxa"] = ("HTTP(1회)", "계정 · 장치 보안 값 · 화면 프로젝트.")
C["kinit_kafka"] = ("Kafka 관리 명령(1회)", "토픽 10개 생성.")
C["submit_flink"] = ("HTTP 8081(1회)", "SQL 잡 3개 + ONNX 잡 1개 제출.")
C["seed_graph"] = ("Bolt(1회)", "묶음 A · B · C, 매뉴얼 · 개체 임베딩.")
assert set(C) == set(L), set(C) ^ set(L)
