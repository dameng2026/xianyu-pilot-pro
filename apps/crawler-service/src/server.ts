import express, { type NextFunction, type Request, type Response } from 'express';
import cors from 'cors';
import crypto from 'crypto';
import type { Browser, BrowserContext, Page } from 'playwright';
import { parseGoofishStoreUrl } from './crawler/parseGoofishStoreUrl.js';
import { closeQueue, goofishCrawlQueue } from './queue/index.js';
import { assertQueueCookieEncryptionReady, encryptQueueCookie } from './queue/secretEnvelope.js';
import { closePool, getPool, runMigrations } from './db/index.js';
import { crawlGoofishSearch } from './crawler/goofishSearch.js';
import { fetchGoofishItemDetail } from './crawler/goofishItemDetail.js';
import { resolveStoreUserId } from './crawler/goofish.js';
import { solveGoofishSlider } from './crawler/sliderSolver.js';
import { captureQrCodeOnly, completeQrLoginSession } from './crawler/qrLoginSolver.js';
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
const MAX_BROWSER_CONCURRENCY = boundedConfigInteger(process.env.CRAWLER_BROWSER_CONCURRENCY, 4, 1, 16);
const MAX_BROWSER_CONCURRENCY_PER_TENANT = boundedConfigInteger(
  process.env.CRAWLER_BROWSER_CONCURRENCY_PER_TENANT,
  Math.min(2, MAX_BROWSER_CONCURRENCY),
  1,
  MAX_BROWSER_CONCURRENCY,
);
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
  return () => {
    if (released) return;
    released = true;
    activeBrowserOperations = Math.max(0, activeBrowserOperations - 1);
    const remaining = Math.max(0, (activeBrowserOperationsByTenant.get(tenantId) || 1) - 1);
    if (remaining === 0) activeBrowserOperationsByTenant.delete(tenantId);
    else activeBrowserOperationsByTenant.set(tenantId, remaining);
  };
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
  const candidates = await pool.query(
    `SELECT tenant_id, bullmq_job_id
     FROM goofish_crawl_jobs
     WHERE status IN ('pending', 'running') AND created_at < NOW() - INTERVAL '1 minute'
     ORDER BY created_at ASC LIMIT 500`,
  );
  let repaired = 0;
  for (const row of candidates.rows) {
    if (await isQueueJobActive(String(row.bullmq_job_id || ''))) continue;
    const result = await pool.query(
      `UPDATE goofish_crawl_jobs
       SET status = 'failed', error_message = '队列任务不存在，请重新提交',
           finished_at = NOW(), execution_token = NULL
       WHERE tenant_id = $1 AND bullmq_job_id = $2 AND status IN ('pending', 'running')`,
      [row.tenant_id, row.bullmq_job_id],
    );
    repaired += result.rowCount || 0;
  }
  if (repaired > 0) console.warn(`[Server] 已修复孤立采集任务: count=${repaired}`);
}

function requireInternalAuth(req: Request, res: Response, next: NextFunction) {
  if (req.path === '/api/health' || req.path === '/api/ready') return next();

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
    const releaseBrowser = tryAcquireBrowserSlot(tenantId);
    if (!releaseBrowser) return browserCapacityUnavailable(res);
    try {
      const detail = await fetchGoofishItemDetail(itemId, cookieStr);
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
    const recent = await pool.query(
      `SELECT bullmq_job_id, status, item_count, created_at FROM goofish_crawl_jobs
       WHERE tenant_id = $1
         AND store_user_id = $2
         AND status IN ('pending', 'running', 'completed')
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
      if (row.status === 'pending' || row.status === 'running') {
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
           WHERE tenant_id = $1 AND bullmq_job_id = $2 AND status IN ('pending', 'running')`,
          [tenantId, row.bullmq_job_id],
        );
      }
    }

    await pool.query(
      `UPDATE goofish_crawl_jobs
       SET status = 'failed', error_message = '采集任务超时，请重新提交', finished_at = NOW()
       WHERE tenant_id = $1 AND store_user_id = $2
         AND status IN ('pending', 'running')
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
         WHERE tenant_id = $1 AND store_user_id = $2 AND status IN ('pending', 'running')
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
           WHERE tenant_id = $1 AND bullmq_job_id = $2 AND status IN ('pending', 'running')`,
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
    if ((row.status === 'pending' || row.status === 'running') && !isFreshPublishingRow(row.created_at)) {
      try {
        if (!await isQueueJobActive(String(row.bullmq_job_id || ''))) {
          await pool.query(
            `UPDATE goofish_crawl_jobs
             SET status = 'failed', error_message = '队列任务不存在，请重新提交',
                 finished_at = NOW(), execution_token = NULL
             WHERE tenant_id = $1 AND bullmq_job_id = $2 AND status IN ('pending', 'running')`,
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
    const { cookie, targetUrl, headless, maxRetries, timeoutMs } = req.body || {};
    let cookieStr: string;
    try {
      cookieStr = normalizeCookieInput(cookie);
    } catch (error) {
      return res.status(400).json({ ok: false, error: error instanceof Error ? error.message : 'Cookie is invalid' });
    }
    const resolvedHeadless = productionLike ? true : (typeof headless === 'boolean' ? headless : undefined);
    let safeTargetUrl;
    try {
      safeTargetUrl = normalizeGoofishTargetUrl(targetUrl);
    } catch (e: any) {
      return res.status(400).json({ ok: false, error: e?.message || '目标 URL 无效' });
    }

    console.log(`[SliderSolver] requestId=${(req as RequestWithTrace).requestId} tenantId=${tenantId} hasCookie=${!!cookieStr} targetHost=${safeTargetUrl ? new URL(safeTargetUrl).hostname : 'default'}`);

    const releaseBrowser = tryAcquireBrowserSlot(tenantId);
    if (!releaseBrowser) return browserCapacityUnavailable(res);
    const result = await (async () => {
      try {
        return await solveGoofishSlider({
          cookieStr,
          targetUrl: safeTargetUrl,
          headless: resolvedHeadless,
          maxRetries: Math.max(1, Math.min(Number(maxRetries) || 3, 5)),
          timeoutMs: Math.max(5000, Math.min(Number(timeoutMs) || 30000, 120000)),
        });
      } finally {
        releaseBrowser();
      }
    })();

    const response = {
      ...result,
      ...(result.error ? { error: toPublicCrawlerError(result.error, '滑块验证处理失败，请稍后重试') } : {}),
      ...(productionLike ? { screenshotPath: undefined } : {}),
    };
    return res.status(result.ok ? 200 : 422).json(response);
  } catch (e: any) {
    console.error(`[SliderSolver] requestId=${(req as RequestWithTrace).requestId} errorType=${safeErrorType(e)}`);
    return res.status(500).json({
      ok: false,
      error: toPublicCrawlerError(e, '滑块验证处理失败，请稍后重试'),
      solved: false,
      captchaDetected: false,
      attempts: 0,
      durationMs: 0,
    });
  }
});

// ---- Health ----
app.get('/api/health', (_req, res) => {
  res.json({ status: 'ok', service: 'crawler-service', check: 'liveness' });
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
        headless: productionLike ? true : headless,
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
    const serverClosed = new Promise<void>((resolve) => server.close(() => resolve()));
    await closeAllQrLoginSessions();
    await serverClosed;
    await Promise.allSettled([closeQueue(), closePool()]);
    clearTimeout(forcedExit);
  };
  process.once('SIGTERM', () => void shutdown('SIGTERM'));
  process.once('SIGINT', () => void shutdown('SIGINT'));
}

start().catch(async (error) => {
  console.error(`[Server] operation=start errorType=${safeErrorType(error)}`);
  await Promise.allSettled([closeAllQrLoginSessions(), closeQueue(), closePool()]);
  process.exitCode = 1;
});
