"""
WebSocket 消息存储模块。

将 WebSocket 收到的消息存储到 xianyu_chat_message 表，
同时更新 xianyu_conversation 和 xianyu_message 表。
"""
import base64
import asyncio
import hashlib
import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python 3.8 fallback
    ZoneInfo = None

from sqlalchemy import bindparam, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.entities import XianyuChatMessage
from .ws_protocol import normalize_peer_name, extract_username_from_reminder

logger = logging.getLogger(__name__)

try:
    _DB_TIMEZONE = ZoneInfo("Asia/Shanghai") if ZoneInfo is not None else timezone(timedelta(hours=8))
except Exception:
    # tzdata can be absent in minimal runtimes; UTC+8 is the correct operational
    # fallback for current Asia/Shanghai timestamps.
    _DB_TIMEZONE = timezone(timedelta(hours=8))


def _is_misplaced_pnm_sender_message(message: dict[str, Any]) -> bool:
    sender_user_id = str(message.get("senderUserId") or message.get("sender_user_id") or "").strip()
    content = str(message.get("msgContent") or message.get("msg_content") or message.get("content") or "").strip()
    pnm_id = str(message.get("pnmId") or message.get("pnm_id") or "").strip()
    return (
        bool(re.fullmatch(r"\d+\.PNM", sender_user_id))
        and bool(re.fullmatch(r"\d+@goofish", content))
        and pnm_id in {"", "1"}
    )


def _serialize_json_document(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        text_value = value.strip()
        if not text_value:
            return None
        try:
            json.loads(text_value)
            return text_value
        except Exception:
            return json.dumps(value, ensure_ascii=False)
    return json.dumps(value, ensure_ascii=False)


def _normalize_goods_id(value: object) -> Optional[int]:
    if value is None:
        return None
    text_value = str(value).strip()
    if not text_value:
        return None
    if text_value.isdigit():
        try:
            return int(text_value)
        except (TypeError, ValueError):
            return None
    match = re.search(r"id=(\d+)", text_value)
    if match:
        try:
            return int(match.group(1))
        except (TypeError, ValueError):
            return None
    return None


def _legacy_message_direction(value: object) -> int:
    direction = str(value or "IN").upper()
    return 1 if direction == "OUT" else 0


def _normalize_image_url(value: object) -> str:
    text_value = str(value or "").strip()
    if not text_value:
        return ""
    if text_value.startswith("//"):
        return f"https:{text_value}"
    if text_value.startswith("http://"):
        return "https://" + text_value[len("http://"):]
    if text_value.startswith("https://"):
        return text_value
    if text_value.startswith("/"):
        return f"https://img.alicdn.com{text_value}"
    return text_value


def _extract_cover_from_text_blob(value: object) -> str:
    text_value = str(value or "")
    if not text_value:
        return ""
    patterns = [
        r'https?://[^\s"\']+\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\']*)?',
        r'//[^\s"\']+\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\']*)?',
        r'/[^\s"\']+\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\']*)?',
    ]
    for pattern in patterns:
        match = re.search(pattern, text_value, flags=re.IGNORECASE)
        if match:
            return _normalize_image_url(match.group(0))
    return ""


def _parse_json_object(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        text_value = value.strip()
        if not text_value:
            return {}
        try:
            parsed = json.loads(text_value)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _ensure_goofish_suffix(value: object) -> str:
    text_value = str(value or "").strip()
    if not text_value:
        return ""
    if text_value.startswith("sid:"):
        text_value = text_value[4:]
    if text_value.endswith("@goofish"):
        return text_value
    return f"{text_value}@goofish"


def _decode_live_message_payload(model: dict[str, Any]) -> tuple[dict[str, Any], str, dict[str, Any]]:
    message = _parse_json_object(model.get("message") or model)
    extension = _parse_json_object(message.get("extension"))
    content = _parse_json_object(message.get("content"))
    custom = _parse_json_object(content.get("custom"))
    summary = str(custom.get("summary") or custom.get("degrade") or "").strip()
    raw_data = str(custom.get("data") or "").strip()
    if not raw_data:
        return {}, summary, extension

    try:
        padding = "=" * (-len(raw_data) % 4)
        decoded_text = base64.b64decode(f"{raw_data}{padding}").decode("utf-8")
        decoded = json.loads(decoded_text)
        if isinstance(decoded, dict):
            return decoded, summary, extension
    except Exception as decode_err:
        logger.debug("解码 live message payload 失败 errorType=%s", type(decode_err).__name__)
    return {}, summary, extension


def _extract_live_image_urls(decoded: dict[str, Any]) -> list[str]:
    results: list[str] = []
    image_root = _parse_json_object(decoded.get("image"))
    pics = image_root.get("pics")
    if isinstance(pics, list):
        for pic in pics:
            if isinstance(pic, dict):
                normalized = _normalize_image_url(pic.get("url"))
                if normalized and normalized not in results:
                    results.append(normalized)
    for value in (
        image_root.get("url"),
        decoded.get("picUrl"),
        decoded.get("imageUrl"),
        decoded.get("url"),
    ):
        normalized = _normalize_image_url(value)
        if normalized and normalized not in results:
            results.append(normalized)
    return results


def _extract_live_message_content(decoded: dict[str, Any], fallback_summary: str = "") -> tuple[int, str, list[str]]:
    raw_content_type = decoded.get("contentType")
    try:
        content_type = int(raw_content_type)
    except (TypeError, ValueError):
        content_type = 1

    if (content_type == 2) or decoded.get("image") or decoded.get("picUrl") or decoded.get("imageUrl"):
        image_urls = _extract_live_image_urls(decoded)
        return 2, (image_urls[0] if image_urls else (fallback_summary or "[图片]")), image_urls

    if content_type == 1 or "text" in decoded:
        text_root = decoded.get("text")
        if isinstance(text_root, dict):
            text_value = str(text_root.get("text") or "").strip()
        else:
            text_value = str(text_root or "").strip()
        return 1, (text_value or fallback_summary), []

    if content_type == 3 and decoded.get("audio") is not None:
        return 3, "[语音消息]", []

    if decoded.get("title") or decoded.get("template"):
        title = str(decoded.get("title") or decoded.get("template") or fallback_summary or "[卡片消息]").strip()
        return content_type if content_type > 0 else 8, title, []

    if fallback_summary:
        return content_type if content_type > 0 else 1, fallback_summary, []
    return content_type if content_type > 0 else 1, "", []


def _extract_live_goods_fields(extension: dict[str, Any]) -> dict[str, str]:
    goods_id = (
        extension.get("itemId")
        or extension.get("itemid")
        or extension.get("goodsId")
        or extension.get("id")
        or extension.get("itemTargetUrl")
        or extension.get("itemUrl")
        or ""
    )
    normalized_goods_id = _normalize_goods_id(goods_id)
    goods_title = str(
        extension.get("itemTitle")
        or extension.get("goodsTitle")
        or extension.get("title")
        or ""
    ).strip()
    goods_cover = _normalize_image_url(
        extension.get("itemPic")
        or extension.get("itemImage")
        or extension.get("imageUrl")
        or extension.get("picUrl")
        or ""
    )
    return {
        "goodsId": str(normalized_goods_id or "").strip(),
        "goodsTitle": goods_title,
        "goodsCoverPic": goods_cover,
    }


def _parse_live_conversation(item: dict[str, Any], seller_external_uid: str) -> Optional[dict[str, Any]]:
    conversation = _parse_json_object(item.get("singleChatUserConversation") or item)
    single_conversation = _parse_json_object(conversation.get("singleChatConversation"))
    sid = _normalize_sid_value(
        single_conversation.get("cid")
        or conversation.get("cid")
        or item.get("cid")
    )
    if not sid:
        return None

    seller_id = _normalize_party_id(seller_external_uid)
    pair_first = _normalize_party_id(single_conversation.get("pairFirst"))
    pair_second = _normalize_party_id(single_conversation.get("pairSecond"))
    other_user_id = ""
    if pair_first and pair_second:
        if seller_id:
            if pair_first == seller_id:
                other_user_id = pair_second
            elif pair_second == seller_id:
                other_user_id = pair_first
        if not other_user_id:
            other_user_id = pair_second or pair_first

    single_extension = _parse_json_object(single_conversation.get("extension"))
    goods_fields = _extract_live_goods_fields(single_extension)
    last_message_wrapper = _parse_json_object(conversation.get("lastMessage"))
    last_message = _parse_json_object(last_message_wrapper.get("message") or last_message_wrapper)
    decoded, summary, extension = _decode_live_message_payload({"message": last_message})
    last_content_type, last_message_text, _ = _extract_live_message_content(decoded, summary)
    last_message_time = _normalize_message_time_value(
        conversation.get("modifyTime")
        or last_message.get("createAt")
        or last_message.get("time")
    )
    last_sender_id = _normalize_party_id(extension.get("senderUserId"))
    reminder_title = normalize_peer_name(str(extension.get("reminderTitle") or "").strip())
    peer_name = reminder_title if reminder_title and last_sender_id and last_sender_id == other_user_id else ""

    peer_user_id = _ensure_goofish_suffix(other_user_id) if other_user_id else f"sid:{sid}"
    return {
        "sid": sid,
        "peerUserId": peer_user_id,
        "peerKey": f"sid:{sid}",
        "peerUserName": peer_name,
        "lastMessage": last_message_text or summary,
        "lastContentType": last_content_type,
        "lastMessageTime": last_message_time,
        "firstMessageTime": last_message_time,
        "goodsId": goods_fields["goodsId"],
        "goodsTitle": goods_fields["goodsTitle"],
        "goodsCoverPic": goods_fields["goodsCoverPic"],
        "reminderContent": summary or last_message_text,
        "unreadCount": int(conversation.get("redPoint") or 0),
        "messageCount": 1,
        "conversationStatus": 0,
        "buyerAvatar": "",
        "goodsPrice": "",
        "goodsStatus": None,
    }


def _parse_live_history_message(
    model: dict[str, Any],
    sid: str,
    seller_external_uid: str,
    peer_user_id: str = "",
) -> Optional[dict[str, Any]]:
    message = _parse_json_object(model.get("message") or model)
    if not message:
        return None

    decoded, summary, extension = _decode_live_message_payload({"message": message})
    content_type, msg_content, image_urls = _extract_live_message_content(decoded, summary)
    sender_user_id = _ensure_goofish_suffix(extension.get("senderUserId"))
    sender_user_name = normalize_peer_name(str(extension.get("reminderTitle") or "").strip())
    seller_id = _normalize_party_id(seller_external_uid)
    sender_id = _normalize_party_id(sender_user_id)
    normalized_peer_user_id = _normalize_party_id(peer_user_id)
    direction = "OUT" if seller_id and sender_id and sender_id == seller_id else "IN"

    if direction == "OUT":
        receiver_user_id = _ensure_goofish_suffix(peer_user_id)
        peer_external_uid = receiver_user_id or _ensure_goofish_suffix(normalized_peer_user_id)
    else:
        receiver_user_id = _ensure_goofish_suffix(seller_external_uid)
        peer_external_uid = sender_user_id or _ensure_goofish_suffix(peer_user_id)

    message_id = str(message.get("messageId") or model.get("messageId") or "").strip()
    parsed = {
        "id": f"live_{message_id}" if message_id else f"live_{sid}_{_normalize_message_time_value(message.get('createAt') or message.get('time'))}",
        "pnmId": message_id,
        "sid": sid,
        "contentType": content_type,
        "msgContent": msg_content or (image_urls[0] if image_urls else summary),
        "senderUserId": sender_user_id,
        "senderUserName": sender_user_name,
        "receiverUserId": receiver_user_id,
        "peerExternalUid": peer_external_uid,
        "messageTime": _normalize_message_time_value(message.get("createAt") or message.get("time")),
        "direction": direction,
        "readStatus": 1 if direction == "OUT" else 0,
        "reminderContent": summary or ("[图片]" if content_type == 2 else msg_content),
        "reminderUrl": "",
        "imageUrls": image_urls,
        "completeMsg": _serialize_json_document(message),
        "raw": model,
    }
    if not _is_displayable_message(parsed):
        return None
    return parsed


async def _fetch_remote_conversation_user_info(account_id: int, sid: str) -> dict[str, str]:
    from .xianyu_api_service import fetch_conversation_user_info

    result = await asyncio.to_thread(fetch_conversation_user_info, account_id, sid)
    if not result or not result.get("success"):
        return {}
    data = result.get("data") or {}
    avatar = _normalize_image_url(data.get("avatar"))
    nick = normalize_peer_name(data.get("nick") or "")
    return {
        "avatar": avatar,
        "nick": nick,
    }


async def _save_conversation_user_info(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    sid: str,
    avatar: str,
    nick: str,
) -> None:
    if not sid or (not avatar and not nick):
        return
    await db.execute(text("""
        UPDATE xianyu_conversation
        SET buyer_avatar = COALESCE(NULLIF(:buyer_avatar, ''), buyer_avatar),
            buyer_name = COALESCE(NULLIF(:buyer_name, ''), buyer_name),
            updated_time = NOW()
        WHERE tenant_id = :tenant_id
          AND account_id = :account_id
          AND (
            peer_key COLLATE utf8mb4_unicode_ci = :sid_key COLLATE utf8mb4_unicode_ci
            OR external_buyer_id COLLATE utf8mb4_unicode_ci = :sid_key COLLATE utf8mb4_unicode_ci
          )
    """), {
        "tenant_id": tenant_id,
        "account_id": account_id,
        "sid_key": f"sid:{sid}",
        "buyer_avatar": avatar,
        "buyer_name": nick,
    })


async def _hydrate_online_conversation_avatars(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    conversations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates = [
        conv for conv in conversations
        if conv.get("sid") and not _normalize_image_url(conv.get("buyerAvatar"))
    ][:12]
    if not candidates:
        return conversations

    updated = False
    semaphore = asyncio.Semaphore(4)

    async def _enrich(conv: dict[str, Any]) -> None:
        nonlocal updated
        async with semaphore:
            info = await _fetch_remote_conversation_user_info(account_id, str(conv.get("sid") or ""))
        avatar = info.get("avatar") or ""
        nick = info.get("nick") or ""
        if avatar:
            conv["buyerAvatar"] = avatar
        if nick and not conv.get("peerUserName"):
            conv["peerUserName"] = nick
        if avatar or nick:
            updated = True
            await _save_conversation_user_info(
                db,
                tenant_id,
                account_id,
                str(conv.get("sid") or ""),
                avatar,
                nick,
            )

    await asyncio.gather(*(_enrich(conv) for conv in candidates))
    if updated:
        await db.commit()
    return conversations


def _to_datetime_from_millis(value: object) -> datetime:
    try:
        millis = int(value or 0)
    except (TypeError, ValueError):
        millis = 0
    if millis > 0:
        try:
            return datetime.fromtimestamp(millis / 1000)
        except (ValueError, OSError):
            pass
    return datetime.now()


def _normalize_message_time_value(value: object) -> int:
    if isinstance(value, datetime):
        try:
            normalized_value = value if value.tzinfo is not None else value.replace(tzinfo=_DB_TIMEZONE)
            return int(normalized_value.timestamp() * 1000)
        except (ValueError, OSError):
            return int(time.time() * 1000)
    if value is None:
        return int(time.time() * 1000)
    text_value = str(value).strip()
    if not text_value:
        return int(time.time() * 1000)
    if text_value.isdigit():
        return int(text_value)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            parsed = datetime.strptime(text_value, fmt).replace(tzinfo=_DB_TIMEZONE)
            return int(parsed.timestamp() * 1000)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text_value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=_DB_TIMEZONE)
        return int(parsed.timestamp() * 1000)
    except ValueError:
        return int(time.time() * 1000)


def _message_text_preview(content: object, content_type: object) -> str:
    text_value = str(content or "").strip()
    try:
        ctype = int(content_type or 1)
    except (TypeError, ValueError):
        ctype = 1
    if ctype == 2:
        return "[图片]"
    return text_value


def _coerce_message_direction(value: object) -> str:
    direction = str(value or "").upper().strip()
    if direction in {"OUT", "SEND", "1"}:
        return "OUT"
    if direction in {"IN", "RECV", "0"}:
        return "IN"
    return "IN"


def _coerce_auto_reply_flag(value: object) -> int:
    try:
        return 1 if int(value or 0) == 1 else 0
    except (TypeError, ValueError):
        return 0


def _peer_id_variants(peer_user_id: str) -> list[str]:
    raw = str(peer_user_id or "").strip()
    if not raw:
        return []
    variants = {raw}
    if raw.endswith("@goofish"):
        variants.add(raw[:-8])
    else:
        variants.add(f"{raw}@goofish")
    return [item for item in variants if item]


def _context_message_identity(message: dict[str, Any]) -> str:
    pnm_id = str(message.get("pnm_id") or message.get("pnmId") or message.get("messageUid") or "").strip()
    if pnm_id:
        return f"pnm:{pnm_id}"
    msg_id = str(message.get("id") or "").strip()
    if msg_id:
        return f"id:{msg_id}"
    direction = _coerce_message_direction(message.get("direction"))
    sender = str(message.get("sender_user_id") or message.get("senderUserId") or message.get("from_user_id") or message.get("fromUserId") or "").strip()
    receiver = str(message.get("receiver_user_id") or message.get("receiverUserId") or message.get("to_user_id") or message.get("toUserId") or "").strip()
    content = str(message.get("msg_content") or message.get("msgContent") or message.get("content") or "").strip()
    message_time = _normalize_message_time_value(message.get("message_time") or message.get("messageTime") or message.get("created_time") or message.get("createdTime"))
    return f"fallback:{direction}:{sender}:{receiver}:{message_time}:{content}"


def _normalize_party_id(value: object) -> str:
    raw = str(value or "").strip()
    return raw[:-8] if raw.endswith("@goofish") else raw


async def _load_seller_external_uid(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
) -> str:
    seller_uid_row = await db.execute(
        text("""
            SELECT external_uid
            FROM xianyu_account
            WHERE tenant_id = :tenant_id AND id = :account_id
            LIMIT 1
        """),
        {"tenant_id": tenant_id, "account_id": account_id},
    )
    return _normalize_party_id(seller_uid_row.scalar_one_or_none() or "")


def _message_matches_peer_user(message: dict[str, Any], peer_user_id: str) -> bool:
    target = _normalize_party_id(peer_user_id)
    if not target:
        return True
    candidates = {
        _normalize_party_id(message.get("senderUserId") or message.get("sender_user_id") or message.get("from_user_id") or message.get("fromUserId")),
        _normalize_party_id(message.get("receiverUserId") or message.get("receiver_user_id") or message.get("to_user_id") or message.get("toUserId")),
        _normalize_party_id(message.get("peerExternalUid") or message.get("peer_external_uid") or message.get("external_buyer_id")),
    }
    candidates.discard("")
    return target in candidates


def _message_has_unknown_peer_identity(message: dict[str, Any]) -> bool:
    candidates = [
        _normalize_party_id(message.get("senderUserId") or message.get("sender_user_id") or message.get("from_user_id") or message.get("fromUserId")),
        _normalize_party_id(message.get("receiverUserId") or message.get("receiver_user_id") or message.get("to_user_id") or message.get("toUserId")),
        _normalize_party_id(message.get("peerExternalUid") or message.get("peer_external_uid") or message.get("external_buyer_id")),
    ]
    return not any(candidates)


def _is_displayable_message(message: dict[str, Any]) -> bool:
    if _is_misplaced_pnm_sender_message(message):
        return False
    sid = str(message.get("sid") or message.get("s_id") or "").strip()
    sender = _normalize_party_id(
        message.get("senderUserId") or message.get("sender_user_id") or message.get("from_user_id") or message.get("fromUserId")
    )
    receiver = _normalize_party_id(
        message.get("receiverUserId") or message.get("receiver_user_id") or message.get("to_user_id") or message.get("toUserId")
    )
    peer = _normalize_party_id(
        message.get("peerExternalUid") or message.get("peer_external_uid") or message.get("external_buyer_id")
    )
    content = str(message.get("msgContent") or message.get("msg_content") or message.get("content") or "").strip()
    reminder = str(message.get("reminderContent") or message.get("reminder_content") or "").strip()
    pnm_id = str(message.get("pnmId") or message.get("pnm_id") or "").strip()
    return any([sender, receiver, peer, content, reminder, pnm_id]) or not sid


def _is_displayable_conversation(conversation: dict[str, Any]) -> bool:
    if _is_misplaced_pnm_sender_message(conversation):
        return False
    peer_user_id = str(conversation.get("peerUserId") or "").strip()
    last_message = str(conversation.get("lastMessage") or "").strip()
    reminder = str(conversation.get("reminderContent") or "").strip()
    goods_id = str(conversation.get("goodsId") or "").strip()
    message_count = int(conversation.get("messageCount") or 0)
    if re.fullmatch(r"\d+\.PNM", peer_user_id) and re.fullmatch(r"\d+@goofish", last_message):
        return False
    if peer_user_id.startswith("sid:") and not any([last_message, reminder, goods_id]) and message_count <= 1:
        return False
    return True


def _normalize_sid_value(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.startswith("sid:"):
        raw = raw[4:]
    return raw[:-8] if raw.endswith("@goofish") else raw


def _conversation_group_key(conversation: dict[str, Any]) -> str:
    sid = _normalize_sid_value(
        conversation.get("sid")
        or conversation.get("s_id")
        or conversation.get("conversationId")
    )
    peer_user_id = _normalize_party_id(conversation.get("peerUserId") or conversation.get("peer_user_id"))
    if sid:
        if not peer_user_id or peer_user_id.startswith("sid:"):
            return f"sid:{sid}"
        return f"sid:{sid}"
    if peer_user_id:
        return f"peer:{peer_user_id}"
    return ""


def _conversation_sort_time(conversation: dict[str, Any]) -> int:
    for key in ("lastMessageTime", "messageTime", "firstMessageTime"):
        try:
            value = int(conversation.get(key) or 0)
        except (TypeError, ValueError):
            value = 0
        if value > 0:
            return value
    return 0


def _choose_richer_conversation_row(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    primary_peer = _normalize_party_id(primary.get("peerUserId"))
    secondary_peer = _normalize_party_id(secondary.get("peerUserId"))
    primary_real_peer = bool(primary_peer and not primary_peer.startswith("sid:"))
    secondary_real_peer = bool(secondary_peer and not secondary_peer.startswith("sid:"))
    if primary_real_peer != secondary_real_peer:
        return primary if primary_real_peer else secondary

    primary_goods = bool(str(primary.get("goodsId") or "").strip())
    secondary_goods = bool(str(secondary.get("goodsId") or "").strip())
    if primary_goods != secondary_goods:
        return primary if primary_goods else secondary

    primary_messages = int(primary.get("messageCount") or 0)
    secondary_messages = int(secondary.get("messageCount") or 0)
    if primary_messages != secondary_messages:
        return primary if primary_messages >= secondary_messages else secondary

    return primary if _conversation_sort_time(primary) >= _conversation_sort_time(secondary) else secondary


def _merge_online_conversation_pair(current: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    preferred = _choose_richer_conversation_row(current, incoming)
    fallback = incoming if preferred is current else current
    latest = current if _conversation_sort_time(current) >= _conversation_sort_time(incoming) else incoming

    merged = {**fallback, **preferred}
    merged["lastMessage"] = latest.get("lastMessage", merged.get("lastMessage", ""))
    merged["lastContentType"] = latest.get("lastContentType", merged.get("lastContentType"))
    merged["reminderContent"] = latest.get("reminderContent", merged.get("reminderContent"))
    merged["lastMessageTime"] = _conversation_sort_time(latest)

    first_candidates = [value for value in [current.get("firstMessageTime"), incoming.get("firstMessageTime")] if value not in (None, "")]
    if first_candidates:
        merged["firstMessageTime"] = min(int(value) for value in first_candidates)

    merged["messageCount"] = int(current.get("messageCount") or 0) + int(incoming.get("messageCount") or 0)
    merged["unreadCount"] = max(int(current.get("unreadCount") or 0), int(incoming.get("unreadCount") or 0))
    merged["hasAiReply"] = bool(current.get("hasAiReply")) or bool(incoming.get("hasAiReply"))
    merged["lastIsAutoReply"] = bool(current.get("lastIsAutoReply")) or bool(incoming.get("lastIsAutoReply"))
    return merged


def _merge_online_conversation_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = _conversation_group_key(row)
        if not key:
            key = f"fallback:{len(grouped)}"
        grouped.setdefault(key, []).append(dict(row))

    merged_rows: list[dict[str, Any]] = []
    for group_rows in grouped.values():
        real_peer_rows = [
            row for row in group_rows
            if (peer := _normalize_party_id(row.get("peerUserId"))) and not peer.startswith("sid:")
        ]
        unique_real_peers = {
            _normalize_party_id(row.get("peerUserId"))
            for row in real_peer_rows
            if _normalize_party_id(row.get("peerUserId"))
        }
        if len(unique_real_peers) == 1:
            merged = group_rows[0]
            for row in group_rows[1:]:
                merged = _merge_online_conversation_pair(merged, row)
            merged_rows.append(merged)
        else:
            merged_rows.extend(group_rows)

    merged_rows.sort(key=_conversation_sort_time, reverse=True)
    return merged_rows


def _derive_online_conversations_next_cursor(conversations: list[dict[str, Any]]) -> int | None:
    if not conversations:
        return None
    timestamps = [
        _conversation_sort_time(conversation)
        for conversation in conversations
    ]
    timestamps = [value for value in timestamps if value > 0]
    return min(timestamps) if timestamps else None


def _has_equivalent_base_message(candidate: dict[str, Any], base_messages: list[dict[str, Any]]) -> bool:
    if int(candidate.get("isAutoReply") or candidate.get("is_auto_reply") or 0) != 1:
        return False

    candidate_direction = _coerce_message_direction(candidate.get("direction"))
    candidate_sid = str(candidate.get("sid") or candidate.get("s_id") or "").replace("@goofish", "").strip()
    candidate_content = str(candidate.get("msgContent") or candidate.get("msg_content") or candidate.get("content") or "").strip()
    candidate_sender = _normalize_party_id(
        candidate.get("senderUserId") or candidate.get("sender_user_id") or candidate.get("from_user_id") or candidate.get("fromUserId")
    )
    candidate_receiver = _normalize_party_id(
        candidate.get("receiverUserId") or candidate.get("receiver_user_id") or candidate.get("to_user_id") or candidate.get("toUserId")
    )
    candidate_time = _normalize_message_time_value(
        candidate.get("messageTime") or candidate.get("message_time") or candidate.get("createdTime") or candidate.get("created_time")
    )

    for existing in base_messages:
        if _coerce_message_direction(existing.get("direction")) != candidate_direction:
            continue
        existing_sid = str(existing.get("sid") or existing.get("s_id") or "").replace("@goofish", "").strip()
        if candidate_sid and existing_sid and existing_sid != candidate_sid:
            continue
        existing_content = str(existing.get("msgContent") or existing.get("msg_content") or existing.get("content") or "").strip()
        if existing_content != candidate_content:
            continue
        existing_sender = _normalize_party_id(
            existing.get("senderUserId") or existing.get("sender_user_id") or existing.get("from_user_id") or existing.get("fromUserId")
        )
        if candidate_sender and existing_sender != candidate_sender:
            continue
        existing_receiver = _normalize_party_id(
            existing.get("receiverUserId") or existing.get("receiver_user_id") or existing.get("to_user_id") or existing.get("toUserId")
        )
        if candidate_receiver and existing_receiver != candidate_receiver:
            continue
        existing_time = _normalize_message_time_value(
            existing.get("messageTime") or existing.get("message_time") or existing.get("createdTime") or existing.get("created_time")
        )
        if candidate_time and existing_time and abs(candidate_time - existing_time) > 15000:
            continue
        return True
    return False


async def _load_ai_reply_context_messages(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    conversation_ids: list[int],
    peer_user_id: str,
    s_id: str,
    base_messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    existing_keys = {_context_message_identity(item) for item in base_messages}
    peer_variants = _peer_id_variants(peer_user_id)
    if not conversation_ids and not peer_variants:
        return []
    query = """
            SELECT
                xm.id,
                xm.conversation_id,
                xm.content,
                xm.message_type,
                xm.direction,
                xm.is_auto_reply,
                xm.created_time,
                xm.msg_time,
                xm.from_user_id,
                xm.to_user_id,
                c.peer_key,
                c.external_buyer_id
            FROM xianyu_message xm
            JOIN xianyu_conversation c
                ON c.id = xm.conversation_id
               AND c.tenant_id = xm.tenant_id
               AND c.account_id = xm.account_id
            WHERE xm.tenant_id = :tenant_id
              AND xm.account_id = :account_id
              AND xm.deleted = 0
              AND COALESCE(xm.is_auto_reply, 0) = 1
    """
    params: dict[str, Any] = {
        "tenant_id": tenant_id,
        "account_id": account_id,
    }
    filters: list[str] = []
    bind_params = []
    if conversation_ids:
        filters.append("xm.conversation_id IN :conversation_ids")
        params["conversation_ids"] = conversation_ids
        bind_params.append(bindparam("conversation_ids", expanding=True))
    if peer_variants:
        filters.append("xm.to_user_id IN :peer_variants")
        params["peer_variants"] = peer_variants
        bind_params.append(bindparam("peer_variants", expanding=True))
    if not filters:
        return []
    query += f" AND ({' OR '.join(filters)})"
    message_times = [
        _normalize_message_time_value(item.get("messageTime") or item.get("message_time"))
        for item in base_messages
        if item.get("messageTime") or item.get("message_time")
    ]
    if message_times:
        start_ms = min(message_times) - 10 * 60 * 1000
        end_ms = max(message_times) + 10 * 60 * 1000
        params["start_time"] = _to_datetime_from_millis(start_ms)
        params["end_time"] = _to_datetime_from_millis(end_ms)
        query += " AND xm.created_time BETWEEN :start_time AND :end_time"
    rows = await db.execute(text(query).bindparams(*bind_params), params)
    messages: list[dict[str, Any]] = []
    for row in rows.mappings().all():
        message_time = _normalize_message_time_value(row.get("msg_time") or row.get("created_time"))
        peer_key = str(row.get("peer_key") or row.get("external_buyer_id") or "")
        sid = str(s_id or "").strip() or (peer_key[4:] if peer_key.startswith("sid:") else peer_key)
        candidate = {
            "id": f"legacy_auto_{row.get('id')}",
            "pnmId": "",
            "sid": sid,
            "contentType": 2 if str(row.get("message_type") or "") == "image" else 1,
            "msgContent": str(row.get("content") or ""),
            "senderUserId": str(row.get("from_user_id") or ""),
            "receiverUserId": str(row.get("to_user_id") or ""),
            "peerExternalUid": str(row.get("external_buyer_id") or ""),
            "messageTime": message_time,
            "direction": _coerce_message_direction(row.get("direction")),
            "readStatus": 1,
            "isAutoReply": 1,
            "conversationId": row.get("conversation_id"),
        }
        if _context_message_identity(candidate) in existing_keys:
            continue
        messages.append(candidate)
    return messages


async def _resolve_conversation_ids_for_context(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    s_id: str,
    peer_user_id: str,
) -> list[int]:
    conditions: list[str] = []
    params: dict[str, Any] = {
        "tenant_id": tenant_id,
        "account_id": account_id,
    }
    if s_id:
        s_id_goofish = f"{s_id}@goofish"
        params["sid_key"] = f"sid:{s_id}"
        params["sid_key_goofish"] = f"sid:{s_id_goofish}"
        params["external_sid"] = s_id
        params["external_sid_goofish"] = s_id_goofish
        conditions.append("""
            (
                c.peer_key COLLATE utf8mb4_unicode_ci IN (:sid_key, :sid_key_goofish)
                OR c.external_buyer_id COLLATE utf8mb4_unicode_ci IN (:sid_key, :sid_key_goofish, :external_sid, :external_sid_goofish)
            )
        """)
    direct_ids: list[int] = []
    if peer_user_id:
        peer_user_id_goofish = f"{peer_user_id}@goofish" if not peer_user_id.endswith("@goofish") else peer_user_id
        params["peer_user_id"] = peer_user_id
        params["peer_user_id_goofish"] = peer_user_id_goofish
        conditions.append("""
            (
                c.external_buyer_id COLLATE utf8mb4_unicode_ci IN (:peer_user_id, :peer_user_id_goofish)
                OR c.peer_external_uid COLLATE utf8mb4_unicode_ci IN (:peer_user_id, :peer_user_id_goofish)
                OR c.peer_key COLLATE utf8mb4_unicode_ci IN (:peer_user_id, :peer_user_id_goofish)
            )
        """)
    ids = set(direct_ids)
    if conditions:
        rows = await db.execute(
            text(f"""
                SELECT DISTINCT c.id
                FROM xianyu_conversation c
                WHERE c.tenant_id = :tenant_id
                  AND c.account_id = :account_id
                  AND (
                    {" OR ".join(conditions)}
                  )
            """),
            params
        )
        ids.update(int(row[0]) for row in rows.all() if row and row[0] is not None)
    return sorted(ids)


async def _merge_context_messages_with_ai_replies(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    base_messages: list[dict[str, Any]],
    s_id: str,
    peer_user_id: str,
    *,
    filter_base_messages_by_peer: bool = True,
) -> list[dict[str, Any]]:
    conversation_ids = await _resolve_conversation_ids_for_context(db, tenant_id, account_id, s_id, peer_user_id)
    ai_messages = await _load_ai_reply_context_messages(
        db, tenant_id, account_id, conversation_ids, peer_user_id, s_id, base_messages
    )
    if peer_user_id and filter_base_messages_by_peer:
        base_messages = [
            item for item in base_messages
            if _message_matches_peer_user(item, peer_user_id) or _message_has_unknown_peer_identity(item)
        ]
    if peer_user_id:
        ai_messages = [item for item in ai_messages if _message_matches_peer_user(item, peer_user_id)]
    ai_messages = [item for item in ai_messages if not _has_equivalent_base_message(item, base_messages)]
    merged = list(base_messages) + ai_messages
    deduped: dict[str, dict[str, Any]] = {}
    for item in merged:
        deduped[_context_message_identity(item)] = item
    return sorted(
        deduped.values(),
        key=lambda item: (
            _normalize_message_time_value(item.get("messageTime") or item.get("message_time")),
            str(item.get("id") or ""),
        ),
    )


def _merge_context_source_messages(
    base_messages: list[dict[str, Any]],
    live_messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for item in list(base_messages) + list(live_messages):
        if not _is_displayable_message(item):
            continue
        deduped[_context_message_identity(item)] = item
    return sorted(
        deduped.values(),
        key=lambda item: (
            _normalize_message_time_value(item.get("messageTime") or item.get("message_time")),
            str(item.get("id") or ""),
        ),
    )


async def _resolve_live_context_sid(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    peer_user_id: str,
) -> str:
    target_peer = _normalize_party_id(peer_user_id)
    if not target_peer:
        return ""
    conversations = await _fetch_live_online_conversations(
        db,
        tenant_id,
        account_id,
        limit=100,
    )
    for conversation in conversations:
        if _normalize_party_id(conversation.get("peerUserId")) == target_peer:
            return _normalize_sid_value(
                conversation.get("sid")
                or conversation.get("s_id")
                or conversation.get("conversationId")
            )
    return ""


async def _fetch_live_online_conversations(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    limit: int = 50,
    user_id: int | None = None,
) -> list[dict[str, Any]]:
    del user_id
    try:
        from .ws_client import ws_manager

        client = ws_manager.get_client(account_id)
        if not client or not getattr(client, "is_connected", False):
            return []

        seller_external_uid = await _load_seller_external_uid(db, tenant_id, account_id)
        seller_external_uid = seller_external_uid or str(getattr(client, "unb", "") or "")
        page_limit = max(min(int(limit or 50), 50), 1)
        cursor: int | None = None
        page = 0
        conversations: list[dict[str, Any]] = []

        while len(conversations) < max(int(limit or 50), 1) and page < 3:
            body = await client.list_conversations(start_timestamp=cursor, limit=page_limit)
            items = body.get("userConvs", []) if isinstance(body, dict) else []
            if not items:
                break
            for item in items:
                parsed = _parse_live_conversation(item, seller_external_uid)
                if parsed:
                    conversations.append(parsed)
            has_more = body.get("hasMore", False) if isinstance(body, dict) else False
            has_more = has_more if isinstance(has_more, bool) else str(has_more) == "1"
            cursor = body.get("nextCursor") if isinstance(body, dict) else None
            if not has_more or cursor in (None, ""):
                break
            page += 1
        return conversations[:max(int(limit or 50), 1)]
    except Exception as exc:
        logger.warning("fetch live conversations failed accountId=%d: %s", account_id, exc)
        return []


async def _fetch_live_context_messages(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    s_id: str,
    limit: int = 50,
    peer_user_id: str = "",
) -> list[dict[str, Any]]:
    try:
        from .ws_client import ws_manager

        client = ws_manager.get_client(account_id)
        if not client or not getattr(client, "is_connected", False):
            return []

        resolved_sid = _normalize_sid_value(s_id)
        if not resolved_sid and peer_user_id:
            resolved_sid = await _resolve_live_context_sid(db, tenant_id, account_id, peer_user_id)
        if not resolved_sid:
            return []

        seller_external_uid = await _load_seller_external_uid(db, tenant_id, account_id)
        seller_external_uid = seller_external_uid or str(getattr(client, "unb", "") or "")
        page_limit = max(min(int(limit or 50), 50), 20)
        cursor: int | None = None
        page = 0
        messages: list[dict[str, Any]] = []

        while len(messages) < max(int(limit or 50), 1) and page < 4:
            body = await client.list_messages(resolved_sid, start_timestamp=cursor, limit=page_limit)
            models = body.get("userMessageModels", []) if isinstance(body, dict) else []
            if not models:
                break
            for model in models:
                parsed = _parse_live_history_message(
                    model,
                    sid=resolved_sid,
                    seller_external_uid=seller_external_uid,
                    peer_user_id=peer_user_id,
                )
                if parsed:
                    messages.append(parsed)
            has_more = body.get("hasMore", False) if isinstance(body, dict) else False
            has_more = has_more if isinstance(has_more, bool) else str(has_more) == "1"
            cursor = body.get("nextCursor") if isinstance(body, dict) else None
            if not has_more or cursor in (None, ""):
                break
            page += 1

        if peer_user_id:
            messages = [
                item for item in messages
                if _message_matches_peer_user(item, peer_user_id) or _message_has_unknown_peer_identity(item)
            ]
        return _merge_context_source_messages([], messages)[:max(int(limit or 50), 1)]
    except Exception as exc:
        logger.warning(
            "fetch live context messages failed accountId=%d errorType=%s",
            account_id,
            type(exc).__name__,
        )
        return []


async def _finalize_context_messages(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    base_messages: list[dict[str, Any]],
    s_id: str,
    peer_user_id: str,
    limit: int,
    offset: int,
    *,
    filter_base_messages_by_peer: bool = True,
) -> tuple[list[dict[str, Any]], int]:
    fetch_limit = max(int(limit or 0) + int(offset or 0), int(limit or 0), 50)
    live_messages = await _fetch_live_context_messages(
        db,
        tenant_id,
        account_id,
        s_id=s_id,
        limit=fetch_limit,
        peer_user_id=peer_user_id,
    )
    merged_source = _merge_context_source_messages(base_messages, live_messages)
    if not merged_source:
        return [], 0

    merged = await _merge_context_messages_with_ai_replies(
        db,
        tenant_id,
        account_id,
        merged_source,
        s_id,
        peer_user_id,
        filter_base_messages_by_peer=filter_base_messages_by_peer,
    )
    total = len(merged)
    if total == 0:
        return [], 0
    # 从最新的消息开始分页（往前翻更旧的消息）
    # offset=0 返回最新 limit 条；offset=limit 返回更旧的 limit 条
    start = max(0, total - offset - limit)
    end = max(0, total - offset)
    return merged[start:end], total


async def _apply_ai_reply_preview(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    conversations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not conversations:
        return conversations
    peer_variants = sorted({
        variant
        for conv in conversations
        for variant in _peer_id_variants(str(conv.get("peerUserId") or conv.get("peerExternalUid") or conv.get("externalBuyerId") or ""))
    })
    if not peer_variants:
        return conversations
    rows = await db.execute(
        text("""
            SELECT
                xm.id,
                xm.conversation_id,
                xm.to_user_id,
                xm.content,
                xm.message_type,
                xm.direction,
                xm.is_auto_reply,
                xm.msg_time,
                xm.created_time
            FROM xianyu_message xm
            WHERE xm.tenant_id = :tenant_id
              AND xm.account_id = :account_id
              AND xm.deleted = 0
              AND COALESCE(xm.is_auto_reply, 0) = 1
              AND xm.to_user_id IN :peer_variants
            ORDER BY COALESCE(xm.msg_time, xm.created_time) DESC, xm.id DESC
        """).bindparams(bindparam("peer_variants", expanding=True)),
        {
            "tenant_id": tenant_id,
            "account_id": account_id,
            "peer_variants": peer_variants,
        }
    )
    ai_rows = [dict(row) for row in rows.mappings().all()]
    for conv in conversations:
        variants = set(_peer_id_variants(str(conv.get("peerUserId") or conv.get("peerExternalUid") or conv.get("externalBuyerId") or "")))
        if not variants:
            conv["hasAiReply"] = False
            conv["lastIsAutoReply"] = False
            continue
        current_time = _normalize_message_time_value(conv.get("lastMessageTime"))
        first_time = _normalize_message_time_value(conv.get("firstMessageTime") or conv.get("lastMessageTime"))
        earliest_allowed = first_time - 10 * 60 * 1000
        latest_allowed = current_time + 10 * 60 * 1000
        ai_row = next((
            row for row in ai_rows
            if str(row.get("to_user_id") or "") in variants
            and earliest_allowed <= _normalize_message_time_value(row.get("msg_time") or row.get("created_time")) <= latest_allowed
        ), None)
        if not ai_row:
            conv["hasAiReply"] = False
            conv["lastIsAutoReply"] = False
            continue
        ai_time = _normalize_message_time_value(ai_row.get("msg_time") or ai_row.get("created_time"))
        conv["hasAiReply"] = True
        conv["lastAiReplyTime"] = ai_time
        if ai_time >= current_time:
            conv["lastMessage"] = str(ai_row.get("content") or "")
            conv["lastContentType"] = 2 if str(ai_row.get("message_type") or "") == "image" else 1
            conv["lastIsAutoReply"] = True
        else:
            conv["lastIsAutoReply"] = False
    return conversations


async def _resolve_peer_id(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    msg: dict,
) -> str:
    """解析会话的 peer_id（对应 xianyu_conversation.external_buyer_id）。

    优先级：
    1. 根据方向取 senderUserId（收）或 receiverUserId（发）
    2. 如果 s_id 下已有当前账号的会话记录，优先复用已有的 external_buyer_id，
       确保同一账号内同一会话的 external_buyer_id 保持一致
    3. 从当前账号历史消息中查找 peer_id（收：sender_user_id；发：receiver_user_id）
    4. 从当前账号已有会话中查找 external_buyer_id
    5. 兜底使用 sid:xxx 作为 peer_id
    """
    direction = str(msg.get("direction") or "IN").upper()
    sender_id = str(msg.get("senderUserId") or "")
    receiver_id = str(msg.get("receiverUserId") or "")
    s_id = str(msg.get("sId") or "")

    # 首选：根据方向确定 peer_id
    peer_id = receiver_id if direction == "OUT" and receiver_id else sender_id

    # 如果解析出的 peer_id 等于卖家自己，不能拿它当买家会话键。
    # 真实日志里大量商品卡片消息 senderUserId/receiverUserId 都是卖家 external_uid，
    # 旧逻辑会把所有 sId 聚合到同一个买家，导致前端只看到 1 个会话。
    seller_uid = str(msg.get("sellerExternalUid") or "")
    # 去掉 @goofish 后缀后比较（WS 协议中有时会带后缀）
    peer_id_clean = peer_id.replace("@goofish", "").strip() if peer_id else ""
    seller_uid_clean = seller_uid.replace("@goofish", "").strip() if seller_uid else ""
    if peer_id and seller_uid and peer_id_clean == seller_uid_clean and s_id:
        logger.info(
            "_resolve_peer_id 检测到 peer_id 等于卖家自己，改用 sId 兜底: accountId=%d sId=%s sellerUid=%s",
            account_id, s_id, seller_uid
        )
        return f"sid:{s_id}"

    # 如果得到了有效的真实 peer_id，则直接使用；不要跨 sId 复用旧 external_buyer_id，
    # 否则在闲鱼协议缺失 senderUserId 的情况下会把多个会话错误合并。
    if peer_id:
        return peer_id

    # peer_id 为空时的兜底逻辑
    if s_id:
        # 兜底1：从当前账号历史消息中按方向查找 peer_id
        history_field = "receiver_user_id" if direction == "OUT" else "sender_user_id"
        recent = await db.execute(
            text(f"""
                SELECT {history_field}
                FROM xianyu_chat_message
                WHERE tenant_id = :tenant_id AND account_id = :account_id
                  AND s_id COLLATE utf8mb4_unicode_ci = :s_id COLLATE utf8mb4_unicode_ci AND deleted = 0
                  AND {history_field} IS NOT NULL AND {history_field} != ''
                ORDER BY id DESC
                LIMIT 1
            """),
            {"tenant_id": tenant_id, "account_id": account_id, "s_id": s_id}
        )
        peer_id = recent.scalar_one_or_none() or ""
        if peer_id and seller_uid and str(peer_id).replace("@goofish", "").strip() == seller_uid_clean:
            logger.info(
                "_resolve_peer_id 历史消息 peer_id 等于卖家自己，忽略并继续使用 sId: accountId=%d sId=%s sellerUid=%s",
                account_id, s_id, seller_uid
            )
            peer_id = ""

        # 兜底2：通过当前账号的 xianyu_chat_message/s_id 查找已有会话的 external_buyer_id
        conv = await db.execute(
            text("""
                SELECT c.external_buyer_id
                FROM xianyu_conversation c
                WHERE c.tenant_id = :tenant_id
                  AND c.account_id = :account_id
                  AND c.external_buyer_id IS NOT NULL
                  AND c.external_buyer_id != ''
                  AND EXISTS (
                    SELECT 1 FROM xianyu_chat_message xm
                    WHERE xm.tenant_id = c.tenant_id
                      AND xm.account_id = c.account_id
                      AND xm.s_id COLLATE utf8mb4_unicode_ci = :s_id COLLATE utf8mb4_unicode_ci
                  )
                ORDER BY c.id ASC
                LIMIT 1
            """),
            {"tenant_id": tenant_id, "account_id": account_id, "s_id": s_id}
        )
        existing_peer = conv.scalar_one_or_none() or ""
        if existing_peer:
            if seller_uid and str(existing_peer).replace("@goofish", "").strip() == seller_uid_clean:
                logger.info(
                    "_resolve_peer_id 已有会话 external_buyer_id 等于卖家自己，忽略并改用 sId: accountId=%d sId=%s sellerUid=%s",
                    account_id, s_id, seller_uid
                )
                return f"sid:{s_id}"
            if str(existing_peer).startswith("sid:"):
                return str(existing_peer)
            if peer_id and peer_id != existing_peer:
                logger.info(
                    "_resolve_peer_id 兜底逻辑：已有会话 external_buyer_id=%s，"
                    "忽略历史消息中的 peer_id=%s accountId=%d sId=%s direction=%s",
                    existing_peer, peer_id, account_id, s_id, direction
                )
            return str(existing_peer)

        if peer_id:
            return str(peer_id)

    # 兜底：当所有方式都无法解析出 peer_id 时，使用 sId 作为 peer_id，
    # 确保会话记录能被创建，后续消息可以通过 sId 关联到该会话。
    if s_id:
        logger.info(
            "_resolve_peer_id 使用 sId 兜底: accountId=%d tenantId=%d sId=%s pnmId=%s",
            account_id, tenant_id, s_id, msg.get("pnmId", "")
        )
        return f"sid:{s_id}"

    return ""


def _generate_message_uid(msg: dict, seller_external_uid: str = "") -> str:
    """生成稳定的消息唯一ID（message_uid）。

    用于去重。始终使用内容哈希：sha256(seller_uid + s_id + sender + receiver + content)。

    注意：
    1. 不包含 message_time。原因：
       - OUT 消息先入库时 messageTime=0（无服务端时间戳），推送回环到来时带真实时间戳。
       - 如果 uid 包含 message_time，两条消息的 uid 不同，去重无法命中，
         导致同一消息被存两次（一条本地时间，一条服务端时间），引发排序错乱。
       - 排除 message_time 后，去重能正确命中，由 save_chat_message 的
         去重更新逻辑用服务端时间戳覆盖 message_time。
    2. 始终使用内容哈希（而非 pnm_id）。原因：
       - 手动发送/AI 自动回复通过 send_text_message 发送后，ACK 响应不含 uuid，
         导致 save_chat_message 入库时 pnm_id 为空，message_uid = 内容哈希。
       - 随后 IM 推送回环到来时携带服务端分配的 pnm_id，如果 message_uid = pnm_id，
         则两条记录的 message_uid 不同，去重失败，产生重复消息。
       - 始终使用内容哈希后，无论 pnm_id 是否存在，同一消息的 message_uid 一致，
         去重能正确命中。
    """
    s_id = str(msg.get("sId") or "")
    sender = str(msg.get("senderUserId") or "")
    receiver = str(msg.get("receiverUserId") or "")
    content = str(msg.get("msgContent") or "")
    raw = f"{seller_external_uid}|{s_id}|{sender}|{receiver}|{content}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _extract_time_from_raw_payload(raw_payload: Any) -> int:
    """从 rawPayload 中提取消息时间戳（毫秒）。

    修复背景：当 WebSocket 协议解析器无法从字段 "5" 提取 messageTime 时，
    原实现直接用当前时间兜底，导致同一批入库的消息时间戳几乎相同（差几毫秒），
    破坏消息时间线排序。

    参考目标项目（xianyu-auto-reply/backend-web/app/api/routes/chat_new.py）：
    - _parse_message 第 817 行：msg_time = message.get("createAt", 0) or message.get("time", 0)
    - _parse_conversation 第 666 行：last_msg_time = conv.get("modifyTime", 0)

    本函数递归搜索 rawPayload 中的常见时间字段：
    - createAt / time / modifyTime / createTime / messageTime
    - 同时兼容嵌套在 message / extension / content 等子结构中的时间字段

    Returns:
        毫秒时间戳；提取失败返回 0
    """
    if not raw_payload:
        return 0

    # 优先字段名（参考目标项目的解析顺序）
    priority_keys = ("createAt", "time", "modifyTime", "createTime", "messageTime")

    def _try_parse_int(value: Any) -> int:
        if value is None:
            return 0
        if isinstance(value, (int, float)):
            return int(value)
        text = str(value).strip()
        if not text:
            return 0
        try:
            return int(text)
        except (ValueError, TypeError):
            return 0

    def _search(obj: Any, depth: int = 0) -> int:
        if depth > 5 or not obj:
            return 0
        if isinstance(obj, dict):
            # 优先在当前层级查找已知时间字段
            for key in priority_keys:
                if key in obj:
                    candidate = _try_parse_int(obj[key])
                    # 合理的时间戳范围：2000-01-01 ~ 2100-01-01（毫秒）
                    if 946684800000 < candidate < 4102444800000:
                        return candidate
            # 递归查找子节点（限制深度避免性能问题）
            for value in obj.values():
                result = _search(value, depth + 1)
                if result:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = _search(item, depth + 1)
                if result:
                    return result
        return 0

    try:
        return _search(raw_payload)
    except Exception as e:
        logger.debug("从 rawPayload 提取时间失败: %s", e)
        return 0


async def save_chat_message(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    msg: dict,
    seller_external_uid: str = "",
    sync_legacy_message: bool = True,
) -> Optional[int]:
    """保存聊天消息到 xianyu_chat_message 表（去重）。
    
    Args:
        db: 数据库会话
        tenant_id: 租户ID
        account_id: 闲鱼账号ID
        msg: 解析后的消息字典
        seller_external_uid: 卖家外部UID（externalUid/unb），用于稳定身份
        
    Returns:
        消息 ID 或 None（已存在时）
    """
    # === Step 1: 消息校验 ===
    from .ws_protocol import validate_parsed_message
    if seller_external_uid:
        msg["sellerExternalUid"] = seller_external_uid
    msg = validate_parsed_message(msg)
    
    pnm_id = msg.get("pnmId", "") or ""
    message_uid = _generate_message_uid(msg, seller_external_uid)
    parse_status = msg.get("parseStatus", "ok") or "ok"
    direction = str(msg.get("direction") or "IN").upper()
    
    # === Step 2: 去重检查（用内容哈希 message_uid，兼容旧 pnm_id 记录）===
    # 去重命中时：如果新消息带服务端时间戳（messageTime > 0），用服务端时间戳覆盖旧 message_time。
    # 这解决了 OUT 消息先入库时（messageTime=0 兜底为本地时间）后推送回环到来时（带服务端时间戳）
    # 的更新问题。服务端时间戳是权威的，应优先使用。
    #
    # 特殊处理 contentType=26（卡片更新消息/订单状态变更）：
    # 闲鱼协议中，同一订单的状态变更消息（如"我已拍下，待付款"→"我已付款，等待你发货"）
    # 可能携带相同的 pnm_id。如果仅凭 pnm_id 去重，付款消息会被拍下消息误去重跳过，
    # 导致自动发货无法触发。因此对 contentType=26 的消息，pnm_id 去重需同时匹配 reminder_content。
    content_type_raw = msg.get("contentType", 1)
    try:
        content_type_int = int(content_type_raw)
    except (TypeError, ValueError):
        content_type_int = 1
    reminder_content_str = str(msg.get("reminderContent", "") or "")
    is_card_update = content_type_int == 26

    if message_uid:
        if is_card_update:
            # contentType=26：pnm_id 去重需同时匹配 reminder_content，避免同订单不同状态变更被误去重
            existing = await db.execute(
                text("""
                    SELECT id, message_time, pnm_id FROM xianyu_chat_message
                    WHERE (message_uid = :muid
                           OR (pnm_id = :muid AND pnm_id != '' AND pnm_id IS NOT NULL)
                           OR (pnm_id = :pnm_id AND :pnm_id != '' AND pnm_id IS NOT NULL
                               AND reminder_content = :reminder_content))
                      AND tenant_id = :tenant_id AND account_id = :account_id
                    LIMIT 1
                """),
                {
                    "muid": message_uid,
                    "pnm_id": pnm_id,
                    "reminder_content": reminder_content_str,
                    "tenant_id": tenant_id,
                    "account_id": account_id,
                }
            )
        else:
            existing = await db.execute(
                text("""
                    SELECT id, message_time, pnm_id FROM xianyu_chat_message
                    WHERE (message_uid = :muid
                           OR (pnm_id = :muid AND pnm_id != '' AND pnm_id IS NOT NULL)
                           OR (pnm_id = :pnm_id AND :pnm_id != '' AND pnm_id IS NOT NULL))
                      AND tenant_id = :tenant_id AND account_id = :account_id
                    LIMIT 1
                """),
                {
                    "muid": message_uid,
                    "pnm_id": pnm_id,
                    "tenant_id": tenant_id,
                    "account_id": account_id,
                }
            )
        existing_row = existing.first()
        if existing_row:
            existing_id = existing_row[0]
            existing_msg_time = existing_row[1] or 0
            existing_pnm_id = existing_row[2] or ""
            new_msg_time = msg.get("messageTime", 0) or 0
            if isinstance(new_msg_time, (int, float)) and new_msg_time > 0 and int(new_msg_time) != int(existing_msg_time or 0):
                try:
                    await db.execute(
                        text("UPDATE xianyu_chat_message SET message_time = :mt, updated_time = NOW() WHERE id = :id"),
                        {"mt": int(new_msg_time), "id": existing_id}
                    )
                    await db.flush()
                    logger.info("消息已存在，更新 message_time: id=%d old=%s new=%d", existing_id, existing_msg_time, int(new_msg_time))
                except Exception as e:
                    logger.debug("更新 message_time 失败（可忽略）: %s", e)
            # 如果新消息带了 pnm_id 而旧记录没有，补充 pnm_id 便于后续查询
            if pnm_id and not existing_pnm_id:
                try:
                    await db.execute(
                        text("UPDATE xianyu_chat_message SET pnm_id = :pnm_id, updated_time = NOW() WHERE id = :id"),
                        {"pnm_id": pnm_id, "id": existing_id}
                    )
                    await db.flush()
                except Exception as pnm_err:
                    logger.debug("补充 pnm_id 失败（可忽略）existing_id=%d errorType=%s", existing_id, type(pnm_err).__name__)
            return None
    elif pnm_id:
        if is_card_update:
            existing = await db.execute(
                text("""
                    SELECT id, message_time FROM xianyu_chat_message
                    WHERE pnm_id = :pnm_id AND reminder_content = :reminder_content
                      AND tenant_id = :tenant_id AND account_id = :account_id
                    LIMIT 1
                """),
                {
                    "pnm_id": pnm_id,
                    "reminder_content": reminder_content_str,
                    "tenant_id": tenant_id,
                    "account_id": account_id,
                }
            )
        else:
            existing = await db.execute(
                text("SELECT id, message_time FROM xianyu_chat_message WHERE pnm_id = :pnm_id AND tenant_id = :tenant_id AND account_id = :account_id LIMIT 1"),
                {"pnm_id": pnm_id, "tenant_id": tenant_id, "account_id": account_id}
            )
        existing_row = existing.first()
        if existing_row:
            existing_id = existing_row[0]
            existing_msg_time = existing_row[1] or 0
            new_msg_time = msg.get("messageTime", 0) or 0
            if isinstance(new_msg_time, (int, float)) and new_msg_time > 0 and int(new_msg_time) != int(existing_msg_time or 0):
                try:
                    await db.execute(
                        text("UPDATE xianyu_chat_message SET message_time = :mt, updated_time = NOW() WHERE id = :id"),
                        {"mt": int(new_msg_time), "id": existing_id}
                    )
                    await db.flush()
                    logger.info("消息已存在(pnm)，更新 message_time: id=%d old=%s new=%d", existing_id, existing_msg_time, int(new_msg_time))
                except Exception as e:
                    logger.debug("更新 message_time 失败（可忽略）: %s", e)
            return None

    # 解析 peer_external_uid
    peer_external_uid = str(msg.get("receiverUserId") or "") if direction == "OUT" else str(msg.get("senderUserId") or "")

    # 插入消息
    message_time = msg.get("messageTime", 0)
    if isinstance(message_time, str):
        try:
            message_time = int(message_time)
        except (ValueError, TypeError):
            message_time = 0
    if not message_time:
        # 修复：messageTime=0 时不能盲目用当前时间，否则同一批消息时间戳几乎相同。
        # 参考目标项目（xianyu-auto-reply）：IM 消息真实时间在 createAt/time/modifyTime 字段。
        # 先尝试从 rawPayload 中提取这些字段，提取失败才用当前时间作为最后兜底。
        message_time = _extract_time_from_raw_payload(msg.get("rawPayload") or msg.get("raw_payload"))
        if message_time:
            logger.info(
                "save_chat_message 从 rawPayload 兜底提取时间: sId=%s pnmId=%s messageTime=%d",
                msg.get("sId", ""), pnm_id, message_time
            )
        else:
            # 最后兜底：用当前时间，但记录警告便于排查
            message_time = int(time.time() * 1000)
            logger.warning(
                "save_chat_message messageTime=0 且 rawPayload 无时间字段，用当前时间兜底: "
                "sId=%s pnmId=%s senderUserId=%s contentLen=%d",
                msg.get("sId", ""), pnm_id,
                str(msg.get("senderUserId", ""))[:30],
                len(msg.get("msgContent", "") or "")
            )

    s_id = msg.get("sId", "")
    logger.info(
        "save_chat_message: accountId=%d sId=%s pnmId=%s msgUid=%s parseStatus=%s senderUserId=%s contentLen=%d",
        account_id, s_id, pnm_id, message_uid, parse_status,
        msg.get("senderUserId", "")[:30],
        len(msg.get("msgContent", "") or "")
    )

    # 构建 complete_msg（含完整解析上下文）
    complete_msg = json.dumps(msg, ensure_ascii=False)
    raw_payload = _serialize_json_document(msg.get("rawPayload", msg.get("raw_payload")))

    # 插入消息（捕获 IntegrityError 做幂等处理，避免并发去重窗口导致整条消息丢失）
    try:
        result = await db.execute(
            text("""
            INSERT INTO xianyu_chat_message (
                tenant_id, account_id, seller_external_uid, pnm_id, message_uid,
                s_id, content_type, msg_content,
                sender_user_id, receiver_user_id, sender_user_name,
                peer_external_uid, xy_goods_id, message_time,
                direction, parse_status, reminder_content, reminder_url,
                complete_msg, raw_payload, read_status, deleted, created_time, updated_time
            ) VALUES (
                :tenant_id, :account_id, :seller_external_uid, :pnm_id, :message_uid,
                :s_id, :content_type, :msg_content,
                :sender_user_id, :receiver_user_id, :sender_user_name,
                :peer_external_uid, :xy_goods_id, :message_time,
                :direction, :parse_status, :reminder_content, :reminder_url,
                :complete_msg, :raw_payload, :read_status, 0, NOW(), NOW()
            )
        """),
        {
            "tenant_id": tenant_id,
            "account_id": account_id,
            "seller_external_uid": seller_external_uid or None,
            "pnm_id": pnm_id or None,
            "message_uid": message_uid or None,
            "s_id": msg.get("sId", ""),
            "content_type": msg.get("contentType", 1),
            "msg_content": msg.get("msgContent", ""),
            "sender_user_id": msg.get("senderUserId", ""),
            "receiver_user_id": msg.get("receiverUserId", ""),
            "sender_user_name": normalize_peer_name(msg.get("senderUserName", "")),
            "peer_external_uid": peer_external_uid or None,
            "xy_goods_id": msg.get("xyGoodsId", ""),
            "message_time": message_time,
            "direction": direction,
            "parse_status": parse_status,
            "reminder_content": msg.get("reminderContent", ""),
            "reminder_url": msg.get("reminderUrl", ""),
            "complete_msg": complete_msg,
            "raw_payload": raw_payload,
            "read_status": 1 if direction == "OUT" else int(msg.get("readStatus", 0) or 0),
            }
        )
        await db.flush()
        new_id = result.lastrowid
    except IntegrityError:
        # 并发去重窗口：两个任务都通过了上面的 SELECT 去重检查，
        # 第二个 INSERT 会触发唯一键冲突。旧实现直接抛错导致整条消息丢失。
        # 此处回滚事务并返回 None，消息已由先到达的插入保存，不丢失数据。
        await db.rollback()
        logger.info(
            "消息插入冲突（已存在），跳过: accountId=%d pnmId=%s msgUid=%s",
            account_id, pnm_id, message_uid
        )
        return None

    # 更新会话（xianyu_conversation）— 只有解析成功或可降级的消息才进入会话
    s_id = msg.get("sId", "")
    if s_id and parse_status in ("ok", "partial"):
        try:
            await _upsert_conversation(db, tenant_id, account_id, msg, seller_external_uid)
        except Exception as conv_err:
            logger.error(
                "更新会话失败（消息已保存，会话创建失败不影响消息存储）: "
                "accountId=%d sId=%s pnmId=%s error=%s",
                account_id, s_id, pnm_id, conv_err
            )

    # 插入 xianyu_message（兼容旧数据流）
    if sync_legacy_message:
        try:
            await _insert_xianyu_message(db, tenant_id, account_id, msg)
        except Exception as msg_err:
            logger.error(
            "插入xianyu_message失败（不影响主流程）: "
            "accountId=%d sId=%s error=%s",
                account_id, s_id, msg_err
            )

    return new_id


async def _upsert_conversation(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    msg: dict,
    seller_external_uid: str = "",
):
    """更新或创建会话记录。"""
    s_id = msg.get("sId", "")
    direction = str(msg.get("direction") or "IN").upper()
    sender_id = msg.get("senderUserId", "")
    receiver_id = msg.get("receiverUserId", "")
    peer_id = await _resolve_peer_id(db, tenant_id, account_id, msg)

    # 生成 peer_key（稳定对端标识）
    peer_external_uid = peer_id if peer_id and not peer_id.startswith("sid:") else ""
    is_sid_fallback = peer_id.startswith("sid:") if peer_id else True
    peer_key = peer_external_uid if peer_external_uid else (f"sid:{s_id}" if s_id else peer_id or "")

    logger.info(
        "_upsert_conversation: accountId=%d sId=%s pnmId=%s peerId=%s peerKey=%s senderUserId=%s receiverUserId=%s",
        account_id, s_id, msg.get("pnmId", ""), (peer_id or "(空)")[:30] if peer_id else "(空)",
        peer_key[:30] if peer_key else "(空)",
        sender_id[:30] if sender_id else "(空)", receiver_id[:30] if receiver_id else "(空)"
    )
    if not peer_id:
        logger.warning(
            "跳过会话更新：peerId 为空 accountId=%d tenantId=%d sId=%s pnmId=%s",
            account_id, tenant_id, s_id, msg.get("pnmId", "")
        )
        return
    content = msg.get("msgContent", "")
    message_time = msg.get("messageTime", 0)
    content_type = msg.get("contentType", 1)
    xy_goods_id = msg.get("xyGoodsId", "")
    normalized_goods_id = _normalize_goods_id(xy_goods_id)
    
    # 提取买家名称（经过系统文本过滤）
    # IN消息：sender_user_name 是买家名称
    # OUT消息：无法直接获取买家名称，保留已有值
    buyer_name = ""
    if direction == "IN":
        buyer_name = normalize_peer_name(str(msg.get("senderUserName", "") or ""))
    # 如果 senderUserName 是"我"或卖家名称，则忽略（可能是系统自己发的消息被推送回来）
    if buyer_name and seller_external_uid:
        # 通过 xianyu_account 表检查是否是卖家自己的名称
        pass  # 简化处理：买家名称不应该是"我"
    if buyer_name in ("我", "", seller_external_uid):
        buyer_name = ""

    # 将 message_time 转换为 datetime
    from datetime import datetime
    if message_time and message_time > 0:
        try:
            msg_dt = datetime.fromtimestamp(message_time / 1000)
        except (ValueError, OSError):
            msg_dt = datetime.now()
    else:
        msg_dt = datetime.now()

    # 查找已有会话（优先按 peer_key，兜底按 peer_id/account_id 加 s_id）
    existing = await db.execute(
        text("""
            SELECT id FROM xianyu_conversation
            WHERE tenant_id = :tenant_id AND account_id = :account_id
              AND peer_key COLLATE utf8mb4_unicode_ci = :pkey COLLATE utf8mb4_unicode_ci
            ORDER BY id DESC LIMIT 1
        """),
        {"tenant_id": tenant_id, "account_id": account_id, "pkey": peer_key}
    )
    row = existing.mappings().first()
    conv = row["id"] if row else None

    # 兜底：通过 s_id 查找（兼容迁移期间的旧数据）
    if not conv and s_id:
        fallback = await db.execute(
            text("""
                SELECT c.id, c.peer_key FROM xianyu_conversation c
                WHERE c.tenant_id = :tenant_id
                  AND c.account_id = :account_id
                  AND EXISTS (
                    SELECT 1 FROM xianyu_chat_message cm
                    WHERE cm.s_id COLLATE utf8mb4_unicode_ci = :s_id COLLATE utf8mb4_unicode_ci
                      AND cm.tenant_id = c.tenant_id
                      AND cm.account_id = c.account_id
                      AND cm.deleted = 0
                  )
                ORDER BY c.id DESC LIMIT 1
            """),
            {"s_id": s_id, "tenant_id": tenant_id, "account_id": account_id}
        )
        fallback_row = fallback.mappings().first()
        if fallback_row:
            conv = fallback_row["id"]
            old_peer_key = fallback_row.get("peer_key", "")
            # 关键修复：如果已有会话的 peer_key 是 sid:xxx 但与当前 s_id 不同，
            # 说明这是另一个不同会话的消息被误匹配，不应该合并。
            # 应创建新的独立会话。
            if old_peer_key and old_peer_key.startswith("sid:") and s_id:
                old_sid = old_peer_key[4:]  # 去掉 "sid:" 前缀
                if old_sid != s_id:
                    logger.warning(
                        "_upsert_conversation s_id 兜底找到不同 sid 的会话，"
                        "跳过合并: accountId=%d sId=%s oldPeerKey=%s",
                        account_id, s_id, old_peer_key
                    )
                    conv = None
                    old_peer_key = None
            # 如果 peer_key 已变更（如从 sid:xxx 变为真实 uid），更新
            if old_peer_key and old_peer_key != peer_key:
                await db.execute(
                    text("""
                        UPDATE xianyu_conversation
                        SET peer_key = :new_pkey,
                            peer_external_uid = :new_peuid,
                            updated_time = NOW()
                        WHERE id = :id
                    """),
                    {"new_pkey": peer_key, "new_peuid": peer_external_uid or None, "id": conv}
                )
                logger.info(
                    "_upsert_conversation 更新 peer_key: %s -> %s, convId=%s",
                    old_peer_key, peer_key, conv
                )

    content_preview = content[:200] if content else f"[消息类型: {content_type}]"
    unread_increment = 0 if direction == "OUT" else 1

    if conv:
        update_fields = """
                last_message_time = :msg_time,
                    last_message_content = :content,
                    unread_count = COALESCE(unread_count, 0) + :unread_increment,
                    updated_time = NOW()
            """
        update_params = {
            "id": conv,
            "msg_time": msg_dt,
            "content": content_preview,
            "unread_increment": unread_increment,
        }
        # 如果有买家名称且会话尚未保存买家名称，更新
        if buyer_name:
            update_fields = f"""
                    buyer_name = COALESCE(NULLIF(buyer_name, ''), :buyer_name),
                    {update_fields.strip()}
            """
            update_params["buyer_name"] = buyer_name
        # 如果有商品ID且会话尚未保存商品ID，更新（关键修复：之前只在新创建会话时才存 goods_id）
        if normalized_goods_id:
            update_fields = f"""
                    goods_id = COALESCE(NULLIF(goods_id, ''), :goods_id),
                    {update_fields.strip()}
            """
            update_params["goods_id"] = str(normalized_goods_id)
        update_fields = "SET " + update_fields.strip()
        await db.execute(
            text(f"""
                UPDATE xianyu_conversation
                {update_fields}
                WHERE id = :id
            """),
            update_params
        )
    else:
        # 创建新会话
        try:
            logger.info(
                "准备插入新会话: accountId=%d tenantId=%d peerKey=%s externalBuyerId=%s xyGoodsId=%s isSidFallback=%s",
                account_id, tenant_id, peer_key, peer_id, xy_goods_id, is_sid_fallback
            )
            await db.execute(
                text("""
                    INSERT INTO xianyu_conversation (
                        tenant_id, account_id, peer_key, external_buyer_id, peer_external_uid,
                        buyer_name, goods_id, last_message_content, last_message_time, unread_count,
                        status, created_time, updated_time
                    ) VALUES (
                        :tenant_id, :account_id, :peer_key, :external_buyer_id, :peer_external_uid,
                        :buyer_name, :goods_id, :last_message_content, :last_message_time, :unread_count,
                        0, NOW(), NOW()
                    )
                """),
                {
                    "tenant_id": tenant_id,
                    "account_id": account_id,
                    "peer_key": peer_key,
                    "external_buyer_id": peer_id,
                    "peer_external_uid": peer_external_uid or None,
                    "buyer_name": buyer_name or None,
                    "goods_id": str(normalized_goods_id or xy_goods_id or "") or None,
                    "last_message_content": content_preview,
                    "last_message_time": msg_dt,
                    "unread_count": unread_increment,
                }
            )
        except Exception as insert_err:
            logger.error(
                "插入会话失败: accountId=%d tenantId=%d peerKey=%s externalBuyerId=%s error=%s",
                account_id, tenant_id, peer_key, peer_id, insert_err, exc_info=True
            )
            raise


async def _insert_xianyu_message(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    msg: dict,
):
    """兼容旧数据流：同步写入 xianyu_message 表。"""
    direction = str(msg.get("direction") or "IN").upper()
    # xianyu_message.direction 列是 tinyint（0=IN/received, 1=OUT/sent），不能用字符串
    direction_val = 1 if direction == "OUT" else 0
    sender_user_id = str(msg.get("senderUserId") or "")
    receiver_user_id = str(msg.get("receiverUserId") or "")
    message_time = msg.get("messageTime") or int(time.time() * 1000)

    if isinstance(message_time, str):
        try:
            message_time = int(message_time)
        except (TypeError, ValueError):
            message_time = int(time.time() * 1000)

    await db.execute(
        text("""
            INSERT INTO xianyu_message (
                tenant_id, account_id, conversation_id, from_user_id, to_user_id,
                content, message_type, direction, created_time, updated_time,
                deleted
            ) VALUES (
                :tenant_id, :account_id, NULL, :from_user_id, :to_user_id,
                :content, :message_type, :direction, FROM_UNIXTIME(:created_time / 1000), NOW(),
                0
            )
        """),
        {
            "tenant_id": tenant_id,
            "account_id": account_id,
            "from_user_id": sender_user_id or None,
            "to_user_id": receiver_user_id or None,
            "content": msg.get("msgContent") or "",
            "message_type": str(msg.get("contentType") or 1),
            "direction": direction_val,
            "created_time": message_time,
        }
    )


async def update_message_read_status(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    pnm_id: str,
    read_status: int,
):
    """更新消息已读状态。"""
    await db.execute(
        text("""
            UPDATE xianyu_chat_message
            SET read_status = :read_status,
                updated_time = NOW()
            WHERE tenant_id = :tenant_id
              AND account_id = :account_id
              AND pnm_id = :pnm_id
              AND deleted = 0
        """),
        {
            "tenant_id": tenant_id,
            "account_id": account_id,
            "pnm_id": pnm_id,
            "read_status": read_status,
        }
    )


async def save_raw_websocket_message(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    message_type: str,
    raw_data: str,
):
    """保存原始 WebSocket 消息（调试用）。"""
    await db.execute(
        text("""
            INSERT INTO xianyu_operation_log (
                tenant_id, account_id, operation_type, operation_desc,
                request_data, response_data, status, created_time, updated_time,
                deleted
            ) VALUES (
                :tenant_id, :account_id, 'WS_RAW_MESSAGE', :operation_desc,
                :request_data, :response_data, 1, NOW(), NOW(),
                0
            )
        """),
        {
            "tenant_id": tenant_id,
            "account_id": account_id,
            "operation_desc": f"原始 WS 消息: {message_type}",
            "request_data": raw_data[:65535],
            "response_data": None,
        }
    )


async def get_recent_messages(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    limit: int = 50,
) -> list[XianyuChatMessage]:
    """获取最近消息。"""
    result = await db.execute(
        text("""
            SELECT * FROM xianyu_chat_message
            WHERE tenant_id = :tenant_id
              AND account_id = :account_id
              AND deleted = 0
            ORDER BY message_time DESC
            LIMIT :limit
        """),
        {
            "tenant_id": tenant_id,
            "account_id": account_id,
            "limit": limit,
        }
    )
    return result.scalars().all()


async def get_message_count(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
) -> int:
    """获取消息总数。"""
    result = await db.execute(
        text("""
            SELECT COUNT(*) FROM xianyu_chat_message
            WHERE tenant_id = :tenant_id
              AND account_id = :account_id
              AND deleted = 0
        """),
        {
            "tenant_id": tenant_id,
            "account_id": account_id,
        }
    )
    return result.scalar() or 0


async def get_unread_count(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
) -> int:
    """获取未读消息数。"""
    result = await db.execute(
        text("""
            SELECT COUNT(*) FROM xianyu_chat_message
            WHERE tenant_id = :tenant_id
              AND account_id = :account_id
              AND direction = 'IN'
              AND read_status = 0
              AND deleted = 0
        """),
        {
            "tenant_id": tenant_id,
            "account_id": account_id,
        }
    )
    return result.scalar() or 0


async def get_online_conversations(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    limit: int = 50,
    before_message_time: int | None = None,
    user_id: int | None = None,
) -> list[dict]:
    """获取在线会话列表。

    按 (peer_user_id, goods_id) 聚合会话。同一买家+同一商品的多个 sId 合并为 1 个会话，
    同一买家不同商品仍为不同会话。当 peer_user_id 为 sid:xxx 兜底时（无法解析真实买家UID），
    则按 sId 聚合避免误合并。
    """
    query_sql = """
            SELECT
                MIN(conv.id) AS conversationId,
                SUBSTRING_INDEX(GROUP_CONCAT(base.s_id ORDER BY base.message_time DESC SEPARATOR ','), ',', 1) AS sid,
                MAX(base.peer_user_id) AS peerUserId,
                COALESCE(
                    MAX(conv.peer_key),
                    MAX(base.conv_peer_key),
                    CONCAT('sid:', SUBSTRING_INDEX(GROUP_CONCAT(base.s_id ORDER BY base.message_time DESC SEPARATOR ','), ',', 1))
                ) AS peerKey,
                COALESCE(
                    SUBSTRING_INDEX(GROUP_CONCAT(NULLIF(base.inbound_sender_name, '') ORDER BY base.message_time DESC SEPARATOR ','), ',', 1),
                    SUBSTRING_INDEX(GROUP_CONCAT(NULLIF(base.history_sender_name, '') ORDER BY base.message_time DESC SEPARATOR ','), ',', 1),
                    ''
                ) AS peerUserName,
                SUBSTRING_INDEX(GROUP_CONCAT(base.msg_content ORDER BY base.message_time DESC SEPARATOR ','), ',', 1) AS lastMessage,
                CAST(SUBSTRING_INDEX(GROUP_CONCAT(base.content_type ORDER BY base.message_time DESC SEPARATOR ','), ',', 1) AS UNSIGNED) AS lastContentType,
                MAX(base.message_time) AS lastMessageTime,
                MIN(base.message_time) AS firstMessageTime,
                COALESCE(
                    SUBSTRING_INDEX(GROUP_CONCAT(NULLIF(base.xy_goods_id, '') ORDER BY base.message_time DESC SEPARATOR ','), ',', 1),
                    ''
                ) AS goodsId,
                COALESCE(MAX(NULLIF(conv.goods_title, '')), '') AS goodsTitle,
                COALESCE(MAX(NULLIF(conv.goods_cover_pic, '')), '') AS goodsCoverPic,
                SUBSTRING_INDEX(GROUP_CONCAT(NULLIF(base.reminder_content, '') ORDER BY base.message_time DESC SEPARATOR '\x01'), '\x01', 1) AS reminderContent,
                COALESCE(MAX(conv.unread_count), SUM(CASE WHEN base.direction = 'IN' AND COALESCE(base.read_status, 0) = 0 THEN 1 ELSE 0 END)) AS unreadCount,
                COUNT(*) AS messageCount,
                COALESCE(MAX(conv.status), 0) AS conversationStatus,
                COALESCE(MAX(NULLIF(conv.buyer_avatar, '')), '') AS buyerAvatar,
                '' AS goodsPrice,
                NULL AS goodsStatus
            FROM (
                SELECT
                    base.tenant_id,
                    base.account_id,
                    CASE
                        WHEN base.s_id LIKE '%@goofish' THEN SUBSTRING_INDEX(base.s_id, '@', 1)
                        ELSE base.s_id
                    END AS s_id,
                    base.msg_content,
                    base.content_type,
                    base.message_time,
                    base.xy_goods_id,
                    base.reminder_content,
                    base.direction,
                    base.read_status,
                    base.sender_user_id,
                    base.receiver_user_id,
                    COALESCE(
                        NULLIF(NULLIF(base.peer_external_uid, ''), a.external_uid),
                        NULLIF(
                            CASE
                                WHEN base.direction = 'OUT' THEN
                                    CASE
                                        WHEN base.receiver_user_id IS NOT NULL
                                          AND base.receiver_user_id != ''
                                          AND (a.external_uid IS NULL OR base.receiver_user_id != a.external_uid)
                                        THEN base.receiver_user_id
                                        ELSE NULL
                                    END
                                ELSE
                                    CASE
                                        WHEN base.sender_user_id IS NOT NULL
                                          AND base.sender_user_id != ''
                                          AND (a.external_uid IS NULL OR base.sender_user_id != a.external_uid)
                                        THEN base.sender_user_id
                                        ELSE NULL
                                    END
                            END,
                            ''
                        ),
                        NULLIF(conv_by_sid.external_buyer_id, ''),
                        CONCAT('sid:', base.s_id)
                    ) AS peer_user_id,
                    COALESCE(
                        NULLIF(conv_by_sid.peer_key, ''),
                        NULLIF(conv_by_sid.external_buyer_id, ''),
                        CONCAT('sid:', base.s_id)
                    ) AS conv_peer_key,
                    NULLIF(CASE WHEN base.direction = 'IN' THEN base.sender_user_name ELSE NULL END, '') AS inbound_sender_name,
                    -- 性能优化：移除相关子查询 history_sender_name（对每行都执行一次全表扫描）。
                    -- 由 _enrich_online_conversations_batch 的 fallback_map 兜底处理（等价实现）。
                    CAST(NULL AS CHAR) AS history_sender_name
                FROM xianyu_chat_message base
                JOIN xianyu_account a
                    ON a.id = base.account_id
                    AND a.tenant_id = base.tenant_id
                    AND (:user_id IS NULL OR a.user_id IS NULL OR a.user_id = :user_id)
                LEFT JOIN xianyu_conversation conv_by_sid
                    ON conv_by_sid.tenant_id = base.tenant_id
                    AND conv_by_sid.account_id = base.account_id
                    AND (
                        conv_by_sid.peer_key COLLATE utf8mb4_unicode_ci = CONCAT('sid:', base.s_id) COLLATE utf8mb4_unicode_ci
                        OR conv_by_sid.external_buyer_id COLLATE utf8mb4_unicode_ci = CONCAT('sid:', base.s_id) COLLATE utf8mb4_unicode_ci
                    )
                WHERE base.tenant_id = :tenant_id
                  AND base.account_id = :account_id
                  AND base.deleted = 0
                  AND base.content_type NOT IN (32)
                  AND base.s_id IS NOT NULL
                  AND base.s_id != ''
            ) base
            LEFT JOIN xianyu_conversation conv
                ON conv.tenant_id = base.tenant_id
                AND conv.account_id = base.account_id
                AND (
                    conv.peer_key COLLATE utf8mb4_unicode_ci = CONCAT('sid:', base.s_id) COLLATE utf8mb4_unicode_ci
                    OR conv.external_buyer_id COLLATE utf8mb4_unicode_ci = CONCAT('sid:', base.s_id) COLLATE utf8mb4_unicode_ci
                )
            GROUP BY
                CASE
                    WHEN base.peer_user_id LIKE 'sid:%' OR base.peer_user_id = '' THEN CONCAT('sid:', base.s_id)
                    ELSE base.peer_user_id
                END,
                COALESCE(NULLIF(base.xy_goods_id, ''), '')
        """
    params: dict[str, Any] = {
        "tenant_id": tenant_id,
        "account_id": account_id,
        "limit": limit,
        "user_id": user_id,
    }
    if before_message_time is not None:
        query_sql += """
            HAVING MAX(base.message_time) < :before_message_time
        """
        params["before_message_time"] = before_message_time
    query_sql += """
            ORDER BY MAX(base.message_time) DESC
            LIMIT :limit
        """
    rows = await db.execute(text(query_sql), params)
    seller_external_uid = await _load_seller_external_uid(db, tenant_id, account_id)
    result = [dict(row) for row in rows.mappings().all()]
    if seller_external_uid:
        result = [
            row for row in result
            if _normalize_party_id(row.get("peerUserId")) != seller_external_uid
        ]
    result = [row for row in result if _is_displayable_conversation(row)]

    if not result and before_message_time is None:
        result = await _fetch_live_online_conversations(
            db,
            tenant_id,
            account_id,
            limit=limit,
            user_id=user_id,
        )
        result = [row for row in result if _is_displayable_conversation(row)]

    # === 性能优化：live conversations 通过外部 HTTP 调用，不应阻塞首次响应 ===
    # 后台异步触发拉取，下次刷新时即可拿到最新数据；本次响应先返回 DB 数据
    if before_message_time is None:
        try:
            asyncio.create_task(_fetch_live_online_conversations_safe(
                db, tenant_id, account_id, limit=limit, user_id=user_id
            ))
        except Exception:
            # 后台任务触发失败不影响主流程
            pass

    result = _merge_online_conversation_rows(result)
    result = await _apply_ai_reply_preview(db, tenant_id, account_id, result)
    logger.info(
        "get_online_conversations: tenantId=%d accountId=%d 返回 %d 条会话（按 peer_user_id+goods_id 聚合）",
        tenant_id, account_id, len(result)
    )

    # === 性能优化：将 N+1 后处理改为批量查询 ===
    # 之前对每个会话（最多200条）依次执行 5 次独立 SQL，最坏 1000 次串行查询。
    # 现在改为 5 次批量 IN 查询，再用内存匹配回填到对应会话。
    result = await _enrich_online_conversations_batch(
        db, tenant_id, account_id, result
    )

    # === 性能优化：远程头像拉取改为后台异步，不阻塞响应 ===
    # 之前会等待最多 12 个外部 HTTP 调用，现在只读 DB 缓存，远程拉取后台异步进行
    result = _hydrate_online_conversation_avatars_from_cache(result)
    try:
        asyncio.create_task(_hydrate_online_conversation_avatars_async(
            db, tenant_id, account_id, result
        ))
    except Exception as task_err:
        logger.debug("启动后台头像拉取任务失败（可忽略）errorType=%s", type(task_err).__name__)

    # === 后台异步拉取商品封面图（针对不在 xianyu_goods 表中的商品）===
    try:
        asyncio.create_task(_fetch_goods_covers_async(
            tenant_id, account_id, result
        ))
    except Exception as task_err:
        logger.debug("启动后台商品封面拉取任务失败（可忽略）errorType=%s", type(task_err).__name__)

    if result:
        for r in result[:20]:
            logger.info(
                "  会话: sid=%s peerUserId=%s peerUserName=%s lastMsg=%s msgCount=%s goodsId=%s goodsTitle=%s goodsPrice=%s goodsCoverPic=%s",
                r.get("sid"), r.get("peerUserId"), r.get("peerUserName"),
                str(r.get("lastMessage", ""))[:30], r.get("messageCount"),
                r.get("goodsId"), r.get("goodsTitle"),
                r.get("goodsPrice"), r.get("goodsCoverPic")
            )
    return result


# 简单的内存缓存：避免短时间重复调用 IM 导致限流（flow control）
# key: (tenant_id, account_id, cursor, page_size), value: (timestamp, result)
_online_conversations_cache: dict[tuple, tuple[float, dict[str, Any]]] = {}
# IM 数据缓存 TTL：10 秒内复用 IM 拉取结果，避免轮询触发限流
_ONLINE_CONVERSATIONS_CACHE_TTL = 10.0  # 秒
# 后台 IM 刷新去抖动：同一 (tenant, account, cursor) 在此时间内不重复触发
_im_refresh_inflight: dict[tuple, float] = {}
_IM_REFRESH_DEBOUNCE = 5.0  # 秒


async def _refresh_im_conversations_background(
    tenant_id: int,
    account_id: int,
    cursor: int | None,
    page_size: int,
    user_id: int | None,
) -> None:
    """后台异步调用 IM WebSocket 拉取会话并更新缓存。

    非阻塞：调用方立即返回 DB 数据，IM 数据到达后更新缓存供下次请求使用。
    带去抖动：同一 key 在 _IM_REFRESH_DEBOUNCE 秒内不重复触发。
    """
    import time as _time
    from .ws_client import ws_manager

    cache_key = (tenant_id, account_id, cursor, page_size)
    now = _time.time()
    last = _im_refresh_inflight.get(cache_key, 0)
    if now - last < _IM_REFRESH_DEBOUNCE:
        return  # 已有刷新在进行或刚完成，跳过
    _im_refresh_inflight[cache_key] = now

    try:
        client = ws_manager.get_client(account_id)
        if not client or not getattr(client, "is_connected", False):
            return

        # 使用独立 DB session（后台任务不能用请求 session）
        from ..core.database import async_session
        from ..core.database import async_session
        async with async_session() as bg_db:
            result = await _fetch_live_online_conversations_page(
                bg_db,
                tenant_id,
                account_id,
                client,
                cursor=cursor,
                page_size=page_size,
            )
            if result is None:
                return
            _online_conversations_cache[cache_key] = (_time.time(), result)
            logger.info(
                "后台 IM 刷新完成 tenantId=%d accountId=%d cursor=%s 返回 %d 条 hasMore=%s",
                tenant_id, account_id, cursor, len(result["conversations"]), result["hasMore"],
            )
            return
            seller_external_uid = await _load_seller_external_uid(bg_db, tenant_id, account_id)
            seller_external_uid = seller_external_uid or str(getattr(client, "unb", "") or "")

            try:
                body = await client.list_conversations(start_timestamp=cursor, limit=page_size)
            except Exception as exc:
                logger.debug("后台 IM 刷新失败 tenantId=%d accountId=%d: %s", tenant_id, account_id, exc)
                return

            # 检测 IM 限流
            body_str = str(body) if isinstance(body, dict) else str(body or "")
            body_code = body.get("code") if isinstance(body, dict) else None
            is_flow_controled = (
                str(body_code) == "400600001"
                or "flow control" in body_str.lower()
                or (isinstance(body, dict) and "userConvs" not in body and "reason" in body)
            )
            if is_flow_controled:
                logger.debug("后台 IM 刷新被限流 tenantId=%d accountId=%d", tenant_id, account_id)
                return

            items = body.get("userConvs", []) if isinstance(body, dict) else []
            conversations: list[dict[str, Any]] = []
            for item in items:
                parsed = _parse_live_conversation(item, seller_external_uid)
                if parsed:
                    conversations.append(parsed)

            has_more = body.get("hasMore", False) if isinstance(body, dict) else False
            has_more = has_more if isinstance(has_more, bool) else str(has_more) == "1"
            next_cursor = body.get("nextCursor") if isinstance(body, dict) else None

            if seller_external_uid:
                conversations = [
                    row for row in conversations
                    if _normalize_party_id(row.get("peerUserId")) != seller_external_uid
                ]
            conversations = [row for row in conversations if _is_displayable_conversation(row)]
            conversations = _hydrate_online_conversation_avatars_from_cache(conversations)

            if cursor is None:
                existing_cached = _online_conversations_cache.get(cache_key)
                existing_result = existing_cached[1] if existing_cached else {}
                existing_conversations = existing_result.get("conversations", []) if isinstance(existing_result, dict) else []
                conversations = _merge_online_conversation_rows([
                    *existing_conversations,
                    *conversations,
                ])
                if has_more and next_cursor in (None, ""):
                    next_cursor = _derive_online_conversations_next_cursor(conversations)

            result = {
                "conversations": conversations,
                "hasMore": has_more,
                "nextCursor": next_cursor,
            }
            _online_conversations_cache[cache_key] = (_time.time(), result)
            logger.info(
                "后台 IM 刷新完成 tenantId=%d accountId=%d cursor=%s 返回 %d 条, hasMore=%s",
                tenant_id, account_id, cursor, len(conversations), has_more,
            )
    except Exception as exc:
        logger.debug("后台 IM 刷新异常 tenantId=%d accountId=%d: %s", tenant_id, account_id, exc)


async def _fetch_live_online_conversations_page(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    client: Any,
    *,
    cursor: int | None,
    page_size: int,
) -> dict[str, Any] | None:
    import asyncio as _asyncio

    if not client or not getattr(client, "is_connected", False):
        return None

    seller_external_uid = await _load_seller_external_uid(db, tenant_id, account_id)
    seller_external_uid = seller_external_uid or str(getattr(client, "unb", "") or "")

    try:
        body = await _asyncio.wait_for(
            client.list_conversations(start_timestamp=cursor, limit=page_size),
            timeout=2.0,
        )
    except _asyncio.TimeoutError:
        logger.warning("IM 分页超时（2 秒）tenantId=%d accountId=%d cursor=%s", tenant_id, account_id, cursor)
        return None
    except Exception as exc:
        logger.warning("IM WebSocket 调用失败 tenantId=%d accountId=%d cursor=%s: %s", tenant_id, account_id, cursor, exc)
        return None

    body_str = str(body) if isinstance(body, dict) else str(body or "")
    body_code = body.get("code") if isinstance(body, dict) else None
    is_flow_controled = (
        str(body_code) == "400600001"
        or "flow control" in body_str.lower()
        or (isinstance(body, dict) and "userConvs" not in body and "reason" in body)
    )
    if is_flow_controled:
        logger.warning("IM 返回限流 tenantId=%d accountId=%d cursor=%s code=%s", tenant_id, account_id, cursor, body_code)
        return None

    items = body.get("userConvs", []) if isinstance(body, dict) else []
    conversations: list[dict[str, Any]] = []
    for item in items:
        parsed = _parse_live_conversation(item, seller_external_uid)
        if parsed:
            conversations.append(parsed)

    has_more = body.get("hasMore", False) if isinstance(body, dict) else False
    has_more = has_more if isinstance(has_more, bool) else str(has_more) == "1"
    next_cursor = body.get("nextCursor") if isinstance(body, dict) else None

    if seller_external_uid:
        conversations = [
            row for row in conversations
            if _normalize_party_id(row.get("peerUserId")) != seller_external_uid
        ]
    conversations = [row for row in conversations if _is_displayable_conversation(row)]
    conversations = _hydrate_online_conversation_avatars_from_cache(conversations)
    if has_more and next_cursor in (None, ""):
        next_cursor = _derive_online_conversations_next_cursor(conversations)

    # === 将 IM 会话的 goods_cover_pic / goods_title 持久化到 xianyu_conversation 表 ===
    goods_updates: list[tuple[str, str, str]] = []
    for conv in conversations:
        sid = str(conv.get("sid", "") or "").strip()
        cover_pic = conv.get("goodsCoverPic", "") or ""
        goods_title = conv.get("goodsTitle", "") or ""
        if sid and (cover_pic or goods_title):
            goods_updates.append((cover_pic, goods_title, sid))
    if goods_updates:
        try:
            for cover_pic, goods_title, sid in goods_updates:
                sid_key = f"sid:{sid}"
                set_parts = []
                params: dict[str, Any] = {"sid_key": sid_key}
                if cover_pic:
                    set_parts.append("goods_cover_pic = COALESCE(NULLIF(goods_cover_pic, ''), :cover_pic)")
                    params["cover_pic"] = cover_pic
                if goods_title:
                    set_parts.append("goods_title = COALESCE(NULLIF(goods_title, ''), :goods_title)")
                    params["goods_title"] = goods_title
                if set_parts:
                    await db.execute(
                        text(f"""
                            UPDATE xianyu_conversation
                            SET {', '.join(set_parts)}
                            WHERE tenant_id = :tenant_id
                              AND account_id = :account_id
                              AND (
                                peer_key COLLATE utf8mb4_unicode_ci = :sid_key COLLATE utf8mb4_unicode_ci
                                OR external_buyer_id COLLATE utf8mb4_unicode_ci = :sid_key COLLATE utf8mb4_unicode_ci
                              )
                        """),
                        {**params, "tenant_id": tenant_id, "account_id": account_id},
                    )
        except Exception as e:
            logger.debug("持久化 IM goods_cover_pic 到 xianyu_conversation 失败: %s", e)

    return {
        "conversations": conversations,
        "hasMore": has_more,
        "nextCursor": next_cursor,
    }


async def get_online_conversations_paged(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    cursor: int | None = None,
    page_size: int = 20,
    user_id: int | None = None,
) -> dict[str, Any]:
    """获取在线会话列表（1 秒内响应，支持 cursor 分页）。

    性能优化策略（解决 20 秒超时问题）：
    - 立即返回 DB 聚合数据（< 100ms）或缓存数据
    - 后台异步触发 IM WebSocket 刷新（不阻塞响应）
    - IM 数据到达后写入缓存，下次请求即可看到最新数据
    - 带 10 秒缓存 + 5 秒去抖动，避免轮询触发 IM 限流

    cursor 分页：
    - cursor=None：第一页，返回 DB 最新会话 + 后台 IM 刷新
    - cursor=<timestamp>：后续页，使用缓存或 IM 拉取（带 2 秒超时）
    """
    import time as _time
    import asyncio as _asyncio
    from .ws_client import ws_manager

    cache_key = (tenant_id, account_id, cursor, page_size)
    now = _time.time()
    cached = _online_conversations_cache.get(cache_key)
    if cached:
        cached_ts, cached_result = cached
        if now - cached_ts < _ONLINE_CONVERSATIONS_CACHE_TTL:
            logger.info(
                "get_online_conversations_paged: 命中缓存 tenantId=%d accountId=%d cursor=%s pageSize=%d",
                tenant_id, account_id, cursor, page_size,
            )
            return cached_result

    # 第一页（cursor=None）：立即返回 DB 数据，后台异步刷新 IM
    if cursor is None:
        # 立即从 DB 聚合数据（< 100ms）
        conversations = await get_online_conversations(
            db=db, tenant_id=tenant_id, account_id=account_id,
            limit=page_size, user_id=user_id,
        )
        result = {
            "conversations": conversations,
            "hasMore": len(conversations) >= page_size,
            "nextCursor": _derive_online_conversations_next_cursor(conversations) if len(conversations) >= page_size else None,
        }
        _online_conversations_cache[cache_key] = (_time.time(), result)

        # 后台异步刷新 IM（不阻塞响应）—— 仅当 WebSocket 已连接时
        client = ws_manager.get_client(account_id)
        if client and getattr(client, "is_connected", False):
            _asyncio.create_task(
                _refresh_im_conversations_background(
                    tenant_id, account_id, cursor, page_size, user_id,
                )
            )

        logger.info(
            "get_online_conversations_paged: DB 即时返回 tenantId=%d accountId=%d cursor=%s 返回 %d 条（后台 IM 刷新中）",
            tenant_id, account_id, cursor, len(conversations),
        )
        return result

    # 后续页：优先返回 DB 本地分页结果，后台再尝试刷新 IM 缓存。
    conversations = await get_online_conversations(
        db=db,
        tenant_id=tenant_id,
        account_id=account_id,
        limit=page_size,
        before_message_time=cursor,
        user_id=user_id,
    )
    if conversations:
        result = {
            "conversations": conversations,
            "hasMore": len(conversations) >= page_size,
            "nextCursor": _derive_online_conversations_next_cursor(conversations) if len(conversations) >= page_size else None,
        }
        _online_conversations_cache[cache_key] = (_time.time(), result)
        client = ws_manager.get_client(account_id)
        if client and getattr(client, "is_connected", False):
            _asyncio.create_task(
                _refresh_im_conversations_background(
                    tenant_id, account_id, cursor, page_size, user_id,
                )
            )
        logger.info(
            "get_online_conversations_paged: DB cursor fallback tenantId=%d accountId=%d cursor=%s 返回 %d 条",
            tenant_id, account_id, cursor, len(conversations),
        )
        return result

    # DB 没有更多本地页时，再尝试实时 IM 分页。
    client = ws_manager.get_client(account_id)
    if not client or not getattr(client, "is_connected", False):
        # WebSocket 未连接，返回空页
        return {"conversations": [], "hasMore": False, "nextCursor": None}

    seller_external_uid = await _load_seller_external_uid(db, tenant_id, account_id)
    seller_external_uid = seller_external_uid or str(getattr(client, "unb", "") or "")

    try:
        # 2 秒超时，避免 20 秒阻塞
        body = await _asyncio.wait_for(
            client.list_conversations(start_timestamp=cursor, limit=page_size),
            timeout=2.0,
        )
    except _asyncio.TimeoutError:
        logger.warning("IM 分页超时(2s) tenantId=%d accountId=%d cursor=%s", tenant_id, account_id, cursor)
        return {"conversations": [], "hasMore": False, "nextCursor": None}
    except Exception as exc:
        logger.warning("IM WebSocket 调用失败: %s", exc)
        return {"conversations": [], "hasMore": False, "nextCursor": None}

    # 检测 IM 限流
    body_str = str(body) if isinstance(body, dict) else str(body or "")
    body_code = body.get("code") if isinstance(body, dict) else None
    is_flow_controled = (
        str(body_code) == "400600001"
        or "flow control" in body_str.lower()
        or (isinstance(body, dict) and "userConvs" not in body and "reason" in body)
    )
    if is_flow_controled:
        logger.warning("IM 返回限流 code=%s, 返回空页", body_code)
        return {"conversations": [], "hasMore": False, "nextCursor": None}

    items = body.get("userConvs", []) if isinstance(body, dict) else []
    conversations: list[dict[str, Any]] = []
    for item in items:
        parsed = _parse_live_conversation(item, seller_external_uid)
        if parsed:
            conversations.append(parsed)

    has_more = body.get("hasMore", False) if isinstance(body, dict) else False
    has_more = has_more if isinstance(has_more, bool) else str(has_more) == "1"
    next_cursor = body.get("nextCursor") if isinstance(body, dict) else None

    if seller_external_uid:
        conversations = [
            row for row in conversations
            if _normalize_party_id(row.get("peerUserId")) != seller_external_uid
        ]
    conversations = [row for row in conversations if _is_displayable_conversation(row)]
    conversations = _hydrate_online_conversation_avatars_from_cache(conversations)

    logger.info(
        "get_online_conversations_paged: IM 分页 tenantId=%d accountId=%d cursor=%s 返回 %d 条, hasMore=%s, nextCursor=%s",
        tenant_id, account_id, cursor, len(conversations), has_more, next_cursor,
    )
    result = {
        "conversations": conversations,
        "hasMore": has_more,
        "nextCursor": next_cursor,
    }
    _online_conversations_cache[cache_key] = (_time.time(), result)
    return result


async def _fetch_live_online_conversations_safe(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    limit: int = 50,
    user_id: int | None = None,
) -> None:
    """后台异步拉取 live conversations 并写库，不阻塞主响应。

    作为账号切换时的预热：本次响应返回 DB 数据，下次刷新即可看到 live 数据。
    使用独立 session 避免与请求 session 共享生命周期。
    """
    try:
        from ..core.database import async_session
        async with async_session() as bg_db:
            await _fetch_live_online_conversations(
                bg_db,
                tenant_id,
                account_id,
                limit=limit,
                user_id=user_id,
            )
    except Exception as exc:
        logger.debug("后台拉取 live conversations 失败（可忽略）: %s", exc)


async def _hydrate_online_conversation_avatars_async(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    conversations: list[dict[str, Any]],
) -> None:
    """后台异步拉取远程头像并写库，不阻塞主响应。

    使用独立 session 避免与请求 session 共享生命周期。
    """
    try:
        from ..core.database import async_session
        async with async_session() as bg_db:
            await _hydrate_online_conversation_avatars(
                bg_db, tenant_id, account_id, conversations
            )
    except Exception as exc:
        logger.debug("后台拉取远程头像失败（可忽略）: %s", exc)


def _hydrate_online_conversation_avatars_from_cache(
    conversations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """仅做内存层面的 image URL 规范化，不发起任何外部 HTTP 调用。

    远程头像由 _hydrate_online_conversation_avatars_async 后台异步拉取，
    下次刷新会从 DB 拿到最新头像。本次响应先返回已有 DB 缓存。
    """
    for conv in conversations:
        avatar = conv.get("buyerAvatar") or ""
        if avatar:
            conv["buyerAvatar"] = _normalize_image_url(avatar)
    return conversations


async def _fetch_goods_covers_async(
    tenant_id: int,
    account_id: int,
    conversations: list[dict[str, Any]],
) -> None:
    """后台异步通过 crawler-service 搜索 API 拉取商品封面图。

    对 xianyu_conversation.goods_cover_pic 为空的商品，使用 goods_title
    作为关键词调用 crawler-service 的 /api/goofish/search 端点搜索，
    在搜索结果中匹配 itemId 后提取 imageUrl 作为封面图。

    使用搜索 API 而非商品详情 API，因为后者会触发 Baxia 风控
    (FAIL_SYS_USER_VALIDATE)。
    """
    if not conversations:
        return

    # 收集需要拉取封面图的 goods_id（cover 为空且有 goods_id）
    goods_ids_need_fetch: list[str] = []
    goods_id_to_sids: dict[str, list[str]] = {}
    for conv in conversations:
        cover = conv.get("goodsCoverPic") or ""
        goods_id = conv.get("goodsId") or ""
        sid = conv.get("sid") or ""
        if goods_id and not cover and sid:
            goods_ids_need_fetch.append(goods_id)
            goods_id_to_sids.setdefault(goods_id, []).append(sid)

    if not goods_ids_need_fetch:
        return

    unique_goods_ids = list({g for g in goods_ids_need_fetch if g})
    if not unique_goods_ids:
        return

    try:
        import os
        from ..core.database import async_session
        from sqlalchemy import select
        from ..models.entities import XianyuAccountAuth
        from ..core.cookie_crypto import decrypt_cookie_if_needed
        from ..core.config import settings
        import httpx

        # 获取账号 Cookie
        async with async_session() as db:
            result = await db.execute(
                select(XianyuAccountAuth).where(
                    XianyuAccountAuth.account_id == account_id,
                    XianyuAccountAuth.tenant_id == tenant_id,
                    XianyuAccountAuth.deleted == 0,
                )
            )
            auth = result.scalar_one_or_none()
            if not auth or not auth.encrypted_cookie:
                logger.debug("拉取商品封面图跳过：账号未登录 account_id=%d", account_id)
                return
            cookie_str = decrypt_cookie_if_needed(auth.encrypted_cookie)

            # 同时获取每个商品的标题（用于搜索）
            goods_id_to_title: dict[str, str] = {}
            if unique_goods_ids:
                placeholders = ",".join([f":gid{i}" for i in range(len(unique_goods_ids))])
                params = {f"gid{i}": gid for i, gid in enumerate(unique_goods_ids)}
                params["tenant_id"] = tenant_id
                params["account_id"] = account_id
                result = await db.execute(text(f"""
                    SELECT DISTINCT goods_id, goods_title
                    FROM xianyu_conversation
                    WHERE tenant_id = :tenant_id
                      AND account_id = :account_id
                      AND deleted = 0
                      AND goods_id IN ({placeholders})
                      AND goods_title IS NOT NULL AND goods_title != ''
                """), params)
                for row in result.fetchall():
                    goods_id_to_title[str(row[0])] = row[1] or ""

        if not cookie_str:
            logger.debug("拉取商品封面图跳过：Cookie 解密失败 account_id=%d", account_id)
            return

        crawler_base = (os.getenv("CRAWLER_SERVICE_URL") or "http://localhost:3001").rstrip("/")
        search_url = f"{crawler_base}/api/goofish/search"
        headers = {
            "X-Internal-Token": settings.effective_internal_api_token,
            "X-Internal-Tenant-Id": str(tenant_id),
        }

        # 并发搜索，限制并发数为 2（Playwright 浏览器实例较重）
        semaphore = asyncio.Semaphore(2)
        cover_map: dict[str, str] = {}

        async def _search_one(goods_id: str) -> None:
            title = goods_id_to_title.get(goods_id, "")
            if not title:
                return
            # 取标题前 30 个字符作为搜索关键词
            # （20 字符太短会导致搜索结果偏少，降低匹配率；
            #  30 字符能覆盖核心商品名，搜索结果更全面）
            keyword = title[:30].strip()
            if not keyword:
                return
            async with semaphore:
                try:
                    # trust_env=False 直连，绕过本地代理 idle timeout
                    async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
                        resp = await client.post(
                            search_url,
                            headers=headers,
                            json={"q": keyword, "page": 1, "pageSize": 10, "cookie": cookie_str},
                        )
                        resp.raise_for_status()
                        data = resp.json()
                    if not data.get("ok"):
                        logger.debug("搜索 API 返回失败: goods_id=%s keyword=%s", goods_id, keyword)
                        return
                    items = data.get("items", [])
                    # 优先精确匹配 itemId
                    for item in items:
                        if str(item.get("itemId") or "") == goods_id:
                            image_url = item.get("imageUrl") or ""
                            if image_url:
                                normalized = _normalize_image_url(image_url)
                                if normalized:
                                    cover_map[goods_id] = normalized
                                    logger.info("搜索精确匹配商品封面图: goods_id=%s keyword=%s cover=%s", goods_id, keyword, normalized[:60])
                                    return
                    # 兜底：itemId 未匹配时，使用 title 包含原始 goods_title 的第一个结果
                    # （goods_title 可能是从消息中提取的截断标题，搜索结果的 title 包含
                    #  这个截断字符串，说明是同一商品的不同卖家列表）
                    for item in items:
                        item_id = str(item.get("itemId") or "")
                        item_title = item.get("title") or ""
                        if not item_id or not item_title:
                            continue
                        if title and title in item_title:
                            image_url = item.get("imageUrl") or ""
                            if image_url:
                                normalized = _normalize_image_url(image_url)
                                if normalized:
                                    cover_map[goods_id] = normalized
                                    logger.info("搜索标题包含匹配商品封面图: goods_id=%s keyword=%s cover=%s", goods_id, keyword, normalized[:60])
                                    return
                    logger.debug("搜索未匹配到商品: goods_id=%s keyword=%s results=%d", goods_id, keyword, len(items))
                except Exception as exc:
                    logger.debug("搜索商品封面图失败: goods_id=%s err=%s", goods_id, exc)

        await asyncio.gather(*(_search_one(gid) for gid in unique_goods_ids[:10]))

        if not cover_map:
            return

        # 写回 xianyu_conversation 表
        async with async_session() as db:
            for goods_id, cover_url in cover_map.items():
                sids = goods_id_to_sids.get(goods_id, [])
                for sid in sids:
                    sid_key = f"sid:{sid}"
                    await db.execute(text("""
                        UPDATE xianyu_conversation
                        SET goods_cover_pic = :cover_pic, updated_time = NOW()
                        WHERE tenant_id = :tenant_id
                          AND account_id = :account_id
                          AND deleted = 0
                          AND (
                            peer_key COLLATE utf8mb4_unicode_ci = :sid_key COLLATE utf8mb4_unicode_ci
                            OR external_buyer_id COLLATE utf8mb4_unicode_ci = :sid_key COLLATE utf8mb4_unicode_ci
                          )
                    """), {
                        "tenant_id": tenant_id,
                        "account_id": account_id,
                        "sid_key": sid_key,
                        "cover_pic": cover_url,
                    })
            await db.commit()
            logger.info("拉取商品封面图完成: account_id=%d 更新 %d 个封面图", account_id, len(cover_map))

    except Exception as exc:
        logger.debug("后台拉取商品封面图失败（可忽略）: %s", exc)


async def _enrich_online_conversations_batch(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    conversations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """批量补全会话的用户名、商品信息。

    将原本 N+1 查询（每会话 5 次独立 SQL）改为 5 次批量 IN 查询，再在内存里匹配回填。
    """
    if not conversations:
        return conversations

    # 收集需要兜底的 sid 列表 和 goods_id 列表
    sids_need_fallback: list[str] = []  # 需要 fallback_row 的 sid（goods_id 或 peer_user_name 为空）
    goods_ids: list[str] = []            # 所有非空 goods_id
    peer_user_ids_real: list[str] = []   # 真实（非 sid:）peer_user_id 且无 peer_user_name

    # 用于内存匹配的索引
    by_sid: dict[str, dict[str, Any]] = {}
    by_goods_id: dict[str, list[dict[str, Any]]] = {}
    by_peer_id_real: dict[str, list[dict[str, Any]]] = {}

    for conv in conversations:
        sid = conv.get("sid", "")
        peer_user_id = conv.get("peerUserId", "") or ""
        peer_user_name = conv.get("peerUserName", "") or ""
        goods_id = conv.get("goodsId", "") or ""

        if sid:
            by_sid.setdefault(sid, conv)
            if (not goods_id or not peer_user_name):
                sids_need_fallback.append(sid)

        if goods_id:
            goods_ids.append(goods_id)
            by_goods_id.setdefault(goods_id, []).append(conv)

        if not peer_user_name and peer_user_id and not peer_user_id.startswith("sid:"):
            peer_user_ids_real.append(peer_user_id)
            by_peer_id_real.setdefault(peer_user_id, []).append(conv)

    # === 批量查询1：fallback_row（每个 sid 取最新 5 条 IN 消息）===
    fallback_map: dict[str, list[dict[str, Any]]] = {}
    if sids_need_fallback:
        unique_sids = list({s for s in sids_need_fallback if s})
        if unique_sids:
            try:
                fb_rows = await db.execute(
                    text("""
                        SELECT
                            s_id,
                            xy_goods_id,
                            reminder_url,
                            reminder_content,
                            sender_user_name,
                            message_time,
                            id
                        FROM xianyu_chat_message
                        WHERE tenant_id = :tenant_id
                          AND account_id = :account_id
                          AND s_id COLLATE utf8mb4_unicode_ci IN :sids
                          AND deleted = 0
                          AND direction = 'IN'
                          AND (
                            (xy_goods_id IS NOT NULL AND xy_goods_id != '')
                            OR (reminder_url IS NOT NULL AND reminder_url != '')
                            OR (sender_user_name IS NOT NULL AND sender_user_name != '' AND sender_user_name != '我')
                            OR (reminder_content IS NOT NULL AND reminder_content != '')
                          )
                        ORDER BY message_time DESC, id DESC
                    """).bindparams(bindparam("sids", expanding=True)),
                    {
                        "tenant_id": tenant_id,
                        "account_id": account_id,
                        "sids": unique_sids,
                    }
                )
                for fb in fb_rows.mappings().all():
                    fb_sid = str(fb.get("s_id") or "")
                    if not fb_sid:
                        continue
                    fallback_map.setdefault(fb_sid, []).append(dict(fb))
                    # 每个 sid 最多保留 5 条
                    if len(fallback_map[fb_sid]) >= 5:
                        # 由于按时间倒序，前 5 条已是最新的
                        pass
            except Exception as e:
                logger.debug("批量 fallback_row 查询失败: %s", e)

    # 应用 fallback 结果
    for sid, fb_list in fallback_map.items():
        conv = by_sid.get(sid)
        if not conv:
            continue
        goods_id = conv.get("goodsId", "") or ""
        peer_user_name = conv.get("peerUserName", "") or ""
        for fb in fb_list[:5]:
            fb_goods_id = str(fb.get("xy_goods_id") or "")
            fb_reminder_url = str(fb.get("reminder_url") or "")
            fb_reminder_content = str(fb.get("reminder_content") or "")
            fb_sender_name = str(fb.get("sender_user_name") or "")

            if not goods_id:
                if fb_goods_id and fb_goods_id.isdigit():
                    goods_id = fb_goods_id
                    conv["goodsId"] = goods_id
                elif fb_reminder_url:
                    m = re.search(r'[?&]itemId=(\d+)', fb_reminder_url)
                    if not m:
                        m = re.search(r'[?&]id=(\d+)', fb_reminder_url)
                    if m:
                        goods_id = m.group(1)
                        conv["goodsId"] = goods_id

            if not peer_user_name:
                if fb_sender_name and fb_sender_name not in ("我", "买家", ""):
                    cleaned = normalize_peer_name(fb_sender_name)
                    if cleaned:
                        peer_user_name = cleaned
                        conv["peerUserName"] = cleaned
                if not peer_user_name and fb_reminder_content:
                    extracted = extract_username_from_reminder(fb_reminder_content)
                    if extracted:
                        cleaned = normalize_peer_name(extracted)
                        if cleaned:
                            peer_user_name = cleaned
                            conv["peerUserName"] = cleaned

            if goods_id and peer_user_name:
                break

    # 重新收集需要补 goods_id 的会话（fallback 后可能新增）
    goods_ids = []
    by_goods_id = {}
    for conv in conversations:
        goods_id = conv.get("goodsId", "") or ""
        if goods_id:
            goods_ids.append(goods_id)
            by_goods_id.setdefault(goods_id, []).append(conv)

    # === 批量查询2：xianyu_goods 商品信息 ===
    goods_data_map: dict[str, dict[str, Any]] = {}
    if goods_ids:
        unique_goods_ids = list({g for g in goods_ids if g})
        if unique_goods_ids:
            try:
                goods_rows = await db.execute(
                    text("""
                        SELECT external_goods_id, goods_id, title, cover_pic,
                               image_url, image_urls, detail_info, sold_price, status
                        FROM xianyu_goods
                        WHERE tenant_id = :tenant_id
                          AND account_id = :account_id
                          AND deleted = 0
                          AND (external_goods_id IN :goods_ids OR goods_id IN :goods_ids)
                    """).bindparams(
                        bindparam("goods_ids", expanding=True)
                    ),
                    {
                        "tenant_id": tenant_id,
                        "account_id": account_id,
                        "goods_ids": unique_goods_ids,
                    }
                )
                for gr in goods_rows.mappings().all():
                    ext_id = str(gr.get("external_goods_id") or "")
                    gid = str(gr.get("goods_id") or "")
                    # 同一 goods_id 可能有多条记录，取第一条
                    for key in (ext_id, gid):
                        if key and key not in goods_data_map:
                            goods_data_map[key] = dict(gr)
            except Exception as e:
                logger.debug("批量商品查询失败: %s", e)

    # 应用商品信息
    sids_need_listing: list[str] = []  # 仍缺商品标题的会话，需要查商品卡片消息
    for conv in conversations:
        goods_id = conv.get("goodsId", "") or ""
        if not goods_id:
            continue
        goods_data = goods_data_map.get(goods_id)
        if not goods_data:
            # 没匹配到商品记录，标记需要查商品卡片消息
            sid = conv.get("sid", "")
            if sid and (not conv.get("goodsTitle") or str(conv.get("goodsTitle", "")).strip() == ""):
                sids_need_listing.append(sid)
            continue
        if not conv.get("goodsTitle") or conv["goodsTitle"] == goods_id:
            conv["goodsTitle"] = goods_data.get("title") or ""
        if not conv.get("goodsCoverPic"):
            cover_pic = (
                _normalize_image_url(goods_data.get("cover_pic"))
                or _normalize_image_url(goods_data.get("image_url"))
                or _extract_cover_from_text_blob(goods_data.get("image_urls"))
                or _extract_cover_from_text_blob(goods_data.get("detail_info"))
            )
            if cover_pic:
                conv["goodsCoverPic"] = cover_pic
        if not conv.get("goodsPrice"):
            conv["goodsPrice"] = goods_data.get("sold_price") or ""
        if conv.get("goodsStatus") is None:
            conv["goodsStatus"] = goods_data.get("status")
        # 如果商品标题仍空，标记需要查商品卡片消息
        sid = conv.get("sid", "")
        if sid and (not conv.get("goodsTitle") or str(conv.get("goodsTitle", "")).strip() == ""):
            sids_need_listing.append(sid)

    # === 批量查询3：订单商品标题（仅对仍缺标题且 goods_id 存在的会话）===
    goods_ids_for_order_title = []
    for conv in conversations:
        goods_id = conv.get("goodsId", "") or ""
        if goods_id and (not conv.get("goodsTitle") or str(conv.get("goodsTitle", "")).strip() == ""):
            goods_ids_for_order_title.append(goods_id)
    if goods_ids_for_order_title:
        unique_goods_ids = list({g for g in goods_ids_for_order_title if g})
        if unique_goods_ids:
            try:
                order_item_rows = await db.execute(
                    text("""
                        SELECT oi.goods_title, o.external_order_id, oi.goods_id
                        FROM xianyu_trade_order_item oi
                        JOIN xianyu_trade_order o ON o.id = oi.order_id
                        WHERE o.tenant_id = :tenant_id
                          AND o.account_id = :account_id
                          AND o.deleted = 0
                          AND oi.deleted = 0
                          AND (o.external_order_id IN :goods_ids OR oi.goods_id IN :goods_ids)
                          AND oi.goods_title IS NOT NULL
                          AND oi.goods_title != ''
                        ORDER BY o.id DESC
                    """).bindparams(
                        bindparam("goods_ids", expanding=True)
                    ),
                    {
                        "tenant_id": tenant_id,
                        "account_id": account_id,
                        "goods_ids": unique_goods_ids,
                    }
                )
                order_title_map: dict[str, str] = {}
                for oi in order_item_rows.mappings().all():
                    ext_id = str(oi.get("external_order_id") or "")
                    gid = str(oi.get("goods_id") or "")
                    title = str(oi.get("goods_title") or "")
                    if not title:
                        continue
                    for key in (ext_id, gid):
                        if key and key not in order_title_map:
                            order_title_map[key] = title
                for conv in conversations:
                    goods_id = conv.get("goodsId", "") or ""
                    if not goods_id:
                        continue
                    title = order_title_map.get(goods_id)
                    if title and (not conv.get("goodsTitle") or str(conv.get("goodsTitle", "")).strip() == ""):
                        conv["goodsTitle"] = title
            except Exception as e:
                logger.debug("批量订单商品标题查询失败: %s", e)

    # === 批量查询4：商品卡片消息（content_type=8，仅对仍缺标题的会话）===
    if sids_need_listing:
        unique_sids = list({s for s in sids_need_listing if s})
        if unique_sids:
            try:
                listing_rows = await db.execute(
                    text("""
                        SELECT s_id, msg_content
                        FROM xianyu_chat_message
                        WHERE tenant_id = :tenant_id
                          AND account_id = :account_id
                          AND s_id COLLATE utf8mb4_unicode_ci IN :sids
                          AND direction = 'OUT'
                          AND content_type = 8
                          AND msg_content IS NOT NULL
                          AND msg_content != ''
                        ORDER BY id DESC
                    """).bindparams(bindparam("sids", expanding=True)),
                    {
                        "tenant_id": tenant_id,
                        "account_id": account_id,
                        "sids": unique_sids,
                    }
                )
                listing_map: dict[str, str] = {}
                for lr in listing_rows.mappings().all():
                    lr_sid = str(lr.get("s_id") or "")
                    if not lr_sid or lr_sid in listing_map:
                        continue
                    listing_map[lr_sid] = str(lr.get("msg_content") or "")[:200]
                for conv in conversations:
                    sid = conv.get("sid", "")
                    if not sid:
                        continue
                    if not conv.get("goodsTitle") or str(conv.get("goodsTitle", "")).strip() == "":
                        content = listing_map.get(sid)
                        if content:
                            conv["goodsTitle"] = content
            except Exception as e:
                logger.debug("批量商品卡片消息查询失败: %s", e)

    # === 批量查询5：订单表买家名称（仅对真实 peer_user_id 且无 peer_user_name 的会话）===
    # 重新收集 fallback 后仍缺 peer_user_name 的会话
    peer_user_ids_real = []
    by_peer_id_real = {}
    for conv in conversations:
        peer_user_id = conv.get("peerUserId", "") or ""
        peer_user_name = conv.get("peerUserName", "") or ""
        if not peer_user_name and peer_user_id and not peer_user_id.startswith("sid:"):
            peer_user_ids_real.append(peer_user_id)
            by_peer_id_real.setdefault(peer_user_id, []).append(conv)

    if peer_user_ids_real:
        # 收集所有可能的 buyer_id 变体（带/不带 @goofish）
        all_variants: list[str] = []
        for pid in peer_user_ids_real:
            all_variants.extend(_peer_id_variants(pid))
        unique_variants = list({v for v in all_variants if v})
        if unique_variants:
            try:
                order_buyer_rows = await db.execute(
                    text("""
                        SELECT buyer_id, COALESCE(NULLIF(buyer_nickname, ''), NULLIF(buyer_name, '')) AS buyer_display_name
                        FROM xianyu_trade_order
                        WHERE tenant_id = :tenant_id
                          AND account_id = :account_id
                          AND deleted = 0
                          AND buyer_id IN :buyer_variants
                          AND COALESCE(NULLIF(buyer_nickname, ''), NULLIF(buyer_name, '')) IS NOT NULL
                        ORDER BY id DESC
                    """).bindparams(bindparam("buyer_variants", expanding=True)),
                    {
                        "tenant_id": tenant_id,
                        "account_id": account_id,
                        "buyer_variants": unique_variants,
                    }
                )
                buyer_name_map: dict[str, str] = {}
                for ob in order_buyer_rows.mappings().all():
                    bid = str(ob.get("buyer_id") or "")
                    name = str(ob.get("buyer_display_name") or "")
                    if not bid or not name:
                        continue
                    # 只记录第一次（按 id DESC 已是最新的）
                    if bid not in buyer_name_map:
                        buyer_name_map[bid] = name
                for pid, convs in by_peer_id_real.items():
                    name = None
                    for variant in _peer_id_variants(pid):
                        if variant in buyer_name_map:
                            name = buyer_name_map[variant]
                            break
                    if not name:
                        continue
                    for conv in convs:
                        if not conv.get("peerUserName"):
                            conv["peerUserName"] = name
            except Exception as e:
                logger.debug("批量订单买家名称查询失败: %s", e)

    # === 最终兜底：避免一律显示"买家"，优先使用更稳定但不误导的占位名 ===
    for conv in conversations:
        if conv.get("peerUserName"):
            continue
        peer_user_id = conv.get("peerUserId", "") or ""
        sid = conv.get("sid", "") or ""
        if peer_user_id and not peer_user_id.startswith("sid:"):
            conv["peerUserName"] = peer_user_id[-6:]
        elif sid and sid != "hello":
            conv["peerUserName"] = f"用户{str(sid)[-4:]}"

    # === 回写 goods_cover_pic 和 goods_title 到 xianyu_conversation 表（缓存加速） ===
    cover_updates: list[tuple[str, str, int]] = []
    for conv in conversations:
        conv_id = conv.get("conversationId")
        if not conv_id:
            continue
        cover_pic = conv.get("goodsCoverPic", "") or ""
        goods_title = conv.get("goodsTitle", "") or ""
        if cover_pic or goods_title:
            cover_updates.append((cover_pic, goods_title, int(conv_id)))
    if cover_updates:
        try:
            for cover_pic, goods_title, conv_id in cover_updates:
                set_parts = []
                params: dict[str, Any] = {"cid": conv_id}
                if cover_pic:
                    set_parts.append("goods_cover_pic = :cover_pic")
                    params["cover_pic"] = cover_pic
                if goods_title:
                    set_parts.append("goods_title = COALESCE(NULLIF(goods_title, ''), :goods_title)")
                    params["goods_title"] = goods_title
                if set_parts:
                    await db.execute(
                        text(f"UPDATE xianyu_conversation SET {', '.join(set_parts)} WHERE id = :cid"),
                        params,
                    )
        except Exception as e:
            logger.debug("回写 goods_cover_pic 到 xianyu_conversation 失败: %s", e)

    return conversations


async def get_context_messages(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    s_id: str,
    limit: int = 50,
    offset: int = 0,
    user_id: int | None = None,
    peer_user_id: str | None = None,
) -> tuple[list[dict], int]:
    """获取会话上下文消息。

    查询逻辑（三种分支互斥）：
    1. s_id 非空 → 只按 base.s_id 查询（忽略 peer_user_id）
    2. s_id 为空但 peer_user_id 非空 → 按 sender_user_id / receiver_user_id / peer_external_uid 查询
    3. 两者都空 → 返回空数组

    所有字符串比较均显式 COLLATE utf8mb4_unicode_ci 以避免 1267 排序规则冲突。
    """
    # 防御性参数归一化
    s_id = str(s_id or "").strip()
    peer_user_id = str(peer_user_id or "").strip()
    if s_id.startswith("sid:"):
        s_id = s_id[4:]
    # 如果 s_id 包含 @goofish 后缀，也去掉
    if s_id.endswith("@goofish"):
        s_id = s_id[:-8]
    seller_external_uid = await _load_seller_external_uid(db, tenant_id, account_id)
    if peer_user_id and seller_external_uid and _normalize_party_id(peer_user_id) == seller_external_uid:
        return [], 0

    # 共享的 JOIN 子句
    base_join = """
        JOIN xianyu_account a
            ON a.id = base.account_id
            AND a.tenant_id = base.tenant_id
            AND (:user_id IS NULL OR a.user_id IS NULL OR a.user_id = :user_id)
    """

    # === 分支1: s_id 非空 —— 只按 s_id 查询 ===
    if s_id:
        # 同时匹配裸 s_id 和带 @goofish 后缀的 s_id（数据库可能存储了 @goofish）
        s_id_goofish = f"{s_id}@goofish"
        peer_user_id_goofish = ""
        s_id_where = """
            AND base.s_id COLLATE utf8mb4_unicode_ci IN (:s_id, :s_id_goofish)
        """
        if peer_user_id:
            peer_user_id_goofish = f"{peer_user_id}@goofish" if not peer_user_id.endswith("@goofish") else peer_user_id
        count_result = await db.execute(
            text(f"""
                SELECT COUNT(*)
                FROM xianyu_chat_message base
                {base_join}
                WHERE base.tenant_id = :tenant_id
                  AND base.account_id = :account_id
                  AND base.deleted = 0
                  AND base.content_type NOT IN (32)
                  {s_id_where}
            """),
            {
                "tenant_id": tenant_id,
                "account_id": account_id,
                "s_id": s_id,
                "s_id_goofish": s_id_goofish,
                "peer_user_id": peer_user_id,
                "peer_user_id_goofish": peer_user_id_goofish,
                "user_id": user_id,
            }
        )
        total = count_result.scalar() or 0

        sql_limit = int(limit or 50) + int(offset or 0)
        rows = await db.execute(
            text(f"""
                SELECT
                    base.id, base.pnm_id, base.s_id AS sid, base.content_type AS contentType,
                    base.msg_content AS msgContent, base.complete_msg AS completeMsg, base.sender_user_id AS senderUserId,
                    base.sender_user_name AS senderUserName, base.xy_goods_id AS xyGoodsId,
                    base.message_time AS messageTime, base.direction, base.reminder_content AS reminderContent,
                    base.reminder_url AS reminderUrl, base.read_status AS readStatus,
                    base.receiver_user_id AS receiverUserId, base.peer_external_uid AS peerExternalUid
                FROM xianyu_chat_message base
                {base_join}
                WHERE base.tenant_id = :tenant_id
                  AND base.account_id = :account_id
                  AND base.deleted = 0
                  AND base.content_type NOT IN (32)
                  {s_id_where}
                ORDER BY base.message_time DESC
                LIMIT :sql_limit
            """),
            {
                "tenant_id": tenant_id,
                "account_id": account_id,
                "s_id": s_id,
                "s_id_goofish": s_id_goofish,
                "peer_user_id": peer_user_id,
                "peer_user_id_goofish": peer_user_id_goofish,
                "sql_limit": sql_limit,
                "user_id": user_id,
            }
        )
        messages = [dict(row) for row in rows.mappings().all()]
        return await _finalize_context_messages(
            db,
            tenant_id,
            account_id,
            messages,
            s_id,
            peer_user_id,
            limit,
            offset,
            filter_base_messages_by_peer=False,
        )

    # === 分支2: s_id 为空、peer_user_id 非空 —— 按真实 UID 查询 ===
    if peer_user_id:
        # 尝试多种格式匹配：裸 UID 和带 @goofish 后缀的 UID
        peer_user_id_goofish = f"{peer_user_id}@goofish" if not peer_user_id.endswith("@goofish") else peer_user_id
        uid_where = """
            AND (
                base.sender_user_id COLLATE utf8mb4_unicode_ci IN (:peer_user_id, :peer_user_id_goofish)
                OR base.receiver_user_id COLLATE utf8mb4_unicode_ci IN (:peer_user_id, :peer_user_id_goofish)
                OR base.peer_external_uid COLLATE utf8mb4_unicode_ci IN (:peer_user_id, :peer_user_id_goofish)
            )
        """
        count_result = await db.execute(
            text(f"""
                SELECT COUNT(*)
                FROM xianyu_chat_message base
                {base_join}
                WHERE base.tenant_id = :tenant_id
                  AND base.account_id = :account_id
                  AND base.deleted = 0
                  AND base.content_type NOT IN (32)
                  {uid_where}
            """),
            {
                "tenant_id": tenant_id, "account_id": account_id,
                "peer_user_id": peer_user_id, "peer_user_id_goofish": peer_user_id_goofish,
                "user_id": user_id
            }
        )
        total = count_result.scalar() or 0

        # 如果通过 peer_user_id 直接匹配不到消息，尝试先找到关联的 s_id
        if total == 0:
            # 通过 peer_user_id 查找关联的 s_id（可能在 sender_user_id/receiver_user_id/peer_external_uid 中）
            sid_result = await db.execute(
                text(f"""
                    SELECT base.s_id
                    FROM xianyu_chat_message base
                    {base_join}
                    WHERE base.tenant_id = :tenant_id
                      AND base.account_id = :account_id
                      AND base.deleted = 0
                      AND base.content_type NOT IN (32)
                      AND (
                          base.sender_user_id COLLATE utf8mb4_unicode_ci IN (:peer_user_id, :peer_user_id_goofish)
                          OR base.receiver_user_id COLLATE utf8mb4_unicode_ci IN (:peer_user_id, :peer_user_id_goofish)
                          OR base.peer_external_uid COLLATE utf8mb4_unicode_ci IN (:peer_user_id, :peer_user_id_goofish)
                      )
                    ORDER BY base.message_time DESC
                    LIMIT 1
                """),
                {
                    "tenant_id": tenant_id, "account_id": account_id,
                    "peer_user_id": peer_user_id, "peer_user_id_goofish": peer_user_id_goofish,
                    "user_id": user_id
                }
            )
            found_sid = sid_result.scalar_one_or_none()
            if found_sid:
                # 使用找到的 s_id 重新查询（进入分支1逻辑）
                count_result = await db.execute(
                    text(f"""
                        SELECT COUNT(*)
                        FROM xianyu_chat_message base
                        {base_join}
                        WHERE base.tenant_id = :tenant_id
                          AND base.account_id = :account_id
                          AND base.s_id COLLATE utf8mb4_unicode_ci = :s_id COLLATE utf8mb4_unicode_ci
                          AND base.deleted = 0
                          AND base.content_type NOT IN (32)
                    """),
                    {"tenant_id": tenant_id, "account_id": account_id, "s_id": found_sid, "user_id": user_id}
                )
                total = count_result.scalar() or 0
                sql_limit = int(limit or 50) + int(offset or 0)
                rows = await db.execute(
                    text(f"""
                        SELECT
                            base.id, base.pnm_id, base.s_id AS sid, base.content_type AS contentType,
                            base.msg_content AS msgContent, base.complete_msg AS completeMsg, base.sender_user_id AS senderUserId,
                            base.sender_user_name AS senderUserName, base.xy_goods_id AS xyGoodsId,
                            base.message_time AS messageTime, base.direction, base.reminder_content AS reminderContent,
                            base.reminder_url AS reminderUrl, base.read_status AS readStatus,
                            base.receiver_user_id AS receiverUserId, base.peer_external_uid AS peerExternalUid
                        FROM xianyu_chat_message base
                        {base_join}
                        WHERE base.tenant_id = :tenant_id
                          AND base.account_id = :account_id
                          AND base.s_id COLLATE utf8mb4_unicode_ci = :s_id COLLATE utf8mb4_unicode_ci
                          AND base.deleted = 0
                          AND base.content_type NOT IN (32)
                        ORDER BY base.message_time DESC
                        LIMIT :sql_limit
                    """),
                    {
                        "tenant_id": tenant_id, "account_id": account_id,
                        "s_id": found_sid, "sql_limit": sql_limit,
                        "user_id": user_id,
                    }
                )
                messages = [dict(row) for row in rows.mappings().all()]
                return await _finalize_context_messages(
                    db,
                    tenant_id,
                    account_id,
                    messages,
                    found_sid,
                    peer_user_id,
                    limit,
                    offset,
                )
            # 也尝试从 xianyu_conversation 表查找
            conv_result = await db.execute(
                text("""
                    SELECT cm.s_id
                    FROM xianyu_conversation c
                    JOIN xianyu_chat_message cm
                        ON cm.tenant_id = c.tenant_id
                        AND cm.account_id = c.account_id
                        AND cm.s_id COLLATE utf8mb4_unicode_ci = c.peer_key COLLATE utf8mb4_unicode_ci
                    WHERE c.tenant_id = :tenant_id
                      AND c.account_id = :account_id
                      AND (
                          c.external_buyer_id COLLATE utf8mb4_unicode_ci IN (:peer_user_id, :peer_user_id_goofish)
                          OR c.peer_external_uid COLLATE utf8mb4_unicode_ci IN (:peer_user_id, :peer_user_id_goofish)
                          OR c.peer_key COLLATE utf8mb4_unicode_ci IN (:peer_user_id, :peer_user_id_goofish)
                      )
                    ORDER BY cm.message_time DESC
                    LIMIT 1
                """),
                {
                    "tenant_id": tenant_id, "account_id": account_id,
                    "peer_user_id": peer_user_id, "peer_user_id_goofish": peer_user_id_goofish,
                }
            )
            conv_sid = conv_result.scalar_one_or_none()
            if conv_sid:
                count_result = await db.execute(
                    text(f"""
                        SELECT COUNT(*)
                        FROM xianyu_chat_message base
                        {base_join}
                        WHERE base.tenant_id = :tenant_id
                          AND base.account_id = :account_id
                          AND base.s_id COLLATE utf8mb4_unicode_ci = :s_id COLLATE utf8mb4_unicode_ci
                          AND base.deleted = 0
                          AND base.content_type NOT IN (32)
                    """),
                    {"tenant_id": tenant_id, "account_id": account_id, "s_id": conv_sid, "user_id": user_id}
                )
                total = count_result.scalar() or 0
                sql_limit = int(limit or 50) + int(offset or 0)
                rows = await db.execute(
                    text(f"""
                        SELECT
                            base.id, base.pnm_id, base.s_id AS sid, base.content_type AS contentType,
                            base.msg_content AS msgContent, base.complete_msg AS completeMsg, base.sender_user_id AS senderUserId,
                            base.sender_user_name AS senderUserName, base.xy_goods_id AS xyGoodsId,
                            base.message_time AS messageTime, base.direction, base.reminder_content AS reminderContent,
                            base.reminder_url AS reminderUrl, base.read_status AS readStatus,
                            base.receiver_user_id AS receiverUserId, base.peer_external_uid AS peerExternalUid
                        FROM xianyu_chat_message base
                        {base_join}
                        WHERE base.tenant_id = :tenant_id
                          AND base.account_id = :account_id
                          AND base.s_id COLLATE utf8mb4_unicode_ci = :s_id COLLATE utf8mb4_unicode_ci
                          AND base.deleted = 0
                          AND base.content_type NOT IN (32)
                        ORDER BY base.message_time DESC
                        LIMIT :sql_limit
                    """),
                    {
                        "tenant_id": tenant_id, "account_id": account_id,
                        "s_id": conv_sid, "sql_limit": sql_limit,
                        "user_id": user_id,
                    }
                )
                messages = [dict(row) for row in rows.mappings().all()]
                return await _finalize_context_messages(
                    db,
                    tenant_id,
                    account_id,
                    messages,
                    conv_sid,
                    peer_user_id,
                    limit,
                    offset,
                )
            return await _finalize_context_messages(
                db,
                tenant_id,
                account_id,
                [],
                "",
                peer_user_id,
                limit,
                offset,
            )

        sql_limit = int(limit or 50) + int(offset or 0)
        rows = await db.execute(
            text(f"""
                SELECT
                    base.id, base.pnm_id, base.s_id AS sid, base.content_type AS contentType,
                    base.msg_content AS msgContent, base.complete_msg AS completeMsg, base.sender_user_id AS senderUserId,
                    base.sender_user_name AS senderUserName, base.xy_goods_id AS xyGoodsId,
                    base.message_time AS messageTime, base.direction, base.reminder_content AS reminderContent,
                    base.reminder_url AS reminderUrl, base.read_status AS readStatus,
                    base.receiver_user_id AS receiverUserId, base.peer_external_uid AS peerExternalUid
                FROM xianyu_chat_message base
                {base_join}
                WHERE base.tenant_id = :tenant_id
                  AND base.account_id = :account_id
                  AND base.deleted = 0
                  AND base.content_type NOT IN (32)
                  {uid_where}
                ORDER BY base.message_time DESC
                LIMIT :sql_limit
            """),
            {
                "tenant_id": tenant_id,
                "account_id": account_id,
                "peer_user_id": peer_user_id,
                "peer_user_id_goofish": peer_user_id_goofish,
                "sql_limit": sql_limit,
                "user_id": user_id,
            }
        )
        messages = [dict(row) for row in rows.mappings().all()]
        return await _finalize_context_messages(
            db,
            tenant_id,
            account_id,
            messages,
            s_id,
            peer_user_id,
            limit,
            offset,
        )

    # === 分支3: 两者都空 ===
    return [], 0
