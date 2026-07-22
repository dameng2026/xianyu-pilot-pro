/**
 * 滑块求解进程注册表与监测器
 *
 * 设计目标：
 * 1. 跟踪每个滑块求解会话产生的子进程（Python 脚本、Chrome 持久化上下文、Chromium 回退）
 * 2. 定期扫描注册表，清理"长期无响应"或"已结束但句柄未释放"的进程
 * 3. 安全策略：只清理本服务注册的 PID，绝不杀系统进程或他人进程
 *
 * 安全策略要点（违反即为 Bug）：
 * - PID 必须在注册表中才会被清理（不杀未注册进程）
 * - 必须超过 deadlineAt + gracePeriodMs 才清理（给正在运行的进程足够时间）
 * - 优先 SIGTERM，5 秒后再 SIGKILL（优雅退出）
 * - 不杀 PID < 100 的进程（系统进程保护）
 * - 每次清理决策都记录日志，便于审计
 */

export type ProcessKind = 'python' | 'chrome-persistent' | 'chromium';

export interface RegisteredProcess {
  /** 会话 ID（一次 solveGoofishSlider 调用对应一个 sessionId） */
  sessionId: string;
  /** 进程类型 */
  kind: ProcessKind;
  /** 主进程 PID */
  pid: number;
  /** 关联的子进程 PID（Chrome 的 renderer/zygote 等） */
  childPids: number[];
  /** userDataDir（仅 chrome-persistent 有值，用于精确清理） */
  userDataDir?: string;
  /** 租户 ID（用于按租户清理） */
  tenantId: string;
  /** 启动时间（ms timestamp） */
  startedAt: number;
  /** 截止时间（ms timestamp），超过此时间视为超时 */
  deadlineAt: number;
  /** 最后活动时间（ms timestamp），由 heartbeat 更新 */
  lastActivityAt: number;
  /** 关联的 ChildProcess（可选，用于直接 kill） */
  childProcess?: { kill: (signal?: NodeJS.Signals | number) => boolean };
  /** 描述（用于日志和健康端点） */
  description: string;
}

export interface ProcessCleanupAction {
  sessionId: string;
  pid: number;
  reason: 'stale-deadline-exceeded' | 'process-exited' | 'manual-cleanup';
  /** 触发清理时的存活时长（ms） */
  ageMs: number;
  /** 超时多久（ms，仅 stale-deadline-exceeded 有值） */
  overdueMs?: number;
  /** 清理结果 */
  result: 'sigterm-sent' | 'sigkill-sent' | 'already-exited' | 'pid-too-low' | 'kill-failed';
  /** 时间戳 */
  timestamp: number;
}

/**
 * 判断进程是否存活（不发送实际信号）
 *
 * process.kill(pid, 0) 在进程存在时返回 true，不存在时抛出 Error。
 * 注意：在 Linux 下，即使进程是僵尸态（Z 状态），kill(pid, 0) 仍会返回 true，
 * 因为僵尸进程的 PID 还在内核 task list 中。但僵尸进程不占用内存（除 task struct），
 * 不需要清理；真正需要清理的是"运行中但无响应"和"已结束但 waitpid 未调用"两种。
 */
export function isProcessAlive(pid: number): boolean {
  if (!Number.isSafeInteger(pid) || pid <= 0) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (e: any) {
    // ESRCH = 进程不存在；EPERM = 权限不足（视为存活，避免误判）
    return e?.code === 'EPERM';
  }
}

/**
 * 进程注册表
 *
 * 所有方法都是线程安全的（Node 单线程，无需锁）。
 * 注册表只在内存中，进程重启后清空（重启时残留进程由 server.ts 的 OrphanCleaner 兜底）。
 */
class ProcessRegistryImpl {
  private entries = new Map<string, RegisteredProcess>();
  private pidToSessionId = new Map<number, string>();
  private cleanupLog: ProcessCleanupAction[] = [];
  private readonly maxLogSize = 200;

  /**
   * 注册一个求解会话的进程
   *
   * @returns sessionId，用于后续 heartbeat / unregister
   */
  register(input: Omit<RegisteredProcess, 'lastActivityAt'>): string {
    const entry: RegisteredProcess = {
      ...input,
      lastActivityAt: Date.now(),
    };
    this.entries.set(entry.sessionId, entry);
    this.pidToSessionId.set(entry.pid, entry.sessionId);
    for (const childPid of entry.childPids) {
      this.pidToSessionId.set(childPid, entry.sessionId);
    }
    return entry.sessionId;
  }

  /**
   * 注销一个求解会话（不杀进程，仅从注册表移除）
   *
   * 调用方应在 finally 块中调用此方法，即使进程已经被杀。
   */
  unregister(sessionId: string): void {
    const entry = this.entries.get(sessionId);
    if (!entry) return;
    this.pidToSessionId.delete(entry.pid);
    for (const childPid of entry.childPids) {
      this.pidToSessionId.delete(childPid);
    }
    this.entries.delete(sessionId);
  }

  /**
   * 更新会话的最后活动时间（heartbeat）
   *
   * 调用方在子进程产生 stdout/stderr 数据时调用，表示进程仍在工作。
   * 进程长时间无 heartbeat 且超过 deadline 视为无响应。
   */
  heartbeat(sessionId: string): void {
    const entry = this.entries.get(sessionId);
    if (entry) entry.lastActivityAt = Date.now();
  }

  /**
   * 追加子进程 PID（Chrome 启动后可能 fork 多个子进程）
   */
  addChildPid(sessionId: string, pid: number): void {
    const entry = this.entries.get(sessionId);
    if (!entry || !Number.isSafeInteger(pid) || pid <= 0) return;
    if (!entry.childPids.includes(pid)) {
      entry.childPids.push(pid);
      this.pidToSessionId.set(pid, sessionId);
    }
  }

  /**
   * 获取所有注册的进程（用于健康端点和监测器）
   */
  list(): RegisteredProcess[] {
    return Array.from(this.entries.values());
  }

  /**
   * 按 sessionId 获取
   */
  get(sessionId: string): RegisteredProcess | undefined {
    return this.entries.get(sessionId);
  }

  /**
   * 获取最近的清理动作日志（用于健康端点审计）
   */
  getCleanupLog(): ProcessCleanupAction[] {
    return [...this.cleanupLog];
  }

  /**
   * 记录清理动作
   */
  recordCleanup(action: ProcessCleanupAction): void {
    this.cleanupLog.push(action);
    if (this.cleanupLog.length > this.maxLogSize) {
      this.cleanupLog.splice(0, this.cleanupLog.length - this.maxLogSize);
    }
  }

  /**
   * 清空注册表（仅在测试或关闭时使用）
   */
  clear(): void {
    this.entries.clear();
    this.pidToSessionId.clear();
  }
}

export const processRegistry = new ProcessRegistryImpl();

// ============================================================
// 进程监测器
// ============================================================

export interface MonitorOptions {
  /** 扫描间隔（ms），默认 30 秒 */
  scanIntervalMs?: number;
  /** 超时宽限期（ms），超过 deadline + 此时间才清理，默认 30 秒 */
  gracePeriodMs?: number;
  /** SIGTERM 后等待 SIGKILL 的时间（ms），默认 5 秒 */
  sigkillDelayMs?: number;
  /** 系统进程保护阈值，PID 小于此值的进程不清理，默认 100 */
  systemPidFloor?: number;
  /** 日志回调，默认 console.log */
  log?: (msg: string) => void;
}

/**
 * 进程监测器
 *
 * 定期扫描注册表，清理以下三类进程：
 * 1. process-exited：进程已退出，从注册表注销
 * 2. stale-deadline-exceeded：进程超过 deadline + grace 仍存活，视为无响应，清理
 *
 * 安全策略：
 * - 只清理注册表中的 PID（不杀未注册进程）
 * - PID < systemPidFloor 不清理（保护系统进程）
 * - 优先 SIGTERM，等待 sigkillDelayMs 后再 SIGKILL
 * - 所有清理动作记录到 cleanupLog，可审计
 */
export class ProcessMonitor {
  private timer: NodeJS.Timeout | undefined;
  private readonly opts: Required<MonitorOptions>;

  constructor(options: MonitorOptions = {}) {
    this.opts = {
      scanIntervalMs: options.scanIntervalMs ?? 30_000,
      gracePeriodMs: options.gracePeriodMs ?? 30_000,
      sigkillDelayMs: options.sigkillDelayMs ?? 5_000,
      systemPidFloor: options.systemPidFloor ?? 100,
      log: options.log ?? ((msg: string) => console.log(msg)),
    };
  }

  start(): void {
    if (this.timer) return;
    this.timer = setInterval(() => this.scan(), this.opts.scanIntervalMs);
    this.timer.unref();
    this.opts.log(`[ProcessMonitor] 已启动，扫描间隔=${this.opts.scanIntervalMs}ms 宽限期=${this.opts.gracePeriodMs}ms`);
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = undefined;
      this.opts.log('[ProcessMonitor] 已停止');
    }
  }

  /**
   * 扫描一次注册表，清理超时和已退出的进程
   *
   * @returns 本次扫描执行的清理动作
   */
  async scan(): Promise<ProcessCleanupAction[]> {
    const now = Date.now();
    const actions: ProcessCleanupAction[] = [];
    const entries = processRegistry.list();

    for (const entry of entries) {
      // pid=0 的条目（如 Chrome launchPersistentContext，主 PID 不可知）：
      // 跳过存活检测，只按 deadline + userDataDir 清理
      const isLogicalSession = entry.pid === 0;

      // 1. 检查主进程是否已退出（仅对有真实 PID 的条目）
      if (!isLogicalSession) {
        const mainAlive = isProcessAlive(entry.pid);
        const childAlive = entry.childPids.some((p) => isProcessAlive(p));

        if (!mainAlive && !childAlive) {
          // 进程已退出，注销即可
          const action: ProcessCleanupAction = {
            sessionId: entry.sessionId,
            pid: entry.pid,
            reason: 'process-exited',
            ageMs: now - entry.startedAt,
            result: 'already-exited',
            timestamp: now,
          };
          actions.push(action);
          processRegistry.recordCleanup(action);
          processRegistry.unregister(entry.sessionId);
          this.opts.log(`[ProcessMonitor] 会话 ${entry.sessionId} (pid=${entry.pid}, kind=${entry.kind}) 已退出，注销`);
          continue;
        }
      }

      // 2. 检查是否超过 deadline + grace
      const overdueMs = now - entry.deadlineAt;
      if (overdueMs < this.opts.gracePeriodMs) {
        // 还在宽限期内，跳过
        continue;
      }

      // 3. 超过 deadline + grace，视为无响应，清理
      this.opts.log(
        `[ProcessMonitor] 会话 ${entry.sessionId} (pid=${entry.pid || 'N/A'}, kind=${entry.kind}) 超时 ${overdueMs}ms，开始清理`,
      );

      if (isLogicalSession) {
        // 逻辑会话（Chrome launchPersistentContext）：按 userDataDir 用 pkill 清理
        if (entry.userDataDir) {
          await this.cleanupByUserDataDir(entry.userDataDir, entry.sessionId);
        }
        const action: ProcessCleanupAction = {
          sessionId: entry.sessionId,
          pid: 0,
          reason: 'stale-deadline-exceeded',
          ageMs: now - entry.startedAt,
          overdueMs,
          result: 'sigkill-sent',
          timestamp: now,
        };
        actions.push(action);
        processRegistry.recordCleanup(action);
      } else {
        // 真实 PID 会话：收集所有需要清理的 PID（主进程 + 子进程，过滤系统进程）
        const pidsToKill = [entry.pid, ...entry.childPids].filter(
          (p) => Number.isSafeInteger(p) && p >= this.opts.systemPidFloor,
        );

        // 4. 先 SIGTERM 所有可能存活的 PID
        const termResults = await this.sendSignalToPids(pidsToKill, 'SIGTERM', entry);
        for (let i = 0; i < pidsToKill.length; i++) {
          const pid = pidsToKill[i];
          const result = termResults[i];
          const action: ProcessCleanupAction = {
            sessionId: entry.sessionId,
            pid,
            reason: 'stale-deadline-exceeded',
            ageMs: now - entry.startedAt,
            overdueMs,
            result,
            timestamp: now,
          };
          actions.push(action);
          processRegistry.recordCleanup(action);
        }

        // 5. 等待 sigkillDelayMs，再 SIGKILL 仍存活的进程
        await new Promise((resolve) => setTimeout(resolve, this.opts.sigkillDelayMs));

        const stillAlivePids = pidsToKill.filter((p) => isProcessAlive(p));
        if (stillAlivePids.length > 0) {
          this.opts.log(`[ProcessMonitor] SIGTERM 后仍有 ${stillAlivePids.length} 个进程存活，发送 SIGKILL: ${stillAlivePids.join(', ')}`);
          const killResults = await this.sendSignalToPids(stillAlivePids, 'SIGKILL', entry);
          for (let i = 0; i < stillAlivePids.length; i++) {
            const pid = stillAlivePids[i];
            const result = killResults[i];
            const action: ProcessCleanupAction = {
              sessionId: entry.sessionId,
              pid,
              reason: 'stale-deadline-exceeded',
              ageMs: now - entry.startedAt,
              overdueMs,
              result,
              timestamp: Date.now(),
            };
            actions.push(action);
            processRegistry.recordCleanup(action);
          }
        }
      }

      // 6. 如果有 userDataDir，清理磁盘残留
      if (entry.userDataDir) {
        await this.cleanupUserDataDir(entry.userDataDir, entry.sessionId);
      }

      // 7. 从注册表注销
      processRegistry.unregister(entry.sessionId);
      this.opts.log(`[ProcessMonitor] 会话 ${entry.sessionId} 清理完成`);
    }

    return actions;
  }

  /**
   * 按 userDataDir 精确清理 Chrome 进程（Linux: pkill -f，Windows: 跳过）
   *
   * userDataDir 在每次请求中含唯一 timestamp，不会误杀并发请求的 Chrome 进程。
   */
  private async cleanupByUserDataDir(userDataDir: string, sessionId: string): Promise<void> {
    if (process.platform === 'win32' || process.platform === 'darwin') {
      // Windows/macOS 不支持 pkill -f，跳过（依赖 Playwright 的 close() 清理）
      return;
    }
    try {
      const { execSync } = await import('child_process');
      // 按 userDataDir 精确匹配 Chrome 进程命令行
      execSync(`pkill -9 -f '${userDataDir}' 2>/dev/null || true`, { stdio: 'ignore', timeout: 5000 });
      this.opts.log(`[ProcessMonitor] 已按 userDataDir 清理 Chrome 进程: ${userDataDir} (session=${sessionId})`);
    } catch {
      // pkill 失败静默
    }
  }

  /**
   * 手动清理指定会话（用于 server.ts 的 admin 端点）
   */
  async cleanupSession(sessionId: string): Promise<ProcessCleanupAction[]> {
    const entry = processRegistry.get(sessionId);
    if (!entry) return [];

    const now = Date.now();
    const pidsToKill = [entry.pid, ...entry.childPids].filter(
      (p) => Number.isSafeInteger(p) && p >= this.opts.systemPidFloor,
    );

    const actions: ProcessCleanupAction[] = [];
    const termResults = await this.sendSignalToPids(pidsToKill, 'SIGTERM', entry);
    for (let i = 0; i < pidsToKill.length; i++) {
      const action: ProcessCleanupAction = {
        sessionId: entry.sessionId,
        pid: pidsToKill[i],
        reason: 'manual-cleanup',
        ageMs: now - entry.startedAt,
        result: termResults[i],
        timestamp: now,
      };
      actions.push(action);
      processRegistry.recordCleanup(action);
    }

    await new Promise((resolve) => setTimeout(resolve, this.opts.sigkillDelayMs));

    const stillAlivePids = pidsToKill.filter((p) => isProcessAlive(p));
    if (stillAlivePids.length > 0) {
      const killResults = await this.sendSignalToPids(stillAlivePids, 'SIGKILL', entry);
      for (let i = 0; i < stillAlivePids.length; i++) {
        const action: ProcessCleanupAction = {
          sessionId: entry.sessionId,
          pid: stillAlivePids[i],
          reason: 'manual-cleanup',
          ageMs: now - entry.startedAt,
          result: killResults[i],
          timestamp: Date.now(),
        };
        actions.push(action);
        processRegistry.recordCleanup(action);
      }
    }

    if (entry.userDataDir) {
      await this.cleanupUserDataDir(entry.userDataDir, entry.sessionId);
    }

    processRegistry.unregister(sessionId);
    this.opts.log(`[ProcessMonitor] 手动清理会话 ${sessionId} 完成`);
    return actions;
  }

  /**
   * 向一组 PID 发送信号
   *
   * 优先使用注册的 childProcess.kill（Python spawn 的子进程），
   * 这样能正确触发 close 事件；其他进程用 process.kill。
   */
  private async sendSignalToPids(
    pids: number[],
    signal: 'SIGTERM' | 'SIGKILL',
    entry: RegisteredProcess,
  ): Promise<ProcessCleanupAction['result'][]> {
    const results: ProcessCleanupAction['result'][] = [];
    for (const pid of pids) {
      if (pid < this.opts.systemPidFloor) {
        results.push('pid-too-low');
        continue;
      }
      if (!isProcessAlive(pid)) {
        results.push('already-exited');
        continue;
      }
      try {
        // 主进程优先用 childProcess.kill（触发 close 事件）
        if (pid === entry.pid && entry.childProcess) {
          const killed = entry.childProcess.kill(signal as NodeJS.Signals);
          results.push(killed ? (signal === 'SIGTERM' ? 'sigterm-sent' : 'sigkill-sent') : 'kill-failed');
        } else {
          process.kill(pid, signal);
          results.push(signal === 'SIGTERM' ? 'sigterm-sent' : 'sigkill-sent');
        }
      } catch {
        results.push('kill-failed');
      }
    }
    return results;
  }

  /**
   * 清理 Chrome 持久化上下文的 userDataDir
   *
   * Chrome 进程被杀后，userDataDir 可能残留 Cookie/localStorage 等，
   * 长期累积会占用磁盘且可能导致下次启动冲突。
   */
  private async cleanupUserDataDir(userDataDir: string, sessionId: string): Promise<void> {
    try {
      const fs = await import('fs/promises');
      await fs.rm(userDataDir, { recursive: true, force: true });
      this.opts.log(`[ProcessMonitor] 已清理 userDataDir: ${userDataDir} (session=${sessionId})`);
    } catch {
      // 清理失败不影响主流程，下次启动会创建新目录
    }
  }
}

/**
 * 全局进程监测器单例
 *
 * 在 server.ts 启动时调用 processMonitor.start()，
 * 在 shutdown 时调用 processMonitor.stop()。
 */
export const processMonitor = new ProcessMonitor({
  scanIntervalMs: 30_000,    // 每 30 秒扫描一次
  gracePeriodMs: 30_000,     // 超过 deadline + 30 秒才清理
  sigkillDelayMs: 5_000,     // SIGTERM 后 5 秒再 SIGKILL
  systemPidFloor: 100,       // PID < 100 不清理（保护系统进程）
  log: (msg: string) => console.log(msg),
});

/**
 * 生成唯一 sessionId
 */
export function generateSessionId(): string {
  const { randomUUID } = require('crypto');
  return `slider-${Date.now()}-${randomUUID().replace(/-/g, '').slice(0, 8)}`;
}
