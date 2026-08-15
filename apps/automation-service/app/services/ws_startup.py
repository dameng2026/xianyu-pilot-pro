"""
WebSocket startup service.

On application startup, automatically read all logged-in Xianyu accounts
and start their WebSocket connections.
"""
import asyncio
import logging
import random
import time
from typing import Any

from sqlalchemy import text

from ..core.cookie_crypto import decrypt_cookie_if_needed
from ..core.database import async_session
from .ws_client import ws_manager
from .ws_storage import save_chat_message

logger = logging.getLogger(__name__)

# 去抖窗口：同一会话在此时间窗口内到达的多条消息会被合并为一条 AI 回复。
# 设为 1 秒：既保留快速连发的合并能力（避免触发闲鱼风控），又减少正常对话间隔下的误合并。
AI_AUTO_REPLY_DEBOUNCE_SECONDS = 1.0
_ai_auto_reply_batch_lock = asyncio.Lock()
_ai_auto_reply_batches: dict[str, dict[str, Any]] = {}
_ai_auto_reply_tasks: dict[str, asyncio.Task] = {}

# 付款兜底节流：同一 account_id+sid+xyGoodsId 在此窗口内只触发一次付款兜底，
# 防止闲鱼 WS 对同一笔付款推送的多条卡片更新消息全部触发重复发货。
#
# 2026-07-29 事故级 Bug 修复：
# 原节流 key 用 account_id+pnmId（60 秒），但闲鱼对不同推送可能用不同 pnmId，
# 导致节流失效。且 60 秒太短，闲鱼每分钟都在推送付款消息（因订单同步失败，
# confirm_shipment 无法调用，闲鱼平台不知道已发货而持续推送）。
# 现改为按 account_id+sid+xyGoodsId 节流（同一会话+商品），窗口扩展到 600 秒，
# 配合 _has_existing_realtime_delivery 的 72 小时去重窗口，彻底阻断重复发货。
PAYMENT_FALLBACK_THROTTLE_SECONDS = 600.0
_payment_fallback_last_run: dict[str, float] = {}


async def _run_delivery_after_message_saved(tenant_id: int, account_id: int, msg: dict) -> None:
    """Run delivery side effects off the WS receive critical path."""
    try:
        from .ws_delivery_handler import handle_incoming_message_for_delivery

        await handle_incoming_message_for_delivery(tenant_id, account_id, msg)
    except Exception as exc:
        logger.error("自动发货处理异常 tenantId=%d accountId=%d: %s", tenant_id, account_id, exc)


def _should_trigger_ai_auto_reply(msg: dict, seller_external_uid: str = "") -> tuple[bool, int, str, str]:
    """Return whether the message should enter AI auto-reply flow.

    自问自答防护（强制）：
    - 仅 direction == "IN" 的消息才触发自动回复
    - 显式校验 senderUserId 不等于卖家自己（防止 IM 回环消息 direction 被误判为 IN）
    - 当 seller_external_uid 已知且 senderUserId 等于卖家自己时，强制返回 False
      （这是自问自答的最后一道闸门，不依赖 validate_parsed_message 的 direction 修正）

    修复（2026-07-30）：放宽 partial_buyer_text 判定，不再强制要求 s_id 存在。
    背景：线上 tenant 121 的 81% 文本消息因协议变体导致 sender_user_id 和 s_id 同时缺失，
    原 logic 要求 bool(sid) 为 True 才视为 partial_buyer_text，否则被判为 system_message 跳过。
    修复后：文本消息只要有 msgContent 且不属于系统提醒码，即允许进入 AI 回复流程，
    由 _infer_missing_session_info 和 process_incoming_message 做后续兜底处理。
    """
    direction = str(msg.get("direction") or "IN").upper()
    content_type = msg.get("contentType", 1)
    try:
        content_type_int = int(content_type) if str(content_type).isdigit() else 1
    except (TypeError, ValueError):
        content_type_int = 1

    sender_user_id = str(msg.get("senderUserId") or "").strip()
    msg_content = str(msg.get("msgContent") or "").strip()
    sid = str(msg.get("sId") or msg.get("sid") or "").strip()
    reminder_content = str(msg.get("reminderContent") or "").strip()
    system_reminder_codes = {"PIC_DEAL_ERROR", "业务通知", "BIZ_NOTIFICATION"}
    looks_like_partial_buyer_text = (
        content_type_int == 1
        and not sender_user_id
        and bool(msg_content)
        and reminder_content not in system_reminder_codes
    )
    is_system_message = (
        content_type_int != 1
        or (not sender_user_id and not looks_like_partial_buyer_text)
        or reminder_content in system_reminder_codes
    )

    # 自问自答防护：senderUserId 等于卖家自己时，强制不触发自动回复。
    # 该检查是 direction 修正失败的兜底，无论 direction 字段是否为 IN 都会拦截。
    if seller_external_uid and sender_user_id:
        seller_uid_norm = seller_external_uid.replace("@goofish", "").strip()
        sender_uid_norm = sender_user_id.replace("@goofish", "").strip()
        if seller_uid_norm and sender_uid_norm and seller_uid_norm == sender_uid_norm:
            return False, content_type_int, sender_user_id, reminder_content

    return direction == "IN" and not is_system_message, content_type_int, sender_user_id, reminder_content


def _coerce_message_time_ms(msg: dict[str, Any]) -> int:
    value = msg.get("messageTime", 0)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _extract_auto_reply_role_hints(msg: dict[str, Any]) -> dict[str, str]:
    raw_payload = msg.get("rawPayload") or msg.get("raw_payload") or {}
    session_info = raw_payload.get("sessionInfo") if isinstance(raw_payload, dict) else {}
    if not isinstance(session_info, dict):
        session_info = {}
    extensions = session_info.get("extensions") if isinstance(session_info.get("extensions"), dict) else {}

    def _pick(*values: Any) -> str:
        for value in values:
            text = str(value or "").strip()
            if text:
                return text
        return ""

    return {
        "receiverUserId": _pick(
            msg.get("receiverUserId"),
            raw_payload.get("receiverUserId") if isinstance(raw_payload, dict) else "",
        ),
        "ownerUserId": _pick(
            msg.get("ownerUserId"),
            extensions.get("ownerUserId"),
            session_info.get("ownerUserId"),
            raw_payload.get("ownerUserId") if isinstance(raw_payload, dict) else "",
        ),
        "itemSellerId": _pick(
            msg.get("itemSellerId"),
            extensions.get("itemSellerId"),
            session_info.get("itemSellerId"),
            raw_payload.get("itemSellerId") if isinstance(raw_payload, dict) else "",
        ),
        "groupOwnerId": _pick(
            msg.get("groupOwnerId"),
            session_info.get("groupOwnerId"),
            raw_payload.get("groupOwnerId") if isinstance(raw_payload, dict) else "",
        ),
        "extUserId": _pick(
            msg.get("extUserId"),
            extensions.get("extUserId"),
            session_info.get("extUserId"),
            raw_payload.get("extUserId") if isinstance(raw_payload, dict) else "",
        ),
    }


def _build_ai_auto_reply_batch_key(tenant_id: int, account_id: int, msg: dict[str, Any]) -> str:
    sid = str(msg.get("sId") or msg.get("sid") or "").strip()
    if sid:
        return f"{tenant_id}:{account_id}:sid:{sid}"

    sender_user_id = str(msg.get("senderUserId") or "").strip()
    if sender_user_id:
        return f"{tenant_id}:{account_id}:buyer:{sender_user_id}"

    pnm_id = str(msg.get("pnmId") or msg.get("pnm_id") or "").strip()
    if pnm_id:
        return f"{tenant_id}:{account_id}:pnm:{pnm_id}"

    content = str(msg.get("msgContent") or "").strip()
    return f"{tenant_id}:{account_id}:fallback:{content[:80]}:{_coerce_message_time_ms(msg)}"


def _merge_ai_auto_reply_messages(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    ordered = sorted(
        (dict(item) for item in messages if isinstance(item, dict)),
        key=lambda item: (_coerce_message_time_ms(item), str(item.get("pnmId") or item.get("pnm_id") or "")),
    )
    merged_messages: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for item in ordered:
        content = str(item.get("msgContent") or "").strip()
        if not content:
            continue
        dedupe_key = (
            str(item.get("pnmId") or item.get("pnm_id") or "").strip()
            or f"{str(item.get('senderUserId') or '').strip()}|{_coerce_message_time_ms(item)}|{content}"
        )
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        merged_messages.append(item)

    if not merged_messages:
        return None

    merged = dict(merged_messages[-1])
    merged["msgContent"] = "\n".join(str(item.get("msgContent") or "").strip() for item in merged_messages)
    merged["mergedMessageCount"] = len(merged_messages)
    merged["mergedMessages"] = [
        {
            "pnmId": str(item.get("pnmId") or item.get("pnm_id") or "").strip(),
            "messageTime": _coerce_message_time_ms(item),
            "senderUserId": str(item.get("senderUserId") or "").strip(),
            "msgContent": str(item.get("msgContent") or "").strip(),
        }
        for item in merged_messages
    ]
    merged["messageTime"] = max(_coerce_message_time_ms(item) for item in merged_messages)
    if len(merged_messages) > 1:
        merged["pnmId"] = str(merged_messages[-1].get("pnmId") or merged_messages[-1].get("pnm_id") or "").strip()
    return merged


async def _flush_ai_auto_reply_batch(batch_key: str) -> None:
    try:
        await asyncio.sleep(AI_AUTO_REPLY_DEBOUNCE_SECONDS)
        async with _ai_auto_reply_batch_lock:
            batch = _ai_auto_reply_batches.pop(batch_key, None)
            _ai_auto_reply_tasks.pop(batch_key, None)
        if not batch:
            return

        merged_msg = _merge_ai_auto_reply_messages(batch.get("messages") or [])
        if not merged_msg:
            return

        await _run_ai_auto_reply_after_message_saved(
            int(batch["tenant_id"]),
            int(batch["account_id"]),
            merged_msg,
            str(batch.get("seller_external_uid") or ""),
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.error("AI 自动回复聚合批次处理异常 key=%s: %s", batch_key, exc, exc_info=True)


async def _queue_ai_auto_reply_after_message_saved(
    tenant_id: int,
    account_id: int,
    msg: dict,
    seller_external_uid: str,
) -> None:
    should_trigger, _, _, _ = _should_trigger_ai_auto_reply(msg, seller_external_uid)
    if not should_trigger:
        return

    batch_key = _build_ai_auto_reply_batch_key(tenant_id, account_id, msg)
    async with _ai_auto_reply_batch_lock:
        batch = _ai_auto_reply_batches.setdefault(
            batch_key,
            {
                "tenant_id": tenant_id,
                "account_id": account_id,
                "seller_external_uid": seller_external_uid,
                "messages": [],
            },
        )
        batch["seller_external_uid"] = seller_external_uid or batch.get("seller_external_uid") or ""
        batch["messages"].append(dict(msg))
        task = _ai_auto_reply_tasks.get(batch_key)
        if task and not task.done():
            return
        _ai_auto_reply_tasks[batch_key] = asyncio.create_task(_flush_ai_auto_reply_batch(batch_key))


async def _reset_ai_auto_reply_batch_state() -> None:
    async with _ai_auto_reply_batch_lock:
        tasks = list(_ai_auto_reply_tasks.values())
        _ai_auto_reply_tasks.clear()
        _ai_auto_reply_batches.clear()
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def _run_ai_auto_reply_after_message_saved(
    tenant_id: int,
    account_id: int,
    msg: dict,
    seller_external_uid: str,
) -> None:
    """Run AI auto-reply off the WS receive critical path."""
    should_trigger, content_type_int, sender_user_id, reminder_content = _should_trigger_ai_auto_reply(msg, seller_external_uid)
    if not should_trigger:
        if str(msg.get("direction") or "IN").upper() == "IN":
            logger.info(
                "跳过 AI 自动回复（系统消息）tenantId=%d accountId=%d sId=%s contentType=%s senderUserId=%s reminderContent=%s",
                tenant_id,
                account_id,
                msg.get("sId", ""),
                content_type_int,
                sender_user_id[:20] if sender_user_id else "(空)",
                reminder_content[:30],
            )
        return

    try:
        from .automation_runtime import process_incoming_message

        async with async_session() as reply_db:
            role_hints = _extract_auto_reply_role_hints(msg)
            await process_incoming_message(reply_db, {
                "tenantId": tenant_id,
                "accountId": account_id,
                "buyerId": msg.get("senderUserId"),
                "buyerName": msg.get("senderUserName"),
                "content": msg.get("msgContent"),
                "messageType": msg.get("messageType") or "text",
                "pnmId": msg.get("pnmId"),
                "sId": msg.get("sId"),
                "goodsId": msg.get("xyGoodsId"),
                "itemTitle": msg.get("goodsTitle") or msg.get("reminderContent"),
                "sellerExternalUid": seller_external_uid,
                "receiverUserId": role_hints.get("receiverUserId"),
                "ownerUserId": role_hints.get("ownerUserId"),
                "itemSellerId": role_hints.get("itemSellerId"),
                "groupOwnerId": role_hints.get("groupOwnerId"),
                "extUserId": role_hints.get("extUserId"),
            })
            await reply_db.commit()
    except Exception as exc:
        logger.error("AI 自动回复异常 tenantId=%d accountId=%d: %s", tenant_id, account_id, exc)


async def on_message_callback(tenant_id: int, account_id: int, msg: dict) -> None:
    """
    Persist the message quickly and defer heavy side effects.

    This callback runs on the WebSocket receive loop, so it must return fast
    enough to avoid delaying the next sync cycle.
    """
    seller_external_uid = ""
    saved_message_id = None
    try:
        async with async_session() as db:
            try:
                seller_uid_row = await db.execute(
                    text("SELECT external_uid FROM xianyu_account WHERE id = :aid AND tenant_id = :tid LIMIT 1"),
                    {"aid": account_id, "tid": tenant_id},
                )
                seller_external_uid = seller_uid_row.scalar_one_or_none() or ""
                # 从 msg 字典读取 isAutoReply 标记，区分 AI 自动回复与人工发送
                # 来源：_persist_outbound_message 主动入库时透传 / 自动回复路径 save_chat_message 入库时设置
                _msg_is_auto_reply = int(msg.get("isAutoReply") or 0)
                saved_message_id = await save_chat_message(
                    db,
                    tenant_id,
                    account_id,
                    msg,
                    seller_external_uid=seller_external_uid,
                    is_auto_reply=_msg_is_auto_reply,
                )
                await db.commit()
                logger.debug(
                    "消息已保存 tenantId=%d accountId=%d pnmId=%s sellerUid=%s",
                    tenant_id,
                    account_id,
                    msg.get("pnmId", ""),
                    seller_external_uid[:10] if seller_external_uid else "(空)",
                )
            except Exception as exc:
                await db.rollback()
                logger.error("保存消息失败 tenantId=%d accountId=%d: %s", tenant_id, account_id, exc)
                return
    except Exception as exc:
        logger.error("创建数据库会话失败: %s", exc)
        return

    if saved_message_id is None:
        # 消息已存在（去重命中）。但对于付款消息（contentType=26 且含"等待你发货"），
        # 仍需触发自动发货作为兜底，避免因去重逻辑或 pnm_id 复用导致付款通知被跳过。
        #
        # 2026-07-29 事故级 Bug 修复（三层防护）：
        # 1. 节流 key 改为 account_id+sid+xyGoodsId（同一会话+商品），而非 pnmId（消息级）
        #    原因：闲鱼对不同推送可能用不同 pnmId，导致节流失效
        # 2. 节流窗口从 60 秒扩展到 600 秒（10 分钟）
        #    原因：闲鱼对未确认发货的订单每分钟推送付款消息，60 秒节流不够
        # 3. 新增前置去重检查：触发兜底前先查 delivery_record 是否已有记录
        #    原因：订单同步失败时 order_id 为空，confirm_shipment 无法调用，
        #    闲鱼持续推送付款消息。即使节流通过，也不应重复发货。
        try:
            from .ws_delivery_handler import is_payment_message
            if is_payment_message(msg):
                sid = str(msg.get("sId") or "")
                xy_goods_id = str(msg.get("xyGoodsId") or "")
                # 节流 key 按 会话+商品 维度（归一化 sid 去掉 @goofish 后缀）
                normalized_sid = sid.replace("@goofish", "")
                throttle_key = f"{account_id}:{normalized_sid}:{xy_goods_id}"
                now = time.monotonic()
                last_run = _payment_fallback_last_run.get(throttle_key, 0.0)
                if now - last_run < PAYMENT_FALLBACK_THROTTLE_SECONDS:
                    logger.debug(
                        "付款兜底节流跳过 accountId=%d sid=%s xyGoodsId=%s 距上次触发 %.1fs（防止重复发货）",
                        account_id, sid, xy_goods_id, now - last_run,
                    )
                    return

                # 前置去重检查：触发兜底前先查 delivery_record 是否已有记录
                # 这是双保险，不依赖下游 _has_existing_realtime_delivery 的去重窗口
                # 场景：订单同步失败 → order_id 为空 → confirm_shipment 跳过 →
                #       闲鱼持续推送付款消息 → 72 小时内已有 delivery_record → 直接跳过
                if sid and xy_goods_id:
                    try:
                        async with async_session() as precheck_db:
                            from .ws_delivery_handler import DELIVERY_TIMING_AFTER_PAYMENT
                            existing = (await precheck_db.execute(
                                text("""
                                    SELECT id, status
                                    FROM delivery_record
                                    WHERE tenant_id = :tenant_id
                                      AND account_id = :account_id
                                      AND deleted = 0
                                      AND (delivery_timing = :delivery_timing OR delivery_timing IS NULL)
                                      AND REPLACE(JSON_UNQUOTE(JSON_EXTRACT(receiver_info, '$.sid')), '@goofish', '') = REPLACE(:sid, '@goofish', '')
                                      AND JSON_UNQUOTE(JSON_EXTRACT(receiver_info, '$.xyGoodsId')) = :xy_goods_id
                                      AND created_time >= DATE_SUB(NOW(), INTERVAL 72 HOUR)
                                    ORDER BY id DESC
                                    LIMIT 1
                                """),
                                {
                                    "tenant_id": tenant_id,
                                    "account_id": account_id,
                                    "delivery_timing": DELIVERY_TIMING_AFTER_PAYMENT,
                                    "sid": sid,
                                    "xy_goods_id": xy_goods_id,
                                }
                            )).mappings().first()
                            if existing:
                                logger.info(
                                    "付款兜底前置去重命中，跳过发货 accountId=%d sid=%s xyGoodsId=%s existingId=%s existingStatus=%s",
                                    account_id, sid, xy_goods_id, existing.get("id"), existing.get("status"),
                                )
                                # 仍更新节流时间，避免短时间内重复查询
                                _payment_fallback_last_run[throttle_key] = now
                                return
                    except Exception as precheck_err:
                        logger.warning(
                            "付款兜底前置去重检查异常，继续触发兜底 accountId=%d error=%s",
                            account_id, precheck_err,
                        )

                _payment_fallback_last_run[throttle_key] = now
                logger.info(
                    "消息已存在但为付款消息，仍触发自动发货兜底: accountId=%d sId=%s xyGoodsId=%s pnmId=%s",
                    account_id, sid, xy_goods_id, msg.get("pnmId", ""),
                )
                asyncio.create_task(_run_delivery_after_message_saved(tenant_id, account_id, dict(msg)))
        except Exception:
            logger.debug(
                "消息已存在，跳过自动回复与自动发货 accountId=%d sId=%s pnmId=%s",
                account_id, msg.get("sId", ""), msg.get("pnmId", ""),
            )
        return

    # 推断缺失的会话信息：轻量级内容消息格式（{"1":101,"3":{...}}）缺少 sId/sender，
    # 从同账号最近的有 sId 的消息推断当前消息属于哪个会话。
    await _infer_missing_session_info(tenant_id, account_id, msg, seller_external_uid)

    # 检测卖家从其他客户端（移动 APP/PC 闲鱼）人工发送的消息，触发会话级自动回复暂停。
    # 触发条件：新入库（saved_message_id 非 None，排除 IM 回环去重命中）+ OUT + is_auto_reply=0。
    # AI 自动回复消息的 IM 回环会因去重命中 saved_message_id=None 被跳过，
    # 网站手动发送消息在 misc.py 中已设置暂停，此处作为兜底（重复设置同样字段值，无副作用）。
    msg_direction = str(msg.get("direction") or "IN").upper()
    msg_is_auto_reply = int(msg.get("isAutoReply") or 0)
    if saved_message_id is not None and msg_direction == "OUT" and msg_is_auto_reply == 0:
        asyncio.create_task(_pause_auto_reply_for_manual_outbound(
            tenant_id, account_id, dict(msg), seller_external_uid
        ))

    # 发货声明回复识别：买家回复"确认/取消"时，更新声明会话状态并触发发货/通知。
    # 已处理的回复抑制 AI 自动回复（系统已响应，避免 AI 再发无关回复）。
    # 未匹配声明会话的回复静默忽略，AI 自动回复照常。
    statement_handled = False
    try:
        from .ws_statement_handler import handle_buyer_statement_reply
        result = await handle_buyer_statement_reply(tenant_id, account_id, dict(msg))
        statement_handled = result is not None
    except Exception as exc:
        logger.debug("声明回复处理异常 tenantId=%d accountId=%d: %s", tenant_id, account_id, exc)

    # Offload heavy follow-up work so the WS loop can continue syncing new messages.
    asyncio.create_task(_run_delivery_after_message_saved(tenant_id, account_id, dict(msg)))
    if not statement_handled:
        # 自问自答前置防护：在创建自动回复 task 之前，显式过滤自己发的消息。
        # 即使 IM 回环消息 direction 被误判为 IN，这里也能拦截，避免创建无效 task。
        # msg_direction 复用前面已定义的变量（人工 OUT 暂停检测处）
        msg_sender_uid = str(msg.get("senderUserId") or "").strip()
        is_self_message = False
        if seller_external_uid and msg_sender_uid:
            seller_uid_norm = seller_external_uid.replace("@goofish", "").strip()
            sender_uid_norm = msg_sender_uid.replace("@goofish", "").strip()
            if seller_uid_norm and sender_uid_norm and seller_uid_norm == sender_uid_norm:
                is_self_message = True
        if msg_direction == "OUT" or is_self_message:
            logger.info(
                "[AUTO_REPLY] 跳过自动回复（自己发的消息）tenantId=%d accountId=%d sId=%s direction=%s senderUserId=%s isSelf=%s",
                tenant_id, account_id, str(msg.get("sId", ""))[:20], msg_direction,
                msg_sender_uid[:20] if msg_sender_uid else "(空)", is_self_message,
            )
        else:
            asyncio.create_task(_queue_ai_auto_reply_after_message_saved(tenant_id, account_id, dict(msg), seller_external_uid))


async def _pause_auto_reply_for_manual_outbound(
    tenant_id: int,
    account_id: int,
    msg: dict,
    seller_external_uid: str,
) -> None:
    """检测到卖家从其他客户端（移动 APP/PC 闲鱼）人工发送消息后，
    暂停该会话的 AI 自动回复 60 秒，避免与人工回复"撞车"产生自问自答。

    触发条件（在 on_message_callback 中已判定）：
        - OUT 消息首次入库（非 IM 回环去重命中）
        - is_auto_reply=0（非 AI 自动回复）

    状态转移：
        - auto_reply_paused=1
        - last_manual_reply_at=<messageTime>
        - auto_reply_manual_disabled 保持原值（用户已手动关闭则依然只能手动开启）

    自动恢复：由 process_incoming_message 在下次买家消息到来时检查 60 秒超时恢复。
    """
    try:
        sid = str(msg.get("sId") or msg.get("sid") or "").strip()
        sender_user_id = str(msg.get("senderUserId") or "").strip()
        receiver_user_id = str(msg.get("receiverUserId") or "").strip()
        msg_content = str(msg.get("msgContent") or "").strip()

        if not sid:
            logger.debug(
                "人工 OUT 消息无 sId，跳过暂停 tenantId=%d accountId=%d",
                tenant_id, account_id,
            )
            return

        # 使用消息时间戳作为暂停起点；若 messageTime<=0 则用当前时间兜底
        message_time_ms = _coerce_message_time_ms(msg)
        if message_time_ms <= 0:
            message_time_ms = int(time.time() * 1000)

        # 排除卖家自己的 ID 后，构造 peer_id 候选列表（用于反查会话）
        seller_norm = seller_external_uid.replace("@goofish", "").strip() if seller_external_uid else ""
        seller_variants = {seller_norm, f"{seller_norm}@goofish"} if seller_norm else set()
        peer_id_candidates: list[str] = []
        for candidate in (receiver_user_id, sender_user_id):
            cand = str(candidate or "").strip()
            if cand and cand not in peer_id_candidates and cand not in seller_variants:
                peer_id_candidates.append(cand)

        async with async_session() as db:
            # 从最近消息中取 peer_external_uid 作为补充候选
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
                "sid": sid,
                "sid_goofish": f"{sid}@goofish" if not sid.endswith("@goofish") else sid,
            })).mappings().first()

            if sid_peer_row:
                for key in ("peer_external_uid", "sender_user_id", "receiver_user_id"):
                    v = str(sid_peer_row.get(key) or "").strip()
                    if v and v not in peer_id_candidates and v not in seller_variants:
                        peer_id_candidates.append(v)

            # 通过 peer_id 候选匹配 xianyu_conversation
            # 使用 expanding bind parameter 支持 list 参数（SQLAlchemy 2.0 标准用法）
            conv_row = None
            if peer_id_candidates:
                from sqlalchemy import bindparam
                conv_row = (await db.execute(text("""
                    SELECT id, auto_reply_manual_disabled
                    FROM xianyu_conversation
                    WHERE tenant_id = :tenant_id AND account_id = :account_id
                      AND deleted = 0
                      AND (
                          external_buyer_id IN (:peer_ids)
                          OR peer_external_uid IN (:peer_ids)
                          OR peer_key IN (:peer_ids)
                      )
                    ORDER BY id DESC LIMIT 1
                """).bindparams(bindparam("peer_ids", expanding=True)), {
                    "tenant_id": tenant_id,
                    "account_id": account_id,
                    "peer_ids": peer_id_candidates,
                })).mappings().first()

            if not conv_row:
                logger.info(
                    "[AUTO_REPLY] 人工 OUT 消息未匹配到会话，跳过暂停 tenantId=%d accountId=%d sId=%s",
                    tenant_id, account_id, sid[:20],
                )
                return

            conv_id = int(conv_row["id"])
            manual_disabled = int(conv_row["auto_reply_manual_disabled"] or 0)

            # 设置会话暂停状态（与 misc.py 人工发送路径一致）
            await db.execute(text("""
                UPDATE xianyu_conversation
                SET auto_reply_paused = 1,
                    last_manual_reply_at = :last_manual_at,
                    last_message_time = NOW(),
                    last_message_content = :content,
                    updated_time = NOW()
                WHERE id = :conversation_id
            """), {
                "conversation_id": conv_id,
                "last_manual_at": message_time_ms,
                "content": msg_content[:500] if msg_content else "",
            })
            await db.commit()

            logger.info(
                "[AUTO_REPLY] 检测到卖家从其他客户端人工发送消息，暂停 AI 回复 60 秒 "
                "tenantId=%d accountId=%d convId=%d sId=%s contentLen=%d",
                tenant_id, account_id, conv_id, sid[:20], len(msg_content),
            )

            # 广播会话暂停状态变更事件，让前端实时更新开关按钮文案
            try:
                from .ws_sse import broadcaster
                await broadcaster.broadcast(tenant_id, "conversation_auto_reply_state", {
                    "conversationId": conv_id,
                    "accountId": account_id,
                    "peerId": peer_id_candidates[0] if peer_id_candidates else "",
                    "sid": sid,
                    "autoReplyPaused": 1,
                    "autoReplyManualDisabled": manual_disabled,
                    "lastManualReplyAt": message_time_ms,
                    "reason": "manual_intervention",
                })
            except Exception as sse_exc:
                logger.warning(
                    "广播会话暂停状态失败（不影响主流程）accountId=%d convId=%d: %s",
                    account_id, conv_id, sse_exc,
                )
    except Exception as exc:
        logger.error(
            "人工 OUT 消息暂停处理异常 tenantId=%d accountId=%d: %s",
            tenant_id, account_id, exc, exc_info=True,
        )


async def _infer_missing_session_info(
    tenant_id: int,
    account_id: int,
    msg: dict,
    seller_external_uid: str,
) -> None:
    """当消息缺少 sId/sender 时，从同账号最近的消息推断会话信息。

    背景：轻量级内容消息格式 {"1":101,"3":{...}} 不携带 sId/senderUserId，
    导致无法触发 AI 自动回复。同一账号在短时间内收到的消息通常属于同一会话，
    因此从最近 30 分钟内有 sId 的消息推断会话信息是可靠的。

    修复（2026-07-30）：推断窗口从 5 分钟扩展到 30 分钟。
    背景：线上 tenant 121 的 WS 消息解析变体导致大量文本消息缺失 sId/sender，
    5 分钟窗口内可能没有任何带 sId 的消息作为推断源，导致推断失败。
    扩展到 30 分钟可显著提高推断成功率，同时仍保持时效性。
    新增：当消息表推断失败时，回退到 xianyu_conversation 表按最近更新会话推断。
    """
    sid = str(msg.get("sId") or "").strip()
    sender_user_id = str(msg.get("senderUserId") or "").strip()
    if sid and sender_user_id:
        return  # 信息完整，无需推断

    content_type = msg.get("contentType", 1)
    try:
        content_type_int = int(content_type) if str(content_type).isdigit() else 1
    except (TypeError, ValueError):
        content_type_int = 1
    if content_type_int != 1:
        return  # 仅对文本消息推断

    msg_content = str(msg.get("msgContent") or "").strip()
    if not msg_content:
        return  # 无内容不推断

    try:
        async with async_session() as db:
            # 查询最近 30 分钟内有 sId 的消息（不限 direction）。
            # 自问自答防护：优先买家真实消息（direction=0 AND is_auto_reply=0），
            # 其次买家其他消息（direction=0），最后卖家消息（direction=1）。
            # 避免自动回复入库的 OUT 消息（is_auto_reply=1）被选为推断源，
            # 导致 IM 回环消息的 senderUserId 被错误推断为买家。
            row = (await db.execute(text("""
                SELECT s_id, sender_user_id, peer_external_uid, xy_goods_id, reminder_url,
                       is_auto_reply, direction
                FROM xianyu_chat_message
                WHERE tenant_id = :tenant_id
                  AND account_id = :account_id
                  AND deleted = 0
                  AND content_type = 1
                  AND s_id IS NOT NULL AND s_id != ''
                  AND created_time >= DATE_SUB(NOW(), INTERVAL 30 MINUTE)
                ORDER BY
                    CASE
                        WHEN direction = 0 AND is_auto_reply = 0 THEN 0
                        WHEN direction = 0 THEN 1
                        ELSE 2
                    END,
                    id DESC
                LIMIT 1
            """), {
                "tenant_id": tenant_id,
                "account_id": account_id,
            })).mappings().first()

            # 回退：消息表推断失败时，从 xianyu_conversation 表按最近更新会话推断
            if not row:
                conv_row = (await db.execute(text("""
                    SELECT external_buyer_id, peer_external_uid, goods_id, goods_title
                    FROM xianyu_conversation
                    WHERE tenant_id = :tenant_id
                      AND account_id = :account_id
                      AND deleted = 0
                      AND external_buyer_id IS NOT NULL AND external_buyer_id != ''
                      AND external_buyer_id NOT LIKE '%.PNM'
                      AND updated_time >= DATE_SUB(NOW(), INTERVAL 30 MINUTE)
                    ORDER BY updated_time DESC, id DESC
                    LIMIT 1
                """), {
                    "tenant_id": tenant_id,
                    "account_id": account_id,
                })).mappings().first()
                if conv_row:
                    inferred_buyer = str(conv_row.get("external_buyer_id") or "").strip()
                    inferred_peer = str(conv_row.get("peer_external_uid") or "").strip()
                    inferred_goods_id = str(conv_row.get("goods_id") or "").strip()
                    if not sid and inferred_buyer:
                        msg["sId"] = inferred_buyer
                    if not sender_user_id and inferred_buyer:
                        msg["senderUserId"] = inferred_buyer
                    if not msg.get("peerExternalUid") and inferred_peer:
                        msg["peerExternalUid"] = inferred_peer
                    if not msg.get("xyGoodsId") and inferred_goods_id:
                        msg["xyGoodsId"] = inferred_goods_id
                    logger.info(
                        "从会话表推断会话信息: tenantId=%d accountId=%d buyer=%s goodsId=%s contentLen=%d",
                        tenant_id, account_id,
                        inferred_buyer[:20] if inferred_buyer else "(空)",
                        inferred_goods_id[:20] if inferred_goods_id else "(空)",
                        len(msg_content),
                    )
                    return

            if not row:
                return

            inferred_sid = str(row.get("s_id") or "").strip()
            inferred_sender = str(row.get("sender_user_id") or "").strip()
            inferred_peer = str(row.get("peer_external_uid") or "").strip()
            inferred_goods_id = str(row.get("xy_goods_id") or "").strip()
            inferred_reminder_url = str(row.get("reminder_url") or "").strip()
            inferred_is_auto_reply = int(row.get("is_auto_reply") or 0)
            raw_direction = str(row.get("direction") or "").strip().upper()
            inferred_direction = 0 if raw_direction in ("", "IN", "0") else 1

            # 判断推断源消息的 sender 是否是卖家自己
            seller_normalized = seller_external_uid.replace("@goofish", "").strip() if seller_external_uid else ""
            sender_normalized = inferred_sender.replace("@goofish", "").strip() if inferred_sender else ""
            sender_is_seller = bool(seller_normalized and sender_normalized and seller_normalized == sender_normalized)

            # 如果 sender 是卖家自己（OUT 消息同步回来），买家 ID 从 peer_external_uid 获取
            effective_buyer = inferred_peer if sender_is_seller else inferred_sender

            # 过滤 PNM 格式的 sender（不是真实用户 ID）
            if effective_buyer and effective_buyer.endswith(".PNM"):
                effective_buyer = ""

            # 自问自答防护：如果推断源是自动回复入库的 OUT 消息（is_auto_reply=1），
            # 不推断 senderUserId（保持为空，由 _should_trigger_ai_auto_reply 的 partial_buyer_text 逻辑处理）。
            # 避免自动回复的 IM 回环消息被错误推断为买家消息，触发自问自答。
            if inferred_is_auto_reply == 1 and inferred_direction == 1:
                effective_buyer = ""  # 不推断 senderUserId
                logger.info(
                    "推断源为自动回复 OUT 消息，跳过 senderUserId 推断（防止自问自答）tenantId=%d accountId=%d sId=%s",
                    tenant_id, account_id, inferred_sid[:20] if inferred_sid else "(空)",
                )

            if not sid and inferred_sid:
                msg["sId"] = inferred_sid
            if not sender_user_id and effective_buyer:
                msg["senderUserId"] = effective_buyer
            if not msg.get("peerExternalUid") and inferred_peer:
                msg["peerExternalUid"] = inferred_peer
            if not msg.get("xyGoodsId") and inferred_goods_id:
                msg["xyGoodsId"] = inferred_goods_id
            if not msg.get("reminderUrl") and inferred_reminder_url:
                msg["reminderUrl"] = inferred_reminder_url

            logger.info(
                "推断会话信息: tenantId=%d accountId=%d sId=%s buyer=%s senderIsSeller=%s goodsId=%s contentLen=%d",
                tenant_id,
                account_id,
                inferred_sid[:20] if inferred_sid else "(空)",
                effective_buyer[:20] if effective_buyer else "(空)",
                sender_is_seller,
                inferred_goods_id[:20] if inferred_goods_id else "(空)",
                len(msg_content),
            )
    except Exception as exc:
        logger.warning("推断会话信息失败 tenantId=%d accountId=%d: %s", tenant_id, account_id, exc)


async def auto_start_all() -> None:
    """Automatically start WebSocket connections for all logged-in accounts.

    持久化策略：不批量重置 ws_status，保留服务重启前的在线状态。
    - 有有效 Cookie/Token 的账号：保持 ws_status=1，WS 客户端重连成功后 _persist_ws_online() 确认在线；
      若 Cookie 过期导致重连失败，_update_cookie_status(0) 会自动置 ws_status=0。
    - 缺少 Cookie/Token 的账号：单独置 ws_status=0（无法连接）。
    - 无 auth 记录但 ws_status=1 的残留：置 ws_status=0（账号已被清理）。
    """
    ws_manager.set_message_callback(on_message_callback)

    try:
        from .ws_token import ip_risk_active
    except Exception:
        ip_risk_active = lambda: False

    try:
        async with async_session() as db:
            # 仅重置无有效 auth 记录但 ws_status=1 的残留账号（auth 被删除或 Cookie 被清空）
            await db.execute(
                text("""
                    UPDATE xianyu_account_runtime r
                    SET r.ws_status = 0, r.online_status = 0, r.updated_time = NOW()
                    WHERE r.ws_status = 1 AND r.deleted = 0
                      AND NOT EXISTS (
                        SELECT 1 FROM xianyu_account_auth auth
                        WHERE auth.account_id = r.account_id
                          AND auth.tenant_id = r.tenant_id
                          AND COALESCE(auth.deleted, 0) = 0
                          AND auth.encrypted_cookie IS NOT NULL
                          AND auth.encrypted_cookie != ''
                      )
                """)
            )
            await db.commit()
            logger.info("已重置无有效 auth 的残留 ws_status=1 状态（保留有 Cookie 账号的在线状态）")

            rows = await db.execute(text("""
                SELECT
                    a.id AS account_id,
                    a.tenant_id,
                    a.external_uid AS unb,
                    auth.encrypted_cookie AS cookie_str,
                    auth.encrypted_token AS m_h5_tk
                FROM xianyu_account a
                JOIN xianyu_account_auth auth
                  ON auth.account_id = a.id
                 AND auth.tenant_id = a.tenant_id
                 AND COALESCE(auth.deleted, 0) = 0
                 AND auth.id = (
                    SELECT auth2.id
                    FROM xianyu_account_auth auth2
                    WHERE auth2.account_id = a.id
                      AND auth2.tenant_id = a.tenant_id
                      AND COALESCE(auth2.deleted, 0) = 0
                    ORDER BY COALESCE(auth2.updated_time, auth2.created_time) DESC, auth2.id DESC
                    LIMIT 1
                 )
                WHERE a.deleted = 0
                  AND auth.encrypted_cookie IS NOT NULL
                  AND auth.encrypted_cookie != ''
                ORDER BY a.id DESC
                LIMIT 50
            """))
            accounts = rows.mappings().all()

            if not accounts:
                logger.info("没有需要启动 WebSocket 的账号")
                return

            logger.info("自动启动 %d 个账号的 WebSocket 连接", len(accounts))

            # === IP 级风控（RGV587）熔断等待 ===
            # 重启后若服务器 IP 仍在禁令期，立即批量连接会触发 Token API 爆发，
            # 必然再次 RGV587 并延长禁令。先等熔断窗口结束，再开始连接。
            try:
                from .ws_token import ip_risk_active, ip_risk_remaining_seconds
                if ip_risk_active():
                    wait_sec = int(ip_risk_remaining_seconds()) + 5
                    logger.warning(
                        "检测到 IP 级风控（RGV587）熔断，自动启动延迟 %d 秒后再连接账号", wait_sec,
                    )
                    await asyncio.sleep(wait_sec)
            except Exception:
                pass

            for acct in accounts:
                account_id = acct["account_id"]
                tenant_id = acct["tenant_id"]
                unb = acct["unb"] or ""
                cookie_str = decrypt_cookie_if_needed(acct["cookie_str"] or "")
                m_h5_tk = decrypt_cookie_if_needed(acct["m_h5_tk"] or "") or ""

                if not cookie_str or not m_h5_tk:
                    logger.warning("账号 %d 缺少 Cookie 或 Token，跳过并标记离线", account_id)
                    # 缺少 Cookie/Token 的账号无法连接，单独置离线
                    await db.execute(
                        text("UPDATE xianyu_account_runtime SET ws_status = 0, online_status = 0, updated_time = NOW() "
                             "WHERE account_id = :aid AND tenant_id = :tid AND deleted = 0"),
                        {"aid": account_id, "tid": tenant_id},
                    )
                    await db.commit()
                    continue

                try:
                    await ws_manager.start_client(
                        account_id=account_id,
                        tenant_id=tenant_id,
                        cookie_str=cookie_str,
                        m_h5_tk=m_h5_tk,
                        unb=unb,
                    )
                    logger.info("已启动 WebSocket: accountId=%d", account_id)
                except Exception as exc:
                    logger.error("启动 WebSocket 失败 accountId=%d: %s", account_id, exc)
                    # 启动失败也标记离线
                    await db.execute(
                        text("UPDATE xianyu_account_runtime SET ws_status = 0, online_status = 0, updated_time = NOW() "
                             "WHERE account_id = :aid AND tenant_id = :tid AND deleted = 0"),
                        {"aid": account_id, "tid": tenant_id},
                    )
                    await db.commit()

                # 分散启动：每个账号随机间隔 2-5 秒，避免 50 个账号在短时间内爆发调用 Token API
                # 引发闲鱼 IP 级风控（RGV587）。若连接过程中熔断触发，加倍等待。
                if ip_risk_active():
                    logger.warning(
                        "自动启动中碰到 IP 级风控熔断 accountId=%d，等待 60 秒后继续", account_id,
                    )
                    await asyncio.sleep(60)
                else:
                    await asyncio.sleep(random.uniform(2.0, 5.0))
    except Exception as exc:
        logger.error("自动启动 WebSocket 异常: %s", exc, exc_info=True)


async def stop_all() -> None:
    """Stop all WebSocket connections."""
    await ws_manager.stop_all()
    logger.info("所有 WebSocket 连接已停止")
