const { chromium } = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
(async () => {
  const output = path.resolve('D:/work/study/lecture-iiot-scada/docs/ai-work/browser-qa');
  await fs.mkdir(output, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1 });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('http://127.0.0.1:28180/', { waitUntil: 'networkidle' });
    await page.getByRole('heading', { name: '알람 너머, 다음 행동까지.' }).waitFor();
    await page.screenshot({ path: path.join(output, 'operations-initial.png'), fullPage: true });
    const controls = await page.getByRole('button').evaluateAll(nodes => nodes.map(n => ({ text: n.innerText, label: n.getAttribute('aria-label'), title: n.title })));
    await fs.writeFile(path.join(output,'initial-inspection.json'),JSON.stringify({url:page.url(),title:await page.title(),errors,controls},null,2));
    console.log(JSON.stringify({title:await page.title(),errors,screenshot:path.join(output,'operations-initial.png'),controls:controls.slice(0,7)}));
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode=1; });
