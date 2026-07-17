"""
通知分发器：负责在事件触发时向用户配置的外部渠道推送消息。

支持的渠道：
- webhook     通用 Webhook（自定义 JSON）
- feishu      飞书自定义机器人（msg_type:text，可选签名校验）
- dingtalk    钉钉自定义机器人（msgtype:text，可选加签）
- wechat_work 企业微信群机器人（msgtype:text）
- pushplus    PushPlus（向 pushplus.plus/send 发 token+title+content）
- email       邮箱 SMTP（向收件人发送邮件）

设计要点：
- 直接在 Python 端发送 HTTP/SMTP，低延迟、无需跨服务调用。
- 读取 user_notification_setting.config_json，按渠道类型格式化消息体。
- 发送结果写入 notification_delivery_log 表，便于审计与排错。
- 所有异常被捕获并记录日志，绝不影响主业务流程。
"""
import base64
import asyncio
import hashlib
import hmac
import json
import logging
import smtplib
import ssl
import time
import urllib.parse
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate
from typing import Optional

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import async_session
from ..core.cookie_crypto import decrypt_cookie_if_needed
from ..core.outbound_network import (
    PinnedHttpsTarget,
    notification_outbound_policy,
    require_expected_httpx_peer,
    require_public_socket_peer,
)
from .ws_delivery_handler import extract_goods_id_from_url, extract_order_id_from_url

logger = logging.getLogger(__name__)


# ============================================================
# 事件显示名常量（与前端 NotifySettings.vue 的 events 列表保持一致）
# ============================================================
EVENT_COOKIE_EXPIRED = "Cookie 到期"
EVENT_NEW_ORDER = "新订单提醒"
EVENT_AUTO_DELIVERY_SUCCESS = "自动发货成功"
EVENT_AUTO_DELIVERY_FAILURE = "自动发货失败"
EVENT_ACCOUNT_OFFLINE = "账号掉线"
EVENT_CAPTCHA_REQUIRED = "人机验证"
EVENT_CAPTCHA_SUCCESS = "人机验证成功"
EVENT_TOKEN_LOW_BALANCE = "Token 余额预警"
EVENT_AUTO_REPLY_PAUSED = "自动回复暂停"

# 用户级通知使用 account_id=0 作为占位符，与账号级通知区分
USER_LEVEL_ACCOUNT_PLACEHOLDER = 0


# ============================================================
# 账号状态通知统一去重机制（内存 + 数据库双层）
# ------------------------------------------------------------
# 设计原则：每条账号状态类通知（Cookie 到期 / 账号掉线 / 人机验证）
# 在账号状态恢复前只发送一次，避免断线重连循环或周期性保活任务
# 每隔几分钟触发一次重复通知刷屏。
#
# 双层去重：
#   1. 内存层（_ACCOUNT_STATUS_NOTIFIED）：快速路径，避免每次都查 DB
#   2. 数据库层（notification_dedup 表）：持久化，进程重启后仍生效
#
# 检查流程：内存命中 → 跳过；内存未命中 → 查 DB → DB 命中则回填内存并跳过
# 标记流程：发送通知后同时写入内存和 DB
# 清除流程：账号恢复时同时清除内存和 DB 中该账号的所有去重记录
# ============================================================
_ACCOUNT_STATUS_NOTIFIED: dict[tuple[int, int, str], float] = {}
_NEW_ORDER_NOTIFIED_TTL_SECONDS = 15 * 60
_NEW_ORDER_NOTIFIED: dict[tuple[int, int, str], float] = {}

# M3: 跨协程共享状态 lazy-initialized asyncio.Lock，避免模块加载时要求事件循环
_account_status_notified_lock = None
_new_order_notified_lock = None


def _get_account_status_notified_lock() -> asyncio.Lock:
    """lazy 初始化 _ACCOUNT_STATUS_NOTIFIED 的 asyncio.Lock。"""
    global _account_status_notified_lock
    if _account_status_notified_lock is None:
        _account_status_notified_lock = asyncio.Lock()
    return _account_status_notified_lock


def _get_new_order_notified_lock() -> asyncio.Lock:
    """lazy 初始化 _NEW_ORDER_NOTIFIED 的 asyncio.Lock。"""
    global _new_order_notified_lock
    if _new_order_notified_lock is None:
        _new_order_notified_lock = asyncio.Lock()
    return _new_order_notified_lock


async def _check_account_status_notified(tenant_id: int, account_id: int, event_display_name: str) -> bool:
    """检查该账号的指定事件是否已经发送过通知（内存 + 数据库双层检查）。

    内存未命中时回查数据库，DB 命中则回填内存缓存。
    """
    # 第一层：内存快速路径
    async with _get_account_status_notified_lock():
        if (tenant_id, account_id, event_display_name) in _ACCOUNT_STATUS_NOTIFIED:
            return True

    # 第二层：数据库持久化检查（进程重启后内存丢失，DB 仍保留记录）
    try:
        async with async_session() as db:
            row = (await db.execute(
                text(
                    "SELECT 1 FROM notification_dedup "
                    "WHERE tenant_id = :tid AND account_id = :aid AND event_type = :evt "
                    "LIMIT 1"
                ),
                {"tid": tenant_id, "aid": account_id, "evt": event_display_name},
            )).first()
            if row:
                # 回填内存缓存，后续直接走快速路径
                async with _get_account_status_notified_lock():
                    _ACCOUNT_STATUS_NOTIFIED[(tenant_id, account_id, event_display_name)] = time.time()
                return True
    except Exception:
        logger.debug("查询 notification_dedup 失败，仅依赖内存去重", exc_info=True)

    return False


async def _mark_account_status_notified(tenant_id: int, account_id: int, event_display_name: str) -> None:
    """标记该账号的指定事件已发送通知（同时写入内存和数据库）。"""
    # 内存层
    async with _get_account_status_notified_lock():
        _ACCOUNT_STATUS_NOTIFIED[(tenant_id, account_id, event_display_name)] = time.time()

    # 数据库层（INSERT ... ON DUPLICATE KEY UPDATE 保证幂等）
    try:
        async with async_session() as db:
            await db.execute(
                text(
                    "INSERT INTO notification_dedup (tenant_id, account_id, event_type, last_sent_time) "
                    "VALUES (:tid, :aid, :evt, NOW()) "
                    "ON DUPLICATE KEY UPDATE last_sent_time = NOW()"
                ),
                {"tid": tenant_id, "aid": account_id, "evt": event_display_name},
            )
            await db.commit()
    except Exception:
        logger.debug("写入 notification_dedup 失败，仅依赖内存去重", exc_info=True)


async def clear_all_account_status_notifications(tenant_id: int, account_id: int) -> None:
    """清除指定账号所有状态通知的去重标记（内存 + 数据库）。

    在账号状态恢复时调用（如 cookie_status 重置为 1、WS 重连成功、
    用户手动更新 Cookie、扫码登录成功等），以便下次再次失效时能重新发送通知。
    """
    # 清除内存层
    try:
        async with _get_account_status_notified_lock():
            keys_to_remove = [
                k for k in _ACCOUNT_STATUS_NOTIFIED
                if k[0] == tenant_id and k[1] == account_id
            ]
            for k in keys_to_remove:
                _ACCOUNT_STATUS_NOTIFIED.pop(k, None)
    except Exception:
        logger.debug("清除内存去重标记异常，忽略", exc_info=True)

    # 清除数据库层
    try:
        async with async_session() as db:
            await db.execute(
                text(
                    "DELETE FROM notification_dedup "
                    "WHERE tenant_id = :tid AND account_id = :aid"
                ),
                {"tid": tenant_id, "aid": account_id},
            )
            await db.commit()
    except Exception:
        logger.debug("清除 notification_dedup 失败，仅清除内存", exc_info=True)


def _purge_expired_new_order_notifications(now: Optional[float] = None) -> None:
    # TODO: 跨协程共享状态，sync 访问点未加锁（_NEW_ORDER_NOTIFIED）
    # 此 sync 函数被 async notify_new_order 调用；异步侧的 check-and-set 已加锁。
    now_ts = now if now is not None else time.time()
    expired_keys = [
        dedup_key
        for dedup_key, ts in _NEW_ORDER_NOTIFIED.items()
        if now_ts - ts >= _NEW_ORDER_NOTIFIED_TTL_SECONDS
    ]
    for dedup_key in expired_keys:
        _NEW_ORDER_NOTIFIED.pop(dedup_key, None)


def _build_new_order_dedup_token(account_id: int, msg: dict) -> Optional[str]:
    reminder_url = str(msg.get("reminderUrl") or msg.get("reminder_url") or "")
    order_id = extract_order_id_from_url(reminder_url) or ""
    goods_id = str(msg.get("xyGoodsId") or extract_goods_id_from_url(reminder_url) or "").strip()
    buyer = str(msg.get("senderUserId") or msg.get("buyerUserId") or "").strip()
    sid = str(msg.get("sId") or msg.get("sid") or "").strip()
    pnm_id = str(msg.get("pnmId") or msg.get("pnm_id") or "").strip()
    reminder = str(msg.get("reminderContent") or msg.get("reminder_content") or "").strip()

    parts = [str(account_id)]
    if order_id:
        parts.append(f"order:{order_id}")
    else:
        for label, value in (("goods", goods_id), ("buyer", buyer), ("sid", sid), ("pnm", pnm_id), ("reminder", reminder)):
            if value:
                parts.append(f"{label}:{value}")

    if len(parts) == 1:
        return None
    return "|".join(parts)


def clear_new_order_state(tenant_id: int, account_id: int, msg: Optional[dict] = None) -> None:
    """清除新订单通知去重状态，通常仅用于测试或需要强制重新通知的场景。"""
    # TODO: 跨协程共享状态，sync 访问点未加锁（_NEW_ORDER_NOTIFIED）
    # 此 sync 函数主要用于测试场景；异步侧的 check-and-set 已加锁。
    try:
        if msg is not None:
            token = _build_new_order_dedup_token(account_id, msg)
            if token:
                _NEW_ORDER_NOTIFIED.pop((tenant_id, account_id, token), None)
            return

        prefix = (tenant_id, account_id)
        expired_keys = [key for key in _NEW_ORDER_NOTIFIED if key[:2] == prefix]
        for key in expired_keys:
            _NEW_ORDER_NOTIFIED.pop(key, None)
    except Exception:
        logger.debug("clear_new_order_state 异常，忽略", exc_info=True)


async def _lookup_account_name(tenant_id: int, account_id: int) -> str:
    """查询账号昵称，找不到时回退为账号ID字符串。"""
    try:
        async with async_session() as db:
            row = (await db.execute(
                text(
                    "SELECT nickname FROM xianyu_account "
                    "WHERE id = :aid AND tenant_id = :tid AND deleted = 0 LIMIT 1"
                ),
                {"aid": account_id, "tid": tenant_id},
            )).mappings().first()
            if row and row.get("nickname"):
                return str(row["nickname"])
    except Exception:
        logger.debug("查询账号昵称失败，回退为账号ID", exc_info=True)
    return str(account_id)


# ============================================================
# 内部工具函数
# ============================================================

def _render_template(template: str, title: str, content: str) -> str:
    """渲染消息模板，支持 {title}、{content}、{time} 变量。"""
    if not template:
        template = "{title}\n{content}"
    return (
        template
        .replace("{title}", title or "")
        .replace("{content}", content or "")
        .replace("{time}", time.strftime("%Y-%m-%d %H:%M:%S"))
    )


def _gen_feishu_sign(timestamp: int, secret: str) -> str:
    """飞书自定义机器人签名：HMAC-SHA256(key=timestamp\nsecret, msg=空) → base64。"""
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    return base64.b64encode(hmac_code).decode("utf-8")


def _gen_dingtalk_sign(timestamp: int, secret: str) -> str:
    """钉钉加签：HMAC-SHA256(key=secret, msg=timestamp\nsecret) → base64 → URLEncode。"""
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return urllib.parse.quote_plus(base64.b64encode(hmac_code).decode("utf-8"))


def _is_channel_ready(channel: dict) -> bool:
    """渠道是否已启用且必要字段已配置。"""
    if not channel or not channel.get("enabled"):
        return False
    ctype = str(channel.get("type") or "")
    if ctype in ("webhook", "feishu", "dingtalk", "wechat_work"):
        return bool(str(channel.get("webhookUrl") or "").strip())
    if ctype == "pushplus":
        return bool(str(channel.get("receiver") or "").strip())
    if ctype == "email":
        return all(str(channel.get(k) or "").strip() for k in ("smtpHost", "smtpUser", "smtpPass", "receiver"))
    return False


def _select_target_channels(channels: list, send_mode: str) -> list:
    """根据发送模式筛选目标渠道列表。

    - single 模式：仅发送给第一个可用渠道。
    - multi 模式：发送给所有可用渠道。
    """
    if not isinstance(channels, list):
        return []
    ready = [c for c in channels if _is_channel_ready(c)]
    if not ready:
        return []
    if send_mode == "single":
        return [ready[0]]
    return ready


def _is_event_enabled(events: list, event_display_name: str) -> bool:
    """检查指定事件是否启用。配置中找不到时默认启用。"""
    if not isinstance(events, list):
        return True
    for e in events:
        if e and e.get("event") == event_display_name:
            return bool(e.get("enabled", True))
    return True


async def _load_notify_config(db: AsyncSession, tenant_id: int) -> Optional[dict]:
    """读取租户的通知配置。返回 {channels, events, sendMode, user_id} 或 None。"""
    row = (await db.execute(
        text(
            "SELECT user_id, config_json FROM user_notification_setting "
            "WHERE tenant_id = :tid AND deleted = 0 "
            "ORDER BY updated_time DESC LIMIT 1"
        ),
        {"tid": tenant_id},
    )).mappings().first()
    if not row:
        return None
    try:
        config = json.loads(row["config_json"]) if isinstance(row["config_json"], str) else row["config_json"]
    except Exception:
        return None
    if not isinstance(config, dict):
        return None
    channels = config.get("channels") or []
    decrypted_channels = []
    for channel in channels if isinstance(channels, list) else []:
        if not isinstance(channel, dict):
            continue
        safe_channel = dict(channel)
        secret_fields = ["secret", "smtpPass", "verificationToken", "encryptKey"]
        if str(safe_channel.get("type") or "").lower() == "pushplus":
            secret_fields.append("receiver")
        for field in secret_fields:
            stored = safe_channel.get(field)
            if stored:
                safe_channel[field] = decrypt_cookie_if_needed(str(stored)) or ""
        decrypted_channels.append(safe_channel)
    return {
        "user_id": row["user_id"],
        "channels": decrypted_channels,
        "events": config.get("events") or [],
        "sendMode": config.get("sendMode") or "single",
    }


async def _insert_delivery_log(
    db: AsyncSession,
    tenant_id: int,
    user_id: Optional[int],
    channel_key: str,
    channel_name: str,
    event_type: str,
    success: bool,
    status_code: Optional[int],
    cost_ms: int,
    message: str,
    request_body: str,
    response_body: str,
) -> None:
    """写入通知投递日志。失败时仅记录调试日志，不影响主流程。"""
    try:
        await db.execute(
            text(
                """
                INSERT INTO notification_delivery_log(
                    tenant_id, user_id, channel_key, channel_name, event_type,
                    success, status_code, cost_ms, message, request_body, response_body,
                    retry_count, created_time
                ) VALUES(
                    :tenant_id, :user_id, :channel_key, :channel_name, :event_type,
                    :success, :status_code, :cost_ms, :message, :request_body, :response_body,
                    0, NOW()
                )
                """
            ),
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "channel_key": channel_key,
                "channel_name": channel_name,
                "event_type": event_type,
                "success": 1 if success else 0,
                "status_code": status_code,
                "cost_ms": cost_ms,
                "message": (message or "")[:500],
                "request_body": "",
                "response_body": "",
            },
        )
        await db.commit()
    except Exception:
        logger.debug("写入 notification_delivery_log 失败，忽略", exc_info=True)


# ============================================================
# 各渠道发送实现：统一返回 dict {success, status_code, cost_ms, message, request_body, response_body}
# ============================================================

async def _insert_in_app_notification(
    db: AsyncSession,
    tenant_id: int,
    account_id: Optional[int],
    event_type: str,
    title: str,
    content: str,
    level: str = "warning",
    priority: int = 2,
    user_id: Optional[int] = None,
) -> None:
    """向 notification 表写入站内提醒，便于前端在账号页直接展示。

    user_id 用于用户级通知（如 Token 余额预警、自动回复暂停）；
    若不传则保持历史行为（user_id 为 NULL）。
    """
    try:
        await db.execute(
            text(
                """
                INSERT INTO notification(
                    tenant_id, user_id, account_id, notice_type, notification_type,
                    title, content, level, priority, is_read, created_time, updated_time, deleted
                ) VALUES(
                    :tenant_id, :user_id, :account_id, :event_type, :event_type,
                    :title, :content, :level, :priority, 0, NOW(), NOW(), 0
                )
                """
            ),
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "account_id": account_id,
                "event_type": event_type,
                "title": (title or "")[:200],
                "content": content or "",
                "level": level or "warning",
                "priority": priority,
            },
        )
        await db.commit()
    except Exception:
        logger.debug("写入 notification 失败，忽略", exc_info=True)


async def _send_webhook(channel: dict, title: str, rendered: str, timeout_seconds: int) -> dict:
    url = str(channel.get("webhookUrl") or "").strip()
    method = str(channel.get("method") or "POST").upper()
    body = json.dumps(
        {"title": title, "content": rendered, "channel": channel.get("key"), "time": time.strftime("%Y-%m-%d %H:%M:%S")},
        ensure_ascii=False,
    )
    started = time.time()
    try:
        target = await notification_outbound_policy.pin_webhook("webhook", url)
        status_code, _response_text = await _bounded_http_request(
            "GET" if method == "GET" else "POST",
            target,
            None if method == "GET" else body,
            timeout_seconds,
        )
        cost_ms = int((time.time() - started) * 1000)
        success = 200 <= status_code < 300
        return {
            "success": success, "status_code": status_code, "cost_ms": cost_ms,
            "message": "Webhook 发送成功" if success else f"Webhook 返回 HTTP {status_code}",
            "request_body": "", "response_body": "",
        }
    except Exception as e:
        logger.warning("webhook delivery failed errorType=%s", type(e).__name__)
        return _err_result(int((time.time() - started) * 1000))


async def _send_feishu(channel: dict, rendered: str, timeout_seconds: int) -> dict:
    url = str(channel.get("webhookUrl") or "").strip()
    secret = str(channel.get("secret") or "").strip()
    body = json.dumps({"msg_type": "text", "content": {"text": rendered}}, ensure_ascii=False)
    if secret:
        ts = int(time.time())
        sign = _gen_feishu_sign(ts, secret)
        url = f"{url}{'&' if '?' in url else '?'}timestamp={ts}&sign={sign}"
    return await _http_post("feishu", url, body, timeout_seconds, parse_key="code", parse_success=0,
                            ok_msg="飞书发送成功", fail_prefix="飞书发送失败")


async def _send_dingtalk(channel: dict, rendered: str, timeout_seconds: int) -> dict:
    url = str(channel.get("webhookUrl") or "").strip()
    secret = str(channel.get("secret") or "").strip()
    body = json.dumps({"msgtype": "text", "text": {"content": rendered}}, ensure_ascii=False)
    if secret.startswith("SEC"):
        ts = int(time.time() * 1000)
        sign = _gen_dingtalk_sign(ts, secret)
        url = f"{url}{'&' if '?' in url else '?'}timestamp={ts}&sign={sign}"
    return await _http_post("dingtalk", url, body, timeout_seconds, parse_key="errcode", parse_success=0,
                            ok_msg="钉钉发送成功", fail_prefix="钉钉发送失败")


async def _send_wechat_work(channel: dict, rendered: str, timeout_seconds: int) -> dict:
    url = str(channel.get("webhookUrl") or "").strip()
    body = json.dumps({"msgtype": "text", "text": {"content": rendered}}, ensure_ascii=False)
    return await _http_post("wechat_work", url, body, timeout_seconds, parse_key="errcode", parse_success=0,
                            ok_msg="企业微信发送成功", fail_prefix="企业微信发送失败")


async def _send_pushplus(channel: dict, title: str, rendered: str, timeout_seconds: int) -> dict:
    token = str(channel.get("receiver") or "").strip()
    body = json.dumps({"token": token, "title": title, "content": rendered, "template": "txt"}, ensure_ascii=False)
    return await _http_post("pushplus", "https://www.pushplus.plus/send", body, timeout_seconds,
                            parse_key="code", parse_success=200,
                            ok_msg="PushPlus 发送成功", fail_prefix="PushPlus 发送失败")


async def _send_email(channel: dict, title: str, rendered: str, timeout_seconds: int) -> dict:
    smtp_host = str(channel.get("smtpHost") or "").strip()
    smtp_port = int(channel.get("smtpPort") or 465)
    smtp_user = str(channel.get("smtpUser") or "").strip()
    smtp_pass = str(channel.get("smtpPass") or "").strip()
    from_email = str(channel.get("fromEmail") or "").strip() or smtp_user
    to_email = str(channel.get("receiver") or "").strip()
    body_log = f"to={to_email}&subject={title}&body={rendered}"
    started = time.time()
    try:
        smtp_host, smtp_port = await notification_outbound_policy.validate_smtp(smtp_host, smtp_port)
        msg = MIMEText(rendered, "plain", "utf-8")
        msg["Subject"] = title
        msg["From"] = formataddr(("闲鱼助手", from_email))
        msg["To"] = to_email
        msg["Date"] = formatdate(localtime=True)

        await asyncio.to_thread(
            _send_smtp_sync,
            smtp_host,
            smtp_port,
            smtp_user,
            smtp_pass,
            from_email,
            to_email,
            msg.as_string(),
            min(max(timeout_seconds, 3), 15),
        )
        cost_ms = int((time.time() - started) * 1000)
        return {
            "success": True, "status_code": 250, "cost_ms": cost_ms,
            "message": "邮箱发送成功", "request_body": "", "response_body": "",
        }
    except Exception as e:
        logger.warning("SMTP delivery failed errorType=%s", type(e).__name__)
        return _err_result(int((time.time() - started) * 1000))


async def _bounded_http_request(
    method: str,
    target: PinnedHttpsTarget,
    body: str | None,
    timeout_seconds: int,
) -> tuple[int, str]:
    timeout = min(max(int(timeout_seconds or 10), 1), 15)
    headers = {"Host": target.host_header}
    if body is not None:
        headers["Content-Type"] = "application/json"
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        async with client.stream(
            method,
            target.request_url,
            content=body,
            headers=headers,
            extensions={"sni_hostname": target.sni_hostname},
        ) as response:
            require_expected_httpx_peer(response, target.peer_ip)
            payload = bytearray()
            async for chunk in response.aiter_bytes():
                payload.extend(chunk)
                if len(payload) > 65_536:
                    raise ValueError("notification provider response is too large")
            return response.status_code, payload.decode("utf-8", errors="replace")


def _send_smtp_sync(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_pass: str,
    from_email: str,
    to_email: str,
    message: str,
    timeout_seconds: int,
) -> None:
    if smtp_port == 465:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=timeout_seconds, context=ctx) as smtp:
            require_public_socket_peer(smtp.sock)
            smtp.login(smtp_user, smtp_pass)
            smtp.sendmail(from_email, [to_email], message)
    else:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=timeout_seconds) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            require_public_socket_peer(smtp.sock)
            smtp.login(smtp_user, smtp_pass)
            smtp.sendmail(from_email, [to_email], message)


async def _http_post(channel_type: str, url: str, body: str, timeout_seconds: int,
                     parse_key: str, parse_success: int,
                     ok_msg: str, fail_prefix: str) -> dict:
    """通用 POST 发送 + 响应解析。parse_key 为响应 JSON 中标识成功的字段名。"""
    started = time.time()
    try:
        target = await notification_outbound_policy.pin_webhook(channel_type, url)
        status_code, resp_text = await _bounded_http_request("POST", target, body, timeout_seconds)
        cost_ms = int((time.time() - started) * 1000)
        success = 200 <= status_code < 300
        if success and resp_text:
            try:
                resp_json = json.loads(resp_text)
                code = resp_json.get(parse_key)
                if code is not None:
                    success = (str(code) == str(parse_success))
                if not success:
                    return {
                        "success": False, "status_code": status_code, "cost_ms": cost_ms,
                        "message": f"{fail_prefix}: HTTP {status_code}"[:500],
                        "request_body": "", "response_body": "",
                    }
            except Exception as parse_err:
                logger.debug("通知响应体非 JSON，按 HTTP 状态码判定成功 errorType=%s", type(parse_err).__name__)
        return {
            "success": success, "status_code": status_code, "cost_ms": cost_ms,
            "message": ok_msg if success else f"{fail_prefix}: HTTP {status_code}",
            "request_body": "", "response_body": "",
        }
    except Exception as e:
        logger.warning("notification provider delivery failed channelType=%s errorType=%s", channel_type, type(e).__name__)
        return _err_result(int((time.time() - started) * 1000))


def _err_result(cost_ms: int) -> dict:
    return {
        "success": False, "status_code": None, "cost_ms": cost_ms,
        "message": "通知发送失败，请检查通道配置", "request_body": "", "response_body": "",
    }


# ============================================================
# 对外核心 API
# ============================================================

async def dispatch_notification(
    tenant_id: int,
    event_display_name: str,
    title: str,
    content: str,
) -> bool:
    """向租户已配置的通知渠道推送一条消息。

    本函数自管理 DB session 与异常，调用方无需 try/except，直接 await 即可。
    若租户未配置通知、事件未启用、或无可用渠道，则静默跳过。
    """
    if not tenant_id:
        return False
    try:
        async with async_session() as db:
            config = await _load_notify_config(db, tenant_id)
            if not config:
                return False
            if not _is_event_enabled(config["events"], event_display_name):
                return False
            targets = _select_target_channels(config["channels"], config["sendMode"])
            if not targets:
                return False
            user_id = config.get("user_id")
            delivered = False
            for channel in targets:
                ctype = str(channel.get("type") or "webhook")
                rendered = _render_template(channel.get("template"), title, content)
                timeout_seconds = int(channel.get("timeoutSeconds") or 10)
                if ctype == "feishu":
                    result = await _send_feishu(channel, rendered, timeout_seconds)
                elif ctype == "dingtalk":
                    result = await _send_dingtalk(channel, rendered, timeout_seconds)
                elif ctype == "wechat_work":
                    result = await _send_wechat_work(channel, rendered, timeout_seconds)
                elif ctype == "pushplus":
                    result = await _send_pushplus(channel, title, rendered, timeout_seconds)
                elif ctype == "email":
                    result = await _send_email(channel, title, rendered, timeout_seconds)
                else:
                    result = await _send_webhook(channel, title, rendered, timeout_seconds)

                await _insert_delivery_log(
                    db, tenant_id, user_id,
                    channel_key=str(channel.get("key") or ctype),
                    channel_name=str(channel.get("name") or ctype),
                    event_type=event_display_name,
                    success=result["success"],
                    status_code=result["status_code"],
                    cost_ms=result["cost_ms"],
                    message=result["message"],
                    request_body=result["request_body"],
                    response_body=result["response_body"],
                )
                if result["success"]:
                    logger.info(
                        "通知发送成功: tenant=%d event=%s channel=%s type=%s",
                        tenant_id, event_display_name, channel.get("name"), ctype
                    )
                else:
                    logger.warning(
                        "通知发送失败: tenant=%d event=%s type=%s status=%s msg=%s",
                        tenant_id, event_display_name, ctype, result["status_code"], result["message"]
                    )
                delivered = delivered or bool(result["success"])
            return delivered
    except Exception:
        logger.warning("dispatch_notification 异常，忽略: event=%s", event_display_name, exc_info=True)
        return False


# ============================================================
# 高层便捷 API —— 供事件触发点调用
# ============================================================

async def notify_cookie_expired(tenant_id: int, account_id: int, cookie_status: int) -> None:
    """Cookie 失效通知。在 ws_client._update_cookie_status 中调用。

    去重策略：同一账号在 cookie_status 恢复为有效前只发送一次通知，
    避免断线重连循环每 ~5 秒触发一次重复通知。
    需在 cookie_status 重置为 1 时调用 clear_all_account_status_notifications 清除标记。
    """
    if await _check_account_status_notified(tenant_id, account_id, EVENT_COOKIE_EXPIRED):
        logger.info(
            "Cookie 失效通知去重跳过: tenant=%d account=%d（已通知过，等待 cookie 恢复后清除）",
            tenant_id, account_id,
        )
        return

    status_text = "已失效" if cookie_status == 0 else f"状态变更({cookie_status})"
    account_name = await _lookup_account_name(tenant_id, account_id)
    content = (
        f"账号名称：{account_name}\n"
        f"状态：{status_text}\n"
        f"时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"请及时更新该账号的 Cookie。"
    )
    await dispatch_notification(
        tenant_id=tenant_id,
        event_display_name=EVENT_COOKIE_EXPIRED,
        title="⚠️ Cookie 失效告警",
        content=content,
    )
    # 标记已通知（内存 + DB），防止重连循环重复发送
    await _mark_account_status_notified(tenant_id, account_id, EVENT_COOKIE_EXPIRED)


async def notify_new_order(tenant_id: int, account_id: int, msg: dict) -> None:
    """新订单提醒。在 ws_delivery_handler 检测到付款消息时调用。"""
    _purge_expired_new_order_notifications()
    token = _build_new_order_dedup_token(account_id, msg)
    dedup_key = None
    if token:
        dedup_key = (tenant_id, account_id, token)
        # 原子 check-and-set：防止并发任务双写去重表
        async with _get_new_order_notified_lock():
            if dedup_key in _NEW_ORDER_NOTIFIED:
                logger.info(
                    "新订单通知去重跳过: tenant=%d account=%d token=%s",
                    tenant_id,
                    account_id,
                    token,
                )
                return
            _NEW_ORDER_NOTIFIED[dedup_key] = time.time()

    reminder = str(msg.get("reminderContent") or msg.get("reminder_content") or "")
    reminder_url = str(msg.get("reminderUrl") or msg.get("reminder_url") or "")
    goods_id = str(msg.get("xyGoodsId") or "")
    buyer = str(msg.get("senderUserName") or "")
    order_id = extract_order_id_from_url(reminder_url) or ""
    content = (
        f"账号ID：{account_id}\n"
        f"商品ID：{goods_id or '未知'}\n"
        f"订单号：{order_id or '未知'}\n"
        f"买家：{buyer or '未知'}\n"
        f"提醒：{reminder or '有新订单需处理'}\n"
        f"时间：{time.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    try:
        delivered = await dispatch_notification(
            tenant_id=tenant_id,
            event_display_name=EVENT_NEW_ORDER,
            title="🛒 新订单提醒",
            content=content,
        )
    except Exception:
        if dedup_key:
            async with _get_new_order_notified_lock():
                _NEW_ORDER_NOTIFIED.pop(dedup_key, None)
        raise
    if dedup_key and not delivered:
        async with _get_new_order_notified_lock():
            _NEW_ORDER_NOTIFIED.pop(dedup_key, None)


async def notify_account_offline(tenant_id: int, account_id: int, reason: str = "") -> None:
    """账号掉线通知。

    去重策略：同一账号在状态恢复前只发送一次通知，
    避免 WS 断线重连循环每隔几分钟触发一次重复通知刷屏。
    需在账号恢复（WS 重连成功 / cookie_status 重置为 1）时调用
    clear_all_account_status_notifications 清除标记。
    """
    if await _check_account_status_notified(tenant_id, account_id, EVENT_ACCOUNT_OFFLINE):
        logger.info(
            "账号掉线通知去重跳过: tenant=%d account=%d（已通知过，等待账号恢复后清除）",
            tenant_id, account_id,
        )
        return

    content = (
        f"账号ID：{account_id}\n"
        f"原因：{reason or '连接断开'}\n"
        f"时间：{time.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    await dispatch_notification(
        tenant_id=tenant_id,
        event_display_name=EVENT_ACCOUNT_OFFLINE,
        title="📡 账号掉线提醒",
        content=content,
    )
    await _mark_account_status_notified(tenant_id, account_id, EVENT_ACCOUNT_OFFLINE)


async def notify_captcha_required(tenant_id: int, account_id: int, scene: str = "") -> None:
    """人机验证提醒。同时写入站内提醒便于前端展示。

    去重策略：同一账号在状态恢复前只发送一次通知，
    避免多个触发点（WS Token 刷新 / Cookie 保活 / 滑块求解器）
    重复发送。需在账号恢复时调用 clear_all_account_status_notifications 清除标记。
    """
    if await _check_account_status_notified(tenant_id, account_id, EVENT_CAPTCHA_REQUIRED):
        logger.info(
            "人机验证通知去重跳过: tenant=%d account=%d（已通知过，等待账号恢复后清除）",
            tenant_id, account_id,
        )
        return

    account_name = await _lookup_account_name(tenant_id, account_id)
    content = (
        f"账号名称：{account_name}\n"
        f"场景：{scene or '触发风控验证'}\n"
        f"时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"请尽快处理，否则可能影响自动化任务。"
    )
    try:
        async with async_session() as db:
            await _insert_in_app_notification(
                db,
                tenant_id=tenant_id,
                account_id=account_id,
                event_type=EVENT_CAPTCHA_REQUIRED,
                title="人机验证提醒",
                content=content,
                level="warning",
                priority=2,
            )
    except Exception:
        logger.debug("写入人机验证站内提醒失败，忽略", exc_info=True)
    await dispatch_notification(
        tenant_id=tenant_id,
        event_display_name=EVENT_CAPTCHA_REQUIRED,
        title="🤖 人机验证提醒",
        content=content,
    )
    await _mark_account_status_notified(tenant_id, account_id, EVENT_CAPTCHA_REQUIRED)



async def notify_auto_delivery(tenant_id: int, account_id: int, success: bool, order_id: str = "", detail: str = "") -> None:
    """自动发货结果通知。success=True 发成功通知，否则发失败通知。"""
    if success:
        event = EVENT_AUTO_DELIVERY_SUCCESS
        title = "✅ 自动发货成功"
    else:
        event = EVENT_AUTO_DELIVERY_FAILURE
        title = "❌ 自动发货失败"
    content = (
        f"账号ID：{account_id}\n"
        f"订单号：{order_id or '未知'}\n"
        f"详情：{detail or ('发货成功' if success else '发货失败')}\n"
        f"时间：{time.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    await dispatch_notification(
        tenant_id=tenant_id,
        event_display_name=event,
        title=title,
        content=content,
    )


async def notify_auto_reply_paused(
    tenant_id: int,
    user_id: int,
    account_id: Optional[int] = None,
    reason: str = "",
) -> None:
    """Token 余额不足导致自动回复暂停通知。

    用户级通知（account_id 用 USER_LEVEL_ACCOUNT_PLACEHOLDER 占位），
    避免对每个账号重复发送。充值后由 clear_token_low_balance_notifications 清除标记。

    触发场景：
    - 在线消息自动回复时 AiBillingPaymentRequired（余额不足）
    - 单次调用通用模型前 ensureAiTokenBalance 校验失败（前端已提示，后端兜底）

    去重策略：同一 tenant_id+user_id 在余额恢复前只发送一次通知。
    """
    dedup_account_id = account_id if account_id is not None else USER_LEVEL_ACCOUNT_PLACEHOLDER
    if await _check_account_status_notified(tenant_id, dedup_account_id, EVENT_AUTO_REPLY_PAUSED):
        logger.info(
            "自动回复暂停通知去重跳过: tenant=%d user=%d（已通知过，等待充值后清除）",
            tenant_id, user_id,
        )
        return

    account_part = ""
    if account_id is not None:
        account_name = await _lookup_account_name(tenant_id, account_id)
        account_part = f"账号名称：{account_name}\n"
    content = (
        f"{account_part}"
        f"原因：{reason or 'AI Token 余额为 0，自动回复已暂停'}\n"
        f"时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"请前往「个人中心 → Token 充值」补充余额后恢复自动回复。"
    )
    try:
        async with async_session() as db:
            await _insert_in_app_notification(
                db,
                tenant_id=tenant_id,
                account_id=dedup_account_id,
                event_type=EVENT_AUTO_REPLY_PAUSED,
                title="AI 自动回复暂停",
                content=content,
                level="warning",
                priority=1,
                user_id=user_id,
            )
    except Exception:
        logger.debug("写入自动回复暂停站内提醒失败，忽略", exc_info=True)
    await dispatch_notification(
        tenant_id=tenant_id,
        event_display_name=EVENT_AUTO_REPLY_PAUSED,
        title="⏸️ AI 自动回复暂停",
        content=content,
    )
    await _mark_account_status_notified(tenant_id, dedup_account_id, EVENT_AUTO_REPLY_PAUSED)


async def notify_token_low_balance(
    tenant_id: int,
    user_id: int,
    balance: int,
    threshold: int = 100,
) -> None:
    """Token 余额低于阈值预警通知。

    用户级通知（account_id=USER_LEVEL_ACCOUNT_PLACEHOLDER）。
    充值后由 clear_token_low_balance_notifications 清除标记。

    触发场景：
    - 定时扫描发现余额 < 阈值（默认 100）
    - 在线消息自动回复扣费后余额跌至阈值以下

    去重策略：同一 tenant_id+user_id 在余额恢复到阈值以上前只发送一次通知。
    """
    if await _check_account_status_notified(tenant_id, USER_LEVEL_ACCOUNT_PLACEHOLDER, EVENT_TOKEN_LOW_BALANCE):
        logger.info(
            "Token 余额预警去重跳过: tenant=%d user=%d（已预警过，等待余额恢复后清除）",
            tenant_id, user_id,
        )
        return

    content = (
        f"当前 Token 余额：{balance}\n"
        f"预警阈值：{threshold}\n"
        f"时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"余额不足将影响 AI 自动回复、AI 润色、AI 客服等功能，请及时充值。"
    )
    try:
        async with async_session() as db:
            await _insert_in_app_notification(
                db,
                tenant_id=tenant_id,
                account_id=USER_LEVEL_ACCOUNT_PLACEHOLDER,
                event_type=EVENT_TOKEN_LOW_BALANCE,
                title="Token 余额预警",
                content=content,
                level="warning",
                priority=1,
                user_id=user_id,
            )
    except Exception:
        logger.debug("写入 Token 余额预警站内提醒失败，忽略", exc_info=True)
    await dispatch_notification(
        tenant_id=tenant_id,
        event_display_name=EVENT_TOKEN_LOW_BALANCE,
        title="💰 Token 余额预警",
        content=content,
    )
    await _mark_account_status_notified(tenant_id, USER_LEVEL_ACCOUNT_PLACEHOLDER, EVENT_TOKEN_LOW_BALANCE)


async def clear_token_low_balance_notifications(tenant_id: int, user_id: int) -> None:
    """清除 Token 余额相关通知的去重标记。

    在用户充值成功、余额恢复到阈值以上时调用，允许下次再次触发预警。
    """
    # 用户级去重使用 account_id=0 占位
    try:
        async with _get_account_status_notified_lock():
            keys_to_remove = [
                k for k in _ACCOUNT_STATUS_NOTIFIED
                if k[0] == tenant_id
                and k[1] == USER_LEVEL_ACCOUNT_PLACEHOLDER
                and k[2] in (EVENT_TOKEN_LOW_BALANCE, EVENT_AUTO_REPLY_PAUSED)
            ]
            for k in keys_to_remove:
                _ACCOUNT_STATUS_NOTIFIED.pop(k, None)
    except Exception:
        logger.debug("清除内存去重标记异常，忽略", exc_info=True)

    try:
        async with async_session() as db:
            await db.execute(
                text(
                    "DELETE FROM notification_dedup "
                    "WHERE tenant_id = :tid AND account_id = :aid "
                    "AND event_type IN (:evt1, :evt2)"
                ),
                {
                    "tid": tenant_id,
                    "aid": USER_LEVEL_ACCOUNT_PLACEHOLDER,
                    "evt1": EVENT_TOKEN_LOW_BALANCE,
                    "evt2": EVENT_AUTO_REPLY_PAUSED,
                },
            )
            await db.commit()
    except Exception:
        logger.debug("清除 notification_dedup 失败，仅清除内存", exc_info=True)
