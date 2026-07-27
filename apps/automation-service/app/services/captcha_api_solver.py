"""对外滑块求解器：bypass 账号逻辑，直接调 crawler-service。

与内部 captcha_solver.py 的区别：
- 不查 xianyu_account 表、不加载账号代理
- 不入 captcha_queue.PriorityQueue（避免与内部任务抢占）
- 直接调用 crawler-service /api/goofish/slide-solve
- 复用 _is_browser_launch_failure() 错误分类逻辑
- 持久化到 xianyu_api_captcha_solve_record
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

import httpx

from .captcha_api_record import create_api_record, update_api_record
from ..core.config import settings

logger = logging.getLogger(__name__)

# 浏览器启动失败特征（与 captcha_solver.py 保持一致）
_BROWSER_LAUNCH_FAILURE_PATTERNS = (
    "browserType.launch", "Target page, context or browser",
    "browser has been closed", "spawn /opt/google/chrome/chrome",
    "spawn EAGAIN", "pthread_create", "Target closed",
    "Protocol error", "Browser logs:", "Max listeners",
    "浏览器任务繁忙", "Failed to start BrowserThread",
    "Failed to start", "Page crashed", "page.goto",
    "Target page already closed", "Navigation failed because",
    "has been closed", "page.waitForTimeout",
)


def _is_browser_launch_failure(error_msg: str) -> bool:
    if not error_msg:
        return False
    msg_lower = error_msg.lower() if isinstance(error_msg, str) else str(error_msg).lower()
    return any(p.lower() in msg_lower for p in _BROWSER_LAUNCH_FAILURE_PATTERNS)


def _crawler_service_url() -> str:
    return getattr(settings, "crawler_service_url", None) or os.environ.get(
        "CRAWLER_SERVICE_URL", "http://localhost:3001"
    )


def _internal_token() -> str:
    return getattr(settings, "effective_internal_api_token", None) or os.environ.get(
        "INTERNAL_API_TOKEN", "dev-only-internal-api-token-change-me-32-chars"
    )


async def solve_for_external(
    cookie: str,
    target_url: str,
    timeout_ms: int,
    request_id: str,
    tenant_id: int,
    api_key_prefix: str,
    client_ip: Optional[str] = None,
) -> dict:
    """
    对外求解入口。

    返回结构：
    {
        "status": "success"|"fail"|"timeout"|"precheck_rejected"|"service_unavailable",
        "solved": bool,
        "captchaDetected": bool,
        "attempts": int,
        "durationMs": int,
        "cookies": Optional[str],
        "error": Optional[str],
    }
    """
    start_time = time.time()

    # 先创建记录（queued），保证预检失败/超时/异常都能持久化
    await create_api_record(tenant_id, api_key_prefix, request_id, client_ip)

    # 预检验：cookie 非空
    if not cookie or not cookie.strip():
        await update_api_record(
            request_id, status="precheck_rejected", result="precheck_fail",
            failure_reason="cookie_invalid", error_message="cookie is empty",
            duration_ms=int((time.time() - start_time) * 1000),
        )
        return {
            "status": "precheck_rejected", "solved": False, "captchaDetected": False,
            "attempts": 0, "durationMs": int((time.time() - start_time) * 1000),
            "cookies": None, "error": "cookie is empty",
        }

    # 标记处理中
    await update_api_record(request_id, status="retrying", started=True)

    # 调用 crawler-service（请求体追加 slotType=api 走独立并发槽位）
    crawler_url = _crawler_service_url().rstrip("/")
    endpoint = f"{crawler_url}/api/goofish/slide-solve"
    payload = {
        "cookie": cookie,
        "targetUrl": target_url,
        "headless": True,  # API 对接默认 headless，不依赖 Xvfb
        "maxRetries": 5,
        "timeoutMs": timeout_ms,
        "profileStrategy": "persistent",
        "semiAutoFallback": False,
        "slotType": "api",  # 走独立并发槽位
    }
    headers = {
        "Content-Type": "application/json",
        "X-Internal-Token": _internal_token(),
        "X-Internal-Tenant-Id": str(tenant_id),
    }

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(endpoint, json=payload, headers=headers)
            data = resp.json()
    except httpx.TimeoutException as e:
        # 超时单独归类，开源版据此显示"超时记录"
        error_msg = str(e)
        duration_ms = int((time.time() - start_time) * 1000)
        await update_api_record(
            request_id, status="timeout", result="timeout",
            failure_reason="timeout", error_message=error_msg,
            duration_ms=duration_ms,
        )
        return {
            "status": "timeout", "solved": False, "captchaDetected": False,
            "attempts": 0, "durationMs": duration_ms, "cookies": None, "error": "求解超时，请稍后重试",
        }
    except Exception as e:
        error_msg = str(e)
        duration_ms = int((time.time() - start_time) * 1000)
        await update_api_record(
            request_id, status="fail", result="slider_fail",
            failure_reason="service_unavailable", error_message=error_msg,
            duration_ms=duration_ms,
        )
        return {
            "status": "service_unavailable", "solved": False, "captchaDetected": False,
            "attempts": 0, "durationMs": duration_ms, "cookies": None, "error": error_msg,
        }

    solve_ok = bool(data.get("ok"))
    solved = bool(data.get("solved"))
    captcha_detected = bool(data.get("captchaDetected"))
    attempts = int(data.get("attempts") or 0)
    crawler_error = data.get("error") or ""
    fresh_cookies = data.get("cookies") or ""
    duration_ms = int((time.time() - start_time) * 1000)

    # 错误分类
    if solve_ok and solved:
        status = "success"
        result = "slider_success"
        failure_reason = ""
        error_message = ""
    elif "Cookie Session 已过期" in crawler_error or "登录页" in crawler_error:
        status = "fail"
        result = "slider_fail"
        failure_reason = "cookie_invalid"
        error_message = crawler_error
    elif _is_browser_launch_failure(crawler_error):
        status = "fail"
        result = "slider_fail"
        failure_reason = "service_unavailable"
        error_message = crawler_error
    else:
        status = "fail"
        result = "slider_fail"
        failure_reason = "slider_fail"
        error_message = crawler_error or "滑块求解未通过"

    await update_api_record(
        request_id, status=status, result=result,
        failure_reason=failure_reason, error_message=error_message,
        duration_ms=duration_ms,
    )

    return {
        "status": status,
        "solved": solved,
        "captchaDetected": captcha_detected,
        "attempts": attempts,
        "durationMs": duration_ms,
        "cookies": fresh_cookies if solve_ok and solved else None,
        "error": None if solve_ok and solved else error_message,
    }
