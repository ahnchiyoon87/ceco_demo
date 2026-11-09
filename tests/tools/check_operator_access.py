"""Read-only fresh-browser check of portal FUXA access; never saves tokens."""
import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests' / 'e2e'))
import maintenance_scenarios as M

async def main():
    portal = 'http://localhost:' + M.V.ENV['PORT_AI_WEB']
    dest = ROOT / 'experiments' / 'BOOTH-20261013' / 'operator-access'
    dest.mkdir(parents=True, exist_ok=True)
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for width, height in [(1920, 1080), (1280, 800), (375, 812)]:
            context = await browser.new_context(viewport={'width': width, 'height': height}, locale='ko-KR')
            page = await context.new_page()
            errors, failures, sockets = [], [], []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('response', lambda r: failures.append({'status': r.status, 'path': urlsplit(r.url).path}) if r.status >= 400 else None)
            def socket_open(socket):
                entry = {'path': urlsplit(socket.url).path, 'messages': 0}
                sockets.append(entry)
                socket.on('framereceived', lambda _: entry.update(messages=entry['messages'] + 1))
            page.on('websocket', socket_open)
            await page.goto(portal, wait_until='domcontentloaded')
            assert await page.evaluate('sessionStorage.getItem("currentUser")') is None
            await page.get_by_role('button', name='설비 제어 패널', exact=True).click()
            frame = page.frame_locator('iframe[title="가상 설비 제어 화면"]')
            await frame.get_by_text('02 운전원 조작', exact=True).wait_for(timeout=20000)
            first = await frame.locator('body').inner_text()
            for _ in range(12):
                await page.wait_for_timeout(1000)
                latest = await frame.locator('body').inner_text()
                if latest != first and any(x['messages'] > 3 for x in sockets):
                    break
            assert latest != first, 'Live sensor values did not change'
            assert any(x['path'] == '/operator/socket.io/' and x['messages'] > 3 for x in sockets)
            user = await page.evaluate('()=>{const u=JSON.parse(sessionStorage.currentUser);return {username:u.username,groups:u.groups,hasToken:!!u.token}}')
            assert user == {'username': 'operator', 'groups': 2, 'hasToken': True}
            assert await frame.locator('input[type="password"]').count() == 0
            assert not errors and not failures
            assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            await page.screenshot(path=str(dest / f'panel-{width}.png'))
            await page.get_by_role('button', name='닫고 설비로 돌아가기', exact=True).click()
            assert await page.locator('iframe').count() == 0
            # Reopening replaces an expired/stale session without showing login.
            await page.evaluate('sessionStorage.setItem("currentUser",JSON.stringify({username:"operator",groups:2,token:"expired-session"}))')
            await page.get_by_role('button', name='설비 제어 패널', exact=True).click()
            await frame.get_by_text('02 운전원 조작', exact=True).wait_for(timeout=20000)
            assert await page.evaluate('JSON.parse(sessionStorage.currentUser).token !== "expired-session"')
            await page.get_by_role('button', name='닫고 설비로 돌아가기', exact=True).click()
            if width == 1920:
                async def fail_session(route):
                    await route.fulfill(status=503, content_type='application/json', body=json.dumps({'detail': '제어 패널에 연결하지 못했습니다. 잠시 후 다시 연결해 주세요.'}))
                await page.route('**/simulation/operator-session', fail_session)
                await page.get_by_role('button', name='설비 제어 패널', exact=True).click()
                await page.get_by_role('alert').wait_for()
                assert await page.locator('iframe').count() == 0
                await page.unroute('**/simulation/operator-session', fail_session)
                await page.get_by_role('button', name='다시 연결', exact=True).click()
                await frame.get_by_text('02 운전원 조작', exact=True).wait_for(timeout=20000)
                failures[:] = [x for x in failures if x['status'] != 503]  # The intentional outage above.
            assert not failures and not errors
            results.append({'viewport': width, 'fresh_browser_no_credentials': True, 'role': user,
                            'live_readings_changed': True, 'sockets': sockets,
                            'reopen_expired_session': True, 'javascript_errors': len(errors)})
            await context.close()
        # The separate internal service still requires its existing host gate.
        request = await p.request.new_context()
        raw = await request.get('http://127.0.0.1:' + M.V.ENV['PORT_FUXA'])
        assert raw.status == 401
        denied = await request.post(portal + '/simulation/operator-session', headers={'Origin': 'http://other.example', 'X-CECO-Portal': 'interactive'}, data={})
        assert denied.status == 403
        html = await request.get(portal + '/operator/')
        assert '<base href="/operator/">' in await html.text()
        await request.dispose()
        await browser.close()
    result = {'passed': True, 'cases': results, 'raw_gate_status': raw.status,
              'cross_origin_session_status': denied.status, 'equipment_commands_sent': 0,
              'connection_failure_retry': True}
    (dest / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    asyncio.run(main())
