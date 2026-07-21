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
.m-data-detail { width: 100%; min-width: 0; padding: 12px 14px 0; box-sizing: border-box; overflow-x: clip; }
.m-detail-loading, .m-chart-empty, .m-inline-empty { display: flex; align-items: center; justify-content: center; color: #7c8ca2; font-size: 13px; }
.m-detail-loading { min-height: 280px; flex-direction: column; gap: 12px; }
.m-loading-ring { width: 28px; height: 28px; border: 3px solid #dceafa; border-top-color: #1674d1; border-radius: 50%; animation: m-detail-spin .8s linear infinite; }
@keyframes m-detail-spin { to { transform: rotate(360deg); } }
.m-detail-card, .m-quick-section { margin-bottom: 14px; padding: 16px; border: 1px solid #e3eaf3; border-radius: 8px; background: #fff; box-shadow: 0 2px 7px rgba(33, 60, 97, .04); }
.m-section-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
.m-section-header h2 { margin: 2px 0 0; color: #20344e; font-size: 17px; line-height: 1.2; }
.m-section-kicker { color: #2878c8; font-size: 11px; font-weight: 700; }
.m-total-value { color: #2878c8; font-size: 12px; font-weight: 700; }
.m-distribution-chart { height: 190px; min-width: 0; }
.m-chart-empty { height: 190px; flex-direction: column; gap: 8px; color: #9ba8b9; }
.m-distribution-list { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; padding-top: 8px; border-top: 1px solid #edf1f5; }
.m-distribution-row { min-width: 0; display: flex; flex-direction: column; gap: 5px; }
.m-distribution-name { overflow: hidden; color: #8190a3; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.m-distribution-name i { display: inline-block; width: 7px; height: 7px; margin-right: 4px; border-radius: 50%; }
.m-distribution-row strong { color: #20344e; font-size: 18px; }
.m-trend-detail .m-section-header { gap: 8px; flex-wrap: wrap; }
.m-trend-pills { display: inline-flex; background: #f2f5fa; border-radius: 8px; padding: 3px; gap: 2px; }
.m-trend-pill { border: 0; background: transparent; color: #7c8ca2; font-size: 11px; font-weight: 600; padding: 5px 10px; border-radius: 6px; cursor: pointer; transition: background .2s, color .2s; }
.m-trend-pill.active { background: #fff; color: #1674d1; box-shadow: 0 1px 3px rgba(22,116,209,.12); font-weight: 700; }
.m-trend-chart { height: 200px; min-width: 0; }
.m-trend-legend { display: flex; flex-wrap: wrap; gap: 12px; padding: 8px 2px 0; }
.m-trend-legend-item { display: inline-flex; align-items: center; gap: 5px; color: #7c8ca2; font-size: 11px; }
.m-trend-legend-item i { display: inline-block; width: 7px; height: 7px; border-radius: 50%; }
.m-alert-summary > .m-section-header > :deep(svg) { color: #df8a18; }
.m-alert-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.m-alert-item { min-width: 0; padding: 11px 9px; border-radius: 8px; }
.m-alert-item span, .m-alert-item small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.m-alert-item span { color: #687b92; font-size: 11px; }.m-alert-item strong { display: block; margin: 7px 0 3px; color: #20344e; font-size: 22px; line-height: 1; }.m-alert-item small { color: #8998aa; font-size: 10px; }
.m-alert-orange { background: #fff6e9; }.m-alert-red { background: #fff0f0; }.m-alert-purple { background: #f3efff; }
.m-status-badge { padding: 5px 8px; border-radius: 999px; background: #f2f4f7; color: #7b8798; font-size: 11px; font-weight: 600; }.m-status-badge.is-connected { background: #e8f8ee; color: #168b59; }.m-status-badge.is-connecting, .m-status-badge.is-reconnecting { background: #fff5df; color: #bc7915; }
.m-status-list { display: flex; flex-direction: column; }.m-status-row { display: flex; align-items: center; min-width: 0; gap: 10px; padding: 10px 0; border-bottom: 1px solid #edf1f5; }.m-status-row:last-child { padding-bottom: 0; border-bottom: 0; }.m-status-copy { display: grid; flex: 1; min-width: 0; grid-template-columns: minmax(0, 1fr) auto; gap: 4px 10px; }.m-status-copy > span { overflow: hidden; color: #53677f; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }.m-status-copy strong { color: #20344e; font-size: 15px; }.m-status-track { grid-column: 1 / -1; height: 4px; overflow: hidden; border-radius: 999px; background: #edf1f5; }.m-status-fill { display: block; height: 100%; border-radius: inherit; background: #16bf78; transition: width .2s ease; }
.m-status-icon { display: grid; width: 34px; height: 34px; place-items: center; flex: 0 0 auto; border-radius: 8px; }.m-status-icon.blue, .m-quick-icon.blue { background: #e6f1ff; color: #1774d0; }.m-status-icon.orange, .m-quick-icon.orange { background: #fff2df; color: #d98012; }.m-status-icon.purple, .m-quick-icon.purple { background: #f0eaff; color: #7655ca; }.m-status-icon.green, .m-quick-icon.green { background: #e4f8ee; color: #168b59; }
.m-quick-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }.m-quick-entry { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; min-width: 0; gap: 8px; padding: 11px; border: 1px solid #e9eff6; border-radius: 8px; background: #fff; color: #334963; font: inherit; font-size: 12px; text-align: left; cursor: pointer; }.m-quick-entry:active { background: #f6f9fd; }.m-quick-entry > span:nth-child(2) { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.m-quick-entry > :deep(svg) { color: #a8b4c3; }.m-quick-icon { display: grid; width: 36px; height: 36px; place-items: center; border-radius: 8px; }
.m-live-badge { display: inline-flex; align-items: center; gap: 5px; color: #7e8b9d; font-size: 11px; }.m-live-badge i { width: 6px; height: 6px; border-radius: 50%; background: #b3bdc9; }.m-events:has(.m-event-list) .m-live-badge i { background: #24a568; }
.m-event-list, .m-notice-list { display: flex; flex-direction: column; }.m-event-row, .m-notice-row { display: flex; gap: 10px; min-width: 0; padding: 10px 0; border-bottom: 1px solid #edf1f5; }.m-event-row:last-child, .m-notice-row:last-child { padding-bottom: 0; border-bottom: 0; }.m-event-row > i { width: 7px; height: 7px; margin-top: 5px; flex: 0 0 auto; border-radius: 50%; }.m-dot-blue { background: #1774d0; }.m-dot-red { background: #df5757; }.m-dot-green { background: #1a9a64; }.m-dot-gray { background: #a9b4c2; }.m-event-row div, .m-notice-row div:last-child { display: flex; min-width: 0; flex: 1; flex-direction: column; gap: 3px; }.m-event-row strong, .m-notice-row strong { overflow: hidden; color: #30465f; font-size: 13px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }.m-event-row span, .m-notice-row span { overflow: hidden; color: #8998aa; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.m-notice-icon { display: grid; width: 32px; height: 32px; place-items: center; flex: 0 0 auto; border-radius: 8px; background: #e6f1ff; color: #1774d0; }.m-more-button { border: 0; background: transparent; color: #2878c8; font-size: 12px; cursor: pointer; }.m-inline-empty { min-height: 56px; border-top: 1px solid #edf1f5; color: #9aa7b8; }
.m-safe-bottom { height: calc(36px + env(safe-area-inset-bottom)); }
@media (max-width: 360px) { .m-data-detail { padding-left: 12px; padding-right: 12px; }.m-detail-card, .m-quick-section { padding: 14px; }.m-alert-grid { gap: 5px; }.m-alert-item { padding: 10px 6px; }.m-alert-item strong { font-size: 19px; }.m-distribution-list { gap: 5px; } }
</style>
