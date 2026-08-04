# -*- coding: utf-8 -*-
"""会员等级店铺数量限制（Python 侧）。

与 Java FeatureSwitchService 保持一致：
- 数据源：admin_module_record 中 user_feature_switch 配置的 store-limit 行（0 表示无限制）；
- 默认值：普通用户 1 / VIP（单店版）1 / VIP 不限 / SVIP 不限；
- 用户等级优先读取 sys_user.vip_level（3=单店版、2=SVIP、1=VIP），否则取有效订阅套餐编码。
"""

import json
import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

DEFAULT_STORE_LIMITS = {"normal": 1, "vipSingle": 1, "vip": 0, "svp": 0}

_LIMIT_FIELD_MAP = {
    "normal": "storeLimitNormal",
    "vipSingle": "storeLimitVipSingle",
    "vip": "storeLimitVip",
    "svp": "storeLimitSvp",
}


def _normalize_plan_code(code) -> str:
    if not code:
        return "normal"
    c = str(code).strip().lower()
    if c == "svip":
        return "svp"
    return c


def _is_vip_single(code) -> bool:
    c = str(code or "").strip().lower()
    return c.startswith("vip-single") or c.startswith("vip_single") or c in ("vip1", "vipone")


def _limit_for_plan(limits: dict, plan_code: str) -> int:
    c = str(plan_code or "").strip().lower()
    if _is_vip_single(c):
        return int(limits.get("vipSingle", 1))
    if c.startswith("svp") or c.startswith("svip"):
        return int(limits.get("svp", 0))
    if c.startswith("vip"):
        return int(limits.get("vip", 0))
    return int(limits.get("normal", 1))


async def resolve_user_plan_code(db: AsyncSession, user_id) -> str:
    """解析用户当前会员套餐编码（含 vip-single）。"""
    try:
        row = (
            await db.execute(
                text("SELECT vip_level FROM sys_user WHERE id=:uid AND deleted=0"),
                {"uid": user_id},
            )
        ).first()
        if row is not None and row.vip_level:
            level = int(row.vip_level)
            if level == 3:
                return "vip-single"
            if level >= 2:
                return "svp"
            return "vip"
    except Exception as e:  # noqa: BLE001
        logger.warning("resolve vip_level failed user=%s errorType=%s", user_id, type(e).__name__)

    try:
        row = (
            await db.execute(
                text(
                    "SELECT p.plan_code FROM billing_subscription s "
                    "JOIN billing_plan p ON p.id=s.plan_id AND p.deleted=0 "
                    "WHERE s.user_id=:uid AND s.status=1 AND s.target_type='user_account' "
                    "AND (s.end_time IS NULL OR s.end_time>=NOW()) "
                    "ORDER BY COALESCE(s.end_time,'9999-12-31') DESC LIMIT 1"
                ),
                {"uid": user_id},
            )
        ).first()
        if row is not None and row.plan_code:
            return _normalize_plan_code(row.plan_code)
    except Exception as e:  # noqa: BLE001
        logger.warning("resolve subscription failed user=%s errorType=%s", user_id, type(e).__name__)

    return "normal"


async def load_store_limits(db: AsyncSession) -> dict:
    """读取功能管理 store-limit 行配置；缺失/异常时返回默认值。"""
    limits = dict(DEFAULT_STORE_LIMITS)
    try:
        row = (
            await db.execute(
                text(
                    "SELECT json_text FROM admin_module_record "
                    "WHERE module_key='user_feature_switch' AND status='config' AND deleted=0 "
                    "ORDER BY id ASC LIMIT 1"
                )
            )
        ).first()
        if row is not None and row.json_text:
            parsed = json.loads(row.json_text)
            store = (parsed or {}).get("features", {}).get("store-limit", {})
            if isinstance(store, dict):
                for key, field in _LIMIT_FIELD_MAP.items():
                    try:
                        n = int(store.get(field))
                        if n >= 0:
                            limits[key] = n
                    except (TypeError, ValueError):
                        pass
    except Exception as e:  # noqa: BLE001
        logger.warning("load store limits failed errorType=%s", type(e).__name__)
    return limits


async def get_user_store_limit(db: AsyncSession, user_id) -> int:
    limits = await load_store_limits(db)
    plan_code = await resolve_user_plan_code(db, user_id)
    return _limit_for_plan(limits, plan_code)


async def count_active_accounts(db: AsyncSession, user_id) -> int:
    try:
        row = (
            await db.execute(
                text("SELECT COUNT(*) AS c FROM xianyu_account WHERE user_id=:uid AND deleted=0"),
                {"uid": user_id},
            )
        ).first()
        return int(row.c or 0) if row is not None else 0
    except Exception as e:  # noqa: BLE001
        logger.warning("count active accounts failed user=%s errorType=%s", user_id, type(e).__name__)
        return 0


async def assert_can_add_store(db: AsyncSession, user_id) -> Optional[dict]:
    """新增/恢复店铺前校验；超限返回结构化错误，未超限返回 None。"""
    limit = await get_user_store_limit(db, user_id)
    if limit <= 0:
        return None
    count = await count_active_accounts(db, user_id)
    if count >= limit:
        return {
            "_error": "STORE_LIMIT_REACHED",
            "message": f"店铺数量已达上限（{limit} 个），请升级 VIP 后继续添加",
            "limit": limit,
            "accountCount": count,
        }
    return None
