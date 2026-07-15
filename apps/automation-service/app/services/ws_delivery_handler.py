"""
事件驱动的自动发货处理器。

通过 WebSocket 实时消息（contentType=26 已付款待发货）触发自动发货：
1. 检测传入消息是否为付款通知
2. 从消息中提取订单ID、商品ID、会话ID等信息
3. 匹配发货规则（delivery_rule）
4. 执行发货（文本/卡密/API/自定义）
5. 通过 WebSocket 发送发货内容给买家
6. 可选调用闲鱼API确认发货
"""
import asyncio
import json
import logging
import re
import time
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import async_session
from .ws_client import ws_manager

logger = logging.getLogger(__name__)


# ============================================================
# 发货模式常量（与参考文档对齐）
# ============================================================
MODE_TEXT = "text"       # 文本发货: 发送固定文本
MODE_KAMI = "kami"       # 卡密发货: 从卡密库扣减
MODE_CUSTOM = "custom"   # 自定义发货: 标记已处理，不发送消息
MODE_API = "api"         # API发货: 调用外部API获取内容
DELIVERY_TIMING_AFTER_PAYMENT = "after_payment"


# ============================================================
# 并发去重：按 会话+商品 维度串行化发货，消除 TOCTOU 竞态
# ============================================================
# key = f"{account_id}:{sid}:{xy_goods_id}"，同一会话同一商品的发货任务排队执行。
# 第一个任务完成 INSERT 后，后续任务的 _has_existing_realtime_delivery 检查会命中并跳过。
_delivery_locks: dict[str, asyncio.Lock] = {}
_delivery_locks_guard = asyncio.Lock()


async def _get_delivery_lock(account_id: int, s_id: str, xy_goods_id: str) -> asyncio.Lock:
    """获取按 会话+商品 维度的发货串行锁。"""
    key = f"{account_id}:{s_id}:{xy_goods_id}"
    async with _delivery_locks_guard:
        lock = _delivery_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _delivery_locks[key] = lock
        return lock


# ============================================================
# 订单ID提取
# ============================================================
def extract_order_id_from_url(url: str) -> Optional[str]:
    """从消息的链接中提取订单ID。
    
    支持多种格式:
    - targetUrl: orderId=xxx / tradeId=xxx / id=xxx
    - reminderUrl: 同上
    """
    if not url:
        return None
    query = parse_qs(urlparse(url).query or "")
    for key in ("orderId", "tradeId", "id"):
        values = query.get(key) or []
        for value in values:
            normalized = str(value).strip()
            if normalized:
                return normalized
    return None


def extract_goods_id_from_url(url: str) -> Optional[str]:
    """从URL中提取商品ID (itemId=xxx 或 id=xxx)。"""
    if not url:
        return None
    query = parse_qs(urlparse(url).query or "")
    for key in ("itemId", "id"):
        values = query.get(key) or []
        for value in values:
            normalized = str(value).strip()
            if normalized:
                return normalized
    return None


def extract_peer_user_id_from_url(url: str) -> Optional[str]:
    """从提醒链接中提取聊天对端用户ID。"""
    if not url:
        return None
    query = parse_qs(urlparse(url).query or "")
    for key in ("peerUserId", "buyerUserId", "toId"):
        values = query.get(key) or []
        for value in values:
            normalized = str(value).strip()
            if normalized:
                return normalized
    return None


def extract_buy_quantity_from_msg(msg: dict) -> int:
    """从消息中提取购买数量。"""
    # 尝试从完整消息体中提取
    complete_msg = msg.get("complete_msg") or msg.get("completeMsg") or {}
    if isinstance(complete_msg, str):
        try:
            complete_msg = json.loads(complete_msg)
        except (json.JSONDecodeError, TypeError):
            pass
    if isinstance(complete_msg, dict):
        # 检查消息体中的数量字段
        quantity = complete_msg.get("quantity") or complete_msg.get("buyQuantity") or 0
        if quantity:
            try:
                return int(quantity)
            except (ValueError, TypeError):
                pass
    # 从 reminderContent 中尝试提取（如 "x1" 格式）
    reminder = str(msg.get("reminderContent") or msg.get("reminder_content") or "")
    match = re.search(r'[x×](\d+)', reminder)
    if match:
        try:
            return int(match.group(1))
        except (ValueError, TypeError):
            pass
    return 1


# ============================================================
# 消息类型检测
# ============================================================
def is_payment_message(msg: dict) -> bool:
    """检测消息是否为"已付款待发货"消息。
    
    参考文档:
    - contentType=26 表示已付款待发货
    - reminderContent 包含"等待你发货"或"已付款"
    """
    content_type = msg.get("contentType") or msg.get("content_type") or 0
    try:
        content_type = int(content_type)
    except (ValueError, TypeError):
        return False
    
    reminder = str(msg.get("reminderContent") or msg.get("reminder_content") or "")
    # contentType=26 同时承载“已拍下待付款”和“已付款待发货”提醒。
    # 自动发货必须 fail-closed：出现待付款语义时绝不能仅凭类型触发。
    unpaid_markers = ("待付款", "等待付款", "未付款", "去付款", "付款提醒")
    if any(marker in reminder for marker in unpaid_markers):
        return False

    paid_markers = ("等待你发货", "已付款", "待发货")
    if any(marker in reminder for marker in paid_markers):
        return True

    # 未携带可确认付款语义的 type=26 消息保持不触发，避免提前泄露发货内容。
    return False


def is_bargain_success_message(msg: dict) -> bool:
    """检测消息是否为"小刀成功"消息。"""
    reminder = str(msg.get("reminderContent") or msg.get("reminder_content") or "")
    if "小刀成功" in reminder or "我已成功小刀" in reminder:
        return True
    return False


def is_bargain_waiting_message(msg: dict) -> bool:
    """检测消息是否为"小刀待刀成"消息。"""
    reminder = str(msg.get("reminderContent") or msg.get("reminder_content") or "")
    if "小刀" in reminder and "待刀成" in reminder:
        return True
    return False


# ============================================================
# 自动发货核心逻辑
# ============================================================

async def handle_incoming_message_for_delivery(
    tenant_id: int,
    account_id: int,
    msg: dict,
):
    """处理传入消息，触发自动发货流程。
    
    此函数在消息回调中被调用，在消息已保存到数据库之后执行。
    
    Args:
        tenant_id: 租户ID
        account_id: 闲鱼账号ID
        msg: 解析后的消息字典
    """
    # Step 1: 判断是否为需要触发自动发货的消息
    if not is_payment_message(msg) and not is_bargain_success_message(msg):
        return

    logger.info(
        "检测到待发货消息: accountId=%d contentType=%s sId=%s",
        account_id, msg.get("contentType"), msg.get("sId", "")
    )

    # 检测到新订单（付款消息）时推送飞书机器人通知（失败不影响主流程）
    if is_payment_message(msg):
        try:
            from .notify_dispatcher import notify_new_order
            await notify_new_order(tenant_id, account_id, msg)
        except Exception:
            logger.debug("新订单飞书通知异常，忽略", exc_info=True)

    async with async_session() as db:
        try:
            await _process_delivery(db, tenant_id, account_id, msg)
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(
                "自动发货处理失败: accountId=%d error=%s",
                account_id, e, exc_info=True
            )


async def _process_delivery(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    msg: dict,
):
    """执行自动发货的核心流程。"""
    # === 1. 提取消息中的关键信息 ===
    s_id = str(msg.get("sId") or "")
    sender_user_id = str(msg.get("senderUserId") or "")
    receiver_user_id = str(msg.get("receiverUserId") or "")
    reminder_url = str(msg.get("reminderUrl") or msg.get("reminder_url") or "")
    reminder_content = str(msg.get("reminderContent") or msg.get("reminder_content") or "")
    pnm_id = str(msg.get("pnmId") or "")
    msg_content = str(msg.get("msgContent") or "")
    
    if not s_id:
        logger.warning("自动发货跳过: sId 为空 accountId=%d", account_id)
        return
    
    # === 2. 提取订单ID（部分付款提醒只有 sid，没有真实 orderId） ===
    order_id = extract_order_id_from_url(reminder_url)
    
    # === 3. 提取商品ID ===
    xy_goods_id = str(msg.get("xyGoodsId") or "")
    if not xy_goods_id:
        xy_goods_id = extract_goods_id_from_url(reminder_url) or ""
    if not xy_goods_id:
        logger.warning("自动发货跳过: 无法从消息中提取商品ID accountId=%d", account_id)
        return

    # === 4. 提取买家信息（需在持锁前提取，用于持锁后的二次去重检查） ===
    buyer_user_id = sender_user_id  # IN消息中 sender 是买家
    if not buyer_user_id:
        buyer_user_id = str(msg.get("senderUserId") or "")
    if not buyer_user_id:
        buyer_user_id = extract_peer_user_id_from_url(reminder_url) or ""
    buyer_user_name = str(msg.get("senderUserName") or msg.get("sender_user_name") or "")

    # === 5. 提取购买数量 ===
    buy_quantity = extract_buy_quantity_from_msg(msg)

    logger.info(
        "自动发货提取信息: accountId=%d orderId=%s xyGoodsId=%s sId=%s buyer=%s quantity=%d",
        account_id, order_id, xy_goods_id, s_id, buyer_user_id, buy_quantity
    )

    # === 5.5 并发去重锁 ===
    # 同一会话同一商品的多个并发发货任务（WS 重连/多消息触发）在这里串行化：
    # 第一个任务完成 INSERT delivery_record 后，后续任务的 _has_existing_realtime_delivery
    # 检查会命中已插入的记录并跳过，彻底消除 TOCTOU 竞态导致的重复发货。
    delivery_lock = await _get_delivery_lock(account_id, s_id, xy_goods_id)
    if delivery_lock.locked():
        logger.info(
            "自动发货等待锁: accountId=%d sId=%s xyGoodsId=%s（前序任务处理中）",
            account_id, s_id, xy_goods_id
        )
    async with delivery_lock:
        # 持锁后再次检查（防止前序任务刚完成 INSERT）
        if await _has_existing_realtime_delivery(
            db,
            tenant_id,
            account_id,
            order_id,
            s_id,
            xy_goods_id,
            buyer_user_id,
            pnm_id,
            "",
        ):
            logger.info(
                "自动发货跳过重复处理（持锁后二次检查） accountId=%d orderId=%s sId=%s xyGoodsId=%s",
                account_id, order_id, s_id, xy_goods_id
            )
            return
        await _process_delivery_inner(
            db, tenant_id, account_id, msg,
            s_id=s_id, sender_user_id=sender_user_id, receiver_user_id=receiver_user_id,
            reminder_url=reminder_url, reminder_content=reminder_content,
            pnm_id=pnm_id, msg_content=msg_content, order_id=order_id,
            xy_goods_id=xy_goods_id, buyer_user_id=buyer_user_id,
            buyer_user_name=buyer_user_name, buy_quantity=buy_quantity,
        )


async def _process_delivery_inner(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    msg: dict,
    *,
    s_id: str,
    sender_user_id: str,
    receiver_user_id: str,
    reminder_url: str,
    reminder_content: str,
    pnm_id: str,
    msg_content: str,
    order_id: Optional[str],
    xy_goods_id: str,
    buyer_user_id: str,
    buyer_user_name: str,
    buy_quantity: int,
) -> None:
    """持锁后的实际发货处理流程。"""
    # === 7. 查找匹配的发货规则 ===
    rule = await _match_delivery_rule(db, tenant_id, account_id, xy_goods_id)
    if not rule:
        logger.info("未找到匹配的发货规则 accountId=%d xyGoodsId=%s", account_id, xy_goods_id)
        # 记录一条失败的发货记录
        await _insert_delivery_record(
            db, tenant_id, account_id, order_id, s_id, pnm_id,
            buyer_user_id, buyer_user_name, xy_goods_id, buy_quantity,
            rule_id=None, delivery_type=MODE_TEXT, content=None,
            status=3, fail_reason="未配置自动发货规则",
            delivery_mode=MODE_TEXT,
            delivery_timing=DELIVERY_TIMING_AFTER_PAYMENT,
        )
        await _notify_realtime_delivery_failure(
            db=db,
            tenant_id=tenant_id,
            account_id=account_id,
            order_id=order_id,
            xy_goods_id=xy_goods_id,
            fail_reason="未配置自动发货规则",
        )
        return
    
    # === 8. 执行发货 ===
    delivery_mode = str(rule.get("delivery_mode") or "kami").lower()
    delivery_content = str(rule.get("delivery_content") or rule.get("content") or "")
    card_group_id = rule.get("card_group_id")
    trigger_source = "payment" if is_payment_message(msg) else "bargain"
    
    if delivery_mode == MODE_KAMI:
        await _execute_kami_delivery(
            db, tenant_id, account_id, order_id, s_id, pnm_id,
            buyer_user_id, buyer_user_name, xy_goods_id, buy_quantity,
            rule, card_group_id, trigger_source
        )
    elif delivery_mode == MODE_TEXT:
        await _execute_text_delivery(
            db, tenant_id, account_id, order_id, s_id, pnm_id,
            buyer_user_id, buyer_user_name, xy_goods_id, buy_quantity,
            rule, delivery_content, trigger_source
        )
    elif delivery_mode == MODE_API:
        await _execute_api_delivery(
            db, tenant_id, account_id, order_id, s_id, pnm_id,
            buyer_user_id, buyer_user_name, xy_goods_id, buy_quantity,
            rule, trigger_source
        )
    elif delivery_mode == MODE_CUSTOM:
        await _execute_custom_delivery(
            db, tenant_id, account_id, order_id, s_id, pnm_id,
            buyer_user_id, buyer_user_name, xy_goods_id, buy_quantity,
            rule, trigger_source
        )
    else:
        logger.warning("未知的发货模式: %s accountId=%d", delivery_mode, account_id)
        await _insert_delivery_record(
            db, tenant_id, account_id, order_id, s_id, pnm_id,
            buyer_user_id, buyer_user_name, xy_goods_id, buy_quantity,
            rule_id=rule.get("id"), delivery_type=delivery_mode,
            content=None, status=3, fail_reason=f"未知发货模式: {delivery_mode}",
            delivery_mode=delivery_mode,
            delivery_timing=DELIVERY_TIMING_AFTER_PAYMENT,
        )


async def _execute_text_delivery(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    order_id: str,
    s_id: str,
    pnm_id: str,
    buyer_user_id: str,
    buyer_user_name: str,
    xy_goods_id: str,
    buy_quantity: int,
    rule: dict,
    delivery_content: str,
    trigger_source: str,
):
    content = delivery_content
    content = content.replace("{buyerUserName}", buyer_user_name or "买家")
    content = content.replace("{orderId}", order_id or "")
    content = content.replace("{goodsTitle}", "")
    content = content.replace("{deliveryTime}", time.strftime("%Y-%m-%d %H:%M:%S"))

    send_ok = False
    fail_reason = None
    try:
        send_ok = await _send_delivery_message(account_id, s_id, buyer_user_id, content)
        if not send_ok:
            fail_reason = "WebSocket 发送消息失败"
    except Exception as e:
        fail_reason = f"发送消息异常: {str(e)}"
        logger.error("文本发货发送消息异常: accountId=%d error=%s", account_id, e)

    await _insert_delivery_record(
        db, tenant_id, account_id, order_id, s_id, pnm_id,
        buyer_user_id, buyer_user_name, xy_goods_id, buy_quantity,
        rule_id=rule.get("id"), delivery_type=MODE_TEXT,
        content=content, status=2 if send_ok else 3,
        fail_reason=fail_reason, trigger_source=trigger_source,
        delivery_mode=MODE_TEXT,
        delivery_timing=rule.get("delivery_timing") or DELIVERY_TIMING_AFTER_PAYMENT,
    )

    if send_ok and order_id:
        await db.execute(
            text("""
                UPDATE xianyu_trade_order
                SET order_status = 3, ship_time = NOW(), updated_time = NOW()
                WHERE tenant_id = :tenant_id
                  AND external_order_id = :external_order_id
                  AND deleted = 0
            """),
            {
                "tenant_id": tenant_id,
                "external_order_id": order_id,
            }
        )
    elif not send_ok:
        await _notify_realtime_delivery_failure(
            db=db,
            tenant_id=tenant_id,
            account_id=account_id,
            order_id=order_id,
            xy_goods_id=xy_goods_id,
            fail_reason=fail_reason or "WebSocket 发送消息失败",
        )


async def _match_delivery_rule(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    xy_goods_id: str,
) -> Optional[dict]:
    """匹配实时自动发货配置。优先命中新版商品级配置，兼容旧规则表。"""
    goods = await _find_goods_for_delivery(db, tenant_id, account_id, xy_goods_id)
    if goods:
        goods_rule = await _load_goods_delivery_rule(db, tenant_id, goods)
        if goods_rule:
            return goods_rule

    goods_id_num = None
    if xy_goods_id and xy_goods_id.isdigit():
        goods_id_num = int(xy_goods_id)
    
    rows = (await db.execute(
        text("""
            SELECT * FROM delivery_rule
            WHERE tenant_id = :tenant_id
              AND deleted = 0
              AND status = 1
              AND (account_id IS NULL OR account_id = :account_id)
              AND (goods_id IS NULL OR goods_id = 0 OR goods_id = :goods_id)
            ORDER BY
              CASE WHEN account_id = :account_id AND goods_id = :goods_id THEN 0
                   WHEN account_id = :account_id AND (goods_id IS NULL OR goods_id = 0) THEN 1
                   ELSE 2
              END,
              id DESC
            LIMIT 1
        """),
        {
            "tenant_id": tenant_id,
            "account_id": account_id,
            "goods_id": goods_id_num or 0,
        }
    )).mappings().all()
    
    return dict(rows[0]) if rows else None


async def _find_goods_for_delivery(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    xy_goods_id: str,
) -> Optional[dict]:
    if not xy_goods_id:
        return None

    row = (await db.execute(
        text("""
            SELECT id, tenant_id, account_id, external_goods_id, title
            FROM xianyu_goods
            WHERE tenant_id = :tenant_id
              AND deleted = 0
              AND external_goods_id = :xy_goods_id
            ORDER BY CASE WHEN account_id = :account_id THEN 0 ELSE 1 END, id DESC
            LIMIT 1
        """),
        {
            "tenant_id": tenant_id,
            "account_id": account_id,
            "xy_goods_id": xy_goods_id,
        }
    )).mappings().first()
    return dict(row) if row else None


async def _load_goods_delivery_rule(
    db: AsyncSession,
    tenant_id: int,
    goods: dict,
) -> Optional[dict]:
    row = (await db.execute(
        text("""
            SELECT id, goods_id, config_json
            FROM delivery_goods_config
            WHERE tenant_id = :tenant_id
              AND goods_id = :goods_id
              AND deleted = 0
            LIMIT 1
        """),
        {
            "tenant_id": tenant_id,
            "goods_id": goods.get("id"),
        }
    )).mappings().first()
    if not row:
        return None

    config_json = row.get("config_json")
    if isinstance(config_json, str):
        try:
            config = json.loads(config_json)
        except json.JSONDecodeError:
            logger.warning("商品级自动发货配置JSON解析失败 tenantId=%s goodsId=%s", tenant_id, goods.get("id"))
            return None
    elif isinstance(config_json, dict):
        config = config_json
    else:
        return None

    timing_config = config.get("payDelivery")
    if not isinstance(timing_config, dict):
        return None

    enabled = timing_config.get("enabled")
    if enabled in (0, "0", False, "false", "False", None):
        return None

    mode = str(timing_config.get("mode") or MODE_TEXT).lower()
    header = str(timing_config.get("header") or "")
    content = str(timing_config.get("content") or "")
    footer = str(timing_config.get("footer") or "")
    source_id = timing_config.get("sourceId")
    source_title = str(timing_config.get("sourceTitle") or "")

    if mode == MODE_TEXT and source_id:
        source = await _load_text_source(db, tenant_id, source_id)
        if source:
            if not content:
                content = str(source.get("content") or "")
            if not source_title:
                source_title = str(source.get("title") or "")

    if mode == MODE_TEXT and not any([header.strip(), content.strip(), footer.strip()]):
        return None

    delivery_content = _build_delivery_content(header, content, footer)
    return {
        "id": row.get("id"),
        "goods_id": goods.get("id"),
        "delivery_mode": mode,
        "delivery_content": delivery_content,
        "content": delivery_content,
        "delivery_timing": DELIVERY_TIMING_AFTER_PAYMENT,
        "source_id": source_id,
        "source_title": source_title,
        "card_group_id": timing_config.get("cardGroupId"),
        "auto_confirm_shipment": timing_config.get("autoConfirmShipment")
        or timing_config.get("auto_confirm_shipment")
        or 0,
        "segment_send": timing_config.get("segmentSend"),
    }


def _build_delivery_content(header: str, content: str, footer: str) -> str:
    return "\n".join(
        part for part in [str(header or "").strip(), str(content or "").strip(), str(footer or "").strip()]
        if part
    )


async def _load_text_source(
    db: AsyncSession,
    tenant_id: int,
    source_id: Any,
) -> Optional[dict]:
    row = (await db.execute(
        text("""
            SELECT id, title, content, remark
            FROM delivery_text_source
            WHERE tenant_id = :tenant_id
              AND id = :source_id
              AND deleted = 0
            LIMIT 1
        """),
        {
            "tenant_id": tenant_id,
            "source_id": source_id,
        }
    )).mappings().first()
    return dict(row) if row else None


async def _has_existing_realtime_delivery(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    order_id: Optional[str],
    s_id: str,
    xy_goods_id: str,
    buyer_user_id: str,
    pnm_id: str,
    delivery_content: str,
) -> bool:
    if order_id:
        existing = (await db.execute(
            text("""
                SELECT id
                FROM delivery_record
                WHERE tenant_id = :tenant_id
                  AND account_id = :account_id
                  AND order_id = :order_id
                  AND deleted = 0
                  AND status IN (1, 2)
                LIMIT 1
            """),
            {
                "tenant_id": tenant_id,
                "account_id": account_id,
                "order_id": order_id,
            }
        )).mappings().first()
        if existing:
            return True

    normalized_sid = s_id if str(s_id).endswith("@goofish") else f"{s_id}@goofish"
    normalized_buyer = (
        buyer_user_id
        if str(buyer_user_id).endswith("@goofish")
        else f"{buyer_user_id}@goofish"
    )
    existing = (await db.execute(
        text("""
            SELECT id
            FROM delivery_record
            WHERE tenant_id = :tenant_id
              AND account_id = :account_id
              AND deleted = 0
              AND delivery_timing = :delivery_timing
              AND JSON_UNQUOTE(JSON_EXTRACT(receiver_info, '$.sid')) = :sid
              AND JSON_UNQUOTE(JSON_EXTRACT(receiver_info, '$.buyerUserId')) = :buyer_user_id
              AND JSON_UNQUOTE(JSON_EXTRACT(receiver_info, '$.xyGoodsId')) = :xy_goods_id
              AND (:pnm_id = '' OR JSON_UNQUOTE(JSON_EXTRACT(receiver_info, '$.pnmId')) = :pnm_id)
              AND (:delivery_content = '' OR COALESCE(delivery_content, '') = :delivery_content)
              AND status IN (1, 2)
            LIMIT 1
        """),
        {
            "tenant_id": tenant_id,
            "account_id": account_id,
            "delivery_timing": DELIVERY_TIMING_AFTER_PAYMENT,
            "sid": normalized_sid,
            "buyer_user_id": normalized_buyer,
            "xy_goods_id": str(xy_goods_id or ""),
            "pnm_id": str(pnm_id or ""),
            "delivery_content": str(delivery_content or ""),
        }
    )).mappings().first()
    return bool(existing)


async def _execute_kami_delivery(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    order_id: str,
    s_id: str,
    pnm_id: str,
    buyer_user_id: str,
    buyer_user_name: str,
    xy_goods_id: str,
    buy_quantity: int,
    rule: dict,
    card_group_id: Optional[int],
    trigger_source: str,
):
    """执行卡密模式发货。
    
    从 card_item 表中原子认领卡密，通过 WebSocket 发送给买家。
    参考参考文档的 KamiConfigServiceImpl.acquireKami()。
    """
    # Step 1: 原子认领卡密（UPDATE + LIMIT 1）
    update_result = await db.execute(
        text("""
            UPDATE card_item
            SET status = 1,
                used_order_id = :order_id,
                used_time = NOW(),
                updated_time = NOW()
            WHERE tenant_id = :tenant_id
              AND deleted = 0
              AND status = 0
              AND (:group_id IS NULL OR group_id = :group_id)
            ORDER BY id ASC
            LIMIT :limit
        """),
        {
            "tenant_id": tenant_id,
            "group_id": card_group_id,
            "order_id": order_id,
            "limit": buy_quantity,
        }
    )
    claimed_count = update_result.rowcount or 0
    
    if claimed_count <= 0:
        logger.warning("卡密库存不足: accountId=%d groupId=%s", account_id, card_group_id)
        await _insert_delivery_record(
            db, tenant_id, account_id, order_id, s_id, pnm_id,
            buyer_user_id, buyer_user_name, xy_goods_id, buy_quantity,
            rule_id=rule.get("id"), delivery_type=MODE_KAMI,
            content=None, status=0, fail_reason="卡密库存不足",
            trigger_source=trigger_source
        )
        return
    
    # Step 2: 读取被认领的卡密内容
    card_items = (await db.execute(
        text("""
            SELECT id, card_key, card_value, extra_info
            FROM card_item
            WHERE tenant_id = :tenant_id
              AND used_order_id = :order_id
              AND deleted = 0
              AND status = 1
            ORDER BY id ASC
        """),
        {"tenant_id": tenant_id, "order_id": order_id}
    )).mappings().all()
    
    if not card_items:
        await _insert_delivery_record(
            db, tenant_id, account_id, order_id, s_id, pnm_id,
            buyer_user_id, buyer_user_name, xy_goods_id, buy_quantity,
            rule_id=rule.get("id"), delivery_type=MODE_KAMI,
            content=None, status=0, fail_reason="卡密认领后读取失败",
            trigger_source=trigger_source
        )
        return
    
    # Step 3: 组装卡密内容
    kami_template = rule.get("kami_delivery_template") or "{kmKey}"
    kami_contents = []
    for item in card_items:
        card_key = str(item.get("card_key") or "")
        card_value = str(item.get("card_value") or "")
        km_key = card_value if card_value else card_key
        single_content = kami_template.replace("{kmKey}", km_key)
        kami_contents.append(single_content)
    
    combined_content = "\n---\n".join(kami_contents)
    
    # Step 4: 发送到买家
    send_ok = False
    fail_reason = None
    try:
        send_ok = await _send_delivery_message(account_id, s_id, buyer_user_id, combined_content)
        if not send_ok:
            fail_reason = "WebSocket 发送卡密失败"
    except Exception as e:
        fail_reason = f"发送卡密异常: {str(e)}"
        logger.error("卡密发货发送消息异常: accountId=%d error=%s", account_id, e)
    
    # Step 5: 更新卡密状态（标记为已使用）
    if send_ok:
        for item in card_items:
            await db.execute(
                text("""
                    UPDATE card_item
                    SET status = 2, updated_time = NOW()
                    WHERE id = :id AND tenant_id = :tenant_id
                """),
                {"id": item["id"], "tenant_id": tenant_id}
            )
    else:
        # 发送失败，回滚卡密状态
        for item in card_items:
            await db.execute(
                text("""
                    UPDATE card_item
                    SET status = 0, used_order_id = NULL, used_time = NULL, updated_time = NOW()
                    WHERE id = :id AND tenant_id = :tenant_id
                """),
                {"id": item["id"], "tenant_id": tenant_id}
            )
    
    # Step 6: 更新卡密组统计计数
    if card_group_id:
        await db.execute(
            text("""
                UPDATE card_group g SET
                    total_count = (SELECT COUNT(*) FROM card_item i WHERE i.group_id = g.id AND i.tenant_id = g.tenant_id AND i.deleted = 0),
                    used_count = (SELECT COUNT(*) FROM card_item i WHERE i.group_id = g.id AND i.tenant_id = g.tenant_id AND i.deleted = 0 AND i.status = 2),
                    available_count = (SELECT COUNT(*) FROM card_item i WHERE i.group_id = g.id AND i.tenant_id = g.tenant_id AND i.deleted = 0 AND i.status = 0),
                    updated_time = NOW()
                WHERE g.id = :group_id AND g.tenant_id = :tenant_id
            """),
            {"group_id": card_group_id, "tenant_id": tenant_id}
        )
    
    # Step 7: 记录发货记录
    await _insert_delivery_record(
        db, tenant_id, account_id, order_id, s_id, pnm_id,
        buyer_user_id, buyer_user_name, xy_goods_id, buy_quantity,
        rule_id=rule.get("id"), delivery_type=MODE_KAMI,
        content=combined_content, status=1 if send_ok else 0,
        fail_reason=fail_reason, trigger_source=trigger_source
    )
    
    # Step 8: 自动确认发货
    if send_ok and rule.get("auto_confirm_shipment") == 1:
        await _auto_confirm_shipment(tenant_id, account_id, order_id)


async def _execute_api_delivery(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    order_id: str,
    s_id: str,
    pnm_id: str,
    buyer_user_id: str,
    buyer_user_name: str,
    xy_goods_id: str,
    buy_quantity: int,
    rule: dict,
    trigger_source: str,
):
    """Fail closed for legacy API-delivery rules until a secure adapter is implemented."""
    logger.warning(
        "拒绝执行未接入安全出站适配器的 API 发货规则 tenantId=%d accountId=%d ruleId=%s",
        tenant_id,
        account_id,
        rule.get("id"),
    )
    await _insert_delivery_record(
        db, tenant_id, account_id, order_id, s_id, pnm_id,
        buyer_user_id, buyer_user_name, xy_goods_id, buy_quantity,
        rule_id=rule.get("id"), delivery_type=MODE_API,
        content=None, status=3,
        fail_reason="API 发货模式暂不可用，请改用文本或卡密发货",
        trigger_source=trigger_source,
        delivery_mode=MODE_API,
        delivery_timing=DELIVERY_TIMING_AFTER_PAYMENT,
    )
    await _notify_realtime_delivery_failure(
        db=db,
        tenant_id=tenant_id,
        account_id=account_id,
        order_id=order_id,
        xy_goods_id=xy_goods_id,
        fail_reason="API 发货模式暂不可用，请改用文本或卡密发货",
    )


async def _execute_custom_delivery(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    order_id: str,
    s_id: str,
    pnm_id: str,
    buyer_user_id: str,
    buyer_user_name: str,
    xy_goods_id: str,
    buy_quantity: int,
    rule: dict,
    trigger_source: str,
):
    """执行自定义模式发货。
    
    不发送任何消息，直接将发货记录标记为成功。
    适用于通过其他渠道（如ERP系统）自行处理发货的场景。
    """
    await _insert_delivery_record(
        db, tenant_id, account_id, order_id, s_id, pnm_id,
        buyer_user_id, buyer_user_name, xy_goods_id, buy_quantity,
        rule_id=rule.get("id"), delivery_type=MODE_CUSTOM,
        content="[自定义发货-不发送消息]", status=1,
        fail_reason=None, trigger_source=trigger_source,
    )


async def _send_delivery_message(
    account_id: int,
    s_id: str,
    buyer_user_id: str,
    content: str,
) -> bool:
    """通过WebSocket发送发货消息给买家。
    
    Args:
        account_id: 闲鱼账号ID
        s_id: 会话ID
        buyer_user_id: 买家用户ID
        content: 发货内容
        
    Returns:
        True 表示发送成功
    """
    client = ws_manager.get_client(account_id)
    if not client or not client.is_connected:
        logger.warning("WebSocket未连接，无法发送消息: accountId=%d", account_id)
        return False
    
    if not client._sid:
        logger.warning("WebSocket未注册（无sid），无法发送消息: accountId=%d", account_id)
        return False
    
    # 构造 cid 和 to_id（格式: xxx@goofish）
    # s_id 可能已经带 @goofish 后缀，也可能不带
    cid = s_id if s_id.endswith("@goofish") else f"{s_id}@goofish"
    to_id = buyer_user_id if buyer_user_id.endswith("@goofish") else f"{buyer_user_id}@goofish"
    
    logger.info(
        "发送发货消息: accountId=%d cid=%s to_id=%s contentLen=%d",
        account_id, cid, to_id, len(content)
    )
    
    result = await client.send_text_message(cid=cid, to_id=to_id, text=content)
    code = result.get("code", 500)
    
    if code == 200:
        logger.info("发货消息发送成功: accountId=%d", account_id)
        return True
    else:
        logger.warning("发货消息发送失败: accountId=%d code=%s error=%s", account_id, code, result.get("error", ""))
        return False


async def _auto_confirm_shipment(
    tenant_id: int,
    account_id: int,
    order_id: str,
):
    """通过统一能力门禁请求确认发货；未验证的闲鱼接口始终 fail-closed。"""
    try:
        from .xianyu_api_service import confirm_shipment

        result = confirm_shipment(account_id, order_id)
        if result and result.get("success"):
            logger.info("确认发货成功: accountId=%d orderId=%s", account_id, order_id)
        else:
            logger.warning(
                "确认发货能力不可用: tenantId=%d accountId=%d orderId=%s error=%s message=%s",
                tenant_id,
                account_id,
                order_id,
                result.get("error", "") if result else "CAPABILITY_UNAVAILABLE",
                result.get("message", "") if result else "",
            )
        return result or {
            "success": False,
            "error": "CAPABILITY_UNAVAILABLE",
            "message": "闲鱼确认发货能力当前不可用",
        }
    except Exception as e:
        logger.error("确认发货异常: accountId=%d orderId=%s error=%s", account_id, order_id, e)
        return {
            "success": False,
            "error": "CONFIRM_SHIPMENT_EXCEPTION",
            "message": str(e),
        }


async def _notify_realtime_delivery_failure(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    order_id: Optional[str],
    xy_goods_id: str,
    fail_reason: str,
) -> None:
    goods_title = ""
    try:
        goods_row = (await db.execute(
            text("""
                SELECT title
                FROM xianyu_goods
                WHERE tenant_id = :tenant_id
                  AND deleted = 0
                  AND external_goods_id = :xy_goods_id
                ORDER BY id DESC
                LIMIT 1
            """),
            {
                "tenant_id": tenant_id,
                "xy_goods_id": xy_goods_id,
            }
        )).mappings().first()
        if goods_row:
            goods_title = str(goods_row.get("title") or "")
    except Exception:
        logger.debug("query realtime delivery goods title failed tenantId=%s xyGoodsId=%s", tenant_id, xy_goods_id, exc_info=True)

    try:
        from .automation_runtime import insert_notification

        lines = ["检测到新订单自动发货未成功，需要人工代发货。"]
        if order_id:
            lines.append(f"订单号：{order_id}")
        if goods_title:
            lines.append(f"商品：{goods_title}")
        if fail_reason:
            lines.append(f"失败原因：{fail_reason}")
        lines.append(f"提醒时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
        await insert_notification(
            db,
            tenant_id,
            None,
            "代发货提醒",
            "\n".join(lines),
            "代发货提醒",
            "warn",
        )
    except Exception:
        logger.debug("write manual delivery reminder failed tenantId=%s accountId=%s", tenant_id, account_id, exc_info=True)


async def _insert_delivery_record(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    order_id: Optional[str],
    s_id: str,
    pnm_id: str,
    buyer_user_id: str,
    buyer_user_name: str,
    xy_goods_id: str,
    buy_quantity: int,
    rule_id: Optional[int],
    delivery_type: str,
    content: Optional[str],
    status: int,
    fail_reason: Optional[str] = None,
    trigger_source: str = "payment",
    external_allocation_id: Optional[str] = None,
    delivery_mode: Optional[str] = None,
    delivery_timing: Optional[str] = None,
):
    """插入发货记录。"""
    delivery_status = "success" if status == 2 else "pending" if status in (0, 1) else "failed"
    error_msg = fail_reason
    
    await db.execute(
        text("""
            INSERT INTO delivery_record(
                tenant_id, account_id, order_id, rule_id, delivery_type, delivery_mode,
                content, delivery_content, receiver_info, delivery_timing,
                status, delivery_status, error_message, retry_count,
                fail_reason, delivery_time, completed_time, created_time, updated_time, deleted
            ) VALUES(
                :tenant_id, :account_id, :order_id, :rule_id, :delivery_type, :delivery_mode,
                :content, :delivery_content, :receiver_info, :delivery_timing,
                :status, :delivery_status, :error_message, 0,
                :fail_reason, IF(:delivery_success = 1, NOW(), NULL), IF(:delivery_success = 1, NOW(), NULL), NOW(), NOW(), 0
            )
        """),
        {
            "tenant_id": tenant_id,
            "account_id": account_id,
            "order_id": order_id,
            "rule_id": rule_id,
            "delivery_type": delivery_type,
            "delivery_mode": delivery_mode or delivery_type,
            "content": content,
            "delivery_content": content,
            "receiver_info": json.dumps(
                {"sid": s_id, "pnmId": pnm_id, "buyerUserId": buyer_user_id, "xyGoodsId": xy_goods_id},
                ensure_ascii=False,
                sort_keys=True,
            ),
            "delivery_timing": delivery_timing,
            "status": status,
            "delivery_status": delivery_status,
            "error_message": error_msg,
            "fail_reason": fail_reason,
            "delivery_success": 1 if status == 2 else 0,
        }
    )
    
    logger.info(
        "发货记录已创建: accountId=%d orderId=%s type=%s status=%s",
        account_id, order_id, delivery_type, delivery_status
    )


