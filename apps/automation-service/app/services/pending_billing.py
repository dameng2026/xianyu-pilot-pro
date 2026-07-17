"""
AI 计费待补扣服务
=================
当 Python 端调用通用模型后，Java 计费服务暂不可用（AiBillingUnavailable）时，
将计费请求暂存到 pending_ai_billing 表，由定时任务在 Java 恢复后补扣。

设计要点：
- request_id 作为幂等键（UNIQUE），Java charge 接口支持 duplicate 检测，重复补扣安全
- 指数退避重试：30s → 60s → 120s → 240s → ... 封顶 30min
- 超过 max_attempts 后标记为 dead，不再重试
- 仅处理 AiBillingUnavailable（服务不可用），AiBillingPaymentRequired（余额不足）
  和 AiBillingError（其他计费错误）不入队，由调用方处理
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import text

from ..core.database import async_session
from ..core.failure_logging import log_service_failure

logger = logging.getLogger(__name__)

# 重试间隔（秒）：30s, 60s, 120s, 240s, 480s, 960s, 1800s(封顶)
BASE_RETRY_SEC = 30
MAX_RETRY_SEC = 30 * 60
DEFAULT_MAX_ATTEMPTS = 12
BATCH_LIMIT = 50
SCAN_INTERVAL_SEC = 60

_ENSURED = False


def _retry_delay_sec(attempt_count: int) -> int:
    """指数退避：30s * 2^(attempt)，封顶 30min"""
    if attempt_count <= 0:
        return BASE_RETRY_SEC
    sec = BASE_RETRY_SEC * (2 ** attempt_count)
    return int(min(MAX_RETRY_SEC, sec))


async def ensure_pending_billing_table() -> None:
    """幂等建表兜底，避免迁移未跑导致暂存失败。"""
    global _ENSURED
    if _ENSURED:
        return
    try:
        async with async_session() as db:
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS pending_ai_billing (
                  id BIGINT PRIMARY KEY AUTO_INCREMENT,
                  tenant_id BIGINT NOT NULL,
                  user_id BIGINT NOT NULL,
                  account_id BIGINT NOT NULL DEFAULT 0,
                  scene VARCHAR(80) NOT NULL,
                  request_id VARCHAR(120) NOT NULL,
                  payload_json MEDIUMTEXT NOT NULL,
                  attempt_count INT NOT NULL DEFAULT 0,
                  max_attempts INT NOT NULL DEFAULT 12,
                  next_retry_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  last_error VARCHAR(512) DEFAULT '',
                  status VARCHAR(20) NOT NULL DEFAULT 'pending',
                  created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                  UNIQUE KEY uk_pending_billing_request (request_id),
                  KEY idx_pending_billing_due (status, next_retry_at),
                  KEY idx_pending_billing_user (tenant_id, user_id, status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """))
            await db.commit()
        _ENSURED = True
    except Exception as exc:
        log_service_failure(logger, exc, operation="ensure_pending_billing_table")
        # 不抛出，降级为不暂存（与原降级行为一致）


async def enqueue_pending_billing(
    db,
    *,
    tenant_id: int,
    user_id: int,
    account_id: int,
    scene: str,
    request_id: str,
    payload: dict[str, Any],
    error: str = "",
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> None:
    """将一次失败的计费请求暂存到 pending_ai_billing 表。

    如果 request_id 已存在（之前已入队），则忽略（幂等）。
    payload 应包含重试时调用 charge_text_usage / charge_image_usage 所需的全部参数。
    """
    if not request_id:
        logger.warning("[PENDING_BILLING] 缺少 request_id，跳过暂存 tenantId=%d scene=%s", tenant_id, scene)
        return
    try:
        payload_json = json.dumps(payload, ensure_ascii=False, default=str)
        # INSERT IGNORE：如果 request_id 已存在则跳过（幂等）
        result = await db.execute(text("""
            INSERT IGNORE INTO pending_ai_billing
                (tenant_id, user_id, account_id, scene, request_id, payload_json,
                 attempt_count, max_attempts, next_retry_at, last_error, status)
            VALUES
                (:tenant_id, :user_id, :account_id, :scene, :request_id, :payload_json,
                 0, :max_attempts, NOW(), :error, 'pending')
        """), {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "account_id": account_id,
            "scene": scene,
            "request_id": request_id,
            "payload_json": payload_json,
            "max_attempts": max_attempts,
            "error": (error or "")[:500],
        })
        await db.commit()
        if result.rowcount > 0:
            logger.info("[PENDING_BILLING] 已暂存计费请求 tenantId=%d userId=%d scene=%s requestId=%s",
                        tenant_id, user_id, scene, request_id)
    except Exception as exc:
        log_service_failure(logger, exc, operation="enqueue_pending_billing")
        # 暂存失败不影响主流程（与原降级行为一致）


async def list_due_pending(db, limit: int = BATCH_LIMIT) -> list[dict[str, Any]]:
    """捞起到期的待补扣记录。"""
    rows = (await db.execute(text("""
        SELECT id, tenant_id, user_id, account_id, scene, request_id, payload_json,
               attempt_count, max_attempts
        FROM pending_ai_billing
        WHERE status = 'pending' AND next_retry_at <= NOW()
        ORDER BY next_retry_at ASC
        LIMIT :limit
    """), {"limit": limit})).mappings().all()
    return [dict(r) for r in rows]


async def mark_pending_success(db, record_id: int) -> None:
    await db.execute(text("""
        UPDATE pending_ai_billing
        SET status = 'success', last_error = '', next_retry_at = NULL, updated_time = NOW()
        WHERE id = :id
    """), {"id": record_id})
    await db.commit()


async def mark_pending_failed(db, record_id: int, attempt_count: int, max_attempts: int, error: str) -> None:
    """失败时更新 attempt_count 并安排下次重试；超过 max_attempts 标记为 dead。"""
    if attempt_count + 1 >= max_attempts:
        await db.execute(text("""
            UPDATE pending_ai_billing
            SET status = 'dead', attempt_count = :attempt_count, last_error = :error,
                next_retry_at = NULL, updated_time = NOW()
            WHERE id = :id
        """), {"id": record_id, "attempt_count": attempt_count + 1, "error": (error or "")[:500]})
        logger.warning("[PENDING_BILLING] 计费补扣超过最大次数，标记为 dead recordId=%d", record_id)
    else:
        delay = _retry_delay_sec(attempt_count + 1)
        next_retry = datetime.now() + timedelta(seconds=delay)
        await db.execute(text("""
            UPDATE pending_ai_billing
            SET attempt_count = :attempt_count, last_error = :error,
                next_retry_at = :next_retry, updated_time = NOW()
            WHERE id = :id
        """), {
            "id": record_id,
            "attempt_count": attempt_count + 1,
            "error": (error or "")[:500],
            "next_retry": next_retry,
        })
        logger.info("[PENDING_BILLING] 计费补扣失败，%ds 后重试 recordId=%d attempt=%d",
                    delay, record_id, attempt_count + 1)
    await db.commit()


async def _retry_one_pending(db, record: dict[str, Any]) -> bool:
    """重试单条待补扣记录，成功返回 True。"""
    from .ai_billing import charge_ai_usage, AiBillingPaymentRequired, AiBillingError

    record_id = int(record["id"])
    request_id = str(record["request_id"])
    scene = str(record["scene"])
    attempt_count = int(record["attempt_count"])

    try:
        payload = json.loads(record["payload_json"])
    except (TypeError, ValueError) as exc:
        await mark_pending_failed(db, record_id, attempt_count, int(record["max_attempts"]),
                                  f"payload 解析失败: {exc}")
        return False

    try:
        result = await charge_ai_usage(payload)
        logger.info("[PENDING_BILLING] 补扣成功 recordId=%d scene=%s requestId=%s result=%s",
                    record_id, scene, request_id, result)
        await mark_pending_success(db, record_id)
        return True
    except AiBillingPaymentRequired as exc:
        # 余额不足，标记为 dead（用户需充值后由其他机制处理）
        await mark_pending_failed(db, record_id, attempt_count, int(record["max_attempts"]),
                                  f"余额不足: {exc}")
        logger.warning("[PENDING_BILLING] 补扣时余额不足，标记为 dead recordId=%d scene=%s", record_id, scene)
        return False
    except AiBillingError as exc:
        await mark_pending_failed(db, record_id, attempt_count, int(record["max_attempts"]), str(exc))
        return False


async def run_pending_billing_retry_once(limit: int = BATCH_LIMIT) -> dict[str, int]:
    """执行一轮待补扣重试。返回统计信息。"""
    await ensure_pending_billing_table()
    success = 0
    failed = 0
    async with async_session() as db:
        records = await list_due_pending(db, limit=limit)
        for record in records:
            try:
                ok = await _retry_one_pending(db, record)
                if ok:
                    success += 1
                else:
                    failed += 1
            except Exception as exc:
                log_service_failure(logger, exc, operation="retry_pending_billing",
                                    extra={"record_id": record.get("id")})
                failed += 1
    if success or failed:
        logger.info("[PENDING_BILLING] 本轮补扣完成 success=%d failed=%d", success, failed)
    return {"success": success, "failed": failed, "scanned": len(records) if 'records' in dir() else 0}


async def run_pending_billing_loop() -> None:
    """待补扣定时循环，每 60 秒扫描一次。在 main.py lifespan 中启动。"""
    logger.info("pending billing retry loop started, interval=%ss", SCAN_INTERVAL_SEC)
    while True:
        try:
            await run_pending_billing_retry_once()
        except Exception as exc:
            log_service_failure(logger, exc, operation="pending_billing_loop")
        await asyncio.sleep(SCAN_INTERVAL_SEC)
