import request from '../utils/request.js'

// 增长合伙人仪表盘（统计卡片 + 代理等级 + 全局配置 + 提现阈值）
export function getGrowthDashboard() {
  return request({ url: '/growth/dashboard', method: 'get' }).then(res => res?.data)
}

// 收益趋势（近 N 天）
export function getGrowthTrend(days = 30) {
  return request({ url: '/growth/trend', method: 'get', params: { days } }).then(res => res?.data)
}

// 拉新排行榜
export function getGrowthLeaderboard(limit = 10) {
  return request({ url: '/growth/leaderboard', method: 'get', params: { limit } }).then(res => res?.data)
}

// 二级用户明细
export function getGrowthReferrals(params = {}) {
  return request({ url: '/growth/referrals', method: 'get', params }).then(res => res?.data)
}

// 我的邀请码列表
export function getMyInviteCodes() {
  return request({ url: '/growth/invite-codes', method: 'get' }).then(res => res?.data)
}

// 创建邀请码
export function createInviteCode(data = {}) {
  return request({ url: '/growth/invite-codes', method: 'post', data }).then(res => res?.data)
}

// 获取推广链接
export function getPromoteLink() {
  return request({ url: '/growth/promote-link', method: 'get' }).then(res => res?.data)
}

// 代理等级配置（前台展示用）
export function getGrowthTierConfig() {
  return request({ url: '/growth/tier-config', method: 'get' }).then(res => res?.data)
}

// 我的余额（用于个人中心卡片）
export function getGrowthBalance() {
  return request({ url: '/growth/balance', method: 'get' }).then(res => res?.data)
}

// 提现申请
export function requestWithdrawal(data) {
  return request({ url: '/growth/withdrawal', method: 'post', data }).then(res => res?.data)
}

// 我的提现记录
export function getMyWithdrawals(page = 1, size = 20) {
  return request({ url: '/growth/withdrawals', method: 'get', params: { page, size } }).then(res => res?.data)
}
