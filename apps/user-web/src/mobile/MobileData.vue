<template>
  <div class="m-data">
    <!-- 顶部 KPI 大卡 + 日期 tabs -->
    <section class="m-data-hero">
      <div class="m-data-hero-head">
        <div class="m-data-hero-badge">
          <span class="m-data-hero-dot"></span>
          <span>实时数据</span>
        </div>
        <h1 class="m-data-hero-title">数据面板</h1>
        <p class="m-data-hero-sub">{{ scopeLabel }} · 更新于 {{ updatedAt }}</p>
      </div>

      <div class="m-data-kpi-row">
        <div class="m-data-kpi-cell">
          <div class="m-data-kpi-value">{{ metricText(stats.orderCount) }}</div>
          <div class="m-data-kpi-label">今日订单</div>
        </div>
        <div class="m-data-kpi-divider"></div>
        <div class="m-data-kpi-cell">
          <div class="m-data-kpi-value m-data-kpi-value--success">{{ metricText(stats.deliverySuccessCount) }}</div>
          <div class="m-data-kpi-label">发货成功</div>
        </div>
        <div class="m-data-kpi-divider"></div>
        <div class="m-data-kpi-cell">
          <div class="m-data-kpi-value m-data-kpi-value--warning">{{ metricText(stats.pendingDeliveryCount) }}</div>
          <div class="m-data-kpi-label">待处理</div>
        </div>
      </div>

      <div class="m-data-date-tabs">
        <button
          v-for="tab in dateTabs"
          :key="tab.value"
          class="m-data-date-tab"
          :class="{ active: activeDate === tab.value }"
          :disabled="tab.disabled"
          @click="switchDate(tab.value)"
        >
          {{ tab.label }}
        </button>
      </div>
    </section>

    <div v-if="loading" class="m-data-loading">
      <div class="m-data-spinner"></div>
      <div class="m-data-loading-text">加载数据中...</div>
    </div>

    <MobileUnavailableState v-else-if="loadError" title="数据面板暂时无法加载" :description="loadError" @retry="loadAll" />

    <template v-else>
      <div v-if="!hasData" class="m-data-empty">
        <div class="m-data-empty-icon">
          <MIcon name="pieChart" :size="48" />
        </div>
        <div class="m-data-empty-title">暂无数据</div>
        <div class="m-data-empty-desc">当前时间段还没有运营数据，稍后再来看看</div>
      </div>

      <template v-else>
        <!-- 核心指标卡 2×3 -->
        <div class="m-data-metric-grid">
          <div
            v-for="metric in displayMetrics"
            :key="metric.key"
            class="m-data-metric-card"
          >
            <div class="m-data-metric-head">
              <span class="m-data-metric-label">{{ metric.label }}</span>
              <div class="m-data-metric-icon" :class="`m-data-metric-icon--${metric.key}`">
                <MIcon :name="metric.icon" :size="18" />
              </div>
            </div>
            <div class="m-data-metric-value" :class="`m-data-metric-value--${metric.key}`">{{ metric.display }}</div>
            <div class="m-data-metric-sub">{{ metric.sub }}</div>
          </div>
        </div>

        <!-- 业务趋势卡 -->
        <section class="m-data-card">
          <div class="m-data-card-header">
            <div class="m-data-card-title-wrap">
              <div class="m-data-card-title-icon m-data-title-icon--primary">
                <MIcon name="trendingUp" :size="18" />
              </div>
              <h2 class="m-data-card-title">业务趋势</h2>
              <span class="m-data-card-hint">近 {{ trendDays }} 天走势</span>
            </div>
            <div class="m-data-trend-pills">
              <button
                v-for="opt in trendRangeOptions"
                :key="opt.value"
                type="button"
                class="m-data-trend-pill"
                :class="{ active: trendDays === opt.value }"
                @click="switchTrendRange(opt.value)"
              >
                {{ opt.label }}
              </button>
            </div>
          </div>
          <div v-if="trendHasData" ref="trendChartEl" class="m-data-echart-box"></div>
          <div v-if="trendHasData" class="m-data-trend-legend">
            <span v-for="series in trendSeries" :key="series.name" class="m-data-trend-legend-item">
              <i :style="{ background: series.color }"></i>{{ series.name }}
            </span>
          </div>
          <div v-else class="m-data-chart-empty">
            <MIcon name="trend" :size="32" />
            <span>暂无趋势数据</span>
          </div>
        </section>

        <!-- 数据概览 2×2 -->
        <section class="m-data-card">
          <div class="m-data-card-header">
            <div class="m-data-card-title-wrap">
              <div class="m-data-card-title-icon m-data-title-icon--primary">
                <MIcon name="activity" :size="18" />
              </div>
              <h2 class="m-data-card-title">数据概览</h2>
            </div>
          </div>
          <div class="m-data-overview-grid">
            <div v-for="item in overviewItems" :key="item.label" class="m-data-overview-card">
              <div class="m-data-overview-icon" :class="`m-data-overview-icon--${item.icon}`">
                <MIcon :name="item.icon" :size="20" />
              </div>
              <div class="m-data-overview-info">
                <div class="m-data-overview-label">{{ item.label }}</div>
                <div class="m-data-overview-value" :class="`m-data-overview-value--${item.icon}`">{{ item.value }}</div>
              </div>
              <div class="m-data-overview-bar-wrap">
                <div class="m-data-overview-bar">
                  <div class="m-data-overview-bar-fill" :class="`m-data-overview-bar-fill--${item.icon}`" :style="{ width: item.pct + '%' }"></div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- 告警卡 3 列 -->
        <div class="m-data-alert-grid">
          <div v-for="alert in alertItems" :key="alert.label" class="m-data-alert-card" :class="`m-data-alert-card--${alert.icon}`">
            <div class="m-data-alert-icon" :class="`m-data-alert-icon--${alert.icon}`">
              <MIcon :name="alert.icon" :size="20" />
            </div>
            <div class="m-data-alert-info">
              <div class="m-data-alert-value" :class="`m-data-alert-value--${alert.icon}`">{{ alert.value }}</div>
              <div class="m-data-alert-label">{{ alert.label }}</div>
            </div>
          </div>
        </div>

        <!-- 快捷入口 4 列 -->
        <section class="m-data-card">
          <div class="m-data-card-header">
            <div class="m-data-card-title-wrap">
              <div class="m-data-card-title-icon m-data-title-icon--neutral">
                <MIcon name="grid" :size="18" />
              </div>
              <h2 class="m-data-card-title">快捷入口</h2>
            </div>
          </div>
          <div class="m-data-quick-grid">
            <button v-for="quick in quickEntries" :key="quick.key" class="m-data-quick-item" @click="$emit('navigate', quick.key)">
              <div class="m-data-quick-icon" :class="`m-data-quick-icon--${quick.key}`">
                <MIcon :name="quick.icon" :size="20" />
              </div>
              <span class="m-data-quick-label">{{ quick.label }}</span>
            </button>
          </div>
        </section>

        <!-- 最新动态 -->
        <section class="m-data-card">
          <div class="m-data-card-header">
            <div class="m-data-card-title-wrap">
              <div class="m-data-card-title-icon m-data-title-icon--warning">
                <MIcon name="bell" :size="18" />
              </div>
              <h2 class="m-data-card-title">最新动态</h2>
            </div>
            <button class="m-data-card-more" @click="$emit('navigate', 'messages')">
              查看全部
              <MIcon name="chevronRight" :size="14" />
            </button>
          </div>
          <div class="m-data-notice-list">
            <div v-for="(notice, idx) in noticeList" :key="notice.id || idx" class="m-data-notice-item">
              <div class="m-data-notice-icon" :class="`m-data-notice-icon--${notice.icon}`">
                <MIcon :name="notice.icon" :size="16" />
              </div>
              <div class="m-data-notice-content">
                <div class="m-data-notice-title">{{ notice.title }}</div>
                <div class="m-data-notice-desc">{{ notice.desc }}</div>
              </div>
              <div class="m-data-notice-time">{{ notice.time }}</div>
            </div>
            <div v-if="!notificationsLoadError && noticeList.length === 0" class="m-data-notice-empty">
              暂无最新通知
            </div>
          </div>
          <MobileUnavailableState
            v-if="notificationsLoadError"
            compact
            title="最近通知暂时不可用"
            :description="notificationsLoadError"
            @retry="loadNotifications"
          />
        </section>

        <!-- 趋势明细表 -->
        <section v-if="trendHasData" class="m-data-card">
          <div class="m-data-card-header">
            <div class="m-data-card-title-wrap">
              <div class="m-data-card-title-icon m-data-title-icon--purple">
                <MIcon name="list" :size="18" />
              </div>
              <h2 class="m-data-card-title">趋势明细</h2>
              <span class="m-data-card-hint">按日展示指标</span>
            </div>
            <button class="m-data-card-more" @click="$emit('navigate', 'data-detail')">
              查看详情
              <MIcon name="chevronRight" :size="14" />
            </button>
          </div>
          <div class="m-data-table-wrap">
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
                  <td class="td-num"><span class="m-data-num-pill m-data-num-pill--success">{{ row.success }}</span></td>
                  <td class="td-num"><span v-if="row.fail > 0" class="m-data-num-dot m-data-num-dot--danger"></span>{{ row.fail }}</td>
                  <td class="td-num"><span v-if="row.aiReply > 0" class="m-data-num-pill m-data-num-pill--purple">{{ row.aiReply }}</span><span v-else class="m-data-num-muted">0</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>
    </template>

    <div class="m-data-safe-bottom"></div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import MIcon from './MIcon.vue'
import MobileUnavailableState from './MobileUnavailableState.vue'
import { getDashboardSummary, getDashboardSalesTrend } from '../api/dashboard.js'
import { getNavigationNotifications } from '../api/navigation.js'
import { getLiteAccounts } from '../api/accounts.js'
import { recordsOfOrThrow } from '../utils/apiData.js'
import { isAccountCookieExpired } from '../utils/accountAuth.js'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])

defineEmits(['navigate', 'force-desktop', 'back'])

const dateTabs = [
  { label: '今日', value: 'today' },
  { label: '近7天', value: '7d' },
  { label: '近30天', value: '30d' }
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
  itemCount: 0,
  unreadMessage: null,
  cookieExpiredCount: null
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
    value: metricText(stats.unreadMessage),
    icon: 'message',
    color: '#f59e0b',
    bg: 'linear-gradient(135deg, #fffbeb, #fefce8)',
    iconBg: 'linear-gradient(135deg, #fef3c7, #fde68a)'
  },
  {
    label: 'Cookie 过期',
    value: metricText(stats.cookieExpiredCount),
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

const noticeList = ref([])
const notificationsLoadError = ref('')

function metricText(value) {
  return value === null || value === undefined ? '—' : value
}

function noticePalette(type) {
  const t = String(type || '').toLowerCase()
  if (t === 'success' || t === 'delivery' || t === 'shipping') {
    return { icon: 'checkCircle', color: '#16bf78', iconBg: 'linear-gradient(135deg, #dcfce7, #bbf7d0)' }
  }
  if (t === 'warning' || t === 'warn' || t === 'pending') {
    return { icon: 'alertTriangle', color: '#f59e0b', iconBg: 'linear-gradient(135deg, #fef3c7, #fde68a)' }
  }
  if (t === 'error' || t === 'fail' || t === 'failed') {
    return { icon: 'alertTriangle', color: '#ef4444', iconBg: 'linear-gradient(135deg, #fee2e2, #fecaca)' }
  }
  if (t === 'order' || t === 'bag' || t === 'trade') {
    return { icon: 'bag', color: '#0d6bff', iconBg: 'linear-gradient(135deg, #dbeafe, #bfdbfe)' }
  }
  if (t === 'ai' || t === 'bot' || t === 'chat' || t === 'reply') {
    return { icon: 'bot', color: '#8b5cf6', iconBg: 'linear-gradient(135deg, #ede9fe, #ddd6fe)' }
  }
  return { icon: 'bell', color: '#0d6bff', iconBg: 'linear-gradient(135deg, #e8f1ff, #dbeafe)' }
}

function formatNoticeTime(value) {
  if (!value) return ''
  const d = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(d.getTime())) return ''
  const now = new Date()
  const diff = (now - d) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${month}-${day}`
}

function normalizeNotice(n) {
  if (!n || typeof n !== 'object') return null
  const type = n.type || n.category
  const palette = noticePalette(type)
  const time = formatNoticeTime(n.createTime || n.createdAt || n.time || n.created_at)
  return {
    id: n.id ?? null,
    title: n.title || '系统通知',
    desc: n.content || n.message || n.desc || '',
    time,
    icon: n.icon || palette.icon,
    color: palette.color,
    iconBg: palette.iconBg
  }
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
  // 后端 /dashboard/summary 仅支持 accountId 过滤，不接受 date/range/days 参数，固定返回今日汇总
  // 切换 tab 时仍重新调用以触发加载状态与数据刷新
  const res = await getDashboardSummary()
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
  // 待回复消息：后端可能未返回该字段，保持 null 表示未提供，alertItems 显示为 "—"
  const unread = d.unreadMessage ?? d.unreadMessageCount
  stats.unreadMessage = unread === null || unread === undefined ? null : (Number(unread) || 0)
}

async function loadTrend() {
  // 后端 /dashboard/sales-trend 支持 days 参数（默认 7），按当前 trendDays 拉取对应天数趋势
  const res = await getDashboardSalesTrend({ days: trendDays.value })
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

async function loadAccounts() {
  // 统计 Cookie 过期账号数：调用 getLiteAccounts 获取账号列表，使用 isAccountCookieExpired 判断
  // 失败时不抛错（cookieExpiredCount 仅是次要指标），保持 null 表示未能加载
  try {
    const res = await getLiteAccounts({ page: 1, pageSize: 100 })
    const data = res?.data
    let list = []
    if (Array.isArray(data)) list = data
    else if (Array.isArray(data?.records)) list = data.records
    else if (Array.isArray(data?.list)) list = data.list
    else if (Array.isArray(data?.accounts)) list = data.accounts
    stats.cookieExpiredCount = list.filter(a => isAccountCookieExpired(a)).length
  } catch (error) {
    stats.cookieExpiredCount = null
  }
}

async function loadNotifications() {
  notificationsLoadError.value = ''
  try {
    const res = await getNavigationNotifications({ limit: 5 })
    const records = recordsOfOrThrow(res?.data, '最近通知响应格式异常').slice(0, 5)
    noticeList.value = records.map(normalizeNotice).filter(Boolean)
  } catch (error) {
    noticeList.value = []
    notificationsLoadError.value = error?.message || '请检查网络连接后重试。'
  }
}

function resetStats() {
  stats.orderCount = 0
  stats.deliverySuccessCount = 0
  stats.pendingDeliveryCount = 0
  stats.deliveryFailCount = 0
  stats.aiReplyCount = 0
  stats.itemCount = 0
  stats.unreadMessage = null
  stats.cookieExpiredCount = null
}

async function loadAll() {
  loading.value = true
  loadError.value = ''
  trendError.value = ''
  const [summaryResult, trendResult, accountsResult] = await Promise.allSettled([
    loadSummary(),
    loadTrend(),
    loadAccounts()
  ])
  if (summaryResult.status === 'rejected') {
    resetStats()
    loadError.value = summaryResult.reason?.message || '请检查网络连接后重试。'
  }
  if (trendResult.status === 'rejected') {
    trend.value = { dates: [], deliverySuccess: [], deliveryFail: [], aiReply: [] }
    trendError.value = trendResult.reason?.message || '请检查网络连接后重试。'
  }
  // accountsResult 失败已在 loadAccounts 内部处理（保持 null），不影响整体加载状态
  loading.value = false
  await nextTick()
  initTrendChart()
}

async function switchDate(value) {
  if (activeDate.value === value) return
  activeDate.value = value
  // 切换顶部时间范围 tab 时同步趋势天数，使趋势图/趋势表格随之更新
  // 后端 summary 接口仅支持今日汇总（不接受 date/range/days 参数），故仅 trend 受 days 影响
  if (value === '7d') trendDays.value = 7
  else if (value === '30d') trendDays.value = 30
  // today 保持当前 trendDays（默认 7），便于查看近期走势
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
  loadNotifications()
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
/* === 根容器 === */
.m-data {
  padding: var(--m-space-3) var(--m-space-3) 0;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
}

/* === 顶部 Hero：KPI 大卡 + 日期 tabs === */
.m-data-hero {
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-4);
  margin-bottom: var(--m-space-3);
  box-shadow: var(--m-shadow-card);
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
  padding: var(--m-space-1) var(--m-space-3);
  border-radius: var(--m-radius-pill);
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-semibold);
  margin-bottom: var(--m-space-3);
  border: 1px solid var(--m-color-success-border);
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
  font-weight: var(--m-font-weight-extrabold);
  color: var(--m-color-text-primary);
  line-height: var(--m-line-height-tight);
  letter-spacing: -0.3px;
}
.m-data-hero-sub {
  margin: 0;
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  line-height: var(--m-line-height-base);
}

/* KPI 行 */
.m-data-kpi-row {
  display: flex;
  align-items: stretch;
  padding: var(--m-space-3) 0;
  border-top: 1px solid var(--m-color-border-light);
  border-bottom: 1px solid var(--m-color-border-light);
  margin-bottom: var(--m-space-3);
}
.m-data-kpi-cell {
  flex: 1;
  min-width: 0;
  text-align: center;
  padding: 0 var(--m-space-2);
}
.m-data-kpi-value {
  font-size: var(--m-font-size-hero);
  font-weight: var(--m-font-weight-extrabold);
  color: var(--m-color-text-primary);
  line-height: var(--m-line-height-tight);
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.5px;
}
.m-data-kpi-value--success {
  color: var(--m-color-success);
}
.m-data-kpi-value--warning {
  color: var(--m-color-warning-text);
}
.m-data-kpi-divider {
  width: 1px;
  align-self: stretch;
  background: var(--m-color-border-light);
}
.m-data-kpi-label {
  margin-top: var(--m-space-1);
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  font-weight: var(--m-font-weight-medium);
}

/* 日期 tabs */
.m-data-date-tabs {
  display: flex;
  gap: var(--m-space-1);
  background: var(--m-color-bg-subtle);
  padding: var(--m-space-1);
  border-radius: var(--m-radius-md);
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
  transition: all 0.15s;
  font-family: inherit;
}
.m-data-date-tab.active {
  background: var(--m-color-bg-card);
  color: var(--m-color-primary);
  font-weight: var(--m-font-weight-semibold);
  box-shadow: var(--m-shadow-card);
}
.m-data-date-tab:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* === Loading === */
.m-data-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--m-space-12) var(--m-space-4);
  gap: var(--m-space-3);
}
.m-data-spinner {
  width: 28px;
  height: 28px;
  border: 2.5px solid var(--m-color-border);
  border-top-color: var(--m-color-primary);
  border-radius: var(--m-radius-circle);
  animation: m-data-spin 0.8s linear infinite;
}
@keyframes m-data-spin {
  to { transform: rotate(360deg); }
}
.m-data-loading-text {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}

/* === Empty === */
.m-data-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--m-space-12) var(--m-space-4);
  gap: var(--m-space-2);
}
.m-data-empty-icon {
  color: var(--m-color-text-disabled);
  margin-bottom: var(--m-space-2);
}
.m-data-empty-title {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-secondary);
}
.m-data-empty-desc {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}

/* === 核心指标卡 2×3 === */
.m-data-metric-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--m-space-3);
  margin-bottom: var(--m-space-3);
}
.m-data-metric-card {
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3);
  box-shadow: var(--m-shadow-card);
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
}
.m-data-metric-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.m-data-metric-label {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  font-weight: var(--m-font-weight-medium);
}
.m-data-metric-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--m-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-data-metric-icon--orderCount {
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
}
.m-data-metric-icon--deliverySuccessCount {
  background: var(--m-color-success-bg);
  color: var(--m-color-success);
}
.m-data-metric-icon--pendingDeliveryCount {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning);
}
.m-data-metric-icon--deliveryFailCount {
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger);
}
.m-data-metric-icon--aiReplyCount {
  background: var(--m-color-purple-bg);
  color: var(--m-color-purple);
}
.m-data-metric-icon--itemCount {
  background: var(--m-color-cyan-bg);
  color: var(--m-color-cyan);
}
.m-data-metric-value {
  font-size: var(--m-font-size-h1);
  font-weight: var(--m-font-weight-extrabold);
  color: var(--m-color-text-primary);
  line-height: var(--m-line-height-tight);
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.3px;
}
.m-data-metric-value--deliverySuccessCount {
  color: var(--m-color-success-text);
}
.m-data-metric-value--deliveryFailCount {
  color: var(--m-color-danger-text);
}
.m-data-metric-value--pendingDeliveryCount {
  color: var(--m-color-warning-text);
}
.m-data-metric-value--aiReplyCount {
  color: var(--m-color-purple);
}
.m-data-metric-sub {
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
}

/* === 通用卡片容器 === */
.m-data-card {
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-4);
  margin-bottom: var(--m-space-3);
  box-shadow: var(--m-shadow-card);
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
  border-radius: var(--m-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-data-title-icon--primary {
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
}
.m-data-title-icon--purple {
  background: var(--m-color-purple-bg);
  color: var(--m-color-purple);
}
.m-data-title-icon--warning {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning);
}
.m-data-title-icon--neutral {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-tertiary);
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
.m-data-card-more {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  background: transparent;
  border: none;
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-primary);
  cursor: pointer;
  padding: var(--m-space-1) var(--m-space-2);
  border-radius: var(--m-radius-md);
  font-family: inherit;
  transition: background 0.15s;
}
.m-data-card-more:active {
  background: var(--m-color-primary-bg);
}

/* === 趋势 pills === */
.m-data-trend-pills {
  display: flex;
  gap: var(--m-space-1);
  flex-shrink: 0;
}
.m-data-trend-pill {
  border: none;
  background: var(--m-color-bg-subtle);
  padding: var(--m-space-1) var(--m-space-2);
  border-radius: var(--m-radius-pill);
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-medium);
  color: var(--m-color-text-tertiary);
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s;
}
.m-data-trend-pill.active {
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
  font-weight: var(--m-font-weight-semibold);
}

/* === ECharts 容器 === */
.m-data-echart-box {
  width: 100%;
  height: 180px;
  min-height: 180px;
}
.m-data-trend-legend {
  display: flex;
  flex-wrap: wrap;
  gap: var(--m-space-3);
  margin-top: var(--m-space-2);
  padding-top: var(--m-space-2);
  border-top: 1px solid var(--m-color-border-light);
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
  width: 10px;
  height: 10px;
  border-radius: var(--m-radius-sm);
}
.m-data-chart-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-2);
  padding: var(--m-space-8) var(--m-space-4);
  color: var(--m-color-text-disabled);
  font-size: var(--m-font-size-caption);
}

/* === 数据概览 2×2 === */
.m-data-overview-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--m-space-3);
}
.m-data-overview-card {
  background: var(--m-color-bg-subtle);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3);
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
}
.m-data-overview-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--m-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-data-overview-icon--checkCircle {
  background: var(--m-color-success-bg);
  color: var(--m-color-success);
}
.m-data-overview-icon--bag {
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
}
.m-data-overview-icon--bot {
  background: var(--m-color-purple-bg);
  color: var(--m-color-purple);
}
.m-data-overview-icon--clock {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning);
}
.m-data-overview-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.m-data-overview-label {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  font-weight: var(--m-font-weight-medium);
}
.m-data-overview-value {
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
  line-height: var(--m-line-height-tight);
  font-variant-numeric: tabular-nums;
}
.m-data-overview-value--checkCircle {
  color: var(--m-color-success-text);
}
.m-data-overview-value--bag {
  color: var(--m-color-primary);
}
.m-data-overview-value--bot {
  color: var(--m-color-purple);
}
.m-data-overview-value--clock {
  color: var(--m-color-warning-text);
}
.m-data-overview-bar-wrap {
  margin-top: var(--m-space-1);
}
.m-data-overview-bar {
  height: 4px;
  background: var(--m-color-border);
  border-radius: var(--m-radius-pill);
  overflow: hidden;
}
.m-data-overview-bar-fill {
  height: 100%;
  border-radius: var(--m-radius-pill);
  transition: width 0.4s ease;
}
.m-data-overview-bar-fill--checkCircle {
  background: var(--m-color-success);
}
.m-data-overview-bar-fill--bag {
  background: var(--m-color-primary);
}
.m-data-overview-bar-fill--bot {
  background: var(--m-color-purple);
}
.m-data-overview-bar-fill--clock {
  background: var(--m-color-warning);
}

/* === 告警卡 3 列 === */
.m-data-alert-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-3);
}
.m-data-alert-card {
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3) var(--m-space-2);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--m-space-2);
  background: var(--m-color-bg-card);
}
.m-data-alert-card--alertTriangle {
  background: var(--m-color-warning-bg);
  border-color: var(--m-color-warning-border);
}
.m-data-alert-card--message {
  background: var(--m-color-primary-bg);
  border-color: var(--m-color-info-border);
}
.m-data-alert-card--wifiOff {
  background: var(--m-color-danger-bg);
  border-color: var(--m-color-danger-border);
}
.m-data-alert-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--m-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
}
.m-data-alert-icon--alertTriangle {
  background: var(--m-color-bg-card);
  color: var(--m-color-warning-text);
}
.m-data-alert-icon--message {
  background: var(--m-color-bg-card);
  color: var(--m-color-primary);
}
.m-data-alert-icon--wifiOff {
  background: var(--m-color-bg-card);
  color: var(--m-color-danger-text);
}
.m-data-alert-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.m-data-alert-value {
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
.m-data-alert-value--alertTriangle {
  color: var(--m-color-warning-text);
}
.m-data-alert-value--message {
  color: var(--m-color-primary);
}
.m-data-alert-value--wifiOff {
  color: var(--m-color-danger-text);
}
.m-data-alert-label {
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
  font-weight: var(--m-font-weight-medium);
  text-align: center;
}

/* === 快捷入口 4 列 === */
.m-data-quick-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--m-space-2);
}
.m-data-quick-item {
  border: none;
  background: transparent;
  padding: var(--m-space-2) var(--m-space-1);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--m-space-2);
  cursor: pointer;
  font-family: inherit;
  transition: transform 0.15s;
}
.m-data-quick-item:active {
  transform: scale(0.96);
}
.m-data-quick-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--m-radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
}
.m-data-quick-icon--products {
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
}
.m-data-quick-icon--orders {
  background: var(--m-color-success-bg);
  color: var(--m-color-success);
}
.m-data-quick-icon--messages {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning);
}
.m-data-quick-icon--workflow {
  background: var(--m-color-purple-bg);
  color: var(--m-color-purple);
}
.m-data-quick-icon--accounts {
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger);
}
.m-data-quick-icon--auto-delivery {
  background: var(--m-color-cyan-bg);
  color: var(--m-color-cyan);
}
.m-data-quick-icon--data {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning-text);
}
.m-data-quick-icon--profile {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
}
.m-data-quick-label {
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-secondary);
  text-align: center;
  line-height: 1.3;
  font-weight: var(--m-font-weight-medium);
}

/* === 最新动态列表 === */
.m-data-notice-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-1);
}
.m-data-notice-item {
  display: flex;
  align-items: flex-start;
  gap: var(--m-space-3);
  padding: var(--m-space-2) var(--m-space-1);
  border-radius: var(--m-radius-md);
  transition: background 0.15s;
}
.m-data-notice-item:active {
  background: var(--m-color-bg-subtle);
}
.m-data-notice-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--m-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-data-notice-icon--checkCircle {
  background: var(--m-color-success-bg);
  color: var(--m-color-success);
}
.m-data-notice-icon--alertTriangle {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning);
}
.m-data-notice-icon--bag {
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
}
.m-data-notice-icon--bot {
  background: var(--m-color-purple-bg);
  color: var(--m-color-purple);
}
.m-data-notice-icon--bell {
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
}
.m-data-notice-icon--message {
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
}
.m-data-notice-content {
  flex: 1;
  min-width: 0;
}
.m-data-notice-title {
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  margin-bottom: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-data-notice-desc {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  line-height: var(--m-line-height-base);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-data-notice-time {
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
  font-weight: var(--m-font-weight-medium);
  flex-shrink: 0;
  margin-top: 2px;
}
.m-data-notice-empty {
  padding: var(--m-space-6) var(--m-space-3);
  text-align: center;
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  font-weight: var(--m-font-weight-medium);
}

/* === 趋势明细表 === */
.m-data-table-wrap {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  margin: 0 calc(-1 * var(--m-space-1));
  padding: 0 var(--m-space-1);
}
.m-data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--m-font-size-caption);
  font-variant-numeric: tabular-nums;
}
.m-data-table th {
  text-align: left;
  padding: var(--m-space-2) var(--m-space-3);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-tiny);
  border-bottom: 1px solid var(--m-color-border);
  white-space: nowrap;
  background: var(--m-color-bg-subtle);
}
.m-data-table th:first-child {
  border-radius: var(--m-radius-md) 0 0 0;
}
.m-data-table th:last-child {
  border-radius: 0 var(--m-radius-md) 0 0;
}
.m-data-table td {
  padding: var(--m-space-3);
  color: var(--m-color-text-primary);
  border-bottom: 1px solid var(--m-color-border-light);
  font-weight: var(--m-font-weight-medium);
}
.m-data-table tr:last-child td {
  border-bottom: none;
}
.m-data-table tr:last-child td:first-child {
  border-radius: 0 0 0 var(--m-radius-md);
}
.m-data-table tr:last-child td:last-child {
  border-radius: 0 0 var(--m-radius-md) 0;
}
.m-data-table tr.row-alt td {
  background: var(--m-color-bg-subtle);
}
.m-data-table .td-date {
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-secondary);
  white-space: nowrap;
}
.m-data-table .td-num {
  text-align: left;
}
.m-data-num-pill {
  display: inline-flex;
  align-items: center;
  padding: var(--m-space-1) var(--m-space-2);
  border-radius: var(--m-radius-pill);
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-bold);
}
.m-data-num-pill--success {
  background: var(--m-color-success-bg);
  color: var(--m-color-success-text);
}
.m-data-num-pill--purple {
  background: var(--m-color-purple-bg);
  color: var(--m-color-purple);
}
.m-data-num-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: var(--m-radius-circle);
  margin-right: var(--m-space-1);
  vertical-align: middle;
}
.m-data-num-dot--danger {
  background: var(--m-color-danger);
}
.m-data-num-muted {
  color: var(--m-color-text-disabled);
  font-weight: var(--m-font-weight-medium);
}

/* === 底部安全区 === */
.m-data-safe-bottom {
  height: 80px;
}

/* === 响应式：小屏适配 === */
@media (max-width: 360px) {
  .m-data {
    padding: var(--m-space-2) var(--m-space-2) 0;
  }
  .m-data-hero {
    padding: var(--m-space-3);
  }
  .m-data-kpi-value {
    font-size: var(--m-font-size-h1);
  }
  .m-data-metric-value {
    font-size: var(--m-font-size-h2);
  }
  .m-data-quick-grid {
    gap: var(--m-space-1);
  }
  .m-data-quick-icon {
    width: 40px;
    height: 40px;
    border-radius: var(--m-radius-md);
  }
  .m-data-quick-label {
    font-size: 9px;
  }
  .m-data-alert-grid {
    gap: var(--m-space-1);
  }
  .m-data-alert-icon {
    width: 32px;
    height: 32px;
  }
  .m-data-alert-value {
    font-size: var(--m-font-size-h3);
  }
  .m-data-overview-grid {
    gap: var(--m-space-2);
  }
  .m-data-echart-box {
    height: 150px;
    min-height: 150px;
  }
}
</style>
