/**
 * 闲鱼扫码登录求解器
 * ==================
 *
 * 使用 Playwright 打开淘宝/闲鱼登录页面：
 * 1. 拦截页面二维码图片（截图二维码区域或网络响应）
 * 2. 等待用户用闲鱼 App 扫码确认登录
 * 3. 监听登录成功跳转（回到 goofish.com 首页）
 * 4. context.cookies() 一次性提取所有 Cookie
 * 5. 返回 Cookie 字符串供 Python 端写入 DB
 *
 * 与 sliderSolver.ts 的区别：
 * - sliderSolver 处理"已登录但出现滑块"场景
 * - qrLoginSolver 处理"Session 过期需重新登录"场景
 *
 * 与 xianyu_qr_login.py（直接调用 mtop API）的区别：
 * - Python 实现依赖逆向接口，可能不稳定
 * - 本实现走真实浏览器，与用户手动登录完全一致，最稳定
 */
import { chromium, type Browser, type BrowserContext, type Page, type BrowserContextOptions } from 'playwright';
import { parseCookieString } from './sliderSolver.js';
import {
  isAllowedBrowserNavigationUrl,
  isProductionLike,
  isSafeBrowserResourceUrl,
  safeErrorType,
  toPublicCrawlerError,
} from '../policy.js';

export interface QrLoginSolveOptions {
  /** 旧的 Cookie（可选，用于复用部分会话状态） */
  cookieStr?: string;
  /** 登录入口 URL，默认闲鱼首页 */
  targetUrl?: string;
  /** 是否无头模式，默认 false（扫码登录需要有头模式方便用户扫码） */
  headless?: boolean;
  /** 等待扫码确认的超时时间（毫秒），默认 120000 = 2 分钟 */
  scanTimeoutMs?: number;
  /** 是否返回二维码图片 bytes（默认 true） */
  captureQrImage?: boolean;
}

export interface QrLoginSolveResult {
  /** 整体是否成功（用户已扫码登录并提取到 Cookie） */
  ok: boolean;
  /** 登录阶段：qr_ready / waiting_scan / scanned / login_success / timeout / error */
  stage: string;
  /** 二维码图片 PNG bytes（仅当 captureQrImage=true 且二维码已就绪时返回） */
  qrImageBytes?: Buffer;
  /** 提取到的 Cookie 字符串（;分隔，可直接写入 DB） */
  cookieStr?: string;
  /** 关键 Cookie 中的 unb（用户 ID） */
  unb?: string;
  /** _m_h5_tk 令牌 */
  mH5Tk?: string;
  /** 失败/超时/错误信息 */
  error?: string;
  /** 总耗时（毫秒） */
  durationMs: number;
}

const DEFAULT_TARGET_URL = 'https://www.goofish.com/';
const DEFAULT_SCAN_TIMEOUT = 120000; // 2 分钟

/**
 * 启动浏览器并打开闲鱼首页。
 * 若未登录会自动跳转到登录页，函数会等待登录页二维码就绪并截图。
 */
export async function solveQrLoginInBrowser(
  options: QrLoginSolveOptions = {}
): Promise<QrLoginSolveResult> {
  const startTime = Date.now();
  const targetUrl = options.targetUrl || DEFAULT_TARGET_URL;
  const headless = isProductionLike(process.env.NODE_ENV || process.env.APP_ENV)
    ? true : options.headless ?? false;
  const scanTimeoutMs = options.scanTimeoutMs ?? DEFAULT_SCAN_TIMEOUT;
  const captureQrImage = options.captureQrImage ?? true;

  let browser: Browser | null = null;
  let context: BrowserContext | null = null;
  let page: Page | null = null;

  try {
    // === 1. 启动浏览器 ===
    const contextOptions: BrowserContextOptions = {
      viewport: { width: 1280, height: 800 },
      userAgent:
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
        '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      locale: 'zh-CN',
    };
    // 注入旧 Cookie（如果有），可能跳过登录直接进入首页
    if (options.cookieStr) {
      const cookies = parseCookieString(options.cookieStr);
      contextOptions.storageState = { cookies, origins: [] };
    }

    browser = await chromium.launch({
      headless,
      chromiumSandbox: true,
      args: [
        '--disable-blink-features=AutomationControlled',
      ],
    });
    context = await browser.newContext(contextOptions);
    await guardLoginNavigation(context);

    // 反检测
    await context.addInitScript(() => {
      Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
      (window as any).chrome = { runtime: {} };
      Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
      Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
    });

    page = await context.newPage();
    console.log('[QrLoginSolver] 访问登录目标页面');
    await page.goto(targetUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });

    // === 2. 判断当前是否已登录 ===
    // 已登录：URL 停留在 goofish.com 且页面包含"我想要"等关键词
    // 未登录：跳转到 login.taobao.com 或显示登录入口
    await page.waitForTimeout(2000);
    const currentUrl = page.url();
    const isLoggedIn = !isLoginPageUrl(currentUrl) && !(await detectLoginIndicator(page));

    if (isLoggedIn) {
      console.log('[QrLoginSolver] 检测到已登录状态，直接提取 Cookie');
      const cookieStr = await extractCookies(context);
      const { unb, mH5Tk } = parseKeyCookies(cookieStr);
      return {
        ok: true,
        stage: 'login_success',
        cookieStr,
        unb,
        mH5Tk,
        durationMs: Date.now() - startTime,
      };
    }

    // === 3. 等待二维码就绪并截图 ===
    console.log('[QrLoginSolver] 未登录，等待二维码出现');
    let qrImageBytes: Buffer | undefined;
    if (captureQrImage) {
      try {
        qrImageBytes = await captureQrCodeImage(page);
        console.log(
          `[QrLoginSolver] 二维码已捕获，大小=${qrImageBytes?.length || 0} bytes`
        );
      } catch (e: any) {
        console.warn(`[QrLoginSolver] 二维码截图失败: errorType=${safeErrorType(e)}`);
      }
    }

    // === 4. 等待用户扫码登录成功 ===
    console.log(`[QrLoginSolver] 等待用户扫码（超时 ${scanTimeoutMs}ms）`);
    const loginSuccess = await waitForLoginSuccess(page, scanTimeoutMs);
    if (!loginSuccess) {
      return {
        ok: false,
        stage: 'timeout',
        qrImageBytes,
        error: '等待用户扫码超时',
        durationMs: Date.now() - startTime,
      };
    }

    // === 5. 提取 Cookie ===
    console.log('[QrLoginSolver] 登录成功，提取 Cookie');
    // 等待 2 秒让所有 Set-Cookie 完成
    await page.waitForTimeout(2000);
    const cookieStr = await extractCookies(context);
    const { unb, mH5Tk } = parseKeyCookies(cookieStr);
    if (!cookieStr || !unb) {
      return {
        ok: false,
        stage: 'error',
        qrImageBytes,
        error: '登录成功但 Cookie 提取失败（unb 为空）',
        durationMs: Date.now() - startTime,
      };
    }

    return {
      ok: true,
      stage: 'login_success',
      cookieStr,
      unb,
      mH5Tk,
      durationMs: Date.now() - startTime,
    };
  } catch (e: any) {
    console.error(`[QrLoginSolver] operation=solve errorType=${safeErrorType(e)}`);
    return {
      ok: false,
      stage: 'error',
      error: toPublicCrawlerError(e, '二维码登录处理失败'),
      durationMs: Date.now() - startTime,
    };
  } finally {
    try {
      if (context) await context.close();
    } catch {}
    try {
      if (browser) await browser.close();
    } catch {}
  }
}

export async function completeQrLoginSession(
  context: BrowserContext,
  page: Page,
  scanTimeoutMs: number = DEFAULT_SCAN_TIMEOUT,
): Promise<QrLoginSolveResult> {
  const startTime = Date.now();
  const timeout = Number.isSafeInteger(scanTimeoutMs)
    ? Math.max(10000, Math.min(scanTimeoutMs, 300000)) : DEFAULT_SCAN_TIMEOUT;
  try {
    const loginSuccess = await waitForLoginSuccess(page, timeout);
    if (!loginSuccess) {
      return {
        ok: false,
        stage: 'timeout',
        error: '等待用户扫码超时',
        durationMs: Date.now() - startTime,
      };
    }

    await page.waitForTimeout(1500);
    const cookieStr = await extractCookies(context);
    const { unb, mH5Tk } = parseKeyCookies(cookieStr);
    if (!cookieStr || !unb) {
      return {
        ok: false,
        stage: 'error',
        error: '登录成功但未能提取有效的闲鱼 Cookie',
        durationMs: Date.now() - startTime,
      };
    }
    return {
      ok: true,
      stage: 'login_success',
      cookieStr,
      unb,
      mH5Tk,
      durationMs: Date.now() - startTime,
    };
  } catch (error) {
    console.error(`[QrLoginSolver] operation=completeSession errorType=${safeErrorType(error)}`);
    return {
      ok: false,
      stage: 'error',
      error: toPublicCrawlerError(error, '二维码登录处理失败'),
      durationMs: Date.now() - startTime,
    };
  }
}

/**
 * 启动浏览器并只获取二维码图片（不等待扫码完成）。
 *
 * 用于"用户在飞书回复请求二维码"场景：
 * Python 端调用此函数获取二维码图片 bytes，发送给用户后关闭浏览器。
 * 然后再次调用 solveQrLoginInBrowser（复用 Cookie）等待扫码完成。
 *
 * 注意：调用方需自行关闭浏览器，此处不关闭。
 */
export async function captureQrCodeOnly(
  options: QrLoginSolveOptions = {}
): Promise<{ ok: boolean; qrImageBytes?: Buffer; error?: string; browser?: Browser; context?: BrowserContext; page?: Page }> {
  const targetUrl = options.targetUrl || DEFAULT_TARGET_URL;
  const headless = isProductionLike(process.env.NODE_ENV || process.env.APP_ENV)
    ? true : options.headless ?? false;
  let browser: Browser | undefined;
  let context: BrowserContext | undefined;

  try {
    const contextOptions: BrowserContextOptions = {
      viewport: { width: 1280, height: 800 },
      userAgent:
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
        '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      locale: 'zh-CN',
    };
    if (options.cookieStr) {
      const cookies = parseCookieString(options.cookieStr);
      contextOptions.storageState = { cookies, origins: [] };
    }

    browser = await chromium.launch({
      headless,
      chromiumSandbox: true,
      args: [
        '--disable-blink-features=AutomationControlled',
      ],
    });
    context = await browser.newContext(contextOptions);
    await guardLoginNavigation(context);
    await context.addInitScript(() => {
      Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
      (window as any).chrome = { runtime: {} };
      Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
      Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
    });
    const page = await context.newPage();
    await page.goto(targetUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(2000);

    // 检测是否已登录
    const currentUrl = page.url();
    if (!isLoginPageUrl(currentUrl) && !(await detectLoginIndicator(page))) {
      // 已登录，无需扫码
      return { ok: true, browser, context, page };
    }

    const qrImageBytes = await captureQrCodeImage(page);
    return {
      ok: !!qrImageBytes,
      qrImageBytes,
      browser,
      context,
      page,
    };
  } catch (e: any) {
    console.error(`[QrLoginSolver] operation=capture errorType=${safeErrorType(e)}`);
    try { if (context) await context.close(); } catch {}
    try { if (browser) await browser.close(); } catch {}
    return { ok: false, error: toPublicCrawlerError(e, '二维码捕获失败') };
  }
}

// ============================================================
// 内部辅助函数
// ============================================================

function isLoginPageUrl(url: string): boolean {
  return (
    /login\.taobao\.com/i.test(url) ||
    /login\.goofish\.com/i.test(url) ||
    /\/login\b/i.test(url) ||
    /\/uiLogin\b/i.test(url)
  );
}

async function guardLoginNavigation(context: BrowserContext): Promise<void> {
  await context.route('**/*', async (route) => {
    const request = route.request();
    if (!isSafeBrowserResourceUrl(request.url())) {
      await route.abort('blockedbyclient');
      return;
    }
    if (!request.isNavigationRequest() || request.frame().parentFrame()
        || isAllowedBrowserNavigationUrl(request.url(), true)) {
      await route.continue();
      return;
    }
    await route.abort('blockedbyclient');
  });
}

async function detectLoginIndicator(page: Page): Promise<boolean> {
  try {
    return await page.evaluate(() => {
      const text = document.body ? document.body.innerText : '';
      if (
        /扫码登录|手机号登录|账号密码登录/i.test(text) &&
        !/我想要|猜你喜欢|闲置/i.test(text)
      ) {
        return true;
      }
      return false;
    });
  } catch {
    return false;
  }
}

/**
 * 截取二维码区域图片。
 *
 * 淘宝/闲鱼登录页的二维码通常在 iframe 或 div.qrcode / #J_QRCodeImg 等元素中。
 * 优先按选择器定位，找不到则截取整个页面。
 */
async function captureQrCodeImage(page: Page): Promise<Buffer | undefined> {
  // 选择器列表：从精确到宽泛
  const qrSelectors = [
    '#J_QRCodeImg',
    '.qrcode-img',
    '.J_QRCodeImg',
    'img[src*="qrcode"]',
    'canvas.qrcode',
    '#login-qrcode',
    '.login-qrcode',
    'iframe[src*="login"]', // 部分场景二维码在 iframe 内
  ];

  // 等待登录页完全渲染
  await page.waitForTimeout(1500);

  // 先尝试主文档
  for (const sel of qrSelectors) {
    try {
      const el = await page.$(sel);
      if (el) {
        // 元素截图，质量更高
        const buf = await el.screenshot({ type: 'png' });
        if (buf && buf.length > 0) {
          console.log(`[QrLoginSolver] 二维码截图成功 selector=${sel}`);
          return buf;
        }
      }
    } catch (e: any) {
      // continue
    }
  }

  // 尝试 iframe 内查找
  for (const frame of page.frames()) {
    for (const sel of qrSelectors) {
      try {
        const el = await frame.$(sel);
        if (el) {
          const buf = await el.screenshot({ type: 'png' });
          if (buf && buf.length > 0) {
            console.log(`[QrLoginSolver] 二维码截图成功（iframe）selector=${sel}`);
            return buf;
          }
        }
      } catch {
        // continue
      }
    }
  }

  return undefined;
}

/**
 * 等待用户扫码登录成功。
 *
 * 检测方式：
 * 1. URL 跳转回 goofish.com（不再是 login.taobao.com）
 * 2. 页面包含"我想要/猜你喜欢"等已登录关键词
 * 3. Cookie 中出现 unb 且不为空
 */
async function waitForLoginSuccess(page: Page, timeoutMs: number): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const url = page.url();
      if (!isLoginPageUrl(url) && !(await detectLoginIndicator(page))) {
        // 二次确认：检查 Cookie 中是否有 unb
        const cookies = await page.context().cookies();
        const unbCookie = cookies.find((c) => c.name === 'unb');
        if (unbCookie && unbCookie.value && unbCookie.value !== '0') {
          return true;
        }
      }
    } catch {
      // 页面可能正在跳转，忽略
    }
    await page.waitForTimeout(1500);
  }
  return false;
}

/**
 * 从 BrowserContext 提取所有 Cookie 并拼接成字符串。
 */
async function extractCookies(context: BrowserContext): Promise<string> {
  const cookies = await context.cookies();
  return cookies
    .filter((c) => c.name && c.value
      && (c.domain === 'goofish.com' || c.domain.endsWith('.goofish.com')))
    .map((c) => `${c.name}=${c.value}`)
    .join('; ');
}

/**
 * 从 Cookie 字符串中解析关键 Cookie：unb 和 _m_h5_tk。
 */
function parseKeyCookies(cookieStr: string): { unb?: string; mH5Tk?: string } {
  if (!cookieStr) return {};
  const map: Record<string, string> = {};
  for (const part of cookieStr.split(';')) {
    const idx = part.indexOf('=');
    if (idx > 0) {
      const k = part.slice(0, idx).trim();
      const v = part.slice(idx + 1).trim();
      if (k) map[k] = v;
    }
  }
  return {
    unb: map['unb'] || undefined,
    mH5Tk: map['_m_h5_tk'] || undefined,
  };
}
