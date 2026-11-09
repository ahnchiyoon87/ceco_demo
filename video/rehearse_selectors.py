"""Read-only rehearsal of film selectors against a stored, real pending plan."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'/'e2e'))
import maintenance_scenarios as M

i=next(x for x in M.api('/api/operations/incidents')['items'] if x['status']=='awaiting_review' and 'thermal' in (x.get('correlation_key') or ''))
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1920,'height':900})
    page.goto('http://localhost:38180',wait_until='networkidle')
    page.add_style_tag(content='.process-flow{position:relative!important;top:auto!important}')
    page.locator('.mfg-nav button').filter(has_text='이상 대응').click()
    page.locator('#case-search').fill(i['id'])
    page.locator('.incident-item').first.click()
    page.locator('.process-flow g[role=button][aria-label^="담당자 검토"]').click()
    page.locator('.plan-card').wait_for(state='visible')
    for name in ['원인 판단','대안 손익 비교','정비 단계','회복 확인 기준']:
        loc=page.locator('.plan-card section:has(h5:text("'+name+'"))').first
        loc.wait_for(state='visible')
        loc.scroll_into_view_if_needed()
        print(name,loc.count(),flush=True)
    page.locator('.review-buttons').scroll_into_view_if_needed()
    page.locator('.proposal-card textarea').fill('화면 검증용 임시 입력 — 제출하지 않음')
    print('approve enabled',page.get_by_role('button',name='승인하고 진행',exact=True).is_enabled(),flush=True)
    page.locator('.proposal-card textarea').fill('')
    browser.close()
