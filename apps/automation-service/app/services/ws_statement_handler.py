"""
发货声明流程处理器

职责：
1. 收到付款消息后，若发货声明开关开启，发送声明文案并创建声明会话（status=waiting）
2. 收到买家回复"确认/取消"后，更新声明会话状态并触发后续动作
   - 确认 → 触发该订单发货（调用 DeliveryExecutionService）
   - 取消 → 通知卖家 + 向买家回复取消提示

设计要点：
- 声明会话按订单粒度跟踪（account_id + order_id）
- 幂等：同一订单已有 declaring/waiting 会话时不重复创建
- 兜底：买家发"确认"但无匹配声明会话时，静默忽略+记日志，AI 自动回复照常
- 与 AI 自动回复解耦：本模块仅处理声明会话状态，不抑制 AI 自动回复

调用入口：
- ws_delivery_handler.handle_incoming_message_for_delivery 收到付款消息后调用 should_send_statement / send_statement_and_create_session
- ws_startup.on_message_callback 收到买家消息后调用 handle_buyer_statement_reply
"""
import logging
import re
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import async_session
from .ws_client import ws_manager

logger = logging.getLogger(__name__)

# ============================================================
# 固定声明文案（用户不可编辑，仅 {订单编号} 和 {商品标题} 会被替换）
# ============================================================
STATEMENT_TEMPLATE = (
    "订单编号：{订单编号}\n\n"
    "您好，该订单包含的商品为虚拟商品，发货后不支持退换。"
    "如无异议，请回复【确认】。\n\n"
    "如有异议，请回复【取消】，这边帮您转人工客服，进行退款操作"
)

# 买家回复"取消"后，向买家发送的提示文案
BUYER_CANCEL_REPLY = "已为您转人工客服，请耐心等待，客服会尽快与您联系处理退款事宜。"

# 买家确认/取消关键词识别（精确匹配，去除标点空格后比对）
# 确认关键词：确认、确定、好的、好、可以、同意
# 取消关键词：取消、不要了、退款、退货、拒绝、不同意
CONFIRM_KEYWORDS = {"确认", "确定", "好的", "好", "可以", "同意", "确认发货"}
CANCEL_KEYWORDS = {"取消", "不要了", "退款", "退货", "拒绝", "不同意", "取消发货"}


# ============================================================
# 声明开关查询
# ============================================================
async def is_statement_enabled(db: AsyncSession, tenant_id: int) -> bool:
    """查询指定租户的发货声明是否开启"""
    try:
        row = (await db.execute(
            text("SELECT enabled FROM delivery_statement WHERE tenant_id=:tid AND deleted=0 LIMIT 1"),
            {"tid": tenant_id},
        )).first()
        if row is None:
            return False
        return int(row[0] or 0) == 1
    except Exception as e:
        logger.warning("查询发货声明开关失败 tenantId=%s error=%s", tenant_id, e)
        return False


# ============================================================
# 发送声明 + 创建会话
# ============================================================
async def send_statement_and_create_session(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    msg: dict,
    *,
    order_id: Optional[str],
    xy_goods_id: str,
    s_id: str,
    pnm_id: str,
    buyer_user_id: str,
    buyer_user_name: str,
    goods_title: str = "",
) -> bool:
    """发送发货声明并创建声明会话。

    Args:
        db: 数据库会话
        tenant_id/account_id: 租户/账号
        msg: 原始消息（用于日志）
        order_id/xy_goods_id/s_id/pnm_id/buyer_user_id/buyer_user_name: 订单与会话信息
        goods_title: 商品标题（用于文案变量替换）

    Returns:
        True=已发送声明并创建会话（调用方应停止发货流程）
        False=未发送声明（开关关闭/已有未完成会话/发送失败），调用方应继续原发货流程
    """
    if not order_id:
        # 无订单号无法跟踪声明会话，跳过声明流程
        return False

    # 幂等：同一订单已有 declaring/waiting 会话时不重复创建
    existing = (await db.execute(
        text("""
            SELECT id, status FROM delivery_statement_session
            WHERE tenant_id=:tid AND account_id=:aid AND order_id=:oid
              AND status IN ('declaring','waiting') AND deleted=0
            ORDER BY created_time DESC LIMIT 1
        """),
        {"tid": tenant_id, "aid": account_id, "oid": order_id},
    )).first()
    if existing is not None:
        logger.info(
            "声明会话已存在，跳过重复发送 tenantId=%d accountId=%d orderId=%s sessionId=%s status=%s",
            tenant_id, account_id, order_id, existing[0], existing[1],
        )
        return True  # 已有未完成会话，停止发货流程

    # 变量替换
    content = STATEMENT_TEMPLATE.replace("{订单编号}", order_id)
    content = content.replace("{商品标题}", goods_title or "")

    # 发送声明消息
    send_ok = await _send_statement_message(account_id, s_id, buyer_user_id, content)
    if not send_ok:
        logger.warning(
            "发送声明失败，跳过创建会话，按原流程发货 tenantId=%d accountId=%d orderId=%s",
            tenant_id, account_id, order_id,
        )
        # 记录一条可见的 failed 会话，便于运营排查“声明已配置但未发出”的场景。
        try:
            await db.execute(
                text("""
                    INSERT INTO delivery_statement_session(
                        tenant_id, account_id, order_id, buyer_id, buyer_nick,
                        xy_goods_id, goods_title, s_id, pnm_id,
                        statement_content, status, created_time, updated_time, deleted
                    ) VALUES(
                        :tid, :aid, :oid, :bid, :bnick,
                        :gid, :gtitle, :sid, :pnm,
                        :content, 'failed', NOW(), NOW(), 0
                    )
                """),
                {
                    "tid": tenant_id, "aid": account_id, "oid": order_id,
                    "bid": buyer_user_id, "bnick": buyer_user_name,
                    "gid": xy_goods_id, "gtitle": goods_title,
                    "sid": s_id, "pnm": pnm_id,
                    "content": content,
                },
            )
            await db.commit()
            logger.warning(
                "发送声明失败，已记录 failed 会话 tenantId=%d accountId=%d orderId=%s",
                tenant_id, account_id, order_id,
            )
        except Exception as persist_err:
            try:
                await db.rollback()
            except Exception:
                pass
            logger.warning(
                "记录 failed 声明会话失败 tenantId=%d accountId=%d orderId=%s error=%s",
                tenant_id, account_id, order_id, str(persist_err)[:200],
            )
        return False  # 发送失败，回退到原发货流程

    # 创建声明会话（status=waiting，已发送）
    await db.execute(
        text("""
            INSERT INTO delivery_statement_session(
                tenant_id, account_id, order_id, buyer_id, buyer_nick,
                xy_goods_id, goods_title, s_id, pnm_id,
                statement_content, status, sent_at,
                created_time, updated_time, deleted
            ) VALUES(
                :tid, :aid, :oid, :bid, :bnick,
                :gid, :gtitle, :sid, :pnm,
                :content, 'waiting', NOW(),
                NOW(), NOW(), 0
            )
        """),
        {
            "tid": tenant_id, "aid": account_id, "oid": order_id,
            "bid": buyer_user_id, "bnick": buyer_user_name,
            "gid": xy_goods_id, "gtitle": goods_title,
            "sid": s_id, "pnm": pnm,
            "content": content,
        },
    )
    logger.info(
        "已发送发货声明并创建会话 tenantId=%d accountId=%d orderId=%s xyGoodsId=%s sId=%s buyer=%s",
        tenant_id, account_id, order_id, xy_goods_id, s_id, buyer_user_id,
    )
    return True


async def _send_statement_message(
    account_id: int,
    s_id: str,
    buyer_user_id: str,
    content: str,
) -> bool:
    """通过 WebSocket 发送声明文案给买家。复用 ws_delivery_handler 的发送逻辑。"""
    client = ws_manager.get_client(account_id)
    if not client or not client.is_connected:
        logger.warning("WebSocket未连接，无法发送声明: accountId=%d", account_id)
        return False
    if not client._sid:
        logger.warning("WebSocket未注册（无sid），无法发送声明: accountId=%d", account_id)
        return False

    cid = s_id if s_id.endswith("@goofish") else f"{s_id}@goofish"
    to_id = buyer_user_id if buyer_user_id.endswith("@goofish") else f"{buyer_user_id}@goofish"

    try:
        result = await client.send_text_message(cid=cid, to_id=to_id, text=content)
        code = result.get("code", 500)
        if code == 200:
            return True
        logger.warning(
            "发送声明消息失败: accountId=%d code=%s error=%s",
            account_id, code, result.get("error", ""),
        )
        return False
    except Exception as e:
        logger.error("发送声明消息异常: accountId=%d error=%s", account_id, e)
        return False


# ============================================================
# 买家回复识别（确认/取消）
# ============================================================
def classify_buyer_reply(msg: dict) -> Optional[str]:
    """识别买家回复是否为"确认"或"取消"。

    Returns:
        "confirm"=确认 / "cancel"=取消 / None=非声明回复（普通消息）
    """
    # 仅处理文本消息（contentType=1）
    content_type = msg.get("contentType") or msg.get("content_type") or 0
    try:
        content_type = int(content_type)
    except (ValueError, TypeError):
        return None
    if content_type != 1:
        return None

    # 提取消息文本
    text_content = str(msg.get("msgContent") or "").strip()
    if not text_content:
        return None

    # 标准化：去除空格、标点（【】[] () （）等）
    normalized = re.sub(r"[\s【】\[\]()（）.,，。!！?？:：;；\-_/\\]", "", text_content)
    normalized_lower = normalized.lower()

    # 优先匹配取消（"取消"优先于"确认"，避免"确认取消"被误判为确认）
    for kw in CANCEL_KEYWORDS:
        if kw in normalized:
            return "cancel"
    for kw in CONFIRM_KEYWORDS:
        if kw in normalized:
            return "confirm"
    # 英文兜底
    if "cancel" in normalized_lower:
        return "cancel"
    if "confirm" in normalized_lower or "yes" in normalized_lower or "ok" in normalized_lower:
        return "confirm"
    return None


async def handle_buyer_statement_reply(
    tenant_id: int,
    account_id: int,
    msg: dict,
) -> Optional[str]:
    """处理买家对声明会话的回复。

    在 ws_startup.on_message_callback 中收到买家消息后调用。
    流程：
    1. 识别回复类型（confirm/cancel/None）
    2. 若为 None，返回 None（普通消息，AI 自动回复照常）
    3. 查询该会话是否有 waiting 状态的声明会话
    4. 无匹配会话：静默忽略+记日志，返回 None（AI 自动回复照常）
    5. 有匹配会话：
       - confirm → 更新会话 confirmed → 触发发货 → 返回 "confirm_handled"
       - cancel → 更新会话 cancelled → 通知卖家+回复买家 → 返回 "cancel_handled"

    Returns:
        "confirm_handled" / "cancel_handled" / None
        返回非 None 表示已处理，调用方可选择抑制 AI 自动回复（当前不抑制）
    """
    reply_type = classify_buyer_reply(msg)
    if reply_type is None:
        return None  # 非声明回复

    s_id = str(msg.get("sId") or "")
    if not s_id:
        return None

    reply_msg_id = str(msg.get("pnmId") or msg.get("msgId") or "")

    async with async_session() as db:
        try:
            # 查询该会话 waiting 状态的声明会话（取最早一条，FIFO）
            session = (await db.execute(
                text("""
                    SELECT id, order_id, xy_goods_id, buyer_id, goods_title
                    FROM delivery_statement_session
                    WHERE tenant_id=:tid AND account_id=:aid
                      AND s_id=:sid AND status='waiting' AND deleted=0
                    ORDER BY created_time ASC LIMIT 1
                """),
                {"tid": tenant_id, "aid": account_id, "sid": s_id},
            )).first()

            if session is None:
                # 无匹配声明会话：静默忽略+记日志，AI 自动回复照常
                logger.debug(
                    "买家回复%s但无匹配声明会话，忽略 tenantId=%d accountId=%d sId=%s",
                    reply_type, tenant_id, account_id, s_id,
                )
                await db.commit()
                return None

            session_id = session[0]
            order_id = session[1]
            xy_goods_id = session[2]
            buyer_id = session[3]
            goods_title = session[4]

            if reply_type == "confirm":
                await _handle_confirm(db, tenant_id, account_id, session_id,
                                      order_id, xy_goods_id, buyer_id, goods_title,
                                      s_id, reply_msg_id)
            else:
                await _handle_cancel(db, tenant_id, account_id, session_id,
                                     order_id, xy_goods_id, buyer_id, goods_title,
                                     s_id, reply_msg_id)
            await db.commit()
            return "confirm_handled" if reply_type == "confirm" else "cancel_handled"
        except Exception as e:
            await db.rollback()
            logger.error(
                "处理买家声明回复失败 tenantId=%d accountId=%d sId=%s replyType=%s error=%s",
                tenant_id, account_id, s_id, reply_type, e, exc_info=True,
            )
            return None


async def _handle_confirm(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    session_id: int,
    order_id: str,
    xy_goods_id: str,
    buyer_id: str,
    goods_title: str,
    s_id: str,
    reply_msg_id: str,
) -> None:
    """处理买家确认：更新会话 confirmed → 触发发货"""
    # 1. 更新会话状态
    result = await db.execute(
        text("""
            UPDATE delivery_statement_session
            SET status='confirmed', confirmed_at=NOW(), confirm_source='buyer',
                reply_msg_id=:rmid, updated_time=NOW()
            WHERE id=:id AND tenant_id=:tid AND status='waiting'
        """),
        {"id": session_id, "tid": tenant_id, "rmid": reply_msg_id},
    )
    if result.rowcount == 0:
        logger.warning(
            "买家确认但会话状态已变更，跳过 tenantId=%d sessionId=%d",
            tenant_id, session_id,
        )
        return

    logger.info(
        "买家确认声明，触发发货 tenantId=%d accountId=%d orderId=%s sessionId=%d",
        tenant_id, account_id, order_id, session_id,
    )

    # 2. 触发发货：复用 ws_delivery_handler 的发货流程
    #    构造一个虚拟的付款消息，复用 _process_delivery 的发货逻辑
    try:
        from .ws_delivery_handler import _trigger_delivery_for_confirmed_statement
        await _trigger_delivery_for_confirmed_statement(
            db, tenant_id, account_id,
            order_id=order_id,
            xy_goods_id=xy_goods_id,
            buyer_user_id=buyer_id,
            s_id=s_id,
            goods_title=goods_title,
            session_id=session_id,
        )
    except Exception as e:
        logger.error(
            "买家确认后触发发货失败 tenantId=%d accountId=%d orderId=%s error=%s",
            tenant_id, account_id, order_id, e, exc_info=True,
        )


async def _handle_cancel(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    session_id: int,
    order_id: str,
    xy_goods_id: str,
    buyer_id: str,
    goods_title: str,
    s_id: str,
    reply_msg_id: str,
) -> None:
    """处理买家取消：更新会话 cancelled → 通知卖家 + 回复买家"""
    result = await db.execute(
        text("""
            UPDATE delivery_statement_session
            SET status='cancelled', cancelled_at=NOW(), cancel_source='buyer',
                reply_msg_id=:rmid, updated_time=NOW()
            WHERE id=:id AND tenant_id=:tid AND status='waiting'
        """),
        {"id": session_id, "tid": tenant_id, "rmid": reply_msg_id},
    )
    if result.rowcount == 0:
        logger.warning(
            "买家取消但会话状态已变更，跳过 tenantId=%d sessionId=%d",
            tenant_id, session_id,
        )
        return

    logger.info(
        "买家取消声明 tenantId=%d accountId=%d orderId=%s sessionId=%d",
        tenant_id, account_id, order_id, session_id,
    )

    # 1. 向买家发送取消提示
    await _send_statement_message(account_id, s_id, buyer_id, BUYER_CANCEL_REPLY)

    # 2. 通知卖家（飞书/站内）
    try:
        from .notify_dispatcher import notify_auto_delivery
        await notify_auto_delivery(
            tenant_id, account_id, success=False,
            order_id=order_id,
            detail=f"买家取消发货声明，已转人工客服。商品：{goods_title or xy_goods_id}",
        )
    except Exception:
        logger.debug("买家取消声明的飞书通知异常，忽略", exc_info=True)
