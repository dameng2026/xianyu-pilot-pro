"""
滑块求解预校验服务
==================
在执行自动滑块求解前，对账号进行三重预校验：

1. **Cookie 状态预校验**：调用闲鱼 hasLogin API 验证 Cookie 是否有效
   - Cookie 有效 → 通过，继续求解
   - Cookie 触发滑块 → 通过（这正是我们要解决的）
   - Cookie 失效/Session 过期 → 拒绝，提示用户重新扫码
   - 调用失败 → 拒绝（避免无效求解）

2. **账号活跃度检查**：连续 3 天无操作的账号禁止求解
   - 基于 xianyu_account_runtime.last_online_time 判断
   - 账号被禁用（status != 1 或 disabled_by_admin = 1）也禁止

3. **会员等级查询**：用于优先级队列排序
   - SVIP/SVP = 2（最高优先级）
   - VIP = 1
   - normal = 0

设计原则：
- 预校验失败时不启动浏览器，避免浪费资源
- 预校验结果通过 failure_reason 字段分类记录，便于后续分析
- Cookie 预校验每次都调用 API（用户明确要求），确保准确性
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import text

from ..core.database import async_session
from ..core.failure_logging import log_service_failure

logger = logging.getLogger(__name__)

# 连续 3 天无操作则禁止求解
ACCOUNT_INACTIVE_DAYS = 3
# Cookie 预校验调用 hasLogin 的超时（秒）
PRECHECK_COOKIE_TIMEOUT_SEC = 20

# 会员等级 → 优先级权重映射
LEVEL_PRIORITY_MAP = {
    "svip": 2,
    "svp": 2,  # svp 是 svip 的别名
    "vip": 1,
    "normal": 0,
}

# 手动求解优先级提升值：手动求解（manual/manual_retry）比自动求解优先级高
# 在基础会员等级优先级（SVIP=2/VIP=1/normal=0）上叠加此值
# 最终优先级：手动 SVIP=102 > 手动 VIP=101 > 手动 normal=100 > 自动 SVIP=2 > 自动 VIP=1 > 自动 normal=0
MANUAL_PRIORITY_BOOST = 100

# 手动触发场景集合：用户在前台主动点击求解按钮的场景
MANUAL_TRIGGER_SCENES = {"manual", "manual_retry"}


async def precheck_cookie_status(account_id: int, tenant_id: int) -> tuple[bool, str, str]:
    """Cookie 状态预校验：调用 hasLogin API 验证 Cookie 是否有效。

    Args:
        account_id: 账号 ID
        tenant_id: 租户 ID

    Returns:
        (is_pass, failure_reason, message)
        - is_pass: 是否通过预校验（True=可继续求解，False=应拒绝求解）
        - failure_reason: 失败原因分类（空字符串表示通过）
          - "cookie_invalid": Cookie Session 已过期，需重新扫码
          - "service_unavailable": hasLogin 服务不可用
          - "precheck_rejected": 其他预校验拒绝原因
        - message: 人类可读的说明信息
    """
    try:
        # 复用 cookie_token_refresher 的 _call_has_login
        # 它会读取数据库 Cookie、调用 hasLogin API、检测风控、返回结构化结果
        from .cookie_token_refresher import _call_has_login
        import asyncio

        result = await asyncio.wait_for(
            _call_has_login(account_id, tenant_id),
            timeout=PRECHECK_COOKIE_TIMEOUT_SEC,
        )

        if result.get("success"):
            logger.info(
                "Cookie 预校验通过 accountId=%d (cookieUpdated=%s)",
                account_id, result.get("cookieUpdated", False),
            )
            return True, "", "Cookie 状态正常"

        error_code = str(result.get("errorCode") or "")
        error_msg = str(result.get("error") or "Cookie 校验失败")

        # CAPTCHA_NEEDED 表示 Cookie 还在但触发了滑块 → 这正是我们要解决的场景，允许继续
        if "CAPTCHA_NEEDED" in error_code or "FAIL_SYS_USER_VALIDATE" in error_msg or "RGV587" in error_msg:
            logger.info(
                "Cookie 预校验：触发滑块验证，允许继续求解 accountId=%d errorCode=%s",
                account_id, error_code,
            )
            return True, "", "Cookie 触发滑块验证，需要求解"

        # SESSION_EXPIRED / COOKIE_EXPIRED → Cookie 已失效，需用户重新扫码
        if "SESSION_EXPIRED" in error_code or "COOKIE_EXPIRED" in error_code or "登入失败" in error_msg:
            logger.warning(
                "Cookie 预校验失败：Session 已过期 accountId=%d errorCode=%s",
                account_id, error_code,
            )
            return False, "cookie_invalid", "Cookie Session 已过期，请重新扫码登录闲鱼账号"

        # HAS_LOGIN_UNCONFIRMED / HAS_LOGIN_REJECTED → Cookie 被平台拒绝
        if "HAS_LOGIN" in error_code:
            logger.warning(
                "Cookie 预校验失败：hasLogin 拒绝 accountId=%d errorCode=%s",
                account_id, error_code,
            )
            return False, "cookie_invalid", "Cookie 已失效（平台拒绝登录），请重新扫码登录"

        # HAS_LOGIN_UNAVAILABLE → 服务暂时不可用，拒绝避免无效求解
        if "HAS_LOGIN_UNAVAILABLE" in error_code:
            logger.warning(
                "Cookie 预校验失败：hasLogin 服务不可用 accountId=%d", account_id,
            )
            return False, "service_unavailable", "Cookie 校验服务暂时不可用，请稍后重试"

        # 其他未知错误
        logger.warning(
            "Cookie 预校验失败：未知错误 accountId=%d errorCode=%s error=%s",
            account_id, error_code, error_msg,
        )
        return False, "precheck_rejected", f"Cookie 校验未通过：{error_msg}"

    except TimeoutError:
        logger.warning("Cookie 预校验超时 accountId=%d", account_id)
        return False, "service_unavailable", "Cookie 校验超时，请稍后重试"
    except Exception as e:
        log_service_failure(
            logger, e, operation="precheck_cookie_status",
            tenant_id=tenant_id, account_id=account_id,
        )
        return False, "service_unavailable", "Cookie 校验服务异常，请稍后重试"


async def precheck_account_active(account_id: int, tenant_id: int) -> tuple[bool, str, str]:
    """账号活跃度与状态检查。

    检查规则：
    1. 账号被禁用（status != 1 或 disabled_by_admin = 1）→ 拒绝
    2. 账号连续 3 天无操作（last_online_time 超过 3 天前）→ 拒绝

    Args:
        account_id: 账号 ID
        tenant_id: 租户 ID

    Returns:
        (is_pass, failure_reason, message)
        - failure_reason: "account_inactive" 或 "account_disabled" 或 ""（通过）
    """
    try:
        async with async_session() as db:
            row = (await db.execute(
                text("""
                    SELECT a.status, a.disabled_by_admin,
                           r.last_online_time, r.last_heartbeat_time
                    FROM xianyu_account a
                    LEFT JOIN xianyu_account_runtime r
                      ON r.account_id = a.id AND r.tenant_id = a.tenant_id
                    WHERE a.id = :aid AND a.tenant_id = :tid
                      AND COALESCE(a.deleted, 0) = 0
                    LIMIT 1
                """),
                {"aid": account_id, "tid": tenant_id},
            )).mappings().first()

        if not row:
            logger.warning("活跃度检查失败：账号不存在 accountId=%d", account_id)
            return False, "account_inactive", "账号不存在"

        # 检查账号是否被禁用
        status = int(row.get("status") or 0)
        disabled_by_admin = int(row.get("disabled_by_admin") or 0)
        if status != 1:
            logger.info(
                "活跃度检查拒绝：账号已禁用 accountId=%d status=%d",
                account_id, status,
            )
            return False, "account_disabled", "账号已被禁用，无法进行滑块求解"
        if disabled_by_admin == 1:
            logger.info(
                "活跃度检查拒绝：账号被管理员禁用 accountId=%d", account_id,
            )
            return False, "account_disabled", "账号已被管理员禁用，无法进行滑块求解"

        # 检查账号活跃度：last_online_time 超过 3 天则视为不活跃
        # 优先用 last_online_time，fallback 到 last_heartbeat_time
        last_online = row.get("last_online_time")
        last_heartbeat = row.get("last_heartbeat_time")
        reference_time = last_online or last_heartbeat

        if reference_time is None:
            # 从未有在线记录 → 视为不活跃（可能是从未连接过的账号）
            logger.info(
                "活跃度检查拒绝：账号从未在线 accountId=%d", account_id,
            )
            return False, "account_inactive", "账号从未在线，请先手动连接一次闲鱼账号"

        # 确保 reference_time 是 datetime 对象
        if isinstance(reference_time, str):
            try:
                reference_time = datetime.fromisoformat(reference_time)
            except ValueError:
                logger.warning(
                    "活跃度检查：last_online_time 格式异常 accountId=%d val=%s",
                    account_id, reference_time,
                )
                return False, "account_inactive", "账号活跃时间格式异常"

        inactive_threshold = datetime.now() - timedelta(days=ACCOUNT_INACTIVE_DAYS)
        if reference_time < inactive_threshold:
            days_inactive = (datetime.now() - reference_time).days
            logger.info(
                "活跃度检查拒绝：账号 %d 天未在线 accountId=%d lastOnline=%s",
                days_inactive, account_id, reference_time,
            )
            return False, "account_inactive", (
                f"账号已连续 {days_inactive} 天无操作，"
                f"超过 {ACCOUNT_INACTIVE_DAYS} 天限制，已暂停自动滑块求解功能。"
                "请先手动连接账号或进行其他操作以恢复活跃状态。"
            )

        return True, "", "账号活跃度正常"

    except Exception as e:
        log_service_failure(
            logger, e, operation="precheck_account_active",
            tenant_id=tenant_id, account_id=account_id,
        )
        return False, "service_unavailable", "账号活跃度检查服务异常，请稍后重试"


async def lookup_account_priority(account_id: int, tenant_id: int) -> int:
    """查询账号的会员等级并映射为优先级权重（已弃用，改为 lookup_user_level）。

    历史遗留：查询 xianyu_account_membership（账号级会员）。
    现已合并到用户级会员（sys_user.vip_level），新代码应使用 lookup_user_level。
    保留此函数仅为向前兼容，永远返回 0（避免历史调用方报错）。

    Args:
        account_id: 账号 ID（已忽略）
        tenant_id: 租户 ID（已忽略）

    Returns:
        永远返回 0（普通用户优先级）。新代码请用 lookup_user_level。
    """
    logger.debug(
        "lookup_account_priority 已弃用，请改用 lookup_user_level accountId=%d",
        account_id,
    )
    return 0


async def lookup_user_level(tenant_id: int) -> tuple[str, int]:
    """查询用户级会员等级与求解优先级权重。

    优先级（基于 sys_user.vip_level，与 FeatureSwitchService 一致）：
    - vip_level >= 2 → ('svp', 2) 最高优先级
    - vip_level == 1 → ('vip', 1)
    - 其他            → ('normal', 0) 最低优先级

    一个用户的所有闲鱼账号共享同一等级。

    Args:
        tenant_id: 租户 ID（即用户 ID）

    Returns:
        (level_code, priority) - 查询失败时降级为 ('normal', 0)
    """
    try:
        async with async_session() as db:
            row = (await db.execute(
                text("""
                    SELECT vip_level
                    FROM sys_user
                    WHERE id = :uid AND COALESCE(deleted, 0) = 0
                    LIMIT 1
                """),
                {"uid": tenant_id},
            )).mappings().first()

        if not row:
            return ("normal", 0)

        vip_level = int(row.get("vip_level") or 0)
        if vip_level >= 2:
            level_code, priority = "svp", 2
        elif vip_level == 1:
            level_code, priority = "vip", 1
        else:
            level_code, priority = "normal", 0

        logger.debug(
            "用户级会员查询 tenantId=%d vipLevel=%d level=%s priority=%d",
            tenant_id, vip_level, level_code, priority,
        )
        return (level_code, priority)

    except Exception as e:
        log_service_failure(
            logger, e, operation="lookup_user_level",
            tenant_id=tenant_id, level=logging.WARNING,
        )
        return ("normal", 0)


async def compute_solve_priority(tenant_id: int, trigger_scene: str = "manual") -> tuple[str, int]:
    """查询用户级会员等级并根据触发场景计算最终求解优先级。

    优先级策略：
    1. 基础优先级由会员等级决定：SVIP=2 > VIP=1 > normal=0
    2. 手动触发场景（manual/manual_retry）在基础优先级上叠加 MANUAL_PRIORITY_BOOST
    3. 最终排序：手动 SVIP > 手动 VIP > 手动 normal > 自动 SVIP > 自动 VIP > 自动 normal

    Args:
        tenant_id: 租户 ID（即用户 ID）
        trigger_scene: 触发场景（manual/manual_retry/ws_connect/cookie_keepalive/token_refresh）

    Returns:
        (level_code, priority) - level_code 为用户会员等级，priority 为排序优先级
    """
    level_code, base_priority = await lookup_user_level(tenant_id)
    priority = base_priority
    if trigger_scene in MANUAL_TRIGGER_SCENES:
        priority = base_priority + MANUAL_PRIORITY_BOOST
    logger.debug(
        "求解优先级计算 tenantId=%d scene=%s level=%s basePriority=%d finalPriority=%d",
        tenant_id, trigger_scene, level_code, base_priority, priority,
    )
    return (level_code, priority)


# 功能开关默认值（与 Java FeatureSwitchService.DEFAULT_FEATURES 一致）
# 仅同步 auto-slider-solve 的默认值，用于 admin_module_record 无配置时降级
_FEATURE_DEFAULT_AUTO_SLIDER_SOLVE = {
    "normal": False,
    "vip": True,
    "svp": True,
}


async def is_auto_slider_solve_allowed(tenant_id: int) -> tuple[bool, str]:
    """查询当前用户的「自动滑块求解」功能开关是否开启。

    数据来源：
    1. sys_user.vip_level → 用户等级
    2. admin_module_record (module_key='user_feature_switch') → 功能开关 JSON
    3. 合并默认值（_FEATURE_DEFAULT_AUTO_SLIDER_SOLVE）

    Args:
        tenant_id: 租户 ID（即用户 ID）

    Returns:
        (allowed, level_code)
        - allowed: True=允许自动求解, False=应静默跳过
        - level_code: 用户等级（normal/vip/svp）
        查询失败时降级为 (True, 'normal') 避免锁死用户主流程。
    """
    level_code, _priority = await lookup_user_level(tenant_id)

    try:
        async with async_session() as db:
            row = (await db.execute(
                text("""
                    SELECT json_text
                    FROM admin_module_record
                    WHERE module_key = 'user_feature_switch'
                      AND status = 'config'
                      AND COALESCE(deleted, 0) = 0
                    ORDER BY id ASC LIMIT 1
                """),
            )).mappings().first()

        if not row or not row.get("json_text"):
            # 无配置记录：使用默认值
            allowed = _FEATURE_DEFAULT_AUTO_SLIDER_SOLVE.get(level_code, False)
            return (bool(allowed), level_code)

        import json
        config = json.loads(str(row.get("json_text")))
        features = config.get("features") or {}
        auto_switch = features.get("auto-slider-solve") or {}

        # 合并默认值：存储配置优先，缺失字段用默认值
        level_on = bool(auto_switch.get(level_code, _FEATURE_DEFAULT_AUTO_SLIDER_SOLVE.get(level_code, False)))

        logger.debug(
            "自动滑块求解开关查询 tenantId=%d level=%s allowed=%s",
            tenant_id, level_code, level_on,
        )
        return (level_on, level_code)

    except Exception as e:
        log_service_failure(
            logger, e, operation="is_auto_slider_solve_allowed",
            tenant_id=tenant_id, level=logging.WARNING,
        )
        # 查询失败降级放行，避免锁死 WS 主流程
        return (True, level_code)
