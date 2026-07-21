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


# ============================================================
# 会话级自动回复运行时状态（人工干预自动暂停/恢复）
# ============================================================
#
# 业务规则：
#   1. 人工发送消息后，会话级 auto_reply_paused=1（人工干预暂停）
#   2. 买家发送"开启自动回复"指令 → 自动恢复（仅当未被用户手动关闭）
#   3. 距上次人工回复 > 1 分钟，买家发新消息时自动恢复
#   4. 用户在网站手动点击按钮关闭时，auto_reply_manual_disabled=1，
#      禁止自动恢复，仅允许用户手动开启
#
# 与账号级/商品级开关的关系：
#   - 会话级状态是"运行时挂起"，不影响账号级/商品级配置
#   - 会话级 auto_reply_paused=1 时，即使账号级/商品级开关为开启，也不自动回复
#   - 用户手动开启会话级开关时，仅清除会话级暂停状态，不修改账号级/商品级配置


async def _resolve_conversation_by_sid(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    sid: str,
    peer_user_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """通过 sId 反查消息表找到对端身份，再匹配 xianyu_conversation。
    如果传入 peer_user_id，直接使用该值作为对端身份候选。
    """
    if not sid and not peer_user_id:
        return None

    sid_norm = (sid or "").strip()
    if sid_norm.startswith("sid:"):
        sid_norm = sid_norm[4:]
    sid_goofish = f"{sid_norm}@goofish" if sid_norm and not sid_norm.endswith("@goofish") else sid_norm

    peer_id_candidates: list[str] = []
    if peer_user_id:
        v = str(peer_user_id).strip()
        if v:
            peer_id_candidates.append(v)
            if v.endswith("@goofish") and v[:-8] not in peer_id_candidates:
                peer_id_candidates.append(v[:-8])
            elif not v.endswith("@goofish") and f"{v}@goofish" not in peer_id_candidates:
                peer_id_candidates.append(f"{v}@goofish")

    if sid_norm:
        sid_peer_row = (await db.execute(text("""
            SELECT peer_external_uid, sender_user_id, receiver_user_id
            FROM xianyu_chat_message
            WHERE tenant_id = :tenant_id AND account_id = :account_id
              AND deleted = 0
              AND s_id COLLATE utf8mb4_unicode_ci IN (:sid, :sid_goofish)
            ORDER BY id DESC LIMIT 1
        """), {
            "tenant_id": tenant_id,
            "account_id": account_id,
            "sid": sid_norm,
            "sid_goofish": sid_goofish,
        })).mappings().first()
        if sid_peer_row:
            for key in ("peer_external_uid", "sender_user_id", "receiver_user_id"):
                v = str(sid_peer_row.get(key) or "").strip()
                if v and v not in peer_id_candidates:
                    peer_id_candidates.append(v)

    if not peer_id_candidates:
        return None

    conv_row = (await db.execute(text("""
        SELECT id, account_id, external_buyer_id, peer_external_uid, peer_key,
               auto_reply_paused, auto_reply_manual_disabled,
               last_manual_reply_at, last_auto_reply_at
        FROM xianyu_conversation
        WHERE tenant_id = :tenant_id AND account_id = :account_id
          AND deleted = 0
          AND (
              external_buyer_id IN (:peer_ids)
              OR peer_external_uid IN (:peer_ids)
              OR peer_key IN (:peer_ids)
          )
        ORDER BY id DESC LIMIT 1
    """), {
        "tenant_id": tenant_id,
        "account_id": account_id,
        "peer_ids": peer_id_candidates,
    })).mappings().first()
    return dict(conv_row) if conv_row else None


@router.post("/conversation-toggle")
async def toggle_conversation_auto_reply(
    request: Request,
    req: Dict[str, Any] | None = None,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """会话级自动回复手动开关。
    用户在网站点击按钮开启/关闭时调用，与人工干预触发的自动暂停区分：
    - enabled=true：手动开启（清除暂停 + 清除手动关闭标记）
    - enabled=false：手动关闭（设置暂停 + 设置手动关闭标记，禁止自动恢复）
    """
    try:
        payload = req or {}
        tenant_id = _get_tenant_id(request)
        if tenant_id <= 0:
            return ResultObject.failed("无效的租户ID")
        account_id = payload.get("accountId")
        sid = payload.get("sid") or payload.get("sId") or payload.get("sessionId")
        peer_user_id = payload.get("peerUserId") or payload.get("peerId")
        enabled = payload.get("enabled")
        if account_id is None or enabled is None or (not sid and not peer_user_id):
            return ResultObject.failed("缺少 accountId、enabled 或 sid/peerUserId 参数")

        conv = await _resolve_conversation_by_sid(
            db, tenant_id, int(account_id), str(sid or ""), peer_user_id
        )
        if not conv:
            return ResultObject.failed("未找到对应会话", code=404)

        conversation_id = int(conv["id"])
        if bool(enabled):
            # 手动开启：清除暂停 + 清除手动关闭标记 + 重置人工回复时间戳
            await db.execute(text("""
                UPDATE xianyu_conversation
                SET auto_reply_paused = 0,
                    auto_reply_manual_disabled = 0,
                    last_manual_reply_at = NULL,
                    updated_time = NOW()
                WHERE id = :conversation_id
            """), {"conversation_id": conversation_id})
            logger.info(
                "conversation auto reply manual resume tenantId=%d accountId=%s convId=%d",
                tenant_id, account_id, conversation_id
            )
        else:
            # 手动关闭：设置暂停 + 设置手动关闭标记（禁止自动恢复）
            await db.execute(text("""
                UPDATE xianyu_conversation
                SET auto_reply_paused = 1,
                    auto_reply_manual_disabled = 1,
                    updated_time = NOW()
                WHERE id = :conversation_id
            """), {"conversation_id": conversation_id})
            logger.info(
                "conversation auto reply manual pause tenantId=%d accountId=%s convId=%d",
                tenant_id, account_id, conversation_id
            )

        await db.commit()

        # 广播会话状态变更事件，让前端实时更新开关按钮文案
        try:
            from ....services.ws_sse import broadcaster
            await broadcaster.broadcast(tenant_id, "conversation_auto_reply_state", {
                "conversationId": conversation_id,
                "accountId": int(account_id),
                "peerId": conv.get("external_buyer_id") or conv.get("peer_external_uid") or peer_user_id,
                "sid": sid or "",
                "autoReplyPaused": 0 if bool(enabled) else 1,
                "autoReplyManualDisabled": 0 if bool(enabled) else 1,
                "reason": "manual_resume" if bool(enabled) else "manual_pause",
            })
        except Exception as sse_exc:
            logger.warning("广播会话状态变更失败 convId=%d: %s", conversation_id, sse_exc)

        return ResultObject.success({
            "ok": True,
            "conversationId": conversation_id,
            "accountId": int(account_id),
            "enabled": bool(enabled),
            "autoReplyPaused": 0 if bool(enabled) else 1,
            "autoReplyManualDisabled": 0 if bool(enabled) else 1,
        })
    except Exception as exc:
        return safe_route_failure(
            logger, exc,
            operation="toggle conversation auto reply",
            user_message="切换会话自动回复状态失败，请稍后重试",
        )


@router.get("/conversation-status")
async def get_conversation_auto_reply_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """查询会话级自动回复状态。
    返回字段：
      - autoReplyPaused：会话级是否暂停（0否 1是）
      - autoReplyManualDisabled：是否被用户手动关闭（0否 1是）
      - lastManualReplyAt：最后人工回复时间戳（毫秒）
      - lastAutoReplyAt：最后 AI 自动回复时间戳（毫秒）
      - effectiveEnabled：综合账号级/全局开关后的"配置层"是否启用
      - runningEnabled：实际是否在自动回复（配置层启用 且 会话级未暂停）
    """
    try:
        tenant_id = _get_tenant_id(request)
        if tenant_id <= 0:
            return ResultObject.failed("无效的租户ID")
        account_id = request.query_params.get("accountId")
        sid = request.query_params.get("sid") or request.query_params.get("sId") or request.query_params.get("sessionId")
        peer_user_id = request.query_params.get("peerUserId") or request.query_params.get("peerId")
        if not account_id or (not sid and not peer_user_id):
            return ResultObject.failed("缺少 accountId 或 sid/peerUserId 参数")

        conv = await _resolve_conversation_by_sid(
            db, tenant_id, int(account_id), str(sid or ""), peer_user_id
        )
        if not conv:
            # 会话尚未建立时，按"未暂停"返回，让前端按账号级/全局开关展示
            account_scopes = await _load_account_scopes(db, tenant_id)
            global_enabled = await _load_global_enabled(db, tenant_id)
            accounts = account_scopes.get("accounts", {}) if account_scopes else {}
            account_enabled = bool(accounts.get(str(account_id))) if str(account_id) in accounts else True
            effective = bool(global_enabled) and account_enabled
            return ResultObject.success({
                "conversationId": None,
                "autoReplyPaused": 0,
                "autoReplyManualDisabled": 0,
                "lastManualReplyAt": None,
                "lastAutoReplyAt": None,
                "effectiveEnabled": effective,
                "runningEnabled": effective,
            })

        conversation_id = int(conv["id"])
        auto_reply_paused = int(conv.get("auto_reply_paused") or 0)
        auto_reply_manual_disabled = int(conv.get("auto_reply_manual_disabled") or 0)
        last_manual_at = conv.get("last_manual_reply_at")
        last_auto_at = conv.get("last_auto_reply_at")

        # 综合账号级/全局开关
        account_scopes = await _load_account_scopes(db, tenant_id)
        global_enabled = await _load_global_enabled(db, tenant_id)
        accounts = account_scopes.get("accounts", {}) if account_scopes else {}
        account_enabled = bool(accounts.get(str(account_id))) if str(account_id) in accounts else True
        effective = bool(global_enabled) and account_enabled
        running = effective and auto_reply_paused == 0

        return ResultObject.success({
            "conversationId": conversation_id,
            "autoReplyPaused": auto_reply_paused,
            "autoReplyManualDisabled": auto_reply_manual_disabled,
            "lastManualReplyAt": int(last_manual_at) if last_manual_at is not None else None,
            "lastAutoReplyAt": int(last_auto_at) if last_auto_at is not None else None,
            "effectiveEnabled": effective,
            "runningEnabled": running,
            "pausedReason": "manual_disable" if auto_reply_manual_disabled == 1
                            else ("manual_intervention" if auto_reply_paused == 1 else None),
        })
    except Exception as exc:
        return safe_route_failure(
            logger, exc,
            operation="get conversation auto reply status",
            user_message="查询会话自动回复状态失败，请稍后重试",
        )
