<template>
  <div class="grid logs-layout" style="grid-template-columns:minmax(0,1fr) 460px;gap:18px">
    <div>
      <div v-if="error" class="global-notice error">{{ error }}</div>
      <div v-if="logsLoadError" class="global-notice error">日志列表加载失败：{{ logsLoadError }}</div>
      <div v-if="success" class="global-notice success">{{ success }}</div>
      <div class="grid stat-grid">
        <StatCard title="总操作数" :value="metricValue(total)" change="真实记录" icon="record" />
        <StatCard title="当前页条数" :value="metricValue(rows.length)" change="本页统计" icon="shield" color="green" />
        <StatCard title="失败数" :value="metricValue(failedCount)" change="本页统计" icon="warning" color="red" />
        <StatCard title="成功数" :value="metricValue(successCount)" change="本页统计" icon="shield" color="green" />
      </div>
      <CardPanel title="操作日志">
        <div class="toolbar">
          <select v-model="filters.operationType" class="input" @change="search">
            <option value="">全部类型</option>
            <option v-for="t in typeOptions" :key="t.value" :value="t.value">{{ t.label }}</option>
          </select>
          <input v-model="filters.keyword" class="input" placeholder="关键词搜索" @keyup.enter="search">
          <AppButton type="primary" :disabled="loading" @click="search">{{ loading ? '查询中...' : '查询' }}</AppButton>
          <AppButton :loading="exporting" :disabled="loading || exporting || !logsAvailable" @click="exportCsv">{{ exporting ? '导出中...' : '导出CSV' }}</AppButton>
        </div>
        <EmptyState v-if="!logsAvailable" icon="⚠" title="操作日志不可用" :description="logsLoadError || '正在加载操作日志，请稍候。'" />
        <BaseTable v-else :columns="cols" :rows="rows">
          <template #operationType="{row}"><span :title="row.operationType">{{ operationTypeLabel(row.operationType) }}</span></template>
          <template #status="{row}"><Badge :type="logStatusBadge(row.status)">{{ logStatusText(row.status) }}</Badge></template>
          <template #createdTime="{row}">{{ formatDateTime(row.createdTime) }}</template>
          <template #op="{row}"><button class="link" @click="showDetail(row)">查看</button></template>
          <template #empty><EmptyState icon="📋" title="暂无操作日志" description="系统操作记录将在此显示。" /></template>
        </BaseTable>
        <Pagination v-if="logsAvailable" :total="total" :current="current" :page-size="size" @page-change="goPage" />
      </CardPanel>
    </div>
    <div class="right-drawer">
      <template v-if="detail">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
          <h3>日志详情</h3>
          <button class="modal-close" @click="detail=null"><Icon name="close" /></button>
        </div>
        <p>日志 ID：<b>{{ detail.id || '-' }}</b></p>
        <div class="grid" style="grid-template-columns:repeat(2,1fr);gap:10px">
          <div class="metric-tile"><span>操作类型</span><b :title="detail.operationType">{{ operationTypeLabel(detail.operationType) }}</b></div>
          <div class="metric-tile"><span>目标类型</span><b>{{ detail.targetType || '-' }}</b></div>
          <div class="metric-tile"><span>状态</span><Badge :type="logStatusBadge(detail.status)">{{ logStatusText(detail.status) }}</Badge></div>
          <div class="metric-tile"><span>操作人</span><b>{{ detail.operator || '-' }}</b></div>
        </div>
        <div class="option-line"><span>操作时间</span><b>{{ formatDateTime(detail.createdTime) }}</b></div>
        <div class="option-line"><span>目标ID</span><b>{{ detail.targetId || '-' }}</b></div>
        <p v-if="detail.description" class="subtle">描述：{{ detail.description }}</p>
        <div v-if="detail.requestParams" class="json-section">
          <div class="json-section-head">
            <button type="button" class="json-toggle" @click="toggleJsonSection('request')">
              <span class="json-toggle-icon">{{ expandedJson.request ? '▾' : '▸' }}</span>
              请求参数
            </button>
            <button type="button" class="json-copy" :disabled="copiedJson === 'request'" @click="copyJson(detail.requestParams, 'request')">{{ copiedJson === 'request' ? '已复制' : '复制' }}</button>
          </div>
          <pre v-show="expandedJson.request" class="mock-json">{{ formatJson(detail.requestParams) }}</pre>
        </div>
        <div v-if="detail.responseResult" class="json-section">
          <div class="json-section-head">
            <button type="button" class="json-toggle" @click="toggleJsonSection('response')">
              <span class="json-toggle-icon">{{ expandedJson.response ? '▾' : '▸' }}</span>
              响应结果
            </button>
            <button type="button" class="json-copy" :disabled="copiedJson === 'response'" @click="copyJson(detail.responseResult, 'response')">{{ copiedJson === 'response' ? '已复制' : '复制' }}</button>
          </div>
          <pre v-show="expandedJson.response" class="mock-json">{{ formatJson(detail.responseResult) }}</pre>
        </div>
      </template>
      <EmptyState v-else icon="📋" title="选择日志查看详情" description="点击左侧列表中的「查看」按钮，这里会展示日志详情。" />
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import StatCard from '../components/StatCard.vue'
import CardPanel from '../components/CardPanel.vue'
import BaseTable from '../components/BaseTable.vue'
import Badge from '../components/Badge.vue'
import AppButton from '../components/AppButton.vue'
import EmptyState from '../components/EmptyState.vue'
import Pagination from '../components/Pagination.vue'
import Icon from '../components/Icon.vue'
import { getOperationLogs, exportOperationLogs } from '../api/operationLogs.js'
import { totalOf } from '../utils/apiData.js'

const expandedJson = reactive({ request: true, response: true })
const copiedJson = ref('')
let copyResetTimer = null
function toggleJsonSection(key) { expandedJson[key] = !expandedJson[key] }
async function copyJson(text, key) {
  if (!text) return
  const content = formatJson(text)
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(content)
    } else {
      const ta = document.createElement('textarea')
      ta.value = content
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    copiedJson.value = key
    if (copyResetTimer) clearTimeout(copyResetTimer)
    copyResetTimer = setTimeout(() => { copiedJson.value = '' }, 1500)
  } catch {
    error.value = '复制失败，请手动选择文本复制'
    setTimeout(() => { if (error.value) error.value = '' }, 4000)
  }
}

const loading = ref(false)
const exporting = ref(false)
const error = ref('')
const success = ref('')
const logsLoadError = ref('')
const logsAvailable = ref(false)
const rows = ref([])
const total = ref(0)
const current = ref(1)
const size = ref(20)
const detail = ref(null)
const filters = reactive({ operationType: '', keyword: '' })

// 操作类型枚举映射（后端原始值 -> 中文标签）
const OPERATION_TYPE_MAP = {
  LOGIN: '登录',
  LOGOUT: '退出登录',
  SEND_MESSAGE: '发送消息',
  MESSAGE_SEND_TEXT: '发送消息',
  AUTO_DELIVERY: '自动发货',
  DELIVERY_CARD: '卡密发货',
  AUTO_REPLY: '自动回复',
  CONFIRM_RECEIPT: '确认收货',
  SYNC_PRODUCTS: '同步商品',
  WEBSOCKET_START: '启动连接',
  WEBSOCKET_STOP: '断开连接',
  PUBLISH_PRODUCT: '发布商品',
  DELETE_LOCAL: '删除本地',
  OFF_SHELF: '下架商品',
  CARD_IMPORT: '卡密导入',
  CARD_DELETE: '卡密删除',
  RULE_SAVE: '保存规则',
  RULE_DELETE: '删除规则',
  OTHER: '其他'
}

const typeOptions = [
  { value: 'LOGIN', label: '登录' },
  { value: 'SEND_MESSAGE', label: '发送消息' },
  { value: 'AUTO_DELIVERY', label: '自动发货' },
  { value: 'AUTO_REPLY', label: '自动回复' },
  { value: 'CONFIRM_RECEIPT', label: '确认收货' },
  { value: 'SYNC_PRODUCTS', label: '同步商品' },
  { value: 'WEBSOCKET_START', label: '启动连接' },
  { value: 'WEBSOCKET_STOP', label: '断开连接' },
  { value: 'PUBLISH_PRODUCT', label: '发布商品' },
  { value: 'CARD_IMPORT', label: '卡密导入' }
]

function operationTypeLabel(code) {
  if (!code) return '-'
  // 1. 精确匹配
  if (OPERATION_TYPE_MAP[code]) return OPERATION_TYPE_MAP[code]
  // 2. 大写下划线格式直接匹配
  const upper = String(code).toUpperCase()
  if (OPERATION_TYPE_MAP[upper]) return OPERATION_TYPE_MAP[upper]
  // 3. 包含匹配（如 MESSAGE_SEND_TEXT 含 MESSAGE_SEND）
  for (const key of Object.keys(OPERATION_TYPE_MAP)) {
    if (upper.includes(key)) return OPERATION_TYPE_MAP[key]
  }
  // 4. 兜底：已经是中文则原样返回，否则截断
  if (/[\u4e00-\u9fa5]/.test(code)) return code
  return code
}

function formatDateTime(value) {
  if (!value) return '-'
  const s = String(value)
  // 兼容 ISO "2026-06-29T10:03:01" 和 "2026-06-29 10:03:01"
  return s.replace('T', ' ').replace(/\.\d+$/, '').slice(0, 19)
}

const cols = [
  { key: 'id', title: '日志ID' },
  { key: 'operationType', title: '操作类型' },
  { key: 'targetType', title: '目标类型' },
  { key: 'description', title: '描述' },
  { key: 'status', title: '状态' },
  { key: 'operator', title: '操作人' },
  { key: 'createdTime', title: '操作时间' },
  { key: 'op', title: '操作' }
]

const failedCount = computed(() => rows.value.filter(r => r.status === '失败').length)
const successCount = computed(() => rows.value.filter(r => r.status === '成功').length)
function metricValue(value) { return logsAvailable.value ? value : '—' }
function logStatusText(status) { return status || '日志状态未知' }
function logStatusBadge(status) {
  if (status === '成功') return 'green'
  if (status === '失败') return 'red'
  if (status === '部分成功') return 'orange'
  return 'gray'
}

async function load() {
  loading.value = true
  error.value = ''
  logsLoadError.value = ''
  logsAvailable.value = false
  rows.value = []
  total.value = 0
  detail.value = null
  try {
    const res = await getOperationLogs({
      current: current.value,
      size: size.value,
      operationType: filters.operationType,
      keyword: filters.keyword
    })
    const data = res?.data
    const list = Array.isArray(data) ? data : data?.records || data?.list || data?.rows || data?.items
    if (!Array.isArray(list)) throw new Error('操作日志响应格式异常')
    rows.value = list
    total.value = totalOf(data, rows.value.length)
    logsAvailable.value = true
  } catch (e) {
    logsLoadError.value = e?.message || '日志加载失败'
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

function formatJson(str) {
  if (!str) return ''
  try { return JSON.stringify(JSON.parse(str), null, 2) } catch { return str }
}

async function exportCsv() {
  if (!logsAvailable.value) {
    error.value = '日志列表不可用，请先重试加载后再导出'
    return
  }
  exporting.value = true
  error.value = ''
  try {
    const blob = await exportOperationLogs({ operationType: filters.operationType, keyword: filters.keyword })
    if (!(blob instanceof Blob) || blob.size === 0) throw new Error('日志导出响应格式异常')
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `operation-logs-${Date.now()}.csv`
    a.click()
    URL.revokeObjectURL(url)
    success.value = '日志导出成功'
    setTimeout(() => { success.value = '' }, 3000)
  } catch (e) {
    error.value = e.message || '导出失败，请稍后重试'
  } finally {
    exporting.value = false
  }
}

function onHeaderAction(event) {
  if (event.detail === 'logs-export') exportCsv()
  if (event.detail === 'logs-refresh') load()
}

onMounted(() => {
  window.addEventListener('xya-header-action', onHeaderAction)
  load()
})

onBeforeUnmount(() => {
  window.removeEventListener('xya-header-action', onHeaderAction)
})
</script>
