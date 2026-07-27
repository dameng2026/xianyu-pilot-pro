"""
评价管理路由。

仅用于鱼小铺账号（xianyu_account.fish_shop_user=1）。普通闲鱼账号不调用评价接口。

路由：
- GET  /rates                   查询本地缓存的评价列表（支持 accountId/category/keyword/page/pageSize）
- POST /rates/sync              触发同步（单账号或全部鱼小铺账号）
- GET  /rates/sync-status       查询同步状态（缓存是否过期、是否正在同步）
- GET  /rates/overview          查询概览统计
- POST /rates/create            创建评价（写操作，需多重校验）
- GET  /rates/fish-shop-accounts 列出鱼小铺账号（用于下拉框）

后端权限校验：
- 调用前判断 fish_shop_user=1（rate_service.verify_fish_shop_account）
- 创建评价校验订单归属（防止跨账号评价）
- 不接受前端传入任意 Cookie
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.database import get_db
from ....core.response import ResultObject
from ....services.rate_service import (
    SUPPORTED_CATEGORIES,
    query_local_rates,
    sync_rates_for_account,
    sync_all_rates,
    get_sync_status,
    get_rate_overview,
    create_rate,
    list_fish_shop_accounts,
)
from ..deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rates")


@router.get("")
async def list_rates(
    accountId: Optional[int] = Query(None, description="账号ID，不传则聚合全部鱼小铺账号"),
    category: str = Query("all", description="评价分类：all/pending/done"),
    keyword: Optional[str] = Query(None, description="关键词搜索：订单号/商品ID/商品标题/买家昵称"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """查询本地缓存的评价列表（多账号聚合 + 分类筛选 + 关键词搜索 + 分页）。

    策略（需求第九节）：缓存优先，前端先展示本地数据，后台按需刷新。
    本接口仅查询本地数据库，不触发闲鱼请求。
    """
    tenant_id = int(current_user.get("tenant_id"))
    if category not in SUPPORTED_CATEGORIES:
        return ResultObject.failed(f"不支持的评价分类：{category}", code=400)
    try:
        result = await query_local_rates(
            db, tenant_id,
            account_id=accountId,
            category=category,
            keyword=keyword,
            page=page,
            page_size=pageSize,
        )
        return ResultObject.success(result)
    except Exception as exc:
        logger.exception("查询评价列表失败 tenantId=%s", tenant_id)
        return ResultObject.failed(f"查询评价列表失败: {type(exc).__name__}")


@router.post("/sync")
async def trigger_sync(
    body: Optional[dict] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """触发评价同步。

    body:
        {"accountId": 123}  同步单个账号
        {} 或不传             同步全部鱼小铺账号

    同步策略（需求第九节、第十节）：
    - 首次同步（无缓存）：完整分页同步
    - 后续快速刷新：仅第一页，发现变化时继续获取剩余页
    - 已有同步任务在运行时返回 TASK_ALREADY_RUNNING
    """
    tenant_id = int(current_user.get("tenant_id"))
    account_id = None
    if body and isinstance(body, dict):
        account_id = body.get("accountId")
        if account_id is not None:
            try:
                account_id = int(account_id)
            except (TypeError, ValueError):
                return ResultObject.failed("accountId 参数无效", code=400)

    try:
        if account_id is not None:
            result = await sync_rates_for_account(db, account_id, tenant_id)
        else:
            result = await sync_all_rates(db, tenant_id)
    except Exception as exc:
        logger.exception("触发评价同步失败 tenantId=%s accountId=%s", tenant_id, account_id)
        return ResultObject.failed(f"触发同步失败: {type(exc).__name__}")

    if not result.get("ok"):
        if result.get("error") == "TASK_ALREADY_RUNNING":
            return ResultObject.success(
                {"syncId": result.get("syncId"), "alreadyRunning": True},
                message="该账号正在同步中，请稍后刷新查看",
            )
        return ResultObject.failed(result.get("error") or "同步失败")

    return ResultObject.success(result, message="同步已触发")


@router.get("/sync-status")
async def get_sync_status_endpoint(
    accountId: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """查询同步状态（缓存是否过期、是否正在同步、最后同步时间）。"""
    tenant_id = int(current_user.get("tenant_id"))
    try:
        result = await get_sync_status(db, tenant_id, account_id=accountId)
        return ResultObject.success(result)
    except Exception as exc:
        logger.exception("查询评价同步状态失败 tenantId=%s", tenant_id)
        return ResultObject.failed(f"查询同步状态失败: {type(exc).__name__}")


@router.get("/overview")
async def get_overview_endpoint(
    accountId: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """查询评价概览统计（总数、待评价、已评价、最近同步时间）。

    好评、中评、差评统计仅在评价等级数值映射得到可靠确认后才可展示（需求第十二节）。
    """
    tenant_id = int(current_user.get("tenant_id"))
    try:
        result = await get_rate_overview(db, tenant_id, account_id=accountId)
        return ResultObject.success(result)
    except Exception as exc:
        logger.exception("查询评价概览失败 tenantId=%s", tenant_id)
        return ResultObject.failed(f"查询评价概览失败: {type(exc).__name__}")


@router.post("/create")
async def create_rate_endpoint(
    body: Optional[dict] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """创建评价（写操作）。

    body:
        {
            "accountId": 123,
            "orderId": "订单ID",
            "rate": 1,            # 评价等级（当前仅支持 1=好评）
            "feedback": "评价内容",
            "anonymous": true
        }

    安全要求（需求第二十三节）：
    - 后端再次校验账号归属与鱼小铺权限
    - 校验 orderId 属于该账号
    - 不接受前端传入任意 Cookie
    - 同一账号同一订单同时只能存在一个评价请求
    """
    tenant_id = int(current_user.get("tenant_id"))
    if not body or not isinstance(body, dict):
        return ResultObject.failed("请求参数不能为空", code=400)

    account_id = body.get("accountId")
    order_id = body.get("orderId")
    rate = body.get("rate")
    feedback = body.get("feedback")
    anonymous = body.get("anonymous")

    if account_id is None:
        return ResultObject.failed("accountId 不能为空", code=400)
    try:
        account_id = int(account_id)
    except (TypeError, ValueError):
        return ResultObject.failed("accountId 参数无效", code=400)

    if not order_id or not isinstance(order_id, str):
        return ResultObject.failed("orderId 不能为空且必须为字符串", code=400)

    if rate is None:
        return ResultObject.failed("rate 不能为空", code=400)
    try:
        rate = int(rate)
    except (TypeError, ValueError):
        return ResultObject.failed("rate 参数无效", code=400)

    if feedback is None or not isinstance(feedback, str):
        return ResultObject.failed("feedback 不能为空", code=400)

    if anonymous is None or not isinstance(anonymous, bool):
        return ResultObject.failed("anonymous 必须为明确布尔值", code=400)

    try:
        result = await create_rate(
            db, account_id, order_id, rate, feedback, anonymous, tenant_id
        )
    except Exception as exc:
        logger.exception(
            "创建评价异常 tenantId=%s accountId=%s orderId=%s",
            tenant_id, account_id, order_id,
        )
        return ResultObject.failed(f"创建评价异常: {type(exc).__name__}")

    if not result.get("ok"):
        if result.get("error") == "CREATE_RATE_IN_PROGRESS":
            return ResultObject.success(
                {"alreadyInProgress": True},
                message="该订单正在提交评价，请稍后",
            )
        return ResultObject.failed(result.get("error") or "创建评价失败")

    return ResultObject.success(result.get("data") or {}, message=result.get("message") or "评价已提交")


@router.get("/fish-shop-accounts")
async def list_fish_shop_accounts_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """列出当前租户下所有鱼小铺账号（用于前端账号选择下拉框）。

    普通闲鱼账号不会出现在此列表中（前端据此判断是否显示"不支持评价管理"提示）。
    """
    tenant_id = int(current_user.get("tenant_id"))
    try:
        accounts = await list_fish_shop_accounts(db, tenant_id)
        return ResultObject.success({"accounts": accounts})
    except Exception as exc:
        logger.exception("查询鱼小铺账号列表失败 tenantId=%s", tenant_id)
        return ResultObject.failed(f"查询鱼小铺账号列表失败: {type(exc).__name__}")
