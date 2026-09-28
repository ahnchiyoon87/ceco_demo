"""Arrange the requested three-part narrative and one complete architecture."""
from pathlib import Path
import re
from html import escape
root=Path(__file__).resolve().parents[1]
p=root/'docs/소스코드로_확인한_아주쉬운_시스템설명.html'
s=p.read_text(encoding='utf8')
sections={m.group(1):m.group(0) for m in re.finditer(r'<section id="([^"]+)">.*?</section>',s,re.S)}
def box(x,y,w,title,sub,h=76):
 return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="white" stroke="#86aaa9"/><text x="{x+w/2}" y="{y+29}" class="bt" text-anchor="middle">{escape(title)}</text><text x="{x+w/2}" y="{y+54}" class="bs" text-anchor="middle">{escape(sub)}</text>'
def arrow(d,label='',x=0,y=0,cmd=False):
 c='#b3481d' if cmd else '#176f67'; marker='cmd' if cmd else 'info'
 return f'<path d="{d}" stroke="{c}" stroke-width="2.5" fill="none" marker-end="url(#{marker})"/>'+ (f'<text x="{x}" y="{y}" class="edge" text-anchor="middle">{escape(label)}</text>' if label else '')
svg='''<div class="arch" tabindex="0" role="region" aria-label="전체 시스템 아키텍처. 좁은 화면에서는 가로로 이동"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1500 1500" role="img" aria-label="설비부터 수집, 분석, 저장, 화면과 Pilot 승인 조치까지 연결한 전체 아키텍처"><defs><marker id="info" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8Z" fill="#176f67"/></marker><marker id="cmd" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8Z" fill="#b3481d"/></marker></defs><style>.bt{font:700 19px Malgun Gothic,sans-serif;fill:#163c48}.bs{font:15px Malgun Gothic,sans-serif;fill:#355967}.edge{font:14px Malgun Gothic,sans-serif;fill:#244f57}.lane{font:700 17px Malgun Gothic,sans-serif;fill:#356675}</style>'''
for y,h,label in [(40,150,'L1 · 설비'),(210,150,'L2 · 수집·중계'),(380,120,'L3 · 원본 기록'),(520,140,'L4 · 분석'),(680,130,'L5 · 결과 기록'),(830,250,'L6 · 이력 저장'),(1100,150,'L7 · 기록 화면')]:
 svg+=f'<rect x="15" y="{y}" width="900" height="{h}" rx="12" fill="#eff6f7"/><text x="30" y="{y+28}" class="lane">{label}</text>'
svg+='<rect x="940" y="365" width="540" height="1100" rx="14" fill="#f0f7f2"/><text class="lane" x="960" y="400">L8 · Pilot 업무 / 조사·검토·조치</text>'
svg+=box(230,85,520,'가상 설비 · AR-100','반응기·교반기·센서·운전 명령')
svg+=box(980,85,470,'FUXA · 운전원 화면 (L7)','Modbus 현재값·직접 조작 / MQTT 분석 알람')
svg+=arrow('M750 105 H980','Modbus 계측값',863,91)+arrow('M980 145 H750','Modbus 운전 명령',865,170,True)
svg+=box(190,265,210,'EdgeX','수집·이벤트·MQTT 내보내기')+box(465,265,160,'EMQX','MQTT 중계')+box(690,265,200,'Telegraf','수집 형식 정리')
svg+=arrow('M490 161 V205 H295 V265','Modbus로 읽은 값',440,225)+arrow('M400 303 H465','MQTT',434,290)+arrow('M625 303 H690','MQTT',658,290)
svg+=box(240,415,610,'Kafka · 원본 토픽','센서 원본 기록 · sensor.telemetry.raw')+arrow('M790 341 V415')
svg+=box(210,565,270,'Flink · 규칙 작업','상·하한 / Z-Score / CEP')+box(595,565,280,'Flink · 모델 작업','전처리 → ONNX 모델 실행')
svg+=arrow('M345 491 V565','원본 읽기',404,540)+arrow('M735 491 V565','원본 읽기',796,540)
svg+=box(240,720,610,'Kafka · 결과 토픽','clean 정리값 / score 이상 점수 / alerts 알람')+arrow('M345 641 V720')+arrow('M735 641 V720')
svg+=box(300,880,490,'Telegraf · 저장용','원본과 분석 결과를 각각 읽어 저장')+arrow('M545 796 V880','결과 읽기',620,852)+arrow('M240 453 H180 V918 H300','원본 직접 저장',270,847)
svg+=box(300,990,490,'InfluxDB','시간별 센서 이력·분석 결과')+arrow('M545 956 V990')
svg+=box(300,1150,490,'Grafana','센서 이력 / 운영 지표를 그래프로 표시')+arrow('M545 1066 V1150','조회된 이력',620,1120)
svg+=box(40,1320,350,'Prometheus','각 프로그램이 제공한 운영 지표 수집')+arrow('M390 1358 H850 V1188 H790','조회된 운영 지표',676,1344)
# Alarm bridge stays in the gap between collection and Pilot lanes; its return
# line ends at FUXA without crossing the command/measurement arrows.
svg+=box(985,235,460,'Telegraf · 알람 중계 → EMQX','Kafka alerts → MQTT 최근 알람')
svg+=arrow('M850 750 H930 V273 H985','알람',961,350)+arrow('M1220 235 V161','MQTT 알람',1300,204)
svg+=box(990,440,440,'① 사건 접수','Kafka 알람을 업무로 등록')+arrow('M850 780 H955 V478 H990','alerts',995,615)
svg+=box(990,585,440,'② Agent 근거 조사','사람이 분석 시작 · 도구 호출 기록 표시')+arrow('M1210 516 V585','분석 요청',1300,557)
svg+=box(1020,745,380,'근거 저장소 · 조회 대상','Neo4j 관계·문서 / InfluxDB 센서 이력')+arrow('M1210 745 V661','조회된 근거',1286,710)
svg+=box(990,905,440,'③ 담당자 검토','조치안·근거 확인 / 승인 또는 반려')+arrow('M1430 623 H1460 V943 H1430')
svg+=box(990,1070,440,'④ 승인 후 실행·확인','조건 재검사 → Modbus 정지 → HTTP 확인')+arrow('M1210 981 V1070','승인된 경우',1300,1034,True)
svg+=box(990,1240,440,'PostgreSQL · 업무 기록','사건·AI 조사·승인·조치 결과 저장')+arrow('M1210 1146 V1240','처리 결과 기록',1310,1200)
svg+=box(990,1360,440,'Vue · 통합 대시보드','백엔드 API로 공정·업무 상태 조회')+arrow('M1210 1316 V1360')
# Two perimeter routes have distinct arrowheads; data vs control direction.
svg+=arrow('M1430 1100 H1490 V65 H650 V85','Modbus 정지 명령',1170,51,True)
svg+=arrow('M230 140 H5 V1475 H965 V1120 H990','HTTP 상태 → 백엔드 → 조치 확인',625,1464)
svg+='<text class="bs" x="35" y="1284">초록: 데이터·알람·근거·상태 전달 / 주황: 승인·제어 명령</text><text class="bs" x="35" y="1442">상자는 역할별 묶음입니다. Kafka 원본/결과는 같은 Kafka의 서로 다른 토픽입니다.</text></svg></div>'
equipment=sections['equipment']
sensor=re.sub(r'^<section[^>]*><span.*?</span><h2>(.*?)</h2>',r'<h3>\1</h3>',sections['sensor'])[:-10]
equipment=equipment[:-10]+sensor+'</section>'
equipment=re.sub(r'<span class="num">.*?</span>','<span class="num">1 · 설비부터 이해합니다</span>',equipment,count=1)
arch='<section id="architecture"><span class="num">2 · 전체 아키텍처 한 장</span><h2>설비에서 나온 정보가 어디로 가고, 명령은 어떻게 돌아오나요?</h2><p>왼쪽은 설비 데이터의 수집·분석·저장, 오른쪽은 운전원 화면과 Pilot 업무입니다. 아래 L1~L8은 역할을 구분한 레이어이며, 서로 다른 컴퓨터가 반드시 여덟 대 필요하다는 뜻은 아닙니다.</p>'+svg+'<p class="caption">화살표는 읽어 온 데이터나 명령의 전달 방향입니다. 조회 요청·응답을 모두 그린 네트워크 패킷 그림은 아닙니다. FUXA는 설비와 직접 연결되는 병렬 화면이어서 위쪽에 배치했습니다. 원본 저장은 Flink와 별도로 분기하며, 두 Flink 작업은 원본을 각각 읽습니다.</p></section>'
ids=['scada','communication','collect','kafka','flink','storage','support']
explanation='<section id="explanation"><span class="num">3 · 그림의 기술과 연결 설명</span><h2>각 상자가 맡은 일과 연결 이유</h2><p>먼저 SCADA와 화면의 관계를 구분한 뒤, 설비에서 데이터를 읽는 지점부터 그림 순서대로 살펴봅니다.</p></section>'
for i,key in enumerate(ids,1):
 part=sections[key]
 part=re.sub(r'<span class="num">.*?</span>',f'<span class="num">3-{i} · 아키텍처 설명</span>',part,count=1)
 explanation+=part
explanation+='<section><h2>마지막 연결: 조사한 결과가 설비 조치로 돌아옵니다</h2><p>Flink가 만든 알람은 Kafka에 기록됩니다. 한쪽은 Telegraf와 EMQX를 거쳐 FUXA에 표시되고, 다른 쪽은 Pilot이 읽어 조사할 사건으로 등록합니다. 현재는 사람이 분석을 시작하면 Agent가 실제 알람, 센서 기록, 연결된 문서를 조회합니다.</p><p>Pilot은 이 조사·검토·실행을 묶은 업무 서비스입니다. 담당자가 정지 제안을 승인하면 내부 실행 기능이 조건을 다시 검사한 뒤 Modbus로 가상 교반기에 정지 명령을 보냅니다. 이후 HTTP로 새 설비 상태를 읽어 정지 여부를 확인하고 PostgreSQL에 결과를 남깁니다. 반려하면 명령을 보내지 않습니다. 점검 요청 제안을 승인한 경우에는 업무만 기록합니다.</p><p>Vue 대시보드는 이 처리 과정과 근거·결과를 백엔드 API로 받아 보여줍니다. FUXA를 대신 클릭하는 방식도, 브라우저가 직접 Modbus로 명령하는 방식도 아닙니다. FUXA 직접 조작과 Pilot 승인 조치는 서로 다른 경로이며, 최종적으로 같은 가상 설비에 연결됩니다.</p></section>'
head=s.split('<body>')[0]
head=head.replace('.arch svg{display:block;width:100%;min-width:900px;height:auto}', '.arch svg{display:block;width:100%;min-width:1200px;height:auto}')
head=head.replace('max-width:1100px','max-width:1500px')
html=head+'<body><main><header><small>IoT SCADA · 설비와 시스템 이해</small><h1>설비를 이해하고,<br>전체 그림을 본 뒤, 기술을 읽습니다.</h1><p class="intro">① 반응기·교반기 등 설비 → ② 전체 아키텍처 한 장 → ③ 각 기술과 연결 설명</p></header><nav aria-label="설명 목차"><a href="#equipment">1. 설비 설명</a><a href="#architecture">2. 전체 아키텍처</a><a href="#explanation">3. 기술·연결 설명</a></nav>'+equipment+arch+explanation+'</main></body></html>'
p.write_text(html,encoding='utf8');(root/'ai-web/public/system-guide.html').write_text(html,encoding='utf8')
print('Ordered guide: equipment / one architecture / stack explanations')
