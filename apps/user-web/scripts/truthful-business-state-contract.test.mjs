import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (...segments) => fs.readFileSync(path.join(root, ...segments), 'utf8')

const dashboard = read('src', 'pages', 'DashboardPage.vue')
assert.doesNotMatch(dashboard, /fallbackSystemStatus[\s\S]{0,500}ok:\s*true/)
assert.doesNotMatch(dashboard, /buildRealtimeSeedEvents|ensureRealtimeSeedEvents/)
assert.doesNotMatch(dashboard, /所有功能免费开放体验|内测公告/)
assert.match(dashboard, /status:\s*'unknown'/)
assert.match(dashboard, /function statusText\(/)
assert.match(dashboard, /carouselUnavailable/)
assert.match(dashboard, /const contentAvailable = ref\(true\)/)
assert.match(dashboard, /homeData\.contentAvailable !== false/)
assert.match(dashboard, /navigationAvailable && !contentAvailable/)
assert.match(dashboard, /其他首页数据不受影响/)

const deliveryTemplates = read('src', 'pages', 'DeliveryTemplatesPage.vue')
assert.doesNotMatch(deliveryTemplates, /xya_delivery_templates|loadFromStorage|saveToStorage|isOfflineMode|genId\(/)
assert.match(deliveryTemplates, /v-else-if="loadError"/)
assert.match(deliveryTemplates, /const templatesAvailable = ref\(false\)/)
assert.match(deliveryTemplates, /if \(!templatesAvailable\.value\) return/)

for (const [file, availabilityName] of [
  ['DeliveryStatementPage.vue', 'settingsAvailable'],
  [path.join('settings', 'ProductOpSettings.vue'), 'settingsAvailable'],
]) {
  const source = read('src', 'pages', file)
  assert.match(source, /v-else-if="loadError"/)
  assert.match(source, new RegExp(`const ${availabilityName} = ref\\(false\\)`))
  assert.match(source, new RegExp(`if \\(\\!${availabilityName}\\.value\\) return`))
}

const workflowApi = read('src', 'api', 'workflow.js')
assert.doesNotMatch(workflowApi, /listWorkflowKeywords\s*=.*Promise\.resolve|saveWorkflowKeyword\s*=.*Promise\.resolve|generateWorkflowKeywords\s*=.*Promise\.resolve/)
assert.match(workflowApi, /FEATURE_UNAVAILABLE/)

const legacyAccountVip = read('src', 'pages', 'AccountVipPage.vue')
for (const fabricatedValue of ['小龙果', '2211422464341', '¥99', '¥199', '永久使用']) {
  assert.equal(legacyAccountVip.includes(fabricatedValue), false, `legacy account VIP page must not expose fabricated value: ${fabricatedValue}`)
}
assert.match(legacyAccountVip, /账号会员页已停用/)

const vip = read('src', 'pages', 'VipPage.vue')
assert.doesNotMatch(vip, /level === 'normal' \? 1 : level === 'vip' \? 3 : 10/)
assert.doesNotMatch(vip, /level === 'normal' \? 20 : level === 'vip' \? 200 : 1000/)
assert.doesNotMatch(vip, /level === 'normal' \? 100 : level === 'vip' \? 3000 : 20000/)
assert.match(vip, /价格未配置/)
assert.match(vip, /canPurchase/)
assert.match(vip, /globalConfirm\.alert/)
assert.doesNotMatch(vip, /window\.alert|window\.confirm/)
assert.doesNotMatch(vip, /优先响应与专属支持|后续可接入支付或授权码/)

for (const file of ['MobileProducts.vue', 'MobileAccounts.vue', 'MobileAutomation.vue', 'MobileMessages.vue', 'MobileData.vue', 'MobileProfile.vue']) {
  const source = read('src', 'mobile', file)
  assert.match(source, /MobileUnavailableState/, `${file} must distinguish unavailable from empty`)
  assert.match(source, /loadError|overviewError|execError|chatError/, `${file} must expose request failure state`)
}

const mobileHome = read('src', 'mobile', 'MobileHome.vue')
assert.match(mobileHome, /statsLoadError/)
assert.match(mobileHome, /metricText\(/)
assert.doesNotMatch(mobileHome, /stats\.value\.onSale\s*=\s*goodsRes\.value\.data\.total/)

const autoDelivery = read('src', 'pages', 'AutoDeliveryPage.vue')
assert.match(autoDelivery, /statsAvailable/)
assert.match(autoDelivery, /sourcesAvailable/)
assert.match(autoDelivery, /_configUnavailable/)

const cardWarehouse = read('src', 'pages', 'CardWarehousePage.vue')
for (const failureText of ['卡密明细加载失败', '使用记录加载失败', '库存统计加载失败']) {
  assert.equal(cardWarehouse.includes(failureText), true)
}

const paymentModal = read('src', 'components', 'PaymentModal.vue')
assert.doesNotMatch(paymentModal, /methods\.value\.length\s*\?\s*methods\.value\s*:\s*\[/)
assert.doesNotMatch(paymentModal, /class="fake-qr"|function qrDot\(/)
assert.match(paymentModal, /capabilityError/)
assert.match(paymentModal, /支付二维码不可用/)
assert.doesNotMatch(paymentModal, /priceYuan \|\| 0|: '¥0'/)

const profileCenter = read('src', 'pages', 'ProfileCenterPage.vue')
assert.match(profileCenter, /overviewLoadError/)
assert.match(profileCenter, /tokenLoadError/)
assert.doesNotMatch(profileCenter, /activePlan\?\.planName \|\| '普通用户'/)
assert.doesNotMatch(profileCenter, /较昨日|较上周/)
assert.doesNotMatch(profileCenter, /stats\.value\.[A-Za-z]+ \|\| 0/)

const app = read('src', 'App.vue')
assert.doesNotMatch(app, /getCachedUsername\(\) \|\| '管理员'/)
assert.doesNotMatch(app, /activePlan:\s*\{\s*planCode:\s*'normal'/)
assert.match(app, /profileUnavailable/)
assert.match(app, /:connection-status="displaySseStatus"/)

for (const file of ['Sidebar.vue', 'Topbar.vue']) {
  const source = read('src', 'components', file)
  assert.doesNotMatch(source, /\|\| '管理员'/, `${file} must not invent an administrator identity`)
  assert.doesNotMatch(source, /\|\| '普通用户'/, `${file} must not invent a plan`)
}

const sidebar = read('src', 'components', 'Sidebar.vue')
assert.match(sidebar, /connectionStatus/)
assert.doesNotMatch(sidebar, /<span class="online-text">在线<\/span>/)

const topbar = read('src', 'components', 'Topbar.vue')
assert.match(topbar, /状态未知/)
assert.doesNotMatch(topbar, /\[props\.sseStatus\] \|\| '在线'/)

const accountAuth = read('src', 'utils', 'accountAuth.js')
assert.match(accountAuth, /function accountWsConnectionState/)
assert.match(accountAuth, /return '状态未知'/)
assert.match(accountAuth, /return 'gray'/)

const mobileAccounts = read('src', 'mobile', 'MobileAccounts.vue')
assert.match(mobileAccounts, /wsStatusText/)
assert.match(mobileAccounts, /m-acc-tag-unknown/)

const accountsPage = read('src', 'pages', 'AccountsPage.vue')
assert.doesNotMatch(accountsPage, /qr-mock\.svg/)
assert.match(accountsPage, /qrUnavailable/)
assert.match(accountsPage, /二维码响应缺少可扫描内容/)
assert.match(accountsPage, /accountsAvailable/)
assert.match(accountsPage, /accountsLoadError/)
assert.match(accountsPage, /accountWsConnectionState/)

const dataPage = read('src', 'pages', 'DataPage.vue')
assert.match(dataPage, /summaryAvailable/)
assert.match(dataPage, /trendAvailable/)
assert.match(dataPage, /Promise\.allSettled/)
assert.doesNotMatch(dataPage, /orderCount:0, deliverySuccessCount:0/)

for (const [file, availability, loadError] of [
  ['OrdersPage.vue', 'ordersAvailable', 'ordersLoadError'],
  ['DeliveryRecordsPage.vue', 'recordsAvailable', 'recordsLoadError'],
  ['LogsPage.vue', 'logsAvailable', 'logsLoadError'],
  ['ScheduledTasksPage.vue', 'tasksAvailable', 'tasksLoadError'],
]) {
  const source = read('src', 'pages', file)
  assert.match(source, new RegExp(availability), `${file} must distinguish load failure from an empty list`)
  assert.match(source, new RegExp(loadError), `${file} must expose the list request error`)
  assert.match(source, /响应格式异常/, `${file} must reject malformed success payloads`)
}
const logsPage = read('src', 'pages', 'LogsPage.vue')
assert.doesNotMatch(logsPage, /status \|\| '成功'/)
assert.match(logsPage, /日志状态未知/)

const autoReply = read('src', 'pages', 'AutoReplyPage.vue')
for (const state of ['accountsAvailable', 'scopeAvailable', 'productsAvailable', 'aiSummaryAvailable', 'scopeWritable']) {
  assert.match(autoReply, new RegExp(state), `AutoReplyPage must track ${state}`)
}
assert.doesNotMatch(autoReply, /最近 24 小时回复到达率/)
assert.doesNotMatch(autoReply, /return '全部账号 · 智能回复已就绪'/)
assert.match(autoReply, /自动回复状态未知/)

const opportunity = read('src', 'pages', 'OpportunityPage.vue')
assert.match(opportunity, /accountLoadError/)
assert.match(opportunity, /accountAvailable/)
assert.doesNotMatch(opportunity, /wantCount \|\| item\.soldCount/)
assert.doesNotMatch(opportunity, /item\.status \?\? 0/)
assert.match(opportunity, /商品搜索响应格式异常/)
assert.match(opportunity, /if \(await loadStoreItems\([^)]*\)\) allCollected\.value = true/)

const appShell = read('src', 'App.vue')
assert.doesNotMatch(appShell, /event: 'settings-save'|event: 'settings-test'/)
assert.match(appShell, /active\.value\.startsWith\('settings-'\)[\s\S]*?return \[\]/)

const feedback = read('src', 'pages', 'FeedbackPage.vue')
for (const state of ['feedbackListAvailable', 'feedbackListError', 'feedbackStatsAvailable', 'detailAvailable']) {
  assert.match(feedback, new RegExp(state), `FeedbackPage must track ${state}`)
}
assert.doesNotMatch(feedback, /statusMeta\[item\.status\]\?\.label \|\| '待处理'/)
assert.match(feedback, /反馈列表响应格式异常/)

const productPublish = read('src', 'pages', 'ProductPublishPage.vue')
assert.match(productPublish, /accountLoadError/)
assert.match(productPublish, /categoriesAvailable/)
assert.match(productPublish, /initializationAvailable/)
assert.match(productPublish, /账号列表响应格式异常/)
assert.doesNotMatch(productPublish, /黑色 ×|银色 ×|32GB ×|64GB ×/)

const messages = read('src', 'pages', 'MessagesPage.vue')
for (const state of ['accountsAvailable', 'conversationsAvailable', 'contextAvailable', 'aiSettingsAvailable', 'tokenBalanceError']) {
  assert.match(messages, new RegExp(state), `MessagesPage must track ${state}`)
}
assert.match(messages, /会话列表响应格式异常/)
assert.match(messages, /消息记录响应格式异常/)
assert.match(messages, /自动回复状态未知/)

console.log('truthful-business-state-contract: ok')
