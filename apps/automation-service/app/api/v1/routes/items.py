import asyncio
import logging
import math
import uuid
import hashlib
import datetime
import threading
from decimal import Decimal, ROUND_DOWN
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update as sql_update, and_, desc
from ....core.database import get_db
from ....core.http_failures import PublicRouteValidationError, log_route_failure, safe_route_failure
from ....core.response import ResultObject
from ....core.cookie_crypto import decrypt_cookie_if_needed
from ....models.entities import XianyuGoods, XianyuAccount, XianyuAccountAuth, XianyuGoodsSyncTask
from ....schemas.common import (
    ItemListReqDTO, ItemReqDTO, ItemDTO, ItemListRespDTO, ItemDetailRespDTO,
    RefreshItemsRespDTO, DeleteItemRespDTO,
    ItemOperateReqDTO, ItemBatchOperateReqDTO, UpdateItemPriceReqDTO,
)
from .internal import verify_internal_token
from ....services.xianyu_goods_sync import XianyuItemOperator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/item")

_polish_tasks: dict[str, dict] = {}
_polish_account_tasks: dict[tuple[int, int], str] = {}
_polish_tasks_lock = threading.Lock()
_POLISH_TASK_RETENTION_SECONDS = 3600


async def _record_goods_reconciliation(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    action: str,
    external_goods_id: str,
) -> str | None:
    """Persist evidence that a remote mutation succeeded while local state did not."""
    sync_id = f"reconcile-{uuid.uuid4().hex}"
    try:
        await db.rollback()
        db.add(XianyuGoodsSyncTask(
            sync_id=sync_id,
            tenant_id=tenant_id,
            account_id=account_id,
            status="failed",
            progress=0,
            error_message=(
                f"RECONCILIATION_REQUIRED action={action} externalGoodsId={external_goods_id}"
            )[:500],
            finished_time=datetime.datetime.now(),
        ))
        await db.commit()
        return sync_id
    except Exception as error:
        log_route_failure(logger, error, operation="persist goods reconciliation task")
        try:
            await db.rollback()
        except Exception:
            pass
        return None


def _polish_task_public_view(task: dict | None) -> dict | None:
    if not task:
        return None
    return {k: v for k, v in task.items() if not k.startswith("_")}


def _cleanup_expired_polish_tasks() -> None:
    cutoff = datetime.datetime.now().timestamp() - _POLISH_TASK_RETENTION_SECONDS
    with _polish_tasks_lock:
        expired_task_ids = [
            task_id
            for task_id, task in _polish_tasks.items()
            if not task.get("running") and task.get("_updatedTs", 0) < cutoff
        ]
        for task_id in expired_task_ids:
            task = _polish_tasks.pop(task_id, None)
            if not task:
                continue
            key = (int(task.get("tenantId") or 0), int(task.get("accountId") or 0))
            if _polish_account_tasks.get(key) == task_id:
                _polish_account_tasks.pop(key, None)


def _get_running_polish_task(account_id: int, tenant_id: int) -> dict | None:
    with _polish_tasks_lock:
        task_id = _polish_account_tasks.get((tenant_id, account_id))
        task = _polish_tasks.get(task_id) if task_id else None
        if task and task.get("running"):
            return _polish_task_public_view(task)
        if task_id:
            _polish_account_tasks.pop((tenant_id, account_id), None)
        return None


def _get_polish_task(task_id: str) -> dict | None:
    with _polish_tasks_lock:
        return _polish_task_public_view(_polish_tasks.get(task_id))


def _create_polish_task(account_id: int, tenant_id: int, total: int) -> dict:
    now = datetime.datetime.now()
    task_id = str(uuid.uuid4())[:16]
    task = {
        "taskId": task_id,
        "accountId": account_id,
        "tenantId": tenant_id,
        "status": "queued",
        "running": True,
        "total": total,
        "processed": 0,
        "polished": 0,
        "failed": 0,
        "progress": 0,
        "needManual": False,
        "message": "擦亮任务已提交，后台处理中",
        "error": None,
        "startedAt": now.isoformat(),
        "finishedAt": None,
        "updatedAt": now.isoformat(),
        "_updatedTs": now.timestamp(),
    }
    _cleanup_expired_polish_tasks()
    with _polish_tasks_lock:
        _polish_tasks[task_id] = task
        _polish_account_tasks[(tenant_id, account_id)] = task_id
    return _polish_task_public_view(task)


def _update_polish_task(
    task_id: str,
    *,
    status: str | None = None,
    running: bool | None = None,
    total: int | None = None,
    processed: int | None = None,
    polished: int | None = None,
    failed: int | None = None,
    progress: int | None = None,
    need_manual: bool | None = None,
    message: str | None = None,
    error: str | None = None,
    finished_at: str | None = None,
) -> dict | None:
    now = datetime.datetime.now()
    with _polish_tasks_lock:
        task = _polish_tasks.get(task_id)
        if not task:
            return None
        updates = {
            "status": status,
            "running": running,
            "total": total,
            "processed": processed,
            "polished": polished,
            "failed": failed,
            "progress": progress,
            "needManual": need_manual,
            "message": message,
            "error": error,
            "finishedAt": finished_at,
        }
        for key, value in updates.items():
            if value is not None:
                task[key] = value
        task["updatedAt"] = now.isoformat()
        task["_updatedTs"] = now.timestamp()
        if task.get("running") is False:
            key = (int(task.get("tenantId") or 0), int(task.get("accountId") or 0))
            if _polish_account_tasks.get(key) == task_id:
                _polish_account_tasks.pop(key, None)
        return _polish_task_public_view(task)


async def _run_polish_task(
    task_id: str,
    *,
    account_id: int,
    tenant_id: int,
    cookie_str: str,
    is_fish_shop: bool,
    goods_items: list[dict],
) -> None:
    polished = 0
    failed = 0
    processed = 0
    total = len(goods_items)
    operator = XianyuItemOperator(cookie_str, is_fish_shop=is_fish_shop)
    _update_polish_task(
        task_id,
        status="running",
        running=True,
        total=total,
        processed=0,
        polished=0,
        failed=0,
        progress=0,
        need_manual=False,
        message="擦亮任务执行中",
        error=None,
    )

    try:
        already_done_count = 0
        first_error = None  # 记录第一个失败错误，便于诊断
        for processed, goods_item in enumerate(goods_items, start=1):
            result = await asyncio.to_thread(operator.polish, goods_item["xyGoodId"])
            if result.get("success"):
                polished += 1
                if result.get("already_done"):
                    already_done_count += 1
            else:
                failed += 1
                # 记录第一个失败错误信息（截断到200字符避免过长）
                if first_error is None and result.get("error"):
                    first_error = str(result["error"])[:200]

            progress = 100 if total <= 0 else min(99, math.floor(processed / total * 100))
            error_message = result.get("error")
            if result.get("need_manual"):
                _update_polish_task(
                    task_id,
                    status="need_manual",
                    running=False,
                    total=total,
                    processed=processed,
                    polished=polished,
                    failed=failed,
                    progress=max(progress, 1),
                    need_manual=True,
                    message="擦亮暂停：检测到风控，请完成滑块验证后重试",
                    error=error_message,
                    finished_at=datetime.datetime.now().isoformat(),
                )
                return

            # 进度提示包含"已擦亮过"的统计，让用户清楚知道实际状态
            if already_done_count > 0:
                msg = f"擦亮任务执行中（已擦亮过 {already_done_count} 件）"
            else:
                msg = "擦亮任务执行中"
            _update_polish_task(
                task_id,
                status="running",
                running=True,
                total=total,
                processed=processed,
                polished=polished,
                failed=failed,
                progress=progress,
                need_manual=False,
                message=msg,
                error=error_message,
            )

        # 完成提示：区分"新擦亮"和"已擦亮过"
        # 注意：必须加 polished > 0 前置条件，否则 polished=0, already_done_count=0 时
        # 0==0 为 True 会误显示"均已擦亮过"，掩盖全部失败的真实情况
        if polished > 0 and already_done_count == polished:
            message = f"擦亮完成：{polished} 件商品均已擦亮过（无需重复擦亮）"
        elif already_done_count > 0:
            message = f"擦亮完成：成功 {polished}（其中 {already_done_count} 件已擦亮过），失败 {failed}"
        else:
            message = f"擦亮完成：成功 {polished}，失败 {failed}"

        # 如果有失败，追加第一个错误信息便于诊断（避免用户看到"失败37"但不知道原因）
        if failed > 0 and first_error:
            message = f"{message}。失败原因示例：{first_error}"

        _update_polish_task(
            task_id,
            status="completed",
            running=False,
            total=total,
            processed=processed,
            polished=polished,
            failed=failed,
            progress=100,
            need_manual=False,
            message=message,
            error=None,
            finished_at=datetime.datetime.now().isoformat(),
        )
    except Exception as exc:
        log_route_failure(logger, exc, operation="background goods polish task")
        _update_polish_task(
            task_id,
            status="failed",
            running=False,
            total=total,
            processed=processed,
            polished=polished,
            failed=failed if failed else max(processed - polished, 0),
            progress=100 if total > 0 and processed >= total else min(99, math.floor(processed / total * 100)) if total else 0,
            need_manual=False,
            message="擦亮失败，请稍后重试；如持续失败，请向管理员提供任务编号",
            error="INTERNAL_ERROR",
            finished_at=datetime.datetime.now().isoformat(),
        )


async def _submit_polish_task(
    *,
    db: AsyncSession,
    account_id: int,
    tenant_id: int,
) -> ResultObject:
    running_task = _get_running_polish_task(account_id, tenant_id)
    if running_task:
        running_task["message"] = "该账号已有擦亮任务正在运行"
        return ResultObject.success(running_task)

    goods_query = select(XianyuGoods).where(
        XianyuGoods.account_id == account_id,
        XianyuGoods.tenant_id == tenant_id,
        XianyuGoods.deleted == 0,
        XianyuGoods.status == 1,
    ).order_by(XianyuGoods.id.asc())
    goods_result = await db.execute(goods_query)
    goods_list = goods_result.scalars().all()
    goods_items = [
        {
            "xyGoodId": goods.external_goods_id,
            "title": goods.title or "",
        }
        for goods in goods_list
        if goods.external_goods_id
    ]

    if not goods_items:
        return ResultObject.success({
            "taskId": None,
            "status": "completed",
            "running": False,
            "total": 0,
            "processed": 0,
            "polished": 0,
            "failed": 0,
            "progress": 100,
            "needManual": False,
            "message": "没有找到在售商品",
            "error": None,
        })

    from ....services.xianyu_goods_sync import extract_token_from_cookie

    auth = await _get_account_auth(db, account_id, tenant_id)
    if not auth:
        return ResultObject.failed("账号未登录或 Cookie 已失效，请重新登录")
    cookie_str = decrypt_cookie_if_needed(auth.encrypted_cookie)

    token = extract_token_from_cookie(cookie_str)
    if not token:
        return ResultObject.failed("Cookie 中缺少 _m_h5_tk，请重新登录")

    is_fish_shop = await _is_fish_shop_account(db, account_id, tenant_id)
    task = _create_polish_task(account_id, tenant_id, len(goods_items))

    if not hasattr(polish_account_items, "_bg_tasks"):
        polish_account_items._bg_tasks = set()
    bg_task = asyncio.create_task(
        _run_polish_task(
            task["taskId"],
            account_id=account_id,
            tenant_id=tenant_id,
            cookie_str=cookie_str,
            is_fish_shop=is_fish_shop,
            goods_items=goods_items,
        )
    )
    polish_account_items._bg_tasks.add(bg_task)
    bg_task.add_done_callback(polish_account_items._bg_tasks.discard)

    return ResultObject.success(task)


def _db_status_to_fe(db_status: int | None) -> int:
    """
    将 DB 状态约定转换为前端状态约定。
    DB:   1=在售, 0=下架, 2=已售
    FE:   0=在售, 1=下架, 2=已售
    """
    mapping = {1: 0, 0: 1, 2: 2}
    return mapping.get(db_status, db_status or 1)


def goods_to_dto(goods: XianyuGoods) -> ItemDTO:
    """将 XianyuGoods 实体转换为 ItemDTO"""
    return ItemDTO(
        id=goods.id,
        xianyu_account_id=goods.account_id,
        xy_goods_id=goods.external_goods_id,
        goods_title=goods.title,
        goods_price=goods.sold_price or goods.price,
        goods_stock=goods.stock,
        goods_image=goods.cover_pic or goods.image_url,
        cover_pic=goods.cover_pic,
        sold_price=goods.sold_price,
        quantity=goods.quantity,
        exposure_count=goods.exposure_count,
        view_count=goods.view_count,
        want_count=goods.want_count,
        detail_url=goods.detail_url,
        detail_info=goods.detail_info,
        sort_order=goods.sort_order,
        status=_db_status_to_fe(goods.status),
        created_time=str(goods.created_time) if goods.created_time else None,
    )


def normalize_price(price: str) -> str:
    """
    标准化价格字符串。
    验证：不为空、正数、最多2位小数。
    返回标准化后的价格字符串（去除末尾多余的0和小数点）。
    """
    if not price or not price.strip():
        raise PublicRouteValidationError("价格不能为空")

    try:
        value = Decimal(price.strip())
    except Exception:
        raise PublicRouteValidationError(f"价格格式无效: {price}")

    if value <= 0:
        raise PublicRouteValidationError("价格必须大于0")

    # 检查小数位数
    if value.as_tuple().exponent < -2:
        raise PublicRouteValidationError("价格最多保留2位小数")

    # 标准化：去除多余的尾随零（避免 Decimal.normalize() 输出科学计数法）
    normalized = value.quantize(Decimal('0.00'), rounding=ROUND_DOWN)
    normalized_str = str(normalized)
    if '.' in normalized_str:
        normalized_str = normalized_str.rstrip('0').rstrip('.')
    return normalized_str


@router.post("/list", response_model=ResultObject[ItemListRespDTO])
async def list_items(
    req: ItemListReqDTO,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    try:
        page_num = max(req.page_num or 1, 1)
        page_size = max(min(req.page_size or 20, 100), 1)

        tenant_id = req.tenant_id
        if not tenant_id:
            return ResultObject.failed("缺少租户上下文")
        query = select(XianyuGoods).where(XianyuGoods.tenant_id == tenant_id)
        if req.xianyu_account_id is not None:
            query = query.where(XianyuGoods.account_id == req.xianyu_account_id)

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page_num - 1) * page_size
        query = query.order_by(XianyuGoods.id.desc()).offset(offset).limit(page_size)
        result = await db.execute(query)
        items = result.scalars().all()

        item_list = [goods_to_dto(i) for i in items]
        return ResultObject.success(ItemListRespDTO(items=item_list, total=total))
    except Exception as e:
        return safe_route_failure(logger, e, operation="list goods", user_message="获取商品列表失败，请稍后重试")


@router.post("/detail", response_model=ResultObject[ItemDetailRespDTO])
async def get_item_detail(
    req: ItemReqDTO,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    try:
        tenant_id = req.tenant_id
        if not tenant_id:
            return ResultObject.failed("缺少租户上下文")
        query = select(XianyuGoods).where(XianyuGoods.tenant_id == tenant_id)
        if req.xy_goods_id:
            query = query.where(XianyuGoods.external_goods_id == req.xy_goods_id)
        if req.xianyu_account_id is not None:
            query = query.where(XianyuGoods.account_id == req.xianyu_account_id)
        result = await db.execute(query)
        item = result.scalar_one_or_none()
        if not item:
            return ResultObject.failed("商品不存在")
        return ResultObject.success(ItemDetailRespDTO(item=goods_to_dto(item)))
    except Exception as e:
        return safe_route_failure(logger, e, operation="get goods detail", user_message="获取商品详情失败，请稍后重试")


# ---- 以下为前端兼容性存根端点 ----

@router.post("/refresh")
async def refresh_items(
    req: dict = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """
    同步商品：从闲鱼拉取商品列表并入库。
    请求参数: { xianyu_account_id: int }
    返回: { sync_id: str, message: str }
    """
    try:
        account_id = req.get("xianyu_account_id") or req.get("xianyuAccountId")
        if not account_id:
            return ResultObject.failed("缺少参数 xianyu_account_id")

        account_id = int(account_id)
        tenant_raw = req.get("tenantId") or req.get("tenant_id") or req.get("_tenantId")
        if not tenant_raw:
            return ResultObject.failed("缺少租户上下文")
        tenant_id = int(tenant_raw)
        # 检查是否已有运行中的同步任务：优先返回已有任务，避免重复创建。
        from ....services.xianyu_goods_sync import is_account_syncing
        running_result = await db.execute(
            select(XianyuGoodsSyncTask)
            .where(
                XianyuGoodsSyncTask.tenant_id == tenant_id,
                XianyuGoodsSyncTask.account_id == account_id,
                XianyuGoodsSyncTask.deleted == 0,
                XianyuGoodsSyncTask.status.in_(["queued", "running"]),
            )
            .order_by(desc(XianyuGoodsSyncTask.created_time), desc(XianyuGoodsSyncTask.id))
            .limit(1)
        )
        running_task = running_result.scalar_one_or_none()
        if running_task or is_account_syncing(account_id):
            return ResultObject.success({
                "sync_id": running_task.sync_id if running_task else None,
                "status": "running",
                "running": True,
                "message": "该账号已有同步任务正在运行",
            })

        # 获取账号信息
        account_result = await db.execute(
            select(XianyuAccount).where(
                XianyuAccount.id == account_id,
                XianyuAccount.tenant_id == tenant_id,
            )
        )
        account = account_result.scalar_one_or_none()
        if not account:
            return ResultObject.failed("账号不存在")

        # 获取 Cookie
        auth_result = await db.execute(
            select(XianyuAccountAuth).where(
                XianyuAccountAuth.account_id == account_id,
                XianyuAccountAuth.tenant_id == tenant_id,
            )
        )
        auth = auth_result.scalar_one_or_none()
        if not auth or not auth.encrypted_cookie:
            return ResultObject.failed("账号未登录或Cookie已失效，请重新登录")

        cookie_str = decrypt_cookie_if_needed(auth.encrypted_cookie)

        # 生成同步任务ID并落库，避免服务重启后完全丢失任务信息。
        sync_id = str(uuid.uuid4())[:16]
        now = datetime.datetime.now()
        db.add(XianyuGoodsSyncTask(
            sync_id=sync_id,
            tenant_id=tenant_id,
            account_id=account_id,
            status="queued",
            progress=0,
            started_time=now,
            deleted=0,
            created_time=now,
            updated_time=now,
        ))
        await db.commit()

        # 启动后台同步（不阻塞当前请求）
        import asyncio
        from ....services.xianyu_goods_sync import sync_goods_for_account

        async def _run_sync():
            try:
                await sync_goods_for_account(
                    account_id=account_id,
                    tenant_id=tenant_id,
                    cookie_str=cookie_str,
                    sync_id=sync_id,
                    db_session_factory=None,
                    async_fetch_detail=True,
                )
            except Exception as e:
                log_route_failure(logger, e, operation="background goods sync")

        # 保存任务强引用，避免被 GC 回收导致任务中途消失
        if not hasattr(refresh_items, "_bg_tasks"):
            refresh_items._bg_tasks = set()
        t = asyncio.create_task(_run_sync())
        refresh_items._bg_tasks.add(t)
        t.add_done_callback(refresh_items._bg_tasks.discard)

        logger.info("商品同步已启动: account_id=%d, sync_id=%s, tenant_id=%s", account_id, sync_id, tenant_id)

        return ResultObject.success({
            "sync_id": sync_id,
            "message": "同步已启动",
        })

    except Exception as e:
        return safe_route_failure(logger, e, operation="start goods sync", user_message="启动商品同步失败，请稍后重试")


@router.post("/publish")
async def publish_item(
    req: dict = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """
    发布商品到闲鱼。
    请求参数:
    {
        xianyuAccountId: int,       # 必填，闲鱼账号ID
        title: str,                 # 必填，标题(≤30字)
        description: str,           # 必填，描述(≤5000字)
        imageUrls: list[str],       # 必填，图片URL列表(最多10张)
        price: str|float,           # 必填，价格
        origPrice: str|float,       # 可选，原价
        stock: int,                 # 可选，库存
        category: str,              # 可选，分类名称
        location: str,              # 可选，位置描述
    }
    """
    try:
        account_id = req.get("xianyuAccountId") or req.get("xianyu_account_id")
        if not account_id:
            return ResultObject.failed("缺少参数 xianyuAccountId")
        account_id = int(account_id)

        tenant_raw = req.get("tenantId") or req.get("tenant_id") or req.get("_tenantId")
        if not tenant_raw:
            return ResultObject.failed("缺少租户上下文")
        tenant_id = int(tenant_raw)

        title = req.get("title", "").strip()
        if not title:
            return ResultObject.failed("宝贝标题不能为空")
        if len(title) > 30:
            return ResultObject.failed("宝贝标题不能超过30个字")

        description = req.get("description", "").strip()
        if not description:
            return ResultObject.failed("宝贝描述不能为空")
        if len(description) > 5000:
            return ResultObject.failed("宝贝描述不能超过5000字")

        image_urls = req.get("imageUrls", [])
        if not image_urls or not isinstance(image_urls, list):
            return ResultObject.failed("请至少上传一张商品图片")

        price = req.get("price", 0)
        try:
            price = float(price)
        except (ValueError, TypeError):
            return ResultObject.failed("价格格式不正确")
        if price <= 0:
            return ResultObject.failed("价格必须大于0")

        stock = req.get("stock", 1)
        try:
            stock = int(stock)
        except (ValueError, TypeError):
            stock = 1

        # 获取账号 Cookie
        from ....services.xianyu_goods_sync import extract_token_from_cookie
        auth = await _get_account_auth(db, account_id, tenant_id)
        if not auth:
            return ResultObject.failed("账号未登录或 Cookie 已失效，请重新登录")
        cookie_str = decrypt_cookie_if_needed(auth.encrypted_cookie)

        # 校验 Token
        token = extract_token_from_cookie(cookie_str)
        if not token:
            return ResultObject.failed("Cookie 中缺少 _m_h5_tk，请重新登录")

        # 构建发布数据
        item_data = {
            "title": title,
            "desc": description,
            "imageUrls": image_urls,
            "price": price,
            "quantity": stock,
        }

        # 可选字段
        orig_price = req.get("origPrice")
        if orig_price:
            item_data["origPrice"] = orig_price

        # 分类（优先用类目推荐 API，这里传参作为手动回退用）
        category = req.get("category", "")
        if category:
            item_data["category"] = {"catName": category}

        # 位置信息（来自前端省、市、区地址字典选择）
        location = req.get("location", {})
        if isinstance(location, dict) and location.get("poiName"):
            item_data["location"] = {
                "prov": location.get("prov", ""),
                "city": location.get("city", ""),
                "area": location.get("area", ""),
                "divisionId": str(location.get("divisionId", "")),
                "gps": location.get("gps", ""),
                "poiId": location.get("poiId", ""),
                "poiName": location.get("poiName", ""),
            }
        elif isinstance(location, str) and location.strip():
            # 兼容旧版：仅传了字符串位置名
            item_data["location"] = {
                "prov": "", "city": "", "area": "", "divisionId": "",
                "gps": "", "poiId": "", "poiName": location,
            }

        # 运费模式
        shipping_mode = req.get("shippingMode", "free")
        item_data["shippingMode"] = shipping_mode

        support_self_pick = req.get("supportSelfPick", False)
        item_data["supportSelfPick"] = support_self_pick

        # 一口价运费
        if shipping_mode == "fixed":
            post_fee = req.get("postFee", 0)
            item_data["postFee"] = post_fee

        # 调用发布服务
        from ....services.xianyu_goods_sync import XianyuItemPublisher, persist_published_goods
        publisher = XianyuItemPublisher(cookie_str, tenant_id)
        result = publisher.publish(item_data)

        if result.get("success"):
            persisted_goods = None
            try:
                persisted_goods = await persist_published_goods(
                    db,
                    tenant_id=tenant_id,
                    account_id=account_id,
                    cookie_str=cookie_str,
                    publish_result=result,
                    publish_payload=item_data,
                )
                await db.commit()
            except Exception as persist_error:
                await db.rollback()
                log_route_failure(logger, persist_error, operation="persist published goods")
            logger.info(
                "商品发布成功: account_id=%s, title=%s, itemId=%s",
                account_id, title, result.get("itemId", "")
            )
            return ResultObject.success({
                "itemId": result.get("itemId", ""),
                "itemUrl": result.get("itemUrl", ""),
                "persistedGoods": persisted_goods,
                "message": "发布成功",
            })
        else:
            logger.error(
                "商品发布失败: account_id=%s, title=%s, error=%s",
                account_id, title, result.get("message", "")
            )
            return ResultObject.failed(result.get("message", "发布失败"))

    except RuntimeError as e:
        return safe_route_failure(logger, e, operation="publish goods runtime", user_message="商品发布失败，请稍后重试")
    except Exception as e:
        return safe_route_failure(logger, e, operation="publish goods", user_message="商品发布失败，请稍后重试")


@router.post("/republish")
async def republish_item(
    req: dict = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    return ResultObject.failed(
        "重新发布能力暂不可用，商品未重新发布",
        503,
    )


@router.post("/delete")
async def delete_item(
    req: ItemOperateReqDTO,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """
    本地删除商品（标记 deleted=1）。
    """
    try:
        tenant_id = req.tenant_id
        if not tenant_id:
            return ResultObject.failed("缺少租户上下文")

        xy_goods_id = req.xy_goods_id
        if not xy_goods_id:
            return ResultObject.failed("缺少商品 ID")

        stmt = (
            sql_update(XianyuGoods)
            .where(
                and_(
                    XianyuGoods.tenant_id == tenant_id,
                    XianyuGoods.external_goods_id == xy_goods_id,
                )
            )
            .values(deleted=1, updated_time=datetime.datetime.now())
        )
        await db.execute(stmt)
        await db.commit()

        logger.info("本地删除商品: tenant_id=%s, goods_id=%s", tenant_id, xy_goods_id)
        return ResultObject.success({"message": "删除成功"})
    except Exception as e:
        return safe_route_failure(logger, e, operation="delete local goods", user_message="删除商品失败，请稍后重试")


@router.post("/offShelf")
async def off_shelf_item(
    req: ItemOperateReqDTO,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """
    下架商品：调用闲鱼 API 下架，同步更新本地状态。
    """
    try:
        tenant_id = req.tenant_id
        account_id = req.xianyu_account_id
        xy_goods_id = req.xy_goods_id
        if not tenant_id or not account_id or not xy_goods_id:
            return ResultObject.failed("缺少必要参数")

        # 获取账号 Cookie
        auth = await _get_account_auth(db, account_id, tenant_id)
        if not auth:
            return ResultObject.failed("账号未登录或 Cookie 已失效")

        # 获取账号是否鱼小铺
        is_fish_shop = await _is_fish_shop_account(db, account_id, tenant_id)

        # 调用闲鱼 API 下架
        operator = XianyuItemOperator(decrypt_cookie_if_needed(auth.encrypted_cookie), is_fish_shop=is_fish_shop)
        operator.off_shelf(xy_goods_id)

        # 更新本地状态
        stmt = (
            sql_update(XianyuGoods)
            .where(
                and_(
                    XianyuGoods.tenant_id == tenant_id,
                    XianyuGoods.account_id == account_id,
                    XianyuGoods.external_goods_id == xy_goods_id,
                )
            )
            .values(status=0, updated_time=datetime.datetime.now())
        )
        await db.execute(stmt)
        await db.commit()

        logger.info("下架成功: account_id=%s, goods_id=%s", account_id, xy_goods_id)
        return ResultObject.success({"message": "下架成功"})
    except Exception as e:
        return safe_route_failure(logger, e, operation="take goods offline", user_message="下架商品失败，请稍后重试")


@router.post("/remoteDelete")
async def remote_delete_item(
    req: ItemOperateReqDTO,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """
    远程删除商品：调用闲鱼 API 删除闲鱼平台上的商品，本地保留记录并标记为已删除状态。
    
    商品状态定义：
        0 = 在售 (ON_SALE)
        1 = 已下架 (OFF_SHELF)
        2 = 已售出 (SOLD)
        3 = 已从闲鱼删除 (REMOTE_DELETED)
    
    两种账号类型均支持，但使用不同的 API：
        - 鱼小铺：使用卖家工作台删除接口
        - 普通账号：使用普通 mtop 删除接口
    
    注意：删除操作不可逆，从闲鱼删除后无法通过本接口恢复。
    """
    # 商品状态常量
    STATUS_REMOTE_DELETED = 3
    GOODS_DELETE_ENABLED_KEY = "goods_delete_enabled"

    try:
        tenant_id = req.tenant_id
        account_id = req.xianyu_account_id
        xy_goods_id = req.xy_goods_id
        if not tenant_id or not account_id or not xy_goods_id:
            return ResultObject.failed("缺少必要参数")

        # 1. 检查功能开关
        try:
            from ....models.entities import XianyuSysSetting
            setting_result = await db.execute(
                select(XianyuSysSetting).where(
                    XianyuSysSetting.setting_key == GOODS_DELETE_ENABLED_KEY
                )
            )
            setting = setting_result.scalar_one_or_none()
            if setting and setting.setting_value == "false":
                return ResultObject.failed("闲鱼删除功能已关闭")
        except Exception:
            # 如果查询设置失败，默认允许操作
            pass

        # 2. 加载商品信息，检查是否已删除（幂等）
        goods_result = await db.execute(
            select(XianyuGoods).where(
                and_(
                    XianyuGoods.tenant_id == tenant_id,
                    XianyuGoods.account_id == account_id,
                    XianyuGoods.external_goods_id == xy_goods_id,
                )
            )
        )
        goods = goods_result.scalar_one_or_none()
        if not goods:
            return ResultObject.failed("商品不存在")
        if goods.status == STATUS_REMOTE_DELETED:
            logger.info("商品已删除，跳过远程删除: goods_id=%s", xy_goods_id)
            return ResultObject.success({"message": "商品已删除，无需重复操作"})

        # 3. 获取账号 Cookie
        auth = await _get_account_auth(db, account_id, tenant_id)
        if not auth:
            return ResultObject.failed("账号未登录或 Cookie 已失效")

        # 4. 获取账号是否鱼小铺
        is_fish_shop = await _is_fish_shop_account(db, account_id, tenant_id)

        # 5. 调用闲鱼 API 删除
        try:
            operator = XianyuItemOperator(decrypt_cookie_if_needed(auth.encrypted_cookie), is_fish_shop=is_fish_shop)
            operator.delete(xy_goods_id)
        except RuntimeError as e:
            return safe_route_failure(logger, e, operation="delete remote goods", user_message="闲鱼删除商品失败，请稍后重试")

        # 6. 更新本地商品状态为「已从闲鱼删除」（status=3）
        try:
            stmt = (
                sql_update(XianyuGoods)
                .where(XianyuGoods.id == goods.id)
                .values(
                    status=STATUS_REMOTE_DELETED,
                    updated_time=datetime.datetime.now(),
                )
            )
            await db.execute(stmt)
            await db.commit()
            logger.info("远程删除成功: account_id=%s, goods_id=%s", account_id, xy_goods_id)
            return ResultObject.success({"message": "闲鱼商品删除成功，本地商品已保留"})
        except Exception as e:
            log_route_failure(logger, e, operation="persist remote goods deletion")
            reconciliation_id = await _record_goods_reconciliation(
                db, tenant_id, account_id, "remote_delete", str(xy_goods_id)
            )
            return ResultObject(
                code=409,
                msg="闲鱼删除已生效，但本地状态同步失败；系统已标记为待对账，请刷新商品状态",
                data={
                    "remoteApplied": True,
                    "reconciliationRequired": True,
                    "reconciliationId": reconciliation_id,
                },
            )

    except Exception as e:
        return safe_route_failure(logger, e, operation="delete remote goods", user_message="远程删除商品失败，请稍后重试")


@router.post("/batch/delete")
async def batch_delete_items(
    req: ItemBatchOperateReqDTO,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """
    批量本地删除商品。
    """
    try:
        tenant_id = req.tenant_id
        account_id = req.xianyu_account_id
        item_ids = req.item_ids
        if not tenant_id or not account_id or not item_ids:
            return ResultObject.failed("缺少必要参数")

        stmt = (
            sql_update(XianyuGoods)
            .where(
                and_(
                    XianyuGoods.tenant_id == tenant_id,
                    XianyuGoods.account_id == account_id,
                    XianyuGoods.external_goods_id.in_(item_ids),
                )
            )
            .values(deleted=1, updated_time=datetime.datetime.now())
        )
        await db.execute(stmt)
        await db.commit()

        logger.info("批量本地删除: account_id=%s, count=%d", account_id, len(item_ids))
        return ResultObject.success({"message": f"批量删除成功，共 {len(item_ids)} 条"})
    except Exception as e:
        return safe_route_failure(logger, e, operation="batch delete local goods", user_message="批量删除商品失败，请稍后重试")


@router.post("/batch/remoteDelete")
async def batch_remote_delete_items(
    req: ItemBatchOperateReqDTO,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """
    批量远程删除商品：逐个调用闲鱼 API 删除。
    """
    try:
        tenant_id = req.tenant_id
        account_id = req.xianyu_account_id
        item_ids = req.item_ids
        if not tenant_id or not account_id or not item_ids:
            return ResultObject.failed("缺少必要参数")

        # 获取账号 Cookie
        auth = await _get_account_auth(db, account_id, tenant_id)
        if not auth:
            return ResultObject.failed("账号未登录或 Cookie 已失效")

        is_fish_shop = await _is_fish_shop_account(db, account_id, tenant_id)
        operator = XianyuItemOperator(decrypt_cookie_if_needed(auth.encrypted_cookie), is_fish_shop=is_fish_shop)

        results = operator.delete_batch(item_ids)

        success_ids = [iid for iid, ok in results.items() if ok]
        failed_ids = [iid for iid, ok in results.items() if not ok]

        # 本地标记已删除成功的
        if success_ids:
            stmt = (
                sql_update(XianyuGoods)
                .where(
                    and_(
                        XianyuGoods.tenant_id == tenant_id,
                        XianyuGoods.account_id == account_id,
                        XianyuGoods.external_goods_id.in_(success_ids),
                    )
                )
                .values(status=3, updated_time=datetime.datetime.now())
            )
            await db.execute(stmt)
            await db.commit()

        logger.info(
            "批量远程删除: account_id=%s, success=%d, failed=%d",
            account_id, len(success_ids), len(failed_ids),
        )

        return ResultObject.success({
            "message": f"删除完成，成功 {len(success_ids)} 条，失败 {len(failed_ids)} 条",
            "success_ids": success_ids,
            "failed_ids": failed_ids,
        })
    except Exception as e:
        return safe_route_failure(logger, e, operation="batch delete remote goods", user_message="批量远程删除商品失败，请稍后重试")


@router.post("/batch/offShelf")
async def batch_off_shelf_items(
    req: ItemBatchOperateReqDTO,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """
    批量下架商品：逐个调用闲鱼 API 下架。
    """
    try:
        tenant_id = req.tenant_id
        account_id = req.xianyu_account_id
        item_ids = req.item_ids
        if not tenant_id or not account_id or not item_ids:
            return ResultObject.failed("缺少必要参数")

        # 获取账号 Cookie
        auth = await _get_account_auth(db, account_id, tenant_id)
        if not auth:
            return ResultObject.failed("账号未登录或 Cookie 已失效")

        is_fish_shop = await _is_fish_shop_account(db, account_id, tenant_id)
        operator = XianyuItemOperator(decrypt_cookie_if_needed(auth.encrypted_cookie), is_fish_shop=is_fish_shop)

        results = operator.off_shelf_batch(item_ids)

        success_ids = [iid for iid, ok in results.items() if ok]
        failed_ids = [iid for iid, ok in results.items() if not ok]

        # 本地更新已下架成功的
        if success_ids:
            stmt = (
                sql_update(XianyuGoods)
                .where(
                    and_(
                        XianyuGoods.tenant_id == tenant_id,
                        XianyuGoods.account_id == account_id,
                        XianyuGoods.external_goods_id.in_(success_ids),
                    )
                )
                .values(status=0, updated_time=datetime.datetime.now())
            )
            await db.execute(stmt)
            await db.commit()

        logger.info(
            "批量下架: account_id=%s, success=%d, failed=%d",
            account_id, len(success_ids), len(failed_ids),
        )

        return ResultObject.success({
            "message": f"下架完成，成功 {len(success_ids)} 条，失败 {len(failed_ids)} 条",
            "success_ids": success_ids,
            "failed_ids": failed_ids,
        })
    except Exception as e:
        return safe_route_failure(logger, e, operation="batch take goods offline", user_message="批量下架商品失败，请稍后重试")


@router.post("/updatePrice")
async def update_item_price(
    req: UpdateItemPriceReqDTO,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """
    修改闲鱼商品价格。
    仅鱼小铺账号支持。流程：
    1. 校验参数
    2. 加载商品、账号信息
    3. 检查鱼小铺账号
    4. 获取 Cookie
    5. 标准化价格
    6. 调用闲鱼 API 改价
    7. 更新本地数据库价格
    """
    try:
        tenant_id = req.tenant_id
        account_id = req.xianyu_account_id
        xy_goods_id = req.xy_goods_id
        price = req.price

        # 1. 参数校验
        if not tenant_id:
            return ResultObject.failed("缺少租户上下文")
        if not account_id:
            return ResultObject.failed("缺少账号ID")
        if not xy_goods_id:
            return ResultObject.failed("缺少商品ID")
        if not price:
            return ResultObject.failed("缺少价格参数")

        # 2. 加载商品信息
        goods_result = await db.execute(
            select(XianyuGoods).where(
                and_(
                    XianyuGoods.tenant_id == tenant_id,
                    XianyuGoods.account_id == account_id,
                    XianyuGoods.external_goods_id == xy_goods_id,
                )
            )
        )
        goods = goods_result.scalar_one_or_none()
        if not goods:
            return ResultObject.failed("商品不存在")

        # 3. 加载账号信息，检查鱼小铺
        account_result = await db.execute(
            select(XianyuAccount).where(
                and_(
                    XianyuAccount.id == account_id,
                    XianyuAccount.tenant_id == tenant_id,
                    XianyuAccount.deleted == 0,
                )
            )
        )
        account = account_result.scalar_one_or_none()
        if not account:
            return ResultObject.failed("账号不存在")

        is_fish_shop = bool(getattr(account, "fish_shop", False))
        if not is_fish_shop:
            return ResultObject.failed("当前账号不是鱼小铺，无法改价")

        # 4. 获取 Cookie
        auth = await _get_account_auth(db, account_id, tenant_id)
        if not auth:
            return ResultObject.failed("未找到账号Cookie，请先登录")
        cookie_str = decrypt_cookie_if_needed(auth.encrypted_cookie)

        # 5. 标准化价格
        try:
            normalized_price = normalize_price(price)
        except PublicRouteValidationError as e:
            return ResultObject.failed(e.public_message)

        # 6. 调用闲鱼 API 改价
        try:
            operator = XianyuItemOperator(cookie_str, is_fish_shop=True)
            operator.update_price(xy_goods_id, normalized_price)
        except RuntimeError as e:
            return safe_route_failure(logger, e, operation="update remote goods price", user_message="闲鱼改价失败，请稍后重试")

        # 7. 更新本地数据库价格
        try:
            stmt = (
                sql_update(XianyuGoods)
                .where(XianyuGoods.id == goods.id)
                .values(
                    sold_price=normalized_price,
                    price=normalized_price,
                    updated_time=datetime.datetime.now(),
                )
            )
            await db.execute(stmt)
            await db.commit()
            logger.info("商品改价成功: account_id=%s, goods_id=%s, new_price=%s",
                        account_id, xy_goods_id, normalized_price)
            return ResultObject.success({"message": "商品改价成功"})
        except Exception as e:
            log_route_failure(logger, e, operation="persist remote goods price")
            reconciliation_id = await _record_goods_reconciliation(
                db, tenant_id, account_id, "remote_price_update", str(xy_goods_id)
            )
            return ResultObject(
                code=409,
                msg="闲鱼改价已生效，但本地价格同步失败；系统已标记为待对账，请刷新商品状态",
                data={
                    "remoteApplied": True,
                    "reconciliationRequired": True,
                    "reconciliationId": reconciliation_id,
                },
            )

    except Exception as e:
        return safe_route_failure(logger, e, operation="update goods price", user_message="商品改价失败，请稍后重试")


@router.post("/updateStock")
async def update_item_stock(
    req: dict = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    return ResultObject.failed(
        "旧版库存更新接口未接入闲鱼平台，未执行任何库存变更；请使用商品编辑接口更新本地库存",
        code=503,
    )


@router.post("/updateAutoDeliveryStatus")
async def update_auto_delivery_status(
    req: dict = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    return ResultObject.failed(
        "旧版自动发货开关接口已停用，未执行任何变更；请使用自动发货规则接口配置",
        code=503,
    )


@router.post("/updateAutoConfirmShipment")
async def update_auto_confirm_shipment(
    req: dict = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    return ResultObject.failed(
        "闲鱼平台确认发货能力当前不可用，未执行任何变更",
        code=503,
    )


@router.post("/updateAutoReplyStatus")
async def update_auto_reply_status(
    request: Request,
    req: dict = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """更新商品自动回复状态（兼容旧接口，实际委派给 auto_reply_scope 模块）。"""
    from app.api.v1.routes.auto_reply_scope import update_product_scope
    return await update_product_scope(request, req, db, _)


@router.post("/autoDeliveryRecords")
async def auto_delivery_records(
    req: dict = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    return ResultObject.failed(
        "旧版发货记录接口已停用，未执行查询；请使用自动发货记录接口",
        code=503,
    )


@router.post("/autoReplyRecords")
async def auto_reply_records(
    req: dict = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    return ResultObject.failed(
        "旧版自动回复记录接口未接入数据源，未执行查询；请使用消息记录接口",
        code=503,
    )


@router.post("/getRagAutoReplyConfig")
async def get_rag_auto_reply_config(
    req: dict = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    return ResultObject.failed(
        "旧版 RAG 配置接口未接入配置存储，未执行查询；请使用知识库配置接口",
        code=503,
    )


@router.post("/updateRagAutoReplyConfig")
async def update_rag_auto_reply_config(
    req: dict = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    return ResultObject.failed(
        "旧版 RAG 配置接口未接入配置存储，未执行任何变更；请使用知识库配置接口",
        code=503,
    )


@router.post("/sku-specs")
async def get_sku_specs(
    req: dict = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    return ResultObject.failed(
        "SKU 规格查询接口尚未接入闲鱼平台，未执行查询",
        code=503,
    )


@router.get("/syncProgress/{sync_id}")
async def get_sync_progress(
    sync_id: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    from ....services.xianyu_goods_sync import get_sync_progress as _get_progress
    progress = _get_progress(sync_id)
    if progress:
        return ResultObject.success(progress)

    result = await db.execute(select(XianyuGoodsSyncTask).where(XianyuGoodsSyncTask.sync_id == sync_id, XianyuGoodsSyncTask.deleted == 0))
    task = result.scalar_one_or_none()
    if not task:
        return ResultObject.success({"progress": 0, "status": "not_found"})
    return ResultObject.success({
        "sync_id": task.sync_id,
        "account_id": task.account_id,
        "status": task.status,
        "progress": task.progress or 0,
        "total": task.total_count or 0,
        "new": task.new_count or 0,
        "updated": task.updated_count or 0,
        "skipped": task.skipped_count or 0,
        "off_shelf": task.off_shelf_count or 0,
        "detail_synced": task.detail_synced_count or 0,
        "duration_seconds": task.duration_seconds or 0,
        "error": task.error_message,
        "started_at": task.started_time.isoformat() if task.started_time else None,
        "finished_at": task.finished_time.isoformat() if task.finished_time else None,
        "source": "db",
    })


@router.get("/syncing/{account_id}")
async def is_syncing(
    account_id: int,
    tenantId: int | None = None,
    tenant_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    from ....services.xianyu_goods_sync import is_account_syncing as _is_syncing
    tenant_value = tenantId if tenantId is not None else tenant_id
    try:
        tenant_value = int(tenant_value)
    except (TypeError, ValueError):
        return ResultObject.validate_failed("tenantId 不能为空且必须为正整数")
    if tenant_value <= 0:
        return ResultObject.validate_failed("tenantId 不能为空且必须为正整数")
    runtime_syncing = bool(_is_syncing(account_id))
    if runtime_syncing:
        return ResultObject.success(runtime_syncing)
    query = select(func.count()).select_from(XianyuGoodsSyncTask).where(
        XianyuGoodsSyncTask.account_id == account_id,
        XianyuGoodsSyncTask.tenant_id == tenant_value,
        XianyuGoodsSyncTask.deleted == 0,
        XianyuGoodsSyncTask.status.in_(["queued", "running"]),
    )
    result = await db.execute(query)
    return ResultObject.success((result.scalar() or 0) > 0)


@router.get("/polishProgress/{task_id}")
async def get_polish_progress(
    task_id: str,
    _: None = Depends(verify_internal_token),
):
    task = _get_polish_task(task_id)
    if task:
        return ResultObject.success(task)
    return ResultObject.success({
        "taskId": task_id,
        "status": "not_found",
        "running": False,
        "progress": 0,
        "message": "擦亮任务不存在或已过期",
    })


@router.post("/polish")
async def polish_account_items(
    req: dict = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """
    一键擦亮：对指定账号的所有在售商品执行擦亮操作。
    请求参数: { xianyu_account_id: int }
    返回: { total, polished, failed, message, results: [...] }
    """
    try:
        account_id = req.get("xianyu_account_id") or req.get("xianyuAccountId")
        if not account_id:
            return ResultObject.failed("缺少参数 xianyu_account_id / xianyuAccountId")
        account_id = int(account_id)

        tenant_raw = req.get("tenantId") or req.get("tenant_id") or req.get("_tenantId")
        if not tenant_raw:
            return ResultObject.failed("缺少租户上下文")
        tenant_id = int(tenant_raw)
        return await _submit_polish_task(
            db=db,
            account_id=account_id,
            tenant_id=tenant_id,
        )

        # 获取账号 Cookie
        from ....services.xianyu_goods_sync import extract_token_from_cookie
        auth = await _get_account_auth(db, account_id, tenant_id)
        if not auth:
            return ResultObject.failed("账号未登录或 Cookie 已失效，请重新登录")
        cookie_str = decrypt_cookie_if_needed(auth.encrypted_cookie)

        # 校验 Token
        token = extract_token_from_cookie(cookie_str)
        if not token:
            return ResultObject.failed("Cookie 中缺少 _m_h5_tk，请重新登录")

        # 判断是否为鱼小铺账号
        is_fish_shop = await _is_fish_shop_account(db, account_id, tenant_id)

        # 查询该账号下所有在售商品（status=0 为在售）
        # DB 状态约定：1=在售，0=下架，2=已售
        goods_query = select(XianyuGoods).where(
            XianyuGoods.account_id == account_id,
            XianyuGoods.tenant_id == tenant_id,
            XianyuGoods.deleted == 0,
            XianyuGoods.status == 1,
        ).order_by(XianyuGoods.id.asc())
        goods_result = await db.execute(goods_query)
        goods_list = goods_result.scalars().all()

        if not goods_list:
            return ResultObject.success({
                "total": 0,
                "polished": 0,
                "failed": 0,
                "message": "没有找到在售商品",
                "results": [],
            })

        # 创建商品操作器，执行批量擦亮
        operator = XianyuItemOperator(cookie_str, is_fish_shop=is_fish_shop)
        item_ids = [g.external_goods_id for g in goods_list if g.external_goods_id]
        polish_results = operator.polish_batch(item_ids)

        # 统计结果
        total = len(item_ids)
        polished = sum(1 for r in polish_results.values() if r.get("success"))
        failed = sum(1 for r in polish_results.values() if not r.get("success"))
        need_manual = any(r.get("need_manual") for r in polish_results.values())

        # 构建详细结果列表
        results_detail = []
        for g in goods_list:
            gid = g.external_goods_id
            r = polish_results.get(gid, {})
            results_detail.append({
                "xyGoodId": gid,
                "title": g.title or "",
                "success": r.get("success", False),
                "error": r.get("error"),
                "needManual": r.get("need_manual", False),
            })

        message = f"擦亮完成：成功 {polished}，失败 {failed}"
        if need_manual:
            message = "擦亮暂停：部分商品触发风控，需要完成滑块验证后重试"

        return ResultObject.success({
            "total": total,
            "polished": polished,
            "failed": failed,
            "message": message,
            "needManual": need_manual,
            "results": results_detail,
        })

    except Exception as e:
        return safe_route_failure(logger, e, operation="polish goods", user_message="擦亮商品失败，请稍后重试")


# ==================== 内部辅助函数 ====================


async def _get_account_auth(db: AsyncSession, account_id: int, tenant_id: int):
    """获取账号的认证信息（Cookie）"""
    result = await db.execute(
        select(XianyuAccountAuth).where(
            and_(
                XianyuAccountAuth.account_id == account_id,
                XianyuAccountAuth.tenant_id == tenant_id,
            )
        )
    )
    auth = result.scalar_one_or_none()
    if not auth or not auth.encrypted_cookie:
        return None
    return auth


async def _is_fish_shop_account(db: AsyncSession, account_id: int, tenant_id: int) -> bool:
    """
    判断账号是否为鱼小铺账号。
    通过 XianyuAccount 扩展字段判断，默认返回 False（普通账号）。
    如需启用鱼小铺功能，请在数据库账号记录中添加 fish_shop 标记。
    """
    try:
        result = await db.execute(
            select(XianyuAccount).where(
                and_(
                    XianyuAccount.id == account_id,
                    XianyuAccount.tenant_id == tenant_id,
                    XianyuAccount.deleted == 0,
                )
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            return False
        # 检查是否有 fish_shop 属性（模型扩展字段/实际列）
        return bool(getattr(account, "fish_shop", False))
    except Exception:
        return False
