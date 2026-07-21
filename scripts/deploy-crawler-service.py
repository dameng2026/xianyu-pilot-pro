#!/usr/bin/env python3
"""Quick crawler-service deploy: upload changed files and rebuild the crawler-service Docker container.

Specifically for the slider-solver fix:
- Dockerfile: install google-chrome-stable to replace Chrome for Testing 149 (SIGTRAP crash in headed)
- sliderSolver.ts: chromePaths add Linux paths + use channel:'chrome' on Linux + --no-sandbox args
"""
import json
import sys
import time
from pathlib import Path

import paramiko

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / ".deploy.prod.json"

# Files changed in this release
CHANGED_FILES = [
    "apps/crawler-service/Dockerfile",
    "apps/crawler-service/src/crawler/sliderSolver.ts",
]


def run_remote(client, cmd: str, timeout: int = 600, label: str = "") -> int:
    """Run a remote command via exec_command, stream stdout/stderr to console."""
    print(f"\n[remote]{f' [{label}]' if label else ''} $ {cmd}")
    stdin, stdout, stderr = client.exec_command(f"bash -lc {repr(cmd)}", timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    # Stream stdout
    for line in stdout:
        print(line, end="")
    for line in stderr:
        print(line, end="", file=sys.stderr)
    print(f"[remote] exit_code={exit_code}")
    return exit_code


def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    backend = config["china_backend"]
    project_dir = backend["project_dir"]
    compose_env = backend.get("compose_env_file", ".env.production")
    host = backend["host"]
    port = int(backend.get("port", 22))
    username = backend["username"]
    password = backend["password"]

    print(f"[deploy] Connecting to {username}@{host}:{port} ...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, port=port, username=username, password=password, timeout=20)
    print("[deploy] Connected.")

    # Step 1: pre-flight check current container status
    print("\n[step 1] Pre-flight check current crawler-service status")
    run_remote(client, f"cd {project_dir} && docker compose ps crawler-service", label="pre-check")

    # Step 2: upload changed files
    print("\n[step 2] Upload changed files via SFTP")
    sftp = client.open_sftp()
    for rel_path in CHANGED_FILES:
        local_path = REPO_ROOT / rel_path
        remote_path = f"{project_dir}/{rel_path}"
        # Ensure remote dir exists
        remote_dir = "/".join(remote_path.split("/")[:-1])
        run_remote(client, f"mkdir -p {remote_dir}", label="mkdir")
        print(f"[sftp] {local_path} -> {remote_path}")
        sftp.put(str(local_path), remote_path)
        # Verify upload via md5sum
        local_md5 = local_path.read_bytes().__hash__()
        # Use Python's hashlib locally
        import hashlib
        local_md5 = hashlib.md5(local_path.read_bytes()).hexdigest()
        rc = run_remote(client, f"md5sum {remote_path}", label="md5verify")
        if rc != 0:
            print(f"[deploy] md5sum failed for {remote_path}")
            sys.exit(1)
    sftp.close()
    print("[deploy] All files uploaded.")

    # Step 3: build new crawler-service image
    print("\n[step 3] Rebuild crawler-service image (this may take a while)")
    build_cmd = (
        f"cd {project_dir} && "
        f"docker compose -f docker-compose.yml -f docker-compose.prod.yml "
        f"--env-file {compose_env} build crawler-service"
    )
    rc = run_remote(client, build_cmd, timeout=900, label="build")
    if rc != 0:
        print(f"[deploy] Build failed with exit code {rc}")
        client.close()
        sys.exit(1)
    print("[deploy] Build successful.")

    # Step 4: recreate the container
    print("\n[step 4] Recreate crawler-service container")
    recreate_cmd = (
        f"cd {project_dir} && "
        f"docker compose -f docker-compose.yml -f docker-compose.prod.yml "
        f"--env-file {compose_env} up -d --no-deps --force-recreate crawler-service"
    )
    rc = run_remote(client, recreate_cmd, timeout=120, label="recreate")
    if rc != 0:
        print(f"[deploy] Recreate failed with exit code {rc}")
        client.close()
        sys.exit(1)
    print("[deploy] Container recreated.")

    # Step 5: wait for crawler-service health
    print("\n[step 5] Wait for crawler-service to become healthy")
    for attempt in range(30):
        time.sleep(3)
        rc = run_remote(
            client,
            "docker exec $(docker ps -q --filter name=crawler-service) wget -qO- http://127.0.0.1:3001/api/health 2>/dev/null || true",
            label=f"health-check-{attempt + 1}",
        )
        # Read the latest output via a separate exec_command to capture stdout
        stdin, stdout, stderr = client.exec_command(
            "docker exec $(docker ps -q --filter name=crawler-service) wget -qO- http://127.0.0.1:3001/api/health 2>/dev/null || true",
            timeout=10,
        )
        out = stdout.read().decode("utf-8", "ignore")
        if '"ok"' in out or "ok" in out.lower():
            print(f"[deploy] crawler-service healthy after {attempt + 1} attempts: {out.strip()}")
            break
    else:
        print("[deploy] crawler-service did not become healthy in 30 attempts")

    # Step 6: verify google-chrome-stable installed in container
    print("\n[step 6] Verify google-chrome-stable is installed in container")
    run_remote(
        client,
        "docker exec $(docker ps -q --filter name=crawler-service) bash -c 'which google-chrome-stable; google-chrome-stable --version; ls -la /opt/google/chrome/chrome'",
        label="chrome-version",
    )

    # Step 7: verify DISPLAY env
    print("\n[step 7] Verify Xvfb DISPLAY env")
    run_remote(
        client,
        "docker exec $(docker ps -q --filter name=crawler-service) bash -c 'echo DISPLAY=$DISPLAY; ps aux | grep -i xvfb | grep -v grep'",
        label="display-env",
    )

    print("\n[deploy] All steps complete. Container is up.")
    client.close()


if __name__ == "__main__":
    main()
