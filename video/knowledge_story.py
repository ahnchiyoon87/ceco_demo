"""Film real source registration, model proposal, reviewed publication and graph.

The source documents and equipment registry are the project's existing originals.
No simulated UI responses or fabricated knowledge build are used.
"""
import asyncio
import human
import hashlib
import json
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
INTRO=[
 ('documents',14,'01  지식의 출발점: 원본 문서',[
  '설비 구성과 이상 대응 방법은 원본 문서에 정리되어 있습니다.',
  '이 문서에는 필터 막힘을 구분하는 단서와 정비·회복 기준이 들어 있습니다.']),
 ('sources',10,'02  자료를 실제로 등록',[
  '정비 매뉴얼과 설비 목록을 지식 스튜디오에 등록합니다.']),
 ('knowledge_build',16,'03  문서에서 관계 후보 생성',[
  'AI가 선택한 원본을 읽고 설비·센서·문서의 관계를 제안합니다.',
  '원문과 대조한 관계 후보입니다. 담당자 검토를 거쳐야 사용할 수 있습니다.']),
 ('knowledge_review',16,'04  검토한 지식을 게시',[
  '담당자가 원본 근거와 연결 관계를 확인합니다.',
  '검토한 지식을 그래프에 적재했습니다.']),
 ('ontology',14,'05  온톨로지: 설비와 근거를 연결',[
  '온톨로지는 설비·센서·문서가 어떻게 연결되는지 정리한 지식 지도입니다.',
  '냉각수 필터를 선택하면 관련 센서와 정비 문서를 함께 찾을 수 있습니다.']),
]

def dump(path,data):
 path.write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str),encoding='utf-8')

async def film(page,run_dir,scene,hold,focus,origin,M,URL):
 manual=ROOT/'5_ai'/'manuals'/'AR100-COOLING-WATER.md'
 registry=ROOT/'shared'/'registry'/'equipment.yaml'
 sources=[registry,manual]
 evidence={'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
 # A readable view of the original file, not an invented portal screen.
 preview=run_dir/'original-manual.html'
 from retake_readability import manual_html
 manual_html(preview)
 await scene('documents')
 await page.goto(preview.as_uri(),wait_until='domcontentloaded')
 await hold(7)
 await human.focus(page,page.locator('h2').filter(has_text='2. 원인 구분'))
 await hold(5)
 await scene('sources')
 await page.goto(URL,wait_until='networkidle')
 await page.add_style_tag(content='.process-flow{position:relative!important;top:auto!important}html{scroll-behavior:smooth}')
 await human.click(page,page.get_by_role('button',name='문서·지식',exact=True))
 await focus('.knowledge-inputs')
 await page.locator('.knowledge-inputs input[type=file]').first.set_input_files([str(p) for p in sources])
 for source in sources:
  await human.check(page,page.get_by_role('checkbox',name=source.name,exact=True))
 await hold(8)
 await scene('knowledge_build')
 shot_start=time.monotonic()-origin
 await human.click(page,page.locator('.knowledge-workspaces button').filter(has_text='관계 후보 생성'))
 question=('냉각 계통에서 알람 센서가 어느 설비에 속하고 어떤 대응 문서를 읽어야 하는지 원본 근거로 연결해 주세요. '
  '설비 목록과 냉각수 정비 문서를 모두 읽으세요. 추가 노드는 Asset R-101, HX-102, ST-103만 제안하고 '
  'site=AR-100, device=reactor-line-01, ID는 AR-100/reactor-line-01/asset/설비명으로 사용하세요. '
  '현재 게시된 설비와 식별자를 맞추기 위해 Asset.properties.name은 반드시 R-101, HX-102, ST-103 중 해당 ID로 기록하세요. '
  '반응기·냉각기 같은 원본의 한글 이름은 properties.description에 기록하세요. '
  '그 밖의 노드와 실행 지시는 추가하지 마세요. 이 세 설비에 실제로 속한 센서의 HAS_SENSOR 관계와 '
  '냉각수 문서 AR100-COOLING-WATER의 HAS_PROCEDURE 관계를 제안하세요. 기존 추출 노드는 그대로 유지하고, '
  '각 제안에는 선택 원본의 정확한 인용을 붙이며 남은 제약은 unresolved에 기록하세요.')
 await human.fill(page,page.locator('#knowledge-question'),question)
 async with page.expect_response(lambda r:'/api/knowledge/build' in r.url and r.request.method=='POST') as response:
  await human.click(page,page.get_by_role('button',name='선택 원본으로 의미 관계 제안',exact=True))
 started=await (await response.value).json()
 if 'id' not in started:raise RuntimeError('실제 지식 후보 생성을 시작하지 못했습니다.')
 await focus('.knowledge-tool-trace')
 await hold(8)
 initial_end=time.monotonic()-origin
 end=time.monotonic()+240
 while True:
  build=await asyncio.to_thread(M.api,'/api/knowledge/builds/'+started['id'])
  if build['status']!='running':break
  if time.monotonic()>end:raise RuntimeError('지식 관계 후보 생성 대기 시간 초과')
  await hold(2)
 dump(run_dir/'knowledge-build.json',build)
 if build['status']!='candidate':raise RuntimeError('지식 관계 후보 생성 실패: '+str(build.get('error')))
 result=build['result']
 assets=[n for n in result['batch']['nodes'] if n['class']=='Asset']
 allowed={'R-101','HX-102','ST-103'}
 for asset in assets:
  props=asset['properties']
  if props.get('name') not in allowed or props.get('site')!='AR-100' or props.get('device')!='reactor-line-01' or asset['id']!='AR-100/reactor-line-01/asset/'+props['name']:
   raise RuntimeError('후보 설비 식별정보가 원본과 일치하지 않습니다. 게시하지 않았습니다.')
 if len(assets)!=3:raise RuntimeError('냉각 계통 설비 세 개의 관계 후보가 모두 필요합니다.')
 nodes={n['id']:n for n in result['batch']['nodes']}
 for relation in result['batch']['relationships']:
  if relation['type']=='HAS_SENSOR':
   source=nodes[relation['from_id']];target=nodes[relation['to_id']]
   if source['class']!='Asset' or target['class']!='Sensor' or source['properties']['name']!=target['properties'].get('equipment_id'):
    raise RuntimeError('센서 소속이 원본 설비 목록과 일치하지 않습니다. 게시하지 않았습니다.')
 evidence.update({'build_id':build['id'],'build_model':build['model'],'build_status':build['status'],
  'nodes':result['node_count'],'relationships':result['relationship_count'],
  'source_tools':[x.get('tool') for x in build['trace'] if x.get('tool')]})
 await page.get_by_role('button',name='생성된 관계 후보 검토',exact=True).wait_for(timeout=15000)
 await focus('.meaning-builder')
 final_start=time.monotonic()-origin
 await hold(8)
 final_end=time.monotonic()-origin
 build_shot={'segments':[{'start':shot_start,'end':initial_end},{'start':final_start,'end':final_end}],
             'caption_split_actual_s':initial_end-shot_start}
 await scene('knowledge_review')
 review_start=time.monotonic()-origin
 await human.click(page,page.get_by_role('button',name='생성된 관계 후보 검토',exact=True))
 await focus('.candidate-browser')
 await hold(5)
 review_first_end=time.monotonic()-origin
 # Validate the actual model proposal against the already published graph before
 # merging. This does not delete existing nodes, replace the registry, or change IO.
 graph=await asyncio.to_thread(M.api,'/api/graph?limit=500')
 for asset in assets:
  same=[n for n in graph['nodes'] if 'Asset' in n.get('labels',[]) and
    all(n.get('properties',{}).get(k)==asset['properties'][k] for k in ('site','device','name'))]
  if any(n.get('properties',{}).get('_source_id',n.get('id'))!=asset['id'] for n in same):
   raise RuntimeError('기존 설비와 후보 식별자가 달라 게시하지 않았습니다.')
 await focus('.publish-box')
 review_second_start=time.monotonic()-origin
 await human.check(page,page.locator('.publish-box input[type=checkbox]'))
 await human.fill(page,page.locator('.publish-box textarea'),'원본 설비 목록과 냉각수 매뉴얼을 대조했습니다. 설비별 센서와 적용 문서의 연결을 확인해 게시합니다.')
 await hold(3)
 async with page.expect_response(lambda r:'/api/knowledge/publish' in r.url and r.request.method=='POST') as response:
  await human.click(page,page.get_by_role('button',name='Neo4j에 게시',exact=True))
 published=await (await response.value).json()
 if published.get('status')!='published':raise RuntimeError('지식 게시 실패: '+str(published.get('detail')))
 published_at=time.monotonic()-origin
 await page.locator('.publish-result').wait_for(timeout=15000)
 await hold(7)
 evidence['publication']=published
 review_shot={'segments':[{'start':review_start,'end':review_first_end},
                           {'start':review_second_start,'end':time.monotonic()-origin}],
              'caption_split_actual_s':review_first_end-review_start+published_at-review_second_start}
 await scene('ontology')
 ontology_start=time.monotonic()-origin
 await human.click(page,page.get_by_role('button',name='온톨로지',exact=True))
 await focus('.knowledge-map')
 await hold(7)
 await human.select(page,page.get_by_role('combobox',name='중심 설비',exact=True),label='ST-103')
 await hold(2)
 await focus('.map-detail')
 selected_at=time.monotonic()-origin
 await hold(7)
 await page.screenshot(path=str(run_dir/'05-ontology.png'))
 after_graph=await asyncio.to_thread(M.api,'/api/graph?limit=500')
 evidence['graph_counts']={'nodes':len(after_graph['nodes']),'relationships':len(after_graph['edges'])}
 dump(run_dir/'knowledge-verification.json',evidence)
 return evidence,{'knowledge_build':build_shot,'knowledge_review':review_shot,
  'ontology':{'caption_split_actual_s':selected_at-ontology_start}}
