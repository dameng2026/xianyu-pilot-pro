"""默认回复 API 类型公共工具

职责：
1. 校验用户填写的 API 地址（仅允许 https 公网，防 SSRF）
2. 调用外部 API（POST），将买家消息内容传给对方
3. 解析返回内容：兼容 JSON（{"reply": "..."} / {"success", "reply"}）与纯文本

实现复用 core/outbound_network.py 的公网地址固定策略（DNS 解析后按 IP 连接、
Host/SNI 保持原域名、连接后校验对端 IP），与图片下载、通知外发保持一致。
"""
from __future__ import annotations

import json
import logging
from typing import Optional

import httpx

from ..core.outbound_network import public_https_outbound_policy, require_expected_httpx_peer

logger = logging.getLogger(__name__)

DEFAULT_API_TIMEOUT = 30
MIN_API_TIMEOUT = 1
MAX_API_TIMEOUT = 60


def normalize_api_timeout(timeout: Optional[int]) -> int:
    """将超时时间归一到合法范围，非法时回退默认值。"""
    if timeout is None:
        return DEFAULT_API_TIMEOUT
    try:
        value = int(timeout)
    except (TypeError, ValueError):
        return DEFAULT_API_TIMEOUT
    if value < MIN_API_TIMEOUT:
        return MIN_API_TIMEOUT
    if value > MAX_API_TIMEOUT:
        return MAX_API_TIMEOUT
    return value


def parse_api_reply(status: int, body_text: str) -> Optional[str]:
    """解析外部 API 的返回内容，提取要发送给买家的文本。"""
    if status != 200:
        logger.warning("默认回复API返回非200状态码: %s", status)
        return None
    if not body_text:
        return None
    text = body_text.strip()
    if not text:
        return None

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        data = None

    if isinstance(data, dict):
        if "success" in data and not data.get("success"):
            logger.warning("默认回复API返回失败标志: %s", data.get("message") or data)
            return None
        for key in ("reply", "data", "content", "message"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    if isinstance(data, str) and data.strip():
        return data.strip()

    return text


async def call_reply_api(
    account_id: int,
    message: str,
    api_url: str,
    timeout: Optional[int] = DEFAULT_API_TIMEOUT,
    chat_id: Optional[str] = None,
    item_id: Optional[str] = None,
    send_user_id: Optional[str] = None,
    send_user_name: Optional[str] = None,
) -> Optional[str]:
    """调用外部 API 获取默认回复内容。

    仅允许 https 公网地址；POST JSON：{"account_id", "message", ...上下文}。
    失败/超时/无有效内容返回 None。
    """
    raw_url = str(api_url or "").strip()
    if not raw_url:
        return None

    try:
        target = await public_https_outbound_policy.pin_public_https(raw_url)
    except Exception as exc:
        logger.warning("默认回复API地址校验失败 accountId=%d errorType=%s", account_id, type(exc).__name__)
        return None

    timeout_seconds = normalize_api_timeout(timeout)
    payload: dict = {"account_id": str(account_id), "message": message}
    if chat_id:
        payload["chat_id"] = chat_id
    if item_id:
        payload["item_id"] = item_id
    if send_user_id:
        payload["send_user_id"] = send_user_id
    if send_user_name:
        payload["send_user_name"] = send_user_name

    try:
        client_timeout = httpx.Timeout(connect=5.0, read=timeout_seconds, write=5.0, pool=5.0)
        limits = httpx.Limits(max_connections=4, max_keepalive_connections=2)
        async with httpx.AsyncClient(
            timeout=client_timeout,
            limits=limits,
            follow_redirects=False,
            trust_env=False,
            headers={"Content-Type": "application/json", "Host": target.host_header},
        ) as client:
            response = await client.post(
                target.request_url,
                json=payload,
                extensions={"sni_hostname": target.sni_hostname},
            )
            require_expected_httpx_peer(response, target.peer_ip)
            if response.status in (301, 302, 303, 307, 308):
                logger.warning(
                    "默认回复API返回重定向(%s)，已拒绝跟随 accountId=%d",
                    response.status,
                    account_id,
                )
                return None
            body_text = await response.aread()
            reply = parse_api_reply(response.status, body_text.decode("utf-8", errors="replace"))
            if reply:
                logger.info("默认回复API调用成功 accountId=%d replyLen=%d", account_id, len(reply))
            else:
                logger.info("默认回复API未返回有效内容 accountId=%d", account_id)
            return reply
    except httpx.HTTPError as exc:
        logger.warning("默认回复API网络请求失败 accountId=%d errorType=%s", account_id, type(exc).__name__)
        return None
    except Exception as exc:
        logger.warning("默认回复API调用异常 accountId=%d errorType=%s", account_id, type(exc).__name__)
        return None
