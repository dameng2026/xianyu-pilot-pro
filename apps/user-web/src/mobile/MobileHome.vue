<template>
  <div class="m-home">
    <!-- ============ 顶部问候区 - 极致克制 ============ -->
    <section class="m-home-greeting">
      <div class="m-greeting-row">
        <div class="m-greeting-text">
          <div class="m-greeting-time">{{ greetingTime }}</div>
          <div class="m-greeting-name">{{ userName }}</div>
        </div>
        <button class="m-account-status" :class="accountStateClass" @click="navigate('accounts')">
          <span class="m-account-dot"></span>
          <span class="m-account-text">{{ accountStateText }}</span>
        </button>
      </div>

      <!-- 系统通知 - iOS 18 风格 -->
      <div v-if="topNotification" class="m-notice-banner" @click="navigate('notifications')">
        <div class="m-notice-icon">
          <MIcon name="bell" :size="14" />
        </div>
        <span class="m-notice-text">{{ topNotification.title || topNotification.content || topNotification.message || topNotification.desc || '系统通知' }}</span>
        <MIcon name="chevronRight" :size="12" class="m-notice-arrow" />
      </div>
      <div v-else-if="notificationsLoadError" class="m-notice-banner m-notice-banner--error" @click="loadNotifications">
        <div class="m-notice-icon m-notice-icon--error">
          <MIcon name="alertCircle" :size="14" />
        </div>
        <span class="m-notice-text">通知加载失败，点击重试</span>
      </div>
    </section>

    <!-- ============ 核心数据卡 - iOS 18 精品卡片 ============ -->
    <section class="m-home-section">
      <!-- 今日数据大卡 -->
      <div class="m-card-primary" v-if="!statsLoading">
        <div class="m-card-primary-header">
          <span class="m-card-primary-label">今日订单</span>
          <button class="m-card-refresh" aria-label="刷新" @click="loadAll">
            <MIcon name="refreshCw" :size="13" />
          </button>
        </div>
        <div class="m-card-primary-value-wrap">
          <span class="m-card-primary-value">{{ metricText(stats.todayOrders) }}</span>
          <span class="m-card-primary-unit">单</span>
        </div>
        <div class="m-card-primary-footer">
          <span class="m-card-primary-amount">¥{{ metricText(stats.todaySalesAmount) }}</span>
          <span class="m-card-primary-sep"></span>
          <span class="m-card-primary-sold">累计售出 {{ metricText(stats.totalSold) }}</span>
        </div>
      </div>

      <!-- 加载骨架 -->
      <div v-if="statsLoading" class="m-skeleton-primary">
        <div class="m-skel-bar m-skel-bar--lg"></div>
        <div class="m-skel-bar m-skel-bar--xl"></div>
        <div class="m-skel-bar m-skel-bar--sm"></div>
      </div>

      <!-- 4格数据网格 -->
      <div class="m-stats-quad" v-if="!statsLoading">
        <div class="m-quad-item" @click="navigate('orders')">
          <div class="m-quad-icon m-quad-icon--orange">
            <MIcon name="truck" :size="18" />
          </div>
          <div class="m-quad-value" :class="{ 'is-warn': (stats.pendingDelivery ?? 0) > 0 }">{{ metricText(stats.pendingDelivery) }}</div>
          <div class="m-quad-label">待发货</div>
        </div>
        <div class="m-quad-item" @click="navigate('products')">
          <div class="m-quad-icon m-quad-icon--green">
            <MIcon name="bag" :size="18" />
          </div>
          <div class="m-quad-value">{{ metricText(stats.products) }}</div>
          <div class="m-quad-label">商品</div>
        </div>
        <div class="m-quad-item" @click="navigate('messages')">
          <div class="m-quad-icon m-quad-icon--blue">
            <MIcon name="chat" :size="18" />
          </div>
          <div class="m-quad-value">{{ metricText(stats.messages) }}</div>
          <div class="m-quad-label">消息</div>
        </div>
        <div class="m-quad-item" @click="navigate('accounts')">
          <div class="m-quad-icon m-quad-icon--purple">
            <MIcon name="user" :size="18" />
          </div>
          <div class="m-quad-value">{{ metricText(stats.onlineAccounts) }}<span class="m-quad-value-sub">/{{ metricText(stats.accounts) }}</span></div>
          <div class="m-quad-label">账号在线</div>
        </div>
      </div>

      <MobileUnavailableState
        v-if="statsLoadError"
        compact
        title="部分经营数据暂时不可用"
        :description="statsLoadError"
        @retry="loadStats"
      />
    </section>

    <!-- ============ 快捷入口 - iOS 图标风格 ============ -->
    <section class="m-home-section">
      <div class="m-section-header">
        <span class="m-section-title">快捷功能</span>
      </div>
      <div class="m-quick-grid">
        <button class="m-quick-cell" @click="navigate('products')">
          <div class="m-quick-icon-wrap icon-bg-green">
            <MIcon name="bag" :size="22" />
          </div>
          <span class="m-quick-text">商品管理</span>
        </button>
        <button class="m-quick-cell" @click="navigate('orders')">
          <div class="m-quick-icon-wrap icon-bg-orange">
            <MIcon name="shoppingCart" :size="22" />
          </div>
          <span class="m-quick-text">订单管理</span>
        </button>
        <button class="m-quick-cell" @click="navigate('messages')">
          <div class="m-quick-icon-wrap icon-bg-blue">
            <MIcon name="messageCircle" :size="22" />
          </div>
          <span class="m-quick-text">消息中心</span>
        </button>
        <button class="m-quick-cell" @click="navigate('auto-delivery')">
          <div class="m-quick-icon-wrap icon-bg-purple">
            <MIcon name="send" :size="22" />
          </div>
          <span class="m-quick-text">自动发货</span>
        </button>
        <button class="m-quick-cell" @click="navigate('workflow')">
          <div class="m-quick-icon-wrap icon-bg-indigo">
            <MIcon name="workflow" :size="22" />
          </div>
          <span class="m-quick-text">工作流</span>
        </button>
        <button class="m-quick-cell" @click="navigate('data')">
          <div class="m-quick-icon-wrap icon-bg-teal">
            <MIcon name="pieChart" :size="22" />
          </div>
          <span class="m-quick-text">数据分析</span>
        </button>
        <button class="m-quick-cell" @click="navigate('opportunity')">
          <div class="m-quick-icon-wrap icon-bg-pink">
            <MIcon name="search" :size="22" />
          </div>
          <span class="m-quick-text">商机发掘</span>
        </button>
        <button class="m-quick-cell" @click="navigate('settings')">
          <div class="m-quick-icon-wrap icon-bg-gray">
            <MIcon name="settings" :size="22" />
          </div>
          <span class="m-quick-text">设置</span>
        </button>
      </div>
    </section>

    <!-- ============ 数据趋势 - 精致图表 ============ -->
    <section class="m-home-section">
      <div class="m-section-header">
        <span class="m-section-title">数据趋势</span>
        <div class="m-segmented">
          <button class="m-segmented-btn" :class="{ active: trendTab === 'order' }" @click="trendTab = 'order'">订单</button>
          <button class="m-segmented-btn" :class="{ active: trendTab === 'message' }" @click="trendTab = 'message'">消息</button>
        </div>
      </div>

      <div class="m-card-chart">
        <div v-if="trendLoading" class="m-chart-loading">
          <MIcon name="refreshCw" :size="18" class="m-spin" />
        </div>
        <div v-else-if="trendError" class="m-chart-error" @click="loadTrend">
          <MIcon name="alertCircle" :size="18" />
          <span>加载失败，点击重试</span>
        </div>
        <template v-else>
          <div v-if="trendValues.length" class="m-chart-wrap">
            <div class="m-chart-header">
              <span class="m-chart-total">近7日 {{ trendTab === 'order' ? '订单' : '消息' }} <strong>{{ trendTotal }}</strong></span>
              <span class="m-chart-delta" :class="trendDeltaClass">{{ trendDeltaText }}</span>
            </div>
            <svg class="m-chart-svg" viewBox="0 0 320 100" preserveAspectRatio="none">
              <path :d="trendAreaPath" fill="rgba(13,107,255,0.08)" />
              <path :d="trendLinePath" fill="none" stroke="#0d6bff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="m-chart-line" />
              <circle v-for="(p, i) in trendPoints" :key="i" :cx="p.x" :cy="p.y" r="3" fill="#fff" stroke="#0d6bff" stroke-width="2" class="m-chart-dot" />
            </svg>
          </div>
          <div v-else class="m-chart-empty">
            <MIcon name="barChart" :size="24" />
            <span>暂无趋势数据</span>
          </div>
        </template>
      </div>
    </section>

    <!-- ============ 异常提醒 - iOS 列表风格 ============ -->
    <section v-if="hasAlerts" class="m-home-section">
      <div class="m-section-header">
        <span class="m-section-title">需要注意</span>
        <span class="m-section-badge">{{ alertList.length }}</span>
      </div>
      <div class="m-card-list">
        <div
          v-for="(alert, i) in alertList"
          :key="i"
          class="m-list-item"
          @click="navigate(alert.target)"
        >
          <div class="m-list-icon" :class="`m-list-icon--${alert.level}`">
            <MIcon :name="alert.icon" :size="14" />
          </div>
          <div class="m-list-content">
            <div class="m-list-title">{{ alert.title }}</div>
            <div class="m-list-desc">{{ alert.desc }}</div>
          </div>
          <span v-if="alert.count !== null" class="m-list-count">{{ alert.count }}</span>
          <MIcon name="chevronRight" :size="12" class="m-list-arrow" />
        </div>
      </div>
    </section>

    <!-- ============ 最近动态 - iOS 分组列表 ============ -->
    <section class="m-home-section">
      <div class="m-section-header">
        <span class="m-section-title">最近动态</span>
        <div class="m-segmented">
          <button class="m-segmented-btn" :class="{ active: activityTab === 'events' }" @click="activityTab = 'events'">实时</button>
          <button class="m-segmented-btn" :class="{ active: activityTab === 'logs' }" @click="activityTab = 'logs'">日志</button>
        </div>
      </div>

      <!-- SSE 连接提示 -->
      <div v-if="activityTab === 'events' && sseStatus !== 'connected'" class="m-connection-banner">
        <MIcon name="wifiOff" :size="12" />
        <span>{{ sseStatus === 'connecting' ? '正在连接实时通道…' : '实时连接中断' }}</span>
      </div>

      <div class="m-card-list">
        <!-- 实时事件 -->
        <template v-if="activityTab === 'events'">
          <div v-for="(evt, i) in recentEvents" :key="i" class="m-list-item m-list-item--plain">
            <span class="m-list-dot" :class="eventColorClass(evt)"></span>
            <div class="m-list-content">
              <div class="m-list-text">{{ formatEventText(evt) }}</div>
              <div class="m-list-time">{{ formatEventTime(evt) }}</div>
            </div>
          </div>
          <div v-if="!recentEvents.length" class="m-empty-inline">
            <span>开启自动化后将显示实时动态</span>
          </div>
        </template>

        <!-- 操作日志 -->
        <template v-if="activityTab === 'logs'">
          <div v-if="logsLoading" class="m-list-loading">
            <MIcon name="refreshCw" :size="14" class="m-spin" />
            <span>加载中…</span>
          </div>
          <template v-else>
            <div v-for="log in recentLogs" :key="log.id || log.operationDesc" class="m-list-item m-list-item--plain">
              <span class="m-list-dot m-dot-gray"></span>
              <div class="m-list-content">
                <div class="m-list-text">{{ log.operationDesc || log.operationType || '操作记录' }}</div>
                <div class="m-list-time">{{ formatLogTime(log.createdTime) }}</div>
              </div>
            </div>
            <div v-if="!recentLogs.length && !logsError" class="m-empty-inline">
              <span>暂无操作日志</span>
            </div>
            <div v-if="logsError" class="m-list-error" @click="loadRecentLogs">
              <MIcon name="alertCircle" :size="12" />
              <span>加载失败，点击重试</span>
            </div>
          </template>
        </template>
      </div>
    </section>

    <div class="m-safe-bottom"></div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, useId } from 'vue'
import MIcon from './MIcon.vue'
import MobileUnavailableState from './MobileUnavailableState.vue'
import { getLiteAccounts } from '../api/accounts.js'
import { getDashboardSummary, getDashboardSalesTrend, getDashboardOrderMessageTrend, getDashboardRecentLogs } from '../api/dashboard.js'
import { getNavigationNotifications } from '../api/navigation.js'
import { accountWsConnected } from '../utils/accountAuth.js'
import { getSseStatus } from '../utils/sse.js'
import { getCachedUsername } from '../utils/auth.js'

const emit = defineEmits(['navigate', 'logout', 'force-desktop', 'tab-change'])

function navigate(page) { emit('navigate', page) }

// ===== 状态 =====
const stats = ref({
  accounts: null, onlineAccounts: null, products: null, onSale: null,
  pendingDelivery: null, deliverySuccess: null, deliveryFail: null,
  todayOrders: null, todaySalesAmount: null, totalSold: null,
  messages: null, autoReply: null
})
const statsLoading = ref(true)
const statsLoadError = ref('')

const notifications = ref([])
const notificationsLoadError = ref('')

const trendData = ref(null)
const orderMsgTrend = ref(null)
const trendLoading = ref(true)
const trendError = ref('')
const trendTab = ref('order')

const recentLogs = ref([])
const logsLoading = ref(true)
const logsError = ref('')

const recentEvents = ref([])
const sseStatus = ref(getSseStatus())
const activityTab = ref('events')

const trendGradientId = `m-trend-grad-${useId()}`

// ===== 派生：用户与问候 =====
const userName = computed(() => getCachedUsername() || '店主')

const greetingTime = computed(() => {
  const h = new Date().getHours()
  if (h >= 6 && h <= 11) return '早上好'
  if (h >= 12 && h <= 13) return '中午好'
  if (h >= 14 && h <= 18) return '下午好'
  if (h >= 19 && h <= 23) return '晚上好'
  return '夜深了'
})

// ===== 派生：账号状态 =====
const accountStateClass = computed(() => {
  const total = Number(stats.value.accounts ?? 0)
  const online = Number(stats.value.onlineAccounts ?? 0)
  if (total === 0) return 'is-neutral'
  if (online === 0) return 'is-danger'
  if (online < total) return 'is-warning'
  return 'is-success'
})

const accountStateText = computed(() => {
  const total = Number(stats.value.accounts ?? 0)
  const online = Number(stats.value.onlineAccounts ?? 0)
  if (total === 0) return '未添加账号'
  if (online === 0) return '全部离线'
  if (online < total) return `${online}/${total} 在线`
  return '全部在线'
})

// ===== 派生：异常提醒 =====
const alertList = computed(() => {
  const list = []
  const pending = Number(stats.value.pendingDelivery ?? 0)
  const fail = Number(stats.value.deliveryFail ?? 0)
  const total = Number(stats.value.accounts ?? 0)
  const online = Number(stats.value.onlineAccounts ?? 0)
  const offline = total - online

  if (pending > 0) {
    list.push({ level: 'warning', icon: 'truck', title: '待发货订单', desc: '需尽快处理发货', count: pending, target: 'orders' })
  }
  if (fail > 0) {
    list.push({ level: 'danger', icon: 'alertTriangle', title: '发货失败', desc: '存在失败发货记录', count: fail, target: 'delivery-records' })
  }
  if (total > 0 && offline > 0) {
    list.push({ level: 'danger', icon: 'wifiOff', title: '账号离线', desc: `${offline} 个账号未连接`, count: offline, target: 'accounts' })
  }
  return list
})

const hasAlerts = computed(() => alertList.value.length > 0)

// ===== 派生：顶部通知 =====
const topNotification = computed(() => notifications.value[0] || null)

// ===== 派生：趋势图 =====
const trendValues = computed(() => {
  if (trendTab.value === 'order') {
    return trendData.value?.orderCount || []
  }
  return orderMsgTrend.value?.messageCount || trendData.value?.messageCount || []
})

const trendTotal = computed(() => trendValues.value.reduce((a, b) => a + Number(b || 0), 0))

const trendDeltaText = computed(() => {
  const vals = trendValues.value
  if (vals.length < 2) return '—'
  const recent = Number(vals[vals.length - 1] || 0)
  const prev = Number(vals[vals.length - 2] || 0)
  if (prev === 0) return recent > 0 ? '↑ 上升' : '持平'
  const delta = ((recent - prev) / prev) * 100
  if (delta > 5) return `↑ ${delta.toFixed(0)}%`
  if (delta < -5) return `↓ ${Math.abs(delta).toFixed(0)}%`
  return '持平'
})

const trendDeltaClass = computed(() => {
  const t = trendDeltaText.value
  if (t.startsWith('↑')) return 'is-up'
  if (t.startsWith('↓')) return 'is-down'
  return ''
})

const trendPoints = computed(() => {
  const vals = trendValues.value
  if (!vals.length) return []
  const max = Math.max(...vals, 1)
  const w = 320
  const h = 100
  const padX = 16
  const padY = 12
  const stepX = vals.length > 1 ? (w - padX * 2) / (vals.length - 1) : 0
  return vals.map((v, i) => ({
    x: padX + i * stepX,
    y: padY + (h - padY * 2) * (1 - Number(v || 0) / max)
  }))
})

const trendLinePath = computed(() => {
  const pts = trendPoints.value
  if (!pts.length) return ''
  return pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
})

const trendAreaPath = computed(() => {
  const pts = trendPoints.value
  if (!pts.length) return ''
  const line = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
  const last = pts[pts.length - 1]
  const first = pts[0]
  return `${line} L${last.x.toFixed(1)},88 L${first.x.toFixed(1)},88 Z`
})

// ===== 数据加载 =====
function metricText(value) {
  if (value === null || value === undefined || value === '') return '—'
  return value
}

function num(v) {
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

async function loadStats() {
  statsLoading.value = true
  statsLoadError.value = ''
  const [accRes, dashRes] = await Promise.allSettled([
    getLiteAccounts({ page: 1, pageSize: 100 }),
    getDashboardSummary()
  ])

  const accData = accRes.status === 'fulfilled' ? accRes.value?.data : null
  if (accData && (Array.isArray(accData) || Array.isArray(accData?.records) || Array.isArray(accData?.list))) {
    const list = accData.records || accData.list || (Array.isArray(accData) ? accData : [])
    stats.value.accounts = accData.total ?? list.length
    stats.value.onlineAccounts = list.filter(a => accountWsConnected(a)).length
  } else {
    stats.value.accounts = null
    stats.value.onlineAccounts = null
  }

  const d = dashRes.status === 'fulfilled' ? dashRes.value?.data : null
  if (d && typeof d === 'object') {
    stats.value.products = num(d.goodsCount)
    stats.value.onSale = num(d.sellingGoodsCount)
    stats.value.totalSold = num(d.totalSoldCount)
    stats.value.todayOrders = num(d.todayOrderCount)
    stats.value.todaySalesAmount = formatAmount(d.todaySalesAmount)
    stats.value.pendingDelivery = num(d.pendingDeliveryCount)
    stats.value.deliverySuccess = num(d.deliverySuccessCount)
    stats.value.deliveryFail = num(d.deliveryFailCount)
    stats.value.messages = num(d.messageCount)
    stats.value.autoReply = num(d.autoReplyCount)
  }

  const failed = []
  if (accRes.status !== 'fulfilled') failed.push('账号')
  if (dashRes.status !== 'fulfilled') failed.push('业务概览')
  if (failed.length) {
    statsLoadError.value = `${failed.join('、')}数据加载失败，请重试。`
  }
  statsLoading.value = false
}

function formatAmount(v) {
  if (v === null || v === undefined || v === '') return null
  const n = Number(v)
  if (!Number.isFinite(n)) return null
  return n.toFixed(2)
}

async function loadTrend() {
  trendLoading.value = true
  trendError.value = ''
  const [salesRes, orderMsgRes] = await Promise.allSettled([
    getDashboardSalesTrend({ days: 7 }),
    getDashboardOrderMessageTrend({ days: 7 })
  ])
  if (salesRes.status === 'fulfilled') trendData.value = salesRes.value?.data || null
  if (orderMsgRes.status === 'fulfilled') orderMsgTrend.value = orderMsgRes.value?.data || null
  if (salesRes.status !== 'fulfilled' && orderMsgRes.status !== 'fulfilled') {
    trendError.value = '趋势数据加载失败'
  }
  trendLoading.value = false
}

async function loadNotifications() {
  notificationsLoadError.value = ''
  try {
    const res = await getNavigationNotifications({ limit: 3 })
    const list = res?.data
    notifications.value = Array.isArray(list) ? list : (list?.records || list?.list || [])
  } catch (e) {
    notifications.value = []
    notificationsLoadError.value = e?.message || '通知加载失败'
  }
}

async function loadRecentLogs() {
  logsLoading.value = true
  logsError.value = ''
  try {
    const res = await getDashboardRecentLogs({ limit: 5 })
    const data = res?.data
    recentLogs.value = Array.isArray(data) ? data : (data?.records || data?.list || [])
  } catch (e) {
    recentLogs.value = []
    logsError.value = e?.message || '日志加载失败'
  }
  logsLoading.value = false
}

async function loadAll() {
  await Promise.allSettled([loadStats(), loadTrend(), loadNotifications(), loadRecentLogs()])
}

// ===== SSE 实时事件 =====
function onSseEvent(event) {
  const detail = event?.detail || {}
  if (!detail.type && !detail.eventType) return
  recentEvents.value.unshift({
    type: detail.type || detail.eventType,
    direction: detail.direction,
    message: detail.message || detail.content || detail.text,
    time: new Date()
  })
  if (recentEvents.value.length > 8) recentEvents.value.length = 8
}

function onSseStatus(event) {
  sseStatus.value = String(event?.detail || 'disconnected')
}

function formatEventText(evt) {
  if (evt.message) return evt.message
  const t = evt.type || ''
  const dir = String(evt.direction || '').toUpperCase()
  if (t === 'message' && dir !== 'OUT') return '收到新消息'
  if (t === 'message' && dir === 'OUT') return '消息已发送'
  if (t.includes('cookie')) return 'Cookie 状态已更新'
  if (t.includes('account')) return '账号状态变更'
  if (t.includes('delivery')) return '自动发货通知'
  if (t.includes('workflow')) return '工作流执行通知'
  return t || '系统通知'
}

function formatEventTime(evt) {
  const d = evt.time instanceof Date ? evt.time : new Date(evt.time)
  const now = new Date()
  const diff = (now - d) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

function formatLogTime(t) {
  if (!t) return ''
  const d = new Date(t)
  if (isNaN(d.getTime())) return String(t).replace('T', ' ').slice(0, 16)
  const now = new Date()
  const diff = (now - d) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  if (diff < 86400) return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
  return `${d.getMonth() + 1}/${d.getDate()}`
}

function eventColorClass(evt) {
  const t = evt.type || ''
  if (t === 'message') return 'm-dot-blue'
  if (t.includes('error') || t.includes('fail')) return 'm-dot-red'
  if (t.includes('success') || t.includes('delivery')) return 'm-dot-green'
  return 'm-dot-gray'
}

onMounted(() => {
  loadStats()
  loadTrend()
  loadNotifications()
  loadRecentLogs()
  window.addEventListener('xya-sse-event', onSseEvent)
  window.addEventListener('xya-sse-status', onSseStatus)
})

onBeforeUnmount(() => {
  window.removeEventListener('xya-sse-event', onSseEvent)
  window.removeEventListener('xya-sse-status', onSseStatus)
})
</script>

<style scoped>
@import './tokens.css';

.m-home {
  padding: 0;
  width: 100%;
  background: #f5f7fa;
  min-height: 100vh;
  animation: mPageEnter 0.25s ease-out;
}

@keyframes mPageEnter {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

/* ============ 顶部问候区 - PC版设计系统 ============ */
.m-home-greeting {
  padding: calc(var(--m-safe-area-top) + 16px) 20px 16px;
  background: transparent;
}

.m-greeting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.m-greeting-text {
  flex: 1;
  min-width: 0;
}

.m-greeting-time {
  font-size: 13px;
  color: #72809a;
  font-weight: 400;
}

.m-greeting-name {
  font-size: 22px;
  font-weight: 600;
  color: #15213d;
  line-height: 1.3;
  margin-top: 4px;
}

.m-account-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
  border: none;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.15s ease;
}

.m-account-status:active {
  background: #f0f5ff !important;
}

.m-account-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.m-account-status.is-success {
  background: #e9fbf3;
  color: #16bf78;
}
.m-account-status.is-success .m-account-dot {
  background: #16bf78;
}

.m-account-status.is-warning {
  background: #fff5e6;
  color: #ff9f22;
}
.m-account-status.is-warning .m-account-dot {
  background: #ff9f22;
}

.m-account-status.is-danger {
  background: #fff0f1;
  color: #ff5b61;
}
.m-account-status.is-danger .m-account-dot {
  background: #ff5b61;
}

.m-account-status.is-neutral {
  background: #f4f7fc;
  color: #72809a;
}
.m-account-status.is-neutral .m-account-dot {
  background: #c4ccd9;
}

.m-notice-banner {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  background: #edf5ff;
  border-radius: 10px;
  color: #0d6bff;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}

.m-notice-banner:active {
  background: #f0f5ff;
}

.m-notice-banner--error {
  background: #fff0f1;
  color: #ff5b61;
}

.m-notice-banner--error:active {
  background: #f0f5ff;
}

.m-notice-icon {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: rgba(13, 107, 255, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.m-notice-icon--error {
  background: rgba(255, 91, 97, 0.12);
}

.m-notice-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.m-notice-arrow {
  opacity: 0.6;
  flex-shrink: 0;
}

/* ============ 区块通用 ============ */
.m-home-section {
  margin-bottom: 20px;
  padding: 0 20px;
}

.m-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  gap: 8px;
}

.m-section-title {
  font-size: 16px;
  font-weight: 600;
  color: #15213d;
}

.m-section-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 10px;
  background: #ff5b61;
  color: #fff;
  font-size: 12px;
  font-weight: 500;
}

/* 分段控制器 - PC版风格 */
.m-segmented {
  display: flex;
  gap: 0;
  background: #f4f7fc;
  padding: 3px;
  border-radius: 8px;
}

.m-segmented-btn {
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 13px;
  color: #72809a;
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all 0.2s ease;
  font-weight: 500;
  font-family: inherit;
}

.m-segmented-btn.active {
  background: #fff;
  color: #15213d;
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(31, 53, 94, 0.08), 0 1px 2px rgba(31, 53, 94, 0.06);
}

.m-segmented-btn:active:not(.active) {
  background: #f0f5ff;
}

/* ============ 主数据卡 - PC版风格 ============ */
.m-card-primary {
  background: #ffffff;
  border-radius: 14px;
  padding: 20px;
  border: 1px solid #e7edf7;
  box-shadow: 0 1px 2px rgba(31, 53, 94, 0.04), 0 8px 24px rgba(31, 53, 94, 0.06);
  margin-bottom: 12px;
  transition: all 0.15s ease;
}

.m-card-primary-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.m-card-primary-label {
  font-size: 14px;
  color: #72809a;
  font-weight: 500;
}

.m-card-refresh {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: none;
  background: #f4f7fc;
  color: #72809a;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.15s ease;
}

.m-card-refresh:active {
  background: #f0f5ff;
}

.m-card-primary-value-wrap {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.m-card-primary-value {
  font-size: 38px;
  font-weight: 700;
  color: #15213d;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.m-card-primary-unit {
  font-size: 16px;
  color: #72809a;
  font-weight: 500;
}

.m-card-primary-footer {
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: #72809a;
}

.m-card-primary-amount {
  color: #16bf78;
  font-weight: 600;
}

.m-card-primary-sep {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: #c4ccd9;
}

.m-card-primary-sold {
  font-weight: 400;
}

/* 骨架屏 */
.m-skeleton-primary {
  background: #ffffff;
  border-radius: 14px;
  padding: 20px;
  border: 1px solid #e7edf7;
  box-shadow: 0 1px 2px rgba(31, 53, 94, 0.04), 0 8px 24px rgba(31, 53, 94, 0.06);
  margin-bottom: 12px;
}

.m-skel-bar {
  background: #f4f7fc;
  background: linear-gradient(90deg, #f4f7fc 25%, #edf2f9 50%, #f4f7fc 75%);
  background-size: 200% 100%;
  animation: m-skel 1.4s ease infinite;
  border-radius: 6px;
}

.m-skel-bar--lg {
  height: 14px;
  width: 80px;
  margin-bottom: 16px;
}

.m-skel-bar--xl {
  height: 38px;
  width: 140px;
  margin-bottom: 16px;
}

.m-skel-bar--sm {
  height: 14px;
  width: 180px;
}

@keyframes m-skel {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* ============ 4格数据网格 - PC版风格 ============ */
.m-stats-quad {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.m-quad-item {
  background: #ffffff;
  border-radius: 14px;
  padding: 16px 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  transition: all 0.15s ease;
  border: 1px solid #e7edf7;
  box-shadow: 0 1px 2px rgba(31, 53, 94, 0.04), 0 8px 24px rgba(31, 53, 94, 0.06);
}

.m-quad-item:active {
  background: #f0f5ff;
}

.m-quad-icon {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.m-quad-icon--orange { background: #fff5e6; color: #ff9f22; }
.m-quad-icon--green { background: #e9fbf3; color: #16bf78; }
.m-quad-icon--blue { background: #edf5ff; color: #0d6bff; }
.m-quad-icon--purple { background: #f4efff; color: #8b5cf6; }

.m-quad-value {
  font-size: 20px;
  font-weight: 700;
  color: #15213d;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.m-quad-value.is-warn {
  color: #ff9f22;
}

.m-quad-value-sub {
  font-size: 12px;
  color: #72809a;
  font-weight: 500;
}

.m-quad-label {
  font-size: 12px;
  color: #72809a;
  font-weight: 500;
  text-align: center;
}

/* ============ 快捷入口 - PC版风格 ============ */
.m-quick-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.m-quick-cell {
  background: #ffffff;
  border: 1px solid #e7edf7;
  border-radius: 14px;
  padding: 14px 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  transition: all 0.15s ease;
  font: inherit;
  box-shadow: 0 1px 2px rgba(31, 53, 94, 0.04), 0 8px 24px rgba(31, 53, 94, 0.06);
}

.m-quick-cell:active {
  background: #f0f5ff;
}

.m-quick-icon-wrap {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.icon-bg-green { background: #e9fbf3; color: #16bf78; }
.icon-bg-orange { background: #fff5e6; color: #ff9f22; }
.icon-bg-blue { background: #edf5ff; color: #0d6bff; }
.icon-bg-purple { background: #f4efff; color: #8b5cf6; }
.icon-bg-indigo { background: #edf5ff; color: #0d6bff; }
.icon-bg-teal { background: #eafcff; color: #11b5d8; }
.icon-bg-pink { background: #fff0f1; color: #ff5b61; }
.icon-bg-gray { background: #f4f7fc; color: #72809a; }

.m-quick-text {
  font-size: 13px;
  color: #15213d;
  text-align: center;
  line-height: 1.3;
  font-weight: 500;
}

/* ============ 趋势图表卡 - PC版风格 ============ */
.m-card-chart {
  background: #ffffff;
  border-radius: 14px;
  padding: 20px;
  border: 1px solid #e7edf7;
  box-shadow: 0 1px 2px rgba(31, 53, 94, 0.04), 0 8px 24px rgba(31, 53, 94, 0.06);
}

.m-chart-loading,
.m-chart-error {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 120px;
  color: #72809a;
  font-size: 14px;
}

.m-chart-error {
  cursor: pointer;
  color: #ff5b61;
}

.m-chart-error:active {
  background: #f0f5ff;
}

.m-chart-wrap {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.m-chart-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 14px;
  color: #72809a;
  font-weight: 500;
}

.m-chart-total strong {
  color: #15213d;
  font-weight: 700;
  font-size: 18px;
  margin-left: 6px;
}

.m-chart-delta {
  font-weight: 600;
}

.m-chart-delta.is-up {
  color: #16bf78;
}

.m-chart-delta.is-down {
  color: #ff5b61;
}

.m-chart-svg {
  width: 100%;
  height: 100px;
  display: block;
}

.m-chart-svg path:first-child {
  fill: rgba(13, 107, 255, 0.08) !important;
}

.m-chart-line {
  stroke: #0d6bff !important;
  filter: none;
}

.m-chart-dot {
  transition: all 0.15s ease;
  stroke: #0d6bff !important;
}

.m-chart-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 120px;
  color: #c4ccd9;
  font-size: 14px;
}

/* ============ 列表卡 - PC版风格 ============ */
.m-card-list {
  background: #ffffff;
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid #e7edf7;
  box-shadow: 0 1px 2px rgba(31, 53, 94, 0.04), 0 8px 24px rgba(31, 53, 94, 0.06);
}

.m-list-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  cursor: pointer;
  transition: all 0.15s ease;
  position: relative;
}

.m-list-item:active {
  background: #f0f5ff;
}

.m-list-item:not(:last-child)::after {
  content: '';
  position: absolute;
  left: 60px;
  right: 0;
  bottom: 0;
  height: 1px;
  background: #eef2f8;
}

.m-list-item--plain:not(:last-child)::after {
  left: 36px;
}

.m-list-icon {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.m-list-icon--warning {
  background: #fff5e6;
  color: #ff9f22;
}

.m-list-icon--danger {
  background: #fff0f1;
  color: #ff5b61;
}

.m-list-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin: 8px 0;
  flex-shrink: 0;
}

.m-dot-blue { background: #0d6bff; }
.m-dot-red { background: #ff5b61; }
.m-dot-green { background: #16bf78; }
.m-dot-gray { background: #c4ccd9; }

.m-list-content {
  flex: 1;
  min-width: 0;
}

.m-list-title {
  font-size: 14px;
  font-weight: 500;
  color: #15213d;
}

.m-list-desc {
  margin-top: 4px;
  font-size: 12px;
  color: #72809a;
}

.m-list-text {
  font-size: 14px;
  color: #15213d;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
}

.m-list-time {
  margin-top: 4px;
  font-size: 12px;
  color: #72809a;
}

.m-list-count {
  font-size: 18px;
  font-weight: 700;
  color: #15213d;
  flex-shrink: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

.m-list-arrow {
  color: #c4ccd9;
  flex-shrink: 0;
  margin-left: 4px;
}

.m-list-loading,
.m-list-error {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 20px;
  color: #72809a;
  font-size: 14px;
}

.m-list-error {
  cursor: pointer;
  color: #ff5b61;
}

.m-list-error:active {
  background: #f0f5ff;
}

.m-empty-inline {
  padding: 20px;
  text-align: center;
  color: #72809a;
  font-size: 14px;
}

/* ============ 连接提示横幅 ============ */
.m-connection-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  margin-bottom: 12px;
  background: #fff5e6;
  color: #ff9f22;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 500;
}

.m-spin {
  animation: m-spin 1s linear infinite;
}

@keyframes m-spin {
  to { transform: rotate(360deg); }
}

.m-safe-bottom {
  height: 96px;
}

/* ============ 小屏适配 ============ */
@media (max-width: 360px) {
  .m-quick-grid {
    gap: 8px;
  }

  .m-quick-icon-wrap {
    width: 44px;
    height: 44px;
  }

  .m-card-primary-value {
    font-size: 32px;
  }

  .m-stats-quad {
    gap: 8px;
  }

  .m-quad-icon {
    width: 36px;
    height: 36px;
  }
}
</style>
