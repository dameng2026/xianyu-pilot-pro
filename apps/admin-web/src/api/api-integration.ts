import request from '@/utils/http'
import { requirePagePayload, requireRecordPayload } from '@/utils/api-payload'

/** API 对接记录查询参数 */
export interface ApiIntegrationRecordQuery {
  current?: number
  size?: number
  tenantId?: number | string
  status?: string // success / fail / timeout / precheck_rejected / retrying / queued
  apiKeyPrefix?: string
  keyword?: string
  startTime?: string
  endTime?: string
}

/** API 对接记录明细行（snake_case，与后端 selectRecords 返回一致） */
export interface ApiIntegrationRecordRow {
  id: number
  tenant_id?: number | null
  api_key_prefix?: string
  client_ip?: string
  request_id: string
  event_desc?: string
  trigger_scene?: string
  result?: string
  status?: string
  engine?: string
  retry_count?: number
  error_message?: string
  failure_reason?: string
  queued_at?: string
  started_at?: string
  finished_at?: string
  token_charged?: number
  token_charge_failed?: number
  duration_ms?: number | null
  created_at?: string
}

/** KPI（snake_case，与后端 selectKpi 返回一致） */
export interface ApiIntegrationKpi {
  total: number
  success_count: number
  fail_count: number
  timeout_count: number
  precheck_rejected_count: number
  service_unavailable_count: number
  charged_tokens: number
}

/** 趋势点（snake_case，与后端 selectTrend 返回一致） */
export interface ApiIntegrationTrendPoint {
  date: string
  total: number
  success: number
  fail: number
  charged_tokens: number
}

/** 租户分组聚合行（snake_case，与后端 selectTenantGroups 返回一致） */
export interface ApiIntegrationTenantGroup {
  tenant_id: number | null
  api_key_prefix?: string
  total: number
  success: number
  fail: number
  charged_tokens: number
  last_solve_time?: string
}

/** 概览统计返回结构 */
export interface ApiIntegrationStats {
  kpi: ApiIntegrationKpi
  trend: ApiIntegrationTrendPoint[]
  tenants: ApiIntegrationTenantGroup[]
}

/** 统计参数 */
export interface ApiIntegrationStatsQuery {
  days?: number // 1=今天 / 7 / 30，省略或 <=0 表示全量
}

/** 获取概览统计（KPI + 趋势 + 租户分组） */
export function getAdminStats(days?: number) {
  const params: ApiIntegrationStatsQuery = {}
  if (days != null && days > 0) params.days = days
  return request.get<any>({ url: '/admin/api-integration/stats', params })
    .then(value => requireRecordPayload<Record<string, any>>(value, 'API对接统计') as ApiIntegrationStats)
}

/** 分页查询明细记录 */
export function getAdminRecords(params: ApiIntegrationRecordQuery = {}) {
  return request.get<any>({ url: '/admin/api-integration/records', params })
    .then(value => requirePagePayload<ApiIntegrationRecordRow>(value, 'API对接记录'))
}

/** 今日 Token 消耗与求解次数（返回今日 KPI） */
export function getAdminTodayToken() {
  return request.get<any>({ url: '/admin/api-integration/today-token' })
    .then(value => requireRecordPayload<Record<string, any>>(value, 'API对接今日Token') as ApiIntegrationKpi)
}
