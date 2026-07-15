import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check():
    e = create_async_engine('mysql+aiomysql://root:123456@localhost:3306/xianyu_assistant_admin')
    async with e.connect() as c:
        r1 = await c.execute(text('SELECT COUNT(*) FROM xianyu_conversation WHERE account_id=1'))
        print('Conversations for account 1:', r1.scalar())

        r2 = await c.execute(text('SELECT COUNT(*) FROM xianyu_chat_message'))
        print('Total messages:', r2.scalar())

        r3 = await c.execute(text('SELECT id, peer_key, goods_title, goods_cover_pic, deleted FROM xianyu_conversation WHERE account_id=1 LIMIT 10'))
        print('Sample conversations:')
        for row in r3:
            print(' ', tuple(row))

        r4 = await c.execute(text('SELECT COUNT(*) FROM xianyu_chat_message WHERE account_id=1'))
        print('Messages for account 1:', r4.scalar())

        r5 = await c.execute(text('SELECT id, s_id, sender_user_id, message_time, deleted FROM xianyu_chat_message WHERE account_id=1 ORDER BY id DESC LIMIT 10'))
        print('Recent messages for account 1:')
        for row in r5:
            print(' ', tuple(row))
    await e.dispose()

asyncio.run(check())
