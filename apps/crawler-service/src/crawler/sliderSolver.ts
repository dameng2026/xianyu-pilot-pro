/**
 * 闲鱼滑块验证自动求解器
 *
 * 使用 Playwright 启动有头浏览器，访问滑块验证页面或闲鱼主页，
 * 检测是否出现滑块验证弹窗，自动拖动滑块完成验证。
 *
 * 实现要点：
 * 1. 注入用户 Cookie 保持登录态
 * 2. 智能检测 #nc_1 / .nc_wrapper / iframe#baxia-dialog 等阿里 Baxia 风控组件
 * 3. 模拟人工拖动：先快后慢、带随机抖动、模拟人类轨迹
 * 4. 检测验证结果：成功（弹窗消失 / 出现成功标识）/ 失败（出现错误提示）
 * 5. 失败时返回详细错误，调用方可重试或回退到人工处理
 */
import { chromium, type Browser, type Page, type BrowserContextOptions, type Cookie } from 'playwright';
import path from 'path';
import fs from 'fs/promises';
import {
  isAllowedBrowserNavigationUrl,
  isProductionLike,
  isSafeBrowserResourceUrl,
  safeErrorType,
  toPublicCrawlerError,
} from '../policy.js';

export interface SlideSolveOptions {
  cookieStr?: string;
  targetUrl?: string;     // 默认为闲鱼首页
  headless?: boolean;     // 默认 false（滑块识别需有头模式更稳定）
  maxRetries?: number;    // 单次会话最多重试次数，默认 3
  timeoutMs?: number;     // 单次操作超时，默认 30000
}

export interface SlideSolveResult {
  ok: boolean;
  solved: boolean;            // 是否成功通过滑块
  captchaDetected: boolean;   // 是否检测到滑块
  attempts: number;           // 实际尝试次数
  error?: string;
  screenshotPath?: string;    // 失败时的截图路径
  durationMs: number;
}

// 默认访问闲鱼消息页面 —— 滑块验证通常在消息页弹出（用户连接消息时触发）
// 访问首页不会弹出滑块，会导致检测不到滑块而误报成功
const DEFAULT_TARGET_URL = 'https://www.goofish.com/im';
const BAXIA_SELECTORS = [
  '#nc_1',              // 阿里 Baxia 标准滑块容器
  '.nc_wrapper',
  '#baxia-dialog',
  'iframe[src*="baxia"]',
  '.J_MIDDLEWARE_FRAME',
  'iframe[id*="baxia"]',
  '.slide-verify',
  '#nc_1_n1z',          // 滑块按钮
  '.btn_slide',
];

function resolveHeadlessMode(headless?: boolean): boolean {
  if (isProductionLike(process.env.NODE_ENV || process.env.APP_ENV)) return true;
  if (typeof headless === 'boolean') {
    return headless;
  }
  if (process.env.HEADLESS === 'true') {
    return true;
  }
  if (process.env.HEADLESS === 'false') {
    return false;
  }
  return process.platform !== 'win32' && !process.env.DISPLAY;
}

/**
 * 将 Cookie 字符串解析为 Playwright Cookie 数组
 */
export function parseCookieString(cookieStr: string, domain: string = '.goofish.com'): Cookie[] {
  if (!cookieStr) return [];
  const cookies: Cookie[] = [];
  for (const part of cookieStr.split(';')) {
    const trimmed = part.trim();
    if (!trimmed) continue;
    const eqIdx = trimmed.indexOf('=');
    if (eqIdx <= 0) continue;
    const name = trimmed.substring(0, eqIdx).trim();
    const value = trimmed.substring(eqIdx + 1).trim();
    if (!name || !value) continue;
    cookies.push({
      name,
      value,
      domain,
      path: '/',
      expires: -1,
      httpOnly: false,
      secure: true,
      sameSite: 'Lax',
    } as Cookie);
  }
  return cookies;
}

/**
 * 检测页面是否出现滑块验证组件
 */
async function detectCaptcha(page: Page): Promise<{ detected: boolean; selector?: string; iframe?: any }> {
  // 直接在主文档检测
  for (const selector of BAXIA_SELECTORS) {
    try {
      const elem = await page.$(selector);
      if (elem && await elem.isVisible()) {
        return { detected: true, selector };
      }
    } catch {
      // ignore
    }
  }

  // 检测 iframe 中的滑块
  const frames = page.frames();
  for (const frame of frames) {
    if (frame === page.mainFrame()) continue;
    for (const selector of BAXIA_SELECTORS) {
      try {
        const elem = await frame.$(selector);
        if (elem && await elem.isVisible()) {
          return { detected: true, selector, iframe: frame };
        }
      } catch {
        // ignore
      }
    }
  }

  return { detected: false };
}

/**
 * 在指定 frame 及其所有子 frame 中递归查找滑块按钮
 * baxia 滑块通常嵌套在多层 iframe 中，需要递归查找
 */
async function findSliderButtonInFrames(frame: any, selectors: string[]): Promise<{ button: any; frame: any } | null> {
  // 当前 frame 查找
  for (const sel of selectors) {
    try {
      const button = await frame.$(sel);
      if (button) {
        const box = await button.boundingBox();
        if (box && box.width > 0) {
          return { button, frame };
        }
      }
    } catch {
      // ignore
    }
  }
  // 递归查找子 frame
  let childFrames: any[] = [];
  try {
    childFrames = frame.childFrames ? frame.childFrames() : [];
  } catch {
    childFrames = [];
  }
  for (const childFrame of childFrames) {
    try {
      const result = await findSliderButtonInFrames(childFrame, selectors);
      if (result) return result;
    } catch {
      // ignore
    }
  }
  return null;
}

/**
 * 获取滑块按钮位置和滑块轨道宽度
 * 递归查找所有嵌套 iframe 中的滑块按钮（baxia 滑块通常在多层 iframe 中）
 */
async function getSliderInfo(frame: any): Promise<{ button: any; trackWidth: number; buttonBox: { x: number; y: number; width: number; height: number }; ownerFrame: any } | null> {
  const buttonSelectors = ['#nc_1_n1z', '.btn_slide', '.nc_iconfont', '.slide-btn', '#nc_1_n1t', '.nc-lang-cnt', '[data-role="slider"]'];
  // 递归查找所有 frame（包括嵌套 iframe）中的滑块按钮
  const found = await findSliderButtonInFrames(frame, buttonSelectors);
  if (!found) return null;

  const { button, frame: ownerFrame } = found;
  const box = await button.boundingBox();
  if (!box) return null;

  // 在按钮所在的 frame 中查找滑块轨道
  const trackSelectors = ['.nc_scale', '.scale_text', '.slide-track', '#nc_1__scale', '.nc-lang'];
  let trackWidth = 300; // 默认轨道宽度
  for (const tsel of trackSelectors) {
    try {
      const track = await ownerFrame.$(tsel);
      if (track) {
        const trackBox = await track.boundingBox();
        if (trackBox && trackBox.width > 0) {
          trackWidth = trackBox.width - box.width;
          break;
        }
      }
    } catch {
      // ignore
    }
  }
  return { button, trackWidth, buttonBox: box, ownerFrame };
}

/**
 * 模拟人工拖动滑块：先快后慢、带随机抖动
 */
async function humanLikeDrag(frame: any, button: any, startX: number, startY: number, distance: number): Promise<void> {
  // 鼠标按下
  await button.dispatchEvent('mousedown');
  await frame.waitForTimeout(100);

  // 分多步拖动，模拟人类轨迹
  const steps = 25 + Math.floor(Math.random() * 15);  // 25-40 步
  let currentX = startX;
  let currentY = startY;

  for (let i = 1; i <= steps; i++) {
    // 先快后慢：使用二次方缓动
    const progress = i / steps;
    const eased = progress * progress * (3 - 2 * progress);  // smoothstep
    const targetX = startX + distance * eased;

    // Y 方向小幅随机抖动（模拟手抖）
    const jitter = (Math.random() - 0.5) * 4;

    currentX = targetX;
    currentY = startY + jitter;

    // 通过 page.mouse 模拟鼠标移动
    await button.dispatchEvent('mousemove', {
      clientX: currentX,
      clientY: currentY,
    });

    // 每步间隔随机化（10-50ms）
    const delay = 10 + Math.random() * 40;
    await frame.waitForTimeout(delay);
  }

  // 终点稍微过冲一下再回退（人类拖动常见行为）
  await frame.waitForTimeout(50);
  await button.dispatchEvent('mousemove', {
    clientX: startX + distance + 5,
    clientY: currentY,
  });
  await frame.waitForTimeout(80);
  await button.dispatchEvent('mousemove', {
    clientX: startX + distance,
    clientY: currentY,
  });

  // 鼠标释放
  await frame.waitForTimeout(100);
  await button.dispatchEvent('mouseup');
}

/**
 * 检测滑块验证是否通过
 */
async function checkSolved(page: Page, frame: any): Promise<boolean> {
  // 成功标识
  const successSelectors = ['.nc_ok', '.success', '#nc_1_n1z.success', '.icon-success'];
  for (const sel of successSelectors) {
    try {
      const elem = await (frame || page).$(sel);
      if (elem && await elem.isVisible()) {
        return true;
      }
    } catch {
      // ignore
    }
  }

  // 失败/重试标识
  const failSelectors = ['.nc_error', '.errloading', '.fail', '#nc_1_refresh1'];
  for (const sel of failSelectors) {
    try {
      const elem = await (frame || page).$(sel);
      if (elem && await elem.isVisible()) {
        return false;
      }
    } catch {
      // ignore
    }
  }

  // 滑块弹窗消失也视为通过
  const stillHasCaptcha = await detectCaptcha(page);
  return !stillHasCaptcha.detected;
}

/**
 * 主入口：启动浏览器、检测滑块、自动拖动
 */
export async function solveGoofishSlider(options: SlideSolveOptions = {}): Promise<SlideSolveResult> {
  const startTime = Date.now();
  const targetUrl = options.targetUrl || DEFAULT_TARGET_URL;
  const headless = resolveHeadlessMode(options.headless);
  const retries = Number(options.maxRetries ?? 3);
  const maxRetries = Number.isSafeInteger(retries) ? Math.max(1, Math.min(retries, 5)) : 3;
  const timeout = Number(options.timeoutMs ?? 30000);
  const timeoutMs = Number.isSafeInteger(timeout) ? Math.max(5000, Math.min(timeout, 120000)) : 30000;

  let browser: Browser | null = null;
  let screenshotPath: string | undefined;

  try {
    const contextOptions: BrowserContextOptions = {
      viewport: { width: 1280, height: 800 },
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
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
    const context = await browser.newContext(contextOptions);
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
    // 反检测：移除 webdriver 标识
    await context.addInitScript(() => {
      Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
      (window as any).chrome = { runtime: {} };
      Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5],
      });
      Object.defineProperty(navigator, 'languages', {
        get: () => ['zh-CN', 'zh', 'en'],
      });
    });

    const page = await context.newPage();

    // 访问目标页面（默认闲鱼消息页）
    console.log(`[SliderSolver] 访问目标页面: ${targetUrl}`);
    await page.goto(targetUrl, { waitUntil: 'domcontentloaded', timeout: timeoutMs });
    // 等待 3 秒让滑块弹窗渲染完成（用户反馈滑块在页面加载约3秒后弹出）
    await page.waitForTimeout(3000);

    // === Cookie 过期检测 ===
    // 关键修复：Cookie Session 过期时闲鱼首页会重定向到登录页（login.taobao.com 或 goofish.com/login），
    // 此时不会出现滑块弹窗，旧逻辑会误报 "solved: true"，导致 captcha_solver 错误地恢复 cookie_status=1。
    // 必须在此检测登录页跳转，明确返回失败，让用户知道需要重新扫码登录而不是滑块问题。
    const currentUrl = page.url();
    const isLoginPage =
      /login\.taobao\.com/i.test(currentUrl) ||
      /login\.goofish\.com/i.test(currentUrl) ||
      /\/login\b/i.test(currentUrl) ||
      /\/uiLogin\b/i.test(currentUrl);
    if (isLoginPage) {
      console.warn('[SliderSolver] 页面被重定向到登录页，Cookie Session 已过期');
      return {
        ok: false,
        solved: false,
        captchaDetected: false,
        attempts: 0,
        error: 'Cookie Session 已过期，页面被重定向到登录页，请重新扫码登录闲鱼账号获取新 Cookie',
        durationMs: Date.now() - startTime,
      };
    }

    // 检测页面是否显示登录入口（部分场景下登录页是 SPA 内嵌，URL 不变化）
    const hasLoginIndicator = await page.evaluate(() => {
      const text = document.body ? document.body.innerText : '';
      // 登录页特征：包含"扫码登录"或"手机号登录"且不含商品列表关键字
      if (/扫码登录|手机号登录|账号密码登录/i.test(text) && !/我想要|猜你喜欢|闲置/i.test(text)) {
        return true;
      }
      return false;
    }).catch(() => false);
    if (hasLoginIndicator) {
      console.warn(`[SliderSolver] 页面显示登录入口，Cookie Session 已过期`);
      return {
        ok: false,
        solved: false,
        captchaDetected: false,
        attempts: 0,
        error: 'Cookie Session 已过期，页面显示登录入口，请重新扫码登录闲鱼账号获取新 Cookie',
        durationMs: Date.now() - startTime,
      };
    }

    let attempts = 0;
    let lastError: string | undefined;

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      attempts = attempt;
      console.log(`[SliderSolver] 第 ${attempt}/${maxRetries} 次检测滑块...`);

      const detected = await detectCaptcha(page);
      if (!detected.detected) {
        console.log(`[SliderSolver] 未检测到滑块，可能已通过验证或不需要验证`);
        return {
          ok: true,
          solved: true,
          captchaDetected: false,
          attempts,
          durationMs: Date.now() - startTime,
        };
      }

      console.log(`[SliderSolver] 检测到滑块: selector=${detected.selector}`);

      const frame = detected.iframe || page.mainFrame();
      const sliderInfo = await getSliderInfo(frame);

      if (!sliderInfo) {
        lastError = `检测到滑块容器 ${detected.selector}，但未找到可拖动的滑块按钮`;
        console.warn(`[SliderSolver] ${lastError}`);
        await page.waitForTimeout(1500);
        continue;
      }

      const { button, trackWidth, buttonBox, ownerFrame } = sliderInfo;
      const startX = buttonBox.x + buttonBox.width / 2;
      const startY = buttonBox.y + buttonBox.height / 2;

      console.log(`[SliderSolver] 开始拖动滑块: startX=${startX}, distance=${trackWidth}`);
      try {
        // 使用滑块按钮实际所在的 frame 进行拖动（baxia 滑块可能在嵌套 iframe 中）
        await humanLikeDrag(ownerFrame || frame, button, startX, startY, trackWidth);
      } catch (e: any) {
        lastError = '拖动滑块异常，请稍后重试';
        console.error(`[SliderSolver] operation=drag errorType=${safeErrorType(e)}`);
        continue;
      }

      // 等待验证结果
      await page.waitForTimeout(2500);
      const solved = await checkSolved(page, ownerFrame || frame);

      if (solved) {
        console.log(`[SliderSolver] 滑块验证通过！`);
        return {
          ok: true,
          solved: true,
          captchaDetected: true,
          attempts,
          durationMs: Date.now() - startTime,
        };
      }

      lastError = `第 ${attempt} 次拖动后未通过验证`;
      console.warn(`[SliderSolver] ${lastError}`);

      // 等待 1.5 秒再重试
      await page.waitForTimeout(1500);
    }

    // 所有重试都失败，截图保存
    const environment = process.env.NODE_ENV || process.env.APP_ENV || 'development';
    const debugDir = process.env.CRAWLER_DEBUG_DIR;
    try {
      if (!debugDir || isProductionLike(environment)) throw new Error('debug screenshots disabled');
      await fs.mkdir(debugDir, { recursive: true });
      screenshotPath = path.join(debugDir, `slide-fail-${Date.now()}.png`);
      await page.screenshot({ path: screenshotPath, fullPage: true });
      console.log('[SliderSolver] 失败调试截图已保存');
    } catch {
      // ignore
    }

    return {
      ok: false,
      solved: false,
      captchaDetected: true,
      attempts,
      error: lastError || `滑块验证失败，已重试 ${maxRetries} 次`,
      screenshotPath,
      durationMs: Date.now() - startTime,
    };
  } catch (e: any) {
    console.error(`[SliderSolver] operation=solve errorType=${safeErrorType(e)}`);
    return {
      ok: false,
      solved: false,
      captchaDetected: false,
      attempts: 0,
      error: toPublicCrawlerError(e, '滑块验证处理失败，请稍后重试'),
      durationMs: Date.now() - startTime,
    };
  } finally {
    if (browser) {
      try {
        await browser.close();
      } catch {
        // ignore
      }
    }
  }
}
