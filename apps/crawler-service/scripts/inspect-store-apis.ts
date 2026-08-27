/**
 * 诊断脚本：打开店铺页，记录所有 MTOP API 响应，
 * 重点找到包含商品列表（含描述）的 API
 */
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';

async function main() {
  // 诊断脚本：默认使用示例店铺 URL / 商品 ID，实际使用请通过环境变量传入（或替换为自有店铺数据）
  const storeUrl = process.env.STORE_URL || 'https://www.goofish.com/personal?userId=2218000000000';
  const itemId = process.env.ITEM_ID || '8000000000000000';

  const cookieHeader = process.env.GOOFISH_COOKIE || '';
  if (!cookieHeader) {
    console.error('请设置 GOOFISH_COOKIE 环境变量');
    process.exit(1);
  }
  console.log(`Cookie 长度: ${cookieHeader.length}`);
  console.log(`店铺 URL: ${storeUrl}`);

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    locale: 'zh-CN',
    timezoneId: 'Asia/Shanghai',
  });

  // 注入 Cookie
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
  if (cookies.length > 0) {
    await context.addCookies(cookies);
    console.log(`已注入 ${cookies.length} 个 Cookie`);
  }

  const page = await context.newPage();

  // 记录所有 MTOP API 响应
  const allMtopResps: Array<{
    apiName: string;
    url: string;
    method: string;
    postData: string;
    textLength: number;
    textPreview: string;
    fullText?: string;
  }> = [];

  page.on('response', async (response) => {
    const reqUrl = response.url() || '';
    if (!reqUrl.includes('mtop')) return;
    try {
      const ct = response.headers()['content-type'] || '';
      if (!/json|text/i.test(ct)) return;
      const text = await response.text();
      if (!text || text.length < 80) return;

      const apiMatch = reqUrl.match(/mtop\.[a-z0-9.]+/i);
      const apiName = apiMatch?.[0] || 'unknown';
      const req = response.request();
      const method = req.method();
      let postData = '';
      try { postData = req.postData() || ''; } catch {}

      const entry = {
        apiName,
        url: reqUrl.slice(0, 300),
        method,
        postData: postData.slice(0, 500),
        textLength: text.length,
        textPreview: text.slice(0, 400),
      };
      allMtopResps.push(entry);

      // 如果响应包含 resultList 或 itemList，保存完整内容
      if (/resultList|itemList|item_list|cardList|"desc"|"description"|exContent/i.test(text)) {
        (entry as any).fullText = text.slice(0, 8000);
        console.log(`[拦截] ${apiName} (len=${text.length}) - 含商品列表/描述字段`);
      } else {
        console.log(`[拦截] ${apiName} (len=${text.length})`);
      }
    } catch {}
  });

  console.log(`\n访问店铺页: ${storeUrl}`);
  await page.goto(storeUrl, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForTimeout(5000);

  // 点击"宝贝"/"商品"tab
  console.log('\n尝试点击"宝贝"tab...');
  const tabSelectors = ['text=宝贝', 'text=商品', 'text=在售', '[role="tab"]:has-text("宝贝")', '[role="tab"]:has-text("商品")'];
  for (const sel of tabSelectors) {
    try {
      const loc = page.locator(sel).first();
      if (await loc.count()) {
        await loc.click({ timeout: 2000 });
        console.log(`  点击成功: ${sel}`);
        await page.waitForTimeout(2000);
        break;
      }
    } catch {}
  }

  // 滚动触发商品列表加载
  console.log('\n滚动页面触发商品加载...');
  for (let i = 0; i < 6; i++) {
    await page.evaluate(() => window.scrollBy(0, 800));
    await page.waitForTimeout(1200);
  }

  await page.waitForTimeout(2000);

  // 输出统计
  console.log(`\n\n========================================`);
  console.log(`=== 共拦截到 ${allMtopResps.length} 个 MTOP 响应 ===`);
  console.log(`========================================\n`);

  const apiCounts: Record<string, number> = {};
  for (const r of allMtopResps) {
    apiCounts[r.apiName] = (apiCounts[r.apiName] || 0) + 1;
  }
  console.log('API 调用统计:');
  for (const [api, cnt] of Object.entries(apiCounts).sort((a, b) => b[1] - a[1])) {
    console.log(`  ${api}: ${cnt} 次`);
  }

  // 输出所有含商品列表/描述的响应详情
  console.log(`\n\n========================================`);
  console.log(`=== 含商品列表/描述字段的响应详情 ===`);
  console.log(`========================================`);
  for (const r of allMtopResps) {
    if (!(r as any).fullText) continue;
    console.log(`\n--- API: ${r.apiName} ---`);
    console.log(`URL: ${r.url}`);
    console.log(`Method: ${r.method}`);
    console.log(`POST data: ${r.postData}`);
    console.log(`Text length: ${r.textLength}`);
    console.log(`Full text (前 6000 字符):`);
    console.log((r as any).fullText.slice(0, 6000));
    console.log('');
  }

  // 保存完整数据到文件
  writeFileSync('scripts/_mtop_dump.json', JSON.stringify(allMtopResps, null, 2));
  console.log('\n完整数据已保存到 scripts/_mtop_dump.json');

  // 同时获取 DOM 结构分析
  console.log('\n\n========================================');
  console.log(`=== DOM 商品卡片结构分析 ===`);
  console.log(`========================================`);
  const domAnalysis = await page.evaluate(() => {
    const results: any[] = [];
    const anchors = Array.from(document.querySelectorAll('a[href]')) as HTMLAnchorElement[];
    let idx = 0;
    for (const a of anchors) {
      const href = a.href || '';
      if (!/goofish\.com\/item|\/item\?|[?&]id=\d{6,}/i.test(href)) continue;
      const container = (a.closest('[class*="item" i], [class*="card" i], [class*="goods" i], li, div') || a) as HTMLElement;
      const text = (container.innerText || '').replace(/\s+/g, ' ').trim();
      // 输出容器内所有子元素的结构
      const children: any[] = [];
      const walk = (el: Element, depth: number) => {
        if (depth > 3) return;
        const cs = window.getComputedStyle(el);
        children.push({
          tag: el.tagName,
          class: (el as HTMLElement).className || '',
          text: (el.textContent || '').slice(0, 80),
          rect: el.getBoundingClientRect ? {
            w: Math.round(el.getBoundingClientRect().width),
            h: Math.round(el.getBoundingClientRect().height),
          } : null,
        });
        for (let i = 0; i < Math.min(el.children.length, 8); i++) {
          walk(el.children[i], depth + 1);
        }
      };
      if (container.children.length > 0) {
        for (let i = 0; i < Math.min(container.children.length, 5); i++) {
          walk(container.children[i], 0);
        }
      }
      results.push({
        idx: idx++,
        href,
        containerText: text.slice(0, 200),
        containerClass: container.className || '',
        childrenCount: container.children.length,
        children,
      });
      if (results.length >= 2) break; // 只分析前 2 个卡片
    }
    return results;
  });
  console.log(JSON.stringify(domAnalysis, null, 2));

  await browser.close();
  console.log('\n浏览器已关闭');
}

main().catch((e) => {
  console.error('失败:', e);
  process.exit(1);
});
