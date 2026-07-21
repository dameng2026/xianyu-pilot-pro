<template>
  <div class="m-data">
    <div class="m-hero-card">
      <div class="m-hero-glow m-hero-glow-1"></div>
      <div class="m-hero-glow m-hero-glow-2"></div>
      <div class="m-hero-pattern"></div>
      <div class="m-hero-content">
        <div class="m-hero-badge">
          <span class="m-hero-dot"></span>
          <span>实时数据</span>
        </div>
        <h1 class="m-hero-title">数据面板</h1>
        <p class="m-hero-sub">{{ scopeLabel }} · 更新于 {{ updatedAt }}</p>
      </div>
      <div class="m-hero-stats">
        <div class="m-hero-stat">
          <div class="m-hero-stat-value">{{ metricText(stats.orderCount) }}</div>
          <div class="m-hero-stat-label">今日订单</div>
        </div>
        <div class="m-hero-stat-divider"></div>
        <div class="m-hero-stat">
          <div class="m-hero-stat-value m-hero-stat-green">{{ metricText(stats.deliverySuccessCount) }}</div>
          <div class="m-hero-stat-label">发货成功</div>
        </div>
        <div class="m-hero-stat-divider"></div>
        <div class="m-hero-stat">
          <div class="m-hero-stat-value m-hero-stat-orange">{{ metricText(stats.pendingDeliveryCount) }}</div>
          <div class="m-hero-stat-label">待处理</div>
        </div>
      </div>
      <div class="m-hero-date-tabs">
        <button
          v-for="tab in dateTabs"
          :key="tab.value"
          class="m-hero-date-tab"
          :class="{ active: activeDate === tab.value }"
          :disabled="tab.disabled"
          @click="switchDate(tab.value)"
        >
          {{ tab.label }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="m-loading-wrap">
      <div class="m-loading-spinner"></div>
      <div class="m-loading-text">加载数据中...</div>
    </div>

    <MobileUnavailableState v-else-if="loadError" title="数据面板暂时无法加载" :description="loadError" @retry="loadAll" />

    <template v-else>
      <div v-if="!hasData" class="m-empty">
        <div class="m-empty-icon">
          <MIcon name="pieChart" :size="48" />
        </div>
        <div class="m-empty-text">暂无数据</div>
        <div class="m-empty-desc">当前时间段还没有运营数据，稍后再来看看</div>
      </div>

      <template v-else>
        <div class="m-metric-grid">
          <div
            v-for="metric in displayMetrics"
            :key="metric.key"
            class="m-metric-card"
          >
            <div class="m-metric-head">
              <span class="m-metric-label">{{ metric.label }}</span>
              <div class="m-metric-icon" :style="{ background: metric.iconBg }">
                <MIcon :name="metric.icon" :size="18" :style="{ color: metric.iconColor }" />
              </div>
            </div>
            <div class="m-metric-value" :style="{ color: metric.valueColor || '#15213d' }">{{ metric.display }}</div>
            <div class="m-metric-sub">{{ metric.sub }}</div>
          </div>
        </div>

        <div class="m-section m-trend-section">
          <div class="m-section-header">
            <div class="m-section-title-wrap">
              <div class="m-section-title-icon m-title-icon-blue">
                <MIcon name="trendingUp" :size="18" />
              </div>
              <h2 class="m-section-title">业务趋势</h2>
              <span class="m-section-hint">近 {{ trendDays }} 天走势</span>
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
          <div v-if="trendHasData" ref="trendChartEl" class="m-echart-box"></div>
          <div v-if="trendHasData" class="m-trend-legend">
            <span v-for="series in trendSeries" :key="series.name" class="m-trend-legend-item">
              <i :style="{ background: series.color }"></i>{{ series.name }}
            </span>
          </div>
          <div v-else class="m-chart-empty">
            <MIcon name="trend" :size="32" />
            <span>暂无趋势数据</span>
          </div>
        </div>

        <div class="m-section">
          <div class="m-section-header">
            <div class="m-section-title-wrap">
              <div class="m-section-title-icon m-title-icon-blue">
                <MIcon name="activity" :size="18" />
              </div>
              <h2 class="m-section-title">数据概览</h2>
            </div>
          </div>
          <div class="m-overview-grid">
            <div v-for="item in overviewItems" :key="item.label" class="m-overview-card">
              <div class="m-overview-icon" :style="{ background: item.iconBg }">
                <MIcon :name="item.icon" :size="20" :style="{ color: item.color }" />
              </div>
              <div class="m-overview-info">
                <div class="m-overview-label">{{ item.label }}</div>
                <div class="m-overview-value" :style="{ color: item.color }">{{ item.value }}</div>
              </div>
              <div class="m-overview-bar-wrap">
                <div class="m-overview-bar">
                  <div class="m-overview-bar-fill m-bar-shine" :style="{ width: item.pct + '%', background: `linear-gradient(90deg, ${item.color}, ${item.color}dd)` }"></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="m-alert-grid">
          <div v-for="alert in alertItems" :key="alert.label" class="m-alert-card" :style="{ background: alert.bg }">
            <div class="m-alert-icon" :style="{ background: alert.iconBg }">
              <MIcon :name="alert.icon" :size="20" :style="{ color: alert.color }" />
            </div>
            <div class="m-alert-info">
              <div class="m-alert-value" :style="{ color: alert.color }">{{ alert.value }}</div>
              <div class="m-alert-label">{{ alert.label }}</div>
            </div>
          </div>
        </div>

        <div class="m-section">
          <div class="m-section-header">
            <div class="m-section-title-wrap">
              <div class="m-section-title-icon">
                <MIcon name="grid" :size="18" />
              </div>
              <h2 class="m-section-title">快捷入口</h2>
            </div>
          </div>
          <div class="m-quick-grid">
            <button v-for="quick in quickEntries" :key="quick.key" class="m-quick-item" @click="$emit('navigate', quick.key)">
              <div class="m-quick-icon" :style="{ background: quick.iconBg }">
                <MIcon :name="quick.icon" :size="22" :style="{ color: quick.color }" />
              </div>
              <span class="m-quick-label">{{ quick.label }}</span>
            </button>
          </div>
        </div>

        <div class="m-section">
          <div class="m-section-header">
            <div class="m-section-title-wrap">
              <div class="m-section-title-icon" style="background: linear-gradient(135deg, #fef3c7, #fde68a); color: #d97706;">
                <MIcon name="bell" :size="18" />
              </div>
              <h2 class="m-section-title">最新动态</h2>
            </div>
            <button class="m-section-more" @click="$emit('navigate', 'messages')">
              查看全部
              <MIcon name="chevronRight" :size="14" />
            </button>
          </div>
          <div class="m-notice-list">
            <div v-for="(notice, idx) in noticeList" :key="idx" class="m-notice-item">
              <div class="m-notice-icon" :style="{ background: notice.iconBg }">
                <MIcon :name="notice.icon" :size="16" :style="{ color: notice.color }" />
              </div>
              <div class="m-notice-content">
                <div class="m-notice-title">{{ notice.title }}</div>
                <div class="m-notice-desc">{{ notice.desc }}</div>
              </div>
              <div class="m-notice-time">{{ notice.time }}</div>
            </div>
          </div>
        </div>

        <div v-if="trendHasData" class="m-section">
          <div class="m-section-header">
            <div class="m-section-title-wrap">
              <div class="m-section-title-icon m-title-icon-purple">
                <MIcon name="list" :size="18" />
              </div>
              <h2 class="m-section-title">趋势明细</h2>
              <span class="m-section-hint">按日展示指标</span>
            </div>
            <button class="m-section-more" @click="$emit('navigate', 'data-detail')">
              查看详情
              <MIcon name="chevronRight" :size="14" />
            </button>
          </div>
          <div class="m-table-wrap">
            <table class="m-data-table">
              <thead>
                <tr>
                  <th>日期</th>
                  <th>发货成功</th>
                  <th>发货失败</th>
                  <th>AI回复</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, idx) in trendRows" :key="row.date" :class="{ 'row-alt': idx % 2 === 1 }">
                  <td class="td-date">{{ row.shortDate }}</td>
                  <td class="td-num"><span class="m-num-pill m-num-green">{{ row.success }}</span></td>
                  <td class="td-num"><span v-if="row.fail > 0" class="m-num-dot m-dot-red"></span>{{ row.fail }}</td>
                  <td class="td-num"><span v-if="row.aiReply > 0" class="m-num-pill m-num-purple">{{ row.aiReply }}</span><span v-else class="m-num-muted">0</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="m-tip-card">
          <div class="m-tip-icon">
            <MIcon name="bulb" :size="20" />
          </div>
          <div class="m-tip-content">
            <div class="m-tip-title">温馨提示</div>
            <div class="m-tip-desc">更详细的数据分析、趋势对比与导出功能建议在桌面端查看，体验更佳。</div>
          </div>
          <button class="m-tip-btn" @click="$emit('force-desktop')">
            桌面版
            <MIcon name="chevronRight" :size="14" />
          </button>
        </div>
      </template>
    </template>

    <div class="m-safe-bottom"></div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import MIcon from './MIcon.vue'
import MobileUnavailableState from './MobileUnavailableState.vue'
import { getDashboardSummary, getDashboardSalesTrend } from '../api/dashboard.js'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])

defineEmits(['navigate', 'force-desktop', 'back'])

const dateTabs = [
  { label: '今日', value: 'today' },
  { label: '近7天', value: '7d', disabled: true },
  { label: '近30天', value: '30d', disabled: true }
]

const trendRangeOptions = [
  { label: '7天', value: 7 },
  { label: '30天', value: 30 }
]

const activeDate = ref('today')
const trendDays = ref(7)
const loading = ref(true)
const loadError = ref('')
const trendError = ref('')
const trendChartEl = ref(null)
let trendChart = null

const stats = reactive({
  orderCount: 0,
  deliverySuccessCount: 0,
  pendingDeliveryCount: 0,
  deliveryFailCount: 0,
  aiReplyCount: 0,
  itemCount: 0
})

const trend = ref({
  dates: [],
  deliverySuccess: [],
  deliveryFail: [],
  aiReply: []
})

const updatedAt = computed(() => {
  const now = new Date()
  return `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
})

const scopeLabel = computed(() => {
  const tab = dateTabs.find(t => t.value === activeDate.value)
  return tab ? tab.label : '今日'
})

const hasData = computed(() => {
  return !!(
    stats.orderCount ||
    stats.deliverySuccessCount ||
    stats.deliveryFailCount ||
    stats.pendingDeliveryCount ||
    stats.aiReplyCount ||
    stats.itemCount
  )
})

const trendHasData = computed(() => {
  const arr = trend.value.deliverySuccess || []
  return arr.length > 0 && arr.some(v => Number(v) > 0)
})

const displayMetrics = computed(() => {
  const metrics = [
    {
      key: 'orderCount',
      label: '订单数',
      sub: '今日订单总量',
      icon: 'bag',
      iconBg: 'linear-gradient(135deg, #e8f1ff, #c5dcff)',
      iconColor: '#0d6bff',
      valueColor: '#0d6bff'
    },
    {
      key: 'deliverySuccessCount',
      label: '发货成功',
      sub: '自动发货完成',
      icon: 'checkCircle',
      iconBg: 'linear-gradient(135deg, #e2f8ee, #b8ebd0)',
      iconColor: '#16bf78',
      valueColor: '#16bf78'
    },
    {
      key: 'pendingDeliveryCount',
      label: '待发货',
      sub: '待处理订单',
      icon: 'clock',
      iconBg: 'linear-gradient(135deg, #fff4e0, #ffdfa3)',
      iconColor: '#ff9f22',
      valueColor: '#ff9f22'
    },
    {
      key: 'deliveryFailCount',
      label: '发货失败',
      sub: '需要关注处理',
      icon: 'alertTriangle',
      iconBg: 'linear-gradient(135deg, #ffe8e8, #ffc5c5)',
      iconColor: '#ef4444',
      valueColor: '#ef4444'
    },
    {
      key: 'aiReplyCount',
      label: 'AI 回复',
      sub: '自动客服回复',
      icon: 'bot',
      iconBg: 'linear-gradient(135deg, #f0ebff, #d4c5ff)',
      iconColor: '#8b5cf6',
      valueColor: '#8b5cf6'
    },
    {
      key: 'itemCount',
      label: '在售商品',
      sub: '当前商品数量',
      icon: 'package',
      iconBg: 'linear-gradient(135deg, #e0f7fb, #cdf0f6)',
      iconColor: '#06b6d4',
      valueColor: '#06b6d4'
    }
  ]
  return metrics.map(metric => ({
    ...metric,
    display: metricText(stats[metric.key])
  }))
})

const trendSeries = [
  { name: '发货成功', color: '#16bf78', key: 'deliverySuccess' },
  { name: '发货失败', color: '#ef4444', key: 'deliveryFail' },
  { name: 'AI 回复', color: '#8b5cf6', key: 'aiReply' }
]

const trendRows = computed(() => {
  const dates = trend.value.dates || []
  const success = trend.value.deliverySuccess || []
  const fail = trend.value.deliveryFail || []
  const aiReply = trend.value.aiReply || []
  return dates.map((d, i) => {
    const dateStr = String(d || '')
    const shortDate = dateStr.length >= 5 ? dateStr.slice(5) : dateStr
    return {
      date: dateStr,
      shortDate,
      success: Number(success[i]) || 0,
      fail: Number(fail[i]) || 0,
      aiReply: Number(aiReply[i]) || 0
    }
  })
})

const overviewItems = computed(() => {
  const success = Number(stats.deliverySuccessCount) || 0
  const fail = Number(stats.deliveryFailCount) || 0
  const orders = Number(stats.orderCount) || 0
  const aiReply = Number(stats.aiReplyCount) || 0
  const total = Math.max(1, success + fail)
  return [
    {
      label: '发货成功率',
      value: total > 0 ? `${Math.round((success / total) * 100)}%` : '—',
      pct: total > 0 ? Math.round((success / total) * 100) : 0,
      color: '#16bf78',
      icon: 'checkCircle',
      iconBg: 'linear-gradient(135deg, #e2f8ee, #b8ebd0)'
    },
    {
      label: '订单总数',
      value: metricText(orders),
      pct: Math.min(100, Math.round((orders / Math.max(1, orders)) * 100)),
      color: '#0d6bff',
      icon: 'bag',
      iconBg: 'linear-gradient(135deg, #e8f1ff, #c5dcff)'
    },
    {
      label: 'AI 回复',
      value: metricText(aiReply),
      pct: Math.min(100, Math.round((aiReply / Math.max(1, aiReply)) * 100)),
      color: '#8b5cf6',
      icon: 'bot',
      iconBg: 'linear-gradient(135deg, #f0ebff, #d4c5ff)'
    },
    {
      label: '待处理',
      value: metricText(stats.pendingDeliveryCount),
      pct: Math.min(100, Math.round((Number(stats.pendingDeliveryCount) / Math.max(1, total)) * 100)),
      color: '#ff9f22',
      icon: 'clock',
      iconBg: 'linear-gradient(135deg, #fff4e0, #ffdfa3)'
    }
  ]
})

const alertItems = computed(() => [
  {
    label: '发货异常',
    value: metricText(stats.deliveryFailCount),
    icon: 'alertTriangle',
    color: '#ef4444',
    bg: 'linear-gradient(135deg, #fef2f2, #fff5f5)',
    iconBg: 'linear-gradient(135deg, #fee2e2, #fecaca)'
  },
  {
    label: '待回复消息',
    value: '0',
    icon: 'message',
    color: '#f59e0b',
    bg: 'linear-gradient(135deg, #fffbeb, #fefce8)',
    iconBg: 'linear-gradient(135deg, #fef3c7, #fde68a)'
  },
  {
    label: 'Cookie 过期',
    value: '0',
    icon: 'wifiOff',
    color: '#8b5cf6',
    bg: 'linear-gradient(135deg, #faf5ff, #f5f3ff)',
    iconBg: 'linear-gradient(135deg, #ede9fe, #ddd6fe)'
  }
])

const quickEntries = [
  { key: 'products', label: '商品管理', icon: 'package', color: '#0d6bff', iconBg: 'linear-gradient(135deg, #e8f1ff, #dbeafe)' },
  { key: 'orders', label: '订单管理', icon: 'truck', color: '#16bf78', iconBg: 'linear-gradient(135deg, #ecfdf5, #d1fae5)' },
  { key: 'messages', label: '消息中心', icon: 'chat', color: '#f59e0b', iconBg: 'linear-gradient(135deg, #fffbeb, #fef3c7)' },
  { key: 'workflow', label: '自动化', icon: 'workflow', color: '#8b5cf6', iconBg: 'linear-gradient(135deg, #f5f3ff, #ede9fe)' },
  { key: 'accounts', label: '账号管理', icon: 'user', color: '#ec4899', iconBg: 'linear-gradient(135deg, #fdf2f8, #fce7f3)' },
  { key: 'auto-delivery', label: '自动发货', icon: 'gift', color: '#06b6d4', iconBg: 'linear-gradient(135deg, #ecfeff, #cffafe)' },
  { key: 'data', label: '数据明细', icon: 'pieChart', color: '#f97316', iconBg: 'linear-gradient(135deg, #fff7ed, #ffedd5)' },
  { key: 'profile', label: '设置', icon: 'settings', color: '#64748b', iconBg: 'linear-gradient(135deg, #f8fafc, #f1f5f9)' }
]

const noticeList = [
  {
    title: '自动发货成功',
    desc: '订单 #20240115001 已完成自动发货',
    time: '2分钟前',
    icon: 'checkCircle',
    color: '#16bf78',
    iconBg: 'linear-gradient(135deg, #dcfce7, #bbf7d0)'
  },
  {
    title: '新订单提醒',
    desc: '您有1笔新订单待处理',
    time: '15分钟前',
    icon: 'bag',
    color: '#0d6bff',
    iconBg: 'linear-gradient(135deg, #dbeafe, #bfdbfe)'
  },
  {
    title: 'AI客服回复',
    desc: 'AI客服已自动回复买家咨询',
    time: '1小时前',
    icon: 'bot',
    color: '#8b5cf6',
    iconBg: 'linear-gradient(135deg, #ede9fe, #ddd6fe)'
  }
]

function metricText(value) {
  return value === null || value === undefined ? '—' : value
}

function initTrendChart() {
  if (!trendChartEl.value) return
  if (trendChart) {
    trendChart.dispose()
  }
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
  const option = {
    grid: {
      left: 8,
      right: 12,
      top: 20,
      bottom: 28,
      containLabel: true
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(21, 33, 61, 0.96)',
      borderColor: 'rgba(255,255,255,0.08)',
      borderWidth: 1,
      borderRadius: 16,
      padding: [14, 18],
      textStyle: {
        color: '#fff',
        fontSize: 12
      },
      axisPointer: {
        type: 'line',
        lineStyle: {
          color: 'rgba(13, 107, 255, 0.3)',
          width: 2,
          type: 'dashed'
        },
        shadowStyle: {
          color: 'rgba(13, 107, 255, 0.06)'
        }
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
      axisLabel: {
        color: '#8c98ae',
        fontSize: 11,
        margin: 12,
        fontWeight: 500
      }
    },
    yAxis: {
      type: 'value',
      show: false,
      min: 0,
      splitLine: { show: false }
    },
    series: seriesData.map((series, index) => ({
      name: series.name,
      type: 'line',
      data: series.data,
      smooth: true,
      smoothMonotone: 'x',
      symbol: 'circle',
      symbolSize: 5,
      showSymbol: series.data.length <= 7,
      lineStyle: {
        color: series.color,
        width: index === 0 ? 3 : 2.5
      },
      itemStyle: {
        color: series.color,
        borderColor: '#fff',
        borderWidth: 2
      },
      areaStyle: index === 0 ? {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(22, 191, 120, 0.24)' },
          { offset: 1, color: 'rgba(22, 191, 120, 0.01)' }
        ])
      } : undefined,
      emphasis: {
        focus: 'series',
        scale: true,
        itemStyle: {
          color: series.color,
          borderColor: '#fff',
          borderWidth: 3
        }
      }
    }))
  }
  trendChart.setOption(option, true)
}

function handleResize() {
  if (trendChart) {
    trendChart.resize()
  }
}

async function loadSummary() {
  const res = await getDashboardSummary({ date: activeDate.value })
  const d = res?.data
  if (!d || typeof d !== 'object' || Array.isArray(d)) throw new Error('数据概览响应格式异常')
  const values = {
    orderCount: d.todayOrderCount ?? d.orderCount,
    deliverySuccessCount: d.deliverySuccessCount,
    pendingDeliveryCount: d.pendingDeliveryCount,
    deliveryFailCount: d.deliveryFailCount,
    aiReplyCount: d.autoReplyCount ?? d.aiReplyCount,
    itemCount: d.goodsCount
  }
  const normalized = Object.fromEntries(Object.entries(values).map(([key, value]) => [key, Number(value) || 0]))
  Object.assign(stats, normalized)
}

async function loadTrend() {
  const res = await getDashboardSalesTrend()
  const d = res?.data
  if (!d || typeof d !== 'object' || Array.isArray(d)) throw new Error('趋势数据响应格式异常')
  const dates = d.dates
  const deliverySuccess = d.deliverySuccess || d.series?.deliverySuccess || []
  const deliveryFail = d.deliveryFail || d.series?.deliveryFail || new Array(dates?.length || 0).fill(0)
  const aiReply = d.aiReply || d.autoReply || d.series?.aiReply || new Array(dates?.length || 0).fill(0)
  if (!Array.isArray(dates)) throw new Error('趋势数据响应格式异常')
  trend.value = {
    dates: dates.slice(-trendDays.value),
    deliverySuccess: (Array.isArray(deliverySuccess) ? deliverySuccess : []).slice(-trendDays.value),
    deliveryFail: (Array.isArray(deliveryFail) ? deliveryFail : []).slice(-trendDays.value),
    aiReply: (Array.isArray(aiReply) ? aiReply : []).slice(-trendDays.value)
  }
}

function resetStats() {
  stats.orderCount = 0
  stats.deliverySuccessCount = 0
  stats.pendingDeliveryCount = 0
  stats.deliveryFailCount = 0
  stats.aiReplyCount = 0
  stats.itemCount = 0
}

async function loadAll() {
  loading.value = true
  loadError.value = ''
  trendError.value = ''
  const [summaryResult, trendResult] = await Promise.allSettled([loadSummary(), loadTrend()])
  if (summaryResult.status === 'rejected') {
    resetStats()
    loadError.value = summaryResult.reason?.message || '请检查网络连接后重试。'
  }
  if (trendResult.status === 'rejected') {
    trend.value = { dates: [], deliverySuccess: [], deliveryFail: [], aiReply: [] }
    trendError.value = trendResult.reason?.message || '请检查网络连接后重试。'
  }
  loading.value = false
  await nextTick()
  initTrendChart()
}

async function switchDate(value) {
  if (dateTabs.find(tab => tab.value === value)?.disabled) return
  if (activeDate.value === value) return
  activeDate.value = value
  await loadAll()
}

async function switchTrendRange(days) {
  if (trendDays.value === days) return
  trendDays.value = days
  await loadTrend().catch(() => {})
  await nextTick()
  updateTrendChart()
}

watch(trendDays, () => {
  nextTick(() => {
    handleResize()
  })
})

onMounted(() => {
  loadAll()
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
  padding: 12px 14px 0;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
}

.m-hero-card {
  background: linear-gradient(145deg, #052560 0%, #0a4299 30%, #0d55d4 65%, #1570ff 100%);
  border-radius: 24px;
  padding: 20px 18px 16px;
  margin-bottom: 16px;
  position: relative;
  overflow: hidden;
  box-shadow: 0 12px 40px rgba(10, 66, 153, 0.4), 0 4px 12px rgba(13, 85, 212, 0.25);
}

.m-hero-glow {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
}

.m-hero-glow-1 {
  top: -60px;
  right: -40px;
  width: 220px;
  height: 220px;
  background: radial-gradient(circle, rgba(99, 179, 255, 0.45) 0%, transparent 70%);
}

.m-hero-glow-2 {
  bottom: -80px;
  left: -30px;
  width: 180px;
  height: 180px;
  background: radial-gradient(circle, rgba(59, 130, 246, 0.3) 0%, transparent 70%);
}

.m-hero-pattern {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-image: radial-gradient(circle at 20% 80%, rgba(255,255,255,0.03) 0%, transparent 50%),
                    radial-gradient(circle at 80% 20%, rgba(255,255,255,0.05) 0%, transparent 50%);
  pointer-events: none;
}

.m-hero-content {
  position: relative;
  z-index: 1;
  margin-bottom: 16px;
}

.m-hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(255, 255, 255, 0.18);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  padding: 5px 12px;
  border-radius: 100px;
  font-size: 11px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.95);
  margin-bottom: 12px;
  border: 1px solid rgba(255,255,255,0.1);
}

.m-hero-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #4ade80;
  box-shadow: 0 0 10px #4ade80, 0 0 20px rgba(74, 222, 128, 0.5);
  animation: m-pulse 2s ease-in-out infinite;
}

@keyframes m-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.6; transform: scale(0.9); }
}

.m-hero-title {
  margin: 0 0 6px;
  font-size: 28px;
  font-weight: 800;
  color: #ffffff;
  line-height: 1.15;
  letter-spacing: -0.5px;
  text-shadow: 0 2px 8px rgba(0,0,0,0.15);
}

.m-hero-sub {
  margin: 0;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.78);
  line-height: 1.5;
  font-weight: 500;
}

.m-hero-stats {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  background: rgba(255,255,255,0.1);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border-radius: 16px;
  padding: 14px 12px;
  margin-bottom: 14px;
  border: 1px solid rgba(255,255,255,0.08);
}

.m-hero-stat {
  flex: 1;
  text-align: center;
}

.m-hero-stat-value {
  font-size: 22px;
  font-weight: 800;
  color: #ffffff;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
  text-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.m-hero-stat-green {
  color: #86efac;
}

.m-hero-stat-orange {
  color: #fdba74;
}

.m-hero-stat-label {
  font-size: 10px;
  color: rgba(255,255,255,0.65);
  margin-top: 4px;
  font-weight: 500;
}

.m-hero-stat-divider {
  width: 1px;
  height: 32px;
  background: rgba(255,255,255,0.15);
}

.m-hero-date-tabs {
  position: relative;
  z-index: 1;
  display: flex;
  background: rgba(255, 255, 255, 0.12);
  border-radius: 14px;
  padding: 4px;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid rgba(255,255,255,0.08);
}

.m-hero-date-tab {
  flex: 1;
  height: 34px;
  border: none;
  background: transparent;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.6);
  cursor: pointer;
  transition: all 0.28s cubic-bezier(0.4, 0, 0.2, 1);
}

.m-hero-date-tab.active {
  background: white;
  color: #0d55d4;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  font-weight: 700;
}

.m-hero-date-tab:disabled {
  color: rgba(255, 255, 255, 0.3);
  cursor: not-allowed;
}

.m-loading-wrap {
  padding: 80px 0;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
}

.m-loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #e8f1ff;
  border-top-color: #0d6bff;
  border-radius: 50%;
  animation: m-spin 0.8s linear infinite;
}

@keyframes m-spin {
  to { transform: rotate(360deg); }
}

.m-loading-text {
  font-size: 13px;
  color: #8c98ae;
  font-weight: 500;
}

.m-empty {
  padding: 60px 16px;
  text-align: center;
  color: #8c98ae;
}

.m-empty-icon {
  width: 88px;
  height: 88px;
  border-radius: 50%;
  background: linear-gradient(135deg, #e8f1ff, #d4e4ff);
  color: #0d6bff;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
  opacity: 0.7;
}

.m-empty-text {
  font-size: 17px;
  font-weight: 700;
  color: #5a6a85;
  margin-bottom: 8px;
}

.m-empty-desc {
  font-size: 13px;
  color: #9aa6bd;
  line-height: 1.6;
}

.m-metric-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 16px;
}

.m-metric-card {
  background: white;
  border-radius: 20px;
  padding: 16px;
  box-shadow: 0 4px 16px rgba(31, 53, 94, 0.07), 0 1px 3px rgba(31, 53, 94, 0.04);
  border: 1px solid #f0f4fa;
  transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.2s;
  position: relative;
  overflow: hidden;
}

.m-metric-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, transparent, rgba(13,107,255,0.1), transparent);
  opacity: 0;
  transition: opacity 0.2s;
}

.m-metric-card:active {
  transform: scale(0.97);
  box-shadow: 0 2px 8px rgba(31, 53, 94, 0.08);
}

.m-metric-card:active::before {
  opacity: 1;
}

.m-metric-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.m-metric-label {
  font-size: 12px;
  font-weight: 600;
  color: #72809a;
}

.m-metric-icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

.m-metric-value {
  font-size: 28px;
  font-weight: 800;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.m-metric-sub {
  font-size: 10px;
  color: #9aa6bd;
  margin-top: 7px;
  font-weight: 500;
}

.m-section {
  background: white;
  border-radius: 22px;
  padding: 18px;
  margin-bottom: 16px;
  box-shadow: 0 4px 16px rgba(31, 53, 94, 0.06), 0 1px 3px rgba(31, 53, 94, 0.03);
  border: 1px solid #f0f4fa;
}

.m-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
}

.m-section-title-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
}

.m-section-title-icon {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: linear-gradient(135deg, #e8f1ff, #d0e2ff);
  color: #0d6bff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.m-title-icon-blue {
  background: linear-gradient(135deg, #e8f1ff, #c5dcff);
  color: #0d6bff;
}

.m-title-icon-purple {
  background: linear-gradient(135deg, #f0ebff, #d4c5ff);
  color: #8b5cf6;
}

.m-section-title {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  color: #15213d;
}

.m-section-hint {
  font-size: 11px;
  color: #8c98ae;
  background: #f5f8ff;
  padding: 3px 10px;
  border-radius: 100px;
  font-weight: 500;
}

.m-trend-pills {
  display: flex;
  background: #f5f8ff;
  border-radius: 12px;
  padding: 4px;
}

.m-trend-pill {
  border: none;
  background: transparent;
  border-radius: 8px;
  padding: 5px 12px;
  font-size: 11px;
  font-weight: 600;
  color: #8c98ae;
  cursor: pointer;
  transition: all 0.2s;
}

.m-trend-pill.active {
  background: white;
  color: #0d6bff;
  box-shadow: 0 2px 8px rgba(13, 107, 255, 0.12);
  font-weight: 700;
}

.m-echart-box {
  width: 100%;
  height: 200px;
}

.m-trend-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 2px 8px 0;
}

.m-trend-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: #72809a;
}

.m-trend-legend-item i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.m-chart-empty {
  height: 140px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 13px;
  color: #9aa6bd;
}

.m-overview-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.m-overview-card {
  background: linear-gradient(145deg, #f8faff, #f5f8ff);
  border-radius: 16px;
  padding: 14px;
  border: 1px solid #f0f4fa;
  transition: transform 0.15s;
}

.m-overview-card:active {
  transform: scale(0.98);
}

.m-overview-icon {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 10px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

.m-overview-info {
  margin-bottom: 12px;
}

.m-overview-label {
  font-size: 11px;
  color: #8c98ae;
  margin-bottom: 4px;
  font-weight: 500;
}

.m-overview-value {
  font-size: 24px;
  font-weight: 800;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}

.m-overview-bar-wrap {
  margin-top: auto;
}

.m-overview-bar {
  height: 7px;
  background: #e8eef8;
  border-radius: 100px;
  overflow: hidden;
  box-shadow: inset 0 1px 2px rgba(0,0,0,0.05);
}

.m-overview-bar-fill {
  height: 100%;
  border-radius: 100px;
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 1px 4px rgba(0,0,0,0.1);
  position: relative;
  overflow: hidden;
}

.m-bar-shine::after {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.4), transparent);
  animation: m-bar-shine 2.5s ease-in-out infinite;
}

@keyframes m-bar-shine {
  0% { left: -100%; }
  50%, 100% { left: 100%; }
}

.m-alert-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 16px;
}

.m-alert-card {
  border-radius: 18px;
  padding: 14px 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  border: 1px solid rgba(0,0,0,0.04);
  box-shadow: 0 2px 10px rgba(31, 53, 94, 0.05);
  transition: transform 0.15s;
}

.m-alert-card:active {
  transform: scale(0.96);
}

.m-alert-icon {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 3px 10px rgba(0,0,0,0.08);
}

.m-alert-info {
  text-align: center;
}

.m-alert-value {
  font-size: 22px;
  font-weight: 800;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}

.m-alert-label {
  font-size: 11px;
  color: #72809a;
  margin-top: 3px;
  font-weight: 500;
}

.m-quick-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px 8px;
}

.m-quick-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  background: transparent;
  border: none;
  padding: 8px 4px;
  cursor: pointer;
  border-radius: 14px;
  transition: all 0.15s;
}

.m-quick-item:active {
  transform: scale(0.92);
  background: #f5f8ff;
}

.m-quick-icon {
  width: 52px;
  height: 52px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 3px 12px rgba(0,0,0,0.06);
  transition: box-shadow 0.15s;
}

.m-quick-item:active .m-quick-icon {
  box-shadow: 0 2px 6px rgba(0,0,0,0.08);
}

.m-quick-label {
  font-size: 11px;
  color: #5a6a85;
  font-weight: 600;
  white-space: nowrap;
}

.m-section-more {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  background: transparent;
  border: none;
  font-size: 12px;
  color: #0d6bff;
  font-weight: 600;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 8px;
  transition: background 0.15s;
}

.m-section-more:active {
  background: #f0f6ff;
}

.m-notice-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.m-notice-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 8px;
  border-radius: 12px;
  transition: background 0.15s;
}

.m-notice-item:active {
  background: #f8faff;
}

.m-notice-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

.m-notice-content {
  flex: 1;
  min-width: 0;
}

.m-notice-title {
  font-size: 13px;
  font-weight: 600;
  color: #15213d;
  margin-bottom: 3px;
}

.m-notice-desc {
  font-size: 11px;
  color: #8c98ae;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.m-notice-time {
  font-size: 10px;
  color: #b3bdcf;
  font-weight: 500;
  flex-shrink: 0;
  margin-top: 2px;
}

.m-table-wrap {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  margin: 0 -6px;
  padding: 0 6px;
}

.m-data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.m-data-table th {
  text-align: left;
  padding: 10px 12px;
  font-weight: 600;
  color: #8c98ae;
  font-size: 11px;
  border-bottom: 1.5px solid #f0f4fa;
  white-space: nowrap;
  background: #fafbff;
}

.m-data-table th:first-child {
  border-radius: 10px 0 0 0;
}

.m-data-table th:last-child {
  border-radius: 0 10px 0 0;
}

.m-data-table td {
  padding: 12px;
  color: #15213d;
  border-bottom: 1px solid #f5f7fb;
  font-variant-numeric: tabular-nums;
  font-weight: 500;
}

.m-data-table tr:last-child td {
  border-bottom: none;
}

.m-data-table tr:last-child td:first-child {
  border-radius: 0 0 0 10px;
}

.m-data-table tr:last-child td:last-child {
  border-radius: 0 0 10px 0;
}

.m-data-table tr.row-alt {
  background: #fafbff;
}

.m-data-table tr.row-alt td {
  background: #fafbff;
}

.td-date {
  font-weight: 600;
  color: #5a6a85;
  white-space: nowrap;
}

.td-num {
  text-align: left;
}

.m-num-pill {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 100px;
  font-size: 11px;
  font-weight: 700;
}

.m-num-green {
  background: linear-gradient(135deg, #e2f8ee, #d4f5e2);
  color: #16bf78;
}

.m-num-purple {
  background: linear-gradient(135deg, #f0ebff, #e8dfff);
  color: #8b5cf6;
}

.m-num-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  margin-right: 5px;
  vertical-align: middle;
}

.m-dot-red {
  background: #ef4444;
  box-shadow: 0 0 6px rgba(239, 68, 68, 0.4);
}

.m-num-muted {
  color: #c4cddb;
  font-weight: 500;
}

.m-tip-card {
  background: linear-gradient(135deg, #f5f9ff 0%, #fafbff 50%, #fffdf5 100%);
  border: 1px solid #e6eefc;
  border-radius: 20px;
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  position: relative;
  overflow: hidden;
}

.m-tip-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, #fbbf24, #f59e0b, #fbbf24);
}

.m-tip-icon {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: linear-gradient(135deg, #fef3c7, #fde68a);
  color: #d97706;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(217, 119, 6, 0.15);
}

.m-tip-content {
  flex: 1;
  min-width: 0;
}

.m-tip-title {
  font-size: 14px;
  font-weight: 700;
  color: #15213d;
  margin-bottom: 4px;
}

.m-tip-desc {
  font-size: 11px;
  color: #72809a;
  line-height: 1.6;
}

.m-tip-btn {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 2px;
  height: 36px;
  padding: 0 14px;
  border: none;
  border-radius: 18px;
  background: linear-gradient(135deg, #0d6bff, #2580ff);
  color: white;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 14px rgba(13, 107, 255, 0.3);
  transition: transform 0.15s, box-shadow 0.15s;
}

.m-tip-btn:active {
  transform: scale(0.96);
  box-shadow: 0 2px 8px rgba(13, 107, 255, 0.25);
}

.m-safe-bottom {
  height: 90px;
}

@media (max-width: 375px) {
  .m-data {
    padding-left: 12px;
    padding-right: 12px;
  }
  .m-hero-card {
    padding: 18px 16px 14px;
    border-radius: 20px;
  }
  .m-hero-title {
    font-size: 26px;
  }
  .m-hero-stats {
    padding: 12px 10px;
  }
  .m-hero-stat-value {
    font-size: 20px;
  }
  .m-metric-value {
    font-size: 24px;
  }
  .m-metric-grid {
    gap: 10px;
  }
  .m-metric-card {
    padding: 14px;
  }
  .m-section {
    padding: 16px;
  }
  .m-overview-value {
    font-size: 22px;
  }
  .m-alert-icon {
    width: 40px;
    height: 40px;
  }
  .m-alert-value {
    font-size: 20px;
  }
  .m-quick-icon {
    width: 48px;
    height: 48px;
  }
}

@media (max-width: 360px) {
  .m-hero-card {
    padding: 16px 14px 12px;
    border-radius: 18px;
  }
  .m-hero-title {
    font-size: 24px;
  }
  .m-hero-stats {
    padding: 10px 8px;
  }
  .m-hero-stat-value {
    font-size: 18px;
  }
  .m-metric-value {
    font-size: 22px;
  }
  .m-metric-icon {
    width: 36px;
    height: 36px;
  }
  .m-overview-value {
    font-size: 20px;
  }
  .m-alert-grid {
    gap: 8px;
  }
  .m-alert-card {
    padding: 12px 8px;
  }
  .m-alert-icon {
    width: 38px;
    height: 38px;
    border-radius: 12px;
  }
  .m-alert-value {
    font-size: 18px;
  }
  .m-alert-label {
    font-size: 10px;
  }
  .m-quick-icon {
    width: 44px;
    height: 44px;
    border-radius: 14px;
  }
  .m-quick-label {
    font-size: 10px;
  }
}
</style>
