const { chromium } = require('./apps/crawler-service/node_modules/playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  // Monitor ALL network requests
  page.on('request', req => {
    const url = req.url();
    if (url.includes('/api/') || url.includes('/msg/') || url.includes('/automation/')) {
      console.log('[REQ]', req.method(), url.substring(0, 120));
    }
  });
  page.on('response', resp => {
    const url = resp.url();
    if (url.includes('/api/') || url.includes('/msg/') || url.includes('/automation/')) {
      console.log('[RESP]', resp.status(), url.substring(0, 120));
    }
  });
  page.on('pageerror', err => console.log('[PAGE ERROR]', err.message.substring(0, 300)));

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
  console.log('\n=== Navigating to messages page ===');
  await page.goto('http://localhost:5174/#/messages?xianyuAccountId=1', { waitUntil: 'domcontentloaded' });

  // Wait and collect network requests
  await page.waitForTimeout(12000);

  // Check page content
  const bodyText = await page.evaluate(() => {
    const main = document.querySelector('.xya-msg-conversation-list, .xya-msg-empty, .xya-msg-chat-panel, main, #app');
    return main ? main.innerText.substring(0, 500) : document.body.innerText.substring(0, 500);
  });
  console.log('\nPage content:', bodyText);

  // Check what page is actually showing
  const currentPage = await page.evaluate(() => location.hash);
  console.log('Current hash:', currentPage);

  // Check for MessagesPage elements
  const msgElements = await page.$$eval('[class*="xya-msg"], [class*="messages"]', els =>
    els.slice(0, 10).map(e => ({ class: e.className?.substring(0, 60), text: e.textContent?.trim()?.substring(0, 40) }))
  );
  console.log('Message elements:', JSON.stringify(msgElements, null, 2));

  // Check for accounts loaded
  const accountSelect = await page.$('select, .account-select, [class*="account"]');
  if (accountSelect) {
    const text = await accountSelect.textContent();
    console.log('Account selector:', text.trim().substring(0, 100));
  }

  // Screenshot
  await page.screenshot({ path: 'g:/源码/xianyu-assistant-package-temp/test_debug2.png', fullPage: false });

  await browser.close();
})();
