import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check():
    e = create_async_engine('mysql+aiomysql://root:123456@localhost:3306/xianyu_assistant_admin')
    async with e.connect() as c:
        # Check xianyu_goods table columns
        r = await c.execute(text("SHOW COLUMNS FROM xianyu_goods"))
        print('xianyu_goods columns:')
        for row in r:
            print(f'  {row[0]} ({row[1]})')

        # Check conversation table
        r = await c.execute(text("""
            SELECT id, peer_key, buyer_avatar, goods_title, goods_cover_pic
            FROM xianyu_conversation
            WHERE account_id=1 AND deleted=0
            LIMIT 5
        """))
        print('\nConversations:')
        for row in r:
            d = dict(row._mapping)
            print(f'  id={d["id"]} peer_key={d["peer_key"]} avatar={d["buyer_avatar"]} title={d["goods_title"]} cover={d["goods_cover_pic"]}')
    await e.dispose()

asyncio.run(check())
