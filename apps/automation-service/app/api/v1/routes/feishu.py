"""
飞书自建应用事件回调路由
========================

接收飞书开放平台的事件回调：
1. URL 验证（challenge 请求）
2. 消息接收事件（im.message.receive_v1）
3. 其他事件（暂不处理）

URL: POST /api/feishu/webhook

注意：此路由不需要登录鉴权，但需要校验飞书的 Verification Token。
飞书在配置事件订阅 URL 时会发送 challenge 请求验证所有权。
"""
import json
import logging
import hmac

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.response import ResultObject
from app.core.cookie_crypto import decrypt_cookie_if_needed
from app.services.feishu_bot import (
    _load_feishu_app_config,
    decrypt_encrypted_event,
    make_url_verification_response,
    parse_message_event,
    verify_event_signature,
)
from app.services.feishu_chat import handle_feishu_user_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feishu", tags=["feishu"])


@router.post("/webhook")
async def feishu_webhook(request: Request):
    """飞书事件回调入口。

    飞书会在以下场景调用此接口：
    1. 配置事件订阅 URL 时发送 challenge 请求
    2. 用户向机器人发送消息时发送 im.message.receive_v1 事件
    3. 其他已订阅事件

    飞书事件回调 v2.0 schema：
    {
      "schema": "2.0",
      "header": {
        "event_id": "...",
        "event_type": "im.message.receive_v1",
        "create_time": "...",
        "token": "...",  // Verification Token
        "app_id": "...",
        "tenant_key": "..."
      },
      "event": { ... }
    }

    加密场景下：
    {
      "encrypt": "<base64_aes_encrypted_payload>"
    }
    """
    try:
        body_bytes = await request.body()
        try:
            body = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            return JSONResponse(status_code=400, content={"error": "invalid json"})

        tenant_key = ""
        # === 处理加密事件 ===
        if "encrypt" in body:
            # 需要从所有租户配置中查找匹配的 encrypt_key
            # 简化处理：遍历可能的 tenant_id（性能可接受，事件回调量很小）
            from sqlalchemy import text
            from app.core.database import async_session
            async with async_session() as db:
                rows = (await db.execute(
                    text(
                        "SELECT tenant_id, config_json FROM user_notification_setting "
                        "WHERE deleted = 0"
                    )
                )).mappings().all()

            decrypted = None
            tenant_id_found = None
            for row in rows:
                try:
                    config = row["config_json"]
                    if isinstance(config, str):
                        config = json.loads(config)
                    channels = config.get("channels") or []
                    for ch in channels:
                        if ch.get("type") == "feishu_app" and ch.get("enabled"):
                            encrypt_key = decrypt_cookie_if_needed(
                                ch.get("encryptKey") or ch.get("encrypt_key") or ""
                            ) or ""
                            if encrypt_key:
                                try:
                                    decrypted = decrypt_encrypted_event(encrypt_key, body["encrypt"])
                                    tenant_id_found = int(row["tenant_id"])
                                    break
                                except Exception:
                                    continue
                    if decrypted:
                        break
                except Exception:
                    continue

            if not decrypted:
                logger.warning("飞书事件加密但无法解密：未找到匹配的 encrypt_key")
                return JSONResponse(status_code=400, content={"error": "decrypt failed"})
            body = decrypted
            tenant_id = tenant_id_found
        else:
            # 未加密：从 header.tenant_key 或 app_id 推断 tenant_id
            tenant_key = body.get("header", {}).get("tenant_key", "")
            tenant_id = await _resolve_tenant_id_from_tenant_key(tenant_key, body)

        if tenant_id is None:
            logger.warning("飞书事件无法确定 tenant_id: hasTenantKey=%s", bool(tenant_key))
            return JSONResponse(status_code=503, content={"error": "tenant mapping unavailable"})

        # === 加载飞书应用配置 ===
        config = await _load_feishu_app_config(tenant_id)
        if not config:
            logger.warning("飞书事件回调但租户未配置自建应用: tenant_id=%d", tenant_id)
            return JSONResponse(status_code=503, content={"error": "tenant configuration unavailable"})

        # === 校验 Verification Token ===
        verification_token = config.get("verificationToken", "")
        if not verify_event_signature(verification_token, body, dict(request.headers)):
            logger.warning("飞书事件 Token 校验失败: tenant_id=%d", tenant_id)
            return JSONResponse(status_code=401, content={"error": "invalid token"})

        # === URL 验证（challenge 请求）===
        if "challenge" in body:
            challenge = body["challenge"]
            logger.info("飞书 URL 验证 challenge: tenant_id=%d", tenant_id)
            return JSONResponse(status_code=200, content=make_url_verification_response(challenge))

        # === 事件去重（基于 event_id）===
        header = body.get("header", {})
        event_id = header.get("event_id", "")
        if event_id and _is_duplicate_event(tenant_id, event_id):
            logger.debug("飞书事件重复，已忽略: event_id=%s", event_id)
            return JSONResponse(status_code=200, content={"code": 0, "msg": "duplicate"})

        # === 处理消息接收事件 ===
        event_type = header.get("event_type", "")
        if event_type == "im.message.receive_v1":
            message_data = parse_message_event(body)
            if not message_data:
                logger.warning("飞书消息事件解析失败: event_id=%s", event_id)
                _mark_event_processed(tenant_id, event_id)
                return JSONResponse(status_code=200, content={"code": 0, "msg": "parse failed"})

            user_open_id = message_data["sender_open_id"]
            content = message_data["content"]
            message_type = message_data["message_type"]

            # 仅处理文本消息（图片/文件等暂不处理）
            if message_type != "text":
                # 非文本消息回复提示
                from app.services.feishu_bot import send_text_message
                await send_text_message(
                    tenant_id, user_open_id,
                    "目前仅支持文本消息，请发送文字内容与我对话。"
                )
                _mark_event_processed(tenant_id, event_id)
                return JSONResponse(status_code=200, content={"code": 0, "msg": "ok"})

            if not content.strip():
                _mark_event_processed(tenant_id, event_id)
                return JSONResponse(status_code=200, content={"code": 0, "msg": "empty"})

            # 调用 AI 对话处理
            logger.info(
                "飞书消息接收: tenant_id=%d messageType=%s contentLength=%d",
                tenant_id, message_type, len(content),
            )
            reply = await handle_feishu_user_message(
                tenant_id=tenant_id,
                user_open_id=user_open_id,
                message_content=content,
            )
            _mark_event_processed(tenant_id, event_id)
            # AI 已经在 handle_feishu_user_message 内部触发了对应的发送动作
            # 这里仅返回 200 让飞书知道事件已处理
            return JSONResponse(status_code=200, content={"code": 0, "msg": "ok"})

        # 其他事件暂不处理
        logger.debug("飞书事件未处理: event_type=%s", event_type)
        _mark_event_processed(tenant_id, event_id)
        return JSONResponse(status_code=200, content={"code": 0, "msg": "ignored"})

    except Exception as e:
        logger.error("飞书 webhook 异常: %s", e, exc_info=True)
        # 瞬时处理失败必须返回非 2xx，让飞书按平台策略重试，避免消息静默丢失。
        return JSONResponse(
            status_code=500,
            content={"code": 1, "msg": "temporary failure"},
        )


@router.get("/config/check")
async def feishu_config_check(request: Request):
    """检查飞书自建应用配置是否完整（用于前端配置页面的连通性测试）"""
    from app.core.security import get_current_user_optional
    current_user = await get_current_user_optional(request)
    if not current_user:
        return ResultObject.validate_failed("未登录")
    tenant_id = current_user.get("tenant_id")
    config = await _load_feishu_app_config(tenant_id)
    if not config:
        return ResultObject.failed("未配置飞书自建应用")
    return ResultObject.success({
        "configured": True,
        "appId": config.get("appId", "")[:8] + "..." if config.get("appId") else "",
        "hasSecret": bool(config.get("appSecret")),
        "hasVerificationToken": bool(config.get("verificationToken")),
        "hasEncryptKey": bool(config.get("encryptKey")),
        "receiveId": config.get("receiveId", ""),
        "receiveIdType": config.get("receiveIdType", "open_id"),
    })


# ============================================================
# 辅助函数
# ============================================================

# Event identifiers are supplied within a tenant/app namespace.  Scope the
# in-memory deduplication key so one tenant can never suppress another
# tenant's event, even if an upstream identifier is reused.
_EVENT_DEDUP: dict[tuple[int, str], float] = {}
_EVENT_DEDUP_TTL = 600  # 10 分钟


def _is_duplicate_event(tenant_id: int, event_id: str) -> bool:
    """检查事件是否已处理过（飞书会重试未及时响应的事件）"""
    import time
    now = time.time()
    # 清理过期记录
    expired = [k for k, v in _EVENT_DEDUP.items() if now - v > _EVENT_DEDUP_TTL]
    for k in expired:
        _EVENT_DEDUP.pop(k, None)
    return (tenant_id, event_id) in _EVENT_DEDUP


def _mark_event_processed(tenant_id: int, event_id: str) -> None:
    import time
    if tenant_id > 0 and event_id:
        _EVENT_DEDUP[(tenant_id, event_id)] = time.time()


async def _resolve_tenant_id_from_tenant_key(tenant_key: str, body: dict) -> int | None:
    """从飞书 tenant_key 推断系统 tenant_id。

    飞书的 tenant_key 是租户在飞书的唯一标识，与系统的 tenant_id 不同。
    简化处理：遍历 user_notification_setting 表查找配置了对应 app_id 的租户。

    退而求其次：如果只有一个租户配置了飞书自建应用，直接返回该租户 ID。
    """
    from sqlalchemy import text
    from app.core.database import async_session

    header = body.get("header") if isinstance(body, dict) else {}
    header = header if isinstance(header, dict) else {}
    app_id = str(header.get("app_id") or body.get("app_id") or "").strip()
    tenant_key = str(tenant_key or "").strip()
    if not app_id and not tenant_key:
        return None

    async with async_session() as db:
        rows = (await db.execute(
            text(
                "SELECT tenant_id, config_json FROM user_notification_setting "
                "WHERE deleted = 0"
            )
        )).mappings().all()
    return _match_feishu_tenant(rows, tenant_key=tenant_key, app_id=app_id)


def _match_feishu_tenant(rows, tenant_key: str, app_id: str) -> int | None:
    matches: set[int] = set()
    for row in rows or []:
        try:
            config = row["config_json"]
            if isinstance(config, str):
                config = json.loads(config)
            for channel in config.get("channels") or []:
                if channel.get("type") != "feishu_app" or not channel.get("enabled"):
                    continue
                configured_app_id = str(channel.get("appId") or channel.get("app_id") or "").strip()
                configured_tenant_key = str(
                    channel.get("tenantKey") or channel.get("tenant_key") or ""
                ).strip()
                app_matches = bool(app_id and configured_app_id and hmac.compare_digest(app_id, configured_app_id))
                tenant_matches = bool(
                    tenant_key
                    and configured_tenant_key
                    and hmac.compare_digest(tenant_key, configured_tenant_key)
                )
                if app_matches or tenant_matches:
                    matches.add(int(row["tenant_id"]))
        except Exception:
            continue
    if len(matches) == 1:
        return next(iter(matches))
    if len(matches) > 1:
        logger.error("飞书应用标识映射到多个租户，拒绝处理 eventTenantCount=%d", len(matches))
    return None
