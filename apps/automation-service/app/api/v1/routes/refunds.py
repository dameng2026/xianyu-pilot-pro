"""
退款管理路由。

仅用于鱼小铺账号（xianyu_account.fish_shop_user=1）。普通闲鱼账号不调用退款接口。

路由：
- GET  /refunds                       查询本地缓存的退款列表（支持 accountId/category/page/pageSize）
- POST /refunds/sync                   触发同步（单账号或全部鱼小铺账号）
- GET  /refunds/sync-status            查询同步状态（缓存是否过期、是否正在同步）
- POST /refunds/{refundId}/agree       同意退款（资金操作，需二次确认）
- GET  /refunds/detail                 查询退款详情（三接口并行 + 缓存优先 + 后台刷新）
- POST /refunds/detail/refresh         手动刷新退款详情（强制失效缓存并重新调用三接口）
- POST /refunds/detail/retry           单独重试某个失败接口（不重新请求成功接口）

后端权限校验：
- 调用前判断 fish_shop_user=1（refund_service.verify_fish_shop_account）
- 同意退款校验退款归属（防止跨账号退款）
- 退款详情校验账号归属 + 鱼小铺 + 退款归属 + orderId/refundId 关系
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
    get_refund_detail,
    refresh_refund_detail,
    retry_refund_detail_api,
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


# ============================================================
# 退款详情（需求第五~二十三节）
# ============================================================
# 三个 MTOP 接口并行调用，缓存优先 + 进行中请求去重 + 局部失败处理
# 后端多重校验：账号归属 + 鱼小铺 + 退款归属 + orderId/refundId 关系
# 普通闲鱼账号不得访问详情、不得通过修改 URL 参数绕过


@router.get("/detail")
async def get_refund_detail_endpoint(
    accountId: int = Query(..., description="退款所属账号ID（必须为鱼小铺账号）"),
    orderId: str = Query(..., description="目标订单ID（按字符串处理，避免大整数精度丢失）"),
    refundId: str = Query(..., description="目标退款ID"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """查询退款详情（缓存优先，过期后台刷新）。

    需求覆盖：
    - 第五节：进入详情先展示摘要，后台并行调用三接口
    - 第十九节：缓存优先 + 进行中请求去重 + 短时缓存
    - 第二十节：局部失败 + 单独重试
    - 第二十二节：深链接参数篡改防护（后端不信任前端传入，必须校验归属）

    返回结构：
        {
            "ok": true,
            "summary": {...}|null,        # 退款列表缓存摘要（立即展示）
            "detail": {                    # 组合详情（三接口并行）
                "serviceRecord": {...},    # 退款服务记录（接口一）
                "fullInfo": {...},         # 完整订单信息（接口二）
                "refundDetail": {...},     # 退款核心详情（接口三）
                "lastSuccessAt": iso|null,
                "partialFailure": bool
            }|null,
            "cached": bool,
            "cacheExpired": bool,
            "backendBackgroundRefreshTriggered": bool,
            "error": str|null
        }
    """
    tenant_id = int(current_user.get("tenant_id"))
    if not accountId or accountId <= 0:
        return ResultObject.failed("accountId 参数无效", code=400)
    if not orderId or not str(orderId).strip():
        return ResultObject.failed("orderId 不能为空", code=400)
    if not refundId or not str(refundId).strip():
        return ResultObject.failed("refundId 不能为空", code=400)

    try:
        result = await get_refund_detail(
            db, tenant_id, int(accountId), str(orderId), str(refundId)
        )
    except Exception as exc:
        return safe_route_failure(
            logger, exc, operation="get refund detail",
            user_message="查询退款详情失败，请稍后重试",
        )

    if not result.get("ok"):
        return ResultObject.failed(result.get("error") or "查询失败")
    return ResultObject.success(result)


@router.post("/detail/refresh")
async def refresh_refund_detail_endpoint(
    body: Optional[dict] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """手动刷新退款详情（强制失效缓存并重新调用三接口）。

    body:
        {"accountId": 123, "orderId": "...", "refundId": "..."}

    需求第十九节第8点：页面提供手动刷新。
    需求第十九节第9点：刷新失败保留旧缓存。
    """
    tenant_id = int(current_user.get("tenant_id"))
    if not body or not isinstance(body, dict):
        return ResultObject.failed("请求体不能为空", code=400)
    account_id = body.get("accountId")
    order_id = body.get("orderId")
    refund_id = body.get("refundId")
    if not account_id or not isinstance(account_id, (int, str)) or int(account_id) <= 0:
        return ResultObject.failed("accountId 参数无效", code=400)
    if not order_id or not isinstance(order_id, str) or not order_id.strip():
        return ResultObject.failed("orderId 不能为空", code=400)
    if not refund_id or not isinstance(refund_id, str) or not refund_id.strip():
        return ResultObject.failed("refundId 不能为空", code=400)

    try:
        result = await refresh_refund_detail(
            db, tenant_id, int(account_id), str(order_id), str(refund_id)
        )
    except Exception as exc:
        return safe_route_failure(
            logger, exc, operation="refresh refund detail",
            user_message="刷新退款详情失败，请稍后重试",
        )

    if not result.get("ok"):
        return ResultObject.failed(result.get("error") or "刷新失败")
    return ResultObject.success(result)


@router.post("/detail/retry")
async def retry_refund_detail_endpoint(
    body: Optional[dict] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """单独重试某个失败接口（不重新请求成功的接口）。

    body:
        {
            "accountId": 123,
            "orderId": "...",
            "refundId": "...",
            "api": "service_record" | "full_info" | "refund_detail"
        }

    需求第二十节：失败区域显示错误和单独重试，单独重试时只请求失败接口。
    """
    tenant_id = int(current_user.get("tenant_id"))
    if not body or not isinstance(body, dict):
        return ResultObject.failed("请求体不能为空", code=400)
    account_id = body.get("accountId")
    order_id = body.get("orderId")
    refund_id = body.get("refundId")
    api = body.get("api")
    if not account_id or not isinstance(account_id, (int, str)) or int(account_id) <= 0:
        return ResultObject.failed("accountId 参数无效", code=400)
    if not order_id or not isinstance(order_id, str) or not order_id.strip():
        return ResultObject.failed("orderId 不能为空", code=400)
    if not refund_id or not isinstance(refund_id, str) or not refund_id.strip():
        return ResultObject.failed("refundId 不能为空", code=400)
    if api not in ("service_record", "full_info", "refund_detail"):
        return ResultObject.failed("api 参数必须是 service_record / full_info / refund_detail", code=400)

    try:
        result = await retry_refund_detail_api(
            db, tenant_id, int(account_id), str(order_id), str(refund_id), str(api)
        )
    except Exception as exc:
        return safe_route_failure(
            logger, exc, operation="retry refund detail api",
            user_message="重试失败接口失败，请稍后重试",
        )

    if not result.get("ok"):
        return ResultObject.failed(result.get("error") or "重试失败")
    return ResultObject.success(result)
