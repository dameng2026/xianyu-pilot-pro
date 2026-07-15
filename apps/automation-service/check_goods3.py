import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check():
    e = create_async_engine('mysql+aiomysql://root:123456@localhost:3306/xianyu_assistant_admin')
    async with e.connect() as c:
        # Check if any message xy_goods_id matches goods in xianyu_goods
        r = await c.execute(text("""
            SELECT m.xy_goods_id, g.goods_id, g.title, g.cover_pic, g.image_url
            FROM xianyu_chat_message m
            LEFT JOIN xianyu_goods g ON g.goods_id = m.xy_goods_id AND g.deleted=0
            WHERE m.account_id=1 AND m.deleted=0 AND m.xy_goods_id IS NOT NULL AND m.xy_goods_id != ''
            LIMIT 10
        """))
        print('Message to goods join:')
        for row in r:
            d = dict(row._mapping)
            print(f'  msg_goods_id={d["xy_goods_id"]} matched_goods_id={d["goods_id"]} title={str(d["title"])[:30] if d["title"] else None} cover={str(d["cover_pic"])[:50] if d["cover_pic"] else None}')

        # Sample goods_ids from xianyu_goods
        r = await c.execute(text('SELECT goods_id, title, cover_pic FROM xianyu_goods WHERE deleted=0 LIMIT 5'))
        print('\nSample goods from xianyu_goods:')
        for row in r:
            d = dict(row._mapping)
            print(f'  goods_id={d["goods_id"]} title={str(d["title"])[:30]} cover={str(d["cover_pic"])[:50] if d["cover_pic"] else None}')
    await e.dispose()

asyncio.run(check())
