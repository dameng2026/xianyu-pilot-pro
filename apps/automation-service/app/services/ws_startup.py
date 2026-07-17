"""
WebSocket startup service.

On application startup, automatically read all logged-in Xianyu accounts
and start their WebSocket connections.
"""
import asyncio
import logging
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


async def _run_delivery_after_message_saved(tenant_id: int, account_id: int, msg: dict) -> None:
    """Run delivery side effects off the WS receive critical path."""
    try:
        from .ws_delivery_handler import handle_incoming_message_for_delivery

        await handle_incoming_message_for_delivery(tenant_id, account_id, msg)
    except Exception as exc:
        logger.error("自动发货处理异常 tenantId=%d accountId=%d: %s", tenant_id, account_id, exc)


def _should_trigger_ai_auto_reply(msg: dict) -> tuple[bool, int, str, str]:
    """Return whether the message should enter AI auto-reply flow."""
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
        and bool(sid)
        and reminder_content not in system_reminder_codes
    )
    is_system_message = (
        content_type_int != 1
        or (not sender_user_id and not looks_like_partial_buyer_text)
        or reminder_content in system_reminder_codes
    )
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
    should_trigger, _, _, _ = _should_trigger_ai_auto_reply(msg)
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
    should_trigger, content_type_int, sender_user_id, reminder_content = _should_trigger_ai_auto_reply(msg)
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
                saved_message_id = await save_chat_message(
                    db,
                    tenant_id,
                    account_id,
                    msg,
                    seller_external_uid=seller_external_uid,
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
        try:
            from .ws_delivery_handler import is_payment_message
            if is_payment_message(msg):
                logger.info(
                    "消息已存在但为付款消息，仍触发自动发货兜底: accountId=%d sId=%s pnmId=%s",
                    account_id, msg.get("sId", ""), msg.get("pnmId", ""),
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
        asyncio.create_task(_queue_ai_auto_reply_after_message_saved(tenant_id, account_id, dict(msg), seller_external_uid))


async def _infer_missing_session_info(
    tenant_id: int,
    account_id: int,
    msg: dict,
    seller_external_uid: str,
) -> None:
    """当消息缺少 sId/sender 时，从同账号最近的消息推断会话信息。

    背景：轻量级内容消息格式 {"1":101,"3":{...}} 不携带 sId/senderUserId，
    导致无法触发 AI 自动回复。同一账号在短时间内收到的消息通常属于同一会话，
    因此从最近 5 分钟内有 sId 的消息推断会话信息是可靠的。
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
            # 查询最近 5 分钟内有 sId 的消息（不限 direction）。
            # 优先买家发的 IN 消息（sender_user_id 是买家），
            # 其次卖家发的 OUT 消息（peer_external_uid 是买家）。
            row = (await db.execute(text("""
                SELECT s_id, sender_user_id, peer_external_uid, xy_goods_id, reminder_url
                FROM xianyu_chat_message
                WHERE tenant_id = :tenant_id
                  AND account_id = :account_id
                  AND deleted = 0
                  AND content_type = 1
                  AND s_id IS NOT NULL AND s_id != ''
                  AND created_time >= DATE_SUB(NOW(), INTERVAL 5 MINUTE)
                ORDER BY id DESC
                LIMIT 1
            """), {
                "tenant_id": tenant_id,
                "account_id": account_id,
            })).mappings().first()

            if not row:
                return

            inferred_sid = str(row.get("s_id") or "").strip()
            inferred_sender = str(row.get("sender_user_id") or "").strip()
            inferred_peer = str(row.get("peer_external_uid") or "").strip()
            inferred_goods_id = str(row.get("xy_goods_id") or "").strip()
            inferred_reminder_url = str(row.get("reminder_url") or "").strip()

            # 判断推断源消息的 sender 是否是卖家自己
            seller_normalized = seller_external_uid.replace("@goofish", "").strip() if seller_external_uid else ""
            sender_normalized = inferred_sender.replace("@goofish", "").strip() if inferred_sender else ""
            sender_is_seller = bool(seller_normalized and sender_normalized and seller_normalized == sender_normalized)

            # 如果 sender 是卖家自己（OUT 消息同步回来），买家 ID 从 peer_external_uid 获取
            effective_buyer = inferred_peer if sender_is_seller else inferred_sender

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

                await asyncio.sleep(1)
    except Exception as exc:
        logger.error("自动启动 WebSocket 异常: %s", exc, exc_info=True)


async def stop_all() -> None:
    """Stop all WebSocket connections."""
    await ws_manager.stop_all()
    logger.info("所有 WebSocket 连接已停止")
