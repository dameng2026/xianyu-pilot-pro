"""
滑块求解优先级队列管理器
========================
替换原有的全局 asyncio.Lock 串行化方案，实现基于会员等级的优先级队列调度。

核心特性：
1. **优先级调度**：SVIP(2) > VIP(1) > 普通(0)，同优先级按入队时间 FIFO
2. **并发处理**：支持 N 个 worker 并发消费队列（默认 2，匹配 crawler-service 单租户并发上限）
3. **失败自动重试**：
   - slider_fail（滑块通过失败）→ 重新入队，最多重试 3 次
   - service_unavailable（服务不可用）→ 重新入队，最多重试 2 次
   - cookie_invalid（Cookie 失效）→ 不重试，通知用户重新扫码
   - account_inactive/account_disabled → 不重试
   - precheck_rejected → 不重试
4. **任务去重**：
   - 手动触发（manual/manual_retry）：60 秒冷却（限制用户频繁点击）+ 队列进程去重（检查 queued/retrying 状态避免重复求解）
   - 自动触发：队列进程去重（检查 queued/retrying 状态避免重复求解）
   - 排除表检查：3天未登录前台用户的闲鱼账号直接创建 precheck_rejected 记录但不入队
   - manual_retry 失败重试场景由调用方传 skip_dedup=True 跳过

设计说明：
- 使用 asyncio.PriorityQueue 实现优先级排序
- 任务以 (-priority, enqueued_at_seq, task_obj) 入队，保证高优先级先出、同优先级 FIFO
- worker 通过 asyncio.Semaphore 控制并发，避免并发浏览器画像爆炸
- 求解过程中更新 xianyu_captcha_solve_record 的 queued_at/started_at/finished_at 时间戳
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import text

from ..core.database import async_session
from ..core.failure_logging import log_service_failure

logger = logging.getLogger(__name__)

# ============================================================
# 配置常量
# ============================================================

# 并发 worker 数量：与 crawler-service MAX_BROWSER_CONCURRENCY=2 严格对齐
# 关键修复（2026-07-31 事故）：原值 4 远超 crawler-service 默认并发 2，导致
# 4 个 worker 同时调用 crawler-service 时，3-4 个 Chrome 实例争抢 Xvfb 资源，
# 浏览器崩溃率飙升（browserContext.newPage: Target page, context or browser has been closed）
# 降到 2 后，与 crawler-service BrowserSlot 严格匹配，避免资源争抢。
# 支持环境变量 SOLVE_WORKER_CONCURRENCY 覆盖（仅在线上紧急调整时使用）。
_default_worker_concurrency = int(os.environ.get("SOLVE_WORKER_CONCURRENCY", "2") or "2")
SOLVE_WORKER_CONCURRENCY = max(1, min(_default_worker_concurrency, 4))

# 同账号去重冷却时间（秒）：60 秒内同账号只入队一次（对齐产品设计"每分钟可主动求解一次"）
SOLVE_DEDUP_COOLDOWN_SEC = 60

# service_unavailable 冷却时间（秒）：hasLogin 服务不可用失败后，
# WS token_refresh 触发的自动求解在此冷却期内不再重复入队，避免高频循环
SERVICE_UNAVAILABLE_COOLDOWN_SEC = 60

# 最大重试次数（按失败原因分类）
# 注意：service_unavailable 已移除重试机制（原 2 次）
# 原因：hasLogin 接口风控返回 HAS_LOGIN_UNCONFIRMED 时，立即重试只会加剧风控，
# 且 WS 会自然重连触发新的求解，无需队列内重试。
# 失败后仅更新原记录为 precheck_rejected/fail，不创建新记录，不重新入队。
#
# 2026-07-29 新增 browser_crashed：浏览器崩溃/启动失败可重试 1 次
# 原因：浏览器崩溃是临时性资源问题（Page crashed / OOM / 进程竞争），
# 重试一次可能就成功（下次启动浏览器时资源已释放）。
# 仅重试 1 次（而非 slider_fail 的 3 次）避免记录数爆炸。
# 配合 captcha_backoff.py 的 skip_backoff=True，不累加指数退避。
MAX_RETRY_BY_REASON = {
    "slider_fail": 3,          # 滑块通过失败，可重试
    "timeout": 1,              # 超时，重试 1 次
    "browser_crashed": 1,      # 浏览器崩溃/启动失败，重试 1 次（临时性错误）
}

# 不可重试的失败原因（需人工介入或服务恢复后由 WS 自然重连触发）
NON_RETRYABLE_REASONS = {
    "cookie_invalid",
    "account_inactive",
    "account_disabled",
    "precheck_rejected",
    "service_unavailable",  # hasLogin 服务不可用：不重试，等 WS 下次自然重连触发
}


# ============================================================
# 辅助函数
# ============================================================

async def _notify_session_expired(account_id: int, tenant_id: int) -> None:
    """Cookie Session 过期后发送飞书通知（dispatch_notification 已在 solver 内触发）。

    这个函数补充发送飞书自建应用通知，确保用户能及时收到 Session 过期提醒。
    """
    import time as _time
    try:
        from .feishu_chat import notify_session_expired_via_feishu_app
        from .ws_client import _lookup_account_name_safe
        account_name = await _lookup_account_name_safe(tenant_id, account_id)
        asyncio.create_task(
            notify_session_expired_via_feishu_app(
                tenant_id=tenant_id,
                account_id=account_id,
                account_name=account_name,
            )
        )
        logger.info("已触发飞书自建应用通知 Session 过期 accountId=%d", account_id)
    except Exception as e:
        log_service_failure(
            logger, e, operation="notify_session_expired_feishu",
            tenant_id=tenant_id, account_id=account_id, level=logging.DEBUG,
        )


# ============================================================
# 数据结构
# ============================================================

@dataclass(order=True)
class SolveTask:
    """滑块求解任务（用于 PriorityQueue 排序）"""
    # 排序键：priority 取负值（值越大越优先），enqueued_seq 保证同优先级 FIFO
    sort_priority: int
    enqueued_seq: int
    # 实际任务数据（不参与排序）
    account_id: int = field(compare=False)
    tenant_id: int = field(compare=False)
    trigger_scene: str = field(default="manual", compare=False)
    open_reason: str = field(default="", compare=False)
    solve_reason: str = field(default="", compare=False)
    priority: int = field(default=0, compare=False)
    retry_count: int = field(default=0, compare=False)
    record_id: Optional[int] = field(default=None, compare=False)
    enqueued_at: float = field(default_factory=time.time, compare=False)


# ============================================================
# 优先级队列管理器
# ============================================================

class CaptchaQueueManager:
    """滑块求解优先级队列管理器（单例）"""

    def __init__(self):
        self._queue: asyncio.PriorityQueue[SolveTask] = asyncio.PriorityQueue()
        self._workers: list[asyncio.Task] = []
        self._started = False
        self._seq_counter = 0
        self._seq_lock = asyncio.Lock()
        # 同账号去重表：account_id -> 上次入队时间戳
        self._enqueued_ts: dict[int, float] = {}
        self._dedup_lock = asyncio.Lock()
        # 排队中任务跟踪表：record_id -> SolveTask（用于查询排队位置）
        # worker 取出任务时从此表移除
        self._pending_tasks: dict[int, SolveTask] = {}
        self._pending_lock = asyncio.Lock()
        # service_unavailable 冷却表：account_id -> 上次因服务不可用失败的时间戳
        # WS 重连触发 token_refresh 时检查此表，冷却期内（默认 10 分钟）不再重复入队
        # 原因：hasLogin 接口风控返回 HAS_LOGIN_UNCONFIRMED 时，立即重试只会加剧风控，
        # 等 WS 下次自然重连触发即可，无需高频重复入队
        self._service_unavailable_ts: dict[int, float] = {}

    async def _cleanup_orphaned_queued_records(self) -> int:
        """清理容器重启导致的孤儿 queued 记录。

        容器重启后内存队列丢失，旧容器中已入队但未处理的 queued 任务成为孤儿，
        永远不会被新容器的 worker 处理。此方法在 start() 中调用，
        将这些孤儿记录标记为 timeout/stale_terminated，避免前端误判"队列卡住"。

        判定条件：
        - status = 'queued'
        - created_at < NOW() - INTERVAL 1 MINUTE（排除刚入队正在被处理的任务）

        Returns:
            被清理的记录数
        """
        try:
            async with async_session() as db:
                # 1. 先查询孤儿记录详情（用于广播）
                rows = (await db.execute(
                    text(
                        """
                        SELECT id, account_id, tenant_id
                        FROM xianyu_captcha_solve_record
                        WHERE status = 'queued'
                          AND COALESCE(deleted, 0) = 0
                          AND created_at < DATE_SUB(NOW(), INTERVAL 1 MINUTE)
                        """
                    ),
                )).mappings().all()

                if not rows:
                    return 0

                # 2. 批量更新为 timeout/stale_terminated
                record_ids = [int(r["id"]) for r in rows]
                id_params = {f"rid{i}": rid for i, rid in enumerate(record_ids)}
                in_clause = ",".join(f":rid{i}" for i in range(len(record_ids)))
                await db.execute(
                    text(
                        f"""
                        UPDATE xianyu_captcha_solve_record
                        SET status = 'timeout',
                            result = 'stale_terminated',
                            failure_reason = 'stale_terminated',
                            error_message = CONCAT(COALESCE(error_message, ''),
                                '[系统清理] 容器重启后孤儿 queued 记录，已自动终止'),
                            finished_at = NOW(),
                            updated_at = NOW()
                        WHERE id IN ({in_clause})
                        """
                    ),
                    id_params,
                )
                await db.commit()

                affected = len(rows)
                logger.warning(
                    "孤儿 queued 记录清理：已将 %d 条 queued 孤儿记录标记为 timeout/stale_terminated",
                    affected,
                )

                # 3. 广播状态变更（让前端实时看到状态从 queued → timeout）
                try:
                    from .captcha_solve_record import _lookup_account_name
                    from .ws_sse import broadcaster
                    for r in rows:
                        account_id = int(r["account_id"])
                        tenant_id = int(r["tenant_id"])
                        record_id = int(r["id"])
                        account_name = await _lookup_account_name(tenant_id, account_id)
                        await broadcaster.broadcast(
                            tenant_id,
                            "captcha_solve",
                            {
                                "accountId": account_id,
                                "accountName": account_name,
                                "status": "timeout",
                                "result": "stale_terminated",
                                "engine": "Playwright",
                                "reason": "容器重启导致任务丢失，已自动终止",
                                "recordId": record_id,
                            },
                        )
                except Exception as e:
                    log_service_failure(
                        logger, e, operation="broadcast_orphan_cleanup",
                        level=logging.DEBUG,
                    )

                return affected
        except Exception as e:
            log_service_failure(
                logger, e, operation="cleanup_orphaned_queued_records",
                level=logging.WARNING,
            )
            return 0

    async def start(self) -> None:
        """启动 worker 协程（幂等，重复调用安全）。

        启动流程：
        1. 清理容器重启导致的孤儿 queued 记录（避免前端误判"队列卡住"）
        2. 启动 worker 协程消费内存队列
        """
        if self._started:
            return
        self._started = True

        # 1. 清理孤儿 queued 记录（容器重启前的旧任务，内存队列已丢失）
        orphan_count = await self._cleanup_orphaned_queued_records()
        if orphan_count > 0:
            logger.info("启动前清理孤儿 queued 记录 %d 条", orphan_count)

        # 2. 启动 worker 协程
        for i in range(SOLVE_WORKER_CONCURRENCY):
            task = asyncio.create_task(self._worker_loop(i))
            self._workers.append(task)
        logger.info(
            "滑块求解优先级队列已启动，worker 数=%d", SOLVE_WORKER_CONCURRENCY,
        )

    async def stop(self) -> None:
        """停止所有 worker"""
        if not self._started:
            return
        self._started = False
        for task in self._workers:
            task.cancel()
        for task in self._workers:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._workers.clear()
        logger.info("滑块求解优先级队列已停止")

    async def enqueue(
        self,
        account_id: int,
        tenant_id: int,
        trigger_scene: str = "manual",
        open_reason: str = "",
        solve_reason: str = "",
        priority: int = 0,
        retry_count: int = 0,
        skip_dedup: bool = False,
    ) -> tuple[Optional[int], int, int]:
        """入队一个滑块求解任务。

        Args:
            account_id: 账号 ID
            tenant_id: 租户 ID
            trigger_scene: 触发场景
            open_reason: 开启原因
            solve_reason: 求解原因
            priority: 优先级（2=SVIP, 1=VIP, 0=普通）
            retry_count: 重试次数（首次入队为 0）
            skip_dedup: 是否跳过 60 秒冷却检查（重试入队时传 True）。
                注意：skip_dedup=True 仅跳过手动触发的 60 秒冷却，
                队列进程去重（queued/retrying 状态检查）仍会执行，避免重试场景重复求解

        Returns:
            (record_id, queue_position, queue_total)
            - 入队成功：record_id 为 int，queue_position/queue_total 为入队瞬间的排队位置
            - 被去重跳过：record_id 为 None，queue_position/queue_total 为 0

        注意：位置信息在入队瞬间计算（持 _pending_lock），避免 worker 在 broadcast
        期间取出任务导致后续查询返回 (0, 0)。调用方应直接使用返回的位置信息，
        不要再调用 get_queue_position 二次查询（此时 worker 可能已取出任务）。
        """
        # === 0. service_unavailable 冷却检查（仅 token_refresh 场景） ===
        # hasLogin 接口风控返回 HAS_LOGIN_UNCONFIRMED 后，短期内不会恢复，
        # WS 会自然重连触发新的求解，无需高频重复入队。
        # 手动触发（manual/manual_retry）不受此限制，用户主动点击应立即处理。
        if trigger_scene == "token_refresh":
            last_fail_ts = self._service_unavailable_ts.get(account_id, 0)
            if last_fail_ts and (time.time() - last_fail_ts) < SERVICE_UNAVAILABLE_COOLDOWN_SEC:
                remaining = int(SERVICE_UNAVAILABLE_COOLDOWN_SEC - (time.time() - last_fail_ts))
                logger.info(
                    "滑块求解入队跳过：service_unavailable 冷却中 accountId=%d 剩余 %d 秒",
                    account_id, remaining,
                )
                return (None, 0, 0)

        # === 0.5 指数退避冷却检查（自动触发场景，避免记录爆炸） ===
        # 关键修复：之前在指数退避冷却期间，WS 每次重连都触发 enqueue_solve 入队，
        # worker 取出后又被 assert_auto_solve_allowed 拦截，标记为 precheck_rejected，
        # 创建一条失败记录。30秒间隔的WS重连一天可产生数百条无意义的失败记录，
        # 严重拉低成功率统计并污染数据库。
        # 自动触发场景（token_refresh/ws_health_check/ws_connect）在冷却期内直接跳过入队，
        # 不创建记录，不占用 worker 资源。
        # 手动触发场景（manual/manual_retry）跳过此检查，确保用户主动求解不被拦截。
        if trigger_scene not in ("manual", "manual_retry"):
            try:
                # 函数内 import 避免循环依赖
                from .captcha_backoff import get_backoff_status
                backoff_st = await get_backoff_status(account_id, tenant_id)
                if not backoff_st.get("allowed", True):
                    remaining = int(backoff_st.get("remainingSec", 0))
                    fail_count = int(backoff_st.get("failCount", 0))
                    logger.info(
                        "滑块求解入队跳过：指数退避冷却中 accountId=%d scene=%s "
                        "剩余 %d 秒 failCount=%d",
                        account_id, trigger_scene, remaining, fail_count,
                    )
                    return (None, 0, 0)
            except Exception as e:
                # 退避检查失败时降级为放行（fail-open），不影响正常流程
                log_service_failure(
                    logger, e, operation="backoff_check_enqueue",
                    tenant_id=tenant_id, account_id=account_id, level=logging.DEBUG,
                )

        # === 1. 排除表检查（所有场景，硬阻断，静默跳过不创建记录） ===
        # 3 天未登录前台用户的闲鱼账号已被定时扫描录入排除表，直接拒绝入队
        # 避免脏数据占用排队序列（排除表本身即为记录，不额外创建 solve_record）
        try:
            async with async_session() as db:
                exclusion_row = (await db.execute(
                    text(
                        "SELECT id FROM xianyu_account_solve_exclusion "
                        "WHERE account_id = :aid LIMIT 1"
                    ),
                    {"aid": account_id},
                )).mappings().first()
            if exclusion_row:
                logger.info(
                    "滑块求解入队排除：账号在排除表中 accountId=%d（用户3天未登录前台），静默跳过",
                    account_id,
                )
                return (None, 0, 0)
        except Exception as e:
            # 排除表不存在或查询失败时降级为放行（不影响正常流程）
            log_service_failure(
                logger, e, operation="exclusion_table_check_enqueue",
                level=logging.DEBUG,
            )

        # === 2. 队列进程去重（所有场景都检查，包括 skip_dedup=True 的重试场景） ===
        # 避免同账号重复入队：检查 queued（内存队列）和 retrying（DB）状态
        # 2a. 检查内存队列 _pending_tasks（queued 状态）
        async with self._pending_lock:
            for task in self._pending_tasks.values():
                if task.account_id == account_id:
                    logger.info(
                        "滑块求解入队去重跳过 accountId=%d（队列中已有排队任务 recordId=%d）",
                        account_id, task.record_id,
                    )
                    return (None, 0, 0)
        # 2b. 检查 DB 中是否有 retrying 状态的同账号任务（worker 正在处理）
        try:
            async with async_session() as db:
                row = (await db.execute(
                    text(
                        "SELECT id FROM xianyu_captcha_solve_record "
                        "WHERE account_id = :aid AND status = 'retrying' "
                        "AND COALESCE(deleted, 0) = 0 LIMIT 1"
                    ),
                    {"aid": account_id},
                )).mappings().first()
                if row:
                    logger.info(
                        "滑块求解入队去重跳过 accountId=%d（已有求解中任务 recordId=%s）",
                        account_id, row["id"],
                    )
                    return (None, 0, 0)
        except Exception as e:
            log_service_failure(
                logger, e, operation="dedup_check_retrying",
                level=logging.WARNING,
            )

        # === 3. 手动触发 60 秒冷却（仅 manual/manual_retry 且非 skip_dedup） ===
        # 60 秒冷却仅限制用户前台频繁点击，不影响重试场景
        # 重试场景（skip_dedup=True）已通过上方队列进程去重保证不重复求解
        if not skip_dedup and trigger_scene in ("manual", "manual_retry"):
            async with self._dedup_lock:
                last_ts = self._enqueued_ts.get(account_id, 0)
                now_ts = time.time()
                if now_ts - last_ts < SOLVE_DEDUP_COOLDOWN_SEC:
                    logger.info(
                        "滑块求解入队去重跳过 accountId=%d（%d 秒前刚入队，冷却需 >= %d 秒）",
                        account_id, int(now_ts - last_ts), SOLVE_DEDUP_COOLDOWN_SEC,
                    )
                    return (None, 0, 0)
                self._enqueued_ts[account_id] = now_ts

        # 生成序列号保证同优先级 FIFO
        async with self._seq_lock:
            self._seq_counter += 1
            seq = self._seq_counter

        # 创建求解记录
        from .captcha_solve_record import create_solve_record
        record_id = await create_solve_record(
            account_id=account_id,
            tenant_id=tenant_id,
            trigger_scene=trigger_scene,
            open_reason=open_reason,
            solve_reason=solve_reason,
            retry_count=retry_count,
        )

        # 更新记录的优先级和入队时间
        if record_id:
            try:
                async with async_session() as db:
                    await db.execute(
                        text(
                            "UPDATE xianyu_captcha_solve_record "
                            "SET priority = :pri, queued_at = NOW() WHERE id = :rid"
                        ),
                        {"pri": priority, "rid": record_id},
                    )
                    await db.commit()
            except Exception as e:
                log_service_failure(
                    logger, e, operation="update_solve_record_queued",
                    level=logging.WARNING,
                )

        # 入队（priority 取负值，值越大越优先出队）
        task = SolveTask(
            sort_priority=-priority,
            enqueued_seq=seq,
            account_id=account_id,
            tenant_id=tenant_id,
            trigger_scene=trigger_scene,
            open_reason=open_reason,
            solve_reason=solve_reason,
            priority=priority,
            retry_count=retry_count,
            record_id=record_id,
            enqueued_at=time.time(),
        )
        # 加入排队跟踪表并在持锁状态下计算排队位置（原子操作）。
        # 关键：必须在持锁状态下计算位置，避免以下竞态：
        #   1. put 入队后 worker 被 await 唤醒取出任务
        #   2. worker 从 _pending_tasks 移除该 record
        #   3. enqueue 后续 get_queue_position 查不到任务返回 (0, 0)
        # 持锁期间 worker 的 _process_task 会等待锁，无法在加入 _pending_tasks
        # 与计算位置之间插入 pop 操作。
        queue_position = 0
        queue_total = 0
        if record_id:
            async with self._pending_lock:
                self._pending_tasks[record_id] = task
                # 在持锁状态下直接计算位置（不调用 get_queue_position 以避免重入锁）
                pending = list(self._pending_tasks.values())
                pending.sort(key=lambda t: (t.sort_priority, t.enqueued_seq))
                queue_total = len(pending)
                for i, t in enumerate(pending):
                    if t.record_id == record_id:
                        queue_position = i + 1
                        break

        # put 到队列（让 worker 可以取出）。此时位置已计算完毕，即使 worker
        # 立即取出任务，返回给调用方的位置信息仍是正确的入队瞬间位置。
        await self._queue.put(task)

        # 广播 queued 状态（让前端即时看到"排队中"）
        try:
            from .captcha_solve_record import broadcast_captcha_solve, _lookup_account_name
            from .ws_sse import broadcaster
            account_name = await _lookup_account_name(tenant_id, account_id)
            await broadcaster.broadcast(
                tenant_id,
                "captcha_solve",
                {
                    "accountId": account_id,
                    "accountName": account_name,
                    "status": "queued",
                    "result": "",
                    "engine": "Playwright",
                    "reason": f"任务已入队，排队中（第 {queue_position} 位，共 {queue_total} 个任务）",
                    "recordId": record_id,
                    "queuePosition": queue_position,
                    "queueTotal": queue_total,
                },
            )
        except Exception as e:
            log_service_failure(
                logger, e, operation="broadcast_queued_status",
                tenant_id=tenant_id, account_id=account_id, level=logging.DEBUG,
            )

        logger.info(
            "滑块求解任务已入队 accountId=%d tenantId=%d priority=%d scene=%s retry=%d recordId=%s 队列长度=%d 排队位置=%d/%d",
            account_id, tenant_id, priority, trigger_scene, retry_count,
            record_id, self._queue.qsize(), queue_position, queue_total,
        )
        return (record_id, queue_position, queue_total)

    async def _worker_loop(self, worker_id: int) -> None:
        """worker 协程主循环：从队列取出任务并处理"""
        logger.info("滑块求解 worker #%d 已启动", worker_id)
        while self._started:
            try:
                task = await self._queue.get()
                try:
                    await self._process_task(task, worker_id)
                except Exception as e:
                    log_service_failure(
                        logger, e, operation=f"solve_worker_{worker_id}",
                        tenant_id=task.tenant_id, account_id=task.account_id,
                    )
                finally:
                    self._queue.task_done()
            except asyncio.CancelledError:
                logger.info("滑块求解 worker #%d 已取消", worker_id)
                break
        logger.info("滑块求解 worker #%d 已退出", worker_id)

    async def _process_task(self, task: SolveTask, worker_id: int) -> None:
        """处理单个求解任务"""
        from .captcha_solver import handle_captcha_for_account
        from .captcha_solve_record import update_solve_record, broadcast_captcha_solve, _lookup_account_name

        logger.info(
            "worker #%d 开始处理滑块求解 accountId=%d priority=%d retry=%d recordId=%s",
            worker_id, task.account_id, task.priority, task.retry_count, task.record_id,
        )

        # 从排队跟踪表移除（已开始处理，不再排队）
        if task.record_id:
            async with self._pending_lock:
                self._pending_tasks.pop(task.record_id, None)

        # 更新记录 started_at + 状态从 queued → retrying（正式开始处理）
        if task.record_id:
            try:
                async with async_session() as db:
                    await db.execute(
                        text(
                            "UPDATE xianyu_captcha_solve_record "
                            "SET started_at = NOW(), status = 'retrying' WHERE id = :rid"
                        ),
                        {"rid": task.record_id},
                    )
                    await db.commit()
            except Exception as e:
                log_service_failure(
                    logger, e, operation="update_solve_record_started",
                    level=logging.WARNING,
                )
            # 广播 retrying 状态（让前端知道已从"排队中"变为"求解中"）
            try:
                from .ws_sse import broadcaster
                account_name = await _lookup_account_name(task.tenant_id, task.account_id)
                await broadcaster.broadcast(
                    task.tenant_id,
                    "captcha_solve",
                    {
                        "accountId": task.account_id,
                        "accountName": account_name,
                        "status": "retrying",
                        "result": "",
                        "engine": "Playwright",
                        "reason": "worker 已取出任务，开始处理滑块求解",
                        "recordId": task.record_id,
                    },
                )
            except Exception as e:
                log_service_failure(
                    logger, e, operation="broadcast_retrying_status",
                    tenant_id=task.tenant_id, account_id=task.account_id, level=logging.DEBUG,
                )

        # 执行求解（handle_captcha_for_account 内部已包含预校验逻辑）
        try:
            result = await handle_captcha_for_account(
                account_id=task.account_id,
                tenant_id=task.tenant_id,
                response=None,
                auto_solve=True,
                trigger_scene=task.trigger_scene,
                open_reason=task.open_reason,
                solve_reason=task.solve_reason,
                record_id=task.record_id,  # 复用已创建的记录
                priority=task.priority,
            )
        except Exception as e:
            log_service_failure(
                logger, e, operation="process_solve_task",
                tenant_id=task.tenant_id, account_id=task.account_id,
            )
            result = {
                "autoSolveResult": {"success": False, "error": str(e)},
                "recovered": False,
                "failureReason": "service_unavailable",
            }

        # 更新记录 finished_at
        if task.record_id:
            try:
                async with async_session() as db:
                    await db.execute(
                        text(
                            "UPDATE xianyu_captcha_solve_record "
                            "SET finished_at = NOW() WHERE id = :rid"
                        ),
                        {"rid": task.record_id},
                    )
                    await db.commit()
            except Exception as e:
                log_service_failure(
                    logger, e, operation="update_solve_record_finished",
                    level=logging.WARNING,
                )

        # 失败重试判断
        auto_solve_result = result.get("autoSolveResult") or {}
        failure_reason = result.get("failureReason") or auto_solve_result.get("failureReason") or ""

        if result.get("recovered"):
            logger.info(
                "滑块求解成功，无需重试 accountId=%d recordId=%s",
                task.account_id, task.record_id,
            )
            # === 求解成功：清除 service_unavailable 冷却 ===
            # 下次失败重新计数，避免一次失败后 10 分钟内即使恢复也无法自动求解
            self._service_unavailable_ts.pop(task.account_id, None)
            # === 求解成功后的后处理：对自动触发场景立即重启 WS 连接 ===
            # handle_captcha_for_account 已恢复 cookie_status=1 并刷新 _m_h5_tk，
            # 这里立即触发 WS 重连，避免等待下一次重连周期
            if task.trigger_scene in ("token_refresh", "cookie_keepalive"):
                try:
                    from .ws_client import ws_manager
                    asyncio.create_task(ws_manager.restart_account(task.account_id))
                    logger.info(
                        "滑块求解成功后已触发 WS 重连 accountId=%d scene=%s",
                        task.account_id, task.trigger_scene,
                    )
                except Exception as e:
                    log_service_failure(
                        logger, e, operation="restart_ws_after_solve_success",
                        tenant_id=task.tenant_id, account_id=task.account_id,
                        level=logging.WARNING,
                    )
            return

        # 判断是否可重试
        if not failure_reason:
            # 没有明确的失败原因，但也没成功，按滑块失败处理
            failure_reason = "slider_fail"

        if failure_reason in NON_RETRYABLE_REASONS:
            logger.info(
                "滑块求解失败且不可重试 accountId=%d reason=%s recordId=%s",
                task.account_id, failure_reason, task.record_id,
            )
            # === service_unavailable 冷却：记录失败时间戳，10 分钟内 token_refresh 不再入队 ===
            # hasLogin 接口风控返回 HAS_LOGIN_UNCONFIRMED 后，立即重试只会加剧风控
            if failure_reason == "service_unavailable":
                self._service_unavailable_ts[task.account_id] = time.time()
                logger.info(
                    "已记录 service_unavailable 冷却 accountId=%d 冷却 %d 秒",
                    task.account_id, SERVICE_UNAVAILABLE_COOLDOWN_SEC,
                )
            # === Cookie 失效后处理：对自动触发场景发送 Session 过期通知 ===
            # handle_captcha_for_account 已更新 cookie_status=0 并断开 WS，
            # 这里补充发送飞书通知（dispatch_notification 已在 solver 内触发）
            if failure_reason == "cookie_invalid" and task.trigger_scene in ("token_refresh", "cookie_keepalive"):
                try:
                    await _notify_session_expired(task.account_id, task.tenant_id)
                except Exception as e:
                    log_service_failure(
                        logger, e, operation="notify_session_expired_from_queue",
                        tenant_id=task.tenant_id, account_id=task.account_id,
                        level=logging.DEBUG,
                    )
            return

        max_retry = MAX_RETRY_BY_REASON.get(failure_reason, 0)
        if task.retry_count >= max_retry:
            logger.info(
                "滑块求解失败且已达最大重试次数 accountId=%d reason=%s retry=%d/%d recordId=%s",
                task.account_id, failure_reason, task.retry_count, max_retry, task.record_id,
            )
            return

        # 重新入队重试
        retry_count = task.retry_count + 1
        logger.info(
            "滑块求解失败，重新入队重试 accountId=%d reason=%s retry=%d/%d recordId=%s",
            task.account_id, failure_reason, retry_count, max_retry, task.record_id,
        )

        # 更新原记录的 failure_reason
        if task.record_id:
            try:
                async with async_session() as db:
                    await db.execute(
                        text(
                            "UPDATE xianyu_captcha_solve_record "
                            "SET failure_reason = :fr WHERE id = :rid"
                        ),
                        {"fr": failure_reason, "rid": task.record_id},
                    )
                    await db.commit()
            except Exception as e:
                log_service_failure(
                    logger, e, operation="update_solve_record_failure_reason",
                    level=logging.WARNING,
                )

        # 重新入队（跳过去重，因为是重试）
        await self.enqueue(
            account_id=task.account_id,
            tenant_id=task.tenant_id,
            trigger_scene=task.trigger_scene,
            open_reason=f"自动重试（第 {retry_count} 次，原因：{failure_reason}）",
            solve_reason=task.solve_reason,
            priority=task.priority,
            retry_count=retry_count,
            skip_dedup=True,
        )

    async def get_queue_position(self, record_id: Optional[int]) -> tuple[int, int]:
        """查询指定记录在队列中的排队位置。

        排队位置按优先级排序计算：高优先级（sort_priority 更小）排前面，
        同优先级按入队顺序（enqueued_seq）FIFO。

        Args:
            record_id: 求解记录 ID

        Returns:
            (position, total) - position 从 1 开始（1=下一个出队），total=排队中总数
            若 record_id 不在排队表中（已被 worker 取出或不存在），返回 (0, total)
        """
        if not record_id:
            return (0, 0)
        async with self._pending_lock:
            pending = list(self._pending_tasks.values())
        if not pending:
            return (0, 0)
        # 按 (sort_priority, enqueued_seq) 排序，与 PriorityQueue 出队顺序一致
        pending.sort(key=lambda t: (t.sort_priority, t.enqueued_seq))
        total = len(pending)
        for i, t in enumerate(pending):
            if t.record_id == record_id:
                return (i + 1, total)
        return (0, total)

    @property
    def queue_size(self) -> int:
        """当前队列长度"""
        return self._queue.qsize()


# ============================================================
# 全局单例
# ============================================================

_queue_manager: Optional[CaptchaQueueManager] = None
_queue_manager_lock = asyncio.Lock()


async def get_queue_manager() -> CaptchaQueueManager:
    """获取全局队列管理器单例（惰性初始化 + 自动启动 worker）"""
    global _queue_manager
    if _queue_manager is not None:
        return _queue_manager
    async with _queue_manager_lock:
        if _queue_manager is None:
            _queue_manager = CaptchaQueueManager()
            await _queue_manager.start()
    return _queue_manager


async def stop_queue_manager() -> None:
    """停止全局队列管理器（应用关闭时调用）"""
    global _queue_manager
    if _queue_manager is not None:
        await _queue_manager.stop()
        _queue_manager = None


async def enqueue_solve(
    account_id: int,
    tenant_id: int,
    trigger_scene: str = "manual",
    open_reason: str = "",
    solve_reason: str = "",
    priority: int = 0,
    retry_count: int = 0,
    skip_dedup: bool = False,
) -> Optional[int]:
    """便捷接口：入队一个滑块求解任务（仅返回 record_id）。

    向后兼容包装：解包 manager.enqueue 返回的 (record_id, position, total) 元组，
    仅返回 record_id。需要排队位置信息的调用方请使用 enqueue_solve_with_position。

    Args:
        retry_count: 重试次数（首次入队为 0，超时自动重试时传入递增后的值）
        skip_dedup: 是否跳过 60 秒冷却检查（manual_retry 失败重试场景传 True，
            对齐前端"失败后可立即重试"设计；前端已保证重试仅在 status=fail 时触发、
            求解中不可重复点击，不会导致滥用）。
            注意：skip_dedup=True 仅跳过 60 秒冷却，队列进程去重（queued/retrying 检查）
            仍会执行，避免同账号重复求解

    Returns:
        record_id 或 None（被去重跳过）
    """
    manager = await get_queue_manager()
    record_id, _position, _total = await manager.enqueue(
        account_id=account_id,
        tenant_id=tenant_id,
        trigger_scene=trigger_scene,
        open_reason=open_reason,
        solve_reason=solve_reason,
        priority=priority,
        retry_count=retry_count,
        skip_dedup=skip_dedup,
    )
    return record_id


async def enqueue_solve_with_position(
    account_id: int,
    tenant_id: int,
    trigger_scene: str = "manual",
    open_reason: str = "",
    solve_reason: str = "",
    priority: int = 0,
    retry_count: int = 0,
    skip_dedup: bool = False,
) -> Optional[tuple[int, int, int]]:
    """便捷接口：入队一个滑块求解任务，返回排队位置信息。

    与 enqueue_solve 的区别：返回 (record_id, queue_position, queue_total) 而非仅 record_id。
    用于 HTTP 路由层（handle_captcha / auto_solve_captcha）直接获取入队瞬间的排队位置，
    避免入队后二次调用 get_queue_position 时因 worker 已取出任务而返回 (0, 0)。

    Returns:
        (record_id, queue_position, queue_total) 或 None（被去重跳过）
        - queue_position: 入队瞬间的排队位置（1=下一个出队）
        - queue_total: 入队瞬间的排队中总数
    """
    manager = await get_queue_manager()
    record_id, position, total = await manager.enqueue(
        account_id=account_id,
        tenant_id=tenant_id,
        trigger_scene=trigger_scene,
        open_reason=open_reason,
        solve_reason=solve_reason,
        priority=priority,
        retry_count=retry_count,
        skip_dedup=skip_dedup,
    )
    if record_id is None:
        return None
    return (record_id, position, total)


async def get_queue_position(record_id: Optional[int]) -> tuple[int, int]:
    """便捷接口：查询指定记录的排队位置。

    Returns:
        (position, total) - position 从 1 开始，total=排队中总数
        若 record_id 已被 worker 取出（不在排队中），返回 (0, total)
    """
    manager = await get_queue_manager()
    return await manager.get_queue_position(record_id)
