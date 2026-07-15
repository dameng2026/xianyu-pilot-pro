import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check():
    e = create_async_engine('mysql+aiomysql://root:123456@localhost:3306/xianyu_assistant_admin')
    async with e.connect() as c:
        # Check message direction and sender/receiver
        r = await c.execute(text("""
            SELECT id, s_id, direction, sender_user_id, receiver_user_id,
                   msg_content, content_type, xy_goods_id, reminder_content
            FROM xianyu_chat_message
            WHERE account_id=1 AND deleted=0
            LIMIT 5
        """))
        print('Sample messages:')
        for row in r:
            print(' ', dict(row._mapping))

        # Run the actual query from get_online_conversations
        r = await c.execute(text("""
            SELECT
                MIN(conv.id) AS conversationId,
                SUBSTRING_INDEX(GROUP_CONCAT(base.s_id ORDER BY base.message_time DESC SEPARATOR ','), ',', 1) AS sid,
                MAX(base.peer_user_id) AS peerUserId,
                COALESCE(MAX(conv.peer_key), MAX(base.conv_peer_key),
                    CONCAT('sid:', SUBSTRING_INDEX(GROUP_CONCAT(base.s_id ORDER BY base.message_time DESC SEPARATOR ','), ',', 1))
                ) AS peerKey,
                SUBSTRING_INDEX(GROUP_CONCAT(base.msg_content ORDER BY base.message_time DESC SEPARATOR ','), ',', 1) AS lastMessage,
                MAX(base.message_time) AS lastMessageTime,
                COALESCE(SUBSTRING_INDEX(GROUP_CONCAT(NULLIF(base.xy_goods_id, '') ORDER BY base.message_time DESC SEPARATOR ','), ',', 1), '') AS goodsId,
                COUNT(*) AS messageCount
            FROM (
                SELECT
                    base.tenant_id, base.account_id,
                    CASE WHEN base.s_id LIKE '%@goofish' THEN SUBSTRING_INDEX(base.s_id, '@', 1) ELSE base.s_id END AS s_id,
                    base.msg_content, base.content_type, base.message_time, base.xy_goods_id,
                    base.reminder_content, base.direction, base.read_status,
                    base.sender_user_id, base.receiver_user_id,
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
                    ) AS peer_user_id,
                    COALESCE(NULLIF(conv_by_sid.peer_key, ''), NULLIF(conv_by_sid.external_buyer_id, ''),
                        CONCAT('sid:', base.s_id)) AS conv_peer_key
                FROM xianyu_chat_message base
                JOIN xianyu_account a ON a.id = base.account_id AND a.tenant_id = base.tenant_id
                LEFT JOIN xianyu_conversation conv_by_sid
                    ON conv_by_sid.tenant_id = base.tenant_id AND conv_by_sid.account_id = base.account_id
                    AND (conv_by_sid.peer_key COLLATE utf8mb4_unicode_ci = CONCAT('sid:', base.s_id) COLLATE utf8mb4_unicode_ci
                         OR conv_by_sid.external_buyer_id COLLATE utf8mb4_unicode_ci = CONCAT('sid:', base.s_id) COLLATE utf8mb4_unicode_ci)
                WHERE base.tenant_id = 1 AND base.account_id = 1 AND base.deleted = 0
                  AND base.content_type NOT IN (32) AND base.s_id IS NOT NULL AND base.s_id != ''
            ) base
            LEFT JOIN xianyu_conversation conv
                ON conv.tenant_id = base.tenant_id AND conv.account_id = base.account_id
                AND (conv.peer_key COLLATE utf8mb4_unicode_ci = CONCAT('sid:', base.s_id) COLLATE utf8mb4_unicode_ci
                     OR conv.external_buyer_id COLLATE utf8mb4_unicode_ci = CONCAT('sid:', base.s_id) COLLATE utf8mb4_unicode_ci)
            GROUP BY
                CASE WHEN base.peer_user_id LIKE 'sid:%' OR base.peer_user_id = '' THEN CONCAT('sid:', base.s_id) ELSE base.peer_user_id END,
                COALESCE(NULLIF(base.xy_goods_id, ''), '')
            ORDER BY MAX(base.message_time) DESC
            LIMIT 10
        """))
        print('\nConversation query results:')
        for row in r:
            d = dict(row._mapping)
            print(f'  sid={d.get("sid")} peerUserId={d.get("peerUserId")} lastMsg={str(d.get("lastMessage"))[:50]} goodsId={d.get("goodsId")} count={d.get("messageCount")}')
    await e.dispose()

asyncio.run(check())
