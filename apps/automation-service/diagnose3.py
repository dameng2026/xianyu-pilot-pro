"""深入诊断：检查 JOIN 条件和为什么 API 返回 0"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    engine = create_async_engine(settings.mysql_url, echo=False)
    
    async with engine.connect() as conn:
        # 1. 检查 xianyu_account 表
        print("=== xianyu_account 表 ===")
        accts = await conn.execute(text("SELECT id, tenant_id, user_id FROM xianyu_account WHERE id = 1"))
        for row in accts:
            print(f"  id={row[0]} tenant_id={row[1]} user_id={row[2]}")
        
        # 2. 模拟完整 JOIN 查询
        print("\n=== 模拟 API 完整查询 ===")
        
        # 不带 JOIN
        sim1 = await conn.execute(
            text("""
                SELECT COUNT(*)
                FROM xianyu_chat_message base
                WHERE base.tenant_id = :tenant_id
                  AND base.account_id = :account_id
                  AND base.s_id COLLATE utf8mb4_unicode_ci IN (:s_id, :s_id_goofish)
                  AND base.deleted = 0
                  AND base.content_type NOT IN (32)
            """),
            {"tenant_id": 1, "account_id": 1, "s_id": "62491400847", "s_id_goofish": "62491400847@goofish"}
        )
        print(f"  不带JOIN: {sim1.scalar()} 条")
        
        # 带 JOIN (完整API查询)
        user_id = 0
        sim2 = await conn.execute(
            text("""
                SELECT COUNT(*)
                FROM xianyu_chat_message base
                JOIN xianyu_account a
                    ON a.id = base.account_id
                    AND a.tenant_id = base.tenant_id
                    AND (:user_id IS NULL OR a.user_id IS NULL OR a.user_id = :user_id)
                WHERE base.tenant_id = :tenant_id
                  AND base.account_id = :account_id
                  AND base.s_id COLLATE utf8mb4_unicode_ci IN (:s_id, :s_id_goofish)
                  AND base.deleted = 0
                  AND base.content_type NOT IN (32)
            """),
            {"tenant_id": 1, "account_id": 1, "s_id": "62491400847", "s_id_goofish": "62491400847@goofish", "user_id": user_id}
        )
        print(f"  带JOIN (user_id=0): {sim2.scalar()} 条")
        
        # 带 JOIN, user_id=None
        sim3 = await conn.execute(
            text("""
                SELECT COUNT(*)
                FROM xianyu_chat_message base
                JOIN xianyu_account a
                    ON a.id = base.account_id
                    AND a.tenant_id = base.tenant_id
                    AND (:user_id IS NULL OR a.user_id IS NULL OR a.user_id = :user_id)
                WHERE base.tenant_id = :tenant_id
                  AND base.account_id = :account_id
                  AND base.s_id COLLATE utf8mb4_unicode_ci IN (:s_id, :s_id_goofish)
                  AND base.deleted = 0
                  AND base.content_type NOT IN (32)
            """),
            {"tenant_id": 1, "account_id": 1, "s_id": "62491400847", "s_id_goofish": "62491400847@goofish", "user_id": None}
        )
        print(f"  带JOIN (user_id=None): {sim3.scalar()} 条")
        
        # 3. 检查 content_type 值
        print("\n=== s_id='62491400847' 的 content_type 值 ===")
        cts = await conn.execute(
            text("SELECT content_type, COUNT(*) FROM xianyu_chat_message WHERE s_id COLLATE utf8mb4_unicode_ci IN ('62491400847', '62491400847@goofish') GROUP BY content_type")
        )
        for row in cts:
            print(f"  content_type={row[0]} count={row[1]}")

    await engine.dispose()

asyncio.run(main())