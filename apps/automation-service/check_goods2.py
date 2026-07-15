import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check():
    e = create_async_engine('mysql+aiomysql://root:123456@localhost:3306/xianyu_assistant_admin')
    async with e.connect() as c:
        # Check goods with matching goods_id
        r = await c.execute(text("""
            SELECT goods_id, title, cover_pic, image_url
            FROM xianyu_goods
            WHERE goods_id IN ('1054890039268', '1053077828446', '990447398913', '1047321047453', '1050134147426')
              AND deleted=0
        """))
        print('Matching goods:')
        for row in r:
            d = dict(row._mapping)
            print(f'  goods_id={d["goods_id"]} title={str(d["title"])[:40]} cover={str(d["cover_pic"])[:60]} image_url={str(d["image_url"])[:60]}')

        # Check total goods count
        r = await c.execute(text('SELECT COUNT(*) FROM xianyu_goods WHERE deleted=0'))
        print(f'\nTotal active goods: {r.scalar()}')

        # Check messages with xy_goods_id
        r = await c.execute(text("""
            SELECT DISTINCT xy_goods_id
            FROM xianyu_chat_message
            WHERE account_id=1 AND deleted=0 AND xy_goods_id IS NOT NULL AND xy_goods_id != ''
            LIMIT 10
        """))
        print('\nMessage goods_ids:')
        for row in r:
            print(f'  {row[0]}')
    await e.dispose()

asyncio.run(check())
