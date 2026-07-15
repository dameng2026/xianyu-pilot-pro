#!/usr/bin/env python3
"""Deploy ws_startup.py fix to production China backend (1.12.66.249)."""
import os
import sys
import time
import paramiko

HOST = "1.12.66.249"
PORT = 22
USER = "ubuntu"
SSH_KEY = os.path.expanduser("~/.ssh/id_ed25519")
PROJECT_DIR = "/home/ubuntu/project"
LOCAL_FILE = os.path.join(
    os.path.dirname(__file__),
    "apps", "automation-service", "app", "services", "ws_startup.py"
)
REMOTE_FILE = f"{PROJECT_DIR}/apps/automation-service/app/services/ws_startup.py"
BACKUP_FILE = f"{REMOTE_FILE}.bak-{int(time.time())}"


def run_cmd(remote, cmd, timeout=300):
    print(f"[deploy] $ {cmd}")
    stdin, stdout, stderr = remote.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out.strip():
        print(out.rstrip())
    if err.strip():
        print(f"[stderr] {err.rstrip()}")
    print(f"[deploy] exit_code={exit_code}")
    return exit_code, out, err


def main():
    if not os.path.isfile(LOCAL_FILE):
        print(f"[deploy] ERROR: local file not found: {LOCAL_FILE}")
        sys.exit(1)

    print(f"[deploy] Connecting to {USER}@{HOST}:{PORT} via SSH key...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, key_filename=SSH_KEY, timeout=30)
    sftp = client.open_sftp()
    print("[deploy] Connected.")

    # 1. Verify remote file exists
    print(f"\n[deploy] Step 1: Verify remote file exists: {REMOTE_FILE}")
    exit_code, out, err = run_cmd(client, f"test -f {REMOTE_FILE} && echo EXISTS || echo MISSING")
    if exit_code != 0 or "EXISTS" not in out:
        print(f"[deploy] ERROR: remote file not found: {REMOTE_FILE}")
        print(f"[deploy] stderr: {err}")
        sys.exit(1)

    # 2. Backup current file
    print(f"\n[deploy] Step 2: Backup current file to {BACKUP_FILE}")
    exit_code, out, err = run_cmd(client, f"cp {REMOTE_FILE} {BACKUP_FILE}")
    if exit_code != 0:
        print(f"[deploy] ERROR: backup failed")
        sys.exit(1)

    # 3. Upload new file
    print(f"\n[deploy] Step 3: Upload new ws_startup.py")
    sftp.put(LOCAL_FILE, REMOTE_FILE)
    print(f"[deploy] Uploaded {os.path.basename(LOCAL_FILE)} -> {REMOTE_FILE}")

    # 4. Verify file was uploaded correctly (compare line count)
    print(f"\n[deploy] Step 4: Verify uploaded file")
    local_lines = len(open(LOCAL_FILE, encoding="utf-8").readlines())
    exit_code, out, err = run_cmd(client, f"wc -l < {REMOTE_FILE}")
    remote_lines = int(out.strip()) if out.strip() else 0
    print(f"[deploy] local lines={local_lines}, remote lines={remote_lines}")
    if abs(local_lines - remote_lines) > 5:
        print(f"[deploy] WARNING: line count mismatch, verifying content...")
    # Quick content check
    exit_code, out, err = run_cmd(client, f"grep -c 'auto_start_all' {REMOTE_FILE}")
    if "1" not in out:
        print(f"[deploy] ERROR: uploaded file doesn't contain auto_start_all function")
        sys.exit(1)

    # 5. Rebuild automation-service Docker image
    print(f"\n[deploy] Step 5: Rebuild automation-service Docker image")
    rebuild_cmd = (
        f"cd {PROJECT_DIR} && "
        f"docker compose -f docker-compose.yml -f docker-compose.prod.yml "
        f"--env-file .env.production build automation 2>&1"
    )
    exit_code, out, err = run_cmd(client, rebuild_cmd, timeout=600)
    if exit_code != 0:
        print(f"[deploy] ERROR: Docker build failed")
        sys.exit(1)

    # 6. Restart automation-service container
    print(f"\n[deploy] Step 6: Restart automation-service container")
    restart_cmd = (
        f"cd {PROJECT_DIR} && "
        f"docker compose -f docker-compose.yml -f docker-compose.prod.yml "
        f"--env-file .env.production up -d automation 2>&1"
    )
    exit_code, out, err = run_cmd(client, restart_cmd, timeout=120)
    if exit_code != 0:
        print(f"[deploy] ERROR: Docker restart failed")
        sys.exit(1)

    # 7. Wait and check health
    print(f"\n[deploy] Step 7: Wait for container to be healthy...")
    time.sleep(10)
    exit_code, out, err = run_cmd(client, "docker ps --filter name=xianyu-automation-service --format '{{.Status}}'")
    print(f"[deploy] Container status: {out.strip()}")

    # 8. Check automation-service logs for startup
    print(f"\n[deploy] Step 8: Check startup logs")
    exit_code, out, err = run_cmd(
        client,
        "docker logs xianyu-automation-service --tail 30 2>&1"
    )

    # 9. Check backend health
    print(f"\n[deploy] Step 9: Health check")
    exit_code, out, err = run_cmd(client, "curl -s -o /dev/null -w '%{http_code}' http://localhost:18080/api/health")
    print(f"[deploy] Backend health HTTP status: {out.strip()}")

    print("\n[deploy] Backend deployment complete!")
    sftp.close()
    client.close()


if __name__ == "__main__":
    main()
