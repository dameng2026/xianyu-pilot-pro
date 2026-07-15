const { chromium } = require('./apps/crawler-service/node_modules/playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  page.on('console', msg => console.log('[BROWSER]', msg.type(), msg.text().substring(0, 300)));
  page.on('pageerror', err => console.log('[PAGE ERROR]', err.message.substring(0, 300)));

  // 1. Login via API
  console.log('=== Login via API ===');
  const loginResult = await fetch('http://localhost:18080/api/login/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'demo', password: '123456' })
  }).then(r => r.json()).catch(e => { console.log('Login error:', e.message); return null; });

  if (!loginResult || !loginResult.data?.token) {
    console.log('Login failed!', JSON.stringify(loginResult).substring(0, 200));
    await browser.close();
    return;
  }

  const token = loginResult.data.token;
  const userId = String(loginResult.data.userId);
  const tenantId = String(loginResult.data.tenantId);
  console.log('Login OK, token:', token.substring(0, 30) + '...');

  // 2. Set localStorage then navigate
  await page.goto('http://localhost:5174/', { waitUntil: 'domcontentloaded' });
  await page.evaluate(({ token, userId, tenantId }) => {
    localStorage.setItem('xianyu_auth_token', token);
    localStorage.setItem('xianyu_username', 'demo');
  }, { token, userId, tenantId });

  // 3. Navigate to messages page
  console.log('\n=== Navigating to messages page ===');
  await page.goto('http://localhost:5174/messages?xianyuAccountId=1', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(10000);

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

  // 7. Wait for avatar fetch
  console.log('\n=== Waiting 12s for avatar fetch ===');
  await page.waitForTimeout(12000);

  // 8. Reload to get fresh data (cache expired)
  console.log('=== Reloading page ===');
  await page.reload({ waitUntil: 'domcontentloaded' });
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

  await browser.close();
})();
