#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量滑块求解实测（全自动 / 仅 page.mouse）。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTO = ROOT / "apps" / "automation-service"
CRAWLER = ROOT / "apps" / "crawler-service"
ENV = ROOT / ".env"


def load_env() -> None:
    if not ENV.exists():
        return
    for line in ENV.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    load_env()
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        os.environ.pop(k, None)
    os.environ["NO_PROXY"] = "*"

    sys.path.insert(0, str(AUTO))
    os.chdir(AUTO)
    import asyncio
    from sqlalchemy import text
    from app.core.cookie_crypto import decrypt_cookie_if_needed
    from app.core.database import async_session

    async def load_cookies():
        out = []
        async with async_session() as db:
            rows = (
                await db.execute(
                    text(
                        """
                        SELECT a.id, a.nickname, auth.encrypted_cookie
                        FROM xianyu_account a
                        JOIN xianyu_account_auth auth
                          ON auth.account_id=a.id AND auth.tenant_id=a.tenant_id
                         AND COALESCE(auth.deleted,0)=0
                        WHERE COALESCE(a.deleted,0)=0
                          AND auth.encrypted_cookie IS NOT NULL AND auth.encrypted_cookie<>''
                        ORDER BY a.updated_time DESC LIMIT 5
                        """
                    )
                )
            ).mappings().all()
            for r in rows:
                c = decrypt_cookie_if_needed(r["encrypted_cookie"]) or ""
                if len(c) > 30:
                    out.append((int(r["id"]), str(r["nickname"] or r["id"]), c))
        return out

    accounts = asyncio.run(load_cookies())
    if not accounts:
        print("[batch] no cookies")
        return 2
    print(f"[batch] accounts={[(a, n, len(c)) for a, n, c in accounts]}")

    script = CRAWLER / "sliderSolve.py"
    py = sys.executable
    for cand in [sys.executable]:
        r = subprocess.run(
            [cand, "-c", "from playwright.async_api import async_playwright"],
            capture_output=True,
        )
        if r.returncode == 0:
            py = cand
            break
    print(f"[batch] python={py} rounds={n}")

    stats = {
        "total": 0,
        "ok": 0,
        "solved": 0,
        "captchaDetected": 0,
        "captchaSolved": 0,
        "loadFailEnv": 0,
        "errors": [],
    }

    for i in range(n):
        aid, nick, cookie = accounts[i % len(accounts)]
        cookie_file = Path(os.environ.get("TEMP", ".")) / f"batch-slider-cookie-{aid}-{i}.txt"
        cookie_file.write_text(cookie, encoding="utf-8")
        print(f"\n===== round {i+1}/{n} account={aid} {nick} =====")
        t0 = time.time()
        try:
            proc = subprocess.run(
                [
                    py,
                    str(script),
                    "--cookie-file",
                    str(cookie_file),
                    "--target-url",
                    "https://www.goofish.com/im",
                    "--max-retries",
                    "5",
                ],
                cwd=str(CRAWLER),
                capture_output=True,
                text=True,
                timeout=360,
                encoding="utf-8",
                errors="replace",
            )
            out = (proc.stdout or "") + "\n" + (proc.stderr or "")
            for line in out.splitlines():
                if any(
                    k in line
                    for k in (
                        "贝塞尔",
                        "悬停",
                        "微步",
                        "attempt=",
                        "通过",
                        "失败",
                        "加载失败",
                        "环境探针",
                        "distance",
                        "找到滑块",
                    )
                ):
                    print(line)
            json_line = None
            for line in reversed(out.splitlines()):
                if line.strip().startswith("{"):
                    json_line = line.strip()
                    break
            if not json_line:
                stats["total"] += 1
                stats["errors"].append(f"r{i+1}:no-json")
                print("[batch] no json")
                continue
            data = json.loads(json_line)
            stats["total"] += 1
            if data.get("ok"):
                stats["ok"] += 1
            if data.get("solved"):
                stats["solved"] += 1
            if data.get("captchaDetected"):
                stats["captchaDetected"] += 1
                if data.get("solved"):
                    stats["captchaSolved"] += 1
            err = str(data.get("error") or "")
            if "加载失败" in err or "风控" in err:
                stats["loadFailEnv"] += 1
            print(
                f"[batch] ok={data.get('ok')} solved={data.get('solved')} "
                f"captcha={data.get('captchaDetected')} attempts={data.get('attempts')} "
                f"ms={data.get('durationMs')} err={err[:140]}"
            )
        except subprocess.TimeoutExpired:
            stats["total"] += 1
            stats["errors"].append(f"r{i+1}:timeout")
            print("[batch] timeout")
        except Exception as e:
            stats["total"] += 1
            stats["errors"].append(f"r{i+1}:{e}")
            print(f"[batch] error {e}")
        finally:
            try:
                cookie_file.unlink(missing_ok=True)
            except Exception:
                pass
        print(f"[batch] elapsed={time.time()-t0:.1f}s")
        time.sleep(6 + (i % 3) * 2)

    captcha_n = stats["captchaDetected"]
    captcha_rate = (stats["captchaSolved"] / captcha_n * 100) if captcha_n else None
    print("\n========== SUMMARY ==========")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    if stats["total"]:
        print(f"overall solved: {stats['solved']}/{stats['total']} = {stats['solved']/stats['total']*100:.1f}%")
    if captcha_rate is not None:
        print(f"CAPTCHA pass rate: {captcha_rate:.1f}% ({stats['captchaSolved']}/{captcha_n})")
        print("TARGET >= 80%")
    else:
        print("No captchaDetected samples this run")
    return 0 if (captcha_rate is not None and captcha_rate >= 80) else 1


if __name__ == "__main__":
    raise SystemExit(main())
