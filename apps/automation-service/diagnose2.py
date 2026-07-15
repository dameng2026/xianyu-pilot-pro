"""深入诊断：检查 tenant_id 和查询条件"""
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
        # 1. 检查 tenant_id
        print("=== tenant_id 分布 ===")
        tenants = await conn.execute(
            text("SELECT tenant_id, COUNT(*) FROM xianyu_chat_message WHERE s_id IN ('62491400847', '62491400847@goofish') GROUP BY tenant_id")
        )
        for row in tenants:
            print(f"  tenant_id={row[0]} count={row[1]}")
        
        # 2. 完整的会话消息
        print("\n=== s_id='62491400847' 的所有消息 ===")
        msgs = await conn.execute(
            text("""
                SELECT id, tenant_id, account_id, s_id, sender_user_id, receiver_user_id, 
                       peer_external_uid, content_type, direction, deleted
                FROM xianyu_chat_message 
                WHERE s_id COLLATE utf8mb4_unicode_ci IN ('62491400847', '62491400847@goofish')
                ORDER BY id
            """)
        )
        for row in msgs.mappings():
            print(f"  id={row['id']} tenant={row['tenant_id']} account={row['account_id']}")
            print(f"    s_id='{row['s_id']}' dir={row['direction']} deleted={row['deleted']}")
            print(f"    sender='{row['sender_user_id']}' receiver='{row['receiver_user_id']}'")
            print(f"    peer_external_uid='{row['peer_external_uid']}'")
        
        # 3. 模拟完整的分支1查询
        print("\n=== 模拟分支1查询 (按s_id) ===")
        s_id = "62491400847"
        s_id_goofish = "62491400847@goofish"
        tenant_id = 1  # 假设 tenant_id = 1
        
        sim = await conn.execute(
            text("""
                SELECT COUNT(*)
                FROM xianyu_chat_message base
                WHERE base.tenant_id = :tenant_id
                  AND base.account_id = :account_id
                  AND base.s_id COLLATE utf8mb4_unicode_ci IN (:s_id, :s_id_goofish)
                  AND base.deleted = 0
                  AND base.content_type NOT IN (32)
            """),
            {"tenant_id": tenant_id, "account_id": 1, "s_id": s_id, "s_id_goofish": s_id_goofish}
        )
        cnt = sim.scalar()
        print(f"  tenant_id=1, account_id=1: {cnt} 条")
        
        # 尝试不同的 tenant_id
        for tid in range(1, 5):
            sim2 = await conn.execute(
                text("""
                    SELECT COUNT(*)
                    FROM xianyu_chat_message base
                    WHERE base.tenant_id = :tenant_id
                      AND base.account_id = :account_id
                      AND base.s_id COLLATE utf8mb4_unicode_ci IN (:s_id, :s_id_goofish)
                      AND base.deleted = 0
                      AND base.content_type NOT IN (32)
                """),
                {"tenant_id": tid, "account_id": 1, "s_id": s_id, "s_id_goofish": s_id_goofish}
            )
            cnt2 = sim2.scalar()
            if cnt2 > 0:
                print(f"  tenant_id={tid}, account_id=1: {cnt2} 条")

    await engine.dispose()

asyncio.run(main())