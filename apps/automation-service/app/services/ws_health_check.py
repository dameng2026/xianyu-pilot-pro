"""WS 连接健康检查定时循环。

场景：滑块求解成功后 WS 客户端已重启，但可能因为网络抖动、cookie 边界
问题等导致 WS 长时间无法真正建立连接。此时 cookie_status=1（cookie 有效）
但 ws_status=0（WS 未连接），用户在前台看到"WS 未连接"，且无法接收最新
消息。

本模块每 2 分钟扫描一次此类账号，对满足条件的账号触发滑块求解入队
（trigger_scene="ws_health_check"），因为 WS 长时间连不上通常意味着
又遇到了滑块验证。captcha_queue 的去重机制（队列进程去重 + DB retrying
去重）会自动防止重复入队。

判定条件（同时满足）：
1. cookie_status = 1（cookie 仍有效）
2. ws_status = 0（WS 未连接）
3. last_heartbeat_time 距今超过 5 分钟（避免刚启动/重启的账号被误判）
4. ws_manager 中无活跃客户端 或 客户端 is_connected=False
5. 账号不在排除表 xianyu_account_solve_exclusion 中（enqueue_solve 内部也会检查）
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text

from ..core.failure_logging import log_service_failure
from .captcha_queue import enqueue_solve

logger = logging.getLogger(__name__)

# 扫描间隔（秒）
WS_HEALTH_CHECK_INTERVAL_SEC = 2 * 60  # 每 2 分钟扫描一次

# WS 无心跳阈值（秒）：超过此时间无心跳才认为 WS 真正异常
WS_NO_HEARTBEAT_THRESHOLD_SEC = 5 * 60  # 5 分钟

# 单次扫描最大入队数量，避免一次涌入过多
MAX_ENQUEUE_PER_SCAN = 10


async def _scan_and_enqueue_ws_health() -> int:
    """扫描 cookie_status=1 但 ws_status=0 的账号，触发滑块求解入队。

    Returns:
        本次扫描实际入队的账号数量
    """
    from ..core.database import async_session
    from .ws_client import ws_manager

    try:
        async with async_session() as db:
            rows = (await db.execute(
                text(
                    "SELECT r.account_id, r.tenant_id, a.nickname, "
                    "r.last_heartbeat_time, r.updated_time, "
                    "TIMESTAMPDIFF(SECOND, COALESCE(r.last_heartbeat_time, '1970-01-01'), NOW()) AS hb_age_sec "
                    "FROM xianyu_account_runtime r "
                    "INNER JOIN xianyu_account a ON a.id = r.account_id AND a.tenant_id = r.tenant_id "
                    "WHERE r.deleted = 0 "
                    "  AND a.deleted = 0 "
                    "  AND r.cookie_status = 1 "
                    "  AND r.ws_status = 0 "
                    "  AND COALESCE(r.last_heartbeat_time, '1970-01-01') < DATE_SUB(NOW(), INTERVAL :threshold SECOND) "
                    "ORDER BY r.updated_time ASC "
                    "LIMIT :limit"
                ),
                {
                    "threshold": WS_NO_HEARTBEAT_THRESHOLD_SEC,
                    "limit": MAX_ENQUEUE_PER_SCAN * 2,  # 多查一些，内存校验后取前 N
                },
            )).mappings().all()
    except Exception as e:
        log_service_failure(logger, e, operation="ws_health_scan", level=logging.WARNING)
        return 0

    if not rows:
        return 0

    enqueued = 0
    for row in rows:
        if enqueued >= MAX_ENQUEUE_PER_SCAN:
            break

        account_id = int(row["account_id"])
        tenant_id = int(row["tenant_id"])
        nickname = str(row["nickname"] or "")[:30]
        hb_age = int(row["hb_age_sec"] or 0)

        # 内存二次校验：如果 ws_manager 中有活跃且已连接的客户端，
        # 说明 DB 状态滞后（_persist_ws_online 还没执行或被覆盖），跳过
        try:
            client = ws_manager.get_client(account_id)
            if client is not None and client.is_connected:
                logger.debug(
                    "WS 健康检查跳过（内存显示已连接）: accountId=%d nickname=%s",
                    account_id, nickname,
                )
                continue
        except Exception:
            # get_client 异常不阻断，继续尝试入队
            pass

        # 入队滑块求解（trigger_scene="ws_health_check"）
        # enqueue_solve 内部有 4 层去重：排除表、内存 pending、DB retrying、手动冷却
        # 这里无需额外去重
        try:
            record_id = await enqueue_solve(
                account_id=account_id,
                tenant_id=tenant_id,
                trigger_scene="ws_health_check",
                open_reason=f"WS 健康检查：cookie 有效但 WS 无心跳 {hb_age}s",
                solve_reason="ws_health_check",
                priority=0,
            )
            if record_id:
                enqueued += 1
                logger.info(
                    "WS 健康检查已入队滑块求解: accountId=%d tenantId=%d nickname=%s hbAge=%ds recordId=%s",
                    account_id, tenant_id, nickname, hb_age, record_id,
                )
            else:
                logger.debug(
                    "WS 健康检查入队被去重跳过: accountId=%d nickname=%s",
                    account_id, nickname,
                )
        except Exception as e:
            log_service_failure(
                logger, e, operation="ws_health_enqueue",
                tenant_id=tenant_id, account_id=account_id, level=logging.WARNING,
            )

    if enqueued > 0:
        logger.info("WS 健康检查扫描完成，本次入队 %d 个账号", enqueued)
    return enqueued


async def run_ws_health_check_loop():
    """WS 连接健康检查主循环。

    每 WS_HEALTH_CHECK_INTERVAL_SEC 秒扫描一次，对 cookie 有效但 WS
    长时间无心跳的账号触发滑块求解入队。
    """
    logger.info(
        "WS 连接健康检查循环已启动，间隔=%ds 无心跳阈值=%ds",
        WS_HEALTH_CHECK_INTERVAL_SEC, WS_NO_HEARTBEAT_THRESHOLD_SEC,
    )
    # 启动后延迟 60 秒再首次扫描，避免与启动流程冲突
    await asyncio.sleep(60)

    while True:
        try:
            await _scan_and_enqueue_ws_health()
        except asyncio.CancelledError:
            logger.info("WS 连接健康检查循环已取消")
            raise
        except Exception as e:
            log_service_failure(logger, e, operation="ws_health_check_loop", level=logging.WARNING)
            # 异常后退避 60 秒，避免疯狂报错
            await asyncio.sleep(60)
            continue

        await asyncio.sleep(WS_HEALTH_CHECK_INTERVAL_SEC)
