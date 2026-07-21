<template>
  <div class="m-home">
    <section class="m-announcement">
      <div class="m-announcement-copy">
        <span class="m-announcement-kicker">闲鱼助手</span>
        <h1>让店铺运营更轻松</h1>
        <p>账号、商品、订单和自动化状态，一处查看。</p>
        <div class="m-announcement-points">
          <span><MIcon name="check" :size="14" />实时状态</span>
          <span><MIcon name="check" :size="14" />低风险操作</span>
        </div>
      </div>
      <div class="m-announcement-art" aria-hidden="true">
        <div class="m-art-card m-art-card-main"><MIcon name="chart" :size="28" /></div>
        <div class="m-art-card m-art-card-small"><MIcon name="check" :size="18" /></div>
        <div class="m-art-ring"></div>
      </div>
      <div class="m-announcement-dots"><span class="active"></span><span></span><span></span></div>
    </section>

    <MobileUnavailableState v-if="statsLoadError" compact title="部分运营数据暂时不可用" :description="statsLoadError" @retry="loadStats" />

    <section class="m-section m-quick-start">
      <div class="m-section-header">
        <div><span class="m-section-eyebrow">开始使用</span><h2>快捷开始</h2></div>
      </div>
      <div class="m-start-grid">
        <button class="m-start-item" @click="navigate('accounts')"><span class="m-start-icon m-blue"><MIcon name="userPlus" :size="21" /></span><span>添加账号</span></button>
        <button class="m-start-item" @click="navigate('messages')"><span class="m-start-icon m-green"><MIcon name="chat" :size="21" /></span><span>连接消息</span></button>
        <button class="m-start-item" @click="navigate('products')"><span class="m-start-icon m-orange"><MIcon name="bag" :size="21" /></span><span>商品配置</span></button>
        <button class="m-start-item" @click="navigate('auto-delivery')"><span class="m-start-icon m-purple"><MIcon name="package" :size="21" /></span><span>自动发货</span></button>
      </div>
      <div class="m-progress-line"><span :style="{ width: onboardingProgress + '%' }"></span></div>
      <p class="m-progress-text">{{ onboardingProgressText }}</p>
    </section>

    <section class="m-section">
      <div class="m-section-header"><div><span class="m-section-eyebrow">运营工具</span><h2>功能特性</h2></div><button class="m-section-more" @click="emit('force-desktop')">全部功能<MIcon name="chevronRight" :size="14" /></button></div>
      <div class="m-feature-list">
        <button class="m-feature-item" @click="navigate('accounts')"><span class="m-feature-icon m-blue"><MIcon name="account" :size="20" /></span><span class="m-feature-copy"><b>多账号管理</b><small>{{ onlineAccountText }}</small></span><MIcon name="chevronRight" :size="18" /></button>
        <button class="m-feature-item" @click="navigate('orders')"><span class="m-feature-icon m-green"><MIcon name="fileText" :size="20" /></span><span class="m-feature-copy"><b>订单管理</b><small>集中处理订单与售后</small></span><MIcon name="chevronRight" :size="18" /></button>
        <button class="m-feature-item" @click="navigate('data')"><span class="m-feature-icon m-orange"><MIcon name="chart" :size="20" /></span><span class="m-feature-copy"><b>商机数据</b><small>查看商品、订单和发货趋势</small></span><MIcon name="chevronRight" :size="18" /></button>
        <button class="m-feature-item" @click="navigate('auto-delivery')"><span class="m-feature-icon m-purple"><MIcon name="package" :size="20" /></span><span class="m-feature-copy"><b>自动化发货</b><small>{{ onboardingText(onboarding.configuredDelivery, '创建自动发货规则') }}</small></span><MIcon name="chevronRight" :size="18" /></button>
        <button class="m-feature-item" @click="navigate('products')"><span class="m-feature-icon m-sky"><MIcon name="bag" :size="20" /></span><span class="m-feature-copy"><b>商品管理</b><small>{{ onSaleText }}</small></span><MIcon name="chevronRight" :size="18" /></button>
      </div>
    </section>

    <section class="m-section">
      <div class="m-section-header"><div><span class="m-section-eyebrow">店铺情况</span><h2>数据概览</h2></div><button class="m-section-more" @click="navigate('data')">数据面板<MIcon name="chevronRight" :size="14" /></button></div>
      <div class="m-overview-grid">
        <button class="m-overview-item" @click="navigate('orders')"><span class="m-overview-label">今日订单</span><strong>{{ metricText(stats.todayOrders) }}</strong><small>订单总数</small></button>
        <button class="m-overview-item" @click="navigate('delivery-records')"><span class="m-overview-label">发货成功</span><strong class="m-value-green">{{ metricText(stats.deliverySuccess) }}</strong><small>今日完成</small></button>
        <button class="m-overview-item" @click="navigate('data')"><span class="m-overview-label">待处理</span><strong class="m-value-orange">{{ metricText(stats.pendingDelivery) }}</strong><small>待发货订单</small></button>
        <button class="m-overview-item" @click="navigate('products')"><span class="m-overview-label">商品总数</span><strong class="m-value-blue">{{ metricText(stats.products) }}</strong><small>{{ onSaleText }}</small></button>
      </div>
    </section>

    <section v-if="recentEvents.length > 0" class="m-section">
      <div class="m-section-header"><div><span class="m-section-eyebrow">消息流</span><h2>最近实时事件</h2></div><span class="m-live-badge"><span class="m-live-dot"></span>{{ sseStatus === 'connected' ? '实时' : '连接中断' }}</span></div>
      <div class="m-event-list"><div v-for="(evt, i) in recentEvents" :key="i" class="m-event-item"><span class="m-event-dot" :class="eventColorClass(evt)"></span><div class="m-event-body"><b>{{ formatEventText(evt) }}</b><small>{{ formatEventTime(evt) }}</small></div></div></div>
    </section>

    <section v-if="notifications.length > 0" class="m-section">
      <div class="m-section-header"><div><span class="m-section-eyebrow">服务通知</span><h2>最近通知</h2></div><button class="m-section-more" @click="navigate('messages')">全部通知<MIcon name="chevronRight" :size="14" /></button></div>
      <div class="m-notice-list"><div v-for="n in notifications" :key="n.id || n.title" class="m-notice-item"><span class="m-notice-icon" :class="'m-notice-' + (n.type || 'info')"><MIcon :name="n.icon || 'bell'" :size="16" /></span><div class="m-notice-body"><b>{{ n.title }}</b><small>{{ n.content || n.message || n.desc }}</small></div></div></div>
    </section>

    <MobileUnavailableState v-if="notificationsLoadError" compact title="最近通知暂时不可用" :description="notificationsLoadError" @retry="loadNotifications" />

    <section class="m-desktop-tip"><span class="m-desktop-tip-icon"><MIcon name="monitor" :size="21" /></span><div><b>复杂操作建议使用桌面版</b><p>商品发布、批量管理和规则编辑在桌面端更适合完成。</p></div><button @click="emit('force-desktop')"><MIcon name="desktop" :size="18" /></button></section>

    <div class="m-bottom-actions"><button class="m-btn m-btn-outline" @click="emit('logout')"><MIcon name="logout" :size="18" />退出登录</button><button class="m-btn m-btn-primary" @click="emit('force-desktop')">进入桌面版<MIcon name="chevronRight" :size="18" /></button></div>
    <div class="m-safe-bottom"></div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import MIcon from './MIcon.vue'
import MobileUnavailableState from './MobileUnavailableState.vue'
import { getLiteAccounts } from '../api/accounts.js'
import { getGoods } from '../api/goods.js'
import { getDashboardSummary } from '../api/dashboard.js'
import { getNavigationNotifications } from '../api/navigation.js'
import { accountWsConnected } from '../utils/accountAuth.js'
import { recordsOfOrThrow } from '../utils/apiData.js'
import { getSseStatus } from '../utils/sse.js'

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
const onboardingDoneCount = computed(() => Object.values(onboarding.value).filter(Boolean).length)
const onboardingProgress = computed(() => (onboardingDoneCount.value / 3) * 100)
const onboardingUnknownCount = computed(() => Object.values(onboarding.value).filter(value => value === null).length)
const onboardingProgressText = computed(() => onboardingUnknownCount.value
  ? `${onboardingDoneCount.value}/3 已确认，${onboardingUnknownCount.value} 项状态未知`
  : `${onboardingDoneCount.value}/3 已完成`)
const onlineAccountText = computed(() => stats.value.onlineAccounts === null ? '在线状态不可用' : `${stats.value.onlineAccounts} 个在线`)
const onSaleText = computed(() => stats.value.onSale === null ? '在售状态不可用' : `在售 ${stats.value.onSale}`)

const recentEvents = ref([])
const sseStatus = ref(getSseStatus())
const notifications = ref([])

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
    statsLoadError.value = `${unavailable.join('、')}数据加载失败，未取得的指标显示为“—”，请重试。`
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

function onboardingText(value, pendingText) {
  if (value === true) return '已完成'
  if (value === false) return pendingText
  return '状态未知'
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
  padding: 12px 16px 0;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
}

.m-hero {
  background: linear-gradient(135deg, #e8f1ff 0%, #f0f5ff 40%, #e6f0ff 100%);
  border-radius: 20px;
  padding: 22px 20px;
  position: relative;
  overflow: hidden;
  margin-bottom: 16px;
}
.m-hero-content { position: relative; z-index: 2; max-width: 60%; }
.m-hero h1 { margin: 0 0 8px; font-size: 28px; font-weight: 800; color: #15213d; line-height: 1.2; }
.m-hero-highlight {
  background: linear-gradient(135deg, #0d6bff, #3b9bff);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
  /* 让“移动端”作为一个词整体换行，避免只剩“端”单独占一行。 */
  white-space: nowrap;
}
.m-hero-sub { margin: 0 0 14px; font-size: 14px; color: #5a6a85; line-height: 1.6; }
.m-hero-tags { display: flex; flex-wrap: wrap; gap: 8px; }
.m-tag {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 12px; color: #0d6bff; background: rgba(13,107,255,0.1);
  padding: 4px 10px; border-radius: 100px; font-weight: 500;
}
.m-tag :deep(svg) { color: #0d6bff; }

.m-hero-illus { position: absolute; right: -10px; top: 50%; transform: translateY(-50%); width: 160px; height: 160px; z-index: 1; }
.m-phone {
  position: absolute; right: 10px; top: 15px; width: 90px; height: 140px;
  background: linear-gradient(145deg, #4a8fff, #2d6bff); border-radius: 16px;
  box-shadow: 0 12px 30px rgba(13,107,255,0.3); padding: 8px 5px; transform: rotate(-8deg);
}
.m-phone::before { content: ''; position: absolute; top: 4px; left: 50%; transform: translateX(-50%); width: 22px; height: 4px; background: rgba(255,255,255,0.4); border-radius: 4px; }
.m-phone-screen { background: rgba(255,255,255,0.95); border-radius: 10px; height: 100%; padding: 12px 8px; margin-top: 4px; }
.m-phone-msg { height: 10px; background: #e8f0ff; border-radius: 4px; margin-bottom: 6px; }
.m-phone-msg-2 { width: 60%; }
.m-fish-badge {
  position: absolute; right: 0; bottom: 10px; width: 48px; height: 48px;
  background: linear-gradient(135deg, #5ba3ff, #2d7bff); border-radius: 50%;
  display: flex; align-items: center; justify-content: center; color: white;
  box-shadow: 0 6px 16px rgba(13,107,255,0.35); z-index: 2;
}

.m-stats-scroll {
  margin-bottom: 16px;
  margin-left: -16px;
  margin-right: -16px;
  padding-left: 16px;
  padding-right: 16px;
  overflow-x: auto;
  overflow-y: hidden;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.m-stats-scroll::-webkit-scrollbar { display: none; }
.m-stats {
  display: flex;
  gap: 10px;
  width: max-content;
  padding-right: 4px;
}
.m-stat-card {
  width: 130px;
  flex-shrink: 0;
  background: white; border-radius: 16px; padding: 14px;
  display: flex; flex-direction: column; gap: 6px;
  box-shadow: 0 2px 8px rgba(31,53,94,0.05); border: 1px solid #f0f4fa;
  cursor: pointer; transition: transform 0.15s;
}
.m-stat-card:active { transform: scale(0.97); }
.m-stat-icon {
  width: 44px; height: 44px; border-radius: 13px;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.m-stat-blue { background: linear-gradient(135deg,#e8f1ff,#d4e4ff); color: #0d6bff; }
.m-stat-blue2 { background: linear-gradient(135deg,#e8f1ff,#d4e4ff); color: #1678ff; }
.m-stat-blue3 { background: linear-gradient(135deg,#e0f2ff,#cce4ff); color: #0566e9; }
.m-stat-orange { background: linear-gradient(135deg,#fff4e0,#ffe7c2); color: #ff9f22; }
.m-stat-green { background: linear-gradient(135deg,#e2f8ee,#cdf2df); color: #16bf78; }
.m-stat-red { background: linear-gradient(135deg,#ffeaea,#ffd0d0); color: #ff5252; }
.m-stat-purple { background: linear-gradient(135deg,#f0ebff,#e2d8ff); color: #8b5cf6; }
.m-stat-label { font-size: 12px; color: #8c98ae; }
.m-stat-value { font-size: 24px; font-weight: 800; color: #15213d; line-height: 1.2; }
.m-stat-desc { font-size: 11px; color: #8c98ae; }
.m-text-green { color: #16bf78 !important; }
.m-text-orange { color: #ff9f22 !important; }

.m-section {
  background: white; border-radius: 20px; padding: 16px; margin-bottom: 14px;
  box-shadow: 0 2px 8px rgba(31,53,94,0.04); border: 1px solid #f0f4fa;
}
.m-section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.m-section-header h2 { margin: 0; font-size: 17px; font-weight: 700; color: #15213d; }
.m-section-more {
  display: inline-flex; align-items: center; gap: 2px;
  background: none; border: none; font-size: 13px; color: #72809a; padding: 4px 6px; cursor: pointer;
}
.m-section-more :deep(svg) { color: #72809a; }
.m-live-badge {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 11px; color: #ff5252; font-weight: 600;
}
.m-live-dot {
  width: 8px; height: 8px; border-radius: 50%; background: #ff5252;
  animation: m-live-pulse 1.5s infinite;
}
@keyframes m-live-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(1.3); }
}

.m-quick-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.m-quick-item {
  display: flex; align-items: center; gap: 10px;
  padding: 12px; background: #f8faff; border-radius: 14px; cursor: pointer; transition: background 0.15s;
}
.m-quick-item:active { background: #eef4ff; }
.m-quick-icon {
  width: 46px; height: 46px; border-radius: 13px;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.m-quick-blue { background: linear-gradient(135deg,#e8f1ff,#d0e2ff); color: #0d6bff; }
.m-quick-green { background: linear-gradient(135deg,#e2f8ee,#cdf2df); color: #16bf78; }
.m-quick-purple { background: linear-gradient(135deg,#f0ebff,#e2d8ff); color: #8b5cf6; }
.m-quick-orange { background: linear-gradient(135deg,#fff4e0,#ffe7c2); color: #ff9f22; }
.m-quick-blue2 { background: linear-gradient(135deg,#e6f2ff,#d0e6ff); color: #2578ff; }
.m-quick-blue3 { background: linear-gradient(135deg,#e0f2ff,#c4e0ff); color: #0566e9; }
.m-quick-purple2 { background: linear-gradient(135deg,#ede8ff,#ddd3ff); color: #7c5cff; }
.m-quick-info { flex: 1; min-width: 0; }
.m-quick-title { font-size: 14px; font-weight: 600; color: #15213d; margin-bottom: 2px; }
.m-quick-desc { font-size: 11px; color: #8c98ae; line-height: 1.4; }
.m-quick-arrow { color: #c4cddb; flex-shrink: 0; }

.m-starter-row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; }
.m-starter-item {
  background: #f8faff; border-radius: 14px; padding: 14px 10px;
  text-align: left; cursor: pointer; position: relative; transition: background 0.15s;
}
.m-starter-item.done { background: #e8f8ee; }
.m-starter-item:active { background: #eef4ff; }
.m-starter-icon {
  width: 44px; height: 44px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center; margin-bottom: 10px;
}
.m-starter-blue { background: linear-gradient(135deg,#e8f1ff,#d0e2ff); color: #0d6bff; }
.m-starter-orange { background: linear-gradient(135deg,#fff4e0,#ffe7c2); color: #ff9f22; }
.m-starter-green { background: linear-gradient(135deg,#e2f8ee,#cdf2df); color: #16bf78; }
.m-starter-done { background: linear-gradient(135deg,#d4f5e2,#b8ebcc); color: #16bf78; }
.m-starter-title { font-size: 13px; font-weight: 600; color: #15213d; margin-bottom: 2px; }
.m-starter-desc { font-size: 11px; color: #8c98ae; }
.m-starter-arrow {
  position: absolute; top: 12px; right: 10px; color: #c4cddb;
  width: 22px; height: 22px; background: rgba(255,255,255,0.8); border-radius: 50%; padding: 3px;
}
.m-onboard-progress {
  margin-top: 30px; height: 8px; background: #f0f4fa; border-radius: 4px; position: relative; overflow: visible;
}
.m-onboard-bar {
  height: 100%; background: linear-gradient(90deg, #16bf78, #0d6bff);
  border-radius: 4px; transition: width 0.3s;
}
.m-onboard-text {
  position: absolute; right: 0; top: -18px; font-size: 11px; color: #8c98ae;
}

.m-event-list { display: flex; flex-direction: column; gap: 10px; }
.m-event-item { display: flex; gap: 10px; align-items: flex-start; }
.m-event-dot {
  width: 8px; height: 8px; border-radius: 50%; margin-top: 5px; flex-shrink: 0;
}
.m-dot-blue { background: #0d6bff; }
.m-dot-red { background: #ff5252; }
.m-dot-green { background: #16bf78; }
.m-dot-gray { background: #c4cddb; }
.m-event-body { flex: 1; min-width: 0; }
.m-event-text { font-size: 13px; color: #15213d; font-weight: 500; }
.m-event-time { font-size: 11px; color: #b0bacb; margin-top: 2px; }

.m-notice-list { display: flex; flex-direction: column; gap: 8px; }
.m-notice-item { display: flex; gap: 10px; padding: 10px; background: #f8faff; border-radius: 12px; }
.m-notice-icon {
  width: 32px; height: 32px; border-radius: 9px;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.m-notice-info { background: #e8f1ff; color: #0d6bff; }
.m-notice-warn { background: #fff4e0; color: #ff9f22; }
.m-notice-error { background: #ffeaea; color: #ff5252; }
.m-notice-success { background: #e2f8ee; color: #16bf78; }
.m-notice-body { flex: 1; min-width: 0; }
.m-notice-title { font-size: 13px; font-weight: 600; color: #15213d; margin-bottom: 2px; }
.m-notice-desc { font-size: 12px; color: #8c98ae; line-height: 1.5; }

.m-pc-notice {
  background: linear-gradient(135deg, #fff9e8 0%, #fffdf5 100%);
  border: 1px solid #ffeec2; border-radius: 18px; padding: 16px;
  display: flex; gap: 12px; margin-bottom: 16px; position: relative; overflow: hidden;
}
.m-pc-notice-icon {
  width: 44px; height: 44px; border-radius: 50%;
  background: linear-gradient(135deg, #ffd88a, #ffb94a); color: white;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.m-pc-notice-content { flex: 1; min-width: 0; }
.m-pc-notice-title { font-size: 15px; font-weight: 700; color: #8a5a00; margin-bottom: 4px; }
.m-pc-notice-desc { font-size: 12px; color: #a07020; line-height: 1.6; }
.m-pc-notice-illus { position: absolute; right: 12px; bottom: 8px; color: #f0c56a; opacity: 0.6; }

.m-bottom-actions { display: flex; gap: 10px; padding: 4px 0 0; }
.m-btn {
  flex: 1; height: 48px; border-radius: 24px; border: none;
  font-size: 15px; font-weight: 600;
  display: inline-flex; align-items: center; justify-content: center; gap: 6px;
  cursor: pointer; transition: transform 0.1s;
}
.m-btn:active { transform: scale(0.97); }
.m-btn-outline { background: white; color: #15213d; border: 1.5px solid #e0e6f0; }
.m-btn-primary { background: linear-gradient(135deg, #0d6bff, #2580ff); color: white; box-shadow: 0 6px 18px rgba(13,107,255,0.3); }

.m-safe-bottom { height: 80px; }

@media (max-width: 480px) {
  /* 两列快捷卡片会把标题和说明压成逐字换行，优先保证内容可读。 */
  .m-quick-grid { grid-template-columns: 1fr; }
  .m-starter-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 360px) {
  .m-hero {
    padding: 18px 16px;
  }
  .m-hero-content { max-width: 68%; }
  .m-hero h1 { font-size: 24px; }
  .m-hero-illus { right: -20px; width: 140px; height: 140px; opacity: .72; }
  .m-phone { right: 12px; top: 10px; width: 78px; height: 122px; }
  .m-quick-item { padding: 12px 14px; }
}
.m-home { padding: 14px 16px 0; background: #f5f8fc; }
.m-announcement { position: relative; min-height: 192px; margin-bottom: 14px; padding: 22px 20px 28px; overflow: hidden; border: 1px solid #cfe0f8; border-radius: 8px; background: linear-gradient(135deg, #e8f3ff, #f8fbff); }
.m-announcement-copy { position: relative; z-index: 2; max-width: 67%; }
.m-announcement-kicker, .m-section-eyebrow { display: block; margin-bottom: 4px; color: #2878c8; font-size: 11px; font-weight: 700; }
.m-announcement h1 { margin: 0 0 8px; color: #172b4d; font-size: 24px; line-height: 1.25; }
.m-announcement p { margin: 0; color: #58708f; font-size: 13px; line-height: 1.55; }
.m-announcement-points { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.m-announcement-points span { display: inline-flex; align-items: center; gap: 3px; color: #176bb6; font-size: 11px; }
.m-announcement-art { position: absolute; right: 8px; top: 29px; width: 108px; height: 118px; }
.m-art-card { position: absolute; display: grid; place-items: center; border: 1px solid rgba(255, 255, 255, .85); box-shadow: 0 10px 24px rgba(42, 109, 177, .16); }
.m-art-card-main { top: 18px; right: 10px; width: 68px; height: 78px; color: #1674d1; border-radius: 8px; background: #fff; transform: rotate(8deg); }
.m-art-card-small { right: 56px; bottom: 5px; width: 36px; height: 36px; color: #168657; border-radius: 50%; background: #e8faef; }
.m-art-ring { position: absolute; right: -27px; top: -31px; width: 126px; height: 126px; border: 20px solid rgba(85, 157, 231, .15); border-radius: 50%; }
.m-announcement-dots { position: absolute; bottom: 12px; left: 20px; display: flex; gap: 5px; }
.m-announcement-dots span { width: 5px; height: 5px; border-radius: 50%; background: #b7c8dd; }.m-announcement-dots .active { width: 15px; border-radius: 4px; background: #2878c8; }
.m-section { margin-bottom: 14px; padding: 16px; border: 1px solid #e3eaf3; border-radius: 8px; box-shadow: 0 2px 7px rgba(33, 60, 97, .04); }
.m-section-header { margin-bottom: 13px; }.m-section-header h2 { font-size: 17px; }.m-section-more { color: #6d7e94; }
.m-start-grid, .m-overview-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.m-start-item, .m-overview-item { min-width: 0; padding: 0; border: 0; background: transparent; cursor: pointer; font: inherit; }
.m-start-item { display: flex; flex-direction: column; align-items: center; gap: 7px; color: #334963; font-size: 12px; }
.m-start-icon { display: grid; width: 43px; height: 43px; place-items: center; border-radius: 8px; }.m-blue { background: #e6f1ff; color: #1774d0; }.m-green { background: #e4f8ee; color: #168b59; }.m-orange { background: #fff2df; color: #d98012; }.m-purple { background: #f0eaff; color: #7655ca; }.m-sky { background: #e2f4fb; color: #2381af; }
.m-progress-line { height: 5px; margin-top: 18px; overflow: hidden; border-radius: 4px; background: #edf1f5; }.m-progress-line span { display: block; height: 100%; border-radius: inherit; background: #2681d4; }.m-progress-text { margin: 7px 0 0; color: #7d8b9d; font-size: 11px; }
.m-feature-list { display: flex; flex-direction: column; }.m-feature-item { display: flex; align-items: center; width: 100%; gap: 11px; padding: 11px 0; border: 0; border-bottom: 1px solid #edf1f5; background: transparent; color: #b2bdca; text-align: left; cursor: pointer; }.m-feature-item:last-child { border-bottom: 0; padding-bottom: 0; }.m-feature-icon { display: grid; width: 39px; height: 39px; place-items: center; flex: 0 0 auto; border-radius: 8px; }.m-feature-copy { display: flex; min-width: 0; flex: 1; flex-direction: column; gap: 3px; }.m-feature-copy b, .m-notice-body b, .m-event-body b { overflow: hidden; color: #20344e; font-size: 13px; font-weight: 650; text-overflow: ellipsis; white-space: nowrap; }.m-feature-copy small, .m-notice-body small, .m-event-body small { overflow: hidden; color: #8290a2; font-size: 11px; line-height: 1.4; text-overflow: ellipsis; white-space: nowrap; }
.m-overview-item { padding: 11px 7px; border: 1px solid #eaf0f6; border-radius: 8px; text-align: left; }.m-overview-label, .m-overview-item small { display: block; overflow: hidden; color: #8190a3; font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }.m-overview-item strong { display: block; margin: 7px 0 3px; color: #20344e; font-size: 21px; line-height: 1; }.m-value-green { color: #169460 !important; }.m-value-orange { color: #d98412 !important; }.m-value-blue { color: #277bc5 !important; }
.m-live-badge { color: #dd5a5a; }.m-live-dot { width: 6px; height: 6px; background: #dd5a5a; }.m-event-list, .m-notice-list { gap: 0; }.m-event-item { gap: 10px; padding: 10px 0; border-bottom: 1px solid #edf1f5; }.m-event-item:last-child { border-bottom: 0; padding-bottom: 0; }.m-event-dot { width: 7px; height: 7px; margin-top: 5px; }.m-event-body, .m-notice-body { display: flex; flex-direction: column; gap: 3px; }.m-notice-item { padding: 10px 0; border-radius: 0; border-bottom: 1px solid #edf1f5; background: transparent; }.m-notice-item:last-child { border-bottom: 0; padding-bottom: 0; }.m-notice-icon { width: 32px; height: 32px; border-radius: 8px; }
.m-desktop-tip { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 14px; padding: 13px; border: 1px solid #f1dfb2; border-radius: 8px; background: #fffaf0; }.m-desktop-tip-icon { display: grid; width: 34px; height: 34px; place-items: center; flex: 0 0 auto; border-radius: 8px; background: #fff0cc; color: #b47613; }.m-desktop-tip div { min-width: 0; flex: 1; }.m-desktop-tip b { color: #825f25; font-size: 13px; }.m-desktop-tip p { margin: 3px 0 0; color: #997b47; font-size: 11px; line-height: 1.45; }.m-desktop-tip button { display: grid; width: 32px; height: 32px; place-items: center; flex: 0 0 auto; padding: 0; border: 0; border-radius: 8px; background: transparent; color: #a77a30; cursor: pointer; }
.m-bottom-actions { padding-top: 0; }.m-btn { height: 44px; border-radius: 8px; font-size: 14px; }.m-btn-primary { box-shadow: none; }.m-safe-bottom { height: 80px; }
@media (max-width: 360px) { .m-home { padding-left: 12px; padding-right: 12px; }.m-announcement { padding-left: 16px; }.m-announcement-copy { max-width: 65%; }.m-announcement h1 { font-size: 21px; }.m-start-grid, .m-overview-grid { gap: 5px; }.m-overview-item { padding-left: 5px; padding-right: 5px; }.m-overview-item strong { font-size: 18px; }.m-art-card-main { right: 0; }.m-art-card-small { right: 46px; } }
</style>
