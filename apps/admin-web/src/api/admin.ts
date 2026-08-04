import request from '@/utils/http'
import {
  requireAffectedCount,
  requireListPayload,
  requirePagePayload,
  requireRecordPayload
} from '@/utils/api-payload'

export interface AdminModuleColumn {
  prop: string
  label: string
  width?: number
  type?: 'tag' | string
}

export interface AdminModuleMeta {
  key: string
  title: string
  description: string
  columns: AdminModuleColumn[]
}

export interface AdminModulePageQuery {
  current?: number
  size?: number
  keyword?: string
  status?: string
  sortField?: string
  sortOrder?: 'asc' | 'desc'
}

export interface AdminPageResult<T = any> {
  records: T[]
  current: number
  size: number
  total: number
}

export interface ModelConfigConnectionTestResult {
  ok: boolean
  durationMs?: number
  responseSummary?: string
  message: string
}

export interface FetchModelListResult {
  ok: boolean
  models: string[]
  message: string
}

export interface RequestUiOptions {
  showErrorMessage?: boolean
}

export function getAdminSummary(options: RequestUiOptions = {}) {
  return request.get<any>({ url: '/admin/dashboard/summary', showErrorMessage: options.showErrorMessage })
}

export function getAdminTrend(range: 7 | 30 | 90 = 7, options: RequestUiOptions = {}) {
  return request.get<any>({ url: '/admin/dashboard/trend', params: { range }, showErrorMessage: options.showErrorMessage })
}

export function getRecentEvents(options: RequestUiOptions = {}) {
  return request.get<any[]>({ url: '/admin/dashboard/recent-events', showErrorMessage: options.showErrorMessage })
    .then(value => requireListPayload<any>(value, '最近后台操作'))
}

/**
 * 仪表盘首屏聚合端点：一次返回 summary + trend + recentEvents + pendingTasks + realtimeStats + topHotGoods + riskDistribution + systemHealth
 * 减少前端多次 HTTP 请求，加速首屏渲染
 * 缓存 30 秒，避免短时间内重复进入仪表盘时重复请求
 */
export function getDashboardInit(options: RequestUiOptions = {}) {
  return request.get<any>({
    url: '/admin/dashboard/init',
    cacheTtl: 30 * 1000,
    showErrorMessage: options.showErrorMessage
  })
    .then(value => requireRecordPayload<Record<string, any>>(value, '运营概览'))
}

/**
 * 仪表盘财务统计：从 payment_order 真实聚合收入，从 ai_usage_log 真实聚合 AI 成本与 Token 消耗
 * - 按 range 7/30/90 天统计范围内总数 + 每日收入趋势
 * - 同时返回今日收入/今日 AI 成本/今日利润，供 KPI 卡片使用
 */
export interface DashboardFinanceData {
  range: number
  dates: string[]
  totalIncomeCent: number
  totalAiCostCent: number
  totalProfitCent: number
  totalChargeTokens: number
  marginPercent: number | null
  dailyIncome: number[]
  todayIncomeCent: number
  todayAiCostCent: number
  todayProfitCent: number
}

export function getDashboardFinance(range: 7 | 30 | 90 = 7, options: RequestUiOptions = {}) {
  return request.get<DashboardFinanceData>({
    url: '/admin/dashboard/finance',
    params: { range },
    showErrorMessage: options.showErrorMessage
  }).then(value => requireRecordPayload<Record<string, any>>(value, '财务统计') as DashboardFinanceData)
}

/**
 * 通知投递统计：从 notification_delivery_log 真实聚合
 */
export interface DashboardNotifyStats {
  range: number
  totalCount: number
  successCount: number
  failedCount: number
  todayCount: number
  avgCostMs: number
  byChannel: Array<{ channel: string; total: number; success: number }>
}

export function getNotifyStats(range: 7 | 30 | 90 = 7, options: RequestUiOptions = {}) {
  return request.get<DashboardNotifyStats>({
    url: '/admin/dashboard/notify-stats',
    params: { range },
    showErrorMessage: options.showErrorMessage
  }).then(value => requireRecordPayload<Record<string, any>>(value, '通知投递统计') as DashboardNotifyStats)
}

/**
 * 客户端错误监控：从 client_error_log 真实聚合
 */
export interface DashboardClientErrorStats {
  range: number
  totalCount: number
  todayCount: number
  topErrorTypes: Array<{ errorType: string; count: number }>
}

export function getClientErrorStats(range: 7 | 30 | 90 = 7, options: RequestUiOptions = {}) {
  return request.get<DashboardClientErrorStats>({
    url: '/admin/dashboard/client-error-stats',
    params: { range },
    showErrorMessage: options.showErrorMessage
  }).then(value => requireRecordPayload<Record<string, any>>(value, '客户端错误统计') as DashboardClientErrorStats)
}

/**
 * 卡密库存统计：从 card_group/card_item 真实聚合
 */
export interface DashboardStockStats {
  totalGroups: number
  totalStock: number
  usedStock: number
  remainStock: number
  lowStockGroups: number
  todayConsumed: number
  lowStockList: Array<{ id: number; group_name: string; remain_count: number; alert_threshold: number }>
}

export function getStockStats(options: RequestUiOptions = {}) {
  return request.get<DashboardStockStats>({
    url: '/admin/dashboard/stock-stats',
    showErrorMessage: options.showErrorMessage
  }).then(value => requireRecordPayload<Record<string, any>>(value, '卡密库存统计') as DashboardStockStats)
}

/**
 * 商机与商品同步统计：从 xianyu_goods_sync_task 和 opportunity_image_history 真实聚合
 */
export interface DashboardSyncStats {
  range: number
  syncTotal: number
  syncSuccess: number
  syncFailed: number
  todaySyncCount: number
  imageGenerated: number
}

export function getSyncStats(range: 7 | 30 | 90 = 7, options: RequestUiOptions = {}) {
  return request.get<DashboardSyncStats>({
    url: '/admin/dashboard/sync-stats',
    params: { range },
    showErrorMessage: options.showErrorMessage
  }).then(value => requireRecordPayload<Record<string, any>>(value, '商机与商品同步统计') as DashboardSyncStats)
}

/**
 * 实时监控卡片：在线账号数 / 今日发布数 / 今日成交额 / 今日 AI 调用次数 / 工作流执行中
 */
export function getRealtimeStats(options: RequestUiOptions = {}) {
  return request.get<{
    onlineAccounts: number | string
    todayPublished: number | string
    todaySalesAmount: number | string
    todayAiCalls: number | string
    todayAiFailures: number | string
    runningWorkflows: number | string
  }>({ url: '/admin/dashboard/realtime-stats', showErrorMessage: options.showErrorMessage })
    .then(value => requireRecordPayload<Record<string, any>>(value, '实时监控') as {
      onlineAccounts: number | string
      todayPublished: number | string
      todaySalesAmount: number | string
      todayAiCalls: number | string
      todayAiFailures: number | string
      runningWorkflows: number | string
    })
}

/**
 * Top 5 热销商品（基于 hot_goods_stat 表，按 daily_sales DESC）
 */
export function getTopHotGoods() {
  return request.get<Array<{
    id: number
    title: string
    price: number | string
    imageUrl: string
    sales: number
    stat_date: string
    accountName: string
  }>>({ url: '/admin/dashboard/top-hot-goods' })
    .then(value => requireListPayload<{
      id: number
      title: string
      price: number | string
      imageUrl: string
      sales: number
      stat_date: string
      accountName: string
    }>(value, '热销商品'))
}

/**
 * 风控分布：按 risk_level 分组账号数
 */
export function getRiskDistribution() {
  return request.get<Array<{ risk_level: number; count: number }>>({
    url: '/admin/dashboard/risk-distribution'
  }).then(value => requireListPayload<{ risk_level: number; count: number }>(value, '风险分布'))
}

/**
 * 系统健康状态：聚合 core-api / automation-service / crawler-service 三个服务的存活状态
 */
export function getSystemHealth(options: RequestUiOptions = {}) {
  return request.get<{
    coreApi: ServiceHealthItem
    automationService: ServiceHealthItem
    crawlerService: ServiceHealthItem
  }>({ url: '/admin/dashboard/system-health', showErrorMessage: options.showErrorMessage })
    .then(value => requireRecordPayload<Record<string, any>>(value, '系统健康') as {
      coreApi: ServiceHealthItem
      automationService: ServiceHealthItem
      crawlerService: ServiceHealthItem
    })
}

export interface ServiceHealthItem {
  name: string
  port?: number
  status: 'up' | 'down' | 'degraded'
  latencyMs: number
  statusCode?: number
  error?: string | null
}

export interface PendingTask {
  title: string
  time: string
  type: 'workflow' | 'risk' | 'notify' | 'kami'
  source: string
  sourceId: number | string
}

export function getPendingTasks() {
  return request.get<PendingTask[]>({ url: '/admin/dashboard/pending-tasks' })
    .then(value => requireListPayload<PendingTask>(value, '待处理事项'))
}

// 通知已读状态
export function markNotificationsRead(eventIds: Array<number | string>, eventSource = 'recent_event') {
  return request.post<{ marked: number }>({
    url: '/admin/notifications/read-status',
    params: { eventIds, eventSource }
  })
}

export function getReadNotificationIds(eventSource = 'recent_event') {
  return request.get<number[]>({
    url: '/admin/notifications/read-status',
    params: { eventSource }
  }).then(value => requireListPayload<number>(value, '通知已读状态'))
}

export function markAllNotificationsRead(eventIds: Array<number | string>, eventSource = 'recent_event') {
  return request.post<{ marked: number }>({
    url: '/admin/notifications/mark-all-read',
    params: { eventIds, eventSource }
  })
}

// 管理员头像上传
export function uploadAdminAvatar(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post<{ url: string; fileName: string }>({
    url: '/admin/avatar/upload',
    params: formData,
    headers: { 'Content-Type': 'multipart/form-data' }
  }).then((value) => {
    const payload = requireRecordPayload<Record<string, unknown>>(value, '头像上传')
    if (typeof payload.url !== 'string' || !payload.url.trim()) {
      throw new Error('头像上传响应格式异常，请稍后重试')
    }
    return payload as { url: string; fileName: string }
  })
}

/** 模块元数据基本不变，缓存 10 分钟 */
export function getModuleMeta(moduleKey: string) {
  return request.get<AdminModuleMeta>({ url: `/admin/modules/${moduleKey}/meta`, cacheTtl: 10 * 60 * 1000 })
}

export function getModuleStats(moduleKey: string) {
  return request.get<any>({ url: `/admin/modules/${moduleKey}/stats` })
}

export function getModulePage(moduleKey: string, params: AdminModulePageQuery) {
  return request.get<AdminPageResult>({ url: `/admin/modules/${moduleKey}/page`, params })
    .then(value => requirePagePayload(value, '模块列表') as AdminPageResult)
}

export function getModuleDetail(moduleKey: string, id: number | string) {
  return request.get<any>({ url: `/admin/modules/${moduleKey}/${id}` })
}

export function saveModuleRecord(moduleKey: string, data: Record<string, any>) {
  return request.post<any>({
    url: `/admin/modules/${moduleKey}`,
    data,
    showSuccessMessage: true
  })
}

export function updateModuleStatus(moduleKey: string, id: number | string, status: string) {
  return request.put<void>({
    url: `/admin/modules/${moduleKey}/${id}/status`,
    params: { status },
    showSuccessMessage: true
  })
}

export function batchUpdateModuleStatus(
  moduleKey: string,
  ids: Array<number | string>,
  status: string
) {
  return request.post<any>({
    url: `/admin/modules/${moduleKey}/batch-status`,
    data: { ids, status },
    showSuccessMessage: true
  })
}

export function batchDeleteModuleRecords(moduleKey: string, ids: Array<number | string>) {
  return request.post<any>({
    url: `/admin/modules/${moduleKey}/batch-delete`,
    data: { ids },
    showSuccessMessage: true
  })
}

export function deleteModuleRecord(moduleKey: string, id: number | string) {
  return request.del<void>({ url: `/admin/modules/${moduleKey}/${id}`, showSuccessMessage: true })
}

export function getModelConfigRecord(moduleKey: string) {
  return getModulePage(moduleKey, { current: 1, size: 1 }).then((page) => page.records[0] || null)
}

export function saveModelConfigRecord(moduleKey: string, data: Record<string, any>) {
  return request.post<any>({ url: `/admin/modules/${moduleKey}`, data })
}

export function updateModelConfigEnabled(moduleKey: string, id: number | string, status: string) {
  return request.put<void>({ url: `/admin/modules/${moduleKey}/${id}/status`, params: { status } })
}

export function testModelConfigConnection(
  moduleKey: string,
  data: Record<string, any>
): Promise<ModelConfigConnectionTestResult> {
  return request.post<ModelConfigConnectionTestResult>({
    url: `/admin/modules/${moduleKey}/test-connection`,
    data
  }).then((value) => {
    const result = requireRecordPayload<Record<string, unknown>>(value, '模型连接测试')
    if (typeof result.ok !== 'boolean' || typeof result.message !== 'string') {
      throw new Error('模型连接测试响应格式异常，请稍后重试')
    }
    return result as unknown as ModelConfigConnectionTestResult
  })
}

export function fetchModelList(
  moduleKey: string,
  data: { baseUrl: string; apiKey: string; id?: number | null }
): Promise<FetchModelListResult> {
  return request.post<FetchModelListResult>({
    url: `/admin/modules/${moduleKey}/fetch-models`,
    data
  }).then((value) => {
    const result = requireRecordPayload<Record<string, unknown>>(value, '模型列表')
    if (
      typeof result.ok !== 'boolean'
      || typeof result.message !== 'string'
      || !Array.isArray(result.models)
      || !result.models.every(model => typeof model === 'string')
    ) {
      throw new Error('模型列表响应格式异常，请稍后重试')
    }
    return result as unknown as FetchModelListResult
  })
}

export function getModuleExportUrl(moduleKey: string, params: AdminModulePageQuery = {}) {
  const search = new URLSearchParams()
  if (params.keyword) search.set('keyword', params.keyword)
  if (params.status) search.set('status', params.status)
  const qs = search.toString()
  return `/admin-api/admin/modules/${moduleKey}/export${qs ? `?${qs}` : ''}`
}

export function refreshHotGoodsStat(minSales: number = 5) {
  return request.post<any>({ url: '/admin/hot-goods/refresh', data: { minSales }, showSuccessMessage: true })
    .then(value => requireAffectedCount(value, '热销商品统计刷新'))
}
