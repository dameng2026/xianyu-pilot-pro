"""
Phase 3b: Rewrite internal.py - remove all workflow/automation_runtime-dependent endpoints.
Keep only: /health, /qrlogin/* endpoints (with tenant_id/user_id checks removed).
"""
import os

INTERNAL_PATH = r'G:\源码\项目借鉴\xianyu-assistant-opensource\apps\api\app\api\v1\routes\internal.py'

new_content = '''import logging
import hmac
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.config import settings
from ....core.database import get_db
from ....core.response import ResultObject

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/internal")


def verify_internal_token(x_internal_token: Optional[str] = Header(None)) -> None:
    """内部接口保护。Phase 1 起 fail-closed：令牌为空或不匹配均拒绝。"""
    if not x_internal_token:
        raise HTTPException(status_code=401, detail="暂未登录或token已经过期")

    expected = (getattr(settings, "internal_api_token", "") or "").strip()
    if not expected:
        logger.error("INTERNAL_API_TOKEN 未配置，拒绝内部接口调用")
        raise HTTPException(status_code=503, detail="INTERNAL_API_TOKEN is not configured")
    if not hmac.compare_digest(str(x_internal_token), expected):
        raise HTTPException(status_code=403, detail="invalid internal token")


@router.get("/health")
async def internal_health(_: None = Depends(verify_internal_token)):
    return ResultObject.success({
        "service": "automation-service",
        "status": "ok",
        "boundary": "python-execution-only",
    })


# ---- Java 网关转发扫码登录：Python 执行扫码流程并保存 Cookie ----
@router.post("/qrlogin/generate")
async def internal_qrlogin_generate(
    body: dict = {},
    _: None = Depends(verify_internal_token),
):
    try:
        from ....core.xianyu_qr_login import generate_qrcode
        result = generate_qrcode()
        if "qrImage" in result and "qrCodeBase64" not in result:
            result["qrCodeBase64"] = result["qrImage"]
        result.setdefault("status", "pending")
        result.setdefault("message", "请使用闲鱼 App 扫码登录")
        return ResultObject.success(result)
    except Exception as e:
        logger.error("internal qr generate failed", exc_info=True)
        return ResultObject.failed(f"生成闲鱼登录二维码失败: {str(e)}")


@router.post("/qrlogin/status/{session_id}")
async def internal_qrlogin_status(
    session_id: str,
    body: dict = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    try:
        from ....core.xianyu_qr_login import get_session_context, get_session_status, cleanup_session
        from .misc import _save_scan_login_result

        ctx = get_session_context(session_id)
        if ctx is None:
            return ResultObject.success({"status": "expired", "message": "会话不存在或已过期"})

        result = get_session_status(session_id)
        if result.get("status") == "confirmed":
            if body.get("accountId") is not None:
                result["accountId"] = body.get("accountId")
                result["message"] = "扫码登录成功，等待更新账号 Cookie"
                return ResultObject.success(result)
            save_result = await _save_scan_login_result(session_id, db)
            if not save_result:
                result["status"] = "error"
                result["message"] = "账号保存失败，请重试"
            elif save_result.get("_error"):
                result["status"] = "error"
                result["message"] = save_result.get("message", "账号保存失败，请重试")
                result["errorCode"] = save_result.get("_error")
            else:
                result["accountId"] = save_result.get("account_id")
                result["cookieStatus"] = save_result.get("cookie_status")
                result["expireTime"] = save_result.get("expire_time")
                result["message"] = "扫码登录成功，账号已保存"
                cleanup_session(session_id)
        return ResultObject.success(result)
    except Exception as e:
        logger.error("internal qr status failed", exc_info=True)
        return ResultObject.failed(str(e))


@router.get("/qrlogin/cookies/{session_id}")
async def internal_qrlogin_cookies(
    session_id: str,
    body: dict = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    try:
        from ....core.xianyu_qr_login import get_session_context, get_session_cookies

        ctx = get_session_context(session_id)
        if ctx is None:
            return ResultObject.success({"status": "expired", "message": "会话不存在或已过期"})

        result = get_session_cookies(session_id)
        if not result:
            return ResultObject.success({"status": "expired", "message": "会话不存在或已过期"})
        return ResultObject.success(result)
    except Exception as e:
        logger.error("internal qr cookies failed", exc_info=True)
        return ResultObject.failed(str(e))


@router.post("/qrlogin/cookies/{session_id}")
async def internal_qrlogin_cookies_post(
    session_id: str,
    body: dict = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    return await internal_qrlogin_cookies(session_id, body, db, _)


@router.post("/qrlogin/cleanup")
async def internal_qrlogin_cleanup(
    body: dict = {},
    _: None = Depends(verify_internal_token),
):
    try:
        from ....core.xianyu_qr_login import cleanup_expired_sessions

        cleanup_expired_sessions()
        return ResultObject.success({"status": "ok"})
    except Exception as e:
        logger.error("internal qr cleanup failed", exc_info=True)
        return ResultObject.failed(str(e))
'''

with open(INTERNAL_PATH, 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f"OK: rewrote internal.py ({len(new_content)} bytes)")
print("Removed: all workflow/task/order/delivery/message/ws-heartbeat/business-opportunity endpoints")
print("Kept: /health, /qrlogin/* endpoints (tenant_id/user_id checks removed)")
