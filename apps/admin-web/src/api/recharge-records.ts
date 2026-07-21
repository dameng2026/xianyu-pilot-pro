import request from '@/utils/http'
import { requirePagePayload, requireRecordPayload } from '@/utils/api-payload'

export interface RechargeRecordQuery {
  current?: number
  size?: number
  userId?: number | string
  keyword?: string
  source?: string
}

export interface RechargeRecordRow {
  id: number
  tenantId?: number | null
  userId: number
  username?: string
  paymentOrderId?: number | null
  orderNo?: string
  tokenAmount: number
  beforeBalance?: number
  afterBalance?: number
  source?: string
  remark?: string
  createdTime?: string
}

export interface RechargeRecordsSummary {
  totalRecords?: number
  totalTokens?: number
  todayRecords?: number
  todayTokens?: number
  monthTokens?: number
}

export function getRechargeRecordsPage(params: RechargeRecordQuery = {}) {
  return request.get<any>({ url: '/ai-billing/recharge-records/page', params })
    .then(value => requirePagePayload<RechargeRecordRow>(value, '充值记录'))
}

export function getRechargeRecordsSummary(params: { userId?: number | string } = {}) {
  return request.get<any>({ url: '/ai-billing/recharge-records/summary', params })
    .then(value => requireRecordPayload<Record<string, any>>(value, '充值记录汇总') as RechargeRecordsSummary)
}
