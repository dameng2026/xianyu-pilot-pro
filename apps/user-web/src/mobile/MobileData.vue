<template>
  <div class="m-data">
    <div class="m-page-header">
      <h1>数据面板</h1>
      <p class="m-page-sub">实时掌握店铺运营数据</p>
    </div>

    <div class="m-date-tabs">
      <button
        v-for="tab in dateTabs"
        :key="tab.value"
        class="m-date-tab"
        :class="{ active: activeDate === tab.value }"
        :disabled="tab.disabled"
        :title="tab.disabled ? '该时间范围的汇总接口暂未开放' : ''"
        @click="switchDate(tab.value)"
      >
        {{ tab.label }}
      </button>
    </div>

    <div v-if="loading" class="m-loading">加载中...</div>

    <MobileUnavailableState v-else-if="loadError" title="数据面板暂时无法加载" :description="loadError" @retry="loadAll" />

    <template v-else>
      <div v-if="!hasData" class="m-empty">
        <div class="m-empty-icon">
          <MIcon name="chart" :size="48" />
        </div>
        <div class="m-empty-text">暂无数据</div>
        <div class="m-empty-desc">当前时间段还没有运营数据，稍后再来看看</div>
      </div>

      <template v-else>
        <div class="m-stat-grid">
          <div class="m-stat-card">
            <div class="m-stat-icon m-stat-blue">
              <MIcon name="list" :size="26" />
            </div>
            <div class="m-stat-info">
              <div class="m-stat-label">订单数</div>
              <div class="m-stat-value">{{ metricText(stats.orderCount) }}</div>
              <div class="m-stat-desc">订单总量</div>
            </div>
          </div>
          <div class="m-stat-card">
            <div class="m-stat-icon m-stat-green">
              <MIcon name="check" :size="26" />
            </div>
            <div class="m-stat-info">
              <div class="m-stat-label">发货成功</div>
              <div class="m-stat-value">{{ metricText(stats.deliverySuccessCount) }}</div>
              <div class="m-stat-desc">自动发货成功</div>
            </div>
          </div>
          <div class="m-stat-card">
            <div class="m-stat-icon m-stat-orange">
              <MIcon name="clock" :size="26" />
            </div>
            <div class="m-stat-info">
              <div class="m-stat-label">待发货</div>
              <div class="m-stat-value">{{ metricText(stats.pendingDeliveryCount) }}</div>
              <div class="m-stat-desc">待处理订单</div>
            </div>
          </div>
          <div class="m-stat-card">
            <div class="m-stat-icon m-stat-red">
              <MIcon name="x" :size="26" />
            </div>
            <div class="m-stat-info">
              <div class="m-stat-label">发货失败</div>
              <div class="m-stat-value">{{ metricText(stats.deliveryFailCount) }}</div>
              <div class="m-stat-desc">需关注处理</div>
            </div>
          </div>
          <div class="m-stat-card">
            <div class="m-stat-icon m-stat-purple">
              <MIcon name="bot" :size="26" />
            </div>
            <div class="m-stat-info">
              <div class="m-stat-label">AI回复数</div>
              <div class="m-stat-value">{{ metricText(stats.aiReplyCount) }}</div>
              <div class="m-stat-desc">自动回复消息</div>
            </div>
          </div>
          <div class="m-stat-card">
            <div class="m-stat-icon m-stat-cyan">
              <MIcon name="bag" :size="26" />
            </div>
            <div class="m-stat-info">
              <div class="m-stat-label">商品总数</div>
              <div class="m-stat-value">{{ metricText(stats.itemCount) }}</div>
              <div class="m-stat-desc">在售商品</div>
            </div>
          </div>
        </div>

        <div class="m-section m-overview-card">
          <div class="m-section-header">
            <h2>趋势概览</h2>
          </div>
          <div class="m-overview-row">
            <div class="m-overview-label">发货成功率</div>
            <div class="m-overview-value">{{ successRateText }}</div>
          </div>
          <div class="m-progress">
            <div class="m-progress-bar" :style="{ width: successRatePercent + '%' }"></div>
          </div>
          <div class="m-overview-meta">
            <span class="m-overview-meta-item">
              <i class="m-dot m-dot-green"></i>成功 {{ metricText(stats.deliverySuccessCount) }}
            </span>
            <span class="m-overview-meta-item">
              <i class="m-dot m-dot-red"></i>失败 {{ metricText(stats.deliveryFailCount) }}
            </span>
          </div>
        </div>

        <MobileUnavailableState v-if="trendError" compact title="趋势数据暂时不可用" :description="trendError" @retry="loadAll" />

        <div v-if="trendHasData" class="m-section m-trend-card">
          <div class="m-section-header">
            <h2>销售趋势</h2>
            <span class="m-section-hint">近7天发货成功</span>
          </div>
          <div class="m-chart">
            <div
              v-for="(item, idx) in trendRows"
              :key="idx"
              class="m-chart-col"
            >
              <div class="m-chart-bar-wrap">
                <div
                  class="m-chart-bar"
                  :style="{ height: barHeight(item.success) + '%' }"
                  :title="`${item.date}：${item.success}`"
                ></div>
              </div>
              <div class="m-chart-date">{{ item.shortDate }}</div>
              <div class="m-chart-val">{{ item.success }}</div>
            </div>
          </div>
        </div>

        <div class="m-section m-quick-section">
          <div class="m-section-header">
            <h2>快捷操作</h2>
          </div>
          <div class="m-quick-grid">
            <div class="m-quick-item" @click="$emit('navigate', 'products')">
              <div class="m-quick-icon m-quick-blue">
                <MIcon name="bag" :size="26" />
              </div>
              <div class="m-quick-info">
                <div class="m-quick-title">商品管理</div>
                <div class="m-quick-desc">商品上下架与编辑</div>
              </div>
              <MIcon name="chevronRight" :size="18" class="m-quick-arrow" />
            </div>
            <div class="m-quick-item" @click="$emit('navigate', 'messages')">
              <div class="m-quick-icon m-quick-green">
                <MIcon name="chat" :size="26" />
              </div>
              <div class="m-quick-info">
                <div class="m-quick-title">在线消息</div>
                <div class="m-quick-desc">查看买家会话</div>
              </div>
              <MIcon name="chevronRight" :size="18" class="m-quick-arrow" />
            </div>
            <div class="m-quick-item" @click="$emit('navigate', 'auto-delivery')">
              <div class="m-quick-icon m-quick-purple">
                <MIcon name="truck" :size="26" />
              </div>
              <div class="m-quick-info">
                <div class="m-quick-title">自动发货</div>
                <div class="m-quick-desc">配置发货规则</div>
              </div>
              <MIcon name="chevronRight" :size="18" class="m-quick-arrow" />
            </div>
            <div class="m-quick-item" @click="$emit('navigate', 'delivery-records')">
              <div class="m-quick-icon m-quick-orange">
                <MIcon name="package" :size="26" />
              </div>
              <div class="m-quick-info">
                <div class="m-quick-title">发货记录</div>
                <div class="m-quick-desc">查询发货明细</div>
              </div>
              <MIcon name="chevronRight" :size="18" class="m-quick-arrow" />
            </div>
          </div>
        </div>

        <div class="m-pc-notice">
          <div class="m-pc-notice-icon">
            <MIcon name="monitor" :size="24" />
          </div>
          <div class="m-pc-notice-content">
            <div class="m-pc-notice-title">更详细的数据分析</div>
            <div class="m-pc-notice-desc">趋势图、明细对比与导出功能建议在桌面端查看，体验更佳。</div>
          </div>
          <button class="m-pc-notice-btn" @click="$emit('force-desktop')">桌面版</button>
        </div>
      </template>
    </template>

    <div class="m-safe-bottom"></div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import MIcon from './MIcon.vue'
import MobileUnavailableState from './MobileUnavailableState.vue'
import { getDashboardSummary, getDashboardSalesTrend } from '../api/dashboard.js'

defineEmits(['navigate', 'force-desktop', 'back'])

const dateTabs = [
  { label: '今日', value: 'today' },
  { label: '近7天', value: '7d', disabled: true },
  { label: '近30天', value: '30d', disabled: true }
]

const activeDate = ref('today')
const loading = ref(true)
const loadError = ref('')
const trendError = ref('')

const stats = reactive({
  orderCount: null,
  deliverySuccessCount: null,
  pendingDeliveryCount: null,
  deliveryFailCount: null,
  aiReplyCount: null,
  itemCount: null
})

const trend = ref({
  dates: [],
  deliverySuccess: []
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

const maxSuccess = computed(() => {
  const arr = trend.value.deliverySuccess || []
  if (!arr.length) return 0
  return Math.max(1, ...arr.map(v => Number(v) || 0))
})

const trendRows = computed(() => {
  const dates = trend.value.dates || []
  const arr = trend.value.deliverySuccess || []
  return dates.map((d, i) => {
    const dateStr = String(d || '')
    const shortDate = dateStr.length >= 5 ? dateStr.slice(5) : dateStr
    return {
      date: dateStr,
      shortDate,
      success: Number(arr[i]) || 0
    }
  })
})

const successRatePercent = computed(() => {
  const success = Number(stats.deliverySuccessCount)
  const fail = Number(stats.deliveryFailCount)
  if (!Number.isFinite(success) || !Number.isFinite(fail)) return 0
  const total = success + fail
  if (!total) return 0
  return Math.round((success * 100) / total)
})

const successRateText = computed(() => {
  const success = Number(stats.deliverySuccessCount)
  const fail = Number(stats.deliveryFailCount)
  return Number.isFinite(success) && Number.isFinite(fail) && success + fail > 0
    ? `${successRatePercent.value}%`
    : '—'
})

function metricText(value) {
  return value === null || value === undefined ? '—' : value
}

function barHeight(value) {
  const v = Number(value) || 0
  if (v <= 0) return 0
  return Math.max(8, Math.round((v / maxSuccess.value) * 100))
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
  const normalized = Object.fromEntries(Object.entries(values).map(([key, value]) => [key, Number(value)]))
  if (Object.values(normalized).some(value => !Number.isFinite(value) || value < 0)) {
    throw new Error('数据概览响应缺少有效指标')
  }
  Object.assign(stats, normalized)
}

async function loadTrend() {
  const res = await getDashboardSalesTrend()
  const d = res?.data
  if (!d || typeof d !== 'object' || Array.isArray(d)) throw new Error('趋势数据响应格式异常')
  const dates = d.dates
  const deliverySuccess = d.deliverySuccess || d.series?.deliverySuccess
  if (!Array.isArray(dates) || !Array.isArray(deliverySuccess) || dates.length !== deliverySuccess.length) throw new Error('趋势数据响应格式异常')
  if (dates.some(value => typeof value !== 'string' || !value.trim())) throw new Error('趋势日期响应格式异常')
  if (deliverySuccess.some(value => !Number.isFinite(Number(value)) || Number(value) < 0)) throw new Error('趋势数据包含无效指标')
  trend.value = {
    dates,
    deliverySuccess
  }
}

function resetStats() {
  stats.orderCount = null
  stats.deliverySuccessCount = null
  stats.pendingDeliveryCount = null
  stats.deliveryFailCount = null
  stats.aiReplyCount = null
  stats.itemCount = null
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
    trend.value = { dates: [], deliverySuccess: [] }
    trendError.value = trendResult.reason?.message || '请检查网络连接后重试。'
  }
  loading.value = false
}

async function switchDate(value) {
  if (dateTabs.find(tab => tab.value === value)?.disabled) return
  if (activeDate.value === value) return
  activeDate.value = value
  await loadAll()
}

onMounted(() => {
  loadAll()
})
</script>

<style scoped>
.m-data {
  padding: 12px 16px 0;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
}

.m-page-header {
  margin-bottom: 14px;
}
.m-page-header h1 {
  margin: 0 0 4px;
  font-size: 24px;
  font-weight: 800;
  color: #15213d;
  line-height: 1.2;
}
.m-page-sub {
  margin: 0;
  font-size: 13px;
  color: #8c98ae;
  line-height: 1.5;
}

.m-date-tabs {
  display: flex;
  background: #f1f5fb;
  border-radius: 12px;
  padding: 4px;
  margin-bottom: 16px;
}
.m-date-tab {
  flex: 1;
  height: 34px;
  border: none;
  background: transparent;
  border-radius: 9px;
  font-size: 13px;
  font-weight: 600;
  color: #72809a;
  cursor: pointer;
  transition: all 0.2s;
}
.m-date-tab.active {
  background: white;
  color: #0d6bff;
  box-shadow: 0 2px 6px rgba(13, 107, 255, 0.12);
}
.m-date-tab:disabled {
  color: #aeb9ca;
  cursor: not-allowed;
}

.m-loading {
  padding: 48px 0;
  text-align: center;
  color: #8c98ae;
  font-size: 14px;
}

.m-empty {
  padding: 48px 16px;
  text-align: center;
  color: #8c98ae;
}
.m-empty-icon {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: linear-gradient(135deg, #e8f1ff, #d4e4ff);
  color: #0d6bff;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 14px;
  opacity: 0.7;
}
.m-empty-text {
  font-size: 16px;
  font-weight: 600;
  color: #5a6a85;
  margin-bottom: 6px;
}
.m-empty-desc {
  font-size: 12px;
  color: #9aa6bd;
  line-height: 1.6;
}

.m-stat-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 16px;
}
.m-stat-card {
  background: white;
  border-radius: 16px;
  padding: 14px;
  display: flex;
  align-items: center;
  gap: 10px;
  box-shadow: 0 2px 8px rgba(31, 53, 94, 0.05);
  border: 1px solid #f0f4fa;
  transition: transform 0.15s;
}
.m-stat-card:active {
  transform: scale(0.97);
}
.m-stat-icon {
  width: 46px;
  height: 46px;
  border-radius: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-stat-blue { background: linear-gradient(135deg, #e8f1ff, #d4e4ff); color: #0d6bff; }
.m-stat-green { background: linear-gradient(135deg, #e2f8ee, #cdf2df); color: #16bf78; }
.m-stat-orange { background: linear-gradient(135deg, #fff4e0, #ffe7c2); color: #ff9f22; }
.m-stat-red { background: linear-gradient(135deg, #ffe8e8, #ffd1d1); color: #ef4444; }
.m-stat-purple { background: linear-gradient(135deg, #f0ebff, #e2d8ff); color: #8b5cf6; }
.m-stat-cyan { background: linear-gradient(135deg, #e0f7fb, #cdf0f6); color: #06b6d4; }
.m-stat-info { flex: 1; min-width: 0; }
.m-stat-label { font-size: 12px; color: #8c98ae; margin-bottom: 2px; }
.m-stat-value {
  font-size: 22px;
  font-weight: 800;
  color: #15213d;
  line-height: 1.2;
  min-width: 0;
  overflow-wrap: anywhere;
  font-variant-numeric: tabular-nums;
}
.m-stat-desc { font-size: 11px; color: #9aa6bd; margin-top: 2px; }

.m-section {
  background: white;
  border-radius: 18px;
  padding: 16px;
  margin-bottom: 14px;
  box-shadow: 0 2px 8px rgba(31, 53, 94, 0.04);
  border: 1px solid #f0f4fa;
}
.m-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.m-section-header h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #15213d;
}
.m-section-hint {
  font-size: 12px;
  color: #8c98ae;
}

.m-overview-card { padding: 18px 16px; }
.m-overview-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 10px;
}
.m-overview-label {
  font-size: 13px;
  color: #5a6a85;
  font-weight: 500;
}
.m-overview-value {
  font-size: 26px;
  font-weight: 800;
  color: #16bf78;
  line-height: 1;
}
.m-progress {
  height: 10px;
  background: #eef2f8;
  border-radius: 100px;
  overflow: hidden;
  margin-bottom: 10px;
}
.m-progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #16bf78, #5fd49a);
  border-radius: 100px;
  transition: width 0.4s ease;
}
.m-overview-meta {
  display: flex;
  gap: 16px;
}
.m-overview-meta-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: #5a6a85;
}
.m-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
}
.m-dot-green { background: #16bf78; }
.m-dot-red { background: #ef4444; }

.m-chart {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  height: 160px;
  padding-top: 6px;
}
.m-chart-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
}
.m-chart-bar-wrap {
  flex: 1;
  width: 100%;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  min-height: 0;
}
.m-chart-bar {
  width: 70%;
  max-width: 28px;
  background: linear-gradient(180deg, #4a8fff 0%, #0d6bff 100%);
  border-radius: 6px 6px 0 0;
  transition: height 0.4s ease;
  min-height: 4px;
}
.m-chart-date {
  margin-top: 6px;
  font-size: 11px;
  color: #8c98ae;
  line-height: 1.3;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-chart-val {
  font-size: 11px;
  font-weight: 600;
  color: #15213d;
  margin-top: 2px;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.m-quick-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.m-quick-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  background: #f8faff;
  border-radius: 14px;
  cursor: pointer;
  transition: background 0.15s;
}
.m-quick-item:active {
  background: #eef4ff;
}
.m-quick-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-quick-blue { background: linear-gradient(135deg, #e8f1ff, #d0e2ff); color: #0d6bff; }
.m-quick-green { background: linear-gradient(135deg, #e2f8ee, #cdf2df); color: #16bf78; }
.m-quick-purple { background: linear-gradient(135deg, #f0ebff, #e2d8ff); color: #8b5cf6; }
.m-quick-orange { background: linear-gradient(135deg, #fff4e0, #ffe7c2); color: #ff9f22; }
.m-quick-info { flex: 1; min-width: 0; }
.m-quick-title { font-size: 14px; font-weight: 600; color: #15213d; margin-bottom: 2px; }
.m-quick-desc { font-size: 11px; color: #8c98ae; line-height: 1.4; }
.m-quick-arrow { color: #c4cddb; flex-shrink: 0; }

.m-pc-notice {
  background: linear-gradient(135deg, #f5f9ff 0%, #fbfcff 100%);
  border: 1px solid #e6eefc;
  border-radius: 16px;
  padding: 14px;
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

@media (max-width: 480px) {
  .m-quick-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 360px) {
  .m-stat-grid {
    grid-template-columns: 1fr;
  }
}
.m-pc-notice-icon {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: linear-gradient(135deg, #4a8fff, #2d6bff);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-pc-notice-content { flex: 1; min-width: 0; }
.m-pc-notice-title {
  font-size: 14px;
  font-weight: 700;
  color: #15213d;
  margin-bottom: 2px;
}
.m-pc-notice-desc {
  font-size: 12px;
  color: #72809a;
  line-height: 1.5;
}
.m-pc-notice-btn {
  flex-shrink: 0;
  height: 32px;
  padding: 0 14px;
  border: none;
  border-radius: 16px;
  background: linear-gradient(135deg, #0d6bff, #2580ff);
  color: white;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(13, 107, 255, 0.25);
}
.m-pc-notice-btn:active {
  transform: scale(0.96);
}

.m-safe-bottom {
  height: 80px;
}
</style>
