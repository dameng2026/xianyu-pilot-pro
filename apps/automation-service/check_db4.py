import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check():
    e = create_async_engine('mysql+aiomysql://root:123456@localhost:3306/xianyu_assistant_admin')
    async with e.connect() as c:
        # Check conversation table
        r = await c.execute(text("""
            SELECT id, peer_key, external_buyer_id, buyer_avatar, goods_title, goods_cover_pic
            FROM xianyu_conversation
            WHERE account_id=1 AND deleted=0
            LIMIT 10
        """))
        print('Conversations:')
        for row in r:
            d = dict(row._mapping)
            print(f'  id={d["id"]} peer_key={d["peer_key"]} ext_buyer_id={d["external_buyer_id"]} avatar={d["buyer_avatar"][:50] if d["buyer_avatar"] else None} title={d["goods_title"]} cover={d["goods_cover_pic"][:50] if d["goods_cover_pic"] else None}')

        # Check if peer_external_uid column exists in xianyu_chat_message
        r = await c.execute(text("SHOW COLUMNS FROM xianyu_chat_message LIKE 'peer_external_uid'"))
        print('\npeer_external_uid column:', list(r.fetchall()))

        # Check actual peer_user_id computation
        r = await c.execute(text("""
            SELECT base.s_id, base.direction, base.sender_user_id, base.receiver_user_id,
                   a.external_uid as account_external_uid,
                   conv_by_sid.peer_key as conv_peer_key,
                   conv_by_sid.external_buyer_id as conv_ext_buyer_id,
                   COALESCE(
                       NULLIF(base.peer_external_uid, ''),
                       NULLIF(CASE
                           WHEN base.direction = 'OUT' THEN
                               CASE WHEN base.receiver_user_id IS NOT NULL AND base.receiver_user_id != ''
                                 AND (a.external_uid IS NULL OR base.receiver_user_id != a.external_uid)
                               THEN base.receiver_user_id ELSE NULL END
                           ELSE
                               CASE WHEN base.sender_user_id IS NOT NULL AND base.sender_user_id != ''
                                 AND (a.external_uid IS NULL OR base.sender_user_id != a.external_uid)
                               THEN base.sender_user_id ELSE NULL END
                       END, ''),
                       NULLIF(conv_by_sid.external_buyer_id, ''),
                       CONCAT('sid:', base.s_id)
                   ) AS computed_peer_user_id
            FROM xianyu_chat_message base
            JOIN xianyu_account a ON a.id = base.account_id AND a.tenant_id = base.tenant_id
            LEFT JOIN xianyu_conversation conv_by_sid
                ON conv_by_sid.tenant_id = base.tenant_id AND conv_by_sid.account_id = base.account_id
                AND (conv_by_sid.peer_key COLLATE utf8mb4_unicode_ci = CONCAT('sid:', base.s_id) COLLATE utf8mb4_unicode_ci
                     OR conv_by_sid.external_buyer_id COLLATE utf8mb4_unicode_ci = CONCAT('sid:', base.s_id) COLLATE utf8mb4_unicode_ci)
            WHERE base.tenant_id = 1 AND base.account_id = 1 AND base.deleted = 0 AND base.s_id = '62417678585'
            LIMIT 5
        """))
        print('\nPeer user ID computation for s_id=62417678585:')
        for row in r:
            d = dict(row._mapping)
            print(f'  s_id={d["s_id"]} dir={d["direction"]} sender={d["sender_user_id"]} recv={d["receiver_user_id"]} acct_uid={d["account_external_uid"]} conv_peer={d["conv_peer_key"]} conv_ext_buyer={d["conv_ext_buyer"]} computed={d["computed_peer_user_id"]}')
    await e.dispose()

asyncio.run(check())
