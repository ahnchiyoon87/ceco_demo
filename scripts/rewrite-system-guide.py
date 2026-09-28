"""Rebuild the explanation HTML; preserve the prior document once."""
from pathlib import Path
import re
from html import escape

root=Path(__file__).resolve().parents[1]
target=root/'docs/소스코드로_확인한_아주쉬운_시스템설명.html'
old=target.read_text(encoding='utf-8')
backup=root/'docs/ai-work/uiux-20260928/system-guide-before-definitions.html'
if not backup.exists(): backup.write_text(old,encoding='utf-8')
style=re.search(r'<style>(.*?)</style>',old,re.S).group(1)
style+='\n.arch{overflow-x:auto;margin:20px 0;border:1px solid #c8dade;border-radius:12px;background:#f8fbfc}.arch svg{display:block;width:100%;min-width:900px;height:auto}.definition{font-size:20px;line-height:1.8;color:#164f58}.role{border-left:4px solid #1f8473;padding:10px 18px;background:#f0f7f5;margin:14px 0}.legend{display:flex;gap:20px;flex-wrap:wrap;font-size:14px}.legend span{padding:5px 10px;border:1px solid #d1dde3;border-radius:6px}.layer{font-size:14px;color:#486477}.arch:focus-visible{outline:3px solid #146c60} @media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}'
parts=[]
def section(id,title,body):
    parts.append(f'<section id="{id}"><span class="num">{len(parts)+1:02d} · 이해하고 연결하기</span><h2>{title}</h2>{body}</section>')
def stack(title,definition,analogy,use,connection):
    return f'<h3>{title}</h3><p class="definition">{definition}</p><p>{analogy}</p><div class="role"><b>우리 시스템에서는</b><p>{use}</p><p><strong>연결:</strong> {connection}</p></div>'
def svg_begin(height,label):
    global marker_prefix
    marker_prefix=f'm{height}-'
    return f'<div class="arch" tabindex="0" role="region" aria-label="{label}. 좁은 화면에서는 가로로 이동"><svg viewBox="0 0 1100 {height}" role="img" aria-label="{label}" xmlns="http://www.w3.org/2000/svg"><defs><marker id="{marker_prefix}data" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0 0L9 4.5L0 9Z" fill="#16796b"/></marker><marker id="{marker_prefix}command" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0 0L9 4.5L0 9Z" fill="#b44e1f"/></marker></defs><style>text{{font-family:Malgun Gothic,sans-serif;fill:#173b49}}.title{{font-size:18px;font-weight:700}}.sub{{font-size:14px}}.lane{{font-size:14px;fill:#4b6574}}.edge{{font-size:13px;fill:#165b53}}</style>'
def box(x,y,w,title,sub):
    return f'<rect x="{x}" y="{y}" width="{w}" height="70" rx="10" fill="white" stroke="#80b5ac"/><text class="title" x="{x+w/2}" y="{y+29}" text-anchor="middle">{escape(title)}</text><text class="sub" x="{x+w/2}" y="{y+53}" text-anchor="middle">{escape(sub)}</text>'
def line(d,label='',x=0,y=0,command=False):
    typ='command' if command else 'data'; color='#b44e1f' if command else '#16796b'
    return f'<path d="{d}" stroke="{color}" stroke-width="2.4" fill="none" marker-end="url(#{marker_prefix}{typ})"/>'+ (f'<text class="edge" x="{x}" y="{y}" text-anchor="middle">{escape(label)}</text>' if label else '')

section('scada','SCADA는 무엇이고, FUXA는 무엇인가요?', '''
<p class="definition"><strong>SCADA는 여러 설비의 상태를 모아 보고, 필요한 운전 명령을 보내는 감시·제어 시스템입니다.</strong> FUXA는 그중 운전원이 보고 조작하는 화면을 만들 수 있는 소프트웨어입니다.</p>
<p>건물의 중앙 관리실을 떠올려 보세요. 관리실에서는 여러 층의 온도와 물탱크 상태를 보고, 필요하면 펌프를 켭니다. 센서, 통신, 화면, 조작 기능이 함께 있어야 이 일이 됩니다. 공장의 SCADA도 이처럼 떨어져 있는 설비를 한곳에서 살펴보고 조작하게 합니다.</p>
<p>SCADA는 특정 제품 하나의 이름이 아닙니다. 감시·데이터 수집·상위 제어를 하는 시스템의 종류를 말합니다. <strong>FUXA는 그 역할을 구현하는 데 사용하는 실제 도구 이름</strong>입니다. “문서를 작성하는 프로그램”과 “워드”가 개념과 제품으로 구분되는 것처럼 생각하면 됩니다.</p>
<div class="cards"><article class="card"><h3>SCADA: 전체 역할</h3><p>어떤 설비가 움직이는지, 현재 온도·압력이 얼마인지 모아서 봅니다. 운전원이 명령이나 목표값을 바꾸고 결과를 확인합니다.</p></article><article class="card"><h3>FUXA: 운전원 화면 도구</h3><p>탱크 그림, 센서 숫자, 기동·정지 버튼을 배치하고 설비의 값과 연결합니다. 우리 화면에서 버튼이 실제 가상 설비에 연결되는 부분입니다.</p></article></div>
<p>화면과 설비 사이에는 통신이 필요하고, 지난 기록을 보려면 저장소가 필요합니다. 이상을 계속 검사하려면 분석 프로그램도 필요합니다. 그래서 우리 구성에는 FUXA뿐 아니라 EdgeX, Kafka, Flink, InfluxDB 등이 함께 있습니다. <strong>이 도구들이 모든 SCADA의 필수 구성인 것은 아니며, 우리 실습에서 수집·분석·이력 기능을 나누어 구현한 선택입니다.</strong></p>
<p>IoT는 기계나 센서 같은 사물이 통신으로 상태를 주고받도록 연결하는 개념입니다. 이 사례에서는 설비의 숫자를 프로그램들이 받아 활용하는 부분을 생각하면 됩니다. IoT와 SCADA는 역할이 겹칠 수 있으며, 하나가 다른 하나의 제품 이름인 관계는 아닙니다.</p>''')

section('equipment','반응기와 교반기는 같은 기계인가요?', '''
<p class="definition"><strong>반응기는 재료를 담고 온도·압력 등의 조건을 맞춰 공정을 진행하는 용기입니다. 교반기는 그 안의 재료를 섞는 장치입니다.</strong></p>
<p>냄비에 수프를 끓이는 모습을 떠올리세요. 냄비가 반응기에 가깝고, 안에서 돌아가는 자동 젓개가 교반기에 가깝습니다. 냄비와 젓개는 함께 사용하지만 같은 물건은 아닙니다. 실제 반응기는 단순히 담아두는 통을 넘어, 재료가 원하는 상태로 변하거나 반응하도록 조건을 관리합니다.</p>
<div class="flow"><div class="box"><b>원료탱크 TK-101</b><small>재료를 보관</small></div><span class="arrow">→</span><div class="box"><b>공급펌프 P-101</b><small>재료를 밀어 보냄</small></div><span class="arrow">→</span><div class="box"><b>반응기 R-101</b><small>교반기로 섞고 히터로 가열</small></div><span class="arrow">→</span><div class="box"><b>배출밸브 CV-101</b><small>나가는 양을 조절</small></div></div><p class="caption">이 화살표는 재료가 이동하는 방향입니다. 뒤의 아키텍처 화살표는 데이터나 명령이 전달되는 방향입니다.</p>
<div class="table-wrap"><table><tr><th>설비</th><th>무엇인가요?</th><th>무엇을 확인하나요?</th></tr>
<tr><td>원료탱크</td><td>공정에 넣기 전 재료를 보관하는 통입니다.</td><td>얼마나 차 있는지 확인합니다. 레벨 50%라면 높이 기준으로 절반 정도 찬 상태를 뜻합니다.</td></tr>
<tr><td>공급펌프</td><td>재료를 움직이도록 힘을 주는 장치입니다. 물을 밀어 올리는 펌프와 같은 역할입니다.</td><td>켜져 있는지, 얼마나 흐르는지, 모터가 전류를 얼마나 쓰는지 봅니다.</td></tr>
<tr><td>반응기</td><td>재료를 받아 섞고 데우는 공정용 통입니다.</td><td>안에 찬 높이, 온도, 압력, pH 등을 봅니다.</td></tr>
<tr><td>교반기 M-101</td><td>모터가 축과 날개를 돌려 반응기 안의 재료를 섞는 장치입니다.</td><td>운전 여부, 모터 전류, 진동을 봅니다. 전류는 모터가 쓰는 전기의 흐름이고, 진동은 얼마나 떨리는지를 나타냅니다.</td></tr>
<tr><td>재킷·히터 HX-101</td><td>재킷은 반응기 바깥을 감싼 열 전달 공간입니다. 히터가 가열을 돕습니다. 냄비 바깥에서 열을 전달하는 모습에 가깝습니다.</td><td>재킷 온도와 통 안의 온도를 따로 봅니다. 열이 전달되는 데 시간이 걸리므로 두 온도가 같지 않을 수 있습니다.</td></tr>
<tr><td>배출밸브</td><td>재료가 나가는 통로를 열거나 좁히는 장치입니다. 수도꼭지와 비슷합니다.</td><td>얼마나 열었는지와 실제로 나가는 유량을 봅니다. 개도 50%가 유량도 정확히 절반이라는 뜻은 아닙니다.</td></tr></table></div>
<p>우리 실습은 실제 공장 대신 <strong>시뮬레이터</strong>를 사용합니다. 컴퓨터 안에서 탱크의 양, 온도, 전류, 진동을 계산하는 가상 설비입니다. 버튼을 누르면 이 프로그램의 운전 상태가 바뀌고, 그 상태에 따라 다음 센서값도 달라집니다. 그림만 움직이는 화면과는 다릅니다.</p>''')

section('sensor','센서값과 설정값: 지금 상태와 원하는 상태', '''
<p class="definition">센서값은 “지금 어떤가”를 알려주는 측정 결과이고, 설정값은 “어떻게 운전할 것인가”를 지정하는 값입니다.</p><p>온도계에 65℃가 보이는 것은 현재 온도입니다. 난방 목표를 72℃로 정하는 것은 설정값입니다. 목표를 바꿨다고 현재 온도가 바로 72℃로 바뀌지는 않습니다. 가열과 열 전달에 시간이 걸립니다.</p>
<p>우리 화면의 TT-101은 반응기 온도, PT-101은 반응기 압력, IT-102는 교반기 전류, VT-101은 교반기 진동입니다. 이런 이름을 <strong>태그</strong>라고 합니다. 숫자에 붙인 이름표라서 프로그램이 “어느 설비의 무엇을 측정한 값인지” 구분할 수 있습니다.</p>
<p>예를 들어 “8.3”만 받으면 의미가 없습니다. “AR-100의 교반기 진동 VT-101, 11시 17분에 측정한 8.3 mm/s”라고 받으면 무엇이 언제 얼마나 변했는지 비교할 수 있습니다. 데이터가 전달될 때 설비 이름, 태그, 시각, 값, 품질 같은 정보가 함께 다니는 이유입니다.</p>
<div class="cards"><article class="card"><h3>기동·정지</h3><p>기동은 움직이기 시작하도록 요청하는 것입니다. 정지는 멈추도록 요청하는 것입니다. 우리 가상 교반기는 운전 명령이 1이면 운전, 0이면 정지로 처리합니다.</p></article><article class="card"><h3>설정값</h3><p>펌프 속도, 밸브 개도, 목표 온도처럼 운전 방식을 정합니다. FUXA 입력칸에 값을 넣고 Enter를 누른 뒤, 표시값이 바뀌었는지 확인합니다. 온도 ×10 입력은 720이 72.0℃라는 뜻입니다.</p></article></div><p>명령을 보낸 것과 실제 상태가 바뀐 것은 구분해야 합니다. 통신이 끊겼거나 보호 조건이 걸렸을 수 있으므로 새 상태를 다시 읽습니다. 고압 인터록은 압력이 너무 높을 때 정해진 동작을 막거나 멈추게 하는 보호 로직입니다. 알람 확인 버튼은 경고를 확인했다는 표시이며 고장을 수리하는 버튼이 아닙니다.</p>''')

section('communication','Modbus·MQTT는 프로그램 이름인가요?',stack('Modbus — 설비의 값을 읽고 쓰는 통신 규칙','Modbus는 프로그램이 설비의 정해진 주소에서 값을 읽거나 쓰도록 정한 통신 방식입니다.','기계 안에 번호가 붙은 서랍들이 있다고 생각하세요. 한 서랍에는 온도, 다른 서랍에는 운전 스위치 값이 있습니다. “이 번호를 읽어주세요” 또는 “이 번호에 정지 값을 써주세요”라고 요청하고 응답을 받습니다.','FUXA는 Modbus TCP로 가상 설비의 센서값을 읽고 기동·정지와 설정값을 씁니다. EdgeX도 Modbus로 값을 읽습니다. TCP는 이 요청을 네트워크 연결로 주고받는 방식입니다.','FUXA ↔ 가상 설비, EdgeX ↔ 가상 설비. 켜기·끄기 값은 코일, 숫자 값은 레지스터라는 주소 공간으로 다룹니다.')+stack('MQTT와 EMQX — 전달 규칙과 중계 프로그램','MQTT는 관심 있는 소식을 등록해 받아보는 메시지 전달 방식이고, EMQX는 그 소식을 중계하는 서버 프로그램입니다.','학교 방송실에서 “급식 소식”을 듣기로 한 교실에 방송을 전달하는 모습과 비슷합니다. 보내는 쪽은 소식을 발행하고, 받는 쪽은 필요한 종류를 구독합니다. 소식 종류에 붙인 경로 이름이 토픽입니다.','EdgeX가 모은 계측 메시지를 EMQX에 보냅니다. Telegraf는 해당 토픽을 구독해 받습니다. 반대쪽에서는 분석된 알람도 별도 토픽을 통해 FUXA에 전달됩니다.','수집: EdgeX → MQTT/EMQX → Telegraf. 알람 표시: 알람 중계 → MQTT/EMQX → FUXA.')+ '<p>Modbus와 MQTT는 맡은 통신 방식이 다릅니다. Modbus로 설비에 값을 물어보고, 가져온 값을 MQTT 메시지로 여러 프로그램에 전달할 수 있습니다. 둘 중 하나만 선택해야 하는 관계가 아닙니다.</p>')

section('collect','왜 EdgeX와 Telegraf가 따로 필요한가요?',stack('EdgeX — 설비 쪽 통신을 맡는 수집 기반','EdgeX는 여러 종류의 장치에서 데이터를 읽고, 다른 프로그램이 사용할 수 있는 이벤트로 전달하는 소프트웨어 묶음입니다.','기계마다 말하는 방식이 다를 때 현장에서 그 말을 알아듣고 기록하는 담당자에 가깝습니다. 분석 담당이 모든 기계의 연결 방법을 직접 알 필요가 없게 합니다.','이 구성에서는 Modbus 장치 서비스가 가상 설비의 태그를 반복해서 읽습니다. EdgeX 내부에서 읽은 데이터를 다룬 다음 MQTT 내보내기 기능이 EMQX로 전달합니다.','가상 설비 → EdgeX의 수집·이벤트 처리 → MQTT 내보내기 → EMQX. 그림에서는 이 내부 구성들을 EdgeX 상자 하나로 묶습니다.')+stack('Telegraf — 데이터를 받아 맞는 형식으로 옮기는 수집 도구','Telegraf는 입력에서 데이터를 받아 정리하고, 설정된 출력으로 보내는 에이전트 프로그램입니다.','서로 다른 양식의 기록을 받아 공통 서식으로 정리하고 목적지에 넣어 주는 담당자라고 생각하세요. 어디서 받는지, 어떻게 정리하는지, 어디로 보내는지를 설정합니다.','첫 번째 역할은 EdgeX 메시지에서 센서 기록을 꺼내 Kafka에 보낼 형식으로 맞추는 일입니다. 두 번째 역할은 Kafka의 기록을 받아 InfluxDB에 저장하는 일입니다. 세 번째 역할은 알람을 MQTT로 다시 보내 FUXA에 표시하는 일입니다.','같은 도구를 서로 다른 설정으로 사용합니다. “Telegraf → Kafka”와 “Kafka → Telegraf → InfluxDB”가 함께 있는 이유입니다.'))

section('kafka','EMQX 다음에 Kafka가 또 있는 이유',stack('Kafka — 여러 소비자가 각자 읽는 이벤트 기록','Kafka는 계속 발생하는 데이터를 순서가 있는 기록으로 보관하고, 여러 프로그램이 각자 읽어 처리할 수 있게 하는 이벤트 스트리밍 플랫폼입니다.','같은 방송을 그 순간에만 듣는 대신, 순서가 적힌 공동 업무 장부에 남긴다고 생각하세요. 검사 담당은 검사할 차례부터 읽고, 보관 담당은 저장할 차례부터 읽습니다. 한 담당이 읽었다고 다른 담당의 기록이 없어지지 않습니다.','센서 원본은 원본 토픽에 기록합니다. Flink는 검사하려고 읽고, Telegraf는 이력으로 저장하려고 읽습니다. Flink가 만든 알람은 별도의 알람 토픽에 기록되어 화면 중계와 업무 접수 쪽으로 전달됩니다.','Kafka 원본 → Flink와 저장 담당으로 분기. Flink → Kafka 결과·알람 → 저장·화면·업무로 분기.')+ '<p>우리 구성에서 EMQX는 설비 쪽 메시지 중계를 맡고, Kafka는 뒤쪽 분석·저장 프로그램이 독립적으로 읽을 공통 기록을 맡습니다. 둘을 모두 쓴다고 자동으로 더 좋은 것은 아닙니다. 여기서는 설비 연결과 여러 분석·저장 작업을 나누어 실습하기 위해 함께 사용합니다. Kafka 기록에는 보관 기간이나 용량 정책이 있으므로 영구 보관 장부로 생각하지는 않습니다.</p>')

section('flink','Flink는 무엇을 보고 이상이라고 하나요?',stack('Flink — 움직이는 데이터를 계속 계산하는 처리 엔진','Flink는 끝없이 들어오는 데이터 흐름을 읽으면서 계산·비교·조건 검사를 하는 스트림 처리 소프트웨어입니다.','검사원이 컨베이어 벨트에서 지나가는 제품을 계속 확인하는 모습과 비슷합니다. 다만 여기서 지나가는 것은 제품이 아니라 시간과 태그가 붙은 센서 기록입니다.','Kafka의 원본 센서값을 받아 상한 초과, 최근 변화, 여러 신호의 발생 순서, 학습한 정상 패턴과의 차이를 검사합니다. 결과와 알람은 Kafka의 별도 토픽으로 보냅니다.','Kafka가 기록을 전달하고, Flink 안에 작성한 규칙·모델이 이상을 판단합니다. “Kafka가 고장을 판단한다”는 뜻은 아닙니다.')+ '''<div class="table-wrap"><table><tr><th>검사</th><th>쉬운 뜻</th><th>어디에 쓰이나요?</th></tr><tr><td>상·하한 규칙</td><td>미리 그어 놓은 선을 넘었는지 봅니다.</td><td>전류나 압력이 프로젝트의 기준 범위를 벗어났는지 확인합니다.</td></tr><tr><td>Z-Score</td><td>최근의 보통 모습에서 얼마나 크게 벗어났는지 봅니다.</td><td>고정 기준만으로 보이지 않는 갑작스러운 변화를 찾습니다.</td></tr><tr><td>CEP</td><td>여러 일이 어떤 순서와 시간 간격으로 발생했는지 봅니다.</td><td>교반기 전류 상승 뒤 일정 시간 안에 진동도 상승하는 조합을 검사합니다.</td></tr><tr><td>Autoencoder 모델</td><td>학습한 정상 조합을 얼마나 잘 재현할 수 있는지 비교합니다. 차이가 크면 낯선 패턴으로 봅니다.</td><td>센서 여러 개가 함께 움직이는 모습의 이상 정도를 계산합니다. ONNX는 이 학습 모델을 저장·실행하는 데 사용하는 형식이고, 실행 라이브러리가 계산을 수행합니다.</td></tr></table></div><p>규칙 검사와 모델 검사는 원본을 각각 읽는 <strong>병렬 경로</strong>입니다. 규칙 검사를 통과해야 모델 검사가 시작되는 순서가 아닙니다. 알람은 “이 조건이 관측됐으니 확인할 필요가 있다”는 뜻이며, 물리적 고장 원인이나 수리 방법이 확정됐다는 뜻은 아닙니다.</p>''')

section('storage','InfluxDB와 Grafana는 어떻게 다른가요?',stack('InfluxDB — 시간별 측정값을 보관하는 데이터베이스','InfluxDB는 시간에 따라 쌓이는 측정 기록을 저장하고 조회하는 데 쓰는 시계열 데이터베이스입니다.','매 순간의 온도와 진동을 날짜·시간별로 적어 둔 기록장입니다. “지금 몇 도인가”뿐 아니라 “10분 동안 어떻게 변했나”를 다시 볼 수 있게 합니다.','Telegraf가 Kafka에서 읽은 원본 센서값과 분석 결과를 InfluxDB에 저장합니다. AI가 과거 센서값을 조사할 때도 이 기록을 조회합니다.','Kafka → 저장용 Telegraf → InfluxDB. 원본 저장은 Flink를 통과하지 않는 별도 경로도 있습니다.')+stack('Grafana — 저장된 값을 꺼내 시각화하는 대시보드','Grafana는 연결된 데이터 소스에 질의해서 결과를 그래프·표·숫자 패널로 보여주는 도구입니다.','기록장에 적힌 숫자를 시간축 위에 점으로 찍어 연결해 주는 화면입니다. 기록장은 InfluxDB에 있고, Grafana는 보고 싶은 시간과 항목을 골라 그림으로 보여줍니다.','전류와 진동을 같은 시간대에 비교해 어느 변화가 먼저 시작됐는지 살펴봅니다. 운영 지표를 모은 Prometheus도 조회할 수 있도록 연결되어 있습니다.','InfluxDB의 센서 이력 → Grafana. Prometheus의 프로그램 운영 지표 → Grafana. Grafana 화면이 AI 조사 시작 신호를 만드는 경로는 아닙니다.')+ '<p><strong>FUXA는 지금 설비를 보고 직접 조작하는 화면, Grafana는 쌓인 기록을 비교해 보는 화면</strong>이라는 차이를 먼저 기억하면 됩니다. 두 제품의 일반 기능은 더 넓지만, 우리 구성에서는 이렇게 역할을 나눴습니다.</p>')

main=svg_begin(1110,'데이터 수집·분석·저장 아키텍처')
for y,label in [(25,'L1 설비'),(175,'L2 수집·중계'),(325,'L3 원본 기록'),(475,'L4 분석'),(625,'L5 결과 기록'),(785,'L6 이력 저장'),(1025,'L7 화면')]:
    main+=f'<text class="lane" x="15" y="{y}">{label}</text>'
main+=box(355,30,430,'가상 설비 · AR-100','반응기·교반기·센서·운전 상태')
main+=box(170,180,230,'EdgeX','장치 수집 → 이벤트 → 내보내기')+box(490,180,180,'EMQX','MQTT 메시지 중계')+box(780,180,260,'Telegraf · 수집용','센서 메시지 형식 정리')
main+=line('M570 100 V140 H285 V180','Modbus로 읽은 센서값',410,130)+line('M400 215 H490','MQTT',445,200)+line('M670 215 H780','MQTT 구독',725,200)
main+=box(210,330,780,'Kafka · 원본 토픽','sensor.telemetry.raw · 여러 프로그램이 각각 읽음')+line('M910 250 V330','센서 원본 기록',965,292)
main+=box(245,480,290,'Flink · 규칙 작업','상·하한 / Z-Score / CEP')+box(665,480,290,'Flink · 모델 작업','전처리 → ONNX 모델 실행')
main+=line('M390 400 V480','원본 읽기',450,445)+line('M810 400 V480','원본 읽기',870,445)
main+=box(210,630,780,'Kafka · 분석 결과 토픽','clean: 정리값 / score: 이상 점수 / alerts: 알람')+line('M390 550 V630','규칙 결과·알람',460,597)+line('M810 550 V630','모델 결과·알람',883,597)
main+=box(355,790,430,'Telegraf · 저장용','원본·정리값·점수·알람을 각각 읽음')+line('M570 700 V790','분석 결과 저장 경로',690,752)
main+=line('M210 365 H165 V825 H355','원본 직접 저장',262,752)
main+=box(355,910,430,'InfluxDB','시간별 센서 기록·분석 결과 보관')+line('M570 860 V910')
main+=box(355,1030,430,'Grafana','기간과 센서를 선택해 그래프로 표시')+line('M570 980 V1030','조회된 이력',665,1010)
main+='</svg></div>'
section('architecture','레이어별 아키텍처 ① — 센서값이 기록과 그래프가 되는 길','<p>레이어는 역할별 묶음입니다. 컴퓨터가 꼭 층마다 한 대씩 있다는 뜻은 아닙니다. 아래 화살표는 <strong>데이터가 전달되는 방향</strong>을 표시합니다. 조회 요청과 응답을 모두 그리면 복잡해지므로, 이 그림에서는 읽어 온 데이터의 흐름을 나타냅니다.</p>'+main+'<p>왼쪽으로 돌아 내려가는 선은 <strong>원본을 분석과 별도로 저장하는 경로</strong>입니다. L3에서 L4의 두 분석 작업으로 갈라지는 선은 두 작업이 원본을 각자 읽는다는 뜻입니다. L3과 L5의 Kafka 상자는 별도 제품 두 대가 아니라 같은 Kafka 안의 원본 토픽과 결과 토픽을 구분한 것입니다.</p><p>이 그림은 EdgeX를 사용하는 기본 구성을 보여줍니다. 가벼운 실습용 lite 구성은 수집 경로가 다르므로 이 그림에 섞지 않았습니다. 다음 그림은 여기서 생긴 알람이 화면·업무로 전달되고, 승인된 명령이 설비로 돌아가는 길입니다.</p>')

control=svg_begin(1060,'알람·운전원 조작·AI 승인 조치 아키텍처')
control+=box(370,30,380,'Kafka · alerts','Flink가 만든 이상 알람')
control+=box(130,180,300,'Telegraf → EMQX','알람을 MQTT로 다시 전달')+box(640,180,330,'Pilot · 사건 접수','알람을 조사할 업무로 등록')
control+=line('M450 100 V140 H280 V180','화면 표시 경로',265,130)+line('M670 100 V140 H805 V180','업무 접수 경로',850,130)
control+=box(130,340,300,'FUXA · 운전원 화면','현재값·최근 알람·기동/정지')+line('M280 250 V340','최근 분석 알람',370,298)
control+=box(640,340,330,'Pilot · AI 조사','사람이 분석 시작 → 실제 조회 도구')+line('M805 250 V340','접수 후 분석 요청',895,300)
control+=box(550,480,500,'근거 조회 대상','InfluxDB 센서 이력 / Neo4j 설비·문서 관계')+line('M760 480 V410','조회된 근거',662,452)
control+=box(640,620,330,'Pilot · 담당자 검토','조치안·근거 확인 → 승인 또는 반려')+line('M970 375 H1080 V655 H970','조치안',1043,570)
control+=box(640,760,330,'Pilot · 승인 후 실행','조건 재확인 → 정지 요청 → 결과 확인')+line('M805 690 V760','승인된 경우',883,734,True)
control+=box(130,920,840,'가상 설비 · AR-100','교반기 운전 명령 반영 / 새 상태 제공')
control+=line('M230 410 V920','Modbus 명령',155,740,True)+line('M370 920 V410','Modbus 현재값',450,840)
control+=line('M735 830 V920','Modbus 정지 쓰기',650,885,True)+line('M905 920 V830','HTTP 새 상태 읽기',984,868)
control+='<text class="sub" x="550" y="1030" text-anchor="middle">업무 기록: PostgreSQL에 사건·분석·승인·조치 결과 저장 · 반려하면 설비 명령 없음</text></svg></div>'
section('return','레이어별 아키텍처 ② — 알람을 보고, 승인한 조치를 전달하는 길','<div class="legend"><span>초록 화살표: 알람·근거·상태·업무 전달</span><span>주황 화살표: 승인 또는 운전 명령</span></div>'+control+'<p>FUXA는 Modbus로 설비의 현재값을 읽습니다. 최근 분석 알람은 MQTT로 따로 받습니다. 따라서 숫자가 움직인다는 사실만으로 뒤의 분석까지 정상이라고 단정할 수는 없습니다.</p><p>우리의 별도 업무 서비스를 여기서는 <strong>Pilot</strong>이라고 부릅니다. AI가 알람·센서 기록·문서를 조회해 조치안을 만들고, 사람이 승인하면 내부 실행 기능이 설비에 명령합니다. AI가 FUXA 버튼을 대신 클릭하지 않습니다. 정지 명령은 Modbus로 보내며, 실행 뒤의 새 상태는 HTTP 상태 조회로 확인합니다.</p><p>추가로 만든 Vue 대시보드는 Pilot의 웹 화면입니다. 백엔드 API를 통해 설비 상태와 업무 기록을 받아 표시하며, 브라우저가 직접 Modbus로 통신하는 것은 아닙니다. FUXA 제어창도 이 대시보드 안에서 열 수 있습니다.</p>')

section('support','운영과 AI 쪽 도구는 무엇을 맡나요?', '''<div class="table-wrap"><table><tr><th>도구</th><th>쉬운 정의와 비유</th><th>우리 구성의 용도</th></tr><tr><td>Prometheus</td><td>프로그램이 내놓는 운영 수치를 주기적으로 모으는 감시 도구입니다. 기계실의 체온계처럼 서버와 처리 작업의 상태를 봅니다.</td><td>수집·처리 시스템의 상태를 살피고 Grafana에서 운영 지표를 조회합니다. 반응기 센서 이력 저장소인 InfluxDB와 대상이 다릅니다.</td></tr><tr><td>PostgreSQL</td><td>행과 열로 구조화된 기록을 저장하는 데이터베이스입니다. 접수번호별 업무 대장에 가깝습니다.</td><td>어떤 사건을 AI가 분석했는지, 누가 승인했는지, 결과가 무엇인지 기록합니다.</td></tr><tr><td>Neo4j</td><td>대상과 대상 사이의 관계를 저장하는 그래프 데이터베이스입니다. 가족 관계도처럼 “무엇이 무엇과 연결됐나”를 찾습니다.</td><td>VT-101이 M-101의 센서이고 M-101에 어떤 문서가 적용되는지 연결합니다. 관계가 있다고 고장 원인이 증명되는 것은 아닙니다.</td></tr><tr><td>Agent</td><td>필요한 도구를 호출해 자료를 찾아보고 응답을 만드는 AI 처리 주체입니다.</td><td>알람·센서·문서를 조회해 근거와 미확인 사항을 나누고 조치를 제안합니다. 실행 결정에는 담당자 검토가 있습니다.</td></tr><tr><td>LiteLLM</td><td>애플리케이션과 AI 모델 사이의 호출을 중계하는 프로그램입니다. 모델로 연결하는 교환대에 가깝습니다.</td><td>Agent가 설정된 모델을 호출하게 합니다. 센서 수집이나 Modbus 제어를 담당하지 않습니다.</td></tr><tr><td>Docker</td><td>프로그램과 실행 환경을 컨테이너라는 단위로 묶어 실행하는 도구입니다.</td><td>Kafka·Flink·저장소 등의 실행 환경을 함께 준비합니다. 공장 데이터가 Docker라는 분석 단계를 통과하는 것은 아닙니다.</td></tr></table></div>''')

section('story','한 사건을 끝까지 연결해 보면', '''<ol class="steps"><li><b>교반기가 평소보다 심하게 떨립니다.</b><p>시뮬레이터에서 이상을 주입하면 교반기 전류와 진동이 올라갑니다. 반응기는 재료를 담은 통이고, 이번에 이상을 살피는 대상은 안에서 재료를 섞는 교반기입니다.</p></li><li><b>EdgeX가 Modbus로 숫자를 읽습니다.</b><p>어느 태그에서 언제 측정한 값인지 붙여 메시지로 만듭니다. EMQX가 이를 전달하고 Telegraf가 형식을 정리해 Kafka에 넣습니다.</p></li><li><b>같은 숫자가 검사와 저장에 사용됩니다.</b><p>Flink는 이상 조건을 검사합니다. 저장용 Telegraf는 원본을 InfluxDB에 남깁니다. Grafana에서는 이 시간대의 전류·진동 변화를 볼 수 있습니다.</p></li><li><b>Flink가 알람을 만들고 Kafka에 기록합니다.</b><p>알람은 화면 중계 경로로 FUXA에 표시됩니다. 동시에 Pilot이 읽어 조사할 사건으로 접수합니다. 알람 자체가 정지 명령은 아닙니다.</p></li><li><b>사람이 분석을 시작하면 Agent가 근거를 조사합니다.</b><p>현재도 전류와 진동이 높은지, 어떤 설비의 센서인지, 적용 문서가 무엇인지 조회합니다. 확인한 사실과 모르는 원인을 나누어 제안합니다.</p></li><li><b>사람이 정지안을 승인하면 명령하고 다시 확인합니다.</b><p>Pilot 내부 실행 기능이 조건을 다시 확인한 후 Modbus로 교반기 정지를 요청합니다. 새 상태에서 정지가 확인되면 결과를 기록합니다. 점검 요청만 승인한 경우에는 점검 업무만 기록하고 설비 명령은 보내지 않습니다.</p></li></ol><div class="callout"><p><strong>센서 → 수집 → 전달 → 검사 → 기록·화면 → 검토·조치</strong>가 연결된 구조입니다. 각 도구는 이 과정의 서로 다른 일을 맡습니다.</p></div>''')

nav=[('scada','SCADA와 FUXA'),('equipment','반응기와 교반기'),('communication','통신 방식'),('collect','수집 도구'),('kafka','Kafka'),('flink','Flink'),('storage','저장과 화면'),('architecture','아키텍처 그림'),('return','조치 경로'),('story','전체 흐름')]
html='<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SCADA와 각 도구의 역할 · 쉽게 풀어 쓴 시스템 아키텍처</title><style>'+style+'</style></head><body><main><header><small>IoT SCADA · 개념에서 실제 연결까지</small><h1>무슨 도구이고,<br>왜 이 자리에 쓰일까요?</h1><p class="intro">SCADA와 FUXA의 차이부터, 반응기·교반기와 데이터의 이동까지.</p><p>정의를 쉬운 말로 풀고, 비유로 이해한 뒤, 우리 구성에서 어디에 연결되는지 살펴봅니다.</p></header><nav aria-label="설명 목차">'+''.join(f'<a href="#{i}">{t}</a>' for i,t in nav)+'</nav>'+''.join(parts)+'</main></body></html>'
target.write_text(html,encoding='utf-8')
(root/'ai-web/public/system-guide.html').write_text(html,encoding='utf-8')
print(f'Wrote {len(parts)} sections, {len(html)} characters')
