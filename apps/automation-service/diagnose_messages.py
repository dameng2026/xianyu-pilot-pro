"""快速诊断：检查数据库中是否存在指定 s_id 的消息"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
os.environ['APP_ENV'] = 'dev'

from app.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    engine = create_async_engine(settings.mysql_url, echo=False)
    
    async with engine.connect() as conn:
        # 1. 检查表是否存在
        tables = await conn.execute(text("SHOW TABLES LIKE 'xianyu_chat_message'"))
        if not tables.fetchone():
            print("错误: xianyu_chat_message 表不存在!")
            return
        
        # 2. 检查表的行数
        count = await conn.execute(text("SELECT COUNT(*) FROM xianyu_chat_message"))
        total = count.scalar()
        print(f"xianyu_chat_message 总行数: {total}")
        
        # 3. 检查指定 s_id
        s_id = "62491400847"
        s_id_goofish = f"{s_id}@goofish"
        
        for sid in [s_id, s_id_goofish]:
            result = await conn.execute(
                text("SELECT COUNT(*) FROM xianyu_chat_message WHERE s_id = :sid"),
                {"sid": sid}
            )
            cnt = result.scalar()
            print(f"  s_id='{sid}' : {cnt} 条消息")
        
        # 4. 查看数据库中实际的 s_id 列表
        print("\n--- 数据库中的 s_id 列表 (前20) ---")
        sids = await conn.execute(
            text("SELECT DISTINCT s_id FROM xianyu_chat_message LIMIT 20")
        )
        for row in sids:
            print(f"  '{row[0]}'")
        
        # 5. 查看最近的消息
        print("\n--- 最近5条消息 ---")
        recent = await conn.execute(
            text("""
                SELECT id, s_id, sender_user_id, receiver_user_id, 
                       content_type, LEFT(msg_content, 50) as content,
                       message_time, direction
                FROM xianyu_chat_message 
                ORDER BY id DESC LIMIT 5
            """)
        )
        for row in recent.mappings():
            print(f"  id={row['id']} s_id='{row['s_id']}' sender={row['sender_user_id']} receiver={row['receiver_user_id']} dir={row['direction']} time={row['message_time']} content={row['content']}")
        
        # 6. 检查 account_id=1 的消息
        print("\n--- account_id=1 的 s_id 列表 ---")
        acct_sids = await conn.execute(
            text("SELECT DISTINCT s_id, COUNT(*) as cnt FROM xianyu_chat_message WHERE account_id = 1 GROUP BY s_id ORDER BY cnt DESC LIMIT 10")
        )
        for row in acct_sids:
            print(f"  s_id='{row[0]}' count={row[1]}")

    await engine.dispose()

asyncio.run(main())