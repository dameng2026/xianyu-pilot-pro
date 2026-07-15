import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check():
    e = create_async_engine('mysql+aiomysql://root:123456@localhost:3306/xianyu_assistant_admin')
    async with e.connect() as c:
        # Check peer_external_uid for recent messages
        r = await c.execute(text("""
            SELECT id, s_id, direction, sender_user_id, receiver_user_id, peer_external_uid
            FROM xianyu_chat_message
            WHERE account_id=1 AND deleted=0
            ORDER BY id DESC
            LIMIT 5
        """))
        print('Recent messages with peer_external_uid:')
        for row in r:
            d = dict(row._mapping)
            print(f'  id={d["id"]} s_id={d["s_id"]} dir={d["direction"]} sender={d["sender_user_id"]} recv={d["receiver_user_id"]} peer_ext_uid={d["peer_external_uid"]}')

        # Check if conversations exist for recent s_ids
        r = await c.execute(text("""
            SELECT id, peer_key, external_buyer_id
            FROM xianyu_conversation
            WHERE account_id=1 AND deleted=0
              AND peer_key IN ('sid:62417678585', 'sid:61815935774', 'sid:61933724967')
        """))
        print('\nConversations for recent s_ids:')
        for row in r:
            print(' ', dict(row._mapping))

        # Full computation for one recent message
        r = await c.execute(text("""
            SELECT
                base.s_id, base.direction, base.sender_user_id, base.receiver_user_id,
                base.peer_external_uid,
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
        """))
        print('\nFull computation for s_id=62417678585:')
        for row in r:
            d = dict(row._mapping)
            for k, v in d.items():
                print(f'  {k} = {v}')
    await e.dispose()

asyncio.run(check())
