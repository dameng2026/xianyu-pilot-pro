#!/usr/bin/env python3
"""临时部署脚本：同步修改密码功能到线上（后端 jar + ALTER TABLE + 前端）"""
import paramiko
import sys
import os

CHINA_HOST = "1.12.66.249"
CHINA_USER = "ubuntu"
CHINA_PASS = "Slfasd123"
PROJECT_DIR = "/home/ubuntu/project"
LOCAL_JAR = os.path.join(os.path.dirname(__file__), "..", "apps", "core-api", "target", "xianyu-assistant-admin-backend-1.0.0.jar")

def run_remote(ssh, cmd, timeout=60):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    return out, err

def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "all"

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(CHINA_HOST, port=22, username=CHINA_USER, password=CHINA_PASS, timeout=15)
    print(f"[OK] Connected to {CHINA_HOST}")

    if action in ("alter", "all"):
        # 1. 获取 MySQL root 密码
        out, _ = run_remote(ssh, f"cd {PROJECT_DIR} && grep MYSQL_ROOT_PASSWORD .env.production | cut -d= -f2")
        mysql_pass = out.strip()
        if not mysql_pass:
            out, _ = run_remote(ssh, f"cd {PROJECT_DIR} && grep -i 'MYSQL_ROOT' .env.production")
            print(f"  MySQL env lines: {out}")
            mysql_pass = "xianyu_admin_2024"
        print(f"  MySQL password: {'*' * len(mysql_pass)}")

        # 2. 检查 operation_log 表结构
        out, err = run_remote(ssh,
            f"cd {PROJECT_DIR} && docker compose exec -T mysql mysql -uroot -p{mysql_pass} -D xianyu_assistant_admin -e \"SHOW COLUMNS FROM operation_log WHERE Field='tenant_id';\" 2>/dev/null")
        print(f"  operation_log tenant_id BEFORE: {out}")
        if err:
            print(f"  ERR: {err[:200]}")

        # 3. 执行 ALTER TABLE
        out, err = run_remote(ssh,
            f"cd {PROJECT_DIR} && docker compose exec -T mysql mysql -uroot -p{mysql_pass} -D xianyu_assistant_admin -e \"ALTER TABLE operation_log MODIFY COLUMN tenant_id bigint NULL DEFAULT NULL;\" 2>/dev/null")
        if err:
            print(f"  ALTER ERR: {err[:200]}")
        else:
            print("[OK] ALTER TABLE operation_log executed")

        # 4. 验证
        out, _ = run_remote(ssh,
            f"cd {PROJECT_DIR} && docker compose exec -T mysql mysql -uroot -p{mysql_pass} -D xianyu_assistant_admin -e \"SHOW COLUMNS FROM operation_log WHERE Field='tenant_id';\" 2>/dev/null")
        print(f"  operation_log tenant_id AFTER: {out}")

    if action in ("jar", "all"):
        # 5. 上传 jar
        local_jar = os.path.abspath(LOCAL_JAR)
        if not os.path.exists(local_jar):
            print(f"[FAIL] JAR not found: {local_jar}")
            ssh.close()
            sys.exit(1)
        print(f"  Uploading jar ({os.path.getsize(local_jar) // 1024 // 1024}MB)...")
        sftp = ssh.open_sftp()
        remote_jar = f"{PROJECT_DIR}/backend.jar"
        sftp.put(local_jar, remote_jar)
        print(f"[OK] JAR uploaded to {remote_jar}")
        sftp.close()

    if action in ("restart", "all"):
        # 6. 重启 backend 容器
        out, err = run_remote(ssh, f"cd {PROJECT_DIR} && docker compose restart backend", timeout=120)
        print(f"  restart stdout: {out}")
        if err:
            print(f"  restart stderr: {err[:300]}")
        print("[OK] Backend container restarted")

        # 7. 等待健康检查
        import time
        for i in range(15):
            time.sleep(3)
            out, _ = run_remote(ssh, "curl -s -o /dev/null -w '%{http_code}' http://localhost:18080/admin-api/health")
            print(f"  health check {i+1}: {out}")
            if out == "200":
                print("[OK] Backend healthy")
                break
        else:
            print("[WARN] Backend not healthy after 45s")

    ssh.close()
    print("[DONE]")

if __name__ == "__main__":
    main()
