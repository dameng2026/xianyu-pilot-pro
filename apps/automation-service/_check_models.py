import pymysql, json
conn = pymysql.connect(host='localhost', port=3306, user='xianyu', password='xianyu_pass', database='xianyu_assistant_admin', charset='utf8mb4')
cur = conn.cursor()
cur.execute("SELECT module_key, status, json_text FROM admin_module_record WHERE module_key IN ('model-config-general', 'model-config-image', 'model-config-image-2', 'model-config-image-3') AND deleted=0 ORDER BY id ASC")
rows = cur.fetchall()
if not rows:
    print("NO ROWS FOUND in admin_module_record for image model configs")
for r in rows:
    mk, status, jt = r
    cfg = json.loads(jt) if jt else {}
    print(f"\n=== {mk} (status={status}) ===")
    print(f"  enabled={cfg.get('enabled')!r} status={cfg.get('status')!r}")
    print(f"  modelName={cfg.get('modelName')!r} baseUrl={cfg.get('baseUrl','')[:60]!r} apiKey={'***' if cfg.get('apiKey') else None}")
conn.close()
