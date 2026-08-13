"""
鱼小铺卖家数据概览路由。

仅统计鱼小铺账号（fish_shop_user=1），普通闲鱼账号不进入统计。

接口：
- GET /fish-shop-data/summary?accountId=&dateType=

参数：
- accountId：可选，不传或为空表示"全部账号"（仅聚合鱼小铺账号）
- dateType：recent1d / recent7d / recent30d，默认 recent7d

返回 ResultObject：
- code=200：成功，data 为结构化汇总
- code=503：服务异常或全部账号失败
- code=409：单账号模式下 Cookie 失效
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.database import get_db
from ....core.response import ResultObject
from ..deps import get_current_user
from ....services.fish_shop_datacompass import (
    ALLOWED_DATE_TYPES,
    BROWSE_ALLOWED_DATE_TYPES,
    DEFAULT_DATE_TYPE,
    fetch_browse_summary,
    fetch_seller_summary,
)
from ....services.xianyu_goods_sync import (
    XianyuAuthExpiredError,
    XianyuRiskControlError,
    XianyuProviderRejectedError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fish-shop-data")


@router.get("/summary")
async def get_seller_summary(
    accountId: Optional[int] = Query(None, description="鱼小铺账号 ID，不传表示全部账号"),
    dateType: str = Query(DEFAULT_DATE_TYPE, description="时间范围：recent1d / recent7d / recent30d"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """获取鱼小铺卖家数据概览。"""
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        return ResultObject.failed("缺少租户上下文，请重新登录")

    user_id = current_user.get("user_id")
    safe_date_type = dateType if dateType in ALLOWED_DATE_TYPES else DEFAULT_DATE_TYPE
    # 显式拒绝普通账号 ID：前端虽然过滤，后端再次校验
    # account_id 是否为鱼小铺账号由 fetch_seller_summary 内部判断
    safe_account_id = accountId if accountId and accountId > 0 else None

    try:
        payload = await fetch_seller_summary(
            db=db,
            tenant_id=tenant_id,
            account_id=safe_account_id,
            date_type=safe_date_type,
            user_id=user_id,
        )
        return ResultObject.success(payload)
    except XianyuAuthExpiredError as e:
        msg = str(e) or "闲鱼账号登录状态已失效，请重新登录后再查看"
        logger.warning(
            "fish_shop_data_summary cookie_expired tenant_id=%s accountId=%s dateType=%s",
            tenant_id, safe_account_id, safe_date_type,
        )
        return ResultObject.failed(msg, code=409, data={"errorType": "cookie_expired"})
    except (XianyuRiskControlError, XianyuProviderRejectedError) as e:
        msg = str(e) or "鱼小铺数据获取失败，请稍后重试"
        logger.warning(
            "fish_shop_data_summary biz_fail tenant_id=%s accountId=%s dateType=%s errorType=%s",
            tenant_id, safe_account_id, safe_date_type, type(e).__name__,
        )
        return ResultObject.failed(msg, code=503, data={"errorType": "biz_failed"})
    except Exception as e:
        logger.warning(
            "fish_shop_data_summary unexpected_fail tenant_id=%s accountId=%s dateType=%s errorType=%s",
            tenant_id, safe_account_id, safe_date_type, type(e).__name__,
        )
        return ResultObject.failed("鱼小铺数据分析暂时不可用，请稍后重试", code=503)


@router.get("/browse")
async def get_browse_summary(
    accountId: Optional[int] = Query(None, description="鱼小铺账号 ID，不传表示全部账号"),
    dateType: str = Query(DEFAULT_DATE_TYPE, description="时间范围：recent1d / recent7d / recent30d / customDate"),
    dateRange: str = Query("", description="自定义日期范围，格式 yyyyMMdd|yyyyMMdd"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """获取鱼小铺流量分布（来源/商品/时间/地域）。"""
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        return ResultObject.failed("缺少租户上下文，请重新登录")

    user_id = current_user.get("user_id")
    safe_date_type = dateType if dateType in BROWSE_ALLOWED_DATE_TYPES else DEFAULT_DATE_TYPE
    safe_account_id = accountId if accountId and accountId > 0 else None

    if safe_date_type == "customDate":
        parts = (dateRange or "").split("|")
        if len(parts) != 2 or len(parts[0]) != 8 or len(parts[1]) != 8:
            return ResultObject.failed("自定义日期格式错误，应为 yyyyMMdd|yyyyMMdd", code=400)

    try:
        payload = await fetch_browse_summary(
            db=db,
            tenant_id=tenant_id,
            account_id=safe_account_id,
            date_type=safe_date_type,
            user_id=user_id,
            date_range=dateRange or "",
        )
        return ResultObject.success(payload)
    except XianyuAuthExpiredError as e:
        logger.warning(
            "fish_shop_data_browse cookie_expired tenant_id=%s accountId=%s dateType=%s",
            tenant_id, safe_account_id, safe_date_type,
        )
        return ResultObject.failed(
            str(e) or "闲鱼账号登录状态已失效，请重新登录后再查看",
            code=409,
            data={"errorType": "cookie_expired"},
        )
    except (XianyuRiskControlError, XianyuProviderRejectedError) as e:
        logger.warning(
            "fish_shop_data_browse biz_fail tenant_id=%s accountId=%s dateType=%s errorType=%s",
            tenant_id, safe_account_id, safe_date_type, type(e).__name__,
        )
        return ResultObject.failed(
            str(e) or "流量分布获取失败，请稍后重试",
            code=503,
            data={"errorType": "biz_failed"},
        )
    except Exception as e:
        logger.warning(
            "fish_shop_data_browse unexpected_fail tenant_id=%s accountId=%s dateType=%s errorType=%s",
            tenant_id, safe_account_id, safe_date_type, type(e).__name__,
        )
        return ResultObject.failed("流量分布暂时不可用，请稍后重试", code=503, data={"errorType": "unexpected"})
