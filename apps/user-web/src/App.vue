<template>
  <div v-if="booting" class="boot-screen">
    <div class="boot-card">
      <img src="/xya/brand/brand_004.png" alt="XianYuAssistant" />
      <b>正在连接后端服务...</b>
      <span>{{ bootMessage }}</span>
    </div>
  </div>

  <div v-else-if="authPages.includes(getNormalizedKey(active))" class="auth-page-boundary">
    <MaintenanceBanner />
    <div v-if="authNotice" class="auth-boundary-notice" role="alert">{{ authNotice }}</div>
    <component
      :is="pageComponent"
      @navigate="navigate"
      @login-success="handleLoginSuccess"
    />
  </div>

  <MobileLite
    v-else-if="shouldUseMobileLite"
    @navigate="navigate"
    @logout="handleLogout"
    @force-desktop="enableMobileDesktopMode"
  />

  <div v-else class="app-shell" :class="{ 'mobile-desktop-override': mobileDesktopOverride }">
    <button
      v-if="isMobile"
      type="button"
      class="mobile-home-button"
      :class="{ 'is-desktop-override': mobileDesktopOverride }"
      @click="returnToMobileHome"
    >
      ← 移动首页
    </button>
    <Sidebar
      :active="active"
      :user="currentUserInfo"
      :connection-status="displaySseStatus"
      @navigate="navigate"
      @open-profile-center="openProfileCenter"
    />
    <main class="main">
      <Topbar :user="currentUserInfo" :sse-status="displaySseStatus" @logout="handleLogout" @open-profile-center="openProfileCenter" @open-ai-cs="openAiCs" />
      <MaintenanceBanner />
      <PageHeader v-if="shouldRenderPageHeader" :title="pageHeaderTitle" :subtitle="pageHeaderSubtitle">
        <div v-if="headerActions.length" class="head-actions">
          <AppButton v-for="action in headerActions" :key="action.text" :type="action.type" @click="onHeaderAction(action)">{{ action.text }}</AppButton>
        </div>
      </PageHeader>
      <div v-if="globalNotice" class="global-notice" :class="globalNotice.type">{{ globalNotice.text }}</div>
      <component
        :is="pageComponent"
        :active="active"
        :user="currentUserInfo"
        :reason="featureUnavailableInfo.reason"
        :required="featureUnavailableInfo.required"
        :feature-key="featureUnavailableInfo.featureKey"
        @navigate="navigate"
      />
    </main>
  </div>
  <ConfirmModal />
  <DraftGuardModal />
  <PaymentModal
    :visible="paymentVisible"
    order-type="token"
    @close="paymentVisible = false"
    @paid="handleTokenPaid"
  />
  <AiCsPanel :visible="aiCsVisible" @close="aiCsVisible = false" />
</template>

<script setup>
import { computed, defineAsyncComponent, h, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Sidebar from './components/Sidebar.vue'
import Topbar from './components/Topbar.vue'
import PageHeader from './components/PageHeader.vue'
import AppButton from './components/AppButton.vue'
// 弹窗与移动端组件懒加载，避免首屏加载不必要代码
const ConfirmModal = defineAsyncComponent(() => import('./components/ConfirmModal.vue'))
const DraftGuardModal = defineAsyncComponent(() => import('./components/DraftGuardModal.vue'))
const PaymentModal = defineAsyncComponent(() => import('./components/PaymentModal.vue'))
const AiCsPanel = defineAsyncComponent(() => import('./components/AiCsPanel.vue'))
const MobileLite = defineAsyncComponent({
  loader: () => import('./components/MobileLite.vue'),
  loadingComponent: { render: () => h('div') },
  errorComponent: { render: () => h('div') },
  delay: 200,
  timeout: 30000
})
const MaintenanceBanner = defineAsyncComponent(() => import('./components/MaintenanceBanner.vue'))
import { pageTitles } from './data/nav.js'
import { createMediaSession, logout as logoutApi } from './api/auth.js'
import { currentUser, invalidateCurrentUserCache } from './api/system.js'
import { clearAuth, getCachedUsername, getToken, isAuthed, setAuth } from './utils/auth.js'
import { confirmAction } from './utils/confirmAction.js'
import { runNavigationGuard } from './utils/navigationGuard.js'
import { closeSse, connectSse } from './utils/sse.js'
import { installClientErrorReporter, recordClientError } from './utils/errorReporter.js'
import { playIncomingMessageSound, primeAudioOnFirstGesture } from './utils/notifySound.js'
import { warmLiteAccountsList } from './api/accounts.js'
import { getNavigationHome } from './api/navigation.js'
import { getFeatureSwitchStatus, invalidateFeatureSwitchCache } from './api/feature-switch.js'
import { globalConfirm } from './composables/confirmState.js'
import { setBrowseMode, setPreviewMode, clearAllLimitModes } from './composables/featureGuard.js'

const AsyncPageLoading = {
  name: 'AsyncPageLoading',
  render: () => h('div', { class: 'page-loading', role: 'status' }, '页面加载中...')
}

const AsyncPageError = {
  name: 'AsyncPageError',
  render: () => h('div', { class: 'page-load-error', role: 'alert' }, '页面加载失败，请刷新后重试')
}

const asyncPage = loader => defineAsyncComponent({
  loader,
  loadingComponent: AsyncPageLoading,
  errorComponent: AsyncPageError,
  delay: 120,
  timeout: 30000
})

const LoginPage = asyncPage(() => import('./pages/LoginPage.vue'))
const RegisterPage = asyncPage(() => import('./pages/RegisterPage.vue'))
const ForgotPasswordPage = asyncPage(() => import('./pages/ForgotPasswordPage.vue'))
const DashboardPage = asyncPage(() => import('./pages/DashboardPage.vue'))
const AiCsSettings = asyncPage(() => import('./pages/settings/AiCsSettings.vue'))
const KnowledgeBaseSettings = asyncPage(() => import('./pages/settings/KnowledgeBaseSettings.vue'))
const SyncSettings = asyncPage(() => import('./pages/settings/SyncSettings.vue'))
const AboutSettings = asyncPage(() => import('./pages/settings/AboutSettings.vue'))

const pageMap = {
  login: LoginPage,
  register: RegisterPage,
  'forgot-password': ForgotPasswordPage,
  dashboard: DashboardPage,
  data: asyncPage(() => import('./pages/DataPage.vue')),
  accounts: asyncPage(() => import('./pages/AccountsPage.vue')),
  products: asyncPage(() => import('./pages/ProductsPage.vue')),
  orders: asyncPage(() => import('./pages/OrdersPage.vue')),
  refunds: asyncPage(() => import('./pages/RefundsPage.vue')),
  rates: asyncPage(() => import('./pages/RatesPage.vue')),
  'product-publish': asyncPage(() => import('./pages/ProductPublishPage.vue')),
  'goods-data': asyncPage(() => import('./pages/GoodsDataPage.vue')),
  // 鱼小铺专属编辑页：路由形态 fish-shop-edit/{accountId}/{itemId}
  // 由 ProductsPage 商品列表「编辑」按钮进入，仅鱼小铺账号商品可访问
  'fish-shop-edit': asyncPage(() => import('./pages/FishShopEditPage.vue')),
  // 退款详情页：路由形态 refund-detail/{accountId}/{orderId}/{refundId}
  // 由 RefundsPage 退款列表「查看详情」按钮进入，仅鱼小铺账号可访问
  // 不加入左侧菜单、不加入移动端白名单（参考 fish-shop-edit 模式）
  'refund-detail': asyncPage(() => import('./pages/RefundDetailPage.vue')),
  opportunities: asyncPage(() => import('./pages/OpportunityPage.vue')),
  'fish-shop-data': asyncPage(() => import('./pages/FishShopDataPage.vue')),
  messages: asyncPage(() => import('./pages/MessagesPage.vue')),
  'message-center': asyncPage(() => import('./pages/MessagesPage.vue')),
  workflow: asyncPage(() => import('./pages/WorkflowPage.vue')),
  'workflow-tasks': asyncPage(() => import('./pages/WorkflowTasksPage.vue')),
  'workflow-drafts': asyncPage(() => import('./pages/WorkflowDraftsPage.vue')),
  'workflow-image-records': asyncPage(() => import('./pages/WorkflowImageRecordsPage.vue')),
  'card-warehouse': asyncPage(() => import('./pages/CardWarehousePage.vue')),
  'auto-delivery': asyncPage(() => import('./pages/AutoDeliveryPage.vue')),
  'delivery-source-library': asyncPage(() => import('./pages/DeliverySourceLibraryPage.vue')),
  'delivery-statement': asyncPage(() => import('./pages/DeliveryStatementPage.vue')),
  'delivery-mall': asyncPage(() => import('./pages/DeliveryMallPage.vue')),
  'delivery-templates': asyncPage(() => import('./pages/DeliveryTemplatesPage.vue')),
  'delivery-records': asyncPage(() => import('./pages/DeliveryRecordsPage.vue')),
  'scheduled-tasks': asyncPage(() => import('./pages/ScheduledTasksPage.vue')),
  'auto-reply': asyncPage(() => import('./pages/AutoReplyPage.vue')),
  logs: asyncPage(() => import('./pages/LogsPage.vue')),
  'slider-solve-records': asyncPage(() => import('./pages/SliderSolveRecordsPage.vue')),
  'api-slider-solve': asyncPage(() => import('./pages/ApiSliderSolvePage.vue')),
  feedback: asyncPage(() => import('./pages/FeedbackPage.vue')),
  'settings-notify': asyncPage(() => import('./pages/settings/NotifySettings.vue')),
  'settings-ai-cs': AiCsSettings,
  'settings-kb': KnowledgeBaseSettings,
  // 数据同步页面仅在本地开发环境注册（VITE_SHOW_DATA_SYNC=true）
  // 商业版（线上生产）不注册该路由，直接访问 #/settings-sync 会被重定向到默认页
  ...(import.meta.env.VITE_SHOW_DATA_SYNC === 'true' ? { 'settings-sync': SyncSettings } : {}),
  'settings-about': AboutSettings,
  vip: asyncPage(() => import('./pages/VipPage.vue')),
  profile: asyncPage(() => import('./pages/ProfileCenterPage.vue')),
  'feature-unavailable': asyncPage(() => import('./pages/FeatureUnavailablePage.vue')),
  // 供货中心（Phase 1 上线）：供货商管理货源商品
  'supply-center': asyncPage(() => import('./pages/SupplyCenterPage.vue')),
  'supply-center-products': asyncPage(() => import('./pages/SupplyProductListPage.vue')),
  'supply-center-products-new': asyncPage(() => import('./pages/SupplyProductEditPage.vue')),
  // 路由形态 supply-center-products-edit/{id}，由 SupplyProductListPage 编辑按钮进入
  'supply-center-products-edit': asyncPage(() => import('./pages/SupplyProductEditPage.vue')),
  // 维护中页面
  'platform-connect': asyncPage(() => import('./pages/FeatureUnavailablePage.vue')),
  'growth-partner': asyncPage(() => import('./pages/GrowthPartnerPage.vue')),
  'invite-poster': asyncPage(() => import('./pages/FeatureUnavailablePage.vue'))
}

// 数据同步板块仅在本地开发环境显示（VITE_SHOW_DATA_SYNC=true）
// 商业版（线上生产）不设置此变量，settings-sync 不会进入 allSettingKeys
const allSettingKeys = [
  'settings-ai-cs',
  'settings-kb',
  'settings-notify',
  ...(import.meta.env.VITE_SHOW_DATA_SYNC === 'true' ? ['settings-sync'] : []),
  'settings-about'
]
const authPages = ['login', 'register', 'forgot-password']
const defaultPage = 'dashboard'
const profileEntryStorageKey = 'xya_profile_initial_tab'
const pagesWithEmbeddedTitle = new Set(['messages', 'message-center', 'delivery-statement', 'delivery-mall', 'feature-unavailable', 'card-warehouse', 'auto-delivery', 'refund-detail', 'settings-ai-cs', 'settings-kb', 'settings-notify', 'settings-sync', 'settings-about', 'growth-partner', 'supply-center', 'supply-center-products', 'supply-center-products-new', 'supply-center-products-edit'])
// 功能开关检查跳过的页面：登录/注册/忘记密码/占位页/工作台（避免登录后卡死）/维护中页面
const featureSwitchSkipPages = new Set(['login', 'register', 'forgot-password', 'feature-unavailable', 'dashboard', 'platform-connect', 'growth-partner', 'invite-poster'])
const profileEntryTabs = new Set(['overview', 'security', 'token', 'recharge'])
const mobileLitePages = new Set([
  'dashboard',
  'data',
  'data-detail',
  'accounts',
  'account-detail',
  'products',
  'product-detail',
  'messages',
  'message-center',
  'chat-detail',
  'workflow',
  'auto-delivery',
  'product-publish',
  'goods-data',
  'fish-shop-edit',
  'orders',
  'profile',
  'api-slider-solve',
  'refund-detail',
  'delivery-source-library',
  'supply-center',
  'supply-center-products',
  'supply-center-products-new',
  'supply-center-products-edit'
])

// 剥离 hash 路由中的查询参数（如 register?ref=XXX -> register）
// active.value 保留原始 raw（含查询参数），但页面判断/组件映射只看 path 部分
const stripQuery = key => {
  if (typeof key !== 'string') return key
  const idx = key.indexOf('?')
  return idx >= 0 ? key.slice(0, idx) : key
}

const isKnownPage = key => {
  const path = stripQuery(key)
  if (pageMap[path]) return true
  if (allSettingKeys.includes(path)) return true
  if (mobileLitePages.has(path)) return true
  if (typeof path === 'string') {
    if (path.startsWith('account-detail/')) return true
    if (path.startsWith('product-detail/')) return true
    if (path.startsWith('data-detail/')) return true
    if (path.startsWith('chat-detail/')) return true
    if (path.startsWith('fish-shop-edit/')) return true
    if (path.startsWith('refund-detail/')) return true
    if (path.startsWith('supply-center-products-edit/')) return true
  }
  return false
}

const normalizePageKey = key => {
  if (isKnownPage(key)) {
    const path = stripQuery(key)
    if (typeof path === 'string') {
      if (path.startsWith('account-detail/')) return 'account-detail'
      if (path.startsWith('product-detail/')) return 'product-detail'
      if (path.startsWith('data-detail/')) return 'data-detail'
      if (path.startsWith('chat-detail/')) return 'chat-detail'
      if (path.startsWith('fish-shop-edit/')) return 'fish-shop-edit'
      if (path.startsWith('refund-detail/')) return 'refund-detail'
      if (path.startsWith('supply-center-products-edit/')) return 'supply-center-products-edit'
    }
    return path
  }
  return defaultPage
}
const getHash = () => {
  const raw = (location.hash || `#/${defaultPage}`).replace('#/', '') || defaultPage
  return raw
}
const getNormalizedKey = (raw) => {
  if (isKnownPage(raw)) {
    const path = stripQuery(raw)
    if (typeof path === 'string') {
      if (path.startsWith('account-detail/')) return 'account-detail'
      if (path.startsWith('product-detail/')) return 'product-detail'
      if (path.startsWith('data-detail/')) return 'data-detail'
      if (path.startsWith('chat-detail/')) return 'chat-detail'
      if (path.startsWith('fish-shop-edit/')) return 'fish-shop-edit'
      if (path.startsWith('refund-detail/')) return 'refund-detail'
      if (path.startsWith('supply-center-products-edit/')) return 'supply-center-products-edit'
    }
    return path
  }
  return defaultPage
}
const normalizeProfileEntryTab = key => profileEntryTabs.has(key) ? key : 'overview'

const booting = ref(true)
const bootMessage = ref('正在检查登录状态')
const loggingIn = ref(false)
const authNotice = ref('')
const active = ref(getHash())
const currentUserInfo = ref(buildDefaultUserInfo())
const displaySseStatus = ref('disconnected')
const globalNotice = ref(null)
// 全局充值弹窗（由 xya-open-payment 事件触发，供 aiTokenGuard 等 Token 不足场景使用）
const paymentVisible = ref(false)
// AI 客服"小梦"面板可见性（Topbar 客服按钮触发）
const aiCsVisible = ref(false)
// 路由切换时自动收起 AI 客服面板（动画收起，历史保留在组件内，下次打开仍可见）
// 面板内部使用 v-show 保持挂载，状态不会丢失
watch(active, () => {
  if (aiCsVisible.value) aiCsVisible.value = false
})
const isMobile = ref(false)
const mobileDesktopOverride = ref(localStorage.getItem('xya_mobile_desktop_override') === '1')
// 功能开关拦截信息（传递给 FeatureUnavailablePage）
const featureUnavailableInfo = ref({ reason: 'disabled', required: '', featureKey: '' })
let noticeTimer = null
let mediaSessionTimer = null
// 程序式导航（navigate 设置 location.hash）触发的 hashchange 不再走守卫，避免重复弹窗
let suppressHashGuard = false

function clearMediaSessionTimer() {
  if (mediaSessionTimer) clearTimeout(mediaSessionTimer)
  mediaSessionTimer = null
}

async function initializeMediaSession({ silent = false } = {}) {
  clearMediaSessionTimer()
  try {
    const response = await createMediaSession()
    if (response?.data?.ready !== true) {
      throw new Error('私有媒体会话未被服务端确认')
    }
    // The server issues a short-lived, path-restricted cookie. Refresh before
    // its 20-minute ceiling without extending the underlying JWT lifetime.
    mediaSessionTimer = setTimeout(() => {
      initializeMediaSession({ silent: true })
    }, 10 * 60 * 1000)
  } catch (error) {
    if (silent) {
      showNotice('私有图片会话刷新失败，图片预览暂不可用；请重新登录后重试', 'warn')
      recordClientError(error, { source: 'media_session_refresh' })
      return false
    }
    const boundaryError = new Error('私有图片安全会话初始化失败，请稍后重试')
    recordClientError(error, { source: 'media_session_initialization' })
    throw boundaryError
  }
  return true
}

function buildDefaultUserInfo(username = getCachedUsername() || '当前用户') {
  const safeName = username || '当前用户'
  return {
    username: safeName,
    nickname: safeName,
    avatar: '/xya/chat_ui_assets/chat_ui_assets_023.png',
    activePlan: null,
    planCode: null,
    planName: null,
    profileUnavailable: true
  }
}

function rememberProfileEntryTab(target = 'overview') {
  const nextTab = normalizeProfileEntryTab(target)
  localStorage.setItem(profileEntryStorageKey, nextTab)
  window.dispatchEvent(new CustomEvent('xya-profile-open-tab', { detail: nextTab }))
}

function showNotice(text, type = 'info') {
  globalNotice.value = { text, type }
  if (noticeTimer) clearTimeout(noticeTimer)
  noticeTimer = setTimeout(() => {
    globalNotice.value = null
  }, 4500)
}

// 全局 xya-toast 事件监听：将各页面派发的 toast 事件统一渲染为顶部 global-notice。
// 事件 detail 形如 { message, isError }，isError=true 时使用 error 色调，否则 info。
function onGlobalToast(event) {
  const detail = event?.detail || {}
  const message = typeof detail === 'string' ? detail : detail.message
  if (!message) return
  const type = detail.isError ? 'error' : (detail.type || 'info')
  showNotice(message, type)
}

// 全局 xya-open-payment 事件监听：打开 Token 充值弹窗（用于 Token 余额不足时的引导充值）。
function onOpenPayment() {
  paymentVisible.value = true
}

// 打开 AI 客服"小梦"面板。
function openAiCs() {
  aiCsVisible.value = true
}

// 充值成功回调：关闭弹窗并提示。
async function handleTokenPaid() {
  paymentVisible.value = false
  showNotice('支付成功，Token 余额已刷新', 'success')
  // 刷新当前用户信息（包含 token 余额），失败不阻塞
  try {
    invalidateCurrentUserCache()
    await loadCurrentUser(true)
  } catch (_e) {
    // 忽略刷新失败
  }
}

/**
 * 功能开关检查：判断目标页面是否对当前用户开放。
 * 返回 { allowed: true } 或 { allowed: false, reason, required }。
 * 当 allowed=true 且 preview=true 时，表示预览模式（可进入但不可执行业务操作）。
 * 失败降级：API 异常时默认放行，避免后端故障锁死所有页面。
 */
async function checkFeatureSwitch(pageKey) {
  if (featureSwitchSkipPages.has(pageKey)) return { allowed: true, preview: false }
  // 仅对已知页面（pageMap 或 allSettingKeys）检查，避免对未知 key 误拦
  if (!pageMap[pageKey] && !allSettingKeys.includes(pageKey)) return { allowed: true, preview: false }
  try {
    const status = await getFeatureSwitchStatus()
    if (!status || typeof status !== 'object') return { allowed: true, preview: false }
    const accessible = status.accessible || {}
    const blocked = status.blocked || {}
    const preview = status.preview || {}
    if (accessible[pageKey] === true) {
      const previewInfo = preview[pageKey]
      return {
        allowed: true,
        preview: !!previewInfo,
        reasonText: previewInfo?.reason_text || ''
      }
    }
    if (blocked[pageKey]) {
      const info = blocked[pageKey]
      return {
        allowed: false,
        preview: false,
        reason: info.reason || 'disabled',
        required: info.required_level || '',
        reasonText: info.reason_text || ''
      }
    }
    return { allowed: true, preview: false }
  } catch (e) {
    recordClientError(e, { source: 'feature_switch_check' })
    return { allowed: true, preview: false }
  }
}

/**
 * 功能被开关拦截时，弹出提示弹窗（不跳转到占位页）。
 * - reason=maintenance：提示"正在维护升级中"（对所有用户生效，路由拦截）
 * - reason=blocked：提示"该功能当前不可访问"（管理员限制不可进入，路由拦截）
 * - reason=disabled：提示"暂未开放"（路由拦截）
 * - reason=level：已改为浏览模式（路由放行），由 guardFeatureAction 在页面内拦截写操作
 */
async function showFeatureBlockedNotice(switchResult) {
  const reason = switchResult.reason || 'disabled'
  if (reason === 'maintenance') {
    await globalConfirm.alert('维护中', switchResult.reasonText || '该页面正在维护升级中，请稍后再试。')
    return
  }
  if (reason === 'blocked') {
    await globalConfirm.alert('不可访问', switchResult.reasonText || '该功能当前不可访问。')
    return
  }
  await globalConfirm.alert('暂未开放', '该功能暂未开放，敬请期待。')
}

async function navigate(key) {
  const requested = key || defaultPage
  const normalizedKey = getNormalizedKey(requested)
  if (!isKnownPage(requested)) {
    showNotice('页面不存在，已返回默认页面', 'warn')
  }
  if (!isAuthed() && !authPages.includes(normalizedKey)) {
    location.hash = '#/login'
    active.value = 'login'
    return
  }
  if (requested === active.value) return
  // 离开当前页前，交由导航守卫处理草稿询问等逻辑
  const allowed = await runNavigationGuard()
  if (!allowed) return
  // 功能开关检查
  const switchResult = await checkFeatureSwitch(normalizedKey)
  if (!switchResult.allowed) {
    // 等级不足：改为浏览模式，放行进入页面，由页面内 guardFeatureAction / request.js 拦截写操作
    if (switchResult.reason === 'level') {
      setBrowseMode({
        featureKey: normalizedKey,
        requiredLevel: switchResult.required,
        reasonText: switchResult.reasonText
      })
      suppressHashGuard = true
      location.hash = `#/${requested}`
      active.value = requested
      if (authPages.includes(normalizedKey)) authNotice.value = ''
      return
    }
    // 维护中 / 不可进入 / 暂未开放：拦截 + 弹窗，不进入页面
    clearAllLimitModes()
    await showFeatureBlockedNotice(switchResult)
    return
  }
  // 放行：清除所有限制模式（上一页的浏览/预览状态不带到新页面）
  clearAllLimitModes()
  // 预览模式：可进入页面查看，但不可执行业务操作（由 guardFeatureAction / request.js 拦截写操作）
  if (switchResult.preview) {
    setPreviewMode({
      featureKey: normalizedKey,
      reasonText: switchResult.reasonText
    })
  }
  suppressHashGuard = true
  location.hash = `#/${requested}`
  active.value = requested
  if (authPages.includes(normalizedKey)) authNotice.value = ''
}

function openProfileCenter(target = 'overview') {
  rememberProfileEntryTab(target)
  navigate('profile')
}

function enableMobileDesktopMode(target) {
  if (target?.profileTab) rememberProfileEntryTab(target.profileTab)
  mobileDesktopOverride.value = true
  localStorage.setItem('xya_mobile_desktop_override', '1')
  if (target?.page) navigate(target.page)
}

function returnToMobileHome() {
  mobileDesktopOverride.value = false
  localStorage.removeItem('xya_mobile_desktop_override')
  navigate(defaultPage)
}

async function onHeaderAction(action) {
  if (action.to) return navigate(action.to)
  if (action.confirm) {
    const ok = await confirmAction({
      title: action.confirm.title || `确认执行${action.text}？`,
      description: action.confirm.description || '该操作可能影响当前数据，请确认后继续。',
      confirmText: action.confirm.confirmText || '',
      dangerous: action.confirm.dangerous || false
    })
    if (!ok) return
  }
  if (action.event) {
    window.dispatchEvent(new CustomEvent('xya-header-action', { detail: action.event }))
    return
  }
  showNotice(`“${action.text}”暂未接入执行逻辑，已为你拦截空点击。`, 'warn')
}

function onHash() {
  const raw = getHash()
  const normalizedKey = getNormalizedKey(raw)
  if (!isAuthed() && !authPages.includes(normalizedKey)) {
    navigate('login')
    return
  }
  // 程序式导航产生的 hashchange：只同步 active，不再触发守卫
  if (suppressHashGuard) {
    suppressHashGuard = false
    const previous = active.value
    active.value = raw
    if (authPages.includes(normalizedKey) && normalizedKey !== getNormalizedKey(previous)) authNotice.value = ''
    return
  }
  if (raw === active.value) return
  // 浏览器前进/后退或地址栏直接改 hash：走守卫后再切换
  handleGuardedHashNavigation(raw)
}

async function handleGuardedHashNavigation(raw) {
  const normalizedKey = getNormalizedKey(raw)
  const allowed = await runNavigationGuard()
  if (!allowed) {
    // 守卫拒绝：把 hash 还原回当前页，避免地址栏与内容不一致
    suppressHashGuard = true
    location.hash = `#/${active.value}`
    return
  }
  // 功能开关检查
  const switchResult = await checkFeatureSwitch(normalizedKey)
  if (!switchResult.allowed) {
    // 等级不足：改为浏览模式，放行进入页面
    if (switchResult.reason === 'level') {
      setBrowseMode({
        featureKey: normalizedKey,
        requiredLevel: switchResult.required,
        reasonText: switchResult.reasonText
      })
      const previous = active.value
      active.value = raw
      if (authPages.includes(normalizedKey) && normalizedKey !== getNormalizedKey(previous)) authNotice.value = ''
      return
    }
    // 维护中 / 不可进入 / 暂未开放：还原 hash 到当前页 + 弹窗
    clearAllLimitModes()
    suppressHashGuard = true
    location.hash = `#/${active.value}`
    await showFeatureBlockedNotice(switchResult)
    return
  }
  // 放行：清除所有限制模式（上一页的浏览/预览状态不带到新页面）
  clearAllLimitModes()
  // 预览模式：可进入页面查看，但不可执行业务操作（由 guardFeatureAction / request.js 拦截写操作）
  if (switchResult.preview) {
    setPreviewMode({
      featureKey: normalizedKey,
      reasonText: switchResult.reasonText
    })
  }
  const previous = active.value
  active.value = raw
  if (authPages.includes(normalizedKey) && normalizedKey !== getNormalizedKey(previous)) authNotice.value = ''
}

async function loadCurrentUser(force = false) {
  if (!getToken()) return
  try {
    const res = await currentUser({ force })
    if (!res?.data || typeof res.data !== 'object' || Array.isArray(res.data)) {
      throw new Error('当前用户资料响应格式异常')
    }
    currentUserInfo.value = {
      ...buildDefaultUserInfo(),
      ...currentUserInfo.value,
      ...res.data,
      profileUnavailable: false
    }
  } catch (e) {
    if (e?.code === 401) {
      window.dispatchEvent(new CustomEvent('xya-auth-expired', { detail: e }))
      return
    }
    currentUserInfo.value = {
      ...currentUserInfo.value,
      profileUnavailable: true
    }
    recordClientError(e, { source: 'current_user' })
  }
}

function clearWarmupTimers() {
  // Startup warmups stay disabled on the US frontend path.
}

function scheduleWarmups() {
  clearWarmupTimers()
  // 预热闲鱼账号列表缓存，使商机发掘等页面进入时可直接复用缓存数据，避免"账号状态加载中"卡顿
  warmLiteAccountsList().catch(() => { /* 静默失败，页面进入时会按需重新拉取 */ })
}

function startSse() {
  if (!getToken()) return
  connectSse(
    event => window.dispatchEvent(new CustomEvent('xya-sse-event', { detail: event })),
    status => { displaySseStatus.value = status }
  )
}

async function handleLoginSuccess(payload) {
  const token = String(payload?.token || '').trim()
  if (!payload || typeof payload !== 'object' || Array.isArray(payload) || !token) {
    authNotice.value = '登录服务未返回有效凭证，未进入系统。请重试或联系管理员。'
    recordClientError(new Error('登录成功事件缺少有效凭证'), { source: 'login_success_boundary' })
    return
  }
  loggingIn.value = true
  try {
    invalidateCurrentUserCache()
    invalidateFeatureSwitchCache()
    setAuth(token, payload.username)
    currentUserInfo.value = buildDefaultUserInfo(payload?.username || getCachedUsername() || '当前用户')
    startSse()
    scheduleWarmups()
    // 功能开关预热 + 媒体会话后台异步，不阻塞进入首页
    getFeatureSwitchStatus().catch(() => {})
    initializeMediaSession().catch(() => {
      showNotice('私有图片会话初始化失败，图片预览暂不可用', 'warn')
    })
    await loadCurrentUser(true)
    navigate(defaultPage)
    authNotice.value = ''
  } catch (error) {
    clearAuth()
    closeSse()
    location.hash = '#/login'
    active.value = 'login'
    authNotice.value = error?.message || '登录会话初始化失败，请重试。'
    recordClientError(error, { source: 'login_session_initialization' })
  } finally {
    loggingIn.value = false
  }
}

async function handleLogout() {
  clearWarmupTimers()
  clearMediaSessionTimer()
  invalidateCurrentUserCache()
  invalidateFeatureSwitchCache()
  let logoutWarning = ''
  try {
    await logoutApi()
  } catch (error) {
    clearAuth()
    logoutWarning = '本地已退出，但服务端会话撤销未确认；如非本人操作，请立即联系管理员。'
    recordClientError(error, { source: 'logout_session_revocation' })
  }
  closeSse()
  currentUserInfo.value = buildDefaultUserInfo('当前用户')
  navigate('login')
  if (logoutWarning) authNotice.value = logoutWarning
}

async function boot() {
  booting.value = true
  try {
    // 优先处理代登路由：URL 形如 #/auto-login?token=xxx&username=xxx
    // 由后台管理员代登跳转过来，token 一次性使用后立即从 URL 中清除
    const autoLogin = consumeAutoLoginHash()
    if (autoLogin) {
      bootMessage.value = '正在以指定账号登录'
      invalidateCurrentUserCache()
      invalidateFeatureSwitchCache()
      setAuth(autoLogin.token, autoLogin.username || '')
      // URL 已由 consumeAutoLoginHash 清理，active 已设为 dashboard
      // 继续走下方已登录分支完成会话初始化
    }

    if (getToken()) {
      bootMessage.value = '正在恢复登录会话'
      if (authPages.includes(getNormalizedKey(active.value))) active.value = defaultPage
      // 首屏只等待用户信息（决定登录态），媒体会话与功能开关后台异步预热，不阻塞渲染
      startSse()
      scheduleWarmups()
      // 功能开关预热：与用户信息并行，首次路由切换时直接命中 30s 内存缓存
      getFeatureSwitchStatus().catch(() => {})
      // 媒体会话后台异步：仅用于私有图片预览，失败时提示但不阻塞首屏
      initializeMediaSession().catch(() => {
        showNotice('私有图片会话初始化失败，图片预览暂不可用', 'warn')
      })
      // 首页数据预热：与用户信息并行，DashboardPage 进入时直接命中缓存避免"加载中"卡顿
      getNavigationHome({ limit: 5 }).catch(() => {})
      await loadCurrentUser()
      if (!location.hash || authPages.includes(getNormalizedKey(getHash()))) navigate(defaultPage)
      return
    }
    if (!location.hash) {
      navigate('login')
      return
    }

    const requested = getHash()
    // 用 getNormalizedKey 剥离查询参数后判断是否是 authPage
    // 支持 #/register?ref=XXX 这类带参 hash 路由
    if (authPages.includes(getNormalizedKey(requested))) {
      active.value = requested
      return
    }

    navigate('login')
  } catch (e) {
    clearMediaSessionTimer()
    invalidateCurrentUserCache()
    clearAuth()
    closeSse()
    currentUserInfo.value = buildDefaultUserInfo('当前用户')
    location.hash = '#/login'
    recordClientError(e, { source: 'app_boot' })
    active.value = 'login'
    authNotice.value = e?.message || '登录安全会话初始化失败，未进入系统。请稍后重试或联系管理员。'
  } finally {
    booting.value = false
  }
}

/**
 * 消费代登 hash：检测 location.hash 是否为 #/auto-login?token=xxx&username=yyy，
 * 若是则返回 {token, username} 并立即清除 URL（避免 token 泄露到 history/referer）。
 * 由后台管理员代登跳转触发，token 仅一次性使用。
 */
function consumeAutoLoginHash() {
  const rawHash = location.hash || ''
  // 严格匹配前缀，避免误消费其他以 auto-login 开头的页面（当前 pageMap 不存在此键）
  if (!rawHash.startsWith('#/auto-login')) return null
  const queryIndex = rawHash.indexOf('?')
  if (queryIndex < 0) return null
  const params = new URLSearchParams(rawHash.slice(queryIndex + 1))
  const token = (params.get('token') || '').trim()
  const username = (params.get('username') || '').trim()
  if (!token) return null
  // 立即用 history.replaceState 清除 URL 中的 token，避免被浏览器历史/Referer/日志泄露
  history.replaceState(null, '', '#/dashboard')
  // 同步更新 active，避免 boot 流程误判
  active.value = defaultPage
  return { token, username }
}

function onAuthExpired() {
  if (loggingIn.value) return
  clearWarmupTimers()
  clearMediaSessionTimer()
  invalidateCurrentUserCache()
  clearAuth()
  closeSse()
  showNotice('登录已过期，请重新登录', 'warn')
  navigate('login')
}

function onCaptchaRequired() {
  // 滑块求解由 useCaptchaSolver 自动处理，此处仅提示
  showNotice('检测到滑块验证，正在自动求解…', 'warn')
}

function onSseEventForSound(event) {
  const detail = event?.detail || {}
  const type = detail.type || detail.eventType
  const direction = String(detail.direction || '').toUpperCase()
  if (type === 'message' && direction !== 'OUT') {
    playIncomingMessageSound()
  }
}

function updateMobileState() {
  const ua = navigator.userAgent || ''
  isMobile.value = window.matchMedia?.('(max-width: 900px)').matches || /Mobi|Android|iPhone|iPad|iPod/i.test(ua)
}

// 接收 featureGuard composable 派发的导航请求（浏览模式弹窗点击"立即升级"后跳转会员中心）
function onNavigateRequest(event) {
  const target = event?.detail
  if (typeof target === 'string' && target) navigate(target)
}

onMounted(() => {
  installClientErrorReporter()
  updateMobileState()
  window.addEventListener('resize', updateMobileState)
  window.addEventListener('orientationchange', updateMobileState)
  window.addEventListener('hashchange', onHash)
  window.addEventListener('xya-auth-expired', onAuthExpired)
  window.addEventListener('xya-captcha-required', onCaptchaRequired)
  window.addEventListener('xya-sse-event', onSseEventForSound)
  // 全局 toast 事件监听：将各页面派发的 xya-toast 统一渲染为顶部 global-notice
  window.addEventListener('xya-toast', onGlobalToast)
  // 全局充值弹窗事件监听：Token 余额不足时由 aiTokenGuard 等模块派发，弹出充值 modal
  window.addEventListener('xya-open-payment', onOpenPayment)
  // AI 客服面板打开事件：Dashboard / 货源商城等页面派发 xya-open-ai-cs，由 App.vue 统一打开"小梦"面板
  // 必须与 onBeforeUnmount 中的 removeEventListener 配对（修复前缺失 addEventListener 导致入口失效）
  window.addEventListener('xya-open-ai-cs', openAiCs)
  // 浏览模式等级不足弹窗点击"立即升级"后，由 featureGuard 派发导航请求
  window.addEventListener('xya-navigate', onNavigateRequest)
  // 初始化滑块求解 SSE 监听
  import('./composables/useCaptchaSolver.js').then(({ useCaptchaSolver }) => {
    useCaptchaSolver().initCaptchaSolverListener()
  })
  primeAudioOnFirstGesture()
  boot()
})

onBeforeUnmount(() => {
  clearWarmupTimers()
  clearMediaSessionTimer()
  window.removeEventListener('resize', updateMobileState)
  window.removeEventListener('orientationchange', updateMobileState)
  window.removeEventListener('hashchange', onHash)
  window.removeEventListener('xya-auth-expired', onAuthExpired)
  window.removeEventListener('xya-captcha-required', onCaptchaRequired)
  window.removeEventListener('xya-sse-event', onSseEventForSound)
  window.removeEventListener('xya-toast', onGlobalToast)
  window.removeEventListener('xya-open-payment', onOpenPayment)
  window.removeEventListener('xya-navigate', onNavigateRequest)
  window.removeEventListener('xya-open-ai-cs', openAiCs)
  import('./composables/useCaptchaSolver.js').then(({ useCaptchaSolver }) => {
    useCaptchaSolver().destroyCaptchaSolverListener()
  })
  closeSse()
})

const pageComponent = computed(() => {
  const normalized = getNormalizedKey(active.value)
  return pageMap[normalized] || DashboardPage
})
const title = computed(() => (pageTitles[getNormalizedKey(active.value)] || pageTitles.dashboard)[0])
const subtitle = computed(() => (pageTitles[getNormalizedKey(active.value)] || pageTitles.dashboard)[1])
const pageHeaderTitle = computed(() => pagesWithEmbeddedTitle.has(getNormalizedKey(active.value)) ? '' : title.value)
const pageHeaderSubtitle = computed(() => pagesWithEmbeddedTitle.has(getNormalizedKey(active.value)) ? '' : subtitle.value)
const shouldUseMobileLite = computed(() => {
  if (!isMobile.value || mobileDesktopOverride.value || authPages.includes(getNormalizedKey(active.value))) return false
  const normalized = getNormalizedKey(active.value)
  return mobileLitePages.has(normalized)
})

const headerActions = computed(() => {
  if (active.value === 'settings-notify') {
    return [
      { text: '保存设置', type: 'primary', event: 'notify-save' },
      { text: '测试发送', type: 'ghost', event: 'notify-test' },
      { text: '刷新日志', type: 'ghost', event: 'notify-refresh' }
    ]
  }
  if (active.value.startsWith('settings-')) {
    // 其余设置页在页面内部提供与加载状态绑定的保存/测试按钮。
    // 不在全局页头重复派发无人监听的事件，避免可见但无反馈的空点击。
    return []
  }

  const map = {
    data: [{ text: '刷新数据', type: 'ghost', event: 'refresh-data-panel' }],
    accounts: [
      { text: '扫码加账号', type: 'primary', event: 'open-scan-account' },
      { text: '手动添加', type: 'ghost', event: 'open-manual-account' },
      { text: '批量刷新', type: 'ghost', event: 'refresh-accounts' }
    ],
    products: [
      { text: '同步闲鱼商品', type: 'primary', event: 'sync-products' },
      { text: '+ 发布商品', type: 'primary', to: 'product-publish' }
    ],
    orders: [{ text: '刷新订单', type: 'ghost', event: 'orders-refresh' }],
    workflow: [
      { text: '+ 新建工作流', type: 'primary', event: 'workflow-new' },
      { text: '保存草稿', type: 'ghost', event: 'workflow-save' },
      { text: '运行测试', type: 'ghost', event: 'workflow-run' },
      { text: '发布并启用', type: 'primary', event: 'workflow-publish' }
    ],
    'workflow-tasks': [
      { text: '刷新列表', type: 'ghost', event: 'workflow-tasks-refresh' },
      { text: '打开流程编排', type: 'primary', to: 'workflow' }
    ],
    'workflow-drafts': [
      { text: '刷新列表', type: 'ghost', event: 'workflow-drafts-refresh' }
    ],
    'workflow-image-records': [
      { text: '刷新列表', type: 'ghost', event: 'workflow-image-records-refresh' }
    ],
    'card-warehouse': [
      { text: '新建卡密组', type: 'primary', event: 'cards-create-group' },
      { text: '导出当前分组', type: 'ghost', event: 'cards-export-current' },
      { text: '刷新数据', type: 'ghost', event: 'cards-refresh' }
    ],
    'auto-delivery': [
      { text: '批量设置', type: 'primary', event: 'delivery-batch' },
      { text: '货源库', type: 'ghost', to: 'delivery-source-library' },
      { text: '刷新数据', type: 'ghost', event: 'delivery-refresh' }
    ],
    'delivery-source-library': [
      { text: '+ 新增货源', type: 'primary', event: 'source-new' },
      { text: '刷新列表', type: 'ghost', event: 'source-refresh' }
    ],
    'delivery-statement': [
      { text: '保存设置', type: 'primary', event: 'statement-save' },
      { text: '预览声明', type: 'ghost', event: 'statement-preview' }
    ],
    'delivery-templates': [
      { text: '+ 新建模板', type: 'primary', event: 'template-new' },
      { text: '刷新列表', type: 'ghost', event: 'template-refresh' }
    ],
    'delivery-records': [
      { text: '导出CSV', type: 'ghost', event: 'delivery-records-export' },
      { text: '批量重试失败', type: 'ghost', event: 'delivery-records-retry', confirm: { title: '确认批量重试失败发货？', description: '系统会重新触发失败记录，请先确认库存和规则配置。' } },
      { text: '刷新数据', type: 'ghost', event: 'delivery-records-refresh' }
    ],
    'scheduled-tasks': [
      { text: '立即执行', type: 'ghost', event: 'scheduled-task-run-current' },
      { text: '保存配置', type: 'ghost', event: 'scheduled-task-save' },
      { text: '+ 新建任务', type: 'primary', event: 'scheduled-task-new' }
    ],
    logs: [
      { text: '导出CSV', type: 'ghost', event: 'logs-export' },
      { text: '刷新', type: 'ghost', event: 'logs-refresh' }
    ],
    profile: [
      { text: '刷新资料', type: 'ghost', event: 'refresh-profile' }
    ]
  }
  return map[active.value] || []
})
const shouldRenderPageHeader = computed(() => Boolean(pageHeaderTitle.value || pageHeaderSubtitle.value || headerActions.value.length))
</script>

<style scoped>
.page-loading,
.page-load-error {
  color: #526079;
  background: #fff;
  border: 1px solid #e8eef8;
  border-radius: 18px;
  padding: 28px;
  text-align: center;
  box-shadow: 0 10px 26px rgba(31, 53, 94, .08);
}

.auth-page-boundary {
  position: relative;
  min-height: 100vh;
}

.auth-boundary-notice {
  position: fixed;
  z-index: 20;
  top: 18px;
  left: 50%;
  max-width: min(560px, calc(100vw - 32px));
  transform: translateX(-50%);
  padding: 12px 16px;
  border: 1px solid #fecaca;
  border-radius: 12px;
  color: #b91c1c;
  background: #fff1f2;
  box-shadow: 0 10px 24px rgba(127, 29, 29, .15);
}

.page-load-error {
  color: #ef4444;
  background: #fff5f5;
  border-color: #ffd1d1;
  font-weight: 700;
}
</style>
