import express, { type NextFunction, type Request, type Response } from 'express';
import cors from 'cors';
import crypto from 'crypto';
import { spawn } from 'child_process';
import path from 'path';
import os from 'os';
import fs from 'fs';
import type { Browser, BrowserContext, Page } from 'playwright';
import { parseGoofishStoreUrl } from './crawler/parseGoofishStoreUrl.js';
import { closeQueue, goofishCrawlQueue } from './queue/index.js';
import { assertQueueCookieEncryptionReady, encryptQueueCookie } from './queue/secretEnvelope.js';
import { closePool, getPool, runMigrations } from './db/index.js';
import { crawlGoofishSearch } from './crawler/goofishSearch.js';
import { fetchGoofishItemDetail } from './crawler/goofishItemDetail.js';
import { resolveStoreUserId } from './crawler/goofish.js';
import { solveGoofishSlider, isHeadedDisplayAvailable, type SlideSolveResult } from './crawler/sliderSolver.js';
import { captureQrCodeOnly, completeQrLoginSession } from './crawler/qrLoginSolver.js';
import { processRegistry, processMonitor } from './crawler/processRegistry.js';
import { cacheX5sec, getCachedX5sec, evictCachedX5sec, injectX5secIntoCookie, cookieHasX5sec, closeX5secCache } from './x5secCache.js';
import {
  isCorsOriginAllowed,
  isProductionLike,
  normalizeCookieInput,
  normalizeGoofishTargetUrl,
  normalizeTenantId,
  parseSearchInput,
  areProductionCorsOriginsSafe,
  resolveInternalTokenPolicy,
  resolveRedisPasswordPolicy,
  safeErrorType,
  toPublicCrawlerError,
} from './policy.js';

// ============================================================
// Python patchright 滑块求解 fallback
// ============================================================
// 2026-08-01 优化：Playwright 的 CDP 鼠标事件被 Baxia FireyeJS 识别为机器人
// （拖动后立即出现 .errloading），即使轨迹模拟再像真人也无法通过。
// patchright 是 Playwright 的反检测分支，自动清理 CDP 痕迹（cdc_/__playwright__/Runtime.enable），
// 从根本上解决 Baxia 通过 CDP 协议识别 Playwright 控制的问题。
//
// 策略：当 Playwright 求解失败且失败原因是 slider_fail（非 cookie_invalid）时，
// 调用 Python sliderSolve.py 重试。Python 有独立的 120s 超时。
const PYTHON_SOLVER_SCRIPT = process.env.PYTHON_SOLVER_SCRIPT || '/app/sliderSolve.py';
const PYTHON_BINARY = process.env.PYTHON_BINARY || 'python3';
// 2026-08-01 优化：Python fallback 超时从 120s 增加到 155s
// 原因：Playwright 超时从 50s 降到 10s，Python fallback 获得更多时间。
//       实测 Python 脚本启动+Chrome启动+导航+检测滑块需要约 30-40s，
//       155s 给拖动阶段留 100s+（足够 2 次拖动+验证+冷却）。
// 总时间预算：Playwright 10s + Python 155s = 165s（在 170s 整体超时以内）
const PYTHON_FALLBACK_TIMEOUT_MS = 155_000;  // 155 秒（Python 独立超时）

// 2026-08-01 优化：Python fallback 全局并发控制
// 2026-08-01 二次优化：移除全局锁，允许 2 个并发（匹配 SOLVE_WORKER_CONCURRENCY=2）
// 原因：全局锁导致第二个请求直接失败，6 个活跃账号只有 1 个能求解。
//       服务器有 16GB 内存，完全支持 2 个 Chrome 进程并行。
//       Python 脚本的 _FileLock 已移除（每个进程用独立 temp 目录，不冲突）。
let pythonFallbackRunning = 0;  // 当前运行的 Python fallback 数量
const MAX_PYTHON_FALLBACK_CONCURRENCY = 2;  // 最大并发数

interface PythonSolveResult {
  ok: boolean;
  solved: boolean;
  captchaDetected: boolean;
  attempts: number;
  error?: string;
  durationMs: number;
  cookies?: string;
  x5sec?: string;
}

async function solveWithPythonPatchright(params: {
  cookieStr: string;
  targetUrl?: string;
  proxy?: { server: string; username?: string; password?: string };
  maxRetries?: number;
}): Promise<PythonSolveResult> {
  const startTime = Date.now();
  const { cookieStr, targetUrl, proxy, maxRetries } = params;

  // 2026-08-01 优化：允许 2 个 Python fallback 并发（原全局锁已移除）
  // 原因：全局锁导致第二个请求直接失败，6 个活跃账号只有 1 个能求解。
  //       服务器有 16GB 内存，完全支持 2 个 Chrome 进程并行。
  if (pythonFallbackRunning >= MAX_PYTHON_FALLBACK_CONCURRENCY) {
    console.log(`[SliderSolver-Python] 已有 ${pythonFallbackRunning} 个 Python fallback 在运行，跳过本次（避免资源耗尽）`);
    return {
      ok: false, solved: false, captchaDetected: false, attempts: 0,
      error: `Python fallback 已有 ${pythonFallbackRunning} 个实例在运行，跳过本次`,
      durationMs: Date.now() - startTime,
    };
  }
  pythonFallbackRunning++;

  // 写入临时 cookie 文件
  const tmpDir = os.tmpdir();
  const cookieFile = path.join(tmpDir, `slider-cookie-${Date.now()}-${crypto.randomBytes(4).toString('hex')}.txt`);
  try {
    fs.writeFileSync(cookieFile, cookieStr, { mode: 0o600 });
  } catch (e: any) {
    pythonFallbackRunning--;
    return {
      ok: false, solved: false, captchaDetected: false, attempts: 0,
      error: `Python fallback: 写入 cookie 文件失败: ${safeErrorType(e)}`,
      durationMs: Date.now() - startTime,
    };
  }

  const args = [
    PYTHON_SOLVER_SCRIPT,
    '--cookie-file', cookieFile,
    // 2026-08-01 优化：max-retries 设为 1
    // 原因：sliderSolve.py 内部 attempt>=1 即返回（只拖动 1 次）。
    //       减少重试次数避免 Baxia 加码惩罚（每次拖动失败都会加重风控）。
    //       第 1 次失败后直接返回，不点重试按钮，避免触发加码。
    '--max-retries', String(Math.max(1, Math.min(maxRetries || 1, 1))),
    // 2026-08-01 修复：用 temp 而不是 seed
    // 原因：seed 策略每次求解都 copytree 克隆 90MB+ profile 到 /tmp，
    // 容器 /tmp 是 tmpfs 只有 512MB，几次求解就塞满导致 [Errno 28] No space left on device。
    // temp 策略创建空目录，不克隆，实测也能通过指纹探针（patchright + WebGL patch 足够）。
    '--profile-strategy', 'temp',
  ];
  if (targetUrl) {
    args.push('--target-url', targetUrl);
  }
  if (proxy?.server) {
    args.push('--proxy-server', proxy.server);
    if (proxy.username) args.push('--proxy-username', proxy.username);
    if (proxy.password) args.push('--proxy-password', proxy.password);
  }

  console.log(`[SliderSolver-Python] 启动 Python patchright 求解: ${PYTHON_BINARY} ${args.join(' ').replace(cookieFile, '<cookie-file>')}`);

  return new Promise<PythonSolveResult>((resolve) => {
    let stdout = '';
    let stderr = '';
    let resolved = false;
    // 2026-08-01 修复：detached: true 让 Python 成为进程组组长，
    // 这样超时时可以用 process.kill(-pid) kill 整个进程组（包括 Chrome 子进程）。
    // 原先 child.kill('SIGKILL') 只 kill Python 主进程，Chrome 子进程变孤儿积累。
    const child = spawn(PYTHON_BINARY, args, {
      cwd: '/app',
      detached: true,
      // 2026-08-01 修复：显式设置 stdio，确保 stdout/stderr 是 pipe
      // 原因：detached: true 时默认 stdio 可能不正确，导致 child.stdout 为 null
      // 或 data 事件不触发，Python 输出无法被捕获。
      stdio: ['ignore', 'pipe', 'pipe'],
      env: {
        ...process.env,
        DISPLAY: process.env.DISPLAY || ':99',
        // 2026-08-01 优化：禁用 Python 输出缓冲，确保日志实时输出到 stdout/stderr
        // 原因：server.ts 通过 spawn pipe 捕获 stdout，但 Python 默认块缓冲，
        // 导致日志在超时时还未刷新到 pipe，stdout 为空无法调试。
        PYTHONUNBUFFERED: '1',
        PYTHONIOENCODING: 'utf-8',
      },
    });
    // 2026-08-01 调试：打印 child.pid 和 stdout/stderr 状态
    console.log(`[SliderSolver-Python] spawn 完成 pid=${child.pid} stdout=${child.stdout ? 'pipe' : 'null'} stderr=${child.stderr ? 'pipe' : 'null'}`);

    const timeoutId = setTimeout(() => {
      if (resolved) return;
      resolved = true;
      // 2026-08-01 修复：kill 整个进程组（Python + Chrome 子进程），避免孤儿 Chrome 积累
      try { if (child.pid) process.kill(-child.pid, 'SIGKILL'); } catch {}
      try { child.kill('SIGKILL'); } catch {}
      try { fs.unlinkSync(cookieFile); } catch {}
      // 2026-08-01 优化：超时时也打印 stderr，用于调试 Python 脚本卡在哪一步
      if (stderr) {
        const stderrLines = stderr.split('\n').filter(l => l.trim()).slice(-15);
        console.log(`[SliderSolver-Python] 超时 stderr（最后15行）:\n${stderrLines.join('\n')}`);
      }
      if (stdout) {
        const stdoutLines = stdout.split('\n').filter(l => l.trim()).slice(-5);
        console.log(`[SliderSolver-Python] 超时 stdout（最后5行）:\n${stdoutLines.join('\n')}`);
      }
      resolve({
        ok: false, solved: false, captchaDetected: false, attempts: 0,
        error: `Python fallback 超时（${PYTHON_FALLBACK_TIMEOUT_MS / 1000}秒）`,
        durationMs: Date.now() - startTime,
      });
    }, PYTHON_FALLBACK_TIMEOUT_MS);
    timeoutId.unref?.();

    child.stdout.on('data', (data: Buffer) => {
      const text = data.toString();
      stdout += text;
      // 2026-08-01 调试：实时转发 stdout，确认 data 事件是否触发
      const firstLine = text.split('\n')[0]?.substring(0, 120);
      console.log(`[SliderSolver-Python] stdout>> ${firstLine}`);
    });
    child.stderr.on('data', (data: Buffer) => {
      const text = data.toString();
      stderr += text;
      // 2026-08-01 调试：实时转发 stderr
      const firstLine = text.split('\n')[0]?.substring(0, 120);
      console.log(`[SliderSolver-Python] stderr>> ${firstLine}`);
    });

    child.on('close', (code: number) => {
      if (resolved) return;
      resolved = true;
      clearTimeout(timeoutId);
      // 2026-08-01 修复：Python 退出后 kill 进程组，清理可能残留的 Chrome 子进程
      try { if (child.pid) process.kill(-child.pid, 'SIGKILL'); } catch {}
      try { fs.unlinkSync(cookieFile); } catch {}

      const durationMs = Date.now() - startTime;
      // 2026-08-01 优化：Python 脚本的 log 函数输出到 stdout（不是 stderr），
      // 所以需要同时打印 stdout 和 stderr 用于调试
      if (stdout) {
        const stdoutLines = stdout.split('\n').filter(l => l.trim()).slice(-15);
        console.log(`[SliderSolver-Python] stdout（最后15行）:\n${stdoutLines.join('\n')}`);
      }
      if (stderr) {
        const stderrLines = stderr.split('\n').filter(l => l.trim()).slice(-10);
        console.log(`[SliderSolver-Python] stderr（最后10行）:\n${stderrLines.join('\n')}`);
      }

      if (code !== 0) {
        // 2026-08-01 优化：错误信息同时包含 stdout 和 stderr 的最后几行
        const lastStdout = stdout.split('\n').filter(l => l.trim()).slice(-3).join(' ');
        const lastStderr = stderr.split('\n').filter(l => l.trim()).slice(-3).join(' ');
        const errorDetail = (lastStderr || lastStdout || '').substring(0, 200);
        resolve({
          ok: false, solved: false, captchaDetected: false, attempts: 0,
          error: `Python fallback 退出码 ${code}: ${errorDetail}`,
          durationMs,
        });
        return;
      }

      // 从 stdout 提取最后一行 JSON（Python 脚本可能输出多行，最后一行是结果）
      const lines = stdout.split('\n').filter(l => l.trim());
      const lastLine = lines[lines.length - 1];
      try {
        const result = JSON.parse(lastLine);
        resolve({
          ok: !!result.ok,
          solved: !!result.solved,
          captchaDetected: !!result.captchaDetected,
          attempts: result.attempts || 0,
          error: result.error,
          durationMs,
          cookies: result.cookies,
          x5sec: result.x5sec,
        });
      } catch (e: any) {
        resolve({
          ok: false, solved: false, captchaDetected: false, attempts: 0,
          error: `Python fallback 解析输出失败: ${safeErrorType(e)} stdout=${lastLine.substring(0, 200)}`,
          durationMs,
        });
      }
    });

    child.on('error', (e: Error) => {
      if (resolved) return;
      resolved = true;
      clearTimeout(timeoutId);
      try { if (child.pid) process.kill(-child.pid, 'SIGKILL'); } catch {}
      try { fs.unlinkSync(cookieFile); } catch {}
      resolve({
        ok: false, solved: false, captchaDetected: false, attempts: 0,
        error: `Python fallback 启动失败: ${safeErrorType(e)}`,
        durationMs: Date.now() - startTime,
      });
    });
  }).finally(() => {
    // 2026-08-01 优化：无论 Python fallback 成功/失败/超时，都释放全局锁
    pythonFallbackRunning--;
  });
}

const app = express();
app.disable('x-powered-by');
const ENVIRONMENT = process.env.NODE_ENV || process.env.APP_ENV || 'development';
const productionLike = isProductionLike(ENVIRONMENT);
const internalTokenPolicy = resolveInternalTokenPolicy(process.env.INTERNAL_API_TOKEN, ENVIRONMENT);
const redisPasswordPolicy = resolveRedisPasswordPolicy(process.env.REDIS_PASSWORD, ENVIRONMENT);
const queueEncryptionReady = (() => {
  try {
    assertQueueCookieEncryptionReady();
    return true;
  } catch {
    return false;
  }
})();

type RequestWithTrace = Request & { requestId?: string };

function normalizeRequestId(value: string | undefined): string {
  if (!value || value.length > 128 || !/^[A-Za-z0-9._:-]+$/.test(value)) {
    return crypto.randomUUID().replace(/-/g, '');
  }
  return value;
}

app.use((req: Request, res: Response, next: NextFunction) => {
  const requestId = normalizeRequestId(req.header('X-Request-Id'));
  (req as RequestWithTrace).requestId = requestId;
  res.setHeader('X-Request-Id', requestId);
  res.setHeader('Cache-Control', 'no-store, max-age=0');
  res.setHeader('Pragma', 'no-cache');
  const started = Date.now();
  res.on('finish', () => {
    const elapsedMs = Date.now() - started;
    console.log(`[Crawler] requestId=${requestId} method=${req.method} status=${res.statusCode} elapsedMs=${elapsedMs}`);
  });
  next();
});

const allowedOrigins = (process.env.CORS_ALLOWED_ORIGINS || '')
  .split(',')
  .map((item) => item.trim())
  .filter(Boolean);
const corsConfigurationReady = areProductionCorsOriginsSafe(allowedOrigins, ENVIRONMENT);

app.use(cors({
  origin: (origin, callback) => {
    if (isCorsOriginAllowed(origin, allowedOrigins, ENVIRONMENT)) {
      callback(null, true);
      return;
    }
    callback(new Error('CORS origin denied'));
  },
}));
app.use(express.json({ limit: '256kb' }));

function boundedConfigInteger(value: string | undefined, fallback: number, minimum: number, maximum: number): number {
  const parsed = Number(value ?? fallback);
  return Number.isSafeInteger(parsed) && parsed >= minimum && parsed <= maximum ? parsed : fallback;
}

function parseQueryInteger(value: unknown, fallback: number, minimum: number, maximum: number): number {
  if (value === undefined || value === null || value === '') return fallback;
  if (typeof value !== 'string' || !/^\d+$/.test(value)) throw new Error('invalid pagination');
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < minimum || parsed > maximum) {
    throw new Error('invalid pagination');
  }
  return parsed;
}

const PORT = boundedConfigInteger(process.env.PORT, 3001, 1, 65535);
const RATE_LIMIT_WINDOW_MS = boundedConfigInteger(process.env.CRAWLER_RATE_LIMIT_WINDOW_MS, 60000, 1000, 3600000);
const RATE_LIMIT_MAX = boundedConfigInteger(process.env.CRAWLER_RATE_LIMIT_MAX, 120, 1, 10000);
// 默认并发 2（原 4）：大量账号涌入时避免同时启动过多 Chrome 导致 PIDS/内存耗尽。
// 可通过环境变量 CRAWLER_BROWSER_CONCURRENCY 调整（1-16）。
const MAX_BROWSER_CONCURRENCY = boundedConfigInteger(process.env.CRAWLER_BROWSER_CONCURRENCY, 2, 1, 16);
const MAX_BROWSER_CONCURRENCY_PER_TENANT = boundedConfigInteger(
  process.env.CRAWLER_BROWSER_CONCURRENCY_PER_TENANT,
  Math.min(2, MAX_BROWSER_CONCURRENCY),
  1,
  MAX_BROWSER_CONCURRENCY,
);
// API 对接独立并发槽位（与内部任务互不抢占）
const MAX_API_CONCURRENCY = boundedConfigInteger(process.env.CRAWLER_API_CONCURRENCY, 2, 1, 16);
let activeApiOperations = 0;
const QR_SESSION_TTL_MS = boundedConfigInteger(process.env.CRAWLER_QR_SESSION_TTL_MS, 180000, 60000, 600000);
const rateBuckets = new Map<string, { count: number; resetAt: number }>();
let rateLimitChecks = 0;
let activeBrowserOperations = 0;
const activeBrowserOperationsByTenant = new Map<string, number>();

function tryAcquireBrowserSlot(tenantId: string): (() => void) | undefined {
  const tenantActive = activeBrowserOperationsByTenant.get(tenantId) || 0;
  if (activeBrowserOperations >= MAX_BROWSER_CONCURRENCY
      || tenantActive >= MAX_BROWSER_CONCURRENCY_PER_TENANT) return undefined;
  activeBrowserOperations += 1;
  activeBrowserOperationsByTenant.set(tenantId, tenantActive + 1);
  let released = false;
  // 关键修复：槽位超时强制释放（5 分钟）
  // 原先若求解过程中浏览器崩溃/异常导致 release() 未被调用，槽位会永久占用，
  // 最终并发槽位耗尽，所有新请求都返回 503"浏览器任务繁忙"。
  // 现在设置 5 分钟超时（正常求解最多 2-3 分钟），超时未释放则自动释放并告警。
  const slotAcquiredAt = Date.now();
  const SLOT_TIMEOUT_MS = 5 * 60 * 1000;
  const timeoutId = setTimeout(() => {
    if (!released) {
      console.warn(`[BrowserSlot] 槽位超时未释放，强制释放 tenantId=${tenantId} 占用时长=${Date.now() - slotAcquiredAt}ms activeBefore=${activeBrowserOperations}`);
      release();
    }
  }, SLOT_TIMEOUT_MS);
  timeoutId.unref();
  const release = () => {
    if (released) return;
    released = true;
    clearTimeout(timeoutId);
    activeBrowserOperations = Math.max(0, activeBrowserOperations - 1);
    const remaining = Math.max(0, (activeBrowserOperationsByTenant.get(tenantId) || 1) - 1);
    if (remaining === 0) activeBrowserOperationsByTenant.delete(tenantId);
    else activeBrowserOperationsByTenant.set(tenantId, remaining);
  };
  return release;
}

/**
 * API 对接独立并发槽位。
 * 与内部 tryAcquireBrowserSlot 互不抢占，避免 API 流量突增影响内部账号保活链路。
 * slotType='api' 时调用此函数。
 */
function tryAcquireApiSlot(): (() => void) | undefined {
  if (activeApiOperations >= MAX_API_CONCURRENCY) return undefined;
  activeApiOperations += 1;
  let released = false;
  const slotAcquiredAt = Date.now();
  const SLOT_TIMEOUT_MS = 5 * 60 * 1000;
  const timeoutId = setTimeout(() => {
    if (!released) {
      console.warn(`[ApiSlot] 槽位超时未释放，强制释放 占用时长=${Date.now() - slotAcquiredAt}ms activeBefore=${activeApiOperations}`);
      release();
    }
  }, SLOT_TIMEOUT_MS);
  timeoutId.unref();
  const release = () => {
    if (released) return;
    released = true;
    clearTimeout(timeoutId);
    activeApiOperations = Math.max(0, activeApiOperations - 1);
  };
  return release;
}

/**
 * 根据 slotType 选择槽位获取函数。
 * - slotType='api' → 走 API 独立槽位池
 * - 其他/未传 → 走原内部槽位池
 */
function acquireSlot(tenantId: string, slotType?: string): (() => void) | undefined {
  if (slotType === 'api') return tryAcquireApiSlot();
  return tryAcquireBrowserSlot(tenantId);
}

function browserCapacityUnavailable(res: Response) {
  res.setHeader('Retry-After', '5');
  return res.status(503).json({ ok: false, error: '浏览器任务繁忙，请稍后重试' });
}

interface QrLoginSession {
  tenantId: string;
  browser: Browser;
  context: BrowserContext;
  page: Page;
  expiresAt: number;
  consuming: boolean;
  timer: NodeJS.Timeout;
  releaseBrowser: () => void;
}

const qrLoginSessions = new Map<string, QrLoginSession>();
const tenantQrSessionReservations = new Set<string>();

async function closeQrLoginSession(sessionId: string): Promise<void> {
  const session = qrLoginSessions.get(sessionId);
  if (!session) return;
  qrLoginSessions.delete(sessionId);
  tenantQrSessionReservations.delete(session.tenantId);
  clearTimeout(session.timer);
  await Promise.allSettled([session.context.close(), session.browser.close()]);
  session.releaseBrowser();
}

async function closeAllQrLoginSessions(): Promise<void> {
  await Promise.allSettled([...qrLoginSessions.keys()].map((sessionId) => closeQrLoginSession(sessionId)));
}

function safeEquals(a: string | undefined, b: string): boolean {
  if (!a) return false;
  const aa = Buffer.from(a);
  const bb = Buffer.from(b);
  if (aa.length !== bb.length) return false;
  return crypto.timingSafeEqual(aa, bb);
}

function tenantIdFrom(req: Request): string {
  return normalizeTenantId(req.header('X-Internal-Tenant-Id'));
}

function makeBullMqSafeJobId(prefix: string, ...parts: Array<string | number>): string {
  // BullMQ custom jobId 不能包含冒号，同时不应该把 URL、邮箱、Cookie 等原始业务字段暴露进 jobId。
  // 统一用短 hash 生成只包含 [A-Za-z0-9_-] 的 ID，彻底规避 “Custom Id cannot contain :”。
  const safePrefix = String(prefix || 'job').replace(/[^A-Za-z0-9_-]/g, '_').slice(0, 32) || 'job';
  const seed = parts.map((part) => String(part ?? '').trim()).join('|');
  const hash = crypto.createHash('sha256').update(seed).digest('hex').slice(0, 24);
  return `${safePrefix}-${hash}`;
}

async function isQueueJobActive(jobId: string): Promise<boolean> {
  if (!/^[A-Za-z0-9_-]{1,128}$/.test(jobId)) return false;
  const job = await goofishCrawlQueue.getJob(jobId);
  if (!job) return false;
  const state = await job.getState();
  return ['active', 'waiting', 'delayed', 'prioritized', 'waiting-children'].includes(state);
}

function isFreshPublishingRow(createdAt: unknown): boolean {
  const timestamp = new Date(String(createdAt || '')).getTime();
  return Number.isFinite(timestamp) && Date.now() - timestamp < 60000;
}

async function reconcileOrphanedCrawlJobs(): Promise<void> {
  const pool = getPool();
  // 包含 'retrying'：markCrawlJobRetrying 将失败任务置为 'retrying'，若 BullMQ 重试也已放弃（队列任务不存在），
  // 必须一并修复为 failed，否则任务会永久卡在 'retrying' 状态，前端轮询看到该状态会抛"未知状态"。
  const candidates = await pool.query(
    `SELECT tenant_id, bullmq_job_id
     FROM goofish_crawl_jobs
     WHERE status IN ('pending', 'running', 'retrying') AND created_at < NOW() - INTERVAL '1 minute'
     ORDER BY created_at ASC LIMIT 500`,
  );
  let repaired = 0;
  for (const row of candidates.rows) {
    if (await isQueueJobActive(String(row.bullmq_job_id || ''))) continue;
    const result = await pool.query(
      `UPDATE goofish_crawl_jobs
       SET status = 'failed', error_message = '队列任务不存在，请重新提交',
           finished_at = NOW(), execution_token = NULL
       WHERE tenant_id = $1 AND bullmq_job_id = $2 AND status IN ('pending', 'running', 'retrying')`,
      [row.tenant_id, row.bullmq_job_id],
    );
    repaired += result.rowCount || 0;
  }
  if (repaired > 0) console.warn(`[Server] 已修复孤立采集任务: count=${repaired}`);
}

function requireInternalAuth(req: Request, res: Response, next: NextFunction) {
  // /api/health 和 /api/health/processes 豁免 internal token（仅暴露运行状态，不涉及业务数据）
  // /api/ready 豁免（Docker healthcheck 使用）
  if (req.path === '/api/health' || req.path === '/api/health/processes' || req.path === '/api/ready') return next();

  if (!internalTokenPolicy.ready) {
    return res.status(503).json({ ok: false, error: internalTokenPolicy.reason || 'internal authentication is not ready' });
  }
  const expected = internalTokenPolicy.token;
  const provided = req.header('X-Internal-Token');
  if (!safeEquals(provided, expected)) {
    return res.status(403).json({ ok: false, error: 'forbidden' });
  }
  let tenantId: string;
  try {
    tenantId = normalizeTenantId(req.header('X-Internal-Tenant-Id'));
  } catch {
    return res.status(400).json({ ok: false, error: 'missing or invalid X-Internal-Tenant-Id' });
  }

  const key = `${tenantId}:${req.ip}`;
  const now = Date.now();
  rateLimitChecks += 1;
  if (rateLimitChecks % 1024 === 0 || rateBuckets.size > 10000) {
    for (const [bucketKey, candidate] of rateBuckets) {
      if (candidate.resetAt < now) rateBuckets.delete(bucketKey);
    }
  }
  if (!rateBuckets.has(key) && rateBuckets.size >= 10000) {
    return res.status(429).json({ ok: false, error: 'too many crawler clients' });
  }
  const bucket = rateBuckets.get(key);
  if (!bucket || bucket.resetAt < now) {
    rateBuckets.set(key, { count: 1, resetAt: now + RATE_LIMIT_WINDOW_MS });
  } else {
    bucket.count += 1;
    if (bucket.count > RATE_LIMIT_MAX) {
      return res.status(429).json({ ok: false, error: 'too many crawler requests' });
    }
  }
  next();
}

app.use(requireInternalAuth);


async function handleGoofishSearch(req: Request, res: Response, rawInput: Record<string, unknown>) {
  let input;
  try {
    input = parseSearchInput(rawInput);
  } catch (e: any) {
    return res.status(400).json({ ok: false, error: e?.message || '搜索参数无效' });
  }

  try {
    const tenantId = tenantIdFrom(req);
    console.log(`[SearchCrawler] requestId=${(req as RequestWithTrace).requestId} tenantId=${tenantId} page=${input.page} pageSize=${input.pageSize} hasCookie=${!!input.cookie}`);

    // 2026-08-01 优化：注入缓存的 x5sec（如果有），绕过 Baxia 风控
    if (input.cookie && !cookieHasX5sec(input.cookie)) {
      try {
        const cachedX5sec = await getCachedX5sec(input.cookie);
        if (cachedX5sec) {
          input.cookie = injectX5secIntoCookie(input.cookie, cachedX5sec);
          console.log(`[SearchCrawler] requestId=${(req as RequestWithTrace).requestId} ✓ 注入缓存 x5sec（免滑块）`);
        }
      } catch (e: any) {
        console.warn(`[SearchCrawler] x5sec 注入失败（降级为原始 cookie）: ${e?.message || e}`);
      }
    }

    const releaseBrowser = tryAcquireBrowserSlot(tenantId);
    if (!releaseBrowser) return browserCapacityUnavailable(res);
    try {
      const result = await crawlGoofishSearch(input.q, input.page, input.pageSize, input.cookie);
      return res.status(200).json({ ok: true, ...result });
    } finally {
      releaseBrowser();
    }
  } catch (e: any) {
    console.error(`[SearchCrawler] requestId=${(req as RequestWithTrace).requestId} method=${req.method} errorType=${safeErrorType(e)}`);
    return res.status(500).json({
      ok: false,
      error: toPublicCrawlerError(e, '商品搜索失败，请稍后重试'),
      items: [],
      total: 0,
      page: input.page,
      pageSize: input.pageSize,
      hasMore: false,
    });
  }
}

// GET 仅保留无 Cookie 的兼容调用；认证 Cookie 必须放在 POST JSON 中，避免泄露到 URL/代理日志。
app.get('/api/goofish/search', async (req, res) => {
  if (typeof req.query.cookie === 'string' && req.query.cookie.trim()) {
    return res.status(400).json({ ok: false, error: 'Cookie 不允许出现在 URL 中，请改用 POST JSON 请求' });
  }
  return handleGoofishSearch(req, res, req.query as Record<string, unknown>);
});

app.post('/api/goofish/search', async (req, res) => {
  return handleGoofishSearch(req, res, (req.body || {}) as Record<string, unknown>);
});

// ---- POST /api/goofish/item-detail ----
// 通过 Playwright 浏览器获取单个商品详情（封面图、标题、价格等），
// 绕过直接调用 MTOP API 触发的 Baxia 风控。
app.post('/api/goofish/item-detail', async (req, res) => {
  try {
    const tenantId = tenantIdFrom(req);
    const itemId = String(req.body?.itemId || '').trim();
    if (!itemId || !/^\d+$/.test(itemId)) {
      return res.status(400).json({ ok: false, error: '缺少有效的 itemId 参数' });
    }

    let cookieStr = '';
    try {
      cookieStr = normalizeCookieInput(req.body?.cookie);
    } catch (error) {
      return res.status(400).json({ ok: false, error: error instanceof Error ? error.message : 'Cookie is invalid' });
    }

    console.log(`[ItemDetailCrawler] requestId=${(req as RequestWithTrace).requestId} tenantId=${tenantId} itemId=${itemId} hasCookie=${!!cookieStr}`);

    // 2026-08-01 优化：注入缓存的 x5sec（如果有），绕过 Baxia 风控
    if (cookieStr && !cookieHasX5sec(cookieStr)) {
      try {
        const cachedX5sec = await getCachedX5sec(cookieStr);
        if (cachedX5sec) {
          cookieStr = injectX5secIntoCookie(cookieStr, cachedX5sec);
          console.log(`[ItemDetailCrawler] requestId=${(req as RequestWithTrace).requestId} ✓ 注入缓存 x5sec（免滑块）`);
        }
      } catch (e: any) {
        console.warn(`[ItemDetailCrawler] x5sec 注入失败（降级为原始 cookie）: ${e?.message || e}`);
      }
    }

    const releaseBrowser = tryAcquireBrowserSlot(tenantId);
    if (!releaseBrowser) return browserCapacityUnavailable(res);
    try {
      const detail = await fetchGoofishItemDetail(itemId, cookieStr);
      if (detail.ok === false) {
        // 采集超时或失败：返回 504 让调用方区分"商品无图"与"采集超时"
        return res.status(504).json({ ok: false, error: detail.error || '获取商品详情超时', detail });
      }
      return res.status(200).json({ ok: true, detail });
    } finally {
      releaseBrowser();
    }
  } catch (e: any) {
    console.error(`[ItemDetailCrawler] requestId=${(req as RequestWithTrace).requestId} errorType=${safeErrorType(e)}`);
    return res.status(500).json({ ok: false, error: toPublicCrawlerError(e, '获取商品详情失败，请稍后重试') });
  }
});

// ---- POST /api/import/goofish ----
app.post('/api/import/goofish', async (req, res) => {
  try {
    const tenantId = tenantIdFrom(req);
    const { url } = req.body;
    let cookie: string;
    try {
      cookie = normalizeCookieInput(req.body?.cookie);
    } catch (error) {
      return res.status(400).json({ ok: false, error: error instanceof Error ? error.message : 'Cookie is invalid' });
    }
    if (!url || typeof url !== 'string' || url.length > 2048) {
      return res.status(400).json({
        ok: false,
        error: '缺少 url 参数或 url 过长',
      });
    }

    // 解析 URL
    let parseResult;
    try {
      parseResult = parseGoofishStoreUrl(url);
    } catch (e: any) {
      return res.status(400).json({
        ok: false,
        error: e.message,
      });
    }
    let { userId, normalizedUrl } = parseResult;

    // 2026-08-01 优化：注入缓存的 x5sec（如果有），绕过 Baxia 风控
    if (cookie && !cookieHasX5sec(cookie)) {
      try {
        const cachedX5sec = await getCachedX5sec(cookie);
        if (cachedX5sec) {
          cookie = injectX5secIntoCookie(cookie, cachedX5sec);
          console.log(`[ImportCrawler] requestId=${(req as RequestWithTrace).requestId} ✓ 注入缓存 x5sec（免滑块）`);
        }
      } catch (e: any) {
        console.warn(`[ImportCrawler] x5sec 注入失败（降级为原始 cookie）: ${e?.message || e}`);
      }
    }

    // 当 URL 中没有 userId 参数（如首页分享链接 https://www.goofish.com/?spm=...），
    // 通过浏览器实际访问页面解析出店铺 userId，再提交爬取任务。
    if (parseResult.needsBrowserResolution || !userId) {
      const rawUrl = parseResult.rawUrl || url;
      console.log(`[Server] requestId=${(req as RequestWithTrace).requestId} URL 缺少 userId，启动浏览器解析: host=${new URL(rawUrl).hostname}`);
      const releaseBrowser = tryAcquireBrowserSlot(tenantId);
      if (!releaseBrowser) return browserCapacityUnavailable(res);
      try {
        userId = await resolveStoreUserId(rawUrl, cookie);
        normalizedUrl = `https://www.goofish.com/personal?userId=${userId}`;
        console.log(`[Server] requestId=${(req as RequestWithTrace).requestId} 浏览器解析 userId 成功`);
      } catch (e: any) {
        console.error(`[Server] requestId=${(req as RequestWithTrace).requestId} operation=resolveStoreUserId errorType=${safeErrorType(e)}`);
        return res.status(400).json({
          ok: false,
          error: toPublicCrawlerError(e, '无法从该链接解析出店铺 userId，请确认链接有效或使用带 userId 的店铺链接'),
        });
      } finally {
        releaseBrowser();
      }
    }

    if (!userId || !/^\d{1,32}$/.test(userId) || !normalizedUrl) {
      return res.status(400).json({ ok: false, error: '店铺 userId 无效' });
    }

    // 判断 6 小时内是否已抓取
    const pool = getPool();
    // 包含 'retrying'：BullMQ 自动重试中的任务对用户而言仍属"进行中"，应直接复用而非新建。
    const recent = await pool.query(
      `SELECT bullmq_job_id, status, item_count, created_at FROM goofish_crawl_jobs
       WHERE tenant_id = $1
         AND store_user_id = $2
         AND status IN ('pending', 'running', 'retrying', 'completed')
         AND created_at > NOW() - INTERVAL '6 hours'
       ORDER BY created_at DESC
       LIMIT 1`,
      [tenantId, userId]
    );

    if (recent.rows.length > 0) {
      const row = recent.rows[0];
      if (row.status === 'completed' && Number(row.item_count || 0) > 0) {
        return res.status(200).json({
          ok: true,
          jobId: row.bullmq_job_id,
          userId,
          status: row.status,
          cached: true,
          message: '该店铺 6 小时内已完成采集，直接读取缓存商品',
        });
      }
      if (row.status === 'pending' || row.status === 'running' || row.status === 'retrying') {
        if (isFreshPublishingRow(row.created_at)) {
          return res.status(200).json({
            ok: true,
            jobId: row.bullmq_job_id,
            userId,
            status: row.status,
            cached: false,
            message: '采集任务正在提交或处理，请继续轮询当前任务',
          });
        }
        try {
          if (await isQueueJobActive(String(row.bullmq_job_id || ''))) {
            return res.status(200).json({
              ok: true,
              jobId: row.bullmq_job_id,
              userId,
              status: row.status,
              cached: false,
              message: '该店铺已有采集任务正在处理，继续轮询当前任务',
            });
          }
        } catch (queueError) {
          console.error(`[Server] requestId=${(req as RequestWithTrace).requestId} operation=verifyCrawlJob errorType=${safeErrorType(queueError)}`);
          return res.status(503).json({ ok: false, error: '采集队列状态暂时不可用，请稍后重试' });
        }
        await pool.query(
          `UPDATE goofish_crawl_jobs
           SET status = 'failed', error_message = '队列任务不存在，请重新提交', finished_at = NOW(), execution_token = NULL
           WHERE tenant_id = $1 AND bullmq_job_id = $2 AND status IN ('pending', 'running', 'retrying')`,
          [tenantId, row.bullmq_job_id],
        );
      }
    }

    await pool.query(
      `UPDATE goofish_crawl_jobs
       SET status = 'failed', error_message = '采集任务超时，请重新提交', finished_at = NOW()
       WHERE tenant_id = $1 AND store_user_id = $2
         AND status IN ('pending', 'running', 'retrying')
         AND created_at <= NOW() - INTERVAL '6 hours'`,
      [tenantId, userId],
    );

    // Reserve the durable job record before publishing to Redis. This prevents
    // a fast worker from completing before the polling record exists.
    const jobId = makeBullMqSafeJobId('goofish', tenantId, userId, Date.now(), crypto.randomUUID());
    let reservation = await pool.query(
      `INSERT INTO goofish_crawl_jobs (tenant_id, bullmq_job_id, store_user_id, status, created_at)
       VALUES ($1, $2, $3, 'pending', NOW())
       ON CONFLICT DO NOTHING
       RETURNING bullmq_job_id`,
      [tenantId, jobId, userId]
    );

    if (reservation.rowCount !== 1) {
      const active = await pool.query(
        `SELECT bullmq_job_id, status, created_at
         FROM goofish_crawl_jobs
         WHERE tenant_id = $1 AND store_user_id = $2 AND status IN ('pending', 'running', 'retrying')
         ORDER BY created_at DESC LIMIT 1`,
        [tenantId, userId],
      );
      if (active.rows.length > 0) {
        if (isFreshPublishingRow(active.rows[0].created_at)) {
          return res.status(200).json({
            ok: true,
            jobId: active.rows[0].bullmq_job_id,
            userId,
            status: active.rows[0].status,
            cached: false,
            message: '采集任务正在提交或处理，请继续轮询当前任务',
          });
        }
        if (await isQueueJobActive(String(active.rows[0].bullmq_job_id || ''))) {
          return res.status(200).json({
            ok: true,
            jobId: active.rows[0].bullmq_job_id,
            userId,
            status: active.rows[0].status,
            cached: false,
            message: '该店铺已有采集任务正在处理，请继续轮询当前任务',
          });
        }
        await pool.query(
          `UPDATE goofish_crawl_jobs
           SET status = 'failed', error_message = '队列任务不存在，请重新提交', finished_at = NOW(), execution_token = NULL
           WHERE tenant_id = $1 AND bullmq_job_id = $2 AND status IN ('pending', 'running', 'retrying')`,
          [tenantId, active.rows[0].bullmq_job_id],
        );
        reservation = await pool.query(
          `INSERT INTO goofish_crawl_jobs (tenant_id, bullmq_job_id, store_user_id, status, created_at)
           VALUES ($1, $2, $3, 'pending', NOW())
           ON CONFLICT DO NOTHING
           RETURNING bullmq_job_id`,
          [tenantId, jobId, userId],
        );
      }
      if (reservation.rowCount !== 1) throw new Error('crawl job reservation failed');
    }

    try {
      await goofishCrawlQueue.add('crawl-goofish-store', {
        tenantId,
        ...(cookie ? { cookieEnvelope: encryptQueueCookie(cookie, `${tenantId}:${jobId}`) } : {}),
      }, {
        jobId,
        removeOnComplete: true,
        removeOnFail: true,
      });
    } catch (queueError) {
      await pool.query(
        `UPDATE goofish_crawl_jobs
         SET status = 'failed', error_message = $1, finished_at = NOW()
         WHERE tenant_id = $2 AND bullmq_job_id = $3 AND status = 'pending'`,
        ['采集队列暂时不可用，请稍后重试', tenantId, jobId],
      );
      console.error(`[Server] requestId=${(req as RequestWithTrace).requestId} operation=publishCrawlJob errorType=${safeErrorType(queueError)}`);
      return res.status(503).json({ ok: false, error: '采集队列暂时不可用，请稍后重试' });
    }

    console.log(`[Server] requestId=${(req as RequestWithTrace).requestId} 任务已创建: tenantId=${tenantId}, jobId=${jobId}`);

    return res.status(200).json({
      ok: true,
      jobId,
      userId,
      status: 'pending',
    });
  } catch (e: any) {
    console.error(`[Server] requestId=${(req as RequestWithTrace).requestId} operation=submitCrawlJob errorType=${safeErrorType(e)}`);
    return res.status(500).json({
      ok: false,
      error: toPublicCrawlerError(e, '店铺采集任务提交失败，请稍后重试'),
    });
  }
});

// ---- GET /api/crawl-jobs/:id ----
app.get('/api/crawl-jobs/:id', async (req, res) => {
  try {
    const tenantId = tenantIdFrom(req);
    const { id } = req.params;
    if (!id || !/^[A-Za-z0-9_-]{1,128}$/.test(id)) {
      return res.status(400).json({ ok: false, error: '非法任务 ID' });
    }
    const pool = getPool();

    const result = await pool.query(
      `SELECT bullmq_job_id, store_user_id, status, item_count, error_message,
              created_at, started_at, finished_at
       FROM goofish_crawl_jobs
       WHERE tenant_id = $1 AND bullmq_job_id = $2
       LIMIT 1`,
      [tenantId, id]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({
        ok: false,
        jobId: id,
        status: 'unknown',
        result: null,
        error: '采集任务不存在或已过期',
      });
    }

    const row = result.rows[0];
    // 'retrying' 也需要 orphan 检测：若 BullMQ 已无对应任务，应推进到 failed，避免永久卡死。
    if ((row.status === 'pending' || row.status === 'running' || row.status === 'retrying') && !isFreshPublishingRow(row.created_at)) {
      try {
        if (!await isQueueJobActive(String(row.bullmq_job_id || ''))) {
          await pool.query(
            `UPDATE goofish_crawl_jobs
             SET status = 'failed', error_message = '队列任务不存在，请重新提交',
                 finished_at = NOW(), execution_token = NULL
             WHERE tenant_id = $1 AND bullmq_job_id = $2 AND status IN ('pending', 'running', 'retrying')`,
            [tenantId, id],
          );
          row.status = 'failed';
          row.error_message = '队列任务不存在，请重新提交';
        }
      } catch (queueError) {
        console.error(`[Server] requestId=${(req as RequestWithTrace).requestId} operation=verifyCrawlJob errorType=${safeErrorType(queueError)}`);
        return res.status(503).json({ ok: false, error: '采集队列状态暂时不可用，请稍后重试' });
      }
    }
    return res.status(200).json({
      ok: true,
      jobId: id,
      status: row.status,
      result: row.status === 'completed' ? { count: row.item_count } : null,
      failedReason: row.error_message ? toPublicCrawlerError(row.error_message, '采集任务执行失败') : null,
    });
  } catch (e: any) {
    console.error(`[Server] requestId=${(req as RequestWithTrace).requestId} operation=getCrawlJob errorType=${safeErrorType(e)}`);
    return res.status(500).json({
      ok: false,
      error: '采集任务状态查询失败，请稍后重试',
    });
  }
});

// ---- GET /api/goofish/stores/:userId/items ----
app.get('/api/goofish/stores/:userId/items', async (req, res) => {
  try {
    const tenantId = tenantIdFrom(req);
    const { userId } = req.params;
    if (!userId || !/^\d{1,32}$/.test(userId)) {
      return res.status(400).json({ ok: false, error: '非法用户 ID' });
    }
    let page: number;
    let pageSize: number;
    try {
      page = parseQueryInteger(req.query.page, 1, 1, 1000);
      pageSize = parseQueryInteger(req.query.pageSize, 500, 1, 500);
    } catch {
      return res.status(400).json({ ok: false, error: '分页参数无效' });
    }
    const pool = getPool();

    const [result, countResult] = await Promise.all([
      pool.query(
      `SELECT id, store_user_id, item_id, title, description, price_text, image_url, item_url,
              first_seen_at, last_seen_at
       FROM goofish_items
       WHERE tenant_id = $1 AND store_user_id = $2 AND is_active = TRUE
       ORDER BY last_seen_at DESC, id DESC
       LIMIT $3 OFFSET $4`,
      [tenantId, userId, pageSize, (page - 1) * pageSize]
      ),
      pool.query(
        `SELECT COUNT(*) AS total
         FROM goofish_items
         WHERE tenant_id = $1 AND store_user_id = $2 AND is_active = TRUE`,
        [tenantId, userId],
      ),
    ]);

    const items = result.rows.map((row) => ({
      id: row.id,
      storeUserId: row.store_user_id,
      itemId: row.item_id,
      title: row.title,
      description: row.description,
      price: row.price_text,
      imageUrl: row.image_url,
      itemUrl: row.item_url,
      firstSeenAt: row.first_seen_at,
      lastSeenAt: row.last_seen_at,
    }));

    const total = Number(countResult.rows[0]?.total || 0);
    return res.status(200).json({
      ok: true,
      userId,
      items,
      total,
      page,
      pageSize,
      hasMore: page * pageSize < total,
    });
  } catch (e: any) {
    console.error(`[Server] requestId=${(req as RequestWithTrace).requestId} operation=listStoreItems errorType=${safeErrorType(e)}`);
    return res.status(500).json({
      ok: false,
      error: '店铺商品查询失败，请稍后重试',
    });
  }
});

// ---- POST /api/goofish/slide-solve ----  滑块验证自动求解
app.post('/api/goofish/slide-solve', async (req, res) => {
  try {
    const tenantId = tenantIdFrom(req);
    const { cookie, targetUrl, headless, maxRetries, timeoutMs, proxy, profileStrategy, semiAutoFallback } = req.body || {};
    let cookieStr: string;
    try {
      cookieStr = normalizeCookieInput(cookie);
    } catch (error) {
      return res.status(400).json({ ok: false, error: error instanceof Error ? error.message : 'Cookie is invalid' });
    }
    const resolvedHeadless = productionLike
      ? (isHeadedDisplayAvailable() ? false : true)  // 生产环境：有显示器（Xvfb）就用有头模式，否则 headless
      : (typeof headless === 'boolean' ? headless : undefined);

    // 2026-08-01 优化：先查 x5sec 缓存，命中则直接返回（跳过滑块求解，实现免滑块）
    // 场景：同一账号短时间内多次触发风控时，第一次求解成功后 x5sec 已缓存，
    //       后续请求直接返回缓存的 x5sec，无需再启动 Chrome 拖动滑块。
    if (!cookieHasX5sec(cookieStr)) {
      try {
        const cachedX5sec = await getCachedX5sec(cookieStr);
        if (cachedX5sec) {
          const requestId = (req as RequestWithTrace).requestId;
          const enhancedCookie = injectX5secIntoCookie(cookieStr, cachedX5sec);
          console.log(`[SliderSolver] requestId=${requestId} ✓ x5sec 缓存命中，跳过滑块求解（免滑块）`);
          return res.status(200).json({
            ok: true,
            solved: true,
            captchaDetected: false,
            attempts: 0,
            durationMs: 0,
            cookies: enhancedCookie,
            x5sec: cachedX5sec,
            cached: true,
          });
        }
      } catch (e: any) {
        console.warn(`[SliderSolver] x5sec 缓存查询失败（降级为正常求解）: ${e?.message || e}`);
      }
    }

    let safeTargetUrl;
    try {
      safeTargetUrl = normalizeGoofishTargetUrl(targetUrl);
    } catch (e: any) {
      return res.status(400).json({ ok: false, error: e?.message || '目标 URL 无效' });
    }

    // 账号绑定代理（全自动固定出口）：仅允许 http(s)/socks5 主机端口，不落日志密码
    let safeProxy: { server: string; username?: string; password?: string } | undefined;
    if (proxy && typeof proxy === 'object' && typeof proxy.server === 'string') {
      const server = String(proxy.server).trim();
      if (/^(https?|socks5?):\/\//i.test(server) && server.length <= 256) {
        safeProxy = { server };
        if (typeof proxy.username === 'string' && proxy.username.trim()) {
          safeProxy.username = proxy.username.trim().slice(0, 128);
        }
        if (typeof proxy.password === 'string' && proxy.password) {
          safeProxy.password = String(proxy.password).slice(0, 256);
        }
      }
    }

    console.log(
      `[SliderSolver] requestId=${(req as RequestWithTrace).requestId} tenantId=${tenantId} hasCookie=${!!cookieStr} hasProxy=${!!safeProxy} targetHost=${safeTargetUrl ? new URL(safeTargetUrl).hostname : 'default'}`,
    );

    const slotType = req.body?.slotType;
    const releaseBrowser = acquireSlot(tenantId, slotType);
    if (!releaseBrowser) return browserCapacityUnavailable(res);

    // 整体超时保护：170 秒（略小于 httpx 180 秒，确保先返回超时响应而非 HTTP 超时）
    // 2026-07-29 事故修复：solveGoofishSlider 内部某些操作（如 chromium.launchPersistentContext、
    // page.goto 在网络异常时）可能卡住无限期，导致 httpx 180 秒超时后客户端断开，
    // 但 crawler-service 内部仍在卡着（BrowserSlot 5 分钟超时才释放槽位）。
    // 修复：用 Promise.race 添加整体超时，170 秒后返回超时响应，释放槽位。
    // solveGoofishSlider 在后台继续执行，其 finally 块最终会清理浏览器资源。
    //
    // 2026-08-01 优化：Playwright 失败后启用 Python patchright fallback。
    // 整体超时 170s 拆分：Playwright 10s + Python fallback 160s = 170s
    // 2026-08-01 优化：Playwright 超时从 50s 降到 10s。
    // 原因：数据分析显示 Playwright 的 CDP 事件被 FireyeJS 识别为机器人，
    //       拖动 100% 失败。50s 内 2 次拖动不仅浪费时间，还触发 Baxia 风控，
    //       导致 Python fallback 启动时账号已是 punish 状态。
    //       降到 10s 只做快速检测（页面加载 + 滑块检测），不拖动，
    //       把时间留给 Python patchright fallback（真正有效的方案）。
    //       如果 Playwright 10s 内检测到无需验证（check_solved），直接返回成功。
    const SOLVE_OVERALL_TIMEOUT_MS = 170_000;
    const PLAYWRIGHT_TIMEOUT_MS = 10_000;  // Playwright 10s 仅做快速检测
    const requestId = (req as RequestWithTrace).requestId;

    // 第一阶段：Playwright 求解（80s 超时）
    const playwrightResult = await (async () => {
      let solveTimeoutId: NodeJS.Timeout | undefined;
      try {
        const timeoutPromise = new Promise<SlideSolveResult>((resolve) => {
          solveTimeoutId = setTimeout(() => {
            console.warn(`[SliderSolver] requestId=${requestId} Playwright 超时 ${PLAYWRIGHT_TIMEOUT_MS}ms`);
            resolve({
              ok: false,
              solved: false,
              captchaDetected: false,
              attempts: 0,
              error: `Playwright 求解超时（${PLAYWRIGHT_TIMEOUT_MS / 1000}秒）`,
              durationMs: PLAYWRIGHT_TIMEOUT_MS,
            });
          }, PLAYWRIGHT_TIMEOUT_MS);
          solveTimeoutId.unref?.();
        });
        return await Promise.race([
          solveGoofishSlider({
            cookieStr,
            targetUrl: safeTargetUrl,
            headless: resolvedHeadless,
            maxRetries: Math.max(1, Math.min(Number(maxRetries) || 5, 5)),
            timeoutMs: Math.max(5000, Math.min(Number(timeoutMs) || 30000, 180000)),
            proxy: safeProxy,
            profileStrategy: (profileStrategy === 'seed' || profileStrategy === 'temp') ? profileStrategy : 'persistent',
            semiAutoFallback: false,  // Python fallback 阶段不启用半自动兜底
          }),
          timeoutPromise,
        ]);
      } finally {
        if (solveTimeoutId) clearTimeout(solveTimeoutId);
        releaseBrowser();
        // 2026-08-01 修复：Promise.race 超时后 solveGoofishSlider 在后台继续运行，
        // Chrome 进程不被清理导致累积（16个 Chrome 进程 → OOM → browser_crashed）。
        // 主动 pkill Playwright 的 chrome-slider-warm-* 目录的 Chrome 进程。
        // Python fallback 用不同的 userDataDir（chrome-slider-temp-*），不受影响。
        try {
          const { execSync } = await import('child_process');
          execSync(`pkill -9 -f 'chrome-slider-warm-' 2>/dev/null || true`, { stdio: 'ignore', timeout: 5000 });
          // 清理孤儿 Chrome 子进程（PPID=1 的 /opt/google/chrome/chrome 进程）
          if (process.platform !== 'win32' && process.platform !== 'darwin') {
            const orphanOutput = execSync(
              "ps -eo pid,ppid,cmd --no-headers | grep '/opt/google/chrome/chrome' | grep -v grep | awk '$2==1{print $1}'",
              { encoding: 'utf-8', timeout: 5000 },
            );
            const orphanPids = orphanOutput.trim().split('\n').map((s: string) => Number(s.trim())).filter((n: number) => n >= 100);
            for (const pid of orphanPids) {
              try { process.kill(pid, 'SIGKILL'); } catch { /* 进程已退出，忽略 */ }
            }
          }
          console.log(`[SliderSolver] requestId=${requestId} Playwright 超时后已清理 Chrome 进程`);
        } catch { /* ignore */ }
      }
    })();

    let result: SlideSolveResult = playwrightResult;
    // 如果 Playwright 求解成功，从 cookies 中解析 x5sec（用于缓存复用）
    if (result.solved && result.cookies) {
      const x5secMatch = result.cookies.match(/(?:^|;\s*)x5sec=([^;]+)/);
      if (x5secMatch) {
        result.x5sec = x5secMatch[1];
        console.log(`[SliderSolver] requestId=${requestId} ✓ 从 Playwright cookies 中提取到 x5sec (长度=${x5secMatch[1].length})`);
      }
    }

    // 第二阶段：Python patchright fallback
    // 触发条件：Playwright 求解失败，且失败原因不是 cookie_invalid（Cookie 失效时 Python 也救不了）
    // 排除：cookie_invalid / account_inactive / account_disabled / precheck_rejected
    const isCookieInvalid = playwrightResult.error && (
      playwrightResult.error.includes('Cookie Session') ||
      playwrightResult.error.includes('Cookie 已过期') ||
      playwrightResult.error.includes('FAIL_SYS_SESSION_EXPIRED')
    );
    const shouldUsePythonFallback = !playwrightResult.ok && !playwrightResult.solved && !isCookieInvalid;

    if (shouldUsePythonFallback) {
      console.log(`[SliderSolver] requestId=${requestId} Playwright 失败（非 Cookie 失效），启动 Python patchright fallback`);
      console.log(`[SliderSolver] Playwright 失败原因: ${playwrightResult.error?.substring(0, 150)}`);

      const pythonResult = await solveWithPythonPatchright({
        cookieStr,
        targetUrl: safeTargetUrl,
        proxy: safeProxy,
        maxRetries: 3,  // 2026-08-01 优化：3 次拖动（punish 状态 2 次 + 非 punish 1 次）
      });

      console.log(`[SliderSolver-Python] 结果: solved=${pythonResult.solved} ok=${pythonResult.ok} duration=${pythonResult.durationMs}ms error=${pythonResult.error?.substring(0, 100)}`);

      if (pythonResult.solved) {
        // Python 求解成功，使用 Python 结果
        result = {
          ok: true,
          solved: true,
          captchaDetected: pythonResult.captchaDetected,
          attempts: playwrightResult.attempts + pythonResult.attempts,
          durationMs: playwrightResult.durationMs + pythonResult.durationMs,
          cookies: pythonResult.cookies,
          x5sec: pythonResult.x5sec,
        };
        // 如果获取到 x5sec，记录日志（用于调试缓存复用方案）
        if (pythonResult.x5sec) {
          console.log(`[SliderSolver] requestId=${requestId} ✓ 获取到 x5sec (长度=${pythonResult.x5sec.length})，可缓存用于后续免滑块请求`);
        }
      } else {
        // Python 也失败，合并错误信息
        result = {
          ok: false,
          solved: false,
          captchaDetected: playwrightResult.captchaDetected || pythonResult.captchaDetected,
          attempts: playwrightResult.attempts + pythonResult.attempts,
          error: `Playwright: ${playwrightResult.error?.substring(0, 100)} | Python: ${pythonResult.error?.substring(0, 100)}`,
          durationMs: playwrightResult.durationMs + pythonResult.durationMs,
        };
      }
    }

    // 注意：滑块求解接口不复用 toPublicCrawlerError 改写规则。
    // 该改写规则仅适用于采集类接口（搜索/详情/店铺爬取），用于告诉用户"采集被风控，先去验证"。
    // 滑块求解本身就是验证流程，套用该规则会出现"求解失败 → 请先完成验证"的自相矛盾提示，
    // 且会掩盖真实的失败原因（如"未找到滑块按钮"、"Cookie Session 已过期"等）。
    // 这里直接返回原始 error 字段，由前端根据 failureReason 分类展示。

    // 2026-08-01 优化：求解成功后缓存 x5sec，后续请求可直接复用（免滑块）
    if (result.solved && result.x5sec) {
      try {
        await cacheX5sec(cookieStr, result.x5sec);
      } catch (e: any) {
        console.warn(`[SliderSolver] requestId=${(req as RequestWithTrace).requestId} x5sec 缓存写入失败: ${e?.message || e}`);
      }
    } else if (result.solved && result.cookies) {
      // 如果 result.x5sec 为空但 cookies 中包含 x5sec，尝试从 cookies 提取并缓存
      const x5secMatch = result.cookies.match(/(?:^|;\s*)x5sec=([^;]+)/);
      if (x5secMatch && x5secMatch[1]) {
        result.x5sec = x5secMatch[1];
        try {
          await cacheX5sec(cookieStr, result.x5sec);
        } catch (e: any) {
          console.warn(`[SliderSolver] requestId=${(req as RequestWithTrace).requestId} x5sec 缓存写入失败: ${e?.message || e}`);
        }
      }
    }

    const response = {
      ...result,
      ...(productionLike ? { screenshotPath: undefined } : {}),
    };
    return res.status(result.ok ? 200 : 422).json(response);
  } catch (e: any) {
    console.error(`[SliderSolver] requestId=${(req as RequestWithTrace).requestId} errorType=${safeErrorType(e)}`);
    return res.status(500).json({
      ok: false,
      // 直接返回原始异常消息，便于前端诊断；兜底文案仅在消息为空时使用
      error: (e instanceof Error && e.message) ? e.message : '滑块验证处理失败，请稍后重试',
      solved: false,
      captchaDetected: false,
      attempts: 0,
      durationMs: 0,
    });
  }
});

// ---- POST /api/goofish/x5sec-cache ----  x5sec 缓存管理（查询/清除）
// 用于调试和手动管理 x5sec 缓存：
// - GET: 查询 cookie 对应的缓存 x5sec（不返回明文，只返回长度和前10字符）
// - DELETE: 清除 cookie 对应的 x5sec 缓存（下次请求会重新触发滑块求解）
app.post('/api/goofish/x5sec-cache', async (req, res) => {
  try {
    const action = String(req.body?.action || 'get').toLowerCase();
    let cookieStr: string;
    try {
      cookieStr = normalizeCookieInput(req.body?.cookie);
    } catch (error) {
      return res.status(400).json({ ok: false, error: error instanceof Error ? error.message : 'Cookie is invalid' });
    }

    if (action === 'get') {
      const cached = await getCachedX5sec(cookieStr);
      const hasInCookie = cookieHasX5sec(cookieStr);
      return res.json({
        ok: true,
        cached: !!cached,
        cachedLength: cached?.length || 0,
        cachedPreview: cached ? cached.substring(0, 10) + '...' : null,
        inCookie: hasInCookie,
      });
    } else if (action === 'inject') {
      // 2026-08-02 新增：返回注入 x5sec 后的 cookie，供 automation-service WS 重连前使用
      if (cookieHasX5sec(cookieStr)) {
        return res.json({ ok: true, injected: false, reason: 'cookie_already_has_x5sec', cookie: cookieStr });
      }
      const cached = await getCachedX5sec(cookieStr);
      if (!cached) {
        return res.json({ ok: true, injected: false, reason: 'cache_miss', cookie: cookieStr });
      }
      const enhancedCookie = injectX5secIntoCookie(cookieStr, cached);
      console.log(`[X5secCache] inject 请求命中缓存，返回注入后的 cookie (长度=${enhancedCookie.length})`);;
      return res.json({ ok: true, injected: true, reason: 'cache_hit', cookie: enhancedCookie, x5sec: cached, x5secLength: cached.length });
    } else if (action === 'evict' || action === 'delete') {
      await evictCachedX5sec(cookieStr);
      return res.json({ ok: true, evicted: true });
    } else {
      return res.status(400).json({ ok: false, error: `未知的 action: ${action}（支持: get, inject, evict）` });
    }
  } catch (e: any) {
    return res.status(500).json({ ok: false, error: safeErrorType(e) });
  }
});

// ---- Health ----
app.get('/api/health', (_req, res) => {
  res.json({ status: 'ok', service: 'crawler-service', check: 'liveness' });
});

// ---- 进程监测健康端点：查看当前注册的求解进程和最近清理日志 ----
app.get('/api/health/processes', (_req, res) => {
  const entries = processRegistry.list();
  const cleanupLog = processRegistry.getCleanupLog();
  const now = Date.now();
  res.json({
    status: 'ok',
    timestamp: now,
    activeSessions: entries.map((e) => ({
      sessionId: e.sessionId,
      kind: e.kind,
      pid: e.pid || null,
      childPids: e.childPids,
      hasUserDataDir: !!e.userDataDir,
      tenantId: e.tenantId,
      startedAt: e.startedAt,
      deadlineAt: e.deadlineAt,
      lastActivityAt: e.lastActivityAt,
      ageMs: now - e.startedAt,
      overdueMs: Math.max(0, now - e.deadlineAt),
      description: e.description,
    })),
    activeCount: entries.length,
    recentCleanups: cleanupLog.slice(-20).map((a) => ({
      sessionId: a.sessionId,
      pid: a.pid,
      reason: a.reason,
      result: a.result,
      ageMs: a.ageMs,
      overdueMs: a.overdueMs,
      timestamp: a.timestamp,
    })),
    cleanupLogCount: cleanupLog.length,
  });
});

app.get('/api/ready', async (_req, res) => {
  const dependencies = { database: false, redis: false };
  try {
    await getPool().query('SELECT 1');
    dependencies.database = true;
  } catch {
  }
  try {
    await Promise.race([
      goofishCrawlQueue.waitUntilReady(),
      new Promise((_, reject) => setTimeout(() => reject(new Error('readiness timeout')), 3000)),
    ]);
    dependencies.redis = true;
  } catch {
  }
  const ready = internalTokenPolicy.ready && redisPasswordPolicy.ready
    && queueEncryptionReady && corsConfigurationReady && dependencies.database && dependencies.redis;
  return res.status(ready ? 200 : 503).json({
    status: ready ? 'ready' : 'unavailable',
    service: 'crawler-service',
    dependencies,
    configuration: {
      internalAuth: internalTokenPolicy.ready,
      redisAuth: redisPasswordPolicy.ready,
      queueEncryption: queueEncryptionReady,
      cors: corsConfigurationReady,
    },
  });
});

// ---- 扫码登录求解器 ----
// POST /api/qrlogin/solve
// 完整流程：启动浏览器 → 拦截二维码 → 等待用户扫码 → 提取 Cookie → 关闭浏览器
// 请求体: { sessionId, scanTimeoutMs? }
// 响应: { ok, stage, cookieStr?, unb?, mH5Tk?, error?, durationMs }
app.post('/api/qrlogin/solve', async (req, res) => {
  let sessionId = '';
  try {
    const tenantId = tenantIdFrom(req);
    sessionId = typeof req.body?.sessionId === 'string' ? req.body.sessionId.trim() : '';
    if (!/^[a-f0-9]{32}$/.test(sessionId)) {
      return res.status(400).json({ ok: false, error: '二维码登录会话 ID 无效' });
    }
    const session = qrLoginSessions.get(sessionId);
    if (!session || session.tenantId !== tenantId) {
      return res.status(404).json({ ok: false, error: '二维码登录会话不存在或已过期' });
    }
    if (session.expiresAt <= Date.now()) {
      await closeQrLoginSession(sessionId);
      return res.status(410).json({ ok: false, error: '二维码登录会话已过期，请重新获取二维码' });
    }
    if (session.consuming) {
      return res.status(409).json({ ok: false, error: '二维码登录会话正在处理中' });
    }
    const remainingLifetime = session.expiresAt - Date.now();
    if (remainingLifetime < 10000) {
      await closeQrLoginSession(sessionId);
      return res.status(410).json({ ok: false, error: '二维码登录会话即将过期，请重新获取二维码' });
    }
    session.consuming = true;
    const timeout = Number(req.body?.scanTimeoutMs ?? 120000);
    const requestedTimeout = Number.isSafeInteger(timeout) ? timeout : 120000;
    const scanTimeoutMs = Math.max(10000, Math.min(requestedTimeout, Math.min(300000, remainingLifetime)));
    const result = await completeQrLoginSession(session.context, session.page, scanTimeoutMs);
    const response = {
      ...result,
      ...(result.error ? { error: toPublicCrawlerError(result.error, '二维码登录处理失败') } : {}),
    };
    return res.status(result.ok ? 200 : result.stage === 'timeout' ? 408 : 422).json(response);
  } catch (error) {
    console.error(`[QrLoginSolver] requestId=${(req as RequestWithTrace).requestId} operation=solve errorType=${safeErrorType(error)}`);
    return res.status(500).json({ ok: false, error: '二维码登录处理失败，请稍后重试' });
  } finally {
    if (sessionId && qrLoginSessions.get(sessionId)?.consuming) {
      await closeQrLoginSession(sessionId);
    }
  }
});

// POST /api/qrlogin/capture
// 仅捕获二维码图片（不等待扫码完成），用于"用户在飞书回复请求二维码"场景
// 响应: { ok, qrImageBase64?, error? }
// 注意：调用方应在收到二维码后再次调用 /api/qrlogin/solve 完成完整登录流程
app.post('/api/qrlogin/capture', async (req, res) => {
  try {
    const tenantId = tenantIdFrom(req);
    const { cookie, targetUrl, headless } = req.body || {};
    let cookieStr: string;
    try {
      cookieStr = normalizeCookieInput(cookie);
    } catch (error) {
      return res.status(400).json({ ok: false, error: error instanceof Error ? error.message : 'Cookie is invalid' });
    }
    let safeTargetUrl;
    try {
      safeTargetUrl = normalizeGoofishTargetUrl(targetUrl);
    } catch (e: any) {
      return res.status(400).json({ ok: false, error: e?.message || '目标 URL 无效' });
    }
    if (tenantQrSessionReservations.has(tenantId)) {
      return res.status(409).json({ ok: false, error: '当前租户已有二维码登录会话，请先完成或取消' });
    }
    tenantQrSessionReservations.add(tenantId);
    const releaseBrowser = tryAcquireBrowserSlot(tenantId);
    if (!releaseBrowser) {
      tenantQrSessionReservations.delete(tenantId);
      return browserCapacityUnavailable(res);
    }
    let result: Awaited<ReturnType<typeof captureQrCodeOnly>> | undefined;
    let sessionRegistered = false;
    try {
      result = await captureQrCodeOnly({
        cookieStr,
        targetUrl: safeTargetUrl,
        headless: productionLike ? (isHeadedDisplayAvailable() ? false : true) : headless,
      });
      if (!result.qrImageBytes || !result.browser || !result.context || !result.page) {
        const error = result.error
          ? toPublicCrawlerError(result.error, '未能捕获登录二维码')
          : '当前账号无需扫码或二维码尚未就绪，请稍后重试';
        return res.status(422).json({ ok: false, error });
      }

      const sessionId = crypto.randomUUID().replace(/-/g, '');
      const expiresAt = Date.now() + QR_SESSION_TTL_MS;
      const timer = setTimeout(() => void closeQrLoginSession(sessionId), QR_SESSION_TTL_MS);
      timer.unref();
      qrLoginSessions.set(sessionId, {
        tenantId,
        browser: result.browser,
        context: result.context,
        page: result.page,
        expiresAt,
        consuming: false,
        timer,
        releaseBrowser,
      });
      sessionRegistered = true;
      return res.status(200).json({
        ok: true,
        sessionId,
        expiresAt: new Date(expiresAt).toISOString(),
        qrImageBase64: result.qrImageBytes.toString('base64'),
      });
    } finally {
      if (!sessionRegistered) {
        tenantQrSessionReservations.delete(tenantId);
        await Promise.allSettled([
          result?.context?.close() ?? Promise.resolve(),
          result?.browser?.close() ?? Promise.resolve(),
        ]);
        releaseBrowser();
      }
    }
  } catch (e: any) {
    console.error(`[QrLoginSolver] requestId=${(req as RequestWithTrace).requestId} operation=capture errorType=${safeErrorType(e)}`);
    return res.status(500).json({ ok: false, error: toPublicCrawlerError(e, '二维码捕获失败') });
  }
});

app.post('/api/qrlogin/cancel', async (req, res) => {
  try {
    const tenantId = tenantIdFrom(req);
    const sessionId = typeof req.body?.sessionId === 'string' ? req.body.sessionId.trim() : '';
    if (!/^[a-f0-9]{32}$/.test(sessionId)) {
      return res.status(400).json({ ok: false, error: '二维码登录会话 ID 无效' });
    }
    const session = qrLoginSessions.get(sessionId);
    if (!session || session.tenantId !== tenantId) {
      return res.status(404).json({ ok: false, error: '二维码登录会话不存在或已过期' });
    }
    await closeQrLoginSession(sessionId);
    return res.status(200).json({ ok: true });
  } catch (error) {
    console.error(`[QrLoginSolver] requestId=${(req as RequestWithTrace).requestId} operation=cancel errorType=${safeErrorType(error)}`);
    return res.status(500).json({ ok: false, error: '取消二维码登录会话失败' });
  }
});

app.use((_req, res) => {
  return res.status(404).json({ ok: false, error: 'not found' });
});

app.use((error: unknown, _req: Request, res: Response, next: NextFunction) => {
  if (res.headersSent) return next(error);
  const candidate = error as { type?: string; message?: string };
  const status = candidate?.type === 'entity.parse.failed'
    ? 400
    : candidate?.message === 'CORS origin denied' ? 403 : 500;
  console.error(`[Crawler] operation=requestMiddleware errorType=${safeErrorType(error)} status=${status}`);
  return res.status(status).json({
    ok: false,
    error: status === 400 ? 'invalid JSON request body' : status === 403 ? 'forbidden' : 'internal service error',
  });
});

// 启动
async function start() {
  // 全局未捕获异常处理器：防止异步回调异常导致进程静默退出
  process.on('unhandledRejection', (reason) => {
    console.error('[Server] unhandledRejection:', reason);
  });
  process.on('uncaughtException', (err) => {
    console.error('[Server] uncaughtException:', err);
    // 不主动退出进程，避免 BullMQ 定时器/Playwright 回调的偶发异常导致服务中断
  });

  if (!internalTokenPolicy.ready) {
    throw new Error(internalTokenPolicy.reason || 'internal authentication configuration is invalid');
  }
  if (!redisPasswordPolicy.ready) {
    throw new Error(redisPasswordPolicy.reason || 'Redis authentication configuration is invalid');
  }
  if (!queueEncryptionReady) {
    throw new Error('COOKIE_CRYPTO_SECRET is missing or unsafe');
  }
  if (!corsConfigurationReady) {
    throw new Error('CORS_ALLOWED_ORIGINS must contain explicit HTTPS origins in production');
  }
  let databaseReady = true;
  try {
    await runMigrations();
    console.log('[Server] 数据库结构校验完成');
  } catch (e: any) {
    databaseReady = false;
    console.error(`[Server] operation=prepareDatabaseSchema errorType=${safeErrorType(e)}`);
    if (productionLike) {
      throw new Error('数据库迁移失败，生产环境拒绝启动');
    }
    console.warn('[Server] 开发环境以降级模式继续运行；/api/ready 将返回 503，数据库功能不可用');
  }

  let queueReady = true;
  try {
    await Promise.race([
      goofishCrawlQueue.waitUntilReady(),
      new Promise((_, reject) => setTimeout(() => reject(new Error('queue startup timeout')), 10000)),
    ]);
  } catch (error) {
    queueReady = false;
    console.error(`[Server] operation=connectQueue errorType=${safeErrorType(error)}`);
    if (productionLike) throw new Error('采集队列不可用，生产环境拒绝启动');
  }
  if (databaseReady && queueReady) await reconcileOrphanedCrawlJobs();

  const reconciliationTimer = databaseReady && queueReady
    ? setInterval(() => {
      void reconcileOrphanedCrawlJobs().catch((error) => {
        console.error(`[Server] operation=reconcileJobs errorType=${safeErrorType(error)}`);
      });
    }, 300000)
    : undefined;
  reconciliationTimer?.unref();

  // 定期清理孤儿 Chrome 进程：Chrome 崩溃后 Playwright 连接断开，close() 失败导致子进程残留。
  // 这些进程被 init 收养（PPID=1），累积会耗尽资源导致新 Chrome 无法启动（恶性循环）。
  //
  // 清理策略（四路并发）：
  //   1. PPID=1 的 Chrome 进程：被 init 收养的孤儿，直接 SIGKILL
  //   2. 父进程已退出（PPID 不在存活进程集合中）的 Chrome 进程：真正的孤儿定义，比仅匹配 PPID=1 更全面
  //   3. Z 状态（僵尸）的 Chrome 进程：父进程已退出但 waitpid 未调用，SIGKILL 无效需用 kill -9
  //   4. 运行时间超过 STALE_CHROME_TTL_SEC 的 Chrome 主进程：即使父进程存活也清理
  //      （解决 Playwright 崩溃后 Chrome 残留但 PPID 仍为主进程的情况，原逻辑无法清理）
  //
  // 间隔：30 秒（原 2 分钟太长，洪峰期间 30 秒内孤儿就可能累积到 PIDS 耗尽）
  // 安全：只匹配 /opt/google/chrome/chrome 路径，不影响其他 Node/Playwright 父进程的 Chrome
  const STALE_CHROME_TTL_SEC = 300; // 5 分钟：正常求解最多 2-3 分钟，超过 5 分钟视为泄漏
  let orphanCleanerTimer: NodeJS.Timeout | undefined;
  if (process.platform !== 'win32' && process.platform !== 'darwin') {
    let orphanCleanerRunCount = 0;
    const cleanOrphanChrome = () => {
      orphanCleanerRunCount += 1;
      try {
        const { execSync } = require('child_process') as { execSync: (cmd: string, opts?: { encoding?: string; timeout?: number }) => string };
        // 获取所有存活进程的 PID 集合（用于判断 Chrome 进程的父进程是否还存活）
        const allPidsOutput = execSync('ps -eo pid --no-headers', { encoding: 'utf-8', timeout: 5000 });
        const alivePidSet = new Set(
          allPidsOutput.trim().split('\n').map((s: string) => Number(s.trim())).filter((n: number) => n > 0),
        );

        // 获取所有 Chrome 进程的 pid,ppid,stat,etimes(运行秒数),cmd
        // etimes 是整数秒数，比 etime（[[DD-]hh:]mm:ss 格式）更容易解析
        const chromeOutput = execSync(
          "ps -eo pid,ppid,stat,etimes,cmd --no-headers | grep '/opt/google/chrome/chrome' | grep -v grep",
          { encoding: 'utf-8', timeout: 5000 },
        );

        const orphanPids: number[] = [];
        const zombiePids: number[] = [];
        const stalePids: number[] = []; // 运行时间超过阈值的 Chrome 主进程
        for (const line of chromeOutput.trim().split('\n')) {
          if (!line.trim()) continue;
          const parts = line.trim().split(/\s+/);
          const pid = Number(parts[0]);
          const ppid = Number(parts[1]);
          const stat = parts[2] || '';
          const etimes = Number(parts[3] || 0);
          if (!Number.isSafeInteger(pid) || pid < 100) continue; // 系统进程保护
          // Z 状态（僵尸）
          if (stat.startsWith('Z')) {
            zombiePids.push(pid);
            continue;
          }
          // PPID=1（被 init 收养）或父进程已退出（PPID 不在存活集合中）→ 孤儿
          if (ppid === 1 || !alivePidSet.has(ppid)) {
            orphanPids.push(pid);
            continue;
          }
          // 运行时间超过阈值的 Chrome 主进程（不含 --type=renderer 等子进程）
          // 关键修复：原逻辑只清理 PPID=1 的孤儿，但 Playwright 崩溃后 Chrome 的 PPID 仍为 crawler-service 主进程
          // 这些进程永远不会被清理，导致 PIDS 耗尽。现在按运行时间兜底清理。
          if (etimes >= STALE_CHROME_TTL_SEC && !line.includes('--type=')) {
            stalePids.push(pid);
          }
        }

        if (orphanPids.length === 0 && zombiePids.length === 0 && stalePids.length === 0) {
          // 每 60 次（约 30 分钟）输出一次无孤儿确认日志，便于诊断清理器在运行
          if (orphanCleanerRunCount % 60 === 0) {
            console.log(`[OrphanCleaner] 第 ${orphanCleanerRunCount} 次扫描：无孤儿/僵尸/超时 Chrome 进程`);
          }
          return;
        }

        const allPids = [...new Set([...orphanPids, ...zombiePids, ...stalePids])];
        console.log(
          `[OrphanCleaner] 第 ${orphanCleanerRunCount} 次扫描：孤儿=${orphanPids.length} 僵尸=${zombiePids.length} 超时=${stalePids.length}，正在清理: ${allPids.join(', ')}`,
        );
        for (const pid of allPids) {
          // 僵尸/孤儿/超时都用 SIGKILL
          try { process.kill(pid, 'SIGKILL'); } catch { /* 进程已退出或权限不足，忽略 */ }
        }
      } catch {
        // ps 失败（无 chrome 进程或命令不可用）时静默
      }
    };
    // 启动后立即执行一次清理（重启时可能残留上次未清理的进程）
    cleanOrphanChrome();
    orphanCleanerTimer = setInterval(cleanOrphanChrome, 30 * 1000);
    orphanCleanerTimer.unref();
  }

  // 启动滑块求解进程监测器：定期扫描注册表，清理超时/已结束的求解进程
  // 安全策略：只清理注册表中的 PID，PID < 100 不清理，优先 SIGTERM 再 SIGKILL
  processMonitor.start();

  const server = app.listen(PORT, () => {
    console.log(`[Server] 爬虫服务已启动: port=${PORT}`);
  });

  let shuttingDown = false;
  const shutdown = async (signal: string) => {
    if (shuttingDown) return;
    shuttingDown = true;
    console.log(`[Server] 收到退出信号: signal=${signal}`);
    const forcedExit = setTimeout(() => {
      console.error('[Server] graceful shutdown timed out');
      process.exit(1);
    }, 30000);
    forcedExit.unref();
    if (reconciliationTimer) clearInterval(reconciliationTimer);
    if (orphanCleanerTimer) clearInterval(orphanCleanerTimer);
    processMonitor.stop();
    const serverClosed = new Promise<void>((resolve) => server.close(() => resolve()));
    await closeAllQrLoginSessions();
    await serverClosed;
    await Promise.allSettled([closeQueue(), closePool(), closeX5secCache()]);
    clearTimeout(forcedExit);
  };
  process.once('SIGTERM', () => void shutdown('SIGTERM'));
  process.once('SIGINT', () => void shutdown('SIGINT'));
}

start().catch(async (error) => {
  console.error(`[Server] operation=start errorType=${safeErrorType(error)}`);
  await Promise.allSettled([closeAllQrLoginSessions(), closeQueue(), closePool(), closeX5secCache()]);
  process.exitCode = 1;
});
