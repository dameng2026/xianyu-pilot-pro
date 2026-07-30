/**
 * 鱼小铺数据分析页面前端契约测试。
 *
 * 覆盖场景（按需求第二十九节）：
 * 1. 页面入口：nav.js / App.vue 已注册鱼小铺数据分析页面
 * 2. 账号下拉：默认"全部账号"，仅包含 fishShopUser 账号
 * 3. 时间范围：近1天/近7天/近30天，默认 recent7d
 * 4. 请求结构：API 客户端指向 /fish-shop-data/summary
 * 5. 竞态保护：使用 AbortController 防止旧请求覆盖新选择
 * 6. 空状态：没有鱼小铺账号时不调用接口
 * 7. 部分失败：显示部分失败提示
 * 8. 金额格式：使用项目统一 formatMoney
 * 9. 安全：前端源码不直接处理 Cookie / _m_h5_tk / sign
 * 10. 现有数据总览保留：DataPage 仍然存在且未被改造
 */
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')

const pageSource = fs.readFileSync(
  path.join(root, 'src', 'pages', 'FishShopDataPage.vue'),
  'utf8',
)
const apiSource = fs.readFileSync(
  path.join(root, 'src', 'api', 'fishShopData.js'),
  'utf8',
)
const navSource = fs.readFileSync(
  path.join(root, 'src', 'data', 'nav.js'),
  'utf8',
)
const appSource = fs.readFileSync(
  path.join(root, 'src', 'App.vue'),
  'utf8',
)

// 现有数据总览页面应仍然存在且未被删除
const dataPagePath = path.join(root, 'src', 'pages', 'DataPage.vue')
assert(fs.existsSync(dataPagePath), 'DataPage.vue 应仍然存在（保留现有数据总览）')
const dataPageSource = fs.readFileSync(dataPagePath, 'utf8')
// 现有数据总览不得混入鱼小铺接口数据
assert(
  !dataPageSource.includes('fish-shop-data/summary'),
  'DataPage 不得混入鱼小铺接口数据',
)
assert(
  !dataPageSource.includes('getFishShopDataSummary'),
  'DataPage 不得调用鱼小铺数据分析 API',
)

// ==================== 页面入口 ====================

// nav.js 应包含鱼小铺数据分析入口
assert(
  navSource.includes("'fish-shop-data'") || navSource.includes('"fish-shop-data"'),
  'nav.js 应包含 fish-shop-data 导航 key',
)
assert(
  navSource.includes('鱼小铺数据分析'),
  'nav.js 应包含"鱼小铺数据分析"标签',
)

// App.vue 应注册 FishShopDataPage
assert(
  appSource.includes('FishShopDataPage.vue'),
  'App.vue 应注册 FishShopDataPage.vue',
)

// ==================== 账号下拉 ====================

// 默认选项"全部账号"
assert(pageSource.includes('全部账号'), '页面应包含"全部账号"默认选项')
// 仅包含 fishShopUser 账号
assert(
  pageSource.includes('fishShopUser === true') || pageSource.includes('fishShopUser === 1'),
  '账号下拉应仅过滤 fishShopUser 账号',
)
// 不包含普通账号
assert(
  !pageSource.includes('普通闲鱼账号') || pageSource.includes('不参与'),
  '页面应说明普通账号不参与统计',
)

// ==================== 时间范围 ====================

// 三个时间范围选项
assert(pageSource.includes("'recent1d'"), '应包含 recent1d 选项')
assert(pageSource.includes("'recent7d'"), '应包含 recent7d 选项')
assert(pageSource.includes("'recent30d'"), '应包含 recent30d 选项')
// 默认 recent7d
assert(
  /dateType\.value\s*=\s*ref\(['"]recent7d['"]\)/.test(pageSource) ||
  /const\s+dateType\s*=\s*ref\(['"]recent7d['"]\)/.test(pageSource),
  '默认 dateType 应为 recent7d',
)
// 三个标签
assert(pageSource.includes('近1天'), '应显示"近1天"标签')
assert(pageSource.includes('近7天'), '应显示"近7天"标签')
assert(pageSource.includes('近30天'), '应显示"近30天"标签')

// ==================== 请求结构 ====================

// API 客户端指向正确端点
assert(
  apiSource.includes('/fish-shop-data/summary'),
  'API 客户端应请求 /fish-shop-data/summary',
)
assert(
  apiSource.includes('recent7d'),
  'API 客户端默认 dateType 应为 recent7d',
)
// 不传 accountId 时表示全部账号
assert(
  /params\.accountId\s*&&\s*params\.accountId\s*>\s*0/.test(apiSource),
  'API 客户端应仅在 accountId > 0 时传参',
)

// ==================== 竞态保护 ====================

// 使用 AbortController 防止旧请求覆盖新选择
assert(
  pageSource.includes('AbortController'),
  '页面应使用 AbortController 防止旧请求覆盖新选择',
)
assert(
  pageSource.includes('inflightRequestId'),
  '页面应使用请求 ID 防止旧请求覆盖新选择',
)
assert(
  /if\s*\(\s*requestId\s*!==\s*inflightRequestId\s*\)\s*return/.test(pageSource),
  '页面应在响应返回时校验请求 ID',
)
// 切换时取消旧请求
assert(
  pageSource.includes('inflightController.abort'),
  '页面应在发起新请求前取消旧请求',
)

// ==================== 空状态 ====================

// 没有鱼小铺账号时不调用接口
assert(
  /fishShopAccounts\.value\.length\s*===\s*0/.test(pageSource),
  '页面应在没有鱼小铺账号时不调用接口',
)
assert(
  pageSource.includes('当前没有可用的鱼小铺账号'),
  '页面应显示没有鱼小铺账号的空状态提示',
)
assert(
  pageSource.includes('绑定或升级为鱼小铺账号'),
  '空状态应提示绑定或升级为鱼小铺账号',
)

// ==================== 部分失败状态 ====================

assert(
  pageSource.includes('partialFailure'),
  '页面应处理部分失败状态',
)
assert(
  pageSource.includes('isPartial'),
  '页面应根据 isPartial 字段判断部分失败',
)
assert(
  pageSource.includes('部分账号数据获取失败'),
  '页面应显示部分账号数据获取失败提示',
)

// ==================== 金额格式 ====================

// 使用项目统一 formatMoney
assert(
  pageSource.includes('formatMoney'),
  '页面应使用项目统一 formatMoney 格式化金额',
)
assert(
  pageSource.includes('formatNumber'),
  '页面应使用项目统一 formatNumber 格式化数量',
)

// ==================== 趋势图 ====================

// 使用 echarts（项目已有图表库）
assert(
  pageSource.includes('echarts'),
  '页面应使用项目已有 echarts 图表库',
)
// 趋势指标切换
assert(
  pageSource.includes('trendMetricKey'),
  '页面应支持趋势指标切换',
)
// 趋势数据来源 graphDataList（经后端解析为 graph）
assert(
  pageSource.includes('summary.value.graph'),
  '页面应从 summary.graph 读取趋势数据',
)

// ==================== 指标卡片 ====================

// 核心指标（按需求第十五节）
const requiredMetrics = [
  'payAmt',      // 成交金额
  'payOrdCnt',   // 支付订单数
  'payByrCnt',   // 支付买家数
  'aov',         // 客单价
  'showPv',      // 商品曝光次数
  'showUv',      // 商品曝光人数
  'ipv',         // 商品浏览次数
  'ipvUv',       // 商品浏览人数
  'vstPv',       // 访问次数
  'vstUv',       // 访客人数
  'chatUv',      // 咨询人数
  'onlCnt',      // 在线商品数
]
for (const key of requiredMetrics) {
  assert(
    pageSource.includes(`'${key}'`) || pageSource.includes(`"${key}"`),
    `页面应包含核心指标: ${key}`,
  )
}

// ==================== ratio 处理 ====================

// ratio 正负方向判断
assert(
  pageSource.includes('ratio > 0') || pageSource.includes('ratio>0'),
  '页面应根据 ratio 正负判断上升/下降',
)
// 不重复乘 100
assert(
  pageSource.includes('* 100') || pageSource.includes('*100'),
  '页面应将 ratio 小数转百分比（乘 100）',
)

// ==================== 全部账号说明 ====================

// 客单价/人数指标说明
assert(
  pageSource.includes('aovNote'),
  '页面应展示全部账号模式下的客单价/人数说明',
)

// ==================== 安全 ====================

// 前端源码不直接处理 Cookie / _m_h5_tk / sign
assert(
  !pageSource.includes('_m_h5_tk'),
  '前端页面不应直接处理 _m_h5_tk',
)
assert(
  !pageSource.includes('document.cookie'),
  '前端页面不应直接读取 document.cookie',
)
assert(
  !apiSource.includes('_m_h5_tk'),
  '前端 API 客户端不应处理 _m_h5_tk',
)
assert(
  !apiSource.includes('document.cookie'),
  '前端 API 客户端不应读取 document.cookie',
)

// ==================== 真实日期范围 ====================

// 使用 realDateRange 显示
assert(
  pageSource.includes('realDateRange'),
  '页面应使用 realDateRange 显示真实日期范围',
)

// ==================== 单账号模式不重复请求 ====================

// 单账号模式只请求一次（通过 if/else 分支保证，前端只发起一次 API 调用）
assert(
  pageSource.includes("selectedAccountId.value !== 'all'") ||
  pageSource.includes(`selectedAccountId.value !== "all"`),
  '页面应根据 selectedAccountId 是否为 all 决定是否传 accountId',
)

// ==================== 现有数据总览未被破坏 ====================

// DataPage 应仍然引用 dashboard API（原有数据源）
assert(
  dataPageSource.includes('api/dashboard.js'),
  'DataPage 应保留原有数据源（dashboard.js）',
)
assert(
  dataPageSource.includes('getDashboardSummary'),
  'DataPage 应保留 getDashboardSummary 调用',
)
assert(
  dataPageSource.includes('getDashboardSalesTrend'),
  'DataPage 应保留 getDashboardSalesTrend 调用',
)

console.log('fish-shop-data-contract: ok')
