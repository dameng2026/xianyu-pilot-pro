<template>
  <CardPanel title="记录" desc="API滑块求解记录与 Token 消费记录">
    <div class="tabs">
      <button :class="['tab', { active: activeTab === 'solve' }]" @click="activeTab = 'solve'">API滑块求解记录</button>
      <button :class="['tab', { active: activeTab === 'token' }]" @click="activeTab = 'token'">Token消费记录</button>
    </div>

    <!-- 筛选 -->
    <div class="toolbar" v-if="activeTab === 'solve'">
      <select v-model="filters.status" @change="search">
        <option value="">全部状态</option>
        <option value="success">成功</option>
        <option value="fail">失败</option>
        <option value="timeout">超时</option>
        <option value="precheck_rejected">预检验拒绝</option>
      </select>
      <input v-model="filters.keyword" placeholder="搜索任务号/失败原因" @keyup.enter="search" />
      <button class="btn-primary" @click="search">查询</button>
      <button class="btn-secondary" @click="reset">重置</button>
    </div>

    <!-- 求解记录表 -->
    <div v-if="activeTab === 'solve'">
      <BaseTable :columns="solveCols" :rows="rows" @row-click="showDetail">
        <template #status="{ row }">
          <Badge :type="statusBadge(row.status)">{{ statusText(row.status) }}</Badge>
        </template>
        <template #duration_ms="{ row }">
          {{ row.duration_ms ? row.duration_ms + 'ms' : '—' }}
        </template>
        <template #token_charged="{ row }">
          {{ row.token_charged }}
        </template>
        <template #empty>
          <div class="table-empty">暂无求解记录</div>
        </template>
      </BaseTable>
      <Pagination :current="current" :total="total" :page-size="size" @page-change="goPage" />
    </div>

    <!-- Token 消费记录表（复用同一数据源，按 tokenCharged > 0 过滤） -->
    <div v-else>
      <BaseTable :columns="tokenCols" :rows="tokenRows">
        <template #status="{ row }">
          <Badge :type="statusBadge(row.status)">{{ statusText(row.status) }}</Badge>
        </template>
        <template #empty>
          <div class="table-empty">暂无消费记录</div>
        </template>
      </BaseTable>
      <Pagination :current="current" :total="tokenTotal" :page-size="size" @page-change="goPage" />
    </div>

    <!-- 详情抽屉 -->
    <div v-if="detail" class="detail-drawer" @click.self="detail = null">
      <div class="detail-panel">
        <div class="detail-header">
          <h3>求解记录详情</h3>
          <button @click="detail = null">×</button>
        </div>
        <div class="detail-body">
          <div class="detail-row"><span>记录编号</span><b>{{ detail.request_id }}</b></div>
          <div class="detail-row"><span>状态</span><Badge :type="statusBadge(detail.status)">{{ statusText(detail.status) }}</Badge></div>
          <div class="detail-row"><span>失败原因</span><b>{{ detail.failure_reason || '—' }}</b></div>
          <div class="detail-row"><span>错误详情</span><pre>{{ detail.error_message || '无' }}</pre></div>
          <div class="detail-row"><span>耗时</span><b>{{ detail.duration_ms ? detail.duration_ms + 'ms' : '—' }}</b></div>
          <div class="detail-row"><span>调用 IP</span><b>{{ detail.client_ip || '—' }}</b></div>
          <div class="detail-row"><span>Token 消耗</span><b>{{ detail.token_charged }}</b></div>
          <div class="detail-row"><span>创建时间</span><b>{{ detail.created_at }}</b></div>
        </div>
      </div>
    </div>
  </CardPanel>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import CardPanel from '../CardPanel.vue'
import BaseTable from '../BaseTable.vue'
import Badge from '../Badge.vue'
import Pagination from '../Pagination.vue'
import { getApiRecords } from '../../api/apiSliderSolve.js'

const activeTab = ref('solve')
const loading = ref(false)
const rows = ref([])
const total = ref(0)
const current = ref(1)
const size = ref(20)
const detail = ref(null)
const filters = reactive({ status: '', keyword: '' })

const solveCols = [
  { key: 'request_id', title: '记录编号' },
  { key: 'status', title: '状态' },
  { key: 'failure_reason', title: '失败原因' },
  { key: 'duration_ms', title: '耗时' },
  { key: 'client_ip', title: '调用IP' },
  { key: 'token_charged', title: 'Token消耗' },
  { key: 'created_at', title: '创建时间' },
]

const tokenCols = [
  { key: 'request_id', title: '消费记录编号' },
  { key: 'token_charged', title: 'Token变化值' },
  { key: 'status', title: '消费状态' },
  { key: 'created_at', title: '创建时间' },
]

const tokenRows = computed(() => rows.value.filter(r => r.token_charged > 0))
const tokenTotal = computed(() => tokenRows.value.length)

async function load() {
  loading.value = true
  try {
    const params = { page: current.value, pageSize: size.value }
    if (filters.status) params.status = filters.status
    if (filters.keyword) params.keyword = filters.keyword
    const res = await getApiRecords(params)
    const payload = res?.data || {}
    rows.value = payload.list || payload.records || []
    total.value = Number(payload.total) || 0
  } catch (e) {
    console.error('load records failed', e)
  } finally {
    loading.value = false
  }
}

function search() { current.value = 1; load() }
function reset() { filters.status = ''; filters.keyword = ''; current.value = 1; load() }
function goPage(p) { current.value = p; load() }
function showDetail(row) { detail.value = row }

function statusBadge(status) {
  const map = { success: 'green', fail: 'red', timeout: 'gray', precheck_rejected: 'orange', retrying: 'blue', queued: 'blue' }
  return map[status] || 'gray'
}
function statusText(status) {
  const map = { success: '成功', fail: '失败', timeout: '超时', precheck_rejected: '预检验拒绝', retrying: '处理中', queued: '处理中' }
  return map[status] || status
}

onMounted(load)
</script>

<style scoped>
.tabs { display: flex; gap: 4px; margin-bottom: 16px; border-bottom: 1px solid var(--line); }
.tab { padding: 8px 16px; border: none; background: transparent; cursor: pointer; font-size: 14px; color: var(--muted); border-bottom: 2px solid transparent; }
.tab.active { color: var(--primary); border-bottom-color: var(--primary); }
.toolbar { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.toolbar select, .toolbar input { height: 32px; padding: 0 8px; border: 1px solid var(--line); border-radius: 6px; font-size: 13px; }
.btn-primary { background: var(--primary); color: #fff; border: none; border-radius: 6px; padding: 0 12px; height: 32px; cursor: pointer; font-size: 13px; }
.btn-secondary { background: #fff; color: var(--text); border: 1px solid var(--line); border-radius: 6px; padding: 0 12px; height: 32px; cursor: pointer; font-size: 13px; }
.table-empty { text-align: center; padding: 24px 0; color: var(--muted); font-size: 13px; }
.detail-drawer { position: fixed; top: 0; right: 0; bottom: 0; left: 0; background: rgba(0,0,0,0.4); z-index: 100; display: flex; justify-content: flex-end; }
.detail-panel { width: 480px; background: #fff; height: 100%; overflow-y: auto; }
.detail-header { display: flex; justify-content: space-between; align-items: center; padding: 16px; border-bottom: 1px solid var(--line); }
.detail-header h3 { margin: 0; font-size: 16px; }
.detail-header button { border: none; background: transparent; font-size: 20px; cursor: pointer; }
.detail-body { padding: 16px; }
.detail-row { display: flex; padding: 8px 0; border-bottom: 1px solid var(--line); font-size: 13px; }
.detail-row span { width: 100px; color: var(--muted); }
.detail-row b { color: var(--text); }
.detail-row pre { background: #f5f8ff; padding: 8px; border-radius: 4px; font-size: 12px; white-space: pre-wrap; word-break: break-all; max-height: 200px; overflow-y: auto; }
</style>
