from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
import fitz
from PIL import Image
import json

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parents[4] / 'CECO_패널_핵심과정_이미지'
OUT.mkdir(exist_ok=True)
pdfmetrics.registerFont(TTFont('K', 'C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('KB', 'C:/Windows/Fonts/malgunbd.ttf'))
c = canvas.Canvas(str(ROOT / 'composition.pdf'), pagesize=(1920,1080))
ink='#172E3D'; teal='#147E6E'; muted='#566D79'
def text(x,y,s,size=24,color=ink,bold=False):
    c.setFillColor(HexColor(color));c.setFont('KB' if bold else 'K',size);c.drawString(x,1080-y-size,s)
def box(x,y,w,h,color='#FFFFFF',radius=20):
    c.setFillColor(HexColor(color));c.roundRect(x,1080-y-h,w,h,radius,stroke=0,fill=1)
def base(n,title,sub):
    box(0,0,1920,1080,'#EDF3F4',0)
    box(0,0,1920,12,teal,0)
    text(70,38,'ASSEMBLY  /  제조 운영 AI 업무도우미',20,teal,True)
    text(70,85,title,43,bold=True)
    text(72,151,sub,23,muted)
    text(70,1026,'AR-100 교육용 시뮬레이션 · 실제 UI 발췌 / 설명 편집',18,muted)
    text(1560,1026,f'업무 흐름   {n:02d} / 04',20,teal,True)
def image(name,x,y,w,h):
    c.drawImage(str(ROOT/name),x,1080-y-h,width=w,height=h)
def crop(name,rect,x,y,w):
    # PDF viewport clips the unchanged screenshot; no UI values are altered.
    sx,sy,sw,sh=rect; scale=w/sw; h=sh*scale
    with Image.open(ROOT/name) as im: iw,ih=im.size
    c.saveState(); p=c.beginPath();p.rect(x,1080-y-h,w,h);c.clipPath(p,stroke=0)
    c.drawImage(str(ROOT/name),x-sx*scale,1080-y+sy*scale-ih*scale,width=iw*scale,height=ih*scale)
    c.restoreState()
def lines(x,y,items,size=26,gap=48,color=ink):
    for i,s in enumerate(items):text(x,y+i*gap,s,size,color)

base(1,'사건 당시와 현재 상태를 함께 확인','알람이 발생했다는 사실에서, 지금 확인해야 할 센서와 관측 품질로 이어집니다.')
box(70,223,1780,680)
text(108,251,'M-101 교반기  ·  전류 / 진동 / 액위',28,bold=True)
image('observations.png',108,320,1704,576.4)
text(90,932,'이 화면의 현재값은 9월 22일 재조회 값입니다. 다음 장의 AI 분석·조치 기록은 9월 21일 시연 기록입니다.',22,muted)
c.showPage()

base(2,'AI가 판단에 필요한 근거를 조회','센서값만 보지 않고, 원본 알람과 설비에 연결된 문서를 함께 확인합니다.')
box(70,225,590,745,ink)
text(108,271,'AI가 확인한 세 가지',31,'#FFFFFF',True)
lines(110,353,['01  센서 관측 이력','02  원본 알람','03  설비 관계와 문서'],29,91,'#FFFFFF')
lines(110,674,['각 조회 결과를 사건에 기록해','분석 근거를 다시 확인할 수','있도록 남깁니다.'],25,48,'#BBD5D5')
box(690,225,1160,745)
text(731,269,'실제 AI 근거 조회 기록',28,bold=True)
crop('timeline-full.png',(835,464,1040,254),733,351,1070)
text(733,698,'조회 결과 → 분석 기록 → 대응안 작성',27,teal,True)
lines(733,761,['설비 관계·문서와 센서 이력을 연결해','대응안을 작성하는 흐름을 기록으로 확인합니다.'],24,45,muted)
c.showPage()

base(3,'근거와 불확실성을 함께 담은 대응안','AI가 교반기 정지 후 점검을 제안하고, 사용자가 판단할 근거와 확인할 사항을 남깁니다.')
box(70,223,590,755,ink)
text(108,266,'제안의 핵심',31,'#FFFFFF',True)
lines(108,347,['전류·진동 동시 상한 초과','교반기 정지 후 점검 제안','적용 문서 출처 표시','미확인 고장 원인 명시'],27,81,'#FFFFFF')
lines(108,745,['오른쪽은 승인 후에도 보존된','실제 AI 대응안입니다.','교육용 프로젝트 상한을 사용합니다.'],23,47,'#BBD5D5')
box(690,211,1160,793)
image('proposal.png',773,218,990,772.3)
c.showPage()

base(4,'사람의 승인 이후, 조치 결과까지 확인','AI의 제안을 사람이 검토하고 승인한 뒤, 시뮬레이터 정지 결과를 기록합니다.')
box(70,225,1780,515)
text(108,258,'대응안 작성 → 조치 승인 → 결과 확인',30,bold=True)
crop('timeline-full.png',(835,121,1040,245),111,330,1688)
box(70,774,865,209,ink)
text(108,806,'사람이 검토하고 승인',29,'#FFFFFF',True)
lines(108,862,['승인 사유와 시각을 사건 이력에 보존합니다.'],25,45,'#C9DDDF')
box(965,774,885,209,'#DDEFE9')
text(1003,806,'정지 확인과 정비 완료를 구분',29,teal,True)
lines(1003,862,['기록된 결과는 시뮬레이터 정지 확인이며,','고장 원인 제거·수리 완료를 뜻하지 않습니다.'],24,43,ink)
c.showPage(); c.save()

names=['01_사건과_센서확인','02_AI_근거조회','03_AI_대응안과_판단근거','04_사람승인과_조치결과']
doc=fitz.open(ROOT/'composition.pdf')
manifest=[]
for page,name in zip(doc,names):
    pix=page.get_pixmap(alpha=False)
    im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
    p=OUT/(name+'.png');im.save(p,compress_level=0)
    assert im.size==(1920,1080) and p.stat().st_size>2*1024*1024
    manifest.append({'file':p.name,'size':list(im.size),'bytes':p.stat().st_size})
(ROOT/'composition-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(OUT)
print(json.dumps(manifest,ensure_ascii=False))
