import request from '@/utils/http'
import { requirePagePayload, requireRecordPayload } from '@/utils/api-payload'

/** 反馈状态枚举 */
export type FeedbackStatus = 'open' | 'in_progress' | 'replied' | 'closed'
export type FeedbackPriority = 'low' | 'normal' | 'high' | 'urgent'
export type FeedbackCategory = 'bug' | 'feature' | 'suggestion' | 'other'
export type FeedbackSiteSource = 'commercial' | 'open-source' | string

/** 反馈查询参数 */
export interface FeedbackQuery {
  current?: number
  size?: number
  keyword?: string
  status?: FeedbackStatus | ''
  category?: FeedbackCategory | ''
  priority?: FeedbackPriority | ''
  siteSource?: FeedbackSiteSource | ''
  tenantId?: number
}

/** 列表项 */
export interface FeedbackListItem {
  id: number
  tenantId?: number
  userId?: number
  username?: string
  category: FeedbackCategory
  title: string
  contentPreview?: string
  siteSource?: FeedbackSiteSource
  siteName?: string
  status: FeedbackStatus
  priority: FeedbackPriority
  contact?: string
  replierUsername?: string
  repliedTime?: string
  createdTime?: string
  updatedTime?: string
  userReplyCount?: number
}

/** 回复记录 */
export interface FeedbackReply {
  id: number
  feedbackId?: number
  replierRole: 'admin' | 'user'
  replierUserId?: number
  replierUsername?: string
  content: string
  createdTime?: string
}

/** 详情 */
export interface FeedbackDetail extends FeedbackListItem {
  content: string
  replies?: FeedbackReply[]
}

/** 分页结果 */
export interface FeedbackPage {
  records: FeedbackListItem[]
  current: number
  size: number
  total: number
}

/** 反馈列表（分页 + 筛选） */
export function getFeedbackList(params: FeedbackQuery) {
  return request.get<FeedbackPage>({ url: '/feedback', params, skipDedupe: true })
    .then(value => requirePagePayload<FeedbackListItem>(value, '用户反馈') as FeedbackPage)
}

/** 反馈详情（含回复列表） */
export function getFeedbackDetail(id: number) {
  return request.get<FeedbackDetail>({ url: `/feedback/${id}`, skipDedupe: true })
    .then(value => requireRecordPayload<Record<string, any>>(value, '反馈详情') as FeedbackDetail)
}

/** 管理员回复反馈 */
export function replyFeedback(id: number, content: string) {
  return request.post<{ ok: boolean }>({
    url: `/feedback/${id}/reply`,
    data: { content },
    showSuccessMessage: true
  })
}

/** 修改反馈状态 */
export function changeFeedbackStatus(id: number, status: FeedbackStatus) {
  return request.post<{ ok: boolean; status: FeedbackStatus }>({
    url: `/feedback/${id}/status`,
    data: { status },
    showSuccessMessage: true
  })
}

/** 修改反馈优先级 */
export function changeFeedbackPriority(id: number, priority: FeedbackPriority) {
  return request.post<{ ok: boolean; priority: FeedbackPriority }>({
    url: `/feedback/${id}/priority`,
    data: { priority },
    showSuccessMessage: true
  })
}

/** 删除反馈（软删除） */
export function deleteFeedback(id: number) {
  return request.del<void>({ url: `/feedback/${id}`, showSuccessMessage: true })
}
