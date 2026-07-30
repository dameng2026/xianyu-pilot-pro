<template>
  <div class="growth-withdrawals-page">
    <!-- 顶部标题 -->
    <ElCard shadow="never" class="toolbar-card">
      <div class="page-title-row">
        <div>
          <h2>提现审批</h2>
          <p>审批用户的提现申请。通过后金额从冻结余额中扣除，驳回后金额退回可用余额。</p>
        </div>
        <div class="actions">
          <ElButton :loading="loading" @click="loadList">刷新</ElButton>
        </div>
      </div>
    </ElCard>

    <!-- 提现申请列表 -->
    <ElCard shadow="never" class="section-card">
      <template #header>
        <div class="table-header">
          <span>提现申请列表</span>
          <div class="actions small">
            <ElSelect
              v-model="query.status"
              placeholder="状态"
              clearable
              style="width: 140px"
              @change="onSearch"
            >
              <ElOption label="全部" value="" />
              <ElOption label="待审批" value="pending" />
              <ElOption label="已通过" value="approved" />
              <ElOption label="已驳回" value="rejected" />
            </ElSelect>
            <ElButton @click="onSearch">查询</ElButton>
          </div>
        </div>
      </template>
      <AdminDataState v-if="listState === 'loading'" state="loading" title="正在读取提现申请" compact />
      <AdminDataState
        v-else-if="listState === 'error'"
        state="error"
        title="提现申请列表暂不可用"
        :description="listError"
        retry-text="重新加载"
        compact
        @retry="loadList"
      />
      <template v-else>
        <ElTable :data="list.records" border stripe height="540">
          <template #empty><div class="empty-state">暂无提现申请</div></template>
          <ElTableColumn prop="id" label="ID" width="70" />
          <ElTableColumn label="用户" min-width="140">
            <template #default="scope">
              <div class="user-cell">
                <span class="user-name">{{ scope.row.nickname || scope.row.username || `用户${scope.row.userId}` }}</span>
                <small class="muted">#{{ scope.row.userId }}</small>
              </div>
            </template>
          </ElTableColumn>
          <ElTableColumn label="提现金额" width="120">
            <template #default="scope">
              <b class="text-warning">¥{{ formatAmount(scope.row.amount) }}</b>
            </template>
          </ElTableColumn>
          <ElTableColumn label="收款方式" width="120">
            <template #default="scope">
              <ElTag :type="paymentMethodTagType(scope.row.paymentMethod)" size="small">
                {{ scope.row.paymentMethodText || paymentMethodText(scope.row.paymentMethod) }}
              </ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn label="收款账号" min-width="180" show-overflow-tooltip>
            <template #default="scope">
              <div class="account-cell">
                <div><b>{{ scope.row.paymentAccount }}</b></div>
                <div v-if="scope.row.paymentName" class="muted">收款人：{{ scope.row.paymentName }}</div>
              </div>
            </template>
          </ElTableColumn>
          <ElTableColumn label="状态" width="100">
            <template #default="scope">
              <ElTag :type="statusTagType(scope.row.status)" size="small">{{ scope.row.statusText || statusText(scope.row.status) }}</ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="createdTime" label="申请时间" width="160" />
          <ElTableColumn prop="reviewedTime" label="审批时间" width="160">
            <template #default="scope">{{ scope.row.reviewedTime || '—' }}</template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="180" fixed="right">
            <template #default="scope">
              <template v-if="scope.row.status === 'pending'">
                <ElButton link type="success" size="small" :loading="approving === scope.row.id" @click="onApprove(scope.row)">通过</ElButton>
                <ElButton link type="danger" size="small" @click="openReject(scope.row)">驳回</ElButton>
              </template>
              <template v-else>
                <ElButton link size="small" @click="viewDetail(scope.row)">详情</ElButton>
              </template>
            </template>
          </ElTableColumn>
        </ElTable>
        <div class="pagination-row">
          <span class="muted">共 {{ list.total }} 条</span>
          <ElPagination
            v-model:current-page="query.page"
            v-model:page-size="query.size"
            layout="total, sizes, prev, pager, next, jumper"
            :total="list.total"
            :page-sizes="[10, 20, 50, 100]"
            @change="loadList"
          />
        </div>
      </template>
    </ElCard>

    <!-- 驳回对话框 -->
    <ElDialog v-model="rejectDialogVisible" title="驳回提现申请" width="480px">
      <ElForm :model="rejectForm" label-width="100px">
        <ElFormItem label="提现金额">
          <b class="text-warning">¥{{ formatAmount(currentRow?.amount) }}</b>
        </ElFormItem>
        <ElFormItem label="收款信息">
          <div>
            <div>{{ currentRow?.paymentMethodText || paymentMethodText(currentRow?.paymentMethod) }}：{{ currentRow?.paymentAccount }}</div>
            <div v-if="currentRow?.paymentName" class="muted">收款人：{{ currentRow?.paymentName }}</div>
          </div>
        </ElFormItem>
        <ElFormItem label="驳回原因" required>
          <ElInput
            v-model="rejectForm.reason"
            type="textarea"
            :rows="3"
            placeholder="请填写驳回原因，将展示给用户"
          />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="rejectDialogVisible = false">取消</ElButton>
        <ElButton type="danger" :loading="rejecting" :disabled="!rejectForm.reason?.trim()" @click="onReject">确认驳回</ElButton>
      </template>
    </ElDialog>

    <!-- 详情对话框 -->
    <ElDialog v-model="detailDialogVisible" title="提现详情" width="480px">
      <div v-if="currentRow" class="detail-list">
        <div class="detail-item">
          <span>提现金额</span>
          <b class="text-warning">¥{{ formatAmount(currentRow.amount) }}</b>
        </div>
        <div class="detail-item">
          <span>收款方式</span>
          <b>{{ currentRow.paymentMethodText || paymentMethodText(currentRow.paymentMethod) }}</b>
        </div>
        <div class="detail-item">
          <span>收款账号</span>
          <b>{{ currentRow.paymentAccount }}</b>
        </div>
        <div class="detail-item">
          <span>收款人</span>
          <b>{{ currentRow.paymentName || '—' }}</b>
        </div>
        <div class="detail-item">
          <span>状态</span>
          <ElTag :type="statusTagType(currentRow.status)" size="small">{{ currentRow.statusText || statusText(currentRow.status) }}</ElTag>
        </div>
        <div class="detail-item">
          <span>申请时间</span>
          <b>{{ currentRow.createdTime || '—' }}</b>
        </div>
        <div class="detail-item">
          <span>审批时间</span>
          <b>{{ currentRow.reviewedTime || '—' }}</b>
        </div>
        <div class="detail-item">
          <span>审批人</span>
          <b>{{ currentRow.reviewer || '—' }}</b>
        </div>
        <div v-if="currentRow.rejectReason" class="detail-item">
          <span>驳回原因</span>
          <b class="text-danger">{{ currentRow.rejectReason }}</b>
        </div>
      </div>
      <template #footer>
        <ElButton type="primary" @click="detailDialogVisible = false">关闭</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<script setup lang="ts">
  import { onMounted, reactive, ref } from 'vue'
  import { ElMessage, ElMessageBox } from 'element-plus'
  import {
    approveGrowthWithdrawal,
    getGrowthWithdrawalsPage,
    rejectGrowthWithdrawal,
    type GrowthWithdrawalRow
  } from '@/api/growth'
  import AdminDataState from '@/components/business/admin-data-state/index.vue'

  defineOptions({ name: 'AdminGrowthWithdrawalsPage' })

  const loading = ref(false)
  const approving = ref<number | null>(null)
  const rejecting = ref(false)
  const listState = ref<'loading' | 'ready' | 'error'>('loading')
  const listError = ref('')
  const list = reactive<any>({ records: [], total: 0 })
  const query = reactive<any>({
    status: '',
    page: 1,
    size: 20
  })

  const rejectDialogVisible = ref(false)
  const detailDialogVisible = ref(false)
  const currentRow = ref<GrowthWithdrawalRow | null>(null)
  const rejectForm = reactive({ reason: '' })

  function formatAmount(cent: any): string {
    const n = Number(cent)
    if (!Number.isFinite(n)) return '0.00'
    return (n / 100).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  }

  function paymentMethodText(method?: string): string {
    switch (method) {
      case 'wechat_qr': return '微信收款码'
      case 'alipay_qr': return '支付宝收款码'
      case 'alipay_account': return '支付宝账号'
      case 'bank_card': return '银行卡'
      default: return method || '—'
    }
  }

  function paymentMethodTagType(method?: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' {
    switch (method) {
      case 'wechat_qr': return 'success'
      case 'alipay_qr':
      case 'alipay_account': return 'warning'
      case 'bank_card': return 'info'
      default: return 'primary'
    }
  }

  function statusText(status?: string): string {
    switch (status) {
      case 'pending': return '待审批'
      case 'approved': return '已通过'
      case 'rejected': return '已驳回'
      default: return status || '—'
    }
  }

  function statusTagType(status?: string) {
    switch (status) {
      case 'pending': return 'warning'
      case 'approved': return 'success'
      case 'rejected': return 'danger'
      default: return 'info'
    }
  }

  async function loadList() {
    listState.value = 'loading'
    listError.value = ''
    loading.value = true
    try {
      const payload = {
        status: query.status || undefined,
        page: query.page,
        size: query.size
      }
      const res = await getGrowthWithdrawalsPage(payload)
      list.records = res.records
      list.total = res.total
      listState.value = 'ready'
    } catch (e: any) {
      listError.value = e?.message || '未知错误'
      listState.value = 'error'
    } finally {
      loading.value = false
    }
  }

  function onSearch() {
    query.page = 1
    loadList()
  }

  async function onApprove(row: unknown) {
    const r = row as GrowthWithdrawalRow
    try {
      await ElMessageBox.confirm(
        `确认通过用户 ${r.nickname || r.username || r.userId} 的提现申请 ¥${formatAmount(r.amount)}？`,
        '审批确认',
        { confirmButtonText: '确认通过', cancelButtonText: '取消', type: 'warning' }
      )
    } catch {
      return
    }
    approving.value = r.id
    try {
      await approveGrowthWithdrawal(r.id)
      ElMessage.success('已通过')
      await loadList()
    } catch (e: any) {
      ElMessage.error('审批失败：' + (e?.message || '未知错误'))
    } finally {
      approving.value = null
    }
  }

  function openReject(row: unknown) {
    const r = row as GrowthWithdrawalRow
    currentRow.value = r
    rejectForm.reason = ''
    rejectDialogVisible.value = true
  }

  async function onReject() {
    if (!currentRow.value) return
    if (!rejectForm.reason?.trim()) {
      ElMessage.warning('请填写驳回原因')
      return
    }
    rejecting.value = true
    try {
      await rejectGrowthWithdrawal(currentRow.value.id, rejectForm.reason.trim())
      ElMessage.success('已驳回')
      rejectDialogVisible.value = false
      await loadList()
    } catch (e: any) {
      ElMessage.error('驳回失败：' + (e?.message || '未知错误'))
    } finally {
      rejecting.value = false
    }
  }

  function viewDetail(row: unknown) {
    currentRow.value = row as GrowthWithdrawalRow
    detailDialogVisible.value = true
  }

  onMounted(() => {
    loadList()
  })
</script>

<style scoped lang="scss">
  .growth-withdrawals-page {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .toolbar-card {
    :deep(.el-card__body) {
      padding: 16px 20px;
    }
  }

  .page-title-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;

    h2 {
      margin: 0 0 4px;
      font-size: 18px;
      font-weight: 600;
    }
    p {
      margin: 0;
      font-size: 13px;
      color: #6b7280;
    }
    .actions {
      display: flex;
      gap: 8px;
    }
  }

  .table-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .actions.small {
      display: flex;
      gap: 8px;
      align-items: center;
    }
  }

  .user-cell {
    display: flex;
    flex-direction: column;
    .user-name {
      font-size: 13px;
    }
  }

  .account-cell {
    display: flex;
    flex-direction: column;
  }

  .text-warning {
    color: #f59e0b;
  }
  .text-success {
    color: #10b981;
  }
  .text-danger {
    color: #ef4444;
  }
  .muted {
    color: #9ca3af;
    font-size: 12px;
  }

  .pagination-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 12px;
  }

  .empty-state {
    text-align: center;
    color: #9ca3af;
    padding: 24px;
  }

  .detail-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .detail-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    border-radius: 8px;
    background: #f9fafb;

    span {
      font-size: 13px;
      color: #6b7280;
    }
    b {
      font-size: 14px;
    }
  }
</style>
