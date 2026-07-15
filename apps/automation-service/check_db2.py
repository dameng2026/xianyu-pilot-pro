import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check():
    e = create_async_engine('mysql+aiomysql://root:123456@localhost:3306/xianyu_assistant_admin')
    async with e.connect() as c:
        # Check account
        r = await c.execute(text('SELECT id, tenant_id, user_id, external_uid FROM xianyu_account WHERE id=1'))
        print('Account 1:', list(r.fetchall()))

        # Check messages tenant_id
        r = await c.execute(text('SELECT DISTINCT tenant_id, account_id, COUNT(*) as cnt FROM xianyu_chat_message WHERE account_id=1 GROUP BY tenant_id, account_id'))
        print('Messages by tenant:', list(r.fetchall()))

        # Check content_type distribution
        r = await c.execute(text('SELECT content_type, deleted, COUNT(*) as cnt FROM xianyu_chat_message WHERE account_id=1 GROUP BY content_type, deleted'))
        print('Content type distribution:', list(r.fetchall()))

        # Check s_id values
        r = await c.execute(text('SELECT s_id, content_type, deleted, message_time FROM xianyu_chat_message WHERE account_id=1 LIMIT 5'))
        print('Sample messages:', list(r.fetchall()))

        # Run the actual query to see what it returns
        r = await c.execute(text("""
            SELECT COUNT(*) FROM (
                SELECT base.s_id, base.message_time
                FROM xianyu_chat_message base
                JOIN xianyu_account a
                    ON a.id = base.account_id
                    AND a.tenant_id = base.tenant_id
                WHERE base.tenant_id = :tenant_id
                  AND base.account_id = :account_id
                  AND base.deleted = 0
                  AND base.content_type NOT IN (32)
                  AND base.s_id IS NOT NULL
                  AND base.s_id != ''
            ) base
        """), {"tenant_id": 1, "account_id": 1})
        print('Query result count (tenant_id=1):', r.scalar())

    await e.dispose()

asyncio.run(check())
