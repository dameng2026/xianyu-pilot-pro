"""
滑块求解失败冷却
================
策略（仅自动路径 / 全自动）：
- 成功：清空 fail_count，允许立即再求
- 失败：fail_count += 1，统一 60 秒冷却（最大 1 分钟）
  * 所有失败原因（slider_fail/cookie_invalid/timeout/browser_crashed/其他）均冷却 60 秒
- 手动触发 (manual / manual_retry) 跳过冷却（force=True）

状态持久化到 xianyu_captcha_backoff，进程重启不丢失。

2026-08-01 重大调整：所有冷却时间统一为 60 秒（最大 1 分钟）。
原因：项目核心目标是保持所有 Cookie 有效账号的 WS 持久化。
      长冷却时间（10/30/60 分钟）会导致 Cookie 有效但 WS 失效的账号长时间无法重连，
      违背 WS 持久化目标。
      60 秒冷却足以避免瞬时高频触发，同时保证 WS 能快速重试恢复。
      详见 .trae/rules/cookie-valid-ws-persistence.md 规则。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import text

from ..core.database import async_session
from ..core.failure_logging import log_service_failure

logger = logging.getLogger(__name__)

# 2026-08-01 重大调整：所有冷却时间统一为 60 秒（最大 1 分钟）
# 原因：项目核心目标是保持 Cookie 有效账号的 WS 持久化，
#       长冷却会阻止 WS 快速重试恢复，违背持久化目标。
#       60 秒冷却足以避免瞬时高频触发，同时保证 WS 能快速重连。
MAX_COOLDOWN_SEC = 60  # 最大冷却时间 1 分钟（所有失败原因统一）

# 兼容旧代码的常量（实际全部使用 MAX_COOLDOWN_SEC）
SLIDER_FAIL_COOLDOWN_LEVEL_1 = 60    # 1 分钟（fail_count 1-2）
SLIDER_FAIL_COOLDOWN_LEVEL_2 = 60    # 1 分钟（fail_count 3-5）
SLIDER_FAIL_COOLDOWN_LEVEL_3 = 60    # 1 分钟（fail_count 6+）

# Cookie 失效冷却：60 秒（与 slider_fail 一致，保持快速重试）
COOKIE_INVALID_COOLDOWN_SEC = 60     # 1 分钟

# 临时性错误冷却：60 秒
DEFAULT_COOLDOWN_SEC = 60             # 1 分钟
_ENSURED = False


def _cooldown_seconds(fail_count: int, failure_reason: str = "") -> int:
    """返回冷却秒数。fail_count <= 0 时不冷却。

    Args:
        fail_count: 失败次数
        failure_reason: 失败原因（保留参数，但不再差异化冷却）

    Returns:
        冷却秒数（固定 60 秒，最大 1 分钟）
    """
    if fail_count <= 0:
        return 0

    # 2026-08-01 重大调整：所有失败原因统一 60 秒冷却
    # 原因：项目核心目标是保持 Cookie 有效账号的 WS 持久化，
    #       长冷却会阻止 WS 快速重试恢复。
    #       60 秒冷却足以避免瞬时高频触发，同时保证 WS 能快速重连。
    return MAX_COOLDOWN_SEC


async def ensure_backoff_table() -> None:
    """幂等建表，避免迁移未跑导致冷却失效。"""
    global _ENSURED
    if _ENSURED:
        return
    try:
        async with async_session() as db:
            await db.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS xianyu_captcha_backoff (
                      account_id BIGINT NOT NULL,
                      tenant_id BIGINT NOT NULL,
                      fail_count INT NOT NULL DEFAULT 0,
                      next_allowed_at DATETIME NULL,
                      last_fail_at DATETIME NULL,
                      last_success_at DATETIME NULL,
                      last_error VARCHAR(512) DEFAULT '',
                      updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP,
                      PRIMARY KEY (account_id),
                      KEY idx_cb_tenant_next (tenant_id, next_allowed_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    """
                )
            )
            await db.commit()
        _ENSURED = True
    except Exception as e:
        log_service_failure(
            logger, e, operation="ensure_captcha_backoff_table", level=logging.WARNING,
        )


async def get_backoff_status(account_id: int, tenant_id: int) -> dict[str, Any]:
    await ensure_backoff_table()
    try:
        async with async_session() as db:
            row = (
                await db.execute(
                    text(
                        # 2026-08-01 修复：用 SQL NOW() + TIMESTAMPDIFF 计算剩余冷却秒数，
                        # 保证与 record_solve_failure 写入时（DATE_ADD(NOW(),...)）时区一致。
                        # 原先用 Python datetime.now()（容器 UTC）与 DB 的 next_allowed_at（MySQL +08:00）比较，
                        # 导致冷却时间被多算 8 小时。
                        "SELECT fail_count, next_allowed_at, last_fail_at, last_success_at, last_error, "
                        "CASE WHEN next_allowed_at IS NOT NULL AND next_allowed_at > NOW() "
                        "     THEN GREATEST(0, TIMESTAMPDIFF(SECOND, NOW(), next_allowed_at)) "
                        "     ELSE 0 END AS remaining_sec "
                        "FROM xianyu_captcha_backoff "
                        "WHERE account_id = :aid AND tenant_id = :tid LIMIT 1"
                    ),
                    {"aid": account_id, "tid": tenant_id},
                )
            ).mappings().first()
        if not row:
            return {
                "failCount": 0,
                "allowed": True,
                "nextAllowedAt": None,
                "remainingSec": 0,
                "lastError": "",
            }
        next_at: Optional[datetime] = row.get("next_allowed_at")
        remaining = int(row.get("remaining_sec") or 0)
        allowed = remaining <= 0
        return {
            "failCount": int(row.get("fail_count") or 0),
            "allowed": allowed,
            "nextAllowedAt": str(next_at) if next_at else None,
            "remainingSec": max(0, remaining),
            "lastError": str(row.get("last_error") or ""),
        }
    except Exception as e:
        log_service_failure(
            logger, e, operation="get_captcha_backoff",
            tenant_id=tenant_id, account_id=account_id, level=logging.WARNING,
        )
        # 读失败时不阻断（fail-open），避免表异常导致永不可求
        return {
            "failCount": 0,
            "allowed": True,
            "nextAllowedAt": None,
            "remainingSec": 0,
            "lastError": "",
        }


async def assert_auto_solve_allowed(
    account_id: int,
    tenant_id: int,
    *,
    force: bool = False,
) -> Optional[dict[str, Any]]:
    """若处于冷却期返回阻断信息 dict；允许则返回 None。

    策略：固定 60 秒冷却。
    force=True 时跳过冷却（手动触发场景 manual / manual_retry）。
    """
    if force:
        return None
    st = await get_backoff_status(account_id, tenant_id)
    if not st.get("allowed"):
        return {
            "error": "滑块求解冷却中",
            "remainingSec": st.get("remainingSec", 0),
            "nextAllowedAt": st.get("nextAllowedAt"),
            "failCount": st.get("failCount", 0),
        }
    return None


async def record_solve_success(account_id: int, tenant_id: int) -> None:
    await ensure_backoff_table()
    try:
        async with async_session() as db:
            await db.execute(
                text(
                    """
                    INSERT INTO xianyu_captcha_backoff
                      (account_id, tenant_id, fail_count, next_allowed_at, last_success_at, last_error, updated_at)
                    VALUES (:aid, :tid, 0, NULL, NOW(), '', NOW())
                    ON DUPLICATE KEY UPDATE
                      fail_count = 0,
                      next_allowed_at = NULL,
                      last_success_at = NOW(),
                      last_error = '',
                      updated_at = NOW()
                    """
                ),
                {"aid": account_id, "tid": tenant_id},
            )
            await db.commit()
        logger.info("滑块冷却已重置(成功) accountId=%d", account_id)
    except Exception as e:
        log_service_failure(
            logger, e, operation="record_captcha_backoff_success",
            tenant_id=tenant_id, account_id=account_id, level=logging.WARNING,
        )


async def record_solve_failure(
    account_id: int,
    tenant_id: int,
    error: str = "",
    *,
    skip_backoff: bool = False,
    failure_reason: str = "",
) -> dict[str, Any]:
    """记录失败并计算下次允许时间，返回冷却状态。

    Args:
        account_id: 账号 ID
        tenant_id: 租户 ID
        error: 错误消息
        skip_backoff: 是否跳过指数退避累加（仅记录 last_error，不累加 fail_count、不设置 next_allowed_at）。
            用于浏览器崩溃等临时性错误：这类错误重试一次可能就成功，
            不应让账号进入 60 秒冷却期导致后续求解被阻断。
            2026-07-29 事故修复：浏览器崩溃（Page crashed / browserContext closed）
            原先被归为 service_unavailable 并累加退避，导致 WS 每次重连触发求解时
            都被 assert_auto_solve_allowed 拦截，账号长时间无法自动求解。
        failure_reason: 失败原因（用于差异化冷却）。
            slider_fail：累进冷却 10/30/60 分钟（Baxia 风控状态需要时间恢复）
            cookie_invalid：冷却 30 分钟（Cookie 已失效，等用户重新登录）
            其他：冷却 60 秒（临时性错误快速重试）
    """
    await ensure_backoff_table()
    err = (error or "")[:500]

    if skip_backoff:
        # 仅记录 last_error，不累加 fail_count、不设置 next_allowed_at
        # 账号仍可立即再次求解（assert_auto_solve_allowed 不会被拦截）
        try:
            async with async_session() as db:
                await db.execute(
                    text(
                        """
                        INSERT INTO xianyu_captcha_backoff
                          (account_id, tenant_id, fail_count, next_allowed_at, last_fail_at, last_error, updated_at)
                        VALUES (:aid, :tid, 0, NULL, NOW(), :err, NOW())
                        ON DUPLICATE KEY UPDATE
                          last_fail_at = NOW(),
                          last_error = :err,
                          tenant_id = :tid,
                          updated_at = NOW()
                        """
                    ),
                    {
                        "aid": account_id,
                        "tid": tenant_id,
                        "err": err,
                    },
                )
                await db.commit()
            logger.info(
                "滑块失败已记录(跳过退避) accountId=%d error=%s — 临时性错误，不累加冷却",
                account_id, err[:120],
            )
        except Exception as e:
            log_service_failure(
                logger, e, operation="record_captcha_backoff_failure_skip",
                tenant_id=tenant_id, account_id=account_id, level=logging.WARNING,
            )
        return {
            "failCount": 0,
            "cooldownSec": 0,
            "nextAllowedAt": None,
            "allowed": True,
            "remainingSec": 0,
            "lastError": err,
        }

    st = await get_backoff_status(account_id, tenant_id)
    fail_count = int(st.get("failCount") or 0) + 1
    cool = _cooldown_seconds(fail_count, failure_reason)
    # 2026-08-01 修复：使用 SQL 的 DATE_ADD(NOW(), INTERVAL :cool SECOND) 计算 next_allowed_at
    # 原因：automation-service 容器时区是 UTC，MySQL 时区是 +08:00（北京时间）。
    # Python datetime.now() 返回 UTC 时间，存入 MySQL 后被当作北京时间，导致比实际早 8 小时。
    # 使用 SQL 的 NOW() 确保 next_allowed_at 与 MySQL 时区一致。
    next_at: Optional[datetime] = None
    try:
        async with async_session() as db:
            await db.execute(
                text(
                    """
                    INSERT INTO xianyu_captcha_backoff
                      (account_id, tenant_id, fail_count, next_allowed_at, last_fail_at, last_error, updated_at)
                    VALUES (:aid, :tid, :fc, DATE_ADD(NOW(), INTERVAL :cool SECOND), NOW(), :err, NOW())
                    ON DUPLICATE KEY UPDATE
                      fail_count = :fc,
                      next_allowed_at = DATE_ADD(NOW(), INTERVAL :cool SECOND),
                      last_fail_at = NOW(),
                      last_error = :err,
                      tenant_id = :tid,
                      updated_at = NOW()
                    """
                ),
                {
                    "aid": account_id,
                    "tid": tenant_id,
                    "fc": fail_count,
                    "cool": cool,
                    "err": err,
                },
            )
            # 回查实际写入的 next_allowed_at（MySQL 时区），用于日志和返回值
            next_at = (
                await db.execute(
                    text(
                        "SELECT next_allowed_at FROM xianyu_captcha_backoff "
                        "WHERE account_id = :aid LIMIT 1"
                    ),
                    {"aid": account_id},
                )
            ).scalar()
            await db.commit()
        logger.warning(
            "滑块冷却已更新(失败) accountId=%d failCount=%d cooldownSec=%d next=%s",
            account_id, fail_count, cool,
            next_at.isoformat(sep=" ", timespec="seconds") if next_at else "N/A",
        )
    except Exception as e:
        log_service_failure(
            logger, e, operation="record_captcha_backoff_failure",
            tenant_id=tenant_id, account_id=account_id, level=logging.WARNING,
        )
    return {
        "failCount": fail_count,
        "cooldownSec": cool,
        "nextAllowedAt": next_at.isoformat(sep=" ", timespec="seconds") if next_at else None,
        "allowed": False,
        "remainingSec": cool,
        "lastError": err,
    }
