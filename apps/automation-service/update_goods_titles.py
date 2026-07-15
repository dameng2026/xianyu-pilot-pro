"""从 content_type=8 消息中提取商品标题，更新到 xianyu_conversation.goods_title。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import async_session
from sqlalchemy import text


async def main():
    async with async_session() as db:
        # 从 content_type=8 消息中提取标题，更新到对应会话
        r = await db.execute(text("""
            UPDATE xianyu_conversation c
            INNER JOIN (
                SELECT s_id, MAX(msg_content) AS title
                FROM xianyu_chat_message
                WHERE deleted=0 AND content_type=8 AND msg_content IS NOT NULL AND msg_content != ''
                GROUP BY s_id
            ) m ON c.peer_key = CONCAT('sid:', m.s_id)
            SET c.goods_title = m.title
            WHERE c.deleted=0
              AND (c.goods_title IS NULL OR c.goods_title = '')
              AND c.goods_id IS NOT NULL AND c.goods_id != 0
        """))
        updated = r.rowcount
        await db.commit()
        print(f"更新 goods_title: {updated} 条")

        # 检查结果
        r = await db.execute(text("""
            SELECT id, goods_id, LEFT(goods_title, 60) AS goods_title
            FROM xianyu_conversation
            WHERE deleted=0 AND goods_id IS NOT NULL AND goods_id != 0
            ORDER BY last_message_time DESC
            LIMIT 10
        """))
        print("\n更新后的会话:")
        for row in r.fetchall():
            print(f"  id={row[0]} goods_id={row[1]} goods_title={row[2]}")


if __name__ == "__main__":
    asyncio.run(main())
