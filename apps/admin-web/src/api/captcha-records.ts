import request from '@/utils/http'
import { requirePagePayload, requireRecordPayload } from '@/utils/api-payload'

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
  successRate: number // 0~1
}

/** 趋势点 */
export interface CaptchaSolveTrendPoint {
  date: string
  total: number
  success: number
  fail: number
  successRate: number
}

/** 账号分组聚合行 */
export interface CaptchaSolveAccountGroup {
  accountId: number
  accountName?: string
  total: number
  success: number
  fail: number
  successRate: number
  lastSolveTime?: string
}

/** 概览统计返回结构 */
export interface CaptchaSolveStats {
  kpi: CaptchaSolveKpi
  trend: CaptchaSolveTrendPoint[]
  accounts: CaptchaSolveAccountGroup[]
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

/** 分页查询明细记录 */
export function getCaptchaSolveRecords(params: CaptchaRecordQuery = {}) {
  return request.get<any>({ url: '/admin/captcha-records', params })
    .then(value => requirePagePayload<CaptchaRecordRow>(value, '滑块求解记录'))
}
