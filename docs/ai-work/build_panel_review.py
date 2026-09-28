"""Standalone review document with embedded, unmodified real UI captures."""
from pathlib import Path
import base64
import html
import re

ROOT = Path(__file__).resolve().parent

def inline(text):
    text = html.escape(text)
    return re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)

source = (ROOT / 'PANEL-DRAFT.md').read_text(encoding='utf-8')
body = source.split('## 비전 및 목표', 1)[1].split('## 관련소스', 1)[0]
sections = []
for line in ('## 비전 및 목표' + body).splitlines():
    if line.startswith('## '):
        sections.append('<h2>' + inline(line[3:]) + '</h2>')
    elif line.startswith('- '):
        sections.append('<p class="item">• ' + inline(line[2:]) + '</p>')
    elif line.strip():
        sections.append('<p>' + inline(line) + '</p>')

def figure(path, title, caption):
    data = base64.b64encode((ROOT / path).read_bytes()).decode('ascii')
    return f'<figure><h3>{html.escape(title)}</h3><img src="data:image/png;base64,{data}" alt="{html.escape(caption)}"><figcaption>{html.escape(caption)}</figcaption></figure>'

figures = ''.join([
    figure('browser-qa/operations-review.png', '01  운영 현황과 사건 근거', '실제 서비스 캡처 · 가상 공정 AR-100 · 사건, 연결 문서 수와 센서 관측을 함께 확인하는 화면입니다.'),
    figure('browser-qa/graph-assets.png', '02  설비에 연결된 센서와 문서', '실제 서비스 캡처 · Asset 필터로 설비와 직접 연결 대상을 표시했습니다. 전체 게시 그래프는 35개 노드·41개 관계이며, 그림은 그 일부입니다. 그래프 가독성은 개선 중입니다.'),
    figure('panel-assets/system-flow.png', '03  시스템 구성', '설명용 구성도 · 실제 화면 캡처가 아닙니다. 사전 지식 구축과 알람 이후 근거 조회·검토·조치를 구분합니다.'),
])

out = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>제조 AI 업무도우미 패널 원고와 실제 화면</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#eef2f5;color:#213544;font:16px/1.85 'Malgun Gothic',sans-serif}main{max-width:1200px;margin:40px auto;background:#fff;padding:56px;border-radius:16px}header{margin-bottom:36px}header small{color:#187b6d;font-weight:700;letter-spacing:2px}h1{font-size:34px;line-height:1.4;letter-spacing:-1px;margin:12px 0}h2{font-size:23px;margin:36px 0 16px}h3{font-size:20px;margin:0 0 16px}p{margin:12px 0}.note{background:#f0f7f5;padding:18px 24px;border-radius:10px;font-size:14px}.item{padding-left:18px;text-indent:-14px}figure{margin:30px 0 50px;padding:24px;border:1px solid #dce5e9;border-radius:12px;break-inside:avoid}img{display:block;width:100%;height:auto;border:1px solid #edf1f4}figcaption{font-size:13px;color:#586f7f;margin-top:16px}a{color:#187b6d}footer{font-size:13px;color:#657785;margin-top:30px}@media(max-width:700px){main{margin:0;padding:24px;border-radius:0}h1{font-size:26px}figure{padding:12px}}@media print{body{background:white}main{margin:0;padding:0;max-width:none}figure{page-break-before:always;border:0;padding:0}h2,h3{break-after:avoid}}
</style><main><header><small>ASSEMBLY / CECO 2026</small><h1>제조 AI 업무도우미<br>패널 원고와 실제 화면</h1><p>온톨로지로 설비·센서·문서를 연결하고, AI 대응안을 사람이 검토하는 제조 업무도우미입니다.</p></header>
<div class="note">2026.09.21 검토본 · 교육용 가상 공정의 강사 시연본입니다. 아래 두 화면은 실행 중인 서비스에서 직접 캡처했습니다. 전체 UI 리허설과 AI 검토·결과 화면의 최종 캡처는 남아 있습니다.</div>
''' + ''.join(sections) + '<h2>관련소스</h2>' + figures + '''<footer>기술 참고: INOXPA BCI 매뉴얼 20.005.30.01EN (B), 2024/08, p.15 · IEC 62682:2022 공식 공개 설명 · OPC UA for Machinery 공식 자료. 가상 설비의 운전 한계나 인증 근거로 전용하지 않습니다.<br>신청서 편집본: CECO-panel-application-draft.docx · 날짜, 담당자와 서명은 제출 시 확정합니다.</footer></main></html>'''
target = ROOT / 'panel-assets' / 'CECO-panel-review.html'
target.write_text(out, encoding='utf-8')
print(target)
