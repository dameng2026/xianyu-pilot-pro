"""恢复软删除的消息和会话。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import async_session
from sqlalchemy import text


async def main():
    async with async_session() as db:
        # 恢复软删除的会话
        r = await db.execute(text(
            "UPDATE xianyu_conversation SET deleted=0 WHERE deleted=1"
        ))
        print(f"恢复会话: {r.rowcount} 条")

        # 恢复软删除的消息
        r = await db.execute(text(
            "UPDATE xianyu_chat_message SET deleted=0 WHERE deleted=1"
        ))
        print(f"恢复消息: {r.rowcount} 条")

        await db.commit()

        # 检查会话统计
        r = await db.execute(text("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN buyer_avatar IS NOT NULL AND buyer_avatar != '' THEN 1 ELSE 0 END) AS with_avatar,
                SUM(CASE WHEN goods_cover_pic IS NOT NULL AND goods_cover_pic != '' THEN 1 ELSE 0 END) AS with_cover,
                SUM(CASE WHEN goods_id IS NOT NULL AND goods_id != 0 THEN 1 ELSE 0 END) AS with_goods_id
            FROM xianyu_conversation WHERE deleted=0
        """))
        row = r.first()
        if row:
            print(f"\n活跃会话统计:")
            print(f"  总数: {row[0]}")
            print(f"  有头像: {row[1]}")
            print(f"  有封面图: {row[2]}")
            print(f"  有商品ID: {row[3]}")

        # 查看几条样例
        r = await db.execute(text("""
            SELECT id, account_id, peer_key, buyer_name,
                   LEFT(buyer_avatar, 80) AS avatar_prefix,
                   LEFT(goods_cover_pic, 80) AS cover_prefix,
                   goods_id, goods_title
            FROM xianyu_conversation
            WHERE deleted=0
            ORDER BY last_message_time DESC
            LIMIT 10
        """))
        print(f"\n会话样例（最近10条）:")
        for row in r.fetchall():
            print(f"  id={row[0]} acc={row[1]} peer_key={row[2]}")
            print(f"    buyer_name={row[3]}")
            print(f"    avatar={row[4]}")
            print(f"    cover={row[5]}")
            print(f"    goods_id={row[6]} goods_title={row[7]}")


if __name__ == "__main__":
    asyncio.run(main())
