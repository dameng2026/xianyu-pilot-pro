const { chromium } = require('./apps/crawler-service/node_modules/playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  // 1. Login
  console.log('=== Logging in ===');
  await page.goto('http://localhost:5174/login', { waitUntil: 'networkidle' });
  await page.fill('input[type="text"], input[placeholder*="用户"], input[name="username"]', 'demo');
  await page.fill('input[type="password"]', '123456');
  await page.click('button[type="submit"], button:has-text("登录")');
  await page.waitForTimeout(3000);

  // 2. Navigate to messages page
  console.log('=== Navigating to messages page ===');
  await page.goto('http://localhost:5174/messages?xianyuAccountId=1', { waitUntil: 'networkidle' });
  await page.waitForTimeout(5000);

  // 3. Take screenshot
  await page.screenshot({ path: 'g:/源码/xianyu-assistant-package-temp/test_messages_page.png', fullPage: false });
  console.log('Screenshot saved to test_messages_page.png');

  // 4. Check conversation list items
  const conversations = await page.$$eval('.xya-msg-conversation', items => {
    return items.slice(0, 10).map(item => {
      const avatarImg = item.querySelector('.xya-msg-avatar-wrap img');
      const avatarDiv = item.querySelector('.xya-msg-avatar:not(.avatar-image)');
      const goodsThumb = item.querySelector('.xya-msg-goods-thumb');
      const goodsText = item.querySelector('.xya-msg-goods-text');
      const nameEl = item.querySelector('.xya-msg-conversation-top strong');
      return {
        name: nameEl?.textContent?.trim() || '',
        hasAvatarImg: !!avatarImg,
        avatarSrc: avatarImg?.src?.substring(0, 60) || '',
        hasAvatarFallback: !!avatarDiv,
        hasGoodsThumb: !!goodsThumb,
        goodsThumbSrc: goodsThumb?.src?.substring(0, 60) || '',
        goodsText: goodsText?.textContent?.trim()?.substring(0, 30) || '',
      };
    });
  });

  console.log('\n=== Conversation List Items ===');
  conversations.forEach((c, i) => {
    console.log(`[${i}] name="${c.name}" avatarImg=${c.hasAvatarImg} src=${c.avatarSrc} fallback=${c.hasAvatarFallback} goodsThumb=${c.hasGoodsThumb} src=${c.goodsThumbSrc} text="${c.goodsText}"`);
  });

  // 5. Check network requests for avatars
  const avatarRequests = [];
  page.on('request', req => {
    if (req.url().includes('/msg/avatars')) avatarRequests.push(req.url());
  });

  // Wait for potential avatar fetch
  await page.waitForTimeout(5000);

  // 6. Take final screenshot after avatar fetch
  await page.screenshot({ path: 'g:/源码/xianyu-assistant-package-temp/test_messages_after.png', fullPage: false });
  console.log('\nFinal screenshot saved');

  // 7. Re-check conversations after avatar fetch
  const conversations2 = await page.$$eval('.xya-msg-conversation', items => {
    return items.slice(0, 10).map(item => {
      const avatarImg = item.querySelector('.xya-msg-avatar-wrap img');
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
  console.log('\n=== After Avatar Fetch ===');
  conversations2.forEach((c, i) => {
    console.log(`[${i}] name="${c.name}" avatar=${c.hasAvatarImg ? 'YES' : 'NO'} src=${c.avatarSrc} goodsThumb=${c.hasGoodsThumb ? 'YES' : 'NO'} src=${c.goodsThumbSrc}`);
  });

  await browser.close();
})();
