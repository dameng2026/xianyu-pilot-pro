const { chromium } = require('./apps/crawler-service/node_modules/playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  // Capture console messages
  page.on('console', msg => console.log('[BROWSER]', msg.type(), msg.text().substring(0, 200)));
  page.on('pageerror', err => console.log('[PAGE ERROR]', err.message.substring(0, 200)));

  // 1. Login via API directly (more reliable)
  console.log('=== Login via API ===');
  const loginResp = await page.evaluate(async () => {
    const res = await fetch('/api/login/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'demo', password: '123456' })
    });
    return res.json();
  });
  console.log('Login response:', JSON.stringify(loginResp).substring(0, 200));

  if (loginResp?.data?.token) {
    localStorage.setItem('token', loginResp.data.token);
    localStorage.setItem('userId', String(loginResp.data.userId));
    localStorage.setItem('tenantId', String(loginResp.data.tenantId));
  }

  // 2. Navigate to messages page
  console.log('\n=== Navigating to messages page ===');
  await page.goto('http://localhost:5174/messages?xianyuAccountId=1', { waitUntil: 'networkidle' });

  // Wait for conversations to load
  await page.waitForTimeout(8000);

  // 3. Take screenshot
  await page.screenshot({ path: 'g:/源码/xianyu-assistant-package-temp/test_messages_page.png', fullPage: false });
  console.log('Screenshot saved');

  // 4. Check page URL and content
  const url = page.url();
  console.log('Current URL:', url);

  // 5. Check conversation list items
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

  console.log('\n=== Conversation List Items (' + conversations.length + ' total) ===');
  conversations.forEach((c, i) => {
    console.log(`[${i}] name="${c.name}" avatarImg=${c.hasAvatarImg} src=${c.avatarSrc} fallback=${c.hasAvatarFallback} goodsThumb=${c.hasGoodsThumb} src=${c.goodsThumbSrc} text="${c.goodsText}"`);
  });

  // 6. Check if there are any empty states
  const emptyState = await page.$('.xya-msg-empty');
  if (emptyState) {
    const text = await emptyState.textContent();
    console.log('\nEmpty state:', text.trim());
  }

  // 7. Wait more for avatar fetch and IM refresh
  console.log('\n=== Waiting 10s for avatar fetch and IM refresh ===');
  await page.waitForTimeout(10000);

  // 8. Take final screenshot
  await page.screenshot({ path: 'g:/源码/xianyu-assistant-package-temp/test_messages_after.png', fullPage: false });

  // 9. Re-check
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
  console.log('\n=== After Wait (' + conversations2.length + ' total) ===');
  conversations2.forEach((c, i) => {
    console.log(`[${i}] name="${c.name}" avatar=${c.hasAvatarImg ? 'YES' : 'NO'} src=${c.avatarSrc} goodsThumb=${c.hasGoodsThumb ? 'YES' : 'NO'} src=${c.goodsThumbSrc}`);
  });

  await browser.close();
})();
