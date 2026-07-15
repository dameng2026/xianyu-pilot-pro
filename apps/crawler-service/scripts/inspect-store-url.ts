/**
 * 从数据库获取最近爬取过的店铺 URL
 */
import { getPool, closePool } from '../src/db/index.js';

async function main() {
  const pool = getPool();
  try {
    const res = await pool.query(
      `SELECT s.user_id, s.store_url, s.last_crawled_at,
              (SELECT COUNT(*) FROM goofish_items i WHERE i.tenant_id = s.tenant_id AND i.store_user_id = s.user_id) as item_cnt
       FROM goofish_stores s
       WHERE s.last_crawled_at IS NOT NULL
       ORDER BY s.last_crawled_at DESC
       LIMIT 5`
    );
    console.log(`=== 最近爬取过的店铺 (${res.rows.length}) ===`);
    for (const row of res.rows as any[]) {
      console.log(`userId=${row.user_id}, items=${row.item_cnt}, lastSeen=${row.last_crawled_at}`);
      console.log(`  url=${row.store_url}`);
    }
  } finally {
    await closePool();
  }
}
main().catch((e) => { console.error(e); process.exit(1); });
