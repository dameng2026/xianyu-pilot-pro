import { reactive, readonly } from 'vue'
import { handleCaptcha, getCaptchaQueuePosition } from '../api/captcha.js'

/**
 * 全局滑块求解状态管理
 *
 * 监听 SSE captcha_solve 事件，维护每个账号的求解状态。
 * 提供 isAccountSolving / isAccountQueued / getAccountSolveStatus / solveManually 方法。
 *
 * 状态字段: { status, result, reason, accountName, timestamp, recordId, queuePosition, queueTotal }
 *   status: 'queued' | 'retrying' | 'success' | 'fail' | 'timeout' | 'precheck_rejected'
 *     - queued: 任务已入队，等待 worker 处理（不触发 5 分钟超时）
 *     - retrying: worker 已取出任务，正在执行滑块求解（适用 5 分钟超时）
 *     - success: 求解成功
 *     - fail: 求解失败（滑块通过失败）
 *     - timeout: 求解超时
 *     - precheck_rejected: 预校验拒绝（账号不活跃/Cookie 失效/hasLogin 服务不可用/冷却中）
 *   result: 'slider_success' | 'slider_fail' | 'precheck_fail' | ''
 *   queuePosition: number (排队位置，1=下一个出队，0=不在排队中/已开始处理)
 *   queueTotal: number (排队中总数)
 *
 * 求解改为队列异步后，solveManually 入队后立即返回，成功/失败通过 SSE 事件异步通知。
 */

const solveStates = reactive({})  // accountId(string) → state object

// 自动求解去重：同账号 30 秒内只自动求解一次
const autoSolveTimestamps = {}
const AUTO_SOLVE_COOLDOWN_MS = 30000

// 排队位置轮询定时器：accountId(string) → interval id
const queuePollTimers = {}
const QUEUE_POLL_INTERVAL_MS = 5000  // 5 秒轮询一次

function setSolveState(accountId, payload) {
  if (!accountId) return
  const key = String(accountId)
  const prev = solveStates[key]
  solveStates[key] = {
    status: payload.status || 'retrying',
    result: payload.result || '',
    reason: payload.reason || '',
    accountName: payload.accountName || prev?.accountName || '',
    timestamp: Date.now(),
    recordId: payload.recordId ?? prev?.recordId ?? null,
    queuePosition: payload.queuePosition ?? prev?.queuePosition ?? 0,
    queueTotal: payload.queueTotal ?? prev?.queueTotal ?? 0,
  }
}

/**
 * 账号是否处于活跃求解状态（排队中 OR 处理中）。
 * 用于防止重复提交：排队中和处理中都不允许再次触发。
 */
function isAccountSolving(accountId) {
  const state = solveStates[String(accountId)]
  return state?.status === 'retrying' || state?.status === 'queued'
}

/**
 * 账号是否处于排队中（仅 queued，不含处理中）。
 * 用于前端区分"排队中"与"求解中"两种展示。
 */
function isAccountQueued(accountId) {
  const state = solveStates[String(accountId)]
  return state?.status === 'queued'
}

function getAccountSolveStatus(accountId) {
  return solveStates[String(accountId)] || null
}

function clearSolveStatus(accountId) {
  const key = String(accountId)
  stopQueuePolling(key)
  delete solveStates[key]
}

// ============================================================
// 排队位置轮询：当状态为 queued 时定时查询排队位置
// SSE 可能因网络延迟未及时到达，轮询作为兜底确保排队位置实时更新
// ============================================================
function startQueuePolling(accountId, recordId) {
  const key = String(accountId)
  if (!recordId) return
  // 已有轮询则跳过
  if (queuePollTimers[key]) return
  const poll = async () => {
    try {
      const res = await getCaptchaQueuePosition({ recordId })
      const data = res?.data || res || {}
      const position = Number(data.position || 0)
      const total = Number(data.total || 0)
      const status = data.status || ''
      // 后端返回的状态已变更（不再是 queued），停止轮询并同步更新前端状态
      // 关键：必须同步更新 solveStates，否则 SSE 事件丢失时前端会一直显示"排队中"
      // 而实际后端已经处理完成（success/fail）
      if (status && status !== 'queued') {
        const prev = solveStates[key]
        if (prev) {
          const reasonByStatus = {
            retrying: '求解中',
            success: '求解成功',
            fail: '求解失败',
            timeout: '求解超时',
            precheck_rejected: '预校验拒绝（账号状态不满足求解条件）',
          }
          solveStates[key] = {
            ...prev,
            status,
            reason: reasonByStatus[status] || prev.reason,
            timestamp: Date.now(),
          }
        }
        stopQueuePolling(key)
        return
      }
      // 更新排队位置（不覆盖 status，保持 queued）
      const prev = solveStates[key]
      if (prev && prev.status === 'queued') {
        solveStates[key] = {
          ...prev,
          queuePosition: position,
          queueTotal: total,
          timestamp: Date.now(),
        }
      } else {
        // 状态已变更，停止轮询
        stopQueuePolling(key)
      }
    } catch {
      // 查询失败静默处理，等下次轮询
    }
  }
  queuePollTimers[key] = setInterval(poll, QUEUE_POLL_INTERVAL_MS)
}

function stopQueuePolling(accountIdKey) {
  if (queuePollTimers[accountIdKey]) {
    clearInterval(queuePollTimers[accountIdKey])
    delete queuePollTimers[accountIdKey]
  }
}

/**
 * 手动触发滑块求解
 * @param {number} accountId 账号ID
 * @param {string} triggerScene 触发场景，默认 'manual'
 * @param {object} extra 额外参数 { openReason, solveReason }
 *   - openReason: 开启原因（为什么打开滑块求解流程）
 *   - solveReason: 求解原因（为什么进行滑块求解）
 * @returns {Promise<{queued: boolean, deduplicated?: boolean, recordId?: number, queuePosition?: number, queueTotal?: number, message: string}>}
 *   求解结果不再同步返回（入队后立即返回），成功/失败通过 SSE 事件异步通知
 */
async function solveManually(accountId, triggerScene = 'manual', extra = {}) {
  if (!accountId) return { queued: false, message: '账号ID不能为空' }
  const key = String(accountId)
  const openReason = extra.openReason || ''
  const solveReason = extra.solveReason || ''

  // 保存调用前状态，用于被去重时回滚（避免乐观标记的 queued 状态残留导致按钮永久禁用）
  const prev = solveStates[key] ? { ...solveStates[key] } : null

  // 标记为排队中（不再立即标记为 retrying，避免被误判为"处理中"触发超时）
  solveStates[key] = {
    status: 'queued',
    result: '',
    reason: solveReason || '任务已提交，等待排队...',
    accountName: solveStates[key]?.accountName || '',
    timestamp: Date.now(),
    recordId: null,
    queuePosition: 0,
    queueTotal: 0,
  }

  try {
    const res = await handleCaptcha({
      accountId: Number(accountId),
      autoSolve: true,
      triggerScene,
      openReason,
      solveReason,
    })
    const data = res?.data || res || {}

    // 被去重跳过（同账号 60 秒内已入队）
    // 回滚到调用前状态：避免乐观标记的 queued 残留导致 isAccountSolving 误判按钮禁用；
    // 同时不把状态置为 fail，避免污染 isRetry 判定（否则下次点击被判为重试跳过前端冷却，
    // 又触发后端去重，形成死循环）。仅通过返回值把 message 交给调用方展示临时提示
    if (data.deduplicated) {
      if (prev) {
        solveStates[key] = prev
      } else {
        delete solveStates[key]
      }
      return { queued: false, deduplicated: true, message: data.message || '该账号近期已触发过求解，请稍后再试' }
    }

    // 入队成功：更新排队位置信息
    const recordId = data.recordId || null
    const queuePosition = Number(data.queuePosition || 0)
    const queueTotal = Number(data.queueTotal || 0)

    // === 关键：防止竞态覆盖 ===
    // 后端预校验（排除表/Cookie 失效/hasLogin 服务不可用）可能在毫秒级完成，
    // 此时 SSE 已先于 HTTP 响应到达并把状态更新为 precheck_rejected/fail/timeout/success。
    // 若无条件用 API 响应的 queued 覆盖，会冲掉已正确的终态，导致前端卡在"排队中"。
    // 解决：若当前已是终态（success/fail/timeout/precheck_rejected），保留 SSE 已更新的状态，仅补充 recordId/位置信息。
    const currentState = solveStates[key]
    const TERMINAL_STATUSES = ['success', 'fail', 'timeout', 'precheck_rejected']
    if (currentState && TERMINAL_STATUSES.includes(currentState.status)) {
      // SSE 已送达终态：仅补充 recordId 和排队位置（若缺失），不覆盖 status/reason
      solveStates[key] = {
        ...currentState,
        recordId: currentState.recordId || recordId,
        queuePosition: currentState.queuePosition || queuePosition,
        queueTotal: currentState.queueTotal || queueTotal,
        timestamp: Date.now(),
      }
    } else {
      solveStates[key] = {
        status: 'queued',
        result: '',
        reason: data.message || `任务已入队，排队中（第 ${queuePosition} 位，共 ${queueTotal} 个任务）`,
        accountName: solveStates[key]?.accountName || '',
        timestamp: Date.now(),
        recordId,
        queuePosition,
        queueTotal,
      }
    }

    // 启动排队位置轮询（SSE 可能因网络延迟未及时到达，轮询作为兜底）
    if (recordId) {
      startQueuePolling(accountId, recordId)
    }

    return {
      queued: true,
      recordId,
      queuePosition,
      queueTotal,
      message: data.message || '任务已入队',
    }
  } catch (e) {
    // 后端 403 功能开关拦截（前端绕过场景）：重新抛出，让调用方弹窗引导
    // autoSolveIfNeeded 用 .catch(() => {}) 吞掉所有错误，不会受影响
    if (e?.code === 403 && e?.data?.feature_key) {
      throw e
    }
    solveStates[key] = {
      status: 'fail',
      result: 'slider_fail',
      reason: e?.message || '滑块求解请求失败',
      accountName: solveStates[key]?.accountName || '',
      timestamp: Date.now(),
      recordId: null,
      queuePosition: 0,
      queueTotal: 0,
    }
    return { queued: false, message: e?.message || '滑块求解请求失败' }
  }
}

/**
 * 自动触发滑块求解（带冷却去重）
 * 由 request.js 的 code=1001 拦截器调用
 */
async function autoSolveIfNeeded(accountId) {
  if (!accountId) return
  const key = String(accountId)
  const now = Date.now()
  const lastTs = autoSolveTimestamps[key] || 0
  if (now - lastTs < AUTO_SOLVE_COOLDOWN_MS) return  // 冷却期内跳过
  autoSolveTimestamps[key] = now
  // 后端 handle API 会写记录 + SSE 广播，前端通过 SSE 更新状态
  solveManually(accountId, 'ws_connect', {
    openReason: 'HTTP 接口返回需要滑块验证自动触发',
    solveReason: 'API 响应 code=1001，需要滑块验证',
  }).catch(() => {})
}

// ============================================================
// SSE 事件监听：监听 captcha_solve 事件更新状态
// ============================================================
function onSseCaptchaSolve(event) {
  const detail = event?.detail
  const data = detail?.payload || detail || {}
  const eventType = detail?.type || data.type || ''
  if (eventType !== 'captcha_solve') return
  const accountId = data.accountId
  if (!accountId) return
  const key = String(accountId)

  setSolveState(accountId, {
    status: data.status,
    result: data.result,
    reason: data.reason,
    accountName: data.accountName,
    recordId: data.recordId,
    queuePosition: data.queuePosition,
    queueTotal: data.queueTotal,
  })

  // 状态变更时管理轮询
  const newStatus = data.status
  if (newStatus === 'queued') {
    // 进入排队状态，启动轮询（如有 recordId）
    if (data.recordId) {
      startQueuePolling(accountId, data.recordId)
    }
  } else {
    // 离开排队状态（retrying/success/fail），停止轮询
    stopQueuePolling(key)
  }
}

function initCaptchaSolverListener() {
  window.addEventListener('xya-sse-event', onSseCaptchaSolve)
}

function destroyCaptchaSolverListener() {
  window.removeEventListener('xya-sse-event', onSseCaptchaSolve)
  // 清理所有轮询定时器
  Object.keys(queuePollTimers).forEach(stopQueuePolling)
}

export function useCaptchaSolver() {
  return {
    solveStates: readonly(solveStates),
    isAccountSolving,
    isAccountQueued,
    getAccountSolveStatus,
    clearSolveStatus,
    solveManually,
    autoSolveIfNeeded,
    initCaptchaSolverListener,
    destroyCaptchaSolverListener,
  }
}
