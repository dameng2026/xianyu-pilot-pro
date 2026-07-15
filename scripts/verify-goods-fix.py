#!/usr/bin/env python3
"""Verify the goods list fix on production."""
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


def wait_for_health(client, attempts=15, interval=10):
    for i in range(attempts):
        out, _, _ = run_remote(client, "curl -sf --max-time 5 http://127.0.0.1:18080/api/health 2>/dev/null || echo HEALTH_FAILED")
        status = out.strip()
        print("[verify] Health attempt %d/%d: %s" % (i + 1, attempts, status[:120]))
        if '"UP"' in status:
            return True
        if i < attempts - 1:
            time.sleep(interval)
    return False


def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    backend = config["china_backend"]
    smoke = config["smoke"]
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=backend["host"],
        port=22,
        username=backend["username"],
        password=backend["password"],
        timeout=20,
    )
    print("[verify] Connected to", backend["host"])

    out, _, _ = run_remote(client, "docker ps --filter name=xianyu-admin-backend --format '{{.Names}} {{.Status}}'")
    print("[verify] Container status:", out.strip())

    if not wait_for_health(client, attempts=15, interval=10):
        print("[verify] Backend did not become healthy. Dumping recent logs:")
        out2, _, _ = run_remote(client, "docker logs --tail 80 xianyu-admin-backend 2>&1 | tail -60", timeout=30)
        print(out2)
        client.close()
        return

    print("[verify] Backend is UP.")

    login_payload = json.dumps({"username": smoke["user_credentials"]["username"],
                                "password": smoke["user_credentials"]["password"]})
    put_remote_file(client, "/tmp/verify_login.json", login_payload)

    login_cmd = (
        "curl -sf -X POST http://127.0.0.1:18080/api/login/login "
        "-H 'Content-Type: application/json' "
        "--data @/tmp/verify_login.json"
    )
    out, err, rc = run_remote(client, login_cmd, timeout=20)
    print("[verify] Login raw response (first 200 chars):", out[:200])
    if not out.strip():
        print("[verify] ERROR: Empty login response. stderr:", err[:300])
        client.close()
        return

    try:
        login_data = json.loads(out)
    except json.JSONDecodeError as e:
        print("[verify] ERROR: Cannot parse login JSON:", e)
        print("[verify] Full output:", out)
        client.close()
        return

    data_field = login_data.get("data", {}) if isinstance(login_data.get("data"), dict) else {}
    token = data_field.get("token") or data_field.get("accessToken") or ""
    if not token:
        print("[verify] ERROR: No token in login response. Full response:")
        print(json.dumps(login_data, ensure_ascii=False)[:500])
        client.close()
        return
    print("[verify] Got token:", token[:30] + "...")

    goods_cmd = (
        "curl -sf 'http://127.0.0.1:18080/api/goods?current=1&size=5&excludeStatus=3' "
        "-H 'Authorization: Bearer " + token + "'"
    )
    out, err, rc = run_remote(client, goods_cmd, timeout=20)
    print("[verify] Goods raw response (first 300 chars):", out[:300])
    if not out.strip():
        print("[verify] ERROR: Empty goods response. stderr:", err[:300])
        client.close()
        return

    try:
        goods_data = json.loads(out)
    except json.JSONDecodeError as e:
        print("[verify] ERROR: Cannot parse goods JSON:", e)
        print("[verify] Full output:", out[:500])
        client.close()
        return

    inner = goods_data.get("data", goods_data) if isinstance(goods_data.get("data"), dict) else goods_data
    records = inner.get("records", [])
    total = inner.get("total", 0)
    print("[verify] Total goods: %d, returned %d records" % (total, len(records)))
    for g in records[:5]:
        gid = g.get("id")
        title = g.get("title", "")[:40]
        ext_id = g.get("externalGoodsId", "")
        status = g.get("status")
        print("  - id=%s title=%s extId=%s status=%s" % (gid, title, ext_id, status))

    if total == 0 and not records:
        print("[verify] WARNING: Still showing 0 goods. The fix may not be effective.")
    else:
        print("[verify] PASS: Goods list returns data.")

    stats_cmd = (
        "curl -sf http://127.0.0.1:18080/api/goods/stats "
        "-H 'Authorization: Bearer " + token + "'"
    )
    out, err, rc = run_remote(client, stats_cmd, timeout=20)
    print("[verify] Stats (first 400 chars):", out[:400])

    run_remote(client, "rm -f /tmp/verify_login.json")

    client.close()
    print("\n[verify] Verification complete.")


if __name__ == "__main__":
    main()
