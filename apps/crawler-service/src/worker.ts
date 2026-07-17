import crypto from 'crypto';
import { closeQueue, createWorker } from './queue/index.js';
import {
  assertQueueCookieEncryptionReady,
  decryptQueueCookie,
} from './queue/secretEnvelope.js';
import { crawlGoofishStoreDetailed } from './crawler/goofish.js';
import { saveCrawlResult, markCrawlJobFailed, markCrawlJobRetrying } from './db/saveItems.js';
import { closePool, getPool, runMigrations } from './db/index.js';
import {
  normalizeCookieInput,
  normalizeTenantId,
  resolveRedisPasswordPolicy,
  safeErrorType,
  toPublicCrawlerError,
} from './policy.js';

async function start() {
  // 全局未捕获异常处理器：防止异步回调异常导致进程静默退出
  process.on('unhandledRejection', (reason) => {
    console.error('[Worker] unhandledRejection:', reason);
  });
  process.on('uncaughtException', (err) => {
    console.error('[Worker] uncaughtException:', err);
  });

  const environment = process.env.NODE_ENV || process.env.APP_ENV || 'development';
  const redisPasswordPolicy = resolveRedisPasswordPolicy(process.env.REDIS_PASSWORD, environment);
  if (!redisPasswordPolicy.ready) {
    throw new Error(redisPasswordPolicy.reason || 'Redis authentication configuration is invalid');
  }
  assertQueueCookieEncryptionReady();
  try {
    await runMigrations();
    console.log('[Worker] 数据库结构校验完成');
  } catch (e: any) {
    console.error(`[Worker] operation=prepareDatabaseSchema errorType=${safeErrorType(e)}`);
    throw new Error('数据库迁移失败，Worker 拒绝启动');
  }

  const worker = createWorker(async (job) => {
    const data = job.data as { tenantId?: unknown; cookieEnvelope?: unknown };
    const tenantId = normalizeTenantId(data.tenantId);
    const jobId = job.id!;

    if (!jobId || !/^[A-Za-z0-9_-]{1,128}$/.test(jobId)) {
      throw new Error('任务载荷无效，已拒绝处理');
    }

    console.log(`[Worker] 开始处理任务: tenantId=${tenantId}, jobId=${jobId}`);

    const pool = getPool();
    const executionToken = crypto.randomUUID().replace(/-/g, '');
    const claimed = await pool.query(
      `UPDATE goofish_crawl_jobs
       SET status = 'running', started_at = NOW(), execution_token = $3
       WHERE tenant_id = $1 AND bullmq_job_id = $2
         AND status IN ('pending', 'running')
       RETURNING bullmq_job_id, store_user_id`,
      [tenantId, jobId, executionToken]
    );
    if (claimed.rowCount !== 1) {
      throw new Error('任务记录不存在或状态不允许执行');
    }

    const storeUserId = String(claimed.rows[0].store_user_id || '');
    try {
      if (!/^\d{1,32}$/.test(storeUserId)) throw new Error('数据库任务店铺标识无效');
      const cookieEnvelope = typeof data.cookieEnvelope === 'string' ? data.cookieEnvelope : undefined;
      const cookie = normalizeCookieInput(decryptQueueCookie(cookieEnvelope, `${tenantId}:${jobId}`));
      const url = `https://www.goofish.com/personal?userId=${storeUserId}`;
      const result = await crawlGoofishStoreDetailed(url, cookie);
      await saveCrawlResult(tenantId, storeUserId, url, result.items, jobId, executionToken);
      console.log(
        `[Worker] 任务完成: tenantId=${tenantId}, jobId=${jobId}, items=${result.items.length}, expected=${result.diagnostics.expectedItemCount ?? 'unknown'}, network=${result.diagnostics.networkCandidateCount}, dom=${result.diagnostics.domCandidateCount}`
      );
    } catch (err: any) {
      const configuredAttempts = Number(job.opts.attempts || 1);
      const maxAttempts = Number.isSafeInteger(configuredAttempts)
        ? Math.max(1, Math.min(configuredAttempts, 10)) : 1;
      const currentAttempt = Math.max(1, Number(job.attemptsMade || 0) + 1);
      console.error(
        `[Worker] 任务失败: tenantId=${tenantId}, jobId=${jobId}, attempt=${currentAttempt}/${maxAttempts}, errorType=${safeErrorType(err)}`
      );
      const publicError = toPublicCrawlerError(err, '采集任务执行失败');
      try {
        if (currentAttempt < maxAttempts) {
          await markCrawlJobRetrying(
            tenantId, jobId, storeUserId, publicError, currentAttempt, maxAttempts, executionToken,
          );
        } else {
          await markCrawlJobFailed(tenantId, jobId, storeUserId, publicError, executionToken);
        }
      } catch (stateError) {
        console.error(`[Worker] operation=recordFailure jobId=${jobId} errorType=${safeErrorType(stateError)}`);
      }
      throw err;
    }
  });

  try {
    await Promise.race([
      worker.waitUntilReady(),
      new Promise((_, reject) => setTimeout(() => reject(new Error('worker startup timeout')), 10000)),
    ]);
  } catch (error) {
    await worker.close(true);
    throw error;
  }
  console.log('[Worker] 爬虫 Worker 已启动，等待任务...');

  let shuttingDown = false;
  const shutdown = async (signal: string) => {
    if (shuttingDown) return;
    shuttingDown = true;
    console.log(`[Worker] 收到退出信号: signal=${signal}`);
    const forcedExit = setTimeout(() => {
      console.error('[Worker] graceful shutdown timed out');
      process.exit(1);
    }, 30000);
    forcedExit.unref();
    await worker.close();
    await Promise.allSettled([closeQueue(), closePool()]);
    clearTimeout(forcedExit);
  };
  process.once('SIGTERM', () => void shutdown('SIGTERM'));
  process.once('SIGINT', () => void shutdown('SIGINT'));
}

start().catch(async (error) => {
  console.error(`[Worker] operation=start errorType=${safeErrorType(error)}`);
  await Promise.allSettled([closeQueue(), closePool()]);
  process.exitCode = 1;
});
