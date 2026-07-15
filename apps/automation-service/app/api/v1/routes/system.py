import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ....core.database import get_db
from ....core.http_failures import safe_route_failure
from ....core.response import ResultObject
from ....models.entities import (
    XianyuSysSetting, XianyuAiProvider, XianyuOperationLog,
    Notification, SysLoginToken
)
from ....schemas.common import (
    SaveSettingReqDTO, GetSettingReqDTO, GetSettingRespDTO,
    AiProviderReqDTO, AiProviderRespDTO
)
from ....schemas.auth import LoginDeviceDTO, KickLoginDeviceReqDTO, ChangePasswordReqDTO
from ..deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sysSetting")


def _legacy_system_settings_unavailable() -> ResultObject:
    return ResultObject.failed(
        "旧版全局系统设置未实现租户隔离，已禁用；请使用企业配置中心",
        503,
    )


@router.post("/get", response_model=ResultObject[GetSettingRespDTO])
async def get_setting(
    req: GetSettingReqDTO,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    return _legacy_system_settings_unavailable()


@router.post("/save", response_model=ResultObject[str])
async def save_setting(
    req: SaveSettingReqDTO,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    return _legacy_system_settings_unavailable()


@router.post("/list")
async def list_settings(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    return _legacy_system_settings_unavailable()


@router.post("/delete")
async def delete_setting(
    req: dict = {},
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    return _legacy_system_settings_unavailable()


ai_provider_router = APIRouter(prefix="/aiProvider")


def _legacy_ai_provider_unavailable() -> ResultObject:
    return ResultObject.failed(
        "旧版 AI Provider 管理未实现租户隔离，已禁用；请使用企业配置中心",
        503,
    )


@ai_provider_router.get("/list", response_model=ResultObject[list])
async def list_ai_providers(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    return _legacy_ai_provider_unavailable()


@ai_provider_router.post("/save", response_model=ResultObject[str])
async def save_ai_provider(
    req: AiProviderReqDTO,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    return _legacy_ai_provider_unavailable()


@ai_provider_router.post("/listByType")
async def list_ai_providers_by_type(
    req: dict = {},
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    return _legacy_ai_provider_unavailable()


@ai_provider_router.post("/delete")
async def delete_ai_provider(
    req: dict = {},
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    return _legacy_ai_provider_unavailable()


@ai_provider_router.post("/activate")
async def activate_ai_provider(
    req: dict = {},
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    return _legacy_ai_provider_unavailable()


@ai_provider_router.post("/test")
async def test_ai_provider(
    req: dict = {},
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    return _legacy_ai_provider_unavailable()


@ai_provider_router.post("/models")
async def get_ai_provider_models(
    req: dict = {},
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    return _legacy_ai_provider_unavailable()


login_device_router = APIRouter(prefix="/loginDevice")


@login_device_router.post("/list", response_model=ResultObject[list])
async def list_login_devices(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        result = await db.execute(
            select(SysLoginToken).where(
                SysLoginToken.user_id == current_user["user_id"],
                SysLoginToken.status == 1
            )
        )
        tokens = result.scalars().all()
        devices = [
            LoginDeviceDTO.model_validate(t) for t in tokens
        ]
        return ResultObject.success(devices)
    except Exception as e:
        return safe_route_failure(logger, e, operation="list login devices", user_message="获取登录设备列表失败，请稍后重试")


@login_device_router.post("/kick", response_model=ResultObject[str])
async def kick_login_device(
    req: KickLoginDeviceReqDTO,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        result = await db.execute(
            select(SysLoginToken).where(
                SysLoginToken.id == req.token_id,
                SysLoginToken.user_id == current_user["user_id"]
            )
        )
        token = result.scalar_one_or_none()
        if not token:
            return ResultObject.failed("设备不存在")
        token.status = -1
        await db.commit()
        return ResultObject.success("踢出成功")
    except Exception as e:
        return safe_route_failure(logger, e, operation="kick login device", user_message="踢出登录设备失败，请稍后重试")


operation_log_router = APIRouter(prefix="/operationLog")


@operation_log_router.get("/list", response_model=ResultObject[list])
async def list_operation_logs(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        tenant_id = current_user.get("tenant_id")
        result = await db.execute(
            select(XianyuOperationLog)
            .where(XianyuOperationLog.tenant_id == tenant_id)
            .order_by(XianyuOperationLog.id.desc())
            .limit(100)
        )
        logs = result.scalars().all()
        return ResultObject.success([
            {
                "id": l.id,
                "user_id": l.user_id,
                "operation_type": l.operation_type,
                "operation_desc": l.operation_desc,
                "created_time": str(l.created_time) if l.created_time else None
            } for l in logs
        ])
    except Exception as e:
        return safe_route_failure(logger, e, operation="list operation logs", user_message="获取操作日志失败，请稍后重试")


notification_router = APIRouter(prefix="/notification")


@notification_router.get("/list", response_model=ResultObject[list])
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        tenant_id = current_user.get("tenant_id")
        result = await db.execute(
            select(Notification)
            .where(
                Notification.tenant_id == tenant_id,
                Notification.deleted == 0,
            )
            .order_by(Notification.id.desc())
            .limit(50)
        )
        logs = result.scalars().all()
        return ResultObject.success([
            {
                "id": l.id,
                "channel": l.notification_type,
                "title": l.title,
                "content": l.content,
                "status": l.is_read,
                "created_time": str(l.created_time) if l.created_time else None
            } for l in logs
        ])
    except Exception as e:
        return safe_route_failure(logger, e, operation="list notifications", user_message="获取通知日志失败，请稍后重试")


system_info_router = APIRouter(prefix="/system")


@system_info_router.get("/info", response_model=ResultObject[dict])
async def get_system_info():
    return ResultObject.success({
        "version": "1.0.0-python",
        "language": "Python",
        "framework": "FastAPI",
        "database": "MySQL",
        "port": 12401
    })


@system_info_router.post("/currentUser", response_model=ResultObject[dict])
async def get_current_user_info(
    current_user: dict = Depends(get_current_user)
):
    """获取当前登录用户信息"""
    try:
        return ResultObject.success({
            "userId": current_user["user_id"],
            "username": current_user["username"],
            "tenantId": current_user.get("tenant_id")
        })
    except Exception as e:
        return safe_route_failure(logger, e, operation="get current user info", user_message="获取当前用户信息失败，请稍后重试")


@system_info_router.post("/changePassword", response_model=ResultObject[str])
async def change_password(
    req: ChangePasswordReqDTO,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """修改密码"""
    try:
        from sqlalchemy import select
        from ....models.entities import SysUser
        from ....core.security import hash_password, verify_password

        result = await db.execute(select(SysUser).where(SysUser.id == current_user["user_id"]))
        user = result.scalar_one_or_none()
        if not user:
            return ResultObject.failed("用户不存在")

        if not verify_password(req.old_password, user.password_hash):
            return ResultObject.failed("原密码错误")

        user.password_hash = hash_password(req.new_password)
        await db.commit()
        return ResultObject.success("密码修改成功")
    except Exception as e:
        return safe_route_failure(logger, e, operation="change password", user_message="修改密码失败，请稍后重试")
