/**
 * 用 Playwright 拦截闲鱼商品详情页的 MTOP 响应
 * 找到真实描述字段
 */
import { chromium } from 'playwright';

async function main() {
  const itemId = '1058957265753';
  const url = `https://www.goofish.com/item?itemId=${itemId}`;

  // 读取环境变量 Cookie
  const cookieHeader = process.env.GOOFISH_COOKIE || '';
  if (!cookieHeader) {
    console.error('请设置 GOOFISH_COOKIE 环境变量');
    process.exit(1);
  }
  console.log(`Cookie 长度: ${cookieHeader.length}`);

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
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

  const mtopResponses: Array<{ url: string; apiName: string; body: any; text: string; postData: string }> = [];

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

      // 同时获取请求的 POST body
      let postData = '';
      try {
        const req = response.request();
        postData = req.postData() || '';
      } catch {}

      let body: any = null;
      try {
        body = JSON.parse(text);
      } catch {
        const m = text.match(/\{[\s\S]+\}/);
        if (m) {
          try { body = JSON.parse(m[0]); } catch {}
        }
      }

      mtopResponses.push({ url: reqUrl, apiName, body, text, postData });
    } catch {}
  });

  console.log(`访问: ${url}`);
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(10000);

  // 再滚动触发更多请求
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(3000);

  // ★ 从 DOM 提取商品描述
  console.log('\n=== 从 DOM 提取商品描述 ===');
  const domDesc = await page.evaluate(() => {
    const result: Record<string, string> = {};
    // 找所有可能含描述的元素
    const selectors = [
      '[class*="desc" i]', '[class*="detail" i]', '[class*="content" i]',
      '[class*="item-text" i]', '[class*="item-info" i]',
      '[class*="description" i]', '[class*="body" i]',
      '.desc', '.detail', '.content', '.description',
    ];
    for (const sel of selectors) {
      const els = document.querySelectorAll(sel);
      for (let i = 0; i < Math.min(els.length, 3); i++) {
        const el = els[i] as HTMLElement;
        const text = (el.innerText || el.textContent || '').trim();
        if (text.length > 30 && text.length < 2000) {
          result[`${sel}[${i}]`] = text.slice(0, 300);
        }
      }
    }
    // 也找含"安装"、"远程"等关键词的长文本块
    const divs = document.querySelectorAll('div, p, span');
    for (let i = 0; i < divs.length; i++) {
      const d = divs[i] as HTMLElement;
      const t = (d.innerText || '').trim();
      if (t.length > 50 && t.length < 1000 && /安装|远程|版本|发货|系统|拍下/.test(t)) {
        result[`div_${i}`] = t.slice(0, 300);
        if (Object.keys(result).length > 20) break;
      }
    }
    return result;
  });
  for (const k of Object.keys(domDesc)) {
    console.log(`  [${k}]: ${domDesc[k].slice(0, 200)}`);
  }

  console.log(`\n=== 拦截到 ${mtopResponses.length} 个 MTOP 响应 ===`);
  const apiCounts: Record<string, number> = {};
  for (const r of mtopResponses) {
    apiCounts[r.apiName] = (apiCounts[r.apiName] || 0) + 1;
  }
  console.log('API 去重统计:', apiCounts);

  // 查找 mtop.taobao.idle.pc.detail 的响应
  const detailResps = mtopResponses.filter(r => r.apiName === 'mtop.taobao.idle.pc.detail');
  for (const r of detailResps) {
    console.log(`\n=== mtop.taobao.idle.pc.detail 响应 ===`);
    console.log(`完整 URL: ${r.url}`);
    console.log(`text 长度: ${r.text.length}`);
    console.log(`完整响应: ${r.text.slice(0, 500)}`);
  }

  // 查找所有 data 中含 title/desc 的响应
  console.log('\n=== 所有含 title/desc 的 MTOP 响应 ===');
  for (const r of mtopResponses) {
    if (!r.body) continue;
    const t = JSON.stringify(r.body);
    if (/"title"|"desc"|"description"|"detail"|"itemDesc"/.test(t)) {
      console.log(`\n--- api=${r.apiName} len=${r.text.length} ---`);
      console.log(`  ${r.text.slice(0, 400)}`);
    }
  }

  await browser.close();
}

main().catch(e => {
  console.error('失败:', e);
  process.exit(1);
});
