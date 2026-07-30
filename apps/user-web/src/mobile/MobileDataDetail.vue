<template>
  <div class="m-data-detail">
    <div v-if="loading" class="m-detail-loading">
      <div class="m-loading-ring"></div>
      正在加载数据详情
    </div>

    <MobileUnavailableState
      v-else-if="loadError"
      title="数据详情暂时无法加载"
      :description="loadError"
      @retry="loadAll"
    />

    <template v-else>
      <section class="m-detail-card m-distribution">
        <div class="m-section-header">
          <div>
            <span class="m-section-kicker">订单处理</span>
            <h2>发货状态分布</h2>
          </div>
          <span class="m-total-value">{{ deliveryTotal }} 笔</span>
        </div>
        <div v-if="hasDistributionData" ref="distributionChartEl" class="m-distribution-chart"></div>
        <div v-else class="m-chart-empty">
          <MIcon name="pieChart" :size="30" />
          <span>暂无可用分布数据</span>
        </div>
        <div class="m-distribution-list">
          <div v-for="item in distributionData" :key="item.name" class="m-distribution-row">
            <span class="m-distribution-name"><i :style="{ background: item.itemStyle.color }"></i>{{ item.name }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </section>

      <section class="m-detail-card m-alert-summary">
        <div class="m-section-header">
          <div>
            <span class="m-section-kicker">待处理事项</span>
            <h2>业务预警</h2>
          </div>
          <MIcon name="alertTriangle" :size="21" />
        </div>
        <div class="m-alert-grid">
          <div class="m-alert-item m-alert-purple">
            <span>AI 预警</span>
            <strong>{{ stats.aiReplyCount }}</strong>
            <small>今日预警</small>
          </div>
          <!-- 处理中：后端 DashboardSummaryVO 暂未提供独立的"告警处理中"计数，
               此处复用 pendingDeliveryCount（待发货）作为"待处理"代理指标 -->
          <div class="m-alert-item m-alert-orange">
            <span>处理中</span>
            <strong>{{ stats.pendingDeliveryCount }}</strong>
            <small>待处理</small>
          </div>
          <!-- 已解决：后端 DashboardSummaryVO 暂未提供独立的"告警已解决"计数，
               此处复用 deliverySuccessCount（发货成功）作为"已处理"代理指标 -->
          <div class="m-alert-item m-alert-red">
            <span>已解决</span>
            <strong>{{ stats.deliverySuccessCount }}</strong>
            <small>已处理</small>
          </div>
        </div>
      </section>

      <section class="m-detail-card m-trend-detail">
        <div class="m-section-header">
          <div>
            <span class="m-section-kicker">销售走势</span>
            <h2>近 {{ trendDays }} 天趋势</h2>
          </div>
          <div class="m-trend-pills">
            <button
              v-for="opt in trendRangeOptions"
              :key="opt.value"
              type="button"
              class="m-trend-pill"
              :class="{ active: trendDays === opt.value }"
              @click="switchTrendRange(opt.value)"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>
        <div v-if="trendHasData" ref="trendChartEl" class="m-trend-chart"></div>
        <div v-else class="m-chart-empty">
          <MIcon name="chart" :size="30" />
          <span>{{ trendError || '暂无趋势数据' }}</span>
        </div>
        <div v-if="trendHasData" class="m-trend-legend">
          <span v-for="series in trendSeries" :key="series.name" class="m-trend-legend-item">
            <i :style="{ background: series.color }"></i>{{ series.name }}
          </span>
        </div>
      </section>

      <section class="m-detail-card m-status-detail">
        <div class="m-section-header">
          <div>
            <span class="m-section-kicker">运行概况</span>
            <h2>当前状态</h2>
          </div>
          <span class="m-status-badge" :class="`is-${sseStatus}`">{{ sseStatusText }}</span>
        </div>
        <div class="m-status-list">
          <div v-for="item in statusItems" :key="item.label" class="m-status-row">
            <div class="m-status-icon" :class="item.tone"><MIcon :name="item.icon" :size="17" /></div>
            <div class="m-status-copy">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
              <div class="m-status-track"><i class="m-status-fill" :style="{ width: `${item.progress}%` }"></i></div>
            </div>
          </div>
        </div>
      </section>

      <section class="m-quick-section">
        <div class="m-section-header">
          <div>
            <span class="m-section-kicker">常用操作</span>
            <h2>快捷入口</h2>
          </div>
        </div>
        <div class="m-quick-grid">
          <button v-for="entry in quickEntries" :key="entry.key" type="button" class="m-quick-entry" @click="emit('navigate', entry.key)">
            <span class="m-quick-icon" :class="entry.tone"><MIcon :name="entry.icon" :size="20" /></span>
            <span>{{ entry.label }}</span>
            <MIcon name="chevronRight" :size="15" />
          </button>
        </div>
      </section>

      <section class="m-detail-card m-events">
        <div class="m-section-header">
          <div>
            <span class="m-section-kicker">实时更新</span>
            <h2>最近事件</h2>
          </div>
          <span class="m-live-badge"><i></i>{{ sseStatusText }}</span>
        </div>
        <div v-if="recentEvents.length" class="m-event-list">
          <div v-for="(event, index) in recentEvents" :key="`${event.type}-${index}`" class="m-event-row">
            <i :class="eventColorClass(event)"></i>
            <div>
              <strong>{{ formatEventText(event) }}</strong>
              <span>{{ formatEventTime(event) }}</span>
            </div>
          </div>
        </div>
        <div v-else class="m-inline-empty">暂无实时事件</div>
      </section>

      <section class="m-detail-card m-notifications">
        <div class="m-section-header">
          <div>
            <span class="m-section-kicker">系统消息</span>
            <h2>最近通知</h2>
          </div>
          <button type="button" class="m-more-button" @click="emit('navigate', 'messages')">全部</button>
        </div>
        <div v-if="notifications.length" class="m-notice-list">
          <div v-for="(notice, index) in notifications" :key="notice.id || index" class="m-notice-row">
            <div class="m-notice-icon"><MIcon name="messageCircle" :size="16" /></div>
            <div>
              <strong>{{ notice.title || '系统通知' }}</strong>
              <span>{{ notice.content || notice.message || notice.description || '暂无详情' }}</span>
            </div>
          </div>
        </div>
        <div v-else class="m-inline-empty">{{ notificationsError || '暂无通知' }}</div>
      </section>
    </template>

    <div class="m-safe-bottom"></div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import * as echarts from 'echarts/core'
import { PieChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getDashboardSummary, getDashboardSalesTrend } from '../api/dashboard.js'
import { getNavigationNotifications } from '../api/navigation.js'
import { recordsOfOrThrow } from '../utils/apiData.js'
import { getSseStatus } from '../utils/sse.js'
import MIcon from './MIcon.vue'
import MobileUnavailableState from './MobileUnavailableState.vue'

echarts.use([PieChart, LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

const emit = defineEmits(['navigate', 'force-desktop', 'back'])
const loading = ref(true)
const loadError = ref('')
const notificationsError = ref('')
const notifications = ref([])
const recentEvents = ref([])
const sseStatus = ref(getSseStatus())
const distributionChartEl = ref(null)
const trendChartEl = ref(null)
let distributionChart = null
let trendChart = null

// 销售趋势时间范围切换器：7天 / 14天 / 30天，对齐 PC 端 DataPage.vue 的可选项
const trendRangeOptions = [
  { label: '7天', value: 7 },
  { label: '14天', value: 14 },
  { label: '30天', value: 30 }
]
const trendDays = ref(7)
const trendError = ref('')
const trend = ref({
  dates: [],
  deliverySuccess: [],
  deliveryFail: [],
  aiReply: []
})

const stats = reactive({
  deliverySuccessCount: 0,
  deliveryFailCount: 0,
  pendingDeliveryCount: 0,
  itemCount: 0,
  sellingGoodsCount: 0,
  aiReplyCount: 0,
  wsOnlineRate: null,
  todayOrderCount: 0
})

const distributionData = computed(() => [
  { name: '发货成功', value: Number(stats.deliverySuccessCount) || 0, itemStyle: { color: '#16bf78' } },
  { name: '发货失败', value: Number(stats.deliveryFailCount) || 0, itemStyle: { color: '#ef4444' } },
  { name: '待发货', value: Number(stats.pendingDeliveryCount) || 0, itemStyle: { color: '#ff9f22' } }
])

const deliveryTotal = computed(() => distributionData.value.reduce((total, item) => total + item.value, 0))
const hasDistributionData = computed(() => deliveryTotal.value > 0)
const sseStatusText = computed(() => {
  if (sseStatus.value === 'connected') return '实时连接正常'
  if (sseStatus.value === 'connecting' || sseStatus.value === 'reconnecting') return '正在连接'
  return '实时连接暂不可用'
})
const deliverySuccessRate = computed(() => {
  const total = deliveryTotal.value
  return total > 0 ? (Number(stats.deliverySuccessCount) || 0) / total * 100 : 0
})
// WS 在线率：后端 DashboardSummaryVO 已直接返回 wsOnlineRate（0-100），无需前端再统计
const wsOnlineRateValue = computed(() => {
  if (stats.wsOnlineRate === null || stats.wsOnlineRate === undefined) return '--'
  return `${Math.round(Number(stats.wsOnlineRate) || 0)}%`
})
const wsOnlineRateProgress = computed(() => {
  if (stats.wsOnlineRate === null || stats.wsOnlineRate === undefined) return 0
  return Math.min(100, Math.max(0, Math.round(Number(stats.wsOnlineRate) || 0)))
})
// 商品在售率：sellingGoodsCount / goodsCount * 100，作为商品数量进度条的填充比例
const goodsSellingRate = computed(() => {
  const total = Number(stats.itemCount) || 0
  const selling = Number(stats.sellingGoodsCount) || 0
  if (total <= 0) return 0
  return Math.min(100, Math.round((selling / total) * 100))
})
// AI 预警数进度：以 aiReplyCount 占今日订单+AI回复基数的比例作为视觉填充
const aiAlertProgress = computed(() => {
  const orders = Number(stats.todayOrderCount) || 0
  const replies = Number(stats.aiReplyCount) || 0
  const base = Math.max(orders + replies, 1)
  return Math.min(100, Math.round((replies / base) * 100))
})
const statusItems = computed(() => [
  { label: '发货成功率', value: deliveryTotal.value > 0 ? `${deliverySuccessRate.value.toFixed(1)}%` : '--', progress: deliverySuccessRate.value, icon: 'pieChart', tone: 'green' },
  { label: '商品数量', value: stats.itemCount, progress: goodsSellingRate.value, icon: 'bag', tone: 'blue' },
  { label: 'WS在线率', value: wsOnlineRateValue.value, progress: wsOnlineRateProgress.value, icon: 'chart', tone: 'orange' },
  { label: 'AI预警数', value: stats.aiReplyCount, progress: aiAlertProgress.value, icon: 'bot', tone: 'purple' }
])

// 销售趋势图系列配置（复用 MobileData.vue 的配色风格）
const trendSeries = [
  { name: '发货成功', color: '#16bf78', key: 'deliverySuccess' },
  { name: '发货失败', color: '#ef4444', key: 'deliveryFail' },
  { name: 'AI 回复', color: '#8b5cf6', key: 'aiReply' }
]
const trendHasData = computed(() => {
  const arr = trend.value.deliverySuccess || []
  return arr.length > 0 && arr.some(v => Number(v) > 0)
})
const quickEntries = [
  { key: 'accounts', label: '账号管理', icon: 'user', tone: 'blue' },
  { key: 'products', label: '商品管理', icon: 'bag', tone: 'green' },
  { key: 'orders', label: '订单管理', icon: 'list', tone: 'orange' },
  { key: 'auto-delivery', label: '自动发货', icon: 'gift', tone: 'purple' },
  { key: 'data', label: '数据统计', icon: 'chart', tone: 'blue' },
  { key: 'card-keys', label: '卡密管理', icon: 'key', tone: 'orange' }
]

function updateDistributionChart() {
  if (!distributionChart || !hasDistributionData.value) return
  distributionChart.setOption({
    tooltip: {
      trigger: 'item',
      formatter: '{b}<br/><strong>{c}</strong> 笔 ({d}%)'
    },
    legend: { show: false },
    series: [{
      type: 'pie',
      radius: ['58%', '78%'],
      center: ['50%', '50%'],
      avoidLabelOverlap: true,
      itemStyle: { borderColor: '#fff', borderWidth: 4, borderRadius: 5 },
      label: { show: false },
      emphasis: { scale: true, scaleSize: 7 },
      data: distributionData.value
    }],
    graphic: [{
      type: 'text',
      left: 'center',
      top: '40%',
      style: { text: `${deliveryTotal.value}\n处理订单`, textAlign: 'center', fill: '#15213d', fontSize: 19, fontWeight: 700, lineHeight: 27 }
    }]
  }, true)
}

function initDistributionChart() {
  if (!distributionChartEl.value || !hasDistributionData.value) return
  distributionChart?.dispose()
  distributionChart = echarts.init(distributionChartEl.value, null, { renderer: 'canvas' })
  updateDistributionChart()
}

// 销售趋势折线图：复用 MobileData.vue 的 tooltip + 渐变填充风格
function initTrendChart() {
  if (!trendChartEl.value || !trendHasData.value) return
  trendChart?.dispose()
  trendChart = echarts.init(trendChartEl.value, null, { renderer: 'canvas' })
  updateTrendChart()
}

function updateTrendChart() {
  if (!trendChart || !trendHasData.value) return
  const dates = trend.value.dates || []
  const labels = dates.map(d => {
    const s = String(d || '')
    return s.length >= 5 ? s.slice(5) : s
  })
  const seriesData = trendSeries.map(series => ({
    ...series,
    data: (trend.value[series.key] || []).map(value => Number(value) || 0)
  }))
  trendChart.setOption({
    grid: { left: 8, right: 12, top: 20, bottom: 28, containLabel: true },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(21, 33, 61, 0.96)',
      borderColor: 'rgba(255,255,255,0.08)',
      borderWidth: 1,
      borderRadius: 16,
      padding: [14, 18],
      textStyle: { color: '#fff', fontSize: 12 },
      axisPointer: {
        type: 'line',
        lineStyle: { color: 'rgba(13, 107, 255, 0.3)', width: 2, type: 'dashed' },
        shadowStyle: { color: 'rgba(13, 107, 255, 0.06)' }
      },
      formatter: function(params) {
        const lines = params.map(item => `<div style="display:flex;align-items:center;gap:8px;margin-top:6px">
          <span style="width:8px;height:8px;border-radius:50%;background:${item.color};display:inline-block"></span>
          <span style="color:rgba(255,255,255,0.8)">${item.seriesName}</span>
          <span style="font-weight:700;margin-left:auto;font-size:14px;color:#fff">${item.value}<span style="font-size:11px;font-weight:500;color:rgba(255,255,255,0.6);margin-left:2px">次</span></span>
        </div>`).join('')
        return `<div style="font-weight:600;margin-bottom:8px;font-size:13px">${params[0]?.axisValue || ''}</div>${lines}`
      }
    },
    xAxis: {
      type: 'category',
      data: labels,
      boundaryGap: false,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#8c98ae', fontSize: 11, margin: 12, fontWeight: 500 }
    },
    yAxis: { type: 'value', show: false, min: 0, splitLine: { show: false } },
    series: seriesData.map((series, index) => ({
      name: series.name,
      type: 'line',
      data: series.data,
      smooth: true,
      smoothMonotone: 'x',
      symbol: 'circle',
      symbolSize: 5,
      showSymbol: series.data.length <= 7,
      lineStyle: { color: series.color, width: index === 0 ? 3 : 2.5 },
      itemStyle: { color: series.color, borderColor: '#fff', borderWidth: 2 },
      areaStyle: index === 0 ? {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(22, 191, 120, 0.24)' },
          { offset: 1, color: 'rgba(22, 191, 120, 0.01)' }
        ])
      } : undefined,
      emphasis: {
        focus: 'series',
        scale: true,
        itemStyle: { color: series.color, borderColor: '#fff', borderWidth: 3 }
      }
    }))
  }, true)
}

function resizeChart() {
  distributionChart?.resize()
  trendChart?.resize()
}

async function loadSummary() {
  const response = await getDashboardSummary({ date: 'today' })
  const data = response?.data
  if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('数据概览响应格式异常')
  Object.assign(stats, {
    deliverySuccessCount: Number(data.deliverySuccessCount) || 0,
    deliveryFailCount: Number(data.deliveryFailCount) || 0,
    pendingDeliveryCount: Number(data.pendingDeliveryCount) || 0,
    itemCount: Number(data.goodsCount) || 0,
    sellingGoodsCount: Number(data.sellingGoodsCount) || 0,
    aiReplyCount: Number(data.autoReplyCount ?? data.aiReplyCount) || 0,
    wsOnlineRate: data.wsOnlineRate === null || data.wsOnlineRate === undefined ? null : Number(data.wsOnlineRate),
    todayOrderCount: Number(data.todayOrderCount ?? data.orderCount) || 0
  })
}

async function loadTrend() {
  const response = await getDashboardSalesTrend({ days: trendDays.value })
  const data = response?.data
  if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('趋势数据响应格式异常')
  const dates = data.dates
  if (!Array.isArray(dates)) throw new Error('趋势数据响应格式异常')
  const deliverySuccess = data.deliverySuccess || data.series?.deliverySuccess || []
  const deliveryFail = data.deliveryFail || data.series?.deliveryFail || new Array(dates.length).fill(0)
  const aiReply = data.aiReplyCount || data.aiReply || data.autoReply || data.series?.aiReply || new Array(dates.length).fill(0)
  trend.value = {
    dates: dates.slice(-trendDays.value),
    deliverySuccess: (Array.isArray(deliverySuccess) ? deliverySuccess : []).slice(-trendDays.value),
    deliveryFail: (Array.isArray(deliveryFail) ? deliveryFail : []).slice(-trendDays.value),
    aiReply: (Array.isArray(aiReply) ? aiReply : []).slice(-trendDays.value)
  }
}

async function loadNotifications() {
  notificationsError.value = ''
  const response = await getNavigationNotifications({ limit: 3 })
  notifications.value = recordsOfOrThrow(response?.data, '最近通知响应格式异常').slice(0, 3)
}

async function loadAll() {
  loading.value = true
  loadError.value = ''
  notificationsError.value = ''
  trendError.value = ''
  const [summaryResult, trendResult, notificationsResult] = await Promise.allSettled([
    loadSummary(),
    loadTrend(),
    loadNotifications()
  ])
  if (summaryResult.status === 'rejected') {
    loadError.value = summaryResult.reason?.message || '请检查网络连接后重试。'
  }
  if (trendResult.status === 'rejected') {
    trend.value = { dates: [], deliverySuccess: [], deliveryFail: [], aiReply: [] }
    trendError.value = trendResult.reason?.message || '趋势数据加载失败'
  }
  if (notificationsResult.status === 'rejected') {
    notifications.value = []
    notificationsError.value = notificationsResult.reason?.message || '通知暂时无法加载'
  }
  loading.value = false
  await nextTick()
  initDistributionChart()
  initTrendChart()
}

async function switchTrendRange(days) {
  if (trendDays.value === days) return
  trendDays.value = days
  trendError.value = ''
  await loadTrend().catch(error => {
    trendError.value = error?.message || '趋势数据加载失败'
  })
  await nextTick()
  if (!trendChart && trendHasData.value) {
    initTrendChart()
  } else {
    updateTrendChart()
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
  if (recentEvents.value.length > 3) recentEvents.value.length = 3
}

function onSseStatus(event) {
  sseStatus.value = String(event?.detail || 'disconnected')
}

function formatEventText(event) {
  if (event.message) return event.message
  const type = event.type || ''
  const direction = String(event.direction || '').toUpperCase()
  if (type === 'message') return direction === 'OUT' ? '消息已发送' : '收到新消息'
  if (type.includes('cookie')) return 'Cookie 状态已更新'
  if (type.includes('account')) return '账号状态变更'
  if (type.includes('delivery')) return '自动发货通知'
  if (type.includes('workflow')) return '工作流执行通知'
  return type || '系统通知'
}

function formatEventTime(event) {
  const date = event.time instanceof Date ? event.time : new Date(event.time)
  const seconds = (Date.now() - date.getTime()) / 1000
  if (seconds < 60) return '刚刚'
  if (seconds < 3600) return `${Math.floor(seconds / 60)}分钟前`
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function eventColorClass(event) {
  const type = event.type || ''
  if (type === 'message') return 'm-dot-blue'
  if (type.includes('error') || type.includes('fail')) return 'm-dot-red'
  if (type.includes('success') || type.includes('delivery')) return 'm-dot-green'
  return 'm-dot-gray'
}

onMounted(() => {
  loadAll()
  window.addEventListener('resize', resizeChart)
  window.addEventListener('xya-sse-event', onSseEvent)
  window.addEventListener('xya-sse-status', onSseStatus)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)
  window.removeEventListener('xya-sse-event', onSseEvent)
  window.removeEventListener('xya-sse-status', onSseStatus)
  distributionChart?.dispose()
  distributionChart = null
  trendChart?.dispose()
  trendChart = null
})
</script>

<style scoped>
.m-data-detail {
  width: 100%;
  min-width: 0;
  padding: var(--m-space-3) var(--m-space-4) 0;
  box-sizing: border-box;
  overflow-x: clip;
}

.m-detail-loading,
.m-chart-empty,
.m-inline-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-body-sm);
}

.m-detail-loading {
  min-height: 280px;
  flex-direction: column;
  gap: var(--m-space-3);
}

.m-loading-ring {
  width: 28px;
  height: 28px;
  border: 3px solid var(--m-color-primary-bg);
  border-top-color: var(--m-color-primary);
  border-radius: var(--m-radius-circle);
  animation: m-detail-spin 0.8s linear infinite;
}

@keyframes m-detail-spin {
  to { transform: rotate(360deg); }
}

.m-detail-card,
.m-quick-section {
  margin-bottom: var(--m-space-4);
  padding: var(--m-space-4);
  border-radius: var(--m-radius-xl);
  background: var(--m-color-bg-card);
  box-shadow: var(--m-shadow-xs);
}

.m-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--m-space-3);
  margin-bottom: var(--m-space-4);
}

.m-section-header h2 {
  margin: var(--m-space-1) 0 0;
  color: var(--m-color-text-primary);
  font-size: var(--m-font-size-h2);
  line-height: var(--m-line-height-tight);
}

.m-section-kicker {
  color: var(--m-color-primary);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-bold);
}

.m-total-value {
  color: var(--m-color-primary);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-bold);
}

.m-distribution-chart {
  height: 190px;
  min-width: 0;
}

.m-chart-empty {
  height: 190px;
  flex-direction: column;
  gap: var(--m-space-2);
  color: var(--m-color-text-tertiary);
}

.m-distribution-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--m-space-2);
  padding-top: var(--m-space-2);
  border-top: 1px solid var(--m-color-border-light);
}

.m-distribution-row {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--m-space-1);
}

.m-distribution-name {
  overflow: hidden;
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-caption);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.m-distribution-name i {
  display: inline-block;
  width: 7px;
  height: 7px;
  margin-right: var(--m-space-1);
  border-radius: var(--m-radius-circle);
}

.m-distribution-row strong {
  color: var(--m-color-text-primary);
  font-size: var(--m-font-size-h2);
}

.m-trend-detail .m-section-header {
  gap: var(--m-space-2);
  flex-wrap: wrap;
}

.m-trend-pills {
  display: inline-flex;
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-lg);
  padding: 3px;
  gap: var(--m-space-1);
}

.m-trend-pill {
  border: 0;
  background: transparent;
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-semibold);
  padding: var(--m-space-1) var(--m-space-3);
  border-radius: var(--m-radius-lg);
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
}

.m-trend-pill.active {
  background: var(--m-color-bg-card);
  color: var(--m-color-primary);
  box-shadow: var(--m-shadow-xs);
  font-weight: var(--m-font-weight-bold);
}

.m-trend-chart {
  height: 200px;
  min-width: 0;
}

.m-trend-legend {
  display: flex;
  flex-wrap: wrap;
  gap: var(--m-space-3);
  padding: var(--m-space-2) 2px 0;
}

.m-trend-legend-item {
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-1);
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-caption);
}

.m-trend-legend-item i {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: var(--m-radius-circle);
}

.m-alert-summary > .m-section-header > :deep(svg) {
  color: var(--m-color-warning-text);
}

.m-alert-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--m-space-2);
}

.m-alert-item {
  min-width: 0;
  padding: var(--m-space-3) var(--m-space-2);
  border-radius: var(--m-radius-md);
}

.m-alert-item span,
.m-alert-item small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.m-alert-item span {
  color: var(--m-color-text-secondary);
  font-size: var(--m-font-size-caption);
}

.m-alert-item strong {
  display: block;
  margin: var(--m-space-2) 0 var(--m-space-1);
  color: var(--m-color-text-primary);
  font-size: var(--m-font-size-h1);
  line-height: 1;
}

.m-alert-item small {
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-tiny);
}

.m-alert-orange { background: var(--m-color-warning-bg); }
.m-alert-red { background: var(--m-color-danger-bg); }
.m-alert-purple { background: var(--m-color-purple-bg); }

.m-status-badge {
  padding: var(--m-space-1) var(--m-space-2);
  border-radius: var(--m-radius-pill);
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-semibold);
}

.m-status-badge.is-connected {
  background: var(--m-color-success-bg);
  color: var(--m-color-success-text);
}

.m-status-badge.is-connecting,
.m-status-badge.is-reconnecting {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning-text);
}

.m-status-list {
  display: flex;
  flex-direction: column;
}

.m-status-row {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: var(--m-space-3);
  padding: var(--m-space-3) 0;
  border-bottom: 1px solid var(--m-color-border-light);
}

.m-status-row:last-child {
  padding-bottom: 0;
  border-bottom: 0;
}

.m-status-copy {
  display: grid;
  flex: 1;
  min-width: 0;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--m-space-1) var(--m-space-3);
}

.m-status-copy > span {
  overflow: hidden;
  color: var(--m-color-text-secondary);
  font-size: var(--m-font-size-body-sm);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.m-status-copy strong {
  color: var(--m-color-text-primary);
  font-size: var(--m-font-size-h3);
}

.m-status-track {
  grid-column: 1 / -1;
  height: var(--m-space-1);
  overflow: hidden;
  border-radius: var(--m-radius-pill);
  background: var(--m-color-border-light);
}

.m-status-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--m-color-success);
  transition: width 0.2s ease;
}

.m-status-icon {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  flex: 0 0 auto;
  border-radius: var(--m-radius-md);
}

.m-status-icon.blue,
.m-quick-icon.blue {
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
}

.m-status-icon.orange,
.m-quick-icon.orange {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning-text);
}

.m-status-icon.purple,
.m-quick-icon.purple {
  background: var(--m-color-purple-bg);
  color: var(--m-color-purple);
}

.m-status-icon.green,
.m-quick-icon.green {
  background: var(--m-color-success-bg);
  color: var(--m-color-success-text);
}

.m-quick-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--m-space-3);
}

.m-quick-entry {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  min-width: 0;
  gap: var(--m-space-2);
  padding: var(--m-space-3);
  border-radius: var(--m-radius-lg);
  background: var(--m-color-bg-card);
  box-shadow: var(--m-shadow-xs);
  color: var(--m-color-text-secondary);
  font: inherit;
  font-size: var(--m-font-size-caption);
  text-align: left;
  cursor: pointer;
}

.m-quick-entry:active {
  background: var(--m-color-bg-hover);
}

.m-quick-entry > span:nth-child(2) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.m-quick-entry > :deep(svg) {
  color: var(--m-color-text-tertiary);
}

.m-quick-icon {
  display: grid;
  width: 36px;
  height: 36px;
  place-items: center;
  border-radius: var(--m-radius-md);
}

.m-live-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-1);
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-caption);
}

.m-live-badge i {
  width: 6px;
  height: 6px;
  border-radius: var(--m-radius-circle);
  background: var(--m-color-text-disabled);
}

.m-events:has(.m-event-list) .m-live-badge i {
  background: var(--m-color-success);
}

.m-event-list,
.m-notice-list {
  display: flex;
  flex-direction: column;
}

.m-event-row,
.m-notice-row {
  display: flex;
  gap: var(--m-space-3);
  min-width: 0;
  padding: var(--m-space-3) 0;
  border-bottom: 1px solid var(--m-color-border-light);
}

.m-event-row:last-child,
.m-notice-row:last-child {
  padding-bottom: 0;
  border-bottom: 0;
}

.m-event-row > i {
  width: 7px;
  height: 7px;
  margin-top: var(--m-space-1);
  flex: 0 0 auto;
  border-radius: var(--m-radius-circle);
}

.m-dot-blue { background: var(--m-color-primary); }
.m-dot-red { background: var(--m-color-danger); }
.m-dot-green { background: var(--m-color-success); }
.m-dot-gray { background: var(--m-color-text-disabled); }

.m-event-row div,
.m-notice-row div:last-child {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: var(--m-space-1);
}

.m-event-row strong,
.m-notice-row strong {
  overflow: hidden;
  color: var(--m-color-text-primary);
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.m-event-row span,
.m-notice-row span {
  overflow: hidden;
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-caption);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.m-notice-icon {
  display: grid;
  width: 32px;
  height: 32px;
  place-items: center;
  flex: 0 0 auto;
  border-radius: var(--m-radius-md);
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
}

.m-more-button {
  border: 0;
  background: var(--m-color-bg-subtle);
  color: var(--m-color-primary);
  font-size: var(--m-font-size-caption);
  padding: var(--m-space-1) var(--m-space-3);
  border-radius: var(--m-radius-lg);
  cursor: pointer;
}

.m-inline-empty {
  min-height: 56px;
  border-top: 1px solid var(--m-color-border-light);
  color: var(--m-color-text-tertiary);
}

.m-safe-bottom {
  height: calc(var(--m-space-8) + var(--m-space-1) + var(--m-safe-area-bottom));
}

@media (max-width: 360px) {
  .m-data-detail {
    padding-left: var(--m-space-3);
    padding-right: var(--m-space-3);
  }
  .m-detail-card,
  .m-quick-section {
    padding: var(--m-space-4);
  }
  .m-alert-grid {
    gap: var(--m-space-1);
  }
  .m-alert-item {
    padding: var(--m-space-3) var(--m-space-2);
  }
  .m-alert-item strong {
    font-size: var(--m-font-size-h2);
  }
  .m-distribution-list {
    gap: var(--m-space-1);
  }
}
</style>
