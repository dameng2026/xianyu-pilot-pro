import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ....core.database import get_db
from ....core.http_failures import safe_route_failure
from ....core.response import ResultObject
from ....models.entities import DeliveryRule
from ....schemas.common import (
    AutoDeliveryConfigReqDTO, AutoDeliveryConfigRespDTO,
    TriggerAutoDeliveryReqDTO
)
from ..deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/autoDelivery")


def _rule_to_dto(rule: DeliveryRule) -> AutoDeliveryConfigRespDTO:
    return AutoDeliveryConfigRespDTO(
        id=rule.id,
        xianyu_account_id=rule.account_id,
        xy_goods_id=str(rule.goods_id) if rule.goods_id else None,
        delivery_type=rule.delivery_mode,
        delivery_content=rule.delivery_content,
        status=rule.status,
    )


def _parse_int_or_none(value):
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


@router.post("/config/list", response_model=ResultObject[list])
async def list_delivery_configs(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        tenant_id = current_user.get("tenant_id")
        result = await db.execute(
            select(DeliveryRule).where(
                DeliveryRule.tenant_id == tenant_id,
                DeliveryRule.deleted == 0,
            ).order_by(DeliveryRule.id.desc())
        )
        configs = result.scalars().all()
        return ResultObject.success([_rule_to_dto(c) for c in configs])
    except Exception as e:
        return safe_route_failure(
            logger, e, operation="list auto delivery configs",
            user_message="获取自动发货配置失败，请稍后重试",
        )


@router.post("/config/save", response_model=ResultObject[str])
async def save_delivery_config(
    req: AutoDeliveryConfigReqDTO,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        tenant_id = current_user.get("tenant_id")
        config = DeliveryRule(
            tenant_id=tenant_id,
            user_id=current_user.get("user_id"),
            account_id=req.xianyu_account_id,
            goods_id=_parse_int_or_none(req.xy_goods_id),
            rule_name="自动发货规则",
            delivery_mode=req.delivery_type or "kami",
            delivery_content=req.delivery_content,
            status=1,
            deleted=0,
        )
        db.add(config)
        await db.commit()
        return ResultObject.success("保存成功")
    except Exception as e:
        return safe_route_failure(
            logger, e, operation="save auto delivery config",
            user_message="保存自动发货配置失败，请稍后重试",
        )


@router.post("/trigger", response_model=ResultObject[str])
async def trigger_auto_delivery(
    req: TriggerAutoDeliveryReqDTO,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    logger.warning(
        "拒绝调用未接入执行队列的旧版自动发货触发接口: tenantId=%s accountId=%s orderId=%s",
        current_user.get("tenant_id"),
        req.xianyu_account_id,
        req.order_id,
    )
    return ResultObject.failed(
        "旧版自动发货触发接口未连接执行队列，任务未提交；请使用订单发货任务接口",
        code=503,
    )


@router.post("/config/get")
async def get_delivery_config(
    req: dict = {},
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    tenant_id = current_user.get("tenant_id")
    rule_id = req.get("id")
    if not rule_id:
        return ResultObject.success(None)
    result = await db.execute(
        select(DeliveryRule).where(
            DeliveryRule.id == rule_id,
            DeliveryRule.tenant_id == tenant_id,
            DeliveryRule.deleted == 0,
        )
    )
    rule = result.scalar_one_or_none()
    return ResultObject.success(_rule_to_dto(rule) if rule else None)


@router.post("/config/goods-rules")
async def goods_delivery_rules(
    xianyu_account_id: int = None,
    xy_goods_id: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    tenant_id = current_user.get("tenant_id")
    query = select(DeliveryRule).where(DeliveryRule.tenant_id == tenant_id, DeliveryRule.deleted == 0)
    if xianyu_account_id is not None:
        query = query.where(DeliveryRule.account_id == xianyu_account_id)
    gid = _parse_int_or_none(xy_goods_id)
    if gid is not None:
        query = query.where(DeliveryRule.goods_id == gid)
    rows = (await db.execute(query.order_by(DeliveryRule.id.desc()))).scalars().all()
    return ResultObject.success([_rule_to_dto(r) for r in rows])


@router.post("/config/delete")
async def delete_delivery_config(
    xianyu_account_id: int = None,
    id: int = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    tenant_id = current_user.get("tenant_id")
    if id:
        result = await db.execute(select(DeliveryRule).where(DeliveryRule.id == id, DeliveryRule.tenant_id == tenant_id))
        rule = result.scalar_one_or_none()
        if rule:
            rule.deleted = 1
            await db.commit()
    return ResultObject.success("删除成功")


@router.post("/config/delete-rule")
async def delete_delivery_rule(
    id: int = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    return await delete_delivery_config(id=id, db=db, current_user=current_user)


@router.post("/config/enabled")
async def update_delivery_enabled(
    id: int = None,
    enabled: bool = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    tenant_id = current_user.get("tenant_id")
    if id is not None:
        result = await db.execute(select(DeliveryRule).where(DeliveryRule.id == id, DeliveryRule.tenant_id == tenant_id))
        rule = result.scalar_one_or_none()
        if rule:
            rule.status = 1 if enabled else 0
            await db.commit()
    return ResultObject.success("更新成功")


@router.post("/config/stock")
async def update_delivery_stock(
    id: int = None,
    stock: int = None,
    current_user: dict = Depends(get_current_user)
):
    return ResultObject.failed(
        "旧版发货库存接口未接入库存表，未执行任何变更；请使用卡密仓库接口",
        code=503,
    )


@router.post("/manualReturn")
async def manual_return_auto_delivery(
    req: dict = {},
    current_user: dict = Depends(get_current_user)
):
    return ResultObject.failed(
        "旧版手动退回接口未接入发货记录，未执行任何变更；请使用发货记录重试接口",
        code=503,
    )
