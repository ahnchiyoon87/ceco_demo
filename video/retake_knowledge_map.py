"""Replace only the read-only ontology scene after the HYD-based UI revision."""
import asyncio,json,time,sys
from pathlib import Path
from playwright.async_api import async_playwright
import human

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'experiments/BOOTH-20261013/run-173439/timeline.json'
OUT=ROOT/'experiments/BOOTH-20261013/natural-final'
OUT.mkdir(exist_ok=True)

async def main():
 meta=json.loads(SOURCE.read_text(encoding='utf-8'))
 oldverification=json.loads(Path(meta['verification']).read_text(encoding='utf-8'))
 errors=[];writes=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch()
  ctx=await browser.new_context(viewport={'width':1920,'height':900},record_video_dir=str(OUT),record_video_size={'width':1920,'height':900},locale='ko-KR')
  await human.install(ctx);page=await ctx.new_page();video=page.video
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.on('request',lambda r:writes.append(r.url) if r.method not in ['GET','HEAD','OPTIONS'] else None)
  origin=time.monotonic()
  await page.goto('http://localhost:38180',wait_until='networkidle')
  await human.click(page,page.locator('.portal-sidebar').get_by_role('button',name='온톨로지',exact=True))
  await page.locator('.map-node').first.wait_for(timeout=45000)
  await human.focus(page,page.locator('.knowledge-map'))
  start=time.monotonic()-origin
  await page.wait_for_timeout(6500)
  await human.select(page,page.get_by_role('combobox',name='중심 설비',exact=True),label='ST-103')
  await page.wait_for_timeout(2000)
  # Keep the emphasized map and the linked evidence visible together.
  await human.focus(page,page.locator('.map-canvas'))
  selected_at=time.monotonic()-origin
  await page.wait_for_timeout(6500)
  await page.screenshot(path=str(OUT/'ontology-final.png'))
  end=time.monotonic()-origin
  counts={'nodes':await page.locator('.map-node').count(),'edges':await page.locator('.map-edge').count(),'direct_connections':await page.locator('.map-connections li').count()}
  assert counts['nodes']==oldverification['knowledge']['graph_counts']['nodes']
  assert counts['edges']==oldverification['knowledge']['graph_counts']['relationships']
  assert not writes and not errors,(writes,errors)
  await ctx.close();raw=str(await video.path());await browser.close()
 for shot in meta['scenes']:
  shot['raw']=meta['raw']
 ontology=next(s for s in meta['scenes'] if s['id']=='ontology')
 ontology.clear();ontology.update({'id':'ontology','start':start,'end':end,'raw':raw,'caption_split_actual_s':selected_at-start})
 meta['storyboard']=[(k,20 if k=='ontology' else d,t,c) for k,d,t,c in meta['storyboard']]
 oldverification['ontology_retake']={'read_only':True,'remote_hyd_commit':'6f350503a78ca792cbcdf29a803d87da17867018','graph_counts':counts,'browser_errors':errors,'writes':writes,'presentation_actions':human.actions}
 path=OUT/'verification.json';path.write_text(json.dumps(oldverification,ensure_ascii=False,indent=2),encoding='utf-8');meta['verification']=str(path)
 (OUT/'timeline.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
 print('READ-ONLY ONTOLOGY RETAKE',round(end-start,2),'s; final',sum(s[1] for s in meta['storyboard']),'s',flush=True)

asyncio.run(main())
