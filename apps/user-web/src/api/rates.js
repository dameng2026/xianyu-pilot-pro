import request from '../utils/request'

/**
 * 评价管理 API。
 *
 * 后端：Java 网关代理到 Python automation-service 的 /api/rates/*
 * 仅鱼小铺账号（fish_shop_user=1）可用，普通账号由后端拒绝。
 */

/**
 * 查询本地缓存的评价列表（多账号聚合 + 分类筛选 + 关键词搜索 + 分页）。
 * 仅查询本地数据库，不触发闲鱼请求（缓存优先策略）。
 * @param {Object} params
 * @param {number} [params.accountId] 账号ID，不传则聚合全部鱼小铺账号
 * @param {string} [params.category] 评价分类：all/pending/done
 * @param {string} [params.keyword] 关键词搜索：订单号/商品ID/商品标题/买家昵称
 * @param {number} [params.page] 页码，从1开始
 * @param {number} [params.pageSize] 每页数量，最大100
 */
export function getRates(params) {
  return request({
    url: '/rates',
    method: 'get',
    params
  })
}

/**
 * 触发评价同步。
 * @param {Object} [data]
 * @param {number} [data.accountId] 同步单个账号；不传则同步全部鱼小铺账号
 * @param {boolean} [data.forceFull] 是否强制全量同步（忽略缓存，拉取所有页）
 */
export function syncRates(data) {
  return request({
    url: '/rates/sync',
    method: 'post',
    data: data || {}
  })
}

/**
 * 查询同步状态（缓存是否过期、是否正在同步、最后同步时间）。
 * @param {number} [accountId] 账号ID，不传则查询全部账号聚合状态
 */
export function getRateSyncStatus(accountId) {
  return request({
    url: '/rates/sync-status',
    method: 'get',
    params: { accountId: accountId || undefined }
  })
}

/**
 * 查询评价概览统计（总数、待评价、已评价、最近同步时间）。
 * 好评、中评、差评统计仅在评价等级数值映射得到可靠确认后才可展示。
 * @param {number} [accountId]
 */
export function getRateOverview(accountId) {
  return request({
    url: '/rates/overview',
    method: 'get',
    params: { accountId: accountId || undefined }
  })
}

/**
 * 创建评价（写操作，需多重校验）。
 *
 * 后端会再次校验：
 * - 账号归属与鱼小铺权限
 * - 订单属于该账号
 * - 订单尚未完成卖家评价
 * - 评价等级已得到可靠映射（当前仅支持好评 rate=1）
 * - anonymous 为明确布尔值
 * - 同一账号同一订单同时只能存在一个评价请求
 *
 * @param {Object} data
 * @param {number} data.accountId 闲鱼账号ID
 * @param {string} data.orderId 订单ID（字符串）
 * @param {number} data.rate 评价等级（当前仅支持 1=好评）
 * @param {string} data.feedback 评价内容
 * @param {boolean} data.anonymous 是否匿名评价
 */
export function createRate(data) {
  return request({
    url: '/rates/create',
    method: 'post',
    data
  })
}

/**
 * 列出当前租户下所有鱼小铺账号（用于前端账号选择下拉框）。
 * 普通闲鱼账号不会出现在此列表中。
 */
export function getRateFishShopAccounts() {
  return request({
    url: '/rates/fish-shop-accounts',
    method: 'get'
  })
}

// ============================================================
// 自动补评价：执行日志查询 + 调度器状态 + 手动触发
// ============================================================

/**
 * 查询自动补评价执行日志（分页）。
 * @param {Object} params
 * @param {number} [params.accountId] 账号ID，不传则查询全部账号
 * @param {number} [params.page] 页码，从1开始
 * @param {number} [params.pageSize] 每页数量，最大100
 */
export function getAutoRateLogs(params) {
  return request({
    url: '/rates/auto-rate/logs',
    method: 'get',
    params
  })
}

/**
 * 查询自动补评价调度器运行状态（用于诊断调度是否正常）。
 */
export function getAutoRateSchedulerStatus() {
  return request({
    url: '/rates/auto-rate/scheduler-status',
    method: 'get'
  })
}

/**
 * 手动触发单个账号的自动补评价（立即执行一次）。
 * 后端会校验：账号已配置/已开启自动评价、为鱼小铺账号、Cookie 有效、评价内容已配置。
 * @param {Object} data
 * @param {number} data.accountId 闲鱼账号ID
 */
export function triggerAutoRateRun(data) {
  return request({
    url: '/rates/auto-rate/run',
    method: 'post',
    data: data || {}
  })
}
