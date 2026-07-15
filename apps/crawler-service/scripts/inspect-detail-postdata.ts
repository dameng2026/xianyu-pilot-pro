/**
 * 捕获 mtop.taobao.idle.pc.detail 的 POST data，分析参数错误原因
 * 同时尝试不同的 itemId 看是否是个别商品问题
 */
import { chromium } from 'playwright';

async function tryItem(itemId: string, cookieHeader: string) {
  const url = `https://www.goofish.com/item?itemId=${itemId}`;
  console.log(`\n\n========== 尝试 itemId=${itemId} ==========`);
  console.log(`URL: ${url}`);

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

  let detailPostData = '';
  let detailUrl = '';
  let detailText = '';

  page.on('response', async (response) => {
    const reqUrl = response.url() || '';
    if (!reqUrl.includes('mtop.taobao.idle.pc.detail') && !reqUrl.includes('mtop.idle.web.item') && !reqUrl.includes('mtop.taobao.idle.web.item')) return;
    try {
      const text = await response.text();
      const req = response.request();
      const postData = req.postData() || '';
      const apiMatch = reqUrl.match(/mtop\.[a-z0-9.]+/i);
      console.log(`\n[拦截] ${apiMatch?.[0] || 'detail-api'}`);
      console.log(`  URL: ${reqUrl.slice(0, 250)}`);
      console.log(`  POST data (raw): ${postData.slice(0, 600)}`);
      // 解码 URL encoded data
      try {
        const decoded = decodeURIComponent(postData);
        console.log(`  POST data (decoded): ${decoded.slice(0, 600)}`);
      } catch {}
      console.log(`  Response (前 500): ${text.slice(0, 500)}`);
      detailPostData = postData;
      detailUrl = reqUrl;
      detailText = text;
    } catch {}
  });

  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForTimeout(8000);

  // 检查页面是否显示错误
  const pageState = await page.evaluate(() => {
    const bodyText = document.body.innerText || '';
    return {
      title: document.title,
      hasError: bodyText.includes('网络不见了') || bodyText.includes('页面不存在'),
      hasContent: bodyText.includes('远程') || bodyText.includes('安装') || bodyText.includes('软件'),
      bodyTextPreview: bodyText.slice(0, 300),
    };
  });
  console.log(`\n页面状态: ${JSON.stringify(pageState, null, 2)}`);

  await browser.close();
  return { detailPostData, detailUrl, detailText, pageState };
}

async function main() {
  const cookieHeader = process.env.GOOFISH_COOKIE || '';
  if (!cookieHeader) {
    console.error('请设置 GOOFISH_COOKIE 环境变量');
    process.exit(1);
  }

  // 尝试多个 itemId
  const itemIds = (process.env.ITEM_IDS || '1049776111066,1058957265753,1054858262063').split(',');
  for (const itemId of itemIds) {
    try {
      await tryItem(itemId.trim(), cookieHeader);
    } catch (e: any) {
      console.error(`itemId=${itemId} 失败: ${e.message}`);
    }
  }
}

main().catch((e) => {
  console.error('失败:', e);
  process.exit(1);
});
