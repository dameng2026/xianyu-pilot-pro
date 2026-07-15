/**
 * 尝试不同的 URL 格式访问商品详情页
 */
import { chromium } from 'playwright';

async function tryUrl(testUrl: string, cookieHeader: string) {
  console.log(`\n========== URL: ${testUrl} ==========`);

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    locale: 'zh-CN',
    timezoneId: 'Asia/Shanghai',
  });

  const cookies: any[] = [];
  for (const part of cookieHeader.split(';')) {
    const trimmed = part.trim();
    if (!trimmed || trimmed.indexOf('=') <= 0) continue;
    const idx = trimmed.indexOf('=');
    const name = trimmed.slice(0, idx).trim();
    const value = trimmed.slice(idx + 1).trim();
    if (name && value) {
      cookies.push({ name, value, domain: '.goofish.com', path: '/', sameSite: 'Lax' });
    }
  }
  if (cookies.length > 0) await context.addCookies(cookies);

  const page = await context.newPage();

  const detailCalls: any[] = [];
  page.on('response', async (response) => {
    const reqUrl = response.url() || '';
    if (!reqUrl.includes('mtop.taobao.idle.pc.detail') && !reqUrl.includes('mtop.idle.web.item') && !reqUrl.includes('mtop.taobao.idle.web.item') && !reqUrl.includes('mtop.idle.item')) return;
    try {
      const text = await response.text();
      const req = response.request();
      const postData = req.postData() || '';
      const apiMatch = reqUrl.match(/mtop\.[a-z0-9.]+/i);
      detailCalls.push({ api: apiMatch?.[0], postData, text });
      console.log(`[拦截] ${apiMatch?.[0]}: postData=${decodeURIComponent(postData).slice(0, 200)}`);
      console.log(`  response: ${text.slice(0, 300)}`);
    } catch {}
  });

  await page.goto(testUrl, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForTimeout(8000);

  const pageState = await page.evaluate(() => {
    const bodyText = document.body.innerText || '';
    return {
      title: document.title,
      hasError: bodyText.includes('网络不见了'),
      bodyTextPreview: bodyText.slice(0, 200),
    };
  });
  console.log(`页面: ${JSON.stringify(pageState)}`);

  await browser.close();
}

async function main() {
  const cookieHeader = process.env.GOOFISH_COOKIE || '';
  if (!cookieHeader) {
    console.error('请设置 GOOFISH_COOKIE');
    process.exit(1);
  }

  const itemId = '1049776111066';
  // 尝试不同的 URL 格式
  const urls = [
    `https://www.goofish.com/item?itemId=${itemId}`,
    `https://www.goofish.com/item?id=${itemId}`,
    `https://www.goofish.com/item/${itemId}`,
    `https://www.goofish.com/item?item_id=${itemId}`,
  ];

  for (const url of urls) {
    try {
      await tryUrl(url, cookieHeader);
    } catch (e: any) {
      console.error(`失败: ${e.message}`);
    }
  }
}

main().catch((e) => {
  console.error('失败:', e);
  process.exit(1);
});
