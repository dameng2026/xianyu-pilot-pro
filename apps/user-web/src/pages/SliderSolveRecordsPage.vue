<template>
  <div class="grid slider-layout" style="grid-template-columns:minmax(0,1fr) 460px;gap:18px">
    <div>
      <div v-if="loadError" class="global-notice error">滑块记录加载失败：{{ loadError }}</div>
      <div class="grid stat-grid">
        <StatCard title="总记录数" :value="total" change="服务端总数" icon="record" />
        <StatCard title="成功数" :value="successCount" change="本页统计" icon="shield" color="green" />
        <StatCard title="失败数" :value="failedCount" change="本页统计" icon="warning" color="red" />
        <StatCard title="求解中数" :value="retryingCount" change="本页统计" icon="refresh" color="orange" />
      </div>
      <div class="queue-status-bar">
        <div class="queue-status-item">
          <span class="queue-dot" :class="{ 'dot-active': queueStatus.queued > 0 }"></span>
          <span class="queue-text">当前排队中 <b :class="{ 'num-active': queueStatus.queued > 0 }">{{ queueStatus.queued }}</b> 个任务</span>
        </div>
        <div class="queue-status-item">
          <span class="queue-dot dot-solving" :class="{ 'dot-active': queueStatus.retrying > 0 }"></span>
          <span class="queue-text">当前求解中 <b :class="{ 'num-active': queueStatus.retrying > 0 }">{{ queueStatus.retrying }}</b> 个任务</span>
        </div>
        <div class="queue-status-item">
          <span class="queue-dot dot-timeout" :class="{ 'dot-active': queueStatus.timeout > 0 }"></span>
          <span class="queue-text">超时 <b :class="{ 'num-active': queueStatus.timeout > 0 }">{{ queueStatus.timeout || 0 }}</b> 条</span>
        </div>
        <div class="queue-status-item">
          <span class="queue-dot dot-rejected" :class="{ 'dot-active': queueStatus.precheckRejected > 0 }"></span>
          <span class="queue-text">预检验拒绝 <b :class="{ 'num-active': queueStatus.precheckRejected > 0 }">{{ queueStatus.precheckRejected || 0 }}</b> 条</span>
        </div>
        <span v-if="queueStatus.queued === 0 && queueStatus.retrying === 0" class="queue-empty-hint">
          队列为空（排队中/求解中是瞬态状态，通常在 1 秒内完成）
        </span>
      </div>
      <!-- 滑块求解规则说明：统计卡片与队列状态下方常驻展示 -->
      <div class="rules-card">
        <div class="rules-head">
          <span class="rules-title">滑块求解规则说明</span>
          <span class="rules-sub">了解求解机制，便于判断预期</span>
        </div>
        <div class="rules-callout">
          <span class="rules-badge badge-blue">i</span>
          <div>
            <strong>预检测与能力范围</strong>
            <span>每次求解前预检 Cookie 有效性，失效则不予求解。本功能主要解决 WS 掉线引起的滑块问题；Cookie 失效表示登录态已被闲鱼拒绝，需重新扫码登录。</span>
          </div>
        </div>
        <div class="rules-grid">
          <div class="rule-item">
            <span class="rules-dot dot-red"></span>
            <span><strong>僵尸账号拦截</strong>：3 天未登录前台的用户，旗下闲鱼账号视为不活跃，不予求解。</span>
          </div>
          <div class="rule-item">
            <span class="rules-dot dot-purple"></span>
            <span><strong>求解优先级</strong>：SVIP &gt; VIP &gt; 普通用户，同级按入队顺序处理。</span>
          </div>
          <div class="rule-item">
            <span class="rules-dot dot-orange"></span>
            <span><strong>手动优先</strong>：手动触发求解优先于自动触发求解。</span>
          </div>
          <div class="rule-item">
            <span class="rules-dot dot-blue"></span>
            <span><strong>排队容量</strong>：无固定上限，按优先级与入队顺序依次处理。</span>
          </div>
          <div class="rule-item">
            <span class="rules-dot dot-green"></span>
            <span><strong>并行求解</strong>：同时并行 4 个滑块求解任务。</span>
          </div>
          <div class="rule-item">
            <span class="rules-dot dot-gray"></span>
            <span><strong>求解耗时</strong>：单次约需 30～120 秒。</span>
          </div>
        </div>
      </div>
      <CardPanel title="滑块求解记录" desc="点击表格行查看完整详情">
        <div class="toolbar">
          <select v-model="filters.status" class="input" @change="search">
            <option value="">全部状态</option>
            <option value="success">成功</option>
            <option value="fail">失败</option>
            <option value="retrying">求解中</option>
            <option value="queued">排队中</option>
            <option value="timeout">超时</option>
            <option value="precheck_rejected">预检验拒绝</option>
          </select>
          <select v-model="filters.triggerScene" class="input" @change="search">
            <option value="">全部触发场景</option>
            <option value="manual">手动触发</option>
            <option value="manual_retry">手动重试</option>
            <option value="ws_connect">WS 连接</option>
            <option value="cookie_keepalive">Cookie 保活</option>
            <option value="token_refresh">Token 刷新</option>
          </select>
          <AppButton type="primary" :disabled="loading" @click="search">{{ loading ? '查询中...' : '查询' }}</AppButton>
        </div>
        <BaseTable :columns="cols" :rows="rows" @row-click="showDetail">
          <template #createdAt="{row}">{{ formatDateTime(row.createdAt) }}</template>
          <template #accountId="{row}"><span :title="row.accountId">{{ row.accountId || '-' }}</span></template>
          <template #accountName="{row}"><span :title="row.accountName">{{ row.accountName || '-' }}</span></template>
          <template #openReason="{row}"><span :title="row.openReason" class="cell-truncate">{{ row.openReason || '-' }}</span></template>
          <template #solveReason="{row}"><span :title="row.solveReason" class="cell-truncate">{{ row.solveReason || '-' }}</span></template>
          <template #status="{row}"><Badge :type="statusBadge(row.status)">{{ statusText(row.status) }}</Badge></template>
          <template #failed="{row}">
            <Badge v-if="row.status === 'fail'" type="red">失败</Badge>
            <Badge v-else-if="row.status === 'success'" type="green">成功</Badge>
            <Badge v-else-if="row.status === 'queued'" type="blue">排队中</Badge>
            <Badge v-else-if="row.status === 'timeout'" type="gray">超时</Badge>
            <Badge v-else-if="row.status === 'precheck_rejected'" type="yellow">预检验拒绝</Badge>
            <Badge v-else type="orange">求解中</Badge>
          </template>
          <template #failReason="{row}">
            <span v-if="row.failureReason" :title="failureReasonText(row.failureReason)" class="cell-truncate fail-text">{{ failureReasonText(row.failureReason) }}</span>
            <span v-else-if="row.status === 'fail' && row.errorMessage" :title="row.errorMessage" class="cell-truncate fail-text">{{ row.errorMessage }}</span>
            <span v-else-if="row.status === 'fail'" class="cell-truncate fail-text">{{ row.result === 'slider_success' ? '滑块已通过但 Cookie Session 已过期' : '滑块验证未通过' }}</span>
            <span v-else>-</span>
          </template>
          <template #empty>
            <EmptyState
              v-if="isTransientStatus"
              icon="⏱️"
              title="当前没有处于此状态的记录"
              :description="`${statusText(filters.status)}是瞬态状态，任务通常在 1 秒内完成。请查看上方实时队列状态了解当前情况`"
            />
            <EmptyState v-else icon="🧩" title="暂无滑块求解记录" description="滑块验证记录将在此显示。" />
          </template>
        </BaseTable>
        <Pagination :total="total" :current="current" :page-size="size" @page-change="goPage" />
      </CardPanel>
    </div>
    <div class="right-drawer">
      <template v-if="detail">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
          <h3>记录详情</h3>
          <button class="modal-close" @click="detail=null"><Icon name="close" /></button>
        </div>
        <p>记录 ID：<b>{{ detail.id || detail.recordId || '-' }}</b></p>
        <div class="grid" style="grid-template-columns:repeat(2,1fr);gap:10px">
          <div class="metric-tile"><span>账号ID</span><b :title="detail.accountId">{{ detail.accountId || '-' }}</b></div>
          <div class="metric-tile"><span>账号名称</span><b :title="detail.accountName">{{ detail.accountName || '-' }}</b></div>
          <div class="metric-tile"><span>处理状态</span><Badge :type="statusBadge(detail.status)">{{ statusText(detail.status) }}</Badge></div>
          <div class="metric-tile">
            <span>是否失败</span>
            <Badge v-if="detail.status === 'fail'" type="red">失败</Badge>
            <Badge v-else-if="detail.status === 'success'" type="green">成功</Badge>
            <Badge v-else-if="detail.status === 'queued'" type="blue">排队中</Badge>
            <Badge v-else-if="detail.status === 'timeout'" type="gray">超时</Badge>
            <Badge v-else-if="detail.status === 'precheck_rejected'" type="yellow">预检验拒绝</Badge>
            <Badge v-else type="orange">求解中</Badge>
          </div>
          <div class="metric-tile"><span>处理结果</span><Badge :type="resultBadge(detail.result)">{{ resultText(detail.result) }}</Badge></div>
          <div class="metric-tile"><span>验证引擎</span><b :title="detail.engine">{{ detail.engine || '-' }}</b></div>
          <div class="metric-tile"><span>触发场景</span><b :title="detail.triggerScene">{{ triggerSceneText(detail.triggerScene) }}</b></div>
          <div class="metric-tile"><span>重试次数</span><b>{{ detail.retryCount ?? 0 }}</b></div>
        </div>
        <div class="option-line"><span>记录时间</span><b>{{ formatDateTime(detail.createdAt) }}</b></div>
        <div class="option-line"><span>更新时间</span><b>{{ formatDateTime(detail.updatedAt) }}</b></div>
        <div class="option-line"><span>事件描述</span><b>{{ detail.eventDesc || '-' }}</b></div>
        <div class="option-line"><span>耗时</span><b>{{ formatDuration(detail.errorMessage) }}</b></div>
        <div class="option-line option-line-block">
          <span>开启原因</span>
          <div class="option-content">{{ detail.openReason || '-' }}</div>
        </div>
        <div class="option-line option-line-block">
          <span>求解原因</span>
          <div class="option-content">{{ detail.solveReason || '-' }}</div>
        </div>
        <div v-if="extractScreenshot(detail.errorMessage)" class="option-line option-line-block">
          <span>调试截图</span>
          <div class="option-content mono">{{ extractScreenshot(detail.errorMessage) }}</div>
        </div>
        <div v-if="detail.status === 'fail'" class="error-message">
          <div class="error-message-head">失败原因</div>
          <pre class="error-message-body">{{ detail.failureReason ? failureReasonText(detail.failureReason) : (stripMeta(detail.errorMessage) || (detail.result === 'slider_success' ? '滑块已通过但 Cookie Session 已过期，需重新扫码登录' : '滑块验证未通过')) }}</pre>
        </div>
        <div v-else-if="detail.status === 'success' && stripMeta(detail.errorMessage)" class="option-line option-line-block">
          <span>备注</span>
          <div class="option-content">{{ stripMeta(detail.errorMessage) }}</div>
        </div>
      </template>
      <EmptyState v-else icon="🧩" title="选择记录查看详情" description="点击左侧列表中的任意一行，这里会展示该滑块求解记录的完整信息。" />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import StatCard from '../components/StatCard.vue'
import CardPanel from '../components/CardPanel.vue'
import BaseTable from '../components/BaseTable.vue'
import Badge from '../components/Badge.vue'
import AppButton from '../components/AppButton.vue'
import EmptyState from '../components/EmptyState.vue'
import Pagination from '../components/Pagination.vue'
import Icon from '../components/Icon.vue'
import { getCaptchaRecords, getCaptchaQueueStatus } from '../api/captcha.js'

const loading = ref(false)
const loadError = ref('')
const rows = ref([])
const total = ref(0)
const current = ref(1)
const size = ref(20)
const detail = ref(null)
const filters = reactive({ status: '', triggerScene: '' })

// 队列实时状态
const queueStatus = reactive({ queued: 0, retrying: 0, timeout: 0, precheckRejected: 0, workers: 4 })
let queueTimer = null

async function loadQueueStatus() {
  try {
    const res = await getCaptchaQueueStatus()
    const payload = res && res.data ? res.data : (res || {})
    queueStatus.queued = Number(payload.queued) || 0
    queueStatus.retrying = Number(payload.retrying) || 0
    queueStatus.timeout = Number(payload.timeout) || 0
    queueStatus.precheckRejected = Number(payload.precheckRejected) || 0
    queueStatus.workers = Number(payload.workers) || 4
  } catch {
    // 静默失败，不影响主列表
  }
}

// 排队中/求解中是瞬态状态，空结果时给用户友好提示
const isTransientStatus = computed(() => filters.status === 'queued' || filters.status === 'retrying')

const cols = [
  { key: 'createdAt', title: '记录时间' },
  { key: 'accountId', title: '账号ID' },
  { key: 'accountName', title: '账号名称' },
  { key: 'openReason', title: '开启原因' },
  { key: 'solveReason', title: '求解原因' },
  { key: 'status', title: '求解状态' },
  { key: 'failed', title: '是否失败' },
  { key: 'failReason', title: '失败原因' }
]

const successCount = computed(() => rows.value.filter(r => r.status === 'success').length)
const failedCount = computed(() => rows.value.filter(r => r.status === 'fail').length)
const retryingCount = computed(() => rows.value.filter(r => r.status === 'retrying').length)

function resultText(result) {
  if (result === 'slider_success') return '滑块成功'
  if (result === 'slider_fail') return '滑块失败'
  if (result === 'precheck_fail') return '预校验失败'
  if (result === 'stale_terminated') return '超时终止'
  if (result === 'cookie_invalid') return 'Cookie 失效'
  if (result === 'service_unavailable') return '服务不可用'
  return '未求解'
}
function resultBadge(result) {
  if (result === 'slider_success') return 'green'
  if (result === 'slider_fail') return 'red'
  if (result === 'precheck_fail') return 'red'
  if (result === 'stale_terminated') return 'orange'
  if (result === 'cookie_invalid') return 'red'
  if (result === 'service_unavailable') return 'gray'
  return 'gray'
}
function statusText(status) {
  if (status === 'success') return '成功'
  if (status === 'fail') return '失败'
  if (status === 'retrying') return '求解中'
  if (status === 'queued') return '排队中'
  if (status === 'timeout') return '超时'
  if (status === 'precheck_rejected') return '预检验拒绝'
  return status || '-'
}
function statusBadge(status) {
  if (status === 'success') return 'green'
  if (status === 'fail') return 'red'
  if (status === 'retrying') return 'orange'
  if (status === 'queued') return 'blue'
  if (status === 'timeout') return 'gray'
  if (status === 'precheck_rejected') return 'yellow'
  return 'gray'
}
function triggerSceneText(scene) {
  const map = {
    manual: '手动触发',
    manual_retry: '手动重试',
    ws_connect: 'WS 连接',
    cookie_keepalive: 'Cookie 保活',
    token_refresh: 'Token 刷新',
  }
  return map[scene] || scene || '-'
}

/** 失败原因分类文案：将后端 failureReason 枚举值映射为中文展示 */
function failureReasonText(reason) {
  if (!reason) return ''
  const map = {
    slider_fail: '滑块验证未通过',
    cookie_invalid: 'Cookie 已失效，需重新扫码登录',
    service_unavailable: '求解服务暂时不可用',
    timeout: '求解超时',
    account_inactive: '账号连续 3 天无操作，已禁用求解',
    account_disabled: '账号状态异常，已禁用求解',
    precheck_rejected: '预校验拒绝（Cookie 或账号状态不满足求解条件）',
    stale_terminated: '记录长时间无响应，已终止',
  }
  return map[reason] || reason
}

function formatDateTime(value) {
  if (!value) return '-'
  return String(value).replace('T', ' ').replace(/\.\d+$/, '').slice(0, 19)
}

/** 从 error_message 元数据前缀解析 durationMs */
function formatDuration(errorMessage) {
  const m = String(errorMessage || '').match(/durationMs=(\d+)/i)
  if (!m) return '-'
  const ms = Number(m[1])
  if (!Number.isFinite(ms) || ms < 0) return '-'
  if (ms < 1000) return `${ms} ms`
  return `${(ms / 1000).toFixed(1)} s`
}

function extractScreenshot(errorMessage) {
  const m = String(errorMessage || '').match(/screenshot=([^\s\]]+)/i)
  return m ? m[1] : ''
}

function stripMeta(errorMessage) {
  if (!errorMessage) return ''
  return String(errorMessage).replace(/^\[[^\]]*\]\s*/, '').trim()
}

async function load() {
  loading.value = true
  loadError.value = ''
  rows.value = []
  total.value = 0
  detail.value = null
  try {
    const params = {
      page: current.value,
      pageSize: size.value,
      status: filters.status,
    }
    if (filters.triggerScene) params.triggerScene = filters.triggerScene
    const res = await getCaptchaRecords(params)
    // 兼容两种响应：Java 网关拆包后 { list, total, ... } 或未拆包 { code, data: { list, total, ... } }
    const payload = res && res.data && (Array.isArray(res.data.list) || res.data.total != null) ? res.data : (res || {})
    const list = Array.isArray(payload.list) ? payload.list : []
    rows.value = list
    total.value = Number(payload.total) || 0
  } catch (e) {
    loadError.value = e?.message || '滑块记录加载失败'
  } finally {
    loading.value = false
  }
}

function goPage(p) {
  current.value = p
  load()
}

function search() {
  current.value = 1
  load()
}

function showDetail(row) { detail.value = row }

// ============================================================
// SSE 事件监听：收到 captcha_solve 事件时自动刷新记录列表
// ============================================================
// 用户反馈：手动点击滑块求解后，本页未显示新增记录。
// 原因：页面仅在 onMounted 时加载一次，不感知后端写入的新记录。
// 修复：监听全局 SSE 事件 captcha_solve（与 useCaptchaSolver.js 一致的事件源），
//       收到事件后刷新列表。为避免 retrying→success/fail 两次事件导致重复请求，加 800ms 防抖。
let refreshTimer = null
function scheduleRefresh() {
  if (refreshTimer) clearTimeout(refreshTimer)
  refreshTimer = setTimeout(() => {
    refreshTimer = null
    // 仅当用户未离开本页且非查询中时刷新，避免与手动查询冲突
    if (!loading.value) load()
  }, 800)
}

function onSseCaptchaSolve(event) {
  const evtDetail = event?.detail
  const data = evtDetail?.payload || evtDetail || {}
  const eventType = evtDetail?.type || data.type || ''
  if (eventType !== 'captcha_solve') return
  scheduleRefresh()
}

onMounted(() => {
  load()
  loadQueueStatus()
  // 队列状态定时刷新（15 秒）
  queueTimer = setInterval(loadQueueStatus, 15000)
  window.addEventListener('xya-sse-event', onSseCaptchaSolve)
})

onUnmounted(() => {
  window.removeEventListener('xya-sse-event', onSseCaptchaSolve)
  if (refreshTimer) {
    clearTimeout(refreshTimer)
    refreshTimer = null
  }
  if (queueTimer) {
    clearInterval(queueTimer)
    queueTimer = null
  }
})
</script>

<style scoped>
.slider-layout :deep(.stat-grid) {
  grid-template-columns: repeat(4, 1fr);
}
@media (max-width: 1500px) {
  .slider-layout :deep(.stat-grid) {
    grid-template-columns: repeat(2, 1fr);
  }
}
.queue-status-bar {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 12px 16px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  margin-bottom: 4px;
  flex-wrap: wrap;
}
.queue-status-item {
  display: flex;
  align-items: center;
  gap: 8px;
}
.queue-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #cbd5e1;
}
.queue-dot.dot-solving {
  background: #fbbf24;
}
.queue-dot.dot-timeout {
  background: #94a3b8;
}
.queue-dot.dot-rejected {
  background: #eab308;
}
.queue-dot.dot-active {
  background: #3b82f6;
  box-shadow: 0 0 6px rgba(59, 130, 246, 0.5);
  animation: pulse 1.5s infinite;
}
.queue-dot.dot-solving.dot-active {
  background: #f59e0b;
  box-shadow: 0 0 6px rgba(245, 158, 11, 0.5);
}
.queue-dot.dot-timeout.dot-active {
  background: #64748b;
  box-shadow: 0 0 6px rgba(100, 116, 139, 0.5);
}
.queue-dot.dot-rejected.dot-active {
  background: #ca8a04;
  box-shadow: 0 0 6px rgba(202, 138, 4, 0.5);
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.queue-text {
  font-size: 13px;
  color: #475569;
}
.queue-text b {
  font-size: 16px;
  color: #94a3b8;
}
.queue-text b.num-active {
  color: #2563eb;
}
.queue-empty-hint {
  font-size: 12px;
  color: #94a3b8;
}
.rules-card {
  padding: 16px 18px;
  background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  margin: 4px 0 14px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.rules-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 1px dashed #e2e8f0;
}
.rules-head::before {
  content: '';
  width: 3px;
  height: 14px;
  background: linear-gradient(180deg, #3b82f6, #6366f1);
  border-radius: 2px;
}
.rules-title {
  font-size: 14px;
  font-weight: 700;
  color: #1e293b;
  letter-spacing: 0.3px;
}
.rules-sub {
  font-size: 12px;
  color: #94a3b8;
  margin-left: auto;
}
.rules-callout {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 14px;
  background: linear-gradient(135deg, #eff6ff 0%, #e0f2fe 100%);
  border: 1px solid #bfdbfe;
  border-left: 3px solid #3b82f6;
  border-radius: 8px;
  margin-bottom: 14px;
  transition: box-shadow 0.2s;
}
.rules-callout:hover {
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.12);
}
.rules-callout strong {
  display: block;
  font-size: 13px;
  color: #1e40af;
  margin-bottom: 4px;
  font-weight: 600;
}
.rules-callout span {
  font-size: 12.5px;
  line-height: 1.75;
  color: #475569;
}
.rules-badge {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  font-style: italic;
  color: #fff;
  margin-top: 1px;
  background: linear-gradient(135deg, #3b82f6, #6366f1);
  box-shadow: 0 1px 3px rgba(59, 130, 246, 0.3);
}
.badge-blue { background: linear-gradient(135deg, #3b82f6, #6366f1); }
.rules-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px 22px;
}
.rule-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 12.5px;
  line-height: 1.85;
  color: #475569;
  padding: 4px 6px;
  border-radius: 6px;
  transition: background 0.15s;
}
.rule-item:hover {
  background: rgba(255, 255, 255, 0.6);
}
.rule-item strong {
  color: #1e293b;
  font-weight: 600;
}
.rules-dot {
  flex-shrink: 0;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 7px;
  position: relative;
}
.rules-dot::after {
  content: '';
  position: absolute;
  inset: -3px;
  border-radius: 50%;
  background: inherit;
  opacity: 0.18;
  z-index: -1;
}
.dot-red { background: #ef4444; }
.dot-purple { background: #8b5cf6; }
.dot-orange { background: #f59e0b; }
.dot-blue { background: #3b82f6; }
.dot-green { background: #10b981; }
.dot-gray { background: #94a3b8; }
@media (max-width: 768px) {
  .rules-grid { grid-template-columns: 1fr; }
  .rules-card { padding: 14px; }
}
.slider-layout :deep(.base-table tbody tr) {
  cursor: pointer;
  transition: background .15s;
}
.slider-layout :deep(.base-table tbody tr:hover) {
  background: #f3f8ff;
}
.cell-truncate {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: middle;
}
.fail-text {
  color: #ef4444;
}
.option-line-block {
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}
.option-line-block .option-content {
  width: 100%;
  padding: 8px 12px;
  background: #f6f8fa;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.6;
  color: #475569;
  word-break: break-word;
  white-space: pre-wrap;
}
.error-message {
  margin-top: 14px;
  border: 1px solid #ffd1d1;
  border-radius: 10px;
  background: linear-gradient(135deg, #fff8f8, #fff5f5);
  overflow: hidden;
}
.error-message-head {
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 700;
  color: #ef4444;
  border-bottom: 1px solid #ffd1d1;
}
.error-message-body {
  margin: 0;
  padding: 12px 14px;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.6;
  color: #526079;
  font-family: inherit;
}
</style>
