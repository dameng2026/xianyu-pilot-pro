/**
 * 查询数据库中存储的 goofish_items，查看 raw_json 结构以找到真实描述字段
 */
import { getPool, closePool } from '../src/db/index.js';

async function main() {
  const pool = getPool();
  try {
    const res = await pool.query(
      `SELECT item_id, title, description, price_text, raw_json, last_seen_at
       FROM goofish_items
       WHERE raw_json IS NOT NULL
       ORDER BY last_seen_at DESC
       LIMIT 3`
    );

    console.log(`=== 查到 ${res.rows.length} 条记录 ===\n`);
    for (const row of res.rows as any[]) {
      console.log('--------------------------------------------------');
      console.log(`itemId: ${row.item_id}`);
      console.log(`title: ${row.title}`);
      console.log(`description: ${row.description}`);
      console.log(`price: ${row.price_text}`);
      console.log(`last_seen: ${row.last_seen_at}`);
      console.log(`raw_json 类型: ${typeof row.raw_json}`);

      const raw = row.raw_json;
      const rawStr = typeof raw === 'string' ? raw : JSON.stringify(raw);
      console.log(`raw_json 长度: ${rawStr.length}`);
      console.log(`raw_json 前 1500 字符:`);
      console.log(rawStr.slice(0, 1500));
      console.log('');
    }

    // 统计 raw_json 中 source 字段
    const stats = await pool.query(
      `SELECT
         COUNT(*) as total,
         COUNT(*) FILTER (WHERE raw_json ? 'source') as has_source,
         COUNT(*) FILTER (WHERE raw_json->>'source' = 'dom') as from_dom,
         COUNT(*) FILTER (WHERE raw_json->>'source' != 'dom' OR raw_json->>'source' IS NULL) as from_network,
         COUNT(description) as has_description,
         COUNT(*) FILTER (WHERE description IS NOT NULL AND description != '') as has_nonempty_desc
       FROM goofish_items
       WHERE last_seen_at > NOW() - INTERVAL '7 days'`
    );
    console.log('\n=== 最近 7 天数据统计 ===');
    console.log(JSON.stringify(stats.rows[0], null, 2));
  } finally {
    await closePool();
  }
}

main().catch((e) => {
  console.error('失败:', e);
  process.exit(1);
});
