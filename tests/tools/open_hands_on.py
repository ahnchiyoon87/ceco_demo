"""Open one visible portal for the user's interaction.

Does not inject a fault, reset the plant, approve a plan, or delete history.
The portal connects the operator panel itself; no special browser login is needed.
Close the browser window to stop this helper.
"""
import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests' / 'e2e'))
import maintenance_scenarios as M


async def main():
    dashboard = 'http://localhost:' + M.V.ENV.get('PORT_AI_WEB', '38180')
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=['--start-maximized'])
        context = await browser.new_context(no_viewport=True, locale='ko-KR', timezone_id='Asia/Seoul')
        ai = await context.new_page()
        await ai.goto(dashboard, wait_until='domcontentloaded')
        await ai.get_by_role('button', name='이상 발생', exact=True).wait_for()
        await ai.bring_to_front()
        print('READY: one visible portal, equipment and dashboard tabs; no fault or approval performed.', flush=True)
        closed = asyncio.Event()
        browser.on('disconnected', lambda _: closed.set())
        await closed.wait()


if __name__ == '__main__':
    asyncio.run(main())
