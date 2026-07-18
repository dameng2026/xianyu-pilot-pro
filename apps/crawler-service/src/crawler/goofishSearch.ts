import { chromium, Browser, Page, BrowserContextOptions, Cookie, Response } from 'playwright';
import path from 'path';
import os from 'os';
import fs from 'fs/promises';
import fsSync from 'fs';
import { spawn } from 'child_process';
import { isSafeBrowserResourceUrl, normalizeGoofishTargetUrl, safeErrorType } from '../policy.js';
import { ANTI_DETECT_SCRIPT } from './sliderSolver.js';

export interface SearchResultItem {
  itemId?: string;
  title?: string;
  price?: string;
  imageUrl?: string;
  itemUrl?: string;
  userNickName?: string;
  area?: string;
}

export interface SearchResult {
  items: SearchResultItem[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
  hasMoreKnown?: boolean;
  totalExact?: boolean;
}

const BLOCK_KEYWORDS = [
  '请完成验证',
  '安全验证',
  '访问过于频繁',
  '请稍后再试',
];

// MTOP 搜索 API 标识，用于精确匹配网络响应
const SEARCH_API_MARKER = 'mtop.taobao.idlemtopsearch.pc.search';

/**
 * MTOP 响应竞速结果。
 * - ok=true 表示成功解析到商品（items 为非空数组）
 * - ok=false 表示 MTOP 返回非成功状态（如 Baxia 风控），items 为空数组，error 携带 retMsg
 * - punishUrl 仅在 MTOP 返回 FAIL_SYS_USER_VALIDATE 且 data 含 punish URL 时存在，
 *   主流程据此触发滑块求解后重试
 * 调用方仍可通过外部 networkItems 数组读取已捕获的商品（向后兼容）
 */
interface MtopSettleResult {
  ok: boolean;
  items: SearchResultItem[];
  error?: string;
  punishUrl?: string;
}

/**
 * 从 MTOP 搜索 API 的响应中提取商品列表。
 *
 * 响应结构（参考 闲鱼搜索接口.md）:
 * {
 *   "api": "mtop.taobao.idlemtopsearch.pc.search",
 *   "data": {
 *     "resultList": [
 *       {
 *         "data": {
 *           "item": {
 *             "main": {
 *               "exContent": {
 *                 "itemId": "1060173583182",
 *                 "title": "商品标题",
 *                 "picUrl": "http://img.alicdn.com/...",
 *                 "price": [{"text":"当前价¥","type":"sign"}, {"text":"160","type":"integer"}],
 *                 "userNickName": "卖家昵称",
 *                 "area": "广东"
 *               },
 *               "clickParam": { "args": { "price": "160", "item_id": "..." } }
 *             }
 *           }
 *         }
 *       }
 *     ]
 *   }
 * }
 */
function parseMtopSearchResponse(json: unknown): SearchResultItem[] {
  const items: SearchResultItem[] = [];
  if (!json || typeof json !== 'object') return items;

  const root = json as Record<string, unknown>;
  const data = root.data;
  if (!data || typeof data !== 'object') return items;

  const dataObj = data as Record<string, unknown>;
  const resultList = dataObj.resultList;
  if (!Array.isArray(resultList)) return items;

  for (const entry of resultList) {
    if (!entry || typeof entry !== 'object') continue;
    const entryObj = entry as Record<string, unknown>;
    const entryData = entryObj.data as Record<string, unknown> | undefined;
    if (!entryData || typeof entryData !== 'object') continue;

    const item = entryData.item as Record<string, unknown> | undefined;
    if (!item || typeof item !== 'object') continue;

    const main = item.main as Record<string, unknown> | undefined;
    if (!main || typeof main !== 'object') continue;

    const ex = main.exContent as Record<string, unknown> | undefined;
    if (!ex || typeof ex !== 'object') continue;

    const clickParam = main.clickParam as Record<string, unknown> | undefined;
    const clickArgs = (clickParam?.args as Record<string, unknown>) || {};

    // itemId
    const itemId = String(ex.itemId || clickArgs.item_id || clickArgs.id || '').trim();

    // title: exContent.title 是商品完整描述标题
    const title = String(ex.title || '').trim();

    // picUrl: 商品封面图
    const picUrl = String(ex.picUrl || '').trim();

    // price: exContent.price 是数组 [{text, type}, ...]
    //   - type="sign" 是前缀（如"当前价¥"、"¥"）
    //   - type="integer" 是数字部分
    // 也兼容 clickParam.args.price（纯数字字符串）
    let price = '';
    if (Array.isArray(ex.price)) {
      const integerPart = (ex.price as Array<Record<string, unknown>>).find(
        (p) => p && p.type === 'integer'
      );
      if (integerPart && integerPart.text) {
        price = String(integerPart.text).trim();
      } else {
        // 兜底：拼接所有 text
        price = (ex.price as Array<Record<string, unknown>>)
          .map((p) => p?.text || '')
          .join('')
          .trim();
      }
    }
    if (!price && clickArgs.price) {
      price = String(clickArgs.price).trim();
    }
    if (!price && typeof ex.price === 'string') {
      price = (ex.price as string).trim();
    }
    if (!price && typeof ex.price === 'number') {
      price = String(ex.price);
    }

    // 卖家昵称
    const userNickName = String(ex.userNickName || '').trim();

    // 地区
    const area = String(ex.area || '').trim();

    // itemUrl
    const itemUrl = itemId ? `https://www.goofish.com/item?itemId=${itemId}` : '';

    // 只保留有 itemId 或 title 的有效商品
    if (itemId || title) {
      items.push({
        itemId,
        title,
        price,
        imageUrl: picUrl,
        itemUrl,
        userNickName,
        area,
      });
    }
  }

  return items;
}

function parseMtopPagination(json: unknown): { total?: number; hasMore?: boolean } {
  if (!json || typeof json !== 'object') return {};
  const data = (json as Record<string, unknown>).data;
  if (!data || typeof data !== 'object') return {};
  const record = data as Record<string, unknown>;
  const pageInfo = record.pageInfo && typeof record.pageInfo === 'object'
    ? record.pageInfo as Record<string, unknown> : {};
  const totalValue = record.total ?? record.totalCount ?? record.totalMatchCount
    ?? pageInfo.total ?? pageInfo.totalCount;
  const total = Number(totalValue);
  const hasMoreValue = record.hasMore ?? pageInfo.hasMore;
  return {
    ...(Number.isSafeInteger(total) && total >= 0 ? { total } : {}),
    ...(typeof hasMoreValue === 'boolean' ? { hasMore: hasMoreValue } : {}),
  };
}

export function paginateCurrentCapturedPage<T>(items: T[], pageSize: number): T[] {
  const safePageSize = Number.isSafeInteger(pageSize) ? Math.max(1, Math.min(pageSize, 50)) : 20;
  return items.slice(0, safePageSize);
}

function deduplicateItems(items: SearchResultItem[]): SearchResultItem[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    let key: string;
    if (item.itemId) {
      key = `id:${item.itemId}`;
    } else if (item.itemUrl) {
      key = `url:${item.itemUrl}`;
    } else {
      key = `combo:${item.title || ''}|${item.price || ''}|${item.imageUrl || ''}`;
    }
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

/**
 * 使用 DOM 选择器从搜索页面提取商品卡片信息（作为网络拦截的兜底）。
 */
async function extractFromDom(page: Page): Promise<SearchResultItem[]> {
  const rawResults = await page.evaluate(() => {
    const results: SearchResultItem[] = [];
    const seen = new Set<string>();

    // 策略 1: 查找常见的商品卡片容器
    const cardSelectors = [
      '[class*="item-card"]',
      '[class*="card-item"]',
      '[class*="goods-card"]',
      '[class*="product-card"]',
      '[class*="search-result"] [class*="item"]',
      '[class*="waterfall"] [class*="item"]',
      '[class*="grid"] [class*="item"]',
      'li[class*="item"]',
      'div[class*="item"]',
    ];

    for (const selector of cardSelectors) {
      const cards = document.querySelectorAll(selector);
      for (const card of cards) {
        const imgEl = card.querySelector('img');
        const imageUrl = imgEl?.src || imgEl?.getAttribute('data-src') || '';

        const titleEl =
          card.querySelector('[class*="title"]') ||
          card.querySelector('[class*="name"]') ||
          card.querySelector('h3') ||
          card.querySelector('h4');
        const title = titleEl?.textContent?.trim() || '';

        const priceEl =
          card.querySelector('[class*="price"]') ||
          card.querySelector('[class*="amount"]') ||
          card.querySelector('[class*="money"]');
        let price = '';
        if (priceEl) {
          price = priceEl.textContent?.trim() || '';
          const priceMatch = price.match(/(\d+(?:\.\d+)?)/);
          if (priceMatch) price = priceMatch[1];
        }

        const linkEl = card.closest('a') || card.querySelector('a[href]');
        let itemUrl = '';
        if (linkEl) {
          const href = (linkEl as HTMLAnchorElement).href;
          if (href && !href.startsWith('javascript:')) {
            itemUrl = href;
          }
        }

        const idMatch = itemUrl.match(/[?&]id=(\d+)/);
        const itemId = idMatch ? idMatch[1] : '';

        if (title || imageUrl) {
          const key = itemId || title + price;
          if (!seen.has(key)) {
            seen.add(key);
            results.push({ itemId, title, price, imageUrl, itemUrl });
          }
        }
      }
      if (results.length > 0) break;
    }

    // 策略 2: 如果策略 1 没找到，遍历所有链接
    if (results.length === 0) {
      const links = document.querySelectorAll('a[href]');
      for (const a of links) {
        const href = (a as HTMLAnchorElement).href.toLowerCase();
        if (!href.includes('item') && !href.includes('goods') && !href.includes('detail'))
          continue;

        const img = a.querySelector('img');
        const text = a.textContent?.trim();
        if (!text || text.length < 2) continue;

        const title = text.substring(0, 200);
        const imageUrl = img?.src || img?.getAttribute('data-src') || '';
        const idMatch = href.match(/[?&]id=(\d+)/);
        const itemId = idMatch ? idMatch[1] : '';

        const key = itemId || title;
        if (!seen.has(key)) {
          seen.add(key);
          results.push({ itemId, title, price: '', imageUrl, itemUrl: (a as HTMLAnchorElement).href });
        }
      }
    }

    return results;
  });
  // 过滤非商品链接：风控降级时页面会显示"绿色消费"等引导链接，不应作为商品返回
  return rawResults.filter((item) => {
    const url = item.itemUrl || '';
    // 有数字 itemId 的一律保留
    if (item.itemId && /^\d+$/.test(item.itemId)) return true;
    // 非 goofish.com 域名过滤掉（如 12377.cn、gov.cn 等引导链接）
    if (url && !url.includes('goofish.com')) return false;
    // goofish.com/publish 等引导链接过滤掉
    if (url.includes('goofish.com/publish')) return false;
    // 其他 goofish.com 链接保留（可能商品详情页）
    return true;
  });
}

/**
 * 从页面中提取分页信息。
 */
async function extractPagination(page: Page): Promise<{ total: number; hasMore?: boolean }> {
  return page.evaluate(() => {
    const bodyText = document.body.innerText || '';
    const totalMatch = bodyText.match(/共\s*(\d+)\s*件/);
    const total = totalMatch ? parseInt(totalMatch[1], 10) : 0;

    const nextBtn =
      document.querySelector('[class*="next"]') ||
      document.querySelector('[class*="pagination"] [class*="next"]') ||
      document.querySelector('a[class*="next"]') ||
      document.querySelector('button[class*="next"]');

    const hasMore = nextBtn === null ? undefined : !(
      (nextBtn as HTMLElement).className.includes('disabled')
      || nextBtn.getAttribute('aria-disabled') === 'true'
      || (nextBtn as HTMLButtonElement).disabled === true
    );

    return { total, hasMore };
  });
}

/**
 * 通过 Python patchright 脚本执行搜索（Node Playwright 的最终兜底方案）。
 *
 * 触发场景：Node Playwright 即使使用真实 Chrome channel + ignoreDefaultArgs 仍被 Baxia
 * 识别为自动化（CDP 协议痕迹 cdc_/__playwright__/Runtime.enable 无法清除）。
 * patchright 是 Playwright 的反检测分支，自动清理所有 CDP 痕迹，已验证不触发风控。
 *
 * 实现：spawn goofishSearch.py，通过 CLI 传递 keyword/page/pageSize/cookieFile，
 * 从 stdout 最后一行解析 JSON 结果。
 *
 * @returns 搜索结果；返回 null 表示未尝试或脚本异常
 */
async function searchViaPythonScript(options: {
  keyword: string;
  pageNum: number;
  pageSize: number;
  cookieStr: string;
  timeoutMs?: number;
}): Promise<{ items: SearchResultItem[]; total?: number; hasMore?: boolean } | null> {
  // 仅在 Windows + 有头模式尝试（与 sliderSolve.py 一致）
  if (process.platform !== 'win32') {
    return null;
  }
  if (!options.cookieStr) {
    return null;
  }

  // 定位 Python 脚本（与 sliderSolve.py 同目录，即 crawler-service 根目录）
  const scriptPath = path.join(process.cwd(), 'goofishSearch.py');
  if (!fsSync.existsSync(scriptPath)) {
    console.warn(`[SearchCrawler] Python 搜索脚本不存在: ${scriptPath}`);
    return null;
  }

  // 定位 Python 可执行文件
  const pythonCandidates = [
    process.env.PYTHON_PATH,
    'python',
    'python3',
    'py',
  ].filter(Boolean) as string[];
  let pythonPath: string | null = null;
  for (const candidate of pythonCandidates) {
    try {
      fsSync.accessSync(candidate, fsSync.constants.X_OK);
      pythonPath = candidate;
      break;
    } catch {
      try {
        const { execSync } = await import('child_process');
        execSync(`${candidate} --version`, { stdio: 'pipe', timeout: 5000 });
        pythonPath = candidate;
        break;
      } catch {
        // continue
      }
    }
  }
  if (!pythonPath) {
    console.warn('[SearchCrawler] 未找到 Python 可执行文件');
    return null;
  }

  // 写入临时 Cookie 文件（Cookie 可能很长，不走 CLI 参数）
  const tmpDir = os.tmpdir();
  const cookieFile = path.join(tmpDir, `goofish-search-cookie-${Date.now()}.txt`);
  try {
    await fs.writeFile(cookieFile, options.cookieStr, 'utf-8');
  } catch (e) {
    console.warn(`[SearchCrawler] 写入临时 Cookie 文件失败: ${safeErrorType(e)}`);
    return null;
  }

  const args = [
    scriptPath,
    '--keyword', options.keyword,
    '--page', String(options.pageNum),
    '--page-size', String(options.pageSize),
    '--cookie-file', cookieFile,
  ];

  console.log(`[SearchCrawler] 调用 Python patchright 脚本搜索: ${pythonPath} ${scriptPath}`);
  console.log(`[SearchCrawler]   keyword=${options.keyword}, page=${options.pageNum}, pageSize=${options.pageSize}`);

  return new Promise((resolve) => {
    const child = spawn(pythonPath!, args, {
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: false,
      cwd: process.cwd(),
    });

    let stdout = '';
    let stderr = '';

    child.stdout.on('data', (data: Buffer) => {
      const text = data.toString('utf-8');
      stdout += text;
      // 实时打印 Python 脚本输出（便于诊断）
      process.stdout.write(`[goofishSearch.py] ${text}`);
    });
    child.stderr.on('data', (data: Buffer) => {
      const text = data.toString('utf-8');
      stderr += text;
      process.stderr.write(`[goofishSearch.py:err] ${text}`);
    });

    // 总超时：搜索场景不求解滑块，Python patchright 直接导航搜索 URL 实测 5-10s 能完成。
    // 默认 30s，调用方可传入更短超时（如搜索兜底场景传 15s）。
    const totalTimeout = options.timeoutMs ?? 30000;
    const timer = setTimeout(() => {
      console.warn(`[SearchCrawler] Python 搜索脚本超时 (${totalTimeout}ms)，终止进程`);
      try { child.kill('SIGTERM'); } catch { /* ignore */ }
      setTimeout(() => {
        try { child.kill('SIGKILL'); } catch { /* ignore */ }
      }, 2000);
    }, totalTimeout);

    child.on('close', (code: number) => {
      clearTimeout(timer);
      // 清理临时 Cookie 文件
      fs.unlink(cookieFile).catch(() => { /* ignore */ });

      // 从 stdout 最后一行解析 JSON 结果（与 sliderSolve.py 协议一致）
      const lines = stdout.split(/\r?\n/).filter((l) => l.trim());
      for (let i = lines.length - 1; i >= 0; i--) {
        const line = lines[i].trim();
        if (line.startsWith('{') && line.endsWith('}')) {
          try {
            const parsed = JSON.parse(line);
            if (parsed && typeof parsed === 'object' && 'ok' in parsed) {
              if (parsed.ok && Array.isArray(parsed.items) && parsed.items.length > 0) {
                console.log(`[SearchCrawler] Python 脚本搜索成功: ${parsed.items.length} 个商品 (exit=${code})`);
                resolve({
                  items: parsed.items.map((it: Record<string, unknown>) => ({
                    itemId: String(it.itemId || ''),
                    title: String(it.title || ''),
                    price: String(it.price || ''),
                    imageUrl: String(it.imageUrl || ''),
                    itemUrl: String(it.itemUrl || ''),
                    userNickName: String(it.userNickName || ''),
                    area: String(it.area || ''),
                  })),
                  total: typeof parsed.total === 'number' ? parsed.total : undefined,
                  hasMore: typeof parsed.hasMore === 'boolean' ? parsed.hasMore : undefined,
                });
                return;
              }
              console.log(`[SearchCrawler] Python 脚本搜索未返回结果: ok=${parsed.ok}, error=${parsed.error || ''} (exit=${code})`);
              resolve(null);
              return;
            }
          } catch {
            // 非合法 JSON，继续向上找
          }
        }
      }
      console.log(`[SearchCrawler] Python 脚本搜索未输出 JSON 结果 (exit=${code})`);
      resolve(null);
    });

    child.on('error', (err) => {
      clearTimeout(timer);
      fs.unlink(cookieFile).catch(() => { /* ignore */ });
      console.warn(`[SearchCrawler] Python 脚本进程错误: ${safeErrorType(err)}`);
      resolve(null);
    });
  });
}

/**
 * 爬取闲鱼搜索页面商品列表。
 *
 * 通过真实浏览器（Playwright）访问 goofish.com 搜索页面，
 * 拦截 mtop.taobao.idlemtopsearch.pc.search API 响应并解析商品列表。
 * 浏览器自动处理 Baxia 反爬令牌（bx-ua/bx-umidtoken/bx_et），
 * 传递 Cookie 可让浏览器使用已登录的闲鱼会话。
 *
 * @param keyword 搜索关键词
 * @param pageNum 页码（从 1 开始）
 * @param pageSize 每页商品数（建议 20）
 * @param cookieStr 闲鱼账号 Cookie 字符串（可选，用于登录态搜索）
 */
export async function crawlGoofishSearch(
  keyword: string,
  pageNum: number = 1,
  pageSize: number = 20,
  cookieStr: string = ''
): Promise<SearchResult> {
  const encodedKeyword = encodeURIComponent(keyword.trim());
  const url = `https://www.goofish.com/search?q=${encodedKeyword}&page=${pageNum}`;
  console.log(`[SearchCrawler] 开始搜索: page=${pageNum}, pageSize=${pageSize}, hasCookie=${!!cookieStr}`);

  const headless = process.env.HEADLESS !== 'false';
  const isWindows = process.platform === 'win32';
  let browser: Browser | null = null;
  // 优先使用 MTOP API 拦截结果，DOM 提取作为兜底
  const networkItems: SearchResultItem[] = [];
  let networkTotal: number | undefined;
  let networkHasMore: boolean | undefined;
  // mtopSettled 防止多次 MTOP 响应并发修改 networkItems / 重复 resolve
  let mtopSettled = false;
  // 用于在拦截到 MTOP 响应后立即唤醒主流程，避免无谓的固定等待
  // resolve 携带 ok/items/error 字段，调用方仍可通过 networkItems 读取结果（向后兼容）
  // 搜索场景不求解滑块，mtopDone 只 resolve 一次，故用 const
  let mtopResolve!: (value: MtopSettleResult) => void;
  const mtopDone = new Promise<MtopSettleResult>((resolve) => {
    mtopResolve = resolve;
  });

  try {
    browser = await chromium.launch({
      headless,
      chromiumSandbox: true,
      // 使用真实 Chrome channel（而非 Chromium），降低被 Baxia 识别为自动化的概率
      // sliderSolver.ts 验证：真实 Chrome + ignoreDefaultArgs 是求解滑块成功的关键配置
      ...(isWindows ? { channel: 'chrome' } : {}),
      // 移除 Playwright 默认的 --enable-automation 参数，这是 Baxia 识别自动化的强信号
      ignoreDefaultArgs: ['--enable-automation'],
    });

    const contextOptions: BrowserContextOptions = {
      viewport: { width: 1366, height: 900 },
      userAgent:
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
      locale: 'zh-CN',
      timezoneId: 'Asia/Shanghai',
    };

    // 注入 Cookie，让浏览器使用已登录的闲鱼会话
    if (cookieStr) {
      const cookies = cookieStr
        .split(';')
        .map((part): Cookie | null => {
          part = part.trim();
          if (!part || !part.includes('=')) return null;
          const idx = part.indexOf('=');
          const name = part.substring(0, idx).trim();
          const value = part.substring(idx + 1).trim();
          return {
            name,
            value,
            domain: '.goofish.com',
            path: '/',
            expires: -1,
            httpOnly: false,
            secure: true,
            sameSite: 'Lax',
          };
        })
        .filter((c): c is Cookie => c !== null);
      if (cookies.length > 0) {
        contextOptions.storageState = { cookies, origins: [] };
      }
    }

    const context = await browser.newContext(contextOptions);
    // 注入反检测脚本，覆盖 navigator.webdriver / plugins / WebGL vendor / Canvas 指纹等
    // Baxia 风控常用检测点，避免 headless 浏览器被识别为自动化而触发 FAIL_SYS_USER_VALIDATE
    await context.addInitScript(ANTI_DETECT_SCRIPT);
    await context.route('**/*', async (route) => {
      const request = route.request();
      if (!isSafeBrowserResourceUrl(request.url())) {
        await route.abort('blockedbyclient');
        return;
      }
      if (!request.isNavigationRequest() || request.frame().parentFrame()) {
        await route.continue();
        return;
      }
      try {
        normalizeGoofishTargetUrl(request.url());
        await route.continue();
      } catch {
        await route.abort('blockedbyclient');
      }
    });
    const page = await context.newPage();

    // 监听网络响应，精确拦截 MTOP 搜索 API 响应。
    // 一旦成功解析到商品，立即 resolve mtopDone，让主流程跳过后续等待。
    // 提取为命名函数，便于在 DOM 兜底前 page.off 移除监听器，避免并发修改 networkItems。
    const mtopResponseHandler = async (response: Response) => {
      // 已 settle 后忽略后续响应，避免并发 push / 重复 resolve
      if (mtopSettled) return;

      const req = response.request();
      const resourceType = req.resourceType();
      if (resourceType !== 'xhr' && resourceType !== 'fetch') {
        return;
      }

      // 只处理 MTOP 搜索 API 的响应
      const reqUrl = req.url() || '';
      if (!reqUrl.includes(SEARCH_API_MARKER)) {
        return;
      }

      const contentType = response.headers()['content-type'] || '';
      if (!contentType.includes('json')) {
        return;
      }

      try {
        const declaredLength = Number(response.headers()['content-length'] || 0);
        if (declaredLength > 2 * 1024 * 1024) return;
        const text = await response.text();
        if (!text || text.length < 50 || text.length > 2 * 1024 * 1024) return;

        let json: unknown;
        try {
          json = JSON.parse(text);
        } catch {
          return;
        }

        // 检查 MTOP 返回状态
        const jsonObj = json as Record<string, unknown>;
        const ret = jsonObj.ret;
        const retMsg =
          Array.isArray(ret) && ret.length > 0 ? String(ret[0]) : String(ret || '');
        if (retMsg && !retMsg.includes('SUCCESS')) {
          // MTOP 返回非成功（如 Baxia 风控）：立即 settle 为失败，唤醒主流程走 DOM 兜底，
          // 避免主流程等满 6 秒超时。不抛出异常，保持向后兼容（调用方读取 items 仍为空数组）。
          // 若 retMsg 包含 FAIL_SYS_USER_VALIDATE 且 data.url 含 punish URL，
          // 把 punishUrl 一并 settle 给主流程，触发滑块求解后重试。
          let punishUrl: string | undefined;
          if (retMsg.includes('FAIL_SYS_USER_VALIDATE')) {
            const dataObj = jsonObj.data as Record<string, unknown> | undefined;
            const urlVal = dataObj?.url;
            if (typeof urlVal === 'string' && urlVal.includes('punish')) {
              punishUrl = urlVal;
            }
          }
          console.log(
            `[SearchCrawler] MTOP 搜索返回非成功: retMsg=${retMsg}${punishUrl ? ' (含 punish URL，将尝试滑块求解)' : ''}`,
          );
          mtopSettled = true;
          mtopResolve({ ok: false, items: [], error: retMsg, punishUrl });
          return;
        }

        const parsed = parseMtopSearchResponse(json);
        const pagination = parseMtopPagination(json);
        if (pagination.total !== undefined) networkTotal = pagination.total;
        if (pagination.hasMore !== undefined) networkHasMore = pagination.hasMore;
        if (parsed.length > 0) {
          // 异步读取响应后再次校验，防止与并发响应竞争
          if (mtopSettled) return;
          mtopSettled = true;
          console.log(`[SearchCrawler] MTOP API 拦截成功: 提取 ${parsed.length} 个商品`);
          networkItems.push(...parsed);
          // 拦截到结果，立即唤醒主流程
          mtopResolve({ ok: true, items: parsed });
        } else {
          console.log('[SearchCrawler] MTOP API 响应解析到 0 个商品');
        }
      } catch (err) {
        console.log(`[SearchCrawler] 读取 MTOP 响应失败: errorType=${safeErrorType(err)}`);
      }
    };
    page.on('response', mtopResponseHandler);

    // 打开搜索页面 - 使用 domcontentloaded 而非 networkidle，加速首屏
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 20000 });

    // 竞速等待：MTOP API 响应到达 vs. 最大 6 秒超时
    // 之前固定等待 4s + autoScroll 3s + 1.5s = 8.5s，现在改为事件驱动
    const maxWaitMs = 6000;
    let raceResult: MtopSettleResult = await Promise.race([
      mtopDone,
      new Promise<MtopSettleResult>((resolve) =>
        setTimeout(() => resolve({ ok: false, items: [], error: 'timeout' }), maxWaitMs),
      ),
    ]);

    // 若 MTOP 返回 FAIL_SYS_USER_VALIDATE 且含 punish URL，说明 Node Playwright 已被 Baxia 识别为自动化。
    // 搜索场景不求解滑块（首页停留>5s 反而会触发更多风控），直接委托 Python patchright 完成搜索：
    //   - patchright 自动清理 CDP 痕迹（cdc_/__playwright__/Runtime.enable）
    //   - 直接 goto 搜索 URL，不在首页停留，避免触发滑块
    //   - 实测 5-10s 内能完成搜索
    if (raceResult.punishUrl && networkItems.length === 0 && cookieStr) {
      console.log('[SearchCrawler] 检测到 Baxia 风控 punish URL，直接委托 Python patchright 搜索（不求解滑块）');
      // 先关闭当前浏览器，避免两个 Chrome 实例争抢资源
      try {
        if (browser) {
          await browser.close();
          browser = null;
          console.log('[SearchCrawler] 已关闭 Node Playwright 浏览器，准备启动 Python patchright');
        }
      } catch (err) {
        console.log(`[SearchCrawler] 关闭 Node 浏览器异常（忽略）: errorType=${safeErrorType(err)}`);
      }
      const pythonResult = await searchViaPythonScript({
        keyword,
        pageNum,
        pageSize,
        cookieStr,
        // 搜索场景超时预算：Python patchright 直接 goto 搜索 URL，实测 5-10s 能完成。
        // 给 15s 足够覆盖慢网/慢机器场景，避免拖累整体响应时间。
        timeoutMs: 15000,
      });
      if (pythonResult && pythonResult.items.length > 0) {
        // 将 Python 脚本返回的商品填入 networkItems，走快速路径返回
        networkItems.push(...pythonResult.items);
        if (pythonResult.total !== undefined) networkTotal = pythonResult.total;
        if (pythonResult.hasMore !== undefined) networkHasMore = pythonResult.hasMore;
        console.log(`[SearchCrawler] Python patchright 搜索成功，使用其结果: ${pythonResult.items.length} 个商品`);
      } else {
        console.log('[SearchCrawler] Python patchright 搜索未返回结果，继续走 DOM 兜底');
      }
    }

    // 若已拿到 MTOP 结果，无需检测阻断/滚动/DOM，直接返回
    if (networkItems.length > 0) {
      const allItems = deduplicateItems(networkItems);
      const pagedItems = paginateCurrentCapturedPage(allItems, pageSize);
      const hasMore = networkHasMore ?? pagedItems.length > 0;
      const total = networkTotal
        ?? ((pageNum - 1) * pageSize + pagedItems.length + (hasMore ? 1 : 0));
      console.log(
        `[SearchCrawler] 搜索完成(快速路径): 共 ${allItems.length} 个商品, 返回 ${pagedItems.length} 个`
      );
      return {
        items: pagedItems,
        total,
        page: pageNum,
        pageSize,
        hasMore,
        hasMoreKnown: networkHasMore !== undefined,
        totalExact: networkTotal !== undefined,
      };
    }

    // 兜底：MTOP 拦截未拿到结果，先移除 response 监听器避免并发修改 networkItems，
    // 再短等 1.5s 后做 DOM 检测
    page.off('response', mtopResponseHandler);
    console.log(`[SearchCrawler] MTOP 快速路径未命中，做 1.5s 兜底等待后 DOM 提取`);
    await page.waitForTimeout(1500);

    // 检测页面阻断
    const bodyText = await page.evaluate(() => document.body.innerText || '');
    const blockedKeyword = BLOCK_KEYWORDS.find((kw) => bodyText.includes(kw));
    if (blockedKeyword) {
      throw new Error(`页面被阻断: 检测到「${blockedKeyword}」，请稍后重试`);
    }

    const domItems = await extractFromDom(page);
    console.log(`[SearchCrawler] DOM 提取: ${domItems.length} 个商品`);
    const allItems = deduplicateItems([...networkItems, ...domItems]);
    const pagination = await extractPagination(page);
    const pagedItems = paginateCurrentCapturedPage(allItems, pageSize);
    const hasMore = pagination.hasMore ?? pagedItems.length > 0;

    console.log(
      `[SearchCrawler] 搜索完成(兜底路径): 共 ${allItems.length} 个商品, 返回 ${pagedItems.length} 个`
    );

    return {
      items: pagedItems,
      total: pagination.total
        || ((pageNum - 1) * pageSize + pagedItems.length + (hasMore ? 1 : 0)),
      page: pageNum,
      pageSize,
      hasMore,
      hasMoreKnown: pagination.hasMore !== undefined,
      totalExact: pagination.total > 0,
    };
  } finally {
    if (browser) {
      await browser.close();
      console.log('[SearchCrawler] 浏览器已关闭');
    }
  }
}
