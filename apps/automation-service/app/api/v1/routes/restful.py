"""
RESTful API router - provides RESTful endpoints for frontend compatibility.
Wraps existing POST-style business logic under RESTful resource paths.
"""
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from ....core.database import get_db
from ....core.http_failures import safe_route_failure
from ....core.response import ResultObject
from ....models.entities import (
    Notification,
    XianyuAccount,
    XianyuAccountAuth,
    XianyuAccountRuntime,
    XianyuGoods,
    XianyuMessage,
    XianyuTradeOrder,
)
from ..deps import get_current_user
from .account import _account_access_conditions, account_to_dto

logger = logging.getLogger(__name__)
router = APIRouter()


def account_to_profile_dto(account):
    """Convert XianyuAccount to a dict for RESTful responses."""
    ip_location = None
    if hasattr(account, 'province') and hasattr(account, 'city'):
        if account.province or account.city:
            ip_location = f"{account.province or ''} {account.city or ''}".strip()
    return {
        "id": account.id,
        "unb": account.external_uid,
        "nickname": account.nickname,
        "avatar": account.avatar_url,
        "account_note": account.remark,
        "remark": account.remark,
        "ip_location": ip_location,
        "province": account.province if hasattr(account, 'province') else None,
        "city": account.city if hasattr(account, 'city') else None,
        "account_level": account.account_level if hasattr(account, 'account_level') else 0,
        "status": account.status,
        "created_time": str(account.created_time) if account.created_time else None,
        "proxy_password": "***",
        "login_password": "***",
        "display_name": account.nickname,
    }


def _db_status_to_fe(db_status):
    """DB(1=在售,0=下架,2=已售) → FE(0=在售,1=下架,2=已售)"""
    mapping = {1: 0, 0: 1, 2: 2}
    return mapping.get(db_status, db_status or 1)


def goods_to_dto(goods):
    """Convert XianyuGoods to a dict for RESTful responses."""
    return {
        "id": goods.id,
        "xianyu_account_id": goods.account_id,
        "xy_goods_id": goods.external_goods_id,
        "goods_title": goods.title,
        "goods_price": goods.sold_price or goods.price,
        "goods_stock": goods.stock,
        "goods_image": goods.cover_pic or goods.image_url,
        "cover_pic": goods.cover_pic,
        "sold_price": goods.sold_price,
        "quantity": goods.quantity,
        "exposure_count": goods.exposure_count,
        "view_count": goods.view_count,
        "want_count": goods.want_count,
        "detail_url": goods.detail_url,
        "detail_info": goods.detail_info,
        "sort_order": goods.sort_order,
        "status": _db_status_to_fe(goods.status),
        "created_time": str(goods.created_time) if goods.created_time else None,
    }


def trade_order_to_dto(order):
    """Convert XianyuTradeOrder to a dict for RESTful responses."""
    return {
        "id": order.id,
        "account_id": order.account_id,
        "xianyu_account_id": order.account_id,
        "external_order_id": order.external_order_id,
        "order_id": order.external_order_id,
        "order_status": order.order_status,
        "buyer_name": order.buyer_name,
        "total_amount": order.total_amount,
        "total_price": order.total_amount,
        "create_time": str(order.create_time) if order.create_time else None,
        "pay_time": str(order.pay_time) if order.pay_time else None,
    }


def chat_message_to_dto(msg):
    """Convert XianyuMessage to a dict for RESTful responses."""
    return {
        "id": msg.id,
        "xianyu_account_id": msg.account_id,
        "session_id": str(msg.conversation_id) if msg.conversation_id else None,
        "from_user_id": msg.from_user_id,
        "to_user_id": msg.to_user_id,
        "content": msg.content,
        "message_type": msg.message_type,
        "direction": msg.direction,
        "created_time": str(msg.created_time) if msg.created_time else None,
    }
# ======================== ACCOUNTS ========================

@router.get("/xianyu/accounts", response_model=ResultObject)
async def restful_get_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = current_user.get("tenant_id")
        user_id = current_user.get("user_id")
        # JOIN auth 表获取 cookie_status
        query = select(
            XianyuAccount,
            XianyuAccountAuth.cookie_status,
            XianyuAccountAuth.last_login_status_code,
            XianyuAccountAuth.last_login_status_message,
            XianyuAccountAuth.last_login_check_time,
        ).outerjoin(
            XianyuAccountAuth,
            (XianyuAccountAuth.account_id == XianyuAccount.id) &
            (XianyuAccountAuth.tenant_id == XianyuAccount.tenant_id),
        ).where(
            XianyuAccount.tenant_id == tenant_id,
            XianyuAccount.deleted == 0,
        )
        # 按 user_id 过滤，确保用户只能看到自己所属的账号
        if user_id:
            from sqlalchemy import or_
            query = query.where(
                or_(
                    XianyuAccount.user_id == user_id,
                    XianyuAccount.user_id.is_(None),
                )
            )
        query = query.order_by(XianyuAccount.id.desc())
        result = await db.execute(query)
        rows = result.all()
        data = []
        for account, cookie_status, login_status_code, login_status_message, login_check_time in rows:
            dto = account_to_dto(account)
            normalized_cookie_status = cookie_status if cookie_status is not None else 0
            dto["cookie_status"] = normalized_cookie_status
            dto["cookieStatus"] = normalized_cookie_status
            dto["login_status_code"] = login_status_code
            dto["loginStatusCode"] = login_status_code
            dto["login_status_message"] = login_status_message
            dto["loginStatusMessage"] = login_status_message
            dto["login_check_time"] = str(login_check_time) if login_check_time else None
            dto["loginCheckTime"] = str(login_check_time) if login_check_time else None
            dto["auth_usable"] = normalized_cookie_status == 1 and str(login_status_code or "").upper() == "OK"
            dto["authUsable"] = dto["auth_usable"]
            data.append(dto)
        return ResultObject.success(data)
    except Exception as e:
        return safe_route_failure(logger, e, operation="rest list accounts", user_message="获取账号列表失败，请稍后重试")
@router.get("/xianyu/accounts/summary", response_model=ResultObject)
async def restful_get_accounts_summary(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = current_user.get("tenant_id")
        base = select(XianyuAccount).where(
            XianyuAccount.tenant_id == tenant_id,
            XianyuAccount.deleted == 0,
        )
        total_result = await db.execute(select(func.count()).select_from(base.subquery()))
        total = total_result.scalar() or 0
        normal_result = await db.execute(
            select(func.count()).select_from(
                base.where(XianyuAccount.status == 1).subquery()
            )
        )
        normal = normal_result.scalar() or 0
        verify_result = await db.execute(
            select(func.count()).select_from(
                base.where(XianyuAccount.status != 1).subquery()
            )
        )
        verify = verify_result.scalar() or 0
        ws_online_result = await db.execute(
            select(func.count()).select_from(XianyuAccountRuntime).where(
                XianyuAccountRuntime.tenant_id == tenant_id,
                XianyuAccountRuntime.deleted == 0,
                XianyuAccountRuntime.ws_status == 1,
            )
        )
        ws_online = ws_online_result.scalar() or 0
        cookie_warn_result = await db.execute(
            select(func.count()).select_from(XianyuAccountAuth).where(
                XianyuAccountAuth.tenant_id == tenant_id,
                XianyuAccountAuth.deleted == 0,
                func.coalesce(XianyuAccountAuth.cookie_status, 0) != 1,
            )
        )
        cookie_warn = cookie_warn_result.scalar() or 0
        return ResultObject.success({
            "total": total,
            "normal": normal,
            "verify": verify,
            "wsOnline": ws_online,
            "cookieWarn": cookie_warn,
        })
    except Exception as e:
        return safe_route_failure(logger, e, operation="rest account summary", user_message="获取账号概览失败，请稍后重试")
# ======================== ACCOUNT DETAIL / UPDATE / DELETE ========================

@router.get("/xianyu/accounts/{account_id}", response_model=ResultObject)
async def restful_get_account_detail(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = current_user.get("tenant_id")
        result = await db.execute(
            select(XianyuAccount).where(
                XianyuAccount.id == account_id,
                *_account_access_conditions(current_user),
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            return ResultObject.failed("账号不存在")
        return ResultObject.success(account_to_dto(account))
    except Exception as e:
        return safe_route_failure(logger, e, operation="rest account detail", user_message="获取账号详情失败，请稍后重试")

@router.put("/xianyu/accounts/{account_id}", response_model=ResultObject)
async def restful_update_account(
    account_id: int,
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = current_user.get("tenant_id")
        result = await db.execute(
            select(XianyuAccount).where(
                XianyuAccount.id == account_id,
                *_account_access_conditions(current_user),
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            return ResultObject.failed("账号不存在")
        remark = body.get("account_note") or body.get("remark")
        if remark:
            account.remark = remark.strip()
        await db.commit()
        await db.refresh(account)
        return ResultObject.success(account_to_dto(account))
    except Exception as e:
        return safe_route_failure(logger, e, operation="rest update account", user_message="更新账号失败，请稍后重试")

@router.delete("/xianyu/accounts/{account_id}", response_model=ResultObject)
async def restful_delete_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = current_user.get("tenant_id")
        result = await db.execute(
            select(XianyuAccount).where(
                XianyuAccount.id == account_id,
                *_account_access_conditions(current_user),
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            return ResultObject.failed("账号不存在")
        account.deleted = 1
        await db.commit()
        return ResultObject.success({"message": "删除成功"})
    except Exception as e:
        return safe_route_failure(logger, e, operation="rest delete account", user_message="删除账号失败，请稍后重试")
@router.post("/xianyu/accounts/{account_id}/refresh", response_model=ResultObject)
async def restful_refresh_account_profile(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = current_user.get("tenant_id")
        result = await db.execute(
            select(XianyuAccount).where(
                XianyuAccount.id == account_id,
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
            logger,
            e,
            operation="rest refresh account profile",
            user_message="刷新账号资料失败，请稍后重试",
        )

@router.get("/xianyu/accounts/{account_id}/credential", response_model=ResultObject)
async def restful_get_account_credential(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = current_user.get("tenant_id")
        result = await db.execute(
            select(XianyuAccount).where(
                XianyuAccount.id == account_id,
                *_account_access_conditions(current_user),
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            return ResultObject.failed("账号不存在")
        auth_result = await db.execute(
            select(XianyuAccountAuth).where(
                XianyuAccountAuth.account_id == account_id,
                XianyuAccountAuth.tenant_id == tenant_id,
                XianyuAccountAuth.deleted == 0,
            )
        )
        auth = auth_result.scalar_one_or_none()
        return ResultObject.success({
            "account_id": account.id,
            "login_username": auth.login_username if auth else None,
            "login_password": "***" if auth and auth.encrypted_login_password else None,
            "has_login_password": bool(auth and auth.encrypted_login_password),
            "show_browser": bool(auth and auth.show_browser),
        })
    except Exception as e:
        return safe_route_failure(logger, e, operation="rest account credential", user_message="获取账号登录凭据失败，请稍后重试")
# ======================== GOODS  ========================

@router.get("/xianyu/goods", response_model=ResultObject)
async def restful_get_goods(
    account_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = current_user.get("tenant_id")
        query = select(XianyuGoods).where(XianyuGoods.tenant_id == tenant_id)
        if account_id is not None:
            query = query.where(XianyuGoods.account_id == account_id)
        count_q = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_q)).scalar() or 0
        offset = (page - 1) * page_size
        result = await db.execute(
            query.order_by(XianyuGoods.id.desc()).offset(offset).limit(page_size)
        )
        items = result.scalars().all()
        records = [goods_to_dto(g) for g in items]
        return ResultObject.success({"records": records, "total": total, "page": page, "page_size": page_size})
    except Exception as e:
        return safe_route_failure(logger, e, operation="rest list goods", user_message="获取商品列表失败，请稍后重试")

@router.get("/xianyu/goods/{goods_id}", response_model=ResultObject)
async def restful_get_goods_detail(
    goods_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = current_user.get("tenant_id")
        result = await db.execute(
            select(XianyuGoods).where(
                XianyuGoods.id == goods_id,
                XianyuGoods.tenant_id == tenant_id,
            )
        )
        goods = result.scalar_one_or_none()
        if not goods:
            return ResultObject.failed("商品不存在")
        return ResultObject.success(goods_to_dto(goods))
    except Exception as e:
        return safe_route_failure(logger, e, operation="rest goods detail", user_message="获取商品详情失败，请稍后重试")

@router.get("/xianyu/goods/syncProgress/{sync_id}", response_model=ResultObject)
async def restful_goods_sync_progress(
    sync_id: str,
    current_user: dict = Depends(get_current_user),
):
    return ResultObject.failed("该旧版同步进度查询能力不可用", 503)

@router.get("/xianyu/goods/syncing/{account_id}", response_model=ResultObject)
async def restful_goods_syncing(
    account_id: int,
    current_user: dict = Depends(get_current_user),
):
    return ResultObject.failed("该旧版同步状态查询能力不可用", 503)
# ======================== ORDERS ========================

@router.get("/xianyu/orders", response_model=ResultObject)
async def restful_get_orders(
    account_id: Optional[int] = Query(None),
    order_status: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = current_user.get("tenant_id")
        query = select(XianyuTradeOrder).where(XianyuTradeOrder.tenant_id == tenant_id)
        if account_id is not None:
            query = query.where(XianyuTradeOrder.account_id == account_id)
        if order_status is not None:
            query = query.where(XianyuTradeOrder.order_status == order_status)
        count_q = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_q)).scalar() or 0
        offset = (page - 1) * page_size
        result = await db.execute(
            query.order_by(XianyuTradeOrder.id.desc()).offset(offset).limit(page_size)
        )
        orders = result.scalars().all()
        records = [trade_order_to_dto(o) for o in orders]
        return ResultObject.success({"records": records, "total": total, "page": page, "page_size": page_size})
    except Exception as e:
        return safe_route_failure(logger, e, operation="rest list orders", user_message="获取订单列表失败，请稍后重试")

@router.get("/xianyu/orders/{order_id}", response_model=ResultObject)
async def restful_get_order_detail(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = current_user.get("tenant_id")
        result = await db.execute(
            select(XianyuTradeOrder).where(
                XianyuTradeOrder.id == order_id,
                XianyuTradeOrder.tenant_id == tenant_id,
            )
        )
        order = result.scalar_one_or_none()
        if not order:
            return ResultObject.failed("订单不存在")
        return ResultObject.success(trade_order_to_dto(order))
    except Exception as e:
        return safe_route_failure(logger, e, operation="rest order detail", user_message="获取订单详情失败，请稍后重试")

# ======================== MESSAGES ========================

@router.get("/xianyu/messages", response_model=ResultObject)
async def restful_get_messages(
    account_id: Optional[int] = Query(None),
    session_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = current_user.get("tenant_id")
        query = select(XianyuMessage).where(XianyuMessage.tenant_id == tenant_id, XianyuMessage.deleted == 0)
        if account_id is not None:
            query = query.where(XianyuMessage.account_id == account_id)
        count_q = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_q)).scalar() or 0
        offset = (page - 1) * page_size
        result = await db.execute(
            query.order_by(XianyuMessage.id.desc()).offset(offset).limit(page_size)
        )
        msgs = result.scalars().all()
        records = [chat_message_to_dto(m) for m in msgs]
        return ResultObject.success({"records": records, "total": total, "page": page, "page_size": page_size})
    except Exception as e:
        return safe_route_failure(logger, e, operation="rest list messages", user_message="获取消息列表失败，请稍后重试")

# ======================== NOTIFICATIONS ========================

@router.get("/xianyu/notifications", response_model=ResultObject)
async def restful_get_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = current_user.get("tenant_id")
        query = select(Notification).where(Notification.tenant_id == tenant_id, Notification.deleted == 0)
        count_q = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_q)).scalar() or 0
        offset = (page - 1) * page_size
        result = await db.execute(
            query.order_by(Notification.id.desc()).offset(offset).limit(page_size)
        )
        notifications = result.scalars().all()
        return ResultObject.success({
            "records": [
                {
                    "id": n.id,
                    "title": n.title,
                    "content": n.content,
                    "type": n.notification_type,
                    "read": n.is_read,
                    "created_time": str(n.created_time) if n.created_time else None,
                }
                for n in notifications
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        })
    except Exception as e:
        return safe_route_failure(logger, e, operation="rest list notifications", user_message="获取通知列表失败，请稍后重试")

@router.post("/xianyu/accounts", response_model=ResultObject)
async def restful_create_account(
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = current_user.get("tenant_id")
        user_id = current_user.get("user_id")
        nickname = body.get("nickname", "")
        remark = body.get("account_note") or body.get("remark", "")
        external_uid = body.get("unb") or body.get("external_uid", "")
        account = XianyuAccount(
            tenant_id=tenant_id,
            user_id=user_id,
            external_uid=external_uid,
            nickname=nickname,
            remark=remark,
            status=1,
            deleted=0,
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)
        return ResultObject.success(account_to_profile_dto(account))
    except Exception as e:
        return safe_route_failure(logger, e, operation="rest create account", user_message="创建账号失败，请稍后重试")

# ======================== DASHBOARD ========================

@router.get("/xianyu/dashboard", response_model=ResultObject)
async def restful_get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = current_user.get("tenant_id")
        # Account counts
        acct_query = select(XianyuAccount).where(
            XianyuAccount.tenant_id == tenant_id,
            XianyuAccount.deleted == 0,
        )
        total_accts = (await db.execute(
            select(func.count()).select_from(acct_query.subquery())
        )).scalar() or 0
        # Order counts
        order_query = select(XianyuTradeOrder).where(
            XianyuTradeOrder.tenant_id == tenant_id
        )
        total_orders = (await db.execute(
            select(func.count()).select_from(order_query.subquery())
        )).scalar() or 0
        # Goods counts
        goods_query = select(XianyuGoods).where(
            XianyuGoods.tenant_id == tenant_id
        )
        total_goods = (await db.execute(
            select(func.count()).select_from(goods_query.subquery())
        )).scalar() or 0
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_orders = (await db.execute(
            select(func.count()).select_from(XianyuTradeOrder).where(
                XianyuTradeOrder.tenant_id == tenant_id,
                XianyuTradeOrder.created_time >= today_start,
            )
        )).scalar() or 0
        return ResultObject.success({
            "accountCount": total_accts,
            "orderCount": total_orders,
            "goodsCount": total_goods,
            "todayOrderCount": today_orders,
        })
    except Exception as e:
        return safe_route_failure(logger, e, operation="rest dashboard", user_message="获取工作台数据失败，请稍后重试")
# ======================== AI PUBLISH ========================
from fastapi import Body
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.response import ResultObject
from app.api.v1.deps import get_db, get_current_user
from fastapi import Depends

@router.post('/item/publish', response_model=ResultObject)
async def publish_item(
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return ResultObject.failed(
        "该旧版发布接口未接入闲鱼发布能力，商品未发布；请使用工作流发布接口",
        503,
    )
