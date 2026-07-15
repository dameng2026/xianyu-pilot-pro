/**
 * 打开商品详情页，拦截所有 MTOP 响应并提取描述字段，
 * 同时从 DOM 提取商品文案，找到真实描述的来源
 */
import { chromium } from 'playwright';

async function main() {
  const itemId = process.env.ITEM_ID || '1049776111066';
  const url = `https://www.goofish.com/item?itemId=${itemId}`;

  const cookieHeader = process.env.GOOFISH_COOKIE || '';
  if (!cookieHeader) {
    console.error('请设置 GOOFISH_COOKIE 环境变量');
    process.exit(1);
  }
  console.log(`商品详情页: ${url}`);

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
  if (cookies.length > 0) {
    await context.addCookies(cookies);
    console.log(`已注入 ${cookies.length} 个 Cookie`);
  }

  const page = await context.newPage();

  const mtopResps: Array<{ apiName: string; url: string; text: string }> = [];
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
      mtopResps.push({ apiName, url: reqUrl, text });
    } catch {}
  });

  console.log(`访问: ${url}`);
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForTimeout(8000);

  // 滚动触发详情加载
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(3000);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(2000);

  // 从 DOM 提取描述
  console.log('\n=== DOM 商品描述提取 ===');
  const domInfo = await page.evaluate(() => {
    const result: any = {};
    const title = document.title || '';
    result['document.title'] = title;

    // 找标题元素
    const titleEls = document.querySelectorAll('h1, h2, [class*="title" i]');
    for (let i = 0; i < Math.min(titleEls.length, 5); i++) {
      const el = titleEls[i] as HTMLElement;
      const t = (el.innerText || el.textContent || '').trim();
      if (t && t.length > 2 && t.length < 200) {
        result[`title_${i}_${el.tagName}_${(el as HTMLElement).className}`] = t;
      }
    }

    // 找描述/详情元素
    const descEls = document.querySelectorAll('[class*="desc" i], [class*="detail" i], [class*="content" i], [class*="item-desc" i], [class*="item-info" i]');
    let descIdx = 0;
    for (const el of Array.from(descEls)) {
      const t = ((el as HTMLElement).innerText || '').trim();
      if (t.length > 30 && t.length < 3000) {
        result[`desc_${descIdx++}_${(el as HTMLElement).className}`] = t.slice(0, 500);
        if (descIdx >= 10) break;
      }
    }

    // 找含关键词的长文本
    const allEls = document.querySelectorAll('div, p, span, section');
    let kwIdx = 0;
    for (const el of Array.from(allEls)) {
      const t = ((el as HTMLElement).innerText || '').trim();
      if (t.length > 60 && t.length < 2000 && /安装|远程|版本|发货|系统|拍下|软件|提供|服务|支持|注/.test(t)) {
        // 排除导航/footer 等通用文本
        if (!/关注|粉丝|评价|动态|首页|个人主页|满意度/.test(t)) {
          result[`kw_${kwIdx++}_${(el as HTMLElement).className}`] = t.slice(0, 500);
          if (kwIdx >= 15) break;
        }
      }
    }
    return result;
  });
  for (const [k, v] of Object.entries(domInfo)) {
    console.log(`  [${k}]: ${(v as string).slice(0, 200)}`);
  }

  // 统计 MTOP API
  console.log(`\n=== 拦截到 ${mtopResps.length} 个 MTOP 响应 ===`);
  const apiCounts: Record<string, number> = {};
  for (const r of mtopResps) {
    apiCounts[r.apiName] = (apiCounts[r.apiName] || 0) + 1;
  }
  for (const [api, cnt] of Object.entries(apiCounts).sort((a, b) => b[1] - a[1])) {
    console.log(`  ${api}: ${cnt} 次`);
  }

  // 查找含 desc/description/detail 字段的响应
  console.log('\n=== 含 desc/description/detail 的 MTOP 响应 ===');
  for (const r of mtopResps) {
    // 检查是否有 "desc":"..." 或 "description":"..." 字段
    const descMatch = r.text.match(/"desc"\s*:\s*"([^"]{10,})"/);
    const descMatch2 = r.text.match(/"description"\s*:\s*"([^"]{10,})"/);
    const detailMatch = r.text.match(/"detail"\s*:\s*"([^"]{10,})"/);
    const itemDescMatch = r.text.match(/"itemDesc"\s*:\s*"([^"]{10,})"/);
    const contentMatch = r.text.match(/"content"\s*:\s*"([^"]{30,})"/);

    if (descMatch || descMatch2 || detailMatch || itemDescMatch || contentMatch) {
      console.log(`\n--- API: ${r.apiName} (len=${r.text.length}) ---`);
      if (descMatch) console.log(`  desc: ${descMatch[1].slice(0, 200)}`);
      if (descMatch2) console.log(`  description: ${descMatch2[1].slice(0, 200)}`);
      if (detailMatch) console.log(`  detail: ${detailMatch[1].slice(0, 200)}`);
      if (itemDescMatch) console.log(`  itemDesc: ${itemDescMatch[1].slice(0, 200)}`);
      if (contentMatch) console.log(`  content: ${contentMatch[1].slice(0, 200)}`);
    }
  }

  // 查找 detail 相关 API 的完整响应
  console.log('\n=== detail 相关 API 完整响应 ===');
  for (const r of mtopResps) {
    if (/detail|item\.get|item\.info|item\.desc/i.test(r.apiName)) {
      console.log(`\n--- ${r.apiName} (len=${r.text.length}) ---`);
      console.log(r.text.slice(0, 1500));
    }
  }

  await browser.close();
  console.log('\n浏览器已关闭');
}

main().catch((e) => {
  console.error('失败:', e);
  process.exit(1);
});
