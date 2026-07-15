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

assert.equal(
  zeroActivityModel.kpiGroups.find(group => group.key === 'service')?.items[0]?.value,
  '0',
  '后端返回 0 次消息命中时必须保留真实 0，不能回退成演示数据'
)
assert.equal(
  zeroActivityModel.qualityPanels.find(panel => panel.key === 'notify')?.emptyState?.title,
  '数据暂不可用',
  '通知统计未接入真实数据源时必须明确标记不可用'
)
assert.equal(
  zeroActivityModel.servicePanels.find(panel => panel.key === 'stock')?.emptyState?.title,
  '数据暂不可用',
  '库存接口未接入时不能展示虚构库存'
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
  zeroActivityModel.finance.chart.series.flatMap(series => series.values),
  Array(zeroActivityModel.finance.chart.labels.length * zeroActivityModel.finance.chart.series.length).fill(0),
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

const negativeProfitFixture = createOverviewTestFixture()
negativeProfitFixture.summary = {
  ...negativeProfitFixture.summary,
  cards: negativeProfitFixture.summary.cards.map(card =>
    card.key === 'todaySalesAmount' ? { ...card, value: 0 } : card
  )
}
negativeProfitFixture.aiMonitor = {
  ...negativeProfitFixture.aiMonitor,
  todayCostCent: 250
}
const negativeProfitModel = buildDashboardOverviewModel(negativeProfitFixture)

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

console.log('dashboard-overview-contract: ok')
