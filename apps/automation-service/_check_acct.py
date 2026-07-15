import pymysql, json
conn = pymysql.connect(host='localhost', port=3306, user='xianyu', password='xianyu_pass', database='xianyu_assistant_admin', charset='utf8mb4')
cur = conn.cursor(pymysql.cursors.DictCursor)
cur.execute("SELECT id, tenant_id, user_id, nickname, status, deleted FROM xianyu_account WHERE deleted=0 ORDER BY id")
rows = cur.fetchall()
for r in rows:
    print(f"account#{r['id']}: tenant={r['tenant_id']} user_id={r['user_id']!r} nickname={r['nickname']!r} status={r['status']!r} deleted={r['deleted']}")
conn.close()
