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
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.entities import (
    AutoReplyRule,
    CardGroup,
    CardItem,
    DeliveryRule,
    WorkflowDefinition,
    XianyuAccount,
    XianyuAccountAuth,
    XianyuAccountHealthSnapshot,
    XianyuAccountRuntime,
    XianyuGoods,
    XianyuRefund,
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


def _humanize_online(status: int) -> str:
    """在线状态中文化：1=在线，0=离线。"""
    return "在线" if int(status or 0) == 1 else "离线"


def _humanize_ws(status: int) -> str:
    """WS 状态中文化：1=已连接，0=未连接。"""
    return "已连接" if int(status or 0) == 1 else "未连接"


def _humanize_cookie(status: int) -> str:
    """Cookie 状态中文化：1=正常，0=待校验/失效，2=已过期。"""
    s = int(status or 0)
    if s == 1:
        return "正常"
    if s == 2:
        return "已过期"
    return "待校验"


def _humanize_account_status(status: int) -> str:
    """账号状态中文化：1=正常，0=已禁用。"""
    return "正常" if int(status or 0) == 1 else "已禁用"


def _humanize_account_type(fish_shop_user: int) -> str:
    """账号类型中文化：1=鱼小铺账号，0=普通账号。"""
    return "鱼小铺账号" if int(fish_shop_user or 0) == 1 else "普通账号"


async def list_accounts(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    **_: Any,
) -> ToolResult:
    """列出当前用户名下的闲鱼账号完整信息（含地区、等级、在线、WS、Cookie、健康分）。

    联表查询 xianyu_account + xianyu_account_runtime + xianyu_account_auth，
    附加 xianyu_account_health_snapshot 的最新健康分。所有状态字段中文化展示，
    不返回 cookie/token 等敏感凭证。

    容错策略（避免"查无账号"误报）：
    1. 先按 tenant_id + user_id + deleted=0 严格查询
    2. 若严格查询无结果，回退到 tenant_id 范围（不限定 user_id）查询，
       这种情况通常是早期账号 user_id 字段未回填，仍应展示给当前租户用户
    3. 同时把 deleted=1 的软删除账号也带出来，标注为「已禁用」，
       避免用户疑惑「我的账号怎么没了」
    """
    try:
        # 基础 SELECT 字段（含 deleted 列用于区分软删除账号）
        base_columns = [
            XianyuAccount.id,
            XianyuAccount.nickname,
            XianyuAccount.external_uid,
            XianyuAccount.platform,
            XianyuAccount.province,
            XianyuAccount.city,
            XianyuAccount.account_level,
            XianyuAccount.fish_shop_user,
            XianyuAccount.status,
            XianyuAccount.remark,
            XianyuAccount.deleted.label("account_deleted"),
            XianyuAccountRuntime.online_status,
            XianyuAccountRuntime.ws_status,
            XianyuAccountRuntime.ws_latency_ms,
            XianyuAccountRuntime.cookie_status.label("runtime_cookie_status"),
            XianyuAccountRuntime.last_login_status_code,
            XianyuAccountRuntime.last_login_status_message,
            XianyuAccountRuntime.last_login_check_time,
            XianyuAccountAuth.cookie_status.label("auth_cookie_status"),
        ]

        def _build_stmt(*where_clauses: Any) -> Any:
            return (
                select(*base_columns)
                .outerjoin(
                    XianyuAccountRuntime,
                    (XianyuAccountRuntime.account_id == XianyuAccount.id)
                    & (XianyuAccountRuntime.tenant_id == XianyuAccount.tenant_id)
                    & (XianyuAccountRuntime.deleted == 0),
                )
                .outerjoin(
                    XianyuAccountAuth,
                    (XianyuAccountAuth.account_id == XianyuAccount.id)
                    & (XianyuAccountAuth.tenant_id == XianyuAccount.tenant_id)
                    & (XianyuAccountAuth.deleted == 0),
                )
                .where(*where_clauses)
                .order_by(XianyuAccount.id.desc())
                .limit(50)
            )

        # 1. 严格查询：tenant_id + user_id + deleted=0
        stmt = _build_stmt(
            XianyuAccount.tenant_id == tenant_id,
            XianyuAccount.user_id == user_id,
            XianyuAccount.deleted == 0,
        )
        rows = (await db.execute(stmt)).all()

        fallback_reason = ""  # 给 AI/前端的提示，说明为什么走了兜底
        if not rows:
            # 2. 兜底查询1：tenant_id + deleted=0（不限 user_id）
            #    适用于早期账号 user_id 未回填的情况
            stmt_fallback = _build_stmt(
                XianyuAccount.tenant_id == tenant_id,
                XianyuAccount.deleted == 0,
            )
            rows = (await db.execute(stmt_fallback)).all()
            if rows:
                fallback_reason = (
                    f"按当前用户ID（{user_id}）严格匹配未找到账号，"
                    f"已回退到租户范围查询，共找到 {len(rows)} 个账号。"
                )
                logger.info(
                    "list_accounts fallback to tenant scope tenantId=%d userId=%d rowCount=%d",
                    tenant_id, user_id, len(rows),
                )

        if not rows:
            # 3. 兜底查询2：tenant_id 范围内（含 deleted=1 的软删除账号）
            #    适用于「账号被误删但用户记忆中还存在」的场景，至少让用户看到列表
            stmt_with_deleted = _build_stmt(
                XianyuAccount.tenant_id == tenant_id,
            )
            rows = (await db.execute(stmt_with_deleted)).all()
            if rows:
                fallback_reason = (
                    f"当前用户ID（{user_id}）名下未找到启用账号，"
                    f"已展示该租户下全部 {len(rows)} 个账号（含已禁用账号，标注见 deleted 字段）。"
                )
                logger.info(
                    "list_accounts fallback include deleted tenantId=%d userId=%d rowCount=%d",
                    tenant_id, user_id, len(rows),
                )

        if not rows:
            return _ok({
                "accounts": [],
                "total": 0,
                "message": "您名下暂无闲鱼账号，是否需要扫码登录绑定一个新账号？",
            })

        # 2. 批量查询健康分快照（每个账号取最新一条）
        account_ids = [int(row[0]) for row in rows]
        health_map: Dict[int, Dict[str, Any]] = {}
        if account_ids:
            health_sql = text("""
                SELECT h.account_id, h.health_score, h.api_success_rate,
                       h.avg_response_ms, h.ws_latency_ms, h.collected_time
                FROM xianyu_account_health_snapshot h
                INNER JOIN (
                    SELECT account_id, MAX(id) AS max_id
                    FROM xianyu_account_health_snapshot
                    WHERE tenant_id = :tenant_id AND account_id IN :account_ids
                    GROUP BY account_id
                ) latest ON latest.max_id = h.id
            """)
            # SQLAlchemy text() 不直接支持 IN :list，用 expanding bindparam
            from sqlalchemy import bindparam
            health_sql = health_sql.bindparams(
                bindparam("tenant_id", value=tenant_id),
                bindparam("account_ids", expanding=True),
            )
            health_rows = (await db.execute(health_sql, {
                "tenant_id": tenant_id,
                "account_ids": account_ids,
            })).mappings().all()
            for hr in health_rows:
                aid = int(hr["account_id"] or 0)
                if aid <= 0:
                    continue
                health_map[aid] = {
                    "healthScore": int(hr["health_score"] or 100),
                    "apiSuccessRate": float(hr["api_success_rate"] or 1.0),
                    "avgResponseMs": int(hr["avg_response_ms"] or 0),
                    "wsLatencyMs": int(hr["ws_latency_ms"] or 0),
                    "collectedTime": hr["collected_time"].isoformat() if hr["collected_time"] else None,
                }

        # 3. 组装返回结果（中文化字段）
        # SELECT 列顺序（base_columns）：
        # 0=id, 1=nickname, 2=external_uid, 3=platform, 4=province, 5=city,
        # 6=account_level, 7=fish_shop_user, 8=status, 9=remark, 10=deleted,
        # 11=online_status, 12=ws_status, 13=ws_latency_ms,
        # 14=runtime_cookie_status, 15=last_login_status_code,
        # 16=last_login_status_message, 17=last_login_check_time,
        # 18=auth_cookie_status
        accounts: List[Dict[str, Any]] = []
        for row in rows:
            account_id = int(row[0])
            # 地区拼接
            province = _safe_str(row[4])
            city = _safe_str(row[5])
            region_parts = [p for p in [province, city] if p]
            region = " ".join(region_parts) if region_parts else "未知"

            # Cookie 状态：优先 runtime，回退 auth
            runtime_cookie = row[14]
            auth_cookie = row[18]
            cookie_status_val = runtime_cookie if runtime_cookie is not None else auth_cookie
            cookie_status_int = int(cookie_status_val or 0)

            # 健康分
            health = health_map.get(account_id, {})
            health_score = int(health.get("healthScore", 100))

            # 软删除标记：deleted=1 表示账号已被软删除
            account_deleted = int(row[10] or 0)
            account_status_raw = int(row[8] or 0)
            # 综合账号可见状态：软删除优先级最高
            if account_deleted == 1:
                account_status_text = "已禁用（已删除）"
                enabled_flag = False
            elif account_status_raw == 1:
                account_status_text = "正常"
                enabled_flag = True
            else:
                account_status_text = "已禁用"
                enabled_flag = False

            accounts.append({
                "id": account_id,
                "nickname": _safe_str(row[1]) or f"账号#{account_id}",
                "uid": _safe_str(row[2]),
                "platform": _safe_str(row[3]) or "xianyu",
                "region": region,
                "level": _safe_str(row[6]) or "未知",
                "accountType": _humanize_account_type(int(row[7] or 0)),
                "enabled": enabled_flag,
                "deleted": account_deleted == 1,
                "accountStatus": account_status_text,
                "remark": _safe_str(row[9]),
                "onlineStatus": _humanize_online(int(row[11] or 0)),
                "wsStatus": _humanize_ws(int(row[12] or 0)),
                "wsLatencyMs": int(row[13] or 0) if row[13] is not None else 0,
                "cookieStatus": _humanize_cookie(cookie_status_int),
                "cookieStatusCode": cookie_status_int,
                "lastLoginStatusCode": _safe_str(row[15]),
                "lastLoginMessage": _safe_str(row[16]),
                "lastLoginCheckTime": row[17].isoformat() if row[17] else None,
                "healthScore": health_score,
                "healthLevel": (
                    "优秀" if health_score >= 90
                    else "良好" if health_score >= 70
                    else "一般" if health_score >= 50
                    else "较差"
                ),
                "apiSuccessRate": health.get("apiSuccessRate", 1.0),
                "avgResponseMs": health.get("avgResponseMs", 0),
            })

        active_count = sum(1 for a in accounts if not a["deleted"])
        deleted_count = sum(1 for a in accounts if a["deleted"])
        result_data: Dict[str, Any] = {
            "accounts": accounts,
            "total": len(accounts),
            "activeCount": active_count,
            "deletedCount": deleted_count,
            "summary": {
                "total": len(accounts),
                "active": active_count,
                "deleted": deleted_count,
                "online": sum(1 for a in accounts if a["onlineStatus"] == "在线"),
                "offline": sum(1 for a in accounts if a["onlineStatus"] != "在线"),
                "cookieNormal": sum(1 for a in accounts if a["cookieStatusCode"] == 1),
                "cookieAbnormal": sum(1 for a in accounts if a["cookieStatusCode"] != 1),
            },
        }
        if fallback_reason:
            result_data["fallbackReason"] = fallback_reason
        return _ok(result_data)
    except Exception as exc:
        logger.warning("list_accounts failed tenantId=%d errorType=%s", tenant_id, type(exc).__name__, exc_info=True)
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
            exc_info=True,
        )
        return _fail("查询账号状态失败，请稍后重试")


async def list_products(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    account_id: Optional[int] = None,
    limit: int = 10,
    **_: Any,
) -> ToolResult:
    """列出指定账号下的商品（用于客服查看商品上下文）。

    accountId 未提供时自动选择该租户下第一个可用账号（与系统提示"自动选择账号"规则对齐）。
    """
    limit = max(1, min(int(limit or 10), 50))
    account_id = _safe_int(account_id) if account_id else 0
    try:
        # accountId 未提供时，自动选择租户下第一个可用账号
        # 仅按 tenant_id 过滤（与 list_orders/list_delivery_records 一致），
        # 后续 ownership 校验会确认账号归属
        if account_id <= 0:
            auto_row = (await db.execute(
                select(XianyuAccount.id).where(
                    XianyuAccount.tenant_id == tenant_id,
                    XianyuAccount.deleted == 0,
                ).order_by(XianyuAccount.id.asc()).limit(1)
            )).scalar_one_or_none()
            if auto_row is None:
                return _fail("您当前没有可用的闲鱼账号，请先绑定账号")
            account_id = int(auto_row)

        # 校验账号归属（仅 tenant_id 隔离；user_id 字段在不同部署下可能为 NULL）
        owner_row = (await db.execute(
            select(XianyuAccount.id).where(
                XianyuAccount.tenant_id == tenant_id,
                XianyuAccount.id == account_id,
                XianyuAccount.deleted == 0,
            )
        )).scalar_one_or_none()
        if owner_row is None:
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
            exc_info=True,
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
            exc_info=True,
        )
        return _fail("生成扫码登录二维码失败，请稍后重试")
    except Exception as exc:
        logger.warning(
            "create_qr_login unexpected failure tenantId=%d userId=%d errorType=%s",
            tenant_id, user_id, type(exc).__name__,
            exc_info=True,
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
            exc_info=True,
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
            exc_info=True,
        )
        await db.rollback()
        return _fail("创建发货规则失败，请稍后重试")


def _build_card_content(card_key: str, card_value: Optional[str] = None) -> str:
    """构建 card_content 字段，与 Java SchemaCompatibilityRunner 第2898行逻辑对齐。

    前端卡密列表展示直接读 card_content 字段，未填充会导致前端显示为空。
    规则：
    - 有 card_value：card_content = "card_key----card_value"
    - 无 card_value：card_content = card_key
    """
    if card_value and card_value.strip():
        return f"{card_key}----{card_value}"
    return card_key


def _parse_cards_input(cards: List[Any]) -> tuple[List[Dict[str, str]], int]:
    """解析卡密输入数组，返回 (有效卡密列表, 无效条数)。

    支持以下输入格式：
    - 字符串：直接作为 card_key（适用于单纯卡密）
    - 对象 {"key": "...", "value": "...", "remark": "..."}：完整字段

    特殊处理：用户用换行/逗号/分号分隔的多行字符串会被拆分为多条卡密。
    """
    valid_items: List[Dict[str, str]] = []
    invalid_count = 0
    for raw in cards:
        card_key = ""
        card_value = ""
        card_remark = ""
        if isinstance(raw, str):
            # 用户可能传入 "卡密1\n卡密2" 单字符串，需拆分
            for part in re.split(r"[\r\n,;]+", raw):
                part = part.strip()
                if not part:
                    continue
                valid_items.append({
                    "card_key": part[:5000],
                    "card_value": "",
                    "card_remark": "",
                })
            continue
        elif isinstance(raw, dict):
            card_key = _safe_str(raw.get("key") or raw.get("cardKey") or raw.get("card_key"))
            card_value = _safe_str(raw.get("value") or raw.get("cardValue") or raw.get("card_value"))
            card_remark = _safe_str(raw.get("remark"))
        if not card_key:
            invalid_count += 1
            continue
        valid_items.append({
            "card_key": card_key[:5000],
            "card_value": card_value[:5000] if card_value else "",
            "card_remark": card_remark[:500] if card_remark else "",
        })
    return valid_items, invalid_count


async def create_card_group(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    group_name: str,
    group_type: str = "kami",
    remark: str = "",
    cards: Optional[List[Any]] = None,
    **_: Any,
) -> ToolResult:
    """创建卡密/货源库分组，可同时批量导入卡密条目。

    参数：
    - group_name: 分组名称
    - group_type: 分组类型 kami/text，默认 kami
    - remark: 备注
    - cards: 可选，卡密条目数组。每项可为：
        - 字符串：直接作为 card_key（适用于单纯卡密）
        - 对象 {"key": "...", "value": "...", "remark": "..."}：完整字段
      传入时会在创建分组后批量写入卡密条目，并刷新分组计数。
    """
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

        # 批量导入卡密（如果传入）
        imported_count = 0
        invalid_count = 0
        if cards and isinstance(cards, list):
            # 使用统一解析函数：支持字符串、对象、多行字符串拆分
            valid_items, invalid_count = _parse_cards_input(cards)
            for item_data in valid_items:
                card_key = item_data["card_key"]
                card_value = item_data["card_value"]
                card_remark = item_data["card_remark"]
                # 关键：同步填充 card_content 字段，前端列表展示依赖此字段
                # 与 Java SchemaCompatibilityRunner 第2898行逻辑对齐
                card_content = _build_card_content(card_key, card_value)
                item = CardItem(
                    group_id=group_id,
                    tenant_id=tenant_id,
                    card_key=card_key,
                    card_value=card_value if card_value else None,
                    card_content=card_content,
                    remark=card_remark if card_remark else None,
                    is_used=0,
                    deleted=0,
                )
                db.add(item)
                imported_count += 1
            if imported_count > 0:
                await db.flush()
                # 刷新分组计数
                await _refresh_card_group_counts(db, group_id)

        logger.info(
            "create_card_group ok tenantId=%d userId=%d groupId=%d imported=%d invalid=%d",
            tenant_id, user_id, group_id, imported_count, invalid_count,
        )
        result_data: Dict[str, Any] = {
            "groupId": group_id,
            "groupName": group.group_name,
            "groupType": group.group_type,
            "status": "created",
            "importedCount": imported_count,
        }
        if invalid_count > 0:
            result_data["invalidCount"] = invalid_count
        return _ok(result_data)
    except Exception as exc:
        logger.warning(
            "create_card_group failed tenantId=%d errorType=%s",
            tenant_id, type(exc).__name__,
            exc_info=True,
        )
        await db.rollback()
        return _fail("创建货源库分组失败，请稍后重试")


async def _refresh_card_group_counts(db: AsyncSession, group_id: int) -> None:
    """刷新卡密分组的 total/used/remain/available 计数。

    与 kami.py 的 _refresh_group_counts 对齐：
    - total_count = 未删除卡密总数
    - used_count = status=2 或 is_used=1 的已使用数
    - remain_count = available_count = status=0 且 is_used=0 的可用数
    """
    try:
        total = (await db.execute(
            text("SELECT COUNT(*) FROM card_item WHERE group_id = :gid AND deleted = 0"),
            {"gid": group_id},
        )).scalar() or 0
        used = (await db.execute(
            text(
                "SELECT COUNT(*) FROM card_item WHERE group_id = :gid AND deleted = 0 "
                "AND (status = 2 OR is_used = 1)"
            ),
            {"gid": group_id},
        )).scalar() or 0
        remain = max(0, int(total) - int(used))
        await db.execute(
            text(
                "UPDATE card_group SET total_count = :total, used_count = :used, "
                "remain_count = :remain, available_count = :remain, updated_time = NOW() "
                "WHERE id = :gid"
            ),
            {
                "gid": group_id,
                "total": int(total),
                "used": int(used),
                "remain": int(remain),
            },
        )
    except Exception as exc:
        logger.warning(
            "_refresh_card_group_counts failed groupId=%d errorType=%s",
            group_id, type(exc).__name__,
            exc_info=True,
        )


async def import_cards(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    group_id: int,
    cards: List[Any],
    **_: Any,
) -> ToolResult:
    """向已存在的卡密分组批量导入卡密条目。

    参数：
    - group_id: 目标分组ID（必填）
    - cards: 卡密条目数组（必填），格式同 create_card_group 的 cards 参数
    """
    group_id = _safe_int(group_id)
    if group_id <= 0:
        return _fail("groupId 必须为正整数")
    if not cards or not isinstance(cards, list) or len(cards) == 0:
        return _fail("cards 不能为空，请至少提供一条卡密")

    try:
        # 校验分组归属
        owner_row = (await db.execute(
            select(CardGroup.user_id).where(
                CardGroup.tenant_id == tenant_id,
                CardGroup.id == group_id,
                CardGroup.deleted == 0,
            )
        )).scalar_one_or_none()
        if owner_row is None:
            return _fail("卡密分组不存在或无权访问")
        # user_id 为 NULL 的早期分组允许当前用户操作；否则必须严格匹配
        if owner_row is not None and int(owner_row or 0) != 0 and int(owner_row) != user_id:
            return _fail("卡密分组不存在或无权访问")

        imported_count = 0
        invalid_count = 0
        # 使用统一解析函数：与 create_card_group 保持一致，支持多行字符串拆分
        valid_items, parse_invalid = _parse_cards_input(cards)
        invalid_count = parse_invalid
        for item_data in valid_items:
            card_key = item_data["card_key"]
            card_value = item_data["card_value"]
            card_remark = item_data["card_remark"]
            # 关键：同步填充 card_content 字段（与 create_card_group 对齐）
            card_content = _build_card_content(card_key, card_value)
            item = CardItem(
                group_id=group_id,
                tenant_id=tenant_id,
                card_key=card_key,
                card_value=card_value if card_value else None,
                card_content=card_content,
                remark=card_remark if card_remark else None,
                is_used=0,
                deleted=0,
            )
            db.add(item)
            imported_count += 1

        if imported_count > 0:
            await db.flush()
            await _refresh_card_group_counts(db, group_id)

        logger.info(
            "import_cards ok tenantId=%d userId=%d groupId=%d imported=%d invalid=%d",
            tenant_id, user_id, group_id, imported_count, invalid_count,
        )
        result_data: Dict[str, Any] = {
            "groupId": group_id,
            "importedCount": imported_count,
        }
        if invalid_count > 0:
            result_data["invalidCount"] = invalid_count
        return _ok(result_data)
    except Exception as exc:
        logger.warning(
            "import_cards failed tenantId=%d groupId=%d errorType=%s",
            tenant_id, group_id, type(exc).__name__,
            exc_info=True,
        )
        await db.rollback()
        return _fail("批量导入卡密失败，请稍后重试")


async def delete_card_group(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    group_id: int,
    **_: Any,
) -> ToolResult:
    """删除卡密/货源库分组（软删除）。

    安全策略：
    - 仅删除空分组（available_count=0）；非空分组返回失败并提示用户先清空卡密
    - 软删除分组（deleted=1）+ 同时软删除分组下的卡密条目（deleted=1）
    - 校验租户与用户归属

    当用户说「删除卡密分组」「删除空分组」「删掉货源库」时调用。
    """
    group_id = _safe_int(group_id)
    if group_id <= 0:
        return _fail("groupId 必须为正整数")
    try:
        # 校验分组归属
        owner_row = (await db.execute(
            select(
                CardGroup.id,
                CardGroup.user_id,
                CardGroup.available_count,
                CardGroup.group_name,
            ).where(
                CardGroup.tenant_id == tenant_id,
                CardGroup.id == group_id,
                CardGroup.deleted == 0,
            )
        )).first()
        if owner_row is None:
            return _fail("卡密分组不存在或无权访问")
        # user_id 为 NULL 的早期分组允许当前用户操作；否则必须严格匹配
        owner_uid = int(owner_row[1] or 0)
        if owner_uid != 0 and owner_uid != user_id:
            return _fail("卡密分组不存在或无权访问")

        available_count = int(owner_row[2] or 0)
        group_name = owner_row[3] or ""
        # 安全护栏：仅允许删除空分组
        if available_count > 0:
            return _fail(
                f"分组「{group_name}」中还有 {available_count} 张可用卡密，"
                "请先清空卡密或将其转移到其他分组后再删除"
            )

        # 软删除分组
        await db.execute(
            text(
                "UPDATE card_group SET deleted = 1, updated_time = NOW() "
                "WHERE id = :gid AND tenant_id = :tid"
            ),
            {"gid": group_id, "tid": tenant_id},
        )
        # 同时软删除分组下的所有卡密条目（即使 available_count=0，
        # 仍可能存在 used_count>0 的已用卡密记录，一并清理）
        await db.execute(
            text(
                "UPDATE card_item SET deleted = 1, updated_time = NOW() "
                "WHERE group_id = :gid AND tenant_id = :tid"
            ),
            {"gid": group_id, "tid": tenant_id},
        )
        await db.flush()
        logger.info(
            "delete_card_group ok tenantId=%d userId=%d groupId=%d groupName=%s",
            tenant_id, user_id, group_id, group_name,
        )
        return _ok({
            "groupId": group_id,
            "groupName": group_name,
            "message": f"分组「{group_name}」已删除",
        })
    except Exception as exc:
        logger.warning(
            "delete_card_group failed tenantId=%d groupId=%d errorType=%s",
            tenant_id, group_id, type(exc).__name__,
            exc_info=True,
        )
        await db.rollback()
        return _fail("删除卡密分组失败，请稍后重试")


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
            exc_info=True,
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
                    cron_expression, enabled, deleted, created_time, updated_time
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
                "enabled": False,
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
            exc_info=True,
        )
        await db.rollback()
        return _fail("创建定时任务失败，请稍后重试")


async def polish_product_title(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    goods_id: Optional[int] = None,
    title: Optional[str] = None,
    **_: Any,
) -> ToolResult:
    """使用通用模型润色商品标题（按次计费）。

    支持两种模式：
    1. 传 goods_id：查询商品当前标题并润色
    2. 传 title：直接润色用户提供的标题文本（无需商品ID）

    流程：
    1. 获取标题（从商品查询或用户直接提供）
    2. 调用通用模型润色（按次计费）
    3. 应用禁止词硬过滤
    4. 返回润色后的标题（不直接写库，由用户在前端确认后保存）
    """
    goods_id = _safe_int(goods_id) if goods_id is not None else 0
    title_text = _safe_str(title) if title is not None else ""

    # 两种模式必须提供其一
    if goods_id <= 0 and not title_text:
        return _fail("请提供 goodsId（商品ID）或 title（要润色的标题文本）")

    try:
        detail_info = ""
        if goods_id > 0:
            # 模式1：按商品ID查询
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
            detail_info = row[1] or ""
        else:
            # 模式2：直接润色用户提供的标题
            original_title = title_text

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
            exc_info=True,
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
        # LEFT JOIN 账号表只用于补充账号信息（这里未取字段）；订单查询不依赖账号是否被删除，
        # 即使账号被软删除，订单仍应可见。不要在 WHERE 中加 a.deleted 条件，否则 LEFT JOIN 会退化为 INNER JOIN。
        sql = (
            "SELECT o.id, o.account_id, o.external_order_id, o.order_status, "
            "o.total_amount, o.buyer_name, o.create_time, o.pay_time, o.ship_time, "
            "o.item_id, o.is_bargain, o.is_rated "
            "FROM xianyu_trade_order o "
            "WHERE o.tenant_id = :tenant_id "
            "AND o.deleted = 0"
        )
        params: Dict[str, Any] = {"tenant_id": tenant_id}
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
                "totalAmount": str(row["total_amount"]) if row["total_amount"] is not None else "",
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
            exc_info=True,
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
            "WHERE tenant_id = :tenant_id AND deleted = 0"
        )
        row = (await db.execute(text(sql), {"tenant_id": tenant_id})).mappings().first()
        total = int(row["total"] or 0) if row else 0
        active = int(row["active"] or 0) if row else 0
        inactive = int(row["inactive"] or 0) if row else 0

        # 查询在线 WS 数
        online_sql = (
            "SELECT COUNT(*) AS online FROM xianyu_account_runtime r "
            "LEFT JOIN xianyu_account a ON a.id = r.account_id "
            "WHERE a.tenant_id = :tenant_id "
            "AND (a.deleted = 0 OR a.deleted IS NULL) AND r.deleted = 0 AND r.online_status = 1"
        )
        online_row = (await db.execute(text(online_sql), {"tenant_id": tenant_id})).mappings().first()
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
            exc_info=True,
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
            exc_info=True,
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
        # 单表查询：发货记录查询不依赖账号是否被软删除，账号被删除时记录仍应可见
        sql = (
            "SELECT r.id, r.account_id, r.order_id, r.rule_id, r.delivery_type, "
            "r.content, r.delivery_status, r.error_message, r.retry_count, r.created_time "
            "FROM delivery_record r "
            "WHERE r.tenant_id = :tenant_id "
            "AND r.deleted = 0"
        )
        params: Dict[str, Any] = {"tenant_id": tenant_id}
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
            exc_info=True,
        )
        return _fail("查询发货记录失败，请稍后重试")


async def list_refunds(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    account_id: Optional[int] = None,
    refund_status: Optional[str] = None,
    days: Optional[int] = None,
    limit: int = 10,
    **_: Any,
) -> ToolResult:
    """查询退款记录列表，按时间倒序返回。

    通过 join xianyu_account 限定为当前用户名下账号的退款；
    与 list_accounts 一致采用 user_id 严格匹配 + tenant_id 兜底策略，
    避免早期账号 user_id 未回填时查不到退款。

    参数：
    - account_id: 可选，限定某个账号的退款
    - refund_status: 可选，退款状态关键词（如「退款中」「退款成功」「退款关闭」），
                    模糊匹配 refund_status / common_refund_status / refund_status_desc
    - days: 可选，最近 N 天内的退款（默认不限制）
    - limit: 返回数量，默认 10，最大 50
    """
    limit = max(1, min(int(limit or 10), 50))
    days_int = 0
    if days is not None:
        try:
            days_int = max(0, int(days))
        except (TypeError, ValueError):
            days_int = 0

    try:
        # 主查询：tenant_id + user_id 严格匹配（通过 join xianyu_account.user_id）
        # 注：LEFT JOIN + WHERE a.user_id 会让 LEFT JOIN 退化为 INNER JOIN，
        # 这是预期行为——主查询只返回当前用户名下账号的退款；
        # 找不到时下方 fallback 用 tenant_id 范围兜底，覆盖早期 user_id 未回填的账号
        sql = (
            "SELECT r.id, r.account_id, r.external_refund_id, r.external_order_id, "
            "r.external_item_id, r.item_title, r.buy_num, r.refund_fee, "
            "r.order_status, r.refund_status, r.refund_status_desc, "
            "r.common_refund_status, r.refund_reason, r.cs_status, "
            "r.buyer_nick, r.refund_create_time, r.last_synced_time, "
            "a.nickname AS account_nickname "
            "FROM xianyu_refund r "
            "LEFT JOIN xianyu_account a ON a.id = r.account_id "
            "WHERE r.tenant_id = :tenant_id "
            "AND r.deleted = 0 "
            "AND a.user_id = :user_id"
        )
        params: Dict[str, Any] = {"tenant_id": tenant_id, "user_id": user_id}

        if account_id and int(account_id) > 0:
            sql += " AND r.account_id = :account_id"
            params["account_id"] = int(account_id)

        if refund_status and str(refund_status).strip():
            kw = f"%{str(refund_status).strip()}%"
            sql += (
                " AND (r.refund_status LIKE :kw "
                "OR r.common_refund_status LIKE :kw "
                "OR r.refund_status_desc LIKE :kw)"
            )
            params["kw"] = kw

        if days_int > 0:
            sql += " AND r.refund_create_time >= DATE_SUB(NOW(), INTERVAL :days DAY)"
            params["days"] = days_int

        sql += " ORDER BY r.refund_create_time DESC, r.id DESC LIMIT :limit"
        params["limit"] = limit
        rows = (await db.execute(text(sql), params)).mappings().all()

        # 兜底：若严格匹配无结果，回退到 tenant_id 范围（不限定 user_id）
        fallback_reason = ""
        if not rows:
            sql_fb = (
                "SELECT r.id, r.account_id, r.external_refund_id, r.external_order_id, "
                "r.external_item_id, r.item_title, r.buy_num, r.refund_fee, "
                "r.order_status, r.refund_status, r.refund_status_desc, "
                "r.common_refund_status, r.refund_reason, r.cs_status, "
                "r.buyer_nick, r.refund_create_time, r.last_synced_time, "
                "a.nickname AS account_nickname "
                "FROM xianyu_refund r "
                "LEFT JOIN xianyu_account a ON a.id = r.account_id "
                "WHERE r.tenant_id = :tenant_id AND r.deleted = 0"
            )
            params_fb: Dict[str, Any] = {"tenant_id": tenant_id}
            if account_id and int(account_id) > 0:
                sql_fb += " AND r.account_id = :account_id"
                params_fb["account_id"] = int(account_id)
            if refund_status and str(refund_status).strip():
                sql_fb += (
                    " AND (r.refund_status LIKE :kw "
                    "OR r.common_refund_status LIKE :kw "
                    "OR r.refund_status_desc LIKE :kw)"
                )
                params_fb["kw"] = f"%{str(refund_status).strip()}%"
            if days_int > 0:
                sql_fb += " AND r.refund_create_time >= DATE_SUB(NOW(), INTERVAL :days DAY)"
                params_fb["days"] = days_int
            sql_fb += " ORDER BY r.refund_create_time DESC, r.id DESC LIMIT :limit"
            params_fb["limit"] = limit
            rows = (await db.execute(text(sql_fb), params_fb)).mappings().all()
            if rows:
                fallback_reason = (
                    f"按当前用户ID（{user_id}）严格匹配未找到退款，"
                    f"已回退到租户范围查询，共找到 {len(rows)} 条退款记录。"
                )
                logger.info(
                    "list_refunds fallback to tenant scope tenantId=%d userId=%d rowCount=%d",
                    tenant_id, user_id, len(rows),
                )

        refunds = [
            {
                "id": int(row["id"]),
                "accountId": int(row["account_id"] or 0),
                "accountNickname": row["account_nickname"] or "",
                "externalRefundId": row["external_refund_id"] or "",
                "externalOrderId": row["external_order_id"] or "",
                "externalItemId": row["external_item_id"] or "",
                "itemTitle": row["item_title"] or "",
                "buyNum": row["buy_num"] or "",
                "refundFee": str(row["refund_fee"]) if row["refund_fee"] is not None else "",
                "orderStatus": row["order_status"] or "",
                "refundStatus": row["refund_status"] or "",
                "refundStatusDesc": row["refund_status_desc"] or "",
                "commonRefundStatus": row["common_refund_status"] or "",
                "refundReason": row["refund_reason"] or "",
                "csStatus": row["cs_status"] or "",
                "buyerNick": row["buyer_nick"] or "",
                "refundCreateTime": row["refund_create_time"].isoformat() if row["refund_create_time"] else None,
                "lastSyncedTime": row["last_synced_time"].isoformat() if row["last_synced_time"] else None,
            }
            for row in rows
        ]
        result_data: Dict[str, Any] = {
            "refunds": refunds,
            "total": len(refunds),
        }
        if fallback_reason:
            result_data["fallbackReason"] = fallback_reason
        return _ok(result_data)
    except Exception as exc:
        logger.warning(
            "list_refunds failed tenantId=%d errorType=%s",
            tenant_id, type(exc).__name__,
            exc_info=True,
        )
        return _fail("查询退款记录失败，请稍后重试")


async def list_card_groups(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    **_: Any,
) -> ToolResult:
    """查询卡密/货源库分组列表。

    user_id 字段在 CardGroup 实体上为 nullable=True：Java 侧创建的分组可能 user_id=NULL，
    Python 侧创建的分组会填充 user_id。因此查询条件需兼容两种情况：
    - 当前用户创建的分组（user_id = :uid）
    - 没有归属用户的分组（user_id IS NULL）—— 通常是 Java 侧创建的历史数据
    """
    try:
        # 用原生 SQL 表达 OR 条件，避免 SQLAlchemy 在 nullable 列上的隐式 AND 行为
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
                CardGroup.deleted == 0,
                # 兼容 user_id=NULL 的历史数据：当前用户的 + 无归属的
                ((CardGroup.user_id == user_id) | (CardGroup.user_id.is_(None))),
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
            exc_info=True,
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
            exc_info=True,
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
            "SELECT id, account_id, task_type, task_name, cron_expression, enabled, "
            "last_run_time, next_run_time, last_status "
            "FROM scheduled_task "
            "WHERE tenant_id = :tenant_id AND deleted = 0 "
            "ORDER BY id DESC LIMIT 50"
        )
        rows = (await db.execute(text(sql), {"tenant_id": tenant_id})).mappings().all()
        tasks = [
            {
                "id": int(row["id"]),
                "accountId": int(row["account_id"] or 0),
                "taskType": row["task_type"] or "",
                "taskName": row["task_name"] or "",
                "cronExpr": row["cron_expression"] or "",
                "enabled": bool(row["enabled"]),
                "lastStatus": row["last_status"] or "",
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
            exc_info=True,
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
            "LEFT JOIN xianyu_account a ON a.id = r.account_id "
            "WHERE r.tenant_id = :tenant_id "
            "AND r.deleted = 0 AND (a.deleted = 0 OR a.deleted IS NULL)"
        )
        params: Dict[str, Any] = {"tenant_id": tenant_id}
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
            exc_info=True,
        )
        return _fail("查询自动回复规则失败，请稍后重试")


async def get_token_balance(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    **_: Any,
) -> ToolResult:
    """查询当前用户的 Token 余额。

    直接查询 sys_user.token_balance 字段，避免依赖 Java 端的 /api/ai-billing/balance 接口
    （该接口需要 JWT 鉴权，不适用于内部 AI 客服工具调用场景）。
    """
    try:
        row = (await db.execute(
            text(
                "SELECT id, username, token_balance, vip_level "
                "FROM sys_user WHERE id = :uid AND deleted = 0"
            ),
            {"uid": user_id},
        )).mappings().first()

        if not row:
            return _fail(f"未找到用户（userId={user_id}），可能已被删除")

        balance = int(row.get("token_balance") or 0)
        vip_level = int(row.get("vip_level") or 0)
        username = row.get("username") or ""

        # VIP 等级文案
        vip_label = {0: "普通用户", 1: "VIP", 2: "SVP"}.get(vip_level, f"VIP{vip_level}")

        # 查询通用模型单次扣费数（按 VIP 等级）
        per_call_tokens = (await db.execute(
            text(
                "SELECT tokens_per_call FROM ai_model_tier_price "
                "WHERE module_key = 'model-config-general' AND vip_level = :lvl "
                "LIMIT 1"
            ),
            {"lvl": vip_level},
        )).scalar()
        if not per_call_tokens:
            # 回退到默认配置
            per_call_tokens = (await db.execute(
                text(
                    "SELECT tokens_per_call FROM ai_model_price_config "
                    "WHERE module_key = 'model-config-general' AND enabled = 1 LIMIT 1"
                ),
            )).scalar() or 3

        per_call_tokens = int(per_call_tokens)
        # 估算还能调用多少次
        remaining_calls = balance // per_call_tokens if per_call_tokens > 0 else 0

        return _ok({
            "userId": int(row.get("id")),
            "username": username,
            "balance": balance,
            "vipLevel": vip_level,
            "vipLabel": vip_label,
            "perCallTokens": per_call_tokens,
            "remainingCalls": remaining_calls,
            "message": (
                f"当前 Token 余额：{balance}，{vip_label}，"
                f"通用模型每次扣 {per_call_tokens} Token，"
                f"约可调用 {remaining_calls} 次"
            ),
        })
    except Exception as exc:
        logger.warning(
            "get_token_balance failed tenantId=%d userId=%d errorType=%s",
            tenant_id, user_id, type(exc).__name__,
            exc_info=True,
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
        # 商品总数（注意：xianyu_goods 和 xianyu_account 都有 status 字段，必须用表别名避免歧义）
        goods_sql = (
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN g.status = 1 THEN 1 ELSE 0 END) AS on_shelf "
            "FROM xianyu_goods g "
            "LEFT JOIN xianyu_account a ON a.id = g.account_id "
            "WHERE g.tenant_id = :tenant_id "
            "AND g.deleted = 0 AND (a.deleted = 0 OR a.deleted IS NULL)"
        )
        goods_row = (await db.execute(text(goods_sql), {"tenant_id": tenant_id})).mappings().first()

        # 今日订单金额与待发货数（按订单实际创建时间过滤，与 list_orders 保持一致）
        orders_sql = (
            "SELECT COUNT(*) AS total_orders, "
            "SUM(CASE WHEN o.order_status = 2 THEN 1 ELSE 0 END) AS pending_ship, "
            "SUM(CASE WHEN o.order_status IN (1,2,3,4) THEN CAST(o.total_amount AS DECIMAL(12,2)) ELSE 0 END) AS today_amount "
            "FROM xianyu_trade_order o "
            "LEFT JOIN xianyu_account a ON a.id = o.account_id "
            "WHERE o.tenant_id = :tenant_id "
            "AND o.deleted = 0 AND (a.deleted = 0 OR a.deleted IS NULL) "
            "AND DATE(o.create_time) = CURDATE()"
        )
        orders_row = (await db.execute(text(orders_sql), {"tenant_id": tenant_id})).mappings().first()

        # 发货统计
        delivery_sql = (
            "SELECT "
            "SUM(CASE WHEN r.delivery_status = 'success' THEN 1 ELSE 0 END) AS success, "
            "SUM(CASE WHEN r.delivery_status = 'failed' THEN 1 ELSE 0 END) AS failed, "
            "SUM(CASE WHEN r.delivery_status = 'pending' THEN 1 ELSE 0 END) AS pending "
            "FROM delivery_record r "
            "LEFT JOIN xianyu_account a ON a.id = r.account_id "
            "WHERE r.tenant_id = :tenant_id "
            "AND r.deleted = 0 AND (a.deleted = 0 OR a.deleted IS NULL) "
            "AND DATE(r.created_time) = CURDATE()"
        )
        delivery_row = (await db.execute(text(delivery_sql), {"tenant_id": tenant_id})).mappings().first()

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
            exc_info=True,
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
            "LEFT JOIN xianyu_account a ON a.id = r.account_id "
            "WHERE r.tenant_id = :tenant_id "
            "AND r.id = :record_id AND r.deleted = 0"
        )
        row = (await db.execute(text(sql), {"tenant_id": tenant_id, "record_id": record_id})).mappings().first()
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
            exc_info=True,
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
            "WHERE tenant_id = :tenant_id "
            "AND id = :task_id AND deleted = 0"
        )
        row = (await db.execute(text(sql), {"tenant_id": tenant_id, "task_id": task_id})).mappings().first()
        if row is None:
            return _fail("定时任务不存在或无权访问")

        new_enabled = 1 if enabled else 0
        await db.execute(
            text("UPDATE scheduled_task SET enabled = :enabled, updated_time = NOW() WHERE id = :task_id"),
            {"enabled": new_enabled, "task_id": task_id},
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
            exc_info=True,
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
            "LEFT JOIN xianyu_account a ON a.id = r.account_id "
            "WHERE r.tenant_id = :tenant_id "
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
            exc_info=True,
        )
        await db.rollback()
        return _fail("切换自动回复规则状态失败，请稍后重试")


# ============================================================
# 商品管理增强类工具
# ============================================================


async def get_product_summary(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    account_id: Optional[int] = None,
    **_: Any,
) -> ToolResult:
    """商品汇总统计：总数、在售、下架/草稿、总曝光、总浏览、总想要。

    当用户问"我总共有多少商品""商品总数""商品统计"时调用此工具。
    可选 accountId 限定单账号；不传则汇总用户名下全部账号。

    状态口径与 Java XianyuGoodsMapper.summaryByStatus 完全对齐：
    - DB status=1 在售，需额外排除"商机发掘"分类与 opp: 开头的草稿商品
    - DB status=0 下架，或属于商机发掘分类，或 external_goods_id 为空/以 opp: 开头 → 归为下架/草稿
    - DB 不存在 status=2（已售）语义，已售商品通过 sold_price 字段判断，本工具不统计
    """
    try:
        # 与 Java XianyuGoodsMapper.summaryByStatus 对齐：onSale / offShelfOrDraft 二分类
        sql = (
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN g.status = 1 "
            "    AND (g.category IS NULL OR g.category != '商机发掘') "
            "    AND g.external_goods_id IS NOT NULL AND g.external_goods_id != '' "
            "    AND g.external_goods_id NOT LIKE 'opp:%' "
            "    THEN 1 ELSE 0 END) AS on_shelf, "
            "SUM(CASE WHEN g.status = 0 "
            "    OR g.category = '商机发掘' "
            "    OR g.external_goods_id IS NULL "
            "    OR g.external_goods_id = '' "
            "    OR g.external_goods_id LIKE 'opp:%' "
            "    THEN 1 ELSE 0 END) AS off_shelf, "
            "COALESCE(SUM(g.exposure_count), 0) AS total_exposure, "
            "COALESCE(SUM(g.view_count), 0) AS total_view, "
            "COALESCE(SUM(g.want_count), 0) AS total_want "
            "FROM xianyu_goods g "
            "LEFT JOIN xianyu_account a ON a.id = g.account_id "
            "WHERE g.tenant_id = :tenant_id "
            "AND g.deleted = 0 AND (a.deleted = 0 OR a.deleted IS NULL)"
        )
        params: Dict[str, Any] = {"tenant_id": tenant_id}
        if account_id and int(account_id) > 0:
            sql += " AND g.account_id = :account_id"
            params["account_id"] = int(account_id)
        row = (await db.execute(text(sql), params)).mappings().first()
        if not row:
            return _ok({"total": 0, "onShelf": 0, "offShelf": 0,
                        "totalExposure": 0, "totalView": 0, "totalWant": 0,
                        "accountId": int(account_id) if account_id else None})
        total = int(row["total"] or 0)
        on_shelf = int(row["on_shelf"] or 0)
        off_shelf = int(row["off_shelf"] or 0)
        # 兜底：若 status 字段出现非 0/1 的脏数据（如 NULL 或 2），归到 off_shelf
        if on_shelf + off_shelf < total:
            off_shelf = total - on_shelf
        return _ok({
            "total": total,
            "onShelf": on_shelf,
            "offShelf": off_shelf,
            # 已售商品通过 sold_price 字段判断，本工具不单独统计 sold_out，避免与前端状态码混淆
            "totalExposure": int(row["total_exposure"] or 0),
            "totalView": int(row["total_view"] or 0),
            "totalWant": int(row["total_want"] or 0),
            "accountId": int(account_id) if account_id else None,
        })
    except Exception as exc:
        logger.warning(
            "get_product_summary failed tenantId=%d errorType=%s",
            tenant_id, type(exc).__name__,
            exc_info=True,
        )
        return _fail("查询商品汇总失败，请稍后重试")


async def delete_product(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    goods_id: int,
    **_: Any,
) -> ToolResult:
    """软删除商品（仅落库 deleted=1，不直接调用闲鱼下架接口）。

    安全约束：
    - 校验商品归属于当前用户
    - 仅置 deleted=1，不真实下架闲鱼平台商品
    - 用户需在前端手动同步下架到闲鱼平台
    """
    goods_id = _safe_int(goods_id)
    if goods_id <= 0:
        return _fail("goodsId 必须为正整数")
    try:
        # 校验归属
        row = (await db.execute(
            select(XianyuGoods.id, XianyuGoods.user_id, XianyuGoods.title).where(
                XianyuGoods.tenant_id == tenant_id,
                XianyuGoods.id == goods_id,
                XianyuGoods.deleted == 0,
            )
        )).one_or_none()
        if row is None:
            return _fail("商品不存在或无权访问")
        goods_user_id = int(row[1] or 0)
        if goods_user_id != 0 and goods_user_id != user_id:
            return _fail("商品不存在或无权访问")
        title = row[2] or ""

        # 软删除
        await db.execute(
            text("UPDATE xianyu_goods SET deleted = 1, updated_time = NOW() "
                 "WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": goods_id, "tenant_id": tenant_id},
        )
        await db.commit()
        logger.info(
            "delete_product ok tenantId=%d userId=%d goodsId=%d",
            tenant_id, user_id, goods_id,
        )
        return _ok({
            "goodsId": goods_id,
            "title": title,
            "message": f"已删除商品「{title}」（仅本地记录，需在前端同步下架到闲鱼平台）",
        })
    except Exception as exc:
        logger.warning(
            "delete_product failed tenantId=%d goodsId=%d errorType=%s",
            tenant_id, goods_id, type(exc).__name__,
            exc_info=True,
        )
        await db.rollback()
        return _fail("删除商品失败，请稍后重试")


async def toggle_product_status(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    goods_id: int,
    on_shelf: bool,
    **_: Any,
) -> ToolResult:
    """商品上下架（仅更新本地 status 字段，不直接调用闲鱼接口）。

    on_shelf=true 上架（status=1），on_shelf=false 下架（status=0）。
    用户需在前端同步状态到闲鱼平台。
    """
    goods_id = _safe_int(goods_id)
    if goods_id <= 0:
        return _fail("goodsId 必须为正整数")
    target_status = 1 if bool(on_shelf) else 0
    try:
        row = (await db.execute(
            select(XianyuGoods.id, XianyuGoods.user_id, XianyuGoods.title, XianyuGoods.status).where(
                XianyuGoods.tenant_id == tenant_id,
                XianyuGoods.id == goods_id,
                XianyuGoods.deleted == 0,
            )
        )).one_or_none()
        if row is None:
            return _fail("商品不存在或无权访问")
        goods_user_id = int(row[1] or 0)
        if goods_user_id != 0 and goods_user_id != user_id:
            return _fail("商品不存在或无权访问")
        title = row[2] or ""
        current_status = int(row[3] or 0)
        if current_status == 2:
            return _fail("商品已售出，无法上下架")

        await db.execute(
            text("UPDATE xianyu_goods SET status = :status, updated_time = NOW() "
                 "WHERE id = :id AND tenant_id = :tenant_id"),
            {"status": target_status, "id": goods_id, "tenant_id": tenant_id},
        )
        await db.commit()
        action = "上架" if target_status == 1 else "下架"
        logger.info(
            "toggle_product_status ok tenantId=%d goodsId=%d status=%d",
            tenant_id, goods_id, target_status,
        )
        return _ok({
            "goodsId": goods_id,
            "title": title,
            "status": target_status,
            "message": f"已{action}商品「{title}」（需在前端同步到闲鱼平台）",
        })
    except Exception as exc:
        logger.warning(
            "toggle_product_status failed tenantId=%d goodsId=%d errorType=%s",
            tenant_id, goods_id, type(exc).__name__,
            exc_info=True,
        )
        await db.rollback()
        return _fail("切换商品上下架状态失败，请稍后重试")


async def search_goods_online(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    keyword: str,
    account_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 10,
    mode: str = "auto",
    **_: Any,
) -> ToolResult:
    """搜索闲鱼商品（复用 misc.py 的搜索执行器，返回商品列表）。

    mode: fast=快速直调MTOP, slow=浏览器拦截, auto=自动降级（默认）
    account_id 提供时使用其 Cookie，否则用租户内第一个有效 Cookie。
    """
    keyword = _safe_str(keyword)
    if not keyword:
        return _fail("搜索关键词不能为空")
    page = max(1, _safe_int(page, default=1))
    page_size = max(1, min(_safe_int(page_size, default=10), 30))
    mode = _safe_str(mode) or "auto"
    if mode not in ("fast", "slow", "auto"):
        mode = "auto"

    try:
        # 重要修复：cookie 实际存储在 xianyu_account_auth.encrypted_cookie 字段（加密），
        # XianyuAccount 实体没有 cookie 字段，直接 select(XianyuAccount.cookie) 会抛 AttributeError。
        # 复用 misc.py 的 _resolve_account_cookie 函数，与商机发掘页面真实链路完全一致：
        # 1. 从 XianyuAccountAuth 读取 encrypted_cookie
        # 2. 通过 decrypt_cookie_if_needed 解密
        # 3. 提取 _m_h5_tk token 用于 MTOP 签名
        from ..services.xianyu_goods_sync import _resolve_account_cookie
        current_user = {"tenant_id": tenant_id, "user_id": user_id}
        cookie_str, cookie_err, resolved_account_id = await _resolve_account_cookie(
            db, tenant_id, account_id, current_user,
        )
        if not cookie_str or cookie_err:
            # cookie 失效或账号未登录，给出明确指引
            return _fail(cookie_err or "未找到可用的账号 Cookie，请先在闲鱼账号页面登录后再试")
        used_account_id = int(resolved_account_id) if resolved_account_id else None

        # 校验 cookie_status=1（账号 Cookie 已验证有效），
        # 否则闲鱼搜索 API 会因为 Cookie 失效返回风控/登录跳转
        if used_account_id:
            runtime_row = (await db.execute(
                select(XianyuAccountRuntime.cookie_status).where(
                    XianyuAccountRuntime.tenant_id == tenant_id,
                    XianyuAccountRuntime.account_id == used_account_id,
                    XianyuAccountRuntime.deleted == 0,
                )
            )).scalar()
            cookie_status_int = int(runtime_row) if runtime_row is not None else -1
            if cookie_status_int != 1:
                return _fail(
                    f"账号 Cookie 状态为「{_humanize_cookie(cookie_status_int)}」，无法执行搜索。"
                    "请先在闲鱼账号页面恢复 Cookie 后再试。"
                )

        # 复用 misc.py 的搜索执行器
        # 重要：_execute_search_with_mode 是同步函数（内部调用同步 httpx + crawler-service HTTP），
        # 直接 await 会触发 "TypeError: object dict can't be used in 'await' expression"。
        # 必须用 asyncio.to_thread 包装，与 misc.py 路由层调用方式保持一致。
        import asyncio as _asyncio
        from ..api.v1.routes.misc import _execute_search_with_mode, SearchError
        try:
            result = await _asyncio.to_thread(
                _execute_search_with_mode,
                keyword, page, page_size, tenant_id, cookie_str, mode,
            )
        except SearchError as se:
            # 把 misc.py 的结构化搜索错误翻译成 AI 可读的失败原因
            return _fail(se.message or "商品搜索暂时不可用，请稍后重试")
        items = result.get("items") or []
        # 精简字段，避免返回过大
        simplified = []
        for it in items[:page_size]:
            simplified.append({
                "itemId": it.get("itemId") or "",
                "title": it.get("title") or "",
                "price": it.get("price") or "",
                "imageUrl": it.get("imageUrl") or "",
                "seller": it.get("seller") or it.get("userNickName") or "",
                "area": it.get("area") or "",
                "link": it.get("link") or "",
            })
        return _ok({
            "keyword": keyword,
            "page": page,
            "pageSize": page_size,
            "searchMode": result.get("searchMode") or mode,
            "total": len(simplified),
            "items": simplified,
            "accountId": used_account_id,
        })
    except Exception as exc:
        logger.warning(
            "search_goods_online failed tenantId=%d keyword=%s errorType=%s exc=%s",
            tenant_id, keyword, type(exc).__name__, exc,
            exc_info=True,
        )
        # 给 AI 一个带简短错误类型的失败原因，便于它建议用户下一步（如换号/恢复 Cookie）
        err_brief = f"{type(exc).__name__}: {exc}"
        if len(err_brief) > 200:
            err_brief = err_brief[:200]
        return _fail(f"搜索商品失败：{err_brief}")


# ============================================================
# 系统功能清单工具（自主学习能力基础）
# ============================================================

# 系统功能清单（与 apps/user-web/src/data/nav.js 同步）
# 维护原则：当前台新增功能页面时，必须同步更新本清单
# 同时由定时任务（ai_cs_feature_sync.py）每天自动扫描 nav.js 变化并写入 ai_cs_knowledge 表
SYSTEM_FEATURES: List[Dict[str, Any]] = [
    {"category": "概览", "features": [
        {"key": "dashboard", "name": "导航面板", "desc": "查看系统所有功能入口的快速导航"},
        {"key": "data", "name": "数据面板", "desc": "查看商品、订单、销售额等核心数据概览"},
    ]},
    {"category": "账号", "features": [
        {"key": "accounts", "name": "闲鱼账号", "desc": "管理闲鱼账号：扫码登录、Cookie 状态、在线状态、会员等级"},
        {"key": "orders", "name": "订单管理", "desc": "查询订单列表、订单详情、订单状态流转"},
        {"key": "refunds", "name": "退款管理", "desc": "查询退款记录、退款详情、处理退款申请"},
        {"key": "rates", "name": "评价管理", "desc": "查询买家评价、自动评价配置"},
        {"key": "fish-shop-data", "name": "鱼小铺数据分析", "desc": "鱼小铺商品数据分析、销售对比、数据罗盘"},
    ]},
    {"category": "商品", "features": [
        {"key": "products", "name": "商品管理", "desc": "管理商品列表、上下架、删除、同步"},
        {"key": "product-publish", "name": "商品发布", "desc": "发布新商品到闲鱼平台（需生成 AI 封面图）"},
        {"key": "opportunities", "name": "商机发掘", "desc": "搜索闲鱼商品、分析同行销量、发掘商机"},
        {"key": "goods-data", "name": "商品数据分析", "desc": "分析商品曝光、浏览、想要等数据"},
    ]},
    {"category": "消息", "features": [
        {"key": "messages", "name": "在线消息", "desc": "查看买家消息、在线回复、会话管理"},
        {"key": "auto-reply", "name": "自动回复", "desc": "配置自动回复规则、关键词触发"},
        {"key": "settings-ai-cs", "name": "AI客服配置", "desc": "配置 AI 客服人设、知识库、回复规则"},
        {"key": "settings-kb", "name": "客服知识库", "desc": "管理客服知识库分类与对话内容"},
    ]},
    {"category": "自动发货", "features": [
        {"key": "auto-delivery", "name": "自动发货", "desc": "配置自动发货规则：触发条件、发货内容、发货时机"},
        {"key": "delivery-source-library", "name": "货源库", "desc": "管理货源库分组、卡密/文本货源"},
        {"key": "card-warehouse", "name": "卡密仓库", "desc": "管理卡密分组、批量导入卡密、查看卡密使用情况"},
        {"key": "delivery-statement", "name": "发货声明", "desc": "配置发货声明文案，发货时自动附带"},
        {"key": "delivery-records", "name": "发货记录", "desc": "查询发货记录、发货状态、失败原因"},
    ]},
    {"category": "分销管理", "features": [
        {"key": "delivery-mall", "name": "货源商城", "desc": "浏览分销货源商城"},
        {"key": "supply-center", "name": "供货中心", "desc": "供货中心（维护中）"},
        {"key": "platform-connect", "name": "平台对接", "desc": "平台对接（维护中）"},
    ]},
    {"category": "工作流", "features": [
        {"key": "workflow", "name": "工作流", "desc": "管理工作流：触发条件、执行动作、测试运行"},
        {"key": "workflow-tasks", "name": "工作流任务", "desc": "查看工作流执行任务记录"},
        {"key": "workflow-drafts", "name": "商品草稿箱", "desc": "管理工作流生成的商品草稿"},
        {"key": "workflow-image-records", "name": "图片生成记录", "desc": "查看 AI 生图记录、生图结果"},
    ]},
    {"category": "营销增长", "features": [
        {"key": "growth-partner", "name": "增长合伙人", "desc": "增长合伙人（维护中）"},
        {"key": "invite-poster", "name": "邀请海报", "desc": "邀请海报（维护中）"},
    ]},
    {"category": "系统", "features": [
        {"key": "scheduled-tasks", "name": "定时任务", "desc": "管理定时任务：商品同步、数据同步等"},
        {"key": "settings-notify", "name": "通知设置", "desc": "配置通知方式：微信、邮件、站内信"},
        {"key": "slider-solve-records", "name": "滑块求解", "desc": "查看滑块求解记录、求解状态"},
        {"key": "api-slider-solve", "name": "API滑块求解", "desc": "通过 API 调用滑块求解服务"},
        {"key": "logs", "name": "操作日志", "desc": "查看系统操作日志"},
        {"key": "feedback", "name": "反馈建议", "desc": "提交反馈或建议"},
        {"key": "settings-about", "name": "关于我们", "desc": "查看系统版本、关于信息"},
    ]},
]


async def list_system_features(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    category: Optional[str] = None,
    **_: Any,
) -> ToolResult:
    """查询系统所有功能页面清单（自主学习能力基础）。

    当用户问"系统有什么功能""能帮我做什么""有哪些页面"时调用此工具。
    返回与前端 nav.js 同步的功能清单，让 AI 客服能准确告知用户系统能力边界。
    可选 category 参数限定单分类；不传则返回全部 9 个分类。
    """
    try:
        if category and category.strip():
            cat = category.strip()
            filtered = [c for c in SYSTEM_FEATURES if c["category"] == cat or c["category"].startswith(cat)]
            if not filtered:
                return _ok({
                    "categories": [],
                    "totalCategories": 0,
                    "totalFeatures": 0,
                    "message": f"未找到分类「{cat}」，当前共有 {len(SYSTEM_FEATURES)} 个分类",
                })
            return _ok({
                "categories": filtered,
                "totalCategories": len(filtered),
                "totalFeatures": sum(len(c["features"]) for c in filtered),
            })
        # 全量返回
        return _ok({
            "categories": SYSTEM_FEATURES,
            "totalCategories": len(SYSTEM_FEATURES),
            "totalFeatures": sum(len(c["features"]) for c in SYSTEM_FEATURES),
            "hint": "系统功能清单已与前台 nav.js 同步，每日由定时任务自动更新知识库",
        })
    except Exception as exc:
        logger.warning(
            "list_system_features failed tenantId=%d errorType=%s",
            tenant_id, type(exc).__name__,
            exc_info=True,
        )
        return _fail("查询系统功能清单失败，请稍后重试")


# ============================================================
# 消息类工具
# ============================================================


async def list_recent_conversations(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    account_id: Optional[int] = None,
    unread_only: bool = False,
    limit: int = 10,
    **_: Any,
) -> ToolResult:
    """查询最近会话列表（含买家昵称、商品、未读数、最后消息）。

    当用户问"在线消息怎么样""最近有谁找我""未读消息"时调用此工具。
    """
    limit = max(1, min(int(limit or 10), 50))
    try:
        # 单表查询：会话查询不依赖账号是否被软删除，账号被删除时会话记录仍应可见
        sql = (
            "SELECT c.id, c.account_id, c.external_buyer_id, c.buyer_name, "
            "c.goods_id, c.goods_title, c.status, c.unread_count, "
            "c.last_message_time, c.last_message_content, "
            "c.auto_reply_paused, c.last_manual_reply_at, c.last_auto_reply_at "
            "FROM xianyu_conversation c "
            "WHERE c.tenant_id = :tenant_id "
            "AND c.deleted = 0"
        )
        params: Dict[str, Any] = {"tenant_id": tenant_id}
        if account_id and int(account_id) > 0:
            sql += " AND c.account_id = :account_id"
            params["account_id"] = int(account_id)
        if unread_only:
            sql += " AND c.unread_count > 0"
        # MySQL 不支持 NULLS LAST 语法，用 IS NULL 排序实现：非 NULL 优先，再按时间倒序
        sql += " ORDER BY c.last_message_time IS NULL, c.last_message_time DESC, c.id DESC LIMIT :limit"
        params["limit"] = limit
        rows = (await db.execute(text(sql), params)).mappings().all()
        convs = []
        for row in rows:
            convs.append({
                "id": int(row["id"]),
                "accountId": int(row["account_id"] or 0),
                "buyerName": row["buyer_name"] or "",
                "buyerId": row["external_buyer_id"] or "",
                "goodsId": row["goods_id"] or "",
                "goodsTitle": row["goods_title"] or "",
                "status": int(row["status"] or 0),
                "unreadCount": int(row["unread_count"] or 0),
                "lastMessageTime": row["last_message_time"].isoformat() if row["last_message_time"] else None,
                "lastMessageContent": (row["last_message_content"] or "")[:200],
                "autoReplyPaused": int(row["auto_reply_paused"] or 0) == 1,
            })
        # 汇总未读
        total_unread = sum(c["unreadCount"] for c in convs)
        return _ok({
            "conversations": convs,
            "total": len(convs),
            "totalUnread": total_unread,
        })
    except Exception as exc:
        logger.warning(
            "list_recent_conversations failed tenantId=%d errorType=%s",
            tenant_id, type(exc).__name__,
            exc_info=True,
        )
        return _fail("查询最近会话失败，请稍后重试")


async def reply_buyer_message(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    account_id: int,
    conversation_id: int,
    message: str,
    **_: Any,
) -> ToolResult:
    """回复买家消息（复用 misc.py 的 websocket_send_message 发送逻辑）。

    会暂停该会话的自动回复 1 分钟，避免 AI 抢答。
    """
    account_id = _safe_int(account_id)
    conversation_id = _safe_int(conversation_id)
    message = _safe_str(message)
    if account_id <= 0:
        return _fail("accountId 必须为正整数")
    if conversation_id <= 0:
        return _fail("conversationId 必须为正整数")
    if not message:
        return _fail("回复内容不能为空")
    if len(message) > 500:
        return _fail("回复内容过长（最多 500 字）")

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

        # 校验会话归属，并取 to_id（external_buyer_id）
        conv_row = (await db.execute(
            text("SELECT id, external_buyer_id, peer_external_uid, peer_key, session_id "
                 "FROM xianyu_conversation "
                 "WHERE tenant_id = :tenant_id AND account_id = :account_id "
                 "AND id = :id AND deleted = 0"),
            {"tenant_id": tenant_id, "account_id": account_id, "id": conversation_id},
        )).mappings().first()
        if conv_row is None:
            return _fail("会话不存在或无权访问")

        to_id = conv_row["external_buyer_id"] or conv_row["peer_external_uid"] or ""
        session_id = conv_row["session_id"] or str(conversation_id)
        if not to_id:
            return _fail("无法解析买家 ID，请稍后重试")

        # 复用 misc.py 的 websocket_send_message，构造 mock current_user
        from ..api.v1.routes.misc import websocket_send_message
        mock_current_user = {"tenant_id": tenant_id}
        # 优先用 session_id 作为 cid（WS 协议层会话ID），兜底用 conversation_id
        cid = session_id or str(conversation_id)
        result = await websocket_send_message(
            data={
                "accountId": account_id,
                "cid": cid,
                "toId": to_id,
                "text": message,
            },
            db=db,
            current_user=mock_current_user,
        )

        # 解析 ResultObject
        # ResultObject 通常形如 {code, msg, data}，code=200 表示成功
        result_data = result if isinstance(result, dict) else {}
        code = result_data.get("code")
        if code == 200:
            logger.info(
                "reply_buyer_message ok tenantId=%d userId=%d accountId=%d convId=%d",
                tenant_id, user_id, account_id, conversation_id,
            )
            return _ok({
                "accountId": account_id,
                "conversationId": conversation_id,
                "buyerId": to_id,
                "content": message,
                "message": "消息已发送给买家，自动回复已暂停 1 分钟",
            })
        else:
            err_msg = result_data.get("msg") or "消息发送失败"
            logger.warning(
                "reply_buyer_message send failed tenantId=%d convId=%d code=%s msg=%s",
                tenant_id, conversation_id, code, err_msg,
            )
            return _fail(err_msg)
    except Exception as exc:
        logger.warning(
            "reply_buyer_message failed tenantId=%d convId=%d errorType=%s",
            tenant_id, conversation_id, type(exc).__name__,
            exc_info=True,
        )
        await db.rollback()
        return _fail("回复买家消息失败，请稍后重试")


# ============================================================
# 鱼小铺数据分析工具
# ============================================================


async def get_fish_shop_data(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    account_id: Optional[int] = None,
    date_type: str = "recent7d",
    **_: Any,
) -> ToolResult:
    """查询鱼小铺数据分析（复用 fish_shop_datacompass.fetch_seller_summary）。

    date_type: recent1d=近1天, recent7d=近7天, recent30d=近30天
    account_id 不传则聚合用户名下全部鱼小铺账号。
    """
    date_type = _safe_str(date_type) or "recent7d"
    if date_type not in ("recent1d", "recent7d", "recent30d"):
        date_type = "recent7d"
    acct_id = None
    if account_id and int(account_id) > 0:
        # 校验归属
        owner_row = (await db.execute(
            select(XianyuAccount.user_id, XianyuAccount.fish_shop_user).where(
                XianyuAccount.tenant_id == tenant_id,
                XianyuAccount.id == int(account_id),
                XianyuAccount.deleted == 0,
            )
        )).one_or_none()
        if owner_row is None or int(owner_row[0] or 0) != user_id:
            return _fail("账号不存在或无权访问")
        if int(owner_row[1] or 0) != 1:
            return _fail("该账号不是鱼小铺账号，无法查询数据罗盘")
        acct_id = int(account_id)

    try:
        from .fish_shop_datacompass import fetch_seller_summary
        raw = await fetch_seller_summary(
            db=db,
            tenant_id=tenant_id,
            account_id=acct_id,
            date_type=date_type,
            user_id=user_id,
        )
        # 精简 banners，提取关键指标
        banners = raw.get("banners") or {}
        key_metrics = {}
        # 关键字段中文化映射
        metric_map = {
            "payAmt": "成交金额",
            "payOrdCnt": "支付订单数",
            "aov": "客单价",
            "showPv": "曝光次数",
            "showUv": "曝光人数",
            "ipv": "商品浏览量",
            "ipvUv": "商品浏览人数",
            "vstPv": "店铺访问次数",
            "vstUv": "店铺访问人数",
            "chatUv": "咨询人数",
            "onlCnt": "在线商品数",
            "rfdAmt": "退款金额",
            "rfdOrdCnt": "退款订单数",
            "rptOrdCnt": "复购订单数",
            "fstByrPayAmt": "新买家成交金额",
            "rptByrPayAmt": "复购买家成交金额",
        }
        for key, label in metric_map.items():
            b = banners.get(key)
            if not b:
                continue
            key_metrics[key] = {
                "label": label,
                "current": b.get("dataStr") or b.get("data"),
                "previous": b.get("lastDataStr") or b.get("lastData"),
                "ratio": b.get("ratioFormat") or b.get("ratio"),
                "cycle": b.get("cycle") or "",
            }
        return _ok({
            "mode": raw.get("mode") or ("single" if acct_id else "all"),
            "dateType": date_type,
            "realDateRange": raw.get("realDateRange") or [],
            "metrics": key_metrics,
            "accounts": raw.get("accounts") or {},
            "hasGraph": bool(raw.get("graph")),
            "graphPoints": len(raw.get("graph") or []),
        })
    except Exception as exc:
        logger.warning(
            "get_fish_shop_data failed tenantId=%d errorType=%s",
            tenant_id, type(exc).__name__,
            exc_info=True,
        )
        return _fail("查询鱼小铺数据分析失败，请稍后重试")


async def get_sales_comparison(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    account_id: Optional[int] = None,
    **_: Any,
) -> ToolResult:
    """查询今日与昨日销售对比：订单数、成交金额、新增退款数。

    当用户问"今天比昨天多卖多少钱""今日销售怎么样"时调用此工具。
    数据来自 xianyu_trade_order 表，按 pay_time 日期聚合。
    """
    try:
        sql = (
            "SELECT "
            "DATE(o.pay_time) AS d, "
            "COUNT(*) AS order_cnt, "
            "COALESCE(SUM(CASE WHEN o.order_status IN (1,2,3,4) "
            "THEN CAST(o.total_amount AS DECIMAL(12,2)) ELSE 0 END), 0) AS pay_amt, "
            "SUM(CASE WHEN o.order_status = 2 THEN 1 ELSE 0 END) AS pending_ship "
            "FROM xianyu_trade_order o "
            "LEFT JOIN xianyu_account a ON a.id = o.account_id "
            "WHERE o.tenant_id = :tenant_id "
            "AND o.deleted = 0 AND (a.deleted = 0 OR a.deleted IS NULL) "
            "AND o.pay_time IS NOT NULL "
            "AND DATE(o.pay_time) IN (CURDATE(), DATE_SUB(CURDATE(), INTERVAL 1 DAY))"
        )
        params: Dict[str, Any] = {"tenant_id": tenant_id}
        if account_id and int(account_id) > 0:
            sql += " AND o.account_id = :account_id"
            params["account_id"] = int(account_id)
        sql += " GROUP BY DATE(o.pay_time)"
        rows = (await db.execute(text(sql), params)).mappings().all()
        today_data = {"orders": 0, "amount": 0.0, "pendingShip": 0}
        yesterday_data = {"orders": 0, "amount": 0.0, "pendingShip": 0}
        for row in rows:
            d = row["d"]
            order_cnt = int(row["order_cnt"] or 0)
            pay_amt = float(row["pay_amt"] or 0)
            pending = int(row["pending_ship"] or 0)
            # 比较 d 与今天/昨天
            try:
                from datetime import date as _date, timedelta as _td
                today = _date.today()
                yesterday = today - _td(days=1)
                if d == today:
                    today_data = {"orders": order_cnt, "amount": pay_amt, "pendingShip": pending}
                elif d == yesterday:
                    yesterday_data = {"orders": order_cnt, "amount": pay_amt, "pendingShip": pending}
            except Exception:
                pass

        # 计算差额与增长率
        amt_diff = today_data["amount"] - yesterday_data["amount"]
        if yesterday_data["amount"] > 0:
            amt_growth_pct = round((amt_diff / yesterday_data["amount"]) * 100, 2)
        elif today_data["amount"] > 0:
            amt_growth_pct = 100.0
        else:
            amt_growth_pct = 0.0
        order_diff = today_data["orders"] - yesterday_data["orders"]

        return _ok({
            "today": today_data,
            "yesterday": yesterday_data,
            "amountDiff": round(amt_diff, 2),
            "amountGrowthPct": amt_growth_pct,
            "orderDiff": order_diff,
            "accountId": int(account_id) if account_id else None,
            "message": (
                f"今日成交 {today_data['amount']:.2f} 元（{today_data['orders']} 单），"
                f"昨日成交 {yesterday_data['amount']:.2f} 元（{yesterday_data['orders']} 单），"
                f"{'增加' if amt_diff >= 0 else '减少'} {abs(amt_diff):.2f} 元（{amt_growth_pct:+.2f}%）"
            ),
        })
    except Exception as exc:
        logger.warning(
            "get_sales_comparison failed tenantId=%d errorType=%s",
            tenant_id, type(exc).__name__,
            exc_info=True,
        )
        return _fail("查询销售对比失败，请稍后重试")


# ============================================================
# 配置更新类工具
# ============================================================


async def update_delivery_statement(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    enabled: Optional[bool] = None,
    content: Optional[str] = None,
    **_: Any,
) -> ToolResult:
    """更新发货声明配置（仅落库 delivery_statement 表）。

    enabled=true 启用 / false 禁用；content 声明文案。
    至少传其中一个参数。
    """
    if enabled is None and content is None:
        return _fail("至少需要传 enabled 或 content 中的一个参数")
    try:
        # 查现有配置
        row = (await db.execute(
            text("SELECT id, enabled, content FROM delivery_statement "
                 "WHERE tenant_id = :tenant_id AND deleted = 0 LIMIT 1"),
            {"tenant_id": tenant_id},
        )).mappings().first()

        if row is None:
            # 新建
            new_enabled = 1 if bool(enabled) else 0
            new_content = _safe_str(content) or ""
            await db.execute(
                text("INSERT INTO delivery_statement (tenant_id, enabled, content, scope, "
                     "created_time, updated_time, deleted) "
                     "VALUES (:tenant_id, :enabled, :content, 'all', NOW(), NOW(), 0)"),
                {"tenant_id": tenant_id, "enabled": new_enabled, "content": new_content},
            )
            await db.commit()
            logger.info("update_delivery_statement created tenantId=%d", tenant_id)
            return _ok({
                "enabled": bool(new_enabled),
                "content": new_content,
                "message": "已创建发货声明配置",
            })
        else:
            # 更新
            new_enabled = 1 if bool(enabled) else (0 if enabled is False else int(row["enabled"] or 0))
            new_content = _safe_str(content) if content is not None else (row["content"] or "")
            await db.execute(
                text("UPDATE delivery_statement SET enabled = :enabled, content = :content, "
                     "updated_time = NOW() WHERE id = :id AND tenant_id = :tenant_id"),
                {"enabled": new_enabled, "content": new_content,
                 "id": int(row["id"]), "tenant_id": tenant_id},
            )
            await db.commit()
            logger.info("update_delivery_statement updated tenantId=%d id=%d", tenant_id, int(row["id"]))
            return _ok({
                "enabled": bool(new_enabled),
                "content": new_content,
                "message": "已更新发货声明配置",
            })
    except Exception as exc:
        logger.warning(
            "update_delivery_statement failed tenantId=%d errorType=%s",
            tenant_id, type(exc).__name__,
            exc_info=True,
        )
        await db.rollback()
        return _fail("更新发货声明配置失败，请稍后重试")


async def update_workflow(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    workflow_id: int,
    name: Optional[str] = None,
    description: Optional[str] = None,
    trigger_type: Optional[str] = None,
    status: Optional[str] = None,
    **_: Any,
) -> ToolResult:
    """更新工作流定义的基础信息（name/description/triggerType/status）。

    不支持修改节点与连线（需在前端画布操作）。
    status 可选值：draft/published/disabled。
    """
    workflow_id = _safe_int(workflow_id)
    if workflow_id <= 0:
        return _fail("workflowId 必须为正整数")
    if trigger_type is not None and _safe_str(trigger_type) not in ("manual", "scheduled", "event", ""):
        return _fail("triggerType 仅支持 manual/scheduled/event")
    if status is not None and _safe_str(status) not in ("draft", "published", "disabled", ""):
        return _fail("status 仅支持 draft/published/disabled")
    try:
        # 校验归属
        row = (await db.execute(
            select(WorkflowDefinition.id, WorkflowDefinition.user_id).where(
                WorkflowDefinition.tenant_id == tenant_id,
                WorkflowDefinition.id == workflow_id,
                WorkflowDefinition.deleted == 0,
            )
        )).one_or_none()
        if row is None:
            return _fail("工作流不存在或无权访问")
        wf_user_id = int(row[1] or 0)
        if wf_user_id != 0 and wf_user_id != user_id:
            return _fail("工作流不存在或无权访问")

        updates: List[str] = []
        params: Dict[str, Any] = {"id": workflow_id, "tenant_id": tenant_id}
        if name is not None and _safe_str(name):
            updates.append("name = :name")
            params["name"] = _safe_str(name)[:200]
        if description is not None:
            updates.append("description = :description")
            params["description"] = _safe_str(description)
        if trigger_type is not None and _safe_str(trigger_type):
            updates.append("trigger_type = :trigger_type")
            params["trigger_type"] = _safe_str(trigger_type)
        if status is not None and _safe_str(status):
            updates.append("status = :status")
            params["status"] = _safe_str(status)
        if not updates:
            return _fail("没有可更新的字段")
        updates.append("updated_time = NOW()")
        sql = f"UPDATE workflow_definition SET {', '.join(updates)} " \
              f"WHERE id = :id AND tenant_id = :tenant_id"
        await db.execute(text(sql), params)
        await db.commit()
        logger.info(
            "update_workflow ok tenantId=%d userId=%d workflowId=%d",
            tenant_id, user_id, workflow_id,
        )
        return _ok({
            "workflowId": workflow_id,
            "updatedFields": [u.split(" = ")[0] for u in updates if " = " in u],
            "message": "工作流配置已更新",
        })
    except Exception as exc:
        logger.warning(
            "update_workflow failed tenantId=%d workflowId=%d errorType=%s",
            tenant_id, workflow_id, type(exc).__name__,
            exc_info=True,
        )
        await db.rollback()
        return _fail("更新工作流配置失败，请稍后重试")


async def update_scheduled_task(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    task_id: int,
    task_name: Optional[str] = None,
    cron_expr: Optional[str] = None,
    task_type: Optional[str] = None,
    **_: Any,
) -> ToolResult:
    """更新定时任务配置（task_name/cron_expr/task_type）。

    不支持修改 account_id（需新建任务绑定其他账号）。
    """
    task_id = _safe_int(task_id)
    if task_id <= 0:
        return _fail("taskId 必须为正整数")
    try:
        # 校验归属
        row = (await db.execute(
            text("SELECT id, user_id, account_id FROM scheduled_task "
                 "WHERE tenant_id = :tenant_id AND id = :id AND deleted = 0"),
            {"tenant_id": tenant_id, "id": task_id},
        )).mappings().first()
        if row is None:
            return _fail("定时任务不存在或无权访问")
        if int(row["user_id"] or 0) != 0 and int(row["user_id"] or 0) != user_id:
            return _fail("定时任务不存在或无权访问")

        updates: List[str] = []
        params: Dict[str, Any] = {"id": task_id, "tenant_id": tenant_id}
        if task_name is not None and _safe_str(task_name):
            updates.append("task_name = :task_name")
            params["task_name"] = _safe_str(task_name)[:200]
        if cron_expr is not None and _safe_str(cron_expr):
            updates.append("cron_expression = :cron_expr")
            params["cron_expr"] = _safe_str(cron_expr)
        if task_type is not None and _safe_str(task_type):
            updates.append("task_type = :task_type")
            params["task_type"] = _safe_str(task_type)
        if not updates:
            return _fail("没有可更新的字段")
        updates.append("updated_time = NOW()")
        sql = f"UPDATE scheduled_task SET {', '.join(updates)} " \
              f"WHERE id = :id AND tenant_id = :tenant_id"
        await db.execute(text(sql), params)
        await db.commit()
        logger.info(
            "update_scheduled_task ok tenantId=%d taskId=%d",
            tenant_id, task_id,
        )
        return _ok({
            "taskId": task_id,
            "updatedFields": [u.split(" = ")[0] for u in updates if " = " in u],
            "message": "定时任务配置已更新",
        })
    except Exception as exc:
        logger.warning(
            "update_scheduled_task failed tenantId=%d taskId=%d errorType=%s",
            tenant_id, task_id, type(exc).__name__,
            exc_info=True,
        )
        await db.rollback()
        return _fail("更新定时任务配置失败，请稍后重试")


async def update_auto_reply_rule(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    rule_id: int,
    rule_name: Optional[str] = None,
    match_type: Optional[str] = None,
    match_keywords: Optional[str] = None,
    reply_content: Optional[str] = None,
    priority: Optional[int] = None,
    **_: Any,
) -> ToolResult:
    """更新自动回复规则配置。

    match_type: keyword/ai/all
    priority: 整数，越大越优先
    """
    rule_id = _safe_int(rule_id)
    if rule_id <= 0:
        return _fail("ruleId 必须为正整数")
    if match_type is not None and _safe_str(match_type) not in ("keyword", "ai", "all", ""):
        return _fail("matchType 仅支持 keyword/ai/all")
    try:
        # 校验归属
        row = (await db.execute(
            text("SELECT r.id, a.user_id FROM auto_reply_rule r "
                 "LEFT JOIN xianyu_account a ON a.id = r.account_id "
                 "WHERE r.tenant_id = :tenant_id AND r.id = :id AND r.deleted = 0"),
            {"tenant_id": tenant_id, "id": rule_id},
        )).mappings().first()
        if row is None:
            return _fail("自动回复规则不存在或无权访问")
        if int(row["user_id"] or 0) != 0 and int(row["user_id"] or 0) != user_id:
            return _fail("自动回复规则不存在或无权访问")

        updates: List[str] = []
        params: Dict[str, Any] = {"id": rule_id, "tenant_id": tenant_id}
        if rule_name is not None and _safe_str(rule_name):
            updates.append("rule_name = :rule_name")
            params["rule_name"] = _safe_str(rule_name)[:200]
        if match_type is not None and _safe_str(match_type):
            updates.append("match_type = :match_type")
            params["match_type"] = _safe_str(match_type)
        if match_keywords is not None:
            updates.append("match_keywords = :match_keywords")
            params["match_keywords"] = _safe_str(match_keywords)
        if reply_content is not None and _safe_str(reply_content):
            updates.append("reply_content = :reply_content")
            params["reply_content"] = _safe_str(reply_content)
        if priority is not None:
            try:
                p_int = int(priority)
                updates.append("priority = :priority")
                params["priority"] = p_int
            except (TypeError, ValueError):
                pass
        if not updates:
            return _fail("没有可更新的字段")
        updates.append("updated_time = NOW()")
        sql = f"UPDATE auto_reply_rule SET {', '.join(updates)} " \
              f"WHERE id = :id AND tenant_id = :tenant_id"
        await db.execute(text(sql), params)
        await db.commit()
        logger.info(
            "update_auto_reply_rule ok tenantId=%d ruleId=%d",
            tenant_id, rule_id,
        )
        return _ok({
            "ruleId": rule_id,
            "updatedFields": [u.split(" = ")[0] for u in updates if " = " in u],
            "message": "自动回复规则已更新",
        })
    except Exception as exc:
        logger.warning(
            "update_auto_reply_rule failed tenantId=%d ruleId=%d errorType=%s",
            tenant_id, rule_id, type(exc).__name__,
            exc_info=True,
        )
        await db.rollback()
        return _fail("更新自动回复规则失败，请稍后重试")


async def prepare_product_publish(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    account_id: int,
    title: str,
    description: str,
    price: str,
    image_urls: List[str],
    stock: Optional[int] = None,
    shipping_mode: Optional[str] = None,
    **_: Any,
) -> ToolResult:
    """准备商品发布参数（不直接发布到闲鱼平台，返回结构化参数供前端确认）。

    安全约束：本工具仅校验参数并返回发布所需的完整字段清单，引导用户前往前端发布页确认发布。
    """
    account_id = _safe_int(account_id)
    if account_id <= 0:
        return _fail("accountId 必须为正整数")
    title = _safe_str(title)
    description = _safe_str(description)
    price = _safe_str(price)
    if not title:
        return _fail("title 不能为空")
    if len(title) > 60:
        return _fail("标题过长（最多 60 字）")
    if not description:
        return _fail("description 不能为空")
    if not price:
        return _fail("price 不能为空")
    if not image_urls or not isinstance(image_urls, list) or len(image_urls) == 0:
        return _fail("至少需要 1 张商品图片")
    if len(image_urls) > 20:
        return _fail("最多支持 20 张图片")
    shipping_mode = _safe_str(shipping_mode) or "free"
    if shipping_mode not in ("free", "fixed", "none"):
        return _fail("shippingMode 仅支持 free/fixed/none")

    try:
        # 校验账号归属
        owner_row = (await db.execute(
            select(XianyuAccount.user_id, XianyuAccount.fish_shop_user, XianyuAccount.nickname).where(
                XianyuAccount.tenant_id == tenant_id,
                XianyuAccount.id == account_id,
                XianyuAccount.deleted == 0,
            )
        )).one_or_none()
        if owner_row is None or int(owner_row[0] or 0) != user_id:
            return _fail("账号不存在或无权访问")
        is_fish_shop = int(owner_row[1] or 0) == 1
        account_name = owner_row[2] or ""

        # 构造发布参数清单
        publish_payload = {
            "accountId": account_id,
            "accountName": account_name,
            "isFishShop": is_fish_shop,
            "title": title,
            "description": description,
            "price": price,
            "stock": _safe_int(stock, default=1) if stock is not None else 1,
            "imageUrls": image_urls,
            "shippingMode": shipping_mode,
            "publishUrl": "/publish",
            # 重要：明确告知用户商品尚未发布，必须前往前端发布页点击发布按钮
            "published": False,
            "message": (
                f"已为商品「{title}」准备好发布参数（{len(image_urls)} 张图片，价格 {price} 元）。"
                "注意：当前商品尚未发布到闲鱼平台，请前往【商品发布】页面："
                "1) 确认参数无误；2) 选择商品分类与发货地址；3) 生成 AI 封面图（发布前强制校验）；"
                "4) 点击页面底部的「发布」按钮完成上架。只有点击发布按钮后商品才会真正上架。"
            ),
        }
        logger.info(
            "prepare_product_publish ok tenantId=%d userId=%d accountId=%d titleLen=%d imgCnt=%d",
            tenant_id, user_id, account_id, len(title), len(image_urls),
        )
        return _ok(publish_payload)
    except Exception as exc:
        logger.warning(
            "prepare_product_publish failed tenantId=%d errorType=%s",
            tenant_id, type(exc).__name__,
            exc_info=True,
        )
        return _fail("准备发布参数失败，请稍后重试")


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
    # 订单与发货与退款
    "list_orders": list_orders,
    "list_delivery_records": list_delivery_records,
    "list_refunds": list_refunds,
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
    "import_cards": import_cards,
    "delete_card_group": delete_card_group,
    "create_workflow": create_workflow,
    "create_scheduled_task": create_scheduled_task,
    "polish_product_title": polish_product_title,
    # 切换类
    "toggle_scheduled_task": toggle_scheduled_task,
    "toggle_auto_reply_rule": toggle_auto_reply_rule,
    # 商品管理增强类
    "get_product_summary": get_product_summary,
    "delete_product": delete_product,
    "toggle_product_status": toggle_product_status,
    "search_goods_online": search_goods_online,
    # 系统功能清单类（自主学习能力基础）
    "list_system_features": list_system_features,
    # 消息类
    "list_recent_conversations": list_recent_conversations,
    "reply_buyer_message": reply_buyer_message,
    # 鱼小铺数据分析类
    "get_fish_shop_data": get_fish_shop_data,
    "get_sales_comparison": get_sales_comparison,
    # 配置更新类
    "update_delivery_statement": update_delivery_statement,
    "update_workflow": update_workflow,
    "update_scheduled_task": update_scheduled_task,
    "update_auto_reply_rule": update_auto_reply_rule,
    # 商品发布类
    "prepare_product_publish": prepare_product_publish,
}


# 工具元信息：供 AI 在系统提示中识别可调用工具
TOOL_DEFINITIONS: list[Dict[str, Any]] = [
    # ===== 账号与商品 =====
    {
        "name": "list_accounts",
        "description": "列出当前用户名下的闲鱼账号完整信息（含地区、等级、在线状态、WS状态、Cookie状态、健康分）。当用户问「我的账号」「账号怎么样」「有几个账号」时调用此工具，无需再调 get_account_status。",
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
        "description": "列出指定账号下的商品（用于客服查看商品上下文）。accountId 未提供时自动选择第一个可用账号",
        "parameters": {
            "accountId": "int (可选) 闲鱼账号ID，不传则自动选择第一个可用账号",
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
        "name": "list_refunds",
        "description": "查询退款记录列表，按退款申请时间倒序返回。当用户问「最近有没有退款」「退款管理」「退款状态」「有没有新退款」时调用此工具。通过 join xianyu_account 限定为当前用户名下账号的退款。",
        "parameters": {
            "accountId": "int (可选) 闲鱼账号ID，不传则查全部账号",
            "refundStatus": "string (可选) 退款状态关键词（如退款中/退款成功/退款关闭），模糊匹配",
            "days": "int (可选) 查最近 N 天内的退款，默认不限制；用户说「最近有没有退款」时传 7",
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
        "description": "创建卡密/货源库分组，可同时批量导入卡密条目。当用户发来一组卡密要求「新建仓库」「建卡密分组」「建货源库」时调用此工具，把卡密作为 cards 数组传入，一次完成创建+导入。cards 数组每项可为字符串（直接作为卡密key）或对象 {key, value, remark}。",
        "parameters": {
            "groupName": "string (必填) 分组名称",
            "groupType": "string (可选) 分组类型：kami/text，默认kami",
            "remark": "string (可选) 备注",
            "cards": "array (可选) 卡密条目数组，每项可为字符串或 {key, value, remark} 对象。用户发来一批卡密时把每行作为一个字符串传入",
        },
    },
    {
        "name": "import_cards",
        "description": "向已存在的卡密/货源库分组批量导入卡密条目。当用户要求「把以下卡密加到分组X」「向仓库Y追加卡密」「向分组追加卡密」时调用本工具，而不是 create_delivery_rule。需先用 list_card_groups 查到目标分组的ID。",
        "parameters": {
            "groupId": "int (必填) 目标分组ID",
            "cards": "array (必填) 卡密条目数组，每项可为字符串或 {key, value, remark} 对象",
        },
    },
    {
        "name": "delete_card_group",
        "description": "删除空的卡密/货源库分组（软删除，仅允许删除 available_count=0 的空分组，非空分组会返回失败）。当用户说「删除卡密分组」「删除空分组」「删掉货源库」时调用本工具，而不是 delete_product。需先用 list_card_groups 查到目标分组的ID。",
        "parameters": {
            "groupId": "int (必填) 要删除的分组ID",
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
        "description": "使用通用模型润色商品标题（按次计费，不直接写库，返回新标题供用户确认）。支持两种模式：1)传 goodsId 润色指定商品标题 2)传 title 直接润色用户提供的标题文本。用户说「帮我润色标题「XXX」」时传 title 参数。",
        "parameters": {
            "goodsId": "int (可选) 商品ID，润色指定商品时传",
            "title": "string (可选) 要润色的标题文本，用户直接提供标题时传",
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
    # ===== 商品管理增强类 =====
    {
        "name": "get_product_summary",
        "description": "查询商品汇总统计：总数、在售、下架、已售、总曝光、总浏览、总想要。当用户问「我总共有多少商品」「商品总数」「商品统计」「商品汇总」时调用此工具，可选 accountId 限定单账号。",
        "parameters": {
            "accountId": "int (可选) 闲鱼账号ID，不传则汇总全部账号",
        },
    },
    {
        "name": "delete_product",
        "description": "软删除商品（仅本地标记删除，不直接调用闲鱼下架接口）。当用户说「帮我删除商品X」「删掉这个商品」时调用此工具，删除后需提醒用户在前端同步下架到闲鱼平台。",
        "parameters": {
            "goodsId": "int (必填) 商品ID",
        },
    },
    {
        "name": "toggle_product_status",
        "description": "商品上下架（仅更新本地状态，不直接调用闲鱼接口）。onShelf=true 上架，onShelf=false 下架。当用户说「帮我下架商品X」「上架这个商品」时调用。",
        "parameters": {
            "goodsId": "int (必填) 商品ID",
            "onShelf": "bool (必填) true=上架 false=下架",
        },
    },
    {
        "name": "search_goods_online",
        "description": "搜索闲鱼商品并返回商品列表（含标题、价格、图片、卖家、地区）。复用项目内的搜索执行器，支持 fast/slow/auto 三种模式。当用户说「帮我搜一下XXX」「搜索商品」「看看同行卖什么」时调用此工具。",
        "parameters": {
            "keyword": "string (必填) 搜索关键词",
            "accountId": "int (可选) 闲鱼账号ID（用其Cookie搜索），不传则用租户内第一个有效账号",
            "page": "int (可选) 页码，默认1",
            "pageSize": "int (可选) 每页数量，默认10，最大30",
            "mode": "string (可选) 搜索模式：fast/slow/auto，默认auto",
        },
    },
    # ===== 系统功能清单类 =====
    {
        "name": "list_system_features",
        "description": "查询系统所有功能页面清单（自主学习能力基础）。返回与前台 nav.js 同步的 9 个分类共 30+ 个功能页面。当用户问「系统有什么功能」「能帮我做什么」「有哪些页面」「能不能帮我XXX」时调用此工具，让 AI 客服准确告知用户系统能力边界。",
        "parameters": {
            "category": "string (可选) 按分类名过滤，如「账号」「商品」「消息」「自动发货」等；不传则返回全部",
        },
    },
    # ===== 消息类 =====
    {
        "name": "list_recent_conversations",
        "description": "查询最近会话列表，含买家昵称、商品信息、未读数、最后消息内容。当用户问「在线消息怎么样」「最近有谁找我」「有没有人发消息」「未读消息」时调用此工具。",
        "parameters": {
            "accountId": "int (可选) 闲鱼账号ID，不传则查全部账号",
            "unreadOnly": "bool (可选) 是否只看未读，默认false",
            "limit": "int (可选) 返回数量，默认10，最大50",
        },
    },
    {
        "name": "reply_buyer_message",
        "description": "回复买家在线消息。调用此工具后会自动暂停该会话的自动回复 1 分钟，避免 AI 抢答。当用户说「帮我回复买家」「告诉他XXX」「回复这个消息」时调用，需先通过 list_recent_conversations 获取 conversationId。",
        "parameters": {
            "accountId": "int (必填) 闲鱼账号ID",
            "conversationId": "int (必填) 会话ID（从 list_recent_conversations 获取）",
            "message": "string (必填) 回复内容，最多 500 字",
        },
    },
    # ===== 鱼小铺数据分析类 =====
    {
        "name": "get_fish_shop_data",
        "description": "查询鱼小铺数据罗盘：成交金额、订单数、客单价、曝光、浏览、咨询、退款等关键指标，含同比环比。当用户问「鱼小铺数据」「数据罗盘」「店铺数据怎么样」「数据分析」时调用此工具。",
        "parameters": {
            "accountId": "int (可选) 鱼小铺账号ID，不传则聚合用户名下全部鱼小铺账号",
            "dateType": "string (可选) 时间范围：recent1d=近1天/recent7d=近7天/recent30d=近30天，默认recent7d",
        },
    },
    {
        "name": "get_sales_comparison",
        "description": "查询今日与昨日销售对比：订单数、成交金额、待发货数、增长率。当用户问「今天比昨天多卖多少钱」「今日销售怎么样」「销售对比」时调用此工具。",
        "parameters": {
            "accountId": "int (可选) 闲鱼账号ID，不传则查全部账号",
        },
    },
    # ===== 配置更新类 =====
    {
        "name": "update_delivery_statement",
        "description": "更新发货声明配置（仅落库，不立即发送声明消息）。可更新启用状态和声明文案。当用户说「帮我配置发货声明」「修改声明文案」「关闭发货声明」时调用此工具。",
        "parameters": {
            "enabled": "bool (可选) 是否启用：true=启用 false=禁用",
            "content": "string (可选) 声明文案内容",
        },
    },
    {
        "name": "update_workflow",
        "description": "更新工作流定义的基础信息（名称、描述、触发方式、状态）。不支持修改节点与连线（需在前端画布操作）。当用户说「帮我重命名工作流」「修改工作流描述」「发布/禁用工作流」时调用。",
        "parameters": {
            "workflowId": "int (必填) 工作流ID",
            "name": "string (可选) 工作流名称",
            "description": "string (可选) 描述",
            "triggerType": "string (可选) 触发方式：manual/scheduled/event",
            "status": "string (可选) 状态：draft/published/disabled",
        },
    },
    {
        "name": "update_scheduled_task",
        "description": "更新定时任务配置（任务名、Cron 表达式、任务类型）。不支持修改账号绑定（需新建任务）。当用户说「帮我修改定时任务」「改一下执行时间」「更新 Cron 表达式」时调用。",
        "parameters": {
            "taskId": "int (必填) 定时任务ID",
            "taskName": "string (可选) 任务名称",
            "cronExpr": "string (可选) Cron 表达式",
            "taskType": "string (可选) 任务类型",
        },
    },
    {
        "name": "update_auto_reply_rule",
        "description": "更新自动回复规则配置（规则名、匹配类型、匹配关键词、回复内容、优先级）。当用户说「帮我修改自动回复规则」「改一下回复内容」「调整优先级」时调用。",
        "parameters": {
            "ruleId": "int (必填) 自动回复规则ID",
            "ruleName": "string (可选) 规则名称",
            "matchType": "string (可选) 匹配类型：keyword/ai/all",
            "matchKeywords": "string (可选) 关键词，逗号分隔",
            "replyContent": "string (可选) 回复内容",
            "priority": "int (可选) 优先级，越大越优先",
        },
    },
    # ===== 商品发布类 =====
    {
        "name": "prepare_product_publish",
        "description": "准备商品发布参数（不直接发布到闲鱼平台，返回结构化参数引导用户前往发布页确认）。当用户说「帮我发布一个商品」「上新一个商品」时调用，需用户提供标题、描述、价格、图片URL列表，准备好参数后引导用户前往【商品发布】页面点击发布按钮。",
        "parameters": {
            "accountId": "int (必填) 闲鱼账号ID",
            "title": "string (必填) 商品标题（最多60字）",
            "description": "string (必填) 商品描述",
            "price": "string (必填) 价格（字符串，如「99.5」）",
            "imageUrls": "array (必填) 商品图片URL列表，至少1张，最多20张",
            "stock": "int (可选) 库存数量，默认1",
            "shippingMode": "string (可选) 运费模式：free/fixed/none，默认free",
        },
    },
]


def get_tool_names() -> list[str]:
    """返回已注册的工具名列表。"""
    return list(TOOL_REGISTRY.keys())


# 查询类工具集合：只读、无副作用，可在 stream_chat 中自动执行无需用户确认
QUERY_TOOLS: set[str] = {
    "list_accounts",
    "get_account_status",
    "list_products",
    "get_goods_detail",
    "get_account_summary",
    "list_orders",
    "list_delivery_records",
    "list_refunds",
    "list_card_groups",
    "list_workflows",
    "list_scheduled_tasks",
    "list_auto_reply_rules",
    "get_token_balance",
    "get_dashboard_summary",
    # 商品管理增强类（只读）
    "get_product_summary",
    "search_goods_online",
    "list_system_features",  # 系统功能清单（自主学习能力基础，只读）
    # 消息类（只读）
    "list_recent_conversations",
    # 鱼小铺数据分析类（只读）
    "get_fish_shop_data",
    "get_sales_comparison",
}


def is_query_tool(tool_name: str) -> bool:
    """判断工具是否为查询类（只读、无副作用）。"""
    return tool_name in QUERY_TOOLS


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
            exc_info=True,
        )
        return _fail(f"工具参数无效：{tool_name}")
    except Exception as exc:
        logger.warning(
            "execute_tool unexpected failure tool=%s tenantId=%d errorType=%s",
            tool_name, tenant_id, type(exc).__name__,
            exc_info=True,
        )
        return _fail(f"工具执行失败：{tool_name}")
