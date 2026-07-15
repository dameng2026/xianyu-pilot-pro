#!/usr/bin/env python3
"""Quick backend deploy: upload changed source files and rebuild the backend Docker container."""
import json
import sys
import time
from pathlib import Path

import paramiko

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / ".deploy.prod.json"

# Files changed in this release
CHANGED_FILES = [
    "apps/core-api/src/main/java/com/xianyu/admin/mapper/XianyuGoodsMapper.java",
]


def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    backend = config["china_backend"]
    project_dir = backend["project_dir"]
    compose_env = backend.get("compose_env_file", ".env.production")

    print(f"[deploy] Connecting to {backend['host']}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=backend["host"],
        port=int(backend.get("port", 22)),
        username=backend["username"],
        password=backend["password"],
        timeout=20,
    )
    print("[deploy] Connected.")

    # Upload changed files
    sftp = client.open_sftp()
    for rel_path in CHANGED_FILES:
        local_path = REPO_ROOT / rel_path
        remote_path = f"{project_dir}/{rel_path}"
        print(f"[deploy] Upload: {local_path} -> {remote_path}")
        sftp.put(str(local_path), remote_path)
    sftp.close()
    print("[deploy] All files uploaded.")

    # Rebuild and restart the backend container
    compose_cmd = (
        f"cd {project_dir} && "
        f"docker compose -f docker-compose.yml -f docker-compose.prod.yml "
        f"--env-file {compose_env} build backend"
    )
    print(f"[deploy] Building backend image...")
    stdin, stdout, stderr = client.exec_command(
        f"bash -lc {repr(compose_cmd)}", timeout=600
    )
    exit_code = stdout.channel.recv_exit_status()
    for line in stdout:
        print(line, end="")
    for line in stderr:
        print(line, end="", file=sys.stderr)
    if exit_code != 0:
        print(f"[deploy] Build failed with exit code {exit_code}")
        client.close()
        sys.exit(1)
    print("[deploy] Build successful.")

    # Restart the container
    restart_cmd = (
        f"cd {project_dir} && "
        f"docker compose -f docker-compose.yml -f docker-compose.prod.yml "
        f"--env-file {compose_env} up -d --no-deps --force-recreate backend"
    )
    print(f"[deploy] Restarting backend container...")
    stdin, stdout, stderr = client.exec_command(
        f"bash -lc {repr(restart_cmd)}", timeout=120
    )
    exit_code = stdout.channel.recv_exit_status()
    for line in stdout:
        print(line, end="")
    for line in stderr:
        print(line, end="", file=sys.stderr)
    if exit_code != 0:
        print(f"[deploy] Restart failed with exit code {exit_code}")
        client.close()
        sys.exit(1)
    print("[deploy] Container restarted.")

    # Wait for health
    print("[deploy] Waiting for backend to become healthy...")
    health_url = "http://127.0.0.1:18080/api/health"
    for attempt in range(30):
        time.sleep(5)
        stdin, stdout, stderr = client.exec_command(
            f"curl -sf --max-time 5 {health_url} 2>/dev/null || true", timeout=10
        )
        output = stdout.read().decode("utf-8", "ignore")
        if '"UP"' in output:
            print(f"[deploy] Backend is healthy: {output.strip()}")
            break
        print(f"[deploy] Attempt {attempt + 1}/30: not healthy yet...")
    else:
        print("[deploy] WARNING: Backend did not become healthy within 150 seconds")
        # Check container status
        stdin, stdout, stderr = client.exec_command(
            f"cd {project_dir} && docker compose -f docker-compose.yml -f docker-compose.prod.yml "
            f"--env-file {compose_env} ps backend",
            timeout=30,
        )
        print(stdout.read().decode("utf-8", "ignore"))

    # Check fresh logs for errors
    print("[deploy] Checking recent backend logs for errors...")
    stdin, stdout, stderr = client.exec_command(
        f"cd {project_dir} && docker compose -f docker-compose.yml -f docker-compose.prod.yml "
        f"--env-file {compose_env} logs --tail=50 backend 2>&1 | grep -i 'error\\|exception\\|failed' | tail -10 || true",
        timeout=30,
    )
    log_errors = stdout.read().decode("utf-8", "ignore")
    if log_errors.strip():
        print(f"[deploy] Recent errors in logs:\n{log_errors}")
    else:
        print("[deploy] No errors found in recent logs.")

    client.close()
    print("[deploy] Done.")


if __name__ == "__main__":
    main()
