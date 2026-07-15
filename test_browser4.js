const { chromium } = require('./apps/crawler-service/node_modules/playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  page.on('console', msg => {
    const text = msg.text();
    if (text.includes('[vite]')) return; // skip vite noise
    console.log('[BROWSER]', msg.type(), text.substring(0, 300));
  });
  page.on('pageerror', err => console.log('[PAGE ERROR]', err.message.substring(0, 300)));
  page.on('requestfailed', req => {
    if (req.url().includes('/api/')) {
      console.log('[REQ FAIL]', req.url().substring(0, 100), req.failure()?.errorText);
    }
  });

  // 1. Login
  const loginResult = await fetch('http://localhost:18080/api/login/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'demo', password: '123456' })
  }).then(r => r.json());

  const token = loginResult.data.token;
  console.log('Login OK');

  // 2. Set localStorage
  await page.goto('http://localhost:5174/', { waitUntil: 'domcontentloaded' });
  await page.evaluate((token) => {
    localStorage.setItem('xianyu_auth_token', token);
    localStorage.setItem('xianyu_username', 'demo');
  }, token);

  // 3. Navigate to messages
  await page.goto('http://localhost:5174/messages?xianyuAccountId=1', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(8000);

  // Check current URL
  console.log('URL:', page.url());

  // Check page title and body text
  const bodyText = await page.evaluate(() => document.body.innerText.substring(0, 500));
  console.log('Body text:', bodyText);

  // Check for any visible elements
  const allElements = await page.$$eval('button, .xya-msg-empty, .xya-msg-conversation, h1, h2, h3', els =>
    els.slice(0, 15).map(e => ({ tag: e.tagName, class: e.className?.substring(0, 50), text: e.textContent?.trim()?.substring(0, 50) }))
  );
  console.log('Visible elements:', JSON.stringify(allElements, null, 2));

  // Take screenshot
  await page.screenshot({ path: 'g:/源码/xianyu-assistant-package-temp/test_debug.png', fullPage: false });

  await browser.close();
})();
