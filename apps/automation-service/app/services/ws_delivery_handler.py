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

from sqlalchemy import bindparam, text
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

# 内存级发货去重：防止同一会话+商品的并发任务在锁失效时重复认领卡密。
# key = f"{account_id}:{normalized_sid}:{xy_goods_id}"，value = 无意义占位。
# 在 _execute_kami_delivery 入口处 set.add，出口处 set.discard。
_delivery_in_flight: set[str] = set()
_delivery_in_flight_guard = asyncio.Lock()


# ============================================================
# 订单同步节流：同一账号在此窗口内收到的多条待发货消息只触发一次远程同步
# ============================================================
# 60 秒窗口足以覆盖一次连发多条付款通知的场景，同时避免高频消息刷接口。
ORDER_SYNC_THROTTLE_SECONDS = 60.0
_order_sync_last_run: dict[int, float] = {}
_order_sync_tasks: dict[int, asyncio.Task] = {}

# M3: 跨协程共享状态 lazy-initialized asyncio.Lock，避免模块加载时要求事件循环
_order_sync_last_run_lock = None
_order_sync_tasks_lock = None


def _get_order_sync_last_run_lock() -> asyncio.Lock:
    global _order_sync_last_run_lock
    if _order_sync_last_run_lock is None:
        _order_sync_last_run_lock = asyncio.Lock()
    return _order_sync_last_run_lock


def _get_order_sync_tasks_lock() -> asyncio.Lock:
    global _order_sync_tasks_lock
    if _order_sync_tasks_lock is None:
        _order_sync_tasks_lock = asyncio.Lock()
    return _order_sync_tasks_lock


async def _get_delivery_lock(account_id: int, s_id: str, xy_goods_id: str) -> asyncio.Lock:
    """获取按 会话+商品 维度的发货串行锁。

    归一化 s_id：去掉 @goofish 后缀。闲鱼 WS 推送的同一会话消息可能带
    或不带 @goofish 后缀（如 64799897685 vs 64799897685@goofish），
    若不归一化会产生不同的 lock key，导致同一会话的并发发货任务不被串行化，
    去重检查在 record 写入前执行，引发重复认领卡密。
    """
    normalized_sid = (s_id or "").replace("@goofish", "")
    key = f"{account_id}:{normalized_sid}:{xy_goods_id}"
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
# 收到付款/待发货消息时自动同步账号最新订单
# ============================================================
def _trigger_account_orders_sync(tenant_id: int, account_id: int) -> None:
    """异步触发账号最新订单同步，带节流去重。

    背景：原设计仅依赖 Java 端 10 分钟定时任务（autoSyncOrdersFromXianyu）拉取
    闲鱼已售订单入库。用户自测下单后订单未同步，根因是 WS 实时消息路径未触发
    订单同步，导致新订单最多要等 10 分钟才入库。

    此函数在检测到"已付款/待发货"消息时立即异步拉取该账号最新订单入库：
    - 用 asyncio.create_task 在后台执行，不阻塞消息回调与自动发货主流程
    - 节流：同一账号 ORDER_SYNC_THROTTLE_SECONDS 秒内只触发一次，避免连发消息刷接口
    - 使用独立数据库会话，与发货流程的事务隔离
    - 任何异常仅记录日志，不影响自动发货
    """
    if not account_id:
        return

    # TODO: 跨协程共享状态，sync 访问点未加锁（_order_sync_last_run / _order_sync_tasks）
    # 此 sync 函数被 sync 调用方调用；异步侧 _run_account_orders_sync 的写入已加锁。
    now = time.monotonic()
    last_run = _order_sync_last_run.get(account_id, 0.0)
    if now - last_run < ORDER_SYNC_THROTTLE_SECONDS:
        logger.debug(
            "账号订单同步节流跳过 tenantId=%d accountId=%d 距上次触发 %.1fs",
            tenant_id, account_id, now - last_run,
        )
        return

    # 同一账号若已有正在运行的同步任务，跳过
    existing_task = _order_sync_tasks.get(account_id)
    if existing_task is not None and not existing_task.done():
        logger.debug(
            "账号订单同步任务已在运行，跳过 tenantId=%d accountId=%d",
            tenant_id, account_id,
        )
        return

    _order_sync_last_run[account_id] = now
    task = asyncio.create_task(_run_account_orders_sync(tenant_id, account_id))
    _order_sync_tasks[account_id] = task


async def _run_account_orders_sync(tenant_id: int, account_id: int) -> None:
    """实际执行账号订单同步的后台任务。

    独立数据库会话中调用 sync_sold_orders_for_account 拉取远程已售订单并入库。
    同步失败不影响自动发货流程，仅记录日志。
    """
    try:
        from .automation_runtime import sync_sold_orders_for_account

        async with async_session() as db:
            try:
                result = await sync_sold_orders_for_account(db, tenant_id, account_id)
                logger.info(
                    "WS 消息触发账号订单同步完成 tenantId=%d accountId=%d ok=%s processed=%d inserted=%d updated=%d failed=%d message=%s",
                    tenant_id, account_id, result.get("ok"),
                    result.get("processed", 0), result.get("inserted", 0),
                    result.get("updated", 0), result.get("failed", 0),
                    result.get("message", ""),
                )
            except Exception as exc:
                await db.rollback()
                raise exc
    except Exception as exc:
        logger.error(
            "WS 消息触发账号订单同步失败 tenantId=%d accountId=%d: %s",
            tenant_id, account_id, exc, exc_info=True,
        )
    finally:
        async with _get_order_sync_tasks_lock():
            _order_sync_tasks.pop(account_id, None)


# ============================================================
# "待刀成"消息处理：标记小刀订单 + 调免拼接口（促成小刀成交）
# ============================================================
async def _handle_bargain_waiting_message(
    tenant_id: int,
    account_id: int,
    msg: dict,
) -> None:
    """处理"我已小刀，待刀成"消息：标记小刀订单 + 调用免拼接口。

    买家发起小刀后，系统自动调用免拼接口（mtop.idle.groupon.activity.seller.freeshipping）
    促成小刀成交。此步骤不发送发货信息，完整发货由后续"小刀成功"消息触发。

    流程：
    1. 提取订单ID、商品ID、买家ID
    2. 标记订单为小刀订单（is_bargain=1）
    3. 商品归属检查（复用 _match_delivery_rule，未命中则跳过）
    4. 调用免拼接口 confirm_freeshipping（已支持幂等）
    """
    s_id = str(msg.get("sId") or "")
    reminder_url = str(msg.get("reminderUrl") or msg.get("reminder_url") or "")

    # 提取订单ID、商品ID、买家ID
    order_id = extract_order_id_from_url(reminder_url)
    xy_goods_id = str(msg.get("xyGoodsId") or "")
    if not xy_goods_id:
        xy_goods_id = extract_goods_id_from_url(reminder_url) or ""
    buyer_user_id = str(msg.get("senderUserId") or "")
    if not buyer_user_id:
        buyer_user_id = extract_peer_user_id_from_url(reminder_url) or ""

    logger.info(
        "检测到待刀成消息: accountId=%d orderId=%s xyGoodsId=%s buyer=%s sId=%s",
        account_id, order_id, xy_goods_id, buyer_user_id, s_id,
    )

    if not xy_goods_id or not buyer_user_id:
        logger.warning(
            "待刀成消息缺少商品ID或买家ID，跳过免拼: accountId=%d xyGoodsId=%s buyer=%s",
            account_id, xy_goods_id, buyer_user_id,
        )
        return

    async with async_session() as db:
        try:
            # 1. 标记订单为小刀订单（即使订单未同步也尝试标记，失败不影响后续免拼）
            if order_id:
                await _mark_order_as_bargain(db, tenant_id, account_id, order_id, xy_goods_id)

            # 2. 商品归属检查：复用现有 _match_delivery_rule
            #    若商品不属于本账号或未配置发货规则，则跳过免拼接口调用
            rule = await _match_delivery_rule(db, tenant_id, account_id, xy_goods_id)
            if not rule:
                logger.info(
                    "待刀成消息：商品不属于本账号或未配置发货规则，跳过免拼: accountId=%d xyGoodsId=%s",
                    account_id, xy_goods_id,
                )
                await db.commit()
                return

            # 3. 调用免拼接口（confirm_freeshipping 已支持幂等：ORDER_ALREADY_DELIVERY 视为成功）
            from .xianyu_api_service import confirm_freeshipping
            result = await asyncio.to_thread(
                confirm_freeshipping,
                account_id, order_id or "", xy_goods_id, buyer_user_id,
            )

            if result and result.get("success"):
                logger.info(
                    "待刀成消息：免拼接口调用成功: accountId=%d orderId=%s itemId=%s buyerId=%s",
                    account_id, order_id, xy_goods_id, buyer_user_id,
                )
            else:
                logger.warning(
                    "待刀成消息：免拼接口调用失败: accountId=%d orderId=%s error=%s message=%s",
                    account_id, order_id,
                    result.get("error", "") if result else "NONE",
                    result.get("message", "") if result else "",
                )

            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(
                "待刀成消息处理失败: accountId=%d error=%s",
                account_id, e, exc_info=True,
            )


async def _mark_order_as_bargain(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    order_id: str,
    xy_goods_id: str,
) -> None:
    """标记订单为小刀订单（is_bargain=1）。

    优先按 external_order_id 精确匹配；若未命中（订单可能尚未同步），
    按 account_id + external_goods_id 匹配最近一笔订单兜底。
    """
    # 1. 按 external_order_id 精确匹配
    result = await db.execute(
        text("""
            UPDATE xianyu_trade_order
            SET is_bargain = 1, updated_time = NOW()
            WHERE tenant_id = :tenant_id
              AND account_id = :account_id
              AND external_order_id = :external_order_id
              AND deleted = 0
        """),
        {
            "tenant_id": tenant_id,
            "account_id": account_id,
            "external_order_id": order_id,
        },
    )

    # 2. 若未命中，按 xy_goods_id 兜底（标记该账号下该商品的最近一笔订单）
    if result.rowcount == 0 and xy_goods_id:
        await db.execute(
            text("""
                UPDATE xianyu_trade_order
                SET is_bargain = 1, updated_time = NOW()
                WHERE tenant_id = :tenant_id
                  AND account_id = :account_id
                  AND external_goods_id = :xy_goods_id
                  AND deleted = 0
                  AND id = (
                      SELECT id FROM (
                          SELECT id FROM xianyu_trade_order
                          WHERE tenant_id = :tenant_id
                            AND account_id = :account_id
                            AND external_goods_id = :xy_goods_id
                            AND deleted = 0
                          ORDER BY created_time DESC
                          LIMIT 1
                      ) AS t
                  )
            """),
            {
                "tenant_id": tenant_id,
                "account_id": account_id,
                "xy_goods_id": xy_goods_id,
            },
        )


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
    # "待刀成"消息：标记小刀订单 + 调免拼接口（促成小刀成交），不触发完整发货
    # "小刀成功"/"已付款"消息：触发完整自动发货（发信息 + 确认发货）
    if is_bargain_waiting_message(msg):
        await _handle_bargain_waiting_message(tenant_id, account_id, msg)
        return

    if not is_payment_message(msg) and not is_bargain_success_message(msg):
        return

    logger.info(
        "检测到待发货消息: accountId=%d contentType=%s sId=%s",
        account_id, msg.get("contentType"), msg.get("sId", "")
    )

    # 收到付款/小刀成功消息时立即异步同步该账号最新订单入库。
    # 解决 WS 实时路径未触发订单同步、新订单需等 10 分钟定时任务才入库的问题。
    # 节流+独立会话，失败不影响自动发货。
    try:
        _trigger_account_orders_sync(tenant_id, account_id)
    except Exception:
        logger.debug("触发账号订单同步异常，忽略", exc_info=True)

    # 检测到新订单（付款消息）时推送飞书机器人通知（失败不影响主流程）
    if is_payment_message(msg):
        try:
            from .notify_dispatcher import notify_new_order
            await notify_new_order(tenant_id, account_id, msg)
        except Exception:
            logger.debug("新订单飞书通知异常，忽略", exc_info=True)

    async with async_session() as db:
        try:
            # 发货声明流程：若声明开关开启，发送声明并创建 waiting 会话，不立即发货
            # 仅对"已付款"消息触发声明流程（小刀成功消息也走声明流程）
            if await _should_send_statement(db, tenant_id):
                handled = await _send_statement_for_payment(db, tenant_id, account_id, msg)
                if handled:
                    await db.commit()
                    return  # 已发送声明，等待买家确认后再发货

            await _process_delivery(db, tenant_id, account_id, msg)
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(
                "自动发货处理失败: accountId=%d error=%s",
                account_id, e, exc_info=True
            )


async def _should_send_statement(db: AsyncSession, tenant_id: int) -> bool:
    """查询发货声明开关是否开启"""
    from .ws_statement_handler import is_statement_enabled
    return await is_statement_enabled(db, tenant_id)


async def _send_statement_for_payment(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    msg: dict,
) -> bool:
    """对付款消息发送发货声明。返回 True 表示已发送声明（调用方应停止发货流程）。

    提取消息中的订单/商品/买家信息，调用 ws_statement_handler 发送声明并创建会话。
    """
    from .ws_statement_handler import send_statement_and_create_session

    s_id = str(msg.get("sId") or "")
    if not s_id:
        return False

    reminder_url = str(msg.get("reminderUrl") or msg.get("reminder_url") or "")
    order_id = extract_order_id_from_url(reminder_url)

    xy_goods_id = str(msg.get("xyGoodsId") or "")
    if not xy_goods_id:
        xy_goods_id = extract_goods_id_from_url(reminder_url) or ""

    buyer_user_id = str(msg.get("senderUserId") or "")
    if not buyer_user_id:
        buyer_user_id = extract_peer_user_id_from_url(reminder_url) or ""

    buyer_user_name = str(msg.get("senderUserName") or msg.get("sender_user_name") or "")
    pnm_id = str(msg.get("pnmId") or "")

    # 查询商品标题（用于文案变量替换）
    goods_title = ""
    if xy_goods_id:
        try:
            row = (await db.execute(
                text("SELECT title FROM xianyu_goods WHERE external_goods_id=:gid AND deleted=0 ORDER BY id DESC LIMIT 1"),
                {"gid": xy_goods_id},
            )).first()
            if row:
                goods_title = row[0] or ""
        except Exception as goods_err:
            logger.warning("查询商品标题失败，将以空标题继续 xy_goods_id=%s errorType=%s", xy_goods_id, type(goods_err).__name__)

    return await send_statement_and_create_session(
        db, tenant_id, account_id, msg,
        order_id=order_id,
        xy_goods_id=xy_goods_id,
        s_id=s_id,
        pnm_id=pnm_id,
        buyer_user_id=buyer_user_id,
        buyer_user_name=buyer_user_name,
        goods_title=goods_title,
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
        # 重置事务快照：_should_send_statement 的 SELECT 已隐式开启事务，
        # MySQL REPEATABLE READ 隔离级别下，Check 1 会使用旧 snapshot，
        # 看不到前序任务刚 commit 的 delivery_record → 去重失效。
        # commit() 结束当前事务，后续查询创建新 snapshot，能看到最新已提交数据。
        if hasattr(db, "commit"):
            try:
                await db.commit()
            except Exception:
                if hasattr(db, "rollback"):
                    try:
                        await db.rollback()
                    except Exception:
                        pass

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
        # 锁内提交：确保 delivery_record INSERT 在锁释放前已对其他会话可见。
        if hasattr(db, "commit"):
            try:
                await db.commit()
            except Exception as commit_err:
                logger.error("锁内提交事务失败: %s", commit_err, exc_info=True)
                if hasattr(db, "rollback"):
                    try:
                        await db.rollback()
                    except Exception:
                        pass


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

    # === 7.5 多规格 SKU 规则匹配 ===
    # 若商品配置了 skuRules，则反查订单 skuId 并按 SKU 精确匹配发货规则。
    # 反查失败或未匹配时回退到商品通用配置（保证发货不中断）。
    sku_rules = rule.get("_sku_rules") if isinstance(rule, dict) else None
    if sku_rules:
        sku_id = await _resolve_order_sku_id(db, order_id, account_id, xy_goods_id)
        if sku_id:
            rule = _apply_sku_rule_override(rule, sku_id)
            logger.info("SKU规则匹配 accountId=%d xyGoodsId=%s skuId=%s matched=%s",
                        account_id, xy_goods_id, sku_id, rule.get("_sku_matched"))
        else:
            logger.info("SKU反查失败，回退商品通用配置 accountId=%d orderId=%s",
                        account_id, order_id)

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


# ============================================================
# 声明确认后触发发货（由 ws_statement_handler._handle_confirm 调用）
# ============================================================
async def _trigger_delivery_for_confirmed_statement(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    *,
    order_id: Optional[str],
    xy_goods_id: str,
    buyer_user_id: str,
    s_id: str,
    goods_title: str,
    session_id: int,
) -> None:
    """买家确认发货声明后，触发该订单的发货流程。

    安全保障（防止重复发货）：
    - 走并发去重锁 _get_delivery_lock（与实时付款路径共用同一把锁，互斥）
    - 走 _has_existing_realtime_delivery 去重检查（防止已发货订单被重复发货）
    - 持锁后再次检查（防止前序任务刚完成 INSERT）
    """
    logger.info(
        "声明确认后触发发货: tenantId=%d accountId=%d orderId=%s xyGoodsId=%s sessionId=%d",
        tenant_id, account_id, order_id, xy_goods_id, session_id,
    )

    # 构造发货所需的上下文参数（复用 _process_delivery_inner）
    buyer_user_name = ""
    buy_quantity = 1

    # === 并发去重锁（与实时付款路径共用同一把锁，确保互斥） ===
    # 防止声明确认与实时付款路径并发触发导致重复发货。
    # 同一会话同一商品的发货任务串行化，前序任务完成后后续任务通过 DB 去重跳过。
    delivery_lock = await _get_delivery_lock(account_id, s_id, xy_goods_id)
    if delivery_lock.locked():
        logger.info(
            "声明确认发货等待锁: accountId=%d sId=%s xyGoodsId=%s（前序任务处理中）",
            account_id, s_id, xy_goods_id
        )
    async with delivery_lock:
        # 重置事务快照：调用方传入的 db session 可能已有活跃事务（旧 snapshot），
        # commit() 结束当前事务，后续查询能看到最新已提交数据。
        if hasattr(db, "commit"):
            try:
                await db.commit()
            except Exception:
                if hasattr(db, "rollback"):
                    try:
                        await db.rollback()
                    except Exception:
                        pass

        # === 持锁后去重检查（防止已发货订单被重复发货） ===
        if await _has_existing_realtime_delivery(
            db,
            tenant_id,
            account_id,
            order_id,
            s_id,
            xy_goods_id,
            buyer_user_id,
            "",  # pnm_id
            "",  # delivery_content
        ):
            logger.info(
                "声明确认发货跳过重复处理（已存在发货记录） accountId=%d orderId=%s sId=%s xyGoodsId=%s",
                account_id, order_id, s_id, xy_goods_id
            )
            return
        await _process_delivery_inner(
            db, tenant_id, account_id, msg={},  # msg 仅用于日志，此处为空
            s_id=s_id, sender_user_id=buyer_user_id, receiver_user_id="",
            reminder_url="", reminder_content="", pnm_id="", msg_content="",
            order_id=order_id, xy_goods_id=xy_goods_id,
            buyer_user_id=buyer_user_id, buyer_user_name=buyer_user_name,
            buy_quantity=buy_quantity,
        )
        # 锁内提交：确保 delivery_record INSERT 在锁释放前已对其他会话可见。
        if hasattr(db, "commit"):
            try:
                await db.commit()
            except Exception as commit_err:
                logger.error("声明确认锁内提交失败: %s", commit_err, exc_info=True)
                if hasattr(db, "rollback"):
                    try:
                        await db.rollback()
                    except Exception:
                        pass

    # 绑定 delivery_record_id 到声明会话（查询最近成功的发货记录）
    try:
        record = (await db.execute(
            text("""
                SELECT id FROM delivery_record
                WHERE tenant_id=:tid AND account_id=:aid
                  AND order_id=:oid AND deleted=0
                  AND status=2
                ORDER BY created_time DESC LIMIT 1
            """),
            {"tid": tenant_id, "aid": account_id, "oid": order_id},
        )).first()
        if record:
            await db.execute(
                text("""
                    UPDATE delivery_statement_session
                    SET delivery_record_id=:rid, updated_time=NOW()
                    WHERE id=:id AND tenant_id=:tid
                """),
                {"rid": record[0], "id": session_id, "tid": tenant_id},
            )
    except Exception:
        logger.debug("绑定 delivery_record_id 到声明会话失败 sessionId=%d", session_id, exc_info=True)


async def _execute_segments_delivery(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    order_id: str,
    s_id: str,
    buyer_user_id: str,
    buyer_user_name: str,
    segments: list[dict],
) -> tuple[bool, Optional[str], str]:
    """遍历 segments 逐条发送（文本/图片分别走对应发送函数，严禁合并为一条消息）。

    每条 segment 为 text 或 image 二选一（已在配置端和 _normalize_segments 双重校验）。
    发送规则：
      - text  : 调用 _send_delivery_message（先做变量替换 {buyerUserName} 等）
      - image : 调用 _send_delivery_image（转推闲鱼 CDN + WebSocket 图片消息）
      - 多条之间加 200ms 间隔，避免触发闲鱼 IM 风控

    判定规则：
      - 全部成功 → overall_success=True
      - 部分成功 → overall_success=False（仍触发确认发货，已发送的消息买家能收到）
      - 全部失败 → overall_success=False（不触发确认发货）

    Returns:
        (overall_success, fail_reason, record_content)
        - record_content: 用于 delivery_record.content 的 JSON 审计摘要
    """
    results: list[dict] = []
    success_count = 0
    failure_count = 0
    last_error: Optional[str] = None
    total = len(segments)

    for idx, seg in enumerate(segments):
        seg_type = str(seg.get("type") or "text").lower()
        seg_result: dict = {"index": idx, "type": seg_type}

        if seg_type == "image":
            image_url = str(seg.get("imageUrl") or "")
            seg_result["imageUrl"] = image_url
            try:
                ok, is_transient, cdn_or_error = await _send_delivery_image(
                    db, tenant_id, account_id, s_id, buyer_user_id, image_url,
                )
                if ok:
                    seg_result["status"] = "success"
                    seg_result["cdnUrl"] = cdn_or_error
                    success_count += 1
                else:
                    seg_result["status"] = "failed"
                    seg_result["error"] = cdn_or_error or "图片发送失败"
                    seg_result["transient"] = is_transient
                    failure_count += 1
                    last_error = seg_result["error"]
            except Exception as e:
                seg_result["status"] = "failed"
                seg_result["error"] = str(e)
                failure_count += 1
                last_error = str(e)
                logger.error("图片发货异常: accountId=%d segIdx=%d error=%s", account_id, idx, e)
        else:
            # text 类型：先做变量替换（与原 _execute_text_delivery 一致）
            text_content = str(seg.get("content") or "")
            text_content = text_content.replace("{buyerUserName}", buyer_user_name or "买家")
            text_content = text_content.replace("{orderId}", order_id or "")
            text_content = text_content.replace("{goodsTitle}", "")
            text_content = text_content.replace("{deliveryTime}", time.strftime("%Y-%m-%d %H:%M:%S"))
            seg_result["content"] = text_content
            try:
                ok, is_transient = await _send_delivery_message(
                    account_id, s_id, buyer_user_id, text_content,
                )
                if ok:
                    seg_result["status"] = "success"
                    success_count += 1
                else:
                    seg_result["status"] = "failed"
                    seg_result["error"] = "买家会话连接暂时不可用" if is_transient else "无法向买家发送消息"
                    seg_result["transient"] = is_transient
                    failure_count += 1
                    last_error = seg_result["error"]
            except Exception as e:
                seg_result["status"] = "failed"
                seg_result["error"] = str(e)
                failure_count += 1
                last_error = str(e)
                logger.error("文本发货异常: accountId=%d segIdx=%d error=%s", account_id, idx, e)

        results.append(seg_result)

        # 多条消息之间加 200ms 间隔，避免触发闲鱼 IM 风控（最后一条不需要等待）
        if idx < total - 1:
            await asyncio.sleep(0.2)

    # 判定整体成功与否
    if failure_count == 0:
        overall_success = True
        fail_reason: Optional[str] = None
    elif success_count == 0:
        overall_success = False
        fail_reason = f"全部 {total} 条消息发送失败：{last_error}"
    else:
        # 部分成功：标记为失败，但仍触发确认发货（已发送的消息买家能收到）
        overall_success = False
        fail_reason = f"{failure_count}/{total} 条消息发送失败：{last_error}（其余 {success_count} 条已送达）"

    # 构造审计内容（JSON 摘要，记录每条 segment 的发送结果，便于排查）
    record_content = json.dumps({
        "mode": "segments",
        "total": total,
        "success": success_count,
        "failed": failure_count,
        "segments": results,
    }, ensure_ascii=False)

    logger.info(
        "segments 发货完成: accountId=%d total=%d success=%d failed=%d",
        account_id, total, success_count, failure_count,
    )

    return (overall_success, fail_reason, record_content)


async def _backfill_delivery_record_order_id(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    order_id: str,
    s_id: str,
    buyer_user_id: str,
    xy_goods_id: str,
) -> None:
    """将反查到的 order_id 回写到 delivery_record（原 order_id 为空时）。"""
    if not order_id:
        return
    try:
        await db.execute(
            text("""
                UPDATE delivery_record
                SET order_id = :order_id, status = 2, updated_time = NOW()
                WHERE tenant_id = :tenant_id
                  AND account_id = :account_id
                  AND deleted = 0
                  AND (order_id IS NULL OR order_id = '')
                  AND delivery_timing = :delivery_timing
                  AND REPLACE(JSON_UNQUOTE(JSON_EXTRACT(receiver_info, '$.sid')), '@goofish', '') = REPLACE(:sid, '@goofish', '')
                  AND REPLACE(JSON_UNQUOTE(JSON_EXTRACT(receiver_info, '$.buyerUserId')), '@goofish', '') = REPLACE(:buyer_user_id, '@goofish', '')
                  AND JSON_UNQUOTE(JSON_EXTRACT(receiver_info, '$.xyGoodsId')) = :xy_goods_id
            """),
            {
                "tenant_id": tenant_id,
                "account_id": account_id,
                "order_id": order_id,
                "delivery_timing": DELIVERY_TIMING_AFTER_PAYMENT,
                "sid": s_id,
                "buyer_user_id": buyer_user_id,
                "xy_goods_id": xy_goods_id,
            }
        )
    except Exception as e:
        logger.warning("回写 order_id 到 delivery_record 失败: %s", e)


async def _check_personal_blacklist(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    buyer_user_id: str,
    xy_goods_id: str,
) -> Optional[str]:
    """检查买家是否在个人黑名单中，命中返回原因（否则 None）。

    买家ID做 @goofish 后缀归一化；goods_id 为空串表示该账号全部商品。
    查询失败时按未命中处理（fail-open），不阻塞正常发货。
    """
    try:
        row = (await db.execute(
            text("""
                SELECT reason FROM personal_blacklist
                WHERE tenant_id = :tenant_id
                  AND (account_id = 0 OR account_id = :account_id)
                  AND deleted = 0
                  AND enabled = 1
                  AND REPLACE(buyer_user_id, '@goofish', '') = REPLACE(:buyer_user_id, '@goofish', '')
                  AND (goods_id = '' OR goods_id = :goods_id)
                ORDER BY CASE WHEN account_id = :account_id THEN 0 ELSE 1 END,
                         CASE WHEN goods_id = '' THEN 1 ELSE 0 END,
                         id DESC
                LIMIT 1
            """),
            {
                "tenant_id": tenant_id,
                "account_id": account_id,
                "buyer_user_id": buyer_user_id or "",
                "goods_id": xy_goods_id or "",
            }
        )).mappings().first()
        if not row:
            return None
        reason = str(row.get("reason") or "").strip()
        return reason or "买家在黑名单中"
    except Exception as exc:
        logger.warning(
            "查询个人黑名单失败，按未命中处理 tenantId=%d accountId=%d errorType=%s",
            tenant_id, account_id, type(exc).__name__,
        )
        return None


async def _check_delivery_block_rules(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    buyer_user_id: str,
    xy_goods_id: str,
    order_id: str = "",
) -> Optional[str]:
    """检查发货拦截规则（买家已有订单 / 未确认收货订单）。

    返回拦截原因（否则 None）。查询失败按未命中处理（fail-open），不阻塞正常发货。
    """
    try:
        rows = (await db.execute(
            text("""
                SELECT rule_code, rule_name FROM delivery_block_rule
                WHERE tenant_id = :tenant_id
                  AND deleted = 0
                  AND enabled = 1
                  AND (account_id = 0 OR account_id = :account_id)
                ORDER BY priority ASC, id ASC
            """),
            {"tenant_id": tenant_id, "account_id": account_id},
        )).mappings().all()
        if not rows:
            return None

        normalized_buyer = str(buyer_user_id or "").replace("@goofish", "").strip()
        if not normalized_buyer:
            return None
        current_order_id = str(order_id or "").strip()

        for row in rows:
            code = str(row.get("rule_code") or "")
            if code == "buyer_has_order":
                count = (await db.execute(
                    text("""
                        SELECT COUNT(*) FROM xianyu_trade_order
                        WHERE tenant_id = :tenant_id
                          AND account_id = :account_id
                          AND deleted = 0
                          AND REPLACE(buyer_id, '@goofish', '') = :buyer_id
                          AND order_status <> 5
                          AND (:current_order_id = '' OR external_order_id <> :current_order_id)
                    """),
                    {
                        "tenant_id": tenant_id,
                        "account_id": account_id,
                        "buyer_id": normalized_buyer,
                        "current_order_id": current_order_id,
                    },
                )).scalar() or 0
                if count > 0:
                    return "买家已有其他订单，已拦截发货"
            elif code == "buyer_unconfirmed":
                count = (await db.execute(
                    text("""
                        SELECT COUNT(*) FROM xianyu_trade_order
                        WHERE tenant_id = :tenant_id
                          AND account_id = :account_id
                          AND deleted = 0
                          AND REPLACE(buyer_id, '@goofish', '') = :buyer_id
                          AND order_status = 3
                          AND confirm_time IS NULL
                          AND (:current_order_id = '' OR external_order_id <> :current_order_id)
                    """),
                    {
                        "tenant_id": tenant_id,
                        "account_id": account_id,
                        "buyer_id": normalized_buyer,
                        "current_order_id": current_order_id,
                    },
                )).scalar() or 0
                if count > 0:
                    return "买家存在未确认收货订单，已拦截发货"
        return None
    except Exception as exc:
        logger.warning(
            "查询发货拦截规则失败，按未命中处理 tenantId=%d accountId=%d errorType=%s",
            tenant_id, account_id, type(exc).__name__,
        )
        return None


def _is_order_closed_error(confirm_result: Optional[dict]) -> bool:
    """判断确认发货失败是否因订单已关闭/取消（可触发 card_only 补发）。"""
    if not confirm_result:
        return False
    error_code = str(confirm_result.get("error") or "").upper()
    raw_message = str(confirm_result.get("message") or "")
    closed_code_markers = ("ORDER_CLOSE", "ORDER_CANCEL", "ORDER_STATUS", "CLOSED", "CLOSE", "CANCEL")
    if any(marker in error_code for marker in closed_code_markers):
        return True
    closed_text_markers = ("已关闭", "订单关闭", "关单", "已取消", "ORDER_ALREADY_CLOSED", "ORDER_CLOSED")
    return any(marker in raw_message for marker in closed_text_markers)


async def _pre_confirm_shipment_if_enabled(
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
    delivery_type: str,
) -> tuple[bool, Optional[str]]:
    """“先确认发货再发内容”开关的预确认逻辑。

    返回 (should_abort, pre_resolved_order_id)：
    - (True, None)：确认发货失败，已写入失败记录并通知，调用方必须中止发送；
    - (False, order_id)：确认发货成功，调用方应跳过发送后的重复确认；
    - (False, None)：未开启开关或无法解析订单，调用方走原有“先发送后确认”路径。
    """
    if not rule or not bool(rule.get("confirm_before_send")):
        return False, None

    resolved_order_id = await _resolve_order_id_for_confirm(
        db, tenant_id, account_id, order_id, xy_goods_id, buyer_user_id,
    )
    if not resolved_order_id:
        return False, None

    is_bargain = await _detect_bargain_from_message_or_db(
        db, account_id, resolved_order_id, xy_goods_id, buyer_user_id, rule,
    )
    confirm_result = await _auto_confirm_shipment(
        tenant_id, account_id, resolved_order_id,
        is_bargain=is_bargain,
        xy_goods_id=xy_goods_id,
        buyer_user_id=buyer_user_id,
    )
    if confirm_result and confirm_result.get("success"):
        try:
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
                    "external_order_id": resolved_order_id,
                }
            )
        except Exception as e:
            logger.warning(
                "先确认发货成功后更新本地订单状态失败 tenantId=%d orderId=%s error=%s",
                tenant_id, resolved_order_id, e,
            )
        return False, resolved_order_id

    # “订单已关闭仍补发”配置：确认发货失败但订单已关闭/取消时，继续发送内容（不确认平台发货）
    if _is_order_closed_error(confirm_result) and bool(rule.get("closed_order_still_send")):
        logger.info(
            "先确认发货失败但订单已关闭，按“关闭后仍补发”配置继续发送 tenantId=%d accountId=%d orderId=%s",
            tenant_id, account_id, resolved_order_id,
        )
        return False, resolved_order_id

    fail_reason = f"先确认发货失败，已中止发送：{_friendly_confirm_error(confirm_result)}"
    await _safe_insert_delivery_record(
        db, tenant_id, account_id, order_id, s_id, pnm_id,
        buyer_user_id, buyer_user_name, xy_goods_id, buy_quantity,
        rule_id=rule.get("id"), delivery_type=delivery_type,
        content=None, status=3, fail_reason=fail_reason,
        trigger_source=trigger_source,
        delivery_mode=delivery_type,
        delivery_timing=rule.get("delivery_timing") or DELIVERY_TIMING_AFTER_PAYMENT,
    )
    await _notify_realtime_delivery_failure(
        db=db,
        tenant_id=tenant_id,
        account_id=account_id,
        order_id=resolved_order_id or order_id,
        xy_goods_id=xy_goods_id,
        fail_reason=fail_reason,
    )
    return True, None


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
    # 个人黑名单：命中直接拦截，不发送、不确认平台发货
    blacklist_reason = await _check_personal_blacklist(
        db, tenant_id, account_id, buyer_user_id, xy_goods_id,
    )
    if blacklist_reason:
        fail_reason = f"买家在黑名单中，已拦截发货：{blacklist_reason}"
        await _safe_insert_delivery_record(
            db, tenant_id, account_id, order_id, s_id, pnm_id,
            buyer_user_id, buyer_user_name, xy_goods_id, buy_quantity,
            rule_id=rule.get("id"), delivery_type=MODE_TEXT,
            content=None, status=3, fail_reason=fail_reason,
            trigger_source=trigger_source,
            delivery_mode=MODE_TEXT,
            delivery_timing=rule.get("delivery_timing") or DELIVERY_TIMING_AFTER_PAYMENT,
        )
        await _notify_realtime_delivery_failure(
            db=db,
            tenant_id=tenant_id,
            account_id=account_id,
            order_id=order_id,
            xy_goods_id=xy_goods_id,
            fail_reason=fail_reason,
        )
        return

    # 发货拦截规则（买家已有订单 / 未确认收货订单）
    block_rule_reason = await _check_delivery_block_rules(
        db, tenant_id, account_id, buyer_user_id, xy_goods_id, order_id,
    )
    if block_rule_reason:
        fail_reason = f"{block_rule_reason}：已拦截发货"
        await _safe_insert_delivery_record(
            db, tenant_id, account_id, order_id, s_id, pnm_id,
            buyer_user_id, buyer_user_name, xy_goods_id, buy_quantity,
            rule_id=rule.get("id"), delivery_type=MODE_TEXT,
            content=None, status=3, fail_reason=fail_reason,
            trigger_source=trigger_source,
            delivery_mode=MODE_TEXT,
            delivery_timing=rule.get("delivery_timing") or DELIVERY_TIMING_AFTER_PAYMENT,
        )
        await _notify_realtime_delivery_failure(
            db=db,
            tenant_id=tenant_id,
            account_id=account_id,
            order_id=order_id,
            xy_goods_id=xy_goods_id,
            fail_reason=fail_reason,
        )
        return

    # “先确认发货再发内容”开关：发送前先确认平台发货，失败则中止发送
    should_abort, pre_resolved_order_id = await _pre_confirm_shipment_if_enabled(
        db=db,
        tenant_id=tenant_id,
        account_id=account_id,
        order_id=order_id,
        s_id=s_id,
        pnm_id=pnm_id,
        buyer_user_id=buyer_user_id,
        buyer_user_name=buyer_user_name,
        xy_goods_id=xy_goods_id,
        buy_quantity=buy_quantity,
        rule=rule,
        trigger_source=trigger_source,
        delivery_type=MODE_TEXT,
    )
    if should_abort:
        return
    pre_confirmed = pre_resolved_order_id is not None

    # V1.66: 优先走 segments 多条发送（文本/图片逐条单独发送，不合并为一条消息）
    segments = rule.get("segments") or []
    if segments:
        send_ok, fail_reason, content = await _execute_segments_delivery(
            db, tenant_id, account_id, order_id, s_id, buyer_user_id,
            buyer_user_name, segments,
        )
    else:
        # 原单条正文发送逻辑（向后兼容旧货源，无 segments 时回退）
        content = delivery_content
        content = content.replace("{buyerUserName}", buyer_user_name or "买家")
        content = content.replace("{orderId}", order_id or "")
        content = content.replace("{goodsTitle}", "")
        content = content.replace("{deliveryTime}", time.strftime("%Y-%m-%d %H:%M:%S"))

        send_ok = False
        fail_reason = None
        try:
            send_ok, is_transient = await _send_delivery_message(account_id, s_id, buyer_user_id, content)
            if not send_ok:
                fail_reason = "买家会话连接暂时不可用，系统将自动重试" if is_transient else "无法向买家发送消息，请检查账号登录状态"
        except Exception as e:
            fail_reason = "发送消息时出现异常，系统将自动重试"
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

    if send_ok and not pre_confirmed:
        # 发送成功：尝试反查 order_id（付款消息常不含 orderId），再调用闲鱼确认发货 API
        # 只有平台真正标记为已发货后才更新本地 order_status=3
        # 避免本地标记 3 但闲鱼平台实际未发货的状态不一致问题
        resolved_order_id = await _resolve_order_id_for_confirm(
            db, tenant_id, account_id, order_id, xy_goods_id, buyer_user_id,
        )
        if resolved_order_id:
            is_bargain = await _detect_bargain_from_message_or_db(
                db, account_id, resolved_order_id, xy_goods_id, buyer_user_id, rule
            )
            confirm_result = await _auto_confirm_shipment(
                tenant_id, account_id, resolved_order_id,
                is_bargain=is_bargain,
                xy_goods_id=xy_goods_id,
                buyer_user_id=buyer_user_id,
            )
            if confirm_result and confirm_result.get("success"):
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
                        "external_order_id": resolved_order_id,
                    }
                )
                # 反查到的 order_id 回写到 delivery_record（仅当原 order_id 为空）
                # 用于后续对账与去重命中（_has_existing_realtime_delivery 按 order_id 精确匹配）
                if not order_id:
                    try:
                        await db.execute(
                            text("""
                                UPDATE delivery_record
                                SET order_id = :order_id, updated_time = NOW()
                                WHERE tenant_id = :tenant_id
                                  AND account_id = :account_id
                                  AND deleted = 0
                                  AND (order_id IS NULL OR order_id = '')
                                  AND delivery_timing = :delivery_timing
                                  AND REPLACE(JSON_UNQUOTE(JSON_EXTRACT(receiver_info, '$.sid')), '@goofish', '') = REPLACE(:sid, '@goofish', '')
                                  AND REPLACE(JSON_UNQUOTE(JSON_EXTRACT(receiver_info, '$.buyerUserId')), '@goofish', '') = REPLACE(:buyer_user_id, '@goofish', '')
                                  AND JSON_UNQUOTE(JSON_EXTRACT(receiver_info, '$.xyGoodsId')) = :xy_goods_id
                            """),
                            {
                                "tenant_id": tenant_id,
                                "account_id": account_id,
                                "order_id": resolved_order_id,
                                "delivery_timing": DELIVERY_TIMING_AFTER_PAYMENT,
                                "sid": s_id,
                                "buyer_user_id": buyer_user_id,
                                "xy_goods_id": xy_goods_id,
                            }
                        )
                    except Exception as e:
                        logger.warning("回写 order_id 到 delivery_record 失败: %s", e)
            else:
                # 确认发货失败：发货消息已发送给买家，但闲鱼平台未标记为已发货
                # 保持本地 order_status 不变（仍为待发货），等待下次同步或重试
                logger.warning(
                    "确认发货失败，本地订单状态保持不变: tenantId=%d accountId=%d orderId=%s error=%s",
                    tenant_id, account_id, resolved_order_id,
                    confirm_result.get("error", "UNKNOWN") if confirm_result else "CAPABILITY_UNAVAILABLE",
                )
                await _notify_realtime_delivery_failure(
                    db=db,
                    tenant_id=tenant_id,
                    account_id=account_id,
                    order_id=resolved_order_id,
                    xy_goods_id=xy_goods_id,
                    fail_reason=f"发货消息已发送，但确认发货失败：{confirm_result.get('message', '未知错误') if confirm_result else '确认发货能力不可用'}",
                )
        else:
            # order_id 为空且本地订单表也查不到（订单同步未完成）
            logger.info(
                "发货消息已发送但 order_id 为空且本地反查无果，跳过 confirm_shipment: tenantId=%d accountId=%d xyGoodsId=%s buyer=%s",
                tenant_id, account_id, xy_goods_id, buyer_user_id,
            )
    if send_ok and pre_confirmed:
        if pre_resolved_order_id:
            await _backfill_delivery_record_order_id(
                db, tenant_id, account_id,
                pre_resolved_order_id, s_id, buyer_user_id, xy_goods_id,
            )

    elif not send_ok:
        await _notify_realtime_delivery_failure(
            db=db,
            tenant_id=tenant_id,
            account_id=account_id,
            order_id=order_id,
            xy_goods_id=xy_goods_id,
            fail_reason=(fail_reason or "WebSocket 发送消息失败")
            + ("（平台已确认发货，但内容未发送）" if pre_confirmed else ""),
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

    if not row:
        # 商品不存在时，尝试从订单项表补全最小商品记录，确保发货配置可命中。
        # 场景：WS 实时收到付款消息，但商品尚未同步到 xianyu_goods 表。
        await _ensure_goods_from_order_items(db, tenant_id, account_id, xy_goods_id)
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


async def _ensure_goods_from_order_items(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    external_goods_id: str,
) -> bool:
    """实时发货时发现商品不存在，从订单项表补全最小商品记录。

    与 automation_runtime._ensure_goods_placeholder_from_order_items 逻辑一致，
    确保实时路径和批量路径都能在商品未同步时补全占位记录。
    """
    if not external_goods_id:
        return False

    # 优先从付款消息中的商品信息创建（account_id 已知）
    # 如果订单项表中也没有，则直接用 account_id 创建最简记录
    item_row = (await db.execute(
        text("""
            SELECT oi.goods_title, oi.goods_image, oi.goods_price
            FROM xianyu_trade_order_item oi
            JOIN xianyu_trade_order o ON o.id = oi.order_id AND o.tenant_id = oi.tenant_id
            WHERE oi.tenant_id = :tenant_id
              AND oi.deleted = 0
              AND oi.goods_id = :goods_id
            ORDER BY oi.id DESC LIMIT 1
        """),
        {
            "tenant_id": tenant_id,
            "goods_id": int(external_goods_id) if external_goods_id.isdigit() else 0,
        }
    )).mappings().first()

    title = ""
    image_url = ""
    price = "0"
    if item_row:
        title = str(item_row.get("goods_title") or "")
        image_url = str(item_row.get("goods_image") or "")
        price = str(item_row.get("goods_price") or "0")

    # 防御性查重：INSERT 前确认该商品在任意 deleted 状态下都不存在，
    # 避免对已被软删除（deleted=1）的商品创建 deleted=0 重复记录（幽灵商品根因之一）。
    existing_row = (await db.execute(
        text("""
            SELECT id FROM xianyu_goods
            WHERE tenant_id = :tenant_id AND account_id = :account_id
              AND external_goods_id = :external_goods_id
            LIMIT 1
        """),
        {
            "tenant_id": tenant_id,
            "account_id": account_id,
            "external_goods_id": external_goods_id,
        }
    )).mappings().first()
    if existing_row:
        return False

    try:
        await db.execute(
            text("""
                INSERT INTO xianyu_goods (
                    tenant_id, account_id, external_goods_id, goods_id, title,
                    price, sold_price, cover_pic, image_url, status,
                    deleted, created_time, updated_time
                ) VALUES (
                    :tenant_id, :account_id, :external_goods_id, :goods_id, :title,
                    :price, :price, :image_url, :image_url, 1,
                    0, NOW(), NOW()
                )
            """),
            {
                "tenant_id": tenant_id,
                "account_id": account_id,
                "external_goods_id": external_goods_id,
                "goods_id": external_goods_id,
                "title": (title or f"商品 {external_goods_id}")[:255],
                "price": (price or "0")[:32],
                "image_url": (image_url or None) if image_url else None,
            }
        )
        logger.info(
            "实时发货自动补全商品占位记录 tenantId=%d accountId=%d externalGoodsId=%s",
            tenant_id, account_id, external_goods_id
        )
        return True
    except Exception:
        return False


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

    # 前端和 Java 后端统一使用 "card" 表示卡密发货，Python 侧历史常量为 "kami"。
    # 此处归一化别名，避免 delivery_mode 进入 "未知的发货模式" 分支导致实时发货全部失败。
    _raw_mode = str(timing_config.get("mode") or MODE_TEXT).lower()
    mode = "kami" if _raw_mode == "card" else _raw_mode
    header = str(timing_config.get("header") or "")
    content = str(timing_config.get("content") or "")
    footer = str(timing_config.get("footer") or "")
    source_id = timing_config.get("sourceId")
    source_title = str(timing_config.get("sourceTitle") or "")

    # V1.66: 解析 segments（多条正文 + 图片发货）
    # config_json.payDelivery.segments 由 Java 端 normalizeSegmentsForConfig 写入，是 List[Dict] 形式
    segments_raw = timing_config.get("segments")
    segments = _normalize_segments(segments_raw)

    if mode == MODE_TEXT and source_id:
        source = await _load_text_source(db, tenant_id, source_id)
        if source:
            if not content:
                content = str(source.get("content") or "")
            if not source_title:
                source_title = str(source.get("title") or "")
            # 若商品配置未带 segments，从货源表回填（保证货源修改后实时发货能拿到最新 segments）
            if not segments:
                segments = _normalize_segments(source.get("segments"))

    if mode == MODE_TEXT and not any([header.strip(), content.strip(), footer.strip()]) and not segments:
        return None

    delivery_content = _build_delivery_content(header, content, footer)
    # 保留 SKU 规则列表，供 _apply_sku_rule_override 按 skuId 精确匹配
    sku_rules = config.get("skuRules") if isinstance(config.get("skuRules"), list) else []
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
        "confirm_before_send": timing_config.get("confirmBeforeSend")
        or timing_config.get("confirm_before_send")
        or 0,
        "closed_order_still_send": timing_config.get("closedOrderStillSend")
        or timing_config.get("closed_order_still_send")
        or 0,
        "segment_send": timing_config.get("segmentSend"),
        "segments": segments,
        "_sku_rules": sku_rules,
        "_raw_config": config,
    }


def _normalize_segments(raw: Any) -> list[dict]:
    """规范化 segments 字段为 list[dict]。
    兼容三种输入：
      - List[Dict]（来自 config_json 解析后的 Python 对象）
      - JSON 字符串（来自 delivery_text_source.segments 列）
      - None / 空值
    校验：每个 segment 必须含 type ∈ {text, image}，且 text/image 互斥。
    返回空 list 表示无 segments（执行端回退到单条 content 发送）。
    """
    if not raw:
        return []
    if isinstance(raw, str):
        if not raw.strip():
            return []
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("segments JSON 解析失败，回退到单条发送: raw=%s", raw[:200])
            return []
    if not isinstance(raw, list) or not raw:
        return []
    result: list[dict] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        seg_type = str(item.get("type") or "text").strip().lower()
        if seg_type not in ("text", "image"):
            logger.warning("segments[%d] type 无效: %s，跳过", idx, seg_type)
            continue
        if seg_type == "image":
            url = str(item.get("imageUrl") or "").strip()
            if not url:
                logger.warning("segments[%d] image 类型但 imageUrl 为空，跳过", idx)
                continue
            seg = {"type": "image", "imageUrl": url}
            if item.get("assetId") is not None:
                try:
                    seg["assetId"] = int(item.get("assetId"))
                except (TypeError, ValueError):
                    pass
            result.append(seg)
        else:
            text_content = str(item.get("content") or "").strip()
            if not text_content:
                logger.warning("segments[%d] text 类型但 content 为空，跳过", idx)
                continue
            result.append({"type": "text", "content": text_content})
    return result


def _build_delivery_content(header: str, content: str, footer: str) -> str:
    return "\n".join(
        part for part in [str(header or "").strip(), str(content or "").strip(), str(footer or "").strip()]
        if part
    )


async def _resolve_order_sku_id(
    db: AsyncSession,
    order_id: Optional[str],
    account_id: int,
    xy_goods_id: str,
) -> Optional[str]:
    """反查订单的 skuId，用于多规格商品按 SKU 匹配发货规则。

    查询顺序：
    1. 从 xianyu_trade_order_item 表按 order_id 查 sku_id（若订单同步时已预存）
    2. 调用闲鱼订单详情接口 mtop.taobao.idle.trade.merchant.full.info 反查

    任一方式成功即返回 skuId 字符串；全部失败返回 None（调用方回退商品通用配置）。
    """
    if not order_id:
        return None

    # 1. 先查本地订单项表
    try:
        row = (await db.execute(
            text("""
                SELECT sku_id FROM xianyu_trade_order_item
                WHERE order_id = :order_id AND deleted = 0
                  AND sku_id IS NOT NULL AND sku_id != ''
                LIMIT 1
            """),
            {"order_id": order_id}
        )).mappings().first()
        if row and row.get("sku_id"):
            return str(row["sku_id"])
    except Exception as error:
        logger.debug("查询订单项 sku_id 失败 orderId=%s error=%s", order_id, error)

    # 2. 调用闲鱼订单详情接口反查
    try:
        # 延迟导入避免循环依赖
        from .refund_service import fetch_refund_full_info
        result = await asyncio.to_thread(fetch_refund_full_info, account_id, order_id, 15)
        if not result.get("success"):
            logger.info("订单详情反查 skuId 失败 orderId=%s error=%s",
                        order_id, result.get("error"))
            return None
        data = result.get("data") or {}
        module = data.get("data", {}).get("module") if isinstance(data.get("data"), dict) else None
        if not isinstance(module, dict):
            module = data.get("module") if isinstance(data, dict) else None
        if not isinstance(module, dict):
            return None

        # 从 merchantItemVO 中提取 skuId
        item_vo = module.get("merchantItemVO") or {}
        if isinstance(item_vo, dict):
            sku_id = item_vo.get("skuId")
            if sku_id:
                return str(sku_id)
            # 部分 SKU 信息在 itemInfoLines 中，但格式不固定，暂不解析

        return None
    except Exception as error:
        logger.warning("反查订单 skuId 异常 orderId=%s errorType=%s error=%s",
                       order_id, type(error).__name__, error)
        return None


def _apply_sku_rule_override(rule: dict, sku_id: str) -> dict:
    """按 skuId 在 skuRules 中查找精确规则，覆盖商品通用规则字段。

    匹配到则返回更新后的 rule（原地修改），未匹配则返回原 rule。
    覆盖字段：delivery_mode / delivery_content / card_group_id / source_id 等。
    """
    sku_rules = rule.get("_sku_rules") or []
    if not sku_rules or not sku_id:
        return rule

    matched = None
    for item in sku_rules:
        if not isinstance(item, dict):
            continue
        if str(item.get("skuId") or "") == str(sku_id):
            matched = item
            break

    if not matched:
        # skuId 未命中，尝试按 propertyKey 二次匹配（应对闲鱼返回 skuId 为空的场景）
        # 此处暂不实现 propertyKey 匹配，保持简单
        return rule

    # 从 SKU 规则的 payDelivery 提取配置，覆盖商品通用规则
    timing_config = matched.get("payDelivery") or {}
    if not isinstance(timing_config, dict):
        return rule

    enabled = timing_config.get("enabled")
    if enabled in (0, "0", False, "false", "False", None):
        # SKU 规则明确禁用，保留商品通用配置不变
        return rule

    _raw_mode = str(timing_config.get("mode") or "text").lower()
    mode = "kami" if _raw_mode == "card" else _raw_mode
    header = str(timing_config.get("header") or "")
    content = str(timing_config.get("content") or "")
    footer = str(timing_config.get("footer") or "")

    rule["delivery_mode"] = mode
    rule["delivery_content"] = _build_delivery_content(header, content, footer)
    rule["content"] = rule["delivery_content"]
    rule["card_group_id"] = timing_config.get("cardGroupId")
    rule["source_id"] = timing_config.get("sourceId")
    rule["source_title"] = str(timing_config.get("sourceTitle") or "")
    rule["_sku_matched"] = True
    rule["_matched_sku_id"] = sku_id
    return rule


async def _load_text_source(
    db: AsyncSession,
    tenant_id: int,
    source_id: Any,
) -> Optional[dict]:
    row = (await db.execute(
        text("""
            SELECT id, title, content, remark, segments
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
    """检查是否已存在该订单/会话的实时发货记录（去重核心）。

    去重维度（任一命中即视为已发货/已处理）：
    1. order_id 精确匹配（优先）：同一 order_id 已有 status IN (1,2) 的记录，或 1 小时内的失败记录
    2. 会话+买家+商品 交叉匹配（order_id 为空时兜底）：同一 (sid, buyerUserId, xyGoodsId)
       已有 after_payment 发货记录

    重要：pnmId 是消息级唯一标识（每条 WS 消息不同），不参与去重判断。
    同一订单的付款消息和后续系统推送消息会有不同 pnmId，但属于同一发货单元。
    若 pnmId 参与去重会导致同一订单被重复发货（事故级 Bug）。

    失败记录参与去重（事故级 Bug 修复）：
    原逻辑仅匹配 status IN (1, 2)，导致永久性失败（如"未配置自动发货规则"）
    形成 WS 推送 → 失败 → 不去重 → 闲鱼再推送 → 再失败 的死循环
    （曾出现单订单 30+ 分钟内被重复触发发货 30+ 次）。

    现引入双层去重窗口（72 小时，覆盖闲鱼最长推送周期）：
    - 成功发货（status IN 1,2）：72 小时窗口
    - 失败发货（status = 3）：72 小时窗口

    背景（2026-07-29 事故级 Bug）：
    原窗口成功 10 分钟/失败 1 小时，但闲鱼 WS 对未确认发货的订单会持续推送付款消息，
    推送间隔约 10-11 分钟（略大于 10 分钟窗口）。每次新推送时前一次记录已超出窗口，
    去重失效，形成无限循环。账号 69（768786986）6 小时内对同一商品+买家重复发货 33 次。
    根因是订单同步 API 失败导致 order_id 永远为空，confirm_shipment 无法调用，
    闲鱼平台不知道已发货而持续推送。72 小时窗口确保即使订单同步长期失败也不会重复发货。
    """
    if order_id:
        existing = (await db.execute(
            text("""
                SELECT id
                FROM delivery_record
                WHERE tenant_id = :tenant_id
                  AND account_id = :account_id
                  AND order_id = :order_id
                  AND deleted = 0
                  AND (
                      status IN (1, 2)
                      OR (status = 3 AND created_time >= DATE_SUB(NOW(), INTERVAL 72 HOUR))
                  )
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

    # 归一化：去掉 @goofish 后缀后比较，彻底消除 receiver_info 中 sid/buyerUserId
    # 格式不一致（有的带 @goofish，有的不带）导致的去重失败问题。
    # 用 REPLACE(..., '@goofish', '') 双向归一化，确保匹配稳定。
    #
    # 注意：pnmId 不参与去重（消息级标识，同一订单不同消息的 pnmId 不同）。
    # delivery_content 仅在传入非空时才检查（用于文本模式区分不同声明文案）。
    #
    # delivery_timing 兼容 NULL：历史 bug 导致部分记录的 delivery_timing 为 NULL，
    # 用 (delivery_timing = :delivery_timing OR delivery_timing IS NULL) 兼容旧数据，
    # 确保这些记录也能被去重命中，避免重复发货。
    # 当 order_id 为空时（付款消息 URL 不含 orderId），按会话+买家+商品去重。
    #
    # 双层时间窗口（72 小时，事故级 Bug 修复）：
    # - 成功记录 72 小时窗口：覆盖闲鱼 WS 最长推送周期，防止订单同步失败时
    #   闲鱼持续推送付款消息导致重复发货
    # - 失败记录 72 小时窗口：绝对止血，避免闲鱼周期性推送付款消息时形成死循环
    #
    # 2026-07-29 事故：原窗口成功 10 分钟/失败 1 小时，闲鱼推送间隔约 10-11 分钟，
    # 账号 69 因订单同步 API 失败导致 order_id 永远为空，6 小时内对同一商品+买家
    # 重复发货 33 次。72 小时窗口确保即使订单同步长期失败也不会重复发货。
    # 72 小时后允许重试，避免永久阻塞（如买家重新下单时仍能发货）。
    existing = (await db.execute(
        text("""
            SELECT id
            FROM delivery_record
            WHERE tenant_id = :tenant_id
              AND account_id = :account_id
              AND deleted = 0
              AND (delivery_timing = :delivery_timing OR delivery_timing IS NULL)
              AND REPLACE(JSON_UNQUOTE(JSON_EXTRACT(receiver_info, '$.sid')), '@goofish', '') = REPLACE(:sid, '@goofish', '')
              AND REPLACE(JSON_UNQUOTE(JSON_EXTRACT(receiver_info, '$.buyerUserId')), '@goofish', '') = REPLACE(:buyer_user_id, '@goofish', '')
              AND JSON_UNQUOTE(JSON_EXTRACT(receiver_info, '$.xyGoodsId')) = :xy_goods_id
              AND (:delivery_content = '' OR COALESCE(delivery_content, '') = :delivery_content)
              AND (
                  (status IN (1, 2) AND created_time >= DATE_SUB(NOW(), INTERVAL 72 HOUR))
                  OR (status = 3 AND created_time >= DATE_SUB(NOW(), INTERVAL 72 HOUR))
              )
            LIMIT 1
        """),
        {
            "tenant_id": tenant_id,
            "account_id": account_id,
            "delivery_timing": DELIVERY_TIMING_AFTER_PAYMENT,
            "sid": str(s_id or ""),
            "buyer_user_id": str(buyer_user_id or ""),
            "xy_goods_id": str(xy_goods_id or ""),
            "delivery_content": str(delivery_content or ""),
        }
    )).mappings().first()
    if existing:
        return True

    # 最后一道防线：本地订单表已标记为已发货（order_status=3）即视为已处理。
    # 场景：发货消息已发送 + confirm_shipment 已成功 + xianyu_trade_order.order_status=3
    # 但 delivery_record 因事务回滚/异常未写入；或之前发货走的是非实时路径（如定时任务）。
    # 此时即使 delivery_record 没有匹配记录，也不应再次触发发货。
    #
    # 匹配优先级：
    # 1. order_id 精确匹配（最稳）
    # 2. (account_id, item_id, buyer_id) 交叉匹配（order_id 为空时兜底）
    normalized_buyer = (buyer_user_id or "").replace("@goofish", "")
    try:
        if order_id:
            order_shipped = (await db.execute(
                text("""
                    SELECT 1
                    FROM xianyu_trade_order
                    WHERE tenant_id = :tenant_id
                      AND account_id = :account_id
                      AND external_order_id = :external_order_id
                      AND deleted = 0
                      AND order_status = 3
                    LIMIT 1
                """),
                {
                    "tenant_id": tenant_id,
                    "account_id": account_id,
                    "external_order_id": order_id,
                }
            )).mappings().first()
            if order_shipped:
                logger.info(
                    "去重命中：本地订单已发货(order_status=3) tenantId=%d accountId=%d orderId=%s",
                    tenant_id, account_id, order_id,
                )
                return True
        elif xy_goods_id and normalized_buyer:
            # order_id 为空时按 商品+买家 兜底匹配（限制近 1 小时，避免老订单阻塞新订单）
            order_shipped = (await db.execute(
                text("""
                    SELECT 1
                    FROM xianyu_trade_order
                    WHERE tenant_id = :tenant_id
                      AND account_id = :account_id
                      AND deleted = 0
                      AND item_id = :item_id
                      AND REPLACE(buyer_id, '@goofish', '') = :buyer_id
                      AND order_status = 3
                      AND ship_time >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
                    LIMIT 1
                """),
                {
                    "tenant_id": tenant_id,
                    "account_id": account_id,
                    "item_id": xy_goods_id,
                    "buyer_id": normalized_buyer,
                }
            )).mappings().first()
            if order_shipped:
                logger.info(
                    "去重命中：本地订单已发货(order_status=3, 兜底匹配) tenantId=%d accountId=%d xyGoodsId=%s buyer=%s",
                    tenant_id, account_id, xy_goods_id, buyer_user_id,
                )
                return True
    except Exception as e:
        # 订单状态查询失败不阻塞发货主流程（依赖原 delivery_record 去重逻辑）
        logger.warning(
            "本地订单状态查询异常，跳过 order_status=3 强校验: tenantId=%d accountId=%d error=%s",
            tenant_id, account_id, e,
        )
    return False


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

    错误兜底原则：
    - 每个关键步骤独立 try/except，单点失败不影响已完成的步骤
    - 任何失败都必须留下 delivery_record，让用户看到可理解的失败原因
    - fail_reason 只暴露用户可理解的中文，不暴露 SQL/堆栈/连接串等技术细节
    - 卡密已发送给买家后，即使后续步骤失败也不回滚卡密（避免重复发送）

    重复发货防护（最后一道防线）：
    - 入口处再次检查该订单/会话是否已有成功发货记录
    - 即使上层 _has_existing_realtime_delivery 去重被绕过（如 order_id 为空 +
      pnmId 已移除去重 + 闲鱼重复推送付款消息），此处也能拦截重复认领卡密
    """
    rule_id = rule.get("id") if isinstance(rule, dict) else None

    # Step -2: 内存级并发去重（最终防线）
    # 即使 _get_delivery_lock 因 sid 格式差异（@goofish 后缀）失效，
    # 此处也能拦截同一会话+商品的并发卡密认领。
    # key 归一化与 _get_delivery_lock 保持一致。
    in_flight_key = f"{account_id}:{(s_id or '').replace('@goofish', '')}:{xy_goods_id}"
    async with _delivery_in_flight_guard:
        if in_flight_key in _delivery_in_flight:
            logger.warning(
                "卡密发货内存级去重拦截: tenantId=%d accountId=%d sId=%s xyGoodsId=%s"
                "（同一会话+商品已有发货任务在进行中，跳过）",
                tenant_id, account_id, s_id, xy_goods_id,
            )
            return
        _delivery_in_flight.add(in_flight_key)

    # Step -1: 重复发货最后防线 - 入口处检查是否已发货
    # 背景：用户反馈付款后收到卡密，买家再次发消息会重新发送新卡密。
    # 根因是闲鱼 WS 可能在买家发消息后重新推送付款系统消息（contentType=26），
    # 触发 _process_delivery。上层 _has_existing_realtime_delivery 去重已修复
    # （移除 pnmId 条件），此处作为卡密认领前的最后一道防线，确保万无一失。
    try:
        already_delivered = await _has_existing_realtime_delivery(
            db, tenant_id, account_id, order_id,
            s_id, xy_goods_id, buyer_user_id, pnm_id="",
            delivery_content="",
        )
        if already_delivered:
            logger.warning(
                "卡密发货最后防线拦截重复发货: tenantId=%d accountId=%d orderId=%s sId=%s xyGoodsId=%s buyer=%s"
                "（该订单/会话已有成功发货记录，跳过卡密认领）",
                tenant_id, account_id, order_id, s_id, xy_goods_id, buyer_user_id,
            )
            _delivery_in_flight.discard(in_flight_key)
            return
    except Exception as check_err:
        # 检查失败不阻断主流程（fail-open），由上层去重和卡密原子认领兜底
        logger.warning("卡密发货入口去重检查异常，继续执行: %s", check_err, exc_info=True)

    # 个人黑名单：命中直接拦截，不发送、不认领卡密、不确认平台发货
    blacklist_reason = await _check_personal_blacklist(
        db, tenant_id, account_id, buyer_user_id, xy_goods_id,
    )
    if blacklist_reason:
        fail_reason = f"买家在黑名单中，已拦截发货：{blacklist_reason}"
        await _safe_insert_delivery_record(
            db, tenant_id, account_id, order_id, s_id, pnm_id,
            buyer_user_id, buyer_user_name, xy_goods_id, buy_quantity,
            rule_id=rule_id, delivery_type=MODE_KAMI,
            content=None, status=3, fail_reason=fail_reason,
            trigger_source=trigger_source,
            delivery_mode=MODE_KAMI,
            delivery_timing=rule.get("delivery_timing") or DELIVERY_TIMING_AFTER_PAYMENT,
        )
        await _notify_realtime_delivery_failure(
            db=db,
            tenant_id=tenant_id,
            account_id=account_id,
            order_id=order_id,
            xy_goods_id=xy_goods_id,
            fail_reason=fail_reason,
        )
        _delivery_in_flight.discard(in_flight_key)
        return

    # 发货拦截规则（买家已有订单 / 未确认收货订单）
    block_rule_reason = await _check_delivery_block_rules(
        db, tenant_id, account_id, buyer_user_id, xy_goods_id, order_id,
    )
    if block_rule_reason:
        fail_reason = f"{block_rule_reason}：已拦截发货"
        await _safe_insert_delivery_record(
            db, tenant_id, account_id, order_id, s_id, pnm_id,
            buyer_user_id, buyer_user_name, xy_goods_id, buy_quantity,
            rule_id=rule_id, delivery_type=MODE_KAMI,
            content=None, status=3, fail_reason=fail_reason,
            trigger_source=trigger_source,
            delivery_mode=MODE_KAMI,
            delivery_timing=rule.get("delivery_timing") or DELIVERY_TIMING_AFTER_PAYMENT,
        )
        await _notify_realtime_delivery_failure(
            db=db,
            tenant_id=tenant_id,
            account_id=account_id,
            order_id=order_id,
            xy_goods_id=xy_goods_id,
            fail_reason=fail_reason,
        )
        _delivery_in_flight.discard(in_flight_key)
        return

    # “先确认发货再发内容”开关：发送前先确认平台发货，失败则中止发送（不认领卡密）
    should_abort, pre_resolved_order_id = await _pre_confirm_shipment_if_enabled(
        db=db,
        tenant_id=tenant_id,
        account_id=account_id,
        order_id=order_id,
        s_id=s_id,
        pnm_id=pnm_id,
        buyer_user_id=buyer_user_id,
        buyer_user_name=buyer_user_name,
        xy_goods_id=xy_goods_id,
        buy_quantity=buy_quantity,
        rule=rule,
        trigger_source=trigger_source,
        delivery_type=MODE_KAMI,
    )
    if should_abort:
        _delivery_in_flight.discard(in_flight_key)
        return
    pre_confirmed = pre_resolved_order_id is not None

    # Step 0: 自愈机制 - 回收历史遗留的孤儿卡密
    # 背景：旧版本 _execute_kami_delivery 在认领后（status=1）若发送/确认等步骤异常或容器重启，
    # 可能未触发 _safe_rollback_cards_by_ids，导致卡密永久卡在 status=1 状态。
    # 之后认领 SQL 的 WHERE status=0 永远找不到可用卡密，每次发货都报"卡密库存不足"。
    # 自愈策略：认领前先扫描该 tenant + group 下 status=1 且 used_order_id IS NULL
    #          且 used_time < NOW() - INTERVAL 5 MINUTE 的卡密，自动回滚为 status=0。
    # 5 分钟超时足够安全：正常认领→发送→标记已使用应在数秒内完成，绝不会超过 5 分钟。
    # 带时间保护避免误回收当前正在认领的卡密。
    try:
        reclaim_result = await db.execute(
            text("""
                UPDATE card_item
                SET status = 0, used_order_id = NULL, used_time = NULL, updated_time = NOW()
                WHERE tenant_id = :tenant_id
                  AND deleted = 0
                  AND status = 1
                  AND used_order_id IS NULL
                  AND used_time < (NOW() - INTERVAL 5 MINUTE)
                  AND (:group_id IS NULL OR group_id = :group_id)
            """),
            {
                "tenant_id": tenant_id,
                "group_id": card_group_id,
            }
        )
        reclaimed_count = reclaim_result.rowcount or 0
        if reclaimed_count > 0:
            logger.warning(
                "卡密自愈：回收孤儿卡密 tenantId=%d accountId=%d groupId=%s reclaimedCount=%d",
                tenant_id, account_id, card_group_id, reclaimed_count,
            )
            # 同步刷新该 group 的统计计数（避免 available_count/remain_count 显示错误）
            if card_group_id:
                try:
                    await db.execute(
                        text("""
                            UPDATE card_group g SET
                                total_count = (SELECT COUNT(*) FROM card_item i WHERE i.group_id = g.id AND i.tenant_id = g.tenant_id AND i.deleted = 0),
                                used_count = (SELECT COUNT(*) FROM card_item i WHERE i.group_id = g.id AND i.tenant_id = g.tenant_id AND i.deleted = 0 AND i.status = 2),
                                remain_count = (SELECT COUNT(*) FROM card_item i WHERE i.group_id = g.id AND i.tenant_id = g.tenant_id AND i.deleted = 0 AND i.status = 0),
                                available_count = (SELECT COUNT(*) FROM card_item i WHERE i.group_id = g.id AND i.tenant_id = g.tenant_id AND i.deleted = 0 AND i.status = 0),
                                updated_time = NOW()
                            WHERE g.id = :group_id AND g.tenant_id = :tenant_id
                        """),
                        {"group_id": card_group_id, "tenant_id": tenant_id}
                    )
                except Exception as stats_err:
                    logger.warning("卡密自愈统计刷新失败 tenantId=%d groupId=%s error=%s", tenant_id, card_group_id, stats_err)
    except Exception as reclaim_err:
        # 自愈失败不影响主流程，继续走原认领逻辑
        logger.warning("卡密自愈扫描失败 tenantId=%d groupId=%s error=%s", tenant_id, card_group_id, reclaim_err, exc_info=True)

    # Step 1: 原子认领卡密（UPDATE + LIMIT 1）
    # 注意：order_id 可能为 None（付款消息的 reminder_url 不含 orderId 时），
    # 此时 used_order_id 会被设为 NULL，后续读取/回滚不能依赖 used_order_id 匹配（NULL != NULL）。
    # 修复方案：认领后用 used_time >= claim_before 时间戳精确定位被认领的 card_item id，
    # 后续读取和回滚全部按 id 操作，彻底摆脱对 used_order_id 的依赖。
    from datetime import datetime as _dt
    claim_before = _dt.now()
    claimed_item_ids: list = []
    claimed_count = 0
    try:
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
        # 认领成功后立即按 used_time >= claim_before 精确获取被认领的 card_item id
        if claimed_count > 0:
            id_rows = (await db.execute(
                text("""
                    SELECT id FROM card_item
                    WHERE tenant_id = :tenant_id
                      AND deleted = 0
                      AND status = 1
                      AND used_time >= :claim_before
                      AND (:group_id IS NULL OR group_id = :group_id)
                    ORDER BY id ASC
                    LIMIT :limit
                """),
                {
                    "tenant_id": tenant_id,
                    "group_id": card_group_id,
                    "claim_before": claim_before,
                    "limit": buy_quantity,
                }
            )).mappings().all()
            claimed_item_ids = [int(r["id"]) for r in id_rows]
    except Exception as e:
        logger.error("卡密认领失败 tenantId=%d accountId=%d groupId=%s error=%s", tenant_id, account_id, card_group_id, e, exc_info=True)
        await _safe_insert_delivery_record(
            db, tenant_id, account_id, order_id, s_id, pnm_id,
            buyer_user_id, buyer_user_name, xy_goods_id, buy_quantity,
            rule_id=rule_id, delivery_type=MODE_KAMI,
            content=None, status=3, fail_reason="卡密仓库暂时无法访问，请稍后重试",
            trigger_source=trigger_source,
        )
        await _notify_realtime_delivery_failure(
            db=db, tenant_id=tenant_id, account_id=account_id,
            order_id=order_id, xy_goods_id=xy_goods_id,
            fail_reason="卡密仓库暂时无法访问，请稍后重试",
        )
        _delivery_in_flight.discard(in_flight_key)
        return

    if claimed_count <= 0:
        logger.warning("卡密库存不足: accountId=%d groupId=%s", account_id, card_group_id)
        await _safe_insert_delivery_record(
            db, tenant_id, account_id, order_id, s_id, pnm_id,
            buyer_user_id, buyer_user_name, xy_goods_id, buy_quantity,
            rule_id=rule_id, delivery_type=MODE_KAMI,
            content=None, status=3, fail_reason="卡密库存不足，请及时补充库存",
            trigger_source=trigger_source,
        )
        await _notify_realtime_delivery_failure(
            db=db, tenant_id=tenant_id, account_id=account_id,
            order_id=order_id, xy_goods_id=xy_goods_id,
            fail_reason="卡密库存不足，请及时补充库存",
        )
        _delivery_in_flight.discard(in_flight_key)
        return

    # Step 2: 读取被认领的卡密内容（按 id 精确读取，不依赖 used_order_id）
    card_items = []
    try:
        if claimed_item_ids:
            card_items = (await db.execute(
                text("""
                    SELECT id, card_key, card_value, extra_info
                    FROM card_item
                    WHERE tenant_id = :tenant_id
                      AND deleted = 0
                      AND status = 1
                      AND id IN :ids
                    ORDER BY id ASC
                """).bindparams(bindparam("ids", expanding=True)),
                {"tenant_id": tenant_id, "ids": claimed_item_ids}
            )).mappings().all()
    except Exception as e:
        logger.error("读取已认领卡密失败 tenantId=%d accountId=%d orderId=%s error=%s", tenant_id, account_id, order_id, e, exc_info=True)

    if not card_items:
        # 认领成功但读取失败：按 id 回滚卡密状态，避免库存泄漏
        await _safe_rollback_cards_by_ids(db, tenant_id, claimed_item_ids)
        await _safe_insert_delivery_record(
            db, tenant_id, account_id, order_id, s_id, pnm_id,
            buyer_user_id, buyer_user_name, xy_goods_id, buy_quantity,
            rule_id=rule_id, delivery_type=MODE_KAMI,
            content=None, status=3, fail_reason="卡密读取失败，已自动回滚，请稍后重试",
            trigger_source=trigger_source,
        )
        await _notify_realtime_delivery_failure(
            db=db, tenant_id=tenant_id, account_id=account_id,
            order_id=order_id, xy_goods_id=xy_goods_id,
            fail_reason="卡密读取失败，已自动回滚，请稍后重试",
        )
        _delivery_in_flight.discard(in_flight_key)
        return

    # Step 3: 组装卡密内容（对异常格式做兜底）
    kami_template = (rule.get("kami_delivery_template") if isinstance(rule, dict) else None) or "{kmKey}"
    kami_contents = []
    for item in card_items:
        try:
            card_key = str(item.get("card_key") or "")
            card_value = str(item.get("card_value") or "")
            km_key = card_value if card_value else card_key
            if not km_key or km_key == "None":
                logger.warning("卡密内容为空 itemId=%s orderId=%s，跳过该项", item.get("id"), order_id)
                km_key = "（卡密内容缺失，请联系商家）"
            single_content = kami_template.replace("{kmKey}", km_key)
            kami_contents.append(single_content)
        except Exception as e:
            logger.error("组装卡密内容异常 itemId=%s error=%s", item.get("id"), e, exc_info=True)
            kami_contents.append("（卡密内容生成失败，请联系商家）")

    if not kami_contents:
        await _safe_rollback_cards_by_ids(db, tenant_id, claimed_item_ids)
        await _safe_insert_delivery_record(
            db, tenant_id, account_id, order_id, s_id, pnm_id,
            buyer_user_id, buyer_user_name, xy_goods_id, buy_quantity,
            rule_id=rule_id, delivery_type=MODE_KAMI,
            content=None, status=3, fail_reason="卡密内容组装失败，已自动回滚",
            trigger_source=trigger_source,
        )
        _delivery_in_flight.discard(in_flight_key)
        return

    combined_content = "\n---\n".join(kami_contents)

    # Step 4: 发送到买家（区分临时性错误与永久性错误）
    send_ok = False
    fail_reason = None
    is_transient_error = False  # 临时性错误：连接断开、超时等，可重试
    try:
        send_ok, is_transient_error = await _send_delivery_message(account_id, s_id, buyer_user_id, combined_content)
        if not send_ok:
            if is_transient_error:
                fail_reason = "买家会话连接暂时不可用，系统将自动重试"
            else:
                fail_reason = "无法向买家发送卡密消息，请检查账号登录状态"
    except Exception as e:
        logger.error("卡密发货发送消息异常: accountId=%d error=%s", account_id, e, exc_info=True)
        fail_reason = "发送卡密消息时出现异常，系统将自动重试"
        is_transient_error = True

    # Step 5: 更新卡密状态（发送成功→已使用；发送失败→回滚）
    # 注意：发送失败时回滚卡密，让下次重试可以重新认领
    if send_ok:
        await _safe_mark_cards_used(db, tenant_id, [item["id"] for item in card_items])
    else:
        await _safe_rollback_cards_by_ids(db, tenant_id, claimed_item_ids)

    # Step 6: 更新卡密组统计计数（失败不影响主流程）
    # 注意：必须同时更新 remain_count 和 available_count，前端（卡密仓库/货源库）读取的是 remain_count，
    # 漏更新 remain_count 会导致前端显示的"可用/库存"数量不随卡密使用而减少。
    if card_group_id:
        try:
            await db.execute(
                text("""
                    UPDATE card_group g SET
                        total_count = (SELECT COUNT(*) FROM card_item i WHERE i.group_id = g.id AND i.tenant_id = g.tenant_id AND i.deleted = 0),
                        used_count = (SELECT COUNT(*) FROM card_item i WHERE i.group_id = g.id AND i.tenant_id = g.tenant_id AND i.deleted = 0 AND i.status = 2),
                        remain_count = (SELECT COUNT(*) FROM card_item i WHERE i.group_id = g.id AND i.tenant_id = g.tenant_id AND i.deleted = 0 AND i.status = 0),
                        available_count = (SELECT COUNT(*) FROM card_item i WHERE i.group_id = g.id AND i.tenant_id = g.tenant_id AND i.deleted = 0 AND i.status = 0),
                        updated_time = NOW()
                    WHERE g.id = :group_id AND g.tenant_id = :tenant_id
                """),
                {"group_id": card_group_id, "tenant_id": tenant_id}
            )
        except Exception as e:
            logger.warning("更新卡密组统计失败 tenantId=%d groupId=%s error=%s", tenant_id, card_group_id, e)

    # Step 7: 记录发货记录（必须成功，让用户看到发货结果）
    # status: 1=处理中(已发送待确认), 2=成功, 3=失败
    record_status = 2 if send_ok else 3
    if send_ok and not order_id:
        # 发送成功但无 order_id，无法确认发货，标记为处理中
        record_status = 1
    await _safe_insert_delivery_record(
        db, tenant_id, account_id, order_id, s_id, pnm_id,
        buyer_user_id, buyer_user_name, xy_goods_id, buy_quantity,
        rule_id=rule_id, delivery_type=MODE_KAMI,
        content=combined_content, status=record_status,
        fail_reason=fail_reason, trigger_source=trigger_source,
    )

    # Step 8: 确认发货（仅在发送成功时执行；order_id 为空时反查本地订单表）
    # 卡密已发送给买家，即使确认发货失败也不影响卡密状态（卡密已消费）
    if send_ok and not pre_confirmed:
        resolved_order_id = await _resolve_order_id_for_confirm(
            db, tenant_id, account_id, order_id, xy_goods_id, buyer_user_id,
        )
        if not resolved_order_id:
            logger.info(
                "卡密已发送但 order_id 为空且本地反查无果，跳过 confirm_shipment: tenantId=%d accountId=%d xyGoodsId=%s buyer=%s",
                tenant_id, account_id, xy_goods_id, buyer_user_id,
            )
        else:
            try:
                is_bargain = await _detect_bargain_from_message_or_db(
                    db, account_id, resolved_order_id, xy_goods_id, buyer_user_id, rule
                )
                confirm_result = await _auto_confirm_shipment(
                    tenant_id, account_id, resolved_order_id,
                    is_bargain=is_bargain,
                    xy_goods_id=xy_goods_id,
                    buyer_user_id=buyer_user_id,
                )
                if confirm_result and confirm_result.get("success"):
                    # 反查到 order_id 后，更新卡密 used_order_id（用于对账）+ 更新本地订单状态
                    try:
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
                                "external_order_id": resolved_order_id,
                            }
                        )
                    except Exception as e:
                        logger.warning("更新本地订单状态失败 tenantId=%d orderId=%s error=%s", tenant_id, resolved_order_id, e)
                    # 反查到的 order_id 回写到 delivery_record（仅当原 order_id 为空）
                    # 用于后续对账与去重命中（_has_existing_realtime_delivery 按 order_id 精确匹配）
                    if not order_id:
                        try:
                            await db.execute(
                                text("""
                                    UPDATE delivery_record
                                    SET order_id = :order_id, status = 2, updated_time = NOW()
                                    WHERE tenant_id = :tenant_id
                                      AND account_id = :account_id
                                      AND deleted = 0
                                      AND (order_id IS NULL OR order_id = '')
                                      AND delivery_timing = :delivery_timing
                                      AND REPLACE(JSON_UNQUOTE(JSON_EXTRACT(receiver_info, '$.sid')), '@goofish', '') = REPLACE(:sid, '@goofish', '')
                                      AND REPLACE(JSON_UNQUOTE(JSON_EXTRACT(receiver_info, '$.buyerUserId')), '@goofish', '') = REPLACE(:buyer_user_id, '@goofish', '')
                                      AND JSON_UNQUOTE(JSON_EXTRACT(receiver_info, '$.xyGoodsId')) = :xy_goods_id
                                """),
                                {
                                    "tenant_id": tenant_id,
                                    "account_id": account_id,
                                    "order_id": resolved_order_id,
                                    "delivery_timing": DELIVERY_TIMING_AFTER_PAYMENT,
                                    "sid": s_id,
                                    "buyer_user_id": buyer_user_id,
                                    "xy_goods_id": xy_goods_id,
                                }
                            )
                        except Exception as e:
                            logger.warning("回写 order_id 到 delivery_record 失败: %s", e)
                else:
                    # 确认发货失败：卡密已发送给买家，但闲鱼平台未标记为已发货
                    # 保持本地 order_status 不变，等待下次同步或重试
                    friendly_error = _friendly_confirm_error(confirm_result)
                    logger.warning(
                        "卡密发货确认失败，本地订单状态保持不变: tenantId=%d accountId=%d orderId=%s error=%s",
                        tenant_id, account_id, resolved_order_id,
                        confirm_result.get("error", "UNKNOWN") if confirm_result else "CAPABILITY_UNAVAILABLE",
                    )
                    # 不向用户告警"确认发货失败"，因为卡密已发给买家，用户感知上是"已发货"
                    # 仅记录日志，由下次订单同步自动校正平台状态
            except Exception as e:
                logger.error("确认发货流程异常 tenantId=%d orderId=%s error=%s", tenant_id, resolved_order_id, e, exc_info=True)
                # 确认发货异常不影响卡密已发送的事实，仅记录日志

    if send_ok and pre_confirmed:
        if pre_resolved_order_id:
            await _backfill_delivery_record_order_id(
                db, tenant_id, account_id,
                pre_resolved_order_id, s_id, buyer_user_id, xy_goods_id,
            )

    # 清理内存级去重标记
    _delivery_in_flight.discard(in_flight_key)


async def _safe_insert_delivery_record(
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
    delivery_mode: Optional[str] = None,
    delivery_timing: Optional[str] = DELIVERY_TIMING_AFTER_PAYMENT,
) -> None:
    """安全地插入发货记录，失败时仅记录日志不抛出异常。

    delivery_timing 默认为 after_payment：所有实时发货均为付款后触发，
    必须正确写入此值，否则 _has_existing_realtime_delivery 的去重查询
    (WHERE delivery_timing = 'after_payment') 匹配不到 NULL，导致重复发货。
    """
    try:
        await _insert_delivery_record(
            db, tenant_id, account_id, order_id, s_id, pnm_id,
            buyer_user_id, buyer_user_name, xy_goods_id, buy_quantity,
            rule_id=rule_id, delivery_type=delivery_type,
            content=content, status=status, fail_reason=fail_reason,
            trigger_source=trigger_source,
            delivery_mode=delivery_mode,
            delivery_timing=delivery_timing,
        )
    except Exception as e:
        logger.error(
            "写入发货记录失败 tenantId=%d accountId=%d orderId=%s status=%s error=%s",
            tenant_id, account_id, order_id, status, e, exc_info=True,
        )


async def _safe_rollback_cards_by_ids(
    db: AsyncSession,
    tenant_id: int,
    card_item_ids: list,
) -> None:
    """按 card_item id 精确回滚卡密状态（不依赖 used_order_id）。

    用于 order_id 为空（付款消息 reminder_url 不含 orderId）时，
    避免 NULL != NULL 导致回滚 WHERE 条件不匹配的问题。
    """
    if not card_item_ids:
        return
    try:
        await db.execute(
            text("""
                UPDATE card_item
                SET status = 0, used_order_id = NULL, used_time = NULL, updated_time = NOW()
                WHERE tenant_id = :tenant_id
                  AND deleted = 0
                  AND status = 1
                  AND id IN :ids
            """).bindparams(bindparam("ids", expanding=True)),
            {"tenant_id": tenant_id, "ids": card_item_ids}
        )
    except Exception as e:
        logger.error(
            "按 id 回滚已认领卡密失败 tenantId=%d ids=%s error=%s（需人工检查卡密状态）",
            tenant_id, card_item_ids, e, exc_info=True,
        )


async def _safe_rollback_claimed_cards(
    db: AsyncSession,
    tenant_id: int,
    order_id: Optional[str],
) -> None:
    """安全地回滚已认领的卡密状态，失败时仅记录日志。"""
    if not order_id:
        return
    try:
        await db.execute(
            text("""
                UPDATE card_item
                SET status = 0, used_order_id = NULL, used_time = NULL, updated_time = NOW()
                WHERE tenant_id = :tenant_id
                  AND used_order_id = :order_id
                  AND deleted = 0
                  AND status = 1
            """),
            {"tenant_id": tenant_id, "order_id": order_id}
        )
    except Exception as e:
        logger.error(
            "回滚已认领卡密失败 tenantId=%d orderId=%s error=%s（需人工检查卡密状态）",
            tenant_id, order_id, e, exc_info=True,
        )


async def _safe_mark_cards_used(
    db: AsyncSession,
    tenant_id: int,
    card_ids: list,
) -> None:
    """安全地将卡密标记为已使用，失败时仅记录日志。

    标记 status=2（已使用）+ is_used=1，保留 deleted=0（不从卡密仓库移除）：
    - status=2 保留卡密的"已使用"状态，便于审计追溯
    - is_used=1 与 Java 侧 updateStatus/updateStatusOnly 逻辑一致
    - deleted=0 使已发送卡密仍可在卡密明细、使用记录、库存统计中被查询和统计
    - 总量(total_count)保持不变，可用量(remain_count)=总量-已使用量，已使用量(used_count)正确递增
    - delivery_record 中的 delivery_content 仍保留卡密内容，可审计
    """
    if not card_ids:
        return
    for card_id in card_ids:
        try:
            await db.execute(
                text("""
                    UPDATE card_item
                    SET status = 2, is_used = 1, updated_time = NOW()
                    WHERE id = :id AND tenant_id = :tenant_id
                """),
                {"id": card_id, "tenant_id": tenant_id}
            )
        except Exception as e:
            logger.error(
                "标记卡密为已使用失败 tenantId=%d cardId=%s error=%s（卡密已发送但状态未更新，需人工检查）",
                tenant_id, card_id, e, exc_info=True,
            )


def _friendly_confirm_error(confirm_result: Optional[dict]) -> str:
    """将确认发货的错误结果转换为用户友好的消息。"""
    if not confirm_result:
        return "闲鱼平台确认发货服务暂时不可用，系统将自动重试"
    error_code = str(confirm_result.get("error") or "").upper()
    raw_message = str(confirm_result.get("message") or "")
    # 已知的闲鱼错误码映射
    if "TOKEN" in error_code or "LOGIN" in error_code or "AUTH" in error_code:
        return "账号登录已过期，请重新登录后系统将自动完成发货确认"
    if "RATE" in error_code or "FREQ" in error_code or "429" in error_code:
        return "闲鱼平台请求频率限制，系统将稍后自动重试确认发货"
    if "ORDER" in error_code and ("CLOSE" in error_code or "CANCEL" in error_code):
        return "订单已关闭，无法在闲鱼平台标记发货（卡密已发送给买家）"
    if "CAPABILITY_UNAVAILABLE" in error_code:
        return "闲鱼确认发货服务暂时不可用，系统将自动重试"
    # 兜底：不直接暴露原始 message（可能含技术细节）
    return "闲鱼平台确认发货失败，系统将自动重试"


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
        content="[自定义发货-不发送消息]", status=2,
        fail_reason=None, trigger_source=trigger_source,
    )


async def _send_delivery_message(
    account_id: int,
    s_id: str,
    buyer_user_id: str,
    content: str,
) -> tuple:
    """通过WebSocket发送发货消息给买家。

    Args:
        account_id: 闲鱼账号ID
        s_id: 会话ID
        buyer_user_id: 买家用户ID
        content: 发货内容

    Returns:
        (success, is_transient) 元组
        - success: True 表示发送成功
        - is_transient: True 表示失败是临时性的（连接断开、超时），可重试；
                        False 表示永久性错误（参数缺失、会话不存在），不可重试
    """
    # 参数校验：避免发送空内容或无效参数
    if not content or not content.strip():
        logger.warning("发货消息内容为空，跳过发送: accountId=%d", account_id)
        return (False, False)

    if not s_id or not buyer_user_id:
        logger.warning("会话ID或买家ID为空，无法发送: accountId=%d sId=%s buyer=%s", account_id, s_id, buyer_user_id)
        return (False, False)

    client = ws_manager.get_client(account_id)
    if not client or not client.is_connected:
        logger.warning("WebSocket未连接，无法发送消息: accountId=%d", account_id)
        # 连接未建立是临时性错误，可重试
        return (False, True)

    if not client._sid:
        logger.warning("WebSocket未注册（无sid），无法发送消息: accountId=%d", account_id)
        # sid 未注册通常是连接刚建立还未完成握手，临时性错误
        return (False, True)

    # 构造 cid 和 to_id（格式: xxx@goofish）
    # s_id 可能已经带 @goofish 后缀，也可能不带
    cid = s_id if s_id.endswith("@goofish") else f"{s_id}@goofish"
    to_id = buyer_user_id if buyer_user_id.endswith("@goofish") else f"{buyer_user_id}@goofish"

    logger.info(
        "发送发货消息: accountId=%d cid=%s to_id=%s contentLen=%d",
        account_id, cid, to_id, len(content)
    )

    try:
        result = await client.send_text_message(cid=cid, to_id=to_id, text=content)
    except asyncio.TimeoutError:
        logger.warning("发货消息发送超时: accountId=%d cid=%s", account_id, cid)
        # 超时是临时性错误
        return (False, True)
    except asyncio.CancelledError:
        logger.warning("发货消息发送被取消: accountId=%d cid=%s", account_id, cid)
        raise
    except Exception as e:
        logger.warning("发货消息发送异常: accountId=%d errorType=%s error=%s", account_id, type(e).__name__, e)
        # 网络类异常视为临时性错误
        return (False, True)

    code = result.get("code", 500)
    error_msg = str(result.get("error") or "")

    if code == 200:
        logger.info("发货消息发送成功: accountId=%d", account_id)
        return (True, False)
    else:
        # 根据错误类型判断是否可重试
        # 连接断开、超时、未注册等属于临时性错误
        transient_keywords = ["未连接", "断开", "重连", "超时", "timeout", "未注册", "无 sid", "无sid"]
        is_transient = any(kw in error_msg for kw in transient_keywords)
        logger.warning(
            "发货消息发送失败: accountId=%d code=%s error=%s transient=%s",
            account_id, code, error_msg, is_transient,
        )
        return (False, is_transient)


async def _send_delivery_image(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    s_id: str,
    buyer_user_id: str,
    image_url: str,
) -> tuple[bool, bool, Optional[str]]:
    """通过 WebSocket 发送图片发货消息给买家。

    复用在线消息页面的图片发送链路：
      1. 读取本地 /uploads/ 图片的宽高
      2. 转推到闲鱼 CDN（_resolve_outbound_image_url）
      3. 调用 client.send_image_message 发送 WebSocket 图片消息

    Args:
        db: 数据库会话（用于读取账号 Cookie 和图片资产租户校验）
        tenant_id: 租户ID
        account_id: 闲鱼账号ID
        s_id: 会话ID
        buyer_user_id: 买家用户ID
        image_url: 图片 URL（本地 /uploads/images/... 或闲鱼 CDN URL）

    Returns:
        (success, is_transient, cdn_url_or_error) 元组
        - success: True 表示发送成功
        - is_transient: True 表示失败是临时性的（连接断开、CDN 上传失败），可重试；
                        False 表示永久性错误（参数缺失、URL 非法），不可重试
        - cdn_url_or_error: 成功时为闲鱼 CDN URL（用于 delivery_record 审计），
                            失败时为错误信息
    """
    if not image_url or not image_url.strip():
        logger.warning("图片发货 URL 为空，跳过发送: accountId=%d", account_id)
        return (False, False, "图片 URL 为空")

    if not s_id or not buyer_user_id:
        logger.warning("会话ID或买家ID为空，无法发送图片: accountId=%d sId=%s buyer=%s",
                       account_id, s_id, buyer_user_id)
        return (False, False, "会话ID或买家ID为空")

    client = ws_manager.get_client(account_id)
    if not client or not client.is_connected:
        logger.warning("WebSocket未连接，无法发送图片消息: accountId=%d", account_id)
        return (False, True, "WebSocket未连接")
    if not client._sid:
        logger.warning("WebSocket未注册（无sid），无法发送图片消息: accountId=%d", account_id)
        return (False, True, "WebSocket未注册")

    cid = s_id if s_id.endswith("@goofish") else f"{s_id}@goofish"
    to_id = buyer_user_id if buyer_user_id.endswith("@goofish") else f"{buyer_user_id}@goofish"

    # 延迟 import：复用 misc.py 的图片转推逻辑（本地 /uploads/ → 闲鱼 CDN）
    # 避免模块加载顺序问题和服务层对路由层的硬依赖
    try:
        from ..api.v1.routes.misc import (
            _resolve_outbound_image_dimensions,
            _resolve_outbound_image_url,
        )
    except ImportError as e:
        logger.error("无法 import 图片转推模块: %s", e)
        return (False, False, "图片转推模块不可用")

    # 步骤1: 读取本地图片宽高（用于消息体，闲鱼 IM 协议要求带 width/height）
    try:
        image_width, image_height = await asyncio.to_thread(
            _resolve_outbound_image_dimensions, image_url, tenant_id
        )
    except Exception as e:
        logger.warning("读取图片尺寸失败，使用默认 800x600: %s", e)
        image_width, image_height = 800, 600

    # 步骤2: 转推到闲鱼 CDN（如果是 /uploads/ 本地路径；已是 https URL 则原样返回）
    try:
        cdn_url = await _resolve_outbound_image_url(db, tenant_id, account_id, image_url)
    except ValueError as e:
        # ValueError 通常是：URL 非法、图片资产不存在、租户不匹配 → 永久性错误
        logger.warning("图片转推闲鱼 CDN 失败（永久错误）: accountId=%d error=%s", account_id, e)
        return (False, False, str(e))
    except Exception as e:
        # 其他异常（网络、CDN 上传失败）→ 临时性错误，可重试
        logger.warning("图片转推异常（临时错误）: accountId=%d errorType=%s error=%s",
                       account_id, type(e).__name__, e)
        return (False, True, f"图片转推异常: {e}")

    # 步骤3: 通过 WebSocket 发送图片消息
    logger.info(
        "发送图片发货消息: accountId=%d cid=%s to_id=%s cdnUrl=%s dimensions=%dx%d",
        account_id, cid, to_id, cdn_url, image_width, image_height,
    )

    try:
        result = await client.send_image_message(
            cid=cid, to_id=to_id, image_url=cdn_url,
            width=image_width, height=image_height,
        )
    except asyncio.TimeoutError:
        logger.warning("图片发货消息发送超时: accountId=%d cid=%s", account_id, cid)
        return (False, True, "发送图片超时")
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.warning("图片发货消息发送异常: accountId=%d errorType=%s error=%s",
                       account_id, type(e).__name__, e)
        return (False, True, f"发送图片异常: {e}")

    code = result.get("code", 500)
    error_msg = str(result.get("error") or "")

    if code == 200:
        logger.info("图片发货消息发送成功: accountId=%d cdnUrl=%s", account_id, cdn_url)
        return (True, False, cdn_url)
    else:
        transient_keywords = ["未连接", "断开", "重连", "超时", "timeout", "未注册", "无 sid", "无sid"]
        is_transient = any(kw in error_msg for kw in transient_keywords)
        logger.warning(
            "图片发货消息发送失败: accountId=%d code=%s error=%s transient=%s",
            account_id, code, error_msg, is_transient,
        )
        return (False, is_transient, error_msg or "图片消息发送失败")


async def _detect_bargain_from_message_or_db(
    db: AsyncSession,
    account_id: int,
    order_id: Optional[str],
    xy_goods_id: str,
    buyer_user_id: str,
    rule: Optional[dict] = None,
) -> bool:
    """判断订单是否为小刀订单。

    优先从数据库 xianyu_trade_order.is_bargain 字段读取，
    其次从发货规则中的 trigger_source 推断（bargain 触发的视为小刀订单）。
    """
    # 1. 从数据库查 is_bargain 字段
    if order_id:
        try:
            row = (await db.execute(
                text("""
                    SELECT is_bargain FROM xianyu_trade_order
                    WHERE account_id = :account_id
                      AND external_order_id = :external_order_id
                      AND deleted = 0
                    LIMIT 1
                """),
                {"account_id": account_id, "external_order_id": order_id},
            )).mappings().first()
            if row and int(row.get("is_bargain") or 0) == 1:
                return True
        except Exception:
            logger.debug("查询 is_bargain 失败 accountId=%d orderId=%s", account_id, order_id, exc_info=True)

    # 2. 从规则中的 trigger_source 推断
    if rule and isinstance(rule, dict):
        trigger_source = str(rule.get("trigger_source") or "")
        if trigger_source == "bargain":
            return True

    return False


async def _resolve_order_id_for_confirm(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    order_id: Optional[str],
    xy_goods_id: str,
    buyer_user_id: str,
) -> Optional[str]:
    """发货后用于确认发货接口的 order_id 解析（双状态架构核心）。

    付款消息的 reminderUrl 经常不含 orderId（只有 itemId/sid/peerUserId），
    导致 _execute_text_delivery / _execute_kami_delivery 跳过 confirm_shipment，
    平台未标记为已发货 → 下次同步又把订单拉回待发货 → 重复触发生命循环。

    本函数在 order_id 为空时按以下优先级解析：
    1. 反查本地 xianyu_trade_order 表的 external_order_id
    2. 调用闲鱼 API 实时查询订单列表（兜底，当订单同步失败导致本地表为空时）

    解析失败返回 None，调用方应保持原有"跳过 confirm_shipment"行为，
    但此时 72 小时去重窗口会防止重复发货。

    2026-07-29 事故级 Bug 修复：
    账号69（768786986）因订单同步 API 长期失败，xianyu_trade_order 表为空，
    导致 order_id 永远为空，confirm_shipment 被跳过，闲鱼平台不知道已发货，
    持续推送付款消息。新增闲鱼 API 实时查询兜底，确保 confirm_shipment 不被跳过。
    """
    if order_id:
        return order_id
    if not xy_goods_id or not buyer_user_id:
        return None

    normalized_buyer = buyer_user_id.replace("@goofish", "")

    # === 第一层：反查本地 xianyu_trade_order 表 ===
    try:
        row = (await db.execute(
            text("""
                SELECT external_order_id
                FROM xianyu_trade_order
                WHERE tenant_id = :tenant_id
                  AND account_id = :account_id
                  AND deleted = 0
                  AND item_id = :item_id
                  AND REPLACE(buyer_id, '@goofish', '') = :buyer_id
                  AND external_order_id IS NOT NULL
                  AND external_order_id != ''
                ORDER BY (order_status = 3) ASC,
                         (delivery_status = 'shipped') ASC,
                         pay_time DESC,
                         id DESC
                LIMIT 1
            """),
            {
                "tenant_id": tenant_id,
                "account_id": account_id,
                "item_id": xy_goods_id,
                "buyer_id": normalized_buyer,
            }
        )).mappings().first()
        if row and row.get("external_order_id"):
            resolved = str(row["external_order_id"]).strip()
            logger.info(
                "反查订单ID成功(本地表): tenantId=%d accountId=%d xyGoodsId=%s buyer=%s → orderId=%s",
                tenant_id, account_id, xy_goods_id, buyer_user_id, resolved,
            )
            return resolved
    except Exception as e:
        logger.warning(
            "反查订单ID异常(本地表): tenantId=%d accountId=%d xyGoodsId=%s buyer=%s error=%s",
            tenant_id, account_id, xy_goods_id, buyer_user_id, e,
        )

    # === 第二层：调用闲鱼 API 实时查询订单列表（兜底）===
    # 场景：订单同步 API 失败导致本地 xianyu_trade_order 表为空，
    # 但发货消息已发送给买家，必须调用 confirm_shipment 更新闲鱼发货状态，
    # 否则闲鱼平台不知道已发货会持续推送付款消息。
    try:
        resolved = await _resolve_order_id_from_remote_api(
            account_id, xy_goods_id, normalized_buyer,
        )
        if resolved:
            logger.info(
                "反查订单ID成功(闲鱼API): tenantId=%d accountId=%d xyGoodsId=%s buyer=%s → orderId=%s",
                tenant_id, account_id, xy_goods_id, buyer_user_id, resolved,
            )
            return resolved
    except Exception as e:
        logger.warning(
            "反查订单ID异常(闲鱼API): tenantId=%d accountId=%d xyGoodsId=%s buyer=%s error=%s",
            tenant_id, account_id, xy_goods_id, buyer_user_id, e,
        )

    logger.warning(
        "反查订单ID失败(本地表+闲鱼API均无果): tenantId=%d accountId=%d xyGoodsId=%s buyer=%s",
        tenant_id, account_id, xy_goods_id, buyer_user_id,
    )
    return None


async def _resolve_order_id_from_remote_api(
    account_id: int,
    xy_goods_id: str,
    normalized_buyer: str,
) -> Optional[str]:
    """从闲鱼 API 实时查询订单列表，按 item_id + buyer_id 筛选 order_id。

    当本地 xianyu_trade_order 表为空（订单同步失败）时，作为兜底方案
    实时调用闲鱼 API 获取 order_id，用于后续 confirm_shipment 调用。

    查询策略：
    - 拉取最近 1 页订单（30 条），按 item_id + buyer_id 精确匹配
    - 如果第一页未命中，拉取第二页（最多 2 页，避免阻塞发货流程太久）
    """
    from .xianyu_api_service import fetch_sold_orders_page

    for page_number in (1, 2):
        try:
            result = await asyncio.to_thread(
                fetch_sold_orders_page,
                account_id,
                page_number,
                30,
                "ALL",
            )
            if not result or not result.get("success"):
                logger.debug(
                    "闲鱼API查询订单列表失败 page=%d accountId=%d: %s",
                    page_number, account_id,
                    result.get("message", "UNKNOWN") if result else "NONE",
                )
                break

            payload = result.get("data") or {}
            items = payload.get("items") or []
            for item in items:
                parsed = _parse_remote_order_item_for_resolve(item)
                if not parsed:
                    continue
                item_id = str(parsed.get("itemId") or "").strip()
                buyer_id = str(parsed.get("buyerId") or "").strip().replace("@goofish", "")
                order_id = str(parsed.get("orderId") or "").strip()
                if (item_id == xy_goods_id
                    and buyer_id == normalized_buyer
                    and order_id):
                    return order_id

            # 如果没有下一页，停止查询
            if not payload.get("nextPage"):
                break
        except Exception as e:
            logger.debug(
                "闲鱼API查询订单列表异常 page=%d accountId=%d: %s",
                page_number, account_id, e,
            )
            break

    return None


def _parse_remote_order_item_for_resolve(item: dict) -> Optional[dict]:
    """从闲鱼 API 返回的订单列表项中提取 itemId/buyerId/orderId。

    简化版的 _parse_remote_sold_order_item，仅用于 order_id 解析兜底。
    """
    if not isinstance(item, dict):
        return None
    common = item.get("commonData") if isinstance(item.get("commonData"), dict) else {}
    buyer_info = item.get("buyerInfoVO") if isinstance(item.get("buyerInfoVO"), dict) else {}
    item_info = item.get("itemInfoVO") if isinstance(item.get("itemInfoVO"), dict) else {}
    item_buy_info = common.get("itemBuyInfo") if isinstance(common.get("itemBuyInfo"), dict) else {}

    order_id = str(common.get("orderId") or "").strip()
    if not order_id:
        return None

    item_id = str(
        common.get("itemId")
        or item_info.get("itemId")
        or item_buy_info.get("itemId")
        or ""
    ).strip()

    buyer_id = str(
        buyer_info.get("buyerUserId")
        or buyer_info.get("userId")
        or common.get("buyerId")
        or ""
    ).strip()

    return {
        "orderId": order_id,
        "itemId": item_id,
        "buyerId": buyer_id,
    }


async def _auto_confirm_shipment(
    tenant_id: int,
    account_id: int,
    order_id: str,
    is_bargain: bool = False,
    xy_goods_id: Optional[str] = None,
    buyer_user_id: Optional[str] = None,
):
    """通过统一能力门禁请求确认发货。

    小刀订单（is_bargain=True）走免拼发货接口（mtop.idle.groupon.activity.seller.freeshipping），
    普通订单走虚拟发货接口（mtop.taobao.idle.logistic.consign.dummy）。
    小刀订单必须提供 xy_goods_id 和 buyer_user_id。
    """
    try:
        from .xianyu_api_service import confirm_order_shipment

        # confirm_order_shipment 内部发起同步 MTOP HTTP 请求，必须放到线程池执行
        # 否则会阻塞事件循环，导致 WS 心跳停滞、其他账号消息排队、滑块求解卡死。
        # 参考：ws_delivery_handler.py 第 362/1347/2515 行、internal.py 第 490 行均使用 asyncio.to_thread。
        result = await asyncio.to_thread(
            confirm_order_shipment,
            account_id,
            order_id,
            is_bargain=is_bargain,
            item_id=xy_goods_id,
            buyer_id=buyer_user_id,
        )
        if result and result.get("success"):
            ship_method = result.get("ship_method", "freeshipping" if is_bargain else "consign")
            logger.info(
                "确认发货成功: accountId=%d orderId=%s isBargain=%s method=%s",
                account_id, order_id, is_bargain, ship_method,
            )
        else:
            logger.warning(
                "确认发货能力不可用: tenantId=%d accountId=%d orderId=%s isBargain=%s error=%s message=%s",
                tenant_id,
                account_id,
                order_id,
                is_bargain,
                result.get("error", "") if result else "CAPABILITY_UNAVAILABLE",
                result.get("message", "") if result else "",
            )
        return result or {
            "success": False,
            "error": "CAPABILITY_UNAVAILABLE",
            "message": "闲鱼确认发货能力当前不可用",
        }
    except Exception as e:
        logger.error(
            "确认发货异常: accountId=%d orderId=%s isBargain=%s error=%s",
            account_id, order_id, is_bargain, e,
        )
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
    delivery_timing: Optional[str] = DELIVERY_TIMING_AFTER_PAYMENT,
):
    """插入发货记录。

    delivery_timing 默认 after_payment：所有实时发货均为付款后触发。
    历史 bug 中此值为 None 导致 delivery_record.delivery_timing 为 NULL，
    使 _has_existing_realtime_delivery 去重查询匹配不到记录，引发重复发货。
    """
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
