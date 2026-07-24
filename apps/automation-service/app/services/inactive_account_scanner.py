"""
不活跃账号扫描器
==================
定时扫描 sys_user.last_login_time 超过 3 天未登录前台的用户，
将其闲鱼账号 ID 录入到 xianyu_account_solve_exclusion 排除表，
使其无法进入滑块求解进程排序，避免脏数据占用排队序列。

触发移出：
- 用户在前台登录时，UserAuthService 会执行 DELETE FROM xianyu_account_solve_exclusion
  WHERE user_id = ?，将用户旗下所有闲鱼账号从排除表移出
- 用户恢复活跃后即可正常使用滑块求解功能

设计原则：
- 扫描幂等：INSERT IGNORE + UNIQUE KEY uk_account_id 保证重复扫描不会产生重复记录
- 已在排除表中的账号不会重复插入
- 扫描失败不影响主流程，下次扫描会自动恢复
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text

from ..core.database import async_session
from ..core.failure_logging import log_service_failure

logger = logging.getLogger(__name__)

# 扫描间隔（秒）：每小时扫描一次
SCANNER_INTERVAL_SECONDS = 3600

# 不活跃阈值（天）：超过此天数未登录前台则视为不活跃
# 通过环境变量覆盖，默认 30 天（原 3 天过于激进，导致活跃用户被误排除）
import os as _os
ACCOUNT_INACTIVE_DAYS = int(_os.environ.get("INACTIVE_ACCOUNT_DAYS", "30"))


async def scan_and_exclude_inactive_accounts() -> int:
    """扫描 3 天未登录前台的用户，将其闲鱼账号录入排除表。

    逻辑：
    1. 查询 sys_user 中 last_login_time < NOW() - 3 天 的用户 ID 列表
       （或 last_login_time IS NULL 且 created_at < NOW() - 3 天，即注册后从未登录且超过 3 天）
    2. 查询这些用户名下的所有未删除闲鱼账号 ID
    3. INSERT IGNORE 到 xianyu_account_solve_exclusion 表

    Returns:
        本次新录入排除表的账号数（已存在的不会重复计入）
    """
    try:
        async with async_session() as db:
            # 1. 查询不活跃用户的闲鱼账号
            # 条件：sys_user.last_login_time 超过 3 天
            #       OR sys_user.last_login_time IS NULL（从未登录）
            #       且账号未删除
            rows = (await db.execute(
                text(
                    """
                    SELECT a.id AS account_id, a.tenant_id, a.user_id
                    FROM xianyu_account a
                    INNER JOIN sys_user u ON u.id = a.user_id
                    WHERE COALESCE(a.deleted, 0) = 0
                      AND COALESCE(u.deleted, 0) = 0
                      AND (
                        u.last_login_time IS NULL
                        OR u.last_login_time < DATE_SUB(NOW(), INTERVAL :days DAY)
                      )
                      AND a.id NOT IN (
                        SELECT account_id FROM xianyu_account_solve_exclusion
                      )
                    """,
                ),
                {"days": ACCOUNT_INACTIVE_DAYS},
            )).mappings().all()

            if not rows:
                logger.debug("不活跃账号扫描：无新账号需录入排除表")
                return 0

            # 2. 批量 INSERT IGNORE 到排除表
            # 使用 INSERT IGNORE + UNIQUE KEY uk_account_id 保证幂等
            values_parts = []
            params: dict[str, object] = {}
            for i, row in enumerate(rows):
                values_parts.append(
                    f"(:aid{i}, :tid{i}, :uid{i}, 'user_inactive')"
                )
                params[f"aid{i}"] = int(row["account_id"])
                params[f"tid{i}"] = int(row["tenant_id"])
                params[f"uid{i}"] = int(row["user_id"])

            values_sql = ", ".join(values_parts)
            result = await db.execute(
                text(
                    f"""
                    INSERT IGNORE INTO xianyu_account_solve_exclusion
                        (account_id, tenant_id, user_id, reason)
                    VALUES {values_sql}
                    """,
                ),
                params,
            )
            await db.commit()

            affected = int(getattr(result, "rowcount", 0) or 0)
            if affected > 0:
                logger.info(
                    "不活跃账号扫描完成：新录入 %d 个账号到排除表（3天未登录阈值，共查询到 %d 个候选）",
                    affected, len(rows),
                )
            else:
                logger.debug(
                    "不活跃账号扫描完成：查询到 %d 个候选但均已在排除表中", len(rows),
                )
            return affected
    except Exception as e:
        log_service_failure(
            logger, e, operation="scan_and_exclude_inactive_accounts",
            level=logging.WARNING,
        )
        return 0


async def run_inactive_account_scanner_loop() -> None:
    """不活跃账号扫描循环（在 FastAPI lifespan 中启动）。

    每小时扫描一次，将 3 天未登录前台用户的闲鱼账号录入排除表。
    用户在前台登录时会自动从排除表移出（由 UserAuthService 登录钩子处理）。
    """
    logger.info(
        "不活跃账号扫描循环已启动，间隔=%ds 不活跃阈值=%d天",
        SCANNER_INTERVAL_SECONDS, ACCOUNT_INACTIVE_DAYS,
    )
    # 启动后立即执行一次扫描，避免首次扫描需等待 1 小时
    try:
        await scan_and_exclude_inactive_accounts()
    except Exception as e:
        log_service_failure(
            logger, e, operation="initial_inactive_account_scan",
            level=logging.WARNING,
        )
    while True:
        try:
            await asyncio.sleep(SCANNER_INTERVAL_SECONDS)
            await scan_and_exclude_inactive_accounts()
        except asyncio.CancelledError:
            logger.info("不活跃账号扫描循环已停止")
            break
        except Exception as e:
            log_service_failure(
                logger, e, operation="inactive_account_scanner_loop",
                level=logging.WARNING,
            )
            # 出错后短暂等待，避免紧密循环
            await asyncio.sleep(60)
