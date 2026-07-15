import request from '@/utils/http'
import { buildFreshContentListRequest } from './content-config'
import { requireListPayload, requirePagePayload, requireRecordPayload } from '@/utils/api-payload'

export type OpenSourceAdPositionType = 'home_carousel' | 'sidebar_text'
export type OpenSourceAdApplicationStatus =
  | 'pending_payment'
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'online'
  | 'offline'

export interface OpenSourceTextAdItem {
  id?: number
  title: string
  summary: string
  badge: string
  linkUrl: string
  enabled: boolean
  sortOrder: number
  createdAt?: string
  updatedAt?: string
}

export interface OpenSourceAdPlanItem {
  id?: number
  code: string
  positionType: OpenSourceAdPositionType
  positionLabel?: string
  title: string
  description: string
  priceLabel: string
  priceYuan?: string
  priceCent?: number
  benefits: string[]
  recommended: boolean
  enabled: boolean
  sortOrder: number
  createdAt?: string
  updatedAt?: string
}

export interface OpenSourceAdApplicationQuery {
  current?: number
  size?: number
  keyword?: string
  status?: OpenSourceAdApplicationStatus | ''
  positionType?: OpenSourceAdPositionType | ''
}

export interface OpenSourceAdApplicationItem {
  id: number
  tenantId?: number
  siteCode?: string
  siteName?: string
  applicationNo?: string
  positionType: OpenSourceAdPositionType
  positionLabel?: string
  planCode?: string
  planTitle?: string
  companyName?: string
  contact?: string
  contactValue?: string
  contactName?: string
  contactPhone?: string
  contactWechat?: string
  title?: string
  landingUrl?: string
  creativeImageUrl?: string
  budget?: string
  startDate?: string
  durationDays?: string
  remark?: string
  status: OpenSourceAdApplicationStatus
  statusLabel?: string
  statusMessage?: string
  paymentMethod?: string
  paymentProviderType?: string
  paymentOrderNo?: string
  paymentStatus?: string
  paymentStatusLabel?: string
  paymentAmountCent?: number
  paymentAmountYuan?: string
  paymentPaidTime?: string
  paymentExpireTime?: string
  publishedRecordId?: number
  publishedRecordType?: string
  reviewerUserId?: number
  reviewerUsername?: string
  reviewedTime?: string
  createdTime?: string
  updatedTime?: string
}

export interface OpenSourceAdApplicationPage {
  records: OpenSourceAdApplicationItem[]
  current: number
  size: number
  total: number
}

export function getOpenSourceTextAds() {
  return request.get<OpenSourceTextAdItem[]>(
    buildFreshContentListRequest('/open-source-admin/ads/text')
  ).then(value => requireListPayload<OpenSourceTextAdItem>(value, '开源版文字广告'))
}

export function saveOpenSourceTextAd(data: OpenSourceTextAdItem) {
  return request.post<OpenSourceTextAdItem>({
    url: '/open-source-admin/ads/text',
    data,
    showSuccessMessage: true,
  })
}

export function updateOpenSourceTextAd(data: OpenSourceTextAdItem) {
  return request.put<OpenSourceTextAdItem>({
    url: '/open-source-admin/ads/text',
    data,
    showSuccessMessage: true,
  })
}

export function deleteOpenSourceTextAd(id: number) {
  return request.del<void>({
    url: `/open-source-admin/ads/text/${id}`,
    showSuccessMessage: true,
  })
}

export function getOpenSourceAdPlans() {
  return request.get<OpenSourceAdPlanItem[]>(
    buildFreshContentListRequest('/open-source-admin/ads/plans')
  ).then(value => requireListPayload<OpenSourceAdPlanItem>(value, '开源版广告套餐'))
}

export function saveOpenSourceAdPlan(data: OpenSourceAdPlanItem) {
  return request.post<OpenSourceAdPlanItem>({
    url: '/open-source-admin/ads/plans',
    data,
    showSuccessMessage: true,
  })
}

export function updateOpenSourceAdPlan(data: OpenSourceAdPlanItem) {
  return request.put<OpenSourceAdPlanItem>({
    url: '/open-source-admin/ads/plans',
    data,
    showSuccessMessage: true,
  })
}

export function deleteOpenSourceAdPlan(id: number) {
  return request.del<void>({
    url: `/open-source-admin/ads/plans/${id}`,
    showSuccessMessage: true,
  })
}

export function getOpenSourceAdApplications(params: OpenSourceAdApplicationQuery) {
  return request.get<OpenSourceAdApplicationPage>({
    url: '/open-source-admin/ads/applications',
    params,
    skipDedupe: true,
  }).then(value => requirePagePayload<OpenSourceAdApplicationItem>(value, '开源版广告申请') as OpenSourceAdApplicationPage)
}

export function getOpenSourceAdApplicationDetail(id: number) {
  return request.get<OpenSourceAdApplicationItem>({
    url: `/open-source-admin/ads/applications/${id}`,
    skipDedupe: true,
  }).then(value => requireRecordPayload<Record<string, any>>(value, '广告申请详情') as OpenSourceAdApplicationItem)
}

export function updateOpenSourceAdApplicationStatus(
  id: number,
  status: OpenSourceAdApplicationStatus,
  statusMessage: string
) {
  return request.post<OpenSourceAdApplicationItem>({
    url: `/open-source-admin/ads/applications/${id}/status`,
    data: { status, statusMessage },
    showSuccessMessage: true,
  })
}
