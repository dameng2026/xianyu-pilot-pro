/**
 * FireyeJS Token 提取器（方案 K - 路线 J）
 *
 * 通过 Playwright 启动真实浏览器访问闲鱼首页，让 FireyeJS 在真实浏览器环境
 * 中执行（fireyejs.js 使用 VM 混淆，无法在 Node.js 中静态执行）。
 *
 * 实现要点：
 * 1. 启动浏览器（复用 sliderSolver 的反检测脚本和浏览器配置）
 * 2. 注入用户 cookie 保持登录态
 * 3. 导航到 https://www.goofish.com/（fireyejs.js 会被自动加载）
 * 4. 等待 window.__fy 对象可用
 * 5. 模拟鼠标移动生成行为数据
 * 6. 调用 __fy.getFYToken() 和 __fy.getUidToken() 获取真实 token
 *
 * 关键约束（违反即为 Bug）：
 * - 不得在 Node.js 中静态执行 fireyejs.js（VM 混淆 + 浏览器 API 依赖）
 * - 必须等待 window.__fy 可用后再调用（可能需要 1-3 秒）
 * - FYToken 依赖行为数据，必须模拟鼠标移动
 * - 浏览器会话必须正确关闭（避免进程泄漏）
 */
import { chromium, type Browser, type BrowserContext, type Page, type Cookie } from 'playwright';
import path from 'path';
import os from 'os';
import fs from 'fs/promises';
import {
  processRegistry,
  generateSessionId,
} from './processRegistry.js';
import {
  ANTI_DETECT_SCRIPT,
  parseCookieString,
  stripRiskCookies,
  isHeadedDisplayAvailable,
} from './sliderSolver.js';

// ============================================================
// 常量与配置
// ============================================================

/** FireyeJS 加载等待超时（毫秒） */
const FIREYEJS_WAIT_TIMEOUT_MS = 15_000;

/** 行为数据采集等待时间（毫秒）- FireyeJS 需要收集鼠标移动等行为数据 */
const BEHAVIOR_COLLECTION_WAIT_MS = 1_500;

/** 页面导航超时（毫秒） */
const NAVIGATION_TIMEOUT_MS = 20_000;

/** 浏览器启动超时（毫秒） */
const BROWSER_LAUNCH_TIMEOUT_MS = 30_000;

/** 浏览器会话整体超时（毫秒）- 用于 processRegistry 的 deadlineAt */
const SESSION_DEADLINE_MS = 60_000;

/** 默认目标 URL - 闲鱼首页会自动加载 fireyejs.js */
const DEFAULT_TARGET_URL = 'https://www.goofish.com/';

/**
 * FireyeJS token 结果
 */
export interface FireyejsTokenResult {
  ok: boolean;
  fyToken: string;
  umidToken: string;
  durationMs: number;
  error?: string;
  /** 浏览器加载到的 FireyeJS 版本信息（用于调试） */
  fireyejsVersion?: string;
  /** 检测到的环境信息（用于调试） */
  environmentInfo?: {
    userAgent: string;
    platform: string;
    hasWebdriver: boolean;
    webdriverValue?: any;
    vendor?: string;
  };
  /** 页面诊断信息（失败时用于排查） */
  diagnostics?: {
    currentUrl: string;
    title: string;
    readyState: string;
    fireyejsScripts: string[];
    fireyejsGlobals: string[];
    bodyTextPreview: string;
    networkRequests: string[];
  };
}

/**
 * FireyeJS token 提取选项
 */
export interface FireyejsTokenOptions {
  /** Cookie 字符串（用于保持登录态，可选） */
  cookieStr?: string;
  /** 目标 URL（默认闲鱼首页） */
  targetUrl?: string;
  /** 是否无头模式（默认有头模式，Baxia 检测更稳定） */
  headless?: boolean;
  /** 账号绑定代理 */
  proxy?: { server: string; username?: string; password?: string };
  /** 是否启用行为模拟（默认 true，必须启用以生成有效 FYToken） */
  simulateBehavior?: boolean;
  /** 是否启用调试日志 */
  debug?: boolean;
}

// ============================================================
// 浏览器启动逻辑（复用 sliderSolver 的反检测配置）
// ============================================================

/**
 * 启动浏览器并返回 context 和 sessionId
 *
 * 复用 sliderSolver 的反检测配置：
 * - ANTI_DETECT_SCRIPT 注入
 * - 真实 UA / 语言 / 时区
 * - ignoreDefaultArgs: ['--enable-automation']
 * - --disable-blink-features=AutomationControlled
 */
async function launchBrowserForFireyejs(
  options: FireyejsTokenOptions,
): Promise<{
  context: BrowserContext;
  browser: Browser | null;
  sessionId: string;
  userDataDir: string;
}> {
  const isLinux = process.platform !== 'win32' && process.platform !== 'darwin';
  const headless =
    typeof options.headless === 'boolean'
      ? options.headless
      : !isHeadedDisplayAvailable();

  // 显式指定 userDataDir，避免 Playwright 自动创建临时目录导致进程泄漏
  const userDataDir = path.join(
    process.env.TEMP || '/tmp',
    `playwright-fireyejs-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
  );
  await fs.mkdir(userDataDir, { recursive: true });

  console.log(`[FireyejsToken] 启动浏览器 headless=${headless} userDataDir=${userDataDir}`);

  const context = await chromium.launchPersistentContext(userDataDir, {
    headless,
    ...(isLinux ? { channel: 'chrome' as const } : {}),
    chromiumSandbox: !isLinux,
    ignoreDefaultArgs: ['--enable-automation'],
    viewport: { width: 1280, height: 800 },
    locale: 'zh-CN',
    timezoneId: 'Asia/Shanghai',
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
      '(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
    ...(options.proxy?.server
      ? {
          proxy: {
            server: options.proxy.server,
            ...(options.proxy.username ? { username: options.proxy.username } : {}),
            ...(options.proxy.password ? { password: options.proxy.password } : {}),
          },
        }
      : {}),
    args: [
      '--disable-blink-features=AutomationControlled',
      '--no-first-run',
      '--no-default-browser-check',
      ...(isLinux
        ? [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--disable-crash-reporter',
            '--disable-crashpad',
            '--disable-breakpad',
            '--disable-features=Crashpad',
          ]
        : []),
    ],
    timeout: BROWSER_LAUNCH_TIMEOUT_MS,
  });

  const browser = context.browser();
  const sessionId = generateSessionId();
  const deadlineAt = Date.now() + SESSION_DEADLINE_MS;

  // 注册到 processRegistry，让 ProcessMonitor 能监测和清理
  processRegistry.register({
    sessionId,
    kind: 'chromium',
    pid: 0,
    childPids: [],
    userDataDir,
    tenantId: '',
    startedAt: Date.now(),
    deadlineAt,
    description: `fireyejs-token userDataDir=${userDataDir}`,
  });

  console.log(`[FireyejsToken] 已注册到 processRegistry: sessionId=${sessionId}`);

  return { context, browser, sessionId, userDataDir };
}

// ============================================================
// Cookie 注入
// ============================================================

/**
 * 注入 cookie 到浏览器上下文
 *
 * 关键：必须清除 x5sec/x5sectag/x5secdata 等风控 cookie，
 * 否则浏览器带着 punish 状态访问会被服务器持续判定为高风险。
 */
async function injectCookies(
  context: BrowserContext,
  cookieStr: string,
): Promise<void> {
  if (!cookieStr) return;

  const cleanCookieStr = stripRiskCookies(cookieStr);
  const goofishCookies = parseCookieString(cleanCookieStr, '.goofish.com');
  if (goofishCookies.length === 0) return;

  await context.addCookies(goofishCookies);
  console.log(`[FireyejsToken] 已注入 ${goofishCookies.length} 个 cookie`);
}

// ============================================================
// 行为模拟（生成 FYToken 所需的行为数据）
// ============================================================

/**
 * 模拟鼠标移动和滚动，生成 FireyeJS 所需的行为数据
 *
 * FireyeJS 的 getFYToken() 会收集以下行为数据：
 * - mouseMoves（鼠标移动次数）
 * - mouseClicks（鼠标点击次数）
 * - keyStrokes（键盘按键次数）
 * - scrollEvents（滚动事件次数）
 *
 * 没有行为数据时，FYToken 会被服务器拒绝（识别为机器人）
 */
async function simulateBehavior(page: Page): Promise<void> {
  // 阶段 1：随机鼠标移动（5-8 次）
  const moveCount = 5 + Math.floor(Math.random() * 4);
  for (let i = 0; i < moveCount; i++) {
    const x = 100 + Math.floor(Math.random() * 800);
    const y = 100 + Math.floor(Math.random() * 500);
    await page.mouse.move(x, y, { steps: 3 + Math.floor(Math.random() * 5) });
    await page.waitForTimeout(80 + Math.floor(Math.random() * 120));
  }

  // 阶段 2：滚动页面（2-3 次）
  const scrollCount = 2 + Math.floor(Math.random() * 2);
  for (let i = 0; i < scrollCount; i++) {
    await page.mouse.wheel(0, 200 + Math.floor(Math.random() * 300));
    await page.waitForTimeout(150 + Math.floor(Math.random() * 200));
  }

  // 阶段 3：等待行为数据被 FireyeJS 采集
  await page.waitForTimeout(BEHAVIOR_COLLECTION_WAIT_MS);
}

// ============================================================
// Token 提取逻辑
// ============================================================

/**
 * 等待 FireyeJS 加载完成
 *
 * 2026-08-03 关键发现：
 *   FireyeJS 1.231.67 版本不再创建 window.__fy，而是使用 window.AWSCFY
 *   页面上存在的全局变量：AWSCFY, fyglobalopt, __fyModule, __baxia__, baxiaCommon
 *
 * 本函数等待以下任一对象可用：
 * - window.__fy（旧版 API，有 getFYToken/getUidToken 方法）
 * - window.AWSCFY（新版 AWSC 框架入口，有 getFYToken 方法）
 * - window.__fyModule（模块对象）
 */
async function waitForFireyejs(page: Page, debug = false): Promise<boolean> {
  try {
    // 首先检查当前是否已有可用的 FireyeJS 对象（避免不必要的等待）
    const initialCheck = await page.evaluate(() => {
      const fy = (window as any).__fy;
      const awscfy = (window as any).AWSCFY;
      const fyModule = (window as any).__fyModule;
      return {
        hasFy: !!(fy && typeof fy.getFYToken === 'function'),
        hasAwscfy: awscfy !== undefined && awscfy !== null,
        hasFyModule: fyModule !== undefined && fyModule !== null,
      };
    });
    if (initialCheck.hasFy || initialCheck.hasAwscfy || initialCheck.hasFyModule) {
      if (debug) console.log(`[FireyejsToken] FireyeJS 立即可用（fy=${initialCheck.hasFy} awscfy=${initialCheck.hasAwscfy} fyModule=${initialCheck.hasFyModule}）`);
      return true;
    }

    // 等待任一 FireyeJS 入口可用
    // 2026-08-03 关键发现：__fyModule 是真实 API，包含 getFYToken 方法
    //   等待条件：__fyModule.getFYToken 可用（或旧版 __fy.getFYToken 可用）
    await page.waitForFunction(
      () => {
        const fy = (window as any).__fy;
        if (fy && typeof fy.getFYToken === 'function') return true;
        const fyModule = (window as any).__fyModule;
        if (fyModule && typeof fyModule.getFYToken === 'function') return true;
        return false;
      },
      { timeout: FIREYEJS_WAIT_TIMEOUT_MS },
    );

    if (debug) {
      const apiInfo = await page.evaluate(() => {
        const fy = (window as any).__fy;
        const awscfy = (window as any).AWSCFY;
        const fyModule = (window as any).__fyModule;
        const fyglobalopt = (window as any).fyglobalopt;
        return {
          hasFy: !!fy,
          fyKeys: fy ? Object.keys(fy).slice(0, 20) : [],
          hasAwscfy: !!awscfy,
          awscfyKeys: awscfy ? Object.keys(awscfy).slice(0, 20) : [],
          hasFyModule: !!fyModule,
          fyModuleKeys: fyModule ? Object.keys(fyModule).slice(0, 20) : [],
          fyglobaloptKeys: fyglobalopt ? Object.keys(fyglobalopt).slice(0, 20) : [],
        };
      });
      console.log(`[FireyejsToken] API 信息: ${JSON.stringify(apiInfo)}`);
    }
    return true;
  } catch (e: any) {
    console.error(`[FireyejsToken] 等待 FireyeJS 超时: ${e?.message || e}`);

    // 超时后检查所有可用的 FireyeJS 全局变量，用于诊断
    if (debug) {
      const globalInfo = await page.evaluate(() => {
        const result: Record<string, string[]> = {};
        const keys = ['__fy', 'AWSCFY', '__fyModule', 'fyglobalopt', '__baxia__', 'baxiaCommon', 'BaxiaCookieManager', 'AWSC', 'um', 'UMID'];
        for (const key of keys) {
          const obj = (window as any)[key];
          if (obj) {
            result[key] = typeof obj === 'object' ? Object.keys(obj).slice(0, 15) : [typeof obj];
          }
        }
        return result;
      });
      console.log(`[FireyejsToken] 可用全局变量: ${JSON.stringify(globalInfo)}`);
    }
    return false;
  }
}

/**
 * 检查 FireyeJS 全局对象的详细信息（用于诊断 API 结构）
 *
 * 2026-08-03 关键发现：
 *   FireyeJS 1.231.67 的 AWSCFY 可能是 constructor function，不是 object
 *   需要检查 typeof、toString、prototype 等
 */
async function inspectFireyejsObjects(page: Page): Promise<Record<string, any>> {
  return await page.evaluate(() => {
    const result: Record<string, any> = {};
    const keys = ['__fy', 'AWSCFY', '__fyModule', 'fyglobalopt', '__baxia__', 'baxiaCommon', 'BaxiaCookieManager', 'AWSC', 'um', 'UMID', 'UA_Opt', '__fy_options'];

    for (const key of keys) {
      const obj = (window as any)[key];
      if (obj === undefined || obj === null) {
        result[key] = { exists: false };
        continue;
      }
      const info: any = {
        exists: true,
        type: typeof obj,
      };
      try {
        info.str = String(obj).substring(0, 150);
      } catch (e) {
        info.str = '<toString failed>';
      }
      if (typeof obj === 'function') {
        info.fnStr = obj.toString().substring(0, 200);
        try {
          info.protoKeys = Object.keys(obj.prototype).slice(0, 15);
        } catch (e) {}
        try {
          info.ownKeys = Object.keys(obj).slice(0, 15);
        } catch (e) {}
      } else if (typeof obj === 'object') {
        try {
          info.keys = Object.keys(obj).slice(0, 20);
        } catch (e) {}
      }
      result[key] = info;
    }
    return result;
  });
}

/**
 * 调用 getFYToken() 获取 FYToken
 *
 * 2026-08-03 关键发现：
 *   FireyeJS 1.231.67 的真实 API 是 window.__fyModule，不是 window.__fy 或 window.AWSCFY
 *   __fyModule 包含：init, getFYToken, getUidToken, startRecord, getVersion 等方法
 *   AWSCFY 只是个空函数（占位符），不是入口
 *
 * 调用流程：
 * 1. __fyModule.init(options) 初始化（如果尚未初始化）
 * 2. __fyModule.startRecord() 开始采集行为数据（如果需要）
 * 3. __fyModule.getFYToken(options, callback) 获取 token
 *
 * getFYToken 可能的调用模式：
 * - callback: __fyModule.getFYToken(options, callback)
 * - promise: __fyModule.getFYToken(options) → Promise
 * - sync: __fyModule.getFYToken() → string
 */
async function extractFYToken(page: Page, debug = false): Promise<string> {
  return await page.evaluate((debugFlag) => {
    const fy = (window as any).__fy;
    const fyModule = (window as any).__fyModule;
    const fyglobalopt = (window as any).fyglobalopt;

    // 构建 options
    const uaOpt = (window as any).UA_Opt;
    const options = {
      appkey: uaOpt?.Appkey || fyglobalopt?.appkey || 'XFFXFXFF',
      scene: uaOpt?.scene || fyglobalopt?.scene || 'nc_h5',
      trans: {},
    };

    if (debugFlag) {
      console.log('[FireyejsToken] options:', JSON.stringify(options));
      console.log('[FireyejsToken] fy:', typeof fy, 'fyModule:', typeof fyModule);
      if (fyModule) {
        console.log('[FireyejsToken] fyModule keys:', Object.keys(fyModule).slice(0, 15));
      }
    }

    // 方式 1：__fy.getFYToken（旧版同步 API）
    if (fy && typeof fy.getFYToken === 'function') {
      if (debugFlag) console.log('[FireyejsToken] 使用 __fy.getFYToken');
      const token = fy.getFYToken(options);
      return token || '';
    }

    // 方式 2：__fyModule.getFYToken（新版 API，2026-08-03 发现）
    if (fyModule && typeof fyModule.getFYToken === 'function') {
      if (debugFlag) console.log('[FireyejsToken] 使用 __fyModule.getFYToken');

      // 先尝试 init（如果未初始化的话）
      if (typeof fyModule.init === 'function') {
        try {
          if (debugFlag) console.log('[FireyejsToken] 调用 __fyModule.init(options)');
          fyModule.init(options);
        } catch (e: any) {
          if (debugFlag) console.log('[FireyejsToken] __fyModule.init 异常（可能已初始化）:', e?.message);
        }
      }

      // 尝试 startRecord（启动行为数据采集）
      if (typeof fyModule.startRecord === 'function') {
        try {
          if (debugFlag) console.log('[FireyejsToken] 调用 __fyModule.startRecord()');
          fyModule.startRecord();
        } catch (e: any) {
          if (debugFlag) console.log('[FireyejsToken] __fyModule.startRecord 异常:', e?.message);
        }
      }

      // 调用 getFYToken，支持 callback / promise / sync 三种模式
      return new Promise<string>((resolve, reject) => {
        let resolved = false;
        const cb = (token: string) => {
          if (!resolved) {
            resolved = true;
            if (debugFlag) console.log('[FireyejsToken] __fyModule.getFYToken callback 返回长度:', token ? token.length : 0);
            resolve(token || '');
          }
        };

        try {
          // 尝试 callback 模式
          const result = fyModule.getFYToken(options, cb);

          if (result && typeof result.then === 'function') {
            // Promise 模式
            if (debugFlag) console.log('[FireyejsToken] __fyModule.getFYToken 返回 Promise');
            result
              .then((t: string) => {
                if (!resolved) {
                  resolved = true;
                  if (debugFlag) console.log('[FireyejsToken] __fyModule.getFYToken promise 返回长度:', t ? t.length : 0);
                  resolve(t || '');
                }
              })
              .catch((e: any) => {
                if (!resolved) {
                  resolved = true;
                  reject(new Error(`__fyModule.getFYToken promise 失败: ${e?.message || e}`));
                }
              });
          } else if (typeof result === 'string') {
            // 同步模式
            if (!resolved) {
              resolved = true;
              if (debugFlag) console.log('[FireyejsToken] __fyModule.getFYToken 同步返回长度:', result.length);
              resolve(result);
            }
          } else if (debugFlag) {
            console.log('[FireyejsToken] __fyModule.getFYToken 返回类型:', typeof result, '等待 callback...');
          }

          // 超时保护
          setTimeout(() => {
            if (!resolved) {
              resolved = true;
              reject(new Error('__fyModule.getFYToken 5秒超时（无 callback/promise/sync 响应）'));
            }
          }, 5000);
        } catch (e: any) {
          if (!resolved) {
            resolved = true;
            reject(new Error(`__fyModule.getFYToken 调用异常: ${e?.message || e}`));
          }
        }
      });
    }

    throw new Error(`getFYToken 不可用。fy=${typeof fy} fyModule=${typeof fyModule}`);
  }, debug);
}

/**
 * 调用 getUidToken() 获取 umidToken
 *
 * 2026-08-03 更新：使用 __fyModule.getUidToken()（新版 API）
 * 也支持旧版 __fy.getUidToken() 和 UMID.getToken()
 */
async function extractUmidToken(page: Page, debug = false): Promise<string> {
  return await page.evaluate((debugFlag) => {
    const fy = (window as any).__fy;
    const fyModule = (window as any).__fyModule;
    const umid = (window as any).UMID;

    // 方式 1：__fyModule.getUidToken()（新版 API，优先）
    if (fyModule && typeof fyModule.getUidToken === 'function') {
      if (debugFlag) console.log('[FireyejsToken] 使用 __fyModule.getUidToken');
      try {
        const token = fyModule.getUidToken();
        if (debugFlag) {
          console.log('[FireyejsToken] __fyModule.getUidToken 返回长度:', token ? token.length : 0);
        }
        if (token) return token;
      } catch (e: any) {
        if (debugFlag) console.log('[FireyejsToken] __fyModule.getUidToken 异常:', e?.message);
      }
    }

    // 方式 2：__fy.getUidToken()（旧版）
    if (fy && typeof fy.getUidToken === 'function') {
      const token = fy.getUidToken();
      if (debugFlag) {
        console.log('[FireyejsToken] __fy.getUidToken 返回长度:', token ? token.length : 0);
      }
      return token || '';
    }

    // 方式 3：UMID.getToken()
    if (umid && typeof umid.getToken === 'function') {
      const token = umid.getToken();
      if (debugFlag) {
        console.log('[FireyejsToken] UMID.getToken 返回长度:', token ? token.length : 0);
      }
      return token || '';
    }

    // 方式 4：从 cookie 中读取 umt
    const cookies = document.cookie.split(';');
    for (const c of cookies) {
      const trimmed = c.trim();
      if (trimmed.startsWith('umt=') || trimmed.startsWith('cna=') || trimmed.startsWith('umid=')) {
        const value = trimmed.substring(trimmed.indexOf('=') + 1);
        if (value && value.length > 10) {
          if (debugFlag) {
            console.log('[FireyejsToken] 从 cookie 读取 umidToken:', trimmed.substring(0, 20));
          }
          return value;
        }
      }
    }

    throw new Error('getUidToken 不可用（__fyModule/__fy/UMID 均无此方法，cookie 也无 umt）');
  }, debug);
}

/**
 * 检测环境信息（用于调试和反检测验证）
 *
 * 2026-08-03 修复：
 *   - 原 hasWebdriver 检查 'webdriver' in navigator，但正常 Chrome 该属性也存在（值为 false）
 *   - 修复：检查 navigator.webdriver === true（自动化模式才返回 true）
 *   - 新增 webdriverValue 字段记录实际值
 *   - 新增 vendor / appVersion 一致性检查
 */
async function detectEnvironment(page: Page): Promise<{
  userAgent: string;
  platform: string;
  hasWebdriver: boolean;
  webdriverValue: any;
  vendor: string;
  userAgentDataPlatform: string;
  consoleErrors: string[];
}> {
  return await page.evaluate(() => {
    // 2026-08-03 v6 新增：检测 navigator.userAgentData.platform
    // 这是 Chrome 90+ 的 User-Agent Client Hints API，FireyeJS 可能通过它检测真实平台
    let uadPlatform = '';
    try {
      const navAny = navigator as any;
      if (navAny.userAgentData) {
        uadPlatform = navAny.userAgentData.platform || '';
      }
    } catch (e) {}
    return {
      userAgent: navigator.userAgent,
      platform: navigator.platform,
      hasWebdriver: navigator.webdriver === true,
      webdriverValue: navigator.webdriver,
      vendor: navigator.vendor,
      userAgentDataPlatform: uadPlatform,
      consoleErrors: (window as any).__fireyejsDebugErrors || [],
    };
  });
}

/**
 * 收集页面诊断信息（用于排查 FireyeJS 未加载的原因）
 *
 * 检查：
 * - 当前 URL（是否被重定向到登录页或错误页）
 * - 页面标题
 * - 页面是否包含 fireyejs 相关 script 标签
 * - window 上的 FireyeJS 相关全局变量
 * - document.readyState
 */
async function collectPageDiagnostics(page: Page): Promise<{
  currentUrl: string;
  title: string;
  readyState: string;
  fireyejsScripts: string[];
  fireyejsGlobals: string[];
  bodyTextPreview: string;
}> {
  return await page.evaluate(() => {
    // 查找所有 script 标签中 src 包含 fireye/fy/baxia 的
    const scripts = Array.from(document.querySelectorAll('script[src]'));
    const fireyejsScripts = scripts
      .map((s) => s.getAttribute('src') || '')
      .filter((src) => /fireye|fy|baxia|umid/i.test(src));

    // 查找 window 上的 FireyeJS 相关全局变量
    const fireyejsGlobals = Object.keys(window).filter(
      (k) => /fy|fireye|baxia|umid|__fy/i.test(k),
    );

    // 获取 body 文本前 200 字符（用于判断是否在登录页/错误页）
    const bodyText = document.body ? document.body.innerText : '';
    const bodyTextPreview = bodyText.substring(0, 200).replace(/\s+/g, ' ').trim();

    return {
      currentUrl: window.location.href,
      title: document.title,
      readyState: document.readyState,
      fireyejsScripts,
      fireyejsGlobals,
      bodyTextPreview,
    };
  });
}

/**
 * 设置控制台消息捕获（用于诊断 FireyeJS 加载失败原因）
 */
async function setupConsoleCapture(page: Page): Promise<void> {
  page.on('console', (msg) => {
    const type = msg.type();
    if (type === 'error' || type === 'warning') {
      const text = msg.text();
      if (/fireye|fy|baxia|umid|error|fail/i.test(text)) {
        console.log(`[FireyejsToken][console.${type}] ${text}`);
      }
    }
  });
  page.on('pageerror', (err) => {
    console.log(`[FireyejsToken][pageerror] ${err.message}`);
  });
}

/**
 * 设置网络请求监控（检测 fireyejs.js 是否被请求和加载）
 */
async function setupNetworkMonitoring(page: Page, debug = false): Promise<{
  fireyejsLoaded: boolean;
  fireyejsRequests: string[];
}> {
  const fireyejsRequests: string[] = [];
  let fireyejsLoaded = false;

  page.on('response', (response) => {
    const url = response.url();
    // 2026-08-03 v6 优化：扩大捕获范围，包含 um.json / nocaptcha / aliyun 端点
    // 原正则只匹配 fireye|fy.js|baxia|umid，遗漏了 um.json 和 nocaptcha 请求
    if (/fireye|fy\.js|baxia|umid|um\.json|nocaptcha|aliyun\.com\/nocaptcha|ynuf\.aliapp/i.test(url)) {
      fireyejsRequests.push(`${response.status()} ${url.substring(0, 150)}`);
      fireyejsLoaded = true;
      if (debug) {
        console.log(`[FireyejsToken][network] ${response.status()} ${url.substring(0, 150)}`);
      }
    }
  });

  return { fireyejsLoaded, fireyejsRequests };
}

// ============================================================
// v7 新增：被动网络捕获（拦截页面自己发起的 NC 请求响应）
// ============================================================

/**
 * 被动捕获的 NC 流程结果
 *
 * 2026-08-03 v7 关键发现：
 *   - 闲鱼页面自己发起的 NC 请求用 appkey=CF_APP_TBLogin_PC（成功）
 *   - 我们主动调用用 appkey=XFFXFXFF（失败，um.json 返回空 id）
 *   - 正确做法：让页面自己跑 NC 流程，从网络响应中拦截结果
 */
export interface PassiveCaptureResult {
  /** 拦截到的 initialize.jsonp 真实 appkey */
  realAppkey: string;
  /** 拦截到的 initialize.jsonp 返回的 token */
  realNcToken: string;
  /** 拦截到的 initialize.jsonp 完整响应 */
  initResponseText: string;
  /** 拦截到的 analyze.jsonp result.code */
  analyzeCode: number | null;
  /** 拦截到的 analyze.jsonp result.value (sig) */
  analyzeSig: string;
  /** 拦截到的 analyze.jsonp result.csessionid */
  analyzeCsessionid: string;
  /** 拦截到的 analyze.jsonp 完整响应 */
  analyzeResponseText: string;
  /** 从所有响应 Set-Cookie 头提取的 x5sec */
  x5secFromSetCookie: string;
  /** 拦截到的 um.json 响应 */
  umJsonResponseText: string;
  /** um.json 返回的 umt cookie（从 Set-Cookie 提取） */
  umtFromSetCookie: string;
  /** v8 新增：um.json 响应体中的 tn 字段（可能是 umt token 的实际值） */
  umTn: string;
  /** v8 新增：um.json 响应体中的 id 字段（非空表示 FYToken 被接受） */
  umId: string;
  /** v9 新增：initialize.jsonp 完整 URL（含 version/href 等所有参数，用于 replay） */
  initFullUrl: string;
  /** v9 新增：analyze.jsonp 完整 URL（含 version/href 等所有参数，用于 replay） */
  analyzeFullUrl: string;
  /** v9 新增：从 initialize.jsonp URL 提取的 version 参数 */
  initVersion: string;
  /** v9 新增：从 initialize.jsonp URL 提取的 href 参数 */
  initHref: string;
  /** 拦截到的所有 NC 相关请求 URL */
  capturedUrls: string[];
}

/**
 * 设置被动网络捕获：监听页面自己发起的 NC 流程请求响应
 *
 * 拦截目标：
 * - https://ynuf.aliapp.org/service/um.json → 提取 umt cookie
 * - https://cf.aliyun.com/nocaptcha/initialize.jsonp → 提取 appkey + ncToken
 * - https://cf.aliyun.com/nocaptcha/analyze.jsonp → 提取 sig + csessionid + x5sec
 * - 所有响应的 Set-Cookie 头 → 提取 x5sec
 *
 * @param page Playwright Page 对象
 * @param debug 是否调试
 * @returns PassiveCaptureResult 引用（会随网络请求实时更新）
 */
function setupPassiveNetworkCapture(page: Page, debug = false): PassiveCaptureResult {
  const result: PassiveCaptureResult = {
    realAppkey: '',
    realNcToken: '',
    initResponseText: '',
    analyzeCode: null,
    analyzeSig: '',
    analyzeCsessionid: '',
    analyzeResponseText: '',
    x5secFromSetCookie: '',
    umJsonResponseText: '',
    umtFromSetCookie: '',
    umTn: '',
    umId: '',
    initFullUrl: '',
    analyzeFullUrl: '',
    initVersion: '',
    initHref: '',
    capturedUrls: [],
  };

  page.on('response', async (response) => {
    const url = response.url();
    try {
      // 1. 拦截 um.json 响应
      if (url.includes('ynuf.aliapp.org/service/um.json')) {
        result.capturedUrls.push(`um.json ${response.status()}`);
        // 提取 Set-Cookie 中的 umt
        const setCookie = response.headers()['set-cookie'] || '';
        const umtMatch = setCookie.match(/umt=([^;]+)/);
        if (umtMatch && umtMatch[1]) {
          result.umtFromSetCookie = umtMatch[1];
          if (debug) console.log(`[PassiveCapture] ✓ um.json Set-Cookie umt 长度=${umtMatch[1].length}`);
        }
        // v8 新增：提取响应体中的 tn 和 id 字段
        // 关键发现：页面自己调用 um.json 时返回 {"tn":"...","id":"..."}（非空）
        // 但 Set-Cookie 中没有 umt。um.js 可能通过 JS document.cookie 设置 umt=tn
        try {
          const text = await response.text();
          result.umJsonResponseText = text.substring(0, 500);
          try {
            const data = JSON.parse(text);
            if (data.tn) {
              result.umTn = String(data.tn);
              if (debug) console.log(`[PassiveCapture] ✓ um.json tn 长度=${result.umTn.length}`);
            }
            if (data.id) {
              result.umId = String(data.id);
              if (debug) console.log(`[PassiveCapture] ✓ um.json id 长度=${result.umId.length}`);
            }
          } catch {}
          if (debug) console.log(`[PassiveCapture] um.json 响应: ${text.substring(0, 200)}`);
        } catch {}
      }

      // 2. 拦截 initialize.jsonp 响应
      if (url.includes('cf.aliyun.com/nocaptcha/initialize.jsonp')) {
        result.capturedUrls.push(`initialize.jsonp ${response.status()}`);
        // v9：记录完整 URL（用于 replay）
        result.initFullUrl = url;
        // v11 新增：记录 initialize.jsonp 完整响应头（x5sec 可能通过 Set-Cookie 下发）
        try {
          const headers = response.headers();
          const setCookie = headers['set-cookie'] || '';
          if (setCookie) {
            if (debug) console.log(`[PassiveCapture] initialize.jsonp Set-Cookie: ${setCookie.substring(0, 300)}`);
            // 从 Set-Cookie 提取 x5sec
            const x5secMatch = setCookie.match(/x5sec=([^;]+)/i);
            if (x5secMatch && x5secMatch[1]) {
              result.x5secFromSetCookie = x5secMatch[1];
              if (debug) console.log(`[PassiveCapture] ✓✓✓ initialize.jsonp Set-Cookie 下发 x5sec 长度=${x5secMatch[1].length}`);
            }
          }
        } catch {}
        // 从 URL 提取真实 appkey
        const appkeyMatch = url.match(/[?&]a=([^&]+)/);
        if (appkeyMatch && appkeyMatch[1]) {
          result.realAppkey = decodeURIComponent(appkeyMatch[1]);
          if (debug) console.log(`[PassiveCapture] ✓ 真实 appkey=${result.realAppkey}`);
        }
        // v9：从 URL 提取 version 参数
        const versionMatch = url.match(/[?&]v=([^&]+)/);
        if (versionMatch && versionMatch[1]) {
          result.initVersion = decodeURIComponent(versionMatch[1]);
          if (debug) console.log(`[PassiveCapture] ✓ 真实 NC version=${result.initVersion}`);
        }
        // v9：从 URL 提取 href 参数
        const hrefMatch = url.match(/[?&]href=([^&]+)/);
        if (hrefMatch && hrefMatch[1]) {
          result.initHref = decodeURIComponent(hrefMatch[1]);
          if (debug) console.log(`[PassiveCapture] ✓ 真实 href=${result.initHref.substring(0, 80)}`);
        }
        // v10 核心修复：从 URL 提取 t 参数作为 ncToken
        // 关键发现：页面自己生成的 initialize.jsonp URL 带 t=xxx 参数
        // initialize.jsonp 响应体没有 token 字段（只返回 {"result":{"msg":"success"},"success":true}）
        // t 参数才是真正的会话 token，页面后续 analyze.jsonp 会用同一个 t
        const tMatch = url.match(/[?&]t=([^&]+)/);
        if (tMatch && tMatch[1]) {
          const tFromUrl = decodeURIComponent(tMatch[1]);
          result.realNcToken = tFromUrl;
          if (debug) console.log(`[PassiveCapture] ✓✓✓ v10 从 URL 提取 t 参数作为 ncToken 长度=${tFromUrl.length} 前缀=${tFromUrl.substring(0, 12)}`);
        }
        if (debug) console.log(`[PassiveCapture] initialize.jsonp 完整 URL 长度=${url.length}`);
        // 提取响应体中的 token（备用：如果响应体有 token 字段则覆盖 URL t 参数）
        try {
          const text = await response.text();
          result.initResponseText = text.substring(0, 2000);
          // JSONP 响应格式：callback({...})，需要提取 JSON
          const jsonMatch = text.match(/\{[\s\S]+\}/);
          if (jsonMatch) {
            try {
              const data = JSON.parse(jsonMatch[0]);
              const token = (data && data.token) || '';
              if (token) {
                result.realNcToken = token;
                if (debug) console.log(`[PassiveCapture] ✓ ncToken 长度=${token.length}（响应体）`);
              }
            } catch {}
          }
        } catch {}
      }

      // 3. 拦截 analyze.jsonp 响应
      if (url.includes('cf.aliyun.com/nocaptcha/analyze.jsonp')) {
        result.capturedUrls.push(`analyze.jsonp ${response.status()}`);
        // v9：记录完整 URL
        result.analyzeFullUrl = url;
        try {
          const text = await response.text();
          result.analyzeResponseText = text.substring(0, 2000);
          // JSONP 响应格式：callback({...})
          const jsonMatch = text.match(/\{[\s\S]+\}/);
          if (jsonMatch) {
            try {
              const data = JSON.parse(jsonMatch[0]);
              const r = (data && data.result) || data || {};
              const code = typeof r.code === 'number' ? r.code : null;
              const value = String(r.value || '');
              const csessionid = String(r.csessionid || '');
              if (code !== null) result.analyzeCode = code;
              if (value) result.analyzeSig = value;
              if (csessionid) result.analyzeCsessionid = csessionid;
              if (debug) {
                console.log(`[PassiveCapture] ✓ analyze code=${code} sig长度=${value.length} csessionid长度=${csessionid.length}`);
              }
            } catch {}
          }
        } catch {}
      }

      // 4. 从所有响应的 Set-Cookie 头提取 x5sec
      const setCookie = response.headers()['set-cookie'] || '';
      if (setCookie && setCookie.includes('x5sec=')) {
        const x5secMatch = setCookie.match(/x5sec=([^;]+)/);
        if (x5secMatch && x5secMatch[1] && !result.x5secFromSetCookie) {
          result.x5secFromSetCookie = x5secMatch[1];
          if (debug) console.log(`[PassiveCapture] ✓✓✓ 从 Set-Cookie 提取 x5sec 长度=${x5secMatch[1].length} 来源=${url.substring(0, 80)}`);
        }
      }
    } catch (e) {
      // 忽略单个响应处理错误
    }
  });

  return result;
}

/**
 * 检测 FireyeJS 版本信息（用于调试）
 */
async function detectFireyejsVersion(page: Page): Promise<string> {
  return await page.evaluate(() => {
    const fy = (window as any).__fy;
    if (!fy) return '';
    // FireyeJS 通常在 __fy.version 或 __fy._version 中存储版本信息
    return fy.version || fy._version || fy.ver || '';
  });
}

// ============================================================
// 主函数：getFireyejsToken
// ============================================================

/**
 * 通过 Playwright 浏览器执行 FireyeJS，获取 FYToken 和 umidToken
 *
 * 完整流程：
 * 1. 启动浏览器（复用 sliderSolver 的反检测配置）
 * 2. 注入 cookie（清除风控 cookie）
 * 3. 导航到闲鱼首页
 * 4. 等待 window.__fy 可用
 * 5. 模拟鼠标移动和滚动
 * 6. 调用 getFYToken() 和 getUidToken()
 * 7. 返回结果
 *
 * @param options 配置选项
 * @returns FireyejsTokenResult
 */
export async function getFireyejsToken(
  options: FireyejsTokenOptions = {},
): Promise<FireyejsTokenResult> {
  const t0 = Date.now();
  const debug = options.debug ?? false;
  const targetUrl = options.targetUrl || DEFAULT_TARGET_URL;
  const simulateBehaviorEnabled = options.simulateBehavior ?? true;

  console.log(
    `[FireyejsToken] 开始获取 token targetUrl=${targetUrl} hasCookie=${!!options.cookieStr} simulateBehavior=${simulateBehaviorEnabled}`,
  );

  let context: BrowserContext | null = null;
  let browser: Browser | null = null;
  let sessionId = '';
  let userDataDir = '';

  try {
    // 1. 启动浏览器
    const launchResult = await launchBrowserForFireyejs(options);
    context = launchResult.context;
    browser = launchResult.browser;
    sessionId = launchResult.sessionId;
    userDataDir = launchResult.userDataDir;

    // 2. 注入反检测脚本（在每个新页面加载前注入）
    // 2026-08-03 修复：同时使用 context.addInitScript 和 page.addInitScript
    // 原因：context.addInitScript 只对创建后新打开的页面生效，
    //       但 launchPersistentContext 可能已有默认页面。page.addInitScript 确保当前页面也注入。
    await context.addInitScript(ANTI_DETECT_SCRIPT);

    // 3. 注入 cookie
    if (options.cookieStr) {
      await injectCookies(context, options.cookieStr);
    }

    // 4. 打开新页面
    const page = await context.newPage();

    // 4.1 在 page 级别也注入反检测脚本（双保险，确保在导航前生效）
    await page.addInitScript(ANTI_DETECT_SCRIPT);
    // 2026-08-03 v6 关键修复：设置 Sec-CH-UA-Platform HTTP 头（与 executeRouteJFlow 一致）
    await page.setExtraHTTPHeaders({
      'Sec-CH-UA-Platform': '"Windows"',
      'Sec-CH-UA': '"Google Chrome";v="146", "Chromium";v="146", "Not.A/Brand";v="8"',
      'Sec-CH-UA-Mobile': '?0',
      'Sec-CH-UA-Platform-Version': '"15.0.0"',
    });

    // 4.2 设置控制台消息捕获和网络监控（用于诊断 FireyeJS 加载失败）
    const networkMonitor = await setupNetworkMonitoring(page, debug);
    await setupConsoleCapture(page);

    try {
      // 5. 导航到目标 URL
      // 2026-08-03 修复：waitUntil 从 'networkidle' 改为 'domcontentloaded'
      // 原因：闲鱼首页有大量异步请求（tracker/perf/lottie 等），networkidle 可能永远无法达到
      //       导致 20 秒超时。domcontentloaded 只等 DOM 解析完成，fireyejs.js 会在 DOMContentLoaded 后异步加载
      //       后续通过 waitForFireyejs() 等待 window.__fy 可用即可
      console.log(`[FireyejsToken] 导航到 ${targetUrl}`);
      await page.goto(targetUrl, {
        waitUntil: 'domcontentloaded',
        timeout: NAVIGATION_TIMEOUT_MS,
      });

      // 额外等待 3 秒，让 fireyejs.js 有时间加载和初始化
      await page.waitForTimeout(3000);

      // 5.1 验证反检测脚本是否生效
      const envInfo = await detectEnvironment(page);
      console.log(
        `[FireyejsToken] 环境信息: ua=${envInfo.userAgent.substring(0, 50)}... platform=${envInfo.platform} uadPlatform=${envInfo.userAgentDataPlatform} webdriver=${envInfo.webdriverValue} vendor=${envInfo.vendor}`,
      );
      if (envInfo.hasWebdriver) {
        console.warn(`[FireyejsToken] ⚠️ navigator.webdriver=true，尝试在页面内手动清除`);
        // 尝试在页面内手动删除 webdriver 属性
        await page.evaluate(() => {
          try {
            delete Object.getPrototypeOf(navigator).webdriver;
          } catch (e) {}
          try {
            Object.defineProperty(navigator, 'webdriver', {
              get: () => false,
              configurable: true,
            });
          } catch (e) {}
          try {
            Object.defineProperty(Navigator.prototype, 'webdriver', {
              get: () => false,
              configurable: true,
            });
          } catch (e) {}
        });
      }

      // 5.2 收集页面诊断信息（排查 FireyeJS 未加载原因）
      const diagnostics = await collectPageDiagnostics(page);
      console.log(
        `[FireyejsToken] 页面诊断: url=${diagnostics.currentUrl.substring(0, 80)} title="${diagnostics.title}" readyState=${diagnostics.readyState}`,
      );
      console.log(
        `[FireyejsToken] FireyeJS 脚本标签: ${diagnostics.fireyejsScripts.length > 0 ? diagnostics.fireyejsScripts.join(', ') : '无'}`,
      );
      console.log(
        `[FireyejsToken] FireyeJS 全局变量: ${diagnostics.fireyejsGlobals.length > 0 ? diagnostics.fireyejsGlobals.join(', ') : '无'}`,
      );
      if (diagnostics.bodyTextPreview) {
        console.log(
          `[FireyejsToken] 页面内容预览: ${diagnostics.bodyTextPreview.substring(0, 100)}`,
        );
      }
      console.log(
        `[FireyejsToken] 网络监控: fireyejsLoaded=${networkMonitor.fireyejsLoaded} 请求数=${networkMonitor.fireyejsRequests.length}`,
      );
      if (networkMonitor.fireyejsRequests.length > 0) {
        networkMonitor.fireyejsRequests.forEach((r) =>
          console.log(`[FireyejsToken][network] ${r}`),
        );
      }

      // 7. 等待 FireyeJS 加载完成
      const fireyejsReady = await waitForFireyejs(page, debug);
      if (!fireyejsReady) {
        // 收集失败时的最终诊断信息
        const finalDiagnostics = await collectPageDiagnostics(page);
        console.log(
          `[FireyejsToken] ⚠️ FireyeJS 未加载完成。最终诊断: url=${finalDiagnostics.currentUrl.substring(0, 80)} title="${finalDiagnostics.title}" scripts=${finalDiagnostics.fireyejsScripts.length} globals=${finalDiagnostics.fireyejsGlobals.length}`,
        );
        return {
          ok: false,
          fyToken: '',
          umidToken: '',
          durationMs: Date.now() - t0,
          error: 'FireyeJS 未加载完成（window.__fy 不可用）',
          environmentInfo: envInfo,
          diagnostics: {
            currentUrl: finalDiagnostics.currentUrl,
            title: finalDiagnostics.title,
            readyState: finalDiagnostics.readyState,
            fireyejsScripts: finalDiagnostics.fireyejsScripts,
            fireyejsGlobals: finalDiagnostics.fireyejsGlobals,
            bodyTextPreview: finalDiagnostics.bodyTextPreview,
            networkRequests: networkMonitor.fireyejsRequests,
          },
        };
      }

      // 8. 模拟行为数据
      if (simulateBehaviorEnabled) {
        console.log(`[FireyejsToken] 模拟行为数据...`);
        await simulateBehavior(page);
      }

      // 9. 检测 FireyeJS 版本
      let fireyejsVersion = '';
      try {
        fireyejsVersion = await detectFireyejsVersion(page);
        if (debug && fireyejsVersion) {
          console.log(`[FireyejsToken] FireyeJS 版本: ${fireyejsVersion}`);
        }
      } catch {
        // 版本检测失败不影响主流程
      }

      // 9.5 检查 FireyeJS 对象结构（用于诊断 API）
      console.log(`[FireyejsToken] 检查 FireyeJS 对象结构...`);
      let objectInspection: Record<string, any> = {};
      try {
        objectInspection = await inspectFireyejsObjects(page);
        // 打印关键对象的类型和属性
        const awscfyInfo = objectInspection['AWSCFY'] || {};
        const fyModuleInfo = objectInspection['__fyModule'] || {};
        const fyglobaloptInfo = objectInspection['fyglobalopt'] || {};
        console.log(
          `[FireyejsToken] AWSCFY: exists=${awscfyInfo.exists} type=${awscfyInfo.type} keys=${JSON.stringify(awscfyInfo.keys || awscfyInfo.ownKeys || awscfyInfo.protoKeys || [])}`,
        );
        console.log(
          `[FireyejsToken] __fyModule: exists=${fyModuleInfo.exists} type=${fyModuleInfo.type} keys=${JSON.stringify(fyModuleInfo.keys || fyModuleInfo.ownKeys || fyModuleInfo.protoKeys || [])}`,
        );
        console.log(
          `[FireyejsToken] fyglobalopt: exists=${fyglobaloptInfo.exists} type=${fyglobaloptInfo.type} keys=${JSON.stringify(fyglobaloptInfo.keys || [])}`,
        );
        if (awscfyInfo.fnStr) {
          console.log(`[FireyejsToken] AWSCFY 函数签名: ${awscfyInfo.fnStr.substring(0, 150)}`);
        }
      } catch (e: any) {
        console.warn(`[FireyejsToken] 对象检查失败: ${e?.message || e}`);
      }

      // 10. 提取 FYToken（带 15 秒超时保护，防止 new AWSCFY() 挂起）
      console.log(`[FireyejsToken] 提取 FYToken（15秒超时）...`);
      let fyToken = '';
      try {
        fyToken = await Promise.race([
          extractFYToken(page, debug),
          new Promise<string>((_, reject) =>
            setTimeout(() => reject(new Error('extractFYToken 15秒超时')), 15000),
          ),
        ]);
      } catch (e: any) {
        return {
          ok: false,
          fyToken: '',
          umidToken: '',
          durationMs: Date.now() - t0,
          error: `getFYToken 调用失败: ${e?.message || e}`,
          fireyejsVersion,
          environmentInfo: envInfo,
        };
      }

      if (!fyToken) {
        return {
          ok: false,
          fyToken: '',
          umidToken: '',
          durationMs: Date.now() - t0,
          error: 'getFYToken 返回空值',
          fireyejsVersion,
          environmentInfo: envInfo,
        };
      }

      // 11. 提取 umidToken
      console.log(`[FireyejsToken] 提取 umidToken...`);
      let umidToken = '';
      try {
        umidToken = await extractUmidToken(page, debug);
      } catch (e: any) {
        // umidToken 失败不阻塞，返回部分成功
        console.warn(`[FireyejsToken] getUidToken 调用失败: ${e?.message || e}`);
      }

      const durationMs = Date.now() - t0;
      console.log(
        `[FireyejsToken] ✓ 成功获取 token fyToken长度=${fyToken.length} umidToken长度=${umidToken.length} 耗时=${durationMs}ms`,
      );

      return {
        ok: true,
        fyToken,
        umidToken,
        durationMs,
        fireyejsVersion,
        environmentInfo: envInfo,
      };
    } finally {
      // 关闭页面
      try {
        await page.close();
      } catch {
        // 忽略关闭错误
      }
    }
  } catch (e: any) {
    const durationMs = Date.now() - t0;
    const errorMsg = e?.message || String(e);
    console.error(`[FireyejsToken] ✗ 获取 token 失败: ${errorMsg} 耗时=${durationMs}ms`);
    return {
      ok: false,
      fyToken: '',
      umidToken: '',
      durationMs,
      error: errorMsg,
    };
  } finally {
    // 清理浏览器资源
    try {
      if (context) {
        await context.close();
      }
    } catch {
      // 忽略关闭错误
    }
    try {
      if (browser) {
        await browser.close();
      }
    } catch {
      // 忽略关闭错误
    }
    // 从 processRegistry 注销
    if (sessionId) {
      try {
        processRegistry.unregister(sessionId);
      } catch {
        // 忽略注销错误
      }
    }
    // 清理 userDataDir
    if (userDataDir) {
      try {
        await fs.rm(userDataDir, { recursive: true, force: true });
      } catch {
        // 忽略清理错误（可能是 Chrome 进程仍在占用）
      }
    }
  }
}

// ============================================================
// 测试函数（用于本地验证）
// ============================================================

/**
 * 测试 FireyeJS token 提取（无 cookie 匿名访问）
 *
 * 用于验证：
 * - 浏览器是否能正常启动
 * - fireyejs.js 是否被正确加载
 * - getFYToken/getUidToken 是否能返回有效 token
 */
export async function testFireyejsTokenExtraction(): Promise<FireyejsTokenResult> {
  console.log('[FireyejsToken] 测试模式：匿名访问闲鱼首页');
  return getFireyejsToken({
    cookieStr: '',
    targetUrl: DEFAULT_TARGET_URL,
    simulateBehavior: true,
    debug: true,
  });
}

// ============================================================
// 路线 J 完整流程：浏览器内完成 FireyeJS → um.json → initialize.jsonp → analyze.jsonp
// ============================================================
//
// 2026-08-03 v5 关键优化：
//   之前在 Python 端调用 um.json 失败（响应仅 9 字节，无 umt cookie），
//   根本原因：**IP 不一致**。
//   - FireyeJS token 在 crawler-service 容器（IP=A）的浏览器中生成
//   - um.json 在 automation-service 容器（IP=B）通过 requests 调用
//   - um.json 服务端会校验 FireyeJS token 与请求 IP 的一致性，IP 不一致则拒绝下发 umt
//
//   修复方案：在 crawler-service 浏览器内完成整个 um.json 调用，保持 IP 一致。
//   1. 浏览器内 fetch um.json（带 fyToken + umidToken）
//   2. 浏览器内 fetch initialize.jsonp（带 umt cookie）
//   3. 浏览器内 fetch analyze.jsonp（带 token + fyToken + 行为数据）
//   4. 浏览器内提取 Set-Cookie 中的 x5sec（如果有）
//
//   优势：
//   - IP 一致性：所有请求都从浏览器发出，IP 相同
//   - Cookie 一致性：浏览器自动管理 Set-Cookie
//   - Referer 一致性：浏览器自动添加正确的 Referer
//   - Origin/CORS：浏览器自动处理跨域

/**
 * 路线 J 完整流程结果（含 um.json/initialize.jsonp/analyze.jsonp 响应）
 */
export interface RouteJFlowResult {
  ok: boolean;
  fyToken: string;
  umidToken: string;
  /** um.json 响应状态码 */
  umJsonStatus: number;
  /** um.json 响应内容（前 500 字符） */
  umJsonResponse: string;
  /** um.json 返回的 umt cookie 值 */
  umtCookie: string;
  /** initialize.jsonp 响应状态码 */
  initStatus: number;
  /** initialize.jsonp 返回的 token (t 字段) */
  ncToken: string;
  /** initialize.jsonp 完整响应 */
  initResponse: string;
  /** analyze.jsonp 响应状态码 */
  analyzeStatus: number;
  /** analyze.jsonp result.code */
  analyzeResultCode: number | null;
  /** analyze.jsonp result.value (sig) */
  analyzeSig: string;
  /** analyze.jsonp result.csessionid */
  analyzeCsessionid: string;
  /** analyze.jsonp 完整响应 */
  analyzeResponse: string;
  /** 从 Set-Cookie 提取的 x5sec（如果有） */
  x5sec: string;
  /** 浏览器最终的所有 cookie（包含 umt/cna/x5sec 等） */
  finalCookies: string;
  /** x5sec 来源 */
  x5secSource: string;
  /** v9 新增：被动捕获到的 initialize.jsonp 完整 URL */
  initFullUrl: string;
  /** v9 新增：被动捕获到的 analyze.jsonp 完整 URL */
  analyzeFullUrl: string;
  /** v9 新增：实际使用的 initialize.jsonp URL（主动构造或 replay） */
  initUsedUrl: string;
  /** v9 新增：实际使用的 analyze.jsonp URL */
  analyzeUsedUrl: string;
  /** v9 新增：被动捕获到的真实 NC version 参数 */
  realNcVersion: string;
  /** v9 新增：被动捕获到的真实 href 参数 */
  realNcHref: string;
  /** v9 新增：被动捕获到的 um.json tn / id */
  passiveUmTn: string;
  passiveUmId: string;
  durationMs: number;
  error?: string;
  /** 是否实际使用了住宅 IP 代理（useProxy=true 但池为空时为 false） */
  proxyUsed?: boolean;
}

/**
 * 在浏览器内调用 um.json 端点（保持 IP 一致性）
 *
 * 使用 fetch() 从浏览器发起请求，浏览器会自动带上：
 * - 同源 Cookie
 * - 正确的 Referer/Origin
 * - 浏览器 IP（与 FireyeJS token 生成时相同）
 *
 * @param page Playwright Page 对象
 * @param fyToken FireyeJS getFYToken() 返回值
 * @param umidToken FireyeJS getUidToken() 返回值
 * @param appkey 应用标识
 * @returns { status, responseText, umtCookie }
 */
async function callUmJsonInBrowser(
  page: Page,
  fyToken: string,
  umidToken: string,
  appkey: string = 'XFFXFXFF',
): Promise<{ status: number; responseText: string; umtCookie: string; cnaCookie: string }> {
  return await page.evaluate(
    async ({ fyToken, umidToken, appkey }) => {
      const ts = Date.now();
      // NVC_Data 结构（最小化，只包含 nc.js 提取的必需字段）
      const body = {
        a: appkey,                // appkey
        scene: 'nc_h5',           // 场景
        b: fyToken,               // FYToken
        h: {
          umidToken: umidToken,   // umidToken
          trans: {},              // options.trans
        },
        d: 'nc_h5',               // scene（重复字段）
        ts: ts,
      };

      try {
        // 2026-08-03 v6 优化：添加 Referer 和 Origin 头
        // um.json 服务器会检查 Referer 和 Origin，缺失或不匹配会拒绝请求
        const resp = await fetch('https://ynuf.aliapp.org/service/um.json', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json;charset=UTF-8',
            'Accept': 'application/json, text/plain, */*',
            'Referer': window.location.href,
            'Origin': window.location.origin,
          },
          body: JSON.stringify(body),
          credentials: 'include',  // 自动带上同源 cookie
        });

        const text = await resp.text();

        // 从响应头提取 Set-Cookie（fetch API 无法直接读取 Set-Cookie，需要通过 document.cookie）
        // fetch 后，浏览器会自动将 Set-Cookie 写入 document.cookie
        const docCookie = document.cookie;
        const umtMatch = docCookie.match(/umt=([^;]+)/);
        const cnaMatch = docCookie.match(/cna=([^;]+)/);

        return {
          status: resp.status,
          responseText: text,
          umtCookie: umtMatch ? umtMatch[1] : '',
          cnaCookie: cnaMatch ? cnaMatch[1] : '',
        };
      } catch (e: any) {
        return {
          status: 0,
          responseText: `fetch error: ${e?.message || e}`,
          umtCookie: '',
          cnaCookie: '',
        };
      }
    },
    { fyToken, umidToken, appkey },
  );
}

/**
 * 在浏览器内调用 initialize.jsonp 端点
 *
 * v9 优化：
 * 1. 优先 replay 被动捕获的完整 URL（含真实 version/href 等参数）
 * 2. 否则使用主动构造的 URL，但添加 href 参数（当前页面 URL）
 * 3. 响应完整调试输出扩大到 2000 字符
 *
 * @param page Playwright Page 对象
 * @param appkey 应用标识
 * @param replayUrl 可选：从被动捕获得到的完整 URL（replay 模式）
 * @param version 可选：NC 库版本号（默认 1.97.0）
 * @returns { status, responseText, token, usedUrl }
 */
async function callInitializeJsonpInBrowser(
  page: Page,
  appkey: string = 'XFFXFXFF',
  replayUrl?: string,
  version: string = '1.97.0',
  realHref?: string,
): Promise<{ status: number; responseText: string; token: string; usedUrl: string }> {
  return await page.evaluate(
    async ({ appkey, replayUrl, version, realHref }) => {
      const callback = 'nc_init_callback_' + Date.now();
      let url: string;

      if (replayUrl) {
        // v9 replay 模式：使用捕获到的真实 URL，只替换 callback 参数
        // 移除原有的 callback 参数，再追加新的
        url = replayUrl.replace(/([?&])callback=[^&]*/, `$1callback=${callback}`);
        if (!url.includes(`callback=${callback}`)) {
          url += (url.includes('?') ? '&' : '?') + `callback=${callback}`;
        }
      } else {
        // v9 主动模式：构造 URL，添加 href 参数（当前页面 URL）
        // v10：优先使用被动捕获的真实 href
        const hrefSource = realHref || window.location.href;
        const href = encodeURIComponent(hrefSource);
        url = `https://cf.aliyun.com/nocaptcha/initialize.jsonp?a=${appkey}&scene=nc_h5&lang=zh_CN&v=${version}&href=${href}&callback=${callback}`;
      }

      try {
        // 使用 script 标签方式发起 JSONP 请求（与 nc.js 一致）
        // 这种方式能自动带上所有 cookie（包括 um.json 设置的 umt）
        return await new Promise<{ status: number; responseText: string; token: string; usedUrl: string }>((resolve) => {
          const script = document.createElement('script');
          let resolved = false;

          // 设置超时
          const timer = setTimeout(() => {
            if (!resolved) {
              resolved = true;
              if (script.parentNode) script.parentNode.removeChild(script);
              resolve({ status: 0, responseText: 'timeout', token: '', usedUrl: url });
            }
          }, 10000);

          // 定义回调函数
          (window as any)[callback] = (data: any) => {
            if (!resolved) {
              resolved = true;
              clearTimeout(timer);
              if (script.parentNode) script.parentNode.removeChild(script);
              delete (window as any)[callback];
              const token = (data && data.token) || '';
              resolve({
                status: 200,
                responseText: JSON.stringify(data).substring(0, 2000),
                token,
                usedUrl: url,
              });
            }
          };

          script.src = url;
          script.onerror = () => {
            if (!resolved) {
              resolved = true;
              clearTimeout(timer);
              if (script.parentNode) script.parentNode.removeChild(script);
              resolve({ status: 0, responseText: 'script error', token: '', usedUrl: url });
            }
          };

          document.head.appendChild(script);
        });
      } catch (e: any) {
        return {
          status: 0,
          responseText: `error: ${e?.message || e}`,
          token: '',
          usedUrl: url,
        };
      }
    },
    { appkey, replayUrl, version, realHref },
  );
}

/**
 * 在浏览器内调用 analyze.jsonp 端点
 *
 * v9 优化：
 * 1. 添加 href 参数（当前页面 URL）—— analyze.jsonp 也会校验 href
 * 2. 支持从被动捕获得到 version 参数，保持与页面一致
 * 3. 响应完整调试输出扩大到 2000 字符
 * 4. 返回 usedUrl 用于调试
 *
 * @param page Playwright Page 对象
 * @param appkey 应用标识
 * @param ncToken initialize.jsonp 返回的 token
 * @param fyToken FireyeJS getFYToken() 返回值
 * @param version NC 库版本号
 * @returns { status, responseText, resultCode, resultValue, resultCsessionid, x5secInCookie, usedUrl }
 */
async function callAnalyzeJsonpInBrowser(
  page: Page,
  appkey: string,
  ncToken: string,
  fyToken: string,
  version: string = '1.97.0',
  realHref?: string,
): Promise<{
  status: number;
  responseText: string;
  resultCode: number | null;
  resultValue: string;
  resultCsessionid: string;
  x5secInCookie: string;
  usedUrl: string;
}> {
  return await page.evaluate(
    async ({ appkey, ncToken, fyToken, version, realHref }) => {
      const callback = 'nc_analyze_callback_' + Date.now();
      // 构造 p 参数（行为指纹）
      const sessionId = Math.random().toString(36).substring(2, 18);
      const tsNow = Date.now();
      const tsStart = tsNow - 2000;
      const pValue = `${sessionId}_300_40_150_20_298_1200_5_${tsStart}_${tsNow}`;
      // v9：添加 href 参数（analyze.jsonp 也会校验）
      // v10：优先使用被动捕获的真实 href（页面在 passport.goofish.com/mini_login.htm 环境调用 NC）
      const hrefSource = realHref || window.location.href;
      const href = encodeURIComponent(hrefSource);
      const url = `https://cf.aliyun.com/nocaptcha/analyze.jsonp?a=${appkey}&t=${encodeURIComponent(ncToken)}&n=${encodeURIComponent(fyToken)}&p=${encodeURIComponent(pValue)}&scene=nc_h5&asyn=0&lang=zh_CN&v=${version}&href=${href}&callback=${callback}`;

      try {
        return await new Promise<{
          status: number;
          responseText: string;
          resultCode: number | null;
          resultValue: string;
          resultCsessionid: string;
          x5secInCookie: string;
          usedUrl: string;
        }>((resolve) => {
          const script = document.createElement('script');
          let resolved = false;

          const timer = setTimeout(() => {
            if (!resolved) {
              resolved = true;
              if (script.parentNode) script.parentNode.removeChild(script);
              // 超时后检查 document.cookie 是否有 x5sec
              const x5secMatch = document.cookie.match(/x5sec=([^;]+)/);
              resolve({
                status: 0,
                responseText: 'timeout',
                resultCode: null,
                resultValue: '',
                resultCsessionid: '',
                x5secInCookie: x5secMatch ? x5secMatch[1] : '',
                usedUrl: url,
              });
            }
          }, 10000);

          (window as any)[callback] = (data: any) => {
            if (!resolved) {
              resolved = true;
              clearTimeout(timer);
              if (script.parentNode) script.parentNode.removeChild(script);
              delete (window as any)[callback];

              const result = (data && data.result) || data || {};
              const code = (typeof result.code === 'number') ? result.code : null;
              const value = String(result.value || '');
              const csessionid = String(result.csessionid || '');

              // 检查 document.cookie 是否有 x5sec
              const x5secMatch = document.cookie.match(/x5sec=([^;]+)/);

              resolve({
                status: 200,
                responseText: JSON.stringify(data).substring(0, 2000),
                resultCode: code,
                resultValue: value,
                resultCsessionid: csessionid,
                x5secInCookie: x5secMatch ? x5secMatch[1] : '',
                usedUrl: url,
              });
            }
          };

          script.src = url;
          script.onerror = () => {
            if (!resolved) {
              resolved = true;
              clearTimeout(timer);
              if (script.parentNode) script.parentNode.removeChild(script);
              const x5secMatch = document.cookie.match(/x5sec=([^;]+)/);
              resolve({
                status: 0,
                responseText: 'script error',
                resultCode: null,
                resultValue: '',
                resultCsessionid: '',
                x5secInCookie: x5secMatch ? x5secMatch[1] : '',
                usedUrl: url,
              });
            }
          };

          document.head.appendChild(script);
        });
      } catch (e: any) {
        return {
          status: 0,
          responseText: `error: ${e?.message || e}`,
          resultCode: null,
          resultValue: '',
          resultCsessionid: '',
          x5secInCookie: '',
          usedUrl: url,
        };
      }
    },
    { appkey, ncToken, fyToken, version, realHref },
  );
}

/**
 * v11 新增：导航到登录页触发页面自身的 NC 验证流程
 *
 * 背景：页面在 goofish.com 首页只自动调用 initialize.jsonp + um.json，
 * 不调用 analyze.jsonp（需要用户交互触发）。而 passport.goofish.com/mini_login.htm
 * 登录页是闲鱼真实触发 NC 验证（滑块）的场景。
 *
 * 策略：导航到登录页，尝试点击"登录"按钮触发验证，
 * 让页面自己调用 analyze.jsonp（页面生成真实行为数据 p 参数），
 * 我们从网络响应拦截 analyze 结果和 x5sec cookie。
 *
 * @param context BrowserContext（复用同 IP、同 cookie）
 * @param debug 是否调试
 * @returns 触发结果
 */
async function triggerLoginPageNcFlow(
  context: BrowserContext,
  debug: boolean,
): Promise<{
  analyzeCode: number | null;
  analyzeSig: string;
  analyzeCsessionid: string;
  x5secFromSetCookie: string;
  capturedUrls: string[];
  pageDiagnostics: string;
}> {
  const result = {
    analyzeCode: null as number | null,
    analyzeSig: '',
    analyzeCsessionid: '',
    x5secFromSetCookie: '',
    capturedUrls: [] as string[],
    pageDiagnostics: '',
  };

  let page: Page | null = null;
  try {
    page = await context.newPage();
    await page.addInitScript(ANTI_DETECT_SCRIPT);
    await page.setExtraHTTPHeaders({
      'Sec-CH-UA-Platform': '"Windows"',
      'Sec-CH-UA': '"Google Chrome";v="146", "Chromium";v="146", "Not.A/Brand";v="8"',
      'Sec-CH-UA-Mobile': '?0',
      'Sec-CH-UA-Platform-Version': '"15.0.0"',
    });
    setupNetworkMonitoring(page, debug);
    setupConsoleCapture(page);
    const localCapture = setupPassiveNetworkCapture(page, debug);

    console.log(`[RouteJFlow] v11 导航到登录页触发页面自身 NC 流程...`);
    // v13 优化：使用与首页隐藏 iframe 相同的完整参数加载登录页
    // 之前直接导航 mini_login.htm 返回空页面，原因是缺少关键参数（lang/appName/styleType/stie 等）
    // 参数来源：首页 iframe src（从 v12 诊断中捕获）
    const loginUrl =
      'https://passport.goofish.com/mini_login.htm' +
      '?lang=zh_cn&appName=xianyu&appEntrance=web&styleType=vertical' +
      '&bizParams=&notLoadSsoView=false&notKeepLogin=false&isMobile=false' +
      '&qrCodeFirst=false&stie=77&rnd=' + Math.random().toString().substring(2, 14);
    await page.goto(loginUrl, {
      waitUntil: 'domcontentloaded',
      timeout: NAVIGATION_TIMEOUT_MS,
    });
    await page.waitForTimeout(5000);

    // 记录登录页诊断信息（debug 模式）
    if (debug) {
      const diag = await page.evaluate(() => {
        const buttons = Array.from(document.querySelectorAll('button, [type="submit"], [class*="login"], [class*="submit"]'))
          .slice(0, 10)
          .map((el) => {
            const cls = (el as HTMLElement).className;
            return `${(el.tagName).toLowerCase()}.${typeof cls === 'string' ? cls.split(' ').join('.') : ''}:${(el.textContent || '').trim().substring(0, 20)}`;
          });
        return {
          url: window.location.href,
          title: document.title,
          hasNcIframe: !!document.querySelector('iframe[src*="nc"]'),
          ncElements: Array.from(document.querySelectorAll('[class*="nc_"]')).slice(0, 10).map((el) => (el as HTMLElement).className.toString()),
          buttons,
        };
      });
      result.pageDiagnostics = JSON.stringify(diag);
      console.log(`[RouteJFlow] v11 登录页诊断: ${result.pageDiagnostics}`);
    }

    // 尝试点击登录按钮触发验证
    try {
      const clicked = await page.evaluate(() => {
        const candidates = Array.from(
          document.querySelectorAll('button, [type="submit"], [class*="login"], [class*="submit"], .fm-button'),
        ).filter((el) => {
          const cls = (el as HTMLElement).className;
          const text = (el.textContent || '').trim();
          return (
            text.includes('登录') ||
            text.includes('登 录') ||
            (typeof cls === 'string' && cls.includes('login')) ||
            (typeof cls === 'string' && cls.includes('submit'))
          );
        });
        if (candidates.length > 0) {
          (candidates[0] as HTMLElement).click();
          return true;
        }
        return false;
      });
      console.log(`[RouteJFlow] v11 点击登录按钮: ${clicked ? '已点击' : '未找到按钮'}`);
    } catch (e: any) {
      console.log(`[RouteJFlow] v11 点击登录按钮失败: ${e?.message}`);
    }

    // v14 新增：调用 baxiaCommon NC 强制显示验证框
    // v15 修复：先 init 初始化 NC，再 show（登录页中 baxiaCommon.NC 初始为 null）
    try {
      // v16 新增：dump AWSC / __baxia__ 详细 API（用于定位正确的 NC 初始化入口）
      const apiDump = await page.evaluate(() => {
        const result: Record<string, any> = {};
        const awsc = (window as any).AWSC;
        if (awsc) {
          result.AWSC = {
            use: typeof awsc.use,
            useKeys: awsc.use ? Object.keys(awsc.use).slice(0, 10) : [],
            configFY: awsc.configFY ? awsc.configFY.toString().substring(0, 150) : '',
          };
        }
        const baxia = (window as any).__baxia__;
        if (baxia) {
          result.__baxia__ = {
            baxiaInit: baxia.baxiaInit ? baxia.baxiaInit.toString().substring(0, 200) : '',
            baxiaPromptInit: typeof baxia.baxiaPromptInit,
            getFYModule: typeof baxia.getFYModule,
            postFYModule: typeof baxia.postFYModule,
            handleEffectUrl: typeof baxia.handleEffectUrl,
          };
        }
        const bc2 = (window as any).baxiaCommon;
        if (bc2) {
          result.baxiaCommon_inst_keys = (() => {
            try {
              const inst = new bc2();
              return Object.keys(inst).slice(0, 30);
            } catch (e) {
              return `error: ${e}`;
            }
          })();
        }
        return result;
      });
      if (debug) {
        console.log(`[RouteJFlow] v16 AWSC/__baxia__ API: ${JSON.stringify(apiDump)}`);
      }
      const showResult = await page.evaluate(async () => {
        const bc = (window as any).baxiaCommon;
        if (!bc) return 'no_baxiaCommon';
        try {
          // 1. 先初始化 NC
          if (typeof bc.init === 'function') {
            try {
              bc.init({ needUmidToken: true });
            } catch (e) {
              // init 内部异常不影响后续尝试
            }
            // init 可能是异步的，等待 NC 就绪
            await new Promise((r) => setTimeout(r, 1500));
          }
          // 2. 再尝试 show（静态属性或实例属性）
          const nc = bc.NC != null ? bc.NC : null;
          if (nc && typeof nc.show === 'function') {
            nc.show();
            return `show_called nc_type=${typeof bc.NC}`;
          }
          // 3. 尝试实例化后 show
          try {
            const inst = new bc();
            const instNc = inst.NC != null ? inst.NC : null;
            if (instNc && typeof instNc.show === 'function') {
              instNc.show();
              return `instance_show_called`;
            }
          } catch {}
          return `no_nc_api nc_type=${typeof bc.NC}`;
        } catch (e) {
          return `error: ${e}`;
        }
      });
      console.log(`[RouteJFlow] v15 baxiaCommon NC 显示: ${showResult}`);
    } catch (e: any) {
      console.log(`[RouteJFlow] v15 baxiaCommon NC.show 异常: ${e?.message}`);
    }

    // v15 新增：尝试填写手机号并再次点击登录，强制触发验证
    try {
      const filled = await page.evaluate(() => {
        // v16 增强：先切换到"密码登录"tab（滑块验证在密码登录时更常见）
        try {
          const pwdTab = document.querySelector('a.password-login-tab-item, [class*="password-login"], .password-login-tab-item');
          if (pwdTab) {
            (pwdTab as HTMLElement).click();
          }
        } catch {}
        // 找到手机号/账号输入框
        const inputs = Array.from(document.querySelectorAll('input')).filter((el) => {
          const type = (el as HTMLInputElement).type || '';
          const placeholder = (el as HTMLInputElement).placeholder || '';
          const name = (el as HTMLInputElement).name || '';
          const cls = (el as HTMLElement).className || '';
          const str = (type + placeholder + name + cls).toLowerCase();
          return (
            str.includes('tel') ||
            str.includes('mobile') ||
            str.includes('phone') ||
            str.includes('手机') ||
            str.includes('loginid') ||
            str.includes('username') ||
            str.includes('account')
          );
        });
        if (inputs.length > 0) {
          const input = inputs[0] as HTMLInputElement;
          const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
          if (setter) {
            setter.call(input, '13800138000');
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
          }
          // v16 新增：同时填写密码框（任意密码，滑块验证在密码校验前触发）
          const pwdInputs = Array.from(document.querySelectorAll('input[type="password"]'));
          if (pwdInputs.length > 0) {
            const pwdInput = pwdInputs[0] as HTMLInputElement;
            if (setter) {
              setter.call(pwdInput, 'Xy123456!');
              pwdInput.dispatchEvent(new Event('input', { bubbles: true }));
              pwdInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
          }
          return `filled count=${inputs.length} pwd=${pwdInputs.length > 0 ? 'yes' : 'no'}`;
        }
        return 'no_input';
      });
      console.log(`[RouteJFlow] v15 填手机号: ${filled}`);
    } catch (e: any) {
      console.log(`[RouteJFlow] v15 填手机号异常: ${e?.message}`);
    }

    // 再次点击登录按钮（v15：填充后重新触发）
    try {
      const clicked2 = await page.evaluate(() => {
        const candidates = Array.from(
          document.querySelectorAll('button, [type="submit"], [class*="login"], [class*="submit"], .fm-button'),
        ).filter((el) => {
          const cls = (el as HTMLElement).className;
          const text = (el.textContent || '').trim();
          return (
            text.includes('登录') ||
            text.includes('登 录') ||
            (typeof cls === 'string' && cls.includes('login')) ||
            (typeof cls === 'string' && cls.includes('submit'))
          );
        });
        if (candidates.length > 0) {
          (candidates[0] as HTMLElement).click();
          return true;
        }
        return false;
      });
      console.log(`[RouteJFlow] v15 再次点击登录按钮: ${clicked2 ? '已点击' : '未找到'}`);
    } catch (e: any) {
      console.log(`[RouteJFlow] v15 再次点击登录异常: ${e?.message}`);
    }

    // v14 新增：等待滑块渲染并尝试拖动
    // v15 增强：轮询等待滑块变为可见（offsetParent != null）
    await page.waitForTimeout(2500);
    let dragDone = false;
    for (let attempt = 0; attempt < 3; attempt++) {
      dragDone = await dragNcSlider(page);
      if (dragDone) break;
      await page.waitForTimeout(1500);
    }
    console.log(`[RouteJFlow] v14 滑块拖动: ${dragDone ? '已尝试' : '未找到'}`);

    // 等待页面触发 NC 验证（initialize + analyze）
    await page.waitForTimeout(6000);

    // 合并捕获结果
    result.capturedUrls = localCapture.capturedUrls;
    result.analyzeCode = localCapture.analyzeCode;
    result.analyzeSig = localCapture.analyzeSig;
    result.analyzeCsessionid = localCapture.analyzeCsessionid;
    result.x5secFromSetCookie = localCapture.x5secFromSetCookie;

    console.log(
      `[RouteJFlow] v11 登录页捕获: analyze=${localCapture.analyzeCode} sig长度=${localCapture.analyzeSig.length} x5sec=${localCapture.x5secFromSetCookie ? '✓' : '✗'} 请求数=${localCapture.capturedUrls.length}`,
    );
    if (debug && localCapture.capturedUrls.length > 0) {
      console.log(`[RouteJFlow] v11 登录页请求: ${localCapture.capturedUrls.join(', ')}`);
    }
  } catch (e: any) {
    console.log(`[RouteJFlow] v11 登录页流程异常: ${e?.message}`);
  } finally {
    // 关闭登录页（不关闭 context）
    if (page) {
      try {
        await page.close();
      } catch {}
    }
  }
  return result;
}

/**
 * v12 新增：dump 页面中所有 NC 相关全局对象和方法
 *
 * 目标：找到页面自身的 NC（nocaptcha）实例 API，直接调用它的 analyze 方法，
 * 让页面生成真实行为数据 p 参数（我们的伪造 p 参数被 code=300 block）。
 *
 * 常见 NC 全局变量：window.nc、window.NC、window.NCObj、window.noCaptcha、
 * window.noCaptchaConfig、data-nc-* 元素等。
 *
 * @param page Playwright Page 对象
 * @param debug 是否调试
 */
async function dumpNcGlobals(page: Page, debug: boolean): Promise<string> {
  try {
    const info = await page.evaluate(() => {
      const result: Record<string, any> = {};
      const keys = Object.keys(window).filter(
        (k) =>
          k.length < 60 &&
          /nc|nocaptcha|baxia|validate|awsc|ncslide|ncconfig/i.test(k),
      );
      for (const key of keys) {
        const obj = (window as any)[key];
        if (obj === undefined || obj === null) continue;
        const type = typeof obj;
        if (type === 'function') {
          result[key] = {
            type: 'function',
            ownKeys: Object.keys(obj).slice(0, 20),
            fnStr: obj.toString().substring(0, 80),
          };
        } else if (type === 'object') {
          result[key] = { type: 'object', keys: Object.keys(obj).slice(0, 20) };
        } else {
          result[key] = { type, value: String(obj).substring(0, 50) };
        }
      }
      // 查找 NC iframe
      const ncIframes = Array.from(document.querySelectorAll('iframe'))
        .map((f) => f.src)
        .filter((s) => /nc|captcha|validate|baxia/i.test(s));
      // 查找 NC DOM 元素
      const ncDomElements = Array.from(document.querySelectorAll('[data-nc], [id*="nc_"], [class*="nc_"]'))
        .slice(0, 10)
        .map((el) => {
          const cls = (el as HTMLElement).className;
          return `${el.tagName}.${typeof cls === 'string' ? cls.split(' ').join('.') : ''}`;
        });

      // v13 深度检查 baxiaCommon（包含 NC/init/handler 方法，是页面自身 NC API）
      const bc = (window as any).baxiaCommon;
      if (bc) {
        result['baxiaCommon_detail'] = {
          NC: typeof bc.NC,
          ncKeys: bc.NC && typeof bc.NC === 'object' ? Object.keys(bc.NC).slice(0, 30) : [],
          ncFnStr: bc.NC && typeof bc.NC === 'function' ? bc.NC.toString().substring(0, 200) : '',
          init: typeof bc.init,
          initFnStr: bc.init ? bc.init.toString().substring(0, 200) : '',
          handler: typeof bc.handler,
          getUA: typeof bc.getUA,
        };
        // 尝试实例化 baxiaCommon 查看实例结构
        try {
          const inst = new bc();
          result['baxiaCommon_instance'] = {
            keys: Object.keys(inst).slice(0, 30),
            NC: typeof inst.NC,
            ncKeys: inst.NC && typeof inst.NC === 'object' ? Object.keys(inst.NC).slice(0, 30) : [],
            ncFnStr: inst.NC && typeof inst.NC === 'function' ? inst.NC.toString().substring(0, 150) : '',
            init: typeof inst.init,
            initFnStr: inst.init ? inst.init.toString().substring(0, 150) : '',
          };
        } catch {}
      }
      return { ncKeys: keys, ncObjects: result, ncIframes, ncDomElements };
    });
    if (debug) {
      console.log(`[RouteJFlow] v12 NC 全局 keys: ${JSON.stringify(info.ncKeys)}`);
      console.log(`[RouteJFlow] v12 NC iframes: ${JSON.stringify(info.ncIframes)}`);
      console.log(`[RouteJFlow] v12 NC DOM: ${JSON.stringify(info.ncDomElements)}`);
      console.log(`[RouteJFlow] v12 NC 对象详情: ${JSON.stringify(info.ncObjects).substring(0, 1500)}`);
    }
    return JSON.stringify(info).substring(0, 2000);
  } catch (e: any) {
    return `dumpNcGlobals error: ${e?.message}`;
  }
}

/**
 * v14 新增：拖动 NC 滑块验证
 *
 * 登录页渲染了 NC 滑块组件（nc_scale 轨道 + btn_slide 滑块按钮），
 * 拖动滑块到底部后页面自动调用 analyze.jsonp（生成真实行为数据），
 * 服务端返回 code=0 并可能通过 Set-Cookie 下发 x5sec。
 *
 * @param page Playwright Page 对象
 * @returns 是否找到并尝试拖动滑块
 */
async function dragNcSlider(page: Page): Promise<boolean> {
  try {
    const sliderInfo = await page.evaluate((): {
      found: boolean;
      notVisible?: boolean;
      scaleX?: number;
      scaleY?: number;
      scaleWidth?: number;
      scaleHeight?: number;
      btnX?: number;
      btnY?: number;
      btnWidth?: number;
    } => {
      // v15 增强：如果滑块容器隐藏，尝试显示（NC 验证框常见 display:none 预加载）
      const wrapper = document.querySelector('.nc_wrapper, [class*="nc_wrapper"]') as HTMLElement | null;
      if (wrapper && wrapper.style && wrapper.style.display === 'none') {
        wrapper.style.display = 'block';
      }
      // 查找滑块元素（轨道 + 按钮）
      const scale = document.querySelector('.nc_scale, [class*="nc_scale"]') as HTMLElement | null;
      const btn = document.querySelector('.btn_slide, [class*="btn_slide"], .nc_iconfont.btn_slide') as HTMLElement | null;
      if (!scale) return { found: false };
      // 检查可见性
      const rect = scale.getBoundingClientRect();
      const visible =
        rect.width > 0 &&
        rect.height > 0 &&
        scale.offsetParent !== null &&
        getComputedStyle(scale).visibility !== 'hidden' &&
        getComputedStyle(scale).display !== 'none';
      if (!visible) {
        return { found: false, notVisible: true };
      }
      const scaleRect = scale.getBoundingClientRect();
      let btnRect: DOMRect | null = null;
      if (btn) {
        btnRect = btn.getBoundingClientRect();
      }
      return {
        found: true,
        scaleX: scaleRect.x,
        scaleY: scaleRect.y,
        scaleWidth: scaleRect.width,
        scaleHeight: scaleRect.height,
        btnX: btnRect ? btnRect.x : scaleRect.x,
        btnY: btnRect ? btnRect.y : scaleRect.y,
        btnWidth: btnRect ? btnRect.width : 40,
      };
    });
    if (!sliderInfo.found || !sliderInfo.scaleWidth || sliderInfo.scaleWidth <= 0) {
      if (sliderInfo.notVisible) {
        console.log(`[RouteJFlow] v14 滑块元素存在但不可见，跳过拖动`);
      } else {
        console.log(`[RouteJFlow] v14 未找到滑块元素，跳过拖动`);
      }
      return false;
    }
    const startX = (sliderInfo.btnX || 0) + (sliderInfo.btnWidth || 40) / 2;
    const startY = (sliderInfo.btnY || 0) + (sliderInfo.scaleHeight || 40) / 2;
    const endX = (sliderInfo.scaleX || 0) + (sliderInfo.scaleWidth || 260) - (sliderInfo.btnWidth || 40) / 2;
    console.log(
      `[RouteJFlow] v14 拖动滑块 startX=${startX.toFixed(0)} endX=${endX.toFixed(0)} y=${startY.toFixed(0)} 轨道宽=${(sliderInfo.scaleWidth || 0).toFixed(0)}`,
    );
    await page.mouse.move(startX, startY, { steps: 5 });
    await page.waitForTimeout(200);
    await page.mouse.down();
    await page.waitForTimeout(100);
    // 分步拖动（模拟人类加速-减速轨迹）
    const steps = 15 + Math.floor(Math.random() * 10);
    for (let i = 1; i <= steps; i++) {
      const progress = i / steps;
      // 缓动曲线：先加速后减速
      const eased = progress < 0.5 ? 2 * progress * progress : 1 - Math.pow(-2 * progress + 2, 2) / 2;
      const x = startX + (endX - startX) * eased;
      await page.mouse.move(x, startY, { steps: 2 });
      await page.waitForTimeout(20 + Math.random() * 40);
    }
    await page.waitForTimeout(150);
    await page.mouse.up();
    console.log(`[RouteJFlow] v14 滑块拖动完成，等待页面触发 analyze...`);
    return true;
  } catch (e: any) {
    console.log(`[RouteJFlow] v14 滑块拖动异常: ${e?.message}`);
    return false;
  }
}

/**
 * 路线 J 完整流程：在浏览器内串联 FireyeJS → um.json → initialize.jsonp → analyze.jsonp
 *
 * 解决 Python 端调用 um.json IP 不一致问题：
 * - FireyeJS token 在 crawler-service 浏览器中生成
 * - um.json 必须从同一浏览器内发起（保持 IP 一致）
 *
 * 完整流程：
 * 1. 启动浏览器，加载闲鱼首页，让 FireyeJS 加载并初始化
 * 2. 模拟鼠标移动生成行为数据
 * 3. 调用 __fyModule.getFYToken() / getUidToken() 获取 token
 * 4. 浏览器内 fetch um.json（带 fyToken/umidToken）→ 获取 umt cookie
 * 5. 浏览器内 JSONP initialize.jsonp（自动带 umt cookie）→ 获取 ncToken
 * 6. 浏览器内 JSONP analyze.jsonp（带 ncToken + fyToken + p）→ 获取 sig + csessionid
 * 7. 检查浏览器 cookie 中是否有 x5sec（analyze 成功后服务端可能下发）
 *
 * @param options 选项（cookieStr / debug 等）
 * @returns RouteJFlowResult
 */
export async function executeRouteJFlow(
  options: FireyejsTokenOptions = {},
): Promise<RouteJFlowResult> {
  const t0 = Date.now();
  const debug = options.debug ?? false;
  const targetUrl = options.targetUrl || DEFAULT_TARGET_URL;
  const simulateBehaviorEnabled = options.simulateBehavior ?? true;

  console.log(
    `[RouteJFlow] 启动完整路线 J 流程 targetUrl=${targetUrl} hasCookie=${!!options.cookieStr}`,
  );

  let context: BrowserContext | null = null;
  let browser: Browser | null = null;
  let sessionId = '';
  let userDataDir = '';

  const result: RouteJFlowResult = {
    ok: false,
    fyToken: '',
    umidToken: '',
    umJsonStatus: 0,
    umJsonResponse: '',
    umtCookie: '',
    initStatus: 0,
    ncToken: '',
    initResponse: '',
    analyzeStatus: 0,
    analyzeResultCode: null,
    analyzeSig: '',
    analyzeCsessionid: '',
    analyzeResponse: '',
    x5sec: '',
    finalCookies: '',
    x5secSource: '',
    initFullUrl: '',
    analyzeFullUrl: '',
    initUsedUrl: '',
    analyzeUsedUrl: '',
    realNcVersion: '',
    realNcHref: '',
    passiveUmTn: '',
    passiveUmId: '',
    durationMs: 0,
  };

  try {
    // 1. 启动浏览器（复用 getFireyejsToken 的初始化逻辑）
    const launchResult = await launchBrowserForFireyejs(options);
    context = launchResult.context;
    browser = launchResult.browser;
    sessionId = launchResult.sessionId;
    userDataDir = launchResult.userDataDir;

    // 2. 注入反检测脚本和 cookie
    await context.addInitScript(ANTI_DETECT_SCRIPT);
    if (options.cookieStr) {
      await injectCookies(context, options.cookieStr);
    }

    // 3. 打开页面并导航
    const page = await context.newPage();
    await page.addInitScript(ANTI_DETECT_SCRIPT);
    // 2026-08-03 v6 关键修复：设置 Sec-CH-UA-Platform HTTP 头
    // 即使覆盖了 navigator.userAgentData，浏览器仍会自动发送 Sec-CH-UA-Platform 请求头
    // 包含真实平台信息（"Linux"），导致 um.json 服务器通过 HTTP 头检测到真实平台
    // 修复：通过 setExtraHTTPHeaders 覆盖 Sec-CH-UA-Platform 为 "Windows"
    await page.setExtraHTTPHeaders({
      'Sec-CH-UA-Platform': '"Windows"',
      'Sec-CH-UA': '"Google Chrome";v="146", "Chromium";v="146", "Not.A/Brand";v="8"',
      'Sec-CH-UA-Mobile': '?0',
      'Sec-CH-UA-Platform-Version': '"15.0.0"',
    });
    await setupNetworkMonitoring(page, debug);
    await setupConsoleCapture(page);

    // v7 新增：设置被动网络捕获，监听页面自己发起的 NC 流程
    // 关键发现：页面自己用 appkey=CF_APP_TBLogin_PC（成功），我们硬编码 XFFXFXFF（失败）
    // v7 策略：让页面自己跑 NC，从网络响应中拦截 sig/csessionid/x5sec
    const passiveCapture = setupPassiveNetworkCapture(page, debug);

    try {
      // v20 新增：导航重试机制（goofish 对服务器 IP 间歇性限流，导航可能超时）
      // 最多重试 2 次，每次等待 5 秒，延长单次超时到 30 秒
      let navigated = false;
      for (let navAttempt = 0; navAttempt < 3 && !navigated; navAttempt++) {
        if (navAttempt > 0) {
          console.log(`[RouteJFlow] v20 导航重试第 ${navAttempt} 次（等待 5 秒）...`);
          await page.waitForTimeout(5000);
        }
        console.log(`[RouteJFlow] 导航到 ${targetUrl}（尝试 ${navAttempt + 1}/3）`);
        try {
          await page.goto(targetUrl, {
            waitUntil: 'domcontentloaded',
            timeout: 30_000,
          });
          navigated = true;
        } catch (navErr: any) {
          console.warn(`[RouteJFlow] v20 导航失败（尝试 ${navAttempt + 1}/3）: ${navErr?.message?.substring(0, 100)}`);
        }
      }
      if (!navigated) {
        result.error = '页面导航多次重试失败（goofish 可能限流）';
        result.durationMs = Date.now() - t0;
        return result;
      }
      await page.waitForTimeout(3000);

      // 4. 等待 FireyeJS 加载
      const fireyejsReady = await waitForFireyejs(page, debug);
      if (!fireyejsReady) {
        result.error = 'FireyeJS 未加载完成';
        result.durationMs = Date.now() - t0;
        return result;
      }

      // 5. 模拟行为数据
      if (simulateBehaviorEnabled) {
        console.log(`[RouteJFlow] 模拟行为数据...`);
        await simulateBehavior(page);
      }

      // 5.1 v12 新增：dump NC 全局对象（找到页面自身的 NC 实例 API）
      // 关键目标：页面自己调用 analyze.jsonp 会生成真实行为数据 p 参数
      // 我们需要找到 NC 实例（window.nc / NC / NCObj 等）并触发其 analyze 方法
      await dumpNcGlobals(page, debug);

      // v18 新增：在 FireyeJS 加载后立即调用 baxiaCommon.NC.show() 显示验证框并拖动滑块
      // 时机关键：此时 NC 实例最可能就绪（v12 dump 证明此阶段 baxiaCommon.NC 有 show 方法）
      // 拖动滑块 → 页面自己调用 analyze.jsonp（生成真实行为数据 p 参数）
      try {
        const ncShowResult = await page.evaluate(() => {
          const bc: any = (window as any).baxiaCommon;
          const nc = bc?.NC;
          let showStatus = '';
          if (nc && typeof nc.show === 'function') {
            try {
              nc.show();
              showStatus = 'show_called';
            } catch (e) {
              // v21：show 内部崩溃（NC 内部组件未就绪），继续尝试手动显示容器
              showStatus = `show_error: ${e}`;
            }
          } else {
            showStatus = `no_nc type=${typeof nc}`;
          }
          // v21：手动显示 NC 滑块容器（即使 show 失败，滑块元素可能已渲染）
          try {
            const wrapper = document.querySelector('.nc_wrapper, [class*="nc_wrapper"]') as HTMLElement | null;
            if (wrapper) {
              wrapper.style.display = 'block';
              wrapper.style.visibility = 'visible';
              // 尝试移除隐藏类
              const classes = wrapper.className.split(/\s+/).filter((c) => !/hide|hidden|none/i.test(c));
              wrapper.className = classes.join(' ');
            }
            const scale = document.querySelector('.nc_scale, [class*="nc_scale"]') as HTMLElement | null;
            if (scale) {
              (scale as HTMLElement).style.display = 'block';
            }
          } catch {}
          return showStatus;
        });
        console.log(`[RouteJFlow] v18 首页 baxiaCommon.NC.show(): ${ncShowResult}`);

        // 等待滑块显示（即使 NC.show 失败，容器已手动显示）
        await page.waitForTimeout(2500);
        // 尝试拖动滑块（最多 3 次）
        let dragDone18 = false;
        for (let attempt = 0; attempt < 3; attempt++) {
          dragDone18 = await dragNcSlider(page);
          if (dragDone18) break;
          await page.waitForTimeout(1500);
        }
        console.log(`[RouteJFlow] v18 首页滑块拖动: ${dragDone18 ? '已尝试' : '未找到'}`);
        // 等待页面触发 analyze
        await page.waitForTimeout(4000);

        // 检查被动捕获结果
        if (passiveCapture.x5secFromSetCookie) {
          result.x5sec = passiveCapture.x5secFromSetCookie;
          result.x5secSource = 'home_nc_set_cookie';
          result.ok = true;
          console.log(`[RouteJFlow] ✓✓✓ v18 首页 NC 流程 Set-Cookie 下发 x5sec 长度=${result.x5sec.length}`);
        } else if (passiveCapture.analyzeCode === 0 && passiveCapture.analyzeSig && passiveCapture.analyzeCsessionid) {
          const realAppkey = passiveCapture.realAppkey || 'CF_APP_TBLogin_PC';
          const x5secdata = `${realAppkey}=${passiveCapture.analyzeSig}=${passiveCapture.analyzeCsessionid}`;
          result.x5sec = x5secdata;
          result.x5secSource = 'home_nc_constructed_from_sig';
          result.ok = true;
          result.analyzeResultCode = 0;
          result.analyzeSig = passiveCapture.analyzeSig;
          result.analyzeCsessionid = passiveCapture.analyzeCsessionid;
          console.log(`[RouteJFlow] ✓✓✓ v18 首页 NC analyze code=0 构造 x5secdata 长度=${x5secdata.length}`);
        } else {
          console.log(`[RouteJFlow] v18 首页 NC 未触发 analyze（analyzeCode=${passiveCapture.analyzeCode} x5sec=无）`);
        }

        // v23 新增：操作首页的登录 iframe（iframe 内是完整登录页，NC 滑块组件在 iframe 内渲染）
        // 首页的 NC 验证框属于登录 iframe（passport.goofish.com/mini_login.htm），主文档 NC.show() 内部崩溃
        // 因为 NC 组件实际在 iframe 内初始化，需在 iframe 上下文操作
        try {
          const frames = page.frames();
          const loginFrame = frames.find((f) => f.url().includes('passport.goofish.com'));
          if (loginFrame) {
            console.log(`[RouteJFlow] v23 找到登录 iframe: ${loginFrame.url().substring(0, 100)}`);
            const frameDiag = await loginFrame.evaluate(() => {
              const bc: any = (window as any).baxiaCommon;
              return {
                ncType: typeof (bc?.NC),
                ncKeys: bc?.NC && typeof bc.NC === 'object' ? Object.keys(bc.NC).slice(0, 10) : [],
                hasNcWrapper: !!document.querySelector('.nc_wrapper'),
                hasNcScale: !!document.querySelector('.nc_scale'),
                hasLoginBtn: !!document.querySelector('[class*="login"], button'),
                hasFy: !!(window as any).__fyModule || !!(window as any).AWSCFY,
              };
            });
            console.log(`[RouteJFlow] v23 iframe 诊断: ${JSON.stringify(frameDiag)}`);

            // v24 新增：在 iframe 内用 Playwright 原生 API 填写表单并触发验证
            // v26 修复：改用密码登录（不依赖手机号注册状态，任意账号都触发验证）
            // v28 新增：iframe 全量网络捕获（诊断登录提交是否真的到达服务端）
            const loginFrameRequests: string[] = [];
            const loginFrameResponses: string[] = [];
            const loginRequestListener = (req: any) => {
              try {
                if (req.frame() !== loginFrame) return;
                const url = req.url();
                if (/login|passport|sms|sendcode|validate|signin|captcha|loginid/i.test(url)) {
                  loginFrameRequests.push(`${req.method()} ${url.substring(0, 160)}`);
                  if (loginFrameRequests.length > 15) loginFrameRequests.shift();
                }
              } catch {}
            };
            const loginResponseListener = (res: any) => {
              try {
                if (res.frame() !== loginFrame) return;
                const url = res.url();
                if (/login|passport|sms|sendcode|validate|signin|captcha|loginid/i.test(url)) {
                  loginFrameResponses.push(`${res.status()} ${url.substring(0, 160)}`);
                  if (loginFrameResponses.length > 15) loginFrameResponses.shift();
                }
              } catch {}
            };
            page.on('request', loginRequestListener);
            page.on('response', loginResponseListener);
            // v34 修复：移除 submit 拦截器！v28 证据显示 mini_login 的登录机制是原生 GET 表单提交
            // （requestSubmit → GET mini_login.htm?fm-login-id=...&fm-login-password=... 返回 200）
            // 服务器根据 URL 参数处理登录并重渲染页面（显示错误/激活 NC 滑块）
            // v29-v33 的 preventDefault 拦截器阻止了原生提交 → 点击登录按钮零请求
            // v34 恢复原生提交，让 iframe 重载并观察服务器响应
            try {
              // 切换到"密码登录"tab
              const pwdTab = loginFrame.locator('a.password-login-tab-item, [class*="password-login"]').first();
              if ((await pwdTab.count()) > 0) {
                await pwdTab.click({ timeout: 5000, force: true });
                await page.waitForTimeout(800);
                console.log(`[RouteJFlow] v26 已切换到密码登录 tab`);
              }
              // 填账号（任意值，触发验证）
              const accountInput = loginFrame
                .locator('input[placeholder*="手机"], input[placeholder*="账号"], input[name*="loginid"], input[placeholder*="邮箱"], input[type="tel"]')
                .first();
              if ((await accountInput.count()) > 0) {
                await accountInput.fill('13800138001', { timeout: 8000 });
                console.log(`[RouteJFlow] v26 iframe 已填账号`);
              }
              // 填密码（任意值）
              const pwdInput = loginFrame.locator('input[type="password"]').first();
              if ((await pwdInput.count()) > 0) {
                await pwdInput.fill('Xy123456!', { timeout: 8000 });
                console.log(`[RouteJFlow] v26 iframe 已填密码`);
              }
              // v28 新增：读取填表后的表单状态（诊断框架是否识别 Playwright 注入）
              const formState = await loginFrame.evaluate(() => {
                const account = document.querySelector('input[name*="loginid"], input[type="tel"], input[placeholder*="手机"], input[placeholder*="账号"]') as HTMLInputElement | null;
                const pwd = document.querySelector('input[type="password"]') as HTMLInputElement | null;
                const btn = document.querySelector('button[type="submit"], .fm-button, [class*="login-btn"], [class*="submit"]') as HTMLButtonElement | null;
                const form = document.querySelector('form.login-form, form') as HTMLFormElement | null;
                return {
                  accountValue: account ? account.value : null,
                  pwdLen: pwd ? pwd.value.length : -1,
                  btnDisabled: btn ? (btn.disabled || btn.getAttribute('aria-disabled')) : null,
                  formValid: form ? form.checkValidity() : null,
                  validationMsg: form && !form.checkValidity() ? (form.querySelector(':invalid') as HTMLElement | null)?.outerHTML?.substring(0, 120) || '' : '',
                };
              });
              console.log(`[RouteJFlow] v28 表单状态: ${JSON.stringify(formState)}`);
              // v35 新增：注入 fetch/XHR 拦截器，捕获 iframe 内所有 AJAX 请求（不受 URL 关键词过滤限制）
              // v34 发现点击登录按钮后零网络请求（过滤器只匹配 login/passport 等关键词，可能漏掉）
              try {
                await loginFrame.evaluate(() => {
                  const w = window as any;
                  w.__routejReqs = [];
                  const origFetch = w.fetch ? w.fetch.bind(w) : null;
                  if (origFetch) {
                    w.fetch = (...args: any[]) => {
                      try {
                        const url = typeof args[0] === 'string' ? args[0] : args[0]?.url || '';
                        w.__routejReqs.push('FETCH ' + String(url).substring(0, 150));
                        if (w.__routejReqs.length > 40) w.__routejReqs.shift();
                      } catch {}
                      return (origFetch as any)(...args);
                    };
                  }
                  const origOpen = XMLHttpRequest.prototype.open;
                  XMLHttpRequest.prototype.open = function (method: string, url: string, ...rest: any[]) {
                    try {
                      w.__routejReqs.push('XHR ' + method + ' ' + String(url).substring(0, 150));
                      if (w.__routejReqs.length > 40) w.__routejReqs.shift();
                    } catch {}
                    return (origOpen as any).call(this, method, url, ...rest);
                  };
                });
              } catch {}
              // v29 修复：不再 requestSubmit（会触发原生 GET 导航重载 iframe）
              // 改为受信点击登录按钮（页面 JS 处理器只绑定按钮点击）
              // v29 新增：枚举 iframe 内所有可点击的登录候选元素
              let loginCandidates: string[] = [];
              try {
                loginCandidates = await loginFrame.evaluate(() => {
                  return Array.from(
                    document.querySelectorAll('button, [type="submit"], [class*="login"], [class*="submit"], [class*="btn"], [role="button"], a'),
                  )
                    .slice(0, 60)
                    .map((el) => {
                      const rect = (el as HTMLElement).getBoundingClientRect();
                      const text = (el.textContent || '').trim().substring(0, 10);
                      const id = (el as HTMLElement).id ? `#${(el as HTMLElement).id}` : '';
                      return `${el.tagName.toLowerCase()}${id}.${((el as HTMLElement).className || '').toString().split(' ').join('.')}:${text}:${rect.width > 0 ? 'vis' : 'hid'}:${(el as HTMLElement).offsetParent ? 'show' : 'hide'}`;
                    });
                });
                console.log(`[RouteJFlow] v31 登录候选元素(${loginCandidates.length}): ${JSON.stringify(loginCandidates)}`);
              } catch {}
              // v31 新增：dump 登录容器 outerHTML（找表单外的真实登录按钮）
              try {
                const contentHtml = await loginFrame.evaluate(() => {
                  const content = document.querySelector('div.login-content, #login, form.login-form, form');
                  if (!content) return '';
                  const wrap = (content as HTMLElement).parentElement || (content as HTMLElement);
                  return wrap.outerHTML.substring(0, 2500);
                });
                if (contentHtml) console.log(`[RouteJFlow] v31 登录容器HTML: ${contentHtml}`);
              } catch {}
              // v33：精确点击 password-login 登录按钮（v32 发现组合 locator .first() 匹配到包装 div div.fm-btn 而非 button）
              // 真实登录按钮：button.fm-button.fm-submit.password-login（文本"登录"）
              // 排除 keep-login-confirm-btn（保持登录弹窗按钮，DOM 更靠前会抢先匹配）
              let btnClicked = false;
              let clickMethod = '';
              const passwordLoginBtn = loginFrame.locator('button.fm-button.fm-submit.password-login');
              const clickLocsV33 = [
                passwordLoginBtn,
                loginFrame.locator('button:text-is("登录")'),
                loginFrame.locator('div.fm-btn:visible'),
                loginFrame.locator('.fm-button:visible'),
              ];
              for (const loc of clickLocsV33) {
                try {
                  if ((await loc.count()) === 0) continue;
                  const c = loc.first();
                  await c.scrollIntoViewIfNeeded({ timeout: 3000 }).catch(() => {});
                  try {
                    await c.click({ timeout: 5000 });
                  } catch {
                    await c.click({ timeout: 5000, force: true });
                  }
                  btnClicked = true;
                  clickMethod = `v33-${clickLocsV33.indexOf(loc)}`;
                  break;
                } catch {}
              }
              // v33：处理"保持登录"确认弹窗（若点击登录后弹出，点击"保持"按钮继续）
              try {
                await page.waitForTimeout(1500);
                const keepBtn = loginFrame.locator('button.keep-login-confirm-btn.primary, button:has-text("保持"):not(.normal)');
                if ((await keepBtn.count()) > 0 && (await keepBtn.first().isVisible().catch(() => false))) {
                  await keepBtn.first().click({ timeout: 4000, force: true }).catch(() => {});
                  console.log(`[RouteJFlow] v33 已点击保持登录弹窗"保持"`);
                }
              } catch {}
              if (!btnClicked) {
                try {
                  const pwdInput2 = loginFrame.locator('input[type="password"]').first();
                  if ((await pwdInput2.count()) > 0) {
                    await pwdInput2.press('Enter', { timeout: 5000 });
                    btnClicked = true;
                    clickMethod = 'v33-Enter';
                  }
                } catch {}
              }
              console.log(
                `[RouteJFlow] v33 登录提交: 按钮点击=${btnClicked} (${clickMethod})，等待滑块验证...`,
              );
              // v32 诊断：dump 登录按钮的绑定信息 + 点击后 2 秒的错误提示
              try {
                const btnDiag = await loginFrame.evaluate(() => {
                  const btn = document.querySelector('button.fm-button.fm-submit.password-login, button.fm-button.fm-submit, .fm-btn button, .fm-btn') as HTMLElement | null;
                  if (!btn) return { found: false };
                  const reactProps = (btn as any).__reactProps || (btn as any).__reactEventHandlers || {};
                  const reactKeys = Object.keys(reactProps).filter((k) => /on/i.test(k)).slice(0, 10);
                  const btnHtml = btn.outerHTML.substring(0, 300);
                  // 检查 form 上是否绑定了 submit/click
                  const form = document.querySelector('form#login-form') as HTMLFormElement | null;
                  const formReact = form ? (form as any).__reactProps || (form as any).__reactEventHandlers || {} : {};
                  const formReactKeys = Object.keys(formReact).filter((k) => /on/i.test(k)).slice(0, 10);
                  return {
                    found: true,
                    btnTag: btn.tagName,
                    btnClass: (btn.className || '').toString(),
                    btnText: (btn.textContent || '').trim().substring(0, 10),
                    btnDisabled: (btn as HTMLButtonElement).disabled,
                    btnOnclick: typeof (btn as any).onclick,
                    reactKeys,
                    formReactKeys,
                    btnHtml,
                  };
                });
                console.log(`[RouteJFlow] v32 登录按钮诊断: ${JSON.stringify(btnDiag)}`);
              } catch {}
              // v32：点击后等待 2 秒读取 login-error 提示（判断 handler 是否执行并给出校验/业务错误）
              await page.waitForTimeout(2000);
              try {
                const errAfter = await loginFrame.evaluate(() => {
                  const el = document.querySelector('.login-error-msg, .login-error');
                  const el2 = document.querySelector('.login-error-msg');
                  return {
                    errText: el2 ? (el2.textContent || '').trim() : '',
                    errVisible: el ? (getComputedStyle(el).display !== 'none') : false,
                  };
                });
                if (errAfter.errText) console.log(`[RouteJFlow] v32 点击后错误提示: "${errAfter.errText}" (visible=${errAfter.errVisible})`);
              } catch {}
              // v35：读取 fetch/XHR 拦截器捕获的请求（判断登录 handler 是否发起任何 AJAX）
              try {
                const reqs = await loginFrame.evaluate(() => {
                  const w = window as any;
                  return w.__routejReqs || [];
                });
                if (reqs.length > 0) {
                  console.log(`[RouteJFlow] v35 受信点击后 AJAX(${reqs.length}): ${reqs.join(' | ')}`);
                } else {
                  console.log(`[RouteJFlow] v35 受信点击后 AJAX: 无（登录 handler 未发起任何请求）`);
                }
              } catch {}
              // v35：JS 合成点击对比（Playwright 受信点击 vs el.click() 合成点击）
              try {
                const jsClicked = await loginFrame.evaluate(() => {
                  const btn = document.querySelector('button.fm-button.fm-submit.password-login') as HTMLElement | null;
                  if (!btn) return 'no_btn';
                  try {
                    btn.click();
                    return 'clicked';
                  } catch (e) {
                    return `error: ${String(e).substring(0, 80)}`;
                  }
                });
                console.log(`[RouteJFlow] v35 JS 合成点击: ${jsClicked}`);
                await page.waitForTimeout(2000);
                const reqs2 = await loginFrame.evaluate(() => {
                  const w = window as any;
                  return w.__routejReqs || [];
                });
                console.log(`[RouteJFlow] v35 JS 点击后 AJAX(${reqs2.length}): ${reqs2.join(' | ')}`);
              } catch {}
              // v36：若点击未触发导航，用 requestSubmit 触发原生 GET 表单提交（v28 证明有效）
              // v35 确认：password-login 按钮在 form 外且无提交 handler，点击只触发 QR 轮询
              // v28 证据：requestSubmit → GET mini_login.htm?fm-login-id=...&fm-login-password=... 返回 200
              // 服务器处理登录尝试后重渲染页面（可能显示错误或激活 NC 滑块）
              // v28 在提交后未检查重载页面状态就中断，v36 提交后让轮询检查新页面
              try {
                const submitted36 = await loginFrame.evaluate(() => {
                  const form = document.querySelector('form#login-form, form.login-form, form');
                  if (form && typeof (form as HTMLFormElement).requestSubmit === 'function') {
                    (form as HTMLFormElement).requestSubmit();
                    return true;
                  }
                  return false;
                });
                console.log(`[RouteJFlow] v36 requestSubmit 原生提交: ${submitted36}，等待导航完成...`);
              } catch (e: any) {
                console.log(`[RouteJFlow] v36 requestSubmit 异常: ${e?.message?.substring(0, 80)}`);
              }
            } catch (e: any) {
              console.log(`[RouteJFlow] v26 iframe 表单操作异常: ${e?.message?.substring(0, 120)}`);
            }
            // v28：监听器保持到 iframe 流程结束（延迟响应也能捕获），页面关闭时自动清理

            // v33 新增：可复用的登录按钮受信点击（升级风控触发 NC）——精确 password-login 按钮
            const clickLoginButton = async (): Promise<boolean> => {
              const clickLocs = [
                loginFrame.locator('button.fm-button.fm-submit.password-login'),
                loginFrame.locator('button:text-is("登录")'),
                loginFrame.locator('div.fm-btn:visible'),
                loginFrame.locator('button[type="submit"]:visible, .fm-button:visible, [class*="login-btn"]:visible, [class*="submit"]:visible'),
              ];
              for (const loc of clickLocs) {
                try {
                  if ((await loc.count()) === 0) continue;
                  const c = loc.first();
                  await c.scrollIntoViewIfNeeded({ timeout: 3000 }).catch(() => {});
                  try {
                    await c.click({ timeout: 4000 });
                  } catch {
                    await c.click({ timeout: 4000, force: true });
                  }
                  return true;
                } catch {}
              }
              return false;
            };

            // v28 新增：轮询滑块出现，每轮先尝试 init + NC.show() 激活 NC widget
            // 关键发现（v27）：iframe 内 baxiaCommon.NC.show 是函数但内部报 "Cannot read properties of null"
            // 说明 NC widget 未初始化（需服务端下发验证需求才初始化），v28 每轮 init 后再 show
            let iframeSlider: { x?: number; y?: number; width?: number; height?: number; notVisible?: boolean } | null = null;
            let lastNcShowStatus = '';
            let escalateClicks = 0;
            for (let poll = 0; poll < 8; poll++) {
              await page.waitForTimeout(1500);
              // v34：poll 0 记录 iframe URL（确认原生 GET 提交是否导航/重载）
              if (poll === 0) {
                try {
                  const frameUrl = loginFrame.url();
                  const hasCred = /fm-login-id|fm-login-password/.test(frameUrl);
                  console.log(`[RouteJFlow] v34 iframe URL 含登录凭据=${hasCred}: ${frameUrl.substring(0, 120)}`);
                } catch {}
              }
              // v29 升级：轮询第 3 轮和第 6 轮若滑块未出现，再次点击登录按钮升级风控
              if (poll === 2 || poll === 5) {
                const reClicked = await clickLoginButton().catch(() => false);
                if (reClicked) {
                  escalateClicks++;
                  console.log(`[RouteJFlow] v34 再次点击登录按钮升级风控（第 ${escalateClicks} 次）`);
                }
              }
              // v36：每轮读取登录错误提示 + URL（诊断原生 GET 提交后服务器的响应）
              try {
                const loginErrText = await loginFrame.evaluate(() => {
                  const el = document.querySelector('.login-error-msg, .login-error');
                  return el ? (el.textContent || '').trim() : '';
                });
                if (loginErrText) console.log(`[RouteJFlow] v36 轮询${poll} 登录提示: "${loginErrText}"`);
              } catch {}
              try {
                const pollUrl = loginFrame.url();
                if (/fm-login-id|fm-login-password/.test(pollUrl)) {
                  console.log(`[RouteJFlow] v36 轮询${poll} URL 含凭据（原生提交已发生）`);
                }
              } catch {}
              // v28：每轮尝试 init + NC.show() 激活 NC widget（v15 逻辑：init 后等待 1.2s 再 show）
              try {
                lastNcShowStatus = await loginFrame.evaluate(async () => {
                  const bc: any = (window as any).baxiaCommon;
                  if (!bc) return 'no_baxiaCommon';
                  try {
                    if (typeof bc.init === 'function') {
                      try {
                        bc.init({ needUmidToken: true });
                      } catch (e) {}
                      await new Promise((r) => setTimeout(r, 1200));
                    }
                  } catch {}
                  const nc = bc.NC;
                  if (nc && typeof nc.show === 'function') {
                    try {
                      nc.show();
                      return 'show_called';
                    } catch (e) {
                      return `show_error: ${String(e).substring(0, 80)}`;
                    }
                  }
                  return `no_nc type=${typeof nc}`;
                });
              } catch (e: any) {
                lastNcShowStatus = `evaluate_error: ${String(e?.message).substring(0, 60)}`;
              }
              if (poll === 0) console.log(`[RouteJFlow] v28 iframe NC init+show(): ${lastNcShowStatus}`);
              // v28 兜底：手动显示 iframe 内 NC 滑块容器
              try {
                await loginFrame.evaluate(() => {
                  const wrapper = document.querySelector('.nc_wrapper, [class*="nc_wrapper"]') as HTMLElement | null;
                  if (wrapper) {
                    wrapper.style.display = 'block';
                    wrapper.style.visibility = 'visible';
                    wrapper.className = wrapper.className.split(/\s+/).filter((c) => !/hide|hidden|none/i.test(c)).join(' ');
                  }
                  const scale = document.querySelector('.nc_scale, [class*="nc_scale"]') as HTMLElement | null;
                  if (scale) {
                    scale.style.display = 'block';
                    scale.style.visibility = 'visible';
                  }
                  const btn = document.querySelector('.btn_slide, [class*="btn_slide"]') as HTMLElement | null;
                  if (btn) {
                    (btn as HTMLElement).style.display = 'block';
                  }
                });
              } catch {}
              // 完整可见性检测（宽度/高度/display/visibility/offsetParent）
              iframeSlider = await loginFrame.evaluate((): { x?: number; y?: number; width?: number; height?: number; notVisible?: boolean } | null => {
                const scale = document.querySelector('.nc_scale, [class*="nc_scale"]') as HTMLElement | null;
                if (!scale) return null;
                const r = scale.getBoundingClientRect();
                const visible =
                  r.width > 0 &&
                  r.height > 0 &&
                  scale.offsetParent !== null &&
                  getComputedStyle(scale).visibility !== 'hidden' &&
                  getComputedStyle(scale).display !== 'none';
                if (!visible) return { notVisible: true, width: r.width };
                return { x: r.x, y: r.y, width: r.width, height: r.height };
              });
              if (iframeSlider && iframeSlider.x !== undefined) {
                console.log(`[RouteJFlow] v28 滑块出现（轮询 ${poll + 1} 次）: ${JSON.stringify(iframeSlider)}`);
                break;
              }
            }
            if (!iframeSlider || iframeSlider.x === undefined) {
              console.log(`[RouteJFlow] v28 iframe 滑块: 未出现（NC=${lastNcShowStatus} 升级点击=${escalateClicks}）`);
            }
            // v28：输出 iframe 登录相关网络请求（诊断登录提交是否到达服务端）
            if (loginFrameRequests.length > 0 || loginFrameResponses.length > 0) {
              console.log(`[RouteJFlow] v28 iframe 登录请求(${loginFrameRequests.length}): ${loginFrameRequests.join(' | ')}`);
              console.log(`[RouteJFlow] v28 iframe 登录响应(${loginFrameResponses.length}): ${loginFrameResponses.join(' | ')}`);
            } else {
              console.log(`[RouteJFlow] v28 iframe 登录请求: 无（提交未到达服务端或 URL 不匹配）`);
            }
            // v37 新增：密码登录路径确认受阻后，尝试短信登录 + 获取验证码
            // 原理：sendCode（获取短信验证码）流程通常先触发 NC 滑块防滥用，是登录页最后未试的 NC 触发点
            if (!iframeSlider || iframeSlider.x === undefined) {
              try {
                console.log(`[RouteJFlow] v37 切换到短信登录流程...`);
                const smsTab = loginFrame.locator('a.sms-login-tab-item').first();
                if ((await smsTab.count()) > 0) {
                  await smsTab.click({ timeout: 5000, force: true });
                  await page.waitForTimeout(800);
                }
                // 填手机号
                const smsPhone = loginFrame
                  .locator('input[placeholder*="手机"], input[name*="sms"], input[type="tel"], input[name="fm-login-id"]')
                  .first();
                if ((await smsPhone.count()) > 0) {
                  await smsPhone.fill('13800138001', { timeout: 8000 });
                  console.log(`[RouteJFlow] v37 短信视图已填手机号`);
                }
                // dump 短信视图按钮
                try {
                  const smsCands = await loginFrame.evaluate(() => {
                    return Array.from(document.querySelectorAll('button, a, [class*="btn"], [class*="code"], [class*="send"]'))
                      .slice(0, 20)
                      .map((el) => {
                        const r = (el as HTMLElement).getBoundingClientRect();
                        return `${el.tagName.toLowerCase()}.${((el as HTMLElement).className || '').toString().split(' ').join('.')}:${(el.textContent || '').trim().substring(0, 12)}:${r.width > 0 ? 'vis' : 'hid'}`;
                      });
                  });
                  console.log(`[RouteJFlow] v37 短信视图候选: ${JSON.stringify(smsCands)}`);
                } catch {}
                // 点击"获取验证码"或"登录"按钮
                const smsBtn = loginFrame
                  .locator('button:has-text("验证码"), a:has-text("验证码"), button:has-text("获取"), button:has-text("登录"), .fm-button:visible')
                  .first();
                if ((await smsBtn.count()) > 0) {
                  await smsBtn.click({ timeout: 5000, force: true }).catch(() => {});
                  console.log(`[RouteJFlow] v37 已点击短信视图按钮`);
                }
                // 轮询滑块 4 次
                for (let sp = 0; sp < 4; sp++) {
                  await page.waitForTimeout(1500);
                  const sSlider = await loginFrame.evaluate(() => {
                    const scale = document.querySelector('.nc_scale, [class*="nc_scale"]') as HTMLElement | null;
                    if (!scale) return null;
                    const r = scale.getBoundingClientRect();
                    const visible =
                      r.width > 0 && r.height > 0 && scale.offsetParent !== null &&
                      getComputedStyle(scale).visibility !== 'hidden' && getComputedStyle(scale).display !== 'none';
                    if (!visible) return { notVisible: true, width: r.width };
                    return { x: r.x, y: r.y, width: r.width, height: r.height };
                  });
                  if (sSlider && sSlider.x !== undefined) {
                    console.log(`[RouteJFlow] v37 短信流程滑块出现（轮询 ${sp + 1}）: ${JSON.stringify(sSlider)}`);
                    iframeSlider = sSlider;
                    break;
                  }
                }
                if (!iframeSlider || iframeSlider.x === undefined) {
                  console.log(`[RouteJFlow] v37 短信流程滑块: 未出现`);
                }
              } catch (e: any) {
                console.log(`[RouteJFlow] v37 短信流程异常: ${e?.message?.substring(0, 100)}`);
              }
            }
            if (iframeSlider && iframeSlider.x !== undefined) {
              // v27：用 Playwright locator boundingBox 获取相对主框架坐标（自动处理 iframe 偏移）
              let dragBox: { x: number; y: number; width: number; height: number } | null = null;
              try {
                const scaleLoc = loginFrame.locator('.nc_scale').first();
                dragBox = await scaleLoc.boundingBox();
              } catch {}
              const b = {
                x: dragBox ? dragBox.x : iframeSlider.x as number,
                y: dragBox ? dragBox.y : (iframeSlider.y || 0),
                width: dragBox ? dragBox.width : (iframeSlider.width || 260),
                height: dragBox ? dragBox.height : (iframeSlider.height || 40),
              };
              const startX = b.x + 20;
              const startY = (b.y || 0) + (b.height || 40) / 2;
              const endX = b.x + (b.width || 260) - 20;
              console.log(`[RouteJFlow] v28 拖动 iframe 滑块 ${startX.toFixed(0)} -> ${endX.toFixed(0)}`);
              await page.mouse.move(startX, startY, { steps: 5 });
              await page.waitForTimeout(200);
              await page.mouse.down();
              await page.waitForTimeout(100);
              const steps = 15 + Math.floor(Math.random() * 8);
              for (let i = 1; i <= steps; i++) {
                const p = i / steps;
                const eased = p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
                await page.mouse.move(startX + (endX - startX) * eased, startY, { steps: 2 });
                await page.waitForTimeout(20 + Math.random() * 40);
              }
              await page.waitForTimeout(150);
              await page.mouse.up();
              console.log(`[RouteJFlow] v28 iframe 滑块拖动完成`);
              // 等待 analyze 触发
              await page.waitForTimeout(5000);
            }
          } else {
            console.log(`[RouteJFlow] v23 未找到登录 iframe（frames=${frames.length}）`);
          }
        } catch (e: any) {
          console.log(`[RouteJFlow] v23 iframe 操作异常: ${e?.message}`);
        }

        // 再次检查被动捕获结果（v23 iframe 操作后）
        if (passiveCapture.x5secFromSetCookie) {
          result.x5sec = passiveCapture.x5secFromSetCookie;
          result.x5secSource = 'home_nc_set_cookie';
          result.ok = true;
          console.log(`[RouteJFlow] ✓✓✓ v23 iframe 流程 Set-Cookie 下发 x5sec 长度=${result.x5sec.length}`);
        } else if (passiveCapture.analyzeCode === 0 && passiveCapture.analyzeSig && passiveCapture.analyzeCsessionid) {
          const realAppkey = passiveCapture.realAppkey || 'CF_APP_TBLogin_PC';
          const x5secdata = `${realAppkey}=${passiveCapture.analyzeSig}=${passiveCapture.analyzeCsessionid}`;
          result.x5sec = x5secdata;
          result.x5secSource = 'home_nc_constructed_from_sig';
          result.ok = true;
          result.analyzeResultCode = 0;
          result.analyzeSig = passiveCapture.analyzeSig;
          result.analyzeCsessionid = passiveCapture.analyzeCsessionid;
          console.log(`[RouteJFlow] ✓✓✓ v23 iframe analyze code=0 构造 x5secdata 长度=${x5secdata.length}`);
        }
      } catch (e: any) {
        console.log(`[RouteJFlow] v18 首页 NC.show 异常: ${e?.message}`);
      }

      // 5.5 v6 新增：等待 FireyeJS 自动调用 um.json（init 后 um.js 会自动请求）
      // 关键发现：FireyeJS 的 init() 会触发 um.js 自动调用 um.json，
      // 设置 umt cookie。我们不需要手动构造 um.json 请求。
      // 等待 2 秒让 um.js 完成自动请求
      console.log(`[RouteJFlow] 等待 FireyeJS 自动初始化（um.json）...`);
      await page.waitForTimeout(2000);

      // 检查浏览器 cookie 中是否已有 umt（FireyeJS 自动设置）
      const autoUmt = await page.evaluate(() => {
        const m = document.cookie.match(/umt=([^;]+)/);
        return m ? m[1] : '';
      });
      if (autoUmt) {
        console.log(`[RouteJFlow] ✓ FireyeJS 自动设置了 umt cookie 长度=${autoUmt.length}`);
        result.umtCookie = autoUmt;
        result.umJsonStatus = 200;
        result.umJsonResponse = '{"id":"auto_set_by_fireyejs"}';
      } else if (passiveCapture.umtFromSetCookie) {
        // v7 新增：优先使用被动捕获的 umt（从 um.json Set-Cookie 头提取）
        console.log(`[RouteJFlow] ✓ 被动捕获到 umt cookie 长度=${passiveCapture.umtFromSetCookie.length}`);
        result.umtCookie = passiveCapture.umtFromSetCookie;
        result.umJsonStatus = 200;
        result.umJsonResponse = passiveCapture.umJsonResponseText || '{"id":"passive_capture"}';
      } else if (passiveCapture.umTn) {
        // v8 新增：um.json 响应体有 tn 字段但没有 Set-Cookie umt
        // 关键发现：页面自己调用 um.json 返回 {"tn":"...","id":"..."}（非空）
        // 但 Set-Cookie 中没有 umt。um.js 可能通过 JS document.cookie 设置 umt=tn
        // 这里手动将 tn 注入为 umt cookie
        console.log(`[RouteJFlow] v8 注入 tn 为 umt cookie 长度=${passiveCapture.umTn.length}`);
        await page.evaluate((tn) => {
          // 设置 umt cookie，domain=.aliapp.org 以便 ynuf.aliapp.org 和 cf.aliyun.com 都能读到
          document.cookie = `umt=${tn}; path=/; domain=.aliyun.com`;
          document.cookie = `umt=${tn}; path=/; domain=.aliapp.org`;
          document.cookie = `umt=${tn}; path=/`;
        }, passiveCapture.umTn);
        result.umtCookie = passiveCapture.umTn;
        result.umJsonStatus = 200;
        result.umJsonResponse = passiveCapture.umJsonResponseText || '{"id":"passive_tn"}';
        // 等待 500ms 让 cookie 生效
        await page.waitForTimeout(500);
      } else {
        console.log(`[RouteJFlow] FireyeJS 未自动设置 umt，将手动调用 um.json`);
      }

      // v7 新增：被动模式优先检查 —— 如果页面已经自己完成 NC 流程并拿到 x5sec，直接返回
      if (passiveCapture.x5secFromSetCookie) {
        result.x5sec = passiveCapture.x5secFromSetCookie;
        result.x5secSource = 'passive_set_cookie';
        result.ok = true;
        result.durationMs = Date.now() - t0;
        console.log(`[RouteJFlow] ✓✓✓ v7 被动模式成功：从 Set-Cookie 提取 x5sec 长度=${result.x5sec.length}`);
        // 仍提取 FYToken 供调用方使用
        try {
          result.fyToken = await Promise.race([
            extractFYToken(page, debug),
            new Promise<string>((_, reject) =>
              setTimeout(() => reject(new Error('extractFYToken 10秒超时')), 10000),
            ),
          ]);
        } catch (e: any) {
          console.warn(`[RouteJFlow] 被动模式下 getFYToken 失败（不影响 x5sec）: ${e?.message}`);
        }
        // 收集浏览器最终 cookie
        const cookiesV7 = await context.cookies();
        result.finalCookies = cookiesV7
          .filter((c) => c.domain.includes('goofish') || c.domain.includes('aliyun') || c.domain.includes('aliapp'))
          .map((c) => `${c.name}=${c.value}`)
          .join('; ');
        return result;
      }

      // v7 新增：如果被动捕获到 analyze 的 sig + csessionid（code=0），直接构造 x5secdata
      if (passiveCapture.analyzeCode === 0 && passiveCapture.analyzeSig && passiveCapture.analyzeCsessionid) {
        const realAppkey = passiveCapture.realAppkey || 'CF_APP_TBLogin_PC';
        const x5secdata = `${realAppkey}=${passiveCapture.analyzeSig}=${passiveCapture.analyzeCsessionid}`;
        result.x5sec = x5secdata;
        result.x5secSource = 'passive_constructed_from_sig';
        result.ok = true;
        result.analyzeResultCode = passiveCapture.analyzeCode;
        result.analyzeSig = passiveCapture.analyzeSig;
        result.analyzeCsessionid = passiveCapture.analyzeCsessionid;
        result.analyzeResponse = passiveCapture.analyzeResponseText.substring(0, 500);
        result.durationMs = Date.now() - t0;
        console.log(`[RouteJFlow] ✓✓✓ v7 被动模式成功：基于拦截到的 sig 构造 x5secdata 长度=${x5secdata.length} appkey=${realAppkey}`);
        try {
          result.fyToken = await Promise.race([
            extractFYToken(page, debug),
            new Promise<string>((_, reject) =>
              setTimeout(() => reject(new Error('extractFYToken 10秒超时')), 10000),
            ),
          ]);
        } catch (e: any) {
          console.warn(`[RouteJFlow] 被动模式下 getFYToken 失败（不影响 x5sec）: ${e?.message}`);
        }
        const cookiesV7b = await context.cookies();
        result.finalCookies = cookiesV7b
          .filter((c) => c.domain.includes('goofish') || c.domain.includes('aliyun') || c.domain.includes('aliapp'))
          .map((c) => `${c.name}=${c.value}`)
          .join('; ');
        return result;
      }

      // v7 诊断：输出被动捕获到的请求（用于排查页面是否自己跑了 NC）
      if (debug) {
        console.log(`[RouteJFlow] v7 被动捕获状态: captured=${passiveCapture.capturedUrls.length} appkey=${passiveCapture.realAppkey || '无'} ncToken长度=${passiveCapture.realNcToken.length} analyzeCode=${passiveCapture.analyzeCode} sig长度=${passiveCapture.analyzeSig.length} umt长度=${passiveCapture.umtFromSetCookie.length} tn长度=${passiveCapture.umTn.length} id长度=${passiveCapture.umId.length}`);
        if (passiveCapture.capturedUrls.length > 0) {
          console.log(`[RouteJFlow] v7 捕获的请求: ${passiveCapture.capturedUrls.join(', ')}`);
        }
      }

      // 6. 提取 FYToken + umidToken
      console.log(`[RouteJFlow] 提取 FYToken...`);
      try {
        result.fyToken = await Promise.race([
          extractFYToken(page, debug),
          new Promise<string>((_, reject) =>
            setTimeout(() => reject(new Error('extractFYToken 15秒超时')), 15000),
          ),
        ]);
      } catch (e: any) {
        result.error = `getFYToken 失败: ${e?.message || e}`;
        result.durationMs = Date.now() - t0;
        return result;
      }

      console.log(`[RouteJFlow] 提取 umidToken...`);
      try {
        result.umidToken = await extractUmidToken(page, debug);
      } catch (e: any) {
        console.warn(`[RouteJFlow] getUidToken 失败: ${e?.message || e}`);
      }

      console.log(
        `[RouteJFlow] ✓ FireyeJS token 获取成功 fyToken长度=${result.fyToken.length} umidToken长度=${result.umidToken.length}`,
      );

      // 7. 浏览器内调用 um.json（v6 优化：如果 FireyeJS 已自动设置 umt，跳过手动调用）
      if (!result.umtCookie) {
        console.log(`[RouteJFlow] 浏览器内调用 um.json...`);
        const umResult = await callUmJsonInBrowser(
          page,
          result.fyToken,
          result.umidToken,
        );
        result.umJsonStatus = umResult.status;
        result.umJsonResponse = umResult.responseText.substring(0, 500);
        result.umtCookie = umResult.umtCookie;

        console.log(
          `[RouteJFlow] um.json status=${umResult.status} response长度=${umResult.responseText.length} umt=${umResult.umtCookie ? '✓' : '✗'} cna=${umResult.cnaCookie ? '✓' : '✗'}`,
        );
        if (debug) {
          console.log(`[RouteJFlow] um.json 响应: ${umResult.responseText.substring(0, 200)}`);
        }
      } else {
        console.log(`[RouteJFlow] ✓ 跳过手动 um.json（FireyeJS 已自动设置 umt）`);
      }

      // 8. 浏览器内调用 initialize.jsonp
      // v7 优化：优先使用被动捕获的真实 appkey（页面用 CF_APP_TBLogin_PC 成功）
      const activeAppkey = passiveCapture.realAppkey || 'XFFXFXFF';
      // v9 优化：使用被动捕获的真实 version（页面实际加载的 NC 库版本）
      const activeNcVersion = passiveCapture.initVersion || '1.97.0';
      // v9：填充调试字段
      result.initFullUrl = passiveCapture.initFullUrl;
      result.analyzeFullUrl = passiveCapture.analyzeFullUrl;
      result.realNcVersion = passiveCapture.initVersion;
      result.realNcHref = passiveCapture.initHref;
      result.passiveUmTn = passiveCapture.umTn;
      result.passiveUmId = passiveCapture.umId;
      // v7 优化：如果被动捕获到 ncToken，直接复用，跳过主动 initialize
      if (passiveCapture.realNcToken) {
        console.log(`[RouteJFlow] ✓ v10 复用被动捕获的 ncToken 长度=${passiveCapture.realNcToken.length} 前缀=${passiveCapture.realNcToken.substring(0, 12)}，跳过主动 initialize`);
        result.initStatus = 200;
        result.initResponse = passiveCapture.initResponseText.substring(0, 500);
        result.ncToken = passiveCapture.realNcToken;
      } else {
        // v9 优化：优先 replay 被动捕获的完整 URL（含真实 href/version 等参数）
        const initReplayUrl = passiveCapture.initFullUrl || undefined;
        console.log(`[RouteJFlow] 浏览器内调用 initialize.jsonp appkey=${activeAppkey} version=${activeNcVersion} replay=${initReplayUrl ? '是' : '否'}...`);
        const initResult = await callInitializeJsonpInBrowser(page, activeAppkey, initReplayUrl, activeNcVersion, passiveCapture.initHref || undefined);
        result.initStatus = initResult.status;
        result.initResponse = initResult.responseText.substring(0, 500);
        result.ncToken = initResult.token;
        result.initUsedUrl = initResult.usedUrl;

        console.log(
          `[RouteJFlow] initialize.jsonp status=${initResult.status} token长度=${initResult.token.length}`,
        );
        if (debug) {
          console.log(`[RouteJFlow] initialize.jsonp usedUrl: ${initResult.usedUrl}`);
          console.log(`[RouteJFlow] initialize.jsonp 完整响应: ${initResult.responseText}`);
        }
      }

      // 9. 浏览器内调用 analyze.jsonp
      // v10 核心修复：t 参数必须用页面生成的 ncToken（从 URL t 参数提取），
      // 而不是 1a3btest 占位符（占位符导致 code=300 block）
      console.log(`[RouteJFlow] 浏览器内调用 analyze.jsonp appkey=${activeAppkey} version=${activeNcVersion} token来源=${result.ncToken ? 'ncToken' : passiveCapture.realNcToken ? 'realNcToken' : '占位符'}...`);
      const tokenForAnalyze = result.ncToken || passiveCapture.realNcToken || '1a3btest';
      if (tokenForAnalyze === '1a3btest') {
        console.warn(`[RouteJFlow] ⚠ 使用占位符 t=1a3btest（未捕获到真实 ncToken，analyze 很可能失败）`);
      } else {
        console.log(`[RouteJFlow] ✓ analyze t 参数前缀=${tokenForAnalyze.substring(0, 12)}`);
      }
      const analyzeResult = await callAnalyzeJsonpInBrowser(
        page,
        activeAppkey,
        tokenForAnalyze,
        result.fyToken,
        activeNcVersion,
        passiveCapture.initHref || undefined,
      );
      result.analyzeStatus = analyzeResult.status;
      result.analyzeResponse = analyzeResult.responseText.substring(0, 500);
      result.analyzeResultCode = analyzeResult.resultCode;
      result.analyzeSig = analyzeResult.resultValue;
      result.analyzeCsessionid = analyzeResult.resultCsessionid;
      result.analyzeUsedUrl = analyzeResult.usedUrl;

      console.log(
        `[RouteJFlow] analyze.jsonp status=${analyzeResult.status} code=${analyzeResult.resultCode} sig长度=${analyzeResult.resultValue.length} csessionid长度=${analyzeResult.resultCsessionid.length} x5secInCookie=${analyzeResult.x5secInCookie ? '✓' : '✗'}`,
      );
      if (debug) {
        console.log(`[RouteJFlow] analyze.jsonp usedUrl: ${analyzeResult.usedUrl}`);
        console.log(`[RouteJFlow] analyze.jsonp 完整响应: ${analyzeResult.responseText}`);
      }

      // 10. 提取 x5sec
      // 10.1 优先：analyze.jsonp 后浏览器 cookie 中的 x5sec
      if (analyzeResult.x5secInCookie) {
        result.x5sec = analyzeResult.x5secInCookie;
        result.x5secSource = 'analyze_browser_cookie';
        result.ok = true;
        console.log(`[RouteJFlow] ✓ 从浏览器 cookie 提取到 x5sec 长度=${result.x5sec.length}`);
      }

      // 10.2 次选：基于 sig 构造 x5secdata（v7：使用真实 appkey）
      if (!result.ok && analyzeResult.resultValue && analyzeResult.resultCode === 0) {
        const x5secdata = `${activeAppkey}=${analyzeResult.resultValue}=${analyzeResult.resultCsessionid}`;
        result.x5sec = x5secdata;
        result.x5secSource = 'constructed_from_sig';
        result.ok = true;
        console.log(`[RouteJFlow] ✓ 基于 sig 构造 x5secdata 长度=${x5secdata.length} appkey=${activeAppkey}`);
      }

      // 10.3 v11 新增：主动 analyze 失败时，导航登录页触发页面自身 NC 流程
      // 页面自己调用 analyze.jsonp 会生成真实行为数据 p 参数（我们的构造 p 参数被 block）
      // 触发方式：点击登录按钮，让页面弹出验证并自动调 analyze
      if (!result.ok) {
        console.log(`[RouteJFlow] v11 主动 analyze 失败（code=${result.analyzeResultCode}），尝试登录页触发页面自身 NC...`);
        const loginResult = await triggerLoginPageNcFlow(context, debug);

        // 从登录页被动捕获中提取结果
        if (loginResult.x5secFromSetCookie) {
          result.x5sec = loginResult.x5secFromSetCookie;
          result.x5secSource = 'login_page_set_cookie';
          result.ok = true;
          console.log(`[RouteJFlow] ✓✓✓ v11 登录页 Set-Cookie 下发 x5sec 长度=${result.x5sec.length}`);
        } else if (loginResult.analyzeCode === 0 && loginResult.analyzeSig && loginResult.analyzeCsessionid) {
          const realAppkey = passiveCapture.realAppkey || 'CF_APP_TBLogin_PC';
          const x5secdata = `${realAppkey}=${loginResult.analyzeSig}=${loginResult.analyzeCsessionid}`;
          result.x5sec = x5secdata;
          result.x5secSource = 'login_page_constructed_from_sig';
          result.ok = true;
          result.analyzeResultCode = 0;
          result.analyzeSig = loginResult.analyzeSig;
          result.analyzeCsessionid = loginResult.analyzeCsessionid;
          console.log(`[RouteJFlow] ✓✓✓ v11 登录页 analyze code=0 构造 x5secdata 长度=${x5secdata.length}`);
        } else {
          console.log(`[RouteJFlow] v11 登录页未触发成功 analyze=${loginResult.analyzeCode} 页面诊断=${loginResult.pageDiagnostics.substring(0, 200)}`);
        }
      }

      // 11. 收集浏览器最终的所有 cookie
      const cookies = await context.cookies();
      const cookieStr = cookies
        .filter((c) => c.domain.includes('goofish') || c.domain.includes('aliyun') || c.domain.includes('aliapp'))
        .map((c) => `${c.name}=${c.value}`)
        .join('; ');
      result.finalCookies = cookieStr;

      if (!result.ok) {
        const errorParts: string[] = [];
        if (result.analyzeResultCode !== null && result.analyzeResultCode !== 0) {
          errorParts.push(`analyze.jsonp result.code=${result.analyzeResultCode}`);
        }
        if (!result.analyzeSig) {
          errorParts.push('analyze.jsonp 未返回 sig');
        }
        if (result.umJsonStatus !== 200) {
          errorParts.push(`um.json status=${result.umJsonStatus}`);
        }
        result.error = errorParts.join('；') || '路线 J 流程未成功';
      }

      result.durationMs = Date.now() - t0;
      console.log(
        `[RouteJFlow] ${result.ok ? '✓✓✓ 成功' : '✗ 失败'} 总耗时=${result.durationMs}ms x5sec来源=${result.x5secSource || '无'}`,
      );

      return result;
    } finally {
      try {
        await page.close();
      } catch {
        // 忽略关闭错误
      }
    }
  } catch (e: any) {
    const durationMs = Date.now() - t0;
    result.error = e?.message || String(e);
    result.durationMs = durationMs;
    console.error(`[RouteJFlow] ✗ 异常: ${result.error} 耗时=${durationMs}ms`);
    return result;
  } finally {
    try {
      if (context) await context.close();
    } catch {}
    try {
      if (browser) await browser.close();
    } catch {}
    if (sessionId) {
      try {
        processRegistry.unregister(sessionId);
      } catch {}
    }
    if (userDataDir) {
      try {
        await fs.rm(userDataDir, { recursive: true, force: true });
      } catch {}
    }
  }
}
