<template>
  <div class="m-home">
    <!-- ============ 顶部：用户信息 + 账号状态 + 系统通知 ============ -->
    <section class="m-home-hero">
      <div class="m-hero-user">
        <div class="m-hero-avatar">
          <MIcon name="user" :size="22" />
        </div>
        <div class="m-hero-userinfo">
          <div class="m-hero-username">{{ userName }}</div>
          <div class="m-hero-greet">{{ greetingTime }}，祝你生意兴隆</div>
        </div>
        <div class="m-hero-account" :class="accountStateClass" @click="navigate('accounts')">
          <span class="m-hero-account-dot"></span>
          <span class="m-hero-account-text">{{ accountStateText }}</span>
        </div>
      </div>

      <!-- 系统通知横幅 -->
      <div v-if="topNotification" class="m-hero-notice" @click="navigate('notifications')">
        <MIcon name="megaphone" :size="14" />
        <span class="m-hero-notice-text">{{ topNotification.title || topNotification.content || topNotification.message || topNotification.desc || '系统通知' }}</span>
        <MIcon name="chevronRight" :size="14" class="m-hero-notice-arrow" />
      </div>
      <div v-else-if="notificationsLoadError" class="m-hero-notice m-hero-notice--err" @click="loadNotifications">
        <MIcon name="alertCircle" :size="14" />
        <span class="m-hero-notice-text">通知加载失败，点击重试</span>
      </div>
    </section>

    <!-- ============ 核心区：店铺经营状态 ============ -->
    <section class="m-home-section">
      <div class="m-section-header">
        <div class="m-section-title">店铺经营状态</div>
        <button v-if="!statsLoading" class="m-section-refresh" aria-label="刷新" @click="loadAll">
          <MIcon name="refreshCw" :size="14" />
        </button>
      </div>

      <!-- 加载骨架 -->
      <div v-if="statsLoading" class="m-stats-skeleton">
        <div class="m-skel-card"></div>
        <div class="m-skel-card"></div>
      </div>

      <template v-else>
        <!-- 经营概览大卡 -->
        <div class="m-stats-board">
          <div class="m-stats-main">
            <div class="m-stats-label">今日订单</div>
            <div class="m-stats-value">{{ metricText(stats.todayOrders) }}</div>
            <div class="m-stats-sub">
              <span class="m-stats-amount">¥{{ metricText(stats.todaySalesAmount) }}</span>
              <span class="m-stats-sep">·</span>
              <span>累计售出 {{ metricText(stats.totalSold) }}</span>
            </div>
          </div>
          <div class="m-stats-divider"></div>
          <div class="m-stats-side" @click="navigate('auto-delivery')">
            <div class="m-stats-label">自动化</div>
            <div class="m-stats-side-value" :class="automationValueClass">{{ automationStatusText }}</div>
            <div class="m-stats-sub">今日执行 {{ metricText(stats.deliverySuccess) }} 次</div>
          </div>
        </div>

        <!-- 2×2 经营指标网格 -->
        <div class="m-stats-grid">
          <div class="m-stat-cell" @click="navigate('auto-delivery')">
            <div class="m-stat-cell-icon m-stat-cell-icon--warning">
              <MIcon name="truck" :size="16" />
            </div>
            <div class="m-stat-cell-body">
              <div class="m-stat-cell-label">待处理任务</div>
              <div class="m-stat-cell-value" :class="{ 'is-warn': (stats.pendingDelivery ?? 0) > 0 }">{{ metricText(stats.pendingDelivery) }}</div>
              <div class="m-stat-cell-desc">待发货订单</div>
            </div>
          </div>

          <div class="m-stat-cell" @click="navigate('products')">
            <div class="m-stat-cell-icon m-stat-cell-icon--success">
              <MIcon name="bag" :size="16" />
            </div>
            <div class="m-stat-cell-body">
              <div class="m-stat-cell-label">商品数量</div>
              <div class="m-stat-cell-value">{{ metricText(stats.products) }}</div>
              <div class="m-stat-cell-desc">在售 {{ metricText(stats.onSale) }}</div>
            </div>
          </div>

          <div class="m-stat-cell" @click="navigate('messages')">
            <div class="m-stat-cell-icon m-stat-cell-icon--info">
              <MIcon name="chat" :size="16" />
            </div>
            <div class="m-stat-cell-body">
              <div class="m-stat-cell-label">消息数量</div>
              <div class="m-stat-cell-value">{{ metricText(stats.messages) }}</div>
              <div class="m-stat-cell-desc">自动回复 {{ metricText(stats.autoReply) }}</div>
            </div>
          </div>

          <div class="m-stat-cell" @click="navigate('accounts')">
            <div class="m-stat-cell-icon m-stat-cell-icon--primary">
              <MIcon name="users" :size="16" />
            </div>
            <div class="m-stat-cell-body">
              <div class="m-stat-cell-label">账号状态</div>
              <div class="m-stat-cell-value">{{ metricText(stats.onlineAccounts) }}/{{ metricText(stats.accounts) }}</div>
              <div class="m-stat-cell-desc">在线/总数</div>
            </div>
          </div>
        </div>

        <MobileUnavailableState
          v-if="statsLoadError"
          compact
          title="部分经营数据暂时不可用"
          :description="statsLoadError"
          @retry="loadStats"
        />
      </template>
    </section>

    <!-- ============ 快捷入口 ============ -->
    <section class="m-home-section">
      <div class="m-section-header">
        <div class="m-section-title">快捷入口</div>
      </div>
      <div class="m-quick-grid">
        <button class="m-quick-item" @click="navigate('products')">
          <div class="m-quick-icon m-quick-icon--green"><MIcon name="bag" :size="20" /></div>
          <span class="m-quick-label">商品管理</span>
        </button>
        <button class="m-quick-item" @click="navigate('orders')">
          <div class="m-quick-icon m-quick-icon--orange"><MIcon name="shoppingCart" :size="20" /></div>
          <span class="m-quick-label">订单管理</span>
        </button>
        <button class="m-quick-item" @click="navigate('messages')">
          <div class="m-quick-icon m-quick-icon--blue"><MIcon name="messageCircle" :size="20" /></div>
          <span class="m-quick-label">消息中心</span>
        </button>
        <button class="m-quick-item" @click="navigate('workflow')">
          <div class="m-quick-icon m-quick-icon--purple"><MIcon name="workflow" :size="20" /></div>
          <span class="m-quick-label">自动化</span>
        </button>
        <button class="m-quick-item" @click="navigate('data')">
          <div class="m-quick-icon m-quick-icon--cyan"><MIcon name="pieChart" :size="20" /></div>
          <span class="m-quick-label">数据分析</span>
        </button>
      </div>
    </section>

    <!-- ============ 运营区：数据趋势 ============ -->
    <section class="m-home-section">
      <div class="m-section-header">
        <div class="m-section-title">数据趋势</div>
        <div class="m-section-tabs">
          <span class="m-tab-pill" :class="{ active: trendTab === 'order' }" @click="trendTab = 'order'">订单</span>
          <span class="m-tab-pill" :class="{ active: trendTab === 'message' }" @click="trendTab = 'message'">消息</span>
        </div>
      </div>

      <div class="m-trend-card">
        <div v-if="trendLoading" class="m-trend-loading">
          <MIcon name="refreshCw" :size="20" class="m-spin" />
          <span>趋势加载中…</span>
        </div>
        <div v-else-if="trendError" class="m-trend-error" @click="loadTrend">
          <MIcon name="alertCircle" :size="20" />
          <span>趋势加载失败，点击重试</span>
        </div>
        <template v-else>
          <div v-if="trendValues.length" class="m-trend-svg-wrap">
            <svg class="m-trend-svg" viewBox="0 0 320 120" preserveAspectRatio="none">
              <defs>
                <linearGradient :id="trendGradientId" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="currentColor" stop-opacity="0.28" />
                  <stop offset="100%" stop-color="currentColor" stop-opacity="0" />
                </linearGradient>
              </defs>
              <path :d="trendAreaPath" :fill="`url(#${trendGradientId})`" />
              <path :d="trendLinePath" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
              <circle v-for="(p, i) in trendPoints" :key="i" :cx="p.x" :cy="p.y" r="2.5" fill="currentColor" />
            </svg>
            <div class="m-trend-summary">
              <span class="m-trend-current">近7日 {{ trendTab === 'order' ? '订单' : '消息' }} {{ trendTotal }}</span>
              <span class="m-trend-trend" :class="trendDeltaClass">{{ trendDeltaText }}</span>
            </div>
          </div>
          <MEmpty v-else inline icon="chart" title="暂无趋势数据" />
        </template>
      </div>
    </section>

    <!-- ============ 运营区：异常提醒 ============ -->
    <section v-if="hasAlerts" class="m-home-section">
      <div class="m-section-header">
        <div class="m-section-title">异常提醒</div>
        <span class="m-section-count">{{ alertList.length }}</span>
      </div>
      <div class="m-alert-list">
        <div
          v-for="(alert, i) in alertList"
          :key="i"
          class="m-alert-row"
          :class="`m-alert-row--${alert.level}`"
          @click="navigate(alert.target)"
        >
          <div class="m-alert-row-icon"><MIcon :name="alert.icon" :size="16" /></div>
          <div class="m-alert-row-body">
            <div class="m-alert-row-title">{{ alert.title }}</div>
            <div class="m-alert-row-desc">{{ alert.desc }}</div>
          </div>
          <div v-if="alert.count !== null" class="m-alert-row-count">{{ alert.count }}</div>
          <MIcon name="chevronRight" :size="14" class="m-alert-row-arrow" />
        </div>
      </div>
    </section>

    <!-- ============ 运营区：最近动态 ============ -->
    <section class="m-home-section">
      <div class="m-section-header">
        <div class="m-section-title">最近动态</div>
        <div class="m-section-tabs">
          <span class="m-tab-pill" :class="{ active: activityTab === 'events' }" @click="activityTab = 'events'">事件</span>
          <span class="m-tab-pill" :class="{ active: activityTab === 'logs' }" @click="activityTab = 'logs'">操作日志</span>
        </div>
      </div>

      <!-- 实时事件 -->
      <div v-if="activityTab === 'events'">
        <div v-if="sseStatus !== 'connected'" class="m-sse-banner">
          <MIcon name="wifiOff" :size="14" />
          <span>{{ sseStatus === 'connecting' ? '正在连接实时通道…' : '实时连接中断，展示可能延迟' }}</span>
        </div>
        <div v-if="recentEvents.length" class="m-activity-list">
          <div v-for="(evt, i) in recentEvents" :key="i" class="m-activity-item">
            <span class="m-activity-dot" :class="eventColorClass(evt)"></span>
            <div class="m-activity-content">
              <div class="m-activity-text">{{ formatEventText(evt) }}</div>
              <div class="m-activity-time">{{ formatEventTime(evt) }}</div>
            </div>
          </div>
        </div>
        <MEmpty v-else inline icon="activity" title="暂无实时事件" desc="开启自动化后将在此显示实时动态" />
      </div>

      <!-- 操作日志 -->
      <div v-if="activityTab === 'logs'">
        <div v-if="logsLoading" class="m-activity-loading">
          <MIcon name="refreshCw" :size="16" class="m-spin" />
          <span>加载中…</span>
        </div>
        <div v-else-if="recentLogs.length" class="m-activity-list">
          <div v-for="log in recentLogs" :key="log.id || log.operationDesc" class="m-activity-item">
            <span class="m-activity-dot m-dot-gray"></span>
            <div class="m-activity-content">
              <div class="m-activity-text">{{ log.operationDesc || log.operationType || '操作记录' }}</div>
              <div class="m-activity-time">{{ formatLogTime(log.createdTime) }}</div>
            </div>
          </div>
        </div>
        <MEmpty v-else-if="!logsError" inline icon="fileText" title="暂无操作日志" />
        <div v-if="logsError" class="m-activity-error" @click="loadRecentLogs">
          <MIcon name="alertCircle" :size="14" />
          <span>日志加载失败，点击重试</span>
        </div>
      </div>
    </section>

    <div class="m-safe-bottom"></div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, useId } from 'vue'
import MIcon from './MIcon.vue'
import MobileUnavailableState from './MobileUnavailableState.vue'
import MEmpty from './components/MEmpty.vue'
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

const trendData = ref(null)        // 销售趋势
const orderMsgTrend = ref(null)    // 订单消息趋势
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
  if (total === 0) return 'm-hero-account--neutral'
  if (online === 0) return 'm-hero-account--danger'
  if (online < total) return 'm-hero-account--warning'
  return 'm-hero-account--success'
})

const accountStateText = computed(() => {
  const total = Number(stats.value.accounts ?? 0)
  const online = Number(stats.value.onlineAccounts ?? 0)
  if (total === 0) return '未添加账号'
  if (online === 0) return '账号全部离线'
  if (online < total) return `${online}/${total} 在线`
  return '账号全部在线'
})

// ===== 派生：自动化 =====
const automationStatusText = computed(() => {
  const success = Number(stats.value.deliverySuccess ?? 0)
  const autoReply = Number(stats.value.autoReply ?? 0)
  if (success > 0 || autoReply > 0) return '运行中'
  return '暂无执行'
})

const automationValueClass = computed(() => {
  const success = Number(stats.value.deliverySuccess ?? 0)
  const autoReply = Number(stats.value.autoReply ?? 0)
  return (success > 0 || autoReply > 0) ? 'is-success' : 'is-neutral'
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
    list.push({ level: 'danger', icon: 'alertTriangle', title: '发货失败', desc: '存在失败发货记录，请关注', count: fail, target: 'delivery-records' })
  }
  if (total > 0 && offline > 0) {
    list.push({ level: 'danger', icon: 'wifiOff', title: '账号离线', desc: `${offline} 个账号未连接实时通道`, count: offline, target: 'accounts' })
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
  // 消息趋势：优先用 order-message-trend 接口的 messageCount，回退到 sales-trend 的 messageCount
  return orderMsgTrend.value?.messageCount || trendData.value?.messageCount || []
})

const trendTotal = computed(() => trendValues.value.reduce((a, b) => a + Number(b || 0), 0))

const trendDeltaText = computed(() => {
  const vals = trendValues.value
  if (vals.length < 2) return '—'
  const recent = Number(vals[vals.length - 1] || 0)
  const prev = Number(vals[vals.length - 2] || 0)
  if (prev === 0) return recent > 0 ? '最新上升' : '持平'
  const delta = ((recent - prev) / prev) * 100
  if (delta > 5) return `↑ ${delta.toFixed(0)}%`
  if (delta < -5) return `↓ ${Math.abs(delta).toFixed(0)}%`
  return '基本持平'
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
  const h = 120
  const padX = 12
  const padY = 16
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
  return `${line} L${last.x.toFixed(1)},104 L${first.x.toFixed(1)},104 Z`
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

  // 账号
  const accData = accRes.status === 'fulfilled' ? accRes.value?.data : null
  if (accData && (Array.isArray(accData) || Array.isArray(accData?.records) || Array.isArray(accData?.list))) {
    const list = accData.records || accData.list || (Array.isArray(accData) ? accData : [])
    stats.value.accounts = accData.total ?? list.length
    stats.value.onlineAccounts = list.filter(a => accountWsConnected(a)).length
  } else {
    stats.value.accounts = null
    stats.value.onlineAccounts = null
  }

  // 概览
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
.m-home {
  padding: var(--m-space-4);
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
}

/* ============ 顶部用户卡 ============ */
.m-home-hero {
  margin-bottom: var(--m-space-4);
}
.m-hero-user {
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
}
.m-hero-avatar {
  width: 44px;
  height: 44px;
  border-radius: var(--m-radius-circle);
  background: linear-gradient(135deg, #3380ff, #2580ff);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(51, 128, 255, 0.25);
}
.m-hero-userinfo {
  flex: 1;
  min-width: 0;
}
.m-hero-username {
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
  line-height: var(--m-line-height-tight);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-hero-greet {
  margin-top: 2px;
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-secondary);
}
.m-hero-account {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: var(--m-radius-pill);
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  flex-shrink: 0;
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
}
.m-hero-account-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--m-radius-circle);
  background: var(--m-color-text-tertiary);
}
.m-hero-account--success { background: var(--m-color-success-bg); color: var(--m-color-success-text); }
.m-hero-account--success .m-hero-account-dot { background: var(--m-color-success); }
.m-hero-account--warning { background: var(--m-color-warning-bg); color: var(--m-color-warning-text); }
.m-hero-account--warning .m-hero-account-dot { background: var(--m-color-warning); }
.m-hero-account--danger { background: var(--m-color-danger-bg); color: var(--m-color-danger-text); }
.m-hero-account--danger .m-hero-account-dot { background: var(--m-color-danger); }
.m-hero-account--neutral { background: var(--m-color-bg-subtle); color: var(--m-color-text-tertiary); }

.m-hero-notice {
  margin-top: var(--m-space-3);
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  padding: 10px var(--m-space-3);
  background: var(--m-color-primary-bg);
  border-radius: var(--m-radius-lg);
  color: var(--m-color-primary);
  font-size: var(--m-font-size-caption);
  cursor: pointer;
}
.m-hero-notice--err {
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger-text);
}
.m-hero-notice-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-hero-notice-arrow { flex-shrink: 0; opacity: 0.6; }

/* ============ 区块通用 ============ */
.m-home-section {
  margin-bottom: var(--m-space-4);
}
.m-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--m-space-3);
  gap: var(--m-space-2);
}
.m-section-title {
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
}
.m-section-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: var(--m-radius-pill);
  background: var(--m-color-danger);
  color: #fff;
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-bold);
}
.m-section-refresh {
  width: 28px;
  height: 28px;
  border-radius: var(--m-radius-md);
  border: none;
  background: var(--m-color-bg-card);
  color: var(--m-color-text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: var(--m-shadow-card);
}
.m-section-refresh:active { background: var(--m-color-bg-subtle); }
.m-section-tabs {
  display: flex;
  gap: var(--m-space-1);
}
.m-tab-pill {
  padding: 4px var(--m-space-3);
  border-radius: var(--m-radius-pill);
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  background: var(--m-color-bg-subtle);
  cursor: pointer;
  transition: all 0.15s;
}
.m-tab-pill.active {
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
  font-weight: var(--m-font-weight-semibold);
}

/* ============ 经营状态大卡 ============ */
.m-stats-board {
  background: linear-gradient(135deg, #3380ff 0%, #2563eb 100%);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-4);
  display: flex;
  align-items: stretch;
  gap: var(--m-space-3);
  color: #fff;
  box-shadow: 0 8px 24px rgba(51, 128, 255, 0.25);
  margin-bottom: var(--m-space-3);
}
.m-stats-main {
  flex: 1;
  min-width: 0;
}
.m-stats-side {
  flex: 0 0 auto;
  text-align: right;
  cursor: pointer;
  min-width: 84px;
}
.m-stats-divider {
  width: 1px;
  background: rgba(255, 255, 255, 0.25);
}
.m-stats-label {
  font-size: var(--m-font-size-caption);
  opacity: 0.85;
  margin-bottom: var(--m-space-1);
}
.m-stats-value {
  font-size: 32px;
  font-weight: var(--m-font-weight-extrabold);
  line-height: 1;
}
.m-stats-side-value {
  font-size: var(--m-font-size-h1);
  font-weight: var(--m-font-weight-bold);
  line-height: 1;
}
.m-stats-side-value.is-success { color: #fff; }
.m-stats-side-value.is-neutral { opacity: 0.7; }
.m-stats-sub {
  margin-top: var(--m-space-2);
  font-size: var(--m-font-size-tiny);
  opacity: 0.85;
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}
.m-stats-amount { font-weight: var(--m-font-weight-semibold); }
.m-stats-sep { opacity: 0.5; }

/* ============ 经营指标网格 ============ */
.m-stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--m-space-3);
}
.m-stat-cell {
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3);
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
  cursor: pointer;
  transition: transform 0.15s;
  box-shadow: var(--m-shadow-card);
}
.m-stat-cell:active { transform: scale(0.98); }
.m-stat-cell-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--m-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-stat-cell-icon--warning { background: var(--m-color-warning-bg); color: var(--m-color-warning); }
.m-stat-cell-icon--success { background: var(--m-color-success-bg); color: var(--m-color-success); }
.m-stat-cell-icon--info { background: var(--m-color-info-bg); color: var(--m-color-info); }
.m-stat-cell-icon--primary { background: var(--m-color-primary-bg); color: var(--m-color-primary); }
.m-stat-cell-body { flex: 1; min-width: 0; }
.m-stat-cell-label {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}
.m-stat-cell-value {
  margin-top: 2px;
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
  line-height: 1.1;
}
.m-stat-cell-value.is-warn { color: var(--m-color-warning-text); }
.m-stat-cell-desc {
  margin-top: 2px;
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
}

/* ============ 骨架屏 ============ */
.m-stats-skeleton {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-3);
}
.m-skel-card {
  height: 92px;
  border-radius: var(--m-radius-xl);
  background: linear-gradient(90deg, var(--m-color-bg-subtle) 25%, var(--m-color-bg-card) 50%, var(--m-color-bg-subtle) 75%);
  background-size: 200% 100%;
  animation: m-skel 1.4s ease infinite;
}
@keyframes m-skel {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* ============ 快捷入口 ============ */
.m-quick-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: var(--m-space-2);
}
.m-quick-item {
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3) var(--m-space-1);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--m-space-2);
  cursor: pointer;
  transition: transform 0.15s;
  font: inherit;
  box-shadow: var(--m-shadow-card);
}
.m-quick-item:active { transform: scale(0.96); }
.m-quick-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--m-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
}
.m-quick-icon--green { background: var(--m-color-success-bg); color: var(--m-color-success); }
.m-quick-icon--orange { background: var(--m-color-warning-bg); color: var(--m-color-warning); }
.m-quick-icon--blue { background: var(--m-color-info-bg); color: var(--m-color-info); }
.m-quick-icon--purple { background: var(--m-color-purple-bg); color: var(--m-color-purple); }
.m-quick-icon--cyan { background: var(--m-color-primary-bg); color: var(--m-color-primary); }
.m-quick-label {
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-secondary);
  text-align: center;
  line-height: 1.2;
}

/* ============ 数据趋势 ============ */
.m-trend-card {
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-4);
  box-shadow: var(--m-shadow-card);
  color: var(--m-color-primary);
}
.m-trend-svg-wrap {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
}
.m-trend-svg {
  width: 100%;
  height: 120px;
  display: block;
}
.m-trend-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-secondary);
}
.m-trend-current { font-weight: var(--m-font-weight-semibold); }
.m-trend-trend.is-up { color: var(--m-color-success); }
.m-trend-trend.is-down { color: var(--m-color-danger); }
.m-trend-loading,
.m-trend-error {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-2);
  height: 120px;
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-caption);
  cursor: default;
}
.m-trend-error { cursor: pointer; color: var(--m-color-danger-text); }

/* ============ 异常提醒 ============ */
.m-alert-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
}
.m-alert-row {
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
  padding: var(--m-space-3);
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border-light);
  border-left-width: 3px;
  border-radius: var(--m-radius-lg);
  cursor: pointer;
  transition: transform 0.15s;
  box-shadow: var(--m-shadow-card);
}
.m-alert-row:active { transform: scale(0.99); }
.m-alert-row--warning { border-left-color: var(--m-color-warning); background: var(--m-color-warning-bg); }
.m-alert-row--warning .m-alert-row-icon { color: var(--m-color-warning); }
.m-alert-row--danger { border-left-color: var(--m-color-danger); background: var(--m-color-danger-bg); }
.m-alert-row--danger .m-alert-row-icon { color: var(--m-color-danger); }
.m-alert-row-icon { flex-shrink: 0; }
.m-alert-row-body { flex: 1; min-width: 0; }
.m-alert-row-title {
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
}
.m-alert-row-desc {
  margin-top: 2px;
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
}
.m-alert-row-count {
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
  flex-shrink: 0;
}
.m-alert-row-arrow { color: var(--m-color-text-disabled); flex-shrink: 0; }

/* ============ 最近动态 ============ */
.m-sse-banner {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  padding: 8px var(--m-space-3);
  margin-bottom: var(--m-space-2);
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning-text);
  border-radius: var(--m-radius-md);
  font-size: var(--m-font-size-caption);
}
.m-activity-list {
  display: flex;
  flex-direction: column;
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-3);
  box-shadow: var(--m-shadow-card);
}
.m-activity-item {
  display: flex;
  align-items: flex-start;
  gap: var(--m-space-3);
  padding: var(--m-space-2) 0;
  border-bottom: 1px solid var(--m-color-border-light);
}
.m-activity-item:last-child { border-bottom: none; }
.m-activity-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--m-radius-circle);
  margin-top: 5px;
  flex-shrink: 0;
}
.m-dot-blue { background: var(--m-color-primary); }
.m-dot-red { background: var(--m-color-danger); }
.m-dot-green { background: var(--m-color-success); }
.m-dot-gray { background: var(--m-color-text-disabled); }
.m-activity-content { flex: 1; min-width: 0; }
.m-activity-text {
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-medium);
  color: var(--m-color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-activity-time {
  margin-top: var(--m-space-1);
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
}
.m-activity-loading,
.m-activity-error {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-2);
  padding: var(--m-space-4);
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-caption);
}
.m-activity-error { cursor: pointer; color: var(--m-color-danger-text); }

.m-spin {
  animation: m-spin 1s linear infinite;
}
@keyframes m-spin {
  to { transform: rotate(360deg); }
}

.m-safe-bottom { height: 80px; }

/* ============ 小屏适配 ============ */
@media (max-width: 360px) {
  .m-quick-grid { gap: var(--m-space-1); }
  .m-quick-item { padding: var(--m-space-2) var(--m-space-1); }
  .m-quick-icon { width: 36px; height: 36px; }
  .m-stats-value { font-size: 28px; }
  .m-hero-account { padding: 3px 8px; font-size: 10px; }
  .m-stats-side { min-width: 72px; }
}
</style>
