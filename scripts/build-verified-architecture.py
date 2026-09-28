"""Render the reviewed CECO runtime architecture, without changing the reference PDF."""
from pathlib import Path
import math
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '시스템구성도_실제통신구조_확인본.pdf'
pdfmetrics.registerFont(TTFont('KR', 'C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('KRB', 'C:/Windows/Fonts/malgunbd.ttf'))
W,H=1200,850
c=canvas.Canvas(str(OUT),pagesize=(W,H))
c.setTitle('IoT-SCADA · AI 업무도우미 | 실제 통신 구조 확인본')
INK='#193348'; MUTED='#587084'; BLUE='#2679B5'; GREEN='#158779'; ORANGE='#C46C21'; PURPLE='#7059AA'
def text(x,y,s,size=13,color=INK,bold=False):
 c.setFillColor(color);c.setFont('KRB' if bold else 'KR',size);c.drawString(x,H-y-size,s)
def rect(x,y,w,h,fill,stroke=None):
 c.setFillColor(fill);c.setStrokeColor(stroke or fill);c.roundRect(x,H-y-h,w,h,10,fill=1,stroke=bool(stroke))
def box(x,y,w,h,title,lines=(),color=BLUE):
 rect(x,y,w,h,'#FFFFFF','#CFDDE5');rect(x,y,5,h,color)
 text(x+17,y+13,title,17,color,True)
 for j,s in enumerate(lines): text(x+17,y+42+j*21,s,12.5)
def arrow(points,label='',color=BLUE,dash=False,labelxy=None):
 c.setStrokeColor(color);c.setLineWidth(1.8);c.setDash(5,4) if dash else c.setDash()
 p=c.beginPath();p.moveTo(points[0][0],H-points[0][1])
 for x,y in points[1:]:p.lineTo(x,H-y)
 c.drawPath(p);c.setDash()
 (x0,y0),(x,y)=points[-2:];a=math.atan2(y-y0,x-x0)
 p=c.beginPath();p.moveTo(x,H-y)
 for b in (a+2.65,a-2.65):p.lineTo(x+8*math.cos(b),H-(y+8*math.sin(b)))
 p.close();c.setFillColor(color);c.drawPath(p,fill=1,stroke=0)
 if label:
  lx,ly=labelxy or ((points[0][0]+x)/2,(points[0][1]+y)/2-19)
  width=pdfmetrics.stringWidth(label,'KR',11)
  rect(lx-3,ly-1,width+6,17,'#F5F8FB');text(lx,ly,label,11,color)
def header(n,title,sub):
 rect(0,0,W,H,'#F5F8FB');text(40,26,'AR-100  /  IoT-SCADA + AI 업무도우미',12,GREEN,True)
 text(40,56,title,28,INK,True);text(40,101,sub,14,MUTED)
 text(40,817,'2026-09-23 확인 · 현재 CECO 구현 기준 · 대상은 교육용 가상 설비',11,MUTED)
 text(1110,817,f'{n} / 4',11,MUTED)
def band(y,title,color=GREEN):text(44,y,title,15,color,True)

header(1,'전체 구조 | 수집·분석·업무·제어가 연결됩니다','기술 목록이 아니라, 어느 프로그램이 어떤 데이터를 주고받는지 나타낸 현재 구현의 연결도입니다.')
band(148,'01  현장 수집과 이상 감지')
xs=[40,235,430,625,820,1015]
titles=['가상 설비','EdgeX','EMQX','Telegraf bridge','Kafka 원본','Flink']
lines=[['센서 12개 · 교반기','Modbus 서버 :502'],['설비값을 읽고','공통 이벤트 생성'],['MQTT 메시지 전달','구독자에게 배달'],['이벤트 형식 정리','Kafka에 기록'],['sensor.telemetry',' .raw'],['규칙 · CEP · ML','이상 여부 분석']]
for x,t,l in zip(xs,titles,lines):box(x,185,170,108,t,l)
for i,label in enumerate(['Modbus 읽기','MQTT','MQTT','Kafka','Kafka 읽기']):arrow([(xs[i]+170,239),(xs[i+1],239)],label,labelxy=(xs[i]+135,161))
band(320,'02  결과 전달과 저장 · 화면으로 분기')
box(1015,353,170,107,'Kafka 결과',['clean / score','sensor.alerts'])
arrow([(1100,293),(1100,353)],'분석 결과',labelxy=(1109,312))
box(735,353,225,107,'Telegraf sink',['원본·정제값·점수·알람','InfluxDB에 저장'])
box(475,353,205,107,'InfluxDB',['시간별 센서·알람 이력'])
box(235,353,185,107,'Grafana',['저장된 추세·이력 조회'])
arrow([(1015,387),(960,387)],'Kafka',labelxy=(970,365));arrow([(735,400),(680,400)])
arrow([(475,400),(420,400)],'조회 결과',labelxy=(422,376))
text(45,373,'원본 Kafka도',12,MUTED);text(45,396,'sink가 함께 읽음',12,MUTED)
box(735,493,225,94,'알람 중계 → EMQX',['Telegraf가 알람을 MQTT로'],color=GREEN)
box(475,493,205,94,'FUXA',['최근 분석 알람 표시'],color=GREEN)
arrow([(1075,460),(1075,540),(960,540)],'alerts',labelxy=(1002,516));arrow([(735,540),(680,540)],'MQTT',labelxy=(685,515))
band(611,'03  사건 접수 → AI 조사 → 사람 승인 → 허용된 조치')
for x,w,t,l in [(40,200,'alarm-worker',['Kafka 알람 수신','사건 자동 등록']), (275,195,'PostgreSQL',['사건·분석·승인·결과','업무 기록 보관']), (505,225,'Agent + 근거 조회',['Neo4j 문서·InfluxDB','상태 API 조회 → 대응안']), (765,180,'AI 업무 화면',['사람이 분석 시작','대응안 승인 / 반려']), (980,205,'조치 실행 코드',['조건 재검사 → Modbus','가상 교반기 정지'])]:box(x,650,w,108,t,l,color=PURPLE)
arrow([(1100,460),(1178,460),(1178,636),(140,636),(140,650)],'sensor.alerts → 사건 접수',labelxy=(680,613))
for a,b in [(240,275),(470,505),(730,765),(945,980)]:arrow([(a,704),(b,704)],color=PURPLE)
text(42,779,'별도 직접 경로: FUXA ↔ 설비(Modbus)  |  조치 실행 → 설비(Modbus)  |  실행 결과 확인 ← 설비(HTTP /state)',13,ORANGE,True)
c.showPage()

header(2,'직접 통신 | Modbus는 누가 누구에게 쓰나요?','FUXA·EdgeX·AI 조치 코드가 모두 같은 가상 설비에 접속합니다. 브라우저가 직접 Modbus를 쓰지는 않습니다.')
box(50,166,280,117,'FUXA 서버',['운전 화면의 현재값을 읽음','기동·정지·설정값을 씀'],GREEN)
box(50,330,280,117,'EdgeX device-modbus',['센서값을 1초마다 수집','수집 결과를 분석 경로로 전달'],BLUE)
box(50,494,280,117,'AI backend의 조치 코드',['사람이 승인한 stop_mixer만 실행','실행 전에 현재 조건 재검사'],ORANGE)
box(770,200,360,395,'AR-100 가상 설비',['plant-simulator:502 · Unit ID 1','','센서 숫자 → Input Register','기동·정지 → Coil','설정값 → Holding Register','','M-101 교반기: coil 주소 1','False 쓰기 → 교반기 정지','','실제 PLC·실물 설비 연결은 미검증'],GREEN)
arrow([(330,220),(770,220)],'Modbus TCP · 읽기 + 쓰기',GREEN,labelxy=(423,193))
arrow([(770,256),(330,256)],'현재 숫자·명령 상태 응답',GREEN,labelxy=(431,258))
arrow([(330,384),(770,384)],'Modbus TCP · 센서 읽기 요청',BLUE,labelxy=(409,356))
arrow([(330,548),(770,548)],'Modbus TCP · write_coil(1, False)',ORANGE,labelxy=(395,520))
box(50,655,280,107,'AI 결과 확인',['새 seq + agitator_run=False','확인 시 stop_verified 기록'],PURPLE)
box(770,655,360,107,'시뮬레이터 상태 API',['HTTP :8080 /state','호스트 접속: 127.0.0.1:27080','Vue 현재값도 backend를 통해 이 API 조회'],PURPLE)
arrow([(330,687),(770,687)],'HTTP GET /state · 현재 구현의 되읽기',PURPLE,labelxy=(401,661))
arrow([(770,735),(330,735)],'JSON 상태 응답 · Modbus 되읽기와 구분',PURPLE,labelxy=(390,739))
text(50,792,'Docker 내부 :502 ↔ 호스트 :27002  |  AI 컨테이너는 host.docker.internal:27002로 접속',12,MUTED)
c.showPage()

header(3,'한 사건의 처리 | 무엇을 보고, 승인하고, 확인하나요?','자동 접수와 사람이 시작하는 AI 분석을 구분했습니다. 원인 후보·조치 제안·실행 결과는 서로 다른 정보입니다.')
steps=[('1','이상 감지 · 사건 등록','Flink → Kafka sensor.alerts → alarm-worker → PostgreSQL','자동',BLUE),('2','AI 분석 시작','운영 워크스페이스에서 사람이 「대응안 작성」 클릭','현재 수동',ORANGE),('3','Agent 도구 실행 · 근거 확인','원본 알람 / 설비 관계·문서 / 사건 당시와 현재 센서값 조회','과정 표시',PURPLE),('4','대응안 카드 · 사람 검토','관찰 내용·가능한 해석·권고 조치·인용 문서·불확실성 확인','승인 / 반려',PURPLE),('5','승인된 조치 실행','현재 상태·기한·사건 버전·근거 재검사 → 허용되면 명령 전송','조건부 실행',ORANGE),('6','새 상태 확인 · 기록','정지 확인 결과와 검토 의견·처리 이력 저장 → 점검 대기','결과 표시',GREEN)]
for i,(num,t,detail,badge,col) in enumerate(steps):
 y=157+i*99;box(50,y,750,80,num+'   '+t,[detail],col);text(674,y+15,badge,12,col,True)
 if i<5:arrow([(425,y+80),(425,y+99)],color=col)
box(842,157,308,145,'Agent + 설정된 LLM',['PostgreSQL: 원본 알람·사건','Neo4j: 설비·센서 관계, 연결 문서','InfluxDB: 센서 이력','HTTP /state: 현재 설비 상태','조회 근거 → 모델 판단 → 구조화 대응안'],PURPLE)
box(842,326,308,144,'대응안에 따른 갈림길',['근거 부족 → 추가 확인 안내','반려 → 설비 명령 없음','inspect_only → 점검 요청 기록','stop_mixer 승인 → Modbus 정지'],ORANGE)
box(842,495,308,133,'결과가 의미하는 것',['「정지 확인」은 가상 설비 상태 확인','고장 원인 확정·수리 완료는 아님','매뉴얼은 연결된 문서만 조회','최종 상태: 점검 대기'],GREEN)
rect(842,655,308,111,'#FFF0DF');text(861,669,'강의용 자동화 추가 항목',16,ORANGE,True)
for j,s in enumerate(['사건 접수 → Agent 자동 시작','현재 구현은 버튼으로 시작함','Process-GPT 연결은 별도 구현']):text(861,700+j*20,s,12)
text(50,780,'화면 위치: http://127.0.0.1:28180 → 운영 워크스페이스 → 사건 선택 → 대응안 검토 / 처리 이력',13,MUTED)
c.showPage()

header(4,'확인 근거 | 구현·실행 확인과 남은 범위','2026-09-23 현재 설정·소스·실행 상태를 대조했습니다. 이번 구조 확인 중 설비 정지 명령은 보내지 않았습니다.')
rows=[('FUXA ↔ 가상 설비','실행 설정 확인','/api/project: ModbusTCP / plant-simulator:502 / slaveid 1'),('EdgeX → 가상 설비','설정 + 실행 확인','ar100.devices.yaml: Modbus / 1000ms · device-modbus 컨테이너 실행'),('현재 수집 경로','실행 설정 확인','DIRECT_MQTT_ENABLE=false · EdgeX + telegraf-bridge 실행'),('AI 컨테이너 → Modbus','실제 읽기 성공','host.docker.internal:27002 연결 True · coil 1 읽기 [True]'),('승인 → 정지 → 상태 확인','구현 + 과거 실행 기록','actions.py: write_coil → HTTP /state → stop_verified'),('사건 접수 → AI 자동 시작','현재 미연결','consumer.py는 사건을 저장 · 분석은 별도 POST /analyze'),('전체 순차 화면 시연','별도 후속 작업','이번에는 통신 구조 확인을 우선 수행 · 순차 캡처 완주와 구분'),('실물 공장 · PLC 제어','미검증','현재 대상은 교육용 AR-100 시뮬레이터')]
for i,(a,b,d) in enumerate(rows):
 y=156+i*62;rect(40,y,1120,55,'#FFFFFF' if i%2==0 else '#EAF1F6')
 text(55,y+16,a,13,INK,True);text(339,y+16,b,12,GREEN if '미' not in b and '후속' not in b else ORANGE);text(513,y+16,d,11.5)
text(45,678,'현재 구성도에서 의도적으로 분리한 항목',16,INK,True)
text(45,714,'• FUXA 직접 제어 / EdgeX 수집 / AI 승인 후 제어는 서로 다른 경로입니다.',13)
text(45,739,'• AI 업무 화면은 Vue + backend입니다. Process-GPT가 현재 실행 엔진이라는 뜻이 아닙니다.',13)
text(45,764,'• Grafana는 이력 조회 화면입니다. AI 사건을 시작하는 입력은 Kafka 알람입니다.',13)
c.save()
doc=pymupdf.open(OUT)
preview=ROOT/'화면캡처'/'시스템아키텍처_확인본';preview.mkdir(parents=True,exist_ok=True)
for i,p in enumerate(doc):p.get_pixmap(matrix=pymupdf.Matrix(1.3,1.3)).save(preview/f'{i+1:02d}.png')
print(OUT)
