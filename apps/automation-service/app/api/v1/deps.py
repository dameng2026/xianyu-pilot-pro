from fastapi import Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import logging
import hmac
from ...core.database import get_db
from ...core.security import decode_token
from ...core.config import settings
from ...models.entities import SysUser

logger = logging.getLogger(__name__)


async def get_current_user(
    authorization: Optional[str] = Header(None),
    x_internal_token: Optional[str] = Header(None, alias="X-Internal-Token"),
    x_internal_tenant_id: Optional[str] = Header(None, alias="X-Internal-Tenant-Id"),
    db: AsyncSession = Depends(get_db)
) -> dict:
    # 优先使用 JWT 认证（前端直接调用）
    token = authorization
    if token:
        if token.startswith("Bearer "):
            token = token[7:]

        try:
            payload = decode_token(token)
        except Exception as e:
            logger.warning("JWT 校验失败 errorType=%s", type(e).__name__)
            raise HTTPException(status_code=401, detail="暂未登录或token已经过期")

        user_id = payload.get("user_id")
        tenant_id = payload.get("tenant_id")
        security_version = payload.get("authVersion")
        try:
            user_id = int(user_id)
            tenant_id = int(tenant_id)
            security_version = int(security_version)
        except (TypeError, ValueError):
            raise HTTPException(status_code=401, detail="暂未登录或token已经过期")
        if user_id <= 0 or tenant_id <= 0 or security_version <= 0:
            raise HTTPException(status_code=401, detail="暂未登录或token已经过期")

        try:
            result = await db.execute(
                select(SysUser).where(
                    SysUser.id == user_id,
                    SysUser.tenant_id == tenant_id,
                    SysUser.status == 1,
                    SysUser.deleted == 0
                )
            )
            user = result.scalar_one_or_none()
        except Exception as exc:
            logger.error("JWT authoritative user lookup unavailable errorType=%s", type(exc).__name__)
            raise HTTPException(status_code=503, detail="authentication state is temporarily unavailable")
        if not user:
            raise HTTPException(status_code=401, detail="用户不存在或已被禁用")

        authoritative_username = str(user.username or "")
        claimed_username = str(payload.get("username") or "")
        if (
            int(user.tenant_id) != tenant_id
            or int(user.security_version or 0) != security_version
            or not claimed_username
            or authoritative_username != claimed_username
        ):
            raise HTTPException(status_code=401, detail="暂未登录或token已经过期")

        return {
            "user_id": user.id,
            "username": authoritative_username,
            "tenant_id": tenant_id,
            "auth_type": "user",
        }

    # 未提供 JWT 时，仅允许 Java core-api 使用内部令牌认证。
    # 普通前端/外部请求没有 Authorization 与 X-Internal-Token 时，应该返回 401，
    # 避免用户端把“未登录”误判为“无权限/内部令牌错误”。
    if not x_internal_token:
        raise HTTPException(status_code=401, detail="暂未登录或token已经过期")

    # Phase 1 安全止血：一旦请求尝试走内部认证，内部令牌为空属于危险配置，
    # 必须 fail-closed，不能降级匿名系统用户。
    expected = (settings.effective_internal_api_token or "").strip()
    if not expected:
        logger.error("INTERNAL_API_TOKEN 未配置，拒绝内部接口调用")
        raise HTTPException(status_code=503, detail="INTERNAL_API_TOKEN is not configured")
    if not hmac.compare_digest(str(x_internal_token), expected):
        raise HTTPException(status_code=403, detail="invalid internal token")

    # 内部调用必须携带明确租户 ID；空租户不能回退到全局数据。
    if not x_internal_tenant_id:
        raise HTTPException(status_code=400, detail="missing X-Internal-Tenant-Id")
    try:
        internal_tenant_id = int(x_internal_tenant_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="invalid X-Internal-Tenant-Id")
    if internal_tenant_id <= 0:
        raise HTTPException(status_code=400, detail="invalid X-Internal-Tenant-Id")

    return {
        "user_id": 0,
        "username": "system",
        "tenant_id": internal_tenant_id,
        "auth_type": "internal",
    }


async def get_internal_service_identity(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Require the authenticated Java gateway, never a browser JWT."""

    if current_user.get("auth_type") != "internal":
        raise HTTPException(status_code=403, detail="internal service authentication required")
    return current_user
