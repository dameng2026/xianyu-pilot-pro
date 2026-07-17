"""Token 余额监控定时任务。

每 30 分钟扫描所有用户的 Token 余额：
- 对余额 < 用户配置阈值（默认 100）的用户触发 notify_token_low_balance 预警通知
- 对余额 >= 阈值的用户清除去重标记，让下次余额再次低于阈值时能重新预警

设计要点：
- 阈值从 user_notification_setting.config_json.tokenBalanceThreshold 读取，默认 100
- 预警去重：通过 notify_dispatcher 的 _check_account_status_notified 实现，每用户只发一次
- 自动清除：余额恢复到阈值以上时，调用 clear_token_low_balance_notifications 清除标记
- 失败容错：单用户异常不影响其他用户扫描
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from sqlalchemy import text

from ..core.database import async_session
from .notify_dispatcher import (
    EVENT_TOKEN_LOW_BALANCE,
    USER_LEVEL_ACCOUNT_PLACEHOLDER,
    _check_account_status_notified,
    clear_token_low_balance_notifications,
    notify_token_low_balance,
)

logger = logging.getLogger(__name__)

# 扫描间隔：30 分钟
SCAN_INTERVAL_SEC = 30 * 60
# 默认预警阈值
DEFAULT_THRESHOLD = 100


async def _load_all_users_with_balance():
    """加载所有未删除用户的 (tenant_id, user_id, token_balance) 列表。"""
    async with async_session() as db:
        rows = (await db.execute(
            text(
                "SELECT tenant_id, id AS user_id, token_balance "
                "FROM sys_user WHERE deleted = 0 AND status = 1 "
                "AND tenant_id IS NOT NULL AND tenant_id > 0"
            )
        )).mappings().all()
        return [(int(r["tenant_id"]), int(r["user_id"]), int(r["token_balance"] or 0)) for r in rows]


async def _load_user_threshold(tenant_id: int, user_id: int) -> int:
    """读取用户配置的预警阈值。未配置时返回默认值 100。"""
    try:
        async with async_session() as db:
            row = (await db.execute(
                text(
                    "SELECT config_json FROM user_notification_setting "
                    "WHERE tenant_id = :tid AND user_id = :uid AND deleted = 0 LIMIT 1"
                ),
                {"tid": tenant_id, "uid": user_id},
            )).mappings().first()
            if not row:
                return DEFAULT_THRESHOLD
            import json
            cfg = row["config_json"]
            if isinstance(cfg, str):
                cfg = json.loads(cfg)
            if not isinstance(cfg, dict):
                return DEFAULT_THRESHOLD
            val = cfg.get("tokenBalanceThreshold")
            try:
                v = int(val)
                return v if v > 0 else DEFAULT_THRESHOLD
            except (TypeError, ValueError):
                return DEFAULT_THRESHOLD
    except Exception:
        logger.debug("读取用户 %d 的预警阈值失败，使用默认值", user_id, exc_info=True)
        return DEFAULT_THRESHOLD


async def _is_event_enabled_for_user(tenant_id: int, user_id: int) -> bool:
    """检查用户是否启用了 Token 余额预警事件。未配置时默认启用。"""
    try:
        async with async_session() as db:
            row = (await db.execute(
                text(
                    "SELECT config_json FROM user_notification_setting "
                    "WHERE tenant_id = :tid AND user_id = :uid AND deleted = 0 LIMIT 1"
                ),
                {"tid": tenant_id, "uid": user_id},
            )).mappings().first()
            if not row:
                return True
            import json
            cfg = row["config_json"]
            if isinstance(cfg, str):
                cfg = json.loads(cfg)
            if not isinstance(cfg, dict):
                return True
            events = cfg.get("events")
            if not isinstance(events, list):
                return True
            for e in events:
                if isinstance(e, dict) and e.get("event") == EVENT_TOKEN_LOW_BALANCE:
                    return bool(e.get("enabled", True))
            # 配置存在但未找到该事件 → 默认启用
            return True
    except Exception:
        logger.debug("检查用户 %d 的事件启用状态失败，默认启用", user_id, exc_info=True)
        return True


async def run_token_balance_warning_once() -> dict:
    """执行一次 Token 余额扫描。

    返回统计信息：{scanned, warned, cleared, errors}
    """
    stats = {"scanned": 0, "warned": 0, "cleared": 0, "errors": 0}
    try:
        users = await _load_all_users_with_balance()
    except Exception as exc:
        logger.warning("Token 余额扫描加载用户列表失败: %s", exc)
        stats["errors"] += 1
        return stats

    for tenant_id, user_id, balance in users:
        stats["scanned"] += 1
        try:
            threshold = await _load_user_threshold(tenant_id, user_id)
            # 检查是否已通知过（避免每次扫描都走 notify 流程）
            already_notified = await _check_account_status_notified(
                tenant_id, USER_LEVEL_ACCOUNT_PLACEHOLDER, EVENT_TOKEN_LOW_BALANCE
            )

            if balance < threshold:
                # 余额低于阈值
                if already_notified:
                    # 已预警过，跳过（去重）
                    continue
                # 检查用户是否启用了该事件
                if not await _is_event_enabled_for_user(tenant_id, user_id):
                    continue
                # 触发预警
                try:
                    await notify_token_low_balance(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        balance=balance,
                        threshold=threshold,
                    )
                    stats["warned"] += 1
                except Exception as exc:
                    logger.warning(
                        "Token 余额预警失败 tenant=%d user=%d balance=%d threshold=%d: %s",
                        tenant_id, user_id, balance, threshold, exc,
                    )
                    stats["errors"] += 1
            else:
                # 余额 >= 阈值：若曾预警过，清除去重标记，让下次余额再次低于阈值时能重新预警
                if already_notified:
                    try:
                        await clear_token_low_balance_notifications(tenant_id, user_id)
                        stats["cleared"] += 1
                        logger.info(
                            "Token 余额已恢复，清除预警标记 tenant=%d user=%d balance=%d threshold=%d",
                            tenant_id, user_id, balance, threshold,
                        )
                    except Exception as exc:
                        logger.warning(
                            "清除 Token 预警标记失败 tenant=%d user=%d: %s",
                            tenant_id, user_id, exc,
                        )
                        stats["errors"] += 1
        except Exception as exc:
            logger.warning(
                "Token 余额扫描单用户异常 tenant=%d user=%d: %s",
                tenant_id, user_id, exc,
            )
            stats["errors"] += 1

    logger.info(
        "Token 余额扫描完成: scanned=%d warned=%d cleared=%d errors=%d",
        stats["scanned"], stats["warned"], stats["cleared"], stats["errors"],
    )
    return stats


async def run_token_balance_warning_loop():
    """Token 余额预警定时循环：每 30 分钟扫描一次。"""
    logger.info("Token 余额预警循环已启动，扫描间隔 %ds", SCAN_INTERVAL_SEC)
    while True:
        try:
            await run_token_balance_warning_once()
        except Exception as exc:
            logger.warning("Token 余额预警循环异常: %s", exc)
        await asyncio.sleep(SCAN_INTERVAL_SEC)
