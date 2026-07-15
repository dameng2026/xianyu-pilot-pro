import logging
from datetime import datetime, timedelta, date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, cast, Date
from ....core.database import get_db
from ....core.http_failures import log_route_failure, safe_route_failure
from ....core.response import ResultObject
from ....models.entities import (
    XianyuAccount, XianyuGoods, XianyuTradeOrder, XianyuMessage, DeliveryRecord
)
from ....schemas.dashboard import DashboardStatsRespDTO
from ..deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard")


@router.post("/stats", response_model=ResultObject[DashboardStatsRespDTO])
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        tenant_id = current_user.get("tenant_id")

        account_count_result = await db.execute(
            select(func.count()).select_from(XianyuAccount).where(
                XianyuAccount.tenant_id == tenant_id
            )
        )
        account_count = account_count_result.scalar() or 0

        item_count_result = await db.execute(
            select(func.count()).select_from(XianyuGoods).where(
                XianyuGoods.tenant_id == tenant_id
            )
        )
        item_count = item_count_result.scalar() or 0

        selling_item_count_result = await db.execute(
            select(func.count()).where(
                XianyuGoods.status == 0,
                XianyuGoods.tenant_id == tenant_id
            )
        )
        selling_item_count = selling_item_count_result.scalar() or 0

        off_shelf_item_count_result = await db.execute(
            select(func.count()).where(
                XianyuGoods.status == 1,
                XianyuGoods.tenant_id == tenant_id
            )
        )
        off_shelf_item_count = off_shelf_item_count_result.scalar() or 0

        sold_item_count_result = await db.execute(
            select(func.count()).where(
                XianyuGoods.status == 2,
                XianyuGoods.tenant_id == tenant_id
            )
        )
        sold_item_count = sold_item_count_result.scalar() or 0

        # 从 delivery_record 获取发货统计
        delivery_stats = await _get_delivery_stats(db, tenant_id)

        return ResultObject.success(DashboardStatsRespDTO(
            account_count=account_count,
            item_count=item_count,
            selling_item_count=selling_item_count,
            off_shelf_item_count=off_shelf_item_count,
            sold_item_count=sold_item_count,
            delivery_success_count=delivery_stats["success"],
            delivery_fail_count=delivery_stats["failed"],
            pending_delivery_count=delivery_stats["pending"]
        ))
    except Exception as e:
        return safe_route_failure(logger, e, operation="dashboard stats", user_message="首页统计数据暂不可用，请稍后重试", code=503)


@router.get("/summary")
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """获取数据面板汇总统计（兼容前端 DataPage.vue）"""
    try:
        tenant_id = current_user.get("tenant_id")
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # 今日订单数 — 使用 create_time 统计今日创建的订单
        today_order_result = await db.execute(
            select(func.count()).select_from(XianyuTradeOrder).where(
                XianyuTradeOrder.tenant_id == tenant_id,
                XianyuTradeOrder.created_time >= today_start
            )
        )
        today_order_count = today_order_result.scalar() or 0

        # 发货统计 — 从 delivery_record 表统计（不要查 xianyu_trade_order.delivery_status）
        delivery_stats = await _get_delivery_stats(db, tenant_id)

        # AI 自动回复数
        auto_reply_result = await db.execute(
            select(func.count()).select_from(XianyuMessage).where(
                XianyuMessage.tenant_id == tenant_id,
                XianyuMessage.is_auto_reply == 1
            )
        )
        auto_reply_count = auto_reply_result.scalar() or 0

        return ResultObject.success({
            "todayOrderCount": today_order_count,
            "orderCount": today_order_count,
            "deliverySuccessCount": delivery_stats["success"],
            "deliveryFailCount": delivery_stats["failed"],
            "pendingDeliveryCount": delivery_stats["pending"],
            "autoReplyCount": auto_reply_count,
            "aiReplyCount": auto_reply_count,
        })
    except Exception as e:
        return safe_route_failure(logger, e, operation="dashboard summary", user_message="数据面板汇总暂不可用，请稍后重试", code=503)


@router.get("/sales-trend")
async def get_dashboard_sales_trend(
    days: int = Query(default=7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """获取近 N 天销售趋势（兼容前端 DataPage.vue）"""
    try:
        tenant_id = current_user.get("tenant_id")
        today = date.today()
        date_labels = [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]
        start_date = today - timedelta(days=days - 1)

        # 每日发货成功数 — 从 delivery_record 统计
        success_rows_result = await db.execute(
            select(
                cast(DeliveryRecord.created_time, Date).label("d"),
                func.count().label("c")
            ).where(
                DeliveryRecord.tenant_id == tenant_id,
                DeliveryRecord.deleted == 0,
                DeliveryRecord.delivery_status == "success",
                cast(DeliveryRecord.created_time, Date) >= start_date
            ).group_by(cast(DeliveryRecord.created_time, Date))
        )
        success_map = {str(row.d): row.c for row in success_rows_result}

        # 每日发货失败数 — 从 delivery_record 统计
        fail_rows_result = await db.execute(
            select(
                cast(DeliveryRecord.created_time, Date).label("d"),
                func.count().label("c")
            ).where(
                DeliveryRecord.tenant_id == tenant_id,
                DeliveryRecord.deleted == 0,
                DeliveryRecord.delivery_status == "failed",
                cast(DeliveryRecord.created_time, Date) >= start_date
            ).group_by(cast(DeliveryRecord.created_time, Date))
        )
        fail_map = {str(row.d): row.c for row in fail_rows_result}

        # 每日 AI 回复数
        reply_rows_result = await db.execute(
            select(
                cast(XianyuMessage.created_time, Date).label("d"),
                func.count().label("c")
            ).where(
                XianyuMessage.tenant_id == tenant_id,
                XianyuMessage.is_auto_reply == 1,
                cast(XianyuMessage.created_time, Date) >= start_date
            ).group_by(cast(XianyuMessage.created_time, Date))
        )
        reply_map = {str(row.d): row.c for row in reply_rows_result}

        return ResultObject.success({
            "dates": date_labels,
            "deliverySuccess": [success_map.get(d, 0) for d in date_labels],
            "deliveryFail": [fail_map.get(d, 0) for d in date_labels],
            "aiReplies": [reply_map.get(d, 0) for d in date_labels],
        })
    except Exception as e:
        return safe_route_failure(logger, e, operation="dashboard sales trend", user_message="销售趋势暂不可用，请稍后重试", code=503)


async def _get_delivery_stats(db: AsyncSession, tenant_id: int) -> dict:
    """从 delivery_record 表统计发货成功/失败/待处理数量（按租户隔离）"""
    try:
        # 发货成功
        success_result = await db.execute(
            select(func.count()).select_from(DeliveryRecord).where(
                DeliveryRecord.tenant_id == tenant_id,
                DeliveryRecord.deleted == 0,
                DeliveryRecord.delivery_status == "success"
            )
        )
        success_count = success_result.scalar() or 0

        # 发货失败
        fail_result = await db.execute(
            select(func.count()).select_from(DeliveryRecord).where(
                DeliveryRecord.tenant_id == tenant_id,
                DeliveryRecord.deleted == 0,
                DeliveryRecord.delivery_status == "failed"
            )
        )
        fail_count = fail_result.scalar() or 0

        # 待发货
        pending_result = await db.execute(
            select(func.count()).select_from(DeliveryRecord).where(
                DeliveryRecord.tenant_id == tenant_id,
                DeliveryRecord.deleted == 0,
                DeliveryRecord.delivery_status == "pending"
            )
        )
        pending_count = pending_result.scalar() or 0

        return {"success": success_count, "failed": fail_count, "pending": pending_count}
    except Exception as e:
        log_route_failure(logger, e, operation="dashboard delivery stats")
        raise RuntimeError("delivery statistics unavailable") from e
