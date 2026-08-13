<template>
  <div class="fsd-page fish-shop-analysis-page">
    <!-- 页面级视图切换：数据分析 / 流量分布 -->
    <div class="view-tabs">
      <button
        v-for="v in viewTabs"
        :key="v.key"
        type="button"
        :class="['view-tab', { active: viewMode === v.key }]"
        @click="switchView(v.key)"
      >
        {{ v.label }}
      </button>
    </div>

    <template v-if="viewMode === 'analysis'">
    <!-- ===== 页面外层标题 ===== -->
    <div class="page-title-section">
      <div class="header-badge">
        <span class="header-dot"></span>
        <span>鱼小铺官方数据罗盘</span>
      </div>
      <h1 class="page-title">鱼小铺数据分析</h1>
      <p v-if="realDateRangeText" class="page-subtitle">
        <span class="meta-val">{{ scopeLabel }}</span>
        <span class="meta-sep">·</span>
        <span class="meta-key">数据时间</span>
        <span class="meta-val">{{ realDateRangeText }}</span>
      </p>
      <p v-else-if="!loading && !error" class="page-subtitle">
        <span class="meta-val">{{ scopeLabel }}</span>
        <span class="meta-sep">·</span>
        <span class="meta-val">{{ dateLabel }}</span>
      </p>
      <p v-else-if="loading" class="page-subtitle loading">
        <span class="loading-dots"><i></i><i></i><i></i></span>
        <span>正在加载鱼小铺卖家数据</span>
      </p>
    </div>

    <!-- ===== 页面筛选信息卡 ===== -->
    <div class="filter-card">
      <div class="filter-info">
        <span class="filter-block-name">鱼小铺数据分析</span>
        <span class="filter-sep">·</span>
        <span class="filter-label">数据时间</span>
        <span class="filter-value">{{ realDateRangeText || dateLabel }}</span>
        <span class="filter-sep">·</span>
        <span class="filter-label">更新于</span>
        <span class="filter-value">{{ updatedAt }}</span>
      </div>
      <div class="filter-controls">
        <div class="control-item">
          <label>账号</label>
          <select
            v-model="selectedAccountId"
            class="form-select"
            :disabled="accountsLoading || fishShopAccounts.length === 0"
          >
            <option value="all">全部鱼小铺账号</option>
            <option
              v-for="acc in fishShopAccounts"
              :key="acc.id"
              :value="acc.id"
            >
              {{ formatAccountLabel(acc) }}
            </option>
          </select>
        </div>
        <div class="control-item">
          <label>时间范围</label>
          <div class="range-pills">
            <button
              v-for="opt in dateRangeOptions"
              :key="opt.value"
              type="button"
              :class="['range-pill', { active: dateType === opt.value }]"
              :disabled="loading"
              @click="switchDateType(opt.value)"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>
        <button class="refresh-btn" :disabled="loading || fishShopAccounts.length === 0" @click="load">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" :class="{ 'spin': loading }">
            <path d="M21 12a9 9 0 11-6.219-8.56" /><polyline points="21 3 21 9 15 9" />
          </svg>
          {{ loading ? '加载中' : '刷新' }}
        </button>
      </div>
    </div>

    <!-- 部分失败提示 -->
    <div v-if="partialFailureBanner" class="error-banner warn">
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" /></svg>
      <span>{{ partialFailureBanner }}</span>
      <button v-if="!loading" type="button" class="retry-link" @click="load">重试</button>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="error-banner">
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>
      {{ error }}
      <button v-if="!loading" type="button" class="retry-link" @click="load">重试</button>
    </div>

    <!-- 空状态：没有鱼小铺账号 -->
    <EmptyState
      v-if="!accountsLoading && fishShopAccounts.length === 0"
      icon="🐟"
      title="当前没有可用的鱼小铺账号"
      description="绑定或升级为鱼小铺账号后可查看数据分析。普通闲鱼账号不参与鱼小铺数据分析。"
    />

    <!-- 加载骨架屏 -->
    <div v-else-if="loading && !summary" class="skeleton-wrap">
      <div class="skeleton-top-row">
        <div class="skeleton-kpi-grid">
          <div v-for="i in 4" :key="i" class="skeleton-card">
            <div class="sk-icon"></div>
            <div class="sk-body">
              <div class="sk-line sm"></div>
              <div class="sk-line lg"></div>
              <div class="sk-line sm"></div>
            </div>
          </div>
        </div>
        <div class="skeleton-chart">
          <div class="sk-line lg"></div>
          <div class="sk-chart-body"></div>
        </div>
      </div>
    </div>

    <!-- 空状态：接口无业务数据 -->
    <EmptyState
      v-else-if="!loading && !error && isEmptyData"
      icon="📊"
      title="当前周期暂无数据"
      :description="`已选择 ${scopeLabel}，但鱼小铺数据罗盘未返回当前周期数据。`"
    />

    <template v-else-if="summary && !isEmptyData">
      <!-- 全部账号说明 -->
      <div v-if="aovNote" class="fsd-note">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10" /><line x1="12" y1="16" x2="12" y2="12" /><line x1="12" y1="8" x2="12.01" y2="8" /></svg>
        <span>{{ aovNote }}</span>
      </div>

      <!-- 核心指标 + 趋势分析（横向 12 列布局） -->
      <div class="top-row">
        <div class="kpi-grid">
          <div
            v-for="(kpi, idx) in heroKpis"
            :key="kpi.key"
            class="kpi-card"
            :style="{ '--kpi-color': kpi.color, '--kpi-delay': idx * 80 + 'ms' }"
          >
            <div class="kpi-icon" :style="{ background: kpi.color + '14', color: kpi.color }">{{ kpi.icon }}</div>
            <div class="kpi-body">
              <span class="kpi-label">{{ kpi.label }}</span>
              <div class="kpi-value-row">
                <strong class="kpi-value">{{ kpi.display }}</strong>
                <span
                  v-if="kpi.ratio !== null"
                  :class="['kpi-trend', 'trend-pill', ratioClass(kpi.ratio)]"
                >
                  <span class="trend-arrow">{{ ratioArrow(kpi.ratio) }}</span>
                  {{ ratioPercent(kpi.ratio) }}
                </span>
              </div>
            </div>
          </div>
        </div>
        <CardPanel class="trend-panel" body-padding="0">
          <template #title>
            <div class="panel-title-row">
              <span class="panel-title-text">趋势分析</span>
              <span class="panel-title-desc">{{ trendDesc }}</span>
            </div>
          </template>
          <template #action>
            <div class="metric-switcher">
              <label>指标</label>
              <select v-model="trendMetricKey" class="metric-select">
                <option v-for="m in trendMetricOptions" :key="m.key" :value="m.key">{{ m.label }}</option>
              </select>
            </div>
          </template>
          <div v-if="trendAvailable" ref="trendChartEl" class="echart-box trend-box"></div>
          <EmptyState v-else icon="📈" title="趋势不可用" description="当前周期暂无趋势数据" />
        </CardPanel>
      </div>

      <!-- 智能洞察 -->
      <div v-if="insights.length > 0" class="insights-panel">
        <div class="insights-head">
          <div class="insights-title">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z" />
              <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z" />
            </svg>
            <span>智能洞察</span>
            <span class="insights-tag">AI</span>
          </div>
          <span class="insights-sub">基于当前周期数据自动生成</span>
        </div>
        <div class="insights-grid">
          <div
            v-for="(insight, idx) in insights"
            :key="idx"
            class="insight-card"
            :style="{ '--insight-color': insight.color, '--insight-delay': idx * 70 + 'ms' }"
          >
            <div class="insight-icon-wrap">
              <div class="insight-icon-bg"></div>
              <span class="insight-icon">{{ insight.icon }}</span>
            </div>
            <div class="insight-body">
              <strong class="insight-title">{{ insight.title }}</strong>
              <p class="insight-desc">{{ insight.desc }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- 转化漏斗 -->
      <CardPanel v-if="funnelAvailable" class="funnel-panel" body-padding="0">
        <template #title>
          <div class="panel-title-row">
            <span class="panel-title-text">转化漏斗</span>
            <span class="panel-title-desc">曝光 → 浏览 → 访问 → 咨询 → 成交</span>
          </div>
        </template>
        <template #action>
          <span class="funnel-total">总曝光 {{ formatInt(totalFunnelExposure) }}</span>
        </template>
        <div class="funnel-wrap">
          <div
            v-for="(stage, idx) in funnelStages"
            :key="stage.key"
            class="funnel-stage-col"
          >
            <div
              class="funnel-stage"
              :style="{ '--stage-color': stage.color, '--stage-delay': idx * 80 + 'ms', '--stage-pct': stage.percent + '%' }"
            >
              <div class="funnel-stage-head">
                <span class="funnel-stage-name">{{ stage.name }}</span>
                <span class="funnel-stage-value">{{ formatInt(stage.value) }}</span>
              </div>
              <div class="funnel-bar-track">
                <div class="funnel-bar-fill" :style="{ width: stage.percent + '%' }"></div>
              </div>
              <div class="funnel-stage-foot">
                <span class="funnel-stage-pct">占比 {{ stage.percent.toFixed(1) }}%</span>
                <span v-if="stage.convRate !== null" class="funnel-stage-conv">
                  环节转化 {{ stage.convRate.toFixed(1) }}%
                </span>
                <span v-else class="funnel-stage-conv muted">起始</span>
              </div>
            </div>
            <!-- 流失指示器 -->
            <div v-if="!stage.isLast && stage.dropOff !== null && stage.dropOff > 0" class="funnel-dropoff">
              <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="6 9 12 15 18 9" />
              </svg>
              <span class="dropoff-text">流失 {{ formatInt(stage.dropOff) }}</span>
              <span class="dropoff-pct">{{ stage.dropOffPct.toFixed(1) }}%</span>
            </div>
          </div>
        </div>
      </CardPanel>

      <!-- 指标分组导航（成交转化 / 流量曝光 / 访问咨询） -->
      <div class="metric-groups">
        <div
          v-for="group in otherMetricGroups"
          :key="group.key"
          class="metric-group"
        >
          <div class="metric-group-head">
            <span class="metric-group-icon" :style="{ color: group.color }">
              <component :is="group.iconComp" />
            </span>
            <span class="metric-group-title">{{ group.title }}</span>
            <span class="metric-group-count">{{ group.cards.length }} 项</span>
          </div>
          <div class="metrics-strip" :class="`cols-${Math.min(group.cards.length, 4)}`">
            <div
              v-for="(m, i) in group.cards"
              :key="m.key"
              class="metric-card"
              :style="{ '--delay': i * 60 + 'ms', '--accent': m.color }"
            >
              <div class="metric-icon-wrap">
                <div class="metric-icon-bg"></div>
                <component :is="m.iconComp" class="metric-icon" />
              </div>
              <div class="metric-body">
                <span class="metric-label">{{ m.title }}</span>
                <strong class="metric-value" :class="{ 'metric-loading': m.value === null }">{{ m.display }}</strong>
                <div class="metric-sub">
                  <span v-if="m.ratio === null" class="metric-sub-text">{{ m.sub }}</span>
                  <span v-else :class="['metric-trend', 'trend-pill', ratioClass(m.ratio)]">
                    <span class="trend-arrow">{{ ratioArrow(m.ratio) }}</span>
                    <span>{{ ratioPercent(m.ratio) }}</span>
                  </span>
                  <span v-if="m.lastDisplay" class="metric-last">上期 {{ m.lastDisplay }}</span>
                </div>
              </div>
              <div v-if="m.sparkPoints" class="metric-spark">
                <svg viewBox="0 0 64 26" preserveAspectRatio="none" class="spark-svg">
                  <polygon :points="m.sparkFill" :fill="m.sparkColor" opacity="0.12" />
                  <polyline :points="m.sparkPoints" fill="none" :stroke="m.sparkColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
                </svg>
              </div>
            </div>
          </div>
        </div>

        <!-- 商品库存：横向宽卡（方案 B） -->
        <div class="metric-group inventory-group">
          <div class="metric-group-head">
            <span class="metric-group-icon" :style="{ color: inventoryGroup.color }">
              <component :is="inventoryGroup.iconComp" />
            </span>
            <span class="metric-group-title">{{ inventoryGroup.title }}</span>
            <span class="metric-group-count">{{ inventoryGroup.cards.length }} 项</span>
          </div>
          <div class="inventory-wide-card" :style="{ '--accent': inventoryCard.color }">
            <div class="inventory-left">
              <div class="metric-icon-wrap">
                <div class="metric-icon-bg"></div>
                <component :is="inventoryCard.iconComp" class="metric-icon" />
              </div>
              <div class="inventory-main">
                <span class="metric-label">{{ inventoryCard.title }}</span>
                <strong class="metric-value" :class="{ 'metric-loading': inventoryCard.value === null }">{{ inventoryCard.display }}</strong>
              </div>
            </div>
            <div class="inventory-middle">
              <span v-if="inventoryCard.ratio === null" class="metric-sub-text">{{ inventoryCard.sub }}</span>
              <span v-else :class="['metric-trend', 'trend-pill', ratioClass(inventoryCard.ratio)]">
                <span class="trend-arrow">{{ ratioArrow(inventoryCard.ratio) }}</span>
                <span>{{ ratioPercent(inventoryCard.ratio) }}</span>
              </span>
              <span v-if="inventoryCard.lastDisplay" class="metric-last">上期 {{ inventoryCard.lastDisplay }}</span>
            </div>
            <div v-if="inventoryCard.sparkPoints" class="inventory-spark">
              <svg viewBox="0 0 64 26" preserveAspectRatio="none" class="spark-svg">
                <polygon :points="inventoryCard.sparkFill" :fill="inventoryCard.sparkColor" opacity="0.12" />
                <polyline :points="inventoryCard.sparkPoints" fill="none" :stroke="inventoryCard.sparkColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </div>
          </div>
        </div>
      </div>

      <!-- 页面底部轻量说明 -->
      <div class="page-footer">
        {{ scopeLabel }} · {{ dateLabel }} · 数据更新于 {{ updatedAt }}
      </div>
    </template>
    </template>

    <template v-else>
      <FishShopBrowseSection />
    </template>
  </div>
</template>

<script setup>
import { computed, h, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import CardPanel from '../components/CardPanel.vue'
import EmptyState from '../components/EmptyState.vue'
import FishShopBrowseSection from '../components/FishShopBrowseSection.vue'
import { getLiteAccounts } from '../api/accounts.js'
import { getFishShopDataSummary } from '../api/fishShopData.js'
import { accountName, formatMoney, formatNumber, timeText } from '../utils/format.js'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  LineChart,
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  CanvasRenderer,
])

// 配色（与 DataPage.vue 保持一致）
const C = {
  primary: '#0d6bff',
  green: '#16bf78',
  red: '#ff5b61',
  orange: '#ff9f22',
  purple: '#8b5cf6',
  cyan: '#11b5d8',
  slate: '#72809a',
  pink: '#ec4899',
}

// ===== 内联 SVG 图标组件（避免依赖 Icon 组件的预定义图标名）=====
const makeIcon = (paths) => () => h('svg', {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  'stroke-width': 2,
  'stroke-linecap': 'round',
  'stroke-linejoin': 'round',
  width: 20,
  height: 20,
}, paths.map(p => h('path', { d: p.d, ...(p.fill ? { fill: p.fill } : {}) })))

const IconPay = makeIcon([{ d: 'M12 1v22' }, { d: 'M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6' }])
const IconOrder = makeIcon([{ d: 'M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z' }, { d: 'M3 6h18' }, { d: 'M16 10a4 4 0 0 1-8 0' }])
const IconUser = makeIcon([{ d: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2' }, { d: 'M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z' }])
const IconPrice = makeIcon([{ d: 'M12 2v20' }, { d: 'M17 5.5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6' }])
const IconEye = makeIcon([{ d: 'M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z' }, { d: 'M12 12a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z' }], )
const IconView = makeIcon([{ d: 'M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z' }, { d: 'M12 12a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z' }])
const IconVisit = makeIcon([{ d: 'M3 12h4l3-9 4 18 3-9h4' }])
const IconChat = makeIcon([{ d: 'M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2Z' }])
const IconBox = makeIcon([{ d: 'M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z' }, { d: 'm3.3 7 8.7 5 8.7-5' }, { d: 'M12 22V12' }])

// 时间范围选项
const dateRangeOptions = [
  { value: 'recent1d', label: '近1天' },
  { value: 'recent7d', label: '近7天' },
  { value: 'recent30d', label: '近30天' },
]

// 指标分组定义
const metricGroups = computed(() => [
  {
    key: 'deal',
    title: '成交转化',
    color: C.primary,
    iconComp: IconPay,
    cards: buildGroup(['payAmt', 'payOrdCnt', 'payByrCnt', 'aov']),
  },
  {
    key: 'traffic',
    title: '流量曝光',
    color: C.orange,
    iconComp: IconEye,
    cards: buildGroup(['showPv', 'showUv', 'ipv', 'ipvUv']),
  },
  {
    key: 'visit',
    title: '访问咨询',
    color: C.cyan,
    iconComp: IconVisit,
    cards: buildGroup(['vstPv', 'vstUv', 'chatUv']),
  },
  {
    key: 'inventory',
    title: '商品库存',
    color: C.slate,
    iconComp: IconBox,
    cards: buildGroup(['onlCnt']),
  },
])

const metricDefMap = {
  payAmt: { key: 'payAmt', title: '成交金额', iconComp: IconPay, color: C.primary, type: 'money' },
  payOrdCnt: { key: 'payOrdCnt', title: '支付订单数', iconComp: IconOrder, color: C.cyan, type: 'int' },
  payByrCnt: { key: 'payByrCnt', title: '支付买家数', iconComp: IconUser, color: C.green, type: 'int' },
  aov: { key: 'aov', title: '客单价', iconComp: IconPrice, color: C.purple, type: 'money' },
  showPv: { key: 'showPv', title: '商品曝光次数', iconComp: IconEye, color: C.orange, type: 'int' },
  showUv: { key: 'showUv', title: '商品曝光人数', iconComp: IconEye, color: C.orange, type: 'int' },
  ipv: { key: 'ipv', title: '商品浏览次数', iconComp: IconView, color: C.primary, type: 'int' },
  ipvUv: { key: 'ipvUv', title: '商品浏览人数', iconComp: IconView, color: C.primary, type: 'int' },
  vstPv: { key: 'vstPv', title: '访问次数', iconComp: IconVisit, color: C.cyan, type: 'int' },
  vstUv: { key: 'vstUv', title: '访客人数', iconComp: IconVisit, color: C.cyan, type: 'int' },
  chatUv: { key: 'chatUv', title: '咨询人数', iconComp: IconChat, color: C.purple, type: 'int' },
  onlCnt: { key: 'onlCnt', title: '在线商品数', iconComp: IconBox, color: C.slate, type: 'int' },
}

function buildGroup(keys) {
  if (!summary.value || !summary.value.banners) {
    return keys.map(k => {
      const def = metricDefMap[k]
      return { ...def, value: null, display: '—', lastDisplay: '', ratio: null, sub: '暂无对比', sparkPoints: null, sparkFill: null, sparkColor: C.slate }
    })
  }
  const banners = summary.value.banners
  return keys.map(k => {
    const def = metricDefMap[k]
    const item = banners[k] || {}
    const value = item.data
    const lastValue = item.lastData
    const ratio = item.ratio
    const ratioNum = ratio === null || ratio === undefined ? null : Number(ratio)
    return {
      ...def,
      value: value === null || value === undefined ? null : value,
      display: formatMetric(value, def.type, item),
      lastDisplay: formatMetric(lastValue, def.type, item, true),
      ratio: ratioNum,
      sub: ratio === null || ratio === undefined ? '暂无对比' : '',
      sparkPoints: computeSparkPoints(k),
      sparkFill: computeSparkFill(k),
      sparkColor: ratioNum === null ? C.slate : (ratioNum > 0 ? C.green : ratioNum < 0 ? C.red : C.slate),
    }
  })
}

// 计算指标卡迷你 sparkline 折线点
function computeSparkPoints(metricKey) {
  if (!summary.value || !summary.value.graph || summary.value.graph.length === 0) return null
  const graph = summary.value.graph
  const values = graph.map(p => numOrZero(p[metricKey]))
  if (values.every(v => v === 0)) return null
  const max = Math.max(...values)
  const min = Math.min(...values)
  const range = max - min || 1
  const w = 64, h = 26
  return values.map((v, i) => {
    const x = values.length === 1 ? w / 2 : (i / (values.length - 1)) * w
    const y = h - ((v - min) / range) * (h - 4) - 2
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
}

// 计算 sparkline 填充多边形点
function computeSparkFill(metricKey) {
  const points = computeSparkPoints(metricKey)
  if (!points) return null
  const w = 64, h = 26
  const pts = points.split(' ')
  return `0,${h} ${pts.join(' ')} ${w},${h}`
}

// 趋势图可选指标
const trendMetricOptions = [
  { key: 'payAmt', label: '成交金额', type: 'money' },
  { key: 'payOrdCnt', label: '支付订单数', type: 'int' },
  { key: 'showPv', label: '商品曝光次数', type: 'int' },
  { key: 'showUv', label: '商品曝光人数', type: 'int' },
  { key: 'ipv', label: '商品浏览次数', type: 'int' },
  { key: 'ipvUv', label: '商品浏览人数', type: 'int' },
  { key: 'vstPv', label: '访问次数', type: 'int' },
  { key: 'vstUv', label: '访客人数', type: 'int' },
  { key: 'chatUv', label: '咨询人数', type: 'int' },
]

// ===== 转化漏斗 =====
const funnelStages = computed(() => {
  if (!summary.value || !summary.value.banners) return []
  const b = summary.value.banners
  const stages = [
    { key: 'showUv', name: '曝光人数', value: numOrZero(b.showUv?.data), color: C.orange, desc: '商品被用户看到的去重人数' },
    { key: 'ipvUv', name: '浏览人数', value: numOrZero(b.ipvUv?.data), color: C.primary, desc: '点击进入商品详情的去重人数' },
    { key: 'vstUv', name: '访客人数', value: numOrZero(b.vstUv?.data), color: C.cyan, desc: '访问店铺的去重人数' },
    { key: 'chatUv', name: '咨询人数', value: numOrZero(b.chatUv?.data), color: C.purple, desc: '发起咨询聊天的去重人数' },
    { key: 'payByrCnt', name: '支付买家', value: numOrZero(b.payByrCnt?.data), color: C.green, desc: '完成支付的去重买家数' },
  ]
  const max = Math.max(...stages.map(s => s.value), 1)
  let prev = null
  return stages.map((s, idx) => {
    const percent = max > 0 ? (s.value / max) * 100 : 0
    const convRate = prev !== null && prev > 0 ? (s.value / prev) * 100 : null
    const dropOff = prev !== null ? Math.max(0, prev - s.value) : null
    const dropOffPct = prev !== null && prev > 0 ? ((prev - s.value) / prev) * 100 : null
    prev = s.value
    return { ...s, percent, convRate, dropOff, dropOffPct, isLast: idx === stages.length - 1 }
  })
})

const funnelAvailable = computed(() => funnelStages.value.length > 0 && totalFunnelExposure.value > 0)
const totalFunnelExposure = computed(() => {
  const stages = funnelStages.value
  return stages.length > 0 ? stages[0].value : 0
})

// ===== 智能洞察 =====
const insights = computed(() => {
  if (!summary.value || !summary.value.banners) return []
  const b = summary.value.banners
  const list = []

  // 1. 找出增长最高和下降最多的指标
  const ratioCandidates = []
  const metricLabels = {
    payAmt: '成交金额', payOrdCnt: '支付订单数', payByrCnt: '支付买家数', aov: '客单价',
    showPv: '商品曝光次数', showUv: '商品曝光人数', ipv: '商品浏览次数', ipvUv: '商品浏览人数',
    vstPv: '访问次数', vstUv: '访客人数', chatUv: '咨询人数', onlCnt: '在线商品数',
  }
  Object.keys(b).forEach(key => {
    const item = b[key]
    if (!item || item.ratio === null || item.ratio === undefined) return
    const ratio = Number(item.ratio)
    if (!Number.isFinite(ratio)) return
    const value = item.data
    if (value === null || value === undefined || value === 0) return
    ratioCandidates.push({ key, label: metricLabels[key] || key, ratio, value })
  })

  if (ratioCandidates.length > 0) {
    // 最大增长
    const top = [...ratioCandidates].sort((a, b) => b.ratio - a.ratio)[0]
    if (top.ratio > 0.001) {
      list.push({
        type: 'up',
        icon: '↑',
        title: `${top.label}环比增长 ${(top.ratio * 100).toFixed(1)}%`,
        desc: '表现优异，可继续保持当前运营策略',
        color: C.green,
      })
    }
    // 最大下降
    const bottom = [...ratioCandidates].sort((a, b) => a.ratio - b.ratio)[0]
    if (bottom.ratio < -0.001) {
      list.push({
        type: 'down',
        icon: '↓',
        title: `${bottom.label}环比下降 ${Math.abs(bottom.ratio * 100).toFixed(1)}%`,
        desc: '建议关注相关环节，排查影响因素',
        color: C.red,
      })
    }
  }

  // 2. 整体转化率（曝光 → 支付）
  const exposure = numOrZero(b.showUv?.data)
  const payByr = numOrZero(b.payByrCnt?.data)
  if (exposure > 0 && payByr > 0) {
    const rate = (payByr / exposure) * 100
    let desc
    if (rate >= 5) desc = '转化效率优秀，高于行业常见水平'
    else if (rate >= 2) desc = '转化效率良好，仍有优化空间'
    else if (rate >= 1) desc = '转化效率偏低，建议优化商品详情与咨询承接'
    else desc = '转化效率较低，建议从曝光精准度与详情页质量入手'
    list.push({
      type: 'info',
      icon: '◉',
      title: `整体转化率 ${rate.toFixed(2)}%`,
      desc,
      color: C.primary,
    })
  }

  // 3. 趋势峰值/谷值
  const graph = summary.value.graph || []
  if (graph.length > 1) {
    const def = trendMetricDef.value
    let peakIdx = 0, peakVal = -Infinity
    let troughIdx = 0, troughVal = Infinity
    graph.forEach((p, idx) => {
      const v = numOrZero(p[trendMetricKey.value])
      if (v > peakVal) { peakVal = v; peakIdx = idx }
      if (v < troughVal) { troughVal = v; troughIdx = idx }
    })
    if (peakVal > 0 && peakIdx !== troughIdx) {
      const peakDate = formatDs(graph[peakIdx].ds)
      const peakText = def.type === 'money' ? `¥${formatNumber(peakVal)}` : formatNumber(peakVal)
      list.push({
        type: 'peak',
        icon: '★',
        title: `${peakDate} 达到 ${def.label} 峰值`,
        desc: `当日 ${def.label} ${peakText}，为本期最高点`,
        color: C.orange,
      })
    }
  }

  return list.slice(0, 4)
})

function numOrZero(v) {
  if (v === null || v === undefined || v === '') return 0
  const n = Number(v)
  return Number.isFinite(n) ? n : 0
}

// ===== 页面级视图切换：数据分析 / 流量分布 =====
const viewMode = ref('analysis')
const viewTabs = [
  { key: 'analysis', label: '数据分析' },
  { key: 'browse', label: '流量分布' },
]

function switchView(key) {
  viewMode.value = key
}

// ===== 状态 =====
const accountsLoading = ref(false)
const allAccounts = ref([])
const fishShopAccounts = computed(() => allAccounts.value.filter(a => a.fishShopUser === true || a.fishShopUser === 1))
const selectedAccountId = ref('all')
const dateType = ref('recent7d')
const loading = ref(false)
const error = ref('')
const partialFailure = ref(null)
const summary = ref(null)
const updatedAt = ref(timeText(Date.now()))
const trendMetricKey = ref('payAmt')
const trendChartEl = ref(null)
let trendChartInstance = null
let inflightController = null
let inflightRequestId = 0

// ===== 计算属性 =====
const scopeLabel = computed(() => {
  if (selectedAccountId.value === 'all') return '全部鱼小铺账号'
  const acc = fishShopAccounts.value.find(a => a.id === Number(selectedAccountId.value))
  return acc ? accountName(acc) : '当前账号'
})

const dateLabel = computed(() => {
  const opt = dateRangeOptions.find(o => o.value === dateType.value)
  return opt ? opt.label : ''
})

const realDateRangeText = computed(() => {
  if (!summary.value || !summary.value.realDateRange || summary.value.realDateRange.length === 0) return ''
  return summary.value.realDateRange.map(formatDs).join(' ~ ')
})

const isEmptyData = computed(() => {
  if (!summary.value) return true
  const banners = summary.value.banners || {}
  return Object.keys(banners).length === 0 && (summary.value.graph || []).length === 0
})

const aovNote = computed(() => summary.value?.aovNote || '')

// ===== Hero KPI 条：4 个核心指标大数字 =====
const heroKpis = computed(() => {
  if (!summary.value || !summary.value.banners) return []
  const b = summary.value.banners
  const defs = [
    { key: 'payAmt', label: '成交金额', type: 'money', color: '#16bf78', icon: '¥' },
    { key: 'payOrdCnt', label: '支付订单', type: 'int', color: '#0d6bff', icon: '#' },
    { key: 'showUv', label: '曝光人数', type: 'int', color: '#ff9f22', icon: '◉' },
    { key: 'aov', label: '客单价', type: 'money', color: '#8b5cf6', icon: '∀' },
  ]
  return defs.map(def => {
    const item = b[def.key] || {}
    const value = item.data
    const ratio = item.ratio === null || item.ratio === undefined ? null : Number(item.ratio)
    let display = '—'
    if (value !== null && value !== undefined && value !== '') {
      if (item.aggregated !== true) {
        if (item.dataStr) display = item.dataStr
        else if (item.dataFormat) display = item.dataFormat
        else display = def.type === 'money' ? formatMoney(value) : formatNumber(value)
      } else {
        display = def.type === 'money' ? formatMoney(value) : formatNumber(value)
      }
    }
    return { ...def, value, display, ratio }
  })
})

const partialFailureBanner = computed(() => {
  if (!partialFailure.value) return null
  const { total, success, failed } = partialFailure.value
  return `部分账号数据获取失败（成功 ${success} / 失败 ${failed} / 共 ${total}），已展示成功账号的汇总数据。`
})

const trendAvailable = computed(() => {
  if (!summary.value || !summary.value.graph) return false
  return summary.value.graph.length > 0
})

const trendMetricDef = computed(() => trendMetricOptions.find(o => o.key === trendMetricKey.value) || trendMetricOptions[0])
const trendMetricLabel = computed(() => trendMetricDef.value.label)
const trendDesc = computed(() => {
  if (!trendAvailable.value) return ''
  return `${trendMetricLabel.value} · 共 ${summary.value.graph.length} 个数据点`
})

// 商品库存单独处理为横向宽卡
const otherMetricGroups = computed(() => metricGroups.value.filter(g => g.key !== 'inventory'))
const inventoryGroup = computed(() => metricGroups.value.find(g => g.key === 'inventory') || { title: '商品库存', color: C.slate, iconComp: IconBox, cards: [] })
const inventoryCard = computed(() => inventoryGroup.value.cards[0] || { title: '在线商品数', display: '—', value: null, ratio: null, lastDisplay: '', sub: '暂无对比', sparkPoints: null, sparkFill: null, sparkColor: C.slate, iconComp: IconBox, color: C.slate })

// ===== 方法 =====
function formatAccountLabel(acc) {
  return accountName(acc)
}

function formatMetric(value, type, item, isLast = false) {
  if (value === null || value === undefined || value === '') return '—'
  const isAggregated = item && item.aggregated === true
  if (!isAggregated) {
    if (isLast) {
      if (item.lastDataStr) return item.lastDataStr
      if (item.lastDataFormat) return item.lastDataFormat
    } else {
      if (item.dataStr) return item.dataStr
      if (item.dataFormat) return item.dataFormat
    }
  }
  if (type === 'money') return formatMoney(value)
  return formatNumber(value)
}

function formatInt(value) {
  if (value === null || value === undefined) return '0'
  return formatNumber(value)
}

function formatDs(ds) {
  if (!ds) return '-'
  const s = String(ds)
  if (s.length === 8) {
    const m = s.slice(4, 6)
    const d = s.slice(6, 8)
    return `${m}-${d}`
  }
  return s
}

function ratioArrow(ratio) {
  if (ratio === null || ratio === undefined) return ''
  if (ratio > 0) return '↑'
  if (ratio < 0) return '↓'
  return '·'
}

function ratioClass(ratio) {
  if (ratio === null || ratio === undefined) return 'trend-flat'
  if (ratio > 0) return 'trend-up'
  if (ratio < 0) return 'trend-down'
  return 'trend-flat'
}

function ratioPercent(ratio) {
  if (ratio === null || ratio === undefined) return ''
  const pct = Math.abs(ratio) * 100
  if (pct >= 100) return `${pct.toFixed(0)}%`
  return `${pct.toFixed(1)}%`
}

async function loadAccounts() {
  accountsLoading.value = true
  try {
    const res = await getLiteAccounts({ current: 1, size: 100 })
    const records = extractRecords(res?.data)
    allAccounts.value = records
    if (selectedAccountId.value !== 'all') {
      const stillValid = fishShopAccounts.value.some(a => a.id === Number(selectedAccountId.value))
      if (!stillValid) selectedAccountId.value = 'all'
    }
  } catch {
    allAccounts.value = []
  } finally {
    accountsLoading.value = false
  }
}

function extractRecords(data) {
  if (Array.isArray(data)) return data
  if (data && typeof data === 'object') {
    for (const key of ['records', 'accounts', 'list', 'rows']) {
      if (Array.isArray(data[key])) return data[key]
    }
  }
  return []
}

async function load() {
  if (fishShopAccounts.value.length === 0) {
    summary.value = null
    error.value = ''
    partialFailure.value = null
    return
  }

  if (inflightController) {
    try { inflightController.abort() } catch { /* noop */ }
  }
  const requestId = ++inflightRequestId
  const controller = new AbortController()
  inflightController = controller

  loading.value = true
  error.value = ''
  partialFailure.value = null

  try {
    const params = {}
    if (selectedAccountId.value !== 'all') {
      params.accountId = Number(selectedAccountId.value)
    }
    params.dateType = dateType.value

    const res = await getFishShopDataSummary(params, { signal: controller.signal })
    if (requestId !== inflightRequestId) return

    const payload = res?.data || res
    summary.value = payload
    updatedAt.value = timeText(Date.now())

    if (payload && payload.loadFailed) {
      error.value = '鱼小铺数据加载失败，请稍后重试。'
      summary.value = null
    } else if (payload && payload.invalidAccount) {
      error.value = '选中的账号不是鱼小铺账号，无法查看数据分析。'
      summary.value = null
    } else if (payload && payload.noFishShopAccount) {
      summary.value = null
    } else if (payload && payload.accounts && payload.accounts.isPartial) {
      partialFailure.value = payload.accounts
    }

    await nextTick()
    renderTrendChart()
  } catch (e) {
    if (requestId !== inflightRequestId) return
    if (e?.name === 'AbortError' || e?.code === 'ERR_CANCELED') return
    error.value = e?.message || '鱼小铺数据分析暂时不可用，请稍后重试。'
    summary.value = null
  } finally {
    if (requestId === inflightRequestId) {
      loading.value = false
    }
  }
}

function switchDateType(value) {
  if (dateType.value === value) return
  dateType.value = value
  load()
}

const tooltipStyle = {
  backgroundColor: 'rgba(255,255,255,0.98)',
  borderColor: 'rgba(13,107,255,0.08)',
  borderWidth: 1,
  borderRadius: 12,
  padding: [12, 16],
  textStyle: { color: '#15213d', fontSize: 13, fontWeight: 500 },
  extraCssText: 'box-shadow:0 12px 40px rgba(31,53,94,0.12);backdrop-filter:blur(16px);',
}

function renderTrendChart() {
  if (!trendChartEl.value || !trendAvailable.value) {
    if (trendChartInstance) {
      trendChartInstance.dispose()
      trendChartInstance = null
    }
    return
  }

  if (!trendChartInstance) {
    trendChartInstance = echarts.init(trendChartEl.value)
  }

  const graph = summary.value.graph || []
  const def = trendMetricDef.value
  const xData = graph.map(p => formatDs(p.ds))
  const yData = graph.map(p => {
    const v = p[trendMetricKey.value]
    if (v === null || v === undefined || v === '') return 0
    const n = Number(v)
    return Number.isFinite(n) ? n : 0
  })

  // 计算最大值用于渐变
  const maxVal = Math.max(...yData, 1)
  const markPoints = []
  if (yData.length > 0) {
    const maxIdx = yData.indexOf(maxVal)
    const minVal = Math.min(...yData)
    const minIdx = yData.indexOf(minVal)
    if (maxVal > 0) {
      markPoints.push({
        coord: [maxIdx, maxVal],
        symbol: 'circle', symbolSize: 10,
        itemStyle: { color: C.green, borderColor: '#fff', borderWidth: 2 },
        label: {
          show: true, position: 'top', color: C.green, fontWeight: 700, fontSize: 11,
          formatter: def.type === 'money' ? `¥${formatNumber(maxVal)}` : formatNumber(maxVal),
        },
      })
    }
    if (minVal !== maxVal) {
      markPoints.push({
        coord: [minIdx, minVal],
        symbol: 'circle', symbolSize: 8,
        itemStyle: { color: C.red, borderColor: '#fff', borderWidth: 2 },
        label: {
          show: true, position: 'bottom', color: C.red, fontWeight: 700, fontSize: 11,
          formatter: def.type === 'money' ? `¥${formatNumber(minVal)}` : formatNumber(minVal),
        },
      })
    }
  }

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'line',
        lineStyle: { color: '#c5d0e4', type: 'dashed', width: 1 },
      },
      formatter: params => {
        const p = params[0]
        const value = def.type === 'money' ? formatMoney(p.value) : formatNumber(p.value)
        return `<div style="font-weight:600;margin-bottom:4px;">${p.axisValue}</div>
                <div style="font-size:16px;font-weight:800;color:${C.primary};">${trendMetricLabel.value}：${value}</div>`
      },
      ...tooltipStyle,
    },
    grid: { left: 52, right: 28, top: 40, bottom: 52, containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: xData,
      axisLine: { lineStyle: { color: '#e7edf7' } },
      axisTick: { show: false },
      axisLabel: { color: '#8c98ae', fontSize: 11, margin: 14, fontWeight: 500 },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#f0f4fa', type: 'dashed' } },
      axisLabel: {
        color: '#8c98ae',
        fontSize: 11,
        fontWeight: 500,
        formatter: v => def.type === 'money' ? `¥${v}` : String(v),
      },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    dataZoom: [
      { type: 'inside', start: 0, end: 100, zoomOnMouseWheel: false },
      {
        type: 'slider',
        height: 22,
        bottom: 10,
        start: 0,
        end: 100,
        borderColor: 'transparent',
        backgroundColor: 'transparent',
        fillerColor: 'rgba(13,107,255,0.08)',
        handleSize: 18,
        moveHandleSize: 14,
        textStyle: { color: '#8c98ae', fontSize: 10 },
        dataBackground: {
          lineStyle: { color: '#e7edf7', width: 1 },
          areaStyle: { color: '#f4f7fc' },
        },
        selectedDataBackground: {
          lineStyle: { color: C.primary, width: 1.5 },
          areaStyle: { color: 'rgba(13,107,255,0.1)' },
        },
      },
    ],
    series: [{
      type: 'line',
      data: yData,
      smooth: 0.35,
      symbol: 'circle',
      symbolSize: 7,
      showSymbol: false,
      emphasis: {
        focus: 'series',
        scale: true,
      },
      lineStyle: {
        color: C.primary,
        width: 3,
        shadowColor: 'rgba(13,107,255,0.2)',
        shadowBlur: 8,
        shadowOffsetY: 4,
      },
      itemStyle: { color: C.primary, borderWidth: 2, borderColor: '#fff' },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(13,107,255,0.22)' },
          { offset: 0.6, color: 'rgba(13,107,255,0.06)' },
          { offset: 1, color: 'rgba(13,107,255,0.01)' },
        ]),
      },
      markPoint: { data: markPoints, animation: true, animationDelay: 300 },
    }],
  }
  trendChartInstance.setOption(option, true)
}

function handleResize() {
  if (trendChartInstance) trendChartInstance.resize()
}

// ===== 监听 =====
watch(selectedAccountId, () => { load() })
watch(trendMetricKey, async () => { await nextTick(); renderTrendChart() })

onMounted(async () => {
  await loadAccounts()
  await load()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  if (inflightController) {
    try { inflightController.abort() } catch { /* noop */ }
  }
  if (trendChartInstance) {
    trendChartInstance.dispose()
    trendChartInstance = null
  }
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
/* ===== 页面级视图切换 ===== */
.view-tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 4px;
  background: #eef1f7;
  border-radius: 12px;
  padding: 4px;
  width: fit-content;
}
.view-tab {
  padding: 8px 22px;
  border: none;
  border-radius: 9px;
  background: transparent;
  color: #526079;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}
.view-tab:hover { color: #16213e; }
.view-tab.active {
  background: #fff;
  color: var(--primary, #2563eb);
  font-weight: 600;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.08);
}

.fsd-page {
  padding: 20px 24px 48px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: #f5f7fb;
  min-height: 100%;
}

/* ===== 页面标题区 ===== */
.page-title-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-bottom: 14px;
}
.header-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #eef5ff;
  border: 1px solid #dbe7f5;
  border-radius: 999px;
  padding: 4px 12px;
  font-size: 12px;
  color: #1677ff;
  width: fit-content;
  font-weight: 500;
}
.header-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: #12b76a;
  box-shadow: 0 0 6px rgba(18, 183, 106, 0.5);
}
.page-title {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #172033;
  letter-spacing: -0.4px;
  line-height: 1.2;
}
.page-subtitle {
  margin: 0;
  font-size: 13px;
  color: #667085;
  font-weight: 400;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.page-subtitle.loading { color: #98a2b3; }
.meta-key { color: #98a2b3; }
.meta-val { color: #475467; font-weight: 500; }
.meta-sep { color: #cbd5e1; margin: 0 2px; }

.loading-dots {
  display: inline-flex;
  gap: 3px;
  align-items: center;
}
.loading-dots i {
  width: 4px; height: 4px;
  border-radius: 50%;
  background: #1677ff;
  animation: dots-bounce 1.2s ease-in-out infinite;
}
.loading-dots i:nth-child(2) { animation-delay: 0.15s; }
.loading-dots i:nth-child(3) { animation-delay: 0.3s; }
@keyframes dots-bounce {
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1.2); }
}

/* ===== 筛选信息卡 ===== */
.filter-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  flex-wrap: wrap;
  padding: 16px 18px;
  background: #fff;
  border: 1px solid #e7ecf3;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(16, 24, 40, 0.04);
}
.filter-info {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 13px;
  color: #475467;
  min-width: 0;
}
.filter-block-name {
  font-size: 14px;
  font-weight: 600;
  color: #172033;
}
.filter-sep { color: #cbd5e1; margin: 0 2px; }
.filter-label { color: #98a2b3; font-size: 12px; }
.filter-value { color: #475467; font-weight: 500; font-size: 13px; }

.filter-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.control-item { display: flex; flex-direction: column; gap: 5px; }
.control-item label {
  font-size: 11px;
  color: #98a2b3;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  font-weight: 600;
}

.form-select, .metric-select {
  background: #fff;
  border: 1px solid #e8edf5;
  border-radius: 8px;
  padding: 0 12px;
  color: #1d2939;
  font-size: 13px;
  min-width: 160px;
  height: 36px;
  outline: none;
  transition: all 0.2s ease;
  cursor: pointer;
  font-weight: 500;
}
.form-select option { background: #fff; color: #1d2939; }
.form-select:hover { border-color: #cbd5e1; }
.form-select:focus {
  border-color: #1677ff;
  box-shadow: 0 0 0 3px rgba(22, 119, 255, 0.12);
}
.form-select:disabled { opacity: 0.5; cursor: not-allowed; }

.range-pills {
  display: inline-flex;
  gap: 2px;
  background: #f5f7fb;
  border: 1px solid #e8edf5;
  border-radius: 8px;
  padding: 3px;
  height: 36px;
  align-items: center;
}
.range-pill {
  border: none;
  background: transparent;
  color: #667085;
  border-radius: 6px;
  padding: 0 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  height: 28px;
  line-height: 28px;
}
.range-pill:hover { color: #1d2939; }
.range-pill.active {
  background: #1677ff;
  color: #fff;
  box-shadow: 0 1px 2px rgba(22, 119, 255, 0.25);
}
.range-pill:disabled { opacity: 0.4; cursor: not-allowed; }

.refresh-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  background: #1677ff;
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 0 16px;
  height: 36px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}
.refresh-btn:hover:not(:disabled) { background: #4096ff; }
.refresh-btn:active:not(:disabled) { background: #0958d9; }
.refresh-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.spin { animation: fsd-spin 1s linear infinite; }
@keyframes fsd-spin { to { transform: rotate(360deg); } }

/* ===== 错误提示 ===== */
.error-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 16px;
  background: #fef3f2;
  border: 1px solid #fda29b;
  border-radius: 10px;
  color: #b42318;
  font-size: 13px;
  font-weight: 500;
}
.error-banner.warn {
  background: #fffaeb;
  border-color: #fec84b;
  color: #b54708;
}
.retry-link {
  margin-left: auto;
  background: transparent;
  border: none;
  color: #1677ff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  text-decoration: underline;
}

/* ===== 全部账号说明 ===== */
.fsd-note {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: #eef5ff;
  border: 1px solid #dbe7f5;
  border-radius: 10px;
  color: #475467;
  font-size: 12px;
  line-height: 1.6;
}
.fsd-note svg { flex-shrink: 0; color: #1677ff; }

/* ===== 顶部行：核心指标 + 趋势分析 ===== */
.top-row {
  display: grid;
  grid-template-columns: 5fr 7fr;
  gap: 16px;
  align-items: stretch;
}
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}
.kpi-card {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 18px 20px;
  background: #fff;
  border: 1px solid #e7ecf3;
  border-radius: 12px;
  transition: all 0.25s ease;
  box-shadow: 0 2px 8px rgba(16, 24, 40, 0.04);
  animation: kpi-in 0.5s cubic-bezier(0.4,0,0.2,1) both;
  animation-delay: var(--kpi-delay, 0ms);
}
@keyframes kpi-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
.kpi-card:hover {
  border-color: #cbd5e1;
  box-shadow: 0 4px 12px rgba(16, 24, 40, 0.06);
}
.kpi-icon {
  width: 38px; height: 38px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  font-size: 18px;
  font-weight: 700;
}
.kpi-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; }
.kpi-label {
  font-size: 13px;
  color: #667085;
  font-weight: 500;
}
.kpi-value-row { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.kpi-value {
  font-size: 28px;
  font-weight: 600;
  color: #172033;
  line-height: 1.1;
  letter-spacing: -0.5px;
  font-variant-numeric: tabular-nums;
}
.kpi-trend {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 2px 7px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}

/* ===== 智能洞察面板 ===== */
.insights-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 18px 20px;
  background: #fff;
  border: 1px solid #e7ecf3;
  border-radius: 14px;
  box-shadow: 0 2px 8px rgba(16, 24, 40, 0.04);
}
.insights-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.insights-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #172033;
}
.insights-title svg { color: #1677ff; }
.insights-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  background: #1677ff;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  border-radius: 6px;
  letter-spacing: 0.5px;
}
.insights-sub {
  font-size: 12px;
  color: #98a2b3;
  font-weight: 500;
}
.insights-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
}
.insight-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 14px;
  background: #fafbfc;
  border: 1px solid #eef1f6;
  border-radius: 10px;
  transition: all 0.25s ease;
  animation: insight-in 0.4s cubic-bezier(0.4,0,0.2,1) both;
  animation-delay: var(--insight-delay, 0ms);
}
@keyframes insight-in {
  from { opacity: 0; transform: translateX(-6px); }
  to { opacity: 1; transform: translateX(0); }
}
.insight-card:hover {
  border-color: var(--insight-color);
  background: #fff;
}
.insight-icon-wrap {
  position: relative;
  width: 32px; height: 32px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.insight-icon-bg {
  position: absolute;
  inset: 0;
  border-radius: 8px;
  background: var(--insight-color);
  opacity: 0.12;
}
.insight-icon {
  position: relative;
  z-index: 1;
  font-size: 16px;
  font-weight: 700;
  color: var(--insight-color);
  line-height: 1;
}
.insight-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.insight-title {
  font-size: 13px;
  font-weight: 600;
  color: #172033;
  line-height: 1.35;
}
.insight-desc {
  margin: 0;
  font-size: 12px;
  color: #667085;
  line-height: 1.5;
}

/* ===== 加载骨架屏 ===== */
.skeleton-wrap { display: flex; flex-direction: column; gap: 16px; }
.skeleton-top-row {
  display: grid;
  grid-template-columns: 5fr 7fr;
  gap: 16px;
}
.skeleton-kpi-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}
.skeleton-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 20px;
  background: #fff;
  border: 1px solid #e7ecf3;
  border-radius: 12px;
}
.sk-icon {
  width: 38px; height: 38px;
  border-radius: 10px;
  background: linear-gradient(90deg, #eef2f7 25%, #f5f7fa 50%, #eef2f7 75%);
  background-size: 200% 100%;
  animation: sk-shimmer 1.4s ease-in-out infinite;
}
.sk-body { flex: 1; display: flex; flex-direction: column; gap: 8px; }
.sk-line {
  height: 10px;
  border-radius: 5px;
  background: linear-gradient(90deg, #eef2f7 25%, #f5f7fa 50%, #eef2f7 75%);
  background-size: 200% 100%;
  animation: sk-shimmer 1.4s ease-in-out infinite;
}
.sk-line.sm { width: 60%; }
.sk-line.lg { width: 80%; height: 16px; }
@keyframes sk-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
.skeleton-chart {
  padding: 18px 20px;
  background: #fff;
  border: 1px solid #e7ecf3;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.skeleton-chart .sk-line.lg { width: 30%; margin-bottom: 0; }
.sk-chart-body {
  height: 300px;
  border-radius: 8px;
  background: linear-gradient(90deg, #f5f7fa 25%, #eef2f7 50%, #f5f7fa 75%);
  background-size: 200% 100%;
  animation: sk-shimmer 1.4s ease-in-out infinite;
}

/* ===== 转化漏斗 ===== */
.funnel-panel {
  border-radius: 14px !important;
  border: 1px solid #e7ecf3 !important;
  box-shadow: 0 2px 8px rgba(16, 24, 40, 0.04) !important;
}
.funnel-total {
  font-size: 12px;
  color: #667085;
  font-weight: 600;
  padding: 4px 10px;
  background: #f5f7fb;
  border-radius: 6px;
}
.funnel-wrap {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  padding: 0 20px 20px;
}
.funnel-stage-col {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.funnel-stage {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 16px;
  border-radius: 10px;
  background: color-mix(in srgb, var(--stage-color) 8%, #fff);
  border: 1px solid color-mix(in srgb, var(--stage-color) 18%, #eef1f6);
  animation: funnel-in 0.4s cubic-bezier(0.4,0,0.2,1) both;
  animation-delay: var(--stage-delay, 0ms);
  transition: all 0.25s ease;
}
.funnel-stage:hover {
  border-color: var(--stage-color);
  box-shadow: 0 4px 12px color-mix(in srgb, var(--stage-color) 12%, transparent);
}
@keyframes funnel-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
.funnel-stage-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}
.funnel-stage-name {
  font-size: 12px;
  color: #475467;
  font-weight: 600;
}
.funnel-stage-value {
  font-size: 22px;
  font-weight: 600;
  color: var(--stage-color);
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.4px;
}
.funnel-bar-track {
  height: 6px;
  background: rgba(255, 255, 255, 0.6);
  border-radius: 999px;
  overflow: hidden;
}
.funnel-bar-fill {
  height: 100%;
  border-radius: 999px;
  background: var(--stage-color);
  transition: width 0.8s cubic-bezier(0.4,0,0.2,1);
}
.funnel-stage-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  flex-wrap: wrap;
  gap: 4px;
}
.funnel-stage-pct {
  color: #667085;
  font-weight: 500;
}
.funnel-stage-conv {
  color: var(--stage-color);
  font-weight: 600;
  padding: 1px 6px;
  background: color-mix(in srgb, var(--stage-color) 10%, #fff);
  border-radius: 4px;
}
.funnel-stage-conv.muted { color: #cbd5e1; background: #f5f7fb; }

.funnel-dropoff {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 3px 8px;
  background: #fef3f2;
  border: 1px solid #fda29b;
  border-radius: 6px;
  font-size: 10px;
  color: #b42318;
  font-weight: 600;
  animation: dropoff-in 0.3s cubic-bezier(0.4,0,0.2,1) both;
  animation-delay: calc(var(--stage-delay, 0ms) + 150ms);
}
@keyframes dropoff-in {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}
.funnel-dropoff svg { color: #b42318; }
.dropoff-text { font-weight: 700; }
.dropoff-pct { color: #f04438; }

/* ===== 指标分组 ===== */
.metric-groups { display: flex; flex-direction: column; gap: 16px; }
.metric-group { display: flex; flex-direction: column; gap: 10px; }
.metric-group-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 4px;
}
.metric-group-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px; height: 24px;
}
.metric-group-icon svg { width: 18px; height: 18px; }
.metric-group-title {
  font-size: 15px;
  font-weight: 600;
  color: #172033;
}
.metric-group-count {
  font-size: 11px;
  color: #98a2b3;
  padding: 2px 8px;
  background: #f5f7fb;
  border-radius: 999px;
  font-weight: 500;
}

/* ===== 指标卡片 ===== */
.metrics-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
.metrics-strip.cols-3 { grid-template-columns: repeat(3, 1fr); }
.metrics-strip.cols-1 { grid-template-columns: repeat(4, 1fr); }
.metric-card {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 18px;
  background: #fff;
  border: 1px solid #e7ecf3;
  border-radius: 12px;
  overflow: hidden;
  transition: all 0.25s ease;
  animation: card-in 0.5s cubic-bezier(0.4,0,0.2,1) both;
  animation-delay: var(--delay, 0ms);
  box-shadow: 0 2px 8px rgba(16, 24, 40, 0.04);
  min-height: 108px;
}
@keyframes card-in {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
.metric-card:hover {
  border-color: rgba(22, 119, 255, 0.3);
  box-shadow: 0 4px 12px rgba(16, 24, 40, 0.06);
}

.metric-icon-wrap {
  position: relative;
  width: 40px; height: 40px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.metric-icon-bg {
  position: absolute;
  inset: 0;
  border-radius: 10px;
  background: var(--accent);
  opacity: 0.1;
}
.metric-icon {
  width: 20px; height: 20px;
  color: var(--accent);
  position: relative;
  z-index: 1;
}

.metric-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.metric-label {
  font-size: 13px;
  color: #667085;
  font-weight: 500;
}
.metric-value {
  font-size: 24px;
  font-weight: 600;
  color: #172033;
  line-height: 1.15;
  letter-spacing: -0.5px;
  font-variant-numeric: tabular-nums;
}
.metric-loading { color: #cbd5e1; }
.metric-loading::after { content: '...'; }
.metric-sub {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: #667085;
  flex-wrap: wrap;
}
.metric-sub-text { color: #98a2b3; font-weight: 500; }
.metric-last { color: #98a2b3; font-size: 11px; }

.metric-spark {
  flex-shrink: 0;
  width: 64px;
  height: 26px;
  margin-left: auto;
  opacity: 0.7;
}
.spark-svg { width: 100%; height: 100%; display: block; }

/* 趋势徽章 */
.trend-pill {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 7px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}
.trend-pill-sm { padding: 2px 6px; font-size: 10px; }
.trend-up { background: #ecfdf3; color: #027a48; }
.trend-down { background: #fef3f2; color: #b42318; }
.trend-flat { background: #f5f7fb; color: #667085; }
.trend-arrow { font-weight: 700; }

/* ===== 趋势分析图表 ===== */
.trend-panel {
  border-radius: 14px !important;
  border: 1px solid #e7ecf3 !important;
  box-shadow: 0 2px 8px rgba(16, 24, 40, 0.04) !important;
  overflow: hidden;
  min-height: 360px;
}

.panel-title-row { display: flex; flex-direction: column; gap: 2px; }
.panel-title-text { font-size: 15px; font-weight: 600; color: #172033; }
.panel-title-desc { font-size: 12px; color: #98a2b3; font-weight: 500; }

.metric-switcher { display: flex; align-items: center; gap: 8px; }
.metric-switcher label { font-size: 12px; color: #667085; }
.metric-select {
  height: 32px;
  padding: 0 12px;
  min-width: 140px;
  background: #fff;
  border: 1px solid #e8edf5;
  border-radius: 8px;
  font-size: 13px;
  color: #1d2939;
  cursor: pointer;
}
.metric-select:hover { border-color: #1677ff; }
.metric-select:focus { outline: none; border-color: #1677ff; box-shadow: 0 0 0 3px rgba(22,119,255,0.12); }

.echart-box { width: 100%; }
.trend-box { height: 320px; margin: 0 -4px; }

/* ===== 商品库存横向宽卡（方案 B） ===== */
.inventory-group { gap: 10px; }
.inventory-wide-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 18px;
  background: #fff;
  border: 1px solid #e7ecf3;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(16, 24, 40, 0.04);
  transition: all 0.25s ease;
}
.inventory-wide-card:hover {
  border-color: rgba(22, 119, 255, 0.3);
  box-shadow: 0 4px 12px rgba(16, 24, 40, 0.06);
}
.inventory-left {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-shrink: 0;
}
.inventory-main {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.inventory-middle {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-left: 32px;
  flex: 1;
  min-width: 0;
}
.inventory-spark {
  flex-shrink: 0;
  width: 80px;
  height: 32px;
  opacity: 0.8;
}

/* ===== 页面底部说明 ===== */
.page-footer {
  font-size: 12px;
  color: #98a2b3;
  text-align: center;
  padding: 16px 0 4px;
  font-weight: 400;
  letter-spacing: 0.2px;
}

/* ===== 响应式 ===== */
@media (max-width: 1439px) {
  .top-row { grid-template-columns: 1fr 1fr; }
  .kpi-value { font-size: 26px; }
}
@media (max-width: 1200px) {
  .top-row { grid-template-columns: 1fr; }
  .funnel-wrap { grid-template-columns: repeat(3, 1fr); }
  .metrics-strip, .metrics-strip.cols-3 { grid-template-columns: repeat(3, 1fr); }
  .metrics-strip.cols-1 { grid-template-columns: repeat(2, 1fr); }
  .inventory-middle { margin-left: 20px; }
}
@media (max-width: 900px) {
  .metrics-strip, .metrics-strip.cols-3 { grid-template-columns: repeat(2, 1fr); }
  .metrics-strip.cols-1 { grid-template-columns: repeat(2, 1fr); }
  .insights-grid { grid-template-columns: repeat(2, 1fr); }
  .inventory-wide-card { flex-wrap: wrap; }
  .inventory-middle { margin-left: 0; width: 100%; }
}
@media (max-width: 768px) {
  .fsd-page { padding: 12px; }
  .filter-card { padding: 14px 16px; flex-direction: column; align-items: stretch; }
  .filter-controls { flex-direction: column; align-items: stretch; gap: 10px; }
  .form-select, .metric-select { min-width: 0; width: 100%; }
  .range-pills { width: 100%; justify-content: space-between; }
  .range-pill { flex: 1; }
  .refresh-btn { width: 100%; justify-content: center; }
  .skeleton-top-row { grid-template-columns: 1fr; }
  .skeleton-kpi-grid { grid-template-columns: repeat(2, 1fr); }
  .funnel-wrap { grid-template-columns: 1fr 1fr; }
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
  .kpi-value { font-size: 22px; }
}
@media (max-width: 480px) {
  .skeleton-kpi-grid { grid-template-columns: 1fr; }
  .metrics-strip, .metrics-strip.cols-3, .metrics-strip.cols-1 { grid-template-columns: 1fr; }
  .kpi-grid { grid-template-columns: 1fr; }
  .insights-grid { grid-template-columns: 1fr; }
  .funnel-wrap { grid-template-columns: 1fr; }
}
</style>
