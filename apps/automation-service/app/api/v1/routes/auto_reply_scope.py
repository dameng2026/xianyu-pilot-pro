"""
Auto-reply scope management.

Precedence:
- Product scope (`xianyu_goods.auto_reply_enabled`)
- Account scope (`user_business_setting.auto-reply-account-scopes`)
- Global switch (`user_business_setting.ai-customer-service.enabled`)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy import or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.database import get_db
from ....core.http_failures import safe_route_failure
from ....core.response import ResultObject
from ....models.entities import XianyuGoods
from .internal import verify_internal_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auto-reply-scope", tags=["autoReplyScope"])

ACCOUNT_SCOPES_KEY = "auto-reply-account-scopes"


def _get_tenant_id(request: Request) -> int:
    raw = request.query_params.get("tenantId") or request.headers.get("X-Internal-Tenant-Id", "0")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def _normalize_scope_text(value: Any) -> str:
    return str(value or "").strip()


@router.get("/products")
async def list_products_with_scope(
    request: Request,
    accountId: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    try:
        tenant_id = _get_tenant_id(request)
        if tenant_id <= 0:
            return ResultObject.failed("无效的租户ID")

        goods_list = await _load_goods_rows(db, tenant_id, accountId)
        account_scopes = await _load_account_scopes(db, tenant_id)
        global_enabled = await _load_global_enabled(db, tenant_id)

        items = []
        for goods in goods_list:
            effective = _compute_effective(
                goods.get("auto_reply_enabled"),
                goods.get("account_id"),
                account_scopes,
                global_enabled,
            )
            items.append({
                "id": goods.get("id"),
                "title": goods.get("title") or "",
                "accountId": goods.get("account_id"),
                "goodsId": goods.get("external_goods_id") or goods.get("goods_id"),
                "auto_reply_enabled": goods.get("auto_reply_enabled"),
                "effective_enabled": effective,
                "account_enabled": account_scopes.get("accounts", {}).get(str(goods.get("account_id"))) if account_scopes else None,
                "global_enabled": global_enabled,
            })
        return ResultObject.success({"items": items, "total": len(items)})
    except Exception as exc:
        return safe_route_failure(logger, exc, operation="list auto reply scope products", user_message="查询自动回复范围失败，请稍后重试")


@router.post("/product")
async def update_product_scope(
    request: Request,
    req: Dict[str, Any] | None = None,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    try:
        payload = req or {}
        tenant_id = _get_tenant_id(request)
        if tenant_id <= 0:
            return ResultObject.failed("无效的租户ID")

        enabled = payload.get("enabled")
        if enabled is None:
            return ResultObject.failed("缺少 enabled 参数")

        value = 1 if bool(enabled) else 0
        item_id = payload.get("itemId")
        if item_id is not None:
            stmt = update(XianyuGoods).where(
                XianyuGoods.id == int(item_id),
                XianyuGoods.tenant_id == tenant_id,
            ).values(auto_reply_enabled=value)
            result = await db.execute(stmt)
            await db.commit()
            if result.rowcount == 0:
                return ResultObject.failed("商品不存在或无权操作")
            logger.info("update auto_reply_enabled by itemId itemId=%s enabled=%s", item_id, value)
            return ResultObject.success({
                "ok": True,
                "itemId": int(item_id),
                "enabled": bool(enabled),
                "created": False,
            })

        goods_id = _normalize_scope_text(payload.get("goodsId") or payload.get("xyGoodsId"))
        account_id = payload.get("accountId")
        if not goods_id or account_id is None:
            return ResultObject.failed("缺少 itemId 或 goodsId/accountId 参数")

        goods, created = await _upsert_goods_scope_row(
            db=db,
            tenant_id=tenant_id,
            account_id=int(account_id),
            goods_id=goods_id,
            enabled=bool(enabled),
            title=payload.get("title") or payload.get("goodsTitle"),
            image_url=payload.get("imageUrl") or payload.get("coverPic"),
        )
        logger.info(
            "update auto_reply_enabled by goods scope goodsId=%s accountId=%s enabled=%s created=%s",
            goods_id,
            account_id,
            value,
            created,
        )
        return ResultObject.success({
            "ok": True,
            "itemId": int(goods.id),
            "goodsId": goods.external_goods_id or goods.goods_id,
            "accountId": int(goods.account_id or account_id),
            "enabled": bool(enabled),
            "created": created,
        })
    except Exception as exc:
        return safe_route_failure(logger, exc, operation="update product auto reply scope", user_message="更新自动回复范围失败，请稍后重试")


@router.post("/account")
async def update_account_scope(
    request: Request,
    req: Dict[str, Any] | None = None,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    try:
        payload = req or {}
        account_id = payload.get("accountId")
        enabled = payload.get("enabled")
        if account_id is None or enabled is None:
            return ResultObject.failed("缺少 accountId 或 enabled 参数")

        tenant_id = _get_tenant_id(request)
        if tenant_id <= 0:
            return ResultObject.failed("无效的租户ID")

        scopes = await _load_account_scopes(db, tenant_id)
        accounts = scopes.setdefault("accounts", {})
        accounts[str(int(account_id))] = bool(enabled)
        await _save_account_scopes(db, tenant_id, scopes)
        logger.info("update account auto reply scope accountId=%s enabled=%s", account_id, enabled)
        return ResultObject.success({"ok": True, "accountId": int(account_id), "enabled": bool(enabled)})
    except Exception as exc:
        return safe_route_failure(logger, exc, operation="update account auto reply scope", user_message="更新自动回复范围失败，请稍后重试")


@router.post("/batch")
async def batch_update_scope(
    request: Request,
    req: Dict[str, Any] | None = None,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    try:
        payload = req or {}
        tenant_id = _get_tenant_id(request)
        if tenant_id <= 0:
            return ResultObject.failed("无效的租户ID")

        enabled = payload.get("enabled")
        if enabled is None:
            return ResultObject.failed("缺少 enabled 参数")
        value = bool(enabled)

        item_ids = payload.get("itemIds")
        account_ids = payload.get("accountIds")

        if item_ids:
            int_ids = [int(item_id) for item_id in item_ids if item_id is not None]
            if int_ids:
                stmt = update(XianyuGoods).where(
                    XianyuGoods.id.in_(int_ids),
                    XianyuGoods.tenant_id == tenant_id,
                ).values(auto_reply_enabled=1 if value else 0)
                result = await db.execute(stmt)
                await db.commit()
                logger.info("batch update product auto reply affected=%s enabled=%s", result.rowcount, value)
                return ResultObject.success({"ok": True, "affected": result.rowcount, "type": "product"})

        if account_ids:
            int_ids = [int(account_id) for account_id in account_ids if account_id is not None]
            if int_ids:
                scopes = await _load_account_scopes(db, tenant_id)
                accounts = scopes.setdefault("accounts", {})
                for account_id in int_ids:
                    accounts[str(account_id)] = value
                await _save_account_scopes(db, tenant_id, scopes)
                logger.info("batch update account auto reply count=%s enabled=%s", len(int_ids), value)
                return ResultObject.success({"ok": True, "affected": len(int_ids), "type": "account"})

        return ResultObject.failed("需要提供 itemIds 或 accountIds 参数")
    except Exception as exc:
        return safe_route_failure(logger, exc, operation="batch update auto reply scope", user_message="批量更新自动回复范围失败，请稍后重试")


@router.get("/status")
async def get_scope_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    try:
        tenant_id = _get_tenant_id(request)
        if tenant_id <= 0:
            return ResultObject.failed("无效的租户ID")

        account_scopes = await _load_account_scopes(db, tenant_id)
        global_enabled = await _load_global_enabled(db, tenant_id)
        return ResultObject.success({
            "global_enabled": global_enabled,
            "account_scopes": account_scopes.get("accounts", {}),
        })
    except Exception as exc:
        return safe_route_failure(logger, exc, operation="get auto reply scope status", user_message="查询自动回复范围失败，请稍后重试")


async def _load_account_scopes(db: AsyncSession, tenant_id: int) -> Dict[str, Any]:
    stmt = text(
        "SELECT config_json FROM user_business_setting "
        "WHERE tenant_id=:tid AND setting_key=:key AND deleted=0 LIMIT 1"
    )
    result = await db.execute(stmt, {"tid": tenant_id, "key": ACCOUNT_SCOPES_KEY})
    row = result.first()
    if not row:
        return {"accounts": {}}
    try:
        config = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        return config if isinstance(config, dict) else {"accounts": {}}
    except Exception:
        return {"accounts": {}}


async def _save_account_scopes(db: AsyncSession, tenant_id: int, scopes: Dict[str, Any]):
    config_json = json.dumps(scopes, ensure_ascii=False)
    stmt = text("""
        INSERT INTO user_business_setting(tenant_id, user_id, setting_key, config_json, created_time, updated_time, deleted)
        VALUES(:tid, 0, :key, :json, NOW(), NOW(), 0)
        ON DUPLICATE KEY UPDATE config_json=VALUES(config_json), updated_time=NOW()
    """)
    await db.execute(stmt, {"tid": tenant_id, "key": ACCOUNT_SCOPES_KEY, "json": config_json})
    await db.commit()


async def _load_global_enabled(db: AsyncSession, tenant_id: int) -> bool:
    stmt = text(
        "SELECT config_json FROM user_business_setting "
        "WHERE tenant_id=:tid AND setting_key='ai-customer-service' AND deleted=0 LIMIT 1"
    )
    result = await db.execute(stmt, {"tid": tenant_id})
    row = result.first()
    if not row:
        return False
    try:
        config = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        return bool(config.get("enabled", False)) if isinstance(config, dict) else False
    except Exception:
        return False


async def _load_goods_rows(db: AsyncSession, tenant_id: int, account_id: Optional[int]) -> list[Dict[str, Any]]:
    sql = """
        SELECT id, account_id, goods_id, external_goods_id, title, auto_reply_enabled, created_time
        FROM xianyu_goods
        WHERE tenant_id = :tenant_id
          AND deleted = 0
    """
    params: Dict[str, Any] = {"tenant_id": tenant_id}
    if account_id is not None:
        sql += " AND account_id = :account_id"
        params["account_id"] = account_id
    sql += " ORDER BY created_time DESC"
    result = await db.execute(text(sql), params)
    return [dict(row._mapping) for row in result.fetchall()]


async def _find_goods_scope_row(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    goods_id: str,
) -> Optional[XianyuGoods]:
    normalized_goods_id = _normalize_scope_text(goods_id)
    if not normalized_goods_id:
        return None
    result = await db.execute(
        select(XianyuGoods)
        .where(
            XianyuGoods.tenant_id == tenant_id,
            XianyuGoods.account_id == account_id,
            XianyuGoods.deleted == 0,
            or_(
                XianyuGoods.external_goods_id == normalized_goods_id,
                XianyuGoods.goods_id == normalized_goods_id,
            ),
        )
        .order_by(XianyuGoods.updated_time.desc(), XianyuGoods.id.desc())
        .limit(1)
    )
    return result.scalars().first()


async def _upsert_goods_scope_row(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    goods_id: str,
    enabled: bool,
    title: Any = None,
    image_url: Any = None,
) -> tuple[XianyuGoods, bool]:
    normalized_goods_id = _normalize_scope_text(goods_id)
    if not normalized_goods_id:
        raise ValueError("goodsId 不能为空")

    normalized_title = _normalize_scope_text(title)
    normalized_image_url = _normalize_scope_text(image_url)
    goods = await _find_goods_scope_row(db, tenant_id, account_id, normalized_goods_id)
    created = goods is None

    if created:
        goods = XianyuGoods(
            tenant_id=tenant_id,
            account_id=account_id,
            goods_id=normalized_goods_id,
            external_goods_id=normalized_goods_id,
            title=normalized_title or f"会话商品 {normalized_goods_id}",
            cover_pic=normalized_image_url or None,
            image_url=normalized_image_url or None,
            auto_reply_enabled=1 if enabled else 0,
            status=1,
            deleted=0,
        )
        db.add(goods)
    else:
        goods.auto_reply_enabled = 1 if enabled else 0
        if not _normalize_scope_text(goods.goods_id):
            goods.goods_id = normalized_goods_id
        if not _normalize_scope_text(goods.external_goods_id):
            goods.external_goods_id = normalized_goods_id
        if normalized_title and not _normalize_scope_text(goods.title):
            goods.title = normalized_title
        if normalized_image_url:
            if not _normalize_scope_text(goods.cover_pic):
                goods.cover_pic = normalized_image_url
            if not _normalize_scope_text(goods.image_url):
                goods.image_url = normalized_image_url

    await db.commit()
    await db.refresh(goods)
    return goods, created


def _compute_effective(
    product_enabled: Optional[int],
    account_id: Optional[int],
    account_scopes: Dict[str, Any],
    global_enabled: bool,
) -> bool:
    if not global_enabled:
        return False
    if product_enabled is not None:
        return product_enabled == 1
    accounts = account_scopes.get("accounts", {}) if account_scopes else {}
    if account_id is not None and str(account_id) in accounts:
        return bool(accounts[str(account_id)])
    return True
