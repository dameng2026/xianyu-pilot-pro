import sys
sys.path.insert(0, r'G:\源码\xianyu-assistant-package-temp\apps\automation-service')
from sqlalchemy import text, create_engine

e = create_engine('mysql+pymysql://xianyu:xianyu_pass@localhost:3306/xianyu_assistant_admin?charset=utf8mb4')
with e.connect() as conn:
    sql = """
        SELECT
            MIN(conv.id) AS conversationId,
            base.s_id AS sid,
            MAX(base.message_time) AS lastMessageTime,
            MIN(base.message_time) AS firstMessageTime
        FROM (
            SELECT base.tenant_id, base.account_id, base.s_id AS s_id, base.message_time
            FROM xianyu_chat_message base
            WHERE base.tenant_id=1 AND base.account_id=1
              AND base.deleted=0 AND base.content_type NOT IN (32)
              AND base.s_id IS NOT NULL AND base.s_id != ''
        ) base
        LEFT JOIN xianyu_conversation conv ON 1=0
        GROUP BY base.s_id
        LIMIT 3
    """
    r = conn.execute(text(sql))
    for row in r.mappings():
        d = dict(row)
        print('KEYS:', list(d.keys()))
        print('firstMessageTime:', d.get('firstMessageTime'))
        print('---')