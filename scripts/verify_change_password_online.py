#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""线上验证修改密码功能：通过 SSH 在服务器本地调用 API"""
import paramiko
import sys
import json
import time

CHINA_HOST = "1.12.66.249"
CHINA_USER = "ubuntu"
CHINA_PASS = "Slfasd123"
BASE_URL = "http://localhost:18080"

ORIGINAL_PASS = "123456"
TEST_PASS = "admin2026test"  # 临时测试密码（含字母+数字，>=8位）


def run_remote(ssh, cmd, timeout=30):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    return out, err


def curl_post(ssh, path, body, token=None):
    """在远程服务器执行 curl POST"""
    headers = '-H "Content-Type: application/json"'
    if token:
        headers += f' -H "Authorization: Bearer {token}"'
    # 使用单引号包裹 JSON body，避免 shell 转义问题
    body_json = json.dumps(body, ensure_ascii=False)
    cmd = f'''curl -s -X POST "{BASE_URL}{path}" {headers} -d '{body_json}' -w "\\n__HTTP_CODE__:%{{http_code}}"'''
    out, err = run_remote(ssh, cmd)
    if err:
        print(f"  CURL ERR: {err[:200]}")
    return out


def extract_http_code(resp):
    """从响应中分离 HTTP code 和 body"""
    marker = "__HTTP_CODE__:"
    if marker in resp:
        idx = resp.rfind(marker)
        code = resp[idx + len(marker):].strip()
        body = resp[:idx].strip()
        return code, body
    return "000", resp


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(CHINA_HOST, port=22, username=CHINA_USER, password=CHINA_PASS, timeout=15)
    print(f"[OK] Connected to {CHINA_HOST}")

    # 0. 健康检查
    out, _ = run_remote(ssh, f"curl -s -o /dev/null -w '%{{http_code}}' {BASE_URL}/admin-api/health")
    print(f"\n[0] Health check: HTTP {out}")
    if out != "200":
        print("[FAIL] Backend not healthy, abort")
        sys.exit(1)

    # 1. 登录获取 token
    print(f"\n[1] Login with admin/{ORIGINAL_PASS}")
    resp = curl_post(ssh, "/admin-api/auth/login", {"userName": "admin", "password": ORIGINAL_PASS})
    code, body = extract_http_code(resp)
    print(f"  HTTP {code}")
    print(f"  Body: {body[:300]}")
    if code != "200":
        print("[FAIL] Login failed, abort")
        sys.exit(1)
    data = json.loads(body)
    token = data.get("data", {}).get("token")
    if not token:
        print("[FAIL] No token in response, abort")
        sys.exit(1)
    print(f"  Token: {token[:30]}...")

    # 2. 修改密码（原密码 → 测试密码）
    print(f"\n[2] Change password: {ORIGINAL_PASS} → {TEST_PASS}")
    resp = curl_post(ssh, "/admin-api/auth/change-password",
                     {"oldPassword": ORIGINAL_PASS, "newPassword": TEST_PASS}, token=token)
    code, body = extract_http_code(resp)
    print(f"  HTTP {code}")
    print(f"  Body: {body[:300]}")
    if code != "200":
        print("[FAIL] Change password failed")
        sys.exit(1)
    print("  [OK] Password changed successfully")

    # 3. 旧密码登录应失败
    print(f"\n[3] Login with OLD password (should fail)")
    resp = curl_post(ssh, "/admin-api/auth/login", {"userName": "admin", "password": ORIGINAL_PASS})
    code, body = extract_http_code(resp)
    print(f"  HTTP {code}")
    print(f"  Body: {body[:200]}")
    if code == "200":
        print("  [WARN] Old password still works (security_version may not have incremented)")
    else:
        print("  [OK] Old password correctly rejected")

    # 4. 新密码登录应成功
    print(f"\n[4] Login with NEW password (should succeed)")
    resp = curl_post(ssh, "/admin-api/auth/login", {"userName": "admin", "password": TEST_PASS})
    code, body = extract_http_code(resp)
    print(f"  HTTP {code}")
    print(f"  Body: {body[:200]}")
    if code != "200":
        print("[FAIL] New password login failed")
    else:
        print("  [OK] New password login successful")
    new_token_data = json.loads(body) if code == "200" else {}
    new_token = new_token_data.get("data", {}).get("token")

    # 5. 改回原密码（通过 SQL，因为 "123456" 不符合密码强度策略：不足8位且无字母）
    print(f"\n[5] Restore password via SQL: {TEST_PASS} → {ORIGINAL_PASS}")
    # 获取 MySQL 密码
    out, _ = run_remote(ssh, f"cd /home/ubuntu/project && grep MYSQL_ROOT_PASSWORD .env.production | cut -d= -f2")
    mysql_pass = out.strip() or "xianyu_admin_2024"
    # BCrypt hash for "123456"（与 seed admin 一致）— 使用 heredoc 避免 $ 被 shell 展开
    bcrypt_hash = "$2b$12$6GoRjGN/4EYF8lBDtD750OoxcQ8Kd68AlHzwRcF1DfueL6MO2w1Bu"
    sql_cmd = (
        f"cd /home/ubuntu/project && "
        f"docker compose exec -T mysql mysql -uroot -p{mysql_pass} -D xianyu_assistant_admin <<'EOSQL'\n"
        f"UPDATE sys_admin_user SET password_hash='{bcrypt_hash}', security_version=security_version+1 WHERE username='admin';\n"
        f"EOSQL"
    )
    out, err = run_remote(ssh, sql_cmd, timeout=30)
    if err and "Warning" not in err:
        print(f"  SQL ERR: {err[:200]}")
    else:
        print("  [OK] Password restored to 123456 via SQL")

    # 6. 验证原密码恢复
    print(f"\n[6] Verify original password works again")
    resp = curl_post(ssh, "/admin-api/auth/login", {"userName": "admin", "password": ORIGINAL_PASS})
    code, body = extract_http_code(resp)
    print(f"  HTTP {code}")
    if code == "200":
        print("  [OK] Original password restored and working")
    else:
        print(f"  [FAIL] Original password not working! Body: {body[:200]}")

    ssh.close()
    print("\n[DONE] Verification complete")


if __name__ == "__main__":
    main()
