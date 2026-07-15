import pymysql, json
conn = pymysql.connect(host='localhost', port=3306, user='xianyu', password='xianyu_pass', database='xianyu_assistant_admin', charset='utf8mb4')
cur = conn.cursor()
cur.execute("SELECT id, workflow_id, status, error_message, output_json, started_time, finished_time FROM workflow_execution WHERE tenant_id=1 ORDER BY id DESC LIMIT 3")
rows = cur.fetchall()
for r in rows:
    eid, wf_id, status, err, oj, st, ft = r
    print(f"\n=== Execution #{eid} (workflow={wf_id}, status={status}) ===")
    print(f"  started={st} finished={ft}")
    print(f"  error={err}")
    if oj:
        try:
            out = json.loads(oj)
            for nr in out.get("nodeResults", []):
                print(f"  node: {nr.get('nodeKey')} type={nr.get('nodeType')} status={nr.get('status')} ok={nr.get('ok')}")
                if nr.get('errorMessage'):
                    print(f"    error: {nr.get('errorMessage')[:500]}")
                if nr.get('output'):
                    o = nr.get('output')
                    if isinstance(o, dict):
                        for k, v in list(o.items())[:8]:
                            sv = str(v)
                            print(f"    {k}: {sv[:200]}")
            # timeline
            for tl in out.get("timeline", [])[-10:]:
                print(f"  timeline: {tl.get('time','')} {tl.get('message','')[:200]}")
        except Exception as e:
            print(f"  output_json parse error: {e}")
            print(f"  raw: {oj[:500]}")
conn.close()
