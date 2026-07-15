export type DashboardTone = 'brand' | 'success' | 'warning' | 'danger' | 'muted'
export type DashboardDataStatus = 'loading' | 'ready' | 'empty' | 'degraded' | 'unavailable'

export interface DashboardDataState {
  status: DashboardDataStatus
  message: string
  failedSources: string[]
}

export interface DashboardMetricItem {
  key: string
  label: string
  value: string
  delta: string
  tone?: DashboardTone
  note?: string
}

export interface DashboardMetricGroup {
  key: string
  title: string
  items: DashboardMetricItem[]
}

export interface DashboardChip {
  key: string
  label: string
  value: string
  tone: DashboardTone
}

export interface DashboardSeries {
  key: string
  label: string
  color: string
  values: number[]
}

export interface DashboardChartModel {
  labels: string[]
  series: DashboardSeries[]
  kind?: 'line' | 'bar'
}

export interface DashboardProgressItem {
  key: string
  label: string
  value: string
  percent: number
  tone?: DashboardTone
}

export interface DashboardFunnelStage {
  key: string
  label: string
  value: string
  percent: string
}

export interface DashboardPendingItem {
  title: string
  time: string
  type: string
  severity: DashboardTone
}

export interface DashboardTableRow {
  label: string
  value: string
  extra?: string
  tone?: DashboardTone
}

export interface DashboardPanel {
  key: string
  title: string
  subtitle?: string
  metrics?: DashboardMetricItem[]
  chart?: DashboardChartModel
  progress?: DashboardProgressItem[]
  table?: DashboardTableRow[]
  pending?: DashboardPendingItem[]
  gauge?: {
    label: string
    value: number | null
    detail: string
  }
  emptyState?: {
    title: string
    description: string
  }
  footer?: string
}

export interface DashboardOverviewFixture {
  summary: Record<string, any>
  trend: Record<string, any>
  realtimeStats: Record<string, any>
  pendingTasks: any[]
  topHotGoods: any[]
  riskDistribution: any[]
  systemHealth: Record<string, any> | null
  recentEvents: any[]
  aiMonitor: Record<string, any>
  autoReplyMonitor: Record<string, any>
  workflowMonitor: Record<string, any>
  tokenStats: Record<string, any>
  costStats: Record<string, any>
  dataState?: DashboardDataState
}

export interface DashboardOverviewModel {
  dataState: DashboardDataState
  hero: {
    title: string
    description: string
    chips: DashboardChip[]
  }
  kpiGroups: DashboardMetricGroup[]
  finance: {
    cards: DashboardMetricItem[]
    chart: DashboardChartModel
    gauge: {
      value: number | null
      detail: string
    }
    breakdown: DashboardTableRow[]
  }
  funnel: {
    stages: DashboardFunnelStage[]
    highlights: DashboardMetricItem[]
  }
  growth: {
    cards: DashboardMetricItem[]
    chart: DashboardChartModel
  }
  monitoring: {
    cards: DashboardPanel[]
  }
  servicePanels: DashboardPanel[]
  qualityPanels: DashboardPanel[]
  bottom: {
    cards: DashboardPanel[]
  }
  pendingItems: DashboardPendingItem[]
  sectionOrder: string[]
}

const FINANCE_RANGE_DAYS = 7
export function createOverviewTestFixture(): DashboardOverviewFixture {
  return {
    summary: {
      cards: [
        { key: 'accountCount', label: '账号数', value: 3, desc: '当前快照' },
        { key: 'goodsCount', label: '商品总数', value: 79, desc: '当前快照' },
        { key: 'sellingGoodsCount', label: '在售商品', value: 79, desc: '当前快照' },
        { key: 'todayOrderCount', label: '今日订单', value: 0, desc: '今日实时口径' },
        { key: 'todaySalesAmount', label: '今日销售额', value: 0, desc: '今日实时口径' },
        { key: 'autoReplyCount', label: 'AI回复', value: 12, desc: '今日实时口径' },
        { key: 'deliverySuccessCount', label: '发货成功', value: 0, desc: '今日实时口径' },
        { key: 'deliveryFailCount', label: '发货失败', value: 0, desc: '今日实时口径' },
        { key: 'pendingDeliveryCount', label: '待发货', value: 0, desc: '今日实时口径' }
      ]
    },
    trend: {
      dates: ['2026-06-26', '2026-06-27', '2026-06-28', '2026-06-29', '2026-06-30', '2026-07-01', '2026-07-02'],
      orders: [0, 0, 0, 0, 0, 0, 0],
      delivery: [0, 0, 0, 0, 0, 0, 0],
      ai: [8, 10, 12, 14, 75, 18, 10]
    },
    realtimeStats: {
      onlineAccounts: 0,
      todayPublished: 13,
      todaySalesAmount: '0.00',
      todayAiCalls: 50,
      todayAiFailures: 0,
      runningWorkflows: 0
    },
    pendingTasks: [
      { title: '工作流执行失败 [WF202607021801410732]', time: '18:01:41', type: 'workflow', source: 'workflow', sourceId: 1 },
      { title: '通知发送失败 [飞书机器人] Cookie 到期', time: '17:45:11', type: 'notify', source: 'notify', sourceId: 2 }
    ],
    topHotGoods: [
      { id: 1, title: '测试卡密商品1', price: 9.9, sales: 3, accountName: '测试账号A' },
      { id: 2, title: '测试卡密商品2', price: 8.8, sales: 2, accountName: '测试账号B' }
    ],
    riskDistribution: [{ risk_level: 0, count: 3 }],
    systemHealth: {
      coreApi: { name: 'core-api', port: 18080, status: 'up', latencyMs: 0 },
      automationService: { name: 'automation-service', status: 'up', latencyMs: 4 },
      crawlerService: { name: 'crawler-service', status: 'degraded', latencyMs: 2000 }
    },
    recentEvents: [
      { id: 242, module: 'DELETE_LOCAL', action: '仅删除本地商品', targetId: '242', time: '2026-07-03 11:44:34', result: '成功' }
    ],
    aiMonitor: { todayCalls: 50, todayChargeTokens: 0, todayCostCent: 0, lowBalanceUsers: 0, byScene: [] },
    autoReplyMonitor: { todayHits: 12, todayAutoAllowed: 12, todayManual: 0, actions: [] },
    workflowMonitor: { todayFailed: 1, running: 0, todayExecutions: 13, byStatus: [{ status: '成功', count: 12 }, { status: '失败', count: 1 }] },
    tokenStats: { totalTokens: 0, totalChargeTokens: 0, totalCostCent: 0, dailyTokens: [], dailyCost: [] },
    costStats: {
      dailyTrend: [
        { statDate: '2026-06-26', costCent: 0 },
        { statDate: '2026-06-27', costCent: 0 },
        { statDate: '2026-06-28', costCent: 0 },
        { statDate: '2026-06-29', costCent: 0 },
        { statDate: '2026-06-30', costCent: 0 },
        { statDate: '2026-07-01', costCent: 0 },
        { statDate: '2026-07-02', costCent: 0 }
      ],
      byScene: [],
      byModel: []
    }
  }
}

export function buildDashboardOverviewModel(input: DashboardOverviewFixture): DashboardOverviewModel {
  return {
    dataState: input.dataState || {
      status: 'ready',
      message: '仪表盘数据已加载',
      failedSources: []
    },
    hero: buildHero(input),
    kpiGroups: buildKpiGroups(input),
    finance: buildFinanceSection(input),
    funnel: buildFunnelSection(input),
    growth: buildGrowthSection(input),
    monitoring: {
      cards: buildMonitoringCards(input)
    },
    servicePanels: buildServicePanels(input),
    qualityPanels: buildQualityPanels(),
    bottom: {
      cards: buildBottomPanels(input)
    },
    pendingItems: buildPendingItems(input.pendingTasks),
    sectionOrder: [
      'kpi',
      'finance',
      'funnel-growth',
      'monitoring',
      'service-stock-alerts',
      'quality-sync',
      'bottom'
    ]
  }
}

function buildHero(input: DashboardOverviewFixture): DashboardOverviewModel['hero'] {
  const pending = buildPendingItems(input.pendingTasks)
  const pendingAvailable = !hasFailedSource(input, '仪表盘聚合接口')
  const aggregateUnavailable = hasFailedSource(input, '仪表盘聚合接口')
  const hasRiskData = Array.isArray(input.riskDistribution) && input.riskDistribution.length > 0
  const riskCount = (input.riskDistribution || [])
    .filter((item: any) => Number(item?.risk_level || 0) >= 2)
    .reduce((sum: number, item: any) => sum + toNumber(item?.count), 0)
  const health = input.systemHealth
  const services = [health?.coreApi, health?.automationService, health?.crawlerService].filter(Boolean)
  const healthyServices = services.filter(
    (item) => item?.status === 'up'
  ).length

  return {
    title: '闲鱼助手平台后台',
    description: '统一查看用户、套餐、商品、闲鱼账号、风控、AI 成本、自动化执行与系统健康状态。',
    chips: [
      { key: 'pending', label: '待处理事项', value: pendingAvailable ? `${pending.length} 项` : '数据不可用', tone: pendingAvailable && pending.length ? 'warning' : 'muted' },
      { key: 'delivery', label: '工作流执行', value: hasRecordData(input.workflowMonitor) ? `${compactNumber(input.workflowMonitor.todayExecutions)} 次` : '数据不可用', tone: hasRecordData(input.workflowMonitor) ? 'brand' : 'muted' },
      { key: 'risk', label: '风险提醒', value: !hasRiskData ? aggregateUnavailable ? '数据不可用' : '暂无账号数据' : riskCount ? `${riskCount} 个异常` : '未发现高风险', tone: !hasRiskData ? 'muted' : riskCount ? 'danger' : 'success' },
      { key: 'health', label: '服务健康', value: services.length ? `${healthyServices}/${services.length} 在线` : '数据不可用', tone: !services.length ? 'muted' : healthyServices === services.length ? 'success' : 'warning' }
    ]
  }
}

function buildKpiGroups(input: DashboardOverviewFixture): DashboardMetricGroup[] {
  const accountCount = statValue(input, 'accountCount')
  const goodsCount = statValue(input, 'goodsCount')
  const todayOrderCount = statValue(input, 'todayOrderCount')
  const hasSalesAmount = hasSummaryStat(input, 'todaySalesAmount')
  const todaySalesAmount = hasSalesAmount ? currencyValue(statValueRaw(input, 'todaySalesAmount')) : '--'
  const hasAiCost = hasOwn(input.aiMonitor, 'todayCostCent')
  const estimatedProfit = toNumber(statValueRaw(input, 'todaySalesAmount')) - centToYuan(input.aiMonitor?.todayCostCent)
  const hasReplyData = hasRecordData(input.autoReplyMonitor) || hasSummaryStat(input, 'autoReplyCount')
  const replyHits = hasReplyData ? compactNumber(replyHitCount(input)) : '--'
  const deliverySuccessCount = statValue(input, 'deliverySuccessCount')
  const pendingDeliveryCount = statValue(input, 'pendingDeliveryCount')
  const hasOrderCount = hasSummaryStat(input, 'todayOrderCount')
  const hasDeliveryData = hasSummaryStat(input, 'deliverySuccessCount') && hasSummaryStat(input, 'pendingDeliveryCount')
  const safeCount = (input.riskDistribution || []).find((item: any) => Number(item?.risk_level || 0) === 0)?.count ?? 0
  const hasRiskData = Array.isArray(input.riskDistribution) && input.riskDistribution.length > 0
  const aggregateUnavailable = hasFailedSource(input, '仪表盘聚合接口')

  return [
    {
      key: 'platform',
      title: '平台用户与租户',
      items: [
        metric('account-total', '账号总量', accountCount, noComparison(), 'brand', '已绑定账号'),
        metric('account-online', '实时在线账号', optionalCompact(input.realtimeStats, 'onlineAccounts'), '当前快照', toNumber(input.realtimeStats?.onlineAccounts) > 0 ? 'success' : 'muted', '非历史活跃口径'),
        metric('account-safe', '低风险账号', hasRiskData ? compactNumber(safeCount) : '--', hasRiskData ? `占比 ${percent(safeCount, toNumber(accountCount))}%` : aggregateUnavailable ? '风险数据不可用' : '暂无账号风险数据', hasRiskData ? 'success' : 'muted', '当前风险分布')
      ]
    },
    {
      key: 'trade',
      title: '交易与履约',
      items: [
        metric('goods-total', '商品总数', goodsCount, noComparison(), 'brand', '货盘规模'),
        metric('today-orders', '今日订单', todayOrderCount, hasOrderCount ? delta(statValueRaw(input, 'todayOrderCount')) : '订单数据不可用', hasOrderCount && toNumber(statValueRaw(input, 'todayOrderCount')) > 0 ? 'warning' : 'muted', '新增订单'),
        metric('delivery', '发货成功', deliverySuccessCount, hasDeliveryData ? `待发货 ${pendingDeliveryCount}` : '履约数据不可用', hasDeliveryData ? 'brand' : 'muted', '履约状态')
      ]
    },
    {
      key: 'service',
      title: '消息与客服',
      items: [
        metric('reply-hit', '消息命中量', replyHits, hasReplyData ? replyHitDelta(input) : '消息数据不可用', hasReplyData ? 'brand' : 'muted', '今日消息处理'),
        metric('reply-auto', 'AI 调用量', optionalCompact(input.realtimeStats, 'todayAiCalls'), '今日实时口径', toNumber(input.realtimeStats?.todayAiCalls) > 0 ? 'brand' : 'muted', 'AI 介入'),
        metric('reply-manual', '待人工跟进', optionalCompact(input.autoReplyMonitor, 'todayManual'), hasOwn(input.realtimeStats, 'todayAiFailures') ? `AI 失败 ${compactNumber(input.realtimeStats?.todayAiFailures)}` : 'AI 失败数据不可用', Number(input.autoReplyMonitor?.todayManual || 0) > 0 ? 'warning' : 'muted', '待人工关注')
      ]
    },
    {
      key: 'revenue',
      title: '收入与利润',
      items: [
        metric('sales-today', '今日收入', todaySalesAmount, noComparison(), 'brand', '订单成交额'),
        metric('ai-cost', '今日AI成本', hasOwn(input.aiMonitor, 'todayCostCent') ? centToCurrency(input.aiMonitor?.todayCostCent) : '--', noComparison(), hasOwn(input.aiMonitor, 'todayCostCent') ? 'warning' : 'muted', '模型成本'),
        metric(
          'profit',
          '今日毛估利润',
          hasSalesAmount && hasAiCost ? currencyValue(estimatedProfit) : '--',
          hasSalesAmount && hasAiCost ? marginDelta(todaySalesAmount, input.aiMonitor?.todayCostCent) : '收入或成本数据不可用',
          !hasSalesAmount || !hasAiCost
            ? 'muted'
            : estimatedProfit > 0
            ? 'success'
            : estimatedProfit < 0
              ? 'danger'
              : 'muted',
          '收入减AI成本（未扣商品成本/佣金/支付手续费）'
        )
      ]
    }
  ]
}

function buildFinanceSection(input: DashboardOverviewFixture): DashboardOverviewModel['finance'] {
  const costTrend = Array.isArray(input.costStats?.dailyTrend) ? input.costStats.dailyTrend.slice(-FINANCE_RANGE_DAYS) : []
  const labels = buildRangeLabels(costTrend, [], FINANCE_RANGE_DAYS)
  const expenseSeries = labels.map((label, index) => {
    const row = (input.costStats?.dailyTrend || [])[index]
    return centToYuan(row?.costCent || 0)
  })
  const hasIncome = hasSummaryStat(input, 'todaySalesAmount')
  const hasCost = hasOwn(input.aiMonitor, 'todayCostCent')
  const todayIncome = toNumber(statValueRaw(input, 'todaySalesAmount'))
  const todayCost = centToYuan(input.aiMonitor?.todayCostCent)
  const todayProfit = todayIncome - todayCost
  const chargeTokenSource = hasOwn(input.tokenStats, 'totalChargeTokens')
    ? input.tokenStats?.totalChargeTokens
    : input.aiMonitor?.todayChargeTokens
  const hasChargeTokens = hasOwn(input.tokenStats, 'totalChargeTokens') || hasOwn(input.aiMonitor, 'todayChargeTokens')
  const chargeTokens = toNumber(chargeTokenSource)
  const profitAvailable = hasIncome && hasCost
  const profitTone: DashboardTone = !profitAvailable ? 'muted' : todayProfit > 0 ? 'success' : todayProfit < 0 ? 'danger' : 'muted'
  const margin = profitAvailable && todayIncome > 0 ? Math.round((todayProfit / todayIncome) * 100) : null

  return {
    cards: [
      metric('income', '今日收入(元)', hasIncome ? currencyValue(todayIncome) : '--', noComparison(), hasIncome ? 'brand' : 'muted', '订单成交'),
      metric('cost', '今日AI成本(元)', hasCost ? currencyValue(todayCost) : '--', noComparison(), hasCost ? 'warning' : 'muted', '模型成本'),
      metric('profit', '今日毛估利润(元)', profitAvailable ? currencyValue(todayProfit) : '--', profitAvailable ? '今日估算口径' : '收入或成本数据不可用', profitTone, '收入减AI成本（未扣商品成本/佣金/支付手续费）'),
      metric('token', 'Token 消耗(万)', hasChargeTokens ? compactWan(chargeTokens) : '--', hasChargeTokens ? '累计计费口径' : 'Token 数据不可用', 'muted', '计费口径')
    ],
    chart: {
      labels,
      series: labels.length
        ? [{ key: 'cost', label: 'AI成本(元)', color: '#22c55e', values: expenseSeries }]
        : []
    },
    gauge: {
      value: margin,
      detail: margin === null ? '无有效收入或成本，无法计算利润率' : '利润率'
    },
    breakdown: [
      { label: '收入', value: hasIncome ? currencyValue(todayIncome) : '--', tone: hasIncome ? 'success' : 'muted' },
      { label: 'AI 成本', value: hasCost ? currencyValue(todayCost) : '--', tone: hasCost ? 'warning' : 'muted' },
      { label: '净利润', value: profitAvailable ? currencyValue(todayProfit) : '--', tone: profitAvailable ? profitTone : 'muted' }
    ]
  }
}

function buildFunnelSection(input: DashboardOverviewFixture): DashboardOverviewModel['funnel'] {
  const hasOrderData = hasSummaryStat(input, 'todayOrderCount')
  if (!hasOrderData) {
    return {
      stages: ['created', 'paid', 'shipped', 'completed'].map((key, index) => ({
        key,
        label: ['下单', '付款', '发货', '完成'][index],
        value: '--',
        percent: '--'
      })),
      highlights: [
        metric('delivery-rate', '整体转化率', '--', '订单数据不可用', 'muted', '完成 / 下单'),
        metric('payment-latency', '平均付款时长', '--', '数据暂不可用', 'muted', '时长接口待接入'),
        metric('shipping-latency', '平均发货时长', '--', '数据暂不可用', 'muted', '时长接口待接入')
      ]
    }
  }
  const created = toNumber(statValueRaw(input, 'todayOrderCount'))
  const paid = Math.max(0, created - Math.min(created, toNumber(statValueRaw(input, 'pendingDeliveryCount'))))
  const shipped = toNumber(statValueRaw(input, 'deliverySuccessCount'))
  const completed = Math.max(0, shipped - toNumber(statValueRaw(input, 'deliveryFailCount')))

  return {
    stages: [
      funnelStage('created', '下单', created, created > 0 ? 100 : null),
      funnelStage('paid', '付款', paid, created > 0 ? Math.round((paid / created) * 100) : null),
      funnelStage('shipped', '发货', shipped, paid > 0 ? Math.round((shipped / paid) * 100) : null),
      funnelStage('completed', '完成', completed, created > 0 ? Math.round((completed / created) * 100) : null)
    ],
    highlights: [
      metric('delivery-rate', '整体转化率', created > 0 ? `${Math.round((completed / created) * 100)}%` : '--', created > 0 ? '今日订单口径' : '今日暂无订单', created > 0 ? 'brand' : 'muted', '完成 / 下单'),
      metric('payment-latency', '平均付款时长', '--', '数据暂不可用', 'muted', '时长接口待接入'),
      metric('shipping-latency', '平均发货时长', '--', '数据暂不可用', 'muted', '时长接口待接入')
    ]
  }
}

function buildGrowthSection(input: DashboardOverviewFixture): DashboardOverviewModel['growth'] {
  const activeAccounts = toNumber(input.realtimeStats?.onlineAccounts)
  const activeAvailable = hasOwn(input.realtimeStats, 'onlineAccounts')

  return {
    cards: [
      metric('new-users', '新增用户', '--', '数据暂不可用', 'muted', '用户增长接口待接入'),
      metric('active-users', '实时在线账号', activeAvailable ? compactNumber(activeAccounts) : '--', activeAvailable ? '当前快照' : '实时数据不可用', activeAvailable && activeAccounts > 0 ? 'success' : 'muted', '非历史活跃用户口径'),
      metric('paid-members', '付费租户', '--', '数据暂不可用', 'muted', '订阅增长接口待接入')
    ],
    chart: {
      labels: [],
      series: []
    }
  }
}

function buildMonitoringCards(input: DashboardOverviewFixture): DashboardPanel[] {
  const aggregateUnavailable = hasFailedSource(input, '仪表盘聚合接口')
  const aiCalls = toNumber(input.realtimeStats?.todayAiCalls)
  const hasAiFailureCount = hasOwn(input.realtimeStats, 'todayAiFailures')
  const failureRate = aiCalls > 0 && hasAiFailureCount
    ? Math.round((toNumber(input.realtimeStats?.todayAiFailures) / Math.max(1, toNumber(input.realtimeStats?.todayAiCalls))) * 100)
    : null
  const riskRows = (input.riskDistribution || []).map((item: any) => ({
    label: riskLabel(item?.risk_level),
    value: compactNumber(item?.count),
    extra: `${percent(item?.count, sumCounts(input.riskDistribution))}%`,
    tone: riskTone(item?.risk_level)
  }))
  const workflowStatuses = normalizeStatusRows(input.workflowMonitor?.byStatus || [])
  const successCount = workflowStatuses.find((item) => item.label.includes('成功'))?.numeric ?? 0
  const failedCount = workflowStatuses.find((item) => item.label.includes('失败'))?.numeric ?? toNumber(input.workflowMonitor?.todayFailed)
  const statusTotal = successCount + failedCount
  const successRate = statusTotal > 0 ? Math.round((successCount / statusTotal) * 100) : null
  const executionCount = toNumber(input.workflowMonitor?.todayExecutions)
  const workflowUnavailable = hasFailedSource(input, '工作流监控')
  const realtimeRefreshFailed = hasFailedSource(input, '实时运营')
  const realtimeAvailable = hasRecordData(input.realtimeStats)
  const realtimePanel: DashboardPanel = realtimeAvailable
    ? {
        key: 'realtime',
        title: '实时运营监控',
        subtitle: realtimeRefreshFailed ? '上次成功快照（本次刷新失败）' : '按今日口径',
        metrics: [
          metric('online', '在线账号', optionalCompact(input.realtimeStats, 'onlineAccounts'), '当前快照', toNumber(input.realtimeStats?.onlineAccounts) > 0 ? 'success' : 'muted'),
          metric('published', '进行中任务', optionalCompact(input.realtimeStats, 'todayPublished'), '今日实时口径', 'brand'),
          metric('ai-calls', 'AI 调用量', optionalCompact(input.realtimeStats, 'todayAiCalls'), '今日实时口径', aiCalls > 0 ? 'brand' : 'muted'),
          metric('fail-rate', 'AI 调用失败率', failureRate === null ? '--' : `${failureRate}%`, !hasAiFailureCount ? '失败数量数据不可用' : aiCalls > 0 ? `失败 ${compactNumber(input.realtimeStats?.todayAiFailures)}` : '今日暂无调用', failureRate === null ? 'muted' : failureRate > 0 ? 'warning' : 'success'),
          metric('today-sales', '今日流水', hasOwn(input.realtimeStats, 'todaySalesAmount') ? currencyValue(input.realtimeStats?.todaySalesAmount) : '--', '今日实时口径', hasOwn(input.realtimeStats, 'todaySalesAmount') ? 'brand' : 'muted'),
          metric('workflow-running', '自动化成功率', successRate === null ? '--' : `${successRate}%`, successRate === null ? '暂无成功/失败分布' : `运行中 ${compactNumber(input.realtimeStats?.runningWorkflows)}`, successRate === null ? 'muted' : successRate < 100 ? 'warning' : 'success')
        ]
      }
    : aggregateUnavailable
      ? unavailablePanel('realtime', '实时运营监控', '仪表盘聚合接口读取失败，当前无法判断在线账号、AI 调用或自动化状态。', '请求失败')
      : {
          key: 'realtime',
          title: '实时运营监控',
          subtitle: '今日',
          emptyState: {
            title: '暂无实时运营数据',
            description: '接口已成功响应，但当前没有实时运营指标。'
          }
        }
  const workflowPanel: DashboardPanel = workflowUnavailable
    ? unavailablePanel('workflow', '工作流概况', '工作流监控请求失败，当前无法判断执行次数或成功率。', '请求失败')
    : executionCount <= 0 && statusTotal <= 0
    ? {
        key: 'workflow',
        title: '工作流概况',
        subtitle: '今日',
        emptyState: {
          title: '今日暂无工作流执行',
          description: '没有可用于计算成功率的工作流执行记录。'
        }
      }
    : {
        key: 'workflow',
        title: '工作流概况',
        subtitle: '今日',
        gauge: successRate === null
          ? undefined
          : {
              label: '成功率',
              value: successRate,
              detail: `${successCount}/${statusTotal}`
            },
        table: successRate === null
          ? []
          : [
              { label: '成功', value: compactNumber(successCount), extra: `${successRate}%`, tone: 'success' },
              { label: '失败', value: compactNumber(failedCount), extra: `${100 - successRate}%`, tone: failedCount > 0 ? 'danger' : 'muted' },
              { label: '进行中', value: compactNumber(input.workflowMonitor?.running), extra: '-', tone: 'brand' }
            ],
        metrics: [
          metric('auto-reply-total', '自动化总次数', compactNumber(executionCount), '今日实时口径', 'brand'),
          metric('workflow-running-count', '当前运行中', compactNumber(input.workflowMonitor?.running), '实时口径', 'brand')
        ],
        emptyState: successRate === null
          ? {
              title: '成功率暂不可用',
              description: '工作流执行汇总未返回成功/失败分布，无法推算成功率。'
            }
          : undefined
      }

  return [
    realtimePanel,
    {
      key: 'health',
      title: '账号健康分布',
      subtitle: '当前快照',
      table: riskRows,
      emptyState: riskRows.length
        ? undefined
        : {
            title: aggregateUnavailable ? '账号健康数据暂不可用' : '暂无账号风险数据',
            description: aggregateUnavailable
              ? '仪表盘聚合接口读取失败，不能据此判断账号是否健康。'
              : '接口已成功响应，但当前没有账号风险分布记录。'
          },
      footer: '历史趋势、Cookie 过期与 API 成功率待真实监控接口补齐'
    },
    workflowPanel
  ]
}

function buildServicePanels(input: DashboardOverviewFixture): DashboardPanel[] {
  const replyHits = compactNumber(replyHitCount(input))
  const serviceDataAvailable = hasRecordData(input.autoReplyMonitor) || hasSummaryStat(input, 'autoReplyCount') || hasRecordData(input.realtimeStats)
  const serviceEfficiencyPanel: DashboardPanel = serviceDataAvailable
    ? {
        key: 'service-efficiency',
        title: '消息与客服效率',
        subtitle: '今日',
        metrics: [
          metric('message-hits', '消息已处理', replyHits, replyHitDelta(input), 'brand'),
          metric('pending-reply', '待跟进数', optionalCompact(input.autoReplyMonitor, 'todayManual'), '今日实时口径', toNumber(input.autoReplyMonitor?.todayManual) > 0 ? 'warning' : 'muted'),
          metric('ai-failed', 'AI 调用失败', optionalCompact(input.realtimeStats, 'todayAiFailures'), '今日实时口径', toNumber(input.realtimeStats?.todayAiFailures) > 0 ? 'danger' : 'muted'),
          metric('response-time', '平均首次响应时长', '--', '数据暂不可用', 'muted', '响应时长接口待接入'),
          metric('handover-rate', '升级处理占比', '--', '数据暂不可用', 'muted', '人工升级接口待接入'),
          metric('satisfaction', '满意度评分', '--', '数据暂不可用', 'muted', '满意度接口待接入')
        ]
      }
    : hasFailedSource(input, '自动回复监控') || hasFailedSource(input, '仪表盘聚合接口')
      ? unavailablePanel('service-efficiency', '消息与客服效率', '消息或自动回复监控请求失败，当前无法判断客服处理效率。', '请求失败')
      : {
          key: 'service-efficiency',
          title: '消息与客服效率',
          subtitle: '今日',
          emptyState: {
            title: '暂无消息与客服数据',
            description: '接口已成功响应，但当前没有消息处理或客服效率记录。'
          }
        }
  const alertsPanel: DashboardPanel = hasFailedSource(input, '仪表盘聚合接口')
    ? unavailablePanel('alerts', '待处理事项', '仪表盘聚合接口读取失败，当前无法判断是否存在待处理告警或任务。', '请求失败')
    : {
        key: 'alerts',
        title: '待处理事项',
        subtitle: '按严重度排序',
        pending: buildPendingItems(input.pendingTasks).slice(0, 4),
        emptyState: input.pendingTasks?.length
          ? undefined
          : {
              title: '暂无待处理事项',
              description: '当前没有待处理告警或任务。'
            },
        footer: '查看告警'
      }
  return [
    serviceEfficiencyPanel,
    unavailablePanel('stock', '卡密库存统计', '卡密库存汇总接口尚未接入，当前无法判断库存数量或预警等级。'),
    alertsPanel
  ]
}

function buildQualityPanels(): DashboardPanel[] {
  return [
    unavailablePanel('notify', '通知投递统计', '通知投递汇总接口尚未接入，不能据消息量推算通知成功、失败或重试数量。'),
    unavailablePanel('client-error', '客户端错误监控', '客户端错误聚合接口尚未接入，当前无法判断是否存在致命错误或受影响会话。'),
    unavailablePanel('sync', '商机与商品同步', '商品同步结果接口尚未接入，当前无法计算同步成功率或失败数量。')
  ]
}

function unavailablePanel(key: string, title: string, description: string, subtitle = '数据源未接入'): DashboardPanel {
  return {
    key,
    title,
    subtitle,
    emptyState: {
      title: '数据暂不可用',
      description
    },
    footer: subtitle === '请求失败' ? '请求成功后自动恢复展示' : '接入真实监控数据后自动展示'
  }
}

function buildBottomPanels(input: DashboardOverviewFixture): DashboardPanel[] {
  const aggregateUnavailable = hasFailedSource(input, '仪表盘聚合接口')
  const eventSourceUnavailable = hasFailedSource(input, '操作日志')
  const healthRefreshFailed = hasFailedSource(input, '系统健康')
  const goodsRows: DashboardTableRow[] = (input.topHotGoods || []).slice(0, 5).map((item: any) => ({
    label: item?.title || '-',
    value: compactNumber(item?.sales || 0),
    extra: item?.accountName || '',
    tone: 'brand'
  }))
  const health = input.systemHealth
  const healthRows: DashboardTableRow[] = [
    serviceRow(health?.coreApi),
    serviceRow(health?.automationService),
    serviceRow(health?.crawlerService)
  ].filter(Boolean) as DashboardTableRow[]
  const recentEvents = (input.recentEvents || []).filter((item: any) => !String(item?.module || '').startsWith('WEBSOCKET_'))
  const eventRows: DashboardTableRow[] = recentEvents.slice(0, 3).map((item: any) => ({
    label: `${item?.module || '-'} · ${item?.action || '-'}`,
    value: item?.time || '-',
    extra: item?.targetId ? `#${item.targetId}` : '',
    tone: item?.result === '成功' ? 'success' : 'danger'
  }))

  return [
    {
      key: 'hot-goods',
      title: 'Top 热销商品',
      subtitle: '近7天',
      table: goodsRows,
      emptyState: goodsRows.length
        ? undefined
        : {
            title: aggregateUnavailable ? '热销商品数据暂不可用' : '暂无真实热销数据',
            description: aggregateUnavailable
              ? '仪表盘聚合接口读取失败，不能判断当前时间范围内是否存在热销商品。'
              : '当前时间范围内没有热销商品记录。'
          },
      footer: '查看全部'
    },
    {
      key: 'system-health',
      title: '系统健康',
      subtitle: healthRefreshFailed && healthRows.length ? '上次成功快照（本次刷新失败）' : '服务探针',
      table: healthRows,
      emptyState: healthRows.length
        ? undefined
        : {
            title: aggregateUnavailable || healthRefreshFailed ? '系统健康数据暂不可用' : '暂无服务探针数据',
            description: aggregateUnavailable || healthRefreshFailed
              ? '系统健康请求失败，不能判断服务是否在线。'
              : '接口已成功响应，但当前没有服务探针结果。'
          },
      footer: healthRows.length
        ? healthRefreshFailed
          ? '当前为上次成功读取的探针结果；资源监控尚未接入'
          : '仅展示真实服务探针；资源监控尚未接入'
        : aggregateUnavailable || healthRefreshFailed ? '请重试获取健康状态' : '等待服务注册探针后展示'
    },
    {
      key: 'recent-events',
      title: '最近后台操作',
      subtitle: '最近3条',
      table: eventRows,
      emptyState: eventRows.length
        ? undefined
        : {
            title: eventSourceUnavailable ? '后台操作日志暂不可用' : '暂无后台操作记录',
            description: eventSourceUnavailable
              ? '操作日志接口读取失败，不能判断当前是否存在后台操作记录。'
              : '当前没有可展示的后台操作日志。'
          },
      footer: '查看全部操作日志'
    }
  ]
}

function buildPendingItems(tasks: any[]): DashboardPendingItem[] {
  return (tasks || []).map((task) => ({
    title: task?.title || '-',
    time: task?.time || '-',
    type: taskTypeLabel(task?.type),
    severity: pendingTone(task?.type)
  }))
}

function metric(
  key: string,
  label: string,
  value: string,
  deltaText: string,
  tone: DashboardTone = 'muted',
  note?: string
): DashboardMetricItem {
  return { key, label, value, delta: deltaText, tone, note }
}

function funnelStage(key: string, label: string, value: number, percentValue: number | null): DashboardFunnelStage {
  return {
    key,
    label,
    value: compactNumber(value),
    percent: percentValue === null ? '--' : `${percentValue}%`
  }
}

function serviceRow(service: any): DashboardTableRow | null {
  if (!service) return null
  const status = String(service.status || '').toLowerCase()
  const statusView = status === 'up'
    ? { value: '在线', tone: 'success' as DashboardTone }
    : ['down', 'offline'].includes(status)
      ? { value: '离线', tone: 'danger' as DashboardTone }
      : status === 'degraded'
        ? { value: '降级', tone: 'warning' as DashboardTone }
        : { value: '状态未知', tone: 'muted' as DashboardTone }
  return {
    label: `${service.name}${service.port ? ` :${service.port}` : ''}`,
    value: statusView.value,
    extra: hasOwn(service, 'latencyMs') ? `${compactNumber(service.latencyMs)}ms` : '--',
    tone: statusView.tone
  }
}

function statValue(input: DashboardOverviewFixture, key: string): string {
  return hasSummaryStat(input, key) ? compactNumber(statValueRaw(input, key)) : '--'
}

function statValueRaw(input: DashboardOverviewFixture, key: string): number {
  return toNumber(findSummaryCard(input.summary?.cards, key)?.value)
}

function replyHitCount(input: DashboardOverviewFixture): number {
  return Math.max(
    toNumber(input.autoReplyMonitor?.todayHits),
    toNumber(input.autoReplyMonitor?.todayAutoAllowed),
    statValueRaw(input, 'autoReplyCount')
  )
}

function replyHitDelta(input: DashboardOverviewFixture): string {
  return replyHitCount(input) > 0 ? '今日实时口径' : '今日暂无命中'
}

function findSummaryCard(cards: any[] = [], key: string) {
  return (cards || []).find((item) => item?.key === key)
}

function buildRangeLabels(primary: any[] = [], fallbackDates: string[] = [], limit = 7) {
  const labelsFromPrimary = (primary || [])
    .slice(-limit)
    .map((item: any) => String(item?.statDate || item?.date || '').slice(5))
    .filter(Boolean)

  if (labelsFromPrimary.length) return labelsFromPrimary

  const fallback = (fallbackDates || []).slice(-limit).map((item) => String(item).slice(5))
  return fallback
}

function normalizeStatusRows(rows: any[]) {
  return (rows || []).map((item) => ({
    label: String(item?.status || '-'),
    numeric: toNumber(item?.count)
  }))
}

function sumCounts(rows: any[]) {
  return (rows || []).reduce((sum, item) => sum + toNumber(item?.count), 0)
}

function riskLabel(level: number) {
  const map: Record<number, string> = {
    0: '健康账号',
    1: '轻微异常',
    2: '风险账号',
    3: '高风险',
    4: '极高风险'
  }
  return map[Number(level) || 0] || '未知'
}

function riskTone(level: number): DashboardTone {
  if (Number(level) >= 3) return 'danger'
  if (Number(level) === 2) return 'warning'
  if (Number(level) === 1) return 'brand'
  return 'success'
}

function taskTypeLabel(type: string) {
  const map: Record<string, string> = {
    workflow: '工作流',
    notify: '通知',
    risk: '风控',
    kami: '卡密'
  }
  return map[type] || '系统'
}

function pendingTone(type: string): DashboardTone {
  if (type === 'risk') return 'danger'
  if (type === 'workflow') return 'warning'
  if (type === 'notify') return 'brand'
  return 'muted'
}

function toNumber(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  const normalized = String(value ?? '')
    .replace(/[,%￥¥\s]/g, '')
    .replace(/,/g, '')
  const parsed = Number(normalized)
  return Number.isFinite(parsed) ? parsed : 0
}

function compactNumber(value: unknown): string {
  return toNumber(value).toLocaleString('zh-CN')
}

function compactWan(value: unknown): string {
  const number = toNumber(value)
  if (number >= 10000) return `${(number / 10000).toFixed(2)}w`
  return compactNumber(number)
}

function delta(value: unknown): string {
  return toNumber(value) > 0 ? '今日实时口径' : '今日暂无新增'
}

function percent(part: unknown, total: number): string {
  const safeTotal = total > 0 ? total : 1
  return String(Math.round((toNumber(part) / safeTotal) * 100))
}

function centToYuan(value: unknown): number {
  return Number((toNumber(value) / 100).toFixed(2))
}

function centToCurrency(value: unknown): string {
  return currencyValue(centToYuan(value))
}

function currencyValue(value: unknown): string {
  return `¥${toNumber(value).toFixed(2)}`
}

function marginDelta(incomeText: string, costCent: unknown): string {
  const income = toNumber(incomeText)
  const cost = centToYuan(costCent)
  if (!income) return '无收入，利润率不可计算'
  return `今日估算利润率 ${Math.round(((income - cost) / income) * 100)}%`
}

function hasSummaryStat(input: DashboardOverviewFixture, key: string) {
  return Boolean(findSummaryCard(input.summary?.cards, key))
}

function hasOwn(value: unknown, key: string): boolean {
  return Boolean(value && typeof value === 'object' && Object.prototype.hasOwnProperty.call(value, key))
}

function hasRecordData(value: unknown): boolean {
  return Boolean(value && typeof value === 'object' && Object.keys(value as Record<string, unknown>).length > 0)
}

function hasFailedSource(input: DashboardOverviewFixture, sourceName: string): boolean {
  return Boolean(input.dataState?.failedSources?.some(source => source.includes(sourceName)))
}

function optionalCompact(value: unknown, key: string): string {
  return hasOwn(value, key) ? compactNumber((value as Record<string, unknown>)[key]) : '--'
}

function noComparison(): string {
  return '暂无同比数据'
}
