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

// ===== 统一充值记录（会员充值 + Token 充值）=====

export interface UnifiedRechargeRecordQuery {
  current?: number
  size?: number
  userId?: number | string
  keyword?: string
  /** 充值类型过滤：'vip' 会员充值 | 'token' Token 充值 | 不传为全部 */
  orderType?: 'vip' | 'token' | ''
}

export interface UnifiedRechargeRow {
  id: number
  tenantId?: number | null
  userId: number
  username?: string
  orderNo?: string
  /** 订单类型：'vip' 会员充值 | 'token' Token 充值 */
  orderType?: string
  recordType?: string
  recordTypeText?: string
  targetType?: string
  targetTypeText?: string
  targetId?: number | null
  planId?: number | null
  tokenPlanId?: number | null
  title?: string
  /** 套餐名（会员套餐或 Token 套餐） */
  planName?: string
  amountCent?: number
  amountYuan?: number
  tokenAmount?: number
  paymentMethod?: string
  paymentMethodText?: string
  providerType?: string
  periodType?: string
  periodText?: string
  status?: number
  paidTime?: string
  createdTime?: string
  vipPlanName?: string
  tokenPlanName?: string
}

export interface UnifiedRechargeSummary {
  todayRevenue?: {
    totalCount?: number
    totalAmountCent?: number
    vipCount?: number
    vipAmountCent?: number
    tokenCount?: number
    tokenAmountCent?: number
  }
  cumulative?: {
    totalRecords?: number
    totalAmountCent?: number
    vipTotalRecords?: number
    vipTotalAmountCent?: number
    tokenTotalRecords?: number
    tokenTotalAmountCent?: number
    tokenTotalTokens?: number
  }
}

export function getUnifiedRechargeRecordsPage(params: UnifiedRechargeRecordQuery = {}) {
  return request.get<any>({ url: '/ai-billing/unified-recharge-records/page', params })
    .then(value => requirePagePayload<UnifiedRechargeRow>(value, '充值记录'))
}

export function getUnifiedRechargeRecordsSummary(params: { userId?: number | string } = {}) {
  return request.get<any>({ url: '/ai-billing/unified-recharge-records/summary', params })
    .then(value => requireRecordPayload<Record<string, any>>(value, '充值记录汇总') as UnifiedRechargeSummary)
}
