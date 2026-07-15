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
    retry_count: int = 0,
) -> Optional[int]:
    """创建一条滑块求解记录，返回 record_id。

    Args:
        account_id: 账号 ID
        tenant_id: 租户 ID
        trigger_scene: 触发场景 (ws_connect/cookie_keepalive/token_refresh/manual)
        event_desc: 事件描述（为空时根据 trigger_scene 自动生成）
        retry_count: 重试次数

    Returns:
        record_id，失败时返回 None
    """
    if not event_desc:
        event_desc = _build_event_desc(trigger_scene)

    account_name = await _lookup_account_name(tenant_id, account_id)

    try:
        async with async_session() as db:
            result = await db.execute(
                text(
                    "INSERT INTO xianyu_captcha_solve_record "
                    "(tenant_id, account_id, account_name, event_desc, trigger_scene, "
                    " result, status, engine, retry_count, created_at, updated_at) "
                    "VALUES (:tid, :aid, :aname, :edesc, :scene, '', 'retrying', 'Playwright', :rc, NOW(), NOW())"
                ),
                {
                    "tid": tenant_id,
                    "aid": account_id,
                    "aname": account_name,
                    "edesc": event_desc,
                    "scene": trigger_scene,
                    "rc": retry_count,
                },
            )
            await db.commit()
            record_id = result.lastrowid
            logger.info(
                "创建滑块求解记录: recordId=%d accountId=%d scene=%s",
                record_id, account_id, trigger_scene,
            )
            return record_id
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
) -> None:
    """更新滑块求解记录。

    Args:
        record_id: 记录 ID（为 None 或 0 时静默跳过）
        status: 处理状态 (retrying/success/fail)
        result: 处理结果 (slider_success/slider_fail)
        error_message: 错误详情
        retry_count: 重试次数
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
    if error_message:
        sets.append("error_message = :emsg")
        params["emsg"] = error_message
    if retry_count is not None:
        sets.append("retry_count = :rc")
        params["rc"] = retry_count

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
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """分页查询滑块求解记录。

    Returns:
        {"list": [...], "total": int, "page": int, "pageSize": int}
    """
    where_clauses = ["tenant_id = :tid", "deleted = 0"]
    params: dict[str, Any] = {"tid": tenant_id}

    if account_id:
        where_clauses.append("account_id = :aid")
        params["aid"] = account_id
    if status:
        where_clauses.append("status = :status")
        params["status"] = status

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
                    f"SELECT id, account_id, account_name, event_desc, trigger_scene, "
                    f"result, status, engine, retry_count, error_message, "
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
                    "triggerScene": row["trigger_scene"],
                    "result": row["result"],
                    "status": row["status"],
                    "engine": row["engine"],
                    "retryCount": row["retry_count"],
                    "errorMessage": row["error_message"],
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
        status: retrying/success/fail
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
