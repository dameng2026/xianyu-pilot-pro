#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""增量同步模块：基于 md5 比对，只通过网络上传变更文件。

替代 prod_deploy.py 中的全量 tar.gz 打包+上传+解压流程。
通过 md5 比对本地与远端 live 目录，只把变更/新增文件通过并发 SFTP 上传，
未变更文件在远端本地 cp 复制（磁盘操作，快），大幅减少跨境传输量。

典型场景：改 5 个文件时，旧方案上传整个 backend 源码包（几十 MB），
新方案只上传 5 个文件（几十 KB），传输量降低 99%+。
"""
from __future__ import annotations

import hashlib
import os
import shlex
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath
from queue import Queue
from threading import Lock


def md5_file(path: Path) -> str:
    """计算文件 md5 哈希。"""
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_local_files(
    items: list[tuple[Path, str]],
    exclude_fn=None,
) -> dict[str, tuple[Path, str]]:
    """收集本地文件列表。

    Args:
        items: [(local_path, arc_name)] 列表。
            local_path 是本地绝对路径，arc_name 是在远端的归档路径前缀。
            例如 [(REPO_ROOT / "apps/core-api", "apps/core-api")]
        exclude_fn: 排除函数，接收相对于 repo root 的 Path，返回 True 则排除。

    Returns:
        {posix_arc_path: (local_abs_path, md5)} 字典。
    """
    result: dict[str, tuple[Path, str]] = {}
    for local_path, arc_name in items:
        if not local_path.exists():
            continue
        if local_path.is_file():
            repo_rel = Path(arc_name) if arc_name else Path(local_path.name)
            if exclude_fn and exclude_fn(repo_rel):
                continue
            arc_path = arc_name if arc_name else local_path.name
            result[arc_path] = (local_path, md5_file(local_path))
            continue

        for root, dirs, files in os.walk(local_path):
            current = Path(root)
            retained_dirs = []
            for d in dirs:
                p = current / d
                rel = p.relative_to(local_path)
                repo_rel = Path(arc_name) / rel if arc_name else rel
                if exclude_fn and exclude_fn(repo_rel):
                    continue
                if p.is_symlink():
                    continue
                retained_dirs.append(d)
            dirs[:] = retained_dirs

            for f in files:
                p = current / f
                rel = p.relative_to(local_path)
                repo_rel = Path(arc_name) / rel if arc_name else rel
                if exclude_fn and exclude_fn(repo_rel):
                    continue
                if p.is_symlink():
                    continue
                rel_posix = str(rel).replace(chr(92), "/")
                arc_path = f"{arc_name}/{rel_posix}" if arc_name else rel_posix
                result[arc_path] = (p, md5_file(p))
    return result


def collect_remote_files(
    ssh_client,
    remote_base: str,
    arc_names: set[str],
    timeout: int = 300,
) -> dict[str, str]:
    """通过 SSH find + md5sum 一次性获取远端 live 目录中 items 范围内的文件 md5。

    Args:
        ssh_client: paramiko SSHClient 实例。
        remote_base: 远端 live 目录绝对路径。
        arc_names: 需要收集的归档路径前缀集合（如 {"apps/core-api", "db"}）。
        timeout: SSH 命令超时秒数。

    Returns:
        {posix_arc_path: md5} 字典。如果 remote_base 不存在返回空字典。
    """
    if not arc_names:
        return {}
    # Empty arc_name means "collect all files under remote_base"
    if "" in arc_names:
        cmd = (
            f"if [ -d {shlex.quote(remote_base)} ]; then "
            f"cd {shlex.quote(remote_base)} && "
            f"find . -type f -exec md5sum {{}} + 2>/dev/null | sed 's|  \\./|  |'; "
            f"fi"
        )
    else:
        cmd = (
            f"if [ -d {shlex.quote(remote_base)} ]; then "
            f"cd {shlex.quote(remote_base)} && "
            f"find . -type f \\( "
            + " -o ".join(
                f"-path ./{shlex.quote(name)} -o -path ./{shlex.quote(name)}/*"
                for name in arc_names
            )
            + " \\) -exec md5sum {{}} + 2>/dev/null | sed 's|  \\./|  |'; "
            f"fi"
        )
    stdin, stdout, stderr = ssh_client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "ignore")
    exit_code = stdout.channel.recv_exit_status()
    result: dict[str, str] = {}
    for line in out.splitlines():
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        md5, path = parts
        path = path.strip()
        result[path] = md5.strip()
    return result


def _ensure_remote_dir_sftp(sftp, remote_path: str) -> None:
    """通过 SFTP 递归创建远端目录（类似于 mkdir -p）。

    并发安全：多个线程可能同时创建同一目录，mkdir 失败时
    如果目录已存在（stat 成功）则忽略错误。
    """
    parent = str(PurePosixPath(remote_path).parent)
    parts = parent.split("/")
    cur = ""
    for part in parts:
        if not part:
            cur = "/"
            continue
        cur = f"{cur}/{part}" if cur.endswith("/") else f"{cur}/{part}"
        try:
            sftp.stat(cur)
        except FileNotFoundError:
            try:
                sftp.mkdir(cur)
            except OSError:
                # 并发竞态：另一个线程可能已创建此目录，确认存在即可
                try:
                    sftp.stat(cur)
                except FileNotFoundError:
                    raise


def _concurrent_upload(
    ssh_client,
    to_upload: list[tuple[str, Path]],
    remote_staged: str,
    max_workers: int,
    log,
) -> int:
    """并发 SFTP 上传文件到 staged 目录。

    每个工作线程使用独立的 SFTP session（paramiko SFTP 不是线程安全的）。
    """
    if not to_upload:
        return 0

    sftp_pool: Queue = Queue()
    for _ in range(max_workers):
        sftp_pool.put(ssh_client.open_sftp())

    uploaded = 0
    lock = Lock()
    errors: list[str] = []

    def upload_one(arc_path: str, local_abs: Path):
        nonlocal uploaded
        remote_path = f"{remote_staged}/{arc_path}"
        sftp = sftp_pool.get()
        try:
            _ensure_remote_dir_sftp(sftp, remote_path)
            sftp.put(str(local_abs), remote_path)
            with lock:
                uploaded += 1
                if uploaded % 20 == 0:
                    log(f"[sync] 已上传 {uploaded}/{len(to_upload)}...")
        except Exception as e:
            with lock:
                errors.append(f"{arc_path}: {e}")
            raise
        finally:
            sftp_pool.put(sftp)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(upload_one, arc, local) for arc, local in to_upload
        ]
        for f in futures:
            f.result()

    while not sftp_pool.empty():
        sftp_pool.get().close()

    if errors:
        raise RuntimeError(
            f"[sync] 上传失败 {len(errors)} 个文件: " + "; ".join(errors[:5])
        )

    log(f"[sync] 上传完成: {uploaded}/{len(to_upload)}")
    return uploaded


def _remote_batch_cp(
    ssh_client,
    remote_base: str,
    remote_staged: str,
    to_copy: list[str],
    log,
    batch_size: int = 200,
) -> int:
    """远端批量 cp 文件从 base 到 staged（未变更文件，远端本地磁盘复制）。"""
    if not to_copy:
        return 0

    total = 0
    for i in range(0, len(to_copy), batch_size):
        batch = to_copy[i : i + batch_size]
        lines = ["set -euo pipefail"]
        for arc_path in batch:
            src = f"{remote_base}/{arc_path}"
            dst = f"{remote_staged}/{arc_path}"
            dst_dir = str(PurePosixPath(dst).parent)
            lines.append(f"mkdir -p {shlex.quote(dst_dir)}")
            lines.append(f"cp -a {shlex.quote(src)} {shlex.quote(dst)}")
        script = "; ".join(lines)
        cmd = f"bash -lc {shlex.quote(script)}"
        stdin, stdout, stderr = ssh_client.exec_command(cmd, timeout=600)
        exit_code = stdout.channel.recv_exit_status()
        if exit_code != 0:
            err = stderr.read().decode("utf-8", "ignore")
            raise RuntimeError(
                f"[sync] 远端 cp 失败 (exit={exit_code}): {err[:500]}"
            )
        total += len(batch)
        if total % 200 == 0:
            log(f"[sync] 远端复制进度: {total}/{len(to_copy)}...")

    log(f"[sync] 远端复制完成: {total}/{len(to_copy)}")
    return total


def _remote_cleanup_extra(
    ssh_client,
    remote_staged: str,
    local_arc_paths: set[str],
    log,
) -> int:
    """删除 staged 中有但本地无的文件（远端 base 遗留的过期文件）。

    首次部署时 staged 是空目录，无需删除。
    """
    cmd = (
        f"cd {shlex.quote(remote_staged)} && "
        f"find . -type f 2>/dev/null | sed 's|^\\./||' | sort"
    )
    stdin, stdout, stderr = ssh_client.exec_command(cmd, timeout=300)
    out = stdout.read().decode("utf-8", "ignore")
    staged_files = {line.strip() for line in out.splitlines() if line.strip()}

    to_delete = staged_files - local_arc_paths
    if not to_delete:
        return 0

    # 批量删除
    batch_size = 500
    deleted = 0
    to_delete_list = sorted(to_delete)
    for i in range(0, len(to_delete_list), batch_size):
        batch = to_delete_list[i : i + batch_size]
        lines = ["set -euo pipefail"]
        for arc_path in batch:
            lines.append(f"rm -f {shlex.quote(remote_staged + '/' + arc_path)}")
        script = "; ".join(lines)
        cmd = f"bash -lc {shlex.quote(script)}"
        stdin, stdout, stderr = ssh_client.exec_command(cmd, timeout=120)
        exit_code = stdout.channel.recv_exit_status()
        if exit_code != 0:
            err = stderr.read().decode("utf-8", "ignore")
            log(f"[sync] 警告: 删除过期文件部分失败: {err[:200]}")
        deleted += len(batch)

    log(f"[sync] 清理过期文件: {deleted} 个")
    return deleted


def _verify_sync(
    ssh_client,
    remote_staged: str,
    local_files: dict[str, tuple[Path, str]],
    log,
) -> None:
    """校验远端 staged 中文件 md5 与本地完全一致。"""
    cmd = (
        f"cd {shlex.quote(remote_staged)} && "
        f"find . -type f -exec md5sum {{}} + 2>/dev/null | sed 's|  \\./|  |'"
    )
    stdin, stdout, stderr = ssh_client.exec_command(cmd, timeout=300)
    out = stdout.read().decode("utf-8", "ignore")
    remote_staged_files: dict[str, str] = {}
    for line in out.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2:
            md5, path = parts
            remote_staged_files[path.strip()] = md5.strip()

    missing: list[str] = []
    mismatched: list[str] = []
    for arc_path, (_, local_md5) in local_files.items():
        remote_md5 = remote_staged_files.get(arc_path)
        if remote_md5 is None:
            missing.append(arc_path)
        elif remote_md5 != local_md5:
            mismatched.append(arc_path)
        if len(missing) + len(mismatched) >= 20:
            break

    problems = missing + mismatched
    if problems:
        sample = "; ".join(problems[:10])
        raise RuntimeError(
            f"[sync] 校验失败: {len(missing)} 缺失, {len(mismatched)} 不匹配。"
            f" 示例: {sample}"
        )

    # 检查 staged 中是否有多余文件
    extra = set(remote_staged_files.keys()) - set(local_files.keys())
    if extra:
        sample = "; ".join(sorted(extra)[:5])
        raise RuntimeError(
            f"[sync] 校验失败: staged 中有 {len(extra)} 个多余文件。示例: {sample}"
        )

    log(f"[sync] 校验通过: {len(local_files)} 个文件 md5 一致")


def sync_items_to_staged(
    ssh_client,
    items: list[tuple[Path, str]],
    remote_staged: str,
    remote_base: str,
    exclude_fn=None,
    max_workers: int = 6,
    dry_run: bool = False,
    log=print,
) -> dict:
    """增量同步本地 items 到远端 staged 目录，基于 remote_base 的 md5 比对。

    流程：
    1. 远端创建空 staged 目录（如不存在）
    2. 收集本地文件 md5（应用 exclude_fn）
    3. 收集远端 base（live）目录中 items 范围内的文件 md5
    4. 比对分类：
       - to_upload: 本地有，base 无 或 md5 不同 → 并发 SFTP 上传
       - to_copy:   本地有，base 有，md5 相同 → 远端本地 cp（快）
    5. 并发上传 to_upload
    6. 远端批量 cp to_copy
    7. 清理 staged 中本地无的过期文件
    8. 逐文件 md5 校验，确保 staged 与本地完全一致

    Args:
        ssh_client: paramiko SSHClient 实例（dry_run 时可为 None）。
        items: [(local_path, arc_name)] 列表。
        remote_staged: 远端 staged 目录绝对路径。
        remote_base: 远端 live 目录绝对路径（用于 md5 比对和 cp 源）。
        exclude_fn: 排除函数（如 prod_deploy.is_excluded）。
        max_workers: 并发上传线程数。
        dry_run: 仅打印计划，不实际执行。
        log: 日志函数。

    Returns:
        {"uploaded": N, "copied": N, "total": N, "to_upload": N, "to_copy": N}
    """
    # 1. 远端创建 staged 目录
    if not dry_run:
        mkdir_cmd = f"mkdir -p {shlex.quote(remote_staged)}"
        stdin, stdout, stderr = ssh_client.exec_command(mkdir_cmd, timeout=60)
        exit_code = stdout.channel.recv_exit_status()
        if exit_code != 0:
            err = stderr.read().decode("utf-8", "ignore")
            raise RuntimeError(f"[sync] 创建 staged 目录失败: {err}")

    # 2. 收集本地文件
    local_files = collect_local_files(items, exclude_fn)
    log(f"[sync] 本地文件: {len(local_files)} 个")

    # 3. 收集远端 base 文件 md5
    arc_names = {arc_name for _, arc_name in items}
    if not dry_run:
        remote_base_files = collect_remote_files(ssh_client, remote_base, arc_names)
    else:
        remote_base_files = {}
    log(f"[sync] 远端 base 文件: {len(remote_base_files)} 个")

    # 4. 比对
    to_upload: list[tuple[str, Path]] = []
    to_copy: list[str] = []
    for arc_path, (local_abs, local_md5) in local_files.items():
        base_md5 = remote_base_files.get(arc_path)
        if base_md5 is None or base_md5 != local_md5:
            to_upload.append((arc_path, local_abs))
        else:
            to_copy.append(arc_path)

    total = len(local_files)
    log(
        f"[sync] 待上传: {len(to_upload)} 个, "
        f"待远端复制: {len(to_copy)} 个, 总计: {total}"
    )

    if to_upload and len(to_upload) <= 10:
        for arc, _ in to_upload:
            log(f"[sync]   上传: {arc}")

    if dry_run:
        return {
            "uploaded": 0,
            "copied": 0,
            "total": total,
            "to_upload": len(to_upload),
            "to_copy": len(to_copy),
        }

    # 5. 并发上传 to_upload
    uploaded = _concurrent_upload(
        ssh_client, to_upload, remote_staged, max_workers, log
    )

    # 6. 远端批量 cp to_copy
    copied = _remote_batch_cp(
        ssh_client, remote_base, remote_staged, to_copy, log
    )

    # 7. 清理 staged 中本地无的过期文件
    _remote_cleanup_extra(
        ssh_client, remote_staged, set(local_files.keys()), log
    )

    # 8. 逐文件 md5 校验
    _verify_sync(ssh_client, remote_staged, local_files, log)

    return {
        "uploaded": uploaded,
        "copied": copied,
        "total": total,
        "to_upload": len(to_upload),
        "to_copy": len(to_copy),
    }
