const { chromium } = require('./apps/crawler-service/node_modules/playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  page.on('console', msg => {
    const text = msg.text();
    if (text.includes('[vite]')) return;
    console.log('[BROWSER]', msg.type(), text.substring(0, 300));
  });
  page.on('pageerror', err => console.log('[PAGE ERROR]', err.message.substring(0, 300)));
  page.on('requestfailed', req => {
    if (req.url().includes('/api/')) {
      console.log('[REQ FAIL]', req.url().substring(0, 120), req.failure()?.errorText);
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

  // 2. Set localStorage then navigate using hash
  await page.goto('http://localhost:5174/', { waitUntil: 'domcontentloaded' });
  await page.evaluate((token) => {
    localStorage.setItem('xianyu_auth_token', token);
    localStorage.setItem('xianyu_username', 'demo');
  }, token);

  // 3. Navigate to messages page using hash
  console.log('=== Navigating to messages page ===');
  await page.goto('http://localhost:5174/#/messages?xianyuAccountId=1', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(10000);

  console.log('URL:', page.url());

  // 4. Take screenshot
  await page.screenshot({ path: 'g:/源码/xianyu-assistant-package-temp/test_messages_1.png', fullPage: false });
  console.log('Screenshot 1 saved');

  // 5. Check conversations
  const conversations = await page.$$eval('.xya-msg-conversation', items => {
    return items.slice(0, 10).map(item => {
      const avatarImg = item.querySelector('.xya-msg-avatar-wrap img.avatar-image');
      const avatarDiv = item.querySelector('.xya-msg-avatar:not(.avatar-image)');
      const goodsThumb = item.querySelector('.xya-msg-goods-thumb');
      const goodsText = item.querySelector('.xya-msg-goods-text');
      const nameEl = item.querySelector('.xya-msg-conversation-top strong');
      return {
        name: nameEl?.textContent?.trim() || '',
        hasAvatarImg: !!avatarImg,
        avatarSrc: avatarImg?.src?.substring(0, 80) || '',
        hasAvatarFallback: !!avatarDiv,
        hasGoodsThumb: !!goodsThumb,
        goodsThumbSrc: goodsThumb?.src?.substring(0, 80) || '',
        goodsText: goodsText?.textContent?.trim()?.substring(0, 30) || '',
      };
    });
  });

  console.log('\n=== Conversation List (' + conversations.length + ' items) ===');
  conversations.forEach((c, i) => {
    console.log(`[${i}] name="${c.name}" avatarImg=${c.hasAvatarImg ? 'Y' : 'N'} src=${c.avatarSrc} fallback=${c.hasAvatarFallback ? 'Y' : 'N'} goodsThumb=${c.hasGoodsThumb ? 'Y' : 'N'} src=${c.goodsThumbSrc} text="${c.goodsText}"`);
  });

  // 6. Check empty states
  const emptyState = await page.$('.xya-msg-empty');
  if (emptyState) {
    console.log('Empty state:', (await emptyState.textContent()).trim());
  }

  // 7. Wait for avatar fetch and IM refresh
  console.log('\n=== Waiting 15s for avatar fetch and IM refresh ===');
  await page.waitForTimeout(15000);

  // 8. Reload
  console.log('=== Reloading page ===');
  await page.goto('http://localhost:5174/#/messages?xianyuAccountId=1', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(10000);

  // 9. Final screenshot
  await page.screenshot({ path: 'g:/源码/xianyu-assistant-package-temp/test_messages_2.png', fullPage: false });

  // 10. Final check
  const conversations2 = await page.$$eval('.xya-msg-conversation', items => {
    return items.slice(0, 10).map(item => {
      const avatarImg = item.querySelector('.xya-msg-avatar-wrap img.avatar-image');
      const goodsThumb = item.querySelector('.xya-msg-goods-thumb');
      const nameEl = item.querySelector('.xya-msg-conversation-top strong');
      return {
        name: nameEl?.textContent?.trim() || '',
        hasAvatarImg: !!avatarImg,
        avatarSrc: avatarImg?.src?.substring(0, 80) || '',
        hasGoodsThumb: !!goodsThumb,
        goodsThumbSrc: goodsThumb?.src?.substring(0, 80) || '',
      };
    });
  });
  console.log('\n=== After Reload (' + conversations2.length + ' items) ===');
  conversations2.forEach((c, i) => {
    console.log(`[${i}] name="${c.name}" avatar=${c.hasAvatarImg ? 'Y' : 'N'} src=${c.avatarSrc} goodsThumb=${c.hasGoodsThumb ? 'Y' : 'N'} src=${c.goodsThumbSrc}`);
  });

  // Also check chat header if a conversation is selected
  const chatHeadAvatar = await page.$('.xya-msg-chat-head img.avatar-image');
  const chatHeadGoodsThumb = await page.$('.xya-msg-chat-head .xya-msg-goods-thumb');
  console.log('\nChat header: avatar=' + (chatHeadAvatar ? 'Y' : 'N') + ' goodsThumb=' + (chatHeadGoodsThumb ? 'Y' : 'N'));

  await browser.close();
})();
