/**
 * 查看 network 来源的 raw_json 结构，找到真实描述字段
 */
import { getPool, closePool } from '../src/db/index.js';

async function main() {
  const pool = getPool();
  try {
    // 查看非 DOM 来源的记录
    const res = await pool.query(
      `SELECT item_id, title, description, price_text, raw_json, last_seen_at
       FROM goofish_items
       WHERE raw_json IS NOT NULL
         AND (raw_json->>'source' IS NULL OR raw_json->>'source' != 'dom')
       ORDER BY last_seen_at DESC
       LIMIT 2`
    );

    console.log(`=== 非 DOM 来源记录数: ${res.rows.length} ===\n`);
    for (const row of res.rows as any[]) {
      console.log('--------------------------------------------------');
      console.log(`itemId: ${row.item_id}`);
      console.log(`title: ${row.title}`);
      console.log(`description: ${row.description}`);
      console.log(`price: ${row.price_text}`);
      console.log(`last_seen: ${row.last_seen_at}`);

      const raw = row.raw_json;
      const rawStr = typeof raw === 'string' ? raw : JSON.stringify(raw);
      console.log(`raw_json 长度: ${rawStr.length}`);
      console.log(`raw_json 前 3000 字符:`);
      console.log(rawStr.slice(0, 3000));
      console.log('');
    }

    if (res.rows.length === 0) {
      console.log('没有非 DOM 来源的记录，查看所有记录的 source 字段分布:');
      const dist = await pool.query(
        `SELECT
           COALESCE(raw_json->>'source', '(null)') as source,
           COUNT(*) as cnt
         FROM goofish_items
         WHERE raw_json IS NOT NULL
         GROUP BY COALESCE(raw_json->>'source', '(null)')
         ORDER BY cnt DESC`
      );
      console.log(JSON.stringify(dist.rows, null, 2));
    }
  } finally {
    await closePool();
  }
}

main().catch((e) => {
  console.error('失败:', e);
  process.exit(1);
});
