import request from '@/utils/http'
import { requireRecordPayload, requireListPayload, requirePagePayload } from '@/utils/api-payload'

// ==================== 类型定义 ====================

export interface GrowthGlobalConfig {
  tokenRewardPerReferral?: number
  minWithdrawalAmount?: number
  firstMonthOnly?: number
  withdrawEnabled?: number
  updatedBy?: string
  updatedTime?: string
}

export interface GrowthTierConfig {
  id?: number
  tierCode?: string
  tierName?: string
  minReferrals?: number
  commissionRate?: number
  tokenRewardPerReferral?: number
  sort?: number
  enabled?: number
  description?: string
  createdTime?: string
  updatedTime?: string
}

export interface GrowthDashboard {
  summary?: {
    totalReferrers?: number
    totalReferrals?: number
    totalWithdrawals?: number
    pendingWithdrawals?: number
    totalWithdrawnAmount?: number
    totalCommissionAmount?: number
    totalTokenReward?: number
    activeInviteCodes?: number
  }
  today?: {
    newReferrals?: number
    newWithdrawals?: number
    commissionAmount?: number
    tokenReward?: number
  }
  trend?: {
    dates?: string[]
    cashSeries?: number[]
    tokenSeries?: number[]
    totalCash?: number
    totalToken?: number
  }
  leaderboard?: GrowthLeaderboardRow[]
  tierDistribution?: Array<{ tierCode: string; tierName: string; count: number }>
}

export interface GrowthLeaderboardRow {
  rank?: number
  userId?: number
  username?: string
  nickname?: string
  avatar?: string
  tierCode?: string
  tierName?: string
  totalReferrals?: number
  validReferrals?: number
  totalEarnings?: number
  totalTokenReward?: number
}

export interface GrowthWithdrawalRow {
  id: number
  userId?: number
  username?: string
  nickname?: string
  tenantId?: number | null
  amount?: number
  amountYuan?: number
  paymentMethod?: string
  paymentMethodText?: string
  paymentAccount?: string
  paymentName?: string
  status?: string
  statusText?: string
  rejectReason?: string
  reviewer?: string
  reviewedTime?: string
  createdTime?: string
  updatedTime?: string
}

export interface GrowthInviteCodeRow {
  id: number
  code?: string
  ownerId?: number
  ownerUsername?: string
  ownerNickname?: string
  channel?: string
  remark?: string
  boundUserId?: number | null
  boundUsername?: string | null
  boundNickname?: string | null
  boundTime?: string | null
  referralCount?: number
  validReferralCount?: number
  totalCommission?: number
  totalTokenReward?: number
  enabled?: number
  enabledText?: string
  createdTime?: string
}

export interface GrowthReferralRow {
  id: number
  inviterId?: number
  inviterUsername?: string
  inviterNickname?: string
  inviteeId?: number
  inviteeUsername?: string
  inviteeNickname?: string
  inviteeAvatar?: string
  inviteCode?: string
  tierCode?: string
  tierName?: string
  firstConsumeAmount?: number
  totalCommission?: number
  totalTokenReward?: number
  boundTime?: string
  firstConsumeTime?: string
  status?: string
  statusText?: string
}

// ==================== 接口方法 ====================

/** 增长中心仪表盘（统计卡片 + 趋势 + 排行榜） */
export function getAdminGrowthDashboard() {
  return request.get<any>({ url: '/growth/dashboard' })
    .then(value => requireRecordPayload<Record<string, any>>(value, '增长中心仪表盘') as GrowthDashboard)
}

/** 全局配置查询 */
export function getGrowthConfig() {
  return request.get<any>({ url: '/growth/config' })
    .then(value => requireRecordPayload<Record<string, any>>(value, '增长配置') as GrowthGlobalConfig)
}

/** 全局配置更新（token 奖励数 / 最低提现金额 / 首月分成开关 / 提现开关） */
export function saveGrowthConfig(data: Partial<GrowthGlobalConfig> & { updatedBy?: string }) {
  return request.put<any>({ url: '/growth/config', data })
    .then(value => requireRecordPayload<Record<string, any>>(value, '增长配置') as GrowthGlobalConfig)
}

/** 代理等级配置列表（含未启用） */
export function getGrowthTierConfigs() {
  return request.get<any>({ url: '/growth/tier-config' })
    .then(value => requireListPayload<GrowthTierConfig>(value, '代理等级配置'))
}

/** 代理等级配置新增/更新 */
export function saveGrowthTierConfig(data: Partial<GrowthTierConfig>) {
  return request.put<any>({ url: '/growth/tier-config', data })
    .then(value => requireRecordPayload<Record<string, any>>(value, '代理等级配置') as GrowthTierConfig)
}

/** 后台排行榜 */
export function getAdminGrowthLeaderboard(limit = 50) {
  return request.get<any>({ url: '/growth/leaderboard', params: { limit } })
    .then(value => requireListPayload<GrowthLeaderboardRow>(value, '排行榜'))
}

/** 后台收益趋势 */
export function getAdminGrowthTrend(days = 30) {
  return request.get<any>({ url: '/growth/trend', params: { days } })
    .then(value => requireRecordPayload<Record<string, any>>(value, '收益趋势') as GrowthDashboard['trend'])
}

/** 提现申请列表 */
export function getGrowthWithdrawalsPage(params: {
  status?: string
  page?: number
  size?: number
} = {}) {
  return request.get<any>({ url: '/growth/withdrawals', params })
    .then(value => requirePagePayload<GrowthWithdrawalRow>(value, '提现申请'))
}

/** 提现审批：通过 */
export function approveGrowthWithdrawal(id: number, reviewer = 'admin') {
  return request.put<any>({
    url: `/growth/withdrawals/${id}/approve`,
    data: { reviewer }
  })
    .then(value => requireRecordPayload<Record<string, any>>(value, '提现审批') as GrowthWithdrawalRow)
}

/** 提现审批：驳回 */
export function rejectGrowthWithdrawal(id: number, rejectReason: string, reviewer = 'admin') {
  return request.put<any>({
    url: `/growth/withdrawals/${id}/reject`,
    data: { reviewer, rejectReason }
  })
    .then(value => requireRecordPayload<Record<string, any>>(value, '提现审批') as GrowthWithdrawalRow)
}

/** 邀请码列表（带统计） */
export function getGrowthInviteCodesPage(params: {
  page?: number
  size?: number
  keyword?: string
} = {}) {
  return request.get<any>({ url: '/growth/invite-codes', params })
    .then(value => requirePagePayload<GrowthInviteCodeRow>(value, '邀请码'))
}

/** 全部推荐关系（二级用户明细） */
export function getGrowthReferralsPage(params: {
  page?: number
  size?: number
  keyword?: string
} = {}) {
  return request.get<any>({ url: '/growth/referrals', params })
    .then(value => requirePagePayload<GrowthReferralRow>(value, '推荐关系'))
}
