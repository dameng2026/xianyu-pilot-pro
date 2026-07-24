#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""部署 user-web + admin-web dist 到 US 服务器"""
import os
import sys
import time
import paramiko

HOST = '154.9.254.86'
USER = 'root'
PASS = 'IkyuM1cakgilY5Vz'

REPO_ROOT = r'g:\源码\xianyu-assistant-package-temp'
FRONTENDS = [
    {
        'name': 'user-web',
        'local': os.path.join(REPO_ROOT, 'apps', 'user-web', 'dist'),
        'remote': '/var/www/user-web',
        'port': 81,
    },
    {
        'name': 'admin-web',
        'local': os.path.join(REPO_ROOT, 'apps', 'admin-web', 'dist'),
        'remote': '/var/www/admin-web',
        'port': 82,
    },
]


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
            if count % 50 == 0:
                print(f'  已上传 {count} 个文件...')
    return count


def deploy_frontend(ssh, sftp, name, local_dir, remote_dir, port):
    print(f'\n{"=" * 60}')
    print(f'部署 {name}: {local_dir} -> {remote_dir}')
    print(f'{"=" * 60}')

    if not os.path.isdir(local_dir):
        print(f'[FAIL] 本地 dist 不存在: {local_dir}')
        return False

    timestamp = int(time.time())
    backup_dir = f'{remote_dir}.bak.{timestamp}'

    # 1. 备份并重建目录
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
        return False
    print(f'备份完成 -> {backup_dir}')

    # 2. 上传
    count = upload_dir(sftp, local_dir, remote_dir)
    print(f'{name}: 上传 {count} 个文件')

    # 3. 验证 index.html
    ec, out, err = run_cmd(ssh, f'ls -la "{remote_dir}/index.html"')
    if ec != 0:
        print(f'ERROR: index.html 不存在: {err}')
        return False
    print(f'index.html 验证通过:\n{out.strip()}')

    # 4. 设置权限
    perm_cmd = (
        f'chown -R www-data:www-data {remote_dir} 2>/dev/null '
        f'|| chown -R nginx:nginx {remote_dir} 2>/dev/null '
        f'|| true; '
        f'chmod -R 755 {remote_dir}; '
        f'echo "权限设置完成"'
    )
    ec, out, err = run_cmd(ssh, perm_cmd, timeout=120)
    print(out.strip())

    # 5. 验证 HTTP
    ec, out, err = run_cmd(ssh, f'curl -s -o /dev/null -w "%{{http_code}}" http://localhost:{port}/')
    http_code = out.strip()
    print(f'{name} (port {port}): HTTP {http_code}')

    if http_code == '200':
        print(f'✓ {name} 部署成功')
        return True
    else:
        print(f'✗ {name} 部署异常 (HTTP {http_code})')
        return False


def main():
    print(f'连接 US 服务器 {USER}@{HOST} ...')
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=20)
    print('SSH 连接成功')
    sftp = ssh.open_sftp()

    results = {}
    for fe in FRONTENDS:
        ok = deploy_frontend(ssh, sftp, fe['name'], fe['local'], fe['remote'], fe['port'])
        results[fe['name']] = ok

    # 重载 nginx（一次即可）
    print('\n=== 重载 nginx ===')
    ec, out, err = run_cmd(ssh, 'nginx -t 2>&1')
    print(f'nginx -t:\n{out.strip()}')
    if ec != 0:
        print(f'nginx -t 失败: {err}')
    else:
        ec, out, err = run_cmd(ssh, 'nginx -s reload 2>&1')
        print(f'nginx -s reload: {out.strip()} (exit={ec})')

    sftp.close()
    ssh.close()

    print('\n=== 部署汇总 ===')
    all_ok = True
    for name, ok in results.items():
        status = '✓ 成功' if ok else '✗ 失败'
        print(f'  {name}: {status}')
        if not ok:
            all_ok = False

    sys.exit(0 if all_ok else 1)


if __name__ == '__main__':
    main()
