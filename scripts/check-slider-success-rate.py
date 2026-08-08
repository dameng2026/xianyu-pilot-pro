#!/usr/bin/env python3
"""线上滑块求解成功率监控（只读）。

统计口径与后台 KPI 一致：
- 排除 timeout / precheck_rejected / service_unavailable / browser_crashed /
  stale_terminated / cookie_invalid / account_inactive / account_disabled
- 成功率 = success / (success + fail)

用法：
    python scripts/check-slider-success-rate.py [--days 1] [--threshold 70]

退出码：
- 0：所有窗口成功率 >= threshold
- 1：任一窗口成功率 < threshold（便于接入 cron/监控告警）

凭据来源：仓库根目录 .deploy.prod.json（china_backend）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import paramiko

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / ".deploy.prod.json"

# 与后台 XianyuCaptchaSolveRecordMapper 的排除口径保持一致
EXCLUDE_REASONS = (
    "'service_unavailable', 'browser_crashed', 'precheck_rejected', 'timeout', "
    "'stale_terminated', 'cookie_invalid', 'account_inactive', 'account_disabled'"
)


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data["china_backend"]


def mysql_query(ssh: paramiko.SSHClient, sql: str, timeout: int = 60) -> str:
    cmd = (
        "cd /home/ubuntu/project && "
        "MYSQL_PWD=$(grep '^MYSQL_ROOT_PASSWORD=' .env.production | cut -d= -f2) && "
        f"docker exec -i xianyu-admin-mysql mysql -uroot -p\"$MYSQL_PWD\" "
        f"xianyu_assistant_admin -N -e \"{sql}\" "
        "2>&1 | grep -v 'using a password'"
    )
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    if err.strip():
        lines = [
            line for line in err.splitlines()
            if line.strip() and "Warning" not in line and "using a password" not in line
        ]
        if lines:
            print(f"[stderr] {lines[0][:300]}", file=sys.stderr)
    return out


def kpi_sql(where: str) -> str:
    valid = (
        "SUM(CASE WHEN NOT (status IN ('timeout', 'precheck_rejected') "
        f"OR COALESCE(failure_reason, '') IN ({EXCLUDE_REASONS})) THEN 1 ELSE 0 END)"
    )
    fail = (
        "SUM(CASE WHEN status = 'fail' AND COALESCE(failure_reason, '') NOT IN "
        f"({EXCLUDE_REASONS}) THEN 1 ELSE 0 END)"
    )
    return (
        "SELECT "
        f"{valid}, SUM(status='success'), {fail} "
        "FROM xianyu_captcha_solve_record "
        f"WHERE COALESCE(deleted, 0) = 0 AND {where}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=1, help="统计最近 N 天（默认 1）")
    parser.add_argument("--threshold", type=float, default=70.0, help="成功率阈值（默认 70%）")
    args = parser.parse_args()

    cfg = load_config()
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        cfg["host"], port=cfg.get("port", 22),
        username=cfg["username"], password=cfg["password"], timeout=20,
    )

    windows = {
        f"近{args.days}天": f"created_at >= DATE_SUB(NOW(), INTERVAL {args.days} DAY)",
        "今天": "created_at >= CURDATE()",
        "修复后(>=2026-08-08 18:10)": "created_at >= '2026-08-08 18:10:00'",
    }
    all_ok = True
    for label, where in windows.items():
        out = mysql_query(ssh, kpi_sql(where), timeout=60).strip()
        parts = out.replace("\n", " ").split()
        if len(parts) < 3 or not parts[-3].isdigit():
            print(f"[{label}] 查询失败: {out[:200]}")
            all_ok = False
            continue
        total, success, fail = int(parts[-3]), int(parts[-2]), int(parts[-1])
        rate = success * 100.0 / total if total else 0.0
        status = "OK" if rate >= args.threshold else "LOW"
        if rate < args.threshold:
            all_ok = False
        print(
            f"[{label}] total={total} success={success} fail={fail} "
            f"rate={rate:.2f}% ({status})"
        )

    print("阈值: %.0f%%" % args.threshold)
    ssh.close()
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
