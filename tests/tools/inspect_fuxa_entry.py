"""Read-only FUXA login form inspection; never prints credentials or tokens."""
import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests'/'e2e'))
import maintenance_scenarios as M

async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch()
  url='http://127.0.0.1:'+M.V.ENV['PORT_FUXA']
  c=await b.new_context(http_credentials={'username':M.V.ENV['HMI_GATE_USER'],'password':M.V.ENV['HMI_GATE_PASSWORD'],'origin':url})
  pg=await c.new_page()
  await pg.goto(url,wait_until='domcontentloaded')
  await pg.wait_for_timeout(2500)
  await pg.locator('button').filter(has_text='account_circle').first.click()
  await pg.wait_for_timeout(500)
  print('Input fields:',await pg.locator('input').evaluate_all("es=>es.map(e=>({type:e.type,placeholder:e.placeholder,name:e.name}))"))
  print('Buttons:',await pg.get_by_role('button').all_text_contents())
  dialog=pg.locator('mat-dialog-container')
  await dialog.locator('input[type="text"]').first.fill('operator')
  await dialog.locator('input[type="password"]').fill(M.V.ENV['FUXA_OPERATOR_PASSWORD'])
  await dialog.get_by_role('button',name='OK',exact=True).click()
  await dialog.wait_for(state='hidden',timeout=15000)
  storage=await c.storage_state()
  print('Operator sign-in succeeded; saved origin count:',len(storage['origins']))
  print('Local storage keys:',[[x['name'] for x in o['localStorage']] for o in storage['origins']])
  await b.close()
asyncio.run(main())
