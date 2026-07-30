<template>
  <div class="m-data">
    <!-- ============ 顶部 Hero：6 大数据概览 ============ -->
    <section class="m-data-hero">
      <div class="m-data-hero-head">
        <div class="m-data-hero-badge">
          <span class="m-data-hero-dot"></span>
          <span>实时数据</span>
        </div>
        <h1 class="m-data-hero-title">数据面板</h1>
        <p class="m-data-hero-sub">更新于 {{ updatedAt }} · 今日汇总</p>
      </div>

      <!-- KPI 加载骨架 -->
      <div v-if="statsLoading" class="m-data-kpi-skeleton">
        <div v-for="i in 6" :key="i" class="m-skel-cell"></div>
      </div>

      <!-- KPI 错误 -->
      <MobileUnavailableState
        v-else-if="statsError"
        compact
        title="数据概览加载失败"
        :description="statsError"
        @retry="loadSummary"
      />

      <!-- 6 大指标网格 -->
      <div v-else class="m-data-kpi-grid">
        <div
          v-for="kpi in kpiList"
          :key="kpi.key"
          class="m-data-kpi-card"
          :class="`m-data-kpi-card--${kpi.key}`"
        >
          <div class="m-data-kpi-icon" :class="`m-data-kpi-icon--${kpi.key}`">
            <MIcon :name="kpi.icon" :size="18" />
          </div>
          <div class="m-data-kpi-value" :class="`m-data-kpi-value--${kpi.key}`">{{ kpi.display }}</div>
          <div class="m-data-kpi-label">{{ kpi.label }}</div>
          <div v-if="kpi.sub" class="m-data-kpi-sub">{{ kpi.sub }}</div>
        </div>
      </div>

      <!-- 日期范围 tabs（影响趋势图） -->
      <div class="m-data-date-tabs">
        <button
          v-for="tab in dateTabs"
          :key="tab.value"
          class="m-data-date-tab"
          :class="{ active: trendDays === tab.value }"
          @click="switchRange(tab.value)"
        >
          {{ tab.label }}
        </button>
      </div>
    </section>

    <!-- ============ 趋势分析 ============ -->
    <section class="m-data-card">
      <div class="m-data-card-header">
        <div class="m-data-card-title-wrap">
          <div class="m-data-card-title-icon m-data-title-icon--primary">
            <MIcon name="trendingUp" :size="18" />
          </div>
          <h2 class="m-data-card-title">趋势分析</h2>
          <span class="m-data-card-hint">近 {{ trendDays }} 天走势</span>
        </div>
        <button
          v-if="!trendLoading"
          class="m-data-card-refresh"
          aria-label="刷新趋势"
          @click="loadTrend"
        >
          <MIcon name="refreshCw" :size="14" />
        </button>
      </div>

      <!-- 趋势 tab 切换 -->
      <div class="m-data-trend-tabs">
        <button
          v-for="tab in trendTabs"
          :key="tab.value"
          class="m-data-trend-tab"
          :class="{ active: activeTrend === tab.value }"
          @click="switchTrend(tab.value)"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- 图表区 -->
      <div v-if="trendLoading" class="m-data-chart-loading">
        <div class="m-data-spinner"></div>
        <span>趋势加载中…</span>
      </div>
      <div v-else-if="trendError" class="m-data-chart-error" @click="loadTrend">
        <MIcon name="alertCircle" :size="20" />
        <span>趋势加载失败，点击重试</span>
      </div>
      <template v-else>
        <div v-if="currentTrendHasData" ref="trendChartEl" class="m-data-echart-box"></div>
        <MEmpty v-else inline icon="trend" title="暂无趋势数据" desc="开启运营后将自动统计" />
      </template>

      <!-- 图例 + 总量 -->
      <div v-if="!trendLoading && !trendError && currentTrendHasData" class="m-data-trend-legend">
        <div v-for="series in currentTrendSeries" :key="series.name" class="m-data-trend-legend-item">
          <i :style="{ background: series.color }"></i>
          <span class="m-data-trend-legend-name">{{ series.name }}</span>
          <strong class="m-data-trend-legend-total">{{ series.total }}</strong>
        </div>
        <div v-if="trendDays === 30" class="m-data-trend-hint">
          <MIcon name="activity" :size="12" />
          <span>左右滑动查看完整趋势</span>
        </div>
      </div>
    </section>

    <div class="m-data-safe-bottom"></div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import MIcon from './MIcon.vue'
import MobileUnavailableState from './MobileUnavailableState.vue'
import MEmpty from './components/MEmpty.vue'
import { getDashboardSummary, getDashboardSalesTrend, getDashboardOrderMessageTrend } from '../api/dashboard.js'

defineEmits(['navigate', 'force-desktop', 'back'])

// ===== ECharts 按需引入 =====
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, DataZoomComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, GridComponent, TooltipComponent, DataZoomComponent, CanvasRenderer])

// ===== 静态配置 =====
const dateTabs = [
  { label: '近7天', value: 7 },
  { label: '近30天', value: 30 }
]

const trendTabs = [
  { label: '订单', value: 'order' },
  { label: '消息', value: 'message' },
  { label: '发货', value: 'delivery' },
  { label: 'AI回复', value: 'aiReply' }
]

// ===== 状态 =====
const statsLoading = ref(true)
const statsError = ref('')
const trendLoading = ref(true)
const trendError = ref('')
const trendDays = ref(7)
const activeTrend = ref('order')
const trendChartEl = ref(null)
let trendChart = null

const stats = reactive({
  todayOrderCount: 0,
  todaySalesAmount: 0,
  goodsCount: 0,
  sellingGoodsCount: 0,
  messageCount: 0,
  deliverySuccessCount: 0,
  deliveryFailCount: 0,
  pendingDeliveryCount: 0,
  autoReplyCount: 0,
  totalSoldCount: 0,
  accountCount: 0
})

// 趋势数据：分别来自 order-message-trend 和 sales-trend
const orderMsgTrend = ref(null)  // { dates, orderCount, messageCount }
const salesTrend = ref(null)     // { dates, deliverySuccess, deliveryFail, aiReplyCount }

// ===== 派生：更新时间 =====
const updatedAt = computed(() => {
  const now = new Date()
  return `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
})

// ===== 派生：6 大 KPI 列表 =====
function formatAmount(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '0'
  return n.toFixed(2)
}

function formatNum(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '0'
  return n
}

const kpiList = computed(() => [
  {
    key: 'order',
    label: '今日订单',
    icon: 'bag',
    display: formatNum(stats.todayOrderCount),
    sub: `累计售出 ${formatNum(stats.totalSoldCount)}`
  },
  {
    key: 'sales',
    label: '今日销售',
    icon: 'trendingUp',
    display: `¥${formatAmount(stats.todaySalesAmount)}`,
    sub: '今日成交金额'
  },
  {
    key: 'goods',
    label: '商品数量',
    icon: 'package',
    display: formatNum(stats.goodsCount),
    sub: `在售 ${formatNum(stats.sellingGoodsCount)}`
  },
  {
    key: 'message',
    label: '消息数量',
    icon: 'chat',
    display: formatNum(stats.messageCount),
    sub: `AI回复 ${formatNum(stats.autoReplyCount)}`
  },
  {
    key: 'delivery',
    label: '发货状态',
    icon: 'truck',
    display: formatNum(stats.deliverySuccessCount),
    sub: `待发 ${formatNum(stats.pendingDeliveryCount)} · 失败 ${formatNum(stats.deliveryFailCount)}`
  },
  {
    key: 'aiReply',
    label: 'AI回复',
    icon: 'bot',
    display: formatNum(stats.autoReplyCount),
    sub: '自动客服回复次数'
  }
])

// ===== 派生：当前趋势 series =====
const currentTrendConfig = computed(() => {
  // 订单/消息来自 order-message-trend；发货/AI回复来自 sales-trend
  if (activeTrend.value === 'order') {
    return {
      source: 'orderMsg',
      dates: orderMsgTrend.value?.dates || [],
      series: [
        { name: '订单数', color: '#0d6bff', key: 'orderCount' }
      ]
    }
  }
  if (activeTrend.value === 'message') {
    return {
      source: 'orderMsg',
      dates: orderMsgTrend.value?.dates || [],
      series: [
        { name: '消息数', color: '#8b5cf6', key: 'messageCount' }
      ]
    }
  }
  if (activeTrend.value === 'delivery') {
    return {
      source: 'sales',
      dates: salesTrend.value?.dates || [],
      series: [
        { name: '发货成功', color: '#16bf78', key: 'deliverySuccess' },
        { name: '发货失败', color: '#ef4444', key: 'deliveryFail' }
      ]
    }
  }
  // aiReply
  return {
    source: 'sales',
    dates: salesTrend.value?.dates || [],
    series: [
      { name: 'AI回复', color: '#8b5cf6', key: 'aiReplyCount' }
    ]
  }
})

const currentTrendHasData = computed(() => {
  const cfg = currentTrendConfig.value
  if (!cfg.dates.length) return false
  return cfg.series.some(s => {
    const arr = getSeriesArr(cfg.source, s.key)
    return arr.some(v => Number(v) > 0)
  })
})

function getSeriesArr(source, key) {
  const data = source === 'orderMsg' ? orderMsgTrend.value : salesTrend.value
  if (!data) return []
  const arr = data[key]
  return Array.isArray(arr) ? arr : []
}

const currentTrendSeries = computed(() => {
  const cfg = currentTrendConfig.value
  return cfg.series.map(s => {
    const arr = getSeriesArr(cfg.source, s.key)
    const total = arr.reduce((a, b) => a + (Number(b) || 0), 0)
    return { name: s.name, color: s.color, total }
  })
})

// ===== 数据加载 =====
async function loadSummary() {
  statsLoading.value = true
  statsError.value = ''
  try {
    const res = await getDashboardSummary()
    const d = res?.data
    if (!d || typeof d !== 'object' || Array.isArray(d)) {
      throw new Error('数据概览响应格式异常')
    }
    stats.todayOrderCount = Number(d.todayOrderCount) || 0
    stats.todaySalesAmount = Number(d.todaySalesAmount) || 0
    stats.goodsCount = Number(d.goodsCount) || 0
    stats.sellingGoodsCount = Number(d.sellingGoodsCount) || 0
    stats.messageCount = Number(d.messageCount) || 0
    stats.deliverySuccessCount = Number(d.deliverySuccessCount) || 0
    stats.deliveryFailCount = Number(d.deliveryFailCount) || 0
    stats.pendingDeliveryCount = Number(d.pendingDeliveryCount) || 0
    stats.autoReplyCount = Number(d.autoReplyCount) || 0
    stats.totalSoldCount = Number(d.totalSoldCount) || 0
    stats.accountCount = Number(d.accountCount) || 0
  } catch (e) {
    statsError.value = e?.message || '请检查网络连接后重试。'
  } finally {
    statsLoading.value = false
  }
}

async function loadTrend() {
  trendLoading.value = true
  trendError.value = ''
  // 并发拉取两个趋势接口：order-message-trend（订单/消息）+ sales-trend（发货/AI回复）
  const [orderMsgRes, salesRes] = await Promise.allSettled([
    getDashboardOrderMessageTrend({ days: trendDays.value }),
    getDashboardSalesTrend({ days: trendDays.value })
  ])
  if (orderMsgRes.status === 'fulfilled') {
    const d = orderMsgRes.value?.data
    if (d && typeof d === 'object' && Array.isArray(d.dates)) {
      orderMsgTrend.value = {
        dates: d.dates,
        orderCount: Array.isArray(d.orderCount) ? d.orderCount : [],
        messageCount: Array.isArray(d.messageCount) ? d.messageCount : []
      }
    }
  } else {
    orderMsgTrend.value = null
  }
  if (salesRes.status === 'fulfilled') {
    const d = salesRes.value?.data
    if (d && typeof d === 'object' && Array.isArray(d.dates)) {
      salesTrend.value = {
        dates: d.dates,
        deliverySuccess: Array.isArray(d.deliverySuccess) ? d.deliverySuccess : [],
        deliveryFail: Array.isArray(d.deliveryFail) ? d.deliveryFail : [],
        // 后端字段名为 aiReplyCount（非 aiReply）
        aiReplyCount: Array.isArray(d.aiReplyCount) ? d.aiReplyCount : []
      }
    }
  } else {
    salesTrend.value = null
  }
  // 两个都失败才算趋势加载失败
  if (orderMsgRes.status !== 'fulfilled' && salesRes.status !== 'fulfilled') {
    trendError.value = salesRes.reason?.message || '请检查网络连接后重试。'
  }
  trendLoading.value = false
  await nextTick()
  updateTrendChart()
}

// ===== ECharts =====
function updateTrendChart() {
  if (!currentTrendHasData.value) {
    if (trendChart) {
      trendChart.dispose()
      trendChart = null
    }
    return
  }
  if (!trendChartEl.value) return
  if (!trendChart) {
    trendChart = echarts.init(trendChartEl.value, null, { renderer: 'canvas' })
  }
  const cfg = currentTrendConfig.value
  const labels = cfg.dates.map(d => {
    const s = String(d || '')
    return s.length >= 5 ? s.slice(5) : s
  })
  const seriesData = cfg.series.map(s => {
    const arr = getSeriesArr(cfg.source, s.key)
    return {
      name: s.name,
      color: s.color,
      data: arr.map(v => Number(v) || 0)
    }
  })
  const option = {
    grid: { left: 8, right: 12, top: 20, bottom: 24, containLabel: true },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(21, 33, 61, 0.96)',
      borderColor: 'rgba(255,255,255,0.08)',
      borderWidth: 1,
      borderRadius: 16,
      padding: [12, 16],
      textStyle: { color: '#fff', fontSize: 12 },
      axisPointer: {
        type: 'line',
        lineStyle: { color: 'rgba(13, 107, 255, 0.3)', width: 2, type: 'dashed' }
      },
      formatter(params) {
        const lines = params.map(item =>
          `<div style="display:flex;align-items:center;gap:8px;margin-top:4px">
            <span style="width:8px;height:8px;border-radius:50%;background:${item.color};display:inline-block"></span>
            <span style="color:rgba(255,255,255,0.8)">${item.seriesName}</span>
            <span style="font-weight:700;margin-left:auto;font-size:14px;color:#fff">${item.value}</span>
          </div>`
        ).join('')
        return `<div style="font-weight:600;margin-bottom:4px;font-size:13px">${params[0]?.axisValue || ''}</div>${lines}`
      }
    },
    xAxis: {
      type: 'category',
      data: labels,
      boundaryGap: false,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#8c98ae', fontSize: 11, margin: 10, fontWeight: 500 }
    },
    yAxis: { type: 'value', show: false, min: 0, splitLine: { show: false } },
    // 30 天数据支持手势左右滑动；7 天全展示无需缩放
    dataZoom: trendDays.value === 30 ? [
      {
        type: 'inside',
        start: 60,
        end: 100,
        zoomOnMouseWheel: false,
        moveOnMouseMove: true,
        moveOnMouseWheel: true
      }
    ] : [],
    series: seriesData.map((s, index) => ({
      name: s.name,
      type: 'line',
      data: s.data,
      smooth: true,
      smoothMonotone: 'x',
      symbol: 'circle',
      symbolSize: 5,
      showSymbol: s.data.length <= 7,
      lineStyle: { color: s.color, width: index === 0 ? 3 : 2.5 },
      itemStyle: { color: s.color, borderColor: '#fff', borderWidth: 2 },
      areaStyle: index === 0 ? {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: hexToRgba(s.color, 0.24) },
          { offset: 1, color: hexToRgba(s.color, 0.01) }
        ])
      } : undefined,
      emphasis: {
        focus: 'series',
        scale: true,
        itemStyle: { color: s.color, borderColor: '#fff', borderWidth: 3 }
      }
    }))
  }
  trendChart.setOption(option, true)
}

function hexToRgba(hex, alpha) {
  const h = String(hex).replace('#', '')
  const r = parseInt(h.substring(0, 2), 16)
  const g = parseInt(h.substring(2, 4), 16)
  const b = parseInt(h.substring(4, 6), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

function handleResize() {
  if (trendChart) trendChart.resize()
}

// ===== 交互 =====
async function switchRange(days) {
  if (trendDays.value === days) return
  trendDays.value = days
  await loadTrend()
}

async function switchTrend(value) {
  if (activeTrend.value === value) return
  activeTrend.value = value
  await nextTick()
  updateTrendChart()
}

// 切换趋势 tab 时只需重绘图表，无需重新请求
watch(activeTrend, () => {
  nextTick(() => {
    updateTrendChart()
    handleResize()
  })
})

onMounted(() => {
  // 分级加载：summary 优先（3 秒内核心数据），trend 异步跟进
  loadSummary()
  loadTrend()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (trendChart) {
    trendChart.dispose()
    trendChart = null
  }
})
</script>

<style scoped>
.m-data {
  padding: var(--m-space-3);
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
}

.m-data-hero {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-4);
  margin-bottom: var(--m-space-3);
  box-shadow: var(--m-shadow-xs);
}
.m-data-hero-head {
  margin-bottom: var(--m-space-4);
}
.m-data-hero-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-1);
  background: var(--m-color-success-bg);
  color: var(--m-color-success-text);
  padding: var(--m-space-0-5) var(--m-space-2);
  border-radius: var(--m-radius-pill);
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-medium);
  margin-bottom: var(--m-space-3);
}
.m-data-hero-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--m-radius-circle);
  background: var(--m-color-success);
  animation: m-data-pulse 1.6s ease-in-out infinite;
}
@keyframes m-data-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.85); }
}
.m-data-hero-title {
  margin: 0 0 var(--m-space-1);
  font-size: var(--m-font-size-h1);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  line-height: var(--m-line-height-tight);
}
.m-data-hero-sub {
  margin: 0;
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}

.m-data-kpi-skeleton {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--m-space-3);
  margin-bottom: var(--m-space-4);
}
.m-skel-cell {
  height: 96px;
  border-radius: var(--m-radius-lg);
  background: linear-gradient(90deg, var(--m-color-bg-subtle) 25%, var(--m-color-bg-hover) 50%, var(--m-color-bg-subtle) 75%);
  background-size: 200% 100%;
  animation: m-skel 1.4s ease infinite;
}
@keyframes m-skel {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.m-data-kpi-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--m-space-3);
  margin-bottom: var(--m-space-4);
}
.m-data-kpi-card {
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3);
  display: flex;
  flex-direction: column;
  gap: var(--m-space-1);
}
.m-data-kpi-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--m-radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: var(--m-space-1);
}
.m-data-kpi-icon--order { background: var(--m-color-primary-bg); color: var(--m-color-primary); }
.m-data-kpi-icon--sales { background: var(--m-color-success-bg); color: var(--m-color-success); }
.m-data-kpi-icon--goods { background: var(--m-color-cyan-bg); color: var(--m-color-cyan); }
.m-data-kpi-icon--message { background: var(--m-color-warning-bg); color: var(--m-color-warning); }
.m-data-kpi-icon--delivery { background: var(--m-color-purple-bg); color: var(--m-color-purple); }
.m-data-kpi-icon--aiReply { background: var(--m-color-danger-bg); color: var(--m-color-danger); }

.m-data-kpi-value {
  font-size: var(--m-font-size-h1);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
  line-height: var(--m-line-height-tight);
  font-variant-numeric: tabular-nums;
}

.m-data-kpi-label {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-secondary);
  font-weight: var(--m-font-weight-medium);
}
.m-data-kpi-sub {
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
  line-height: 1.3;
}

.m-data-date-tabs {
  display: flex;
  gap: var(--m-space-1);
  background: var(--m-color-bg-subtle);
  padding: var(--m-space-1);
  border-radius: var(--m-radius-lg);
}
.m-data-date-tab {
  flex: 1;
  border: none;
  background: transparent;
  padding: var(--m-space-2) var(--m-space-3);
  border-radius: var(--m-radius-md);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-medium);
  color: var(--m-color-text-secondary);
  cursor: pointer;
  transition: all var(--m-duration-fast);
  font-family: inherit;
}
.m-data-date-tab.active {
  background: var(--m-color-bg-card);
  color: var(--m-color-primary);
  font-weight: var(--m-font-weight-semibold);
  box-shadow: var(--m-shadow-xs);
}

.m-data-card {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-4);
  margin-bottom: var(--m-space-3);
  box-shadow: var(--m-shadow-xs);
}
.m-data-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--m-space-3);
  gap: var(--m-space-2);
}
.m-data-card-title-wrap {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  min-width: 0;
}
.m-data-card-title-icon {
  width: 28px;
  height: 28px;
  border-radius: var(--m-radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-data-title-icon--primary {
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
}
.m-data-card-title {
  margin: 0;
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
}
.m-data-card-hint {
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
  margin-left: var(--m-space-1);
}
.m-data-card-refresh {
  width: 28px;
  height: 28px;
  border-radius: var(--m-radius-lg);
  border: none;
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all var(--m-duration-fast);
}
.m-data-card-refresh:active { background: var(--m-color-bg-hover); }

.m-data-trend-tabs {
  display: flex;
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-3);
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.m-data-trend-tabs::-webkit-scrollbar { display: none; }
.m-data-trend-tab {
  flex-shrink: 0;
  border: none;
  background: var(--m-color-bg-subtle);
  padding: var(--m-space-2) var(--m-space-3);
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-medium);
  color: var(--m-color-text-tertiary);
  cursor: pointer;
  font-family: inherit;
  transition: all var(--m-duration-fast);
  white-space: nowrap;
}
.m-data-trend-tab.active {
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
  font-weight: var(--m-font-weight-semibold);
}

.m-data-echart-box {
  width: 100%;
  height: 200px;
  min-height: 200px;
}
.m-data-chart-loading,
.m-data-chart-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-2);
  height: 200px;
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-caption);
}
.m-data-chart-error { cursor: pointer; color: var(--m-color-danger-text); }
.m-data-spinner {
  width: 28px;
  height: 28px;
  border: 2.5px solid var(--m-color-border-light);
  border-top-color: var(--m-color-primary);
  border-radius: var(--m-radius-circle);
  animation: m-data-spin 0.8s linear infinite;
}
@keyframes m-data-spin {
  to { transform: rotate(360deg); }
}

.m-data-trend-legend {
  display: flex;
  flex-wrap: wrap;
  gap: var(--m-space-3);
  margin-top: var(--m-space-3);
  padding-top: var(--m-space-3);
  border-top: 1px solid var(--m-color-border-light);
  align-items: center;
}
.m-data-trend-legend-item {
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-1);
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-secondary);
}
.m-data-trend-legend-item i {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: var(--m-radius-sm);
}
.m-data-trend-legend-name { color: var(--m-color-text-tertiary); }
.m-data-trend-legend-total {
  color: var(--m-color-text-primary);
  font-weight: var(--m-font-weight-semibold);
  margin-left: 2px;
}
.m-data-trend-hint {
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-1);
  margin-left: auto;
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-quaternary);
}

.m-data-safe-bottom { height: 80px; }

@media (max-width: 360px) {
  .m-data {
    padding: var(--m-space-2);
  }
  .m-data-hero {
    padding: var(--m-space-3);
  }
  .m-data-kpi-grid {
    gap: var(--m-space-2);
  }
  .m-data-kpi-card {
    padding: var(--m-space-2);
  }
  .m-data-kpi-value {
    font-size: var(--m-font-size-h2);
  }
  .m-data-kpi-icon {
    width: 28px;
    height: 28px;
  }
  .m-data-echart-box {
    height: 160px;
    min-height: 160px;
  }
  .m-data-chart-loading,
  .m-data-chart-error {
    height: 160px;
  }
}
</style>
