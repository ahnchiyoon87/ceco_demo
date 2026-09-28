"""Reuse the supplied layered PDF's exact drawing functions and first-page layout."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
original = (ROOT/'시스템이해/build_reference_layered_report.py').read_text(encoding='utf-8')
source = original.split("start('2. 스택 — 어느 층에서 무엇을 하는가'")[0]
source = source.replace("ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'lecture-iiot-scada'", "ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'lecture-iiot-scada'")
source = source.replace("OUT=BASE/'시스템구성도_풀스택_보강본.pdf'", "OUT=BASE/'프로토타입_아키텍처_보고용.pdf'")
source = source.replace("QA=ROOT/'시스템이해/_검토/reference_rebuild'", "QA=BASE/'화면캡처/프로토타입_아키텍처_보고용'")
source = source.replace("for f in [OUT,OLD]:\n    if f.exists():copy2(f,QA/(datetime.now().strftime('%H%M%S_')+f.name))", "")
changes={
'AR-100 SCADA · Pilot — 아키텍처 · 스택 · 흐름':'IoT-SCADA · Pilot — 프로토타입 아키텍처',
'교반기 이상 대응 폐루프 · 9개 층 · 기존 SCADA와 업무 코드를 기반으로 한 Pilot 연결 설계':'기존 프로토타입 기반 강의 · 이상 감지부터 승인·조치·결과 확인까지',
"(L,'현재 코드',TEAL),(L+144,'Pilot 설계',PURPLE),(L+292,'확장 검토',ORANGE)":"(L,'현재 구현',TEAL),(L+144,'전달 방식',PURPLE),(L+292,'실습 운영',ORANGE)",
'확인한 구현 연결':'가상 설비 시연 확인',
'연결·종단 검증 필요':'3안 중 최종 선택',
'기능별 도입 판단':'70명 운영 방식',
'L1–L6는 IoT-SCADA, L7–L9는 별도 Pilot 업무 영역입니다. 기존 ai-layer의 코드를 재사용하며 설계·확장 요소는 별도로 표시했습니다.':'Pilot은 이상 사건의 AI 조사·담당자 승인·조치·결과 확인을 이어주는 업무 서비스입니다. L1–L6는 IoT-SCADA, L7–L9는 Pilot의 내부 기능입니다.',
'1. 아키텍처 — 9개 층이 한 바퀴 돈다':'1. 프로토타입 — 감지에서 승인·조치까지',
'설비 값이 올라와 → 수집·전달되고 → 이력과 알람이 만들어지면 → Pilot이 사건을 받고 근거를 조사해 → 조치를 제안합니다. 사람이 승인하면 → 조치 서비스가 설비에 명령하고 → 새 상태를 다시 읽어 결과를 확인합니다.':'Kafka로 전달된 센서값을 Flink가 분석합니다. 알람을 사건으로 접수하고 → Agent가 조사·제안합니다. 담당자가 승인하면 → Pilot이 설비에 조치하고 → 결과를 확인합니다. 현재 AI 분석 시작은 버튼으로 수행합니다.',
'L9 프로세스 · 승인 · 실행 · 앱':'L9 Pilot 내부 · 검토 · 승인 · 조치',
'Pilot 설계 / 기존 업무 API 재사용':'별도 action 서비스 아님 / 승인 후 내부 실행',
'기존 분석 + 자동 기동 연결 설계':'현재 분석 버튼 / 알람 후 자동 시작은 보강',
'상태·이력·문서 / 확장 분석 별도':'실제 관측·관계·연결 문서를 근거로 조회',
'AR-100 / 실제 PLC는 연결 가정':'가상 설비 시연 확인 / 실물 PLC 미검증',
"'Pilot 프로세스','사건·제안·검토'":"'Pilot 업무','사건·제안·검토'",
"'action 서비스','재검사 · Modbus 실행'":"'승인 후 조치','현재 조건 확인 · 명령'",
"'LiteLLM · 모델 중계','코딩 에이전트: 구축·수정 보조'":"'설정된 LLM','조회 근거로 대응안 생성'",
"'API/MCP 연결 / 부족하면 보류'":"'실제 조회 도구 / 부족하면 보류'",
"'Skill','순서·중단 규칙'":"'판단 지침','조건·중단 규칙'",
"'Data 조회 / Fabric','현재 원천 조회 / Fabric은 확장'":"'관측 데이터 조회','InfluxDB 이력 / 현재 상태 API'",
'Ontology Studio 통합 검토':'현재 연결된 설비·문서 조회',
"'RCA / 예측','확장 검토'":"'원인 후보','확정과 구분'",
"'Modbus 명령',4.1,ORANGE":"'현재: Modbus',4.1,ORANGE",
'조치 후 새 상태·센서값이 다시 올라온다 — 폐루프':'현재 검증: Modbus 정지 → HTTP 상태 확인 / 강의용 최종 전달 방식은 2쪽에서 선택',
}
for old,new in changes.items():
 if old not in source:
  if old=="'API/MCP 연결 / 부족하면 보류'":
   source=source.replace('API/MCP 연결 / 부족하면 보류','실제 조회 도구 / 부족하면 보류');continue
  raise ValueError('Missing source: '+old)
 source=source.replace(old,new)
exec(compile(source,str(ROOT/'시스템이해/build_reference_layered_report.py'),'exec'),globals())

start('2. 회의에서 확정할 두 가지','프로토타입은 존재합니다. 검증된 현재 경로를 기준으로 강의용 연결 방식과 실습 운영 방식을 결정합니다.')
say(120,'<b>현재 확인:</b> 가상 설비 이상 → 사건 접수 → Agent 도구 조회 → 검토 카드 → 승인 → Modbus 정지 → 새 상태 확인까지 실제 시연하고 캡처했습니다.',65)
heading(211,'① 승인 후 설비에 조치를 전달하는 방식')
table(247,['선택안','의미와 확인할 점','현재 상태'],[
 ['Pilot → Modbus → 설비','Pilot 내부에서 직접 명령합니다. FUXA 직접 조작과 충돌하지 않도록 권한·현재 상태를 확인합니다.','현재 프로토타입<br/><b>가상 설비 시연 확인</b>'],
 ['Pilot → FUXA → 설비','FUXA를 통해 명령합니다. 외부 제어 API·태그 쓰기·실행 권한·결과 응답을 확인해야 합니다.','대안<br/>연동 검증 필요'],
 ['Pilot → Kafka → 실행 코드 → 설비','명령을 Kafka로 전달하면 실행 코드가 설비에 씁니다. 중복·지연·만료·결과 회신을 처리해야 합니다.','대안<br/>명령 소비·실행 구현 필요'],
 ],[132,238,CW-370],8.4)
para(L,485,CW,'세 방식 모두 <b>담당자는 Pilot 화면에서 승인</b>합니다. 바뀌는 것은 승인 뒤 명령을 전달하는 경로입니다. 조치는 Pilot의 기능이며 별도 action 서비스를 반드시 배포한다는 뜻이 아닙니다.',9.1)
heading(554,'② 70명 규모의 실습 운영 방식')
para(L,591,CW,'70명 규모를 개인별·조별·공유 서버 중 어떤 방식으로 운영할지 확정해야 합니다. <b>현재 프로토타입의 동작 확인과 70명 동시 운영 검증은 별개입니다.</b>',9.3)
para(L,650,CW,'검증할 항목: 개인별·조별 실행 또는 공유 서버 구성, 학생별 데이터·설비 분리, 동시 Agent 요청 수, 모델 호출 한도, 응답 시간과 오류율입니다. 정한 운영 조건으로 부하 시험 후 판단합니다.',9.1)
say(719,'<b>현재 남은 보강:</b> 알람 접수 후 Agent 자동 시작 연결·검증. 실물 설비 적용, 고장 원인 확정, 수리 완료는 이번 가상 설비 시연 범위에 포함되지 않습니다.',58)
done();C.save()
d=pymupdf.open(OUT)
for i,page in enumerate(d):page.get_pixmap(matrix=pymupdf.Matrix(2.5,2.5)).save(QA/f'{i+1:02d}.png')
print(OUT)
