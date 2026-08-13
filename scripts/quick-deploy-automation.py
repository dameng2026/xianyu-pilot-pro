#!/usr/bin/env python3
"""Quick deploy: upload modified automation-service files and rebuild containers."""
import json
import sys
import time
import paramiko

CONFIG_PATH = ".deploy.prod.json"

CHANGED_FILES = [
    "apps/automation-service/app/services/captcha_queue.py",
    "apps/automation-service/app/services/ws_token.py",
    "apps/automation-service/app/services/ws_client.py",
]

# Containers that share the automation-service image
CONTAINERS = ["automation", "automation-worker"]


def run_remote(client, cmd, timeout=300):
    quoted = "'" + cmd.replace("'", "'\"'\"'") + "'"
    full_cmd = "bash -lc " + quoted
    stdin, stdout, stderr = client.exec_command(full_cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    exit_code = stdout.channel.recv_exit_status()
    return out, err, exit_code


def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    backend = config["china_backend"]
    project_dir = backend["project_dir"]
    compose_env = backend["compose_env_file"]

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=backend["host"],
        port=22,
        username=backend["username"],
        password=backend["password"],
        timeout=20,
    )
    print("[deploy] Connected to", backend["host"])

    # Upload changed files via SFTP
    sftp = client.open_sftp()
    for local_path in CHANGED_FILES:
        remote_path = project_dir + "/" + local_path
        print("[deploy] Uploading %s -> %s" % (local_path, remote_path))
        sftp.put(local_path, remote_path)
    sftp.close()
    print("[deploy] All files uploaded.")

    # Rebuild and recreate automation containers
    compose_cmd = (
        "cd " + project_dir + " && "
        "docker compose -f docker-compose.yml -f docker-compose.prod.yml "
        "--env-file " + compose_env + " build " + " ".join(CONTAINERS)
    )
    print("[deploy] Building images...")
    out, err, rc = run_remote(client, compose_cmd, timeout=600)
    print("[deploy] Build output (last 500 chars):", out[-500:])
    if err:
        print("[deploy] Build stderr (last 300 chars):", err[-300:])
    if rc != 0:
        print("[deploy] ERROR: Build failed with exit code", rc)
        client.close()
        sys.exit(1)

    recreate_cmd = (
        "cd " + project_dir + " && "
        "docker compose -f docker-compose.yml -f docker-compose.prod.yml "
        "--env-file " + compose_env + " up -d --no-deps --force-recreate " + " ".join(CONTAINERS)
    )
    print("[deploy] Recreating containers...")
    out, err, rc = run_remote(client, recreate_cmd, timeout=120)
    print("[deploy] Recreate output:", out[-400:])
    if rc != 0:
        print("[deploy] ERROR: Recreate failed with exit code", rc)
        client.close()
        sys.exit(1)

    # Wait for automation service to be healthy
    print("[deploy] Waiting for automation service to start...")
    for i in range(15):
        time.sleep(5)
        out, _, _ = run_remote(client, "docker ps --filter name=xianyu-automation-service --format '{{.Status}}'", timeout=10)
        status = out.strip()
        print("[deploy] Attempt %d: %s" % (i + 1, status))
        if "healthy" in status:
            print("[deploy] Automation service is healthy.")
            break
    else:
        print("[deploy] WARNING: Automation service not healthy after 75s. Checking logs...")
        out, _, _ = run_remote(client, "docker logs --tail 30 xianyu-automation-service 2>&1", timeout=15)
        print(out)

    # Show final container status
    out, _, _ = run_remote(client, "docker ps --filter name=xianyu-automation --format '{{.Names}} {{.Status}}'", timeout=10)
    print("[deploy] Final container status:\n", out)

    client.close()
    print("[deploy] Deployment complete.")


if __name__ == "__main__":
    main()
