<template>
  <div class="promotion-page">
    <!-- 顶部标题区 -->
    <ElCard shadow="never" class="toolbar-card">
      <div class="page-title-row">
        <div>
          <h2>会员充值活动</h2>
          <p>
            通过活动优惠价、购买人数限制、活动通知文案等方式增强会员套餐的促销氛围。活动开启后，前台会员套餐页面会同时展示原价、活动价、名额、活动时间等信息。所有价格与名额判断均由服务端实时校验，前台不会绕过活动限制。
          </p>
        </div>
        <div class="actions">
          <ElButton type="primary" :disabled="listState !== 'ready'" @click="openCreate">新建活动</ElButton>
          <ElButton :loading="loading" @click="loadList">刷新</ElButton>
        </div>
      </div>
    </ElCard>

    <!-- 说明条 -->
    <ElAlert type="warning" :closable="false" class="tip-alert" show-icon>
      <template #title>
        <span>
          <b>规则要点</b>：① 活动价格不得高于套餐原价，套餐原价变更时会自动校验；② 同一套餐同一周期不能同时参与时间重叠的多个活动；③ 名额采用「创建订单预占 + 支付成功确认 + 超时/取消释放」机制，防止超卖；④ 已支付订单的活动价以快照为准，活动配置变更不影响历史订单。
        </span>
      </template>
    </ElAlert>

    <!-- 活动列表 -->
    <ElCard shadow="never" class="section-card">
      <template #header>
        <div class="table-header">
          <span>活动列表</span>
          <div class="actions small">
            <ElInput
              v-model="query.keyword"
              placeholder="活动名称 / 编码"
              clearable
              style="width: 220px"
              @keyup.enter="onSearch"
              @clear="onSearch"
            />
            <ElSelect v-model="query.status" clearable placeholder="状态" style="width: 140px" @change="onSearch">
              <ElOption label="草稿" value="draft" />
              <ElOption label="未开始" value="pending" />
              <ElOption label="进行中" value="ongoing" />
              <ElOption label="已结束" value="ended" />
              <ElOption label="已关闭" value="closed" />
              <ElOption label="名额已满" value="quota_full" />
            </ElSelect>
            <ElButton @click="onSearch">查询</ElButton>
          </div>
        </div>
      </template>

      <AdminDataState v-if="listState === 'loading'" state="loading" title="正在读取活动列表" compact />
      <AdminDataState
        v-else-if="listState === 'error'"
        state="error"
        title="活动列表暂不可用"
        :description="listError"
        retry-text="重新加载"
        compact
        @retry="loadList"
      />
      <template v-else>
        <ElTable :data="list.records" border stripe>
          <template #empty><div class="empty-state">暂无活动，点击「新建活动」创建</div></template>
          <ElTableColumn prop="id" label="ID" width="70" />
          <ElTableColumn label="活动名称" min-width="180">
            <template #default="{ row }">
              <div class="activity-name-cell">
                <span class="activity-name">{{ row.activityName }}</span>
                <span v-if="row.activityCode" class="muted small-text">{{ row.activityCode }}</span>
              </div>
            </template>
          </ElTableColumn>
          <ElTableColumn label="状态" width="110">
            <template #default="{ row }">
              <ElTag :type="statusTagType(row.effectiveStatus)" size="small">
                {{ statusText(row.effectiveStatus) }}
              </ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn label="活动时间" width="280">
            <template #default="{ row }">
              <div class="time-cell">
                <span>{{ formatDateTime(row.startTime) }}</span>
                <span class="muted">至</span>
                <span>{{ row.isLongTerm ? '长期' : formatDateTime(row.endTime) }}</span>
              </div>
            </template>
          </ElTableColumn>
          <ElTableColumn label="套餐数" width="80" align="center">
            <template #default="{ row }">{{ row.planCount || 0 }}</template>
          </ElTableColumn>
          <ElTableColumn label="已售 / 名额" width="140" align="center">
            <template #default="{ row }">
              <div>
                <span class="num-text">{{ row.soldCount || 0 }}</span>
                <span class="muted"> / </span>
                <span>{{ row.totalQuota > 0 ? row.totalQuota : '不限量' }}</span>
              </div>
              <div class="muted small-text">预占 {{ row.preoccupiedCount || 0 }}</div>
            </template>
          </ElTableColumn>
          <ElTableColumn label="创建人" width="120">
            <template #default="{ row }">
              <span v-if="row.createdByName">{{ row.createdByName }}</span>
              <span v-else class="muted">—</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="创建时间" width="160">
            <template #default="{ row }">{{ formatDateTime(row.createdTime) }}</template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="280" fixed="right">
            <template #default="{ row }">
              <ElButton link type="primary" size="small" @click="openStats(row)">统计</ElButton>
              <ElButton
                v-if="canStart(row.effectiveStatus)"
                link type="success" size="small"
                @click="onStart(row)"
              >开启</ElButton>
              <ElButton
                v-if="canClose(row.effectiveStatus)"
                link type="warning" size="small"
                @click="onClose(row)"
              >关闭</ElButton>
              <ElButton
                v-if="canReopen(row.effectiveStatus)"
                link type="success" size="small"
                @click="onReopen(row)"
              >重开</ElButton>
              <ElButton
                v-if="canEdit(row.effectiveStatus)"
                link type="primary" size="small"
                @click="openEdit(row)"
              >编辑</ElButton>
              <ElButton
                v-if="canDelete(row.effectiveStatus)"
                link type="danger" size="small"
                @click="onDelete(row)"
              >删除</ElButton>
            </template>
          </ElTableColumn>
        </ElTable>
        <div class="pagination-row">
          <span class="muted">共 {{ list.total }} 条</span>
          <ElPagination
            v-model:current-page="query.current"
            v-model:page-size="query.size"
            layout="total, sizes, prev, pager, next, jumper"
            :total="list.total"
            :page-sizes="[10, 20, 50, 100]"
            @change="loadList"
          />
        </div>
      </template>
    </ElCard>

    <!-- 新建/编辑对话框 -->
    <ActivityFormDialog
      v-model="formDialogVisible"
      :detail="formDialogDetail"
      @saved="onFormSaved"
    />

    <!-- 统计/订单对话框 -->
    <ActivityStatsDialog
      v-model="statsDialogVisible"
      :activity="statsDialogActivity"
    />
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import AdminDataState from '@/components/business/admin-data-state/index.vue'
import ActivityFormDialog from './ActivityFormDialog.vue'
import ActivityStatsDialog from './ActivityStatsDialog.vue'
import {
  closePromotionActivity,
  deletePromotionActivity,
  fetchPromotionActivityDetail,
  fetchPromotionActivitiesPage,
  reopenPromotionActivity,
  startPromotionActivity
} from '@/api/promotion'

defineOptions({ name: 'AdminPromotionPage' })

type ListState = 'loading' | 'ready' | 'error'

const loading = ref(false)
const listState = ref<ListState>('loading')
const listError = ref('')
const list = reactive<any>({ records: [], total: 0 })
const query = reactive<any>({ current: 1, size: 20, keyword: '', status: '' })

const formDialogVisible = ref(false)
const formDialogDetail = ref<Record<string, any> | null>(null)

const statsDialogVisible = ref(false)
const statsDialogActivity = ref<Record<string, any> | null>(null)

async function loadList() {
  loading.value = true
  listState.value = 'loading'
  listError.value = ''
  try {
    const params: any = { current: query.current, size: query.size }
    if (query.keyword) params.keyword = query.keyword
    if (query.status) params.status = query.status
    const data = await fetchPromotionActivitiesPage(params)
    if (!data || !Array.isArray(data.records)) throw new Error('活动接口返回格式异常')
    Object.assign(list, data)
    listState.value = 'ready'
  } catch (error: any) {
    listError.value = error?.message || '活动列表读取失败，请检查服务状态后重试。'
    listState.value = 'error'
  } finally {
    loading.value = false
  }
}

function onSearch() {
  query.current = 1
  loadList()
}

function openCreate() {
  formDialogDetail.value = null
  formDialogVisible.value = true
}

async function openEdit(row: any) {
  if (!row?.id) return
  try {
    const detail = await fetchPromotionActivityDetail(row.id)
    formDialogDetail.value = detail
    formDialogVisible.value = true
  } catch (error: any) {
    ElMessage.error(error?.message || '活动详情读取失败')
  }
}

function openStats(row: any) {
  if (!row?.id) return
  statsDialogActivity.value = row
  statsDialogVisible.value = true
}

function onFormSaved() {
  loadList()
}

function statusText(status: string): string {
  switch (status) {
    case 'draft': return '草稿'
    case 'pending': return '未开始'
    case 'ongoing': return '进行中'
    case 'ended': return '已结束'
    case 'closed': return '已关闭'
    case 'quota_full': return '名额已满'
    case 'deleted': return '已删除'
    default: return status || '—'
  }
}

function statusTagType(status: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' {
  switch (status) {
    case 'ongoing': return 'success'
    case 'pending': return 'warning'
    case 'ended':
    case 'closed': return 'info'
    case 'quota_full': return 'danger'
    default: return 'primary'
  }
}

function canStart(status: string): boolean {
  return status === 'draft'
}

function canClose(status: string): boolean {
  return status === 'ongoing' || status === 'pending' || status === 'quota_full'
}

function canReopen(status: string): boolean {
  return status === 'ended' || status === 'closed'
}

function canEdit(status: string): boolean {
  return status === 'draft' || status === 'closed' || status === 'ended'
}

function canDelete(status: string): boolean {
  return status === 'draft' || status === 'closed'
}

function formatDateTime(v: any): string {
  if (!v) return '—'
  const s = String(v).replace('T', ' ')
  return s.length > 19 ? s.substring(0, 19) : s
}

async function onStart(row: any) {
  try {
    await ElMessageBox.confirm(
      `确认开启活动「${row.activityName}」？开启后前台将展示活动价格与名额信息。`,
      '开启活动',
      { type: 'warning', confirmButtonText: '确认开启', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await startPromotionActivity(row.id)
    await loadList()
  } catch (error: any) {
    ElMessage.error(error?.message || '活动开启失败')
  }
}

async function onClose(row: any) {
  try {
    await ElMessageBox.confirm(
      `确认关闭活动「${row.activityName}」？\n\n关闭后：\n• 前台立即恢复套餐正常价格\n• 已支付订单和已发放会员权益不受影响\n• 待支付订单需在订单超时后自动关闭并释放预占名额`,
      '关闭活动',
      { type: 'warning', confirmButtonText: '确认关闭', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await closePromotionActivity(row.id)
    await loadList()
  } catch (error: any) {
    ElMessage.error(error?.message || '活动关闭失败')
  }
}

async function onReopen(row: any) {
  try {
    await ElMessageBox.confirm(
      `确认重新开启活动「${row.activityName}」？如活动时间已过，请先编辑活动时间。`,
      '重新开启',
      { type: 'warning', confirmButtonText: '确认重开', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await reopenPromotionActivity(row.id)
    await loadList()
  } catch (error: any) {
    ElMessage.error(error?.message || '活动重新开启失败')
  }
}

async function onDelete(row: any) {
  try {
    await ElMessageBox.confirm(
      `确认删除活动「${row.activityName}」？\n\n仅草稿或已关闭且无订单的活动可删除。`,
      '删除活动',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await deletePromotionActivity(row.id)
    await loadList()
  } catch (error: any) {
    ElMessage.error(error?.message || '活动删除失败')
  }
}

loadList()
</script>

<style scoped lang="scss">
.promotion-page {
  display: grid;
  gap: 18px;
}

.toolbar-card {
  border-radius: 18px;
}

.page-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.page-title-row h2 {
  margin: 0;
  font-size: 24px;
}

.page-title-row p {
  margin: 8px 0 0;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
  max-width: 760px;
  font-size: 13px;
}

.actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.actions.small {
  flex-wrap: nowrap;
}

.tip-alert {
  border-radius: 14px;
}

.tip-alert b {
  color: var(--el-color-warning);
}

.section-card {
  border-radius: 18px;
}

.table-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.empty-state {
  padding: 40px 0;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.activity-name-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.activity-name {
  font-weight: 600;
}

.time-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.num-text {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  color: var(--el-color-danger);
}

.muted {
  color: var(--el-text-color-secondary);
}

.small-text {
  font-size: 11px;
}

.pagination-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 16px;
  flex-wrap: wrap;
}

@media (max-width: 1100px) {
  .page-title-row {
    flex-direction: column;
    align-items: stretch;
  }
  .actions {
    justify-content: flex-start;
  }
}
</style>
