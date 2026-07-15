<template>
  <div>
    <div class="toolbar"><span class="subtle">统计范围：</span><b>全部账号</b><span class="subtle">更新时间：{{ updatedAt }}</span><label class="subtle" for="data-stat-date">统计日期</label><input id="data-stat-date" v-model="date" class="input" type="date" style="max-width:180px"><AppButton :disabled="loading" @click="load">{{ loading ? '加载中...' : '刷新' }}</AppButton></div>
    <div v-if="summaryError" class="global-notice error">汇总数据加载失败：{{ summaryError }}</div>
    <div v-if="trendError" class="global-notice error">趋势数据加载失败：{{ trendError }}</div>
    <div class="grid stat-grid">
      <StatCard title="订单数" :value="metricText(stats.orderCount)" change="订单统计" icon="product" />
      <StatCard title="发货成功" :value="metricText(stats.deliverySuccessCount)" change="自动发货成功" icon="record" color="green" />
      <StatCard title="发货失败" :value="metricText(stats.deliveryFailCount)" change="自动发货失败" icon="task" color="orange" />
      <StatCard title="待发货" :value="metricText(stats.pendingDeliveryCount)" change="待处理订单" icon="task" color="purple" />
      <StatCard title="AI回复" :value="metricText(stats.aiReplyCount)" change="智能客服命中" icon="chat" />
      <StatCard title="数据状态" :value="summaryAvailable ? (stats.hasData ? '有数据' : '暂无数据') : '状态未知'" change="后端统计结果" icon="data" color="green" />
    </div>
    <div class="grid three-col">
      <CardPanel title="发货成功趋势"><template #action><div class="chips"><span class="chip">近7天</span></div></template><MiniLineChart v-if="trendAvailable" :values="trend.deliverySuccess" /><EmptyState v-else icon="⚠" title="趋势不可用" :description="trendError || '正在加载趋势数据'" /></CardPanel>
      <CardPanel title="发货失败趋势"><MiniLineChart v-if="trendAvailable" :values="trend.deliveryFail" /><EmptyState v-else icon="⚠" title="趋势不可用" :description="trendError || '正在加载趋势数据'" /></CardPanel>
      <CardPanel title="AI回复分布"><DonutChart v-if="summaryAvailable" :center="String(totalReplies)" label="AI回复" :items="replyItems" /><EmptyState v-else icon="⚠" title="分布不可用" :description="summaryError || '正在加载汇总数据'" /></CardPanel>
    </div>
    <div class="grid three-col" style="margin-top:16px">
      <CardPanel title="趋势明细">
        <BaseTable v-if="trendAvailable" :columns="trendCols" :rows="trendRows" />
        <EmptyState v-else icon="⚠" title="趋势明细不可用" :description="trendError || '正在加载趋势数据'" />
      </CardPanel>
      <CardPanel title="发货概况">
        <template v-if="summaryAvailable">
          <DonutChart :center="String(totalDelivery)" label="发货合计" :items="deliveryItems" />
          <div class="metric-row" style="margin-top:20px"><div class="metric-tile"><span>成功率</span><b style="color:var(--green)">{{ successRate }}</b></div><div class="metric-tile"><span>失败</span><b style="color:#ef4444">{{ metricText(stats.deliveryFailCount) }}</b></div><div class="metric-tile"><span>待处理</span><b>{{ metricText(stats.pendingDeliveryCount) }}</b></div></div>
        </template>
        <EmptyState v-else icon="⚠" title="发货概况不可用" :description="summaryError || '正在加载汇总数据'" />
      </CardPanel>
      <CardPanel title="最新实时事件">
        <EmptyState
          v-if="logs.length === 0"
          icon="📡"
          :title="sseStatus === 'connected' ? '暂无实时事件' : '实时事件流暂时不可用'"
          :description="sseStatus === 'connected' ? '订单、发货、AI 回复等实时事件会在这里显示。' : '当前未确认实时连接可用，请以各业务列表中的服务端数据为准。'"
        />
        <div v-for="n in logs" :key="n.t+n.time" class="option-line"><div><b>{{ n.t }}</b><p class="subtle" style="margin:4px 0 0">{{ n.d }}</p></div><span class="subtle">{{ n.time }}</span></div>
      </CardPanel>
    </div>
    <CardPanel title="快捷操作" style="margin-top:16px"><div class="grid quick-grid"><div v-for="q in quick" :key="q.key" class="quick-card" @click="$emit('navigate', q.key)"><div class="circle-ico blue-bg">＋</div><div><b>{{ q.label }}</b><span>快速进入常用功能</span></div></div></div></CardPanel>
  </div>
</template>
<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import StatCard from '../components/StatCard.vue'; import CardPanel from '../components/CardPanel.vue'; import MiniLineChart from '../components/MiniLineChart.vue'; import DonutChart from '../components/DonutChart.vue'; import BaseTable from '../components/BaseTable.vue'; import AppButton from '../components/AppButton.vue'; import EmptyState from '../components/EmptyState.vue'
import { getDashboardSummary, getDashboardSalesTrend } from '../api/dashboard.js'
import { shortText } from '../utils/format.js'
import { getSseStatus } from '../utils/sse.js'
defineEmits(['navigate'])
const emptyStats = () => ({ orderCount:null, deliverySuccessCount:null, deliveryFailCount:null, pendingDeliveryCount:null, aiReplyCount:null, hasData:false })
const stats = ref(emptyStats())
const trend = ref({ dates:[], deliverySuccess:[], deliveryFail:[], aiReplies:null })
const updatedAt = ref('-')
const summaryError = ref('')
const trendError = ref('')
const summaryAvailable = ref(false)
const trendAvailable = ref(false)
const loading = ref(false)
const logs = ref([])
const sseStatus = ref(getSseStatus())
const date = ref('')
const totalDelivery = computed(() => Number(stats.value.deliverySuccessCount) + Number(stats.value.deliveryFailCount))
const totalReplies = computed(() => Array.isArray(trend.value.aiReplies)
  ? trend.value.aiReplies.reduce((a,b)=>a+Number(b ?? 0),0)
  : Number(stats.value.aiReplyCount ?? 0))
const successRate = computed(() => totalDelivery.value > 0 ? `${Math.round(Number(stats.value.deliverySuccessCount) * 100 / totalDelivery.value)}%` : '—')
const deliveryItems = computed(() => [{label:'成功', value:String(stats.value.deliverySuccessCount)}, {label:'失败', value:String(stats.value.deliveryFailCount)}, {label:'待发货', value:String(stats.value.pendingDeliveryCount)}])
const replyItems = computed(() => [{label:'AI回复', value:String(totalReplies.value)}, {label:'订单数', value:String(stats.value.orderCount)}])
const trendCols=[{key:'date',title:'日期'},{key:'success',title:'发货成功'},{key:'fail',title:'发货失败'},{key:'reply',title:'AI回复'}]
const trendRows = computed(() => (trend.value.dates || []).map((d,i)=>({date:d, success:trend.value.deliverySuccess?.[i] ?? '—', fail:trend.value.deliveryFail?.[i] ?? '—', reply:trend.value.aiReplies?.[i] ?? '—'})))
const quick=[{label:'添加闲鱼账号',key:'accounts'},{label:'发布新商品',key:'product-publish'},{label:'同步商品',key:'products'},{label:'配置自动发货',key:'auto-delivery'},{label:'商机发现',key:'opportunities'},{label:'卡密管理',key:'card-warehouse'},{label:'新建工作流',key:'workflow'},{label:'更多功能',key:'settings-ai-cs'}]
function metricOrThrow(data, keys, label) {
  const key = keys.find(candidate => Object.prototype.hasOwnProperty.call(data, candidate))
  if (!key || typeof data[key] !== 'number' || !Number.isFinite(data[key]) || data[key] < 0) {
    throw new Error(`${label}响应格式异常`)
  }
  return data[key]
}
function numericSeriesOrThrow(value, expectedLength, label) {
  if (!Array.isArray(value) || value.length !== expectedLength
    || value.some(item => typeof item !== 'number' || !Number.isFinite(item) || item < 0)) {
    throw new Error(`${label}响应格式异常`)
  }
  return value
}
async function load(){
  loading.value = true
  summaryError.value = ''
  trendError.value = ''
  summaryAvailable.value = false
  trendAvailable.value = false
  stats.value = emptyStats()
  trend.value = { dates:[], deliverySuccess:[], deliveryFail:[], aiReplies:null }
  const [summaryResult, trendResult] = await Promise.allSettled([
    getDashboardSummary(date.value ? { date: date.value } : {}),
    getDashboardSalesTrend()
  ])
  if (summaryResult.status === 'fulfilled') {
    try {
      const sd = summaryResult.value?.data
      if (!sd || typeof sd !== 'object' || Array.isArray(sd)) throw new Error('汇总数据响应格式异常')
      const nextStats = {
        orderCount: metricOrThrow(sd, ['todayOrderCount', 'orderCount'], '订单统计'),
        deliverySuccessCount: metricOrThrow(sd, ['deliverySuccessCount'], '发货成功统计'),
        deliveryFailCount: metricOrThrow(sd, ['deliveryFailCount'], '发货失败统计'),
        pendingDeliveryCount: metricOrThrow(sd, ['pendingDeliveryCount'], '待发货统计'),
        aiReplyCount: metricOrThrow(sd, ['autoReplyCount', 'aiReplyCount'], 'AI 回复统计'),
        hasData: false
      }
      nextStats.hasData = [nextStats.orderCount, nextStats.deliverySuccessCount, nextStats.deliveryFailCount, nextStats.pendingDeliveryCount, nextStats.aiReplyCount].some(value => Number(value) > 0)
      stats.value = nextStats
      summaryAvailable.value = true
    } catch (e) { summaryError.value = e.message || '汇总数据不可用' }
  } else summaryError.value = summaryResult.reason?.message || '汇总数据加载失败'
  if (trendResult.status === 'fulfilled') {
    try {
      const td = trendResult.value?.data
      if (!td || typeof td !== 'object' || Array.isArray(td)) throw new Error('趋势数据响应格式异常')
      if (!Array.isArray(td.dates) || !Array.isArray(td.deliverySuccess) || !Array.isArray(td.deliveryFail)) throw new Error('趋势数据响应格式异常')
      const aiReplies = td.aiReplyCount ?? td.aiReplies
      if (td.dates.some(item => typeof item !== 'string' || !item.trim())) throw new Error('趋势日期响应格式异常')
      trend.value = {
        dates: td.dates,
        deliverySuccess: numericSeriesOrThrow(td.deliverySuccess, td.dates.length, '发货成功趋势'),
        deliveryFail: numericSeriesOrThrow(td.deliveryFail, td.dates.length, '发货失败趋势'),
        aiReplies: numericSeriesOrThrow(aiReplies, td.dates.length, 'AI 回复趋势')
      }
      trendAvailable.value = true
    } catch (e) { trendError.value = e.message || '趋势数据不可用' }
  } else trendError.value = trendResult.reason?.message || '趋势数据加载失败'
  if (summaryAvailable.value || trendAvailable.value) updatedAt.value = new Date().toLocaleString('zh-CN', { hour12:false })
  else updatedAt.value = '-'
  loading.value = false
}
function metricText(value){ return value === null || value === undefined ? '—' : value }
function onSse(event){ const d=event.detail||{}; logs.value.unshift({t:d.type||d.event||'实时事件', d:shortText(d.message||d.content||JSON.stringify(d),70), time:new Date().toLocaleTimeString('zh-CN',{hour12:false})}); logs.value=logs.value.slice(0,5) }
function onSseStatus(event){ sseStatus.value = String(event?.detail || 'disconnected') }
function onHeader(e){ if(e.detail === 'refresh-data-panel') load() }
onMounted(()=>{ window.addEventListener('xya-sse-event', onSse); window.addEventListener('xya-sse-status', onSseStatus); window.addEventListener('xya-header-action', onHeader); load() })
onBeforeUnmount(()=>{ window.removeEventListener('xya-sse-event', onSse); window.removeEventListener('xya-sse-status', onSseStatus); window.removeEventListener('xya-header-action', onHeader) })
</script>
