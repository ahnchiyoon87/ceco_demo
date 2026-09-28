from pathlib import Path
import re
from html import escape
root=Path(__file__).resolve().parents[1]
p=root/'docs/소스코드로_확인한_아주쉬운_시스템설명.html'
s=p.read_text(encoding='utf8')
colors=['#b65300','#c20b69','#a70ade','#2357df','#087fa5','#7636ea','#078476','#52647b','#35445a']
titles=[('프로세스·승인·실행','사람 검토와 승인 후 조치'),('AI 에이전트','알람 접수·근거 조사·제안'),('지식·관계·문서','설비와 적용 문서 연결'),('관제·SCADA·운영 감시','현재 상태·이력·시스템 상태'),('시계열·업무 저장','센서 이력과 업무 기록 구분'),('스트림 처리·이상 검사','같은 원본을 각각 읽어 분석'),('이벤트 백본','원본·분석 결과·알람 전달'),('IoT 미들웨어·MQTT','설비 수집과 메시지 중계'),('설비·센서·제어','교육용 가상 반응기 라인')]
svg='''<div class="arch" tabindex="0" role="region" aria-label="L9부터 L1까지 전체 시스템 아키텍처"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -15 1420 1745" role="img" aria-label="9개 가로 레이어 안에 배치한 현재 SCADA와 Pilot 구성"><defs>'''
for name,c in [('data','#2563eb'),('ai','#ae14cf'),('cmd','#c45208')]:
 svg+=f'<marker id="{name}" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8Z" fill="{c}"/></marker>'
svg+='</defs><style>.at{font:700 18px Malgun Gothic,sans-serif;fill:#183754}.as{font:14px Malgun Gothic,sans-serif;fill:#4b6278}.al{font:700 19px Malgun Gothic,sans-serif;fill:#1e3850}.ae{font:13px Malgun Gothic,sans-serif;paint-order:stroke;stroke:white;stroke-width:3px;stroke-linejoin:round}</style>'
for i,(title,desc) in enumerate(titles):
 y=20+i*185;c=colors[i]
 svg+=f'<rect x="20" y="{y}" width="1330" height="165" rx="13" fill="{c}" fill-opacity=".045" stroke="{c}" stroke-width="1.5"/><rect x="38" y="{y+18}" width="45" height="26" rx="5" fill="{c}"/><text x="60" y="{y+37}" text-anchor="middle" fill="white" font-size="15" font-family="sans-serif" font-weight="bold">L{9-i}</text><text class="al" x="38" y="{y+73}">{title}</text><text class="as" x="38" y="{y+111}">• {desc}</text>'
def box(layer,col,title,lines,accent=False):
 global svg
 x=310+col*255;y=20+(9-layer)*185+25;w=230
 svg+=f'<rect x="{x}" y="{y}" width="{w}" height="115" rx="9" fill="white" stroke="{colors[9-layer] if accent else "#c2cede"}" stroke-width="1.4"/><text class="at" x="{x+w/2}" y="{y+29}" text-anchor="middle">{escape(title)}</text>'
 for j,t in enumerate(lines):svg+=f'<text class="as" x="{x+w/2}" y="{y+54+j*20}" text-anchor="middle">{escape(t)}</text>'
def path(d,label='',x=0,y=0,kind='data'):
 global svg
 color={'data':'#2563eb','ai':'#ae14cf','cmd':'#c45208'}[kind]
 svg+=f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2.5" marker-end="url(#{kind})"/>'
 if label:svg+=f'<text class="ae" x="{x}" y="{y}" text-anchor="middle" fill="{color}">{escape(label)}</text>'
box(9,0,'담당자 검토',['근거·조치안 확인','승인 / 반려'],True)
box(9,1,'Vue 통합 대시보드',['직접 조작·설정값·관제','Agent 진행·검토·결과'])
box(9,2,'LangGraph 업무 흐름',['조사 → 검토 대기 → 실행','저장된 상태로 재개'],True)
box(9,3,'Pilot 내부 제어 기능',['운전원 직접 조작 / 승인 조치','Modbus 명령 → 새 상태 확인'],True)
box(8,0,'알람 접수 워커',['Kafka alerts 소비','사건 등록·중복 관측 결합'])
box(8,1,'조회 도구',['알람 / 센서 관측 / 문서','실제 호출 기록 저장'])
box(8,2,'업무 Agent',['사람이 분석 시작','근거·불확실성·대응안'],True)
box(8,3,'LiteLLM → 모델',['GCP 모델 호출 중계','coding → gpt-6-luna'])
box(7,0,'원본 문서·절차',['설비 맥락·대응·근거 정책','버전·출처를 함께 확인'])
box(7,1,'Neo4j 지식그래프',['설비 ↔ 센서 ↔ 문서','소속·적용 관계 조회'],True)
box(7,2,'근거 조회 기능',['그래프 / 시계열 / 현재 상태','원인 확정과 관측 사실 구분'])
box(7,3,'지식 후보·검토',['원본 등록 → 관계 후보','출처 검토 후 그래프 게시'])
box(6,0,'FUXA 웹 SCADA',['Modbus 계측·직접 조작','MQTT 최근 알람'])
box(6,1,'Grafana',['InfluxDB 공정 이력','Prometheus 운영 지표'],True)
box(6,2,'Prometheus',['EMQX·Kafka·Flink 등','시스템 운영 지표 수집'])
box(6,3,'Alertmanager',['운영 경보 그룹·억제','설비 정지 명령 경로 아님'])
box(5,0,'Telegraf 저장용',['Kafka 원본·결과를 읽어','InfluxDB에 기록'])
box(5,1,'InfluxDB',['시간별 센서값·분석 결과','공정 히스토리안'],True)
box(5,2,'PostgreSQL',['사건·분석·승인·조치','업무 상태·실행 이력'])
box(5,3,'저장 영역 구분',['센서 이력: InfluxDB','업무 기록: PostgreSQL'])
box(4,0,'입력: Kafka 원본',['규칙·모델이 각각 읽음','직렬 검사 순서가 아님'])
box(4,1,'Flink 규칙 작업',['상·하한 / Z-Score','CEP 시간·순서 패턴'])
box(4,2,'Flink ONNX 작업',['전처리 후 Autoencoder','이상 점수·알람 계산'])
box(4,3,'출력: Kafka 결과',['clean / score / alerts','알람 ≠ 원인 확정·정지'])
box(3,0,'Telegraf 수집용',['EdgeX MQTT 이벤트 수신','태그·시각·값 형식 정리'])
box(3,1,'Kafka · raw',['원본 센서 이벤트','분석·저장 프로그램이 소비'],True)
box(3,2,'Kafka · alerts',['Flink가 만든 이상 알람','화면 중계·업무 접수'],True)
box(3,3,'Kafka · clean / score',['정리된 값·이상 점수','같은 Kafka의 별도 토픽'])
box(2,0,'EMQX',['MQTT 메시지 중계','계측 이벤트 / 표시 알람'])
box(2,1,'EdgeX Foundry',['Modbus 장치 수집','이벤트 처리 → MQTT 출력'])
box(2,2,'Telegraf 알람 중계',['Kafka alerts 수신','MQTT로 FUXA에 전달'])
box(2,3,'MQTT 토픽',['edgex/telemetry','scada/hmi/latest-alert'])
box(1,0,'가상 설비 · 시뮬레이터',['원료탱크·펌프·반응기','교반기·히터·냉각기·밸브'])
box(1,1,'센서·Modbus 주소',['12개 계측 태그','코일·설정 레지스터'])
box(1,2,'설비 상태 API',['HTTP /state','새 seq·운전 상태 확인'])
box(1,3,'설비 내부 동작',['명령 반영·물리모델 계산','고압 인터록·이상 주입'])
# Inter-layer paths use the inter-card corridors, with arrows ending at boxes.
path('M680 1525 V1450','Modbus 계측',745,1495)
path('M565 1382 H540','MQTT 발행',552,1368)
path('M425 1340 V1265','MQTT 수신',477,1300)
path('M540 1207 H565','원본',553,1192)
path('M680 1155 V1080','원본 읽기',728,1120)
path('M705 1155 V1124 H935 V1080','원본 읽기',855,1114)
path('M755 1080 V1135 H855 V1155','알람',815,1128)
path('M965 1080 V1155','알람',997,1120)
path('M1020 1080 V1128 H1190 V1155','정리값·점수',1130,1118)
path('M565 1225 H552 V1280 H292 V860 H310','원본·결과 이력 저장',409,1139)
path('M540 838 H565')
path('M680 785 V710','이력 조회',736,750)
path('M820 653 H795','운영 지표',808,638)
path('M1050 653 H1075')
# Alerts go to intake and MQTT bridge via distinct corridors.
path('M855 1265 V1307 H935 V1340','알람 중계',947,1298)
path('M935 1455 V1473 H425 V1455','MQTT 재발행',668,1470)
path('M310 1405 H265 V652 H310','MQTT 최근 알람',366,733)
path('M820 1238 H807 V1290 H278 V282 H310','alerts → 사건',392,387)
# AI lookup and workflow paths.
path('M795 125 H808 V217 H935 V230','사람이 분석 시작',748,211,'ai')
path('M820 282 H795','도구 요청',807,269,'ai')
path('M1050 282 H1075','모델 호출',1063,269,'ai')
path('M680 415 V345','관계·문서 근거',751,390,'ai')
path('M540 468 H565','문서 연결',552,451,'ai')
path('M1075 494 H1063 V557 H680 V530','검토 후 게시',878,550,'ai')
path('M935 230 V160','제안·검토 대기',1008,195,'ai')
path('M425 45 V29 H935 V45','담당자 승인',684,26,'cmd')
path('M680 45 V10 H1190 V45','운전원 직접 조작 API',1020,9,'cmd')
path('M1050 100 H1075','실행',1063,84,'cmd')
path('M850 160 V180 H680 V160','진행·결과 표시',766,177,'ai')
# Equipment paths stay outside all layer boxes; their endpoints stay within L1/L6/L9.
path('M310 1553 H242 V636 H310','Modbus 현재값',365,1509)
path('M310 676 H228 V1590 H310','Modbus 운전원 명령',363,1664,'cmd')
path('M1305 101 H1372 V1583 H1305','Modbus 운전 명령',1210,1700,'cmd')
path('M1050 1564 H1384 V126 H1305','HTTP 새 상태 확인',1202,1680)
path('M1305 1228 H1332 V920 H425 V900','결과 이력 저장',1170,916)
path('M850 160 V190 H1340 V760 H1063 V848 H1050','업무 기록 저장·조회',1193,747,'ai')
svg+='<text class="as" x="25" y="1714">파랑: 데이터·알람·조회 결과　보라: AI 조사·지식 연결　주황: 승인·설비 명령　|　교차점은 연결을 의미하지 않습니다.</text></svg></div>'
s=re.sub(r'<div class="arch".*?</svg></div>',svg,s,count=1,flags=re.S)
s=s.replace('왼쪽은 설비 데이터의 수집·분석·저장, 오른쪽은 운전원 화면과 Pilot 업무입니다. 아래 L1~L8은 역할을 구분한 레이어이며, 서로 다른 컴퓨터가 반드시 여덟 대 필요하다는 뜻은 아닙니다.','아래 L1 설비에서 위쪽 L9 업무·승인까지 역할별로 나눴습니다. 모든 구성은 해당 레이어 안에 배치했습니다. 레이어는 역할 구분이며 서버 대수를 뜻하지 않습니다.')
s=re.sub(r'<p class="caption">화살표는 읽어 온 데이터.*?</p>','<p class="caption">화살표는 데이터·알람·조회 결과 또는 명령의 방향입니다. Kafka의 raw·alerts·clean·score는 같은 Kafka 안의 별도 토픽입니다. Flink 규칙과 모델은 raw를 각각 읽고, 원본 저장은 분석과 별도로 분기합니다. L9 진행도는 실제 LangGraph 상태를 BPMN 형태로 표시하며 별도 BPMN 실행 엔진은 아닙니다.</p>',s,count=1,flags=re.S)
p.write_text(s,encoding='utf8');(root/'ai-web/public/system-guide.html').write_text(s,encoding='utf8')
print('9 layers; all boxes inside bands')

