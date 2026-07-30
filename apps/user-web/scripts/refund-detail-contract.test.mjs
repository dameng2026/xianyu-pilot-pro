import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// ============================================================
// 退款详情页前端契约测试
//
// 需求覆盖：
// - 第二节：退款列表"查看详情"进入内部详情页，不再跳转外部闲鱼详情
// - 第三节：进入详情必须能确定 所属账号 + orderId + refundId + 列表摘要；
//           返回列表时恢复 账号筛选 / 分类 / 页码 / 滚动位置
// - 第四节：仅鱼小铺账号可访问；不得通过修改 URL 参数绕过
// - 第五节：路由形态 refund-detail/{accountId}/{orderId}/{refundId}
// - 第十九节：缓存优先 + 进行中请求去重
// - 第二十节：局部失败、单独重试只请求失败接口
// - 第二十四节：测试要求（路由、权限、缓存、components、状态金额分离等）
// ============================================================

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')

// ============================================================
// 1. refundListState 工具：保存/消费/查看/清除列表筛选状态
// ============================================================

// 提供 mock sessionStorage（浏览器环境模拟）
class MemoryStorage {
  constructor() { this._data = new Map() }
  get length() { return this._data.size }
  key(index) { return [...this._data.keys()][index] ?? null }
  getItem(key) { return this._data.has(String(key)) ? this._data.get(String(key)) : null }
  setItem(key, value) { this._data.set(String(key), String(value)) }
  removeItem(key) { this._data.delete(String(key)) }
  clear() { this._data.clear() }
}

// 在加载 refundListState.js 前先注入 window.sessionStorage
// 这样测试既能覆盖 storage 路径，也能覆盖内存兜底路径
const mockStorage = new MemoryStorage()
globalThis.window = { sessionStorage: mockStorage }

// 动态导入被测模块（import 是 hoisted，所以必须先设置 globalThis.window）
const {
  saveRefundListState,
  consumeRefundListState,
  peekRefundListState,
  clearRefundListState,
} = await import('../src/utils/refundListState.js')

// 测试辅助：每个 sub-test 前后清理 storage + memory，避免相互污染
function resetState() {
  clearRefundListState()
  mockStorage.clear()
}

// 1.1 保存后立即能消费到等价数据
resetState()
saveRefundListState({
  selectedAccountId: '7',
  category: 'shipped',
  page: 3,
  pageSize: 20,
  scrollTop: 1234,
})
const consumed = consumeRefundListState()
assert.ok(consumed, 'consumeRefundListState 必须返回保存的状态')
assert.equal(consumed.selectedAccountId, '7', 'selectedAccountId 必须恢复')
assert.equal(consumed.category, 'shipped', 'category 必须恢复')
assert.equal(consumed.page, 3, 'page 必须恢复')
assert.equal(consumed.pageSize, 20, 'pageSize 必须恢复')
assert.equal(consumed.scrollTop, 1234, 'scrollTop 必须恢复')
assert.ok(consumed.savedAt, 'savedAt 时间戳必须存在')

// 1.2 consume 后状态应被清除（不重复恢复旧状态）
resetState()
saveRefundListState({ selectedAccountId: '11', category: 'all', page: 1, pageSize: 20 })
assert.ok(consumeRefundListState(), '第一次 consume 应拿到状态')
assert.equal(consumeRefundListState(), null, '第二次 consume 应返回 null（状态已清除）')

// 1.3 peek 不消费状态
resetState()
saveRefundListState({
  selectedAccountId: '8',
  category: 'unshipped',
  page: 2,
  pageSize: 15,
  scrollTop: 500,
})
const peeked = peekRefundListState()
assert.ok(peeked, 'peek 必须返回保存的状态')
assert.equal(peeked.selectedAccountId, '8', 'peek 返回的 selectedAccountId 必须一致')
// 再 peek 仍能拿到（未被消费）
assert.ok(peekRefundListState(), 'peek 不应消费状态')
// consume 后才清除
assert.ok(consumeRefundListState(), 'consume 应拿到状态')
assert.equal(consumeRefundListState(), null, 'consume 后状态被清除')

// 1.4 clearRefundListState 显式清除
resetState()
saveRefundListState({ selectedAccountId: '9', category: 'all', page: 1, pageSize: 20 })
clearRefundListState()
assert.equal(peekRefundListState(), null, 'clear 后 peek 应返回 null')

// 1.5 默认值与边界处理
resetState()
saveRefundListState({})
const def = consumeRefundListState()
assert.ok(def, '空对象保存后仍应返回默认状态')
assert.equal(def.selectedAccountId, '', '默认 selectedAccountId 应为空字符串')
assert.equal(def.category, 'all', '默认 category 应为 all')
assert.equal(def.page, 1, '默认 page 应为 1')
assert.equal(def.pageSize, 20, '默认 pageSize 应为 20')
assert.equal(def.scrollTop, 0, '默认 scrollTop 应为 0')

// 1.6 非法值安全规范化
resetState()
saveRefundListState({
  selectedAccountId: 123,  // 非字符串
  category: null,  // 非字符串
  page: -5,  // 非法页码
  pageSize: 'abc',  // 非法
  scrollTop: -10,  // 非法
})
const normalized = consumeRefundListState()
assert.equal(normalized.selectedAccountId, '', '非字符串 selectedAccountId 应回退为空字符串')
assert.equal(normalized.category, 'all', '非字符串 category 应回退为 all')
assert.equal(normalized.page, 1, '非法 page 应回退为 1')
assert.equal(normalized.pageSize, 20, '非法 pageSize 应回退为 20')
assert.equal(normalized.scrollTop, 0, '非法 scrollTop 应回退为 0')

// 1.7 storage 失败时使用内存兜底（设置 storage 抛异常）
resetState()
const failingStorage = {
  getItem() { return null },
  setItem() { throw new Error('quota exceeded') },
  removeItem() { throw new Error('denied') },
}
globalThis.window = { sessionStorage: failingStorage }
// refundListState.js 每次 setItem/getItem 都重新调用 getStorage()
// 所以这里能直接测试 setItem 抛异常时的兜底行为
saveRefundListState({ selectedAccountId: '10', category: 'all', page: 1, pageSize: 20 })
const fallback = consumeRefundListState()
assert.ok(fallback, 'storage 不可用时仍应通过内存兜底恢复状态')
assert.equal(fallback.selectedAccountId, '10', '内存兜底应返回正确 selectedAccountId')

// 还原 globalThis.window 以免污染其他测试
delete globalThis.window

console.log('refund-list-state-contract: ok')

// ============================================================
// 2. RefundDetailPage.vue 路由参数解析契约
// ============================================================

const detailPageSource = fs.readFileSync(
  path.join(root, 'src', 'pages', 'RefundDetailPage.vue'),
  'utf8'
)

// 2.1 路由形态必须是 refund-detail/{accountId}/{orderId}/{refundId}
// 源码中应为类似 /^refund-detail\/([^/]+)\/([^/]+)\/([^/]+)$/ 的正则
assert.match(
  detailPageSource,
  /refund-detail\\\//,
  'RefundDetailPage 必须包含 refund-detail/ 路由前缀的正则匹配'
)
assert.match(
  detailPageSource,
  /\[\^\/\]\+/,
  '路由参数必须使用 [^/]+ 匹配非斜杠字符'
)
// 必须捕获三个参数（accountId / orderId / refundId）
const routeRegexMatch = detailPageSource.match(/\(\[\^\/\]\+\)/g)
assert.ok(
  routeRegexMatch && routeRegexMatch.length >= 3,
  '路由正则必须捕获三个参数：accountId / orderId / refundId'
)

// 2.2 必须从 location.hash 解析路由（不依赖 vue-router）
assert.match(
  detailPageSource,
  /location\.hash/,
  'RefundDetailPage 必须从 location.hash 解析路由参数'
)

// 2.3 参数缺失时必须显示错误，不发起请求
assert.match(
  detailPageSource,
  /routeError\.value\s*=\s*['"]详情页地址参数缺失/,
  '参数缺失时必须设置 routeError 并显示错误提示'
)

// 2.4 必须 emit navigate 事件回到列表（不使用 history.back 以确保恢复筛选状态）
assert.match(
  detailPageSource,
  /emit\(['"]navigate['"],\s*['"]refunds['"]\)/,
  '返回列表必须通过 emit navigate 事件，由 App.vue 统一处理路由'
)

// 2.5 当前 refundId 在退款历史中必须高亮（isCurrent 标记）
assert.match(
  detailPageSource,
  /isCurrent/,
  '退款历史中当前 refundId 必须有 isCurrent 高亮标记'
)
assert.match(
  detailPageSource,
  /current-refund/,
  '当前退款行必须有 current-refund CSS 类'
)

// 2.6 三接口状态指示器（局部失败显示单独重试）
assert.match(
  detailPageSource,
  /apiStatusList/,
  '必须有三接口状态指示器 apiStatusList'
)
assert.match(
  detailPageSource,
  /onRetryApi/,
  '必须有单独重试方法 onRetryApi'
)

// 2.7 同意退款必须二次确认
assert.match(
  detailPageSource,
  /agreeModal\.visible/,
  '同意退款必须有二次确认弹窗 agreeModal'
)
assert.match(
  detailPageSource,
  /confirmAgreeRefund/,
  '同意退款必须有确认方法 confirmAgreeRefund'
)

// 2.8 写操作成功后刷新当前退款（不刷新全部账号）
assert.match(
  detailPageSource,
  /await loadDetail\(true\)/,
  '同意退款成功后必须调用 loadDetail(true) 刷新当前退款'
)

// 2.9 不显示递归"退款详情"按钮（避免递归跳转）
// bottomBarButtons 只渲染 applyDisputePage 和 agreeRefundApply，不渲染 viewRefundDetail
assert.match(
  detailPageSource,
  /v-if=['"]btn\.code === 'applyDisputePage'['"]/,
  'bottomBar 仅渲染 applyDisputePage 按钮'
)
assert.match(
  detailPageSource,
  /v-else-if=['"]btn\.code === 'agreeRefundApply'['"]/,
  'bottomBar 仅渲染 agreeRefundApply 按钮'
)
// 不应渲染 viewRefundDetail 类型的按钮
assert.doesNotMatch(
  detailPageSource,
  /v-if=['"]btn\.code === 'viewRefundDetail'['"]/,
  '详情页不得显示会跳回相同退款详情的"退款详情"按钮（避免递归跳转）'
)

// 2.10 必须使用短时缓存（cachedFlag / cacheExpiredFlag）
assert.match(
  detailPageSource,
  /cachedFlag/,
  '必须有缓存命中标记 cachedFlag'
)
assert.match(
  detailPageSource,
  /cacheExpiredFlag/,
  '必须有缓存过期标记 cacheExpiredFlag'
)

// 2.11 全部失败且无缓存时显示完整错误状态
assert.match(
  detailPageSource,
  /allFailedNoCache/,
  '必须有 allFailedNoCache 计算属性处理全部失败场景'
)

// 2.12 卖家发货物流与买家退货物流必须分开展示
assert.match(
  detailPageSource,
  /sellerLogistics/,
  '必须有卖家发货物流计算属性 sellerLogistics'
)
assert.match(
  detailPageSource,
  /buyerReturnLogistics/,
  '必须有买家退货物流计算属性 buyerReturnLogistics'
)
assert.match(
  detailPageSource,
  /卖家发货物流/,
  '页面必须显示"卖家发货物流"标题'
)
assert.match(
  detailPageSource,
  /买家退货物流/,
  '页面必须显示"买家退货物流"标题'
)

// 2.13 当前退款申请金额优先使用 basicRefundInfo.applyMoney（不被 refundFee 覆盖）
assert.match(
  detailPageSource,
  /displayApplyMoney/,
  '必须有当前退款申请金额计算属性 displayApplyMoney'
)
// 源码可能直接写 basicRefundInfo.value?.applyMoney，也可能先 const basic = basicRefundInfo.value
// 再使用 basic?.applyMoney。两种写法都满足"优先使用 basicRefundInfo.applyMoney"的契约。
const applyMoneyPatternMatch =
  detailPageSource.match(/basicRefundInfo\.value\?\.\s*applyMoney/) ||
  detailPageSource.match(/const\s+basic\s*=\s*basicRefundInfo\.value[\s\S]*?basic\?\.\s*applyMoney/)
assert.ok(
  applyMoneyPatternMatch,
  'displayApplyMoney 必须优先使用 basicRefundInfo.applyMoney（直接或通过中间变量 basic）'
)
// 同时验证不直接用 merchantPriceVO.refundFee 覆盖当前申请金额（refundFee 仅作为订单维度退款金额展示）
assert.match(
  detailPageSource,
  /displayApplyMoney\s*=\s*computed\(\(\)\s*=>\s*\{[\s\S]*?return\s+summary\.value\?\.\s*refundFee/,
  'displayApplyMoney 应回退到 summary.refundFee（而非 merchantPriceVO.refundFee）'
)

// 2.14 富文本必须安全渲染（不使用 v-html）
assert.doesNotMatch(
  detailPageSource,
  /v-html/,
  'RefundDetailPage 不得使用 v-html 渲染富文本（必须使用 {{ }} 文本插值）'
)
assert.match(
  detailPageSource,
  /buildSafeStyle/,
  '富文本样式必须经过 buildSafeStyle 白名单过滤'
)

// 2.15 URL 安全：维权链接打开前必须再次校验协议
assert.match(
  detailPageSource,
  /parsed\.protocol !== 'http:' && parsed\.protocol !== 'https:'/,
  '维权链接打开前必须校验协议为 http/https'
)

// 2.16 图片预览：凭证图片支持预览
assert.match(
  detailPageSource,
  /openImagePreview/,
  '必须有图片预览方法 openImagePreview'
)
assert.match(
  detailPageSource,
  /previewImageUrl/,
  '必须有图片预览状态 previewImageUrl'
)

console.log('refund-detail-page-contract: ok')

// ============================================================
// 3. RefundsPage.vue 查看详情跳转契约
// ============================================================

const refundsPageSource = fs.readFileSync(
  path.join(root, 'src', 'pages', 'RefundsPage.vue'),
  'utf8'
)

// 3.1 必须导入 saveRefundListState / consumeRefundListState
assert.match(
  refundsPageSource,
  /import\s*\{[^}]*saveRefundListState[^}]*\}\s*from\s*['"][^'"]*refundListState/,
  'RefundsPage 必须导入 saveRefundListState'
)
assert.match(
  refundsPageSource,
  /import\s*\{[^}]*consumeRefundListState[^}]*\}\s*from\s*['"][^'"]*refundListState/,
  'RefundsPage 必须导入 consumeRefundListState'
)

// 3.2 onViewDetail 必须保存列表状态后跳转到 refund-detail 路由
assert.match(
  refundsPageSource,
  /function onViewDetail/,
  '必须有 onViewDetail 方法'
)
assert.match(
  refundsPageSource,
  /saveRefundListState\(\{/,
  'onViewDetail 必须调用 saveRefundListState 保存列表状态'
)
assert.match(
  refundsPageSource,
  /emit\(['"]navigate['"],\s*`refund-detail\/\$\{accountId\}\/\$\{encodeURIComponent\(orderId\)\}\/\$\{encodeURIComponent\(refundId\)\}`\)/,
  'onViewDetail 必须通过 emit navigate 跳转到 refund-detail/{accountId}/{orderId}/{refundId} 路由'
)

// 3.3 onViewDetail 必须校验 accountId / orderId / refundId 三要素
assert.match(
  refundsPageSource,
  /if \(!accountId \|\| !orderId \|\| !refundId\)/,
  'onViewDetail 必须校验 accountId / orderId / refundId 三要素齐全'
)

// 3.4 onMounted 必须消费保存的列表状态
assert.match(
  refundsPageSource,
  /onMounted\(async \(\) => \{[\s\S]*?consumeRefundListState\(\)/,
  'RefundsPage onMounted 必须调用 consumeRefundListState 恢复列表状态'
)

// 3.5 必须恢复滚动位置
assert.match(
  refundsPageSource,
  /savedState\.scrollTop/,
  'RefundsPage 必须恢复滚动位置 savedState.scrollTop'
)
assert.match(
  refundsPageSource,
  /window\.scrollTo/,
  'RefundsPage 必须调用 window.scrollTo 恢复滚动位置'
)

// 3.6 不再默认跳转外部闲鱼详情（不使用 window.open 或 location.href 跳转 goofish）
// 注：onApplyDispute 可能使用 window.open 打开维权链接，但 onViewDetail 不得使用
const onViewDetailMatch = refundsPageSource.match(
  /function onViewDetail[\s\S]*?\n\}/
)
assert.ok(onViewDetailMatch, '必须找到 onViewDetail 函数定义')
const onViewDetailBody = onViewDetailMatch[0]
assert.doesNotMatch(
  onViewDetailBody,
  /window\.open/,
  'onViewDetail 不得使用 window.open 跳转外部闲鱼详情'
)
assert.doesNotMatch(
  onViewDetailBody,
  /location\.href\s*=/,
  'onViewDetail 不得使用 location.href 跳转外部闲鱼详情'
)

console.log('refunds-page-view-detail-contract: ok')

// ============================================================
// 4. App.vue 路由注册契约
// ============================================================

const appVueSource = fs.readFileSync(
  path.join(root, 'src', 'App.vue'),
  'utf8'
)

// 4.1 refund-detail 必须在 pageMap 中注册
assert.match(
  appVueSource,
  /['"]refund-detail['"]:\s*asyncPage\(\(\) => import\(['"][^'"]*RefundDetailPage\.vue['"]\)\)/,
  'App.vue 必须在 pageMap 中注册 refund-detail 路由'
)

// 4.2 isKnownPage 必须识别 refund-detail/ 前缀
assert.match(
  appVueSource,
  /if \(key\.startsWith\(['"]refund-detail\/['"]\)\) return true/,
  'isKnownPage 必须识别 refund-detail/ 前缀'
)

// 4.3 normalizePageKey 必须将 refund-detail/* 归一化为 refund-detail
assert.match(
  appVueSource,
  /if \(key\.startsWith\(['"]refund-detail\/['"]\)\) return ['"]refund-detail['"]/,
  'normalizePageKey 必须将 refund-detail/* 归一化为 refund-detail'
)

// 4.4 getNormalizedKey 必须将 refund-detail/* 归一化为 refund-detail
assert.match(
  appVueSource,
  /if \(raw\.startsWith\(['"]refund-detail\/['"]\)\) return ['"]refund-detail['"]/,
  'getNormalizedKey 必须将 refund-detail/* 归一化为 refund-detail'
)

console.log('app-vue-route-registration-contract: ok')

// ============================================================
// 5. refunds.js API 契约
// ============================================================

const refundsApiSource = fs.readFileSync(
  path.join(root, 'src', 'api', 'refunds.js'),
  'utf8'
)

// 5.1 必须导出三个详情接口函数
assert.match(
  refundsApiSource,
  /export function getRefundDetail/,
  'refunds.js 必须导出 getRefundDetail 函数'
)
assert.match(
  refundsApiSource,
  /export function refreshRefundDetail/,
  'refunds.js 必须导出 refreshRefundDetail 函数'
)
assert.match(
  refundsApiSource,
  /export function retryRefundDetailApi/,
  'refunds.js 必须导出 retryRefundDetailApi 函数'
)

// 5.2 三个接口 URL 必须与后端路由一致
assert.match(
  refundsApiSource,
  /url:\s*['"]\/refunds\/detail['"]/,
  'getRefundDetail 必须使用 /refunds/detail URL'
)
assert.match(
  refundsApiSource,
  /url:\s*['"]\/refunds\/detail\/refresh['"]/,
  'refreshRefundDetail 必须使用 /refunds/detail/refresh URL'
)
assert.match(
  refundsApiSource,
  /url:\s*['"]\/refunds\/detail\/retry['"]/,
  'retryRefundDetailApi 必须使用 /refunds/detail/retry URL'
)

// 5.3 getRefundDetail 必须使用 GET 方法
assert.match(
  refundsApiSource,
  /export function getRefundDetail[\s\S]*?method:\s*['"]get['"]/
)

// 5.4 refreshRefundDetail 必须使用 POST 方法
assert.match(
  refundsApiSource,
  /export function refreshRefundDetail[\s\S]*?method:\s*['"]post['"]/
)

// 5.5 retryRefundDetailApi 必须使用 POST 方法
assert.match(
  refundsApiSource,
  /export function retryRefundDetailApi[\s\S]*?method:\s*['"]post['"]/
)

// 5.6 retryRefundDetailApi 必须接受 api 参数（service_record/full_info/refund_detail）
assert.match(
  refundsApiSource,
  /payload\.api/,
  'retryRefundDetailApi 必须接受 api 参数'
)

// 5.7 同意退款函数必须保留（写操作）
assert.match(
  refundsApiSource,
  /export function agreeRefund/,
  'refunds.js 必须保留 agreeRefund 函数（写操作）'
)

console.log('refunds-api-contract: ok')

// ============================================================
// 6. RefundDetailPage.vue 数据合并与状态分离契约
// ============================================================

// 6.1 退款状态与订单状态必须分开显示
assert.match(
  detailPageSource,
  /displayRefundStatus/,
  '必须有退款状态计算属性 displayRefundStatus（与订单状态分开）'
)

// 6.2 当前退款状态优先级：basicRefundInfo.refundStatusDesc > refundStatusInfo.title > summary
// 源码可能直接写 basicRefundInfo.value?.refundStatusDesc，也可能先 const basic = basicRefundInfo.value
// 再使用 basic?.refundStatusDesc。两种写法都满足"优先使用 basicRefundInfo.refundStatusDesc"的契约。
const refundStatusPatternMatch =
  detailPageSource.match(/basicRefundInfo\.value\?\.\s*refundStatusDesc/) ||
  detailPageSource.match(/const\s+basic\s*=\s*basicRefundInfo\.value[\s\S]*?basic\?\.\s*refundStatusDesc/)
assert.ok(
  refundStatusPatternMatch,
  'displayRefundStatus 必须优先使用 basicRefundInfo.refundStatusDesc（直接或通过中间变量 basic）'
)

// 6.3 三接口数据必须分别访问（serviceRecord / fullInfo / refundDetail）
assert.match(
  detailPageSource,
  /detail\.value\?\.serviceRecord/,
  '必须访问 detail.serviceRecord 数据块'
)
assert.match(
  detailPageSource,
  /detail\.value\?\.fullInfo/,
  '必须访问 detail.fullInfo 数据块'
)
assert.match(
  detailPageSource,
  /detail\.value\?\.refundDetail/,
  '必须访问 detail.refundDetail 数据块'
)

// 6.4 components 必须按 render 字段访问（不按固定下标）
assert.match(
  detailPageSource,
  /refundDetailData\.value\?\.components\?\.basicRefundInfo/,
  '必须通过 components.basicRefundInfo 按 render 字段访问'
)
assert.match(
  detailPageSource,
  /refundDetailData\.value\?\.components\?\.nodeStatusInfo/,
  '必须通过 components.nodeStatusInfo 按 render 字段访问'
)
assert.match(
  detailPageSource,
  /refundDetailData\.value\?\.components\?\.progressDetail/,
  '必须通过 components.progressDetail 按 render 字段访问'
)
assert.match(
  detailPageSource,
  /refundDetailData\.value\?\.components\?\.refundDescribe/,
  '必须通过 components.refundDescribe 按 render 字段访问'
)
assert.match(
  detailPageSource,
  /refundDetailData\.value\?\.components\?\.bottomBar/,
  '必须通过 components.bottomBar 按 render 字段访问'
)

// 6.5 物流分离：tradeLogisticInfo 是卖家发货，buyerReturnLogisticInfo 是买家退货
assert.match(
  detailPageSource,
  /tradeLogisticInfo/,
  '必须使用 tradeLogisticInfo 作为卖家发货物流来源'
)
assert.match(
  detailPageSource,
  /buyerReturnLogisticInfo/,
  '必须使用 buyerReturnLogisticInfo 作为买家退货物流来源'
)

// 6.6 凭证来源：refundProof.proofMultiMediaList + progressNodeList[].proofInfoList
assert.match(
  detailPageSource,
  /refundProof\?\.proofMultiMediaList/,
  '凭证必须从 refundProof.proofMultiMediaList 收集'
)
assert.match(
  detailPageSource,
  /proofInfoList/,
  '凭证必须从 progressNodeList[].proofInfoList 收集'
)

console.log('refund-detail-data-merge-contract: ok')

// ============================================================
// 7. 不增加左侧导航菜单契约（需求第二节最后一句）
// ============================================================

const navDataPath = path.join(root, 'src', 'data', 'nav.js')
if (fs.existsSync(navDataPath)) {
  const navSource = fs.readFileSync(navDataPath, 'utf8')
  // nav.js 中不应出现 refund-detail 菜单项
  assert.doesNotMatch(
    navSource,
    /['"]refund-detail['"]\s*:/,
    '不得在 nav.js 中新增 refund-detail 菜单项（详情页不加入左侧导航）'
  )
  console.log('refund-detail-no-nav-menu-contract: ok')
} else {
  // 如果没有 nav.js，跳过此契约（项目可能使用其他导航配置方式）
  console.log('refund-detail-no-nav-menu-contract: skipped (no nav.js)')
}

// ============================================================
// 8. 权限契约：详情页不得信任前端传入的账号类型
// ============================================================

// 8.1 RefundDetailPage 不得在前端硬编码鱼小铺判断（必须由后端校验）
// 前端只负责展示后端返回的错误，不主动判断账号类型
assert.doesNotMatch(
  detailPageSource,
  /fish_shop_user/i,
  'RefundDetailPage 不得在前端硬编码 fish_shop_user 判断（必须由后端校验）'
)
assert.doesNotMatch(
  detailPageSource,
  /fishShopUser/i,
  'RefundDetailPage 不得在前端硬编码 fishShopUser 判断（必须由后端校验）'
)

// 8.2 后端返回错误时必须展示 routeError 或 globalError
assert.match(
  detailPageSource,
  /globalError\.value\s*=\s*data\.error/,
  '后端返回失败时必须设置 globalError 展示错误'
)

console.log('refund-detail-permission-contract: ok')

console.log('refund-detail-contract: ok')
