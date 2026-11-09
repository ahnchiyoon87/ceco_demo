"""Read-only desktop/mobile layout and single-address portal checks."""
import asyncio
import json
import re
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'experiments' / 'BOOTH-20261013' / 'guided-ui'
OUT.mkdir(parents=True, exist_ok=True)


async def main():
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for width, height in [(1920,1080),(1280,800),(375,812)]:
            page = await browser.new_page(viewport={'width':width,'height':height}, locale='ko-KR')
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            await page.goto('http://localhost:38180',wait_until='domcontentloaded')
            await page.get_by_role('button',name='이상 발생',exact=True).wait_for()
            await page.wait_for_timeout(2000)
            assert await page.locator('#simulation-scenario option').count()==6
            assert await page.locator('.process-flow g.step').count()==5
            assert await page.locator('.process-flow [role=button]').count()==0
            assert await page.locator('.process-flow').evaluate('e=>e.closest("details")===null')
            for label in ['프로세스 보기','현재 처리 단계 보기','기록 갱신','기록 새로고침','AI 분석 · 대응안 작성']:
                assert await page.get_by_role('button',name=label,exact=True).count()==0,label
            assert await page.get_by_role('button',name='정비 승인',exact=True).count()<=1
            body=await page.locator('body').inner_text()
            assert 'gpt-6' not in body and '교육용' not in body and '강사' not in body
            assert await page.locator('.key-readings article').count()==6
            dimensions=await page.evaluate('''() => ({viewport:innerWidth,body:document.body.scrollWidth,root:document.getElementById('app').scrollWidth})''')
            assert dimensions['body']<=width and dimensions['root']<=width,dimensions
            await page.screenshot(path=str(OUT/f'equipment-{width}.png'))
            await page.locator('.process-flow').wait_for()
            assert page.url=='http://localhost:38180/'
            await page.screenshot(path=str(OUT/f'dashboard-{width}.png'))
            assert await page.locator('.portal-sidebar nav button').count()==4
            for label in ['온톨로지','문서·지식','처리 이력','운영 현황']:
                await page.locator('.portal-sidebar').get_by_role('button',name=label,exact=True).click()
                await page.wait_for_timeout(500)
                assert await page.locator('.portal-sidebar button[aria-current=page]').inner_text()==label
                sizes=await page.evaluate('({body:document.body.scrollWidth,root:document.getElementById("app").scrollWidth})')
                assert sizes['body']<=width and sizes['root']<=width,(label,sizes)
            assert await page.locator('.process-flow').is_visible()
            await page.screenshot(path=str(OUT/f'restored-menu-{width}.png'))

            assert not errors, errors
            results.append({'width':width,'height':height,'no_horizontal_overflow':True,'native_fault_options':6,'key_readings':6,'single_entry_url':page.url,'always_visible_process':True,'normal_manual_analysis_buttons':0,'browser_errors':errors})
            await page.close()
        await browser.close()
    (OUT/'result.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(results,ensure_ascii=False,indent=2))


asyncio.run(main())
