"""发货拦截规则路由（禁止发货规则引擎）"""
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

router = APIRouter(prefix="/deliveryBlockRule", tags=["deliveryBlockRule"])

ALLOWED_RULE_CODES = {
    "buyer_has_order": "买家已有其他订单",
    "buyer_unconfirmed": "买家存在未确认收货订单",
}


class DeliveryBlockRuleSaveRequest(CamelModel):
    account_id: int = Field(0, description="闲鱼账号ID，0表示全部账号")
    rule_code: str = Field(..., min_length=1, max_length=50)
    rule_name: str = ""
    enabled: bool = False
    priority: Optional[int] = None
    config: Optional[dict] = None


class DeliveryBlockRuleToggleRequest(CamelModel):
    id: int
    enabled: bool


def _rule_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "accountId": row.get("account_id"),
        "accountName": row.get("account_name") or ("全部账号" if not row.get("account_id") else ""),
        "ruleCode": row.get("rule_code") or "",
        "ruleName": row.get("rule_name") or "",
        "enabled": bool(row.get("enabled")),
        "priority": row.get("priority") or 0,
        "config": row.get("config_json"),
        "createdAt": str(row.get("created_time")) if row.get("created_time") else None,
        "updatedAt": str(row.get("updated_time")) if row.get("updated_time") else None,
    }


@router.get("/list")
async def list_delivery_block_rules(
    accountId: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """查询发货拦截规则，支持按账号过滤。"""
    try:
        tenant_id = int(current_user.get("tenant_id") or 0)
        if tenant_id <= 0:
            return ResultObject.failed("缺少租户上下文", 400)
        where = ["r.tenant_id = :tenant_id", "r.deleted = 0"]
        params: dict[str, Any] = {"tenant_id": tenant_id}
        if accountId is not None:
            where.append("(r.account_id = 0 OR r.account_id = :account_id)")
            params["account_id"] = accountId
        rows = (await db.execute(text(f"""
            SELECT r.*, a.nickname AS account_name
            FROM delivery_block_rule r
            LEFT JOIN xianyu_account a ON a.id = r.account_id AND a.tenant_id = r.tenant_id
            WHERE {' AND '.join(where)}
            ORDER BY r.account_id ASC, r.priority ASC, r.id ASC
        """), params)).mappings().all()
        data = [_rule_to_dict(dict(r)) for r in rows]
        return ResultObject.success({"records": data, "total": len(data)})
    except Exception as exc:
        return safe_route_failure(
            logger, exc, operation="list delivery block rules",
            user_message="获取发货拦截规则失败，请稍后重试",
        )


@router.post("/save")
async def save_delivery_block_rule(
    req: DeliveryBlockRuleSaveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """新增/更新发货拦截规则（按 tenant+account+rule_code upsert）。"""
    try:
        tenant_id = int(current_user.get("tenant_id") or 0)
        if tenant_id <= 0:
            return ResultObject.failed("缺少租户上下文", 400)
        rule_code = (req.rule_code or "").strip()
        if rule_code not in ALLOWED_RULE_CODES:
            return ResultObject.failed(f"不支持的规则编码: {rule_code}", 400)
        rule_name = (req.rule_name or "").strip() or ALLOWED_RULE_CODES[rule_code]
        config_json = None
        if req.config is not None:
            import json as _json
            try:
                config_json = _json.dumps(req.config, ensure_ascii=False)
            except (TypeError, ValueError):
                config_json = None

        existing = (await db.execute(
            text("""
                SELECT id FROM delivery_block_rule
                WHERE tenant_id = :tenant_id AND account_id = :account_id AND rule_code = :rule_code AND deleted = 0
                LIMIT 1
            """),
            {
                "tenant_id": tenant_id,
                "account_id": req.account_id,
                "rule_code": rule_code,
            },
        )).mappings().first()

        if existing:
            await db.execute(
                text("""
                    UPDATE delivery_block_rule
                    SET rule_name = :rule_name, enabled = :enabled,
                        config_json = COALESCE(:config_json, config_json),
                        priority = :priority, updated_time = NOW()
                    WHERE id = :id AND tenant_id = :tenant_id
                """),
                {
                    "id": existing["id"],
                    "tenant_id": tenant_id,
                    "rule_name": rule_name,
                    "enabled": 1 if req.enabled else 0,
                    "config_json": config_json,
                    "priority": req.priority if req.priority is not None else 0,
                },
            )
            rule_id = existing["id"]
        else:
            result = await db.execute(
                text("""
                    INSERT INTO delivery_block_rule(
                        tenant_id, account_id, rule_code, rule_name, config_json,
                        enabled, priority, deleted, created_time, updated_time
                    ) VALUES(
                        :tenant_id, :account_id, :rule_code, :rule_name, :config_json,
                        :enabled, :priority, 0, NOW(), NOW()
                    )
                """),
                {
                    "tenant_id": tenant_id,
                    "account_id": req.account_id,
                    "rule_code": rule_code,
                    "rule_name": rule_name,
                    "config_json": config_json,
                    "enabled": 1 if req.enabled else 0,
                    "priority": req.priority if req.priority is not None else 0,
                },
            )
            rule_id = result.lastrowid
        await db.commit()
        return ResultObject.success({"id": rule_id, "enabled": req.enabled}, message="发货拦截规则已保存")
    except Exception as exc:
        await db.rollback()
        return safe_route_failure(
            logger, exc, operation="save delivery block rule",
            user_message="保存发货拦截规则失败，请稍后重试",
        )


@router.post("/toggle")
async def toggle_delivery_block_rule(
    req: DeliveryBlockRuleToggleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """启用/禁用发货拦截规则。"""
    try:
        tenant_id = int(current_user.get("tenant_id") or 0)
        if tenant_id <= 0:
            return ResultObject.failed("缺少租户上下文", 400)
        result = await db.execute(
            text("""
                UPDATE delivery_block_rule
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
            message="已启用拦截" if req.enabled else "已停用拦截",
        )
    except Exception as exc:
        await db.rollback()
        return safe_route_failure(
            logger, exc, operation="toggle delivery block rule",
            user_message="切换发货拦截规则失败，请稍后重试",
        )


@router.post("/delete")
async def delete_delivery_block_rule(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """软删除发货拦截规则。"""
    try:
        tenant_id = int(current_user.get("tenant_id") or 0)
        if tenant_id <= 0:
            return ResultObject.failed("缺少租户上下文", 400)
        result = await db.execute(
            text("""
                UPDATE delivery_block_rule
                SET deleted = 1, updated_time = NOW()
                WHERE id = :id AND tenant_id = :tenant_id AND deleted = 0
            """),
            {"id": id, "tenant_id": tenant_id},
        )
        if result.rowcount == 0:
            return ResultObject.failed("规则不存在或无权删除", 404)
        await db.commit()
        return ResultObject.success({"id": id, "deleted": True}, message="规则已删除")
    except Exception as exc:
        await db.rollback()
        return safe_route_failure(
            logger, exc, operation="delete delivery block rule",
            user_message="删除发货拦截规则失败，请稍后重试",
        )
