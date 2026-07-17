"""
飞书对话式 AI 助手
==================

接收飞书用户消息 → AI 意图分析 → 触发对应动作：

支持的意图：
1. **request_qrcode**（请求二维码登录）
   - 用户消息包含"二维码"、"扫码"、"登录"、"过期的 Cookie 怎么办"等
   - 触发：启动 Playwright 拦截官方二维码 → 上传图片 → 发送给用户
   - 用户扫码后调用 qrlogin/solve 端点等待登录成功 → 写入 DB → 自动重连 WS

2. **account_status_query**（账号状态查询）
   - 用户消息包含"账号状态"、"连接情况"、"在线吗"等
   - 触发：查询所有账号 cookie_status / WS 连接状态 → 文本回复

3. **general_chat**（通用闲聊）
   - 兜底意图，AI 自由回复

会话状态管理：
- 每个飞书用户（open_id）一个会话上下文
- 保留最近 10 轮对话历史
- 等待扫码期间标记 "pending_qr_login" 状态，避免重复触发
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx
from sqlalchemy import text

from ..core.database import async_session
from .ai_billing import (
    AiBillingError,
    AiBillingPaymentRequired,
    build_request_id,
    charge_text_usage,
    estimate_text_tokens,
    precheck_ai_usage,
)
from .ai_provider import generate_text
from .feishu_bot import (
    _load_feishu_app_config,
    send_image_bytes,
    send_text_message,
)

logger = logging.getLogger(__name__)


def _error_type(error: BaseException) -> str:
    name = type(error).__name__
    return name if name.replace("_", "").isalnum() else "Exception"


# ============================================================
# 会话状态管理
# ============================================================
@dataclass
class FeishuChatSession:
    """飞书用户会话状态"""
    tenant_id: int
    user_open_id: str
    # 对话历史：[{role: "user"/"assistant", content: str}]
    history: list[dict[str, str]] = field(default_factory=list)
    # 状态：idle / pending_qr_login / pending_account_select
    state: str = "idle"
    # 状态附加数据（如 pending_qr_login 时存储 account_id）
    state_data: dict[str, Any] = field(default_factory=dict)
    # 最后活跃时间戳
    last_active: float = field(default_factory=time.time)


# Feishu open_id values are scoped to an application, so two tenants using
# different self-built applications can legitimately receive the same value.
# The tenant must therefore be part of the cache key; otherwise conversation
# history and pending QR-login state can cross the tenant boundary.
_SESSIONS: dict[tuple[int, str], FeishuChatSession] = {}
# 每 30 分钟清理过期会话（超过 1 小时未活跃）
_SESSION_TTL_SECONDS = 3600
_MAX_SESSIONS = 10_000


def _get_session(tenant_id: int, open_id: str) -> FeishuChatSession:
    """获取或创建飞书用户会话"""
    if tenant_id <= 0 or not str(open_id or "").strip():
        raise ValueError("valid tenant and Feishu user identity are required")
    key = (tenant_id, open_id)
    if key not in _SESSIONS:
        _purge_expired_sessions()
        if len(_SESSIONS) >= _MAX_SESSIONS:
            oldest_key = min(_SESSIONS, key=lambda candidate: _SESSIONS[candidate].last_active)
            _SESSIONS.pop(oldest_key, None)
        _SESSIONS[key] = FeishuChatSession(tenant_id=tenant_id, user_open_id=open_id)
    session = _SESSIONS[key]
    session.last_active = time.time()
    return session


def _purge_expired_sessions() -> None:
    """清理过期会话"""
    now = time.time()
    expired = [k for k, v in _SESSIONS.items() if now - v.last_active > _SESSION_TTL_SECONDS]
    for k in expired:
        _SESSIONS.pop(k, None)


# ============================================================
# AI 意图分析
# ============================================================
INTENT_SYSTEM_PROMPT = """你是闲鱼助手的智能助手，负责分析用户消息的意图并触发对应动作。

支持的意图类型：
1. request_qrcode - 用户请求二维码登录/扫码登录。触发词包括："二维码"、"扫码"、"登录"、"重新登录"、"过期的 Cookie"、"Cookie 过期"、"Session 过期"等。
2. account_status_query - 用户查询账号状态。触发词包括："账号状态"、"连接情况"、"在线吗"、"哪个账号在线"、"账号掉线"等。
3. general_chat - 通用闲聊，与账号/登录无关的对话。

输出格式：仅输出 JSON，不要任何额外文字。
{
  "intent": "request_qrcode | account_status_query | general_chat",
  "confidence": 0.0-1.0,
  "response": "对用户消息的简短回复（用于 general_chat 时直接发送）",
  "account_nickname": "如果用户提到具体账号名称，提取出来；否则为空字符串"
}

示例：
- 用户："我需要二维码登录" → {"intent":"request_qrcode","confidence":0.95,"response":"","account_nickname":""}
- 用户："小龙云设计账号掉线了吗" → {"intent":"account_status_query","confidence":0.9,"response":"","account_nickname":"小龙云设计"}
- 用户："你好" → {"intent":"general_chat","confidence":0.95,"response":"你好！我是闲鱼助手，可以帮你处理账号登录、查询账号状态等。有什么我可以帮你的吗？","account_nickname":""}
"""


async def _analyze_intent(
    tenant_id: int,
    user_id: int,
    message: str,
    history: list[dict[str, str]],
    billing_request_id: str,
) -> dict[str, Any]:
    """调用 AI 模型分析用户消息意图。

    Returns:
        {"intent": str, "confidence": float, "response": str, "account_nickname": str}
    """
    try:
        # 构造历史对话（最近 6 轮）
        recent_history = history[-6:] if len(history) > 6 else history
        messages = [{"role": "system", "content": INTENT_SYSTEM_PROMPT}]
        for h in recent_history:
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": message})

        prompt_for_billing = INTENT_SYSTEM_PROMPT + "\n" + "\n".join(
            f"{item['role']}:{item['content']}" for item in messages
        )
        await precheck_ai_usage({
            "tenantId": tenant_id,
            "userId": user_id,
            "scene": "feishu_chat_intent",
            "providerName": "default",
            "modelName": "default",
            "modelType": "chat",
            "promptTokens": estimate_text_tokens(prompt_for_billing),
            "completionTokens": 0,
            "requestId": billing_request_id,
        })

        result = await generate_text(
            scene="feishu_chat_intent",
            system_prompt=INTENT_SYSTEM_PROMPT,
            user_prompt=message,
            messages=messages,
            temperature=0.3,
            request_id=billing_request_id,
        )
        if not result.get("ok"):
            logger.warning("AI 意图分析失败: %s", result.get("error"))
            return {
                "intent": "general_chat",
                "confidence": 0.0,
                "response": "抱歉，我暂时无法处理你的消息，请稍后再试。",
                "account_nickname": "",
            }
        content = result.get("content", "").strip()
        await charge_text_usage(
            tenant_id=tenant_id,
            user_id=user_id,
            scene="feishu_chat_intent",
            provider_name=str(result.get("provider") or "default"),
            model_name=str(result.get("model") or "default"),
            prompt=prompt_for_billing,
            completion=content,
            request_id=billing_request_id,
            raw_usage=result.get("usage") or {},
        )
        # 尝试解析 JSON
        try:
            data = json.loads(content)
            return {
                "intent": data.get("intent", "general_chat"),
                "confidence": float(data.get("confidence", 0.0)),
                "response": data.get("response", ""),
                "account_nickname": data.get("account_nickname", ""),
            }
        except json.JSONDecodeError:
            # AI 未按格式返回，按 general_chat 处理
            return {
                "intent": "general_chat",
                "confidence": 0.5,
                "response": content or "我理解了你的消息。",
                "account_nickname": "",
            }
    except AiBillingError:
        raise
    except Exception as e:
        logger.error("AI 意图分析异常: %s", e, exc_info=True)
        return {
            "intent": "general_chat",
            "confidence": 0.0,
            "response": "抱歉，处理消息时出现异常。",
            "account_nickname": "",
        }


async def _resolve_feishu_billing_user_id(tenant_id: int) -> int | None:
    try:
        async with async_session() as db:
            value = (await db.execute(
                text(
                    "SELECT user_id FROM user_notification_setting "
                    "WHERE tenant_id=:tenant_id AND deleted=0 AND user_id IS NOT NULL "
                    "ORDER BY updated_time DESC, id DESC LIMIT 1"
                ),
                {"tenant_id": tenant_id},
            )).scalar()
        user_id = int(value or 0)
        return user_id if user_id > 0 else None
    except Exception as exc:
        logger.error("无法解析飞书 AI 计费用户 tenant_id=%d errorType=%s", tenant_id, _error_type(exc))
        return None


# ============================================================
# 业务动作：请求二维码登录
# ============================================================
async def _handle_request_qrcode(
    tenant_id: int,
    session: FeishuChatSession,
    user_open_id: str,
    account_nickname: str = "",
) -> str:
    """处理请求二维码意图：启动 Playwright 拦截二维码并发送给用户。

    Returns:
        给用户的回复文本
    """
    # 去重：正在等待扫码时不重复触发
    if session.state == "pending_qr_login":
        return "上一次的二维码还在等待扫码中，请先用闲鱼 App 扫描之前发送的二维码，或等待 2 分钟超时后再试。"

    # 查找目标账号（如果用户指定了账号名）
    target_account_id: Optional[int] = None
    if account_nickname:
        try:
            async with async_session() as db:
                row = (await db.execute(
                    text(
                        "SELECT a.id FROM xianyu_account a "
                        "WHERE a.tenant_id = :tid AND a.deleted = 0 "
                        "AND a.nickname LIKE :nick LIMIT 1"
                    ),
                    {"tid": tenant_id, "nick": f"%{account_nickname}%"},
                )).mappings().first()
                if row:
                    target_account_id = int(row["id"])
                else:
                    return f"未找到名称包含「{account_nickname}」的账号，请确认账号名称后再试。"
        except Exception as e:
            logger.error("查询账号失败: %s", e, exc_info=True)
            return "查询账号信息失败，请稍后再试。"
    else:
        # 未指定账号：使用第一个 Cookie 失效的账号，否则使用第一个账号
        try:
            async with async_session() as db:
                row = (await db.execute(
                    text(
                        "SELECT a.id FROM xianyu_account a "
                        "JOIN xianyu_account_auth auth "
                        "  ON auth.account_id = a.id AND auth.tenant_id = a.tenant_id "
                        "WHERE a.tenant_id = :tid AND a.deleted = 0 "
                        "AND COALESCE(auth.deleted, 0) = 0 "
                        "AND auth.cookie_status = 0 "
                        "ORDER BY a.id ASC LIMIT 1"
                    ),
                    {"tid": tenant_id},
                )).mappings().first()
                if row:
                    target_account_id = int(row["id"])
                else:
                    async with async_session() as db2:
                        row2 = (await db2.execute(
                            text(
                                "SELECT a.id FROM xianyu_account a "
                                "WHERE a.tenant_id = :tid AND a.deleted = 0 "
                                "ORDER BY a.id ASC LIMIT 1"
                            ),
                            {"tid": tenant_id},
                        )).mappings().first()
                        if row2:
                            target_account_id = int(row2["id"])
        except Exception as e:
            logger.error("查询账号失败: %s", e, exc_info=True)
            return "查询账号信息失败，请稍后再试。"

    if target_account_id is None:
        return "未找到任何账号，请先在账号管理页添加账号。"

    # 更新会话状态
    session.state = "pending_qr_login"
    session.state_data = {"account_id": target_account_id, "started_at": time.time()}

    # 先发送提示消息
    await send_text_message(
        tenant_id, user_open_id,
        f"正在为你启动浏览器获取登录二维码（账号 ID: {target_account_id}），请稍候 5-10 秒..."
    )

    # 调用 crawler-service 的 /api/qrlogin/capture 端点获取二维码图片
    try:
        qr_result = await _fetch_qr_image_from_crawler(tenant_id)
        if not qr_result:
            session.state = "idle"
            session.state_data = {}
            return "获取二维码失败，请稍后重试，或前往账号管理页手动扫码登录。"
        qr_image_bytes, qr_session_id = qr_result
        session.state_data["qr_session_id"] = qr_session_id

        # 发送二维码图片到飞书
        sent = await send_image_bytes(tenant_id, user_open_id, qr_image_bytes)
        if not sent:
            await _cancel_qr_session(tenant_id, qr_session_id)
            session.state = "idle"
            session.state_data = {}
            return "二维码已生成但发送到飞书失败，请稍后重试。"

        # 异步启动等待扫码完成的后台任务
        asyncio.create_task(
            _wait_for_qr_login_and_recover(
                tenant_id=tenant_id,
                account_id=target_account_id,
                user_open_id=user_open_id,
                session=session,
                qr_session_id=qr_session_id,
            )
        )
        return "二维码已发送，请用闲鱼 App 扫描二维码完成登录。系统将在你扫码后自动恢复连接。"
    except Exception as e:
        logger.error("请求二维码登录异常 errorType=%s", _error_type(e))
        pending_session_id = str(session.state_data.get("qr_session_id") or "")
        if len(pending_session_id) == 32:
            await _cancel_qr_session(tenant_id, pending_session_id)
        session.state = "idle"
        session.state_data = {}
        return "请求二维码登录失败，请稍后重试或前往账号管理页手动登录。"


async def _fetch_qr_image_from_crawler(tenant_id: int) -> Optional[tuple[bytes, str]]:
    """创建租户绑定的二维码会话并返回图片与一次性会话 ID。"""
    import os
    crawler_url = os.getenv("CRAWLER_SERVICE_URL", "http://localhost:3001")
    internal_token = os.getenv("INTERNAL_API_TOKEN", "dev-only-internal-api-token-change-me-32-chars")
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{crawler_url}/api/qrlogin/capture",
                json={"headless": True},  # 后台获取二维码用无头模式
                headers={
                    "X-Internal-Token": internal_token,
                    "X-Internal-Tenant-Id": str(tenant_id),
                },
            )
            data = resp.json()
            if not data.get("ok"):
                logger.warning("crawler-service 获取二维码失败: %s", data.get("error"))
                return None
            qr_b64 = data.get("qrImageBase64")
            session_id = str(data.get("sessionId") or "")
            if not qr_b64 or len(session_id) != 32 or not all(c in "0123456789abcdef" for c in session_id):
                logger.warning("crawler-service 返回二维码为空")
                return None
            image = base64.b64decode(qr_b64, validate=True)
            if not image or len(image) > 5 * 1024 * 1024:
                logger.warning("crawler-service 返回二维码大小无效")
                return None
            return image, session_id
    except Exception as e:
        logger.error("调用 crawler-service 获取二维码异常 errorType=%s", _error_type(e))
        return None


async def _cancel_qr_session(tenant_id: int, session_id: str) -> None:
    import os
    crawler_url = os.getenv("CRAWLER_SERVICE_URL", "http://localhost:3001")
    internal_token = os.getenv("INTERNAL_API_TOKEN", "dev-only-internal-api-token-change-me-32-chars")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{crawler_url}/api/qrlogin/cancel",
                json={"sessionId": session_id},
                headers={
                    "X-Internal-Token": internal_token,
                    "X-Internal-Tenant-Id": str(tenant_id),
                },
            )
    except Exception as error:
        logger.warning("取消二维码会话失败 errorType=%s", _error_type(error))


async def _wait_for_qr_login_and_recover(
    tenant_id: int,
    account_id: int,
    user_open_id: str,
    session: FeishuChatSession,
    qr_session_id: str,
) -> None:
    """后台任务：调用 qrlogin/solve 等待用户扫码完成，成功后写入 DB 并重连 WS。

    超时 2 分钟，超时后通知用户并重置会话状态。
    """
    try:
        import os
        crawler_url = os.getenv("CRAWLER_SERVICE_URL", "http://localhost:3001")
        internal_token = os.getenv("INTERNAL_API_TOKEN", "dev-only-internal-api-token-change-me-32-chars")

        await send_text_message(
            tenant_id, user_open_id,
            "正在等待你扫码确认登录（超时时间 2 分钟）..."
        )

        # 在 capture 创建的同一个浏览器会话上等待扫码，二维码与登录状态才会一致。
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                f"{crawler_url}/api/qrlogin/solve",
                json={
                    "sessionId": qr_session_id,
                    "scanTimeoutMs": 120000,
                },
                headers={
                    "X-Internal-Token": internal_token,
                    "X-Internal-Tenant-Id": str(tenant_id),
                },
            )
            data = resp.json()

        if not data.get("ok"):
            error = data.get("error", "未知错误")
            stage = data.get("stage", "error")
            if stage == "timeout":
                await send_text_message(
                    tenant_id, user_open_id,
                    "等待扫码超时（2 分钟内未确认登录），请回复「二维码」重新获取。"
                )
            else:
                await send_text_message(
                    tenant_id, user_open_id,
                    f"扫码登录失败：{error}。请回复「二维码」重试，或前往账号管理页手动登录。"
                )
            return

        # 登录成功，写入 DB
        new_cookie = str(data.get("cookieStr") or "")
        new_unb = str(data.get("unb") or "")
        new_m_h5_tk = str(data.get("mH5Tk") or "")
        cookie_is_safe = (
            0 < len(new_cookie) <= 16 * 1024
            and not any(ord(char) < 32 or ord(char) == 127 for char in new_cookie)
        )
        if (
            not cookie_is_safe
            or not new_unb.isdigit()
            or len(new_unb) > 32
            or len(new_m_h5_tk) > 1024
        ):
            await send_text_message(
                tenant_id, user_open_id,
                "扫码登录成功但 Cookie 提取失败，请前往账号管理页手动处理。"
            )
            return

        from ..core.cookie_crypto import encrypt_cookie_for_storage
        async with async_session() as db:
            # 更新 cookie + token + 状态
            auth_update = await db.execute(
                text(
                    "UPDATE xianyu_account_auth SET "
                    "encrypted_cookie = :cookie, "
                    "encrypted_token = :tk, "
                    "cookie_status = 1, "
                    "last_login_status_code = 'OK', "
                    "last_login_status_message = '飞书扫码登录成功', "
                    "last_login_check_time = NOW(), updated_time = NOW() "
                    "WHERE account_id = :aid AND tenant_id = :tid"
                ),
                {
                    "cookie": encrypt_cookie_for_storage(new_cookie),
                    "tk": encrypt_cookie_for_storage(new_m_h5_tk) if new_m_h5_tk else None,
                    "aid": account_id,
                    "tid": tenant_id,
                },
            )
            runtime_update = await db.execute(
                text(
                    "UPDATE xianyu_account_runtime SET "
                    "cookie_status = 1, "
                    "last_login_status_code = 'OK', "
                    "last_login_status_message = '飞书扫码登录成功', "
                    "last_login_check_time = NOW(), updated_time = NOW() "
                    "WHERE account_id = :aid AND tenant_id = :tid"
                ),
                {"aid": account_id, "tid": tenant_id},
            )
            # 更新 external_uid
            if new_unb:
                account_update = await db.execute(
                    text(
                        "UPDATE xianyu_account SET external_uid = :unb, updated_time = NOW() "
                        "WHERE id = :aid AND tenant_id = :tid"
                    ),
                    {"unb": new_unb, "aid": account_id, "tid": tenant_id},
                )
            else:
                account_update = None
            if auth_update.rowcount != 1 or runtime_update.rowcount != 1 or account_update is None or account_update.rowcount != 1:
                await db.rollback()
                raise RuntimeError("account login state rows are missing")
            await db.commit()

        # 通知用户
        await send_text_message(
            tenant_id, user_open_id,
            "扫码登录成功！Cookie 已更新，正在自动重连 WebSocket..."
        )

        # 自动重连 WS
        try:
            from .ws_client import ws_manager
            await ws_manager.restart_account(account_id)
            await send_text_message(
                tenant_id, user_open_id,
                "WebSocket 已自动重连，账号已恢复在线。"
            )
        except Exception as e:
            logger.warning("扫码登录后重连 WS 失败 accountId=%d errorType=%s", account_id, _error_type(e))
            await send_text_message(
                tenant_id, user_open_id,
                "Cookie 已更新但 WebSocket 重连失败，请前往连接管理页手动启动连接。"
            )
    except Exception as e:
        logger.error("等待扫码登录后台任务异常 errorType=%s", _error_type(e))
        try:
            await send_text_message(
                tenant_id, user_open_id,
                "扫码登录流程异常，请前往账号管理页手动处理。"
            )
        except Exception as notify_err:
            logger.warning("扫码登录异常后发送飞书通知失败 errorType=%s", type(notify_err).__name__)
    finally:
        # 重置会话状态
        session.state = "idle"
        session.state_data = {}


# ============================================================
# 业务动作：账号状态查询
# ============================================================
async def _handle_account_status_query(
    tenant_id: int,
    account_nickname: str = "",
) -> str:
    """查询账号状态并返回文本报告"""
    try:
        from .ws_client import ws_manager
        async with async_session() as db:
            if account_nickname:
                rows = (await db.execute(
                    text(
                        "SELECT a.id, a.nickname, a.external_uid, "
                        "auth.cookie_status, auth.last_login_status_code, "
                        "auth.last_login_status_message, auth.last_login_check_time "
                        "FROM xianyu_account a "
                        "JOIN xianyu_account_auth auth "
                        "  ON auth.account_id = a.id AND auth.tenant_id = a.tenant_id "
                        "WHERE a.tenant_id = :tid AND a.deleted = 0 "
                        "AND COALESCE(auth.deleted, 0) = 0 "
                        "AND a.nickname LIKE :nick "
                        "ORDER BY a.id ASC"
                    ),
                    {"tid": tenant_id, "nick": f"%{account_nickname}%"},
                )).mappings().all()
            else:
                rows = (await db.execute(
                    text(
                        "SELECT a.id, a.nickname, a.external_uid, "
                        "auth.cookie_status, auth.last_login_status_code, "
                        "auth.last_login_status_message, auth.last_login_check_time "
                        "FROM xianyu_account a "
                        "JOIN xianyu_account_auth auth "
                        "  ON auth.account_id = a.id AND auth.tenant_id = a.tenant_id "
                        "WHERE a.tenant_id = :tid AND a.deleted = 0 "
                        "AND COALESCE(auth.deleted, 0) = 0 "
                        "ORDER BY a.id ASC"
                    ),
                    {"tid": tenant_id},
                )).mappings().all()

        if not rows:
            return f"未找到{'名称包含「' + account_nickname + '」的' if account_nickname else '任何'}账号。"

        lines = [f"账号状态报告（共 {len(rows)} 个账号）：", ""]
        for r in rows:
            account_id = int(r["id"])
            nickname = r["nickname"] or ""
            cookie_status = int(r["cookie_status"] or 0)
            status_code = r["last_login_status_code"] or ""
            status_msg = r["last_login_status_message"] or ""

            # 查询 WS 连接状态
            ws_status = ws_manager.get_status(account_id)
            ws_connected = ws_status.get("connected", False)

            cookie_text = "✅ 有效" if cookie_status == 1 else "❌ 失效"
            ws_text = "🟢 已连接" if ws_connected else "⚪ 未连接"
            lines.append(f"• {nickname}（ID: {account_id}）")
            lines.append(f"  Cookie: {cookie_text} | WS: {ws_text}")
            if cookie_status == 0 and status_msg:
                lines.append(f"  失效原因: {status_msg}")
            lines.append("")

        lines.append("如需重新登录，请回复「二维码」获取登录二维码。")
        return "\n".join(lines)
    except Exception as e:
        logger.error("查询账号状态失败: %s", e, exc_info=True)
        return "查询账号状态失败，请稍后再试。"


# ============================================================
# 主入口：处理飞书用户消息
# ============================================================
async def handle_feishu_user_message(
    tenant_id: int,
    user_open_id: str,
    message_content: str,
) -> str:
    """处理飞书用户消息，返回给用户的回复文本。

    内部流程：
    1. 获取/创建会话
    2. AI 意图分析
    3. 根据意图触发对应动作
    4. 记录对话历史
    """
    _purge_expired_sessions()
    session = _get_session(tenant_id, user_open_id)

    # 记录用户消息到历史
    session.history.append({"role": "user", "content": message_content})
    if len(session.history) > 20:
        session.history = session.history[-10:]

    try:
        # AI 意图分析
        billing_user_id = await _resolve_feishu_billing_user_id(tenant_id)
        if not billing_user_id:
            return "AI 助手无法确定计费用户，请检查飞书通知配置的用户归属。"
        intent_data = await _analyze_intent(
            tenant_id,
            billing_user_id,
            message_content,
            session.history,
            build_request_id("feishu_chat_intent"),
        )
        intent = intent_data.get("intent", "general_chat")
        confidence = intent_data.get("confidence", 0.0)
        account_nickname = intent_data.get("account_nickname", "")
        ai_response = intent_data.get("response", "")

        logger.info(
            "飞书消息意图分析: tenant_id=%d intent=%s confidence=%.2f hasNickname=%s",
            tenant_id, intent, confidence, bool(account_nickname),
        )

        # 根据意图触发动作
        if intent == "request_qrcode" and confidence >= 0.6:
            reply = await _handle_request_qrcode(
                tenant_id, session, user_open_id, account_nickname
            )
        elif intent == "account_status_query" and confidence >= 0.6:
            reply = await _handle_account_status_query(tenant_id, account_nickname)
        else:
            # 通用闲聊
            reply = ai_response or "我收到了你的消息，有什么我可以帮你的吗？"
            # 如果用户处于 pending_qr_login 状态，在闲聊回复中提示
            if session.state == "pending_qr_login":
                reply += "\n\n（提示：你的扫码登录请求仍在处理中，请先用闲鱼 App 扫描之前发送的二维码。）"

        # 记录助手回复到历史
        session.history.append({"role": "assistant", "content": reply})
        return reply
    except AiBillingPaymentRequired:
        return "AI Token 余额不足，请充值后重试。"
    except AiBillingError:
        return "AI 计费服务暂不可用，请稍后重试。"
    except Exception as e:
        logger.error("处理飞书用户消息异常: %s", e, exc_info=True)
        return "处理消息时出现异常，请稍后再试。"


# ============================================================
# 主动通知：Cookie Session 过期时推送飞书通知
# ============================================================
async def notify_session_expired_via_feishu_app(
    tenant_id: int,
    account_id: int,
    account_name: str,
) -> None:
    """Cookie Session 过期时通过飞书自建应用推送通知。

    通知内容包含账号名称和提示用户回复「二维码」获取登录二维码。
    """
    try:
        config = await _load_feishu_app_config(tenant_id)
        if not config or not config.get("receiveId"):
            return  # 未配置接收者，跳过

        await send_text_message(
            tenant_id,
            config["receiveId"],
            (
                f"⚠️ 账号「{account_name}」（ID: {account_id}）Cookie Session 已过期，"
                f"WebSocket 已断开连接。\n\n"
                f"系统已自动尝试滑块验证，但 Cookie Session 真正过期，需要重新登录。\n\n"
                f"💡 你可以直接回复「二维码」获取登录二维码，扫码后系统会自动恢复连接。"
            ),
            receive_id_type=config.get("receiveIdType", "open_id"),
        )
    except Exception as e:
        logger.warning("通过飞书自建应用通知 Session 过期失败: %s", e, exc_info=True)
