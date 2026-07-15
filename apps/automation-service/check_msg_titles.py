"""检查消息中是否包含商品标题信息。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import async_session
from sqlalchemy import text


async def main():
    async with async_session() as db:
        # 检查 content_type=8 的消息（商品卡片消息）
        r = await db.execute(text("""
            SELECT id, s_id, content_type, LEFT(msg_content, 200) AS msg_content,
                   LEFT(reminder_content, 200) AS reminder_content,
                   LEFT(reminder_url, 200) AS reminder_url,
                   xy_goods_id
            FROM xianyu_chat_message
            WHERE deleted=0 AND content_type=8
            ORDER BY message_time DESC
            LIMIT 10
        """))
        rows = r.fetchall()
        print(f"content_type=8 消息数: {len(rows)}")
        for row in rows:
            print(f"\n  id={row[0]} s_id={row[1]} goods_id={row[6]}")
            print(f"  msg_content: {row[3]}")
            print(f"  reminder_content: {row[4]}")
            print(f"  reminder_url: {row[5]}")

        # 也检查 content_type=1 的消息（文本消息），看是否包含商品标题
        print("\n\n=== content_type=1 消息样例 ===")
        r = await db.execute(text("""
            SELECT id, s_id, content_type, LEFT(msg_content, 200) AS msg_content,
                   LEFT(reminder_content, 200) AS reminder_content,
                   xy_goods_id
            FROM xianyu_chat_message
            WHERE deleted=0 AND content_type=1
            ORDER BY message_time DESC
            LIMIT 5
        """))
        for row in r.fetchall():
            print(f"\n  id={row[0]} s_id={row[1]} goods_id={row[5]}")
            print(f"  msg_content: {row[3]}")
            print(f"  reminder_content: {row[4]}")

        # 检查 xianyu_conversation 表的 goods_title 字段
        print("\n\n=== 会话 goods_title 检查 ===")
        r = await db.execute(text("""
            SELECT id, goods_id, goods_title, LEFT(last_message_content, 100) AS last_msg
            FROM xianyu_conversation
            WHERE deleted=0 AND goods_id IS NOT NULL AND goods_id != 0
            ORDER BY last_message_time DESC
            LIMIT 10
        """))
        for row in r.fetchall():
            print(f"  id={row[0]} goods_id={row[1]} goods_title={row[2]} last_msg={row[3]}")


if __name__ == "__main__":
    asyncio.run(main())
