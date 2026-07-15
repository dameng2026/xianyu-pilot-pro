<template>
  <div>
    <div v-if="error" class="global-notice error">{{ error }}</div>
    <div v-if="statsError" class="global-notice warn">{{ statsError }}</div>
    <div class="grid stat-grid">
      <StatCard title="执行记录" :value="metricText(total)" :change="listError ? '状态不可用' : '真实执行表'" icon="task" />
      <StatCard title="成功" :value="metricText(statusStats.success)" :change="statsError ? '状态不可用' : '全量统计'" icon="shield" color="green" />
      <StatCard title="失败" :value="metricText(statusStats.failed)" :change="statsError ? '状态不可用' : '全量统计'" icon="warning" color="red" />
      <StatCard title="进行中" :value="metricText(statusStats.active)" :change="statsError ? '状态不可用' : '排队中 + 运行中'" icon="play" color="blue" />
    </div>

    <div class="workflow-task-layout">
      <CardPanel title="工作流任务">
        <div class="toolbar">
          <select class="account-select" :value="selectedAccountId" @change="onAccountChange($event)">
            <option value="">全部账号</option>
            <option v-for="acct in accounts" :key="acct.id" :value="acct.id">{{ acct.nickname || acct.displayName || ('账号' + acct.id) }}</option>
          </select>
          <span v-if="accountsError" class="account-load-error">{{ accountsError }}</span>
          <span class="select" :class="{active: !status}" @click="setStatus('')">全部状态</span>
          <span class="select" :class="{active: status === 'success'}" @click="setStatus('success')">成功</span>
          <span class="select" :class="{active: status === 'failed'}" @click="setStatus('failed')">失败</span>
          <span class="select" :class="{active: status === 'running'}" @click="setStatus('running')">运行中</span>
          <AppButton @click="load">刷新</AppButton>
        </div>
        <EmptyState v-if="listError" variant="error" title="任务列表加载失败" :description="listError">
          <template #actions><AppButton @click="load">重试</AppButton></template>
        </EmptyState>
        <BaseTable v-else :columns="cols" :rows="tasks">
          <template #status="{row}"><Badge :type="statusBadge(row.status)">{{ statusText(row.status) }}</Badge></template>
          <template #progress="{row}"><span class="mini-progress"><i :style="{width:progressWidth(row.progress)}"></i></span> {{ progressText(row.progress) }}</template>
          <template #node="{row}">{{ row.nodeSuccess ?? '—' }} / {{ row.nodeTotal ?? '—' }}</template>
          <template #createdTime="{row}">{{ formatDateTime(row.createdTime) }}</template>
          <template #op="{row}"><button class="link" @click="open(row.id)">查看详情</button></template>
        </BaseTable>
        <Pagination v-if="!listError" :total="total" :current="current" :page-size="pageSize" @page-change="goPage" />
      </CardPanel>

      <CardPanel title="任务详情" class="task-detail">
        <EmptyState v-if="detailError" variant="error" title="任务详情加载失败" :description="detailError" />
        <template v-else-if="detail">
          <h2>{{ detail.executionNo }}</h2>
          <p><Badge :type="statusBadge(detail.status)">{{ statusText(detail.status) }}</Badge> {{ detail.workflowName }}</p>
          <div class="detail-grid"><span>触发方式</span><b>{{ detail.triggerMode }}</b><span>进度</span><b>{{ progressText(detail.progress) }}</b><span>开始时间</span><b>{{ detail.startedTime || '-' }}</b><span>结束时间</span><b>{{ detail.finishedTime || '-' }}</b></div>
          <div class="toolbar" style="margin:12px 0">
            <AppButton v-if="['running','queued'].includes(detail.status)" type="danger" @click="terminateCurrent">终止执行</AppButton>
            <AppButton v-if="detail.status === 'failed'" type="primary" @click="retryFailed">重试失败节点</AppButton>
          </div>
          <h3>节点执行步骤</h3>
          <div v-for="s in detail.steps || []" :key="s.id" class="step-line">
            <i :class="s.status"></i>
            <div><b>{{ s.nodeName }}</b><small>{{ s.nodeType }} · {{ s.durationMs === null || s.durationMs === undefined ? '耗时未提供' : `${s.durationMs}ms` }}</small></div>
            <Badge :type="statusBadge(s.status)">{{ statusText(s.status) }}</Badge>
          </div>
          <h3>执行时间线</h3>
          <div v-for="e in detail.timeline || []" :key="e.id" class="timeline-line">
            <b>{{ e.title || e.eventType }}</b><span>{{ e.content }}</span><small>{{ e.createdTime }}</small>
          </div>
          <h3>执行输出</h3>
          <pre class="mock-json">{{ detail.output === null || detail.output === undefined ? '执行输出未提供' : JSON.stringify(detail.output, null, 2) }}</pre>
          <h3>节点产物</h3>
          <div v-if="(detail.artifacts || []).length" class="artifact-list">
            <div v-for="a in detail.artifacts" :key="a.id || a.nodeKey + a.artifactType" class="artifact-item">
              <div class="artifact-head">
                <span class="chip">{{ a.artifactType || a.artifact_type }}</span>
                <span class="artifact-title">{{ a.title || '' }}</span>
                <span class="artifact-node">{{ a.nodeKey || a.node_key || '' }}</span>
              </div>
              <pre class="artifact-text">{{ formatArtifact(a) }}</pre>
            </div>
          </div>
          <EmptyState v-else icon="📦" title="暂无产物数据" description="工作流执行产生的图片、商品、文案等产物会显示在这里。" />
        </template>
        <EmptyState v-else icon="🔍" title="请选择任务" description="从左侧任务列表中选择一项，查看详细执行信息。" />
      </CardPanel>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import StatCard from '../components/StatCard.vue'
import CardPanel from '../components/CardPanel.vue'
import AppButton from '../components/AppButton.vue'
import BaseTable from '../components/BaseTable.vue'
import Pagination from '../components/Pagination.vue'
import Badge from '../components/Badge.vue'
import EmptyState from '../components/EmptyState.vue'
import { getWorkflowExecution, listWorkflowExecutions, terminateWorkflowExecution, retryWorkflowFailedNode } from '../api/workflow.js'
import { getLiteAccounts } from '../api/accounts.js'

function formatDateTime(value) {
  if (!value) return '-'
  const s = String(value)
  // 兼容 ISO "2026-06-29T10:03:01" 和 "2026-06-29 10:03:01"
  return s.replace('T', ' ').replace(/\.\d+$/, '').slice(0, 19)
}
import { globalConfirm } from '../composables/confirmState.js'
import { formatArtifact } from '../utils/artifactFormat.js'

const tasks = ref([])
const detail = ref(null)
const status = ref('')
const total = ref(0)
const current = ref(1)
const pageSize = ref(20)
const error = ref('')
const listError = ref('')
const detailError = ref('')
const statsError = ref('')
const accountsError = ref('')
const accounts = ref([])
const selectedAccountId = ref('')
// 全量状态统计（独立于当前页数据，避免仅基于当前页 20 条计算导致误导）
const statusStats = ref({ success: null, failed: null, active: null })
const cols = [
  { key: 'executionNo', title: '任务编号' },
  { key: 'workflowName', title: '工作流' },
  { key: 'triggerMode', title: '触发方式' },
  { key: 'node', title: '节点' },
  { key: 'progress', title: '进度' },
  { key: 'status', title: '状态' },
  { key: 'createdTime', title: '创建时间' },
  { key: 'op', title: '操作' }
]
function strictTotalOf(response, label) {
  const data = response?.data
  if (!data || typeof data !== 'object' || Array.isArray(data) || data.total === null || data.total === undefined) {
    throw new Error(`${label}响应缺少总数`)
  }
  const totalValue = Number(data.total)
  if (!Number.isSafeInteger(totalValue) || totalValue < 0) {
    throw new Error(`${label}总数响应格式异常`)
  }
  return totalValue
}

// 并行请求各状态的全量总数，避免 StatCard 仅显示当前页 20 条的误导
async function loadStatusStats() {
  statsError.value = ''
  try {
    const acctParam = selectedAccountId.value ? { accountId: selectedAccountId.value } : {}
    const [successRes, failedRes, queuedRes, runningRes] = await Promise.all([
      listWorkflowExecutions({ current: 1, size: 1, status: 'success', ...acctParam }),
      listWorkflowExecutions({ current: 1, size: 1, status: 'failed', ...acctParam }),
      listWorkflowExecutions({ current: 1, size: 1, status: 'queued', ...acctParam }),
      listWorkflowExecutions({ current: 1, size: 1, status: 'running', ...acctParam })
    ])
    const queuedTotal = strictTotalOf(queuedRes, '排队中任务统计')
    const runningTotal = strictTotalOf(runningRes, '运行中任务统计')
    const activeTotal = queuedTotal + runningTotal
    if (!Number.isSafeInteger(activeTotal)) throw new Error('进行中任务统计总数超出安全范围')
    statusStats.value = {
      success: strictTotalOf(successRes, '成功任务统计'),
      failed: strictTotalOf(failedRes, '失败任务统计'),
      active: activeTotal
    }
  } catch (e) {
    statusStats.value = { success: null, failed: null, active: null }
    statsError.value = `${e?.message || '状态统计加载失败'}，相关指标显示为“—”。`
  }
}
async function loadAccounts() {
  accountsError.value = ''
  try {
    const res = await getLiteAccounts({ size: 200 })
    const data = res?.data
    const list = Array.isArray(data) ? data : data?.records || data?.accounts || data?.list || data?.rows
    if (!Array.isArray(list)) throw new Error('账号列表响应格式异常')
    accounts.value = list
  } catch (e) {
    console.warn('[WorkflowTasks] 账号列表加载失败:', e?.message || e)
    accounts.value = []
    accountsError.value = '账号筛选暂时不可用'
  }
}
async function load() {
  error.value = ''
  listError.value = ''
  try {
    const params = { current: current.value, size: pageSize.value, status: status.value }
    if (selectedAccountId.value) params.accountId = selectedAccountId.value
    const res = await listWorkflowExecutions(params)
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data) || !Array.isArray(data.records)) throw new Error('工作流任务列表响应格式异常')
    tasks.value = data.records
    total.value = strictTotalOf(res, '工作流任务列表')
    // 并行加载全量状态统计（不阻塞主列表渲染）
    loadStatusStats()
    if (!detail.value && tasks.value[0]) open(tasks.value[0].id)
  } catch (e) {
    tasks.value = []
    total.value = null
    listError.value = e.message || '任务列表加载失败'
  }
}
function goPage(p) {
  current.value = p
  load()
}
async function open(id) {
  detailError.value = ''
  try {
    const data = (await getWorkflowExecution(id))?.data
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('工作流任务详情响应格式异常')
    detail.value = data
  }
  catch (e) {
    detail.value = null
    detailError.value = e?.message || '请稍后重试。'
  }
}
function setStatus(s) { status.value = s; current.value = 1; detail.value = null; load() }
function onAccountChange(e) {
  selectedAccountId.value = e.target.value
  current.value = 1
  detail.value = null
  load()
}
async function terminateCurrent(){
  if(!detail.value) return
  error.value = ''
  try {
    const reason=await globalConfirm.prompt('请输入终止原因', '用户手动终止')
    if(reason===false || !reason) return
    await terminateWorkflowExecution(detail.value.id,{reason})
    await open(detail.value.id); await load()
  } catch (e) { error.value = e.message || '终止执行失败' }
}
async function retryFailed(){
  if(!detail.value) return
  error.value = ''
  try {
    const failed=(detail.value.steps||[]).find(s=>s.status==='failed')
    const res=await retryWorkflowFailedNode(detail.value.id,{nodeKey:failed?.nodeKey})
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('工作流重试响应格式异常')
    detail.value=data; await load()
  } catch (e) { error.value = e.message || '重试失败节点失败' }
}
function statusText(s) { return ({ success: '成功', failed: '失败', running: '运行中', queued: '排队中', terminated:'已终止' })[s] || s || '-' }
function statusBadge(s) { return ({ success:'green', failed:'red', running:'blue', queued:'blue', terminated:'gray' })[s] || 'gray' }
function metricText(value) { return value === null || value === undefined ? '—' : value }
function progressText(value) { return value === null || value === undefined ? '—' : `${value}%` }
function progressWidth(value) { return value === null || value === undefined ? '0%' : `${Math.max(0, Math.min(100, Number(value) || 0))}%` }
function onHeaderAction(event) {
  if (event.detail === 'workflow-tasks-refresh') load()
}
onMounted(() => {
  window.addEventListener('xya-header-action', onHeaderAction)
  loadAccounts()
  load()
})
onBeforeUnmount(() => {
  window.removeEventListener('xya-header-action', onHeaderAction)
})
</script>

<style scoped>
.account-load-error{color:#b54708;font-size:12px}
.workflow-task-layout{display:grid;grid-template-columns:minmax(0,1fr) 430px;gap:18px}.select.active{border-color:#0d6bff;color:#0d6bff;background:#eef6ff}.account-select{height:32px;padding:0 10px;border:1px solid #d8e0ec;border-radius:8px;font-size:13px;color:#16213e;background:#fff;cursor:pointer;outline:none;transition:border-color .2s}.account-select:hover{border-color:#0d6bff}.account-select:focus{border-color:#0d6bff;box-shadow:0 0 0 3px rgba(13,107,255,.1)}.mini-progress{display:inline-block;width:80px;height:7px;background:#e8eef8;border-radius:7px;vertical-align:middle}.mini-progress i{display:block;height:7px;background:var(--primary);border-radius:7px}.detail-grid{display:grid;grid-template-columns:86px 1fr;gap:10px 12px;border:1px solid #edf2f7;border-radius:12px;padding:12px;margin:14px 0}.detail-grid span{color:#7a879e}.step-line{display:grid;grid-template-columns:18px 1fr 58px;gap:8px;align-items:center;border-bottom:1px solid #eef3fa;padding:10px 0}.step-line i{width:10px;height:10px;border-radius:50%;background:#94a3b8}.step-line i.success{background:#16bf78}.step-line i.failed{background:#f04438}.step-line i.running,.step-line i.queued{background:#0d6bff}.step-line small{display:block;color:#8a95a8;margin-top:3px}.mock-json{background:#0e1726;color:#dbeafe;border-radius:12px;padding:12px;overflow:auto;max-height:220px;font-size:12px;white-space:pre-wrap;word-break:break-word;overflow-wrap:anywhere}.artifact-list{display:flex;flex-direction:column;gap:10px;margin-top:8px}.artifact-item{padding:10px 12px;background:#fafbfc;border-radius:10px;border:1px solid #eaf0f8}.artifact-head{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:6px}.artifact-head .chip{display:inline-block;padding:2px 8px;border-radius:999px;background:#edf5ff;color:#0d6bff;font-size:11px}.artifact-title{font-size:13px;font-weight:600;color:#16213e}.artifact-node{font-size:11px;color:#9ca3af;margin-left:auto;font-family:ui-monospace,Menlo,Consolas,monospace}.artifact-text{background:#f3f5f7;border-radius:8px;padding:10px 12px;font-size:12px;line-height:1.6;margin:6px 0 0;color:#1f2937;font-family:ui-monospace,Menlo,Consolas,monospace;white-space:pre-wrap;word-break:break-word;overflow-wrap:anywhere;max-height:none}.timeline-line{border-left:3px solid #dbeafe;padding:8px 10px;margin:8px 0;background:#fbfdff;border-radius:8px}.timeline-line b{display:block}.timeline-line span{display:block;color:#667085;margin-top:3px}.timeline-line small{color:#98a2b3}.empty-mini{padding:22px;text-align:center;color:#98a2b3;border:1px dashed #dbe5f1;border-radius:12px;background:#fbfdff}@media (max-width:1200px){.workflow-task-layout{grid-template-columns:1fr}}
</style>
