import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ....core.database import get_db
from ....core.http_failures import safe_route_failure
from ....core.response import ResultObject
from ....models.entities import AutoReplyRule
from ....schemas.common import AutoReplyRuleReqDTO, AutoReplyRuleRespDTO
from ..deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/autoReplyRule")


def rule_to_dto(rule: AutoReplyRule) -> AutoReplyRuleRespDTO:
    """将新实体 AutoReplyRule 转换为 AutoReplyRuleRespDTO"""
    return AutoReplyRuleRespDTO(
        id=rule.id,
        xianyu_account_id=rule.account_id,
        rule_name=rule.rule_name,
        match_type=rule.match_type,
        match_keywords=rule.match_keywords,
        reply_content=rule.reply_content,
        xy_goods_id=rule.xy_goods_id,
        reply_image=rule.reply_image,
        status=rule.status,
    )


@router.post("/list", response_model=ResultObject[list])
async def list_auto_reply_rules(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        tenant_id = current_user.get("tenant_id")
        result = await db.execute(
            select(AutoReplyRule).where(AutoReplyRule.tenant_id == tenant_id)
        )
        rules = result.scalars().all()
        return ResultObject.success([
            rule_to_dto(r) for r in rules
        ])
    except Exception as e:
        return safe_route_failure(
            logger, e, operation="list auto reply rules",
            user_message="获取自动回复规则失败，请稍后重试",
        )


@router.post("/save", response_model=ResultObject[str])
async def save_auto_reply_rule(
    req: AutoReplyRuleReqDTO,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        tenant_id = current_user.get("tenant_id")
        rule = AutoReplyRule(
            tenant_id=tenant_id,
            account_id=req.xianyu_account_id,
            xy_goods_id=req.xy_goods_id,
            rule_name=req.rule_name,
            match_type=req.match_type,
            match_keywords=req.match_keywords,
            reply_content=req.reply_content,
            reply_image=req.reply_image,
            status=1
        )
        db.add(rule)
        await db.commit()
        return ResultObject.success("保存成功")
    except Exception as e:
        return safe_route_failure(
            logger, e, operation="save auto reply rule",
            user_message="保存自动回复规则失败，请稍后重试",
        )


@router.post("/delete", response_model=ResultObject[str])
async def delete_auto_reply_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        tenant_id = current_user.get("tenant_id")
        result = await db.execute(
            select(AutoReplyRule).where(
                AutoReplyRule.id == rule_id,
                AutoReplyRule.tenant_id == tenant_id
            )
        )
        rule = result.scalar_one_or_none()
        if not rule:
            return ResultObject.failed("规则不存在")
        await db.delete(rule)
        await db.commit()
        return ResultObject.success("删除成功")
    except Exception as e:
        return safe_route_failure(
            logger, e, operation="delete auto reply rule",
            user_message="删除自动回复规则失败，请稍后重试",
        )


@router.post("/batchImport")
async def batch_import_auto_reply_rules(
    req: dict = {},
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    return ResultObject.failed("自动回复规则批量导入能力暂不可用，规则未导入", 503)
