import asyncio
import datetime
import logging
import math

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.database import get_db
from ....core.http_failures import safe_route_failure
from ....core.response import ResultObject
from ....models.entities import XianyuTradeOrder
from ....schemas.order import (
    ConfirmShipmentReqDTO,
    OrderListData,
    OrderQueryReqDTO,
    OrderVO,
    SoldOrderSyncReqDTO,
)
from ....services.xianyu_api_service import confirm_order_shipment
from ..deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/order")


def trade_order_to_vo(order: XianyuTradeOrder) -> OrderVO:
    return OrderVO(
        id=order.id,
        account_id=order.account_id,
        external_order_id=order.external_order_id,
        order_status=order.order_status,
        buyer_name=order.buyer_name,
        total_amount=order.total_amount,
        create_time=str(order.create_time) if order.create_time else None,
        pay_time=str(order.pay_time) if order.pay_time else None,
        xianyu_account_id=order.account_id,
        order_id=order.external_order_id,
        total_price=order.total_amount,
    )


@router.post("/list", response_model=ResultObject[OrderListData])
async def list_orders(
    req: OrderQueryReqDTO,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        page_num = max(req.page_num or 1, 1)
        page_size = max(min(req.page_size or 20, 100), 1)

        tenant_id = current_user.get("tenant_id")
        query = select(XianyuTradeOrder).where(XianyuTradeOrder.tenant_id == tenant_id)
        if req.xianyu_account_id is not None:
            query = query.where(XianyuTradeOrder.account_id == req.xianyu_account_id)
        if req.xy_goods_id:
            query = query.where(XianyuTradeOrder.external_order_id == req.xy_goods_id)
        if req.order_status is not None:
            query = query.where(XianyuTradeOrder.order_status == req.order_status)

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page_num - 1) * page_size
        query = query.order_by(XianyuTradeOrder.id.desc()).offset(offset).limit(page_size)
        result = await db.execute(query)
        orders = result.scalars().all()

        records = [trade_order_to_vo(o) for o in orders]
        pages = math.ceil(total / page_size) if total > 0 else 0
        return ResultObject.success(
            OrderListData(
                records=records,
                total=total,
                page_num=page_num,
                page_size=page_size,
                pages=pages,
            )
        )
    except Exception as e:
        return safe_route_failure(logger, e, operation="list orders", user_message="查询订单列表失败，请稍后重试")


@router.post("/confirmShipment", response_model=ResultObject[str])
async def confirm_shipment(
    req: ConfirmShipmentReqDTO,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """确认发货：小刀订单走免拼发货接口，普通订单走虚拟发货接口。

    优先使用请求体中的 is_bargain 字段判断订单类型；
    若未提供则查询数据库 xianyu_trade_order.is_bargain 字段。
    """
    tenant_id = current_user.get("tenant_id")
    try:
        is_bargain = bool(req.is_bargain)
        # 若请求未指定 is_bargain，从数据库查
        if not is_bargain and req.order_id:
            row = (await db.execute(
                select(XianyuTradeOrder).where(
                    XianyuTradeOrder.tenant_id == tenant_id,
                    XianyuTradeOrder.external_order_id == req.order_id,
                    XianyuTradeOrder.deleted == 0,
                )
            )).scalar_one_or_none()
            if row and row.is_bargain:
                is_bargain = True

        result = await asyncio.to_thread(
            confirm_order_shipment,
            req.xianyu_account_id,
            req.order_id,
            is_bargain=is_bargain,
            item_id=req.item_id,
            buyer_id=req.buyer_id,
        )
        if result and result.get("success"):
            return ResultObject.success("确认发货成功")
        return ResultObject.failed(
            (result.get("message") if result else None) or "确认发货失败，请稍后重试",
            code=503,
        )
    except Exception as e:
        return safe_route_failure(
            logger, e, operation="confirm shipment",
            user_message="确认发货失败，请稍后重试",
        )


@router.post("/confirmFreeshipping", response_model=ResultObject[str])
async def confirm_freeshipping(
    req: ConfirmShipmentReqDTO,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """免拼发货（小刀订单专用）。

    调用闲鱼 mtop.idle.groupon.activity.seller.freeshipping 接口，
    必须提供 item_id 和 buyer_id。
    """
    try:
        if not req.item_id or not req.buyer_id:
            return ResultObject.validate_failed("免拼发货必须提供商品ID和买家ID")
        result = confirm_order_shipment(
            req.xianyu_account_id,
            req.order_id,
            is_bargain=True,
            item_id=req.item_id,
            buyer_id=req.buyer_id,
        )
        if result and result.get("success"):
            return ResultObject.success("免拼发货成功")
        return ResultObject.failed(
            (result.get("message") if result else None) or "免拼发货失败，请稍后重试",
            code=503,
        )
    except Exception as e:
        return safe_route_failure(
            logger, e, operation="confirm freeshipping",
            user_message="免拼发货失败，请稍后重试",
        )


@router.post("/syncSoldOrders", response_model=ResultObject[dict])
async def sync_sold_orders(
    req: SoldOrderSyncReqDTO,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    logger.warning(
        "拒绝调用未接入同步流程的旧版订单同步接口: tenantId=%s accountId=%s",
        current_user.get("tenant_id"),
        req.xianyu_account_id,
    )
    return ResultObject.failed(
        "旧版订单同步接口未接入同步流程，同步未启动；请使用订单同步任务接口",
        code=503,
    )
