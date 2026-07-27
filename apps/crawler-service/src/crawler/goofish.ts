import crypto from 'crypto';
import { chromium, Browser, Page, type BrowserContext, type Response as PlaywrightResponse } from 'playwright';
import { parseGoofishStoreUrl } from './parseGoofishStoreUrl.js';
import {
  isProductionLike,
  isSafeBrowserResourceUrl,
  normalizeGoofishTargetUrl,
  safeErrorType,
} from '../policy.js';

export interface CrawledItem {
  itemId?: string;
  title?: string;
  description?: string;
  price?: string;
  imageUrl?: string;
  itemUrl?: string;
  seller?: string;
  area?: string;
  soldCount?: number;
}

interface CrawlDiagnostics {
  expectedItemCount?: number;
  networkCandidateCount: number;
  domCandidateCount: number;
  pageTitle?: string;
  blockedKeyword?: string;
  lastUrl?: string;
}

export interface CrawlGoofishStoreResult {
  items: CrawledItem[];
  diagnostics: CrawlDiagnostics;
}

const GOOFISH_APP_KEY = '34839810';
const USER_PAGE_HEAD_API = 'mtop.idle.web.user.page.head';
const USER_AGENT =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';

const BLOCK_KEYWORDS = [
  '安全验证',
  '验证码',
  '访问过于频繁',
  '请稍后再试',
  '系统繁忙',
  '页面不存在',
];

const ITEM_ID_KEYS = new Set([
  'itemid', 'item_id', 'id', 'auctionid', 'goodsid', 'goods_id', 'xygoodsid', 'item_id_str',
]);

const TITLE_KEYS = new Set([
  'title', 'name', 'itemtitle', 'idletitle', 'subject',
]);

// ★ 商品描述字段：MTOP 响应中 exContent.detailParams.desc / desc / description / reminderContent 等
//   这些是商品详情文案，绝对不能当作标题使用（否则会把"302人想要 LateSunday"等元数据带进标题）
const DESC_KEYS = new Set([
  'desc', 'description', 'detail', 'itemdesc', 'item_desc', 'content', 'remindercontent',
]);

const PRICE_KEYS = new Set([
  'price', 'reserveprice', 'reserve_price', 'soldprice', 'currentprice', 'priceinfo',
  'pricevo', 'pricetag', 'pricetext', 'showprice', 'tradeprice', 'amount',
]);

const IMAGE_KEYS = new Set([
  'image', 'imageurl', 'picurl', 'pic_url', 'cover', 'coverurl', 'mainpic', 'mainimageurl',
  'imgurl', 'displaypic', 'verticalpic', 'img',
]);

const URL_KEYS = new Set([
  'itemurl', 'url', 'detailurl', 'targeturl', 'pcurl', 'link',
]);

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function stringOrUndefined(val: unknown): string | undefined {
  if (typeof val === 'string') {
    const trimmed = val.trim();
    return trimmed || undefined;
  }
  if (typeof val === 'number' && Number.isFinite(val)) return String(val);
  return undefined;
}

function numberOrUndefined(val: unknown): number | undefined {
  if (typeof val === 'number' && Number.isFinite(val)) return val;
  if (typeof val === 'string') {
    const parsed = Number(val.replace(/[^\d.-]/g, ''));
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
}

function findValue(obj: Record<string, unknown>, keySet: Set<string>): unknown {
  for (const [key, val] of Object.entries(obj)) {
    if (keySet.has(key.toLowerCase())) return val;
  }
  return undefined;
}

function getPath(obj: unknown, path: string[]): unknown {
  let cur: unknown = obj;
  for (const key of path) {
    if (!isObject(cur)) return undefined;
    cur = cur[key];
  }
  return cur;
}

function formatPrice(value: unknown): string | undefined {
  if (value === null || value === undefined || value === '' || value === '-' || value === '--') return undefined;
  if (typeof value === 'string') return value.trim() || undefined;
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  if (Array.isArray(value)) {
    const typed = value
      .filter((item) => isObject(item))
      .map((item) => ({ type: String(item.type || ''), text: String(item.text || item.value || '') }))
      .filter((item) => item.text);
    if (typed.length) {
      const sign = typed.find((item) => item.type === 'sign')?.text || '';
      const integer = typed.find((item) => item.type === 'integer')?.text || '';
      const decimal = typed.find((item) => item.type === 'decimal')?.text || '';
      if (integer) return decimal ? `${sign}${integer}.${decimal}` : `${sign}${integer}`;
      return typed.map((item) => item.text).join('') || undefined;
    }
  }
  if (isObject(value)) {
    if (value.text !== undefined) return stringOrUndefined(value.text);
    if (value.value !== undefined) return stringOrUndefined(value.value);
    for (const key of ['price', 'priceText', 'showPrice', 'currentPrice', 'soldPrice', 'tradePrice']) {
      const found = formatPrice(value[key]);
      if (found) return found;
    }
  }
  return undefined;
}

function findPrice(obj: unknown, depth = 0): string | undefined {
  if (obj == null || depth > 10) return undefined;
  if (Array.isArray(obj)) {
    const direct = formatPrice(obj);
    if (direct) return direct;
    for (const item of obj) {
      const nested = findPrice(item, depth + 1);
      if (nested) return nested;
    }
    return undefined;
  }
  if (!isObject(obj)) return formatPrice(obj);

  const ex = obj.exContent;
  if (isObject(ex)) {
    for (const key of ['price', 'soldPrice', 'tradePrice', 'showPrice', 'priceText', 'reservePrice', 'currentPrice']) {
      const found = formatPrice(ex[key]);
      if (found) return found;
    }
  }

  for (const key of ['price', 'soldPrice', 'tradePrice', 'showPrice', 'priceText', 'reservePrice', 'currentPrice', 'priceInfo', 'priceVO', 'priceTag']) {
    const found = formatPrice(obj[key]);
    if (found) return found;
  }

  for (const value of Object.values(obj)) {
    const found = findPrice(value, depth + 1);
    if (found) return found;
  }
  return undefined;
}

function extractItemIdFromUrl(url?: string): string | undefined {
  if (!url) return undefined;
  const decoded = decodeURIComponent(url);
  const idMatch = decoded.match(/[?&](?:id|itemId|item_id)=([0-9]{6,})/i) || decoded.match(/item(?:\/|%2F)([0-9]{6,})/i);
  return idMatch?.[1];
}

function normalizeUrl(url?: string, itemId?: string): string | undefined {
  if (url) {
    const decoded = decodeURIComponent(url);
    const id = extractItemIdFromUrl(decoded) || itemId;
    if (decoded.startsWith('fleamarket://item') && id) return `https://www.goofish.com/item?id=${id}`;
    if (/^https?:\/\//i.test(decoded)) return decoded;
    if (decoded.startsWith('//')) return `https:${decoded}`;
    if (decoded.startsWith('/')) return `https://www.goofish.com${decoded}`;
  }
  return itemId ? `https://www.goofish.com/item?id=${itemId}` : undefined;
}

function normalizeImageUrl(url?: string): string | undefined {
  if (!url) return undefined;
  if (url.startsWith('//')) return `https:${url}`;
  if (url.startsWith('http')) return url;
  return url;
}

// 非商品标题黑名单：店铺页常见但并非商品的内容
const NON_PRODUCT_TITLE_KEYWORDS = [
  '满意度调研',
  '满意度调查',
  'tags',
  '宝贝',
  '商品',
  '在售',
  '已售',
  '首页',
  '个人主页',
  '关注',
  '粉丝',
  '评价',
  '动态',
];

// 已知店铺商品列表相关的 MTOP API 标识
const STORE_ITEM_API_MARKERS = [
  'mtop.idle.web.user.page',
  'mtop.taobao.idle.web.user.page',
  'mtop.idle.rec.user',
  'mtop.idle.web.search',
  'mtop.taobao.idlemtopsearch.pc.search',
];

function isLikelyStoreItemApiResponse(text: string): boolean {
  if (!text) return false;
  const lower = text.toLowerCase();
  return STORE_ITEM_API_MARKERS.some((marker) => lower.includes(marker));
}

function isValidItemId(itemId?: string): boolean {
  if (!itemId) return false;
  // 闲鱼商品 ID 必须是纯数字且至少 6 位
  return /^\d{6,}$/.test(itemId);
}

function isNonProductTitle(title?: string): boolean {
  if (!title) return false;
  const trimmed = title.trim();
  if (!trimmed) return true;
  // 长度过短或过长都不可信
  if (trimmed.length < 2 || trimmed.length > 200) return true;
  const lower = trimmed.toLowerCase();
  return NON_PRODUCT_TITLE_KEYWORDS.some((kw) => lower.includes(kw.toLowerCase()));
}

function isValidPrice(price?: string): boolean {
  if (!price) return false;
  // 价格必须包含数字
  return /\d/.test(price);
}

function normalizeGoofishItem(raw: unknown): CrawledItem | null {
  if (!isObject(raw)) return null;

  const itemData = isObject(raw.data) ? raw.data : raw;
  const candidates: unknown[] = [
    raw,
    itemData,
    // ★ 店铺商品列表 API (mtop.idle.web.xyh.item.list) 的卡片结构：
    //   cardData 内含干净的 title / id / priceInfo / picInfo / detailParams
    getPath(raw, ['cardData']),
    getPath(raw, ['cardData', 'detailParams']),
    getPath(raw, ['cardData', 'picInfo']),
    // ★ 当 raw 本身就是 cardData 时（extractItemsFromJson 直接传入 cardData），
    //   picInfo 是对象 {picUrl, width, height, hasVideo}，detailParams 含 picUrl 字符串，
    //   需要把它们加入候选，findValue 才能从中提取 picUrl 字符串
    getPath(raw, ['picInfo']),
    getPath(raw, ['detailParams']),
    getPath(raw, ['data', 'item', 'main', 'exContent']),
    getPath(raw, ['data', 'item', 'main']),
    getPath(raw, ['item', 'main', 'exContent']),
    getPath(raw, ['item', 'main']),
    getPath(raw, ['main', 'exContent']),
    raw.exContent,
    raw.item,
    raw.itemDO,
    raw.itemInfo,
  ].filter(Boolean);

  const pick = (keys: Set<string>): unknown => {
    for (const candidate of candidates) {
      if (isObject(candidate)) {
        const found = findValue(candidate, keys);
        if (found !== undefined && found !== null && found !== '') return found;
      }
    }
    return undefined;
  };

  const clickArgs = getPath(raw, ['data', 'clickParam', 'args']);
  if (isObject(clickArgs)) candidates.push(clickArgs);

  const title = stringOrUndefined(pick(TITLE_KEYS));
  // ★ 独立提取商品描述（之前 desc/description/remindercontent 被错误地塞进 title，
  //   导致标题中出现 "302人想要 LateSunday" 等元数据污染）
  const description = stringOrUndefined(pick(DESC_KEYS));
  let itemId = stringOrUndefined(pick(ITEM_ID_KEYS));
  const rawUrl = stringOrUndefined(pick(URL_KEYS));
  itemId = itemId || extractItemIdFromUrl(rawUrl);
  const itemUrl = normalizeUrl(rawUrl, itemId);
  const imageUrl = normalizeImageUrl(stringOrUndefined(pick(IMAGE_KEYS)));
  const price = findPrice(raw);
  const seller = stringOrUndefined(pick(new Set(['seller', 'sellernick', 'usernick', 'nick', 'nickname'])));
  const area = stringOrUndefined(pick(new Set(['area', 'location', 'province', 'city', 'iploc', 'iplocation'])));
  const soldCount = numberOrUndefined(pick(new Set(['soldcount', 'bizquantity', 'wantcount', 'favcount'])));

  // 严格过滤：必须有合法的数字 itemId（闲鱼商品 ID 至少 6 位纯数字）
  if (!isValidItemId(itemId)) return null;

  // 标题不能是通用词/非商品内容
  if (isNonProductTitle(title)) return null;

  // 价格如果存在必须包含数字
  if (price && !isValidPrice(price)) return null;

  if (title && title.length > 500) return null;

  return {
    itemId,
    title,
    description,
    price,
    imageUrl,
    itemUrl,
    seller,
    area,
    soldCount,
  };
}

function extractItemsFromJson(obj: unknown, results: CrawledItem[], depth = 0): void {
  // 限制递归深度，避免过深的 JSON 遍历引入非商品数据
  if (depth > 8 || obj == null) return;

  if (Array.isArray(obj)) {
    for (const item of obj) extractItemsFromJson(item, results, depth + 1);
    return;
  }
  if (!isObject(obj)) return;

  const dataField = obj.data;

  // 优先处理 MTOP 搜索 API 结构：data.resultList[]
  if (isObject(dataField) && Array.isArray((dataField as Record<string, unknown>).resultList)) {
    const resultList = (dataField as Record<string, unknown>).resultList;
    if (Array.isArray(resultList)) {
      for (const entry of resultList) {
        const normalized = normalizeGoofishItem(entry);
        if (normalized) results.push(normalized);
      }
      return; // 已经按标准结构提取，不再递归
    }
  }

  // ★ 处理店铺商品列表 API (mtop.idle.web.xyh.item.list) 结构：data.cardList[].cardData
  //   cardData 中包含干净的 title / id / priceInfo / picInfo / detailParams，
  //   不会被 "XX人想要 / LateSunday" 等水印污染
  if (isObject(dataField) && Array.isArray((dataField as Record<string, unknown>).cardList)) {
    const cardList = (dataField as Record<string, unknown>).cardList;
    if (Array.isArray(cardList)) {
      for (const entry of cardList) {
        // 卡片结构: {cardData: {...}, cardType: 1003}
        const cardData = isObject(entry) && isObject((entry as Record<string, unknown>).cardData)
          ? (entry as Record<string, unknown>).cardData
          : entry;
        const normalized = normalizeGoofishItem(cardData);
        if (normalized) results.push(normalized);
      }
      return;
    }
  }

  // 兜底：尝试将当前对象本身当作商品候选
  const normalized = normalizeGoofishItem(obj);
  if (normalized) results.push(normalized);

  // 仅在浅层（depth <= 4）继续递归，避免误提取深层数据
  if (depth > 4) return;

  // 仅当对象本身疑似商品列表容器时才继续递归
  const keys = Object.keys(obj).map((k) => k.toLowerCase());
  const likelyListContainer = keys.some((k) =>
    ['resultlist', 'items', 'itemlist', 'cardlist', 'feeds'].includes(k)
  );
  if (!likelyListContainer) return;

  for (const val of Object.values(obj)) {
    extractItemsFromJson(val, results, depth + 1);
  }
}

function parseJsonLike(text: string): unknown[] {
  const trimmed = text.trim();
  if (!trimmed) return [];
  const candidates: unknown[] = [];

  const tryParse = (value: string) => {
    try {
      candidates.push(JSON.parse(value));
    } catch {
      // ignored
    }
  };

  tryParse(trimmed);

  // mtopjsonp1({...}) / callback({...})
  const callbackMatch = trimmed.match(/^[\w.$]+\((.*)\)\s*;?$/s);
  if (callbackMatch?.[1]) tryParse(callbackMatch[1]);

  // Script bundles sometimes embed __INIT_DATA__ = {...}; keep this conservative to avoid huge false positives.
  const initDataMatches = trimmed.matchAll(/(?:__INIT_DATA__|__INITIAL_STATE__|window\.__[^=]+)\s*=\s*(\{.*?\})\s*;\s*(?:\n|$)/gs);
  for (const match of initDataMatches) {
    if (match[1] && match[1].length < 2_000_000) tryParse(match[1]);
  }

  return candidates;
}

function deduplicateItems(items: CrawledItem[]): CrawledItem[] {
  const seen = new Set<string>();
  const normalized = items
    .map((item) => {
      const itemId = item.itemId || extractItemIdFromUrl(item.itemUrl);
      return {
        ...item,
        itemId,
        itemUrl: normalizeUrl(item.itemUrl, itemId),
        imageUrl: normalizeImageUrl(item.imageUrl),
        title: item.title?.replace(/\s+/g, ' ').trim(),
        price: item.price?.replace(/\s+/g, '').trim(),
      };
    })
    .filter((item) => item.title || item.itemId || item.itemUrl);

  return normalized.filter((item) => {
    const key = item.itemId
      ? `id:${item.itemId}`
      : item.itemUrl
        ? `url:${item.itemUrl}`
        : `combo:${item.title || ''}|${item.price || ''}|${item.imageUrl || ''}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function parseCookieHeader(cookieHeader?: string): Array<{ name: string; value: string; domain: string; path: string; sameSite: 'Lax'; secure: true }> {
  const header = (cookieHeader || process.env.GOOFISH_COOKIE || '').trim();
  if (!header) return [];
  const cookies: Array<{ name: string; value: string; domain: string; path: string; sameSite: 'Lax'; secure: true }> = [];
  for (const part of header.split(';')) {
    const idx = part.indexOf('=');
    if (idx <= 0) continue;
    const name = part.slice(0, idx).trim();
    const value = part.slice(idx + 1).trim();
    if (!name || !value) continue;
    cookies.push({ name, value, domain: '.goofish.com', path: '/', sameSite: 'Lax', secure: true });
  }
  return cookies;
}

function extractMtopToken(cookieHeader?: string): string | undefined {
  const header = (cookieHeader || process.env.GOOFISH_COOKIE || '').trim();
  const match = header.match(/(?:^|;\s*)_m_h5_tk=([^;]+)/);
  const raw = match?.[1];
  if (!raw) return undefined;
  return decodeURIComponent(raw).split('_')[0] || undefined;
}

function buildMtopHeaders(cookieHeader?: string): Record<string, string> {
  return {
    'User-Agent': USER_AGENT,
    'Accept': 'application/json,text/plain,*/*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Origin': 'https://www.goofish.com',
    'Referer': 'https://www.goofish.com/',
    'Cookie': cookieHeader || process.env.GOOFISH_COOKIE || '',
    'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    'sec-ch-ua-platform': '"Windows"',
    'sec-ch-ua-mobile': '?0',
    'sec-fetch-site': 'same-site',
    'sec-fetch-mode': 'cors',
    'sec-fetch-dest': 'empty',
  };
}

async function mtopPost(api: string, version: string, data: unknown, cookieHeader?: string): Promise<unknown> {
  const token = extractMtopToken(cookieHeader);
  if (!token) throw new Error('Cookie 中缺少 _m_h5_tk，无法生成 MTOP 签名');

  const t = Date.now().toString();
  const dataStr = JSON.stringify(data ?? {}, null, 0);
  const sign = crypto.createHash('md5').update(`${token}&${t}&${GOOFISH_APP_KEY}&${dataStr}`).digest('hex');
  const params = new URLSearchParams({
    jsv: '2.7.2',
    appKey: GOOFISH_APP_KEY,
    t,
    sign,
    v: version,
    type: 'originaljson',
    accountSite: 'xianyu',
    dataType: 'json',
    timeout: '20000',
    api,
    sessionOption: 'AutoLoginOnly',
    spm_cnt: 'a21ybx.personal.0.0',
    spm_pre: `a21ybx.personal.${t}`,
    log_id: crypto.randomUUID().replace(/-/g, '').slice(0, 32),
  });
  const url = `https://h5api.m.goofish.com/h5/${api}/${version}/?${params.toString()}`;
  const resp = await fetch(url, {
    method: 'POST',
    headers: buildMtopHeaders(cookieHeader),
    body: new URLSearchParams({ data: dataStr }),
    signal: AbortSignal.timeout(25000),
  });
  const declaredLength = Number(resp.headers.get('content-length') || 0);
  if (declaredLength > 2 * 1024 * 1024) throw new Error('MTOP response exceeds size limit');
  const text = await resp.text();
  if (text.length > 2 * 1024 * 1024) throw new Error('MTOP response exceeds size limit');
  const parsed = parseJsonLike(text)[0] || JSON.parse(text);
  return parsed;
}

function readExpectedItemCount(headResp: unknown): number | undefined {
  const values: unknown[] = [];
  const walk = (obj: unknown, path: string[] = [], depth = 0) => {
    if (depth > 8 || obj == null) return;
    if (isObject(obj)) {
      const pathStr = path.join('.').toLowerCase();
      if ((pathStr.endsWith('tabs.item.number') || pathStr.endsWith('tabs.item.count')) && obj.number !== undefined) {
        values.push(obj.number);
      }
      if (pathStr.endsWith('tabs.item') && (obj.number !== undefined || obj.count !== undefined)) {
        values.push(obj.number ?? obj.count);
      }
      for (const [key, val] of Object.entries(obj)) walk(val, [...path, key], depth + 1);
    } else if (Array.isArray(obj)) {
      for (const item of obj) walk(item, path, depth + 1);
    }
  };
  walk(headResp);
  for (const value of values) {
    const num = numberOrUndefined(value);
    if (num !== undefined && num >= 0) return num;
  }
  return undefined;
}

async function fetchExpectedStoreItemCount(userId: string, cookieHeader?: string): Promise<number | undefined> {
  if (!extractMtopToken(cookieHeader)) return undefined;
  try {
    const resp = await mtopPost(USER_PAGE_HEAD_API, '1.0', { self: false, userId }, cookieHeader);
    const ret = isObject(resp) ? resp.ret : undefined;
    const retText = Array.isArray(ret) ? ret.join(' ') : String(ret || '');
    if (retText && !retText.includes('SUCCESS')) {
      console.warn('[Crawler] 店铺头部接口非成功');
      return undefined;
    }
    return readExpectedItemCount(resp);
  } catch (e: any) {
    console.warn(`[Crawler] 店铺头部接口失败，继续走浏览器抓取: errorType=${safeErrorType(e)}`);
    return undefined;
  }
}

async function tryClickItemsTab(page: Page): Promise<void> {
  const selectors = [
    'text=宝贝',
    'text=商品',
    'text=在售',
    '[role="tab"]:has-text("宝贝")',
    '[role="tab"]:has-text("商品")',
  ];
  for (const selector of selectors) {
    try {
      const locator = page.locator(selector).first();
      if (await locator.count()) {
        await locator.click({ timeout: 1500 });
        await page.waitForTimeout(800);
        return;
      }
    } catch {
      // ignore and try next selector
    }
  }
}

async function autoScrollUntilStable(
  page: Page,
  getItemCount: () => number,
  expectedItemCount?: number
): Promise<void> {
  const configuredMaxScrolls = Number(process.env.CRAWLER_MAX_SCROLLS || 80);
  const maxScrolls = Number.isSafeInteger(configuredMaxScrolls)
    ? Math.max(10, Math.min(configuredMaxScrolls, 200)) : 80;
  const idleLimit = 5;
  let stableRounds = 0;
  let lastHeight = 0;
  let lastCount = 0;

  for (let i = 0; i < maxScrolls; i += 1) {
    if (expectedItemCount && expectedItemCount > 0 && getItemCount() >= expectedItemCount) {
      console.log(`[Crawler] 已达到店铺预期商品数: expected=${expectedItemCount}, actual=${getItemCount()}`);
      break;
    }

    const beforeHeight = await page.evaluate(() => document.body.scrollHeight);
    await page.evaluate(() => window.scrollBy(0, Math.max(window.innerHeight * 0.85, 700)));
    await page.waitForTimeout(650);

    try {
      await page.waitForLoadState('networkidle', { timeout: 2500 });
    } catch {
      // 长轮询/埋点会导致 networkidle 超时，忽略
    }

    const afterHeight = await page.evaluate(() => document.body.scrollHeight);
    const count = getItemCount();
    if (afterHeight === lastHeight && count === lastCount && afterHeight === beforeHeight) {
      stableRounds += 1;
    } else {
      stableRounds = 0;
    }
    lastHeight = afterHeight;
    lastCount = count;

    if (stableRounds >= idleLimit && i >= 4) {
      console.log(`[Crawler] 页面滚动已稳定: rounds=${stableRounds}, items=${count}, height=${afterHeight}`);
      break;
    }
  }
}

async function extractDomItems(page: Page): Promise<CrawledItem[]> {
  // 注意：page.evaluate 回调内部必须使用箭头函数/匿名函数表达式，禁止使用命名 function 声明。
  // 原因：tsx(esbuild keepNames)会对命名 function 声明注入 __name helper，
  // 回调被序列化到浏览器执行时 __name 未定义会抛 ReferenceError，导致整个爬取崩溃。
  // 箭头函数与 const 赋值的匿名函数表达式不会被注入 __name，可以安全序列化。
  const domItems = await page.evaluate<Array<{ title?: string; description?: string; price?: string; imageUrl?: string; itemUrl?: string; itemId?: string }>>(() => {
    const normalize = (value?: string | null): string => (value || '').replace(/\s+/g, ' ').trim();
    const results: Array<{ title?: string; description?: string; price?: string; imageUrl?: string; itemUrl?: string; itemId?: string }> = [];
    const anchors = Array.from(document.querySelectorAll('a[href]')) as HTMLAnchorElement[];
    for (const a of anchors) {
      const href = a.href || '';
      if (!/goofish\.com\/item|\/item\?|[?&]id=\d{6,}/i.test(href)) continue;
      const container = (a.closest('[class*="item" i], [class*="card" i], [class*="goods" i], li, div') || a) as HTMLElement;
      const text = normalize(container.innerText || a.innerText || a.getAttribute('aria-label'));
      if (!text || text.length < 2) continue;
      const img = (container.querySelector('img') || a.querySelector('img')) as HTMLImageElement | null;
      const priceMatch = text.match(/[¥￥]\s*\d+(?:\.\d+)?|\b\d+(?:\.\d+)?\s*元/);

      // ★ 修复 DOM 提取：闲鱼店铺卡片里通常有独立的"标题元素"和"描述元素"
      //   之前直接用整个卡片的 innerText 当标题，导致标题里混入价格、"XX人想要"、店铺水印等
      //   现在按优先级找标题元素：[class*="title"] > [class*="name"] > h* > a 本身的文本
      const titleEl = (container.querySelector('[class*="title" i], [class*="name" i], h1, h2, h3, h4, h5, h6') || a) as HTMLElement;
      let title = normalize(titleEl.innerText || titleEl.textContent || a.innerText || a.getAttribute('aria-label') || '');
      // 从完整 text 中移除标题部分，剩下作为 description
      let description = '';
      if (title && text.startsWith(title)) {
        description = normalize(text.slice(title.length));
      } else if (title && text.includes(title)) {
        description = normalize(text.replace(title, ''));
      }
      // 移除标题和描述中的价格
      if (priceMatch?.[0]) {
        title = normalize(title.replace(priceMatch[0], ''));
        description = normalize(description.replace(priceMatch[0], ''));
      }
      // 截断标题长度
      title = title.slice(0, 200);

      const idMatch = decodeURIComponent(href).match(/[?&](?:id|itemId|item_id)=([0-9]{6,})/i);
      results.push({
        title,
        description: description || undefined,
        price: priceMatch?.[0],
        imageUrl: img?.src || undefined,
        itemUrl: href,
        itemId: idMatch?.[1],
      });
    }
    return results;
  });
  return domItems;
}

async function writeDebugArtifacts(page: Page, userId: string, diagnostics: CrawlDiagnostics): Promise<void> {
  const dir = process.env.CRAWLER_DEBUG_DIR;
  const environment = process.env.NODE_ENV || process.env.APP_ENV || 'development';
  if (!dir || isProductionLike(environment)) return;
  try {
    const fs = await import('fs/promises');
    const path = await import('path');
    await fs.mkdir(dir, { recursive: true });
    const prefix = path.join(dir, `goofish-store-${userId}-${Date.now()}`);
    await page.screenshot({ path: `${prefix}.png`, fullPage: true });
    await fs.writeFile(`${prefix}.html`, await page.content(), 'utf-8');
    await fs.writeFile(`${prefix}.json`, JSON.stringify(diagnostics, null, 2), 'utf-8');
    console.log('[Crawler] 已写入本地调试快照');
  } catch (e: any) {
    console.warn(`[Crawler] 写入调试快照失败: errorType=${safeErrorType(e)}`);
  }
}

async function guardMainFrameNavigation(context: BrowserContext): Promise<void> {
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
}

async function prepareContext(context: BrowserContext, cookieHeader?: string): Promise<void> {
  const cookies = parseCookieHeader(cookieHeader);
  if (cookies.length) {
    await context.addCookies(cookies);
    console.log(`[Crawler] 已注入登录 Cookie: cookieCount=${cookies.length}`);
  } else {
    console.warn('[Crawler] 未提供登录 Cookie，店铺页很可能触发登录/风控。');
  }
  await context.addInitScript(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
  });
}

const USER_ID_FIELD_RE = /["']?(?:userId|user_id|sellerId|seller_id|sellerid|shopUserId|shopId)["']?\s*[:=]\s*["']?(\d{6,})["']?/gi;

function collectUserIdsFromText(text: string, bucket: string[]): void {
  if (!text) return;
  for (const match of text.matchAll(USER_ID_FIELD_RE)) {
    if (match[1] && !bucket.includes(match[1])) bucket.push(match[1]);
  }
}

function extractUserIdFromUrl(urlStr: string): string | undefined {
  if (!urlStr) return undefined;
  const q = urlStr.match(/[?&](?:userId|user_id|sellerId|seller_id)=(\d{6,})/i);
  if (q) return q[1];
  const p = urlStr.match(/\/personal\/?(\d{6,})/i);
  if (p) return p[1];
  return undefined;
}

/**
 * 当店铺链接中没有 userId 参数时（如首页分享链接 https://www.goofish.com/?spm=...），
 * 通过浏览器实际访问页面，从 URL 跳转、网络请求/响应或页面 DOM/JS 中提取店铺 userId。
 *
 * Cookie 注入方式与店铺爬取保持一致（domain 为 .goofish.com 等）。
 */
export async function resolveStoreUserId(rawUrl: string, cookieHeader?: string): Promise<string> {
  // 关键：商机发掘店铺搜索独立决定 headless 模式，不读取 sliderSolver.ts 使用的 HEADLESS 环境变量。
  // 原因：sliderSolver.ts 在 HEADLESS=true 下成功率非常高，严禁影响；
  // 而店铺搜索在 headless 模式下 Baxia 风控识别率高，必须在 Xvfb 提供 DISPLAY 时切到 headed 模式。
  const isHeadedAvailable =
    process.platform === 'win32' ||
    process.platform === 'darwin' ||
    Boolean(process.env.DISPLAY && process.env.DISPLAY.trim());
  const headless = !isHeadedAvailable;
  const isWindows = process.platform === 'win32';
  const isLinux = process.platform !== 'win32' && process.platform !== 'darwin';
  let browser: Browser | null = null;

  console.log(`[Crawler] 启动浏览器解析店铺 userId: headless=${headless}`);

  try {
    browser = await chromium.launch({
      headless,
      chromiumSandbox: !isLinux,
      ...((isWindows || isLinux) ? { channel: 'chrome' } : {}),
      args: [
        '--disable-blink-features=AutomationControlled',
        ...(isLinux ? ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--disable-crash-reporter', '--disable-crashpad', '--disable-breakpad', '--disable-features=Crashpad'] : []),
      ],
    });

    const context = await browser.newContext({
      viewport: { width: 1440, height: 1000 },
      userAgent: USER_AGENT,
      locale: 'zh-CN',
      timezoneId: 'Asia/Shanghai',
      extraHTTPHeaders: {
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
      },
    });
    await guardMainFrameNavigation(context);
    await prepareContext(context, cookieHeader);

    const page = await context.newPage();

    // 优先级 1：mtop.idle.web.user.page.head 请求的 postData 中携带的 userId
    // （这是店铺首页头部接口，请求体形如 {"self":false,"userId":"123456789"}）
    const headApiUserIds: string[] = [];
    // 优先级 2：最终 URL 跳转后携带的 userId
    // 优先级 3：其余网络请求 URL / 响应文本中的 userId 候选
    const networkUserIds: string[] = [];
    const pendingParses: Promise<void>[] = [];

    page.on('request', (request) => {
      try {
        const reqUrl = request.url();
        const isHeadApi = reqUrl.includes('mtop.idle.web.user.page.head');
        // 从请求 URL query 中提取 userId
        const urlUid = extractUserIdFromUrl(reqUrl);
        if (urlUid) {
          const bucket = isHeadApi ? headApiUserIds : networkUserIds;
          if (!bucket.includes(urlUid)) bucket.push(urlUid);
        }
        // 从 POST body 中提取 userId（mtop 接口的 data 字段）
        if (isHeadApi) {
          const postData = request.postData();
          if (postData) collectUserIdsFromText(postData, headApiUserIds);
        }
      } catch {
        // 忽略个别请求解析异常
      }
    });

    page.on('response', (response: PlaywrightResponse) => {
      const parsePromise = (async () => {
        const req = response.request();
        const resourceType = req.resourceType();
        if (!['xhr', 'fetch', 'document', 'script'].includes(resourceType)) return;
        const reqUrl = req.url();
        const urlUid = extractUserIdFromUrl(reqUrl);
        if (urlUid && !networkUserIds.includes(urlUid)) networkUserIds.push(urlUid);
        const contentType = response.headers()['content-type'] || '';
        if (!/json|javascript|text\/html|text\/plain/i.test(contentType)) return;
        const text = await response.text().catch(() => '');
        if (!text || text.length < 40) return;
        collectUserIdsFromText(text, networkUserIds);
      })();
      pendingParses.push(parsePromise.catch(() => undefined));
    });

    await page.goto(rawUrl, { waitUntil: 'domcontentloaded', timeout: 45000 });
    // 等待页面跳转/异步请求完成
    await page.waitForTimeout(3000);
    try {
      await page.waitForLoadState('networkidle', { timeout: 4000 });
    } catch {
      // 长轮询/埋点会导致 networkidle 超时，忽略
    }
    await Promise.allSettled(pendingParses);

    // 优先级 2：最终 URL 跳转后携带的 userId
    const finalUrl = page.url();
    const finalUrlUid = extractUserIdFromUrl(finalUrl);

    // 优先级 4：页面 DOM/JS 中的 userId（script 标签、链接等）
    const domUserIds = await page.evaluate(() => {
      const found: string[] = [];
      const re = /["']?(?:userId|user_id|sellerId|seller_id|sellerid|shopUserId|shopId)["']?\s*[:=]\s*["']?(\d{6,})["']?/gi;
      // 1. inline script 内容
      const scripts = Array.from(document.querySelectorAll('script'));
      for (const s of scripts) {
        const text = s.textContent || '';
        for (const m of text.matchAll(re)) {
          if (m[1] && !found.includes(m[1])) found.push(m[1]);
        }
      }
      // 2. 指向店铺的链接 /personal?userId=xxx
      const links = Array.from(document.querySelectorAll('a[href]')) as HTMLAnchorElement[];
      for (const a of links) {
        const m = (a.href || '').match(/[?&](?:userId|user_id|sellerId|seller_id)=(\d{6,})/i)
          || (a.href || '').match(/\/personal\/?(\d{6,})/i);
        if (m && !found.includes(m[1])) found.push(m[1]);
      }
      return found;
    });

    // 按优先级合并候选
    const ordered: string[] = [];
    const pushIfNew = (id?: string) => {
      if (id && !ordered.includes(id)) ordered.push(id);
    };
    headApiUserIds.forEach(pushIfNew);
    pushIfNew(finalUrlUid);
    networkUserIds.forEach(pushIfNew);
    domUserIds.forEach(pushIfNew);

    if (ordered.length === 0) {
      throw new Error('无法从页面中解析出店铺 userId，请确认链接是否为有效的闲鱼店铺链接');
    }

    const resolved = ordered[0];
    console.log(`[Crawler] 浏览器解析店铺 userId 成功: candidateCount=${ordered.length}`);
    return resolved;
  } finally {
    if (browser) {
      await browser.close();
      console.log('[Crawler] userId 解析浏览器已关闭');
    }
  }
}

const ITEM_DETAIL_API_MARKER = 'mtop.taobao.idle.pc.detail';
const configuredMaxDetailFetches = Number(process.env.CRAWLER_MAX_DETAIL_FETCHES || 30);
const MAX_DETAIL_FETCHES = Number.isSafeInteger(configuredMaxDetailFetches)
  ? Math.max(0, Math.min(configuredMaxDetailFetches, 100)) : 30;

/**
 * 打开商品详情页（必须用 ?id= 而非 ?itemId=，否则闲鱼网页 JS 会发送空 itemId），
 * 拦截 mtop.taobao.idle.pc.detail 响应，提取 data.itemDO.desc 作为商品文案。
 *
 * 事件驱动：用 Promise.race 竞速等待 detail 响应到达 vs. 8 秒超时，
 * 响应到达后立即返回，不固定等待。
 */
async function fetchItemDescription(
  context: BrowserContext,
  itemId: string
): Promise<string | undefined> {
  const detailUrl = `https://www.goofish.com/item?id=${itemId}`;
  const page = await context.newPage();

  let resolveDetail!: (desc: string | undefined) => void;
  const detailPromise = new Promise<string | undefined>((resolve) => { resolveDetail = resolve; });
  let settled = false;

  const responseHandler = async (response: PlaywrightResponse) => {
    const reqUrl = response.url() || '';
    if (!reqUrl.includes(ITEM_DETAIL_API_MARKER)) return;
    try {
      const text = await response.text();
      if (!text || text.includes('FAIL_BIZ_PARAM_ERROR')) return;
      const parsed = JSON.parse(text);
      const desc = parsed?.data?.itemDO?.desc;
      if (typeof desc === 'string' && desc.trim()) {
        if (!settled) { settled = true; resolveDetail(desc.trim()); }
      }
    } catch {
      // 忽略解析异常
    }
  };
  page.on('response', responseHandler);

  try {
    await page.goto(detailUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
    // 竞速：detail 响应到达 vs. 8 秒超时
    const desc = await Promise.race([
      detailPromise,
      new Promise<string | undefined>((resolve) => setTimeout(() => resolve(undefined), 8000)),
    ]);
    return desc;
  } catch {
    return undefined;
  } finally {
    try { page.off('response', responseHandler); } catch {}
    try { await page.close(); } catch {}
  }
}

/**
 * 主爬取函数：使用 Cookie 打开店铺页，尽可能滚动到底并收集该店铺全部在售商品。
 */
export async function crawlGoofishStoreDetailed(url: string, cookieHeader?: string): Promise<CrawlGoofishStoreResult> {
  const { userId, normalizedUrl } = parseGoofishStoreUrl(url);
  // 关键：商机发掘店铺搜索独立决定 headless 模式，不读取 sliderSolver.ts 使用的 HEADLESS 环境变量。
  // 原因：sliderSolver.ts 在 HEADLESS=true 下成功率非常高，严禁影响；
  // 而店铺搜索在 headless 模式下 Baxia 风控识别率高，必须在 Xvfb 提供 DISPLAY 时切到 headed 模式。
  const isHeadedAvailable =
    process.platform === 'win32' ||
    process.platform === 'darwin' ||
    Boolean(process.env.DISPLAY && process.env.DISPLAY.trim());
  const headless = !isHeadedAvailable;
  const isWindows = process.platform === 'win32';
  const isLinux = process.platform !== 'win32' && process.platform !== 'darwin';
  const diagnostics: CrawlDiagnostics = { networkCandidateCount: 0, domCandidateCount: 0 };
  const expectedItemCount = await fetchExpectedStoreItemCount(userId, cookieHeader);
  diagnostics.expectedItemCount = expectedItemCount;

  console.log(`[Crawler] 开始爬取店铺全部商品: expected=${expectedItemCount ?? 'unknown'}, headless=${headless}`);

  let browser: Browser | null = null;
  const networkItems: CrawledItem[] = [];
  const pendingParses: Promise<void>[] = [];

  try {
    browser = await chromium.launch({
      headless,
      chromiumSandbox: !isLinux,
      ...((isWindows || isLinux) ? { channel: 'chrome' } : {}),
      args: [
        '--disable-blink-features=AutomationControlled',
        ...(isLinux ? ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--disable-crash-reporter', '--disable-crashpad', '--disable-breakpad', '--disable-features=Crashpad'] : []),
      ],
    });

    const context = await browser.newContext({
      viewport: { width: 1440, height: 1000 },
      userAgent: USER_AGENT,
      locale: 'zh-CN',
      timezoneId: 'Asia/Shanghai',
      extraHTTPHeaders: {
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
      },
    });
    await guardMainFrameNavigation(context);
    await prepareContext(context, cookieHeader);

    const page = await context.newPage();
    page.on('response', (response: PlaywrightResponse) => {
      const parsePromise = (async () => {
        const req = response.request();
        const resourceType = req.resourceType();
        if (!['xhr', 'fetch', 'document', 'script'].includes(resourceType)) return;
        const reqUrl = req.url() || '';
        // 仅处理闲鱼 MTOP API 响应（店铺商品列表相关）
        const isMtopApi = reqUrl.includes('mtop.idle') || reqUrl.includes('mtop.taobao.idle');
        if (!isMtopApi) return;
        const contentType = response.headers()['content-type'] || '';
        if (!/json|javascript|text\/html|text\/plain/i.test(contentType)) return;
        const text = await response.text().catch(() => '');
        if (!text || text.length < 80) return;
        // 提取 MTOP API 名称用于日志
        const apiMatch = reqUrl.match(/mtop\.[a-z0-9.]+/i);
        const apiName = apiMatch?.[0] || 'unknown';
        const beforeCount = networkItems.length;
        for (const json of parseJsonLike(text)) {
          extractItemsFromJson(json, networkItems);
        }
        const added = networkItems.length - beforeCount;
        // ★ 增强调试日志：无论是否提取到商品，都输出拦截到的 MTOP API
        console.log(`[Crawler] MTOP 拦截: api=${apiName}, len=${text.length}, added=${added}, total=${networkItems.length}, hasCardList=${text.includes('cardList')}, hasResultList=${text.includes('resultList')}`);
      })();
      pendingParses.push(parsePromise.catch(() => undefined));
    });

    await page.goto(normalizedUrl, { waitUntil: 'domcontentloaded', timeout: 45000 });
    diagnostics.lastUrl = page.url();
    diagnostics.pageTitle = await page.title().catch(() => undefined);
    console.log('[Crawler] 店铺页面加载完成');
    await page.waitForTimeout(2500);
    await tryClickItemsTab(page);

    const bodyText = await page.evaluate(() => document.body.innerText || '');
    console.log(`[Crawler] 页面正文已读取: length=${bodyText.length}`);
    const blockedKeyword = BLOCK_KEYWORDS.find((kw) => bodyText.includes(kw));
    diagnostics.blockedKeyword = blockedKeyword;
    if (blockedKeyword) {
      await writeDebugArtifacts(page, userId, diagnostics);
      throw new Error(`页面阻断: 检测到「${blockedKeyword}」，请确认 Cookie 未过期且未触发风控`);
    }

    await autoScrollUntilStable(page, () => deduplicateItems(networkItems).length, expectedItemCount);
    await Promise.allSettled(pendingParses);
    await page.waitForTimeout(1000);

    // DOM 兜底提取：仅作为网络拦截的补充。即使失败（浏览器结构变更/序列化异常）也不应中断主流程，
    // 因为 networkItems 通常已包含完整商品列表。
    let domItems: CrawledItem[] = [];
    try {
      domItems = await extractDomItems(page);
    } catch (domErr: any) {
      console.warn(`[Crawler] DOM 兜底提取失败，跳过(不影响网络拦截结果): errorType=${safeErrorType(domErr)}`);
    }
    diagnostics.networkCandidateCount = networkItems.length;
    diagnostics.domCandidateCount = domItems.length;

    let items = deduplicateItems([...networkItems, ...domItems]);
    if (items.length === 0) {
      await writeDebugArtifacts(page, userId, diagnostics);
      throw new Error(
        '未提取到店铺商品。请确认 Cookie 有效、店铺确实存在在售商品，并尝试设置 HEADLESS=false 与 CRAWLER_DEBUG_DIR 查看页面是否被登录/风控/空店铺拦截。'
      );
    }
    if (expectedItemCount && expectedItemCount > 0 && items.length < Math.min(expectedItemCount, 3)) {
      await writeDebugArtifacts(page, userId, diagnostics);
      throw new Error(
        `店铺商品提取不足: 预期约 ${expectedItemCount} 个，仅提取 ${items.length} 个。` +
        '这通常是 Cookie 失效、页面风控或前端结构变更导致，请设置 HEADLESS=false 与 CRAWLER_DEBUG_DIR 复核。'
      );
    }

    await writeDebugArtifacts(page, userId, diagnostics);
    console.log(`[Crawler] 店铺爬取完成: items=${items.length}, expected=${expectedItemCount ?? 'unknown'}, network=${networkItems.length}, dom=${domItems.length}`);

    // ★ 为每个商品补充详情页描述（店铺列表 API 不含商品文案，需逐个访问详情页获取）
    //   使用 ?id= 格式打开 https://www.goofish.com/item?id={itemId}，
    //   拦截 mtop.taobao.idle.pc.detail 响应，提取 data.itemDO.desc
    //   并行获取（有限并发 5），避免串行 30×8s=240s 接近前端 5 分钟轮询超时
    const itemsNeedingDesc = items.filter((it) => it.itemId && !it.description);
    const fetchCount = Math.min(itemsNeedingDesc.length, MAX_DETAIL_FETCHES);
    if (fetchCount > 0) {
      console.log(`[Crawler] 开始并行获取商品描述: count=${fetchCount}/${itemsNeedingDesc.length}, concurrency=5`);
      const DETAIL_CONCURRENCY = 5;
      let descOk = 0;
      let completed = 0;
      for (let start = 0; start < fetchCount; start += DETAIL_CONCURRENCY) {
        const batch = itemsNeedingDesc.slice(start, start + DETAIL_CONCURRENCY);
        const results = await Promise.allSettled(
          batch.map((item) => fetchItemDescription(context, item.itemId!))
        );
        results.forEach((res, idx) => {
          completed += 1;
          if (res.status === 'fulfilled' && res.value) {
            batch[idx].description = res.value;
            descOk += 1;
          }
        });
        console.log(`[Crawler] 描述获取进度: ${completed}/${fetchCount}, 成功=${descOk}`);
      }
      console.log(`[Crawler] 商品描述获取完成: 成功=${descOk}/${fetchCount}`);
    }

    return { items, diagnostics };
  } finally {
    if (browser) {
      await browser.close();
      console.log('[Crawler] 浏览器已关闭');
    }
  }
}

export async function crawlGoofishStore(url: string, cookieHeader?: string): Promise<CrawledItem[]> {
  const result = await crawlGoofishStoreDetailed(url, cookieHeader);
  return result.items;
}
