#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""增量同步前端 dist 到美国生产服务器（基于 md5 比对，自动同步所有变更文件）。

相比 upload-frontend-dist.py（每次全量 mv 备份 + 上传），本脚本：
- 遍历本地 dist 全部文件，对比远端 md5，仅上传变更/新增文件
- 删除远端已不存在的文件（避免旧 chunk 残留导致浏览器缓存的旧 index.html 404）
- 跳过备份步骤（既有 .bak.* 由全量脚本保留）
- 适合每次上线前端的标准部署

⚠️ 重要：Vite 构建时即便只改一个文件，依赖图变化也会导致大量 chunk hash 变化。
        必须基于本地 dist 全量比对，不能只传"你以为改了的"文件。

用法：
    python scripts/upload-frontend-patch.py                # 同步 user-web dist
    python scripts/upload-frontend-patch.py --target admin # 同步 admin-web dist
    python scripts/upload-frontend-patch.py --target both  # 同步两个前端
    python scripts/upload-frontend-patch.py --dry-run      # 仅打印将同步的文件

环境变量：
    US_FRONTEND_HOST / US_FRONTEND_USER / US_FRONTEND_PASS 可覆盖默认凭据
"""
import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path

try:
    import paramiko
except ImportError:
    print('ERROR: 需要安装 paramiko: pip install paramiko', file=sys.stderr)
    sys.exit(2)

# 默认凭据（与 upload-frontend-dist.py 一致；可通过环境变量覆盖）
HOST = os.environ.get('US_FRONTEND_HOST', '154.9.254.86')
USER = os.environ.get('US_FRONTEND_USER', 'root')
PASS = os.environ.get('US_FRONTEND_PASS', 'IkyuM1cakgilY5Vz')

PROJECT_ROOT = Path(__file__).resolve().parent.parent
USER_WEB_DIST = PROJECT_ROOT / 'apps' / 'user-web' / 'dist'
ADMIN_WEB_DIST = PROJECT_ROOT / 'apps' / 'admin-web' / 'dist'

USER_WEB_REMOTE = '/var/www/user-web'
ADMIN_WEB_REMOTE = '/var/www/admin-web'


def md5_of(path: Path) -> str:
    h = hashlib.md5()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def collect_local_files(dist_dir: Path) -> dict[str, str]:
    """遍历本地 dist 目录，返回 {相对路径: md5} 字典。"""
    result = {}
    for root, _, files in os.walk(dist_dir):
        for f in files:
            p = Path(root) / f
            rel = str(p.relative_to(dist_dir)).replace('\\', '/')
            result[rel] = md5_of(p)
    return result


def collect_remote_files(sftp, remote_dir: str) -> dict[str, str]:
    """遍历远端目录，返回 {相对路径: md5} 字典。使用 find + md5sum 一次性算完。"""
    # 注意：sftp 不能直接执行 shell 命令；调用方需通过 ssh exec_command 完成
    raise NotImplementedError('应通过 ssh exec_command 调用 collect_remote_files_via_ssh')


def collect_remote_files_via_ssh(ssh, remote_dir: str) -> dict[str, str]:
    """通过 SSH 执行 find + md5sum 一次性获取远端所有文件的 md5。"""
    cmd = f"cd {remote_dir} && find . -type f -exec md5sum {{}} + | sed 's|  \\./|  |'"
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=300)
    out = stdout.read().decode('utf-8', 'ignore')
    result = {}
    for line in out.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2:
            md5, path = parts
            result[path.strip()] = md5.strip()
    return result


def upload_one(ssh, sftp, local: Path, remote_dir: str, remote_subpath: str) -> tuple[bool, str]:
    """上传单个文件到 remote_dir/remote_subpath，返回 (是否成功, 远端路径)。
    调用前应已通过 md5 比对确认需要上传。"""
    remote_path = f'{remote_dir}/{remote_subpath}'

    # 确保远端目录存在
    parts = remote_subpath.split('/')
    cur = remote_dir
    for p in parts[:-1]:
        if not p:
            continue
        cur = f'{cur}/{p}'
        try:
            sftp.stat(cur)
        except FileNotFoundError:
            sftp.mkdir(cur)

    sftp.put(str(local), remote_path)
    return True, remote_path


def run_cmd(ssh, cmd: str, timeout: int = 60) -> tuple[int, str, str]:
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', 'ignore')
    err = stderr.read().decode('utf-8', 'ignore')
    return stdout.channel.recv_exit_status(), out, err


def main():
    parser = argparse.ArgumentParser(description='增量同步前端 dist 到美国生产服务器（基于 md5 比对）')
    parser.add_argument('--target', choices=['user', 'admin', 'both'], default='user',
                        help='部署目标：user (默认) / admin / both')
    parser.add_argument('--no-reload', action='store_true', help='不重载 nginx')
    parser.add_argument('--dry-run', action='store_true', help='仅打印将同步的文件，不实际执行')
    parser.add_argument('--keep-remote-extra', action='store_true',
                        help='保留远端有但本地无的文件（默认会删除，避免旧 chunk 残留）')
    args = parser.parse_args()

    targets = []
    if args.target in ('user', 'both'):
        targets.append(('user-web', USER_WEB_DIST, USER_WEB_REMOTE))
    if args.target in ('admin', 'both'):
        targets.append(('admin-web', ADMIN_WEB_DIST, ADMIN_WEB_REMOTE))

    # 收集本地文件
    local_all: dict[str, dict[str, str]] = {}
    for label, dist_dir, _ in targets:
        local_all[label] = collect_local_files(dist_dir)

    print(f'连接服务器 {USER}@{HOST} ...')
    if args.dry_run:
        # dry-run 模式仍需连接以获取远端 md5 列表
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(HOST, username=USER, password=PASS, timeout=30)
        sftp = ssh.open_sftp()
    else:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(HOST, username=USER, password=PASS, timeout=30)
        sftp = ssh.open_sftp()
    print('SSH 连接成功')

    # 收集远端文件并对比
    total_upload = 0
    total_skip = 0
    total_delete = 0
    plan_per_target: list[tuple[str, list[Path], list[str], str]] = []
    # 每项: (label, 待上传本地文件列表, 待删除远端文件列表, remote_dir)
    for label, dist_dir, remote_dir in targets:
        print(f'\n==== 对比 {label} ====')
        local_files = local_all[label]
        remote_files = collect_remote_files_via_ssh(ssh, remote_dir)
        print(f'  本地文件: {len(local_files)} 个, 远端文件: {len(remote_files)} 个')

        to_upload = []
        for rel, lmd5 in local_files.items():
            rmd5 = remote_files.get(rel)
            if rmd5 is None or rmd5 != lmd5:
                to_upload.append(dist_dir / rel)

        to_delete = []
        if not args.keep_remote_extra:
            for rel in remote_files:
                if rel not in local_files:
                    to_delete.append(rel)

        print(f'  待上传: {len(to_upload)} 个, 待跳过: {len(local_files) - len(to_upload)} 个, 待删除: {len(to_delete)} 个')
        if to_upload:
            print(f'  上传示例(前5): {[str(p.relative_to(dist_dir)).replace(chr(92),"/") for p in to_upload[:5]]}')
        if to_delete:
            print(f'  删除示例(前5): {to_delete[:5]}')
        total_upload += len(to_upload)
        total_skip += len(local_files) - len(to_upload)
        total_delete += len(to_delete)
        plan_per_target.append((label, to_upload, to_delete, remote_dir))

    print(f'\n==== 总计: 上传 {total_upload} + 跳过 {total_skip} + 删除 {total_delete} ====')

    if args.dry_run:
        print('\n--dry-run 模式，未实际执行')
        sftp.close()
        ssh.close()
        return 0

    # 执行上传 + 删除
    for label, to_upload, to_delete, remote_dir in plan_per_target:
        print(f'\n==== 执行 {label} ====')
        dist_dir = USER_WEB_DIST if label == 'user-web' else ADMIN_WEB_DIST

        # 上传
        uploaded = 0
        for local in to_upload:
            subpath = str(local.relative_to(dist_dir)).replace('\\', '/')
            try:
                _, _ = upload_one(ssh, sftp, local, remote_dir, subpath)
                uploaded += 1
                if uploaded % 20 == 0:
                    print(f'  已上传 {uploaded}/{len(to_upload)}...')
            except Exception as e:
                print(f'  ERROR 上传 {subpath}: {e}', file=sys.stderr)
        print(f'  上传完成: {uploaded}/{len(to_upload)}')

        # 删除远端多余文件
        deleted = 0
        for rel in to_delete:
            remote_path = f'{remote_dir}/{rel}'
            try:
                sftp.remove(remote_path)
                deleted += 1
            except FileNotFoundError:
                pass
            except Exception as e:
                print(f'  WARN 删除 {rel} 失败: {e}', file=sys.stderr)
        if deleted:
            print(f'  删除完成: {deleted}/{len(to_delete)}')

    # 设置权限
    print('\n==== 设置权限 ====')
    perm_targets = []
    if args.target in ('user', 'both'):
        perm_targets.append('/var/www/user-web')
    if args.target in ('admin', 'both'):
        perm_targets.append('/var/www/admin-web')
    if perm_targets:
        perm_cmd = (
            'chown -R www-data:www-data ' + ' '.join(perm_targets) + ' 2>/dev/null '
            '|| chown -R nginx:nginx ' + ' '.join(perm_targets) + ' 2>/dev/null '
            '|| true; '
            'chmod -R 755 ' + ' '.join(perm_targets) + '; '
            'echo "权限设置完成"'
        )
        ec, out, _ = run_cmd(ssh, perm_cmd, timeout=120)
        print(out.strip())

    # reload nginx
    if not args.no_reload:
        ec, out, _ = run_cmd(ssh, 'nginx -t 2>&1')
        print(f'nginx -t:\n{out.strip()}')
        if ec != 0:
            print('ERROR: nginx -t 失败，未重载', file=sys.stderr)
            sys.exit(1)
        ec, out, _ = run_cmd(ssh, 'nginx -s reload 2>&1')
        print(f'nginx -s reload: {out.strip()} (exit={ec})')

    # HTTP 验证
    print('\n==== HTTP 验证 ====')
    if args.target in ('user', 'both'):
        ec, out, _ = run_cmd(ssh, 'curl -s -o /dev/null -w "%{http_code}" http://localhost:81/')
        print(f'user-web (port 81): HTTP {out.strip()}')
    if args.target in ('admin', 'both'):
        ec, out, _ = run_cmd(ssh, 'curl -s -o /dev/null -w "%{http_code}" http://localhost:82/')
        print(f'admin-web (port 82): HTTP {out.strip()}')

    sftp.close()
    ssh.close()
    print('\n✓ 同步完成')
    return 0


if __name__ == '__main__':
    sys.exit(main())
