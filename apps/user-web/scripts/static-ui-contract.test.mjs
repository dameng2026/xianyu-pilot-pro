import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')
const src = path.join(root, 'src')

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

function read(...segments) {
  return fs.readFileSync(path.join(src, ...segments), 'utf8')
}

const appVue = read('App.vue')
const navJs = read('data', 'nav.js')
const pageDir = path.join(src, 'pages')
const pageFiles = fs.readdirSync(pageDir).filter(name => name.endsWith('.vue'))

const autoDeliveryPage = read('pages', 'AutoDeliveryPage.vue')
const sourceLibraryPage = read('pages', 'DeliverySourceLibraryPage.vue')
const ordersPage = read('pages', 'OrdersPage.vue')
const messagesPage = read('pages', 'MessagesPage.vue')
const productPublishPage = read('pages', 'ProductPublishPage.vue')
const notifySettingsPage = read('pages', 'settings', 'NotifySettings.vue')
const accountsPage = read('pages', 'AccountsPage.vue')

for (const page of [
  'LoginPage.vue',
  'DashboardPage.vue',
  'AccountsPage.vue',
  'ProductsPage.vue',
  'AutoReplyPage.vue',
  'AutoDeliveryPage.vue',
  'DeliverySourceLibraryPage.vue',
  'OrdersPage.vue'
]) {
  assert(pageFiles.includes(page), `缺少核心页面：${page}`)
}

for (const route of [
  'dashboard',
  'accounts',
  'products',
  'orders',
  'auto-reply',
  'auto-delivery',
  'delivery-source-library',
  'vip',
  'profile'
]) {
  assert(appVue.includes(`'${route}'`) || appVue.includes(`${route}:`), `App.vue 缺少路由：${route}`)
  assert(navJs.includes(route), `nav.js 缺少导航/标题配置：${route}`)
}

for (const expectedEvent of [
  'delivery-refresh',
  'source-new',
  'source-refresh',
  'orders-refresh',
  'notify-save',
  'notify-test',
  'notify-refresh'
]) {
  assert(appVue.includes(expectedEvent), `App.vue 缺少头部动作事件：${expectedEvent}`)
}

assert(autoDeliveryPage.includes('getDeliverySources'), '自动发货页应加载货源库列表')
assert(autoDeliveryPage.includes("emit('navigate', 'delivery-source-library')"), '自动发货页应提供跳转货源库入口')
assert(sourceLibraryPage.includes('分析匹配商品'), '货源库页应包含可说明实际推荐模式的匹配入口')
assert(sourceLibraryPage.includes('getDeliverySourceGoods'), '货源库页应查询货源已配置商品列表')
assert(sourceLibraryPage.includes('recommendDeliverySourceGoods'), '货源库页应调用 AI 推荐接口')
assert(sourceLibraryPage.includes('applyDeliverySourceToGoods'), '货源库页应支持批量或单个绑定商品')
assert(ordersPage.includes('getOrders'), '订单页应加载订单列表接口')
assert(notifySettingsPage.includes('代发货提醒'), '通知设置页应包含代发货提醒事件')
assert(appVue.includes('mobileLitePages.has(active.value)'), '移动端壳子不应拦截桌面专属页面路由')

assert(messagesPage.includes('@click="openImagePreview(img)"'), 'MessagesPage should allow opening chat images in a preview')
assert(messagesPage.includes('return resolveTrustedMediaUrl(value)'), 'MessagesPage should validate local and remote image URLs through the shared media policy')
assert(messagesPage.includes("const query = reactive({ xianyuAccountId: '', pageSize: 50 })"), 'MessagesPage should request 50 online conversations per page')
assert(messagesPage.includes('@scroll="handleConversationListScroll"'), 'MessagesPage should auto-load more conversations when the list scroll reaches the bottom')
assert(messagesPage.includes('暂无更多会话'), 'MessagesPage should show an explicit no-more-conversations state')
assert(messagesPage.includes('共 {{ displayList.length }} 条会话</div>'), 'MessagesPage footer should no longer imply a 7-day-only conversation scope')
assert(messagesPage.includes('token为零'), 'MessagesPage should expose an explicit token-empty runtime status')
assert(messagesPage.includes('--xya-msg-topbar-safe-space: 52px;'), 'MessagesPage should reserve a safe area for the fixed topbar')
assert(messagesPage.includes('height: calc(100dvh - 48px);'), 'MessagesPage should stretch the chat workspace close to a full viewport height')
assert(messagesPage.includes('overflow-x: hidden;'), 'MessagesPage should prevent horizontal scrolling in the conversation list')
assert(messagesPage.includes('scrollbar-width: none;'), 'MessagesPage should hide the conversation list scrollbar while keeping it scrollable')
assert(productPublishPage.includes('const displayCoverImage = computed(() => displayImageUrl(form.imageUrls[0] || \'\'))'), 'ProductPublishPage should derive the preview cover through a normalized display URL')
assert(productPublishPage.includes("if (value.startsWith('/uploads/')) return value"), 'ProductPublishPage should preserve uploaded cover paths instead of rewriting them')
assert(sourceLibraryPage.includes('goodsCover(row)'), 'source library goods list should render goods cover')
assert(sourceLibraryPage.includes('accountAvatar(row)'), 'source library goods list should render account avatar')
assert(sourceLibraryPage.includes('accountDisplayLabel(row)'), 'source library goods list should render account name with id')
assert(accountsPage.includes('重新扫码'), 'AccountsPage should expose a rescan entry for existing accounts')
assert(accountsPage.includes('generateQrLogin(qr.accountId ? { accountId: qr.accountId } : {})') || accountsPage.includes('generateQrLogin({ accountId:'), 'AccountsPage should request qr login sessions with target account id when rescanning')
assert(accountsPage.includes('getQrLoginStatus(qr.sessionId, qr.accountId ? { accountId: qr.accountId } : {})') || accountsPage.includes('getQrLoginStatus(qr.sessionId, { accountId:'), 'AccountsPage should poll qr login status with the target account id when rescanning')
console.log('static-ui-contract: ok')
