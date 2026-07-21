import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

import {
  buildDashboardOverviewModel,
  createOverviewTestFixture
} from '../src/views/admin/module/dashboard-overview'

const fixture = createOverviewTestFixture()
const model = buildDashboardOverviewModel(fixture)

const zeroActivityFixture = createOverviewTestFixture()
zeroActivityFixture.summary = {
  cards: zeroActivityFixture.summary.cards.map(card =>
    card.key === 'autoReplyCount' ? { ...card, value: 0 } : card
  )
}
zeroActivityFixture.autoReplyMonitor = { todayHits: 0, todayAutoAllowed: 0, todayManual: 0, actions: [] }
zeroActivityFixture.workflowMonitor = { todayFailed: 0, running: 0, todayExecutions: 0, byStatus: [] }
const zeroActivityModel = buildDashboardOverviewModel(zeroActivityFixture)
const noGoodsFixture = createOverviewTestFixture()
noGoodsFixture.topHotGoods = []
const noGoodsModel = buildDashboardOverviewModel(noGoodsFixture)
const noHealthFixture = createOverviewTestFixture()
noHealthFixture.systemHealth = null
const noHealthModel = buildDashboardOverviewModel(noHealthFixture)
const unavailableFixture = createOverviewTestFixture()
unavailableFixture.dataState = {
  status: 'unavailable',
  message: '仪表盘核心数据请求失败',
  failedSources: ['dashboard']
}
const unavailableModel = buildDashboardOverviewModel(unavailableFixture)
const degradedFixture = createOverviewTestFixture()
degradedFixture.pendingTasks = []
degradedFixture.topHotGoods = []
degradedFixture.recentEvents = []
degradedFixture.dataState = {
  status: 'degraded',
  message: '仅加载到经营汇总',
  failedSources: ['仪表盘聚合接口', '操作日志', '趋势与监控明细']
}
const degradedModel = buildDashboardOverviewModel(degradedFixture)
const emptyRiskFixture = createOverviewTestFixture()
emptyRiskFixture.riskDistribution = []
const emptyRiskModel = buildDashboardOverviewModel(emptyRiskFixture)
const failedWorkflowFixture = createOverviewTestFixture()
failedWorkflowFixture.workflowMonitor = {}
failedWorkflowFixture.dataState = {
  status: 'degraded',
  message: '工作流监控失败',
  failedSources: ['工作流监控']
}
const failedWorkflowModel = buildDashboardOverviewModel(failedWorkflowFixture)
const missingFailureCountFixture = createOverviewTestFixture()
delete missingFailureCountFixture.realtimeStats.todayAiFailures
const missingFailureCountModel = buildDashboardOverviewModel(missingFailureCountFixture)

// 新场景：未接入真实数据源时（financeStats/notifyStats/stockStats 等均为 null），面板应回退到 unavailable
const noStatsFixture = createOverviewTestFixture()
noStatsFixture.financeStats = null
noStatsFixture.notifyStats = null
noStatsFixture.clientErrorStats = null
noStatsFixture.stockStats = null
noStatsFixture.syncStats = null
const noStatsModel = buildDashboardOverviewModel(noStatsFixture)

// 新场景：财务真实数据，验证昨日微信二维码收款 4 元的展示
const financeModel = buildDashboardOverviewModel(fixture)

// 新场景：切换到 30 天范围，验证卡片标签动态化
const range30Fixture = createOverviewTestFixture()
range30Fixture.rangeDays = 30
range30Fixture.financeStats = {
  ...(range30Fixture.financeStats as any),
  range: 30,
  totalIncomeCent: 1200,
  totalAiCostCent: 300,
  totalProfitCent: 900,
  marginPercent: 75,
  dates: ['2026-06-22', '2026-06-23', '2026-06-24', '2026-06-25', '2026-06-26', '2026-06-27', '2026-06-28'],
  dailyIncome: [100, 200, 150, 300, 200, 150, 100]
}
const range30Model = buildDashboardOverviewModel(range30Fixture)

// 新场景：负利润，验证 financeStats 真实数据路径下负利润不被钳制为 0
const negativeProfitFixture = createOverviewTestFixture()
negativeProfitFixture.financeStats = {
  ...(negativeProfitFixture.financeStats as any),
  totalIncomeCent: 0,
  totalAiCostCent: 250,
  totalProfitCent: -250,
  marginPercent: null,
  todayIncomeCent: 0,
  todayAiCostCent: 250,
  todayProfitCent: -250,
  dailyIncome: [0, 0, 0, 0, 0, 0, 0]
}
const negativeProfitModel = buildDashboardOverviewModel(negativeProfitFixture)

// 新场景：财务数据全 0，验证趋势图保持真实 0
const zeroFinanceFixture = createOverviewTestFixture()
zeroFinanceFixture.financeStats = {
  ...(zeroFinanceFixture.financeStats as any),
  totalIncomeCent: 0,
  totalAiCostCent: 0,
  totalProfitCent: 0,
  marginPercent: null,
  dailyIncome: [0, 0, 0, 0, 0, 0, 0]
}
zeroFinanceFixture.costStats = {
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
const zeroFinanceModel = buildDashboardOverviewModel(zeroFinanceFixture)

assert.equal(
  zeroActivityModel.kpiGroups.find(group => group.key === 'service')?.items[0]?.value,
  '0',
  '后端返回 0 次消息命中时必须保留真实 0，不能回退成演示数据'
)
assert.equal(
  noStatsModel.qualityPanels.find(panel => panel.key === 'notify')?.emptyState?.title,
  '数据暂不可用',
  '通知统计未接入真实数据源时必须明确标记不可用'
)
assert.equal(
  noStatsModel.servicePanels.find(panel => panel.key === 'stock')?.emptyState?.title,
  '数据暂不可用',
  '库存接口未接入时不能展示虚构库存'
)
assert.equal(
  noStatsModel.qualityPanels.find(panel => panel.key === 'client-error')?.emptyState?.title,
  '数据暂不可用',
  '客户端错误统计未接入时必须标记不可用'
)
assert.equal(
  noStatsModel.qualityPanels.find(panel => panel.key === 'sync')?.emptyState?.title,
  '数据暂不可用',
  '同步统计未接入时必须标记不可用'
)
assert.equal(
  noGoodsModel.bottom.cards.find(panel => panel.key === 'hot-goods')?.emptyState?.title,
  '暂无真实热销数据',
  '热销商品为空时必须展示真实空状态，不能回退演示商品'
)
assert.equal(
  noHealthModel.bottom.cards.find(panel => panel.key === 'system-health')?.emptyState?.title,
  '暂无服务探针数据',
  '接口成功但无健康记录时必须显示真实空状态'
)
assert(
  !model.bottom.cards.find(panel => panel.key === 'system-health')?.table?.some(row => row.label.includes('使用率')),
  '没有资源监控接口时不能伪造 CPU、内存或磁盘使用率'
)
assert.equal(
  zeroActivityModel.monitoring.cards.find(panel => panel.key === 'workflow')?.emptyState?.title,
  '今日暂无工作流执行',
  '没有工作流执行时不能显示 100% 成功率'
)
assert.deepEqual(
  zeroFinanceModel.finance.chart.series.flatMap(series => series.values),
  Array(zeroFinanceModel.finance.chart.labels.length * zeroFinanceModel.finance.chart.series.length).fill(0),
  '没有收入和成本时趋势图必须保持真实 0，不能回退演示曲线'
)
assert.equal(
  model.monitoring.cards.find(panel => panel.key === 'health')?.chart,
  undefined,
  '没有历史账号健康接口时不能根据当前快照伪造近 7 天趋势'
)
assert.deepEqual(
  zeroActivityModel.growth.chart.series,
  [],
  '没有用户增长接口时不能伪造新增、活跃或付费趋势'
)
assert.deepEqual(unavailableModel.dataState, unavailableFixture.dataState)
assert.equal(
  degradedModel.hero.chips.find(chip => chip.key === 'pending')?.value,
  '数据不可用',
  '聚合接口失败时空待办数组不能解释为 0 项'
)
assert.equal(
  degradedModel.bottom.cards.find(panel => panel.key === 'hot-goods')?.emptyState?.title,
  '热销商品数据暂不可用',
  '聚合接口失败时空热销数组必须解释为不可用而非真实空数据'
)
assert.equal(
  emptyRiskModel.hero.chips.find(chip => chip.key === 'risk')?.value,
  '暂无账号数据',
  '接口成功返回空风险分布时必须展示空状态而非请求失败'
)
assert.equal(
  failedWorkflowModel.monitoring.cards.find(panel => panel.key === 'workflow')?.emptyState?.title,
  '数据暂不可用',
  '工作流请求失败不能伪装为今日 0 次执行'
)
assert.equal(
  missingFailureCountModel.monitoring.cards
    .find(panel => panel.key === 'realtime')
    ?.metrics?.find(metric => metric.key === 'fail-rate')?.value,
  '--',
  'AI 调用量存在但失败字段缺失时不能显示 0% 失败率'
)

assert.equal(model.hero.title, '闲鱼助手平台后台')
assert.equal(model.kpiGroups.length, 4)
assert.deepEqual(model.sectionOrder, [
  'kpi',
  'finance',
  'funnel-growth',
  'monitoring',
  'service-stock-alerts',
  'quality-sync',
  'bottom'
])
assert.equal(model.finance.cards.length, 4)
assert.equal(model.monitoring.cards.length, 3)
assert.equal(model.bottom.cards.length, 3)
assert(model.pendingItems.length > 0, '待处理事项应被映射到新版长图结构')

// 新断言：财务真实数据展示（昨日微信二维码收款 4 元，AI 成本 0）
assert.equal(
  financeModel.finance.cards.find(card => card.key === 'income')?.value,
  '¥4.00',
  '财务面板应基于 payment_order 真实聚合，昨日微信二维码收款 4 元必须展示为 ¥4.00'
)
assert.equal(
  financeModel.finance.cards.find(card => card.key === 'profit')?.value,
  '¥4.00',
  '财务面板毛估利润 = 收入 - AI 成本，4 元收入 0 成本应为 ¥4.00'
)
assert.equal(
  financeModel.finance.cards.find(card => card.key === 'income')?.label,
  '近7天收入(元)',
  '财务面板卡片标签必须随时间范围动态化（默认 7 天）'
)
assert.equal(
  financeModel.finance.chart.series.find(series => series.key === 'income')?.values[5],
  4,
  '财务趋势图收入系列第 6 天应为 4 元（昨日 400 分收款）'
)
assert.equal(
  financeModel.finance.gauge.value,
  100,
  '财务利润率 gauge 应基于 financeStats.marginPercent 计算（4 元利润 / 4 元收入 = 100%）'
)

// 新断言：KPI 收入与利润组使用 financeStats 真实数据
const revenueKpi = financeModel.kpiGroups.find(group => group.key === 'revenue')
assert.equal(
  revenueKpi?.items.find(item => item.key === 'sales-today')?.note,
  '二维码收款流水（payment_order）',
  'KPI 收入与利润组应优先使用 payment_order 真实数据'
)

// 新断言：切换到 30 天范围，卡片标签联动
assert.equal(
  range30Model.finance.cards.find(card => card.key === 'income')?.label,
  '近30天收入(元)',
  '切换到 30 天范围后，财务卡片标签必须联动为"近30天收入(元)"'
)
assert.equal(
  range30Model.finance.cards.find(card => card.key === 'income')?.value,
  '¥12.00',
  '30 天范围应展示 30 天范围内的真实总收入（1200 分 = 12 元）'
)
assert.equal(
  range30Model.finance.cards.find(card => card.key === 'profit')?.value,
  '¥9.00',
  '30 天毛估利润 = 12 - 3 = 9 元'
)

// 新断言：通知投递/客户端错误/同步统计/卡密库存使用真实数据
assert.equal(
  financeModel.qualityPanels.find(panel => panel.key === 'notify')?.metrics?.[0]?.value,
  '18',
  '通知投递面板应展示真实投递总数（18 条）'
)
assert.equal(
  financeModel.qualityPanels.find(panel => panel.key === 'notify')?.subtitle,
  '近7天',
  '通知投递面板副标题应随时间范围联动'
)
assert.equal(
  financeModel.qualityPanels.find(panel => panel.key === 'client-error')?.metrics?.[0]?.value,
  '5',
  '客户端错误面板应展示真实错误总数（5 条）'
)
assert.equal(
  financeModel.qualityPanels.find(panel => panel.key === 'sync')?.metrics?.[0]?.value,
  '24',
  '同步统计面板应展示真实同步总数（24 条）'
)
assert.equal(
  financeModel.servicePanels.find(panel => panel.key === 'stock')?.metrics?.[0]?.value,
  '4',
  '卡密库存面板应展示真实卡密组数（4 个）'
)
assert.equal(
  financeModel.servicePanels.find(panel => panel.key === 'stock')?.table?.[0]?.label,
  '测试卡密组B',
  '卡密库存面板应展示真实低库存列表'
)

// 负利润断言（financeStats 真实数据路径）
assert.equal(negativeProfitModel.finance.cards[2]?.value, '¥-2.50')
assert.equal(negativeProfitModel.finance.cards[2]?.tone, 'danger')
assert.equal(negativeProfitModel.finance.breakdown[2]?.value, '¥-2.50')
assert.equal(negativeProfitModel.finance.breakdown[2]?.tone, 'danger')

const page = fs.readFileSync(path.resolve('src/views/admin/module/index.vue'), 'utf8')
const source = fs.readFileSync(path.resolve('src/views/admin/module/dashboard-overview.ts'), 'utf8')

for (const forbiddenFallback of [
  'DEFAULT_',
  '188',
  "'100%'",
  'CPU 使用率',
  '内存使用率',
  '磁盘使用率',
  '8.5s',
  '25.6s'
]) {
  assert(!source.includes(forbiddenFallback), `仪表盘不能保留伪造回退：${forbiddenFallback}`)
}

for (const sectionLabel of [
  '经营总览',
  '收入与 AI 成本',
  '订单转化漏斗',
  '消息与客服效率',
  '通知投递统计',
  '最近后台操作'
]) {
  assert(page.includes(sectionLabel), `仪表盘模板缺少新版分区：${sectionLabel}`)
}

assert(!source.includes('Math.max(0, todayIncome - todayCost)'), '利润展示不应再把负利润钳制为 0')
assert(page.includes('DASHBOARD_REQUEST_OPTIONS = { showErrorMessage: false }'), '仪表盘聚合失败应由单一页面状态呈现，不能触发 toast 风暴')
for (const quietDashboardCall of [
  'getDashboardInit(DASHBOARD_REQUEST_OPTIONS)',
  'getAdminSummary(DASHBOARD_REQUEST_OPTIONS)',
  'getRecentEvents(DASHBOARD_REQUEST_OPTIONS)',
  'getRealtimeStats(DASHBOARD_REQUEST_OPTIONS)',
  'getSystemHealth(DASHBOARD_REQUEST_OPTIONS)'
]) {
  assert(page.includes(quietDashboardCall), `仪表盘请求必须关闭重复全局错误提示：${quietDashboardCall}`)
}

// 新断言：前端必须并行拉取 5 个新接口
for (const newApiCall of [
  'getDashboardFinance(',
  'getNotifyStats(',
  'getClientErrorStats(',
  'getStockStats(',
  'getSyncStats('
]) {
  assert(page.includes(newApiCall), `仪表盘必须并行拉取新接口：${newApiCall}`)
}

console.log('dashboard-overview-contract: ok')
