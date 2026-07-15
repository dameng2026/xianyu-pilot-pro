#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""临时部署脚本：仅上传 admin-web dist 到 US 服务器（修改密码功能前端）"""
import os
import sys
import time
import paramiko

HOST = '154.9.254.86'
USER = 'root'
PASS = 'IkyuM1cakgilY5Vz'

ADMIN_WEB_LOCAL = r'g:\源码\xianyu-assistant-package-temp\apps\admin-web\dist'
ADMIN_WEB_REMOTE = '/var/www/admin-web'


def run_cmd(ssh, cmd, timeout=120):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', 'ignore')
    err = stderr.read().decode('utf-8', 'ignore')
    exit_code = stdout.channel.recv_exit_status()
    return exit_code, out, err


def upload_dir(sftp, local_dir, remote_dir, count=0):
    try:
        sftp.stat(remote_dir)
    except FileNotFoundError:
        sftp.mkdir(remote_dir)
    for item in os.listdir(local_dir):
        local_path = os.path.join(local_dir, item)
        remote_path = f'{remote_dir}/{item}'
        if os.path.isdir(local_path):
            count = upload_dir(sftp, local_path, remote_path, count)
        elif os.path.isfile(local_path):
            sftp.put(local_path, remote_path)
            count += 1
            if count % 30 == 0:
                print(f'  已上传 {count} 个文件...')
    return count


def main():
    if not os.path.isdir(ADMIN_WEB_LOCAL):
        print(f'[FAIL] 本地 dist 不存在: {ADMIN_WEB_LOCAL}')
        sys.exit(1)

    print(f'连接 US 服务器 {USER}@{HOST} ...')
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=20)
    print('SSH 连接成功')
    sftp = ssh.open_sftp()

    timestamp = int(time.time())
    backup_dir = f'{ADMIN_WEB_REMOTE}.bak.{timestamp}'

    # 1. 备份并重建目录
    backup_cmd = (
        f'if [ -d "{ADMIN_WEB_REMOTE}" ]; then '
        f'  mv "{ADMIN_WEB_REMOTE}" "{backup_dir}"; '
        f'fi; '
        f'mkdir -p "{ADMIN_WEB_REMOTE}"'
    )
    print(f'备份: {backup_cmd}')
    ec, out, err = run_cmd(ssh, backup_cmd, timeout=60)
    if ec != 0:
        print(f'备份失败 exit={ec}: {err}')
        sys.exit(1)
    print(f'备份完成 -> {backup_dir}')

    # 2. 上传
    count = upload_dir(sftp, ADMIN_WEB_LOCAL, ADMIN_WEB_REMOTE)
    print(f'admin-web: 上传 {count} 个文件')

    # 3. 验证 index.html
    ec, out, err = run_cmd(ssh, f'ls -la "{ADMIN_WEB_REMOTE}/index.html"')
    if ec != 0:
        print(f'ERROR: index.html 不存在: {err}')
        sys.exit(1)
    print(f'index.html 验证通过:\n{out.strip()}')

    # 4. 设置权限
    print('\n=== 设置文件权限 ===')
    perm_cmd = (
        'chown -R www-data:www-data /var/www/admin-web 2>/dev/null '
        '|| chown -R nginx:nginx /var/www/admin-web 2>/dev/null '
        '|| true; '
        'chmod -R 755 /var/www/admin-web; '
        'echo "权限设置完成"'
    )
    ec, out, err = run_cmd(ssh, perm_cmd, timeout=60)
    print(out.strip())

    # 5. 重载 nginx
    print('\n=== 重载 nginx ===')
    ec, out, err = run_cmd(ssh, 'nginx -t 2>&1')
    print(f'nginx -t:\n{out.strip()}')
    if ec != 0:
        print(f'nginx -t 失败: {err}')
        sys.exit(1)
    ec, out, err = run_cmd(ssh, 'nginx -s reload 2>&1')
    print(f'nginx -s reload: {out.strip()} (exit={ec})')

    # 6. 验证 HTTP
    ec, out, err = run_cmd(ssh, 'curl -s -o /dev/null -w "%{http_code}" http://localhost:82/')
    admin_code = out.strip()
    print(f'\nadmin-web (port 82): HTTP {admin_code}')

    if admin_code == '200':
        print('\n✓ admin-web 部署成功')
        result = 0
    else:
        print('\n✗ admin-web 部署异常')
        result = 1

    sftp.close()
    ssh.close()
    sys.exit(result)


if __name__ == '__main__':
    main()
