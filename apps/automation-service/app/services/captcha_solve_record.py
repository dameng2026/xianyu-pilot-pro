"""
滑块求解记录服务
================
提供滑块求解记录的创建、更新、查询能力，以及 SSE 广播。

每次调用 handle_captcha_for_account 时创建一条记录，
求解过程中更新记录的 status / result / error_message。

SSE 事件类型 "captcha_solve" 广播到前端，实时展示求解状态。
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import text

from ..core.database import async_session
from ..core.failure_logging import log_service_failure
from .ws_sse import broadcaster

logger = logging.getLogger(__name__)

# 触发场景 → 事件描述映射
TRIGGER_SCENE_DESC = {
    "ws_connect": "WS 连接触发滑块验证",
    "cookie_keepalive": "Cookie 保活触发滑块验证",
    "token_refresh": "Token 刷新触发滑块验证",
    "manual": "手动触发滑块求解",
    "manual_retry": "手动重试滑块求解",
}


def _build_event_desc(trigger_scene: str, extra: str = "") -> str:
    """根据触发场景生成事件描述"""
    base = TRIGGER_SCENE_DESC.get(trigger_scene, "触发滑块验证")
    if extra:
        return f"{base}（{extra}）"
    return base


async def _lookup_account_name(tenant_id: int, account_id: int) -> str:
    """查询账号昵称，找不到时回退为账号ID字符串"""
    try:
        async with async_session() as db:
            row = (await db.execute(
                text(
                    "SELECT nickname FROM xianyu_account "
                    "WHERE id = :aid AND tenant_id = :tid AND deleted = 0 LIMIT 1"
                ),
                {"aid": account_id, "tid": tenant_id},
            )).mappings().first()
            if row and row.get("nickname"):
                return str(row["nickname"])
    except Exception:
        logger.debug("查询账号昵称失败，回退为账号ID", exc_info=True)
    return str(account_id)


async def create_solve_record(
    account_id: int,
    tenant_id: int,
    trigger_scene: str = "manual",
    event_desc: str = "",
    open_reason: str = "",
    solve_reason: str = "",
    retry_count: int = 0,
) -> Optional[int]:
    """创建一条滑块求解记录，返回 record_id。

    Args:
        account_id: 账号 ID
        tenant_id: 租户 ID
        trigger_scene: 触发场景 (ws_connect/cookie_keepalive/token_refresh/manual)
        event_desc: 事件描述（为空时根据 trigger_scene 自动生成）
        open_reason: 开启原因（为什么打开滑块求解流程，例如"用户手动点击"/"账号状态异常自动触发"）
        solve_reason: 求解原因（为什么进行滑块求解，例如"WS Token 失败"/"Cookie 保活触发滑块"）
        retry_count: 重试次数

    Returns:
        record_id，失败时返回 None
    """
    if not event_desc:
        event_desc = _build_event_desc(trigger_scene)
    # 默认开启原因：根据触发场景推断
    if not open_reason:
        if trigger_scene in ("manual", "manual_retry"):
            open_reason = "用户手动点击求解按钮"
        else:
            open_reason = "账号状态异常自动触发"
    # 默认求解原因：使用事件描述
    if not solve_reason:
        solve_reason = event_desc

    account_name = await _lookup_account_name(tenant_id, account_id)

    try:
        async with async_session() as db:
            result = await db.execute(
                text(
                    "INSERT INTO xianyu_captcha_solve_record "
                    "(tenant_id, account_id, account_name, event_desc, open_reason, solve_reason, trigger_scene, "
                    " result, status, engine, retry_count, created_at, updated_at, deleted) "
                    "VALUES (:tid, :aid, :aname, :edesc, :oreason, :sreason, :scene, "
                    " '', 'queued', 'Playwright', :rc, NOW(), NOW(), 0)"
                ),
                {
                    "tid": tenant_id,
                    "aid": account_id,
                    "aname": account_name,
                    "edesc": event_desc,
                    "oreason": open_reason,
                    "sreason": solve_reason,
                    "scene": trigger_scene,
                    "rc": retry_count,
                },
            )
            await db.commit()
            # aiomysql/SQLAlchemy 下 result.lastrowid 偶发为 0，回退 LAST_INSERT_ID()
            record_id = getattr(result, "lastrowid", None) or 0
            if not record_id:
                try:
                    rid_row = (await db.execute(text("SELECT LAST_INSERT_ID() AS id"))).mappings().first()
                    record_id = int(rid_row["id"]) if rid_row and rid_row.get("id") else 0
                except Exception:
                    record_id = 0
            if not record_id:
                logger.warning(
                    "创建滑块求解记录成功但未取到 recordId accountId=%d scene=%s",
                    account_id, trigger_scene,
                )
                return None
            logger.info(
                "创建滑块求解记录: recordId=%d accountId=%d scene=%s openReason=%s solveReason=%s",
                record_id, account_id, trigger_scene, open_reason, solve_reason,
            )
            return int(record_id)
    except Exception as e:
        log_service_failure(
            logger, e, operation="create_captcha_solve_record",
            tenant_id=tenant_id, account_id=account_id, level=logging.WARNING,
        )
        return None


async def update_solve_record(
    record_id: Optional[int],
    status: str = "",
    result: str = "",
    error_message: str = "",
    retry_count: Optional[int] = None,
    duration_ms: Optional[int] = None,
    screenshot_path: str = "",
    engine: str = "",
) -> None:
    """更新滑块求解记录。

    Args:
        record_id: 记录 ID（为 None 或 0 时静默跳过）
        status: 处理状态 (queued/retrying/success/fail)
        result: 处理结果 (slider_success/slider_fail)
        error_message: 错误详情
        retry_count: 重试次数
        duration_ms: 耗时（毫秒），写入 error_message 前缀元数据时使用
        screenshot_path: 调试截图路径
        engine: 验证引擎
    """
    if not record_id:
        return

    sets = ["updated_at = NOW()"]
    params: dict[str, Any] = {"rid": record_id}

    if status:
        sets.append("status = :status")
        params["status"] = status
    if result:
        sets.append("result = :result")
        params["result"] = result
    # 将耗时/截图附加到 error_message，避免强制 DB 迁移；成功时也保留诊断信息
    meta_bits: list[str] = []
    if duration_ms is not None and duration_ms >= 0:
        meta_bits.append(f"durationMs={duration_ms}")
    if screenshot_path:
        meta_bits.append(f"screenshot={screenshot_path}")
    if error_message or meta_bits:
        msg = error_message or ""
        if meta_bits:
            prefix = "[" + ", ".join(meta_bits) + "]"
            msg = f"{prefix} {msg}".strip()
        sets.append("error_message = :emsg")
        params["emsg"] = msg[:2000]
    if retry_count is not None:
        sets.append("retry_count = :rc")
        params["rc"] = retry_count
    if engine:
        sets.append("engine = :engine")
        params["engine"] = engine[:64]

    try:
        async with async_session() as db:
            await db.execute(
                text(f"UPDATE xianyu_captcha_solve_record SET {', '.join(sets)} WHERE id = :rid"),
                params,
            )
            await db.commit()
    except Exception as e:
        log_service_failure(
            logger, e, operation="update_captcha_solve_record",
            level=logging.WARNING,
        )


async def list_solve_records(
    tenant_id: int,
    account_id: int = 0,
    status: str = "",
    trigger_scene: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """分页查询滑块求解记录。

    Returns:
        {"list": [...], "total": int, "page": int, "pageSize": int}
    """
    where_clauses = ["tenant_id = :tid", "COALESCE(deleted, 0) = 0"]
    params: dict[str, Any] = {"tid": tenant_id}

    if account_id:
        where_clauses.append("account_id = :aid")
        params["aid"] = account_id
    if status:
        where_clauses.append("status = :status")
        params["status"] = status
    if trigger_scene:
        where_clauses.append("trigger_scene = :scene")
        params["scene"] = trigger_scene

    where_sql = " AND ".join(where_clauses)
    offset = max(0, (page - 1) * page_size)

    try:
        async with async_session() as db:
            # 查询总数
            count_row = (await db.execute(
                text(f"SELECT COUNT(*) AS cnt FROM xianyu_captcha_solve_record WHERE {where_sql}"),
                params,
            )).mappings().first()
            total = int(count_row["cnt"]) if count_row else 0

            # 查询列表
            rows = (await db.execute(
                text(
                    f"SELECT id, account_id, account_name, event_desc, open_reason, solve_reason, "
                    f"trigger_scene, result, status, engine, retry_count, error_message, "
                    f"priority, failure_reason, queued_at, started_at, finished_at, "
                    f"created_at, updated_at "
                    f"FROM xianyu_captcha_solve_record WHERE {where_sql} "
                    f"ORDER BY created_at DESC, id DESC LIMIT :limit OFFSET :offset"
                ),
                {**params, "limit": page_size, "offset": offset},
            )).mappings().all()

            items = []
            for row in rows:
                items.append({
                    "id": row["id"],
                    "accountId": row["account_id"],
                    "accountName": row["account_name"],
                    "eventDesc": row["event_desc"],
                    "openReason": row.get("open_reason") or "",
                    "solveReason": row.get("solve_reason") or "",
                    "triggerScene": row["trigger_scene"],
                    "result": row["result"],
                    "status": row["status"],
                    "engine": row["engine"],
                    "retryCount": row["retry_count"],
                    "errorMessage": row["error_message"],
                    "priority": int(row.get("priority") or 0),
                    "failureReason": row.get("failure_reason") or "",
                    "queuedAt": str(row["queued_at"]) if row.get("queued_at") else "",
                    "startedAt": str(row["started_at"]) if row.get("started_at") else "",
                    "finishedAt": str(row["finished_at"]) if row.get("finished_at") else "",
                    "createdAt": str(row["created_at"]) if row["created_at"] else "",
                    "updatedAt": str(row["updated_at"]) if row["updated_at"] else "",
                })

            return {
                "list": items,
                "total": total,
                "page": page,
                "pageSize": page_size,
            }
    except Exception as e:
        log_service_failure(
            logger, e, operation="list_captcha_solve_records",
            tenant_id=tenant_id,
        )
        return {"list": [], "total": 0, "page": page, "pageSize": page_size}


async def broadcast_captcha_solve(
    tenant_id: int,
    account_id: int,
    account_name: str,
    status: str,
    result: str = "",
    engine: str = "Playwright",
    reason: str = "",
    record_id: Optional[int] = None,
) -> None:
    """通过 SSE 广播滑块求解状态事件。

    事件类型: "captcha_solve"
    前端监听后更新求解状态指示器。

    Args:
        status: queued/retrying/success/fail
        result: slider_success/slider_fail
        reason: 失败原因或额外信息
    """
    try:
        await broadcaster.broadcast(
            tenant_id,
            "captcha_solve",
            {
                "accountId": account_id,
                "accountName": account_name,
                "status": status,
                "result": result,
                "engine": engine,
                "reason": reason,
                "recordId": record_id,
            },
        )
    except Exception as e:
        log_service_failure(
            logger, e, operation="broadcast_captcha_solve",
            tenant_id=tenant_id, account_id=account_id, level=logging.DEBUG,
        )


# ============================================================
# 僵尸记录清理（Phase 5：无响应进行中记录处理）
# ============================================================

# 僵尸记录判定阈值：started_at 超过此分钟数仍为 retrying 状态 → 标记为 stale_terminated
# 5 分钟超时：避免浏览器窗口/HTTP 调用长时间挂起占用服务器资源
STALE_RECORD_TIMEOUT_MINUTES = 5

# 清理循环间隔（秒）
STALE_CLEANUP_INTERVAL_SECONDS = 300  # 5 分钟

# 超时终止后允许重新入队的最大次数（避免无限重试）
STALE_TERMINATED_MAX_RETRY = 1


async def cleanup_stale_records() -> int:
    """清理僵尸求解记录：将超时仍为 retrying 的记录标记为 stale_terminated。

    判定条件（仅针对正在处理的任务，排队中的任务不受影响）：
    - status = 'retrying'
    - started_at IS NOT NULL AND started_at < NOW() - INTERVAL 5 MINUTE
      （started_at 由 worker 取出任务时设置，表示已正式开始处理）

    注意：status='queued'（排队中）的记录不会被清理，避免排队任务被误判超时。
    只有 worker 正式开始处理的任务（status='retrying' 且 started_at 非空）才适用 5 分钟超时。

    超时后执行三步动作：
    1. 标记为 stale_terminated（status=fail, result=stale_terminated, failure_reason=stale_terminated）
    2. 广播 SSE captcha_solve 事件，让前后台实时看到状态变化
    3. 触发重新入队（cookie 预校验由 worker 自动处理，cookie 无效则不重试）

    Returns:
        被清理的记录数
    """
    import asyncio

    try:
        async with async_session() as db:
            # 1. 先查询超时的 retrying 记录详情（用于广播和重新入队）
            # 仅清理已正式开始处理（started_at 非空）且超时的记录，排队中（queued）的任务不受影响
            rows = (await db.execute(
                text(
                    """
                    SELECT id, account_id, tenant_id, account_name, retry_count,
                           trigger_scene, priority, open_reason, solve_reason
                    FROM xianyu_captcha_solve_record
                    WHERE status = 'retrying'
                      AND COALESCE(deleted, 0) = 0
                      AND started_at IS NOT NULL
                      AND started_at < DATE_SUB(NOW(), INTERVAL :min1 MINUTE)
                    """,
                ),
                {"min1": STALE_RECORD_TIMEOUT_MINUTES},
            )).mappings().all()

            if not rows:
                return 0

            # 2. 批量更新为 stale_terminated
            record_ids = [int(r["id"]) for r in rows]
            # 构造 IN 子句参数
            id_params = {f"rid{i}": rid for i, rid in enumerate(record_ids)}
            in_clause = ",".join(f":rid{i}" for i in range(len(record_ids)))
            await db.execute(
                text(
                    f"""
                    UPDATE xianyu_captcha_solve_record
                    SET status = 'fail',
                        result = 'stale_terminated',
                        failure_reason = 'stale_terminated',
                        error_message = CONCAT(COALESCE(error_message, ''),
                            '[系统清理] 求解任务超时无响应（超过{STALE_RECORD_TIMEOUT_MINUTES}分钟），已自动终止'),
                        finished_at = NOW(),
                        updated_at = NOW()
                    WHERE id IN ({in_clause})
                    """,
                ),
                id_params,
            )
            await db.commit()

            affected = len(rows)
            logger.warning(
                "僵尸滑块求解记录清理：已将 %d 条超时 retrying 记录标记为 stale_terminated（超时=%d分钟）",
                affected, STALE_RECORD_TIMEOUT_MINUTES,
            )

            # 3. 对每条记录广播 SSE + 触发重新入队
            for row in rows:
                record_id = int(row["id"])
                account_id = int(row["account_id"])
                tenant_id = int(row["tenant_id"])
                account_name = str(row.get("account_name") or "")
                retry_count = int(row.get("retry_count") or 0)
                trigger_scene = str(row.get("trigger_scene") or "manual")
                priority = int(row.get("priority") or 0)
                open_reason = str(row.get("open_reason") or "")
                solve_reason = str(row.get("solve_reason") or "")

                # 3a. 广播 SSE 事件（前端实时看到状态从"进行中"变为"超时终止"）
                try:
                    await broadcaster.broadcast(
                        tenant_id,
                        "captcha_solve",
                        {
                            "accountId": account_id,
                            "accountName": account_name,
                            "status": "fail",
                            "result": "stale_terminated",
                            "engine": "Playwright",
                            "reason": f"求解超时（{STALE_RECORD_TIMEOUT_MINUTES}分钟无响应），已自动终止",
                            "recordId": record_id,
                        },
                    )
                except Exception as exc:
                    log_service_failure(
                        logger, exc, operation="broadcast_stale_terminated",
                        tenant_id=tenant_id, account_id=account_id, level=logging.DEBUG,
                    )

                # 3b. 触发重新入队（cookie 预校验由 worker 在 _process_task 中自动处理）
                # 仅在未达到最大重试次数时重新入队
                if retry_count < STALE_TERMINATED_MAX_RETRY:
                    asyncio.create_task(_reenqueue_after_stale(
                        account_id=account_id,
                        tenant_id=tenant_id,
                        trigger_scene=trigger_scene,
                        open_reason=f"超时自动重试（第 {retry_count + 1} 次，原记录已超时终止）",
                        solve_reason=solve_reason,
                        priority=priority,
                        retry_count=retry_count + 1,
                    ))
                else:
                    logger.info(
                        "超时终止记录已达到最大重试次数，不再重新入队 accountId=%d retry=%d/%d",
                        account_id, retry_count, STALE_TERMINATED_MAX_RETRY,
                    )

            return affected
    except Exception as e:
        log_service_failure(
            logger, e, operation="cleanup_stale_records",
            level=logging.WARNING,
        )
        return 0


async def _reenqueue_after_stale(
    account_id: int,
    tenant_id: int,
    trigger_scene: str,
    open_reason: str,
    solve_reason: str,
    priority: int,
    retry_count: int,
) -> None:
    """超时终止后重新入队（异步执行，不阻塞清理循环）。

    重新入队后，worker 会自动进行 cookie 预校验（precheck_cookie_status）：
    - Cookie 有效 → 继续求解
    - Cookie 触发滑块 → 继续求解（这正是要解决的）
    - Cookie 无效/Session 过期 → 标记为 cookie_invalid，不重试

    注意：必须 skip_dedup=True，因为原任务才5分钟前入队，
    30 分钟去重会跳过超时重试。
    """
    try:
        from .captcha_queue import get_queue_manager
        manager = await get_queue_manager()
        # 直接调用 manager.enqueue，skip_dedup=True 跳过30分钟去重
        record_id = await manager.enqueue(
            account_id=account_id,
            tenant_id=tenant_id,
            trigger_scene=trigger_scene,
            open_reason=open_reason,
            solve_reason=solve_reason,
            priority=priority,
            retry_count=retry_count,
            skip_dedup=True,
        )
        if record_id:
            logger.info(
                "超时终止后已重新入队 accountId=%d tenantId=%d retry=%d recordId=%d（cookie 预校验将由 worker 处理）",
                account_id, tenant_id, retry_count, record_id,
            )
        else:
            logger.warning(
                "超时终止后重新入队失败（被去重或其他原因跳过）accountId=%d", account_id,
            )
    except Exception as e:
        log_service_failure(
            logger, e, operation="reenqueue_after_stale",
            tenant_id=tenant_id, account_id=account_id, level=logging.WARNING,
        )


async def run_stale_cleanup_loop() -> None:
    """僵尸记录清理循环（在 FastAPI lifespan 中启动）。

    每 5 分钟扫描一次，将超过 5 分钟仍为 retrying 状态的记录标记为 stale_terminated，
    广播 SSE 事件，并在 cookie 有效时触发重新入队。
    """
    import asyncio
    logger.info("僵尸滑块求解记录清理循环已启动，间隔=%ds 超时=%dmin 最大重试=%d",
                STALE_CLEANUP_INTERVAL_SECONDS, STALE_RECORD_TIMEOUT_MINUTES, STALE_TERMINATED_MAX_RETRY)
    while True:
        try:
            await asyncio.sleep(STALE_CLEANUP_INTERVAL_SECONDS)
            await cleanup_stale_records()
        except asyncio.CancelledError:
            logger.info("僵尸滑块求解记录清理循环已停止")
            break
        except Exception as e:
            log_service_failure(
                logger, e, operation="stale_cleanup_loop",
                level=logging.WARNING,
            )
            # 出错后短暂等待，避免紧密循环
            await asyncio.sleep(60)
