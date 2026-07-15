/**
 * 用 ?id= 格式打开商品详情页，捕获 mtop.taobao.idle.pc.detail 的完整响应，
 * 找到描述字段在响应 JSON 中的路径
 */
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';

async function main() {
  const itemId = process.env.ITEM_ID || '1049776111066';
  // ★ 关键：用 ?id= 而不是 ?itemId=，否则 goofish 网页 JS 会发送空 itemId
  const url = `https://www.goofish.com/item?id=${itemId}`;

  const cookieHeader = process.env.GOOFISH_COOKIE || '';
  if (!cookieHeader) {
    console.error('请设置 GOOFISH_COOKIE');
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
  if (cookies.length > 0) await context.addCookies(cookies);

  const page = await context.newPage();

  let detailResponseText = '';
  page.on('response', async (response) => {
    const reqUrl = response.url() || '';
    if (!reqUrl.includes('mtop.taobao.idle.pc.detail')) return;
    try {
      const text = await response.text();
      if (text.includes('FAIL_BIZ_PARAM_ERROR')) return; // 跳过失败的
      detailResponseText = text;
      console.log(`[拦截] mtop.taobao.idle.pc.detail 成功响应 (len=${text.length})`);
    } catch {}
  });

  console.log(`访问: ${url}`);
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForTimeout(8000);

  if (!detailResponseText) {
    console.error('未拦截到成功的 detail 响应');
    await browser.close();
    process.exit(1);
  }

  // 解析 JSON 并查找描述字段
  const detail = JSON.parse(detailResponseText);
  const data = detail.data || {};

  console.log('\n=== data 顶层字段 ===');
  for (const key of Object.keys(data)) {
    const val = data[key];
    const type = Array.isArray(val) ? 'array' : typeof val;
    const preview = typeof val === 'string' ? val.slice(0, 100) : (typeof val === 'object' ? JSON.stringify(val).slice(0, 100) : String(val));
    console.log(`  ${key} (${type}): ${preview}`);
  }

  // 递归查找含描述的字段
  console.log('\n=== 递归查找描述字段 ===');
  const findDescFields = (obj: any, path: string[] = [], depth = 0): void => {
    if (depth > 6 || obj == null) return;
    if (typeof obj === 'string') {
      // 检查是否是商品描述（长度 > 20，含中文，不是数字/URL）
      if (obj.length > 20 && /[\u4e00-\u9fff]/.test(obj) && !/^\d+$/.test(obj) && !obj.startsWith('http')) {
        console.log(`  ${path.join('.')}: ${obj.slice(0, 200)}`);
      }
      return;
    }
    if (Array.isArray(obj)) {
      for (let i = 0; i < Math.min(obj.length, 5); i++) {
        findDescFields(obj[i], [...path, String(i)], depth + 1);
      }
      return;
    }
    if (typeof obj === 'object') {
      for (const [key, val] of Object.entries(obj)) {
        // 重点关注的字段名
        if (/desc|description|detail|content|title|body|text|item/i.test(key)) {
          findDescFields(val, [...path, key], depth + 1);
        }
      }
    }
  };
  findDescFields(data);

  // 保存完整响应到文件
  writeFileSync('scripts/_detail_response.json', detailResponseText);
  console.log('\n完整响应已保存到 scripts/_detail_response.json');

  // 同时从 DOM 提取描述
  console.log('\n=== DOM 提取 ===');
  const domDesc = await page.evaluate(() => {
    const result: any = {};
    // 找标题
    const titleEl = document.querySelector('h1, [class*="title" i]');
    if (titleEl) result.title = (titleEl as HTMLElement).innerText.trim();

    // 找描述/详情区域
    const descEls = document.querySelectorAll('[class*="desc" i], [class*="detail" i], [class*="content" i]');
    for (let i = 0; i < Math.min(descEls.length, 10); i++) {
      const el = descEls[i] as HTMLElement;
      const t = (el.innerText || '').trim();
      if (t.length > 30 && t.length < 2000) {
        result[`desc_${i}_${el.className.slice(0, 40)}`] = t.slice(0, 400);
      }
    }
    return result;
  });
  for (const [k, v] of Object.entries(domDesc)) {
    console.log(`  [${k}]: ${(v as string).slice(0, 200)}`);
  }

  await browser.close();
  console.log('\n浏览器已关闭');
}

main().catch((e) => {
  console.error('失败:', e);
  process.exit(1);
});
