"""
飞书自建应用机器人 API 客户端
================================

实现与飞书开放平台的双向通信：
- 获取 / 刷新 tenant_access_token
- 发送文本消息（包含按用户/群聊 ID）
- 上传图片并获取 image_key
- 发送图片消息
- 接收并校验事件回调签名
- 接收用户消息事件并提取关键字段

与 notify_dispatcher.py 中"飞书自定义机器人"（webhook + 签名）的实现完全不同：
- 自定义机器人：单向推送，仅需 webhookUrl + secret
- 自建应用机器人：双向通信，需要 app_id/app_secret，支持接收用户回复

凭证存储：
- app_id / app_secret / verification_token / encrypt_key
  存储于 user_notification_setting.config_json.channels[]
  type='feishu_app' 的元素中（与 type='feishu' 的自定义机器人区分开）
- secret 字段用于存储 app_secret（复用现有 schema，不新增表）
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Any, Optional

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import async_session
from ..core.cookie_crypto import decrypt_cookie_if_needed, encrypt_cookie_for_storage

logger = logging.getLogger(__name__)


def _decrypt_secret(value: Any) -> str:
    return str(decrypt_cookie_if_needed(str(value or "")) or "")


def _encrypt_secret(value: Any) -> str:
    return str(encrypt_cookie_for_storage(str(value or "")) or "")


# ============================================================
# 飞书开放平台 API 端点
# ============================================================
FEISHU_HOST = "https://open.feishu.cn"
URL_GET_TENANT_ACCESS_TOKEN = f"{FEISHU_HOST}/open-apis/auth/v3/tenant_access_token/internal"
URL_SEND_MESSAGE = f"{FEISHU_HOST}/open-apis/im/v1/messages"
URL_UPLOAD_IMAGE = f"{FEISHU_HOST}/open-apis/im/v1/images"


# tenant_access_token 缓存：(tenant_id) -> (token, expire_at)
# 飞书 token 有效期 2 小时，提前 5 分钟刷新
_TOKEN_CACHE: dict[int, tuple[str, float]] = {}
_TOKEN_LOCK: dict[int, Any] = {}


# ============================================================
# 配置加载
# ============================================================
async def _load_feishu_app_config(tenant_id: int) -> Optional[dict]:
    """从 user_notification_setting.config_json 读取飞书自建应用配置。

    在 channels[] 中查找 type='feishu_app' 且 enabled=True 的元素，
    返回其字段（appId, secret 即 appSecret, verificationToken, encryptKey, receiveId, receiveIdType）。

    Returns:
        None 表示未配置；dict 表示配置项
    """
    try:
        async with async_session() as db:
            row = (await db.execute(
                text(
                    "SELECT config_json FROM user_notification_setting "
                    "WHERE tenant_id = :tid AND deleted = 0 "
                    "ORDER BY updated_time DESC LIMIT 1"
                ),
                {"tid": tenant_id},
            )).mappings().first()
        if not row:
            return None
        config = row["config_json"]
        if isinstance(config, str):
            config = json.loads(config)
        channels = config.get("channels") or []
        for ch in channels:
            if ch.get("type") == "feishu_app" and ch.get("enabled"):
                return {
                    "appId": ch.get("appId") or ch.get("app_id") or "",
                    "appSecret": _decrypt_secret(ch.get("secret") or ch.get("appSecret") or ch.get("app_secret")),
                    "verificationToken": _decrypt_secret(ch.get("verificationToken") or ch.get("verification_token")),
                    "encryptKey": _decrypt_secret(ch.get("encryptKey") or ch.get("encrypt_key")),
                    "receiveId": ch.get("receiveId") or ch.get("receive_id") or "",
                    "receiveIdType": ch.get("receiveIdType") or ch.get("receive_id_type") or "open_id",
                }
        return None
    except Exception as e:
        logger.warning("加载飞书自建应用配置失败 tenant_id=%d: %s", tenant_id, e, exc_info=True)
        return None


async def _save_feishu_app_config(tenant_id: int, user_id: int, config: dict) -> bool:
    """保存飞书自建应用配置到 config_json.channels[]（type='feishu_app'）。

    若已存在 feishu_app 渠道则更新，否则追加。
    """
    try:
        async with async_session() as db:
            row = (await db.execute(
                text(
                    "SELECT id, config_json FROM user_notification_setting "
                    "WHERE tenant_id = :tid AND deleted = 0 "
                    "ORDER BY updated_time DESC LIMIT 1"
                ),
                {"tid": tenant_id},
            )).mappings().first()
            if row:
                full_config = row["config_json"]
                if isinstance(full_config, str):
                    full_config = json.loads(full_config)
                channels = full_config.get("channels") or []
                # 查找已有 feishu_app 渠道
                found = False
                for i, ch in enumerate(channels):
                    if ch.get("type") == "feishu_app":
                        channels[i] = {
                            "key": "feishu_app",
                            "name": "飞书自建应用",
                            "type": "feishu_app",
                            "enabled": True,
                            "appId": config.get("appId", ""),
                            "secret": _encrypt_secret(config.get("appSecret", "")),
                            "verificationToken": _encrypt_secret(config.get("verificationToken", "")),
                            "encryptKey": _encrypt_secret(config.get("encryptKey", "")),
                            "receiveId": config.get("receiveId", ""),
                            "receiveIdType": config.get("receiveIdType", "open_id"),
                        }
                        found = True
                        break
                if not found:
                    channels.append({
                        "key": "feishu_app",
                        "name": "飞书自建应用",
                        "type": "feishu_app",
                        "enabled": True,
                        "appId": config.get("appId", ""),
                        "secret": _encrypt_secret(config.get("appSecret", "")),
                        "verificationToken": _encrypt_secret(config.get("verificationToken", "")),
                        "encryptKey": _encrypt_secret(config.get("encryptKey", "")),
                        "receiveId": config.get("receiveId", ""),
                        "receiveIdType": config.get("receiveIdType", "open_id"),
                    })
                full_config["channels"] = channels
                await db.execute(
                    text(
                        "UPDATE user_notification_setting SET config_json = :cfg, updated_time = NOW() "
                        "WHERE id = :id"
                    ),
                    {"cfg": json.dumps(full_config, ensure_ascii=False), "id": row["id"]},
                )
            else:
                # 不存在则插入
                full_config = {
                    "sendMode": "single",
                    "channels": [{
                        "key": "feishu_app",
                        "name": "飞书自建应用",
                        "type": "feishu_app",
                        "enabled": True,
                        "appId": config.get("appId", ""),
                        "secret": _encrypt_secret(config.get("appSecret", "")),
                        "verificationToken": _encrypt_secret(config.get("verificationToken", "")),
                        "encryptKey": _encrypt_secret(config.get("encryptKey", "")),
                        "receiveId": config.get("receiveId", ""),
                        "receiveIdType": config.get("receiveIdType", "open_id"),
                    }],
                    "events": [],
                }
                await db.execute(
                    text(
                        "INSERT INTO user_notification_setting (tenant_id, user_id, config_json, created_time, updated_time, deleted) "
                        "VALUES (:tid, :uid, :cfg, NOW(), NOW(), 0)"
                    ),
                    {
                        "tid": tenant_id,
                        "uid": user_id,
                        "cfg": json.dumps(full_config, ensure_ascii=False),
                    },
                )
            await db.commit()
            return True
    except Exception as e:
        logger.error("保存飞书自建应用配置失败 tenant_id=%d: %s", tenant_id, e, exc_info=True)
        return False


# ============================================================
# tenant_access_token 管理
# ============================================================
async def get_tenant_access_token(tenant_id: int) -> Optional[str]:
    """获取飞书自建应用的 tenant_access_token（带缓存）。

    缓存有效期 2 小时，提前 5 分钟刷新。失败返回 None。
    """
    import asyncio

    now = time.time()
    cached = _TOKEN_CACHE.get(tenant_id)
    if cached and cached[1] > now + 300:
        return cached[0]

    # 简单的协程锁：避免并发请求 token
    lock = _TOKEN_LOCK.get(tenant_id)
    if lock is None:
        lock = asyncio.Lock()
        _TOKEN_LOCK[tenant_id] = lock
    async with lock:
        # 双重检查
        cached = _TOKEN_CACHE.get(tenant_id)
        if cached and cached[1] > now + 300:
            return cached[0]

        config = await _load_feishu_app_config(tenant_id)
        if not config or not config.get("appId") or not config.get("appSecret"):
            logger.warning("飞书自建应用配置不完整 tenant_id=%d", tenant_id)
            return None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    URL_GET_TENANT_ACCESS_TOKEN,
                    json={
                        "app_id": config["appId"],
                        "app_secret": config["appSecret"],
                    },
                )
                data = resp.json()
                if data.get("code") != 0:
                    logger.warning(
                        "获取 tenant_access_token 失败 tenant_id=%d: %s",
                        tenant_id, data.get("msg"),
                    )
                    return None
                token = data.get("tenant_access_token")
                expire = data.get("expire", 7200)
                _TOKEN_CACHE[tenant_id] = (token, now + expire)
                logger.info(
                    "获取 tenant_access_token 成功 tenant_id=%d, 有效期=%ds",
                    tenant_id, expire,
                )
                return token
        except Exception as e:
            logger.error("获取 tenant_access_token 异常 tenant_id=%d: %s", tenant_id, e, exc_info=True)
            return None


# ============================================================
# 发送消息
# ============================================================
async def send_text_message(
    tenant_id: int,
    receive_id: str,
    text: str,
    receive_id_type: str = "open_id",
) -> bool:
    """向指定用户/群聊发送文本消息。

    Args:
        tenant_id: 租户 ID（用于读取 app 配置）
        receive_id: 接收者 ID（open_id / user_id / chat_id 等）
        text: 消息文本
        receive_id_type: receive_id 类型，默认 open_id

    Returns:
        True 表示发送成功
    """
    token = await get_tenant_access_token(tenant_id)
    if not token:
        return False

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                URL_SEND_MESSAGE,
                params={"receive_id_type": receive_id_type},
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "receive_id": receive_id,
                    "msg_type": "text",
                    "content": json.dumps({"text": text}, ensure_ascii=False),
                },
            )
            data = resp.json()
            if data.get("code") != 0:
                logger.warning(
                    "飞书发送文本消息失败 tenant_id=%d receive_id=%s: %s",
                    tenant_id, receive_id, data.get("msg"),
                )
                return False
            return True
    except Exception as e:
        logger.error("飞书发送文本消息异常 tenant_id=%d: %s", tenant_id, e, exc_info=True)
        return False


async def upload_image(tenant_id: int, image_bytes: bytes) -> Optional[str]:
    """上传图片到飞书获取 image_key。

    Args:
        tenant_id: 租户 ID
        image_bytes: 图片二进制数据（PNG/JPEG）

    Returns:
        image_key 字符串，失败返回 None
    """
    token = await get_tenant_access_token(tenant_id)
    if not token:
        return None

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                URL_UPLOAD_IMAGE,
                headers={"Authorization": f"Bearer {token}"},
                data={"image_type": "message"},
                files={"image": ("qr.png", image_bytes, "image/png")},
            )
            data = resp.json()
            if data.get("code") != 0:
                logger.warning(
                    "飞书上传图片失败 tenant_id=%d: %s",
                    tenant_id, data.get("msg"),
                )
                return None
            return data.get("data", {}).get("image_key")
    except Exception as e:
        logger.error("飞书上传图片异常 tenant_id=%d: %s", tenant_id, e, exc_info=True)
        return None


async def send_image_message(
    tenant_id: int,
    receive_id: str,
    image_key: str,
    receive_id_type: str = "open_id",
) -> bool:
    """发送图片消息。

    Args:
        tenant_id: 租户 ID
        receive_id: 接收者 ID
        image_key: upload_image 返回的 image_key
        receive_id_type: receive_id 类型
    """
    token = await get_tenant_access_token(tenant_id)
    if not token:
        return False

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                URL_SEND_MESSAGE,
                params={"receive_id_type": receive_id_type},
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "receive_id": receive_id,
                    "msg_type": "image",
                    "content": json.dumps({"image_key": image_key}, ensure_ascii=False),
                },
            )
            data = resp.json()
            if data.get("code") != 0:
                logger.warning(
                    "飞书发送图片消息失败 tenant_id=%d receive_id=%s: %s",
                    tenant_id, receive_id, data.get("msg"),
                )
                return False
            return True
    except Exception as e:
        logger.error("飞书发送图片消息异常 tenant_id=%d: %s", tenant_id, e, exc_info=True)
        return False


async def send_image_bytes(
    tenant_id: int,
    receive_id: str,
    image_bytes: bytes,
    receive_id_type: str = "open_id",
) -> bool:
    """一次性上传并发送图片消息（封装 upload_image + send_image_message）。

    Returns:
        True 表示发送成功
    """
    image_key = await upload_image(tenant_id, image_bytes)
    if not image_key:
        return False
    return await send_image_message(tenant_id, receive_id, image_key, receive_id_type)


# ============================================================
# 事件回调签名校验
# ============================================================
def verify_event_signature(
    verification_token: str,
    body: dict,
    headers: dict,
) -> bool:
    """校验飞书事件回调请求是否合法。

    飞书事件订阅 v1 校验方式：
    - 比对请求体中的 token 字段是否等于 verification_token
    - （可选）若配置了 encrypt_key，需先解密 encrypt 字段

    Args:
        verification_token: 飞书开放平台配置的 Verification Token
        body: 请求体解析后的 dict
        headers: HTTP 头

    Returns:
        True 表示校验通过
    """
    if not verification_token:
        return False
    body_token = body.get("header", {}).get("token") or body.get("token")
    return body_token == verification_token


def decrypt_encrypted_event(encrypt_key: str, encrypted: str) -> dict:
    """解密飞书加密的事件回调 payload。

    飞书加密方式：AES-256-CBC
    - key = SHA256(encrypt_key)
    - iv = encrypted 前 16 字节
    - ciphertext = encrypted 第 16 字节之后
    - 解密后是 JSON 字符串

    Args:
        encrypt_key: 飞书开放平台配置的 Encrypt Key
        encrypted: encrypt 字段的值（base64 编码）

    Returns:
        解密后的 dict
    """
    if not encrypt_key:
        return {}
    key = hashlib.sha256(encrypt_key.encode("utf-8")).digest()
    data = base64.b64decode(encrypted)
    iv = data[:16]
    ciphertext = data[16:]
    # 使用 cryptography 库解密 AES-256-CBC
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    plain_padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    plain = unpadder.update(plain_padded) + unpadder.finalize()
    return json.loads(plain.decode("utf-8"))


# ============================================================
# 接收事件解析
# ============================================================
def parse_message_event(body: dict) -> Optional[dict]:
    """解析飞书消息接收事件 v2.0，提取关键字段。

    事件 schema 见 https://open.feishu.cn/document/event-docs/event-im-message-receive-v1

    Returns:
        {
            "sender_open_id": str,    # 发送者 open_id
            "sender_user_id": str,    # 发送者 user_id
            "sender_name": str,       # 发送者昵称
            "chat_id": str,           # 会话 ID（用户/群聊）
            "message_id": str,        # 消息 ID
            "message_type": str,      # text/image/...
            "content": str,           # 消息内容（已解码）
            "create_time": int,       # 消息时间戳（秒）
            "chat_type": str,         # p2p / group
            "raw": dict,              # 原始事件
        }
        None 表示非消息事件或解析失败
    """
    try:
        header = body.get("header", {})
        event_type = header.get("event_type")
        if event_type != "im.message.receive_v1":
            return None
        event = body.get("event", {})
        sender = event.get("sender", {})
        sender_id = sender.get("sender_id", {})
        message = event.get("message", {})
        message_content = message.get("content", "{}")
        try:
            content_obj = json.loads(message_content) if isinstance(message_content, str) else message_content
        except Exception:
            content_obj = {"text": str(message_content)}
        return {
            "sender_open_id": sender_id.get("open_id", ""),
            "sender_user_id": sender_id.get("user_id", ""),
            "sender_name": sender.get("name", "") or sender_id.get("name", ""),
            "chat_id": message.get("chat_id", ""),
            "message_id": message.get("message_id", ""),
            "message_type": message.get("message_type", ""),
            "content": content_obj.get("text", "") if isinstance(content_obj, dict) else str(content_obj),
            "create_time": int(message.get("create_time") or 0),
            "chat_type": message.get("chat_type", "p2p"),
            "raw": body,
        }
    except Exception as e:
        logger.warning("解析飞书消息事件失败: %s", e, exc_info=True)
        return None


def make_url_verification_response(challenge: str) -> dict:
    """构造飞书 URL 验证响应。

    飞书在配置事件订阅 URL 时会发送 challenge 请求，需原样返回 challenge 字段。
    """
    return {"challenge": challenge}
