#!/usr/bin/env python3
"""Wait for backend to become healthy."""
import json
import time
import paramiko

CONFIG_PATH = ".deploy.prod.json"


def run_remote(client, cmd, timeout=15):
    quoted = "'" + cmd.replace("'", "'\"'\"'") + "'"
    full_cmd = "bash -lc " + quoted
    stdin, stdout, stderr = client.exec_command(full_cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "ignore")
    return out


def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    backend = config["china_backend"]
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=backend["host"], port=22,
        username=backend["username"], password=backend["password"],
        timeout=20,
    )
    print("[wait] Connected")

    for i in range(20):
        out = run_remote(client, "curl -sf --max-time 5 http://127.0.0.1:18080/api/health 2>/dev/null || echo HEALTH_FAILED")
        status = out.strip()
        print("[wait] Attempt %d/20: %s" % (i + 1, status[:120]))
        if '"UP"' in status:
            print("[wait] Backend is UP!")
            # Also check container status
            out2 = run_remote(client, "docker ps --filter name=xianyu-admin --format '{{.Names}} {{.Status}}'")
            print("[wait] Containers:\n" + out2)
            break
        time.sleep(10)
    else:
        print("[wait] Backend did not become healthy. Checking logs...")
        out2 = run_remote(client, "docker logs --tail 30 xianyu-admin-backend 2>&1 | tail -20", timeout=30)
        print(out2)

    client.close()


if __name__ == "__main__":
    main()
