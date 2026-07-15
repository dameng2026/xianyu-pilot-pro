"""测试 _fetch_goods_covers_async 函数（使用搜索 API）。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import async_session
from sqlalchemy import text
from app.services.ws_storage import _fetch_goods_covers_async


async def main():
    # 从数据库读取活跃会话，构造 conversations 列表
    async with async_session() as db:
        r = await db.execute(text("""
            SELECT id, account_id, tenant_id, peer_key, goods_id,
                   buyer_avatar, goods_cover_pic
            FROM xianyu_conversation
            WHERE deleted=0 AND goods_id IS NOT NULL AND goods_id != 0
              AND (goods_cover_pic IS NULL OR goods_cover_pic = '')
            ORDER BY last_message_time DESC
            LIMIT 10
        """))
        rows = r.fetchall()

    if not rows:
        print("没有需要拉取封面图的会话")
        return

    account_id = rows[0][1]
    tenant_id = rows[0][2]
    print(f"账号: account_id={account_id} tenant_id={tenant_id}")
    print(f"会话数: {len(rows)}")

    # 构造 conversations
    conversations = []
    for row in rows:
        peer_key = row[3] or ""
        sid = peer_key[4:] if peer_key.startswith("sid:") else peer_key
        conversations.append({
            "sid": sid,
            "goodsId": str(row[4]) if row[4] else "",
            "goodsCoverPic": row[6] or "",
        })

    print(f"\n待拉取封面图的商品数: {sum(1 for c in conversations if c['goodsId'] and not c['goodsCoverPic'])}")
    print("开始调用 _fetch_goods_covers_async（使用搜索 API）...")
    print("这可能需要一些时间（每个搜索约 3-5 秒）...\n")

    # 直接调用
    await _fetch_goods_covers_async(tenant_id, account_id, conversations)

    # 检查结果
    print("\n等待 3 秒后检查 DB...")
    await asyncio.sleep(3)

    async with async_session() as db:
        r = await db.execute(text("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN goods_cover_pic IS NOT NULL AND goods_cover_pic != '' THEN 1 ELSE 0 END) AS with_cover
            FROM xianyu_conversation
            WHERE deleted=0 AND account_id=:aid
        """), {"aid": account_id})
        row = r.first()
        print(f"\nDB 状态:")
        print(f"  总会话数: {row[0]}")
        print(f"  有封面图: {row[1]}")

        # 查看几条样例
        r = await db.execute(text("""
            SELECT id, peer_key, goods_id, LEFT(goods_title, 40) AS title, LEFT(goods_cover_pic, 80) AS cover
            FROM xianyu_conversation
            WHERE deleted=0 AND goods_cover_pic IS NOT NULL AND goods_cover_pic != ''
            ORDER BY updated_time DESC
            LIMIT 10
        """))
        print(f"\n有封面图的会话样例:")
        for row in r.fetchall():
            print(f"  id={row[0]} peer_key={row[1]} goods_id={row[2]}")
            print(f"    title={row[3]}")
            print(f"    cover={row[4]}")


if __name__ == "__main__":
    asyncio.run(main())
