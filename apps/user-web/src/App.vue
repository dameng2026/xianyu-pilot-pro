<template>
  <div v-if="booting" class="boot-screen">
    <div class="boot-card">
      <img src="/xya/brand/brand_004.png" alt="XianYuAssistant" />
      <b>正在连接后端服务...</b>
      <span>{{ bootMessage }}</span>
    </div>
  </div>

  <div v-else-if="authPages.includes(active)" class="auth-page-boundary">
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
      <Topbar :user="currentUserInfo" :sse-status="displaySseStatus" @logout="handleLogout" @open-profile-center="openProfileCenter" />
      <PageHeader v-if="shouldRenderPageHeader" :title="pageHeaderTitle" :subtitle="pageHeaderSubtitle">
        <div v-if="headerActions.length" class="head-actions">
          <AppButton v-for="action in headerActions" :key="action.text" :type="action.type" @click="onHeaderAction(action)">{{ action.text }}</AppButton>
        </div>
      </PageHeader>
      <div v-if="globalNotice" class="global-notice" :class="globalNotice.type">{{ globalNotice.text }}</div>
      <component :is="pageComponent" :active="active" :user="currentUserInfo" @navigate="navigate" />
    </main>
  </div>
  <ConfirmModal />
</template>

<script setup>
import { computed, defineAsyncComponent, h, onBeforeUnmount, onMounted, ref } from 'vue'
import Sidebar from './components/Sidebar.vue'
import Topbar from './components/Topbar.vue'
import PageHeader from './components/PageHeader.vue'
import AppButton from './components/AppButton.vue'
import ConfirmModal from './components/ConfirmModal.vue'
import MobileLite from './components/MobileLite.vue'
import { pageTitles } from './data/nav.js'
import { createMediaSession, logout as logoutApi } from './api/auth.js'
import { currentUser, invalidateCurrentUserCache } from './api/system.js'
import { clearAuth, getCachedUsername, getToken, isAuthed, setAuth } from './utils/auth.js'
import { confirmAction } from './utils/confirmAction.js'
import { closeSse, connectSse } from './utils/sse.js'
import { installClientErrorReporter, recordClientError } from './utils/errorReporter.js'
import { playIncomingMessageSound, primeAudioOnFirstGesture } from './utils/notifySound.js'
import { warmLiteAccountsList } from './api/accounts.js'

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
const SettingsPage = asyncPage(() => import('./pages/SettingsPage.vue'))

const pageMap = {
  login: LoginPage,
  register: RegisterPage,
  'forgot-password': ForgotPasswordPage,
  dashboard: DashboardPage,
  data: asyncPage(() => import('./pages/DataPage.vue')),
  accounts: asyncPage(() => import('./pages/AccountsPage.vue')),
  connections: asyncPage(() => import('./pages/ConnectionsPage.vue')),
  products: asyncPage(() => import('./pages/ProductsPage.vue')),
  orders: asyncPage(() => import('./pages/OrdersPage.vue')),
  'product-publish': asyncPage(() => import('./pages/ProductPublishPage.vue')),
  opportunities: asyncPage(() => import('./pages/OpportunityPage.vue')),
  messages: asyncPage(() => import('./pages/MessagesPage.vue')),
  'message-center': asyncPage(() => import('./pages/MessagesPage.vue')),
  workflow: asyncPage(() => import('./pages/WorkflowPage.vue')),
  'workflow-tasks': asyncPage(() => import('./pages/WorkflowTasksPage.vue')),
  'card-warehouse': asyncPage(() => import('./pages/CardWarehousePage.vue')),
  'auto-delivery': asyncPage(() => import('./pages/AutoDeliveryPage.vue')),
  'delivery-source-library': asyncPage(() => import('./pages/DeliverySourceLibraryPage.vue')),
  'delivery-statement': asyncPage(() => import('./pages/DeliveryStatementPage.vue')),
  'delivery-templates': asyncPage(() => import('./pages/DeliveryTemplatesPage.vue')),
  'delivery-records': asyncPage(() => import('./pages/DeliveryRecordsPage.vue')),
  'scheduled-tasks': asyncPage(() => import('./pages/ScheduledTasksPage.vue')),
  'auto-reply': asyncPage(() => import('./pages/AutoReplyPage.vue')),
  logs: asyncPage(() => import('./pages/LogsPage.vue')),
  'slider-solve-records': asyncPage(() => import('./pages/SliderSolveRecordsPage.vue')),
  feedback: asyncPage(() => import('./pages/FeedbackPage.vue')),
  'settings-notify': asyncPage(() => import('./pages/settings/NotifySettings.vue')),
  vip: asyncPage(() => import('./pages/VipPage.vue')),
  profile: asyncPage(() => import('./pages/ProfileCenterPage.vue'))
}

const settingsKeys = ['settings-ai-cs', 'settings-product', 'settings-about']
const authPages = ['login', 'register', 'forgot-password']
const defaultPage = 'dashboard'
const profileEntryStorageKey = 'xya_profile_initial_tab'
const pagesWithEmbeddedTitle = new Set(['messages', 'message-center', 'delivery-statement'])
const profileEntryTabs = new Set(['overview', 'security', 'token'])
const mobileLitePages = new Set([
  'dashboard',
  'data',
  'accounts',
  'products',
  'messages',
  'message-center',
  'workflow',
  'profile'
])
const isKnownPage = key => Boolean(pageMap[key]) || settingsKeys.includes(key)
const normalizePageKey = key => isKnownPage(key) ? key : defaultPage
const getHash = () => normalizePageKey((location.hash || `#/${defaultPage}`).replace('#/', '') || defaultPage)
const normalizeProfileEntryTab = key => profileEntryTabs.has(key) ? key : 'overview'

const booting = ref(true)
const bootMessage = ref('正在检查登录状态')
const loggingIn = ref(false)
const authNotice = ref('')
const active = ref(getHash())
const currentUserInfo = ref(buildDefaultUserInfo())
const displaySseStatus = ref('disconnected')
const globalNotice = ref(null)
const isMobile = ref(false)
const mobileDesktopOverride = ref(localStorage.getItem('xya_mobile_desktop_override') === '1')
let noticeTimer = null
let mediaSessionTimer = null

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

function navigate(key) {
  const requested = key || defaultPage
  const next = normalizePageKey(requested)
  if (requested !== next) {
    showNotice('页面不存在，已返回默认页面', 'warn')
  }
  if (!isAuthed() && !authPages.includes(next)) {
    location.hash = '#/login'
    active.value = 'login'
    return
  }
  location.hash = `#/${next}`
  active.value = next
  if (authPages.includes(next)) authNotice.value = ''
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
  const raw = (location.hash || `#/${defaultPage}`).replace('#/', '') || defaultPage
  const next = normalizePageKey(raw)
  if (!isAuthed() && !authPages.includes(next)) {
    navigate('login')
    return
  }
  const previous = active.value
  active.value = next
  if (authPages.includes(next) && next !== previous) authNotice.value = ''
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
    setAuth(token, payload.username)
    await initializeMediaSession()
    currentUserInfo.value = buildDefaultUserInfo(payload?.username || getCachedUsername() || '当前用户')
    startSse()
    scheduleWarmups()
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
    if (getToken()) {
      bootMessage.value = '正在恢复登录会话'
      if (authPages.includes(active.value)) active.value = defaultPage
      await initializeMediaSession()
      startSse()
      scheduleWarmups()
      await loadCurrentUser()
      if (!location.hash || authPages.includes(getHash())) navigate(defaultPage)
      return
    }
    if (!location.hash) {
      navigate('login')
      return
    }

    const requested = getHash()
    if (authPages.includes(requested)) {
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

onMounted(() => {
  installClientErrorReporter()
  updateMobileState()
  window.addEventListener('resize', updateMobileState)
  window.addEventListener('orientationchange', updateMobileState)
  window.addEventListener('hashchange', onHash)
  window.addEventListener('xya-auth-expired', onAuthExpired)
  window.addEventListener('xya-captcha-required', onCaptchaRequired)
  window.addEventListener('xya-sse-event', onSseEventForSound)
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
  import('./composables/useCaptchaSolver.js').then(({ useCaptchaSolver }) => {
    useCaptchaSolver().destroyCaptchaSolverListener()
  })
  closeSse()
})

const pageComponent = computed(() => settingsKeys.includes(active.value) ? SettingsPage : (pageMap[active.value] || DashboardPage))
const title = computed(() => (pageTitles[active.value] || pageTitles.dashboard)[0])
const subtitle = computed(() => (pageTitles[active.value] || pageTitles.dashboard)[1])
const pageHeaderTitle = computed(() => pagesWithEmbeddedTitle.has(active.value) ? '' : title.value)
const pageHeaderSubtitle = computed(() => pagesWithEmbeddedTitle.has(active.value) ? '' : subtitle.value)
const shouldUseMobileLite = computed(() =>
  isMobile.value &&
  !mobileDesktopOverride.value &&
  !authPages.includes(active.value) &&
  mobileLitePages.has(active.value)
)

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
    connections: [
      { text: '批量连接', type: 'primary', event: 'connections-batch-start' },
      { text: '批量断开', type: 'danger', event: 'connections-batch-stop', confirm: { title: '确认批量断开连接？', description: '断开后会暂停接收这些账号的实时消息。' } }
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
