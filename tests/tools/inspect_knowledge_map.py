"""Read-only checks for the remote-HYD-based map using published CECO knowledge."""
import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'experiments/BOOTH-20261013/knowledge-map-ui'
OUT.mkdir(exist_ok=True)

async def main():
 results=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch()
  for w,h in [(1920,1080),(1280,800),(375,812)]:
   page=await browser.new_page(viewport={'width':w,'height':h},locale='ko-KR')
   errors=[];writes=[]
   page.on('pageerror',lambda e:errors.append(str(e)))
   page.on('request',lambda r:writes.append(r.url) if r.method not in ['GET','HEAD','OPTIONS'] else None)
   await page.goto('http://localhost:38180',wait_until='domcontentloaded')
   await page.locator('.portal-sidebar').get_by_role('button',name='온톨로지',exact=True).click()
   await page.locator('.map-node').first.wait_for(timeout=45000)
   nodes=await page.locator('.map-node').count();edges=await page.locator('.map-edge').count()
   assert nodes==220 and edges==356,(nodes,edges)
   await page.screenshot(path=str(OUT/f'overview-{w}.png'))
   await page.get_by_role('combobox',name='중심 설비',exact=True).select_option(label='ST-103')
   await page.wait_for_timeout(1000)
   assert await page.locator('.map-node.selected').count()==1
   assert await page.locator('.map-node.dim').count()>0
   connections=await page.locator('.map-connections li').count()
   assert await page.locator('.map-edge.hot').count()==connections and connections>0
   assert await page.locator('.map-node').count()==nodes
   await page.screenshot(path=str(OUT/f'selected-{w}.png'))
   await page.locator('.map-connections button').first.click()
   await page.wait_for_timeout(600)
   assert await page.locator('.map-node').count()==nodes
   await page.locator('.map-node.selected').press('Space')
   assert await page.locator('.map-node.dim').count()==0
   await page.get_by_role('searchbox',name='지식 지도 이름 검색',exact=True).fill('ST-103')
   assert await page.locator('.map-node.match').count()>0
   assert await page.locator('.map-node.match.dim').count()==0
   await page.get_by_role('searchbox',name='지식 지도 이름 검색',exact=True).fill('')
   sizes=await page.evaluate('({body:document.body.scrollWidth,app:document.getElementById("app").scrollWidth,viewport:innerWidth})')
   assert sizes['body']<=w and sizes['app']<=w,sizes
   assert await page.locator('.map-canvas').evaluate('e=>e.scrollHeight>e.clientHeight')
   assert await page.locator('.map-canvas [marker-end]').count()==0
   widths=await page.locator('.map-node text').evaluate_all('es=>es.map(e=>({text:e.getComputedTextLength(),box:Number(e.previousElementSibling.getAttribute("width"))}))')
   assert all(x['text']<x['box']-14 for x in widths),[x for x in widths if x['text']>=x['box']-14][:2]
   assert not errors,errors
   assert not writes,writes
   results.append({'width':w,'nodes':nodes,'edges':edges,'selected_direct_connections':connections,'keyboard_deselection':True,'search_selection_readable':True,'no_page_overflow':True,'labels_inside_nodes':True,'browser_errors':errors,'writes':writes})
   await page.close()
  await browser.close()
 (OUT/'result.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(results,ensure_ascii=False,indent=2))

asyncio.run(main())
