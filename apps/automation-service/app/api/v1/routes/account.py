import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select, text
from ....core.database import get_db
from ....core.http_failures import safe_route_failure
from ....core.response import ResultObject
from ....core.cookie_crypto import encrypt_cookie_for_storage
from ....models.entities import (
    XianyuAccount,
    XianyuAccountAuth,
    XianyuAccountRuntime,
)
from ....schemas.account import (
    AccountReqDTO, ManualAddAccountReqDTO, UpdateAccountReqDTO,
    DeleteAccountReqDTO, GetAccountDetailReqDTO, RefreshAccountProfileReqDTO,
    AccountProfileDTO, GetAccountListRespDTO, AddAccountRespDTO,
    UpdateAccountRespDTO, DeleteAccountRespDTO, GetAccountDetailRespDTO,
    RefreshAccountProfileRespDTO, LoginCredentialRespDTO
)
from ..deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/account")


async def _rollback_safely(db: AsyncSession, *, operation: str) -> None:
    try:
        await db.rollback()
    except Exception as exc:
        logger.error("rollback failed operation=%s errorType=%s", operation, type(exc).__name__)


def _account_access_conditions(current_user: dict) -> list:
    tenant_id = int(current_user.get("tenant_id"))
    user_id = int(current_user.get("user_id") or 0)
    conditions = [
        XianyuAccount.tenant_id == tenant_id,
        XianyuAccount.deleted == 0,
    ]
    if user_id > 0:
        conditions.append(
            or_(XianyuAccount.user_id == user_id, XianyuAccount.user_id.is_(None))
        )
    return conditions


def account_to_dto(account: XianyuAccount) -> AccountProfileDTO:
    """将新实体 XianyuAccount 转换为 AccountProfileDTO"""
    ip_location = None
    if account.province or account.city:
        ip_location = f"{account.province or ''} {account.city or ''}".strip()

    dto = AccountProfileDTO(
        id=account.id,
        external_uid=account.external_uid,
        nickname=account.nickname,
        avatar_url=account.avatar_url,
        remark=account.remark,
        province=account.province,
        city=account.city,
        ip_location=ip_location,
        account_level=account.account_level,
        status=account.status,
        created_time=str(account.created_time) if account.created_time else None,
        # 向后兼容字段
        unb=account.external_uid,
        account_note=account.remark,
        display_name=account.nickname,
        avatar=account.avatar_url,
        proxy_password="***",
        login_password="***",
    )
    return dto


@router.post("/list", response_model=ResultObject[GetAccountListRespDTO])
async def get_account_list(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        tenant_id = current_user.get("tenant_id")
        user_id = current_user.get("user_id")
        query = select(XianyuAccount).where(*_account_access_conditions(current_user))
        result = await db.execute(query)
        accounts = result.scalars().all()
        account_list = [account_to_dto(a) for a in accounts]
        return ResultObject.success(GetAccountListRespDTO(accounts=account_list))
    except Exception as e:
        return safe_route_failure(
            logger, e, operation="list accounts", user_message="获取账号列表失败，请稍后重试"
        )


@router.post("/add", response_model=ResultObject[AddAccountRespDTO])
async def add_account(
    req: AccountReqDTO,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        if not req.cookie:
            return ResultObject.failed("Cookie不能为空")

        unb = extract_unb_from_cookie(req.cookie)
        if not unb:
            return ResultObject.failed("无法从Cookie中提取UNB信息")

        tenant_id = current_user.get("tenant_id")

        existing = await db.execute(
            select(XianyuAccount).where(
                XianyuAccount.external_uid == unb,
                XianyuAccount.tenant_id == tenant_id
            )
        )
        if existing.scalar_one_or_none():
            return ResultObject.failed("账号已存在")

        account = XianyuAccount(
            tenant_id=tenant_id,
            user_id=current_user.get("user_id"),
            external_uid=unb,
            remark=req.account_note,
            status=1
        )
        db.add(account)
        await db.flush()
        await db.refresh(account)

        auth = XianyuAccountAuth(
            tenant_id=tenant_id,
            account_id=account.id,
            encrypted_cookie=encrypt_cookie_for_storage(req.cookie),
            encrypted_token=encrypt_cookie_for_storage(extract_m_h5_tk_from_cookie(req.cookie)) if extract_m_h5_tk_from_cookie(req.cookie) else None,
            cookie_status=0,
            last_login_status_code="COOKIE_UPDATED",
            last_login_status_message="Cookie 已更新，等待统一登录校验",
        )
        db.add(auth)
        db.add(XianyuAccountRuntime(
            tenant_id=tenant_id,
            account_id=account.id,
            cookie_status=0,
            last_login_status_code="COOKIE_UPDATED",
            last_login_status_message="Cookie 已更新，等待统一登录校验",
        ))
        await db.commit()

        return ResultObject.success(AddAccountRespDTO(
            account_id=account.id,
            message="添加成功"
        ))
    except Exception as e:
        await _rollback_safely(db, operation="add account")
        return safe_route_failure(
            logger, e, operation="add account", user_message="添加账号失败，请稍后重试"
        )


@router.post("/manualAdd", response_model=ResultObject[AddAccountRespDTO])
async def manual_add_account(
    req: ManualAddAccountReqDTO,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        if not req.cookie:
            return ResultObject.failed("Cookie不能为空")

        unb = extract_unb_from_cookie(req.cookie)
        if not unb:
            return ResultObject.failed("无法从Cookie中提取UNB信息")

        tenant_id = current_user.get("tenant_id")

        existing = await db.execute(
            select(XianyuAccount).where(
                XianyuAccount.external_uid == unb,
                XianyuAccount.tenant_id == tenant_id
            )
        )
        if existing.scalar_one_or_none():
            return ResultObject.failed("账号已存在")

        account = XianyuAccount(
            tenant_id=tenant_id,
            user_id=current_user.get("user_id"),
            external_uid=unb,
            remark=req.account_note,
            status=1
        )
        db.add(account)
        await db.flush()
        await db.refresh(account)

        auth = XianyuAccountAuth(
            tenant_id=tenant_id,
            account_id=account.id,
            encrypted_cookie=encrypt_cookie_for_storage(req.cookie),
            encrypted_token=encrypt_cookie_for_storage(extract_m_h5_tk_from_cookie(req.cookie)) if extract_m_h5_tk_from_cookie(req.cookie) else None,
            cookie_status=0,
            last_login_status_code="COOKIE_UPDATED",
            last_login_status_message="Cookie 已更新，等待统一登录校验",
        )
        db.add(auth)
        db.add(XianyuAccountRuntime(
            tenant_id=tenant_id,
            account_id=account.id,
            cookie_status=0,
            last_login_status_code="COOKIE_UPDATED",
            last_login_status_message="Cookie 已更新，等待统一登录校验",
        ))
        await db.commit()

        return ResultObject.success(AddAccountRespDTO(
            account_id=account.id,
            message="添加成功"
        ))
    except Exception as e:
        await _rollback_safely(db, operation="manually add account")
        return safe_route_failure(
            logger, e, operation="manually add account", user_message="添加账号失败，请稍后重试"
        )


@router.post("/update", response_model=ResultObject[UpdateAccountRespDTO])
async def update_account(
    req: UpdateAccountReqDTO,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        tenant_id = current_user.get("tenant_id")
        result = await db.execute(
            select(XianyuAccount).where(
                XianyuAccount.id == req.account_id,
                *_account_access_conditions(current_user),
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            return ResultObject.failed("账号不存在")

        if req.account_note is not None:
            account.remark = req.account_note.strip()

        await db.commit()
        return ResultObject.success(UpdateAccountRespDTO(message="更新成功"))
    except Exception as e:
        await _rollback_safely(db, operation="update account")
        return safe_route_failure(
            logger, e, operation="update account", user_message="更新账号失败，请稍后重试"
        )


@router.post("/delete", response_model=ResultObject[DeleteAccountRespDTO])
async def delete_account(
    req: DeleteAccountReqDTO,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        tenant_id = current_user.get("tenant_id")
        result = await db.execute(
            select(XianyuAccount).where(
                XianyuAccount.id == req.account_id,
                *_account_access_conditions(current_user),
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            return ResultObject.failed("账号不存在")

        # 删除关联的认证信息
        await db.execute(
            XianyuAccountAuth.__table__.delete().where(
                XianyuAccountAuth.account_id == req.account_id,
                XianyuAccountAuth.tenant_id == tenant_id,
            )
        )
        await db.execute(
            XianyuAccountRuntime.__table__.delete().where(
                XianyuAccountRuntime.account_id == req.account_id,
                XianyuAccountRuntime.tenant_id == tenant_id,
            )
        )
        await db.delete(account)
        await db.commit()
        return ResultObject.success(DeleteAccountRespDTO(message="删除成功"))
    except Exception as e:
        await _rollback_safely(db, operation="delete account")
        return safe_route_failure(
            logger, e, operation="delete account", user_message="删除账号失败，请稍后重试"
        )


@router.post("/detail", response_model=ResultObject[GetAccountDetailRespDTO])
async def get_account_detail(
    req: GetAccountDetailReqDTO,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        tenant_id = current_user.get("tenant_id")
        result = await db.execute(
            select(XianyuAccount).where(
                XianyuAccount.id == req.account_id,
                *_account_access_conditions(current_user),
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            return ResultObject.failed("账号不存在")
        return ResultObject.success(GetAccountDetailRespDTO(account=account_to_dto(account)))
    except Exception as e:
        return safe_route_failure(
            logger, e, operation="get account detail", user_message="获取账号详情失败，请稍后重试"
        )


@router.post("/refreshProfile", response_model=ResultObject[RefreshAccountProfileRespDTO])
async def refresh_account_profile(
    req: RefreshAccountProfileReqDTO,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        tenant_id = current_user.get("tenant_id")
        result = await db.execute(
            select(XianyuAccount).where(
                XianyuAccount.id == req.account_id,
                *_account_access_conditions(current_user),
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            return ResultObject.failed("账号不存在")
        return ResultObject.failed(
            "账号远程资料刷新能力暂不可用，资料未刷新",
            503,
        )
    except Exception as e:
        return safe_route_failure(
            logger, e, operation="refresh account profile", user_message="刷新账号资料失败，请稍后重试"
        )


@router.post("/loginCredential", response_model=ResultObject[LoginCredentialRespDTO])
async def get_login_credential(
    req: GetAccountDetailReqDTO,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        tenant_id = current_user.get("tenant_id")
        result = await db.execute(
            select(XianyuAccount).where(
                XianyuAccount.id == req.account_id,
                *_account_access_conditions(current_user),
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            return ResultObject.failed("账号不存在")
        auth_result = await db.execute(
            select(XianyuAccountAuth).where(
                XianyuAccountAuth.account_id == req.account_id,
                XianyuAccountAuth.tenant_id == tenant_id,
                XianyuAccountAuth.deleted == 0,
            )
        )
        auth = auth_result.scalar_one_or_none()
        return ResultObject.success(LoginCredentialRespDTO(
            account_id=account.id,
            login_username=auth.login_username if auth else None,
            login_password="***" if auth and auth.encrypted_login_password else None,
            has_login_password=bool(auth and auth.encrypted_login_password),
            show_browser=bool(auth and auth.show_browser),
        ))
    except Exception as e:
        return safe_route_failure(
            logger, e, operation="get login credential", user_message="获取登录凭据失败，请稍后重试"
        )


def extract_unb_from_cookie(cookie: str) -> str:
    if not cookie:
        return None
    for part in cookie.split(";"):
        part = part.strip()
        if part.startswith("unb="):
            return part[4:]
    return None


def extract_m_h5_tk_from_cookie(cookie: str) -> str:
    """从 Cookie 字符串中提取 _m_h5_tk 值。"""
    if not cookie:
        return ""
    import re
    match = re.search(r'_m_h5_tk=([^;]+)', cookie)
    return match.group(1) if match else ""


@router.post("/updateCookie", response_model=ResultObject[dict])
async def update_account_cookie(
    data: dict = {},
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """更新账号的 Cookie，同时自动提取 _m_h5_tk 并重置 cookie_status 为正常。
    
    请求体: {"accountId": 1, "cookie": "完整Cookie字符串"}
    """
    try:
        account_id = data.get("accountId")
        cookie = data.get("cookie", "")
        if not account_id or not cookie:
            return ResultObject.validate_failed("accountId 和 cookie 不能为空")

        tenant_id = current_user.get("tenant_id")
        try:
            account_id = int(account_id)
            tenant_id = int(tenant_id)
        except (TypeError, ValueError):
            return ResultObject.validate_failed("accountId 必须为正整数")
        if account_id <= 0 or tenant_id <= 0:
            return ResultObject.validate_failed("accountId 必须为正整数")

        account_result = await db.execute(
            select(XianyuAccount.id).where(
                XianyuAccount.id == account_id,
                *_account_access_conditions(current_user),
            )
        )
        if account_result.scalar_one_or_none() is None:
            return ResultObject.failed("账号不存在", code=404)
        auth_result = await db.execute(
            select(XianyuAccountAuth.id).where(
                XianyuAccountAuth.account_id == account_id,
                XianyuAccountAuth.tenant_id == tenant_id,
                XianyuAccountAuth.deleted == 0,
            )
        )
        if auth_result.scalar_one_or_none() is None:
            return ResultObject.failed("账号登录凭据状态异常，请重新添加账号", code=409)

        # 提取 _m_h5_tk
        m_h5_tk = extract_m_h5_tk_from_cookie(cookie)
        if not m_h5_tk:
            logger.warning("updateCookie: Cookie 中未提取到 _m_h5_tk accountId=%s", account_id)

        # 更新 auth 表
        await db.execute(
            text(
                "UPDATE xianyu_account_auth SET encrypted_cookie = :cookie, "
                "encrypted_token = :token, cookie_status = 0, "
                "last_login_status_code = :code, last_login_status_message = :message, "
                "last_login_check_time = NOW(), updated_time = NOW() "
                "WHERE account_id = :aid AND tenant_id = :tid"
            ),
            {
                "cookie": encrypt_cookie_for_storage(cookie),
                "token": encrypt_cookie_for_storage(m_h5_tk) if m_h5_tk else None,
                "code": "COOKIE_UPDATED",
                "message": "Cookie 已更新，等待统一登录校验",
                "aid": account_id,
                "tid": tenant_id
            }
        )
        # 更新 runtime 表
        await db.execute(
            text(
                "UPDATE xianyu_account_runtime SET cookie_status = 0, "
                "last_login_status_code = :code, last_login_status_message = :message, "
                "last_login_check_time = NOW(), updated_time = NOW() "
                "WHERE account_id = :aid AND tenant_id = :tid"
            ),
            {
                "code": "COOKIE_UPDATED",
                "message": "Cookie 已更新，等待统一登录校验",
                "aid": account_id,
                "tid": tenant_id
            }
        )

        await db.commit()

        # Cookie 已更新并重置 cookie_status=1，清除账号状态通知去重标记（内存 + DB），
        # 以便下次再次失效时能重新发送通知。
        try:
            from app.services.notify_dispatcher import clear_all_account_status_notifications
            await clear_all_account_status_notifications(tenant_id, int(account_id))
        except Exception:
            logger.debug("clear_all_account_status_notifications 调用异常，忽略", exc_info=True)

        logger.info(
            "updateCookie: 已更新账号 Cookie accountId=%s tokenPresent=%s",
            account_id,
            bool(m_h5_tk),
        )

        return ResultObject.success({
            "message": "Cookie 更新成功",
            "accountId": account_id,
            "hasToken": bool(m_h5_tk),
        })
    except Exception as e:
        await _rollback_safely(db, operation="update account cookie")
        return safe_route_failure(
            logger, e, operation="update account cookie", user_message="Cookie 更新失败，请稍后重试"
        )


# ============================================================
# Cookie/Token 自动刷新调度器接口
# ============================================================
@router.get("/refresh/status", response_model=ResultObject[dict])
async def get_refresh_status(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """获取 Cookie/Token 刷新调度器状态"""
    try:
        from app.services.cookie_token_refresher import get_dispatcher_status
        raw_status = await get_dispatcher_status()
        tenant_id = int(current_user.get("tenant_id"))
        user_id = int(current_user.get("user_id") or 0)
        account_query = select(XianyuAccount.id).where(
            XianyuAccount.tenant_id == tenant_id,
            XianyuAccount.deleted == 0,
        )
        if user_id > 0:
            account_query = account_query.where(
                or_(XianyuAccount.user_id == user_id, XianyuAccount.user_id.is_(None))
            )
        allowed_account_ids = set((await db.execute(account_query)).scalars().all())
        accounts = []
        for raw in raw_status.get("accounts", []):
            try:
                if int(raw.get("tenantId")) != tenant_id:
                    continue
                account_id = int(raw.get("accountId"))
            except (TypeError, ValueError):
                continue
            if account_id not in allowed_account_ids:
                continue
            accounts.append({
                "accountId": account_id,
                "nextCookieKeepalive": raw.get("nextCookieKeepalive"),
                "nextMh5tkRefresh": raw.get("nextMh5tkRefresh"),
                "nextWsTokenRefresh": raw.get("nextWsTokenRefresh"),
                "lastCookieKeepaliveOk": bool(raw.get("lastCookieKeepaliveOk")),
                "lastMh5tkRefreshOk": bool(raw.get("lastMh5tkRefreshOk")),
                "lastWsTokenRefreshOk": bool(raw.get("lastWsTokenRefreshOk")),
                "lastError": "最近一次刷新失败，请重试" if raw.get("lastError") else "",
            })
        raw_config = raw_status.get("config") or {}
        safe_config_keys = {
            "cookieKeepaliveIntervalMinutes",
            "mh5tkRefreshMinHours",
            "mh5tkRefreshMaxHours",
            "wsTokenRefreshMinHours",
            "wsTokenRefreshMaxHours",
            "accountIntervalMinSeconds",
            "accountIntervalMaxSeconds",
        }
        return ResultObject.success({
            "running": bool(raw_status.get("running")),
            "accountsCount": len(accounts),
            "config": {key: raw_config.get(key) for key in safe_config_keys if key in raw_config},
            "accounts": accounts,
        })
    except Exception as e:
        return safe_route_failure(
            logger, e, operation="get account refresh status", user_message="刷新服务状态暂时无法读取"
        )


@router.post("/refresh/force", response_model=ResultObject[dict])
async def force_refresh_account(
    data: dict = {},
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """手动触发单账号刷新
    请求体: {"accountId": 1, "refreshType": "all|cookie|mh5tk|ws_token"}
    """
    try:
        account_id = data.get("accountId")
        tenant_id = current_user.get("tenant_id")
        refresh_type = data.get("refreshType") or "all"
        if not account_id:
            return ResultObject.validate_failed("accountId 不能为空")
        try:
            account_id = int(account_id)
            tenant_id = int(tenant_id)
        except (TypeError, ValueError):
            return ResultObject.validate_failed("accountId 和 tenantId 必须为正整数")
        if account_id <= 0 or tenant_id <= 0:
            return ResultObject.validate_failed("accountId 和 tenantId 必须为正整数")
        if refresh_type not in ("all", "cookie", "mh5tk", "ws_token"):
            return ResultObject.validate_failed("refreshType 必须为 all/cookie/mh5tk/ws_token")

        user_id = int(current_user.get("user_id") or 0)
        account_query = select(XianyuAccount.id).where(
            XianyuAccount.id == account_id,
            XianyuAccount.tenant_id == tenant_id,
            XianyuAccount.deleted == 0,
        )
        if user_id > 0:
            account_query = account_query.where(
                or_(XianyuAccount.user_id == user_id, XianyuAccount.user_id.is_(None))
            )
        if (await db.execute(account_query)).scalar_one_or_none() is None:
            return ResultObject.failed("账号不存在", code=404)

        from app.services.cookie_token_refresher import force_refresh_account as _force
        result = await _force(account_id, tenant_id, refresh_type)
        raw_details = result.get("details") if isinstance(result, dict) else {}
        safe_details = {
            key: value if value in {"ok", "failed", "skipped"} else "failed"
            for key, value in (raw_details or {}).items()
            if key in {"cookie", "mh5tk", "ws_token"}
        }
        if not result.get("success"):
            error_code = result.get("errorCode")
            if error_code == "ACCOUNT_NOT_FOUND":
                return ResultObject(code=404, msg="账号不存在", data={"success": False, "details": safe_details})
            return ResultObject(
                code=409,
                msg="账号刷新未完成，请检查登录状态后重试",
                data={"success": False, "details": safe_details},
            )
        return ResultObject.success({"success": True, "details": safe_details})
    except Exception as e:
        return safe_route_failure(
            logger,
            e,
            operation="force account refresh",
            user_message="账号刷新服务暂时不可用",
            code=503,
        )
