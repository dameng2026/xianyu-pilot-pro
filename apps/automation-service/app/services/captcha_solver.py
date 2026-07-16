"""
滑块验证处理服务
================

实现两部分能力：

1. **智能检测**：从 MTOP API 响应中检测滑块/人机验证需求
   - 关键词：FAIL_SYS_USER_VALIDATE / RGV587_ERROR / 被挤爆啦 / CAPTCHA_NEEDED
   - 提取验证 URL（data.url）

2. **操作指引**：为前端提供详细的分步操作指引
   - 检测到滑块后返回结构化指引数据
   - 包含：访问 URL、操作步骤、Cookie 更新提示

3. **自动拖动**：调用 crawler-service 的 Playwright 滑块求解接口
   - 通过 HTTP 调用 crawler-service 的 /api/goofish/slide-solve
   - 失败时回退到人工处理指引

调用方式：
- detect_captcha(response) -> 检测是否需要滑块
- build_instructions(account_id, captcha_url) -> 构建操作指引
- try_auto_solve(account_id) -> 调用 Playwright 自动求解
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx
from sqlalchemy import text

from ..core.config import settings
from ..core.cookie_crypto import decrypt_cookie_if_needed, encrypt_cookie_for_storage
from ..core.database import async_session
from ..core.failure_logging import log_service_failure

logger = logging.getLogger(__name__)


def _resolve_headless_mode(value: Optional[bool]) -> bool:
    if value is not None:
        return bool(value)
    return os.name != "nt" and not os.environ.get("DISPLAY")


# ============================================================
# 滑块验证检测关键词
# ============================================================
CAPTCHA_KEYWORDS = (
    "FAIL_SYS_USER_VALIDATE",
    "RGV587_ERROR",
    "被挤爆啦",
    "CAPTCHA_NEEDED",
    "xcaptcha",
    "baxia",
    "punish",
)

CAPTCHA_URL_KEYWORDS = (
    "url",
    "captcha_url",
    "captchaUrl",
    "verifyUrl",
    "verify_url",
)


@dataclass
class CaptchaDetectResult:
    """滑块检测结果"""
    detected: bool
    captcha_url: Optional[str] = None
    reason: Optional[str] = None
    raw_response: Optional[dict] = None


@dataclass
class CaptchaInstructions:
    """操作指引"""
    account_id: int
    captcha_url: Optional[str]
    steps: list[str] = field(default_factory=list)
    title: str = "检测到账号需要完成滑块验证"
    auto_solve_available: bool = True
    manual_fallback_url: str = "https://www.goofish.com/"
    message: str = ""


# ============================================================
# 1. 智能检测
# ============================================================
def detect_captcha_from_response(response: dict | str | None) -> CaptchaDetectResult:
    """从 MTOP API 响应中检测滑块验证需求。

    支持两种输入：
    - dict: 完整的 MTOP 响应 JSON
    - str: 响应文本（直接搜索关键词）

    返回 CaptchaDetectResult，包含验证 URL（如果有的话）。
    """
    if not response:
        return CaptchaDetectResult(detected=False)

    if isinstance(response, str):
        text_lower = response.lower()
        for kw in CAPTCHA_KEYWORDS:
            if kw.lower() in text_lower:
                return CaptchaDetectResult(
                    detected=True,
                    reason=f"响应包含关键词: {kw}",
                )
        return CaptchaDetectResult(detected=False)

    # dict 类型：先查 ret 字段，再查 data.url
    ret_list = response.get("ret") or []
    if isinstance(ret_list, list):
        ret_str = " | ".join(str(r) for r in ret_list)
    else:
        ret_str = str(ret_list)

    for kw in CAPTCHA_KEYWORDS:
        if kw in ret_str:
            # 尝试提取验证 URL
            data = response.get("data") or {}
            captcha_url = None
            if isinstance(data, dict):
                for url_key in CAPTCHA_URL_KEYWORDS:
                    if url_key in data and data[url_key]:
                        captcha_url = str(data[url_key])
                        break

            return CaptchaDetectResult(
                detected=True,
                captcha_url=captcha_url,
                reason=f"ret 包含 {kw}",
                raw_response=response,
            )

    # 兜底：检查整个响应的字符串形式
    response_str = str(response)
    for kw in CAPTCHA_KEYWORDS:
        if kw in response_str:
            return CaptchaDetectResult(
                detected=True,
                reason=f"响应包含关键词: {kw}",
                raw_response=response if isinstance(response, dict) else None,
            )

    return CaptchaDetectResult(detected=False)


# ============================================================
# 2. 操作指引
# ============================================================
def build_captcha_instructions(
    account_id: int,
    captcha_url: Optional[str] = None,
    account_name: Optional[str] = None,
) -> CaptchaInstructions:
    """构建详细的滑块验证操作指引。

    返回的指引包含：
    - 自动求解：调用 Playwright 自动拖动（auto_solve_available=True）
    - 人工兜底：4 步指引（访问闲鱼→完成验证→复制 Cookie→更新 Cookie）
    """
    steps = [
        '【方案一·自动求解】点击下方"自动求解"按钮，系统将启动浏览器自动拖动滑块完成验证（推荐先尝试）',
        "【方案二·人工处理】如果自动求解失败，请按以下步骤操作：",
        "  1. 点击访问闲鱼主页 https://www.goofish.com/ 并登录（如已登录可跳过）",
        "  2. 在闲鱼页面完成滑块验证（通常出现在消息、商品发布等场景）",
        "  3. 验证通过后，按 F12 打开开发者工具 → Application → Cookies → 复制 .goofish.com 域下的完整 Cookie",
        '  4. 返回本页面，点击"手动更新 Cookie"按钮，粘贴复制的 Cookie 并保存',
        '  5. 保存后点击"启动连接"，系统会自动刷新 WebSocket Token 并重连',
    ]

    name_prefix = f"账号 {account_name or account_id} " if account_id else ""
    return CaptchaInstructions(
        account_id=account_id,
        captcha_url=captcha_url,
        steps=steps,
        title=f"{name_prefix}检测到滑块验证",
        auto_solve_available=True,
        message=(
            "检测到账号需要完成滑块验证。请先尝试自动求解；"
            "如自动求解失败，请按指引手动完成验证并更新 Cookie。"
            "更新 Cookie 后点击启动连接，会自动刷新 Token，"
            "滑块校验生效会延迟，稍等片刻会自动连接。"
        ),
    )


# ============================================================
# 3. Playwright 自动求解
# ============================================================
async def try_auto_solve(
    account_id: int,
    tenant_id: int,
    target_url: Optional[str] = None,
    headless: Optional[bool] = None,
    max_retries: int = 5,
    *,
    force: bool = False,
    profile_strategy: str = "persistent",
    semi_auto_fallback: bool = False,
) -> dict:
    """调用 crawler-service 的 Playwright 滑块求解接口。

    Args:
        account_id: 账号 ID（用于读取 Cookie）
        target_url: 目标页面 URL（默认闲鱼首页）
        headless: 是否无头模式（默认 false，滑块识别有头更稳定）
        max_retries: 最大重试次数
        force: 是否跳过指数退避（默认 False，全自动遵守退避）

    Returns:
        {
            "success": bool,
            "solved": bool,
            "captchaDetected": bool,
            "attempts": int,
            "error": Optional[str],
            "durationMs": int,
        }
    """
    # 全自动指数退避：冷却期内直接拒绝，避免 punish 加码
    from .captcha_backoff import assert_auto_solve_allowed, record_solve_failure, record_solve_success
    from .account_proxy import load_account_proxy, proxy_to_playwright, proxy_public_label

    blocked = await assert_auto_solve_allowed(account_id, tenant_id, force=force)
    if blocked:
        logger.warning(
            "滑块求解被指数退避拦截 accountId=%d error=%s",
            account_id, blocked.get("error"),
        )
        return blocked

    # 读取账号 Cookie
    try:
        async with async_session() as db:
            row = (await db.execute(
                text(
                    "SELECT encrypted_cookie, tenant_id FROM xianyu_account_auth "
                    "WHERE account_id = :aid AND tenant_id = :tid AND deleted = 0 LIMIT 1"
                ),
                {"aid": account_id, "tid": tenant_id},
            )).mappings().first()
    except Exception as e:
        log_service_failure(
            logger, e, operation="load_captcha_account_cookie",
            tenant_id=tenant_id, account_id=account_id,
        )
        return {
            "success": False,
            "solved": False,
            "captchaDetected": False,
            "attempts": 0,
            "errorCode": "CAPTCHA_ACCOUNT_LOAD_FAILED",
            "error": "读取账号信息失败，请稍后重试",
            "durationMs": 0,
        }

    if not row:
        return {
            "success": False,
            "solved": False,
            "captchaDetected": False,
            "attempts": 0,
            "error": "账号不存在或未配置 Cookie",
            "durationMs": 0,
        }

    cookie_str = decrypt_cookie_if_needed(row["encrypted_cookie"])
    if not cookie_str:
        return {
            "success": False,
            "solved": False,
            "captchaDetected": False,
            "attempts": 0,
            "error": "Cookie 解密失败",
            "durationMs": 0,
        }

    # 按账号绑定代理（可选）
    proxy = await load_account_proxy(account_id, tenant_id)
    proxy_payload = proxy_to_playwright(proxy)
    if proxy_payload:
        logger.info(
            "滑块求解使用账号绑定代理 accountId=%d proxy=%s",
            account_id, proxy_public_label(proxy),
        )

    # 调用 crawler-service
    crawler_url = getattr(settings, "crawler_service_url", None) or os.environ.get(
        "CRAWLER_SERVICE_URL", "http://localhost:3001"
    )
    endpoint = f"{crawler_url.rstrip('/')}/api/goofish/slide-solve"

    # 内部 token
    internal_token = (
        getattr(settings, "internal_api_token", None)
        or os.environ.get("INTERNAL_API_TOKEN")
        or "dev-only-internal-api-token-change-me-32-chars"
    )
    tenant_id = int(row["tenant_id"])

    resolved_headless = _resolve_headless_mode(headless)

    payload = {
        "cookie": cookie_str,
        "targetUrl": target_url,
        "headless": resolved_headless,
        "maxRetries": max_retries,
        "timeoutMs": 90000,
        # profile 策略：persistent（默认持久化，累积历史降低风控）/ seed / temp
        "profileStrategy": profile_strategy,
        # 半自动人工兜底：全自动失败后保留窗口供人工拖拽
        "semiAutoFallback": semi_auto_fallback,
    }
    if proxy_payload:
        payload["proxy"] = proxy_payload

    headers = {
        "Content-Type": "application/json",
        "X-Internal-Token": internal_token,
        "X-Internal-Tenant-Id": str(tenant_id),
    }

    started = time.time()
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(endpoint, json=payload, headers=headers)
            data = resp.json()
    except Exception as e:
        log_service_failure(
            logger, e, operation="solve_captcha",
            tenant_id=tenant_id, account_id=account_id,
        )
        await record_solve_failure(
            account_id, tenant_id, error="滑块求解服务暂时不可用",
        )
        return {
            "success": False,
            "solved": False,
            "captchaDetected": False,
            "attempts": 0,
            "errorCode": "CAPTCHA_SOLVER_UNAVAILABLE",
            "error": "滑块求解服务暂时不可用，请稍后重试",
            "durationMs": int((time.time() - started) * 1000),
        }

    duration_ms = int((time.time() - started) * 1000)
    solve_ok = bool(data.get("ok"))
    crawler_error = data.get("error") or ""

    # 读取求解成功后的最新 cookies（Baxia 验证通过后服务器下发新 token，如 _m_h5_tk）
    fresh_cookies = data.get("cookies") or ""

    # 退避状态：成功清零 / 失败累加（含 captchaDetected 但未通过）
    if solve_ok and bool(data.get("solved")):
        await record_solve_success(account_id, tenant_id)
    else:
        await record_solve_failure(
            account_id, tenant_id,
            error=crawler_error or "滑块验证未通过",
        )

    # 如果求解成功且有最新 cookies，立即更新数据库中的 cookie
    # 关键：Baxia 验证通过后浏览器中的 cookie 已更新，必须持久化到数据库，
    # 否则后续 _verify_cookie_via_token_api 和 API 调用仍用旧 cookie 会失败
    if solve_ok and fresh_cookies:
        try:
            from .ws_token import extract_m_h5_tk_from_cookie
            m_h5_tk = extract_m_h5_tk_from_cookie(fresh_cookies)
            encrypted_cookie = encrypt_cookie_for_storage(fresh_cookies)
            encrypted_token = encrypt_cookie_for_storage(m_h5_tk) if m_h5_tk else None
            async with async_session() as db:
                await db.execute(
                    text("""
                        UPDATE xianyu_account_auth
                        SET encrypted_cookie = :cookie,
                            encrypted_token = COALESCE(:token, encrypted_token),
                            updated_time = NOW()
                        WHERE account_id = :account_id AND tenant_id = :tenant_id
                          AND COALESCE(deleted, 0) = 0
                    """),
                    {
                        "cookie": encrypted_cookie,
                        "token": encrypted_token,
                        "account_id": account_id,
                        "tenant_id": tenant_id,
                    },
                )
                await db.commit()
            logger.info(
                "滑块求解成功，已更新数据库 Cookie accountId=%d cookieLen=%d hasToken=%s",
                account_id, len(fresh_cookies), bool(m_h5_tk),
            )
        except Exception as e:
            log_service_failure(
                logger, e, operation="update_captcha_fresh_cookies",
                tenant_id=tenant_id, account_id=account_id, level=logging.WARNING,
            )

    return {
        "success": solve_ok,
        "solved": bool(data.get("solved")),
        "captchaDetected": bool(data.get("captchaDetected")),
        "attempts": int(data.get("attempts") or 0),
        "errorCode": "" if solve_ok else "CAPTCHA_SOLVE_FAILED",
        "error": None if solve_ok else (crawler_error or "滑块验证未通过，请改用人工验证"),
        "screenshotPath": data.get("screenshotPath"),
        "durationMs": duration_ms,
        "cookies": fresh_cookies if solve_ok else None,
    }


# ============================================================
# 4. 综合处理：检测 + 通知 + 自动求解
# ============================================================
async def _update_cookie_status_for_captcha(
    account_id: int,
    tenant_id: int,
    cookie_status: int,
    status_code: str,
    status_message: str,
) -> None:
    """滑块求解过程中同步更新 Cookie 状态（xianyu_account_auth + xianyu_account_runtime）。

    同时通过 SSE 广播 cookie_status_changed 事件，让前端账号列表实时刷新 Cookie 状态列。

    Args:
        cookie_status: 0=不可用/验证中, 1=可用
        status_code: last_login_status_code（VERIFYING/CAPTCHA_FAILED/SESSION_EXPIRED/OK）
        status_message: last_login_status_message
    """
    try:
        async with async_session() as db:
            for table in ("xianyu_account_auth", "xianyu_account_runtime"):
                await db.execute(
                    text(
                        f"UPDATE {table} SET cookie_status = :cs, "
                        f"last_login_status_code = :sc, "
                        f"last_login_status_message = :sm, "
                        f"last_login_check_time = NOW(), updated_time = NOW() "
                        f"WHERE account_id = :aid AND tenant_id = :tid"
                    ),
                    {
                        "cs": cookie_status,
                        "sc": status_code,
                        "sm": status_message,
                        "aid": account_id,
                        "tid": tenant_id,
                    },
                )
            await db.commit()
    except Exception as e:
        log_service_failure(
            logger, e, operation="update_cookie_status_for_captcha",
            tenant_id=tenant_id, account_id=account_id, level=logging.WARNING,
        )

    # 通过 SSE 广播 cookie_status_changed 事件，前端账号列表实时刷新 Cookie 状态列
    try:
        from .ws_sse import broadcaster
        await broadcaster.broadcast(tenant_id, "cookie_status_changed", {
            "accountId": account_id,
            "tenantId": tenant_id,
            "cookieStatus": cookie_status,
            "loginStatusCode": status_code,
            "loginStatusMessage": status_message,
        })
        logger.info(
            "SSE 已广播 cookie_status_changed（滑块求解）: accountId=%d, status=%d, code=%s",
            account_id, cookie_status, status_code,
        )
    except Exception as sse_err:
        log_service_failure(
            logger, sse_err, operation="broadcast_captcha_cookie_status",
            tenant_id=tenant_id, account_id=account_id, level=logging.WARNING,
        )


async def _verify_cookie_via_token_api(account_id: int, tenant_id: int) -> bool:
    """滑块求解成功后，调用 Token API 二次验证 Cookie 是否真正可用。

    滑块求解器在 Cookie Session 已过期时会误报成功（页面跳转到登录页，
    没有滑块组件）。此处通过 Token API 的实际响应来确认 Cookie 真实可用性。

    Args:
        account_id: 账号 ID
        tenant_id: 租户 ID

    Returns:
        True: Cookie 可用，Token API 返回 SUCCESS
        False: Cookie 已过期（FAIL_SYS_SESSION_EXPIRED）或不可用
    """
    try:
        async with async_session() as db:
            row = (await db.execute(
                text(
                    "SELECT encrypted_cookie, encrypted_token "
                    "FROM xianyu_account_auth "
                    "WHERE account_id = :aid AND tenant_id = :tid AND deleted = 0 LIMIT 1"
                ),
                {"aid": account_id, "tid": tenant_id},
            )).mappings().first()
        if not row:
            logger.warning("_verify_cookie_via_token_api: 账号不存在 accountId=%d", account_id)
            return False

        cookie_str = decrypt_cookie_if_needed(row["encrypted_cookie"])
        if not cookie_str:
            logger.warning("_verify_cookie_via_token_api: Cookie 为空 accountId=%d", account_id)
            return False

        m_h5_tk = None
        if row["encrypted_token"]:
            m_h5_tk = decrypt_cookie_if_needed(row["encrypted_token"])

        # 调用 ws_token 模块的完整 Token 获取流程
        # （会自动尝试 cookie 中的 _m_h5_tk、DB 中的 _m_h5_tk、刷新 _m_h5_tk 三种路径）
        from .ws_token import get_ws_token_with_refreshed_m_h5_tk
        access_token, _, error_type, _ = get_ws_token_with_refreshed_m_h5_tk(cookie_str, m_h5_tk)
        if access_token:
            logger.info(
                "_verify_cookie_via_token_api: Cookie 验证通过 accountId=%d, accessToken长度=%d",
                account_id, len(access_token),
            )
            return True
        logger.warning(
            "_verify_cookie_via_token_api: Cookie 不可用 accountId=%d, error_type=%s",
            account_id, error_type,
        )
        return False
    except Exception as e:
        log_service_failure(
            logger, e, operation="verify_captcha_cookie",
            tenant_id=tenant_id, account_id=account_id,
        )
        return False


async def handle_captcha_for_account(
    account_id: int,
    tenant_id: int,
    response: dict | str | None = None,
    auto_solve: bool = False,
    trigger_scene: str = "manual",
    open_reason: str = "",
    solve_reason: str = "",
) -> dict:
    """综合处理账号的滑块验证场景。

    1. 如果提供了 response，先检测是否真的需要滑块
    2. 如果检测到，写入 cookie_status=0 并通知用户
    3. 如果 auto_solve=True，尝试自动求解
    4. 自动求解成功后，刷新 token 并恢复 cookie_status

    Args:
        trigger_scene: 触发场景 (ws_connect/cookie_keepalive/token_refresh/manual)，
                       用于写入求解记录和 SSE 广播
        open_reason: 开启原因（为什么打开滑块求解流程）
        solve_reason: 求解原因（为什么进行滑块求解，具体业务原因）

    Returns:
        {
            "detected": bool,
            "captchaUrl": Optional[str],
            "instructions": dict,
            "autoSolveResult": Optional[dict],
            "recovered": bool,  # 是否成功恢复
        }
    """
    from .notify_dispatcher import notify_captcha_required
    from .captcha_solve_record import (
        create_solve_record, update_solve_record, broadcast_captcha_solve,
        _lookup_account_name,
    )

    detected = False
    captcha_url = None
    if response is not None:
        result = detect_captcha_from_response(response)
        detected = result.detected
        captcha_url = result.captcha_url

    instructions = build_captcha_instructions(account_id, captcha_url)
    auto_solve_result = None
    recovered = False
    solve_record_id = None

    if detected or auto_solve:
        # 通知用户
        try:
            await notify_captcha_required(
                tenant_id, account_id,
                scene=f"账号触发滑块验证（自动求解={'开启' if auto_solve else '关闭'}）",
            )
        except Exception as exc:
            log_service_failure(
                logger, exc, operation="notify_captcha_required",
                tenant_id=tenant_id, account_id=account_id, level=logging.DEBUG,
            )

    if auto_solve and (detected or response is None):
        logger.info("开始为账号 %d 自动求解滑块 (scene=%s)", account_id, trigger_scene)

        # 先查指数退避：冷却中则直接落库失败记录，不启动浏览器
        from .captcha_backoff import assert_auto_solve_allowed
        account_name = await _lookup_account_name(tenant_id, account_id)
        blocked = await assert_auto_solve_allowed(account_id, tenant_id, force=False)
        if blocked:
            solve_record_id = await create_solve_record(
                account_id, tenant_id, trigger_scene=trigger_scene,
                open_reason=open_reason or "全自动冷却拦截",
                solve_reason=solve_reason or blocked.get("error") or "指数退避冷却中",
            )
            await update_solve_record(
                solve_record_id, status="fail", result="slider_fail",
                error_message=blocked.get("error") or "全自动滑块冷却中",
                engine="Backoff",
            )
            await broadcast_captcha_solve(
                tenant_id, account_id, account_name,
                status="fail", result="slider_fail",
                reason=blocked.get("error") or "全自动滑块冷却中",
                record_id=solve_record_id,
            )
            return {
                "detected": detected,
                "captchaUrl": captcha_url,
                "instructions": {
                    "title": instructions.title,
                    "steps": instructions.steps,
                    "message": instructions.message,
                    "autoSolveAvailable": instructions.auto_solve_available,
                    "manualFallbackUrl": instructions.manual_fallback_url,
                },
                "autoSolveResult": blocked,
                "recovered": False,
            }

        # 创建求解记录 + 广播"求解中"状态
        solve_record_id = await create_solve_record(
            account_id, tenant_id, trigger_scene=trigger_scene,
            open_reason=open_reason, solve_reason=solve_reason,
        )
        await broadcast_captcha_solve(
            tenant_id, account_id, account_name,
            status="retrying", reason=f"正在求解滑块（{trigger_scene}）",
            record_id=solve_record_id,
        )

        # 同步更新 Cookie 状态为"验证中"，让前端账号列表立即反映求解状态
        await _update_cookie_status_for_captcha(
            account_id, tenant_id,
            cookie_status=0,
            status_code="VERIFYING",
            status_message=f"正在自动求解滑块验证（{trigger_scene}）",
        )

        auto_solve_result = await try_auto_solve(account_id, tenant_id)

        if auto_solve_result.get("solved"):
            logger.info("账号 %d 滑块自动求解成功", account_id)

            # === 关键二次验证：调用 Token API 确认 Cookie 真实可用 ===
            # 滑块求解器在 Cookie Session 已过期时会误报成功（页面跳转到登录页，
            # 没有滑块组件）。此处用 Token API 做最终验证，避免错误恢复 cookie_status=1
            # 导致后续 ws_client 校验失败。
            cookie_valid = await _verify_cookie_via_token_api(account_id, tenant_id)
            if not cookie_valid:
                logger.warning(
                    "账号 %d 滑块求解器报告成功，但 Token API 验证 Cookie 仍不可用，"
                    "Cookie Session 已真正过期，需要用户重新扫码登录",
                    account_id,
                )
                # 不恢复 cookie_status=1，保持 0 状态，并附带明确错误信息
                await _update_cookie_status_for_captcha(
                    account_id, tenant_id,
                    cookie_status=0,
                    status_code="SESSION_EXPIRED",
                    status_message="Cookie Session 已过期，请重新扫码登录闲鱼账号",
                )

                # Cookie 已失效，主动断开 WS 连接，避免前端显示"WS 在线但 Cookie 失败"的矛盾状态
                try:
                    from .ws_client import ws_manager
                    await ws_manager.stop_client(account_id)
                    logger.info("Cookie 验证失败，已断开 WS 连接 accountId=%d", account_id)
                except Exception as e:
                    log_service_failure(
                        logger, e, operation="stop_captcha_ws_client",
                        tenant_id=tenant_id, account_id=account_id, level=logging.WARNING,
                    )

                # 在 auto_solve_result 中附加验证失败标记，让前端能展示真实原因
                auto_solve_result["cookieVerified"] = False
                auto_solve_result["error"] = (
                    "滑块已通过，但 Cookie Session 已真正过期（FAIL_SYS_SESSION_EXPIRED），"
                    "请前往账号管理页重新扫码登录闲鱼账号获取新 Cookie"
                )
                # 更新求解记录为失败 + 广播失败事件
                await update_solve_record(
                    solve_record_id, status="fail", result="slider_success",
                    error_message="Cookie Session 已过期，需重新扫码登录",
                    retry_count=int(auto_solve_result.get("attempts") or 0),
                    duration_ms=int(auto_solve_result.get("durationMs") or 0),
                    screenshot_path=str(auto_solve_result.get("screenshotPath") or ""),
                    engine="Playwright",
                )
                await broadcast_captcha_solve(
                    tenant_id, account_id, account_name,
                    status="fail", result="slider_success",
                    reason="滑块已通过但 Cookie Session 已过期，需重新扫码登录",
                    record_id=solve_record_id,
                )
                # 不标记 recovered=True，让前端引导用户重新登录
            else:
                logger.info("账号 %d Cookie 二次验证通过，恢复 cookie_status=1", account_id)
                recovered = True

                # 滑块验证已通过，清除账号状态通知去重标记（内存 + DB），
                # 以便下次再次失效时能重新发送通知。
                try:
                    from .notify_dispatcher import clear_all_account_status_notifications
                    await clear_all_account_status_notifications(tenant_id, account_id)
                except Exception:
                    pass

                # 恢复 cookie_status=1，last_login_status_code 必须为 'OK'
                # （_load_ws_credentials 校验要求 login_status_code == "OK"）
                await _update_cookie_status_for_captcha(
                    account_id, tenant_id,
                    cookie_status=1,
                    status_code="OK",
                    status_message="滑块验证已通过（自动求解+Token API 二次验证）",
                )

                # 触发 _m_h5_tk 刷新（不触发 ws_token 刷新，避免 Session 过期时 ws_client 覆盖 cookie_status=0）
                try:
                    from .cookie_token_refresher import force_refresh_account
                    await force_refresh_account(account_id, tenant_id, "mh5tk")
                except Exception as e:
                    log_service_failure(
                        logger, e, operation="refresh_captcha_account_token",
                        tenant_id=tenant_id, account_id=account_id, level=logging.WARNING,
                    )

                # 更新求解记录为成功 + 广播成功事件
                # 成功时不把 duration/screenshot 写入 error_message，避免前端误判为失败信息
                await update_solve_record(
                    solve_record_id, status="success", result="slider_success",
                    retry_count=int(auto_solve_result.get("attempts") or 0),
                    engine="Playwright",
                    error_message=(
                        f"[durationMs={int(auto_solve_result.get('durationMs') or 0)}] 滑块求解成功"
                    ),
                )
                await broadcast_captcha_solve(
                    tenant_id, account_id, account_name,
                    status="success", result="slider_success",
                    reason="滑块求解成功，Cookie 已恢复",
                    record_id=solve_record_id,
                )
        else:
            # 滑块求解失败
            logger.warning("账号 %d 滑块自动求解失败", account_id)
            error_msg = auto_solve_result.get("error") or "滑块验证未通过"
            # 同步更新 Cookie 状态为"不可用"，让前端账号列表反映失败状态
            await _update_cookie_status_for_captcha(
                account_id, tenant_id,
                cookie_status=0,
                status_code="CAPTCHA_FAILED",
                status_message=f"滑块求解失败：{error_msg}",
            )
            await update_solve_record(
                solve_record_id, status="fail", result="slider_fail",
                error_message=error_msg,
                retry_count=int(auto_solve_result.get("attempts") or 0),
                duration_ms=int(auto_solve_result.get("durationMs") or 0),
                screenshot_path=str(auto_solve_result.get("screenshotPath") or ""),
                engine="Playwright",
            )
            await broadcast_captcha_solve(
                tenant_id, account_id, account_name,
                status="fail", result="slider_fail",
                reason=error_msg,
                record_id=solve_record_id,
            )

    return {
        "detected": detected,
        "captchaUrl": captcha_url,
        "instructions": {
            "title": instructions.title,
            "steps": instructions.steps,
            "message": instructions.message,
            "autoSolveAvailable": instructions.auto_solve_available,
            "manualFallbackUrl": instructions.manual_fallback_url,
        },
        "autoSolveResult": auto_solve_result,
        "recovered": recovered,
    }
