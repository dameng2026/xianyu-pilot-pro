import request from '@/utils/http'
import { requirePagePayload, requireRecordPayload } from '@/utils/api-payload'

/** 活动列表查询参数 */
export interface PromotionActivityQuery {
  current?: number
  size?: number
  keyword?: string
  status?: string
}

/** 活动套餐配置（表单） */
export interface PromotionPlanForm {
  planId: number
  periodType: 'month' | 'quarter' | 'year'
  activityPriceCent: number
  quota: number
  sortOrder?: number
  activityTag?: string
  showSoldCount?: boolean
  showQuota?: boolean
  showRemain?: boolean
  allowRepurchase?: boolean
  maxPurchasePerUser?: number
}

/** 活动表单 */
export interface PromotionActivityForm {
  id?: number
  activityName: string
  activityCode: string
  description?: string
  startTime: string
  endTime: string
  isLongTerm?: boolean
  autoCloseOnEnd?: boolean
  noticeTitle?: string
  noticeContent?: string
  noticeVisible?: boolean
  noticePosition?: 'top' | 'banner' | 'card'
  noticeIcon?: 'hot' | 'gift' | 'flash' | 'star'
  plans?: PromotionPlanForm[]
}

/** 活动订单查询 */
export interface PromotionOrderQuery {
  current?: number
  size?: number
  status?: string
}

export function fetchPromotionActivitiesPage(params: PromotionActivityQuery = {}) {
  return request.get<any>({ url: '/promotion/activities/page', params })
    .then(value => requirePagePayload<any>(value, '会员充值活动'))
}

export function fetchPromotionActivityDetail(id: number) {
  return request.get<any>({ url: `/promotion/activities/${id}` })
    .then(value => requireRecordPayload<Record<string, any>>(value, '活动详情'))
}

export function createPromotionActivity(data: PromotionActivityForm) {
  return request.post<any>({ url: '/promotion/activities', data, showSuccessMessage: true })
    .then(value => requireRecordPayload<Record<string, any>>(value, '创建活动'))
}

export function updatePromotionActivity(id: number, data: PromotionActivityForm) {
  return request.put<any>({ url: `/promotion/activities/${id}`, data, showSuccessMessage: true })
    .then(value => requireRecordPayload<Record<string, any>>(value, '更新活动'))
}

export function startPromotionActivity(id: number) {
  return request.post<void>({ url: `/promotion/activities/${id}/start`, showSuccessMessage: true })
}

export function closePromotionActivity(id: number) {
  return request.post<void>({ url: `/promotion/activities/${id}/close`, showSuccessMessage: true })
}

export function reopenPromotionActivity(id: number) {
  return request.post<void>({ url: `/promotion/activities/${id}/reopen`, showSuccessMessage: true })
}

export function deletePromotionActivity(id: number) {
  return request.del<void>({ url: `/promotion/activities/${id}`, showSuccessMessage: true })
}

export function fetchPromotionActivityStats(id: number) {
  return request.get<any>({ url: `/promotion/activities/${id}/stats` })
    .then(value => requireRecordPayload<Record<string, any>>(value, '活动统计'))
}

export function fetchPromotionActivityOrders(id: number, params: PromotionOrderQuery = {}) {
  return request.get<any>({ url: `/promotion/activities/${id}/orders`, params })
    .then(value => requirePagePayload<any>(value, '活动订单'))
}

export function adjustPromotionPlanQuota(
  activityId: number,
  activityPlanId: number,
  newQuota: number,
  remark?: string
) {
  return request.post<void>({
    url: `/promotion/activities/${activityId}/plans/${activityPlanId}/quota`,
    params: { newQuota, remark: remark || '' },
    showSuccessMessage: true
  })
}

/**
 * 拉取启用中的会员套餐列表（用于活动配置时选择套餐）。
 * 复用 /admin-api/billing/plans（管理员与前台共用接口）。
 */
export function fetchEnabledBillingPlans() {
  return request.get<any[]>({ url: '/billing/plans' })
    .then(value => {
      if (!Array.isArray(value)) {
        throw new Error('会员套餐列表响应格式异常')
      }
      return value
    })
}
