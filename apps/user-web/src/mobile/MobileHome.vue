<template>
  <div class="m-home">
    <!-- 区块 2：问候 + 今日概览大卡 -->
    <section class="m-home-greeting">
      <div class="m-greeting-text">
        <div class="m-greeting-time">{{ greetingTime }}，{{ userName }}</div>
        <div class="m-greeting-status" :class="todaySummaryClass">{{ todaySummary }}</div>
      </div>

      <div class="m-card-hero" @click="navigate('orders')">
        <div class="m-hero-main">
          <div class="m-hero-label">今日订单</div>
          <div class="m-hero-value">{{ metricText(stats.todayOrders) }}</div>
          <div class="m-hero-sub">点击查看订单详情</div>
        </div>
        <div class="m-hero-divider"></div>
        <div class="m-hero-side">
          <div class="m-hero-side-label">待发货</div>
          <div class="m-hero-side-value" :class="{ 'm-hero-side-value--warn': (stats.pendingDelivery ?? 0) > 0 }">{{ metricText(stats.pendingDelivery) }}</div>
          <div v-if="(stats.pendingDelivery ?? 0) > 0" class="m-hero-side-sub">需尽快处理</div>
        </div>
      </div>
    </section>

    <MobileUnavailableState v-if="statsLoadError" compact title="部分运营数据暂时不可用" :description="statsLoadError" @retry="loadStats" />

    <!-- 区块 3：需要关注（2×2 状态网格） -->
    <section v-if="hasAlerts" class="m-home-section">
      <div class="m-section-header">
        <div class="m-section-title">需要关注</div>
      </div>

      <div class="m-alerts-grid">
        <!-- 待发货 -->
        <div v-if="(stats.pendingDelivery ?? 0) > 0" class="m-alert-card m-alert-card--warning" @click="navigate('orders')">
          <div class="m-alert-header">
            <span class="m-alert-label">待发货</span>
            <span class="m-alert-count">{{ stats.pendingDelivery }}</span>
          </div>
          <div class="m-alert-desc">需尽快处理发货</div>
        </div>

        <!-- 异常 -->
        <div v-if="(stats.deliveryFail ?? 0) > 0" class="m-alert-card m-alert-card--danger" @click="navigate('delivery-records')">
          <div class="m-alert-header">
            <span class="m-alert-label">异常</span>
            <span class="m-alert-count">{{ stats.deliveryFail }}</span>
          </div>
          <div class="m-alert-desc">发货失败需关注</div>
        </div>

        <!-- 自动化 -->
        <div class="m-alert-card" :class="automationCardClass" @click="navigate('auto-delivery')">
          <div class="m-alert-header">
            <span class="m-alert-label">自动化</span>
            <span class="m-alert-status">{{ automationStatusText }}</span>
          </div>
          <div class="m-alert-desc">今日执行 {{ metricText(stats.deliverySuccess) }} 次</div>
        </div>

        <!-- 未读消息 -->
        <div v-if="(stats.unreadMessages ?? 0) > 0" class="m-alert-card m-alert-card--info" @click="navigate('messages')">
          <div class="m-alert-header">
            <span class="m-alert-label">未读消息</span>
            <span class="m-alert-count">{{ stats.unreadMessages }}</span>
          </div>
          <div class="m-alert-desc">来自买家咨询</div>
        </div>
      </div>
    </section>

    <!-- 区块 4：快捷操作 -->
    <section class="m-home-section">
      <div class="m-section-header">
        <div class="m-section-title">快捷操作</div>
      </div>

      <div class="m-quick-actions-grid">
        <button class="m-quick-action" @click="navigate('accounts')">
          <div class="m-quick-action-icon m-quick-action-icon--primary">
            <MIcon name="userPlus" :size="18" />
          </div>
          <div class="m-quick-action-label">添加账号</div>
        </button>

        <button class="m-quick-action" @click="navigate('messages')">
          <div class="m-quick-action-icon m-quick-action-icon--success">
            <MIcon name="chat" :size="18" />
          </div>
          <div class="m-quick-action-label">连接消息</div>
        </button>

        <button class="m-quick-action" @click="navigate('products')">
          <div class="m-quick-action-icon m-quick-action-icon--warning">
            <MIcon name="bag" :size="18" />
          </div>
          <div class="m-quick-action-label">商品配置</div>
        </button>

        <button class="m-quick-action" @click="navigate('auto-delivery')">
          <div class="m-quick-action-icon m-quick-action-icon--purple">
            <MIcon name="package" :size="18" />
          </div>
          <div class="m-quick-action-label">自动发货</div>
        </button>
      </div>
    </section>

    <!-- 区块 5：自动化状态卡 -->
    <section class="m-home-section">
      <div class="m-automation-card" @click="navigate('auto-delivery')">
        <div class="m-automation-row">
          <div class="m-automation-icon" :class="automationIconClass">
            <MIcon name="workflow" :size="20" />
          </div>
          <div class="m-automation-content">
            <div class="m-automation-title">自动化{{ automationRunning ? '运行中' : '已停止' }}</div>
            <div class="m-automation-stats">
              今日 {{ metricText(stats.deliverySuccess) }} 次执行
            </div>
          </div>
          <div class="m-automation-status">
            <span class="m-status-dot" :class="automationStatusClass"></span>
          </div>
        </div>
      </div>
    </section>

    <!-- 区块 6：最近动态 -->
    <section class="m-home-section">
      <div class="m-section-header">
        <div class="m-section-title">最近动态</div>
        <div class="m-section-tabs">
          <span class="m-tab-pill" :class="{ active: activityTab === 'events' }" @click="activityTab = 'events'">事件</span>
          <span class="m-tab-pill" :class="{ active: activityTab === 'notifications' }" @click="activityTab = 'notifications'">通知</span>
        </div>
      </div>

      <div v-if="activityTab === 'events'" class="m-activity-list">
        <div v-if="sseStatus !== 'connected'" class="m-activity-banner">
          <MIcon name="wifiOff" :size="14" />
          <span>实时连接中断，正在重连...</span>
        </div>
        <div v-for="(evt, i) in recentEvents" :key="i" class="m-activity-item">
          <span class="m-activity-dot" :class="eventColorClass(evt)"></span>
          <div class="m-activity-content">
            <div class="m-activity-text">{{ formatEventText(evt) }}</div>
            <div class="m-activity-time">{{ formatEventTime(evt) }}</div>
          </div>
        </div>
        <MEmpty v-if="recentEvents.length === 0" inline icon="activity" title="暂无事件" />
      </div>

      <div v-if="activityTab === 'notifications'" class="m-activity-list">
        <div v-for="n in notifications" :key="n.id || n.title" class="m-activity-item">
          <span class="m-activity-dot m-activity-dot--info"></span>
          <div class="m-activity-content">
            <div class="m-activity-text">{{ n.title }}</div>
            <div class="m-activity-time">{{ n.content || n.message || n.desc }}</div>
          </div>
        </div>
        <MEmpty v-if="notifications.length === 0" inline icon="bell" title="暂无通知" />
      </div>
    </section>

    <MobileUnavailableState v-if="notificationsLoadError" compact title="最近通知暂时不可用" :description="notificationsLoadError" @retry="loadNotifications" />

    <div class="m-safe-bottom"></div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import MIcon from './MIcon.vue'
import MobileUnavailableState from './MobileUnavailableState.vue'
import MEmpty from './components/MEmpty.vue'
import { getLiteAccounts } from '../api/accounts.js'
import { getGoods } from '../api/goods.js'
import { getDashboardSummary } from '../api/dashboard.js'
import { getNavigationNotifications } from '../api/navigation.js'
import { accountWsConnected } from '../utils/accountAuth.js'
import { recordsOfOrThrow } from '../utils/apiData.js'
import { getSseStatus } from '../utils/sse.js'
import { getCachedUsername } from '../utils/auth.js'

const emit = defineEmits(['navigate', 'logout', 'force-desktop', 'tab-change'])

function navigate(page) { emit('navigate', page) }

const stats = ref({
  accounts: null, onlineAccounts: null, products: null, onSale: null,
  pendingDelivery: null, deliverySuccess: null, deliveryFail: null,
  todayOrders: null, unreadMessages: null
})

const statsLoadError = ref('')
const notificationsLoadError = ref('')
const onboarding = ref({ addedAccount: null, syncedProducts: null, configuredDelivery: null })

const recentEvents = ref([])
const sseStatus = ref(getSseStatus())
const notifications = ref([])
const activityTab = ref('events')

// 问候语：按当前小时返回时段问候
const greetingTime = computed(() => {
  const h = new Date().getHours()
  if (h >= 6 && h <= 11) return '早上好'
  if (h >= 12 && h <= 13) return '中午好'
  if (h >= 14 && h <= 18) return '下午好'
  if (h >= 19 && h <= 23) return '晚上好'
  return '夜深了'
})

// 用户名：从本地缓存获取，缺省为"店主"
const userName = computed(() => getCachedUsername() || '店主')

// 今日概览动态文案
const todaySummary = computed(() => {
  const pending = Number(stats.value.pendingDelivery ?? 0)
  const fail = Number(stats.value.deliveryFail ?? 0)
  const orders = Number(stats.value.todayOrders ?? 0)
  const abnormal = pending + fail
  if (abnormal > 0) return `今天有 ${abnormal} 项待处理`
  if (orders > 0) return `今天有 ${orders} 个新订单`
  return '今天一切正常'
})

const todaySummaryClass = computed(() => {
  const pending = Number(stats.value.pendingDelivery ?? 0)
  const fail = Number(stats.value.deliveryFail ?? 0)
  return (pending + fail) > 0 ? 'm-greeting-status--danger' : ''
})

// 是否有待关注项
const hasAlerts = computed(() => {
  return (Number(stats.value.pendingDelivery ?? 0)) > 0 ||
         (Number(stats.value.deliveryFail ?? 0)) > 0 ||
         (Number(stats.value.unreadMessages ?? 0)) > 0 ||
         onboarding.value.configuredDelivery !== true
})

// 自动化相关派生状态
const automationRunning = computed(() => onboarding.value.configuredDelivery === true)

const automationCardClass = computed(() => {
  if (onboarding.value.configuredDelivery === true) return 'm-alert-card--success'
  if (onboarding.value.configuredDelivery === false) return 'm-alert-card--warning'
  return ''
})

const automationStatusText = computed(() => {
  if (onboarding.value.configuredDelivery === true) return '运行中'
  if (onboarding.value.configuredDelivery === false) return '需关注'
  return '未知'
})

const automationStatusClass = computed(() => {
  if (onboarding.value.configuredDelivery === true) return 'm-status-dot--success'
  if (onboarding.value.configuredDelivery === false) return 'm-status-dot--warning'
  return 'm-status-dot--neutral'
})

const automationIconClass = computed(() => {
  if (onboarding.value.configuredDelivery === true) return 'm-automation-icon--success'
  if (onboarding.value.configuredDelivery === false) return 'm-automation-icon--warning'
  return 'm-automation-icon--neutral'
})

async function loadStats() {
  statsLoadError.value = ''
  stats.value = {
    accounts: null, onlineAccounts: null, products: null, onSale: null,
    pendingDelivery: null, deliverySuccess: null, deliveryFail: null,
    todayOrders: null, unreadMessages: null
  }
  onboarding.value = { addedAccount: null, syncedProducts: null, configuredDelivery: null }
  const [accRes, goodsRes, dashRes] = await Promise.allSettled([
    getLiteAccounts({ page: 1, pageSize: 100 }),
    getGoods({ page: 1, pageSize: 1 }),
    getDashboardSummary()
  ])
  const unavailable = []
    const accountData = accRes.status === 'fulfilled' ? accRes.value?.data : null
    const accountShapeValid = Array.isArray(accountData) || Array.isArray(accountData?.records) || Array.isArray(accountData?.list)
    if (accountShapeValid) {
      const list = accountData.records || accountData.list || (Array.isArray(accountData) ? accountData : [])
      stats.value.accounts = accountData.total ?? list.length
      stats.value.onlineAccounts = list.filter(a => accountWsConnected(a)).length
      onboarding.value.addedAccount = stats.value.accounts > 0
    } else {
      unavailable.push('账号')
    }
    const goodsData = goodsRes.status === 'fulfilled' ? goodsRes.value?.data : null
    const goodsShapeValid = Array.isArray(goodsData) || Array.isArray(goodsData?.records) || Array.isArray(goodsData?.list)
    if (goodsShapeValid) {
      const goodsList = goodsData.records || goodsData.list || (Array.isArray(goodsData) ? goodsData : null)
      stats.value.products = goodsData.total ?? (Array.isArray(goodsList) ? goodsList.length : null)
      onboarding.value.syncedProducts = stats.value.products > 0
    } else {
      unavailable.push('商品')
    }
    const d = dashRes.status === 'fulfilled' ? dashRes.value?.data : null
    const dashboardShapeValid = d && typeof d === 'object' && ['onSaleCount', 'sellingItemCount', 'pendingDelivery', 'pendingDeliveryCount', 'deliverySuccess', 'deliverySuccessCount', 'deliveryFail', 'deliveryFailCount', 'todayOrderCount', 'orderCount', 'unreadMessage', 'unreadMessageCount', 'autoDeliveryEnabled'].some(key => Object.prototype.hasOwnProperty.call(d, key))
    if (dashboardShapeValid) {
      stats.value.onSale = firstMetric(d, 'onSaleCount', 'sellingItemCount')
      stats.value.pendingDelivery = firstMetric(d, 'pendingDelivery', 'pendingDeliveryCount')
      stats.value.deliverySuccess = firstMetric(d, 'deliverySuccess', 'deliverySuccessCount')
      stats.value.deliveryFail = firstMetric(d, 'deliveryFail', 'deliveryFailCount')
      stats.value.todayOrders = firstMetric(d, 'todayOrderCount', 'orderCount')
      stats.value.unreadMessages = firstMetric(d, 'unreadMessage', 'unreadMessageCount')
      if (typeof d.autoDeliveryEnabled === 'boolean') {
        onboarding.value.configuredDelivery = d.autoDeliveryEnabled
      } else if (Number(stats.value.deliverySuccess) > 0) {
        onboarding.value.configuredDelivery = true
      } else {
        onboarding.value.configuredDelivery = null
      }
    } else {
      unavailable.push('业务概览')
    }
  if (unavailable.length) {
    statsLoadError.value = `${unavailable.join('、')}数据加载失败，未取得的指标显示为"—"，请重试。`
  }
}

function firstMetric(source, ...keys) {
  for (const key of keys) {
    if (Object.prototype.hasOwnProperty.call(source, key) && source[key] !== null && source[key] !== undefined) return source[key]
  }
  return null
}

function metricText(value) {
  return value === null || value === undefined ? '—' : value
}

async function loadNotifications() {
  notificationsLoadError.value = ''
  try {
    const res = await getNavigationNotifications({ limit: 3 })
    notifications.value = recordsOfOrThrow(res?.data, '最近通知响应格式异常').slice(0, 3)
  } catch (error) {
    notifications.value = []
    notificationsLoadError.value = error?.message || '请检查网络连接后重试。'
  }
}

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
  return `${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`
}

function eventColorClass(evt) {
  const t = evt.type || ''
  if (t === 'message') return 'm-dot-blue'
  if (t.includes('error') || t.includes('fail')) return 'm-dot-red'
  if (t.includes('success') || t.includes('delivery')) return 'm-dot-green'
  return 'm-dot-gray'
}

function onSseStatus(event) {
  sseStatus.value = String(event?.detail || 'disconnected')
}

onMounted(() => {
  loadStats()
  loadNotifications()
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

/* === 区块 2：问候 + 今日概览大卡 === */
.m-home-greeting {
  margin-bottom: var(--m-space-4);
}
.m-greeting-text {
  margin-bottom: var(--m-space-3);
}
.m-greeting-time {
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
  line-height: var(--m-line-height-tight);
}
.m-greeting-status {
  margin-top: var(--m-space-1);
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-secondary);
}
.m-greeting-status--danger {
  color: var(--m-color-danger-text);
}

.m-card-hero {
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-4);
  box-shadow: var(--m-shadow-card);
  display: flex;
  align-items: center;
  gap: var(--m-space-4);
  cursor: pointer;
  transition: transform 0.15s;
}
.m-card-hero:active {
  transform: scale(0.98);
}
.m-hero-main {
  flex: 1;
  min-width: 0;
}
.m-hero-label {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  margin-bottom: var(--m-space-1);
}
.m-hero-value {
  font-size: var(--m-font-size-hero);
  font-weight: var(--m-font-weight-extrabold);
  color: var(--m-color-text-primary);
  line-height: var(--m-line-height-tight);
}
.m-hero-sub {
  margin-top: var(--m-space-1);
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
}
.m-hero-divider {
  width: 1px;
  align-self: stretch;
  background: var(--m-color-border-light);
}
.m-hero-side {
  flex: 0 0 auto;
  text-align: right;
}
.m-hero-side-label {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  margin-bottom: var(--m-space-1);
}
.m-hero-side-value {
  font-size: var(--m-font-size-h1);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-primary);
  line-height: var(--m-line-height-tight);
}
.m-hero-side-value--warn {
  color: var(--m-color-warning-text);
}
.m-hero-side-sub {
  margin-top: var(--m-space-1);
  font-size: var(--m-font-size-caption);
  color: var(--m-color-warning-text);
}

/* === 区块通用 === */
.m-home-section {
  margin-bottom: var(--m-space-4);
}
.m-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--m-space-3);
}
.m-section-title {
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
}
.m-section-tabs {
  display: flex;
  gap: var(--m-space-1);
}
.m-tab-pill {
  padding: var(--m-space-1) var(--m-space-3);
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

/* === 区块 3：需要关注（2×2 状态网格） === */
.m-alerts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--m-space-3);
}
.m-alert-card {
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3);
  min-height: 72px;
  cursor: pointer;
  transition: transform 0.15s;
  display: flex;
  flex-direction: column;
  gap: var(--m-space-1);
}
.m-alert-card:active {
  transform: scale(0.98);
}
.m-alert-card--warning {
  background: var(--m-color-warning-bg);
  border-color: var(--m-color-warning-border);
}
.m-alert-card--danger {
  background: var(--m-color-danger-bg);
  border-color: var(--m-color-danger-border);
}
.m-alert-card--success {
  background: var(--m-color-success-bg);
  border-color: var(--m-color-success-border);
}
.m-alert-card--info {
  background: var(--m-color-info-bg);
  border-color: var(--m-color-info-border);
}
.m-alert-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.m-alert-label {
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-secondary);
}
.m-alert-card--warning .m-alert-label { color: var(--m-color-warning-text); }
.m-alert-card--danger .m-alert-label { color: var(--m-color-danger-text); }
.m-alert-card--success .m-alert-label { color: var(--m-color-success-text); }
.m-alert-card--info .m-alert-label { color: var(--m-color-info-text); }
.m-alert-count {
  font-size: var(--m-font-size-h1);
  font-weight: var(--m-font-weight-bold);
  line-height: 1;
}
.m-alert-card--warning .m-alert-count { color: var(--m-color-warning-text); }
.m-alert-card--danger .m-alert-count { color: var(--m-color-danger-text); }
.m-alert-card--success .m-alert-count { color: var(--m-color-success-text); }
.m-alert-card--info .m-alert-count { color: var(--m-color-info-text); }
.m-alert-status {
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-secondary);
}
.m-alert-card--warning .m-alert-status { color: var(--m-color-warning-text); }
.m-alert-card--success .m-alert-status { color: var(--m-color-success-text); }
.m-alert-desc {
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
}

/* === 区块 4：快捷操作 === */
.m-quick-actions-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--m-space-2);
}
.m-quick-action {
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3) var(--m-space-2);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--m-space-2);
  cursor: pointer;
  transition: transform 0.15s;
  font: inherit;
}
.m-quick-action:active {
  transform: scale(0.98);
}
.m-quick-action-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--m-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
}
.m-quick-action-icon--primary {
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
}
.m-quick-action-icon--success {
  background: var(--m-color-success-bg);
  color: var(--m-color-success);
}
.m-quick-action-icon--warning {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning);
}
.m-quick-action-icon--purple {
  background: var(--m-color-purple-bg);
  color: var(--m-color-purple);
}
.m-quick-action-label {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-secondary);
}

/* === 区块 5：自动化状态卡 === */
.m-automation-card {
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-4);
  box-shadow: var(--m-shadow-card);
  cursor: pointer;
  transition: transform 0.15s;
}
.m-automation-card:active {
  transform: scale(0.98);
}
.m-automation-row {
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
}
.m-automation-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--m-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-automation-icon--success {
  background: var(--m-color-success-bg);
  color: var(--m-color-success);
}
.m-automation-icon--warning {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning);
}
.m-automation-icon--neutral {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-tertiary);
}
.m-automation-content {
  flex: 1;
  min-width: 0;
}
.m-automation-title {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
}
.m-automation-stats {
  margin-top: var(--m-space-1);
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}
.m-automation-status {
  flex-shrink: 0;
}
.m-status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: var(--m-radius-circle);
}
.m-status-dot--success {
  background: var(--m-color-success);
  animation: m-status-pulse 1.5s infinite;
}
.m-status-dot--warning {
  background: var(--m-color-warning);
}
.m-status-dot--neutral {
  background: var(--m-color-text-tertiary);
}
@keyframes m-status-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.3); }
}

/* === 区块 6：最近动态 === */
.m-activity-banner {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  padding: var(--m-space-2) var(--m-space-3);
  margin-bottom: var(--m-space-2);
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger-text);
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
}
.m-activity-item {
  display: flex;
  align-items: flex-start;
  gap: var(--m-space-3);
  padding: var(--m-space-2) 0;
  border-bottom: 1px solid var(--m-color-border-light);
}
.m-activity-item:last-child {
  border-bottom: none;
}
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
.m-activity-dot--info { background: var(--m-color-info); }
.m-activity-content {
  flex: 1;
  min-width: 0;
}
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

.m-safe-bottom {
  height: 80px;
}

@media (max-width: 360px) {
  .m-quick-actions-grid {
    gap: var(--m-space-1);
  }
  .m-quick-action {
    padding: var(--m-space-2) var(--m-space-1);
  }
}
</style>
