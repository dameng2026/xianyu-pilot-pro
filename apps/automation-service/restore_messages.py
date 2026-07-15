import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def restore():
    e = create_async_engine('mysql+aiomysql://root:123456@localhost:3306/xianyu_assistant_admin')
    async with e.begin() as c:
        # Un-delete messages and conversations
        await c.execute(text('UPDATE xianyu_chat_message SET deleted=0 WHERE account_id=1'))
        await c.execute(text('UPDATE xianyu_conversation SET deleted=0 WHERE account_id=1'))

        r = await c.execute(text('SELECT COUNT(*) FROM xianyu_chat_message WHERE account_id=1 AND deleted=0'))
        print(f'Active messages: {r.scalar()}')
        r = await c.execute(text('SELECT COUNT(*) FROM xianyu_conversation WHERE account_id=1 AND deleted=0'))
        print(f'Active conversations: {r.scalar()}')
    await e.dispose()

asyncio.run(restore())
