"""
闲鱼 WebSocket 消息协议解析模块。

处理：
1. Base64 + MessagePack 解包 syncPushPackage 中的数据
2. 数字索引字段（私有协议）解析
3. 消息去重（pnm_id）
"""
import base64
import hashlib
import json
import logging
import re
import time
import uuid
from typing import Any, Optional

import msgpack

logger = logging.getLogger(__name__)


def _normalize_goofish_target(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.startswith("sid:"):
        raw = raw[4:]
    if raw.endswith("@goofish"):
        raw = raw[:-8]
    raw = raw.strip()
    return f"{raw}@goofish" if raw else ""


def _is_misplaced_pnm_sender_message(msg: dict[str, Any]) -> bool:
    sender_user_id = str(msg.get("senderUserId") or "").strip()
    msg_content = str(msg.get("msgContent") or "").strip()
    pnm_id = str(msg.get("pnmId") or "").strip()
    return (
        bool(re.fullmatch(r"\d+\.PNM", sender_user_id))
        and bool(re.fullmatch(r"\d+@goofish", msg_content))
        and pnm_id in {"", "1"}
    )


def _normalize_msgpack_key(value: Any) -> str:
    """把 msgpack 的 key 转成可哈希、可读的稳定字符串表示。"""
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return value.decode("utf-8", errors="ignore")
            except Exception:
                return value.decode("latin-1", errors="ignore")
    if isinstance(value, (str, int, float, bool, type(None))):
        return str(value)
    if isinstance(value, (list, tuple)):
        try:
            return json.dumps([_normalize_msgpack_key(item) for item in value], ensure_ascii=False)
        except Exception:
            return repr(value)
    if isinstance(value, dict):
        try:
            items = []
            for k, v in value.items():
                items.append([_normalize_msgpack_key(k), _normalize_msgpack_key(v)])
            return json.dumps(items, ensure_ascii=False)
        except Exception:
            return repr(value)
    return repr(value)


def _normalize_msgpack_value(value: Any) -> Any:
    """宽容地把 msgpack 解出的 bytes/容器递归转成可 JSON 化对象。"""
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return value.decode("utf-8", errors="ignore")
            except Exception:
                return value.decode("latin-1", errors="ignore")
    if isinstance(value, list):
        return [_normalize_msgpack_value(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_msgpack_value(item) for item in value]
    if isinstance(value, dict):
        normalized: dict[Any, Any] = {}
        for k, v in list(value.items()):
            try:
                safe_key = _normalize_msgpack_key(k)
                normalized[safe_key] = _normalize_msgpack_value(v)
            except TypeError:
                try:
                    normalized[repr(k)] = _normalize_msgpack_value(v)
                except Exception:
                    pass  # 已知非关键异常：repr(k) 作为兜底 key 仍失败时跳过该字段
        return normalized
    return value


def decrypt_payload(encrypted_data: str) -> list[dict[str, Any]]:
    """将闲鱼 syncPushPackage 中的 data 解包为对象列表。

    对齐真实协议特征：Base64 解码后可能是连续拼接的多个 MessagePack 对象，
    也可能并不是纯 MessagePack，而是 JSON / 文本 / 混合嵌套结构。
    """
    try:
        if not encrypted_data:
            return []

        cleaned = encrypted_data
        missing_padding = len(cleaned) % 4
        if missing_padding:
            cleaned += "=" * (4 - missing_padding)

        decoded = base64.b64decode(cleaned)
        results: list[dict[str, Any]] = []

        def _collect_dicts(value: Any):
            normalized = _normalize_msgpack_value(value)
            if isinstance(normalized, dict):
                results.append(normalized)
                for child in normalized.values():
                    _collect_dicts(child)
            elif isinstance(normalized, list):
                for item in normalized:
                    _collect_dicts(item)
            elif isinstance(normalized, str):
                text = normalized.strip()
                if not text:
                    return
                if text.startswith("{") or text.startswith("["):
                    try:
                        parsed = json.loads(text)
                        _collect_dicts(parsed)
                    except Exception:
                        pass  # 已知非关键异常：嵌套 JSON 字符串解析失败时跳过，继续其他解析策略

        # 策略 0：有些包实际是 base64(JSON)
        try:
            text = decoded.decode("utf-8").strip()
            if text.startswith("{") or text.startswith("["):
                parsed = json.loads(text)
                _collect_dicts(parsed)
                if results:
                    return results
        except Exception:
            pass  # 已知非关键异常：base64(JSON) 策略失败时回退到 MessagePack 解包策略

        # 策略一：标准流式解包 + 递归收集嵌套 dict
        try:
            unpacker = msgpack.Unpacker(raw=True, strict_map_key=False)
            unpacker.feed(decoded)
            for obj in unpacker:
                _collect_dicts(obj)
            if results:
                return results
        except Exception as e:
            logger.debug("msgpack 策略一失败(%s)，尝试策略二", e)

        # 策略二：use_list=False（tuple 可哈希）+ raw=False（str 天然可哈希）
        try:
            unpacker = msgpack.Unpacker(raw=False, strict_map_key=False, use_list=False)
            unpacker.feed(decoded)
            for obj in unpacker:
                _collect_dicts(obj)
            if results:
                return results
        except Exception as e:
            logger.debug("msgpack 策略二失败(%s)，尝试策略三", e)

        # 策略三：单对象解包
        try:
            obj = msgpack.unpackb(decoded, raw=False, strict_map_key=False)
            _collect_dicts(obj)
            if results:
                return results
        except Exception as e:
            logger.debug("msgpack 策略三失败(%s)，尝试策略四", e)

        # 策略四：raw=True 单对象解包
        try:
            obj = msgpack.unpackb(decoded, raw=True, strict_map_key=False)
            _collect_dicts(obj)
            if results:
                return results
        except Exception as e:
            logger.debug("msgpack 策略四失败(%s)", e)

        logger.warning("所有 MessagePack 解包策略均失败, data_len=%d", len(encrypted_data))
        return results
    except Exception as e:
        logger.error("MessagePack 解包失败: %s, data_len=%d", e, len(encrypted_data) if encrypted_data else 0)
        return []


def parse_sync_package(package: dict) -> Optional[dict]:
    """解析 WebSocket 同步包（/s/para、/s/sync、/s/vulcan）。
    
    Args:
        package: 原始同步包字典，格式：
            {
                "lwp": "/s/para" | "/s/sync" | "/s/vulcan",
                "headers": {...},
                "body": {
                    "syncPushPackage": {
                        "data": [
                            {
                                "data": "Base64 MessagePack 字符串",
                                "msgType": ...
                            }
                        ]
                    }
                }
            }
            或 body 本身就是 syncPushPackage 结构。
            
    Returns:
        解析后的消息字典列表：{
            "messages": [...],
            "ack_pnm_ids": [...]  # 需要 ACK 的消息 ID 列表
        }
        失败返回 None
    """
    try:
        body = package.get("body", {})
        sync_push = body.get("syncPushPackage") or body
        data_list = sync_push.get("data", [])
        if not data_list:
            return None

        messages = []
        ack_ids = []

        for item in data_list:
            encrypted = item.get("data", "")
            if not encrypted:
                continue

            unpacked_objects = decrypt_payload(encrypted)
            if not unpacked_objects:
                continue

            for msg_data in unpacked_objects:
                if not isinstance(msg_data, dict):
                    continue

                parsed = parse_numbered_fields(msg_data)
                if parsed:
                    parsed["rawPayload"] = msg_data
                    messages.append(parsed)
                    if parsed.get("pnmId"):
                        ack_ids.append(parsed["pnmId"])
                    # 解析异常时只记录结构元数据，不回显会话载荷。
                    if (not parsed.get("msgContent") and 
                        parsed.get("sId") in ("", "1") and
                        parsed.get("pnmId") in ("", "1")):
                        logger.info(
                            "WS 解析诊断: parsedKeys=%s rawKeys=%s contentPresent=%s",
                            sorted(str(key) for key in parsed.keys()),
                            sorted(str(key) for key in msg_data.keys()),
                            bool(parsed.get("msgContent")),
                        )
                else:
                    first_block = msg_data.get("1") if isinstance(msg_data, dict) else None
                    is_control_packet = (
                        isinstance(first_block, list)
                        and first_block
                        and all(isinstance(item, dict) for item in first_block)
                        and all(set(map(str, item.keys())).issubset({"1", "2", "3", "4"}) for item in first_block)
                        and not any(k in msg_data for k in ("sessionInfo", "content", "2", "3", "5", "6", "10", "msgType"))
                    )
                    if is_control_packet:
                        continue
                    should_log_sample = any(
                        key in msg_data
                        for key in (
                            "topic_title", "session_id", "sessionId", "sessionInfo", "content",
                            "receiverIds", "messageId", "pnmId", "msgType", "1", "2", "3", "5", "6", "10"
                        )
                    )
                    if not should_log_sample:
                        continue
                    logger.info(
                        "WS 消息解析失败 rawKeys=%s",
                        sorted(str(key) for key in msg_data.keys()),
                    )

        return {
            "messages": messages,
            "ack_pnm_ids": ack_ids,
        }
    except Exception as e:
        logger.error("同步包解析异常: %s", e, exc_info=True)
        import traceback
        logger.error("同步包解析异常完整堆栈:\n%s", traceback.format_exc())
        return None


def parse_send_response(package: dict) -> Optional[dict]:
    """解析发送消息的响应包（/r/MessageSend/sendByReceiverScope）。
    
    Args:
        package: 原始响应包
        
    Returns:
        {"code": 200, "uuid": "...", "error": "..."} 或 None
    """
    try:
        body = package.get("body", {})
        if isinstance(body, list) and len(body) > 0:
            body = body[0]
        code = package.get("code", body.get("code", 500))
        result = {
            "code": code,
            "uuid": body.get("uuid") if isinstance(body, dict) else None,
        }
        # 提取错误信息（闲鱼错误响应可能有多种字段名）
        if code != 200 and isinstance(body, dict):
            error_msg = (
                body.get("message") or body.get("errorInfo") or
                body.get("error") or body.get("msg") or
                package.get("message") or package.get("error") or package.get("msg")
            )
            if error_msg:
                result["error"] = str(error_msg)
        return result
    except Exception as e:
        logger.error("发送响应解析异常: %s", e)
        return None


def parse_numbered_fields(data: dict) -> Optional[dict]:
    """解析闲鱼私有协议的数字索引字段。"""
    if not isinstance(data, dict):
        return None

    # 简单文本推荐/话题消息结构
    topic_title = data.get("topic_title")
    session_id = data.get("session_id") or data.get("sessionId")
    simple_content = data.get("content")
    if isinstance(topic_title, str) and session_id and isinstance(simple_content, str):
        # 修复：过滤商品卡片消息(contentType=8)的"话术脚本"被误解析为独立消息。
        # 背景：闲鱼 IM 协议在推送商品卡片消息时，会同时推送一批"话术脚本"
        # （rawPayload.sessionArouse.arouseChatScriptInfo 数组），每项格式为
        # {"topic_title":"shading_opening","session_id":xxx,"content":"怎么登录？"}。
        # 这些话术脚本不是真实买家消息，没有 senderUserId/messageTime，
        # 被错误入库后会导致：
        # 1. messageTime=0 被当前时间兜底，伪造出毫秒级递增时间戳
        # 2. sender_user_id 为空，direction 硬编码 IN，污染会话消息列表
        # 3. 用户看到"会话显示昨天但消息是几个月前"的时间错乱
        # 判定特征：rawPayload 仅有 topic_title/session_id/content 三个字段，
        # 无 senderUserId/messageTime/messageId 等真实消息字段。
        # topic_title 已知值：shading_opening / STIMULATED_SALE_BUY 等，
        # 不再用白名单，避免未来新变体漏网（曾因白名单漏 STIMULATED_SALE_BUY 导致再次故障）。
        is_chat_script = (
            not data.get("senderUserId")
            and not data.get("messageId")
            and not data.get("pnmId")
            and not data.get("messageTime")
            and not data.get("createTime")
            and not data.get("createAt")
            and isinstance(topic_title, str)
            and bool(topic_title)
        )
        if is_chat_script:
            logger.debug(
                "过滤话术脚本消息（非真实买家消息） titleLen=%d sessionRefPresent=%s contentLen=%d",
                len(topic_title),
                bool(session_id),
                len(simple_content),
            )
            return None
        sender_user_id = ""
        receiver_user_id = ""
        receiver_ids = data.get("receiverIds")
        if isinstance(receiver_ids, list) and receiver_ids:
            receiver_user_id = str(receiver_ids[0] or "")
        session_info = data.get("sessionInfo") if isinstance(data.get("sessionInfo"), dict) else None
        extensions = session_info.get("extensions") if session_info and isinstance(session_info.get("extensions"), dict) else {}
        if not sender_user_id:
            sender_user_id = str(extensions.get("extUserId") or "") if extensions else ""
        if not receiver_user_id:
            receiver_user_id = str(extensions.get("ownerUserId") or "") if extensions else ""
        return {
            "sId": str(session_id),
            "pnmId": str(data.get("messageId") or data.get("pnmId") or ""),
            "senderUserId": sender_user_id,
            "senderUserName": "",
            "messageTime": 0,
            "msgContent": simple_content,
            "contentType": 1,
            "msgType": 1,
            "direction": "IN",
            "reminderContent": topic_title,
            "reminderUrl": "",
            "receiverUserId": receiver_user_id,
            "xyGoodsId": "",
        }

    # 过滤明显的非聊天控制包/成员状态包
    first_block = data.get("1")
    if isinstance(first_block, list) and first_block and all(isinstance(item, dict) for item in first_block):
        only_control_fields = all(set(map(str, item.keys())).issubset({"1", "2", "3", "4"}) for item in first_block)
        if only_control_fields and not any(k in data for k in ("sessionInfo", "content", "2", "3", "5", "6", "10", "msgType")):
            return None

    # === 卡片更新消息（付款通知等）===
    # 参考垃圾箱项目 parse_card_update_message：message["1"] 是字符串，
    # message["4"] 是包含 reminderContent 的字典，message["2"] 是会话ID，
    # message["5"] 是毫秒时间戳。这类消息用于通知付款状态变更（如"我已付款，等待你发货"），
    # 是触发自动发货的关键消息源。若不处理，付款通知会被丢弃，自动发货无法触发。
    if isinstance(data.get("1"), str) and isinstance(data.get("4"), dict) and "reminderContent" in data["4"]:
        message_4 = data["4"]
        reminder_content = str(message_4.get("reminderContent") or "")
        reminder_url = str(message_4.get("reminderUrl") or "")
        reminder_title = str(message_4.get("reminderTitle") or "")
        sender_user_id = str(message_4.get("senderUserId") or message_4.get("sendUserId") or "")
        # 会话ID：data["2"] 可能带 @goofish 后缀，取 @ 前的部分
        chat_id_raw = str(data.get("2") or "")
        s_id = chat_id_raw.split("@")[0] if "@" in chat_id_raw else chat_id_raw
        # 时间戳：data["5"] 通常是毫秒
        msg_time = data.get("5") or message_4.get("msgTime") or message_4.get("createTime") or 0
        try:
            msg_time = int(msg_time)
        except (TypeError, ValueError):
            msg_time = 0
        # 提取商品ID：优先从 reminderUrl 的 itemId= 参数精确匹配
        xy_goods_id = ""
        match = None
        if reminder_url:
            match = re.search(r'[?&]itemId=(\d+)', reminder_url)
            if not match:
                match = re.search(r'[?&]id=(\d+)', reminder_url)
            if match:
                xy_goods_id = match.group(1)
        # 兜底：从 extJson 提取
        if not xy_goods_id:
            ext_json = message_4.get("extJson") or ""
            if ext_json and isinstance(ext_json, str):
                try:
                    ext_dict = json.loads(ext_json)
                    if isinstance(ext_dict, dict) and ext_dict.get("itemId"):
                        xy_goods_id = str(ext_dict["itemId"])
                except (json.JSONDecodeError, TypeError):
                    pass
        if reminder_content or s_id or sender_user_id or xy_goods_id:
            logger.info(
                "WS 卡片更新消息解析: sessionRefPresent=%s senderRefPresent=%s goodsRefPresent=%s "
                "reminderContentLen=%d reminderUrlPresent=%s",
                bool(s_id), bool(sender_user_id), bool(xy_goods_id),
                len(reminder_content), bool(reminder_url),
            )
            return {
                "sId": s_id,
                "pnmId": str(data.get("3") or data.get("messageId") or data.get("pnmId") or ""),
                "senderUserId": sender_user_id,
                "senderUserName": reminder_title,
                "messageTime": msg_time,
                "msgContent": reminder_content,
                "contentType": 26,
                "msgType": 1,
                "direction": "IN",
                "reminderContent": reminder_content,
                "reminderUrl": reminder_url,
                "receiverUserId": "",
                "xyGoodsId": xy_goods_id,
            }

    # === 参考实现的快速消息判定 ===
    # 已读回执：data["2"] == 2
    msg_type_raw = data.get("2")
    if msg_type_raw == 2:
        logger.debug(
            "WS parse_numbered_fields: 已读回执 dataKeys=%s",
            sorted(str(key) for key in data.keys()),
        )
        return None  # 暂不处理已读回执
    # 聊天消息：data["1"] 是 Map 且包含 "3"(pnmId)
    inner_wrapper = data.get("1")
    if isinstance(inner_wrapper, dict) and inner_wrapper.get("3"):
        # 直接使用 wrapper dict 作为 msg_info，跳过 _find_nested_message_info
        msg_info = inner_wrapper
        msg_type = 0
        logger.debug("WS parse_numbered_fields: 参考路径命中 data_keys=%s", list(data.keys()))
        _skip_find = True
    else:
        msg_info = None
        _skip_find = False
    # ================================

    # === 轻量级内容消息格式 {"1": int, "3": {"1":"", "2":"内容", "3":"", "4":1, "5":"..."}} ===
    # 这种格式中 data["1"] 是整数（消息子类型标识，如 101），data["3"] 是内容容器。
    # content_container 的字段含义和标准 message_info 不同：
    #   "1" = sId（通常为空，会话信息在同步包外层）
    #   "2" = 消息文本内容（不是 sId）
    #   "3" = pnmId（通常为空）
    #   "4" = contentType (1=文本, 25=已拍下, 26=已付款等)
    #   "5" = 扩展内容 JSON 字符串（含 contentType, text/dxCard 等）
    # 若不在此处拦截，_find_nested_message_info 会误将 content_container 当作 message_info，
    # 导致字段映射错乱（sId 被设为消息文本，然后在 validate 阶段被清空）。
    if (
        not _skip_find
        and isinstance(data.get("1"), int)
        and isinstance(data.get("3"), dict)
        and not isinstance(data.get("1"), bool)
    ):
        content_container = data["3"]
        raw_msg_content = str(content_container.get("2") or "")
        content_type_val = content_container.get("4")
        try:
            content_type_int = int(content_type_val) if content_type_val is not None else 1
        except (TypeError, ValueError):
            content_type_int = 1

        # 从扩展内容 JSON ("5") 中提取额外信息
        ext_json_str = str(content_container.get("5") or "")
        ext_data: dict = {}
        if ext_json_str and ext_json_str.startswith("{"):
            try:
                parsed_ext = json.loads(ext_json_str)
                if isinstance(parsed_ext, dict):
                    ext_data = parsed_ext
            except (json.JSONDecodeError, TypeError):
                pass

        # 从 ext_data 提取消息内容（text.text 优先）
        msg_content_from_ext = ""
        text_obj = ext_data.get("text") if isinstance(ext_data.get("text"), dict) else None
        if text_obj and isinstance(text_obj.get("text"), str):
            msg_content_from_ext = text_obj["text"].strip()

        final_msg_content = msg_content_from_ext or raw_msg_content
        if not final_msg_content:
            # 内容为空，可能是纯卡片消息，从 dxCard 提取摘要
            dx_card = ext_data.get("dxCard") if isinstance(ext_data.get("dxCard"), dict) else None
            if dx_card:
                final_msg_content = raw_msg_content or "[卡片消息]"

        s_id_val = str(content_container.get("1") or "").strip()
        pnm_id_val = str(content_container.get("3") or "").strip()

        if final_msg_content:
            logger.info(
                "WS 轻量级内容消息: subType=%s contentType=%d sessionRefPresent=%s "
                "messageRefPresent=%s contentLen=%d",
                data.get("1"),
                content_type_int,
                bool(s_id_val),
                bool(pnm_id_val),
                len(final_msg_content),
            )
            return {
                "sId": s_id_val,
                "pnmId": pnm_id_val,
                "senderUserId": "",
                "senderUserName": "",
                "messageTime": 0,
                "msgContent": final_msg_content,
                "contentType": content_type_int,
                "msgType": 1,
                "direction": "IN",
                "reminderContent": final_msg_content if content_type_int == 1 else "",
                "reminderUrl": "",
                "receiverUserId": "",
                "xyGoodsId": "",
            }

    content_root = data.get("content") if isinstance(data.get("content"), dict) else None

    # contentType=11 的业务通知/草稿失败类消息
    if isinstance(content_root, dict) and str(content_root.get("contentType")) == "11":
        custom_data = content_root.get("customData") if isinstance(content_root.get("customData"), dict) else {}
        custom_inner = custom_data.get("data") if isinstance(custom_data.get("data"), dict) else {}
        fail_info = custom_inner.get("failInfo") if isinstance(custom_inner.get("failInfo"), dict) else {}
        error_message = str(fail_info.get("errorMessage") or "").strip()
        error_code = str(fail_info.get("errorCode") or "").strip()
        receiver_ids = data.get("receiverIds")
        receiver_user_id = str(receiver_ids[0] or "") if isinstance(receiver_ids, list) and receiver_ids else ""
        msg_content = error_message or error_code or "[业务通知]"
        reminder_content = error_code or "业务通知"
        if msg_content or receiver_user_id:
            return {
                "sId": str(data.get("session_id") or data.get("sessionId") or custom_inner.get("id") or ""),
                "pnmId": str(data.get("messageId") or data.get("pnmId") or custom_inner.get("id") or ""),
                "senderUserId": "",
                "senderUserName": "",
                "messageTime": 0,
                "msgContent": msg_content,
                "contentType": 11,
                "msgType": 1,
                "direction": "IN",
                "reminderContent": reminder_content,
                "reminderUrl": "",
                "receiverUserId": receiver_user_id,
                "xyGoodsId": str(custom_inner.get("id") or ""),
            }

    # 新结构：sessionInfo / content.contentType=8 的会话唤起/商品会话包
    session_info = data.get("sessionInfo") if isinstance(data.get("sessionInfo"), dict) else None
    content_root = data.get("content") if isinstance(data.get("content"), dict) else None
    if session_info:
        extensions = session_info.get("extensions") if isinstance(session_info.get("extensions"), dict) else {}
        session_id = session_info.get("sessionId") or data.get("sessionId") or ""
        create_time = session_info.get("createTime") or extensions.get("VULCAN_CREATE_TIME") or 0
        sender_user_id = extensions.get("extUserId") or ""
        receiver_user_id = ""
        receiver_ids = data.get("receiverIds")
        if isinstance(receiver_ids, list) and receiver_ids:
            receiver_user_id = str(receiver_ids[0] or "")
        if not receiver_user_id:
            receiver_user_id = extensions.get("ownerUserId") or ""
        item_id = extensions.get("itemId") or ""
        item_title = extensions.get("itemTitle") or ""
        content_type = 8
        if content_root and content_root.get("contentType") not in (None, ""):
            content_type = content_root.get("contentType")
        msg_content = item_title or f"[会话消息:{content_type}]"
        if session_id or sender_user_id or receiver_user_id or item_id or item_title:
            return {
                "sId": str(session_id) if session_id else "",
                "pnmId": str(data.get("messageId") or data.get("pnmId") or ""),
                "senderUserId": str(sender_user_id) if sender_user_id else "",
                "senderUserName": "",
                "messageTime": int(create_time) if str(create_time).isdigit() else 0,
                "msgContent": msg_content,
                "contentType": int(content_type) if str(content_type).isdigit() else 8,
                "msgType": data.get("type", 1),
                "reminderContent": item_title,
                "reminderUrl": "",
                "receiverUserId": str(receiver_user_id) if receiver_user_id else "",
                "xyGoodsId": str(item_id) if item_id else "",
            }

    def _get(obj: Any, *keys: str, default=None):
        if not isinstance(obj, dict):
            return default
        for key in keys:
            if key in obj and obj[key] not in (None, ""):
                return obj[key]
        return default

    def _find_nested_message_info(obj: Any) -> dict:
        if not isinstance(obj, dict):
            return {}
        # 标准结构：obj["1"] 是 message_info 子字典
        first_key = _get(obj, "1", default={})
        if isinstance(first_key, dict):
            inner = first_key
            if "6" in inner or _is_valid_message_info_pattern(inner):
                return inner
        # 扁平结构：obj 本身就是 message_info
        if "6" in obj or _is_valid_message_info_pattern(obj):
            return obj
        # 递归搜索子节点
        for value in obj.values():
            found = _find_nested_message_info(value)
            if found:
                return found
        return {}

    def _is_valid_message_info_pattern(obj: dict) -> bool:
        """检查 dict 是否符合标准 message_info 的 "2"(sId) + "5"(messageTime) 模式。

        防止将轻量级内容容器的 {"2":"消息内容", "5":"JSON字符串"} 误认为 message_info。
        标准 message_info 中 "2" 是会话ID（纯数字），"5" 是毫秒时间戳（整数）。
        """
        if "2" not in obj or "5" not in obj:
            return False
        sid_candidate = obj["2"]
        time_candidate = obj["5"]
        # sId 不应包含中文（会话ID是数字或数字@goofish格式）
        if isinstance(sid_candidate, str) and contains_chinese(sid_candidate):
            return False
        # messageTime 应该是数字或可转换为数字
        try:
            int(time_candidate)
        except (TypeError, ValueError):
            return False
        return True

    if not _skip_find:
        msg_type = _get(data, "2", "msgType", default=1)
        msg_info = _find_nested_message_info(data)
        if not msg_info:
            return None
    else:
        # 参考路径已设置 msg_type=0 和 msg_info
        pass

    logger.debug(
        "WS parse_numbered_fields msg_infoKeys=%s dataKeys=%s",
        sorted(str(key) for key in msg_info.keys()),
        sorted(str(key) for key in data.keys()),
    )

    sender_info = _get(msg_info, "1", "senderInfo", default={})
    sender_user_id = ""
    sender_user_name = ""
    if isinstance(sender_info, dict):
        sender_user_id = _get(sender_info, "1", "senderUserId", default="") or ""
        sender_user_name = _get(sender_info, "2", "senderUserName", "nick", default="") or ""
    elif sender_info:
        sender_user_id = str(sender_info)

    # 兜底：从顶层 data 的 senderUserId 提取
    if not sender_user_id:
        sender_user_id = str(_get(data, "senderUserId", "senderId", default="") or "")
    if not sender_user_name:
        sender_user_name = str(_get(data, "senderUserName", "senderNick", default="") or "")

    s_id = _get(msg_info, "2", "sId", default="") or ""
    pnm_id = _get(msg_info, "3", "pnmId", default="") or ""
    message_time = _get(msg_info, "5", "messageTime", default=0) or 0
    # 兜底：当协议字段 "5" 缺失时，参考目标项目（xianyu-auto-reply）的解析方式，
    # 从 IM 消息的常见时间字段中提取（createAt / time / modifyTime）。
    # 这些字段通常出现在 msg_info 或顶层 data 中（参考 chat_new.py 第 817 行）。
    if not message_time:
        for time_source in (
            _get(msg_info, "createAt", "time", "modifyTime", default=0),
            _get(data, "createAt", "time", "modifyTime", default=0),
            _get(msg_info, "createTime", default=0),
            _get(data, "createTime", default=0),
        ):
            if time_source:
                try:
                    candidate = int(time_source)
                    if candidate > 0:
                        message_time = candidate
                        break
                except (TypeError, ValueError):
                    continue

    # 解析消息内容
    content_obj = _get(msg_info, "6", "content", default={})
    msg_content = ""
    content_type = 1
    image_urls: list[str] = []

    def _extract_image_urls(payload: Any) -> list[str]:
        if not isinstance(payload, dict):
            return []
        image_obj = payload.get("image") if isinstance(payload.get("image"), dict) else {}
        urls = []
        for candidate in (
            image_obj.get("url"),
            image_obj.get("picUrl"),
            payload.get("imageUrl"),
            payload.get("picUrl"),
            payload.get("url"),
        ):
            if isinstance(candidate, str) and candidate.strip():
                urls.append(candidate.strip())
        pics = image_obj.get("pics")
        if isinstance(pics, list):
            for pic in pics:
                if not isinstance(pic, dict):
                    continue
                for candidate in (pic.get("url"), pic.get("picUrl")):
                    if isinstance(candidate, str) and candidate.strip():
                        urls.append(candidate.strip())
        deduped = []
        seen = set()
        for url in urls:
            if url not in seen:
                seen.add(url)
                deduped.append(url)
        return deduped

    def _decode_embedded_content(payload: Any) -> Any:
        if isinstance(payload, dict):
            return payload
        if not isinstance(payload, str):
            return payload
        text = payload.strip()
        if not text:
            return ""
        if text.startswith("{") or text.startswith("["):
            try:
                return json.loads(text)
            except (json.JSONDecodeError, TypeError):
                return text
        cleaned = text
        missing_padding = len(cleaned) % 4
        if missing_padding:
            cleaned += "=" * (4 - missing_padding)
        try:
            decoded = base64.b64decode(cleaned, validate=True).decode("utf-8")
        except Exception:
            return text
        decoded = decoded.strip()
        if decoded.startswith("{") or decoded.startswith("["):
            try:
                return json.loads(decoded)
            except (json.JSONDecodeError, TypeError):
                return decoded
        return decoded

    def _extract_content(parsed_content: Any) -> tuple[int, str, list[str]]:
        if isinstance(parsed_content, str):
            return 1, parsed_content[:500], []
        if not isinstance(parsed_content, dict):
            return 1, "", []
        parsed_type = parsed_content.get("contentType", 1)
        text_obj = parsed_content.get("text", {})
        parsed_text = text_obj.get("text", "") if isinstance(text_obj, dict) else str(text_obj or "")
        if parsed_text:
            return parsed_type, parsed_text, []
        if int(parsed_type or 1) == 2:
            parsed_image_urls = _extract_image_urls(parsed_content)
            if parsed_image_urls:
                return 2, parsed_image_urls[0], parsed_image_urls
        return parsed_type, "", []

    if isinstance(content_obj, dict):
        inner = _get(content_obj, "3", "content", default={})
        if isinstance(inner, dict):
            parsed_sources = [
                _get(inner, "1", "data", default=""),
                _get(inner, "5", "text", "content", default=""),
            ]
            for source in parsed_sources:
                parsed_content = _decode_embedded_content(source)
                next_content_type, next_msg_content, next_image_urls = _extract_content(parsed_content)
                if next_content_type == 2 and content_type != 2:
                    content_type = 2
                elif content_type == 1 and next_content_type not in (None, ""):
                    content_type = next_content_type
                if next_image_urls and not image_urls:
                    image_urls = next_image_urls
                if next_msg_content and not msg_content:
                    msg_content = next_msg_content
                if image_urls and msg_content:
                    break
        # 兜底：content_obj 直接包含 text 字段
        elif not msg_content:
            direct_text = _get(content_obj, "text", default="")
            if direct_text:
                msg_content = str(direct_text)[:500]
    # 兜底：content_obj 是字符串直接作为内容
    elif isinstance(content_obj, str) and content_obj:
        msg_content = content_obj[:500]
    # 兜底：从顶层 data 提取 content
    if not msg_content:
        top_content = _get(data, "content", default="")
        if isinstance(top_content, str) and top_content:
            msg_content = top_content[:500]
        elif isinstance(top_content, dict):
            top_text = _get(top_content, "text", "content", default="")
            if top_text:
                msg_content = str(top_text)[:500]
    if image_urls and not msg_content:
        msg_content = image_urls[0]

    # 解析提醒信息（reminder）—— 对齐参考实现：msg_info["10"] 是 field10Map
    reminder = _get(msg_info, "10", "reminder", default={})
    reminder_title = ""
    if isinstance(reminder, dict):
        reminder_content = _get(reminder, "reminderContent", "content", default="") or ""
        reminder_url = _get(reminder, "reminderUrl", "url", default="") or ""
        reminder_title = _get(reminder, "reminderTitle", "title", default="") or ""
        if not sender_user_id:
            sender_user_id = _get(reminder, "senderUserId", "sender", default="") or ""
        # 注意：参考实现中 field10Map 没有 senderUserName 字段，用户名从 reminderContent 提取
        # 这里保留兼容性提取，但优先级降低
        if not sender_user_name:
            sender_user_name = _get(reminder, "senderUserName", "nick", default="") or ""
        receiver = _get(reminder, "receiver", "receiverUserId", default="") or ""
    else:
        reminder_content = str(reminder) if reminder else ""
        reminder_url = ""
        receiver = ""

    # 对齐参考实现的用户名提取优先级：
    # 1. 优先从 reminderContent 提取（"XXX 向你发送了一条新消息" 模式）
    # 2. 兜底用 reminderTitle（系统提醒标题，后续会被 normalize_peer_name 过滤系统文本）
    # 参考 Java 实现：SyncMessageHandler.java 第 251-278 行
    if not sender_user_name and reminder_content:
        extracted_name = extract_username_from_reminder(reminder_content)
        if extracted_name:
            sender_user_name = extracted_name
    # 兜底：用 reminderTitle 作为用户名（参考实现的第二优先级）
    if (not sender_user_name or not sender_user_name.strip()) and reminder_title:
        sender_user_name = str(reminder_title)

    xy_goods_id = ""
    # 对齐参考实现：从 reminderUrl 中精确提取 itemId= 参数
    # 不限制域名，闲鱼可能使用 m.goofish.com / h5.m.goofish.com 等多种域名
    match = None
    if reminder_url:
        # 优先精确匹配 itemId=（参考实现的方式）
        match = re.search(r'[?&]itemId=(\d+)', reminder_url)
        if not match:
            # 降级：匹配独立的 id= 参数（避免误匹配 mtopId= 等其他参数）
            match = re.search(r'[?&]id=(\d+)', reminder_url)
        if match:
            xy_goods_id = match.group(1)
    # 兜底：从 sessionInfo.extensions.itemId 或顶层 itemId 提取
    if not xy_goods_id:
        ext_item_id = ""
        if isinstance(session_info, dict):
            ext_obj = session_info.get("extensions") if isinstance(session_info.get("extensions"), dict) else {}
            ext_item_id = str(ext_obj.get("itemId") or "")
        if not ext_item_id:
            ext_item_id = str(_get(data, "itemId", "goodsId", default="") or "")
        if ext_item_id and str(ext_item_id).isdigit():
            xy_goods_id = str(ext_item_id)

    if not any([s_id, pnm_id, sender_user_id, msg_content, reminder_content]):
        logger.info(
            "WS 结构命中但字段缺失 msgType=%s dataKeys=%s",
            msg_type,
            sorted(str(key) for key in data.keys()),
        )
        return None

    # 仅记录提取结果的存在性和结构，不记录会话标识或用户文本。
    try:
        reminder_keys = list(reminder.keys()) if isinstance(reminder, dict) else []
        logger.info(
            "WS parse_numbered_fields 提取结果: sessionRefPresent=%s messageRefPresent=%s "
            "senderRefPresent=%s senderNamePresent=%s goodsRefPresent=%s reminderUrlPresent=%s "
            "reminderContentLen=%d reminderTitleLen=%d reminderKeys=%s msgInfoKeys=%s",
            bool(s_id),
            bool(pnm_id),
            bool(sender_user_id),
            bool(sender_user_name),
            bool(xy_goods_id),
            bool(reminder_url),
            len(str(reminder_content)) if reminder_content else 0,
            len(str(reminder_title)) if reminder_title else 0,
            reminder_keys,
            list(msg_info.keys()) if isinstance(msg_info, dict) else []
        )
    except Exception:
        pass  # 已知非关键异常：调试日志格式化失败不影响解析结果

    return {
        "sId": str(s_id) if s_id else "",
        "pnmId": str(pnm_id) if pnm_id else "",
        "senderUserId": str(sender_user_id) if sender_user_id else "",
        "senderUserName": str(sender_user_name) if sender_user_name else "",
        "messageTime": int(message_time) if str(message_time).isdigit() else 0,
        "msgContent": msg_content,
        "contentType": content_type,
        "msgType": msg_type,
        "direction": "IN",
        "reminderContent": str(reminder_content) if reminder_content else "",
        "reminderUrl": str(reminder_url) if reminder_url else "",
        "receiverUserId": str(receiver) if receiver else "",
        "xyGoodsId": xy_goods_id,
        "imageUrl": image_urls[0] if image_urls else "",
        "imageUrls": image_urls,
    }


def generate_mid() -> str:
    """生成消息 ID（用于 WebSocket 消息头中的 mid）。

    与 Java 成功实现对齐：随机数(0-999) + 毫秒时间戳 + " 0"
    示例：1231741667630548 0
    """
    ts = int(time.time() * 1000)
    rand = int(hashlib.md5(str(ts).encode()).hexdigest(), 16) % 1000
    return f"{rand}{ts} 0"


# ============================================================
# 消息校验函数（用于检测解析后的字段错位）
# ============================================================

# ============================================================
# 用户名提取与系统文本过滤
# ============================================================

# 系统通知/非真实用户的文本关键词
SYSTEM_PEER_KEYWORDS = [
    "交易消息", "工作台通知", "系统通知", "通知消息",
    "买家已拍下，待付款", "我已拍下，待付款",
    "我已付款，等待你发货", "买家确认收货，交易成功",
    "快给ta一个评价吧～", "记得及时发货",
    "等待你发货", "订单提醒",
]


def extract_username_from_reminder(reminder_content: str) -> str:
    """从 reminderContent 中提取真实用户名。

    闲鱼消息结构中的 reminderContent 格式：
      格式1: "用户名 向你发送了一条新消息"
      格式2: "用户名 ：消息内容"

    Args:
        reminder_content: 提醒内容文本

    Returns:
        提取的用户名，如果无法提取返回空字符串
    """
    if not reminder_content:
        return ""

    content = reminder_content.strip()

    # 格式1: "用户名 向你发送了一条新消息"
    # 对齐参考实现：不限制用户名长度（参考 Java 实现仅要求 nameEnd > 0）
    patterns = [
        " 向你发送了一条新消息",
        " 向你发送了一条消息",
    ]
    for pattern in patterns:
        idx = content.find(pattern)
        if idx > 0:
            return content[:idx]

    # 格式2: "用户名 ：消息内容" 或 "用户名：消息内容"
    # 对齐参考实现：限制位置 < 20，避免匹配到消息内容中的冒号
    for sep in [" ：", "："]:
        idx = content.find(sep)
        if idx > 0 and idx < 20:
            return content[:idx]

    return ""


def is_synthetic_peer_name(name: str) -> bool:
    """检查名称是否为系统通知文本（非真实用户名）。

    系统通知的 reminderTitle 会包含"等待你发货""订单提醒"等文本，
    这些不是真实用户名称，需要过滤掉。

    Args:
        name: 待检查的名称

    Returns:
        True 表示是系统文本（非真实用户名）
    """
    if not name or not name.strip():
        return True
    text = name.strip()
    for keyword in SYSTEM_PEER_KEYWORDS:
        if keyword in text:
            return True
    # 额外检查常见的系统文本关键词
    extra_keywords = ["发货", "等待", "付款", "订单", "提醒", "通知",
                      "系统", "消息", "讲价", "小刀", "砍价"]
    text_lower = text.lower()
    for keyword in extra_keywords:
        if keyword.lower() in text_lower:
            return True
    return False


def normalize_peer_name(name: str) -> str:
    """标准化用户名：去除系统文本，返回清洗后的用户名。

    如果名称包含系统通知关键词，返回空字符串。

    Args:
        name: 原始用户名

    Returns:
        标准化后的用户名（系统文本则返回空字符串）
    """
    if not name or not name.strip():
        return ""
    text = name.strip()
    if is_synthetic_peer_name(text):
        return ""
    return text


def contains_chinese(text: str) -> bool:
    """检查字符串是否包含中文字符。"""
    if not text:
        return False
    for ch in text:
        if '\u4e00' <= ch <= '\u9fff' or '\u3400' <= ch <= '\u4dbf':
            return True
    return False


def validate_parsed_message(msg: dict) -> dict:
    """对解析后的消息进行后置校验，修复或标记异常字段。

    背景诊断发现：
    - s_id 被消息内容污染（出现"你好"、"在干嘛"等中文文本）
    - sender_user_id 大量为空
    - pnm_id 基本为空（去重失效）

    Args:
        msg: parse_numbered_fields 解析后的消息字典

    Returns:
        处理后的消息字典，包含 parse_status 字段
    """
    msg = dict(msg)  # 不修改原对象
    if _is_misplaced_pnm_sender_message(msg):
        msg["parseStatus"] = "failed"
        logger.warning(
            "validate: sender_user_id/content 疑似字段错位, 标记 failed. "
            "senderRefPresent=%s contentLen=%d messageRefPresent=%s",
            bool(msg.get("senderUserId")),
            len(str(msg.get("msgContent") or "")),
            bool(msg.get("pnmId")),
        )
        return msg
    s_id = str(msg.get("sId") or "")
    msg_content = str(msg.get("msgContent") or "")
    sender_user_id = str(msg.get("senderUserId") or "")
    receiver_user_id = str(msg.get("receiverUserId") or "")
    pnm_id = str(msg.get("pnmId") or "")
    content_type = int(msg.get("contentType") or 1)

    violations = []

    # 校验1: s_id 不能是自然语言文本
    if contains_chinese(s_id) and not s_id.startswith("sid:"):
        violations.append("s_id_contains_chinese")
        # 尝试从原始字段恢复 s_id（将 s_id 视为被错位的内容）
        # 此时 s_id 里存的实际是消息内容或其它文本
        # 将错位的 s_id 置空，后续触发 peerId 的 sid:xxx 兜底
        msg["sId"] = ""
        logger.warning(
            "validate: s_id 包含中文(疑似字段错位), 已清空. "
            "originalSessionRefLen=%d contentLen=%d messageRefPresent=%s",
            len(s_id),
            len(msg_content),
            bool(pnm_id),
        )

    # 校验2: 文本消息的 msg_content 为空但 s_id 有中文 → 字段错位
    if content_type == 1 and not msg_content and contains_chinese(s_id):
        violations.append("content_misplaced_in_sid")
        # 将 s_id 的值作为 msg_content
        msg["msgContent"] = s_id
        msg["sId"] = ""
        logger.warning(
            "validate: 文本内容错位到 s_id 字段, 已修复. "
            "recoveredContentLen=%d",
            len(s_id),
        )

    # 校验3: peer 等于卖家自己 → 排除自身消息
    sender_user_id_normalized = sender_user_id.replace("@goofish", "").strip() if sender_user_id else ""
    seller_external_uid = str(msg.get("sellerExternalUid") or "")
    seller_external_uid_normalized = seller_external_uid.replace("@goofish", "").strip() if seller_external_uid else ""
    if sender_user_id_normalized and seller_external_uid_normalized and sender_user_id_normalized == seller_external_uid_normalized:
        violations.append("peer_is_self")
        msg["direction"] = "OUT"  # 自己发给别人
        logger.warning(
            "validate: sender_user_id 等于卖家自己, 修正 direction=OUT"
        )
    elif (
        not sender_user_id_normalized
        and receiver_user_id
        and seller_external_uid_normalized
    ):
        # 自问自答防护：sender_user_id 为空时，通过 receiverUserId 反向推断发送者。
        # 场景：IM 回环消息可能因协议变体导致 senderUserId 字段缺失，
        # 此时若 receiverUserId 等于卖家自己，说明是买家发给我的（保持 IN）；
        # 若 receiverUserId 不等于卖家自己（即买家），说明是自己发出的（修正为 OUT）。
        receiver_user_id_normalized = receiver_user_id.replace("@goofish", "").strip()
        if receiver_user_id_normalized and receiver_user_id_normalized != seller_external_uid_normalized:
            violations.append("receiver_is_buyer_self_missing")
            msg["direction"] = "OUT"  # 自己发给买家（senderUserId 缺失的回环消息）
            logger.warning(
                "validate: sender_user_id 为空且 receiverUserId 指向买家, 修正 direction=OUT (防止自问自答)"
            )

    # 校验4: sender/receiver/pnm 为空并不一定是失败。
    # 闲鱼官方消息列表里经常只给 sId + msgContent（用户截图中的会话正是这种结构），
    # 此时可以用 sId 作为会话主键继续入库和展示；只有连 sId 都没有时才判定失败。
    if not sender_user_id and not receiver_user_id and not pnm_id:
        if s_id and msg_content:
            violations.append("peer_id_fallback_sid")
        elif not s_id:
            violations.append("all_ids_empty")

    # 校验5: pnm_id 为空时，用稳定 hash 作为备用消息 UID。
    # messageTime 常为 0，因此 hash 中同时纳入 contentType / reminderContent，降低重复折叠概率。
    if not pnm_id and msg_content:
        fallback_raw = "|".join([
            s_id,
            sender_user_id,
            receiver_user_id,
            str(msg.get("messageTime") or "0"),
            str(content_type),
            msg_content,
            str(msg.get("reminderContent") or ""),
        ])
        msg["pnmId"] = hashlib.sha256(fallback_raw.encode()).hexdigest()[:24]
        violations.append("pnm_id_fallback_hash")

    # 确定 parse_status：
    # - sId+内容存在但 peer 缺失 → partial，可展示并可用 sid:xxx 兜底聚合；
    # - sId 乱码/中文且未恢复、或全无可用标识 → failed。
    if not violations:
        msg["parseStatus"] = "ok"
    elif "all_ids_empty" in violations or ("s_id_contains_chinese" in violations and not msg.get("sId")):
        msg["parseStatus"] = "failed"
    else:
        msg["parseStatus"] = "partial"

    if violations:
        logger.info(
            "validate: parseStatus=%s violations=%s sessionRefPresent=%s "
            "messageRefPresent=%s senderRefPresent=%s",
            msg["parseStatus"],
            violations,
            bool(s_id),
            bool(pnm_id),
            bool(sender_user_id),
        )

    return msg


def build_reg_message(access_token: str, did: str, ua: str = "") -> dict:
    """构建 /reg 注册消息。
    
    Args:
        access_token: WebSocket accessToken
        did: 设备 ID（格式: UUID-UNB）
        ua: User-Agent 字符串
        
    Returns:
        注册消息字典
    """
    mid = generate_mid()
    headers = {
        "cache-header": "app-key token ua wv",
        "app-key": "444e9908a51d1cb236a27862abc769c9",
        "token": access_token,
        "ua": ua,
        "did": did,
        "dt": "j",
        "wv": "im:3,au:3,sy:6",
        "sync": "0,0;0;0;",
        "mid": mid,
    }
    return {
        "lwp": "/reg",
        "headers": headers,
    }


def build_sync_message(pts: int = 0, high_pts: int = 0) -> dict:
    """构建 /r/SyncStatus/ackDiff 同步消息。
    
    Args:
        pts: 同步起始时间点（微秒），0 表示从当前时间开始
        high_pts: 已确认的同步高点（maxHighPts），用于增量同步
        
    Returns:
        同步消息字典
    """
    if pts <= 0:
        pts = int(time.time() * 1000000)  # 微秒，匹配 Java System.currentTimeMillis() * 1000
    now_sec = int(time.time())
    now_ms = now_sec * 1000
    return {
        "lwp": "/r/SyncStatus/ackDiff",
        "headers": {
            "mid": generate_mid(),
        },
        "body": [
            {
                "pipeline": "sync",
                "tooLong2Tag": "PNM,1",
                "channel": "sync",
                "topic": "sync",
                "highPts": high_pts,
                "pts": pts,
                "seq": 0,
                "timestamp": now_ms,
            }
        ]
    }


def build_ack_message(pnm_id: str) -> dict:
    """构建 ACK 确认消息。
    
    Args:
        pnm_id: 需要确认的消息 ID
        
    Returns:
        ACK 消息字典
    """
    return {
        "lwp": "/!",
        "body": {
            "pnmId": pnm_id,
        },
        "code": 200,
    }


def build_heartbeat_message() -> dict:
    """构建心跳消息。"""
    return {
        "lwp": "/!",
        "body": {},
    }


def build_send_message(
    cid: str,
    to_id: str,
    from_id: str,
    text: str,
    sid: str,
) -> dict:
    """构建发送消息。
    
    Args:
        cid: 会话 ID (格式: xxx@goofish)
        to_id: 接收者 ID (格式: xxx@goofish)
        from_id: 发送者 ID (格式: xxx@goofish)
        text: 消息文本
        sid: 注册时获取的 sid
        
    Returns:
        发送消息字典
    """
    cid = _normalize_goofish_target(cid)
    to_id = _normalize_goofish_target(to_id)
    from_id = _normalize_goofish_target(from_id)

    # 参考 Java 版已验证可用的实现：消息内容先构建为 JSON 再 base64
    message_content = {
        "contentType": 1,
        "text": {"text": text},
    }
    b64_data = base64.b64encode(json.dumps(message_content, ensure_ascii=False).encode()).decode()

    message_body = {
        "uuid": str(uuid.uuid4()),
        "cid": cid,
        "conversationType": 1,
        "content": {
            "contentType": 101,
            "custom": {
                "type": 1,
                "data": b64_data,
            },
        },
        "redPointPolicy": 0,
        "extension": {"extJson": "{}"},
        "ctx": {"appVersion": "1.0", "platform": "web"},
        "mtags": {},
        "msgReadStatusSetting": 1,
    }

    # actualReceivers 必须作为 body 的第二个独立元素，
    # 且必须包含发送者自身的 ID 才能被服务端接受（否则返回 code=500）。
    receivers = {
        "actualReceivers": [to_id, from_id],
    }

    return {
        "lwp": "/r/MessageSend/sendByReceiverScope",
        "headers": {
            "mid": generate_mid(),
            "sid": sid,
        },
        "body": [message_body, receivers],
    }


def build_send_image_message(
    cid: str,
    to_id: str,
    from_id: str,
    image_url: str,
    sid: str,
    width: int = 800,
    height: int = 600,
) -> dict:
    """构建发送图片消息。

    Args:
        cid: 会话 ID (格式: xxx@goofish)
        to_id: 接收者 ID (格式: xxx@goofish)
        from_id: 发送者 ID (格式: xxx@goofish)
        image_url: 图片 URL
        sid: 注册时获取的 sid

    Returns:
        发送消息字典
    """
    cid = _normalize_goofish_target(cid)
    to_id = _normalize_goofish_target(to_id)
    from_id = _normalize_goofish_target(from_id)

    safe_width = max(int(width or 800), 1)
    safe_height = max(int(height or 600), 1)
    message_content = {
        "contentType": 2,
        "image": {
            "url": image_url,
            "pics": [
                {
                    "height": safe_height,
                    "type": 0,
                    "url": image_url,
                    "width": safe_width,
                }
            ],
        },
    }
    b64_data = base64.b64encode(json.dumps(message_content, ensure_ascii=False).encode()).decode()

    message_body = {
        "uuid": str(uuid.uuid4()),
        "cid": cid,
        "conversationType": 1,
        "content": {
            "contentType": 101,
            "custom": {
                "type": 1,
                "data": b64_data,
            },
        },
        "redPointPolicy": 0,
        "extension": {"extJson": "{}"},
        "ctx": {"appVersion": "1.0", "platform": "web"},
        "mtags": {},
        "msgReadStatusSetting": 1,
    }

    receivers = {
        "actualReceivers": [to_id, from_id],
    }

    return {
        "lwp": "/r/MessageSend/sendByReceiverScope",
        "headers": {
            "mid": generate_mid(),
            "sid": sid,
        },
        "body": [message_body, receivers],
    }
