import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def clear():
    e = create_async_engine('mysql+aiomysql://root:123456@localhost:3306/xianyu_assistant_admin')
    async with e.begin() as c:
        # Count before
        r = await c.execute(text('SELECT COUNT(*) FROM xianyu_chat_message WHERE account_id=1'))
        before_msgs = r.scalar()
        r = await c.execute(text('SELECT COUNT(*) FROM xianyu_conversation WHERE account_id=1'))
        before_convs = r.scalar()
        print(f'Before: {before_msgs} messages, {before_convs} conversations')

        # Soft-delete all messages and conversations for account 1
        await c.execute(text('UPDATE xianyu_chat_message SET deleted=1 WHERE account_id=1'))
        await c.execute(text('UPDATE xianyu_conversation SET deleted=1 WHERE account_id=1'))

        # Count after
        r = await c.execute(text('SELECT COUNT(*) FROM xianyu_chat_message WHERE account_id=1 AND deleted=0'))
        after_msgs = r.scalar()
        r = await c.execute(text('SELECT COUNT(*) FROM xianyu_conversation WHERE account_id=1 AND deleted=0'))
        after_convs = r.scalar()
        print(f'After: {after_msgs} messages, {after_convs} conversations (active)')
    await e.dispose()

asyncio.run(clear())
