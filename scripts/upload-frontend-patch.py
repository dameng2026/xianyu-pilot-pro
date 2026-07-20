#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""增量上传前端 dist 变更文件到美国生产服务器。

相比 upload-frontend-dist.py（全量上传 user-web + admin-web），本脚本：
- 仅上传本次构建发生变化的文件（基于 git diff 或显式列表）
- 跳过备份步骤（既有的 .bak.* 由全量脚本保留）
- 适合快速迭代上线（变更 5-10 个文件，秒级完成）

用法：
    python scripts/upload-frontend-patch.py                # 自动检测 user-web dist 变更
    python scripts/upload-frontend-patch.py --target admin # 上传 admin-web 变更
    python scripts/upload-frontend-patch.py --files a b c  # 显式指定文件

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


def detect_changed_files(dist_dir: Path) -> list[Path]:
    """通过 git diff released/<latest>..HEAD 检测 dist 目录下的变更文件。

    若仓库无 released/* 标签，则回退到对比工作区与上次构建产物（不支持），
    此时建议显式传 --files。
    """
    try:
        latest_tag = subprocess.check_output(
            ['git', 'tag', '--list', 'released/*', '--sort=-v:refname'],
            cwd=PROJECT_ROOT, text=True,
        ).splitlines()[0].strip()
    except (subprocess.CalledProcessError, IndexError):
        print('WARN: 未找到 released/* 标签，无法自动检测变更；请显式传 --files', file=sys.stderr)
        return []

    diff = subprocess.check_output(
        ['git', 'diff', '--name-only', latest_tag, '--', str(dist_dir.relative_to(PROJECT_ROOT))],
        cwd=PROJECT_ROOT, text=True,
    ).splitlines()
    return [PROJECT_ROOT / line for line in diff if (PROJECT_ROOT / line).is_file()]


def upload_one(ssh, sftp, local: Path, remote_dir: str, remote_subpath: str) -> tuple[bool, str]:
    """上传单个文件到 remote_dir/remote_subpath，返回 (是否变化, 远端路径)。"""
    remote_path = f'{remote_dir}/{remote_subpath}'
    local_md5 = md5_of(local)

    # 比较远端文件 md5（若存在且一致则跳过）
    try:
        with sftp.open(remote_path, 'rb') as rf:
            remote_md5 = hashlib.md5(rf.read()).hexdigest()
        if remote_md5 == local_md5:
            return False, remote_path
    except FileNotFoundError:
        pass
    except OSError:
        # 部分服务器对 sftp.open 读取支持不佳，回退为强制上传
        pass

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
    parser = argparse.ArgumentParser(description='增量上传前端 dist 变更文件到美国生产服务器')
    parser.add_argument('--target', choices=['user', 'admin', 'both'], default='user',
                        help='部署目标：user (默认) / admin / both')
    parser.add_argument('--files', nargs='*', help='显式指定本地文件路径（覆盖自动检测）')
    parser.add_argument('--no-reload', action='store_true', help='不重载 nginx')
    parser.add_argument('--dry-run', action='store_true', help='仅打印将上传的文件，不实际执行')
    args = parser.parse_args()

    targets = []
    if args.target in ('user', 'both'):
        targets.append(('user-web', USER_WEB_DIST, USER_WEB_REMOTE))
    if args.target in ('admin', 'both'):
        targets.append(('admin-web', ADMIN_WEB_DIST, ADMIN_WEB_REMOTE))

    plan: list[tuple[str, Path, str, str]] = []  # (label, local, remote_dir, subpath)
    for label, dist_dir, remote_dir in targets:
        if args.files:
            files = []
            for f in args.files:
                p = Path(f)
                if not p.is_absolute():
                    p = (PROJECT_ROOT / p).resolve()
                files.append(p)
        else:
            files = detect_changed_files(dist_dir)
        for f in files:
            if not f.is_file():
                print(f'WARN: 文件不存在，跳过: {f}', file=sys.stderr)
                continue
            try:
                subpath = str(f.relative_to(dist_dir)).replace('\\', '/')
            except ValueError:
                # 文件不在 dist 目录下，使用文件名作为远端路径（仅适用于根目录文件）
                print(f'WARN: 文件不在 {dist_dir} 下，跳过: {f}', file=sys.stderr)
                continue
            plan.append((label, f, remote_dir, subpath))

    if not plan:
        print('没有需要上传的变更文件')
        return 0

    print(f'==== 待上传 {len(plan)} 个文件 ====')
    for label, local, _, subpath in plan:
        print(f'  [{label}] {subpath}  ({local.stat().st_size} bytes)')

    if args.dry_run:
        print('\n--dry-run 模式，未实际上传')
        return 0

    print(f'\n连接服务器 {USER}@{HOST} ...')
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=30)
    sftp = ssh.open_sftp()
    print('SSH 连接成功')

    uploaded = 0
    skipped = 0
    for label, local, remote_dir, subpath in plan:
        changed, remote_path = upload_one(ssh, sftp, local, remote_dir, subpath)
        if changed:
            print(f'  ↑ {label}: {subpath}')
            uploaded += 1
        else:
            print(f'  = {label}: {subpath} (md5 一致，跳过)')
            skipped += 1

    print(f'\n上传完成: {uploaded} 个变更, {skipped} 个跳过')

    # 设置权限
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
    print('\n✓ 增量部署完成')
    return 0


if __name__ == '__main__':
    sys.exit(main())
