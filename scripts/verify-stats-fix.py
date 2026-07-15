#!/usr/bin/env python3
"""Verify all production services are running with latest changes."""
import json
import time
import paramiko

CONFIG_PATH = ".deploy.prod.json"


def run_remote(client, cmd, timeout=30):
    quoted = "'" + cmd.replace("'", "'\"'\"'") + "'"
    full_cmd = "bash -lc " + quoted
    stdin, stdout, stderr = client.exec_command(full_cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    exit_code = stdout.channel.recv_exit_status()
    return out, err, exit_code


def put_remote_file(client, remote_path, content):
    sftp = client.open_sftp()
    try:
        with sftp.file(remote_path, "w") as f:
            f.write(content)
    finally:
        sftp.close()


def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    backend = config["china_backend"]
    smoke = config["smoke"]
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=backend["host"], port=22,
        username=backend["username"], password=backend["password"],
        timeout=20,
    )
    print("[verify] Connected to", backend["host"])

    # 1. Check all container statuses
    out, _, _ = run_remote(client, "docker ps --format '{{.Names}}\t{{.Status}}' | sort")
    print("[verify] All containers:")
    print(out)

    # 2. Check health endpoints
    out, _, _ = run_remote(client, "curl -sf --max-time 5 http://127.0.0.1:18080/api/health 2>/dev/null || echo HEALTH_FAILED")
    print("[verify] Backend health:", out.strip()[:150])

    out, _, _ = run_remote(client, "curl -sf --max-time 5 http://127.0.0.1:18080/admin-api/health 2>/dev/null || echo ADMIN_HEALTH_FAILED")
    print("[verify] Admin health:", out.strip()[:150])

    # 3. Login and check goods with stats
    login_payload = json.dumps({"username": smoke["user_credentials"]["username"],
                                "password": smoke["user_credentials"]["password"]})
    put_remote_file(client, "/tmp/verify_login.json", login_payload)
    out, _, _ = run_remote(client, "curl -sf -X POST http://127.0.0.1:18080/api/login/login -H 'Content-Type: application/json' --data @/tmp/verify_login.json")
    login_data = json.loads(out)
    data_field = login_data.get("data", {}) if isinstance(login_data.get("data"), dict) else {}
    token = data_field.get("token") or ""
    if not token:
        print("[verify] ERROR: No token")
        client.close()
        return
    print("[verify] Login OK")

    # 4. Query goods - check which have non-zero stats
    out, _, _ = run_remote(client,
        "curl -sf 'http://127.0.0.1:18080/api/goods?current=1&size=20&excludeStatus=3' "
        "-H 'Authorization: Bearer " + token + "'")
    goods_data = json.loads(out)
    inner = goods_data.get("data", goods_data) if isinstance(goods_data.get("data"), dict) else goods_data
    records = inner.get("records", [])
    total = inner.get("total", 0)
    print("[verify] Total goods: %d, showing %d" % (total, len(records)))

    nonzero_view = 0
    nonzero_want = 0
    nonzero_stock = 0
    for g in records:
        vc = g.get("viewCount", 0) or 0
        wc = g.get("wantCount", 0) or 0
        qt = g.get("quantity", 0) or 0
        if vc > 0:
            nonzero_view += 1
        if wc > 0:
            nonzero_want += 1
        if qt > 0:
            nonzero_stock += 1

    print("[verify] In current page: view!=0: %d, want!=0: %d, stock!=0: %d" % (nonzero_view, nonzero_want, nonzero_stock))
    print("[verify] Sample records:")
    for g in records[:8]:
        print("  id=%-4s view=%-5s want=%-4s stock=%-5s title=%s" % (
            g.get("id"), g.get("viewCount"), g.get("wantCount"), g.get("quantity"),
            g.get("title", "")[:35]))

    # 5. Check sync progress (detail sync may still be running)
    out, _, _ = run_remote(client, "docker logs --tail 5 xianyu-automation-service 2>&1 | grep '详情同步' | tail -3", timeout=15)
    print("[verify] Latest detail sync logs:")
    print(out if out.strip() else "  (no recent detail sync logs - sync may have completed)")

    # 6. Count goods with non-zero stats in DB
    out, _, _ = run_remote(client,
        "docker exec xianyu-admin-mysql mysql -u${MYSQL_APP_USER:-xianyu_app} -p${MYSQL_APP_PASSWORD:-dev-only-mysql-app-password-change-me} xianyu_assistant_admin -N -e \""
        "SELECT COUNT(*) AS total, "
        "SUM(CASE WHEN view_count > 0 THEN 1 ELSE 0 END) AS has_view, "
        "SUM(CASE WHEN want_count > 0 THEN 1 ELSE 0 END) AS has_want, "
        "SUM(CASE WHEN quantity > 0 THEN 1 ELSE 0 END) AS has_stock "
        "FROM xianyu_goods WHERE deleted = 0\" 2>/dev/null", timeout=15)
    print("[verify] DB stats summary:")
    print(out if out.strip() else "  (could not query DB)")

    # Cleanup
    run_remote(client, "rm -f /tmp/verify_login.json")
    client.close()
    print("\n[verify] Done.")


if __name__ == "__main__":
    main()
