"""消息过滤规则路由

功能：
- 按账号配置关键词过滤规则
- filter_type: skip_reply 命中后跳过自动回复；skip_notify 命中后跳过消息通知
- 支持单条新增/更新、批量新增、软删除、批量删除、启停切换
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.database import get_db
from ....core.http_failures import safe_route_failure
from ....core.response import ResultObject
from ....core.camel import CamelModel
from ..deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/messageFilters", tags=["messageFilter"])

VALID_FILTER_TYPES = {"skip_reply", "skip_notify"}


class MessageFilterSaveRequest(CamelModel):
    id: Optional[int] = None
    account_id: int = Field(..., description="闲鱼账号ID")
    keyword: str = Field(..., min_length=1, max_length=200)
    filter_types: list[str] = Field(default_factory=list, description="支持多选: skip_reply / skip_notify")
    enabled: Optional[bool] = None


class MessageFilterBatchRequest(BaseModel):
    ids: list[int] = Field(default_factory=list)


class MessageFilterToggleRequest(CamelModel):
    id: int
    enabled: bool


def _normalize_filter_types(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized


async def _assert_account_visible(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
) -> bool:
    """校验账号属于当前租户且未删除。"""
    row = (await db.execute(
        text("""
            SELECT id FROM xianyu_account
            WHERE id = :account_id AND tenant_id = :tenant_id AND deleted = 0
            LIMIT 1
        """),
        {"account_id": account_id, "tenant_id": tenant_id},
    )).mappings().first()
    return row is not None


def _rule_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "accountId": row.get("account_id"),
        "accountName": row.get("account_name") or "",
        "keyword": row.get("keyword") or "",
        "filterType": row.get("filter_type") or "",
        "enabled": bool(row.get("enabled")),
        "createdAt": str(row.get("created_time")) if row.get("created_time") else None,
        "updatedAt": str(row.get("updated_time")) if row.get("updated_time") else None,
    }


@router.get("/list")
async def list_message_filters(
    request: Request,
    accountId: Optional[int] = None,
    filterType: Optional[str] = None,
    keyword: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """查询消息过滤规则，支持按账号/过滤类型/关键词筛选。"""
    try:
        tenant_id = int(current_user.get("tenant_id") or 0)
        if tenant_id <= 0:
            return ResultObject.failed("缺少租户上下文", 400)

        where = ["f.tenant_id = :tenant_id", "f.deleted = 0"]
        params: dict[str, Any] = {"tenant_id": tenant_id}

        if accountId is not None:
            where.append("f.account_id = :account_id")
            params["account_id"] = accountId
        if filterType:
            where.append("f.filter_type = :filter_type")
            params["filter_type"] = filterType.strip()
        if keyword and keyword.strip():
            where.append("f.keyword LIKE :keyword")
            params["keyword"] = f"%{keyword.strip()}%"

        sql = f"""
            SELECT f.id, f.account_id, f.keyword, f.filter_type, f.enabled,
                   f.created_time, f.updated_time, a.nickname AS account_name
            FROM message_filter f
            LEFT JOIN xianyu_account a ON a.id = f.account_id AND a.tenant_id = f.tenant_id
            WHERE {' AND '.join(where)}
            ORDER BY f.created_time DESC, f.id DESC
        """
        rows = (await db.execute(text(sql), params)).mappings().all()
        data = [_rule_to_dict(dict(r)) for r in rows]
        return ResultObject.success({"records": data, "total": len(data)})
    except Exception as exc:
        return safe_route_failure(
            logger, exc, operation="list message filters",
            user_message="获取消息过滤规则失败，请稍后重试",
        )


@router.post("/save")
async def save_message_filter(
    req: MessageFilterSaveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """新增或更新消息过滤规则。

    - 新增：keyword + filter_types 会为每个过滤类型生成一条记录。
    - 更新：仅当 id 存在时更新单条记录的 keyword/enabled/filter_type。
    """
    try:
        tenant_id = int(current_user.get("tenant_id") or 0)
        if tenant_id <= 0:
            return ResultObject.failed("缺少租户上下文", 400)

        keyword_text = req.keyword.strip()
        if not keyword_text:
            return ResultObject.failed("关键词不能为空", 400)
        if not await _assert_account_visible(db, tenant_id, req.account_id):
            return ResultObject.failed("账号不存在或无权操作", 404)

        if req.id:
            # 更新单条记录
            updates = ["updated_time = NOW()"]
            params: dict[str, Any] = {
                "id": req.id,
                "tenant_id": tenant_id,
            }
            updates.append("keyword = :keyword")
            params["keyword"] = keyword_text
            if req.enabled is not None:
                updates.append("enabled = :enabled")
                params["enabled"] = 1 if req.enabled else 0
            if req.filter_types:
                normalized = _normalize_filter_types(req.filter_types)
                if normalized:
                    updates.append("filter_type = :filter_type")
                    params["filter_type"] = normalized[0]

            result = await db.execute(
                text(f"""
                    UPDATE message_filter
                    SET {', '.join(updates)}
                    WHERE id = :id AND tenant_id = :tenant_id AND deleted = 0
                """),
                params,
            )
            if result.rowcount == 0:
                return ResultObject.failed("规则不存在或无权修改", 404)
            await db.commit()
            return ResultObject.success({"id": req.id, "updated": True})

        # 新增：为每个过滤类型生成记录
        filter_types = _normalize_filter_types(req.filter_types)
        if not filter_types:
            return ResultObject.failed("请选择至少一种过滤类型", 400)
        invalid = [ft for ft in filter_types if ft not in VALID_FILTER_TYPES]
        if invalid:
            return ResultObject.failed(f"无效的过滤类型: {', '.join(invalid)}", 400)

        created_ids: list[int] = []
        failed_items: list[dict[str, Any]] = []
        for filter_type in filter_types:
            exists = (await db.execute(
                text("""
                    SELECT id FROM message_filter
                    WHERE tenant_id = :tenant_id AND account_id = :account_id
                      AND keyword = :keyword AND filter_type = :filter_type AND deleted = 0
                    LIMIT 1
                """),
                {
                    "tenant_id": tenant_id,
                    "account_id": req.account_id,
                    "keyword": keyword_text,
                    "filter_type": filter_type,
                },
            )).mappings().first()
            if exists:
                failed_items.append({"accountId": req.account_id, "filterType": filter_type, "message": "已存在"})
                continue
            result = await db.execute(
                text("""
                    INSERT INTO message_filter(tenant_id, account_id, keyword, filter_type, enabled, deleted, created_time, updated_time)
                    VALUES(:tenant_id, :account_id, :keyword, :filter_type, 1, 0, NOW(), NOW())
                """),
                {
                    "tenant_id": tenant_id,
                    "account_id": req.account_id,
                    "keyword": keyword_text,
                    "filter_type": filter_type,
                },
            )
            created_ids.append(result.lastrowid)
        await db.commit()

        message = f"成功创建 {len(created_ids)} 条规则"
        if failed_items:
            message += f"，{len(failed_items)} 条已存在"
        return ResultObject.success({
            "createdIds": created_ids,
            "createdCount": len(created_ids),
            "failedItems": failed_items,
        }, message=message)
    except Exception as exc:
        await db.rollback()
        return safe_route_failure(
            logger, exc, operation="save message filter",
            user_message="保存消息过滤规则失败，请稍后重试",
        )


@router.post("/delete")
async def delete_message_filter(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """软删除单条消息过滤规则。"""
    try:
        tenant_id = int(current_user.get("tenant_id") or 0)
        if tenant_id <= 0:
            return ResultObject.failed("缺少租户上下文", 400)
        result = await db.execute(
            text("""
                UPDATE message_filter
                SET deleted = 1, updated_time = NOW()
                WHERE id = :id AND tenant_id = :tenant_id AND deleted = 0
            """),
            {"id": id, "tenant_id": tenant_id},
        )
        if result.rowcount == 0:
            return ResultObject.failed("规则不存在或无权删除", 404)
        await db.commit()
        return ResultObject.success({"id": id, "deleted": True}, message="删除成功")
    except Exception as exc:
        await db.rollback()
        return safe_route_failure(
            logger, exc, operation="delete message filter",
            user_message="删除消息过滤规则失败，请稍后重试",
        )


@router.post("/batchDelete")
async def batch_delete_message_filters(
    req: MessageFilterBatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """批量软删除消息过滤规则。"""
    try:
        tenant_id = int(current_user.get("tenant_id") or 0)
        if tenant_id <= 0:
            return ResultObject.failed("缺少租户上下文", 400)
        ids = [i for i in dict.fromkeys(req.ids) if i > 0]
        if not ids:
            return ResultObject.failed("请选择要删除的规则", 400)

        result = await db.execute(
            text("""
                UPDATE message_filter
                SET deleted = 1, updated_time = NOW()
                WHERE tenant_id = :tenant_id AND deleted = 0 AND id IN :ids
            """).bindparams(bindparam("ids", expanding=True)),
            {"tenant_id": tenant_id, "ids": ids},
        )
        await db.commit()
        return ResultObject.success(
            {"deletedCount": result.rowcount or 0},
            message=f"成功删除 {result.rowcount or 0} 条规则",
        )
    except Exception as exc:
        await db.rollback()
        return safe_route_failure(
            logger, exc, operation="batch delete message filters",
            user_message="批量删除消息过滤规则失败，请稍后重试",
        )


@router.post("/toggle")
async def toggle_message_filter(
    req: MessageFilterToggleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """启用/禁用消息过滤规则。"""
    try:
        tenant_id = int(current_user.get("tenant_id") or 0)
        if tenant_id <= 0:
            return ResultObject.failed("缺少租户上下文", 400)
        result = await db.execute(
            text("""
                UPDATE message_filter
                SET enabled = :enabled, updated_time = NOW()
                WHERE id = :id AND tenant_id = :tenant_id AND deleted = 0
            """),
            {"id": req.id, "tenant_id": tenant_id, "enabled": 1 if req.enabled else 0},
        )
        if result.rowcount == 0:
            return ResultObject.failed("规则不存在或无权操作", 404)
        await db.commit()
        return ResultObject.success(
            {"id": req.id, "enabled": req.enabled},
            message="已启用" if req.enabled else "已禁用",
        )
    except Exception as exc:
        await db.rollback()
        return safe_route_failure(
            logger, exc, operation="toggle message filter",
            user_message="切换消息过滤规则状态失败，请稍后重试",
        )
