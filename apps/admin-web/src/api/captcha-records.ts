import request from '@/utils/http'
import { requireListPayload, requirePagePayload, requireRecordPayload } from '@/utils/api-payload'

/** 滑块求解记录查询参数 */
export interface CaptchaRecordQuery {
  current?: number
  size?: number
  accountId?: number | string
  userId?: number | string
  status?: string // retrying / success / fail
  triggerScene?: string // ws_connect / cookie_keepalive / token_refresh / manual / manual_retry
  accountName?: string
  startTime?: string
  endTime?: string
}

/** 滑块求解记录明细行 */
export interface CaptchaRecordRow {
  id: number
  tenantId?: number | null
  accountId: number
  accountName?: string
  eventDesc?: string
  openReason?: string
  solveReason?: string
  triggerScene?: string
  result?: string
  status?: string
  engine?: string
  retryCount?: number
  errorMessage?: string
  durationMs?: number | null
  screenshotPath?: string | null
  errorMessageText?: string
  priority?: number
  failureReason?: string
  /** 代理来源：server_ip/residential_ip/account_bound/unknown（2026-08-03 新增） */
  proxySource?: string
  queuedAt?: string
  startedAt?: string
  finishedAt?: string
  createdAt?: string
  updatedAt?: string
}

/** 概览统计：KPI */
export interface CaptchaSolveKpi {
  total: number
  success: number
  fail: number
  timeout: number
  precheckRejected: number
  serviceUnavailable: number
  successRate: number // 0~1
}

/** 趋势点 */
export interface CaptchaSolveTrendPoint {
  date: string
  total: number
  success: number
  fail: number
  timeout: number
  precheckRejected: number
  serviceUnavailable: number
  successRate: number
}

/** 账号分组聚合行 */
export interface CaptchaSolveAccountGroup {
  accountId: number
  accountName?: string
  total: number
  success: number
  fail: number
  timeout: number
  precheckRejected: number
  serviceUnavailable: number
  successRate: number
  lastSolveTime?: string
}

/** 概览统计返回结构 */
export interface CaptchaSolveStats {
  kpi: CaptchaSolveKpi
  trend: CaptchaSolveTrendPoint[]
  accounts: CaptchaSolveAccountGroup[]
  /** 按代理来源聚合的成功率（2026-08-03 新增，住址IP vs 服务器IP对比） */
  byProxySource?: CaptchaSolveProxySourceGroup[]
}

/** 按代理来源聚合的统计行 */
export interface CaptchaSolveProxySourceGroup {
  proxySource: string // server_ip / residential_ip / account_bound / unknown
  total: number
  success: number
  fail: number
  successRate: number // 0~1
}

/** 滑块求解统计参数 */
export interface CaptchaStatsQuery {
  days?: number // 1=今天 / 7 / 30，省略或 <=0 表示全量
  userId?: number | string
  accountId?: number | string
}

/** 获取概览统计（KPI + 趋势 + 账号分组） */
export function getCaptchaSolveStats(params: CaptchaStatsQuery = {}) {
  return request.get<any>({ url: '/admin/captcha-records/stats', params })
    .then(value => requireRecordPayload<Record<string, any>>(value, '滑块求解统计') as CaptchaSolveStats)
}

// ==================== 尝试明细成功率统计 ====================

/** 通用维度统计行（求解方案 / 拖动方法 / 速度策略 共用） */
export interface CaptchaAttemptDimensionStat {
  dim: string // 维度值（如 'playwright' / 'in_container' / 'standard'）
  total: number // 总次数
  success: number // 成功次数
  successRate: number // 成功率 0~100
  avgDurationMs: number // 平均耗时（毫秒）
}

/** 按尝试轮次聚合的统计行 */
export interface CaptchaAttemptNoStat {
  attemptNo: number // 尝试轮次编号（1-5）
  total: number
  success: number
  successRate: number // 0~100
  avgDurationMs: number
}

/** 尝试明细成功率统计返回结构 */
export interface CaptchaAttemptStats {
  bySolveScheme: CaptchaAttemptDimensionStat[] // 按求解方案聚合
  byDragMethod: CaptchaAttemptDimensionStat[] // 按拖动方法聚合
  bySpeedStrategy: CaptchaAttemptDimensionStat[] // 按速度策略聚合
  byAttemptNo: CaptchaAttemptNoStat[] // 按尝试轮次聚合
  totalAttempts: number // 总尝试次数
  totalSuccess: number // 总成功次数
  overallSuccessRate: number // 整体成功率 0~100
  days: number // 统计天数（0=全量）
  accountId: number // 账号 ID（0=不限账号）
}

/** 单次尝试明细行 */
export interface CaptchaAttemptDetail {
  attemptNo: number
  solveScheme: string
  dragMethod: string
  speedStrategy: string
  success: boolean
  durationMs: number
  errorMessage?: string
  createdAt?: string
}

/** 获取尝试明细成功率统计（按方案/方法/策略/轮次四维聚合） */
export function getCaptchaAttemptStats(params: CaptchaStatsQuery = {}) {
  return request.get<any>({ url: '/admin/captcha-records/attempt-stats', params })
    .then(value => requireRecordPayload<Record<string, any>>(value, '尝试明细统计') as CaptchaAttemptStats)
}

/** 查询单条求解记录的每次尝试明细列表 */
export function getCaptchaRecordAttempts(recordId: number | string) {
  return request.get<any>({ url: `/admin/captcha-records/${recordId}/attempts` })
    .then(value => requireListPayload<CaptchaAttemptDetail>(value, '求解尝试明细'))
}

/** 队列实时状态 */
export interface CaptchaQueueStatus {
  queued: number
  retrying: number
  timeout: number
  precheckRejected: number
  workers: number
}

/** 查询队列实时状态（排队中/求解中任务数） */
export function getCaptchaQueueStatus() {
  return request.get<any>({ url: '/admin/captcha-records/queue-status' })
    .then(value => requireRecordPayload<Record<string, any>>(value, '队列实时状态') as CaptchaQueueStatus)
}

/** 分页查询明细记录 */
export function getCaptchaSolveRecords(params: CaptchaRecordQuery = {}) {
  return request.get<any>({ url: '/admin/captcha-records', params })
    .then(value => requirePagePayload<CaptchaRecordRow>(value, '滑块求解记录'))
}
