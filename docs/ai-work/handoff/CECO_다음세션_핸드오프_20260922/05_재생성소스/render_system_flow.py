"""Author a vector architecture figure and matching PNG, not a demo screenshot."""
from pathlib import Path
from html import escape
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent / 'panel-assets'
OUT.mkdir(exist_ok=True)
W, H = 2000, 1160
im = Image.new('RGB', (W, H), '#f5f8fa')
draw = ImageDraw.Draw(im)
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
       '<title>온톨로지 기반 제조 AI 업무도우미 시스템 구성도</title>',
       '<desc>SCADA 알람, 지식 연결, AI 분석, 사람 검토와 승인 후 결과 확인의 실제 구현 구조를 설명한다. 서비스 화면 캡처가 아니다.</desc>']


def rect(x, y, w, h, fill, border=None, radius=0):
    draw.rounded_rectangle((x, y, x+w, y+h), radius, fill, border, width=2)
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{border or fill}" stroke-width="2"/>')


def text(x, y, value, size=34, color='#294255', bold=False, max_width=None):
    path = 'C:/Windows/Fonts/malgunbd.ttf' if bold else 'C:/Windows/Fonts/malgun.ttf'
    font = ImageFont.truetype(path, size)
    if max_width is not None:
        assert draw.textlength(value, font=font) <= max_width, (value, max_width)
    draw.text((x, y), value, font=font, fill=color, anchor='lt')
    svg.append(f'<text x="{x}" y="{y+size*.86}" font-family="Malgun Gothic, sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}">{escape(value)}</text>')


def arrow(x1, y1, x2, y2):
    color = '#7e9ba8'
    draw.line((x1, y1, x2, y2), fill=color, width=4)
    if y1 == y2:
        points = [(x2, y2), (x2-12, y2-8), (x2-12, y2+8)]
    else:
        points = [(x2, y2), (x2-8, y2-12), (x2+8, y2-12)]
    draw.polygon(points, fill=color)
    svg.append(f'<path d="M{x1},{y1} L{x2},{y2}" stroke="{color}" stroke-width="4"/>')
    svg.append(f'<polygon points="{" ".join(f"{x},{y}" for x,y in points)}" fill="{color}"/>')


rect(0, 0, W, H, '#f5f8fa')
text(64, 46, 'ASSEMBLY  /  MANUFACTURING AI', 26, '#147c70', True)
text(60, 100, '알람에서 근거 있는 대응까지', 66, '#142e40', True)
text(64, 195, '기존 SCADA 위에 지식 연결과 AI 업무 흐름을 더합니다.', 34)

cards = [
    ('01', '이상 신호 수집', '기존 IIoT · SCADA', '#476e88',
     ['가상 반응기 AR-100', '전류·진동 알람 수신', '관련 알람을 사건으로 묶기'],
     '센서 이력 · 원본 알람 보존'),
    ('02', '설비·문서 연결', '온톨로지 · Neo4j', '#187f75',
     ['센서 ↔ 설비 ↔ 적용 문서', '게시된 설비 관계로 조회', '문서 버전과 출처 확인'],
     '사전 준비: 자료 등록·관계 검토'),
    ('03', '근거 분석', 'Luna · LiteLLM 중계', '#5c62a0',
     ['사건 당시와 현재 비교', '관측·문서 도구 조회', '원인 후보·미확인 항목 정리'],
     '검토할 대응안 또는 근거 보완'),
    ('04', '사람이 결정', '승인 · 반려', '#aa7440',
     ['근거와 대응안 확인', '검토 의견과 결정 기록', '승인 전에는 명령 없음'],
     '반려·근거 보완 시 명령 없음'),
]
for i, (number, title, subtitle, accent, lines, footer) in enumerate(cards):
    x = 60+i*483
    rect(x, 294, 430, 434, '#ffffff', '#dce5ea', 20)
    rect(x+28, 322, 66, 50, accent, radius=10)
    text(x+41, 334, number, 26, '#ffffff', True)
    text(x+28, 405, title, 43, '#173548', True, 374)
    text(x+28, 467, subtitle, 30, accent, True, 374)
    for j, line in enumerate(lines):
        text(x+28, 535+j*48, line, 29, max_width=374)
    text(x+28, 684, footer, 25, '#627885', max_width=374)
    if i < 3:
        arrow(x+442, 510, x+470, 510)

arrow(1724, 739, 1724, 781)
rect(60, 796, 1879, 220, '#e8f3ef', '#c5ded6', 20)
text(88, 820, '승인 후에도 다시 확인합니다', 33, '#176858', True)
for x, label, detail in [
    (88, '01  실행 조건 재검사', '최신 관측 · 대상 · 문서 · 인터록'),
    (730, '02  시뮬레이터 조치', '허용된 교반기 정지 명령'),
    (1365, '03  새 관측으로 확인', '정지 확인 후에도 정비는 대기'),
]:
    text(x, 894, label, 35, '#214d43', True, 550)
    text(x, 954, detail, 28, '#4b6b61', max_width=550)
arrow(665, 916, 702, 916)
arrow(1301, 916, 1338, 916)
text(64, 1057, '가상 공정 기반 교육·전시 시연  |  구성 설명 그림 · 실제 서비스 캡처 아님', 27, '#5b7180')
text(64, 1101, '사건·조회 근거·검토·조치 결과는 업무 DB에 보존합니다. 정지 확인은 원인 제거·정비 완료를 뜻하지 않습니다.', 25, '#5b7180')
svg.append('</svg>')
(OUT/'system-flow.svg').write_text('\n'.join(svg), encoding='utf-8')
im.save(OUT/'system-flow.png', dpi=(300, 300))
print(OUT/'system-flow.png')
