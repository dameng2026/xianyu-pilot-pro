import logging
import os
import asyncio
import datetime
import hashlib
import ipaddress
import io
from datetime import timedelta
from typing import Optional
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, UploadFile, File, Form, Query
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, and_, or_, text
from ....core.database import get_db
from ....core.http_failures import safe_route_failure
from ....core.image_security import MAX_IMAGE_BYTES, ValidatedImage, download_public_image, validate_image_bytes
from ....services.upload_governance import (
    ALLOWED_PUBLIC_UPLOAD_PURPOSES,
    UploadGovernanceError,
    store_governed_image,
)
from ....core.response import ResultObject
from ....core.config import settings
from ....core.cookie_crypto import decrypt_cookie_if_needed, encrypt_cookie_for_storage
from ....models.entities import (
    XianyuOperationLog, XianyuAccount,
    XianyuAccountAuth, XianyuAccountRuntime,
    XianyuGoods, XianyuTradeOrder, Notification
)
from ....services.ws_client import ws_manager
from ....services.ws_storage import save_chat_message
from ....services.ws_sse import broadcaster
from ....services.automation_runtime import update_ws_heartbeat
from ....core.xianyu_qr_login import (
    cleanup_sessions_for_owner,
    generate_qrcode,
    get_session_context,
    get_session_cookies,
    get_session_status,
)
from ....core.cookie_crypto import encrypt_cookie_for_storage
from ....models.entities import XianyuAccount, XianyuAccountAuth
from ....services.xianyu_goods_sync import (
    _make_api_request as _xianyu_mtop_request,
    _get_token_from_cookie as _xianyu_token_from_cookie,
    _normalize_mtop_search_item,
    _resolve_account_cookie,
    SEARCH_MTOP_API,
    TOKEN_EXPIRED as _XIANYU_TOKEN_EXPIRED,
    TOKEN_EXPIRED_ALIAS as _XIANYU_TOKEN_EXPIRED_ALIAS,
    RGV587 as _XIANYU_RGV587,
)
from ....services.auto_category import upload_image_to_xianyu as _upload_image_to_xianyu
from ..deps import get_current_user

logger = logging.getLogger(__name__)

_IMAGE_UPLOAD_BASE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "../../../../uploads/images")
)


def _normalize_safe_goofish_id(value: object) -> str:
    text_value = str(value or "").strip()
    if not text_value:
        return ""
    if text_value.startswith("sid:"):
        text_value = text_value[4:]
    if text_value.endswith("@goofish"):
        text_value = text_value[:-8]
    return text_value.strip()


def _to_goofish_id(value: object) -> str:
    normalized = _normalize_safe_goofish_id(value)
    if not normalized:
        return ""
    return normalized if normalized.endswith("@goofish") else f"{normalized}@goofish"


def _parse_account_id(value: object) -> Optional[int]:
    try:
        if value is None:
            return None
        text_value = str(value).strip()
        if not text_value:
            return None
        return int(text_value)
    except Exception:
        return None


def _is_ws_auth_failure(status: dict) -> bool:
    phase = str(status.get("phase") or status.get("status") or "").lower()
    last_error = str(status.get("lastError") or status.get("last_error") or "")
    if phase in {"token_failed", "register_failed", "auth_failed", "captcha", "expired"}:
        return True
    hints = ("滑块", "验证", "captcha", "过期", "token", "cookie", "rgv587", "login", "登录")
    return any(hint.lower() in last_error.lower() for hint in hints)


def _ws_auth_failure_message(status: dict) -> str:
    return "连接失败：账号登录状态失效或需要安全验证，请更新 Cookie 或扫码重新登录。"


def _is_ws_connection_failed(status: dict) -> bool:
    """识别 WS 客户端已进入明确失败状态（非认证失败的连接失败）。

    与 _is_ws_auth_failure 的区别：
    - auth_failure: Cookie/Token/滑块问题，可触发滑块自动求解
    - connection_failed: 网络错误、连接关闭、已停止等通用失败，不应触发滑块求解

    ws_client.py 中 phase 可能值：created/starting/stopped/refresh_token/token_failed/
    connecting/connected_socket/registering/register_failed/syncing/connected/
    closed/error/auth_failed/captcha/expired。
    其中 closed/error/stopped/disconnected/not_started 为通用失败，未被
    _is_ws_auth_failure 覆盖，会导致 _wait_ws_connect_result 空等 12 秒超时。
    """
    phase = str((status or {}).get("phase") or (status or {}).get("status") or "").lower()
    return phase in {"closed", "error", "stopped", "disconnected", "not_started"}


def _safe_ws_phase(status: dict) -> str:
    phase = str((status or {}).get("phase") or (status or {}).get("status") or "").lower()
    allowed = {
        "connected", "connecting", "registering", "disconnected", "stopped",
        "auth_failed", "token_failed", "register_failed", "captcha", "expired",
    }
    return phase if phase in allowed else "unknown"


def _safe_ws_last_error(status: dict) -> str:
    return _ws_auth_failure_message(status) if _is_ws_auth_failure(status or {}) else ""


async def _account_belongs_to_tenant(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    user_id: Optional[int] = None,
) -> bool:
    query = select(XianyuAccount.id).where(
        XianyuAccount.id == account_id,
        XianyuAccount.tenant_id == tenant_id,
        XianyuAccount.deleted == 0,
    )
    try:
        scoped_user_id = int(user_id) if user_id is not None else 0
    except (TypeError, ValueError):
        scoped_user_id = 0
    if scoped_user_id > 0:
        query = query.where(
            or_(XianyuAccount.user_id == scoped_user_id, XianyuAccount.user_id.is_(None))
        )
    result = await db.execute(query)
    return result.scalar_one_or_none() is not None


async def _load_ws_credentials(db: AsyncSession, tenant_id: int, account_id: int, allow_unverified: bool = False):
    """从数据库读取账号最新 Cookie/Token，用于手动重连和发送前自愈。"""
    await db.execute(
        text("""
            UPDATE xianyu_account_auth auth
            JOIN xianyu_account a
              ON a.id = auth.account_id
             AND a.tenant_id = auth.tenant_id
            SET auth.deleted = 0,
                auth.updated_time = NOW()
            WHERE a.id = :account_id
              AND a.tenant_id = :tenant_id
              AND a.deleted = 0
              AND COALESCE(auth.deleted, 0) = 1
        """),
        {"tenant_id": tenant_id, "account_id": account_id},
    )
    result = await db.execute(
        text("""
            SELECT a.external_uid AS unb,
                   auth.encrypted_cookie AS encrypted_cookie,
                   auth.encrypted_token AS encrypted_token,
                   COALESCE(auth.cookie_status, 0) AS cookie_status,
                   auth.last_login_status_code AS login_status_code
            FROM xianyu_account a
            JOIN xianyu_account_auth auth
              ON auth.account_id = a.id AND auth.tenant_id = a.tenant_id
            WHERE a.id = :account_id
              AND a.tenant_id = :tenant_id
              AND a.deleted = 0
              AND COALESCE(auth.deleted, 0) = 0
            ORDER BY COALESCE(auth.updated_time, auth.created_time) DESC, auth.id DESC
            LIMIT 1
        """),
        {"tenant_id": tenant_id, "account_id": account_id},
    )
    row = result.mappings().first()
    if not row:
        return None, "账号未找到或未保存登录凭证"

    cookie_str = decrypt_cookie_if_needed(row.get("encrypted_cookie") or "")
    m_h5_tk = (decrypt_cookie_if_needed(row.get("encrypted_token") or "") or "").strip()
    if not m_h5_tk:
        m_h5_tk = _xianyu_token_from_cookie(cookie_str) or ""
    if not cookie_str:
        return None, "账号缺少 Cookie，请自行提供 Cookie 或扫码重新登录"
    if not m_h5_tk:
        return None, "Cookie 中缺少 _m_h5_tk，请自行提供 Cookie 或扫码重新登录"
    if (
        not allow_unverified
        and (
            int(row.get("cookie_status") or 0) != 1
            or str(row.get("login_status_code") or "").upper() != "OK"
        )
    ):
        return None, "账号 Cookie 尚未通过统一登录校验，请先在账号管理或连接管理页执行校验"
    return {
        "cookie_str": cookie_str,
        "m_h5_tk": m_h5_tk,
        "unb": row.get("unb") or "",
        "cookie_status": int(row.get("cookie_status") or 0),
        "login_status_code": row.get("login_status_code"),
    }, None


async def _restart_ws_client_from_db(db: AsyncSession, tenant_id: int, account_id: int, allow_unverified: bool = False):
    creds, error = await _load_ws_credentials(db, tenant_id, account_id, allow_unverified=allow_unverified)
    if error:
        return None, error
    try:
        await ws_manager.start_client(
            account_id=account_id,
            tenant_id=tenant_id,
            cookie_str=creds["cookie_str"],
            m_h5_tk=creds["m_h5_tk"],
            unb=creds["unb"],
        )
        return ws_manager.get_client(account_id), None
    except Exception as exc:
        logger.error(
            "重建 WebSocket 客户端失败 accountId=%s errorType=%s",
            account_id,
            type(exc).__name__,
        )
        return None, "WebSocket 连接服务暂时不可用，请稍后重试"


async def _precheck_ws_token(db: AsyncSession, tenant_id: int, account_id: int, allow_unverified: bool = False):
    """连接前同步预检 WS Token，快速判断 Cookie 是否能通过闲鱼消息页面验证。

    在启动后台 WS 客户端之前，先同步调用 Token API 探测 Cookie 状态：
    - 成功：返回 (True, None)，继续启动 WS 客户端
    - 滑块验证：返回 (False, "captcha")，Cookie 触发风控，需重新登录
    - Session 过期：返回 (False, "expired")，Cookie 已失效，需重新登录
    - Token 缺失：返回 (False, "token_missing")，Cookie 缺少 _m_h5_tk

    这样可以避免 Cookie 已失效时还要空等 12 秒才返回 pending。
    """
    creds, error = await _load_ws_credentials(db, tenant_id, account_id, allow_unverified=allow_unverified)
    if error:
        return False, ("creds_error", error)
    try:
        from app.services.ws_token import get_ws_token_with_refreshed_m_h5_tk
        access_token, effective_m_h5_tk, error_type, refreshed_cookie = get_ws_token_with_refreshed_m_h5_tk(
            creds["cookie_str"], creds["m_h5_tk"]
        )
        if access_token:
            return True, None
        if error_type == "captcha":
            return False, ("captcha", "Cookie 已触发滑块验证，请重新扫码登录或手动更新 Cookie")
        if error_type == "expired":
            return False, ("expired", "Cookie Session 已过期，请重新扫码登录闲鱼账号")
        return False, ("unknown", "获取 WebSocket Token 失败，请检查 Cookie 或重新登录")
    except Exception as exc:
        logger.error("_precheck_ws_token 异常 accountId=%d errorType=%s", account_id, type(exc).__name__)
        return False, ("error", "Token 预检服务暂时不可用，请稍后重试")


async def _wait_ws_connect_result(account_id: int, timeout_seconds: float = 12.0):
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    last_status = ws_manager.get_status(account_id)
    while asyncio.get_event_loop().time() < deadline:
        client = ws_manager.get_client(account_id)
        last_status = ws_manager.get_status(account_id)
        if client and getattr(client, "is_connected", False):
            return "connected", last_status
        if _is_ws_auth_failure(last_status):
            return "auth_failed", last_status
        if _is_ws_connection_failed(last_status):
            return "failed", last_status
        await asyncio.sleep(0.2)
    return "pending", last_status


async def _resolve_ws_sid(db: AsyncSession, tenant_id: int, account_id: int, raw_cid: object) -> str:
    cid = _normalize_safe_goofish_id(raw_cid)
    if not cid:
        return ""

    logger.info(
        "_resolve_ws_sid 输入: accountId=%d referencePresent=%s",
        account_id,
        bool(cid),
    )

    direct_result = await db.execute(
        text("""
            SELECT s_id FROM xianyu_chat_message
            WHERE tenant_id = :tenant_id AND account_id = :account_id
              AND deleted = 0
              AND s_id COLLATE utf8mb4_unicode_ci = :cid COLLATE utf8mb4_unicode_ci
            ORDER BY message_time DESC LIMIT 1
        """),
        {"tenant_id": tenant_id, "account_id": account_id, "cid": cid}
    )
    direct_row = direct_result.mappings().first()
    if direct_row and direct_row.get("s_id"):
        result = str(direct_row["s_id"])
        logger.info("_resolve_ws_sid Query1 命中")
        return result

    logger.info("_resolve_ws_sid Query1 未命中，进入 Query2")

    lookup_result = await db.execute(
        text("""
            SELECT s_id FROM xianyu_chat_message
            WHERE tenant_id = :tenant_id AND account_id = :account_id
              AND deleted = 0
              AND (
                  sender_user_id COLLATE utf8mb4_unicode_ci = :cid COLLATE utf8mb4_unicode_ci
                  OR receiver_user_id COLLATE utf8mb4_unicode_ci = :cid COLLATE utf8mb4_unicode_ci
                  OR peer_external_uid COLLATE utf8mb4_unicode_ci = :cid COLLATE utf8mb4_unicode_ci
              )
            ORDER BY message_time DESC LIMIT 1
        """),
        {"tenant_id": tenant_id, "account_id": account_id, "cid": cid}
    )
    lookup_row = lookup_result.mappings().first()
    if lookup_row and lookup_row.get("s_id"):
        result = str(lookup_row["s_id"])
        logger.info("_resolve_ws_sid Query2 命中")
        return result

    logger.info("_resolve_ws_sid 未命中任何查询，使用请求会话引用")
    return cid


async def _resolve_ws_peer_id(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    ws_sid: str,
    raw_to_id: object,
    own_id: str,
) -> str:
    bare_sid = _normalize_safe_goofish_id(ws_sid)
    direct_to_id = _normalize_safe_goofish_id(raw_to_id)
    # 如果传入的 to_id 是有效的真实用户 ID（不是 sid 本身），直接使用
    if direct_to_id and direct_to_id != bare_sid:
        return direct_to_id
    if not bare_sid:
        return ""

    conv_result = await db.execute(
        text("""
            SELECT c.external_buyer_id, c.peer_external_uid, c.peer_key
            FROM xianyu_conversation c
            WHERE c.tenant_id = :tenant_id AND c.account_id = :account_id
              AND (
                  c.peer_key COLLATE utf8mb4_unicode_ci = CONCAT('sid:', :sid) COLLATE utf8mb4_unicode_ci
                  OR c.external_buyer_id COLLATE utf8mb4_unicode_ci = CONCAT('sid:', :sid) COLLATE utf8mb4_unicode_ci
                  OR EXISTS (
                      SELECT 1 FROM xianyu_chat_message xm
                      WHERE xm.tenant_id = c.tenant_id
                        AND xm.account_id = c.account_id
                        AND xm.s_id COLLATE utf8mb4_unicode_ci = :sid COLLATE utf8mb4_unicode_ci
                  )
              )
            ORDER BY c.id DESC LIMIT 1
        """),
        {"tenant_id": tenant_id, "account_id": account_id, "sid": bare_sid}
    )
    conv_row = conv_result.mappings().first()
    if conv_row:
        for key in ("peer_external_uid", "external_buyer_id", "peer_key"):
            candidate = _normalize_safe_goofish_id(conv_row.get(key))
            if candidate and candidate != own_id:
                return candidate

    msg_result = await db.execute(
        text("""
            SELECT sender_user_id, receiver_user_id, peer_external_uid
            FROM xianyu_chat_message
            WHERE tenant_id = :tenant_id AND account_id = :account_id
              AND s_id COLLATE utf8mb4_unicode_ci = :sid COLLATE utf8mb4_unicode_ci
              AND deleted = 0
            ORDER BY message_time DESC LIMIT 20
        """),
        {"tenant_id": tenant_id, "account_id": account_id, "sid": bare_sid}
    )
    for row in msg_result.mappings().all():
        for key in ("peer_external_uid", "sender_user_id", "receiver_user_id"):
            candidate = _normalize_safe_goofish_id(row.get(key))
            if candidate and candidate != own_id:
                return candidate

    return ""


async def _resolve_ws_goods_id(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    ws_sid: str,
    raw_goods_id: object,
) -> str:
    direct_goods_id = str(raw_goods_id or "").strip()
    if direct_goods_id:
        return direct_goods_id
    bare_sid = _normalize_safe_goofish_id(ws_sid)
    if not bare_sid:
        return ""

    msg_result = await db.execute(
        text("""
            SELECT xy_goods_id
            FROM xianyu_chat_message
            WHERE tenant_id = :tenant_id AND account_id = :account_id
              AND s_id COLLATE utf8mb4_unicode_ci IN (:sid, :sid_goofish)
              AND deleted = 0
              AND xy_goods_id IS NOT NULL
              AND xy_goods_id != ''
            ORDER BY message_time DESC, id DESC
            LIMIT 1
        """),
        {
            "tenant_id": tenant_id,
            "account_id": account_id,
            "sid": bare_sid,
            "sid_goofish": f"{bare_sid}@goofish",
        }
    )
    msg_row = msg_result.mappings().first()
    if msg_row and msg_row.get("xy_goods_id"):
        return str(msg_row.get("xy_goods_id") or "").strip()

    conv_result = await db.execute(
        text("""
            SELECT goods_id
            FROM xianyu_conversation
            WHERE tenant_id = :tenant_id AND account_id = :account_id
              AND (
                  peer_key COLLATE utf8mb4_unicode_ci IN (:sid_key, :sid_key_goofish)
                  OR external_buyer_id COLLATE utf8mb4_unicode_ci IN (:sid_key, :sid_key_goofish)
              )
              AND goods_id IS NOT NULL
              AND goods_id != ''
            ORDER BY id DESC
            LIMIT 1
        """),
        {
            "tenant_id": tenant_id,
            "account_id": account_id,
            "sid_key": f"sid:{bare_sid}",
            "sid_key_goofish": f"sid:{bare_sid}@goofish",
        }
    )
    conv_row = conv_result.mappings().first()
    if conv_row and conv_row.get("goods_id"):
        return str(conv_row.get("goods_id") or "").strip()

    return ""


def _validate_safe_https_image_url(image_url: str) -> str:
    """Return empty string when safe, otherwise a user-facing validation message."""
    if not image_url or len(image_url) > 500:
        return "图片链接不能为空且不能超过500个字符"
    parsed = urlparse(image_url)
    if parsed.scheme != "https" or not parsed.netloc:
        return "图片链接仅支持 HTTPS 地址"
    host = (parsed.hostname or "").lower()
    if host in {"localhost"} or host.endswith(".localhost"):
        return "不允许发送本机或内网图片地址"
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            return "不允许发送本机或内网图片地址"
    except ValueError:
        pass
    return ""


def _read_uploaded_image_bytes(image_url: str, tenant_id: int | None = None) -> bytes:
    prefix = "/uploads/images/"
    if not image_url.startswith(prefix):
        raise ValueError("仅支持发送本地上传目录中的图片")
    relative_path = image_url[len(prefix):]
    if not relative_path or "\\" in relative_path:
        raise ValueError("本地上传图片路径无效")
    normalized = os.path.normpath(relative_path).replace("\\", "/")
    if normalized != relative_path or normalized.startswith("../") or normalized.startswith("/"):
        raise ValueError("本地上传图片路径无效")
    first_segment = normalized.split("/", 1)[0]
    if tenant_id is not None and first_segment != f"tenant-{int(tenant_id)}":
        raise ValueError("无权访问其他租户的上传图片")
    base_path = os.path.realpath(_IMAGE_UPLOAD_BASE_DIR)
    local_path = os.path.realpath(os.path.join(base_path, normalized))
    if os.path.commonpath([base_path, local_path]) != base_path:
        raise ValueError("本地上传图片路径无效")
    if not os.path.exists(local_path) or not os.path.isfile(local_path):
        raise ValueError("未找到本地上传图片，请重新上传后再发送")
    with open(local_path, "rb") as file_obj:
        data = file_obj.read(MAX_IMAGE_BYTES + 1)
    try:
        return validate_image_bytes(data).content
    except ValueError as exc:
        raise ValueError("本地上传图片无效或超过 5MB，请重新上传") from exc


async def _read_active_uploaded_image_bytes(
    db: AsyncSession,
    image_url: str,
    tenant_id: int,
) -> bytes:
    """Load a tenant-owned image only while its durable asset row is active."""

    prefix = "/uploads/images/"
    normalized = str(image_url or "").strip()
    if not normalized.startswith(prefix):
        raise ValueError("local image URL is outside the managed upload namespace")
    storage_key = normalized[len(prefix):]
    if not storage_key or storage_key.split("/", 1)[0] != f"tenant-{int(tenant_id)}":
        raise ValueError("local image URL does not belong to the current tenant")
    result = await db.execute(text(
        "SELECT size_bytes, sha256 FROM tenant_storage_asset "
        "WHERE tenant_id=:tenant_id AND storage_key=:storage_key "
        "AND public_url=:public_url AND status='active' LIMIT 1"
    ), {
        "tenant_id": int(tenant_id),
        "storage_key": storage_key,
        "public_url": normalized,
    })
    row = result.mappings().first()
    if not row:
        raise ValueError("local image asset is unavailable")
    content = await asyncio.to_thread(_read_uploaded_image_bytes, normalized, tenant_id)
    expected_size = int(row.get("size_bytes") or 0)
    expected_sha256 = str(row.get("sha256") or "").strip().lower()
    if expected_size <= 0 or len(content) != expected_size:
        raise ValueError("local image asset does not match its storage record")
    if len(expected_sha256) != 64 or hashlib.sha256(content).hexdigest() != expected_sha256:
        raise ValueError("local image asset does not match its storage record")
    return content


def _resolve_outbound_image_dimensions(
    image_url: str,
    tenant_id: int | None = None,
) -> tuple[int, int]:
    normalized = str(image_url or "").strip()
    if not normalized.startswith("/uploads/"):
        return 800, 600
    try:
        image_data = _read_uploaded_image_bytes(normalized, tenant_id)
        with Image.open(io.BytesIO(image_data)) as image_obj:
            width, height = image_obj.size
        return max(int(width or 800), 1), max(int(height or 600), 1)
    except Exception as exc:
        logger.warning(
            "读取待发送图片尺寸失败，使用默认尺寸 errorType=%s",
            type(exc).__name__,
        )
        return 800, 600


async def _resolve_outbound_image_url(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    image_url: str,
) -> str:
    normalized = str(image_url or "").strip()
    if not normalized:
        raise ValueError("图片链接不能为空")
    if normalized.startswith("/uploads/"):
        creds, error = await _load_ws_credentials(db, tenant_id, account_id)
        if error:
            raise ValueError(error)
        image_data = await _read_active_uploaded_image_bytes(db, normalized, tenant_id)
        cdn_url, _, _ = await asyncio.to_thread(_upload_image_to_xianyu, creds["cookie_str"], image_data)
        url_error = _validate_safe_https_image_url(cdn_url)
        if url_error:
            raise ValueError(url_error)
        return cdn_url
    url_error = _validate_safe_https_image_url(normalized)
    if url_error:
        raise ValueError(url_error)
    return normalized


# ---- QR 登录后自动启动 WebSocket ----
def _schedule_ws_start(account_id: int, tenant_id: int):
    import asyncio as _asyncio
    logger.info("QR 后调度 WS 启动: accountId=%d tenantId=%d", account_id, tenant_id)
    try:
        loop = _asyncio.get_running_loop()
        loop.create_task(_do_start_ws(account_id, tenant_id))
    except RuntimeError:
        logger.error("QR 后无法获取运行中的事件循环，尝试用 asyncio.run")
        _asyncio.run(_do_start_ws(account_id, tenant_id))


async def _do_start_ws(account_id: int, tenant_id: int):
    try:
        from ....core.database import async_session
        async with async_session() as ws_db:
            auth_result = await ws_db.execute(
                select(XianyuAccountAuth).where(
                    XianyuAccountAuth.account_id == account_id,
                    XianyuAccountAuth.tenant_id == tenant_id,
                )
            )
            auth = auth_result.scalar_one_or_none()
            if not auth or not auth.encrypted_cookie:
                logger.warning("QR 后自动启动 WS 失败: 无 auth accountId=%d", account_id)
                return

            acc_result = await ws_db.execute(
                select(XianyuAccount).where(
                    XianyuAccount.id == account_id,
                    XianyuAccount.tenant_id == tenant_id,
                )
            )
            acc = acc_result.scalar_one_or_none()
            unb = acc.external_uid if acc else ""

            from ....services.ws_startup import on_message_callback
            ws_manager.set_message_callback(on_message_callback)
            await ws_manager.start_client(
                account_id=account_id,
                tenant_id=tenant_id,
                cookie_str=decrypt_cookie_if_needed(auth.encrypted_cookie),
                m_h5_tk=decrypt_cookie_if_needed(auth.encrypted_token or "") or "",
                unb=unb,
            )
            await update_ws_heartbeat(ws_db, {
                "tenantId": tenant_id,
                "accountId": account_id,
                "onlineStatus": 1,
                "wsStatus": 1,
                "latency": 0,
            })
            await ws_db.commit()
            logger.info("QR 登录后 WebSocket 已启动: accountId=%d", account_id)
    except Exception as e:
        logger.error("QR 后自动启动 WS 异常 accountId=%d errorType=%s", account_id, type(e).__name__)


async def _save_scan_login_result(session_id: str, db: AsyncSession) -> dict:
    """保存扫码登录成功后获取到的 Cookie 到数据库。

    从扫码登录会话中提取 Cookie 数据，创建或更新 XianyuAccount 和 XianyuAccountAuth 记录。
    返回: {"account_id": int, "cookie_status": int, "expire_time": str, ...} 或 {"_error": str, "message": str}
    """
    try:
        session_data = get_session_cookies(session_id)
        if not session_data:
            return {"_error": "SESSION_MISSING", "message": "会话不存在或尚未登录成功"}

        cookie_text = session_data.get("cookie_text", "")
        unb = session_data.get("unb", "")
        m_h5_tk = session_data.get("m_h5_tk", "")
        user_id = session_data.get("user_id")
        tenant_id = session_data.get("tenant_id")

        if not unb:
            return {"_error": "NO_UNB", "message": "Cookie 中未提取到 unb"}
        if not tenant_id:
            return {"_error": "NO_TENANT", "message": "缺少租户信息"}
        if not user_id:
            return {"_error": "NO_USER", "message": "缺少用户信息"}

        # 检查账号是否已存在（包含软删除的记录）
        # 先查所有记录（含 deleted=1），避免因唯一约束导致插入失败
        result = await db.execute(
            select(XianyuAccount).where(
                XianyuAccount.external_uid == unb,
                XianyuAccount.tenant_id == tenant_id,
            ).order_by(XianyuAccount.deleted.asc()).limit(1)
        )
        existing_account = result.scalar_one_or_none()

        if existing_account:
            account = existing_account
            if existing_account.deleted == 1:
                # 恢复软删除的账号
                existing_account.deleted = 0
                existing_account.status = 1
                existing_account.user_id = user_id
                logger.info("扫码登录: 恢复软删除账号 accountId=%d", account.id)
            else:
                logger.info("扫码登录: 账号已存在 accountId=%d", account.id)
        else:
            account = XianyuAccount(
                tenant_id=tenant_id,
                user_id=user_id,
                platform="xianyu",
                external_uid=unb,
                status=1,
            )
            db.add(account)
            await db.commit()
            await db.refresh(account)
            logger.info("扫码登录: 新建账号 accountId=%d", account.id)

        # 加密并保存 Cookie
        encrypted_cookie = encrypt_cookie_for_storage(cookie_text)
        encrypted_token = encrypt_cookie_for_storage(m_h5_tk) if m_h5_tk else None

        # 检查 auth 记录是否已存在
        auth_result = await db.execute(
            select(XianyuAccountAuth).where(
                XianyuAccountAuth.account_id == account.id,
                XianyuAccountAuth.tenant_id == tenant_id,
            ).order_by(XianyuAccountAuth.deleted.asc(), XianyuAccountAuth.id.desc()).limit(1)
        )
        existing_auth = auth_result.scalar_one_or_none()

        if existing_auth:
            existing_auth.deleted = 0
            existing_auth.encrypted_cookie = encrypted_cookie
            if encrypted_token:
                existing_auth.encrypted_token = encrypted_token
            existing_auth.cookie_status = 1
            existing_auth.last_login_status_code = "OK"
            existing_auth.last_login_status_message = "账号登录状态正常"
            existing_auth.last_login_check_time = func.now()
        else:
            auth = XianyuAccountAuth(
                tenant_id=tenant_id,
                account_id=account.id,
                encrypted_cookie=encrypted_cookie,
                encrypted_token=encrypted_token,
                cookie_status=1,
                last_login_status_code="OK",
                last_login_status_message="账号登录状态正常",
                last_login_check_time=func.now(),
            )
            db.add(auth)

        runtime_result = await db.execute(
            select(XianyuAccountRuntime).where(
                XianyuAccountRuntime.account_id == account.id,
                XianyuAccountRuntime.tenant_id == tenant_id,
            ).order_by(XianyuAccountRuntime.deleted.asc(), XianyuAccountRuntime.id.desc()).limit(1)
        )
        existing_runtime = runtime_result.scalar_one_or_none()
        if existing_runtime:
            existing_runtime.deleted = 0
            existing_runtime.cookie_status = 1
            existing_runtime.last_login_status_code = "OK"
            existing_runtime.last_login_status_message = "账号登录状态正常"
            existing_runtime.last_login_check_time = func.now()
        else:
            db.add(XianyuAccountRuntime(
                tenant_id=tenant_id,
                account_id=account.id,
                cookie_status=1,
                last_login_status_code="OK",
                last_login_status_message="账号登录状态正常",
                last_login_check_time=func.now(),
            ))

        await db.commit()

        # 扫码登录成功后 cookie_status=1，清除账号状态通知去重标记（内存 + DB）。
        try:
            from app.services.notify_dispatcher import clear_all_account_status_notifications
            await clear_all_account_status_notifications(tenant_id, int(account.id))
        except Exception:
            logger.debug("clear_all_account_status_notifications 调用异常，忽略", exc_info=True)

        return {
            "account_id": account.id,
            "cookie_status": 1,
            "expire_time": None,
        }
    except Exception as e:
        logger.error("保存扫码登录结果失败 errorType=%s", type(e).__name__, exc_info=True)
        return {"_error": "SAVE_FAILED", "message": "账号保存失败，请稍后重试"}


media_router = APIRouter(prefix="/media")
image_router = APIRouter(prefix="/image")
captcha_router = APIRouter(prefix="/captcha")
backup_router = APIRouter(prefix="/backup")
excel_router = APIRouter(prefix="/excel")
goods_sku_router = APIRouter(prefix="/goods-sku")
business_router = APIRouter(prefix="/business-opportunity")
data_panel_router = APIRouter(prefix="/data-panel")
navigation_router = APIRouter(prefix="/navigation")
qrlogin_router = APIRouter(prefix="/qrlogin")


def _qr_owner(current_user: dict) -> tuple[Optional[int], Optional[int]]:
    try:
        user_id = int(current_user.get("user_id"))
        tenant_id = int(current_user.get("tenant_id"))
    except (TypeError, ValueError):
        return None, None
    if user_id <= 0 or tenant_id <= 0:
        return None, None
    return user_id, tenant_id


# ---- QR Login (用户端路由, 前端直接调用) ----
@qrlogin_router.post("/generate")
async def qrlogin_generate(
    current_user: dict = Depends(get_current_user)
):
    try:
        user_id, tenant_id = _qr_owner(current_user)
        if user_id is None or tenant_id is None:
            return ResultObject.unauthorized()
        result = generate_qrcode(user_id=user_id, tenant_id=tenant_id)
        if "qrImage" in result and "qrCodeBase64" not in result:
            result["qrCodeBase64"] = result["qrImage"]
        return ResultObject.success(result)
    except Exception as e:
        logger.error("生成二维码失败 errorType=%s", type(e).__name__)
        return ResultObject.failed("生成登录二维码失败，请稍后重试", code=503)


@qrlogin_router.post("/status/{session_id}")
async def qrlogin_status(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        from ....core.xianyu_qr_login import cleanup_session

        user_id, tenant_id = _qr_owner(current_user)
        if user_id is None or tenant_id is None:
            return ResultObject.unauthorized()

        ctx = get_session_context(session_id)
        if ctx is None:
            return ResultObject.success({"status": "expired", "message": "会话不存在或已过期"})
        if ctx.get("user_id") != user_id or ctx.get("tenant_id") != tenant_id:
            return ResultObject.failed("无权访问此扫码登录会话", code=403)

        result = get_session_status(session_id)
        # 扫码确认后自动保存到数据库
        if result.get("status") == "confirmed":
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
        logger.error("查询二维码状态失败 errorType=%s", type(e).__name__, exc_info=True)
        return ResultObject.failed("登录状态查询失败，请稍后重试", code=503)


@qrlogin_router.post("/cleanup")
async def qrlogin_cleanup(
    current_user: dict = Depends(get_current_user)
):
    try:
        user_id, tenant_id = _qr_owner(current_user)
        if user_id is None or tenant_id is None:
            return ResultObject.unauthorized()
        removed = cleanup_sessions_for_owner(user_id, tenant_id)
        return ResultObject.success({"status": "ok", "removed": removed})
    except Exception as e:
        logger.error("清理二维码会话失败 errorType=%s", type(e).__name__, exc_info=True)
        return ResultObject.failed("扫码会话清理失败，请稍后重试", code=503)


notification_router = APIRouter(prefix="/notification")
websocket_router = APIRouter(prefix="/websocket")
operation_log_router = APIRouter(prefix="/operationLog")


@websocket_router.post("/sendMessage")
async def websocket_send_message(
    data: dict = {},
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        raw_account_id = data.get("xianyuAccountId") or data.get("accountId")
        account_id = _parse_account_id(raw_account_id)
        cid = data.get("cid") or data.get("conversationId") or data.get("sessionId") or data.get("sId") or data.get("sid")
        to_id = data.get("toId") or data.get("peerUserId") or data.get("peer_user_id")
        message_text = data.get("text") or data.get("message") or data.get("content")

        if not account_id or not cid or not message_text:
            return ResultObject.validate_failed("accountId, cid 和 text 不能为空")

        tenant_id = current_user.get("tenant_id")
        if not await _account_belongs_to_tenant(
            db, tenant_id, account_id, current_user.get("user_id")
        ):
            return ResultObject.failed("账号不存在", code=404)
        client = ws_manager.get_client(account_id)
        if not client or not getattr(client, "is_connected", False):
            # 发送前主动用数据库中的最新 Cookie/Token 重建连接，解决“接收正常但发送端卡在旧 token_failed 客户端”的问题。
            client, restart_error = await _restart_ws_client_from_db(db, tenant_id, account_id)
            if restart_error:
                return ResultObject.failed(restart_error)
            outcome, status = await _wait_ws_connect_result(account_id, timeout_seconds=8.0)
            if outcome == "auth_failed":
                return ResultObject.failed(_ws_auth_failure_message(status))
            if outcome != "connected":
                return ResultObject.failed("WebSocket 连接尚未就绪，请稍后重试", code=503)
            client = ws_manager.get_client(account_id)
        if not client:
            return ResultObject.failed("账号未连接 WebSocket")

        ws_sid = await _resolve_ws_sid(db, tenant_id, account_id, cid)
        if not ws_sid:
            return ResultObject.failed("无法识别会话ID，发送失败")
        ws_cid = _to_goofish_id(ws_sid)

        own_id = _normalize_safe_goofish_id(client.unb or "")
        resolved_to_id = await _resolve_ws_peer_id(db, tenant_id, account_id, ws_sid, to_id, own_id)
        resolved_goods_id = await _resolve_ws_goods_id(db, tenant_id, account_id, ws_sid, data.get("xyGoodsId"))
        if not resolved_to_id:
            return ResultObject.failed("无法识别会话对端，发送失败")
        ws_to_id = _to_goofish_id(resolved_to_id)

        logger.info(
            "WS 发送消息参数 accountId=%d sessionRefPresent=%s "
            "peerRefPresent=%s contentLen=%d",
            account_id,
            bool(ws_sid),
            bool(resolved_to_id),
            len(str(message_text)),
        )

        result = await client.send_text_message(ws_cid, ws_to_id, str(message_text))
        if result.get("code") != 200:
            error = result.get("error", "")
            # 翻译闲鱼服务端的常见错误
            if "conversation not exist" in error.lower():
                user_error = "会话已被删除或已过期，无法发送消息"
            else:
                user_error = "消息发送失败，请稍后重试"
            return ResultObject.failed(user_error)

        sender_id = _to_goofish_id(client.unb or "")
        out_message_time = int(datetime.datetime.now().timestamp() * 1000)
        await save_chat_message(db, tenant_id, account_id, {
            "pnmId": result.get("uuid") or "",
            "sId": ws_sid,
            "contentType": 1,
            "msgContent": str(message_text),
            "senderUserId": sender_id,
            "senderUserName": "我",
            "receiverUserId": ws_to_id,
            "xyGoodsId": resolved_goods_id,
            "messageTime": out_message_time,
            "direction": "OUT",
            "readStatus": 1,
        }, seller_external_uid=client.unb or "")
        await db.commit()
        # 不在此处广播 SSE：IM 推送回环会触发 ws_client._handle_message 广播，
        # 此处再广播会导致前端收到两条 SSE，造成消息重复显示。
        return ResultObject.success({"message": "Sent", "uuid": result.get("uuid"), "sid": ws_sid, "toId": ws_to_id})
    except Exception as e:
        await db.rollback()
        return safe_route_failure(
            logger, e, operation="send websocket message", user_message="消息发送失败，请稍后重试"
        )


@websocket_router.post("/sendImageMessage")
async def websocket_send_image_message(
    data: dict = {},
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        raw_account_id = data.get("xianyuAccountId") or data.get("accountId")
        account_id = _parse_account_id(raw_account_id)
        cid = data.get("cid") or data.get("conversationId") or data.get("sessionId") or data.get("sId") or data.get("sid")
        to_id = data.get("toId") or data.get("peerUserId") or data.get("peer_user_id")
        image_url = str(data.get("imageUrl", "") or "").strip()

        if not account_id or not cid or not image_url:
            return ResultObject.validate_failed("accountId, cid 和 imageUrl 不能为空")
        tenant_id = current_user.get("tenant_id")
        if not await _account_belongs_to_tenant(
            db, tenant_id, account_id, current_user.get("user_id")
        ):
            return ResultObject.failed("账号不存在", code=404)
        image_width, image_height = await asyncio.to_thread(
            _resolve_outbound_image_dimensions, image_url, tenant_id
        )
        try:
            image_url = await _resolve_outbound_image_url(db, tenant_id, account_id, image_url)
        except ValueError as exc:
            return ResultObject.validate_failed("图片地址无效或不允许发送")
        client = ws_manager.get_client(account_id)
        if not client or not getattr(client, "is_connected", False):
            client, restart_error = await _restart_ws_client_from_db(db, tenant_id, account_id)
            if restart_error:
                return ResultObject.failed(restart_error)
            outcome, status = await _wait_ws_connect_result(account_id, timeout_seconds=8.0)
            if outcome == "auth_failed":
                return ResultObject.failed(_ws_auth_failure_message(status))
            if outcome != "connected":
                return ResultObject.failed("WebSocket 连接尚未就绪，请稍后重试", code=503)
            client = ws_manager.get_client(account_id)
        if not client:
            return ResultObject.failed("账号未连接 WebSocket")

        ws_sid = await _resolve_ws_sid(db, tenant_id, account_id, cid)
        if not ws_sid:
            return ResultObject.failed("无法识别会话ID，发送失败")
        ws_cid = _to_goofish_id(ws_sid)

        own_id = _normalize_safe_goofish_id(client.unb or "")
        resolved_to_id = await _resolve_ws_peer_id(db, tenant_id, account_id, ws_sid, to_id, own_id)
        resolved_goods_id = await _resolve_ws_goods_id(db, tenant_id, account_id, ws_sid, data.get("xyGoodsId"))
        if not resolved_to_id:
            return ResultObject.failed("无法识别会话对端，发送失败")
        ws_to_id = _to_goofish_id(resolved_to_id)

        result = await client.send_image_message(
            ws_cid,
            ws_to_id,
            image_url,
            width=image_width,
            height=image_height,
        )
        if result.get("code") != 200:
            return ResultObject.failed("图片消息发送失败，请稍后重试")

        sender_id = _to_goofish_id(client.unb or "")
        out_image_time = int(datetime.datetime.now().timestamp() * 1000)
        await save_chat_message(db, tenant_id, account_id, {
            "pnmId": result.get("uuid") or "",
            "sId": ws_sid,
            "contentType": 2,
            "msgContent": image_url,
            "senderUserId": sender_id,
            "senderUserName": "我",
            "receiverUserId": ws_to_id,
            "xyGoodsId": resolved_goods_id,
            "messageTime": out_image_time,
            "direction": "OUT",
            "readStatus": 1,
        }, seller_external_uid=client.unb or "")
        await db.commit()
        # 不在此处广播 SSE：IM 推送回环会触发 ws_client._handle_message 广播，
        # 此处再广播会导致前端收到两条 SSE，造成消息重复显示。
        return ResultObject.success({"message": "Sent", "uuid": result.get("uuid"), "sid": ws_sid, "toId": ws_to_id, "imageUrl": image_url})
    except Exception as e:
        await db.rollback()
        return safe_route_failure(
            logger, e, operation="send websocket image", user_message="图片消息发送失败，请稍后重试"
        )


@websocket_router.post("/start")
async def websocket_start(
    data: dict = {},
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """启动 WebSocket 连接。

    手动连接时强制从数据库重建客户端，避免旧的 token_failed/stopped 客户端导致前端一直卡在“正在连接”。
    若检测到滑块/Token/Cookie 失败，立即返回失败；未检测到验证失败但连接仍在建立时，
    按产品要求返回“连接成功/已提交”，后台继续完成连接。
    """
    account_id = _parse_account_id(data.get("xianyuAccountId") or data.get("accountId"))
    if not account_id:
        return ResultObject.validate_failed("accountId 不能为空")
    tenant_id = current_user.get("tenant_id")
    if not await _account_belongs_to_tenant(
        db, tenant_id, account_id, current_user.get("user_id")
    ):
        return ResultObject.failed("账号不存在", code=404)
    raw_force_reconnect = data.get("forceReconnect")
    if raw_force_reconnect is None:
        raw_force_reconnect = data.get("force_reconnect")
    force_reconnect = str(raw_force_reconnect).strip().lower() in {"1", "true", "yes", "on"}

    current = ws_manager.get_client(account_id)
    if current and getattr(current, "is_connected", False):
        status = ws_manager.get_status(account_id)
        return ResultObject.success({
            "connected": True,
            "status": "already_connected",
            "hasSid": bool(status.get("hasSid")),
            "lastError": "",
        })

    # === 连接前同步预检 WS Token ===
    # 在启动后台 WS 客户端之前，先同步调用 Token API 探测 Cookie 是否可用。
    # 如果 Cookie 已触发滑块/已过期，立即返回失败，避免用户空等 12 秒后还看到"连接仍在建立中"。
    precheck_ok, precheck_fail = await _precheck_ws_token(
        db, tenant_id, account_id, allow_unverified=force_reconnect
    )
    if not precheck_ok:
        fail_type, fail_message = precheck_fail
        logger.warning("websocket_start 预检失败 accountId=%d failType=%s", account_id, fail_type)
        return ResultObject.success({
            "connected": False,
            "optimistic": False,
            "status": fail_type,
            "hasSid": False,
            "lastError": fail_message,
            "message": fail_message,
        })

    client, error = await _restart_ws_client_from_db(
        db,
        tenant_id,
        account_id,
        allow_unverified=force_reconnect,
    )
    if error:
        return ResultObject.failed(error)

    outcome, status = await _wait_ws_connect_result(account_id, timeout_seconds=12.0)
    if outcome == "connected":
        return ResultObject.success({
            "connected": True,
            "status": "connected",
            "hasSid": bool(status.get("hasSid")),
            "lastError": "",
        })
    if outcome == "auth_failed":
        # === 用户手动点击连接失败时自动过一次滑块 ===
        # 检测到滑块/Token/Cookie 失败，自动触发滑块求解 + Token API 二次验证：
        # - 求解通过 + Cookie 可用：恢复 cookie_status=1，自动重连 WS，返回"已恢复连接"
        # - 求解通过但 Cookie Session 真过期：返回明确提示"Session 已过期，请重新扫码登录"
        # - 求解失败：返回原始失败提示
        try:
            from app.services.captcha_solver import handle_captcha_for_account
            captcha_result = await handle_captcha_for_account(
                account_id=account_id,
                tenant_id=tenant_id,
                response=None,
                auto_solve=True,
                trigger_scene="ws_connect",
            )
            recovered = bool(captcha_result.get("recovered"))
            auto_solve_result = captcha_result.get("autoSolveResult") or {}
            cookie_verified = auto_solve_result.get("cookieVerified", True)

            if recovered:
                # 滑块通过 + Cookie 二次验证通过 → 自动重连 WS
                try:
                    asyncio.create_task(ws_manager.restart_account(account_id))
                except Exception:
                    pass
                return ResultObject.success({
                    "connected": False,
                    "status": "recovering",
                    "hasSid": False,
                    "lastError": "",
                    "captchaSolved": True,
                    "cookieVerified": True,
                    "message": "检测到登录失效，已自动完成滑块验证并恢复 Cookie，正在重新连接…",
                })
            elif auto_solve_result.get("solved") and not cookie_verified:
                # 滑块通过但 Cookie Session 真过期
                return ResultObject.failed(
                    "Cookie Session 已真正过期（滑块已通过但 Token API 仍拒绝），"
                    "请前往账号管理页或连接管理页重新扫码登录闲鱼账号获取新 Cookie。"
                )
            else:
                # 滑块求解失败
                return ResultObject.failed(
                    "自动安全验证未通过，请稍后重试，或前往账号管理页手动更新 Cookie。"
                )
        except Exception as e:
            return safe_route_failure(
                logger,
                e,
                operation="solve websocket captcha",
                user_message="自动安全验证服务暂时不可用，请更新 Cookie 或扫码重新登录",
                code=503,
            )

    if outcome == "failed":
        # WS 客户端已进入明确失败状态（closed/error/stopped 等），
        # 不再乐观假设连接成功，直接返回失败并附上真实原因。
        last_error = str(status.get("lastError") or status.get("last_error") or "").strip()
        message = last_error or "WebSocket 连接失败，请检查网络或账号 Cookie 后重试"
        return ResultObject.success({
            "connected": False,
            "optimistic": False,
            "status": _safe_ws_phase(status),
            "hasSid": bool(status.get("hasSid")),
            "lastError": message,
            "message": message,
        })

    # pending：12 秒内既未连上、也未进入明确失败状态。
    # 预检已通过说明 Cookie 有效，但 WS 连接超时，通常是网络问题或闲鱼服务端延迟。
    # 返回 connected=False + 根据当前 phase 给出诊断提示，让用户知道该如何处理。
    phase = _safe_ws_phase(status)
    last_error = str(status.get("lastError") or status.get("last_error") or "").strip()
    if phase in {"refresh_token", "connecting", "connected_socket", "registering", "syncing"}:
        message = "WebSocket 连接超时（12秒内未完成握手），请检查网络后重试，或稍后再查看连接状态"
    elif last_error:
        message = last_error
    else:
        message = "WebSocket 连接未完成，请稍后查看连接状态，或检查网络后重试"
    return ResultObject.success({
        "connected": False,
        "optimistic": False,
        "status": phase,
        "hasSid": bool(status.get("hasSid")),
        "lastError": message,
        "message": message,
    })


@websocket_router.post("/stop")
async def websocket_stop(
    data: dict = {},
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """停止 WebSocket 连接。"""
    account_id = _parse_account_id(data.get("xianyuAccountId") or data.get("accountId"))
    if not account_id:
        return ResultObject.validate_failed("accountId 不能为空")
    tenant_id = current_user.get("tenant_id")
    if not await _account_belongs_to_tenant(
        db, tenant_id, account_id, current_user.get("user_id")
    ):
        return ResultObject.failed("账号不存在", code=404)
    client = ws_manager.get_client(account_id)
    if not client:
        return ResultObject.success({"connected": False, "status": "not_found"})
    await client.stop()
    # 用户主动断开，持久化离线状态到 DB
    try:
        await update_ws_heartbeat(db, {
            "tenantId": tenant_id,
            "accountId": account_id,
            "onlineStatus": 0,
            "wsStatus": 0,
            "latency": 0,
        })
    except Exception as e:
        logger.warning("websocket_stop 持久化离线状态失败 accountId=%d: %s", account_id, e)
    return ResultObject.success({"connected": False, "status": "disconnected"})


@websocket_router.post("/status")
async def websocket_status(
    data: dict = {},
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """获取 WebSocket 连接状态。"""
    account_id = _parse_account_id(data.get("xianyuAccountId") or data.get("accountId"))
    if not account_id:
        return ResultObject.validate_failed("accountId 不能为空")
    tenant_id = current_user.get("tenant_id")
    if not await _account_belongs_to_tenant(
        db, tenant_id, account_id, current_user.get("user_id")
    ):
        return ResultObject.failed("账号不存在", code=404)
    client = ws_manager.get_client(account_id)
    if not client:
        return ResultObject.success({
            "connected": False,
            "status": "not_found",
            "hasSid": False,
            "lastError": "",
        })
    status = ws_manager.get_status(account_id)
    return ResultObject.success({
        "connected": bool(getattr(client, "is_connected", False)),
        "status": _safe_ws_phase(status),
        "hasSid": bool(status.get("hasSid")),
        "lastError": _safe_ws_last_error(status),
    })


@media_router.post("/list")
async def media_list(
    data: dict = {},
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    return ResultObject.failed(
        "媒体库功能尚未提供租户隔离存储，当前不可用；未读取任何文件",
        code=410,
    )


@media_router.post("/delete")
async def media_delete(
    data: dict = {},
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    return ResultObject.failed(
        "媒体库功能尚未提供租户隔离存储，当前不可用；未删除任何文件",
        code=410,
    )


@image_router.post("/upload")
async def image_upload(
    accountId: int = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        if accountId < 0:
            return ResultObject.validate_failed("accountId 必须为非负整数")
        tenant_id = current_user.get("tenant_id")
        if accountId > 0 and not await _account_belongs_to_tenant(
            db, tenant_id, accountId, current_user.get("user_id")
        ):
            return ResultObject.failed("账号不存在", code=404)
        content = await file.read(MAX_IMAGE_BYTES + 1)
        image = validate_image_bytes(content, declared_media_type=file.content_type)
        stored = await store_governed_image(
            image,
            tenant_id=int(tenant_id),
            user_id=current_user.get("user_id"),
            prefix="img",
            source_type="user-upload",
            base_dir=_IMAGE_UPLOAD_BASE_DIR,
        )
        logger.info("Image uploaded bytes=%d", len(content))
        return ResultObject.success({
            "url": stored.public_url,
            "name": stored.saved_name,
            "assetId": stored.asset_id,
            "size": len(content),
            "message": "上传成功"
        })
    except UploadGovernanceError as e:
        return ResultObject.failed(e.public_message, code=e.status_code)
    except ValueError:
        return ResultObject.validate_failed(
            "图片文件无效；仅支持 JPEG、PNG、GIF、WebP，且大小不能超过 5MB"
        )
    except Exception as e:
        return safe_route_failure(
            logger, e, operation="upload image", user_message="图片暂时无法上传，请稍后重试"
        )


@image_router.post("/uploadFromUrl")
async def image_upload_from_url(
    data: dict = {},
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    image_url = str(data.get("url") or "").strip()
    if not image_url:
        return ResultObject.validate_failed("图片地址不能为空")
    requested_visibility = str(data.get("visibility") or "private").strip().lower()
    requested_purpose = str(data.get("purpose") or "url-import").strip().lower()
    if requested_visibility not in {"private", "public"}:
        return ResultObject.validate_failed("图片可见性参数无效")
    if requested_visibility == "public" and (
        current_user.get("auth_type") != "internal"
        or requested_purpose not in ALLOWED_PUBLIC_UPLOAD_PURPOSES
    ):
        return ResultObject.failed("仅内部内容发布流程可创建公开图片", code=403)
    purpose = requested_purpose if requested_visibility == "public" else "url-import"
    try:
        image = await download_public_image(image_url)
    except Exception as e:
        return safe_route_failure(
            logger,
            e,
            operation="download public image",
            user_message="图片地址不安全、无法访问或返回的不是受支持图片",
            code=422,
        )
    try:
        tenant_id = int(current_user.get("tenant_id") or 0)
        stored = await store_governed_image(
            image,
            tenant_id=tenant_id,
            user_id=current_user.get("user_id"),
            prefix="url-img",
            source_type="url-import",
            base_dir=_IMAGE_UPLOAD_BASE_DIR,
            visibility=requested_visibility,
            purpose=purpose,
            owner_type=(
                "service" if current_user.get("auth_type") == "internal" else "user"
            ),
        )
        logger.info("URL image saved bytes=%d", len(image.content))
        return ResultObject.success({
            "url": stored.public_url,
            "name": stored.saved_name,
            "assetId": stored.asset_id,
            "size": len(image.content),
            "message": "导入成功",
        })
    except UploadGovernanceError as e:
        return ResultObject.failed(e.public_message, code=e.status_code)
    except Exception as e:
        return safe_route_failure(
            logger, e, operation="store imported image", user_message="图片暂时无法保存，请稍后重试"
        )


# ---- Goofish MTOP 商品关键词搜索 ----
# 此端点是 Java 网关 /api/goofish/search 调用的目标。
# 使用已登录闲鱼账号的 Cookie + _m_h5_tk 调用 MTOP 搜索 API。
# SEARCH_MTOP_API, _resolve_account_cookie, _normalize_mtop_search_item 已移至
# xianyu_goods_sync.py 并在顶部导入，避免跨层导入失败。


def _call_crawler_search(keyword: str, page: int, page_size: int, tenant_id: int, cookie_str: str = "") -> dict:
    """调用 crawler-service (Playwright 无头浏览器) 搜索闲鱼商品。

    crawler-service 通过真实浏览器访问 goofish.com 搜索页面，
    自动处理 Baxia 反爬令牌（bx-ua/bx-umidtoken/bx_et），
    避免 MTOP API 直调被 RGV587 风控拦截。
    传递用户 Cookie 让浏览器使用已登录的闲鱼会话。
    """
    import requests as _requests

    crawler_base = (os.getenv("CRAWLER_SERVICE_URL") or "http://localhost:3001").rstrip("/")
    crawler_url = f"{crawler_base}/api/goofish/search"
    headers = {
        "X-Internal-Token": settings.effective_internal_api_token,
        "X-Internal-Tenant-Id": str(tenant_id),
    }
    payload = {
        "q": keyword,
        "page": page,
        "pageSize": page_size,
    }
    if cookie_str:
        payload["cookie"] = cookie_str
    resp = _requests.post(crawler_url, headers=headers, json=payload, timeout=90)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError("crawler-service 搜索失败")

    items = data.get("items", [])
    # 标准化为前端期望的格式（crawler-service 已从 MTOP API 响应中提取完整字段）
    normalized = []
    for item in items:
        item_id = item.get("itemId", "")
        title = item.get("title", "")
        price = item.get("price", "")
        normalized.append({
            "title": title,
            "price": price,
            "imageUrl": item.get("imageUrl", ""),
            "link": f"https://www.goofish.com/item?itemId={item_id}" if item_id else (item.get("itemUrl") or ""),
            "itemId": item_id,
            "seller": item.get("userNickName", ""),
            "area": item.get("area", ""),
            "soldCount": 0,
            "wantCount": 0,
            "description": title,
        })

    return {
        "items": normalized,
        "total": data.get("total", len(normalized)),
        "page": data.get("page", page),
        "pageSize": data.get("pageSize", page_size),
        "hasMore": data.get("hasMore", False),
    }


def _call_mtop_search_direct(keyword: str, page: int, page_size: int, cookie_str: str) -> dict:
    """快速搜索：直接调用闲鱼 MTOP 搜索 API（不经浏览器）。

    速度最快（~1秒），仅需 Cookie + _m_h5_tk 即可签名调用。
    参考 闲鱼搜索接口.md 文档：POST https://h5api.m.goofish.com/h5/mtop.taobao.idlemtopsearch.pc.search/1.0/

    注意：直调 MTOP 不携带 bx-ua/bx-umidtoken/bx_et 等 Baxia 反爬令牌，
    在某些账号/IP 下可能触发 FAIL_SYS_USER_VALIDATE 或 RGV587 风控。
    触发风控时抛出 RuntimeError，由上层降级到慢速搜索（浏览器方式）。
    """
    search_data = {
        "keyword": keyword,
        "pageNumber": page,
        "rowsPerPage": page_size,
        "fromFilter": False,
        "sortValue": "",
        "sortField": "",
        "searchReqFromPage": "pcSearch",
        "customDistance": "",
        "gps": "",
        "customGps": "",
        "propValueStr": {},
        "extraFilterValue": "{}",
        "userPositionJson": "{}",
    }

    response = _xianyu_mtop_request(
        cookie_str, SEARCH_MTOP_API, search_data,
        timeout=15,
        extra_form={"sessionOption": "AutoLoginOnly", "accountSite": "xianyu"},
    )

    ret = response.get("ret", [])
    ret_msg = str(ret[0]) if isinstance(ret, list) and ret else str(ret)

    # 检测风控/Token失效错误，抛出异常让上层降级到慢速搜索
    if _XIANYU_RGV587 in ret_msg:
        raise RuntimeError("快速搜索触发风控，将降级到兼容搜索")
    if _XIANYU_TOKEN_EXPIRED in ret_msg or _XIANYU_TOKEN_EXPIRED_ALIAS in ret_msg:
        raise RuntimeError("Cookie/_m_h5_tk 已失效")
    if "FAIL_SYS_USER_VALIDATE" in ret_msg:
        raise RuntimeError("快速搜索触发安全验证，将降级到兼容搜索")
    if "SUCCESS" not in ret_msg:
        raise RuntimeError("MTOP 搜索未返回可用结果")

    # 解析商品列表（参考 闲鱼搜索接口.md 响应结构）
    result_data = response.get("data", {})
    if not isinstance(result_data, dict):
        result_data = {}

    raw_items = (
        result_data.get("resultList")
        or result_data.get("items")
        or result_data.get("itemList")
        or result_data.get("cardList")
        or []
    )

    normalized = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        item = _normalize_mtop_search_item(raw_item)
        if item.get("title") or item.get("itemId"):
            normalized.append(item)

    # 分页信息
    result_info = result_data.get("resultInfo", {}) if isinstance(result_data.get("resultInfo"), dict) else {}
    has_more = bool(result_info.get("hasNextPage", False))
    try:
        total = int(result_info.get("numFound", 0) or 0)
    except (ValueError, TypeError):
        total = 0

    return {
        "items": normalized,
        "total": total or len(normalized),
        "page": page,
        "pageSize": page_size,
        "hasMore": has_more,
    }


def _detect_mtop_error(ret_msg: str) -> Optional[str]:
    """检测 MTOP 返回中的已知错误，返回用户可读的错误描述。"""
    if not ret_msg:
        return None
    if _XIANYU_RGV587 in ret_msg:
        return "搜索触发闲鱼风控限制(RGV587)，请稍后再试"
    if _XIANYU_TOKEN_EXPIRED in ret_msg or _XIANYU_TOKEN_EXPIRED_ALIAS in ret_msg:
        return "Cookie/_m_h5_tk 已失效，请重新登录获取有效Cookie"
    if "SUCCESS" not in ret_msg:
        return None  # 调用方兜底
    return None


# _resolve_account_cookie 和 _normalize_mtop_search_item 已移至
# xianyu_goods_sync.py 并在顶部导入


def _execute_search_with_mode(
    keyword: str, page: int, page_size: int, tenant_id: int,
    cookie_str: str, mode: str,
) -> dict:
    """统一搜索执行器：根据 mode 选择快速搜索(直调MTOP)或慢速搜索(浏览器)。

    - mode=fast：仅快速搜索（直调MTOP API），失败抛异常
    - mode=slow：仅慢速搜索（Playwright浏览器），失败抛异常
    - mode=auto（默认）：先快速搜索，失败则降级到慢速搜索
    """
    mode = (mode or "auto").lower().strip()
    if mode not in ("fast", "slow", "auto"):
        mode = "auto"

    fast_fallback = False

    # 快速搜索（直调MTOP API，~1秒）
    if mode in ("fast", "auto"):
        try:
            result = _call_mtop_search_direct(keyword, page, page_size, cookie_str)
            if result.get("items"):
                result["searchMode"] = "fast"
                logger.info("[搜索] 快速搜索成功 keywordLen=%d count=%d", len(keyword), len(result["items"]))
                return result
            # 快速搜索无结果但未报错，记录后尝试慢速
            fast_fallback = True
            logger.info("[搜索] 快速搜索无结果 keywordLen=%d，尝试慢速搜索", len(keyword))
        except Exception as e:
            fast_fallback = True
            logger.info(
                "[搜索] 快速搜索失败 keywordLen=%d errorType=%s，将降级到慢速搜索",
                len(keyword),
                type(e).__name__,
            )
            if mode == "fast":
                # fast 模式不降级，直接抛出
                raise

    # 慢速搜索（Playwright浏览器，~2-3秒）
    try:
        result = _call_crawler_search(keyword, page, page_size, tenant_id, cookie_str)
        result["searchMode"] = "slow"
        if fast_fallback:
            result["fastFallbackReason"] = "快速搜索暂不可用，已自动切换兼容搜索"
        logger.info("[搜索] 慢速搜索成功 keywordLen=%d count=%d", len(keyword), len(result.get("items", [])))
        return result
    except Exception as e:
        logger.error(
            "[搜索] 慢速搜索失败 keywordLen=%d errorType=%s",
            len(keyword),
            type(e).__name__,
            exc_info=True,
        )
        error_msg = str(e)
        if "ConnectionRefused" in error_msg or "Connection refused" in error_msg:
            raise RuntimeError("crawler-service 未启动，请启动爬虫服务后重试")
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            raise RuntimeError("搜索超时，请稍后重试")
        if "阻断" in error_msg or "验证码" in error_msg or "安全验证" in error_msg:
            raise RuntimeError("闲鱼触发安全验证，请稍后再试")
        raise


@business_router.get("/goofish-search")
async def business_goofish_search(
    q: str = Query(""),
    page: int = Query(1),
    pageSize: int = Query(20),
    accountId: Optional[int] = Query(None),
    mode: str = Query("auto"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    关键词搜索闲鱼商品（MTOP 实时搜索）。
    支持三种搜索模式：
      - mode=fast：快速搜索，直调闲鱼MTOP API（~1秒，可能触发风控）
      - mode=slow：慢速搜索，Playwright浏览器加载页面（~2-3秒，稳定）
      - mode=auto（默认）：先快速搜索，失败自动降级到慢速搜索
    前端 -> Java 网关 -> Python automation-service 的主搜索链路。
    """
    keyword = q.strip()
    if not keyword:
        return ResultObject.validate_failed("请输入搜索关键词")
    if len(keyword) > 50:
        return ResultObject.validate_failed("关键词长度不能超过 50 个字符")

    safe_page = max(1, min(page, 100))
    safe_page_size = max(1, min(pageSize, 50))

    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        return ResultObject.failed("缺少租户上下文，请重新登录")

    # 获取账号 Cookie
    cookie_str, cookie_err = await _resolve_account_cookie(db, tenant_id, accountId, current_user)
    if cookie_err:
        return ResultObject.failed(cookie_err)

    try:
        result = await asyncio.to_thread(
            _execute_search_with_mode,
            keyword, safe_page, safe_page_size, tenant_id, cookie_str, mode,
        )
    except Exception as e:
        return safe_route_failure(
            logger, e, operation="search goofish goods", user_message="商品搜索暂时不可用，请稍后重试", code=503
        )

    return ResultObject.success(result)


@business_router.get("/internal/goofish/search")
async def internal_goofish_search(
    q: str = Query(""),
    page: int = Query(1),
    pageSize: int = Query(20),
    accountId: Optional[int] = Query(None),
    mode: str = Query("auto"),
    tenant_id: Optional[int] = Query(default=None),
    current_user: dict = Depends(get_current_user),
):
    """Retired duplicate search boundary.

    The supported authenticated route is ``/business-opportunity/goofish-search``.
    Keeping this route as an explicit tombstone prevents old clients from silently
    regaining the former caller-controlled tenant behavior.
    """
    return ResultObject.failed(
        "旧版内部搜索入口已停用，请使用商品搜索入口",
        code=410,
    )
