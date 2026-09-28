from pathlib import Path
import base64
import pymupdf
ROOT=Path(__file__).resolve().parents[1]
pdf=ROOT/'프로토타입_아키텍처_보고용.pdf'
doc=pymupdf.open(pdf)
assert len(doc)==2
assert 'Process-GPT' not in ''.join(p.get_text() for p in doc)
pages=[]
for i,p in enumerate(doc):
    data=base64.b64encode(p.get_pixmap(matrix=pymupdf.Matrix(2.5,2.5)).tobytes('png')).decode()
    pages.append(f'<section id="p{i+1}"><img src="data:image/png;base64,{data}" alt="'+('프로토타입 전체 아키텍처' if i==0 else '조치 전달 3가지 방식과 70명 실습 운영 결정 사항')+'"></section>')
html='''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>IoT-SCADA · Pilot 프로토타입 아키텍처</title><style>
*{box-sizing:border-box}body{margin:0;background:#edf1f5;color:#16232e;font:16px/1.7 'Malgun Gothic',sans-serif}header{max-width:1000px;margin:25px auto;padding:25px;background:white;border-radius:10px}h1{font-size:25px;margin:0 0 12px}p{margin:8px 0}nav{display:flex;gap:12px;flex-wrap:wrap;margin-top:16px}a,button{border:0;background:#193c6d;color:white;border-radius:6px;padding:9px 15px;text-decoration:none;font:inherit;cursor:pointer}main{max-width:1000px;margin:auto}section{margin:20px 0;background:white;box-shadow:0 3px 14px #19334816}img{width:100%;display:block;height:auto}.note{color:#536574;font-size:14px}@media print{body{background:white}header{display:none}main{max-width:none}section{margin:0;box-shadow:none;break-after:page}img{max-height:100vh;object-fit:contain}}@media(max-width:600px){header{margin:0;padding:18px}h1{font-size:21px}}
</style></head><body><header><h1>IoT-SCADA · Pilot 프로토타입 아키텍처</h1><p><b>Pilot은 이상 사건을 받아 AI 조사·담당자 승인·설비 조치·결과 확인을 하나로 이어주는 업무 서비스입니다.</b> Agent는 그 안에서 근거를 조사하고 대응안을 만드는 역할을 합니다.</p><p class="note">교육용 가상 설비에서 승인 후 Modbus 정지와 결과 확인까지 시연했습니다. 현재 AI 분석은 버튼으로 시작하며, 자동 시작 연결과 70명 운영 검증은 남아 있습니다.</p><nav><a href="#p1">아키텍처</a><a href="#p2">결정할 사항</a><button onclick="window.print()">인쇄</button></nav></header><main>'''+''.join(pages)+'</main></body></html>'
out=ROOT/'프로토타입_아키텍처_보고용.html'
out.write_text(html,encoding='utf-8')
print(out)
