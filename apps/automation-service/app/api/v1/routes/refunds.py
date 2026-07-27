"""
退款管理路由。

仅用于鱼小铺账号（xianyu_account.fish_shop_user=1）。普通闲鱼账号不调用退款接口。

路由：
- GET  /refunds                 查询本地缓存的退款列表（支持 accountId/category/page/pageSize）
- POST /refunds/sync             触发同步（单账号或全部鱼小铺账号）
- GET  /refunds/sync-status      查询同步状态（缓存是否过期、是否正在同步）
- POST /refunds/{refundId}/agree 同意退款（资金操作，需二次确认）

后端权限校验：
- 调用前判断 fish_shop_user=1（refund_service.verify_fish_shop_account）
- 同意退款校验退款归属（防止跨账号退款）
- 不接受前端传入任意 Cookie
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.database import get_db
from ....core.http_failures import safe_route_failure
from ....core.response import ResultObject
from ....services.refund_service import (
    SUPPORTED_CATEGORIES,
    query_local_refunds,
    sync_refunds_for_account,
    sync_all_refunds,
    get_sync_status,
    agree_refund,
    list_fish_shop_accounts,
)
from ..deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/refunds")


@router.get("")
async def list_refunds(
    accountId: Optional[int] = Query(None, description="账号ID，不传则聚合全部鱼小铺账号"),
    category: str = Query("all", description="退款分类：all/unshipped/shipped/return/freight"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """查询本地缓存的退款列表（多账号聚合 + 分类筛选 + 分页）。

    策略（需求第十五节）：缓存优先，前端先展示本地数据，后台按需刷新。
    本接口仅查询本地数据库，不触发闲鱼请求。
    """
    tenant_id = int(current_user.get("tenant_id"))
    if category not in SUPPORTED_CATEGORIES:
        return ResultObject.failed(f"不支持的退款分类：{category}", code=400)
    try:
        result = await query_local_refunds(
            db, tenant_id,
            account_id=accountId,
            category=category,
            page=page,
            page_size=pageSize,
        )
        return ResultObject.success(result)
    except Exception as exc:
        return safe_route_failure(logger, exc, operation="list refunds", user_message="查询退款列表失败，请稍后重试")


@router.post("/sync")
async def trigger_sync(
    body: Optional[dict] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """触发退款同步。

    body:
        {"accountId": 123}  同步单个账号
        {} 或不传             同步全部鱼小铺账号

    同步策略（需求第十七节）：
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
            result = await sync_refunds_for_account(db, account_id, tenant_id)
        else:
            result = await sync_all_refunds(db, tenant_id)
    except Exception as exc:
        return safe_route_failure(logger, exc, operation="trigger refund sync", user_message="触发同步失败，请稍后重试")

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
        return safe_route_failure(logger, exc, operation="get refund sync status", user_message="查询同步状态失败，请稍后重试")


@router.post("/{refund_id}/agree")
async def agree_refund_endpoint(
    refund_id: str,
    body: Optional[dict] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """同意退款（资金操作）。

    body:
        {"accountId": 123}  退款所属账号

    安全要求（需求第二十三节）：
    - 后端再次校验账号归属与鱼小铺权限
    - 校验 refundId 属于该账号
    - 校验当前退款仍允许同意退款（rightVO.btnList 返回 agreeRefundApply）
    - 不接受前端传入任意 Cookie
    """
    tenant_id = int(current_user.get("tenant_id"))
    if not refund_id:
        return ResultObject.failed("refundId 不能为空", code=400)

    account_id = None
    if body and isinstance(body, dict):
        account_id = body.get("accountId")
    if account_id is None:
        return ResultObject.failed("accountId 不能为空", code=400)
    try:
        account_id = int(account_id)
    except (TypeError, ValueError):
        return ResultObject.failed("accountId 参数无效", code=400)

    try:
        result = await agree_refund(db, account_id, refund_id, tenant_id)
    except Exception as exc:
        return safe_route_failure(logger, exc, operation="agree refund", user_message="同意退款失败，请稍后重试")

    if not result.get("ok"):
        return ResultObject.failed(result.get("error") or "同意退款失败")

    return ResultObject.success(result.get("data") or {}, message=result.get("message") or "同意退款请求已提交")


@router.get("/fish-shop-accounts")
async def list_fish_shop_accounts_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """列出当前租户下所有鱼小铺账号（用于前端账号选择下拉框）。

    普通闲鱼账号不会出现在此列表中（前端据此判断是否显示"不支持退款管理"提示）。
    """
    tenant_id = int(current_user.get("tenant_id"))
    try:
        accounts = await list_fish_shop_accounts(db, tenant_id)
        return ResultObject.success({"accounts": accounts})
    except Exception as exc:
        return safe_route_failure(logger, exc, operation="list fish shop accounts", user_message="查询鱼小铺账号列表失败，请稍后重试")
