#!/usr/bin/env python3
"""Deploy API slider solve fixes: upload Java + Python files and rebuild affected containers."""
import json
import sys
import time
from pathlib import Path

import paramiko

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / ".deploy.prod.json"

# Files changed in this release
CHANGED_FILES = [
    # Java: precheck_rejected record creation + status mapping fix
    "apps/core-api/src/main/java/com/xianyu/admin/service/ApiSliderSolveService.java",
    # Python: timeout detection + record creation order fix
    "apps/automation-service/app/services/captcha_api_solver.py",
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
        # Ensure remote directory exists
        remote_dir = "/".join(remote_path.split("/")[:-1])
        stdin, stdout, stderr = client.exec_command(f"mkdir -p {remote_dir}", timeout=10)
        stdout.channel.recv_exit_status()
        print(f"[deploy] Upload: {local_path} -> {remote_path}")
        sftp.put(str(local_path), remote_path)
    sftp.close()
    print("[deploy] All files uploaded.")

    # Rebuild and restart the backend (Java) container
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
    print("[deploy] Backend build successful.")

    # Restart the backend container
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
    print("[deploy] Backend container restarted.")

    # Restart the automation + automation-worker containers (Python files changed)
    for svc in ("automation", "automation-worker"):
        restart_cmd = (
            f"cd {project_dir} && "
            f"docker compose -f docker-compose.yml -f docker-compose.prod.yml "
            f"--env-file {compose_env} up -d --no-deps --force-recreate {svc}"
        )
        print(f"[deploy] Restarting {svc} container...")
        stdin, stdout, stderr = client.exec_command(
            f"bash -lc {repr(restart_cmd)}", timeout=120
        )
        exit_code = stdout.channel.recv_exit_status()
        for line in stdout:
            print(line, end="")
        for line in stderr:
            print(line, end="", file=sys.stderr)
        if exit_code != 0:
            print(f"[deploy] {svc} restart failed with exit code {exit_code}")
            client.close()
            sys.exit(1)
        print(f"[deploy] {svc} container restarted.")

    # Wait for backend health
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
        print("[deploy] No errors found in recent backend logs.")

    # Check automation logs
    print("[deploy] Checking recent automation logs for errors...")
    stdin, stdout, stderr = client.exec_command(
        f"cd {project_dir} && docker compose -f docker-compose.yml -f docker-compose.prod.yml "
        f"--env-file {compose_env} logs --tail=30 automation 2>&1 | grep -i 'error\\|exception\\|traceback' | tail -10 || true",
        timeout=30,
    )
    log_errors = stdout.read().decode("utf-8", "ignore")
    if log_errors.strip():
        print(f"[deploy] Recent errors in automation logs:\n{log_errors}")
    else:
        print("[deploy] No errors found in recent automation logs.")

    client.close()
    print("[deploy] Done.")


if __name__ == "__main__":
    main()
