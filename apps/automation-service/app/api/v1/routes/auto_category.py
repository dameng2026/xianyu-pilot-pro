"""
自动分类 API 路由
提供图片上传后自动识别分类的接口
"""

import asyncio
import hashlib
import logging
import os
import ipaddress
import requests
import socket
from typing import Optional
from urllib.parse import unquote, urlparse

from fastapi import APIRouter, Depends, UploadFile, File, Form, Body, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from ....core.database import get_db
from ....core.http_failures import log_route_failure, safe_route_failure
from ....core.response import ResultObject
from ....core.cookie_crypto import decrypt_cookie_if_needed
from ....core.config import settings
from ....core.image_security import MAX_IMAGE_BYTES, validate_image_bytes
from ....models.entities import XianyuAccount, XianyuAccountAuth
from ....services.auto_category import auto_category as auto_category_service, _get_token_from_cookie
from ....services.category_data import load_categories, merge_candidates, save_categories
from ....services.upload_governance import UploadGovernanceError, govern_transient_upload
from ..deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/xianyu/accounts",
    tags=["autoCategory"],
    dependencies=[Depends(get_current_user)],
)

# 图片上传目录（与 misc.py 中的 image_upload 保持一致）
_UPLOAD_BASE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "../../../../uploads/images")
)
_MAX_REMOTE_IMAGE_BYTES = MAX_IMAGE_BYTES
AUTO_CATEGORY_LOAD_TIMEOUT_SECONDS = 20.0
AUTO_CATEGORY_SERVICE_TIMEOUT_SECONDS = 30.0
_AUTO_CATEGORY_CONCURRENCY = 2
_auto_category_semaphore = asyncio.Semaphore(_AUTO_CATEGORY_CONCURRENCY)


class AutoCategoryTimeoutError(RuntimeError):
    pass


def _release_auto_category_slot(task: asyncio.Task) -> None:
    try:
        task.exception()
    except (asyncio.CancelledError, Exception):
        pass
    _auto_category_semaphore.release()


async def _bounded_blocking_call(function, *args, timeout: float, **kwargs):
    """Offload blocking category I/O while retaining its slot after timeout."""

    await _auto_category_semaphore.acquire()
    task = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    release_in_finally = True
    try:
        return await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
    except asyncio.TimeoutError as exc:
        release_in_finally = False
        task.add_done_callback(_release_auto_category_slot)
        raise AutoCategoryTimeoutError("auto category operation timed out") from exc
    except asyncio.CancelledError:
        release_in_finally = False
        task.add_done_callback(_release_auto_category_slot)
        raise
    finally:
        if release_in_finally:
            _auto_category_semaphore.release()


def _validate_remote_image_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("远程图片仅支持 HTTPS URL")
    if parsed.username or parsed.password:
        raise ValueError("远程图片 URL 不允许包含用户凭据")
    if parsed.port not in (None, 443):
        raise ValueError("远程图片 URL 不允许使用非标准端口")

    host = parsed.hostname.strip("[]")
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            addresses = {
                ipaddress.ip_address(info[4][0])
                for info in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            }
        except (OSError, ValueError) as exc:
            raise ValueError("远程图片域名无法解析") from exc
    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("远程图片 URL 指向非公网地址")
    return parsed.geturl()


def _validate_relative_image_path(url: str, tenant_id: int | None = None) -> str:
    parsed = urlparse((url or "").strip())
    decoded_path = unquote(parsed.path or "")
    if parsed.scheme or parsed.netloc or parsed.username or parsed.password:
        raise ValueError("图片路径格式非法")
    if "\\" in decoded_path or not decoded_path.startswith("/"):
        raise ValueError("图片路径格式非法")
    normalized = os.path.normpath(decoded_path).replace("\\", "/")
    if normalized != decoded_path:
        raise ValueError("图片路径不允许目录跳转")
    if not (
        normalized.startswith("/uploads/images/")
        or normalized.startswith("/uploads/cache/")
    ):
        raise ValueError("图片路径不在允许的上传目录")
    if not os.path.basename(normalized):
        raise ValueError("图片文件名不能为空")
    if tenant_id is not None:
        expected_prefixes = (
            f"/uploads/images/tenant-{int(tenant_id)}/",
            f"/uploads/cache/tenant-{int(tenant_id)}/",
        )
        if not normalized.startswith(expected_prefixes):
            # Legacy flat files have no ownership metadata and therefore
            # cannot be safely reused by a tenant-scoped operation.
            raise ValueError("图片不属于当前租户或缺少租户归属信息")
    return normalized


def _connected_peer_address(response) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    raw = getattr(response, "raw", None)
    candidates = (
        getattr(getattr(raw, "_connection", None), "sock", None),
        getattr(getattr(raw, "connection", None), "sock", None),
    )
    for peer_socket in candidates:
        if peer_socket is None:
            continue
        try:
            peer = peer_socket.getpeername()
            raw_address = peer[0] if isinstance(peer, (tuple, list)) else peer
            return ipaddress.ip_address(str(raw_address).split("%", 1)[0])
        except (AttributeError, OSError, TypeError, ValueError):
            continue
    raise ValueError("无法核验远程图片连接地址")


def _read_limited_image_response(response) -> bytes:
    content_type = str(response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    allowed_types = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    if content_type and content_type not in allowed_types | {"application/octet-stream"}:
        raise ValueError("远程资源不是图片")
    length = response.headers.get("content-length")
    if length:
        try:
            declared_length = int(length)
        except (TypeError, ValueError) as exc:
            raise ValueError("远程图片长度无效") from exc
        if declared_length < 0:
            raise ValueError("远程图片长度无效")
        if declared_length > _MAX_REMOTE_IMAGE_BYTES:
            raise ValueError("远程图片不能超过 5MB")
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        total += len(chunk)
        if total > _MAX_REMOTE_IMAGE_BYTES:
            raise ValueError("远程图片不能超过 5MB")
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data:
        raise ValueError("下载的图片内容为空")
    declared_for_validation = content_type if content_type in allowed_types else None
    return validate_image_bytes(
        data,
        declared_media_type=declared_for_validation,
        max_bytes=_MAX_REMOTE_IMAGE_BYTES,
    ).content


def _resolve_image_data(url: str, tenant_id: int | None = None) -> bytes:
    """
    将图片 URL 解析为二进制数据。

    支持两种场景：
    1. 完整 HTTP URL → 通过 requests 下载
    2. 受治理相对路径 → 从与 core-api 共享的租户目录读取
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    # 场景 2：相对路径 → 本地文件系统读取
    if url.startswith("/"):
        safe_path = _validate_relative_image_path(url, tenant_id)
        namespace = "images" if safe_path.startswith("/uploads/images/") else "cache"
        relative_path = safe_path.removeprefix(f"/uploads/{namespace}/")
        images_root = os.path.realpath(_UPLOAD_BASE_DIR)
        namespace_root = images_root if namespace == "images" else os.path.realpath(
            os.path.join(images_root, "..", "cache")
        )
        tenant_root = os.path.realpath(
            os.path.join(namespace_root, f"tenant-{int(tenant_id)}")
        ) if tenant_id is not None else namespace_root
        local_path = os.path.realpath(os.path.join(namespace_root, relative_path))
        if os.path.commonpath([tenant_root, local_path]) != tenant_root:
            raise ValueError("图片路径不在当前租户上传目录")
        if not os.path.exists(local_path) or not os.path.isfile(local_path):
            raise ValueError("受治理图片文件不存在或共享存储不可用")
        logger.info("从共享存储读取租户图片 namespace=%s", namespace)
        with open(local_path, "rb") as file_obj:
            data = file_obj.read(MAX_IMAGE_BYTES + 1)
        return validate_image_bytes(data, max_bytes=MAX_IMAGE_BYTES).content

    # 场景 1：完整 HTTP URL → 下载
    safe_url = _validate_remote_image_url(url)
    resp = requests.get(
        safe_url,
        headers=headers,
        timeout=(5, 30),
        allow_redirects=False,
        stream=True,
    )
    try:
        peer_address = _connected_peer_address(resp)
        if not peer_address.is_global:
            raise ValueError("远程图片连接到了非公网地址")
        if 300 <= resp.status_code < 400:
            raise ValueError("远程图片 URL 不允许重定向")
        resp.raise_for_status()
        return _read_limited_image_response(resp)
    finally:
        resp.close()


def _require_tenant(current_user: dict) -> int:
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise ValueError("缺少租户上下文")
    return int(tenant_id)


async def _get_account_cookie(db: AsyncSession, account_id: int, tenant_id: int) -> Optional[str]:
    """获取指定账号的最新有效解密 Cookie（按更新时间倒序取最近一条）"""
    result = await db.execute(
        select(XianyuAccountAuth).where(
            XianyuAccountAuth.account_id == account_id,
            XianyuAccountAuth.tenant_id == tenant_id,
            XianyuAccountAuth.deleted == 0,
            XianyuAccountAuth.cookie_status == 1,
            XianyuAccountAuth.last_login_status_code == "OK",
            XianyuAccountAuth.encrypted_cookie.isnot(None),
            XianyuAccountAuth.encrypted_cookie != "",
        ).order_by(XianyuAccountAuth.updated_time.desc()).limit(1)
    )
    auth = result.scalar_one_or_none()
    if not auth or not auth.encrypted_cookie:
        return None
    return decrypt_cookie_if_needed(auth.encrypted_cookie)


async def _verify_active_local_image_asset(
    db: AsyncSession,
    image_url: str,
    tenant_id: int,
    content: bytes,
) -> None:
    """Require local URL inputs to match an active tenant storage record."""

    normalized = str(image_url or "").strip()
    if normalized.startswith("/uploads/images/"):
        relative_path = normalized.removeprefix("/uploads/images/")
        storage_key = relative_path
    elif normalized.startswith("/uploads/cache/"):
        relative_path = normalized.removeprefix("/uploads/cache/")
        storage_key = "cache/" + relative_path
    else:
        return
    if not relative_path.startswith(f"tenant-{int(tenant_id)}/"):
        raise ValueError("local image asset does not belong to the current tenant")
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
    expected_size = int(row.get("size_bytes") or 0)
    expected_sha256 = str(row.get("sha256") or "").strip().lower()
    if expected_size <= 0 or len(content) != expected_size:
        raise ValueError("local image asset does not match its storage record")
    if len(expected_sha256) != 64 or hashlib.sha256(content).hexdigest() != expected_sha256:
        raise ValueError("local image asset does not match its storage record")


@router.post("/{account_id}/auto-category")
async def auto_category(
    account_id: int,
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    根据封面图 URL 自动识别分类。

    请求体:
    {
        "coverImageUrl": "https://xxx.com/a.jpg",   # 必填
        "title": "可选，商品标题",
        "description": "可选，商品描述"
    }
    """
    request_id = body.get("requestId", "")

    try:
        try:
            tenant_id = _require_tenant(current_user)
        except ValueError:
            return ResultObject.failed("缺少租户上下文", 400)

        cover_image_url = (body.get("coverImageUrl") or "").strip()
        if not cover_image_url:
            return ResultObject.validate_failed("coverImageUrl 不能为空")

        title = (body.get("title") or "").strip() or None
        description = (body.get("description") or "").strip() or None

        # 获取账号 Cookie
        cookie_str = await _get_account_cookie(db, account_id, tenant_id)
        if not cookie_str:
            logger.warning("账号未登录或Cookie已失效: account_id=%d", account_id)
            return ResultObject.success({
                "success": False,
                "source": "manual",
                "autoSelected": False,
                "selectedCategory": None,
                "candidates": [],
                "cdnImageUrl": None,
                "fallbackRequired": True,
                "fallbackReason": "COOKIE_EXPIRED",
            })

        # 下载/读取封面图
        try:
            image_data = await _bounded_blocking_call(
                _resolve_image_data,
                cover_image_url,
                tenant_id,
                timeout=AUTO_CATEGORY_LOAD_TIMEOUT_SECONDS,
            )
            await _verify_active_local_image_asset(
                db, cover_image_url, tenant_id, image_data
            )
        except AutoCategoryTimeoutError:
            return ResultObject.success({
                "success": False,
                "source": "local_category",
                "autoSelected": False,
                "selectedCategory": None,
                "candidates": [],
                "cdnImageUrl": None,
                "fallbackRequired": True,
                "fallbackReason": "SERVICE_TIMEOUT",
            })
        except Exception as e:
            log_route_failure(logger, e, operation="load auto category cover image")
            return ResultObject.success({
                "success": False,
                "source": "local_category",
                "autoSelected": False,
                "selectedCategory": None,
                "candidates": [],
                "cdnImageUrl": None,
                "fallbackRequired": True,
                "fallbackReason": "UPLOAD_FAILED",
            })

        # 执行自动分类（该函数内部有完整的错误处理，永远返回 dict）
        try:
            async with govern_transient_upload(
                image_data,
                tenant_id=tenant_id,
                user_id=current_user.get("user_id"),
                source_type="auto-category-url",
            ):
                result = await _bounded_blocking_call(
                    auto_category_service,
                    cookie_str=cookie_str,
                    image_data=image_data,
                    title=title,
                    description=description,
                    timeout=AUTO_CATEGORY_SERVICE_TIMEOUT_SECONDS,
                )
        except AutoCategoryTimeoutError:
            return ResultObject.success({
                "success": False,
                "source": "manual",
                "autoSelected": False,
                "selectedCategory": None,
                "candidates": [],
                "cdnImageUrl": None,
                "fallbackRequired": True,
                "fallbackReason": "SERVICE_TIMEOUT",
            })
        except UploadGovernanceError as e:
            return ResultObject.failed(e.public_message, code=e.status_code)

        return ResultObject.success(result)

    except Exception as e:
        log_route_failure(logger, e, operation="auto category")
        return ResultObject.success({
            "success": False,
            "source": "manual",
            "autoSelected": False,
            "selectedCategory": None,
            "candidates": [],
            "cdnImageUrl": None,
            "fallbackRequired": True,
            "fallbackReason": "INTERNAL_ERROR",
        })


@router.post("/{account_id}/auto-category/upload")
async def auto_category_upload(
    account_id: int,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    上传封面图文件并自动识别分类。
    使用 multipart/form-data 上传。
    """
    try:
        try:
            tenant_id = _require_tenant(current_user)
        except ValueError:
            return ResultObject.failed("缺少租户上下文", 400)

        if not file:
            return ResultObject.validate_failed("文件不能为空")

        # 获取账号 Cookie
        cookie_str = await _get_account_cookie(db, account_id, tenant_id)
        if not cookie_str:
            logger.warning("账号未登录或Cookie已失效: account_id=%d", account_id)
            return ResultObject.success({
                "success": False,
                "source": "manual",
                "autoSelected": False,
                "selectedCategory": None,
                "candidates": [],
                "cdnImageUrl": None,
                "fallbackRequired": True,
                "fallbackReason": "COOKIE_EXPIRED",
            })

        # 读取上传的文件
        image_data = await file.read(MAX_IMAGE_BYTES + 1)
        validate_image_bytes(image_data, declared_media_type=file.content_type)

        # 执行自动分类
        async with govern_transient_upload(
            image_data,
            tenant_id=tenant_id,
            user_id=current_user.get("user_id"),
            source_type="auto-category",
        ):
            result = await _bounded_blocking_call(
                auto_category_service,
                cookie_str=cookie_str,
                image_data=image_data,
                title=title,
                description=description,
                timeout=AUTO_CATEGORY_SERVICE_TIMEOUT_SECONDS,
            )

        return ResultObject.success(result)

    except AutoCategoryTimeoutError:
        return ResultObject.success({
            "success": False,
            "source": "manual",
            "autoSelected": False,
            "selectedCategory": None,
            "candidates": [],
            "cdnImageUrl": None,
            "fallbackRequired": True,
            "fallbackReason": "SERVICE_TIMEOUT",
        })
    except ValueError:
        return ResultObject.validate_failed(
            "图片文件无效；仅支持 JPEG、PNG、GIF、WebP，且大小不能超过 5MB"
        )
    except UploadGovernanceError as e:
        return ResultObject.failed(e.public_message, code=e.status_code)
    except Exception as e:
        log_route_failure(logger, e, operation="auto category upload")
        return ResultObject.success({
            "success": False,
            "source": "manual",
            "autoSelected": False,
            "selectedCategory": None,
            "candidates": [],
            "cdnImageUrl": None,
            "fallbackRequired": True,
            "fallbackReason": "INTERNAL_ERROR",
        })


@router.get("/auto-category/config")
async def auto_category_config():
    """
    获取自动分类系统配置状态。
    返回 appKey 状态和当前阈值配置。
    """
    return ResultObject.success({
        "appKeyConfigured": bool(settings.xianyu_mtop_app_key),
        "appKeyPreview": settings.xianyu_mtop_app_key[:4] + "****" if settings.xianyu_mtop_app_key else "",
        "minScore": settings.auto_category_min_score,
        "minMargin": settings.auto_category_min_margin,
        "categoryApi": settings.xianyu_mtop_category_api,
    })


# ---- 分类树管理（非账号相关） ----
categories_router = APIRouter(
    prefix="/xianyu/categories",
    tags=["categories"],
    dependencies=[Depends(get_current_user)],
)


@categories_router.get("")
async def get_categories():
    """
    获取完整分类树。
    返回与前端 categories.json 兼容的树结构。
    """
    try:
        data = load_categories()
        tree = data.get("cation", data.get("categories", []))
        return ResultObject.success({"cation": tree})
    except Exception as e:
        logger.error("获取分类树失败 errorType=%s", type(e).__name__)
        return ResultObject.failed("商品分类树暂不可用，请稍后重试", 503)


@categories_router.post("/sync")
async def sync_categories(body: dict = Body(...)):
    """
    手动将自动分类候选合并到分类树中。
    请求体: { "candidates": [...] }
    """
    try:
        candidates = body.get("candidates", [])
        if not candidates:
            return ResultObject.validate_failed("candidates 不能为空")
        added = merge_candidates(candidates)
        return ResultObject.success({
            "added": added,
            "message": f"合并完成，新增 {added} 个分类" if added else "无新增分类",
        })
    except Exception as e:
        return safe_route_failure(logger, e, operation="sync category tree", user_message="同步分类树失败，请稍后重试")
