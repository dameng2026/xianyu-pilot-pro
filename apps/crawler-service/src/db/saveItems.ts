import crypto from 'crypto';
import { getPool } from './index.js';

export interface GoofishItem {
  itemId?: string;
  title?: string;
  description?: string;
  price?: string;
  imageUrl?: string;
  itemUrl?: string;
}

/**
 * 保存爬取结果到数据库。
 * 所有数据均按 tenant_id 隔离，禁止跨租户复用缓存、任务或商品结果。
 */
export async function saveCrawlResult(
  tenantId: string,
  storeUserId: string,
  storeUrl: string,
  items: GoofishItem[],
  bullmqJobId: string,
  executionToken: string,
): Promise<void> {
  const pool = getPool();
  const client = await pool.connect();

  try {
    await client.query('BEGIN');

    await client.query(
      `INSERT INTO goofish_stores (tenant_id, user_id, store_url, last_crawled_at, updated_at)
       VALUES ($1, $2, $3, NOW(), NOW())
       ON CONFLICT (tenant_id, user_id) DO UPDATE SET
         store_url = EXCLUDED.store_url,
         last_crawled_at = NOW(),
         updated_at = NOW()`,
      [tenantId, storeUserId, storeUrl]
    );

    await client.query(
      `UPDATE goofish_items
       SET is_active = FALSE
       WHERE tenant_id = $1 AND store_user_id = $2 AND is_active = TRUE`,
      [tenantId, storeUserId],
    );

    for (const item of items) {
      const itemKey = item.itemId
        || item.itemUrl
        || crypto.createHash('md5').update(`${item.title || ''}|${item.price || ''}|${item.imageUrl || ''}`).digest('hex');
      await client.query(
        `INSERT INTO goofish_items (tenant_id, store_user_id, item_id, item_key, title, description, price_text, image_url, item_url, is_active, last_crawl_job_id, first_seen_at, last_seen_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, TRUE, $10, NOW(), NOW())
         ON CONFLICT (tenant_id, store_user_id, item_key) DO UPDATE SET
           item_id = COALESCE(EXCLUDED.item_id, goofish_items.item_id),
           title = COALESCE(EXCLUDED.title, goofish_items.title),
           description = COALESCE(EXCLUDED.description, goofish_items.description),
           price_text = COALESCE(EXCLUDED.price_text, goofish_items.price_text),
           image_url = COALESCE(EXCLUDED.image_url, goofish_items.image_url),
           item_url = COALESCE(EXCLUDED.item_url, goofish_items.item_url),
           is_active = TRUE,
           last_crawl_job_id = EXCLUDED.last_crawl_job_id,
           last_seen_at = NOW()`,
        [
          tenantId,
          storeUserId,
          item.itemId || null,
          itemKey,
          item.title || null,
          item.description || null,
          item.price || null,
          item.imageUrl || null,
          item.itemUrl || null,
          bullmqJobId,
        ]
      );
    }

    const completed = await client.query(
      `UPDATE goofish_crawl_jobs
       SET status = 'completed', item_count = $1, finished_at = NOW()
       WHERE tenant_id = $2 AND bullmq_job_id = $3 AND status = 'running' AND execution_token = $4
       RETURNING bullmq_job_id`,
      [items.length, tenantId, bullmqJobId, executionToken]
    );
    if (completed.rowCount !== 1) {
      throw new Error('crawl job record is missing or no longer running');
    }

    await client.query('COMMIT');
    console.log(`[DB] 保存完成: tenantId=${tenantId}, jobId=${bullmqJobId}, items=${items.length}`);
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

/**
 * 记录爬取任务失败。
 */
export async function markCrawlJobFailed(
  tenantId: string,
  bullmqJobId: string,
  storeUserId: string,
  errorMessage: string,
  executionToken: string,
): Promise<void> {
  const pool = getPool();

  const failed = await pool.query(
    `UPDATE goofish_crawl_jobs
     SET status = 'failed', error_message = $1, finished_at = NOW(), execution_token = NULL
     WHERE tenant_id = $2 AND bullmq_job_id = $3 AND status = 'running' AND execution_token = $4
     RETURNING bullmq_job_id`,
    [errorMessage, tenantId, bullmqJobId, executionToken]
  );
  if (failed.rowCount !== 1) throw new Error('crawl job failure update lost its execution fence');

  console.log(`[DB] 任务失败记录: tenantId=${tenantId}, jobId=${bullmqJobId}`);
}


/**
 * 标记任务进入 BullMQ 自动重试等待态。
 * 注意：数据库 status 仍使用 pending，避免旧表枚举或前端状态判断不认识 retrying。
 */
export async function markCrawlJobRetrying(
  tenantId: string,
  bullmqJobId: string,
  storeUserId: string,
  errorMessage: string,
  nextAttempt: number,
  maxAttempts: number,
  executionToken: string,
): Promise<void> {
  const pool = getPool();
  const message = `第 ${nextAttempt}/${maxAttempts} 次尝试失败，等待自动重试：${errorMessage}`;

  const retrying = await pool.query(
    `UPDATE goofish_crawl_jobs
     SET status = 'pending', error_message = $1, execution_token = NULL
     WHERE tenant_id = $2 AND bullmq_job_id = $3 AND status = 'running' AND execution_token = $4
     RETURNING bullmq_job_id`,
    [message, tenantId, bullmqJobId, executionToken]
  );
  if (retrying.rowCount !== 1) throw new Error('crawl job retry update lost its execution fence');

  console.log(`[DB] 任务等待重试: tenantId=${tenantId}, jobId=${bullmqJobId}, attempt=${nextAttempt}/${maxAttempts}`);
}
