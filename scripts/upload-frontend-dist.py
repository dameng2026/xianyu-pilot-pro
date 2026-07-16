#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SFTP upload local dist to US production frontends."""
import os
import sys
import time
import paramiko

HOST = '154.9.254.86'
USER = 'root'
PASS = 'IkyuM1cakgilY5Vz'

USER_WEB_LOCAL = r'g:\源码\xianyu-assistant-package-temp\apps\user-web\dist'
ADMIN_WEB_LOCAL = r'g:\源码\xianyu-assistant-package-temp\apps\admin-web\dist'
USER_WEB_REMOTE = '/var/www/user-web'
ADMIN_WEB_REMOTE = '/var/www/admin-web'


def run_cmd(ssh, cmd, timeout=120):
    """Execute command and wait for completion, return (exit_code, stdout, stderr)."""
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', 'ignore')
    err = stderr.read().decode('utf-8', 'ignore')
    exit_code = stdout.channel.recv_exit_status()
    return exit_code, out, err


def upload_dir(sftp, ssh, local_dir, remote_dir, count=0):
    """Recursively upload a local directory to remote via SFTP."""
    try:
        sftp.stat(remote_dir)
    except FileNotFoundError:
        sftp.mkdir(remote_dir)

    for item in os.listdir(local_dir):
        local_path = os.path.join(local_dir, item)
        remote_path = f'{remote_dir}/{item}'
        if os.path.isdir(local_path):
            count = upload_dir(sftp, ssh, local_path, remote_path, count)
        elif os.path.isfile(local_path):
            sftp.put(local_path, remote_path)
            count += 1
            if count % 50 == 0:
                print(f'  已上传 {count} 个文件...')
    return count


def deploy_one(ssh, sftp, label, local_dir, remote_dir, timestamp):
    """Backup, clear, upload, verify one frontend."""
    print(f'\n=== 部署 {label} ===')
    backup_dir = f'{remote_dir}.bak.{timestamp}'

    # 1. Backup existing dir (mv), then create fresh empty dir
    backup_cmd = (
        f'if [ -d "{remote_dir}" ]; then '
        f'  mv "{remote_dir}" "{backup_dir}"; '
        f'fi; '
        f'mkdir -p "{remote_dir}"'
    )
    print(f'备份: {backup_cmd}')
    ec, out, err = run_cmd(ssh, backup_cmd, timeout=60)
    if ec != 0:
        print(f'备份失败 exit={ec}: {err}')
        sys.exit(1)
    print(f'备份完成 -> {backup_dir}')

    # 2. Upload dist contents
    count = upload_dir(sftp, ssh, local_dir, remote_dir)
    print(f'{label}: 上传 {count} 个文件')

    # 3. Verify index.html exists in root
    ec, out, err = run_cmd(ssh, f'ls -la "{remote_dir}/index.html"')
    if ec != 0:
        print(f'ERROR: index.html 不存在于 {remote_dir}/')
        print(f'stderr: {err}')
        sys.exit(1)
    print(f'index.html 验证通过:\n{out.strip()}')

    # 4. List top-level entries for sanity
    ec, out, err = run_cmd(ssh, f'ls -la "{remote_dir}" | head -20')
    print(f'{remote_dir} 顶层内容:\n{out.strip()}')

    return count, backup_dir


def main():
    print(f'连接服务器 {USER}@{HOST} ...')
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=20)
    print('SSH 连接成功')
    sftp = ssh.open_sftp()

    timestamp = int(time.time())
    total_files = 0

    # Deploy user-web
    n, user_bak = deploy_one(ssh, sftp, 'user-web', USER_WEB_LOCAL, USER_WEB_REMOTE, timestamp)
    total_files += n

    # Deploy admin-web
    n, admin_bak = deploy_one(ssh, sftp, 'admin-web', ADMIN_WEB_LOCAL, ADMIN_WEB_REMOTE, timestamp)
    total_files += n

    # 5. Set permissions (try www-data first, fall back to nginx, then root)
    print('\n=== 设置文件权限 ===')
    perm_cmd = (
        'chown -R www-data:www-data /var/www/user-web /var/www/admin-web 2>/dev/null '
        '|| chown -R nginx:nginx /var/www/user-web /var/www/admin-web 2>/dev/null '
        '|| true; '
        'chmod -R 755 /var/www/user-web /var/www/admin-web; '
        'echo "权限设置完成"'
    )
    ec, out, err = run_cmd(ssh, perm_cmd, timeout=120)
    print(out.strip())
    if ec != 0:
        print(f'权限设置警告 exit={ec}: {err}')

    # 6. Test and reload nginx
    print('\n=== 重载 nginx ===')
    ec, out, err = run_cmd(ssh, 'nginx -t 2>&1')
    print(f'nginx -t:\n{out.strip()}')
    if ec != 0:
        print(f'nginx -t 失败: {err}')
        sys.exit(1)

    ec, out, err = run_cmd(ssh, 'nginx -s reload 2>&1')
    print(f'nginx -s reload: {out.strip()} (exit={ec})')
    if ec != 0:
        print(f'nginx reload 失败: {err}')
        sys.exit(1)

    # 7. Verify HTTP 200 on both ports
    print('\n=== 验证 HTTP 访问 ===')
    ec, out, err = run_cmd(ssh, 'curl -s -o /dev/null -w "%{http_code}" http://localhost:81/')
    user_code = out.strip()
    print(f'user-web (port 81): HTTP {user_code}')

    ec, out, err = run_cmd(ssh, 'curl -s -o /dev/null -w "%{http_code}" http://localhost:82/')
    admin_code = out.strip()
    print(f'admin-web (port 82): HTTP {admin_code}')

    # Also verify index.html existence one more time
    print('\n=== index.html 最终检查 ===')
    ec, out, err = run_cmd(
        ssh,
        'ls -la /var/www/user-web/index.html /var/www/admin-web/index.html'
    )
    print(out.strip())
    if ec != 0:
        print(f'index.html 检查失败: {err}')
        sys.exit(1)

    # Summary
    print('\n========== 部署汇总 ==========')
    print(f'总上传文件数: {total_files}')
    print(f'user-web 备份: {user_bak}')
    print(f'admin-web 备份: {admin_bak}')
    print(f'user-web HTTP: {user_code}')
    print(f'admin-web HTTP: {admin_code}')

    if user_code == '200' and admin_code == '200':
        print('\n✓ 部署成功: 两个前端均返回 HTTP 200')
        result = 0
    else:
        print('\n✗ 部署异常: HTTP 状态码非 200，请检查')
        result = 1

    sftp.close()
    ssh.close()
    sys.exit(result)


if __name__ == '__main__':
    main()
