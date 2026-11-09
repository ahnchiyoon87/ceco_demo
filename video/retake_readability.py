"""Re-film only original document and graph views; no build/publish/equipment IO."""
import asyncio
import html
import json
import subprocess
import sys
import time
from pathlib import Path
from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parents[1]

def manual_html(destination):
    source=ROOT/'5_ai'/'manuals'/'AR100-COOLING-WATER.md'
    script='import {marked} from "marked";import{readFileSync}from"node:fs";process.stdout.write(marked.parse(readFileSync(process.argv[1],"utf8").split("---").slice(2).join("---").trim()));'
    rendered=subprocess.run(['node','--input-type=module','-e',script,str(source)],cwd=ROOT/'5_ai'/'web',capture_output=True,text=True,encoding='utf-8',check=True).stdout
    destination.write_text('<!doctype html><meta charset="utf-8"><title>원본 · 냉각수 계통 정비 문서</title>'
        '<style>body{margin:0;background:#e9efed;color:#173d40;font-family:"Malgun Gothic",sans-serif}'
        'header{background:#163b40;color:white;padding:20px 60px;font-size:24px;position:sticky;top:0;z-index:1}'
        'header small{display:block;font-size:17px;margin-top:7px;color:#b7d9cf}'
        'article{margin:24px auto;padding:30px 44px;max-width:1650px;background:white;border-radius:14px;font-size:21px;line-height:1.65}'
        'h1{font-size:31px;margin:0 0 20px}h2{font-size:25px;margin:28px 0 14px;scroll-margin-top:125px}'
        'table{border-collapse:collapse;width:100%;margin:20px 0}th,td{border:1px solid #cbded7;padding:10px 16px;text-align:left}'
        'th{background:#e8f3ed}code{font-size:17px;background:#eef3f1;padding:2px 4px}'
        'article>p:first-of-type{font-size:17px;color:#52716c}</style>'
        '<header>원본 정비 문서<small>'+html.escape(source.name)+' · 교육용 가상 공정 · 버전 1</small></header>'
        '<article>'+rendered+'</article>',encoding='utf-8')

async def main(path):
    meta=json.loads(path.read_text(encoding='utf-8'))
    folder=path.parent/'readability-retake'
    folder.mkdir(exist_ok=True)
    manual=folder/'original-manual.html'
    manual_html(manual)
    shots=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch()
        context=await browser.new_context(viewport={'width':1920,'height':900},record_video_dir=str(folder),record_video_size={'width':1920,'height':900},locale='ko-KR')
        page=await context.new_page()
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        start=time.monotonic()
        video=page.video
        await page.goto(manual.as_uri(),wait_until='domcontentloaded')
        shot={'id':'documents','start':time.monotonic()-start}
        await page.wait_for_timeout(6000)
        await page.locator('h2').filter(has_text='2. 원인 구분').scroll_into_view_if_needed()
        await page.locator('h2').filter(has_text='2. 원인 구분').evaluate("e=>e.scrollIntoView({block:'start'})")
        await page.wait_for_timeout(6000)
        await page.screenshot(path=str(folder/'document.png'))
        shot['end']=time.monotonic()-start;shots.append(shot)
        await page.goto('http://localhost:38180',wait_until='networkidle')
        await page.locator('.mfg-nav button').filter(has_text='설비 지식 스튜디오').click()
        await page.get_by_role('button',name='게시된 관계 그래프',exact=True).click()
        await page.get_by_role('button',name='관계 구조',exact=True).click()
        await page.get_by_role('button',name='전체 그래프를 화면 가운데 맞추기',exact=True).click()
        await page.locator('.graph-toolbar').evaluate("e=>e.scrollIntoView({block:'start'})")
        await page.wait_for_timeout(1000)
        shot={'id':'ontology','start':time.monotonic()-start}
        await page.wait_for_timeout(7000)
        await page.get_by_role('button',name='설비·근거 탐색',exact=True).click()
        await page.get_by_role('combobox',name='노드 종류 필터',exact=True).select_option('Asset')
        await page.locator('.graph-node-picker select').select_option(label='ST-103')
        await page.locator('.node-connections').evaluate("e=>e.scrollIntoView({block:'start'})")
        await page.wait_for_timeout(500)
        shot['caption_split_actual_s']=time.monotonic()-start-shot['start']
        await page.wait_for_timeout(9000)
        await page.screenshot(path=str(folder/'connections.png'))
        shot['end']=time.monotonic()-start;shots.append(shot)
        assert not errors,errors
        await context.close();raw=str(await video.path());await browser.close()
    before=path.parent/'timeline-before-readability.json'
    if not before.exists():before.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    for shot in shots:
        shot['raw']=raw
        index=next(i for i,s in enumerate(meta['scenes']) if s['id']==shot['id'])
        meta['scenes'][index]=shot
    index=next(i for i,s in enumerate(meta['storyboard']) if s[0]=='ontology')
    meta['storyboard'][index][3][1]='냉각수 필터를 선택하면 관련 센서와 정비 문서를 함께 찾을 수 있습니다.'
    meta['readability_retake']={'read_only':True,'raw':raw,'browser_errors':errors,'scenes':['documents','ontology']}
    path.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    (folder/'evidence.json').write_text(json.dumps(meta['readability_retake'],ensure_ascii=False,indent=2),encoding='utf-8')
    print('Document and ontology views re-recorded; no publication, fault, approval or equipment commands.',flush=True)

if __name__=='__main__':
    asyncio.run(main(Path(sys.argv[1]).resolve()))
