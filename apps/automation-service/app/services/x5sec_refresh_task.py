"""x5sec 主动刷新后台任务（11.5.1-5 实施产物，2026-08-04）

目标：x5sec 即将过期时主动刷新，而非等 WS 掉线后被动获取，减少 WS 中断时间。

设计原则（遵守 cookie-valid-ws-persistence.md 约束 7）：
- **不得主动触发滑块求解**：对 Cookie 有效且 WS 正常的账号做滑块求解会触发 Baxia 风控
- 仅使用纯 HTTP 提取（方案 D）：HTTP GET 闲鱼首页，检查 Set-Cookie 是否下发 x5sec
- 刷新失败不影响现有 WS 连接（被动获取逻辑保留）

流程：
1. 每 X5SEC_REFRESH_INTERVAL_SEC（默认 20 小时）执行一次
2. 遍历 cookie_status=1 的账号（从 xianyu_account_runtime）
3. 读取每个账号的 x5sec 缓存剩余 TTL（get_x5sec_cache_ttl_remaining）
4. TTL < 4 小时 → HTTP GET 闲鱼首页尝试获取新 x5sec → 成功则 cache_x5sec 刷新
5. 无缓存或无需刷新 → 跳过

启动方式：由 automation-worker 的定时任务调用 run_x5sec_refresh_loop()
（或独立进程 python -m app.services.x5sec_refresh_task）
"""
from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import text

from ..core.failure_logging import log_service_failure

logger = logging.getLogger(__name__)

# 刷新间隔：默认 20 小时（TTL 24 小时留 4 小时余量）
X5SEC_REFRESH_INTERVAL_SEC = int(
    __import__("os").environ.get("X5SEC_REFRESH_INTERVAL_SEC", str(20 * 60 * 60))
)
# 刷新阈值：缓存剩余 TTL < 此值时触发刷新（默认 4 小时）
X5SEC_REFRESH_TTL_THRESHOLD_SEC = int(
    __import__("os").environ.get("X5SEC_REFRESH_TTL_THRESHOLD_SEC", str(4 * 60 * 60))
)
# 单次扫描最多刷新账号数（避免批量请求触发风控）
X5SEC_REFRESH_MAX_ACCOUNTS = int(
    __import__("os").environ.get("X5SEC_REFRESH_MAX_ACCOUNTS", "20")
)


async def _fetch_x5sec_via_homepage_only(cookie_str: str) -> str:
    """回退方案：仅首页 GET（ws_token 辅助函数不可用时使用）。

    Returns:
        提取到的 x5sec 值；未提取到返回空字符串
    """
    try:
        import re

        import requests

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://www.goofish.com/",
        }
        resp = requests.get(
            "https://www.goofish.com/",
            headers={**headers, "Cookie": cookie_str},
            timeout=8,
            allow_redirects=False,
        )
        set_cookie = resp.headers.get("set-cookie", "")
        if set_cookie:
            m = re.search(r"x5sec=([^;]+)", set_cookie)
            if m and m.group(1):
                return m.group(1)
    except Exception as e:
        logger.debug("x5sec 主动刷新 HTTP 提取失败: %s", e)
    return ""


async def _fetch_x5sec_via_http(cookie_str: str) -> str:
    """纯 HTTP 提取 x5sec（复用 ws_token 多端点探测逻辑，不含主动 CAPTCHA 触发）。

    2026-08-05 强化：从单一首页 GET 扩展为多端点探测（首页 + im + personal + _m_h5_tk 刷新 API）。
    不同端点在不同风控状态下可能下发 x5sec，多端点探测提升主动刷新命中率。

    设计约束（遵守 cookie-valid-ws-persistence.md）：
    - **不调用来源 6（主动 Token API）**：主动刷新场景下调用 Token API 可能加码风控，
      违反"不主动触发滑块求解"原则。仅用 GET 端点探测 + _m_h5_tk 刷新 API。
    - 不启动浏览器、不调用 crawler-service 滑块求解端点。

    Returns:
        提取到的 x5sec 值；未提取到返回空字符串
    """
    try:
        from .ws_token import (
            _X5SEC_GET_PROBE_URLS,
            _fetch_x5sec_from_get_endpoint,
            _fetch_x5sec_from_refresh_mh5tk,
            extract_m_h5_tk_from_cookie,
        )
    except ImportError as e:
        logger.debug("x5sec 主动刷新: ws_token 辅助函数不可用，回退首页 GET: %s", e)
        return await _fetch_x5sec_via_homepage_only(cookie_str)

    m_h5_tk = extract_m_h5_tk_from_cookie(cookie_str) or ""

    # 多端点 GET 探测（首页 + im + personal）
    for probe_url in _X5SEC_GET_PROBE_URLS:
        x5sec = await asyncio.to_thread(
            _fetch_x5sec_from_get_endpoint, probe_url, cookie_str, None
        )
        if x5sec:
            logger.info(
                "x5sec 主动刷新: ✓ 多端点探测命中 url=%s x5sec_len=%d",
                probe_url, len(x5sec),
            )
            return x5sec

    # _m_h5_tk 刷新 API 探测
    if m_h5_tk:
        x5sec = await asyncio.to_thread(
            _fetch_x5sec_from_refresh_mh5tk, cookie_str, m_h5_tk, None
        )
        if x5sec:
            logger.info(
                "x5sec 主动刷新: ✓ _m_h5_tk 刷新 API 下发 x5sec len=%d",
                len(x5sec),
            )
            return x5sec

    return ""


async def _refresh_expiring_accounts() -> int:
    """扫描并刷新 TTL 即将过期的 x5sec 缓存。

    Returns:
        本次刷新成功（写入新缓存）的账号数量
    """
    try:
        from ..core.database import async_session
        from .x5sec_cache_client import (
            cache_x5sec,
            get_x5sec_cache_ttl_remaining,
            get_cached_x5sec,
        )
    except ImportError as e:
        logger.warning("x5sec 主动刷新依赖缺失: %s", e)
        return 0

    try:
        from ..core.cookie_crypto import decrypt_cookie_if_needed
    except ImportError:
        decrypt_cookie_if_needed = None

    refreshed = 0
    try:
        async with async_session() as db:
            rows = (await db.execute(
                text(
                    "SELECT r.account_id, r.tenant_id, a.nickname, auth.encrypted_cookie "
                    "FROM xianyu_account_runtime r "
                    "INNER JOIN xianyu_account a ON a.id = r.account_id AND a.tenant_id = r.tenant_id "
                    "LEFT JOIN xianyu_account_auth auth ON auth.account_id = r.account_id "
                    "  AND auth.tenant_id = r.tenant_id "
                    "WHERE r.deleted = 0 AND a.deleted = 0 AND r.cookie_status = 1 "
                    "ORDER BY r.updated_time DESC "
                    "LIMIT :limit"
                ),
                {"limit": X5SEC_REFRESH_MAX_ACCOUNTS * 3},
            )).mappings().all()
    except Exception as e:
        log_service_failure(logger, e, operation="x5sec_refresh_scan", level=logging.WARNING)
        return 0

    for row in rows:
        account_id = row["account_id"]
        nickname = row.get("nickname") or ""
        encrypted_cookie = row.get("encrypted_cookie") or ""
        if not encrypted_cookie:
            continue

        cookie_str = encrypted_cookie
        if decrypt_cookie_if_needed is not None:
            try:
                cookie_str = decrypt_cookie_if_needed(encrypted_cookie)
            except Exception as e:
                logger.warning("x5sec 主动刷新解密失败 account=%d: %s", account_id, e)
                continue
        if not cookie_str:
            continue

        # 检查缓存剩余 TTL
        try:
            ttl_remaining = get_x5sec_cache_ttl_remaining(cookie_str)
        except Exception:
            ttl_remaining = -1

        if ttl_remaining > X5SEC_REFRESH_TTL_THRESHOLD_SEC:
            # 缓存充足，无需刷新
            continue
        if ttl_remaining < 0:
            # 无缓存：可能是从未成功获取过，或被动获取仍可工作，跳过（避免无意义请求）
            logger.info(
                "x5sec 主动刷新跳过（无缓存）account=%d nickname=%s", account_id, nickname
            )
            continue

        # 触发刷新：纯 HTTP 提取（不触发滑块）
        logger.info(
            "x5sec 主动刷新触发 account=%d nickname=%s ttl_remaining=%ds (<%ds)",
            account_id, nickname, ttl_remaining, X5SEC_REFRESH_TTL_THRESHOLD_SEC,
        )
        new_x5sec = await _fetch_x5sec_via_http(cookie_str)
        if new_x5sec:
            ok = cache_x5sec(cookie_str, new_x5sec)
            if ok:
                refreshed += 1
                logger.info(
                    "x5sec 主动刷新成功 account=%d nickname=%s x5sec_len=%d",
                    account_id, nickname, len(new_x5sec),
                )
            else:
                logger.warning("x5sec 主动刷新缓存写入失败 account=%d", account_id)
        else:
            logger.info(
                "x5sec 主动刷新未获取到新值（账号可能风控/无需刷新）account=%d nickname=%s",
                account_id, nickname,
            )
        # 控制节奏：每次刷新之间间隔，避免触发频率风控
        await asyncio.sleep(1.0)

    return refreshed


async def run_x5sec_refresh_loop() -> None:
    """x5sec 主动刷新后台循环（常驻）。

    由 automation-worker 启动；每 X5SEC_REFRESH_INTERVAL_SEC 执行一次扫描。
    """
    logger.info(
        "x5sec 主动刷新循环启动 interval=%ds threshold=%ds max_accounts=%d",
        X5SEC_REFRESH_INTERVAL_SEC,
        X5SEC_REFRESH_TTL_THRESHOLD_SEC,
        X5SEC_REFRESH_MAX_ACCOUNTS,
    )
    while True:
        try:
            start = time.time()
            refreshed = await _refresh_expiring_accounts()
            logger.info(
                "x5sec 主动刷新扫描完成 refreshed=%d 耗时=%.1fs",
                refreshed, time.time() - start,
            )
        except Exception as e:
            log_service_failure(logger, e, operation="x5sec_refresh_loop", level=logging.WARNING)
        await asyncio.sleep(X5SEC_REFRESH_INTERVAL_SEC)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_x5sec_refresh_loop())
