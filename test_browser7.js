const { chromium } = require('./apps/crawler-service/node_modules/playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  const apiCalls = [];
  page.on('request', req => {
    const url = req.url();
    if (url.includes('/api/') || url.includes('/msg/') || url.includes('/automation/')) {
      apiCalls.push({ type: 'REQ', method: req.method(), url: url.substring(0, 150) });
    }
  });
  page.on('response', resp => {
    const url = resp.url();
    if (url.includes('/api/') || url.includes('/msg/') || url.includes('/automation/')) {
      apiCalls.push({ type: 'RESP', status: resp.status(), url: url.substring(0, 150) });
    }
  });
  page.on('pageerror', err => console.log('[PAGE ERROR]', err.message.substring(0, 300)));
  page.on('console', msg => {
    if (msg.type() === 'error' || msg.type() === 'warn') {
      console.log('[CONSOLE]', msg.type(), msg.text().substring(0, 200));
    }
  });

  // 1. Login via API to get token
  const loginResult = await fetch('http://localhost:18080/api/login/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'demo', password: '123456' })
  }).then(r => r.json());

  const token = loginResult.data.token;
  console.log('Login OK, token:', token.substring(0, 20) + '...');

  // 2. Set localStorage BEFORE navigating
  await page.goto('http://localhost:5174/', { waitUntil: 'domcontentloaded' });
  await page.evaluate((token) => {
    localStorage.setItem('xianyu_auth_token', token);
    localStorage.setItem('xianyu_username', 'demo');
  }, token);

  // 3. Navigate to messages page (correct hash format: #/messages)
  console.log('\n=== Navigating to #/messages ===');
  await page.goto('http://localhost:5174/#/messages', { waitUntil: 'domcontentloaded' });

  // Wait for app boot + account loading + conversation loading
  console.log('Waiting 15s for page to fully load...');
  await page.waitForTimeout(15000);

  // Check current hash
  const currentHash = await page.evaluate(() => location.hash);
  console.log('Current hash:', currentHash);

  // Print API calls
  console.log('\n=== API Calls ===');
  apiCalls.forEach(call => {
    console.log(`[${call.type}] ${call.status || call.method} ${call.url}`);
  });

  // Check page content
  const pageState = await page.evaluate(() => {
    const convList = document.querySelector('.xya-msg-conversation-list');
    const convItems = document.querySelectorAll('.xya-msg-conversation-item');
    const accountSelect = document.querySelector('select.xya-msg-select');
    const selectedOption = accountSelect?.options?.[accountSelect.selectedIndex];
    const chatHeader = document.querySelector('.xya-msg-chat-header, .xya-msg-chat-panel');
    const emptyState = document.querySelector('.xya-msg-empty');

    // Get all avatar images
    const avatarImgs = Array.from(document.querySelectorAll('.xya-msg-avatar, img[class*="avatar"]')).map(img => ({
      src: img.src || img.dataset?.src || '',
      loaded: img.complete && img.naturalWidth > 0,
    }));

    // Get all goods thumbnail images
    const goodsImgs = Array.from(document.querySelectorAll('.xya-msg-goods-thumb, img[class*="goods"]')).map(img => ({
      src: img.src || img.dataset?.src || '',
      loaded: img.complete && img.naturalWidth > 0,
    }));

    return {
      hash: location.hash,
      hasConvList: !!convList,
      convCount: convItems.length,
      accountSelectText: selectedOption?.text || '',
      accountSelectValue: selectedOption?.value || '',
      hasChatHeader: !!chatHeader,
      hasEmptyState: !!emptyState,
      emptyText: emptyState?.textContent?.trim()?.substring(0, 100) || '',
      avatarImgs,
      goodsImgs,
      bodyText: document.body.innerText.substring(0, 300),
    };
  });

  console.log('\n=== Page State ===');
  console.log(JSON.stringify(pageState, null, 2));

  // Take screenshot
  await page.screenshot({ path: 'g:/源码/xianyu-assistant-package-temp/test_messages_final.png', fullPage: false });
  console.log('\nScreenshot saved: test_messages_final.png');

  // If conversations loaded, click first one to see chat detail
  if (pageState.convCount > 0) {
    console.log('\n=== Clicking first conversation ===');
    await page.click('.xya-msg-conversation-item');
    await page.waitForTimeout(3000);

    const chatState = await page.evaluate(() => {
      const chatHeader = document.querySelector('.xya-msg-chat-header, .xya-msg-chat-panel');
      const headerAvatar = chatHeader?.querySelector('img[class*="avatar"]') || chatHeader?.querySelector('.xya-msg-avatar');
      const headerGoods = chatHeader?.querySelector('.xya-msg-goods-thumb') || chatHeader?.querySelector('img[class*="goods"]');

      return {
        headerText: chatHeader?.innerText?.substring(0, 200) || '',
        headerAvatarSrc: headerAvatar?.src || '',
        headerAvatarLoaded: headerAvatar?.complete && headerAvatar?.naturalWidth > 0,
        headerGoodsSrc: headerGoods?.src || '',
        headerGoodsLoaded: headerGoods?.complete && headerGoods?.naturalWidth > 0,
      };
    });
    console.log('Chat state:', JSON.stringify(chatState, null, 2));

    await page.screenshot({ path: 'g:/源码/xianyu-assistant-package-temp/test_messages_chat.png', fullPage: false });
    console.log('Chat screenshot saved: test_messages_chat.png');
  }

  await browser.close();
  console.log('\n=== Done ===');
})();
