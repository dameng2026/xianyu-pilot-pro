"""个人黑名单路由（发货拦截）

功能：
- 按账号（可选商品范围）拉黑买家，命中后自动发货直接拦截并写失败记录
- 支持新增/更新、软删除、启停切换
"""
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

router = APIRouter(prefix="/blacklist", tags=["blacklist"])


class PersonalBlacklistSaveRequest(CamelModel):
    id: Optional[int] = None
    account_id: int = Field(..., description="闲鱼账号ID")
    buyer_user_id: str = Field(..., min_length=1, max_length=128)
    buyer_nickname: str = ""
    goods_id: str = ""
    reason: str = ""
    enabled: Optional[bool] = None


class PersonalBlacklistToggleRequest(CamelModel):
    id: int
    enabled: bool


def _normalize_buyer_id(value: str) -> str:
    raw = str(value or "").strip()
    if raw.lower().endswith("@goofish"):
        raw = raw[: -len("@goofish")]
    return raw


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


def _row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "accountId": row.get("account_id"),
        "accountName": row.get("account_name") or ("全部账号" if not row.get("account_id") else ""),
        "buyerUserId": row.get("buyer_user_id") or "",
        "buyerNickname": row.get("buyer_nickname") or "",
        "goodsId": row.get("goods_id") or "",
        "reason": row.get("reason") or "",
        "enabled": bool(row.get("enabled")),
        "createdAt": str(row.get("created_time")) if row.get("created_time") else None,
        "updatedAt": str(row.get("updated_time")) if row.get("updated_time") else None,
    }


@router.get("/personal/list")
async def list_personal_blacklist(
    accountId: Optional[int] = None,
    keyword: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """查询个人黑名单，支持按账号/买家ID或昵称筛选。"""
    try:
        tenant_id = int(current_user.get("tenant_id") or 0)
        if tenant_id <= 0:
            return ResultObject.failed("缺少租户上下文", 400)

        where = ["b.tenant_id = :tenant_id", "b.deleted = 0"]
        params: dict[str, Any] = {"tenant_id": tenant_id}
        if accountId is not None:
            where.append("b.account_id = :account_id")
            params["account_id"] = accountId
        if keyword and keyword.strip():
            where.append("(b.buyer_user_id LIKE :keyword OR b.buyer_nickname LIKE :keyword)")
            params["keyword"] = f"%{keyword.strip()}%"

        rows = (await db.execute(text(f"""
            SELECT b.*, a.nickname AS account_name
            FROM personal_blacklist b
            LEFT JOIN xianyu_account a ON a.id = b.account_id AND a.tenant_id = b.tenant_id
            WHERE {' AND '.join(where)}
            ORDER BY b.updated_time DESC, b.id DESC
        """), params)).mappings().all()
        data = [_row_to_dict(dict(r)) for r in rows]
        return ResultObject.success({"records": data, "total": len(data)})
    except Exception as exc:
        return safe_route_failure(
            logger, exc, operation="list personal blacklist",
            user_message="获取黑名单失败，请稍后重试",
        )


@router.post("/personal/save")
async def save_personal_blacklist(
    req: PersonalBlacklistSaveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """新增或更新个人黑名单。"""
    try:
        tenant_id = int(current_user.get("tenant_id") or 0)
        if tenant_id <= 0:
            return ResultObject.failed("缺少租户上下文", 400)
        if req.account_id != 0 and not await _assert_account_visible(db, tenant_id, req.account_id):
            return ResultObject.failed("账号不存在或无权操作", 404)

        buyer_user_id = _normalize_buyer_id(req.buyer_user_id)
        if not buyer_user_id:
            return ResultObject.failed("买家ID不能为空", 400)
        goods_id = (req.goods_id or "").strip()
        buyer_nickname = (req.buyer_nickname or "").strip()
        reason = (req.reason or "").strip()

        if req.id:
            updates = [
                "buyer_user_id = :buyer_user_id",
                "buyer_nickname = :buyer_nickname",
                "goods_id = :goods_id",
                "reason = :reason",
                "updated_time = NOW()",
            ]
            params: dict[str, Any] = {
                "id": req.id,
                "tenant_id": tenant_id,
                "buyer_user_id": buyer_user_id,
                "buyer_nickname": buyer_nickname,
                "goods_id": goods_id,
                "reason": reason,
            }
            if req.enabled is not None:
                updates.append("enabled = :enabled")
                params["enabled"] = 1 if req.enabled else 0
            result = await db.execute(
                text(f"""
                    UPDATE personal_blacklist
                    SET {', '.join(updates)}
                    WHERE id = :id AND tenant_id = :tenant_id AND deleted = 0
                """),
                params,
            )
            if result.rowcount == 0:
                return ResultObject.failed("黑名单记录不存在或无权修改", 404)
            await db.commit()
            return ResultObject.success({"id": req.id, "updated": True}, message="黑名单已更新")

        result = await db.execute(
            text("""
                INSERT INTO personal_blacklist(
                    tenant_id, account_id, buyer_user_id, buyer_nickname,
                    goods_id, reason, enabled, deleted, created_time, updated_time
                ) VALUES(
                    :tenant_id, :account_id, :buyer_user_id, :buyer_nickname,
                    :goods_id, :reason, :enabled, 0, NOW(), NOW()
                )
            """),
            {
                "tenant_id": tenant_id,
                "account_id": req.account_id,
                "buyer_user_id": buyer_user_id,
                "buyer_nickname": buyer_nickname,
                "goods_id": goods_id,
                "reason": reason,
                "enabled": 1 if req.enabled is not False else 0,
            },
        )
        await db.commit()
        return ResultObject.success({"id": result.lastrowid}, message="已加入黑名单")
    except Exception as exc:
        await db.rollback()
        if "Duplicate entry" in str(exc):
            return ResultObject.failed("该账号下已存在相同的买家与商品黑名单记录", 400)
        return safe_route_failure(
            logger, exc, operation="save personal blacklist",
            user_message="保存黑名单失败，请稍后重试",
        )


@router.post("/personal/delete")
async def delete_personal_blacklist(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """软删除个人黑名单记录。"""
    try:
        tenant_id = int(current_user.get("tenant_id") or 0)
        if tenant_id <= 0:
            return ResultObject.failed("缺少租户上下文", 400)
        result = await db.execute(
            text("""
                UPDATE personal_blacklist
                SET deleted = 1, updated_time = NOW()
                WHERE id = :id AND tenant_id = :tenant_id AND deleted = 0
            """),
            {"id": id, "tenant_id": tenant_id},
        )
        if result.rowcount == 0:
            return ResultObject.failed("黑名单记录不存在或无权删除", 404)
        await db.commit()
        return ResultObject.success({"id": id, "deleted": True}, message="已移出黑名单")
    except Exception as exc:
        await db.rollback()
        return safe_route_failure(
            logger, exc, operation="delete personal blacklist",
            user_message="删除黑名单失败，请稍后重试",
        )


@router.post("/personal/toggle")
async def toggle_personal_blacklist(
    req: PersonalBlacklistToggleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """启用/禁用个人黑名单记录。"""
    try:
        tenant_id = int(current_user.get("tenant_id") or 0)
        if tenant_id <= 0:
            return ResultObject.failed("缺少租户上下文", 400)
        result = await db.execute(
            text("""
                UPDATE personal_blacklist
                SET enabled = :enabled, updated_time = NOW()
                WHERE id = :id AND tenant_id = :tenant_id AND deleted = 0
            """),
            {"id": req.id, "tenant_id": tenant_id, "enabled": 1 if req.enabled else 0},
        )
        if result.rowcount == 0:
            return ResultObject.failed("黑名单记录不存在或无权操作", 404)
        await db.commit()
        return ResultObject.success(
            {"id": req.id, "enabled": req.enabled},
            message="已启用拦截" if req.enabled else "已停用拦截",
        )
    except Exception as exc:
        await db.rollback()
        return safe_route_failure(
            logger, exc, operation="toggle personal blacklist",
            user_message="切换黑名单状态失败，请稍后重试",
        )
