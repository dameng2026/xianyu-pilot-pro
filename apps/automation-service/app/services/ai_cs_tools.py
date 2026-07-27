"""AI 客服"小梦"工具调用函数。

工具由 AI 在对话中触发，经用户确认后执行。每个工具：
- 接收 db、tenant_id、user_id 及工具特定参数
- 返回统一结构 {"success": bool, "data": dict|None, "error": str|None}
- 全部为 async 函数，便于复用现有 ORM 与服务

安全约束：
- 三层鉴权（session_id + user_id + tenant_id）由调用方（路由层）完成
- 工具内部再次以 tenant_id 限定所有数据库查询，避免越权
- 不得返回 cookie、token、密码等敏感字段
- 创建类工具仅写入数据库，不直接触发对外副作用（如真实发货、WS 推送）
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.entities import (
    AutoReplyRule,
    CardGroup,
    DeliveryRule,
    WorkflowDefinition,
    XianyuAccount,
    XianyuAccountAuth,
    XianyuAccountRuntime,
    XianyuGoods,
)

logger = logging.getLogger(__name__)

# 工具执行结果统一结构
ToolResult = Dict[str, Any]


def _ok(data: Optional[dict] = None, **extra: Any) -> ToolResult:
    """构造成功结果。"""
    payload: ToolResult = {"success": True, "data": data or {}, "error": None}
    if extra:
        payload["data"].update(extra)
    return payload


def _fail(error: str, **extra: Any) -> ToolResult:
    """构造失败结果。error 为面向 AI 的简短描述，不暴露内部细节。"""
    payload: ToolResult = {"success": False, "data": None, "error": error}
    if extra:
        payload["data"] = extra
    return payload


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_str(value: Any, *, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


async def list_accounts(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    **_: Any,
) -> ToolResult:
    """列出当前用户名下的闲鱼账号（仅元信息，不含 cookie/token）。"""
    try:
        stmt = (
            select(
                XianyuAccount.id,
                XianyuAccount.nickname,
                XianyuAccount.external_uid,
                XianyuAccount.platform,
                XianyuAccount.fish_shop_user,
                XianyuAccount.status,
                XianyuAccount.remark,
            )
            .where(
                XianyuAccount.tenant_id == tenant_id,
                XianyuAccount.user_id == user_id,
                XianyuAccount.deleted == 0,
            )
            .order_by(XianyuAccount.id.desc())
            .limit(50)
        )
        rows = (await db.execute(stmt)).all()
        accounts = [
            {
                "id": row[0],
                "nickname": row[1] or "",
                "externalUid": row[2] or "",
                "platform": row[3] or "xianyu",
                "fishShopUser": int(row[4] or 0),
                "status": int(row[5] or 0),
                "remark": row[6] or "",
            }
            for row in rows
        ]
        return _ok({"accounts": accounts, "total": len(accounts)})
    except Exception as exc:
        logger.warning("list_accounts failed tenantId=%d errorType=%s", tenant_id, type(exc).__name__)
        return _fail("查询账号列表失败，请稍后重试")


async def get_account_status(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    account_id: int,
    **_: Any,
) -> ToolResult:
    """查询单个账号的运行时状态（在线、Cookie 状态等），不含敏感凭证。"""
    account_id = _safe_int(account_id)
    if account_id <= 0:
        return _fail("accountId 必须为正整数")
    try:
        # 校验账号归属
        owner_row = (await db.execute(
            select(XianyuAccount.user_id).where(
                XianyuAccount.tenant_id == tenant_id,
                XianyuAccount.id == account_id,
                XianyuAccount.deleted == 0,
            )
        )).scalar_one_or_none()
        if owner_row is None:
            return _fail("账号不存在或无权访问")
        if int(owner_row or 0) != user_id:
            return _fail("账号不存在或无权访问")

        runtime = (await db.execute(
            select(XianyuAccountRuntime).where(
                XianyuAccountRuntime.tenant_id == tenant_id,
                XianyuAccountRuntime.account_id == account_id,
                XianyuAccountRuntime.deleted == 0,
            )
        )).scalar_one_or_none()
        auth = (await db.execute(
            select(
                XianyuAccountAuth.cookie_status,
                XianyuAccountAuth.last_login_status_code,
                XianyuAccountAuth.last_login_status_message,
                XianyuAccountAuth.last_login_check_time,
            ).where(
                XianyuAccountAuth.tenant_id == tenant_id,
                XianyuAccountAuth.account_id == account_id,
                XianyuAccountAuth.deleted == 0,
            )
        )).one_or_none()

        return _ok({
            "accountId": account_id,
            "onlineStatus": int(runtime.online_status) if runtime else 0,
            "wsStatus": int(runtime.ws_status) if runtime else 0,
            "wsLatencyMs": int(runtime.ws_latency_ms) if runtime else 0,
            "cookieStatus": int(auth[0]) if auth else 0,
            "lastLoginStatusCode": auth[1] if auth else None,
            "lastLoginStatusMessage": auth[2] if auth else None,
            "lastLoginCheckTime": auth[3].isoformat() if auth and auth[3] else None,
        })
    except Exception as exc:
        logger.warning(
            "get_account_status failed tenantId=%d accountId=%d errorType=%s",
            tenant_id, account_id, type(exc).__name__,
        )
        return _fail("查询账号状态失败，请稍后重试")


async def list_products(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    account_id: int,
    limit: int = 10,
    **_: Any,
) -> ToolResult:
    """列出指定账号下的商品（用于客服查看商品上下文）。"""
    account_id = _safe_int(account_id)
    if account_id <= 0:
        return _fail("accountId 必须为正整数")
    limit = max(1, min(int(limit or 10), 50))
    try:
        # 校验账号归属
        owner_row = (await db.execute(
            select(XianyuAccount.user_id).where(
                XianyuAccount.tenant_id == tenant_id,
                XianyuAccount.id == account_id,
                XianyuAccount.deleted == 0,
            )
        )).scalar_one_or_none()
        if owner_row is None or int(owner_row or 0) != user_id:
            return _fail("账号不存在或无权访问")

        rows = (await db.execute(
            select(
                XianyuGoods.id,
                XianyuGoods.external_goods_id,
                XianyuGoods.title,
                XianyuGoods.price,
                XianyuGoods.stock,
                XianyuGoods.exposure_count,
                XianyuGoods.view_count,
                XianyuGoods.want_count,
                XianyuGoods.status,
            )
            .where(
                XianyuGoods.tenant_id == tenant_id,
                XianyuGoods.account_id == account_id,
                XianyuGoods.deleted == 0,
            )
            .order_by(XianyuGoods.id.desc())
            .limit(limit)
        )).all()
        products = [
            {
                "id": row[0],
                "externalGoodsId": row[1] or "",
                "title": row[2] or "",
                "price": row[3] or "",
                "stock": int(row[4] or 0),
                "exposureCount": int(row[5] or 0),
                "viewCount": int(row[6] or 0),
                "wantCount": int(row[7] or 0),
                "status": int(row[8] or 0),
            }
            for row in rows
        ]
        return _ok({"products": products, "total": len(products)})
    except Exception as exc:
        logger.warning(
            "list_products failed tenantId=%d accountId=%d errorType=%s",
            tenant_id, account_id, type(exc).__name__,
        )
        return _fail("查询商品列表失败，请稍后重试")


async def create_qr_login(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    **_: Any,
) -> ToolResult:
    """创建闲鱼扫码登录会话，返回二维码图片与 sessionId。

    实际的账号保存由前端轮询 /qrlogin/status 时触发，本工具仅生成二维码。
    """
    try:
        from ..core.xianyu_qr_login import generate_qrcode
        import asyncio as _asyncio
        result = await _asyncio.to_thread(generate_qrcode, user_id=user_id, tenant_id=tenant_id)
        return _ok({
            "sessionId": result.get("sessionId", ""),
            "qrImage": result.get("qrImage") or result.get("qrCodeBase64", ""),
            "status": "pending",
            "message": "请使用闲鱼 App 扫描二维码完成登录",
        })
    except RuntimeError as exc:
        # generate_qrcode 将上游失败包装为 RuntimeError，对外暴露友好文案
        logger.warning(
            "create_qr_login failed tenantId=%d userId=%d errorType=%s",
            tenant_id, user_id, type(exc).__name__,
        )
        return _fail("生成扫码登录二维码失败，请稍后重试")
    except Exception as exc:
        logger.warning(
            "create_qr_login unexpected failure tenantId=%d userId=%d errorType=%s",
            tenant_id, user_id, type(exc).__name__,
        )
        return _fail("生成扫码登录二维码失败，请稍后重试")


async def create_auto_reply_rule(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    account_id: int,
    rule_name: str,
    match_type: str,
    match_keywords: str,
    reply_content: str,
    **_: Any,
) -> ToolResult:
    """创建自动回复规则。"""
    account_id = _safe_int(account_id)
    if account_id <= 0:
        return _fail("accountId 必须为正整数")
    if not rule_name or not rule_name.strip():
        return _fail("规则名称不能为空")
    if match_type not in ("keyword", "ai", "all"):
        return _fail("matchType 仅支持 keyword/ai/all")
    if match_type == "keyword" and not (match_keywords or "").strip():
        return _fail("keyword 类型规则必须填写关键词")
    if not (reply_content or "").strip():
        return _fail("回复内容不能为空")
    try:
        # 校验账号归属
        owner_row = (await db.execute(
            select(XianyuAccount.user_id).where(
                XianyuAccount.tenant_id == tenant_id,
                XianyuAccount.id == account_id,
                XianyuAccount.deleted == 0,
            )
        )).scalar_one_or_none()
        if owner_row is None or int(owner_row or 0) != user_id:
            return _fail("账号不存在或无权访问")

        rule = AutoReplyRule(
            tenant_id=tenant_id,
            account_id=account_id,
            rule_name=rule_name.strip()[:200],
            match_type=match_type,
            match_keywords=(match_keywords or "").strip(),
            reply_content=reply_content.strip(),
            reply_mode="keyword" if match_type != "ai" else "ai",
            status=1,
            priority=0,
        )
        db.add(rule)
        await db.flush()
        rule_id = int(rule.id)
        logger.info(
            "create_auto_reply_rule ok tenantId=%d userId=%d accountId=%d ruleId=%d",
            tenant_id, user_id, account_id, rule_id,
        )
        return _ok({"ruleId": rule_id, "ruleName": rule.rule_name, "status": "created"})
    except Exception as exc:
        logger.warning(
            "create_auto_reply_rule failed tenantId=%d accountId=%d errorType=%s",
            tenant_id, account_id, type(exc).__name__,
        )
        await db.rollback()
        return _fail("创建自动回复规则失败，请稍后重试")


async def create_delivery_rule(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    account_id: int,
    rule_name: str,
    goods_id: int,
    delivery_mode: str,
    card_group_id: Optional[int] = None,
    delivery_content: str = "",
    trigger_on_pay: int = 1,
    trigger_keyword: str = "",
    **_: Any,
) -> ToolResult:
    """创建自动发货规则（不立即触发发货，仅落库）。"""
    account_id = _safe_int(account_id)
    goods_id = _safe_int(goods_id)
    if account_id <= 0:
        return _fail("accountId 必须为正整数")
    if goods_id <= 0:
        return _fail("goodsId 必须为正整数")
    if not rule_name or not rule_name.strip():
        return _fail("规则名称不能为空")
    if delivery_mode not in ("kami", "text"):
        return _fail("deliveryMode 仅支持 kami/text")
    if delivery_mode == "kami" and _safe_int(card_group_id) <= 0:
        return _fail("卡密发货必须指定 cardGroupId")
    if delivery_mode == "text" and not (delivery_content or "").strip():
        return _fail("文本发货必须填写 deliveryContent")
    try:
        owner_row = (await db.execute(
            select(XianyuAccount.user_id).where(
                XianyuAccount.tenant_id == tenant_id,
                XianyuAccount.id == account_id,
                XianyuAccount.deleted == 0,
            )
        )).scalar_one_or_none()
        if owner_row is None or int(owner_row or 0) != user_id:
            return _fail("账号不存在或无权访问")

        rule = DeliveryRule(
            tenant_id=tenant_id,
            user_id=user_id,
            account_id=account_id,
            rule_name=rule_name.strip()[:200],
            goods_id=goods_id,
            delivery_mode=delivery_mode,
            card_group_id=_safe_int(card_group_id) if delivery_mode == "kami" else None,
            delivery_content=(delivery_content or "").strip() or None,
            trigger_on_pay=1 if trigger_on_pay else 0,
            trigger_keyword=(trigger_keyword or "").strip() or None,
            max_delivery_per_day=0,
            status=1,
        )
        db.add(rule)
        await db.flush()
        rule_id = int(rule.id)
        logger.info(
            "create_delivery_rule ok tenantId=%d userId=%d accountId=%d ruleId=%d",
            tenant_id, user_id, account_id, rule_id,
        )
        return _ok({"ruleId": rule_id, "ruleName": rule.rule_name, "status": "created"})
    except Exception as exc:
        logger.warning(
            "create_delivery_rule failed tenantId=%d accountId=%d errorType=%s",
            tenant_id, account_id, type(exc).__name__,
        )
        await db.rollback()
        return _fail("创建发货规则失败，请稍后重试")


async def create_card_group(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    group_name: str,
    group_type: str = "kami",
    remark: str = "",
    **_: Any,
) -> ToolResult:
    """创建卡密/货源库分组（空分组，需后续导入卡密）。"""
    if not group_name or not group_name.strip():
        return _fail("分组名称不能为空")
    if group_type not in ("kami", "text"):
        return _fail("groupType 仅支持 kami/text")
    try:
        group = CardGroup(
            tenant_id=tenant_id,
            user_id=user_id,
            group_name=group_name.strip()[:200],
            group_type=group_type,
            total_count=0,
            used_count=0,
            remain_count=0,
            available_count=0,
            remark=(remark or "").strip() or None,
            status=1,
        )
        db.add(group)
        await db.flush()
        group_id = int(group.id)
        logger.info(
            "create_card_group ok tenantId=%d userId=%d groupId=%d",
            tenant_id, user_id, group_id,
        )
        return _ok({"groupId": group_id, "groupName": group.group_name, "status": "created"})
    except Exception as exc:
        logger.warning(
            "create_card_group failed tenantId=%d errorType=%s",
            tenant_id, type(exc).__name__,
        )
        await db.rollback()
        return _fail("创建货源库分组失败，请稍后重试")


async def create_workflow(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    name: str,
    description: str = "",
    trigger_type: str = "manual",
    **_: Any,
) -> ToolResult:
    """创建工作流定义（草稿状态，用户需在前端完善节点）。"""
    if not name or not name.strip():
        return _fail("工作流名称不能为空")
    if trigger_type not in ("manual", "scheduled", "event"):
        return _fail("triggerType 仅支持 manual/scheduled/event")
    try:
        wf = WorkflowDefinition(
            tenant_id=tenant_id,
            user_id=user_id,
            name=name.strip()[:200],
            description=(description or "").strip() or None,
            trigger_type=trigger_type,
            config_json={},
            canvas_json={"zoom": 1, "offset": {"x": 0, "y": 0}},
            status="draft",
            version=1,
            execution_count=0,
        )
        db.add(wf)
        await db.flush()
        wf_id = int(wf.id)
        logger.info(
            "create_workflow ok tenantId=%d userId=%d workflowId=%d",
            tenant_id, user_id, wf_id,
        )
        return _ok({"workflowId": wf_id, "name": wf.name, "status": "draft"})
    except Exception as exc:
        logger.warning(
            "create_workflow failed tenantId=%d errorType=%s",
            tenant_id, type(exc).__name__,
        )
        await db.rollback()
        return _fail("创建工作流失败，请稍后重试")


async def create_scheduled_task(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    account_id: int,
    task_type: str,
    cron_expr: str,
    task_name: str = "",
    **_: Any,
) -> ToolResult:
    """创建定时任务记录（仅落库，不立即生效，由前端补全配置后启用）。

    本工具仅写入 scheduled_task 表的元信息；具体执行由 worker 按 task_type 路由。
    """
    account_id = _safe_int(account_id)
    if account_id <= 0:
        return _fail("accountId 必须为正整数")
    if not task_type or not task_type.strip():
        return _fail("taskType 不能为空")
    if not cron_expr or not cron_expr.strip():
        return _fail("cronExpr 不能为空")
    try:
        owner_row = (await db.execute(
            select(XianyuAccount.user_id).where(
                XianyuAccount.tenant_id == tenant_id,
                XianyuAccount.id == account_id,
                XianyuAccount.deleted == 0,
            )
        )).scalar_one_or_none()
        if owner_row is None or int(owner_row or 0) != user_id:
            return _fail("账号不存在或无权访问")

        # 仅当 scheduled_task 表存在时写入；表结构由 Java 管理，这里使用 raw SQL
        # 避免引入未对齐的 ORM 模型。表不存在时返回友好错误。
        try:
            result = await db.execute(text("""
                INSERT INTO scheduled_task(
                    tenant_id, user_id, account_id, task_type, task_name,
                    cron_expr, status, deleted, created_time, updated_time
                ) VALUES (
                    :tenant_id, :user_id, :account_id, :task_type, :task_name,
                    :cron_expr, 0, 0, NOW(), NOW()
                )
            """), {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "account_id": account_id,
                "task_type": task_type.strip()[:50],
                "task_name": (task_name or "").strip()[:200] or None,
                "cron_expr": cron_expr.strip()[:120],
            })
            await db.flush()
            task_id = int(result.lastrowid or 0)
            if task_id <= 0:
                await db.rollback()
                return _fail("创建定时任务失败：未返回任务ID")
            logger.info(
                "create_scheduled_task ok tenantId=%d userId=%d taskId=%d",
                tenant_id, user_id, task_id,
            )
            return _ok({
                "taskId": task_id,
                "taskType": task_type,
                "cronExpr": cron_expr,
                "status": "disabled",
                "message": "定时任务已创建（默认未启用，需在前端启用）",
            })
        except Exception as table_exc:
            # scheduled_task 表可能不存在或字段差异
            logger.warning(
                "create_scheduled_task table op failed tenantId=%d errorType=%s",
                tenant_id, type(table_exc).__name__,
            )
            await db.rollback()
            return _fail("定时任务表暂不可用，请稍后重试或联系管理员")
    except Exception as exc:
        logger.warning(
            "create_scheduled_task failed tenantId=%d errorType=%s",
            tenant_id, type(exc).__name__,
        )
        await db.rollback()
        return _fail("创建定时任务失败，请稍后重试")


async def polish_product_title(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    goods_id: int,
    **_: Any,
) -> ToolResult:
    """使用通用模型润色商品标题（按次计费）。

    流程：
    1. 查询商品当前标题
    2. 调用通用模型润色（按次计费）
    3. 应用禁止词硬过滤
    4. 返回润色后的标题（不直接写库，由用户在前端确认后保存）
    """
    goods_id = _safe_int(goods_id)
    if goods_id <= 0:
        return _fail("goodsId 必须为正整数")
    try:
        # 查询商品并校验归属
        row = (await db.execute(
            select(
                XianyuGoods.title,
                XianyuGoods.detail_info,
                XianyuGoods.user_id,
            ).where(
                XianyuGoods.tenant_id == tenant_id,
                XianyuGoods.id == goods_id,
                XianyuGoods.deleted == 0,
            )
        )).one_or_none()
        if row is None:
            return _fail("商品不存在或无权访问")
        goods_user_id = int(row[2] or 0)
        if goods_user_id != 0 and goods_user_id != user_id:
            return _fail("商品不存在或无权访问")
        original_title = row[0] or ""
        if not original_title:
            return _fail("商品暂无标题，无法润色")

        # 调用通用模型润色（ai_provider 内部已读取后台通用模型配置）
        from .ai_provider import generate_text, enforce_polish_restriction
        from .ai_billing import precheck_ai_usage, charge_text_usage, build_request_id

        request_id = build_request_id("ai_cs_polish")
        # 计费预检：余额不足时直接拒绝
        try:
            await precheck_ai_usage({
                "tenantId": tenant_id,
                "userId": user_id,
                "scene": "product_polish",
                "providerName": "default",
                "modelName": "default",
                "modelType": "chat",
                "billingMode": "per_call",
            })
        except Exception as exc:
            # 余额不足或计费不可用时不阻塞润色返回，由调用方决定是否提示用户
            logger.info(
                "polish_product_title precheck failed tenantId=%d userId=%d errorType=%s",
                tenant_id, user_id, type(exc).__name__,
            )

        system_prompt = (
            "你是闲鱼商品标题润色助手。请基于原标题与商品描述，生成 1 个更具吸引力的标题。"
            "要求：保留核心关键词，不超过 30 个汉字，不含违禁词，不编造价格或库存信息，"
            "只输出新标题，不要任何解释或前后缀。"
        )
        user_prompt = f"原标题：{original_title}\n商品描述：{(row[1] or '')[:500]}"
        result = await generate_text(
            scene="ai_cs_polish",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.6,
            request_id=request_id,
        )
        if not result.get("ok"):
            error_code = result.get("errorCode") or "AI_PROVIDER_UNAVAILABLE"
            logger.info(
                "polish_product_title generate failed tenantId=%d goodsId=%d code=%s",
                tenant_id, goods_id, error_code,
            )
            return _fail("AI 润色暂不可用，请稍后重试")

        polished = (result.get("content") or "").strip()
        if not polished:
            return _fail("AI 未返回有效润色结果")

        # 应用禁止词硬过滤
        masked_title, masked_body, hits = await enforce_polish_restriction(polished, "")
        final_title = masked_title[:200]

        # 实际扣费（按次计费，由后端 AiBillingService 强制）
        try:
            await charge_text_usage(
                tenant_id=tenant_id,
                user_id=user_id,
                scene="ai_cs_polish",
                provider_name=str(result.get("provider") or "default"),
                model_name=str(result.get("model") or "default"),
                model_type="chat",
                prompt=user_prompt,
                completion=final_title,
                request_id=request_id,
                raw_usage=result.get("usage") or {},
            )
        except Exception as exc:
            # 扣费失败不阻塞结果返回，但记录日志便于排查
            logger.warning(
                "polish_product_title charge failed tenantId=%d userId=%d errorType=%s",
                tenant_id, user_id, type(exc).__name__,
            )

        return _ok({
            "goodsId": goods_id,
            "originalTitle": original_title,
            "polishedTitle": final_title,
            "forbiddenHits": hits,
            "message": "润色完成，请在商品编辑页保存以应用新标题",
        })
    except Exception as exc:
        logger.warning(
            "polish_product_title failed tenantId=%d goodsId=%d errorType=%s",
            tenant_id, goods_id, type(exc).__name__,
        )
        return _fail("商品标题润色失败，请稍后重试")


# ============================================================
# 查询类工具：订单 / 发货 / 卡密 / 工作流 / 定时任务 / 自动回复 / 退款
# ============================================================


async def list_orders(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    account_id: Optional[int] = None,
    status: Optional[int] = None,
    limit: int = 10,
    **_: Any,
) -> ToolResult:
    """查询订单列表，可按账号与订单状态过滤。

    订单状态：0=待付款, 1=已付款, 2=待发货, 3=已发货, 4=已完成, 5=已关闭
    """
    limit = max(1, min(int(limit or 10), 50))
    try:
        sql = (
            "SELECT o.id, o.account_id, o.external_order_id, o.order_status, "
            "o.total_amount, o.buyer_name, o.create_time, o.pay_time, o.ship_time, "
            "o.item_id, o.is_bargain, o.is_rated "
            "FROM xianyu_trade_order o "
            "INNER JOIN xianyu_account a ON a.id = o.account_id "
            "WHERE o.tenant_id = :tenant_id AND a.user_id = :user_id "
            "AND o.deleted = 0 AND a.deleted = 0"
        )
        params: Dict[str, Any] = {"tenant_id": tenant_id, "user_id": user_id}
        if account_id and int(account_id) > 0:
            sql += " AND o.account_id = :account_id"
            params["account_id"] = int(account_id)
        if status is not None and str(status) != "":
            try:
                status_int = int(status)
                if 0 <= status_int <= 5:
                    sql += " AND o.order_status = :status"
                    params["status"] = status_int
            except (TypeError, ValueError):
                pass
        sql += " ORDER BY o.id DESC LIMIT :limit"
        params["limit"] = limit
        rows = (await db.execute(text(sql), params)).mappings().all()
        orders = [
            {
                "id": row["id"],
                "accountId": row["account_id"],
                "externalOrderId": row["external_order_id"] or "",
                "orderStatus": int(row["order_status"] or 0),
                "totalAmount": row["total_amount"] or "",
                "buyerName": row["buyer_name"] or "",
                "createTime": row["create_time"].isoformat() if row["create_time"] else None,
                "payTime": row["pay_time"].isoformat() if row["pay_time"] else None,
                "shipTime": row["ship_time"].isoformat() if row["ship_time"] else None,
                "itemId": row["item_id"] or "",
                "isBargain": int(row["is_bargain"] or 0),
                "isRated": int(row["is_rated"] or 0),
            }
            for row in rows
        ]
        return _ok({"orders": orders, "total": len(orders)})
    except Exception as exc:
        logger.warning(
            "list_orders failed tenantId=%d errorType=%s",
            tenant_id, type(exc).__name__,
        )
        return _fail("查询订单列表失败，请稍后重试")


async def get_account_summary(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    **_: Any,
) -> ToolResult:
    """查询当前用户的账号汇总统计：总数、正常、异常、在线数。"""
    try:
        sql = (
            "SELECT "
            "COUNT(*) AS total, "
            "SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END) AS active, "
            "SUM(CASE WHEN status != 1 THEN 1 ELSE 0 END) AS inactive "
            "FROM xianyu_account "
            "WHERE tenant_id = :tenant_id AND user_id = :user_id AND deleted = 0"
        )
        row = (await db.execute(text(sql), {"tenant_id": tenant_id, "user_id": user_id})).mappings().first()
        total = int(row["total"] or 0) if row else 0
        active = int(row["active"] or 0) if row else 0
        inactive = int(row["inactive"] or 0) if row else 0

        # 查询在线 WS 数
        online_sql = (
            "SELECT COUNT(*) AS online FROM xianyu_account_runtime r "
            "INNER JOIN xianyu_account a ON a.id = r.account_id "
            "WHERE a.tenant_id = :tenant_id AND a.user_id = :user_id "
            "AND a.deleted = 0 AND r.deleted = 0 AND r.online_status = 1"
        )
        online_row = (await db.execute(text(online_sql), {"tenant_id": tenant_id, "user_id": user_id})).mappings().first()
        online = int(online_row["online"] or 0) if online_row else 0

        return _ok({
            "total": total,
            "active": active,
            "inactive": inactive,
            "online": online,
            "offline": max(0, total - online),
        })
    except Exception as exc:
        logger.warning(
            "get_account_summary failed tenantId=%d errorType=%s",
            tenant_id, type(exc).__name__,
        )
        return _fail("查询账号汇总失败，请稍后重试")


async def get_goods_detail(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    goods_id: int,
    **_: Any,
) -> ToolResult:
    """查询单个商品的详情（含 SKU 与发货规则）。"""
    goods_id = _safe_int(goods_id)
    if goods_id <= 0:
        return _fail("goodsId 必须为正整数")
    try:
        # 校验归属
        row = (await db.execute(
            select(
                XianyuGoods.id,
                XianyuGoods.account_id,
                XianyuGoods.external_goods_id,
                XianyuGoods.title,
                XianyuGoods.price,
                XianyuGoods.stock,
                XianyuGoods.detail_info,
                XianyuGoods.exposure_count,
                XianyuGoods.view_count,
                XianyuGoods.want_count,
                XianyuGoods.status,
                XianyuGoods.user_id,
            ).where(
                XianyuGoods.tenant_id == tenant_id,
                XianyuGoods.id == goods_id,
                XianyuGoods.deleted == 0,
            )
        )).one_or_none()
        if row is None:
            return _fail("商品不存在或无权访问")
        goods_user_id = int(row[11] or 0)
        if goods_user_id != 0 and goods_user_id != user_id:
            return _fail("商品不存在或无权访问")

        # 查询发货规则
        delivery_sql = (
            "SELECT id, rule_name, delivery_mode, trigger_on_pay, status "
            "FROM delivery_rule "
            "WHERE tenant_id = :tenant_id AND goods_id = :goods_id AND deleted = 0 "
            "ORDER BY id DESC LIMIT 5"
        )
        delivery_rows = (await db.execute(
            text(delivery_sql), {"tenant_id": tenant_id, "goods_id": goods_id}
        )).mappings().all()

        return _ok({
            "goodsId": int(row[0]),
            "accountId": int(row[1] or 0),
            "externalGoodsId": row[2] or "",
            "title": row[3] or "",
            "price": row[4] or "",
            "stock": int(row[5] or 0),
            "detailInfo": (row[6] or "")[:500],
            "exposureCount": int(row[7] or 0),
            "viewCount": int(row[8] or 0),
            "wantCount": int(row[9] or 0),
            "status": int(row[10] or 0),
            "deliveryRules": [
                {
                    "id": int(dr["id"]),
                    "ruleName": dr["rule_name"] or "",
                    "deliveryMode": dr["delivery_mode"] or "",
                    "triggerOnPay": int(dr["trigger_on_pay"] or 0),
                    "status": int(dr["status"] or 0),
                }
                for dr in delivery_rows
            ],
        })
    except Exception as exc:
        logger.warning(
            "get_goods_detail failed tenantId=%d goodsId=%d errorType=%s",
            tenant_id, goods_id, type(exc).__name__,
        )
        return _fail("查询商品详情失败，请稍后重试")


async def list_delivery_records(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    account_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 10,
    **_: Any,
) -> ToolResult:
    """查询发货记录，可按账号与发货状态过滤。

    发货状态：pending=待处理, success=成功, failed=失败
    """
    limit = max(1, min(int(limit or 10), 50))
    try:
        sql = (
            "SELECT r.id, r.account_id, r.order_id, r.rule_id, r.delivery_type, "
            "r.content, r.delivery_status, r.error_message, r.retry_count, r.created_time "
            "FROM delivery_record r "
            "INNER JOIN xianyu_account a ON a.id = r.account_id "
            "WHERE r.tenant_id = :tenant_id AND a.user_id = :user_id "
            "AND r.deleted = 0 AND a.deleted = 0"
        )
        params: Dict[str, Any] = {"tenant_id": tenant_id, "user_id": user_id}
        if account_id and int(account_id) > 0:
            sql += " AND r.account_id = :account_id"
            params["account_id"] = int(account_id)
        if status and str(status) in ("pending", "success", "failed"):
            sql += " AND r.delivery_status = :status"
            params["status"] = str(status)
        sql += " ORDER BY r.id DESC LIMIT :limit"
        params["limit"] = limit
        rows = (await db.execute(text(sql), params)).mappings().all()
        records = [
            {
                "id": int(row["id"]),
                "accountId": int(row["account_id"] or 0),
                "orderId": int(row["order_id"] or 0),
                "ruleId": int(row["rule_id"] or 0),
                "deliveryType": row["delivery_type"] or "",
                "content": (row["content"] or "")[:200],
                "deliveryStatus": row["delivery_status"] or "pending",
                "errorMessage": (row["error_message"] or "")[:200],
                "retryCount": int(row["retry_count"] or 0),
                "createdTime": row["created_time"].isoformat() if row["created_time"] else None,
            }
            for row in rows
        ]
        return _ok({"records": records, "total": len(records)})
    except Exception as exc:
        logger.warning(
            "list_delivery_records failed tenantId=%d errorType=%s",
            tenant_id, type(exc).__name__,
        )
        return _fail("查询发货记录失败，请稍后重试")


async def list_card_groups(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    **_: Any,
) -> ToolResult:
    """查询卡密/货源库分组列表。"""
    try:
        stmt = (
            select(
                CardGroup.id,
                CardGroup.group_name,
                CardGroup.group_type,
                CardGroup.total_count,
                CardGroup.used_count,
                CardGroup.remain_count,
                CardGroup.available_count,
                CardGroup.status,
                CardGroup.remark,
            )
            .where(
                CardGroup.tenant_id == tenant_id,
                CardGroup.user_id == user_id,
                CardGroup.deleted == 0,
            )
            .order_by(CardGroup.id.desc())
            .limit(50)
        )
        rows = (await db.execute(stmt)).all()
        groups = [
            {
                "id": int(row[0]),
                "groupName": row[1] or "",
                "groupType": row[2] or "kami",
                "totalCount": int(row[3] or 0),
                "usedCount": int(row[4] or 0),
                "remainCount": int(row[5] or 0),
                "availableCount": int(row[6] or 0),
                "status": int(row[7] or 0),
                "remark": row[8] or "",
            }
            for row in rows
        ]
        return _ok({"groups": groups, "total": len(groups)})
    except Exception as exc:
        logger.warning(
            "list_card_groups failed tenantId=%d errorType=%s",
            tenant_id, type(exc).__name__,
        )
        return _fail("查询卡密分组失败，请稍后重试")


async def list_workflows(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    limit: int = 10,
    **_: Any,
) -> ToolResult:
    """查询工作流定义列表。"""
    limit = max(1, min(int(limit or 10), 50))
    try:
        stmt = (
            select(
                WorkflowDefinition.id,
                WorkflowDefinition.name,
                WorkflowDefinition.description,
                WorkflowDefinition.trigger_type,
                WorkflowDefinition.status,
                WorkflowDefinition.version,
                WorkflowDefinition.execution_count,
                WorkflowDefinition.updated_time,
            )
            .where(
                WorkflowDefinition.tenant_id == tenant_id,
                WorkflowDefinition.user_id == user_id,
                WorkflowDefinition.deleted == 0,
            )
            .order_by(WorkflowDefinition.id.desc())
            .limit(limit)
        )
        rows = (await db.execute(stmt)).all()
        workflows = [
            {
                "id": int(row[0]),
                "name": row[1] or "",
                "description": (row[2] or "")[:200],
                "triggerType": row[3] or "manual",
                "status": row[4] or "draft",
                "version": int(row[5] or 1),
                "executionCount": int(row[6] or 0),
                "updatedTime": row[7].isoformat() if row[7] else None,
            }
            for row in rows
        ]
        return _ok({"workflows": workflows, "total": len(workflows)})
    except Exception as exc:
        logger.warning(
            "list_workflows failed tenantId=%d errorType=%s",
            tenant_id, type(exc).__name__,
        )
        return _fail("查询工作流列表失败，请稍后重试")


async def list_scheduled_tasks(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    **_: Any,
) -> ToolResult:
    """查询定时任务列表。"""
    try:
        sql = (
            "SELECT id, account_id, task_type, task_name, cron_expr, status, "
            "last_run_time, next_run_time "
            "FROM scheduled_task "
            "WHERE tenant_id = :tenant_id AND user_id = :user_id AND deleted = 0 "
            "ORDER BY id DESC LIMIT 50"
        )
        rows = (await db.execute(text(sql), {"tenant_id": tenant_id, "user_id": user_id})).mappings().all()
        tasks = [
            {
                "id": int(row["id"]),
                "accountId": int(row["account_id"] or 0),
                "taskType": row["task_type"] or "",
                "taskName": row["task_name"] or "",
                "cronExpr": row["cron_expr"] or "",
                "status": int(row["status"] or 0),
                "lastRunTime": row["last_run_time"].isoformat() if row["last_run_time"] else None,
                "nextRunTime": row["next_run_time"].isoformat() if row["next_run_time"] else None,
            }
            for row in rows
        ]
        return _ok({"tasks": tasks, "total": len(tasks)})
    except Exception as exc:
        logger.warning(
            "list_scheduled_tasks failed tenantId=%d errorType=%s",
            tenant_id, type(exc).__name__,
        )
        return _fail("查询定时任务失败，请稍后重试")


async def list_auto_reply_rules(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    account_id: Optional[int] = None,
    limit: int = 10,
    **_: Any,
) -> ToolResult:
    """查询自动回复规则列表。"""
    limit = max(1, min(int(limit or 10), 50))
    try:
        sql = (
            "SELECT r.id, r.account_id, r.rule_name, r.match_type, r.match_keywords, "
            "r.reply_content, r.reply_mode, r.status, r.priority, r.updated_time "
            "FROM auto_reply_rule r "
            "INNER JOIN xianyu_account a ON a.id = r.account_id "
            "WHERE r.tenant_id = :tenant_id AND a.user_id = :user_id "
            "AND r.deleted = 0 AND a.deleted = 0"
        )
        params: Dict[str, Any] = {"tenant_id": tenant_id, "user_id": user_id}
        if account_id and int(account_id) > 0:
            sql += " AND r.account_id = :account_id"
            params["account_id"] = int(account_id)
        sql += " ORDER BY r.priority DESC, r.id DESC LIMIT :limit"
        params["limit"] = limit
        rows = (await db.execute(text(sql), params)).mappings().all()
        rules = [
            {
                "id": int(row["id"]),
                "accountId": int(row["account_id"] or 0),
                "ruleName": row["rule_name"] or "",
                "matchType": row["match_type"] or "keyword",
                "matchKeywords": row["match_keywords"] or "",
                "replyContent": (row["reply_content"] or "")[:200],
                "replyMode": row["reply_mode"] or "keyword",
                "status": int(row["status"] or 0),
                "priority": int(row["priority"] or 0),
                "updatedTime": row["updated_time"].isoformat() if row["updated_time"] else None,
            }
            for row in rows
        ]
        return _ok({"rules": rules, "total": len(rules)})
    except Exception as exc:
        logger.warning(
            "list_auto_reply_rules failed tenantId=%d errorType=%s",
            tenant_id, type(exc).__name__,
        )
        return _fail("查询自动回复规则失败，请稍后重试")


async def get_token_balance(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    **_: Any,
) -> ToolResult:
    """查询当前用户的 Token 余额（调用 Java 内部 API）。"""
    try:
        from ..core.config import settings
        import httpx

        base = (settings.core_api_base_url or "").rstrip("/")
        if not base:
            return _fail("AI 计费服务未配置")

        headers = {"Content-Type": "application/json"}
        if settings.effective_internal_api_token:
            headers["X-Internal-Token"] = settings.effective_internal_api_token

        async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
            resp = await client.get(
                f"{base}/api/ai-billing/internal-balance",
                headers=headers,
                params={"tenantId": tenant_id, "userId": user_id},
            )
            if resp.status_code != 200:
                logger.info(
                    "get_token_balance http %d tenantId=%d userId=%d",
                    resp.status_code, tenant_id, user_id,
                )
                return _fail("查询 Token 余额失败")
            data = resp.json()
            # 兼容 Result<{balance: number, ...}> 与裸对象
            balance = None
            if isinstance(data, dict):
                payload = data.get("data") if isinstance(data.get("data"), dict) else data
                balance = payload.get("balance") if isinstance(payload, dict) else None
            if balance is None:
                return _fail("Token 余额数据格式异常")
            return _ok({
                "balance": int(balance),
                "message": f"当前 Token 余额：{int(balance)}",
            })
    except Exception as exc:
        logger.warning(
            "get_token_balance failed tenantId=%d userId=%d errorType=%s",
            tenant_id, user_id, type(exc).__name__,
        )
        return _fail("查询 Token 余额失败，请稍后重试")


async def get_dashboard_summary(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    **_: Any,
) -> ToolResult:
    """查询数据面板汇总：商品总数、今日订单金额、待发货订单数、发货统计。"""
    try:
        # 商品总数
        goods_sql = (
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END) AS on_shelf "
            "FROM xianyu_goods g "
            "INNER JOIN xianyu_account a ON a.id = g.account_id "
            "WHERE g.tenant_id = :tenant_id AND a.user_id = :user_id "
            "AND g.deleted = 0 AND a.deleted = 0"
        )
        goods_row = (await db.execute(text(goods_sql), {"tenant_id": tenant_id, "user_id": user_id})).mappings().first()

        # 今日订单金额与待发货数
        orders_sql = (
            "SELECT COUNT(*) AS total_orders, "
            "SUM(CASE WHEN order_status = 2 THEN 1 ELSE 0 END) AS pending_ship, "
            "SUM(CASE WHEN order_status IN (1,2,3,4) THEN CAST(total_amount AS DECIMAL(12,2)) ELSE 0 END) AS today_amount "
            "FROM xianyu_trade_order o "
            "INNER JOIN xianyu_account a ON a.id = o.account_id "
            "WHERE o.tenant_id = :tenant_id AND a.user_id = :user_id "
            "AND o.deleted = 0 AND a.deleted = 0 "
            "AND DATE(o.created_time) = CURDATE()"
        )
        orders_row = (await db.execute(text(orders_sql), {"tenant_id": tenant_id, "user_id": user_id})).mappings().first()

        # 发货统计
        delivery_sql = (
            "SELECT "
            "SUM(CASE WHEN delivery_status = 'success' THEN 1 ELSE 0 END) AS success, "
            "SUM(CASE WHEN delivery_status = 'failed' THEN 1 ELSE 0 END) AS failed, "
            "SUM(CASE WHEN delivery_status = 'pending' THEN 1 ELSE 0 END) AS pending "
            "FROM delivery_record r "
            "INNER JOIN xianyu_account a ON a.id = r.account_id "
            "WHERE r.tenant_id = :tenant_id AND a.user_id = :user_id "
            "AND r.deleted = 0 AND a.deleted = 0 "
            "AND DATE(r.created_time) = CURDATE()"
        )
        delivery_row = (await db.execute(text(delivery_sql), {"tenant_id": tenant_id, "user_id": user_id})).mappings().first()

        return _ok({
            "goodsTotal": int(goods_row["total"] or 0) if goods_row else 0,
            "goodsOnShelf": int(goods_row["on_shelf"] or 0) if goods_row else 0,
            "todayOrders": int(orders_row["total_orders"] or 0) if orders_row else 0,
            "todayOrderAmount": str(orders_row["today_amount"] or 0) if orders_row else "0",
            "pendingShipOrders": int(orders_row["pending_ship"] or 0) if orders_row else 0,
            "todayDeliverySuccess": int(delivery_row["success"] or 0) if delivery_row else 0,
            "todayDeliveryFailed": int(delivery_row["failed"] or 0) if delivery_row else 0,
            "todayDeliveryPending": int(delivery_row["pending"] or 0) if delivery_row else 0,
        })
    except Exception as exc:
        logger.warning(
            "get_dashboard_summary failed tenantId=%d errorType=%s",
            tenant_id, type(exc).__name__,
        )
        return _fail("查询数据面板失败，请稍后重试")


# ============================================================
# 操作类工具：重试发货 / 切换定时任务 / 切换自动回复规则
# ============================================================


async def retry_delivery_record(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    record_id: int,
    **_: Any,
) -> ToolResult:
    """重试失败的发货记录（仅将状态重置为 pending，实际发货由 worker 异步执行）。"""
    record_id = _safe_int(record_id)
    if record_id <= 0:
        return _fail("recordId 必须为正整数")
    try:
        # 校验归属
        sql = (
            "SELECT r.delivery_status FROM delivery_record r "
            "INNER JOIN xianyu_account a ON a.id = r.account_id "
            "WHERE r.tenant_id = :tenant_id AND a.user_id = :user_id "
            "AND r.id = :record_id AND r.deleted = 0"
        )
        row = (await db.execute(text(sql), {"tenant_id": tenant_id, "user_id": user_id, "record_id": record_id})).mappings().first()
        if row is None:
            return _fail("发货记录不存在或无权访问")
        if row["delivery_status"] == "success":
            return _fail("该发货记录已成功，无需重试")

        await db.execute(
            text(
                "UPDATE delivery_record SET delivery_status = 'pending', "
                "error_message = NULL, retry_count = retry_count + 1, updated_time = NOW() "
                "WHERE id = :record_id AND tenant_id = :tenant_id"
            ),
            {"record_id": record_id, "tenant_id": tenant_id},
        )
        await db.flush()
        logger.info(
            "retry_delivery_record ok tenantId=%d userId=%d recordId=%d",
            tenant_id, user_id, record_id,
        )
        return _ok({
            "recordId": record_id,
            "status": "pending",
            "message": "已重置为待处理，系统将尽快自动重试发货",
        })
    except Exception as exc:
        logger.warning(
            "retry_delivery_record failed tenantId=%d recordId=%d errorType=%s",
            tenant_id, record_id, type(exc).__name__,
        )
        await db.rollback()
        return _fail("重试发货失败，请稍后重试")


async def toggle_scheduled_task(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    task_id: int,
    enabled: bool,
    **_: Any,
) -> ToolResult:
    """启用或禁用定时任务。"""
    task_id = _safe_int(task_id)
    if task_id <= 0:
        return _fail("taskId 必须为正整数")
    try:
        # 校验归属
        sql = (
            "SELECT id FROM scheduled_task "
            "WHERE tenant_id = :tenant_id AND user_id = :user_id "
            "AND id = :task_id AND deleted = 0"
        )
        row = (await db.execute(text(sql), {"tenant_id": tenant_id, "user_id": user_id, "task_id": task_id})).mappings().first()
        if row is None:
            return _fail("定时任务不存在或无权访问")

        new_status = 1 if enabled else 0
        await db.execute(
            text("UPDATE scheduled_task SET status = :status, updated_time = NOW() WHERE id = :task_id"),
            {"status": new_status, "task_id": task_id},
        )
        await db.flush()
        logger.info(
            "toggle_scheduled_task ok tenantId=%d userId=%d taskId=%d enabled=%s",
            tenant_id, user_id, task_id, bool(enabled),
        )
        return _ok({
            "taskId": task_id,
            "enabled": bool(enabled),
            "message": f"定时任务已{'启用' if enabled else '禁用'}",
        })
    except Exception as exc:
        logger.warning(
            "toggle_scheduled_task failed tenantId=%d taskId=%d errorType=%s",
            tenant_id, task_id, type(exc).__name__,
        )
        await db.rollback()
        return _fail("切换定时任务状态失败，请稍后重试")


async def toggle_auto_reply_rule(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    rule_id: int,
    enabled: bool,
    **_: Any,
) -> ToolResult:
    """启用或禁用自动回复规则。"""
    rule_id = _safe_int(rule_id)
    if rule_id <= 0:
        return _fail("ruleId 必须为正整数")
    try:
        # 校验归属
        sql = (
            "SELECT r.id FROM auto_reply_rule r "
            "INNER JOIN xianyu_account a ON a.id = r.account_id "
            "WHERE r.tenant_id = :tenant_id AND a.user_id = :user_id "
            "AND r.id = :rule_id AND r.deleted = 0"
        )
        row = (await db.execute(text(sql), {"tenant_id": tenant_id, "user_id": user_id, "rule_id": rule_id})).mappings().first()
        if row is None:
            return _fail("自动回复规则不存在或无权访问")

        new_status = 1 if enabled else 0
        await db.execute(
            text("UPDATE auto_reply_rule SET status = :status, updated_time = NOW() WHERE id = :rule_id"),
            {"status": new_status, "rule_id": rule_id},
        )
        await db.flush()
        logger.info(
            "toggle_auto_reply_rule ok tenantId=%d userId=%d ruleId=%d enabled=%s",
            tenant_id, user_id, rule_id, bool(enabled),
        )
        return _ok({
            "ruleId": rule_id,
            "enabled": bool(enabled),
            "message": f"自动回复规则已{'启用' if enabled else '禁用'}",
        })
    except Exception as exc:
        logger.warning(
            "toggle_auto_reply_rule failed tenantId=%d ruleId=%d errorType=%s",
            tenant_id, rule_id, type(exc).__name__,
        )
        await db.rollback()
        return _fail("切换自动回复规则状态失败，请稍后重试")


# ============================================================
# 工具注册表：供 ai_cs_runtime 解析与调度
# ============================================================

ToolFunc = Callable[..., Awaitable[ToolResult]]

TOOL_REGISTRY: Dict[str, ToolFunc] = {
    # 账号与商品
    "list_accounts": list_accounts,
    "get_account_status": get_account_status,
    "list_products": list_products,
    "get_goods_detail": get_goods_detail,
    "get_account_summary": get_account_summary,
    # 订单与发货
    "list_orders": list_orders,
    "list_delivery_records": list_delivery_records,
    "retry_delivery_record": retry_delivery_record,
    # 卡密与工作流
    "list_card_groups": list_card_groups,
    "list_workflows": list_workflows,
    "list_scheduled_tasks": list_scheduled_tasks,
    "list_auto_reply_rules": list_auto_reply_rules,
    # 数据面板与余额
    "get_token_balance": get_token_balance,
    "get_dashboard_summary": get_dashboard_summary,
    # 创建类
    "create_qr_login": create_qr_login,
    "create_auto_reply_rule": create_auto_reply_rule,
    "create_delivery_rule": create_delivery_rule,
    "create_card_group": create_card_group,
    "create_workflow": create_workflow,
    "create_scheduled_task": create_scheduled_task,
    "polish_product_title": polish_product_title,
    # 切换类
    "toggle_scheduled_task": toggle_scheduled_task,
    "toggle_auto_reply_rule": toggle_auto_reply_rule,
}


# 工具元信息：供 AI 在系统提示中识别可调用工具
TOOL_DEFINITIONS: list[Dict[str, Any]] = [
    # ===== 账号与商品 =====
    {
        "name": "list_accounts",
        "description": "列出当前用户名下的闲鱼账号（仅元信息，不含 cookie/token）",
        "parameters": {},
    },
    {
        "name": "get_account_status",
        "description": "查询单个账号的运行时状态：在线状态、WS 连接、Cookie 状态、最近登录检查",
        "parameters": {
            "accountId": "int (必填) 闲鱼账号ID",
        },
    },
    {
        "name": "get_account_summary",
        "description": "查询当前用户的账号汇总统计：总数、正常、异常、在线数",
        "parameters": {},
    },
    {
        "name": "list_products",
        "description": "列出指定账号下的商品（用于客服查看商品上下文）",
        "parameters": {
            "accountId": "int (必填) 闲鱼账号ID",
            "limit": "int (可选) 返回数量，默认10，最大50",
        },
    },
    {
        "name": "get_goods_detail",
        "description": "查询单个商品详情（含 SKU 与发货规则）",
        "parameters": {
            "goodsId": "int (必填) 商品ID",
        },
    },
    # ===== 订单与发货 =====
    {
        "name": "list_orders",
        "description": "查询订单列表，可按账号与订单状态过滤。订单状态：0=待付款,1=已付款,2=待发货,3=已发货,4=已完成,5=已关闭",
        "parameters": {
            "accountId": "int (可选) 闲鱼账号ID，不传则查全部账号",
            "status": "int (可选) 订单状态 0-5",
            "limit": "int (可选) 返回数量，默认10，最大50",
        },
    },
    {
        "name": "list_delivery_records",
        "description": "查询发货记录，可按账号与发货状态过滤。状态：pending=待处理,success=成功,failed=失败",
        "parameters": {
            "accountId": "int (可选) 闲鱼账号ID",
            "status": "string (可选) 发货状态：pending/success/failed",
            "limit": "int (可选) 返回数量，默认10，最大50",
        },
    },
    {
        "name": "retry_delivery_record",
        "description": "重试失败的发货记录（仅将状态重置为 pending，实际发货由 worker 异步执行）",
        "parameters": {
            "recordId": "int (必填) 发货记录ID",
        },
    },
    # ===== 卡密与工作流 =====
    {
        "name": "list_card_groups",
        "description": "查询卡密/货源库分组列表",
        "parameters": {},
    },
    {
        "name": "list_workflows",
        "description": "查询工作流定义列表",
        "parameters": {
            "limit": "int (可选) 返回数量，默认10，最大50",
        },
    },
    {
        "name": "list_scheduled_tasks",
        "description": "查询定时任务列表",
        "parameters": {},
    },
    {
        "name": "list_auto_reply_rules",
        "description": "查询自动回复规则列表",
        "parameters": {
            "accountId": "int (可选) 闲鱼账号ID",
            "limit": "int (可选) 返回数量，默认10，最大50",
        },
    },
    # ===== 数据面板与余额 =====
    {
        "name": "get_token_balance",
        "description": "查询当前用户的 Token 余额",
        "parameters": {},
    },
    {
        "name": "get_dashboard_summary",
        "description": "查询数据面板汇总：商品总数、今日订单金额、待发货订单数、发货统计",
        "parameters": {},
    },
    # ===== 创建类 =====
    {
        "name": "create_qr_login",
        "description": "创建闲鱼扫码登录会话，返回二维码图片与 sessionId",
        "parameters": {},
    },
    {
        "name": "create_auto_reply_rule",
        "description": "创建自动回复规则（仅落库，不立即生效）",
        "parameters": {
            "accountId": "int (必填) 闲鱼账号ID",
            "ruleName": "string (必填) 规则名称",
            "matchType": "string (必填) 匹配类型：keyword/ai/all",
            "matchKeywords": "string (keyword 类型必填) 关键词，逗号分隔",
            "replyContent": "string (必填) 回复内容",
        },
    },
    {
        "name": "create_delivery_rule",
        "description": "创建自动发货规则（不立即触发发货，仅落库）",
        "parameters": {
            "accountId": "int (必填) 闲鱼账号ID",
            "ruleName": "string (必填) 规则名称",
            "goodsId": "int (必填) 关联商品ID",
            "deliveryMode": "string (必填) 发货方式：kami/text",
            "cardGroupId": "int (kami 必填) 卡密分组ID",
            "deliveryContent": "string (text 必填) 文本发货内容",
            "triggerOnPay": "int (可选) 付款触发：1是 0否，默认1",
            "triggerKeyword": "string (可选) 关键词触发",
        },
    },
    {
        "name": "create_card_group",
        "description": "创建卡密/货源库分组（空分组，需后续导入卡密）",
        "parameters": {
            "groupName": "string (必填) 分组名称",
            "groupType": "string (可选) 分组类型：kami/text，默认kami",
            "remark": "string (可选) 备注",
        },
    },
    {
        "name": "create_workflow",
        "description": "创建工作流定义（草稿状态，用户需在前端完善节点）",
        "parameters": {
            "name": "string (必填) 工作流名称",
            "description": "string (可选) 描述",
            "triggerType": "string (可选) 触发方式：manual/scheduled/event，默认manual",
        },
    },
    {
        "name": "create_scheduled_task",
        "description": "创建定时任务记录（默认未启用，需在前端启用）",
        "parameters": {
            "accountId": "int (必填) 闲鱼账号ID",
            "taskType": "string (必填) 任务类型",
            "cronExpr": "string (必填) Cron 表达式",
            "taskName": "string (可选) 任务名称",
        },
    },
    {
        "name": "polish_product_title",
        "description": "使用通用模型润色商品标题（按次计费，不直接写库，返回新标题供用户确认）",
        "parameters": {
            "goodsId": "int (必填) 商品ID",
        },
    },
    # ===== 切换类 =====
    {
        "name": "toggle_scheduled_task",
        "description": "启用或禁用定时任务",
        "parameters": {
            "taskId": "int (必填) 定时任务ID",
            "enabled": "bool (必填) true=启用 false=禁用",
        },
    },
    {
        "name": "toggle_auto_reply_rule",
        "description": "启用或禁用自动回复规则",
        "parameters": {
            "ruleId": "int (必填) 自动回复规则ID",
            "enabled": "bool (必填) true=启用 false=禁用",
        },
    },
]


def get_tool_names() -> list[str]:
    """返回已注册的工具名列表。"""
    return list(TOOL_REGISTRY.keys())


async def execute_tool(
    tool_name: str,
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    arguments: Dict[str, Any],
) -> ToolResult:
    """按名称执行工具。未知工具返回友好错误。"""
    func = TOOL_REGISTRY.get(tool_name)
    if func is None:
        return _fail(f"未知工具：{tool_name}")
    try:
        return await func(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            **arguments,
        )
    except TypeError as exc:
        # 参数缺失/类型不匹配
        logger.info(
            "execute_tool invalid args tool=%s tenantId=%d errorType=%s",
            tool_name, tenant_id, type(exc).__name__,
        )
        return _fail(f"工具参数无效：{tool_name}")
    except Exception as exc:
        logger.warning(
            "execute_tool unexpected failure tool=%s tenantId=%d errorType=%s",
            tool_name, tenant_id, type(exc).__name__,
        )
        return _fail(f"工具执行失败：{tool_name}")
