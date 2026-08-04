<template>
  <div class="supply-audit-page">
    <ElCard shadow="never" class="filter-card">
      <div class="page-title-row">
        <div>
          <h2>供货审核工作台</h2>
          <p>审核供货商提交的货源商品，通过后商品会进入货源商城；驳回时请填写驳回原因，供货商将收到通知。</p>
        </div>
        <div class="toolbar-actions">
          <ElTag v-if="tabState === 'pending' && stats.pending != null" type="warning">待审核 {{ stats.pending }}</ElTag>
          <ElTag v-if="tabState === 'pending' && stats.approvedToday != null" type="success">今日通过 {{ stats.approvedToday }}</ElTag>
          <ElTag v-if="tabState === 'pending' && stats.rejectedToday != null" type="danger">今日驳回 {{ stats.rejectedToday }}</ElTag>
          <ElButton type="primary" :loading="loading" @click="load">刷新</ElButton>
        </div>
      </div>

      <div class="tab-row">
        <button
          v-for="tab in auditTabs"
          :key="tab.value"
          type="button"
          :class="['tab-btn', { active: tabState === tab.value }]"
          @click="switchTab(tab.value)"
        >
          {{ tab.label }}
        </button>
      </div>

      <ElForm :inline="true" :model="query" class="search-form">
        <ElFormItem label="模块">
          <ElSelect v-model="query.moduleKey" placeholder="全部模块" clearable style="width: 180px">
            <ElOption label="供货商品" value="supply_product" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem v-if="tabState === 'history'" label="状态">
          <ElSelect v-model="query.status" placeholder="全部状态" clearable style="width: 140px">
            <ElOption label="已通过" value="approved" />
            <ElOption label="已驳回" value="rejected" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem>
          <ElButton type="primary" @click="search">查询</ElButton>
          <ElButton @click="reset">重置</ElButton>
        </ElFormItem>
      </ElForm>
    </ElCard>

    <ElCard shadow="never" class="table-card">
      <AdminDataState
        v-if="listState === 'loading'"
        state="loading"
        title="正在加载审核记录"
        :retryable="false"
      />
      <AdminDataState
        v-else-if="listState === 'error'"
        state="error"
        title="审核记录暂时不可用"
        description="请求失败，请稍后重试。"
        @retry="load"
      />
      <AdminDataState
        v-else-if="listState === 'empty'"
        state="empty"
        :title="emptyTitle"
        :description="emptyDescription"
        :retryable="false"
      />
      <ElTable v-else :data="records" border stripe style="width: 100%">
        <template #empty><div class="empty-state">暂无审核记录</div></template>
        <ElTableColumn prop="id" label="审核ID" width="90" align="center" />
        <ElTableColumn label="模块" width="120" align="center">
          <template #default="{ row }">
            <ElTag :type="moduleTagType(row.module_key)" effect="light">
              {{ moduleLabel(row.module_key) }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="商品信息" min-width="260">
          <template #default="{ row }">
            <div class="product-cell">
              <div class="product-cover" :style="coverStyle(row as AuditRecord)"></div>
              <div class="product-info">
                <div class="product-title">{{ productTitle(row as AuditRecord) }}</div>
                <div class="product-meta">
                  <ElTag v-if="productType(row as AuditRecord)" :type="productTypeTagType(row as AuditRecord)" size="small" effect="plain">
                    {{ productType(row as AuditRecord) === 'text' ? '文本' : '卡密' }}
                  </ElTag>
                  <span v-if="productPrice(row as AuditRecord)" class="product-price">¥{{ productPrice(row as AuditRecord) }}</span>
                  <span class="product-id">#{{ row.business_id }}</span>
                </div>
              </div>
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn label="提交方" width="160">
          <template #default="{ row }">
            <div class="user-cell">
              <strong>{{ row.submitter_name || '-' }}</strong>
              <span>租户 #{{ row.tenant_id ?? '-' }} · 用户 #{{ row.submitter_id ?? '-' }}</span>
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn label="状态" width="110" align="center">
          <template #default="{ row }">
            <ElTag :type="statusTagType(row.status)" effect="dark">
              {{ statusLabel(row.status) }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="submitted_at" label="提交时间" width="170" />
        <ElTableColumn v-if="tabState === 'history'" prop="audited_at" label="审核时间" width="170" />
        <ElTableColumn v-if="tabState === 'history'" label="审核人" width="120">
          <template #default="{ row }">{{ row.auditor_name || '-' }}</template>
        </ElTableColumn>
        <ElTableColumn v-if="tabState === 'history'" label="驳回原因" min-width="200">
          <template #default="{ row }">
            <span v-if="row.reason" class="reason-text">{{ row.reason }}</span>
            <span v-else class="muted">-</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="220" align="center" fixed="right">
          <template #default="{ row }">
            <ElButton link type="primary" @click="openDetail(row as AuditRecord)">查看</ElButton>
            <template v-if="tabState === 'pending'">
              <ElButton link type="success" :loading="actingId === row.id" @click="handleApprove(row as AuditRecord)">通过</ElButton>
              <ElButton link type="danger" @click="openRejectDialog(row as AuditRecord)">驳回</ElButton>
            </template>
          </template>
        </ElTableColumn>
      </ElTable>

      <div v-if="listState === 'ready'" class="pagination-row">
        <span class="muted">共 {{ total }} 条记录</span>
        <ElPagination
          v-model:current-page="query.page"
          v-model:page-size="query.size"
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          @change="load"
        />
      </div>
    </ElCard>

    <ElDrawer v-model="detailVisible" title="审核详情" size="640px" :before-close="handleDetailClose">
      <AdminDataState
        v-if="detailState === 'loading'"
        state="loading"
        title="正在加载审核详情"
        :retryable="false"
        compact
      />
      <AdminDataState
        v-else-if="detailState === 'error'"
        state="error"
        title="审核详情暂时不可用"
        description="详情请求失败，请重试。"
        compact
        @retry="retryDetail"
      />
      <template v-else-if="currentDetail">
        <div class="detail-meta">
          <ElTag :type="moduleTagType(currentDetail.module_key)" effect="light">
            {{ moduleLabel(currentDetail.module_key) }}
          </ElTag>
          <ElTag :type="statusTagType(currentDetail.status)" effect="dark">
            {{ statusLabel(currentDetail.status) }}
          </ElTag>
          <span class="detail-id">#{{ currentDetail.id }}</span>
        </div>

        <h3 class="detail-title-text">{{ productTitle(currentDetail) }}</h3>

        <ElDescriptions :column="2" border size="small" class="detail-desc">
          <ElDescriptionsItem label="提交用户">{{ currentDetail.submitter_name || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="租户 ID">{{ currentDetail.tenant_id ?? '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="用户 ID">{{ currentDetail.submitter_id ?? '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="业务 ID">{{ currentDetail.business_id ?? '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="提交时间">{{ currentDetail.submitted_at || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="审核时间">{{ currentDetail.audited_at || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="审核人">{{ currentDetail.auditor_name || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="审核状态">{{ statusLabel(currentDetail.status) }}</ElDescriptionsItem>
        </ElDescriptions>

        <div v-if="snapshotPreview" class="detail-block">
          <div class="detail-block-label">提交快照</div>
          <pre class="snapshot-text">{{ snapshotPreview }}</pre>
        </div>

        <div v-if="currentDetail.reason" class="detail-block">
          <div class="detail-block-label">审核理由</div>
          <div class="reason-block" :class="{ 'reason-block-reject': currentDetail.status === 'rejected' }">
            {{ currentDetail.reason }}
          </div>
        </div>

        <div v-if="currentDetail.status === 'pending'" class="detail-actions">
          <ElButton type="success" :loading="actingId === currentDetail.id" @click="handleApprove(currentDetail)">
            通过审核
          </ElButton>
          <ElButton type="danger" @click="openRejectDialog(currentDetail)">驳回审核</ElButton>
        </div>
      </template>
    </ElDrawer>

    <ElDialog v-model="rejectDialogVisible" title="驳回审核" width="540px" destroy-on-close>
      <div v-if="rejectTarget" class="reject-context">
        <div class="reject-title">{{ productTitle(rejectTarget) }}</div>
        <div class="reject-meta">审核 #{{ rejectTarget.id }} · {{ moduleLabel(rejectTarget.module_key) }}</div>
      </div>
      <ElInput
        v-model="rejectReason"
        type="textarea"
        :rows="5"
        placeholder="请填写驳回原因，供货商会看到此说明（不少于 5 个字）"
        maxlength="500"
        show-word-limit
      />
      <div class="reject-tip">提示：驳回后供货商可在「我的货源」中查看原因并修改后重新提交。</div>
      <template #footer>
        <ElButton @click="rejectDialogVisible = false">取消</ElButton>
        <ElButton type="danger" :loading="rejecting" @click="submitReject">确认驳回</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getPendingAuditList,
  approveAudit,
  rejectAudit,
  getAuditHistory
} from '@/api/supply'

defineOptions({ name: 'AdminSupplyAuditPage' })

type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

interface AuditRecord {
  id: number
  tenant_id?: number
  module_key: string
  business_id: number
  submitter_id?: number
  submitter_name?: string
  status: 'pending' | 'approved' | 'rejected'
  snapshot_json?: string
  submitted_at?: string
  audited_at?: string
  auditor_id?: number
  auditor_name?: string
  reason?: string
  productInfo?: {
    title?: string
    cover_url?: string
    price_cent?: number
    product_type?: string
    seller_id?: number
  } & Record<string, unknown>
  [key: string]: unknown
}

const tabState = ref<'pending' | 'history'>('pending')
const loading = ref(false)
const listState = ref<'loading' | 'ready' | 'empty' | 'error'>('loading')
const records = ref<AuditRecord[]>([])
const total = ref(0)
const query = reactive({
  moduleKey: '',
  status: '',
  page: 1,
  size: 20
})

const detailVisible = ref(false)
const detailState = ref<'idle' | 'loading' | 'ready' | 'error'>('idle')
const detailTarget = ref<AuditRecord | null>(null)
const currentDetail = ref<AuditRecord | null>(null)

const rejectDialogVisible = ref(false)
const rejectTarget = ref<AuditRecord | null>(null)
const rejectReason = ref('')
const rejecting = ref(false)

const actingId = ref<number | null>(null)

const stats = reactive({
  pending: null as number | null,
  approvedToday: null as number | null,
  rejectedToday: null as number | null
})

const auditTabs = [
  { value: 'pending' as const, label: '待审核' },
  { value: 'history' as const, label: '审核历史' }
]

const emptyTitle = computed(() =>
  tabState.value === 'pending' ? '暂无待审核记录' : '暂无审核历史记录'
)
const emptyDescription = computed(() =>
  tabState.value === 'pending'
    ? '当前没有等待审核的供货商品。'
    : '当前筛选条件下没有审核历史记录。'
)

function moduleLabel(moduleKey: string): string {
  if (moduleKey === 'supply_product') return '供货商品'
  return moduleKey || '未知模块'
}

function moduleTagType(moduleKey: string): TagType {
  if (moduleKey === 'supply_product') return 'primary'
  return 'info'
}

function statusLabel(status: string): string {
  if (status === 'pending') return '待审核'
  if (status === 'approved') return '已通过'
  if (status === 'rejected') return '已驳回'
  return '未知'
}

function statusTagType(status: string): TagType {
  if (status === 'pending') return 'warning'
  if (status === 'approved') return 'success'
  if (status === 'rejected') return 'danger'
  return 'info'
}

function productTitle(row: AuditRecord): string {
  return row.productInfo?.title || (row.snapshot_json ? parseTitleFromSnapshot(row.snapshot_json) : '') || `商品 #${row.business_id}`
}

function productType(row: AuditRecord): string {
  return row.productInfo?.product_type || ''
}

function productTypeTagType(row: AuditRecord): TagType {
  const t = productType(row)
  if (t === 'text') return 'primary'
  if (t === 'card') return 'warning'
  return 'info'
}

function productPrice(row: AuditRecord): string {
  const cents = Number(row.productInfo?.price_cent ?? 0)
  if (!Number.isFinite(cents) || cents <= 0) return ''
  return (cents / 100).toFixed(2)
}

function parseTitleFromSnapshot(snapshotJson: string): string {
  try {
    const obj = JSON.parse(snapshotJson)
    if (typeof obj === 'object' && obj && typeof obj.title === 'string') return obj.title
  } catch {
    /* ignore */
  }
  return ''
}

function coverStyle(row: AuditRecord) {
  const url = (row.productInfo?.cover_url as string) || ''
  if (url) return { backgroundImage: `url(${url})`, backgroundSize: 'cover', backgroundPosition: 'center' }
  return { background: 'linear-gradient(135deg, #e2e8f0, #cbd5e1)' }
}

const snapshotPreview = computed(() => {
  const detail = currentDetail.value
  if (!detail?.snapshot_json) return ''
  try {
    const obj = JSON.parse(detail.snapshot_json)
    return JSON.stringify(obj, null, 2)
  } catch {
    return detail.snapshot_json
  }
})

onMounted(load)

async function load() {
  loading.value = true
  listState.value = 'loading'
  try {
    const params: { page: number; size: number; moduleKey?: string; status?: string } = {
      page: query.page,
      size: query.size
    }
    if (query.moduleKey) params.moduleKey = query.moduleKey
    if (tabState.value === 'history' && query.status) params.status = query.status

    const data = tabState.value === 'pending' ? await getPendingAuditList(params) : await getAuditHistory(params)
    const payload = (data ?? {}) as Record<string, unknown>
    const list = (Array.isArray(payload.list) ? payload.list : Array.isArray(payload.records) ? payload.records : []) as AuditRecord[]
    records.value = list
    total.value = Number(payload.total ?? 0)
    listState.value = list.length > 0 ? 'ready' : 'empty'
    void refreshStats()
  } catch (err: any) {
    records.value = []
    total.value = 0
    listState.value = 'error'
    ElMessage.error(err?.message || '审核记录加载失败')
  } finally {
    loading.value = false
  }
}

async function refreshStats() {
  stats.pending = null
  stats.approvedToday = null
  stats.rejectedToday = null
  try {
    const pendingData = await getPendingAuditList({ page: 1, size: 1 })
    stats.pending = Number((pendingData as any)?.total ?? 0)
  } catch {
    /* ignore */
  }
  try {
    const approvedData = await getAuditHistory({ page: 1, size: 1, status: 'approved' })
    stats.approvedToday = Number((approvedData as any)?.total ?? 0)
  } catch {
    /* ignore */
  }
  try {
    const rejectedData = await getAuditHistory({ page: 1, size: 1, status: 'rejected' })
    stats.rejectedToday = Number((rejectedData as any)?.total ?? 0)
  } catch {
    /* ignore */
  }
}

function switchTab(value: 'pending' | 'history') {
  if (tabState.value === value) return
  tabState.value = value
  query.page = 1
  query.status = ''
  load()
}

function search() {
  query.page = 1
  load()
}

function reset() {
  query.moduleKey = ''
  query.status = ''
  query.page = 1
  load()
}

async function openDetail(row: AuditRecord) {
  detailVisible.value = true
  detailState.value = 'loading'
  detailTarget.value = row
  currentDetail.value = null
  try {
    // 当前后端 pendingList/history 已包含 productInfo，直接使用行数据；如未来需要独立详情接口可在此扩展
    currentDetail.value = row
    detailState.value = 'ready'
  } catch {
    detailState.value = 'error'
  }
}

function retryDetail() {
  if (detailTarget.value) void openDetail(detailTarget.value)
}

function handleDetailClose(done: () => void) {
  currentDetail.value = null
  detailState.value = 'idle'
  detailTarget.value = null
  done()
}

async function handleApprove(row: AuditRecord) {
  try {
    await ElMessageBox.confirm(
      `确认通过审核 #${row.id}「${productTitle(row)}」？通过后商品将进入货源商城。`,
      '确认通过',
      { type: 'success' }
    )
  } catch {
    return
  }
  actingId.value = row.id
  try {
    await approveAudit(row.id, '')
    ElMessage.success('已通过审核')
    if (detailVisible.value && currentDetail.value?.id === row.id) {
      detailVisible.value = false
      currentDetail.value = null
    }
    await load()
  } catch (err: any) {
    ElMessage.error(err?.message || '审核通过失败')
  } finally {
    actingId.value = null
  }
}

function openRejectDialog(row: AuditRecord) {
  rejectTarget.value = row
  rejectReason.value = ''
  rejectDialogVisible.value = true
}

async function submitReject() {
  if (!rejectTarget.value) return
  const reason = rejectReason.value.trim()
  if (reason.length < 5) {
    ElMessage.warning('请填写不少于 5 个字的驳回原因')
    return
  }
  rejecting.value = true
  try {
    await rejectAudit(rejectTarget.value.id, reason)
    ElMessage.success('已驳回审核')
    rejectDialogVisible.value = false
    if (detailVisible.value && currentDetail.value?.id === rejectTarget.value.id) {
      detailVisible.value = false
      currentDetail.value = null
    }
    await load()
  } catch (err: any) {
    ElMessage.error(err?.message || '驳回失败')
  } finally {
    rejecting.value = false
  }
}
</script>

<style scoped>
.supply-audit-page { padding: 16px; }
.filter-card { margin-bottom: 16px; }
.page-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
  flex-wrap: wrap;
}
.page-title-row h2 { margin: 0 0 6px; font-size: 20px; }
.page-title-row p { margin: 0; color: var(--el-text-color-secondary); max-width: 760px; }
.toolbar-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }

.tab-row {
  display: flex;
  gap: 6px;
  margin-bottom: 14px;
}
.tab-btn {
  padding: 6px 18px;
  border-radius: 8px;
  border: 1px solid var(--el-border-color);
  background: var(--el-bg-color);
  color: var(--el-text-color-secondary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all .15s;
}
.tab-btn:hover {
  border-color: var(--el-color-primary-light-5);
  color: var(--el-color-primary);
}
.tab-btn.active {
  background: var(--el-color-primary);
  border-color: var(--el-color-primary);
  color: #fff;
}

.search-form { row-gap: 8px; }
.table-card { min-height: 420px; }
.pagination-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 16px;
}
.muted { color: var(--el-text-color-secondary); font-size: 13px; }
.empty-state {
  padding: 40px 0;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.product-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}
.product-cover {
  width: 44px;
  height: 44px;
  border-radius: 8px;
  flex-shrink: 0;
  background-color: #e2e8f0;
}
.product-info { min-width: 0; }
.product-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 240px;
}
.product-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.product-price {
  font-size: 13px;
  font-weight: 700;
  color: #ff3b30;
}
.product-id {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

.user-cell { display: grid; gap: 2px; }
.user-cell strong { color: var(--el-text-color-primary); font-size: 13px; }
.user-cell span { color: var(--el-text-color-secondary); font-size: 12px; }

.reason-text {
  color: var(--el-text-color-regular);
  font-size: 13px;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.detail-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.detail-id { color: var(--el-text-color-secondary); font-size: 12px; }
.detail-title-text {
  margin: 0 0 16px;
  font-size: 18px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  line-height: 1.5;
}
.detail-desc { margin-bottom: 18px; }
.detail-block { margin-top: 16px; }
.detail-block-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 8px;
}
.snapshot-text {
  padding: 12px 14px;
  background: #f7f9fc;
  border-radius: 10px;
  border: 1px solid #e7edf5;
  font-size: 12px;
  color: #2c3e50;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 280px;
  overflow: auto;
  margin: 0;
}
.reason-block {
  padding: 12px 14px;
  background: #f7f9fc;
  border-radius: 10px;
  border: 1px solid #e7edf5;
  font-size: 13px;
  line-height: 1.6;
  color: var(--el-text-color-regular);
  white-space: pre-wrap;
  word-break: break-word;
}
.reason-block-reject {
  background: #fef2f2;
  border-color: #fecaca;
  color: #b91c1c;
}
.detail-actions {
  display: flex;
  gap: 10px;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--el-border-color);
}

.reject-context {
  margin-bottom: 14px;
  padding: 12px 14px;
  background: #f7f9fc;
  border-radius: 10px;
  border-left: 3px solid var(--el-color-danger);
}
.reject-title {
  font-weight: 700;
  font-size: 14px;
  margin-bottom: 4px;
  color: var(--el-text-color-primary);
}
.reject-meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.reject-tip {
  margin-top: 10px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

@media (max-width: 1100px) {
  .page-title-row {
    flex-direction: column;
    align-items: stretch;
  }
  .toolbar-actions {
    flex-wrap: wrap;
  }
}
</style>
