"""API 对接滑块求解记录持久化服务。

与内部 captcha_solve_record.py 物理隔离，写入 xianyu_api_captcha_solve_record 表。
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import text

from ..core.database import async_session

logger = logging.getLogger(__name__)


async def create_api_record(
    tenant_id: int,
    api_key_prefix: str,
    request_id: str,
    client_ip: Optional[str] = None,
    event_desc: str = "external api slider solve",
) -> None:
    """创建 API 求解记录，status=queued"""
    sql = text(
        "INSERT INTO xianyu_api_captcha_solve_record "
        "(tenant_id, api_key_prefix, client_ip, request_id, event_desc, trigger_scene, "
        "result, status, engine, retry_count, priority, failure_reason, queued_at, created_at, updated_at, deleted) "
        "VALUES (:tid, :prefix, :ip, :rid, :edesc, 'api', '', 'queued', 'Playwright', 0, 0, '', NOW(), NOW(), NOW(), 0)"
    )
    params = {
        "tid": tenant_id, "prefix": api_key_prefix, "ip": client_ip,
        "rid": request_id, "edesc": event_desc,
    }
    try:
        async with async_session() as db:
            await db.execute(sql, params)
            await db.commit()
    except Exception as e:
        logger.exception("create_api_record failed req=%s tenant=%s: %s", request_id, tenant_id, e)


async def update_api_record(
    request_id: str,
    status: str = "",
    result: str = "",
    failure_reason: str = "",
    error_message: str = "",
    duration_ms: Optional[int] = None,
    started: bool = False,
) -> None:
    """更新 API 求解记录。started=True 时设置 started_at=NOW()，否则设置 finished_at=NOW()"""
    sets = ["updated_at = NOW()"]
    params: dict = {"rid": request_id}
    if status:
        sets.append("status = :status")
        params["status"] = status
    if result:
        sets.append("result = :result")
        params["result"] = result
    if failure_reason:
        sets.append("failure_reason = :reason")
        params["reason"] = failure_reason
    if error_message:
        sets.append("error_message = :err")
        params["err"] = _sanitize_error(error_message)
    if duration_ms is not None:
        sets.append("duration_ms = :dur")
        params["dur"] = duration_ms
    if started:
        sets.append("started_at = NOW()")
    else:
        sets.append("finished_at = NOW()")
    sql = text(f"UPDATE xianyu_api_captcha_solve_record SET {', '.join(sets)} WHERE request_id = :rid")
    try:
        async with async_session() as db:
            await db.execute(sql, params)
            await db.commit()
    except Exception as e:
        logger.exception("update_api_record failed req=%s: %s", request_id, e)


def _sanitize_error(msg: str) -> str:
    """脱敏 cookie 片段"""
    import re
    if not msg:
        return ""
    msg = re.sub(r"(?i)(cookie=)[^;\s]+", r"\1***", msg)
    msg = re.sub(r"(?i)(_m_h5_tk=)[^;\s]+", r"\1***", msg)
    return msg[:2000]  # 截断防止超长
