"""退款关单（退款订单注销）配置路由"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.camel import CamelModel
from ....core.database import get_db
from ....core.http_failures import safe_route_failure
from ....core.response import ResultObject
from ..deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/refundCancel", tags=["refundCancel"])


class RefundCancelSaveRequest(CamelModel):
    enabled: bool = False
    url: str = ""
    timeout: Optional[int] = Field(None, description="超时秒数，默认60")


async def _assert_account_visible(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
) -> bool:
    row = (await db.execute(
        text("""
            SELECT id FROM xianyu_account
            WHERE id = :account_id AND tenant_id = :tenant_id AND deleted = 0
            LIMIT 1
        """),
        {"account_id": account_id, "tenant_id": tenant_id},
    )).mappings().first()
    return row is not None


@router.get("/{accountId}")
async def get_refund_cancel_config(
    accountId: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """查询指定账号的退款关单配置。"""
    try:
        tenant_id = int(current_user.get("tenant_id") or 0)
        if tenant_id <= 0:
            return ResultObject.failed("缺少租户上下文", 400)
        if not await _assert_account_visible(db, tenant_id, accountId):
            return ResultObject.failed("账号不存在或无权操作", 404)
        row = (await db.execute(
            text("""
                SELECT refund_cancel_enabled, refund_cancel_url, refund_cancel_timeout
                FROM xianyu_account
                WHERE id = :account_id AND tenant_id = :tenant_id AND deleted = 0
                LIMIT 1
            """),
            {"account_id": accountId, "tenant_id": tenant_id},
        )).mappings().first()
        if not row:
            return ResultObject.failed("账号不存在或无权操作", 404)
        return ResultObject.success({
            "accountId": accountId,
            "enabled": bool(row.get("refund_cancel_enabled")),
            "url": row.get("refund_cancel_url") or "",
            "timeout": row.get("refund_cancel_timeout") if row.get("refund_cancel_timeout") is not None else 60,
        })
    except Exception as exc:
        return safe_route_failure(
            logger, exc, operation="get refund cancel config",
            user_message="获取退款关单配置失败，请稍后重试",
        )


@router.post("/{accountId}")
async def save_refund_cancel_config(
    accountId: int,
    req: RefundCancelSaveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """保存指定账号的退款关单配置。"""
    try:
        tenant_id = int(current_user.get("tenant_id") or 0)
        if tenant_id <= 0:
            return ResultObject.failed("缺少租户上下文", 400)
        if not await _assert_account_visible(db, tenant_id, accountId):
            return ResultObject.failed("账号不存在或无权操作", 404)

        url = (req.url or "").strip()
        if req.enabled and not url:
            return ResultObject.failed("开启退款关单时必须填写外部注销接口 URL", 400)
        if req.enabled and not url.lower().startswith("https://"):
            return ResultObject.failed("为安全起见，注销接口仅支持 https 公网地址", 400)
        try:
            timeout = int(req.timeout if req.timeout is not None else 60)
        except (TypeError, ValueError):
            timeout = 60
        if timeout < 1 or timeout > 120:
            return ResultObject.failed("超时时间需在 1-120 秒之间", 400)

        await db.execute(
            text("""
                UPDATE xianyu_account
                SET refund_cancel_enabled = :enabled,
                    refund_cancel_url = :url,
                    refund_cancel_timeout = :timeout,
                    updated_time = NOW()
                WHERE id = :account_id AND tenant_id = :tenant_id AND deleted = 0
            """),
            {
                "account_id": accountId,
                "tenant_id": tenant_id,
                "enabled": 1 if req.enabled else 0,
                "url": url if req.enabled else None,
                "timeout": timeout,
            },
        )
        await db.commit()
        return ResultObject.success({"accountId": accountId}, message="退款关单配置已保存")
    except Exception as exc:
        await db.rollback()
        return safe_route_failure(
            logger, exc, operation="save refund cancel config",
            user_message="保存退款关单配置失败，请稍后重试",
        )
