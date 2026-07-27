<template>
  <ElDialog
    v-model="visible"
    :title="`活动统计：${activity?.activityName || ''}`"
    width="1100px"
    top="4vh"
    :close-on-click-modal="false"
  >
    <div v-if="loading" class="loading-state">
      <ElIcon class="is-loading"><Loading /></ElIcon>
      <span style="margin-left: 8px">正在加载统计数据...</span>
    </div>
    <template v-else-if="stats">
      <!-- 顶部指标 -->
      <div class="metrics-grid">
        <ElCard shadow="never">
          <div class="metric-label">活动订单数</div>
          <div class="metric-value">{{ stats.totalOrders || 0 }}</div>
          <div class="metric-sub">支付成功 {{ stats.paidOrders || 0 }} / 待支付 {{ stats.pendingOrders || 0 }} / 已关闭 {{ stats.closedOrders || 0 }}</div>
        </ElCard>
        <ElCard shadow="never">
          <div class="metric-label">活动销售额</div>
          <div class="metric-value price-text">¥{{ stats.totalRevenueYuan || '0.00' }}</div>
          <div class="metric-sub">仅统计支付成功订单</div>
        </ElCard>
        <ElCard shadow="never">
          <div class="metric-label">优惠总金额</div>
          <div class="metric-value discount-text">¥{{ stats.totalDiscountYuan || '0.00' }}</div>
          <div class="metric-sub">原价 - 活动价</div>
        </ElCard>
        <ElCard shadow="never">
          <div class="metric-label">参与用户数</div>
          <div class="metric-value">{{ stats.paidUserCount || 0 }}</div>
          <div class="metric-sub">去重支付成功用户</div>
        </ElCard>
        <ElCard shadow="never">
          <div class="metric-label">转化率</div>
          <div class="metric-value">{{ stats.conversionRate || '0%' }}</div>
          <div class="metric-sub">支付成功 / 总订单</div>
        </ElCard>
        <ElCard shadow="never">
          <div class="metric-label">活动状态</div>
          <div class="metric-value">
            <ElTag :type="statusTagType(stats.effectiveStatus)" size="small">
              {{ statusText(stats.effectiveStatus) }}
            </ElTag>
          </div>
          <div class="metric-sub">服务端实时计算</div>
        </ElCard>
      </div>

      <!-- 套餐明细 -->
      <ElCard shadow="never" class="section-card">
        <template #header>
          <div class="card-header">
            <span>套餐销售明细</span>
            <ElButton link type="primary" size="small" @click="loadStats">刷新</ElButton>
          </div>
        </template>
        <ElTable :data="stats.planStats || []" border stripe size="small">
          <template #empty><div class="empty-state">暂无套餐销售数据</div></template>
          <ElTableColumn prop="planName" label="套餐" min-width="140" show-overflow-tooltip />
          <ElTableColumn label="计费周期" width="80">
            <template #default="{ row }">{{ periodText(row.periodType) }}</template>
          </ElTableColumn>
          <ElTableColumn label="原价" width="100">
            <template #default="{ row }">
              <span class="muted">¥{{ row.originalPriceYuan }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="活动价" width="100">
            <template #default="{ row }">
              <span class="price-text">¥{{ row.activityPriceYuan }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="已售 / 名额" width="140">
            <template #default="{ row }">
              <span :class="{ 'quota-warning': isQuotaWarning(row) }">{{ row.quotaText }}</span>
              <div class="muted small-text">预占 {{ row.preoccupiedCount }} 份</div>
            </template>
          </ElTableColumn>
          <ElTableColumn label="剩余" width="100">
            <template #default="{ row }">
              <ElProgress
                v-if="row.quota > 0"
                :percentage="quotaPercentage(row)"
                :status="quotaStatus(row)"
                :show-text="false"
                :stroke-width="6"
              />
              <div class="muted small-text">{{ row.remainText }}</div>
            </template>
          </ElTableColumn>
          <ElTableColumn label="活动收入" width="110">
            <template #default="{ row }">
              <span class="price-text">¥{{ row.revenueYuan || '0.00' }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <ElButton link type="primary" size="small" @click="openAdjustQuota(row)">调整名额</ElButton>
            </template>
          </ElTableColumn>
        </ElTable>
        <div class="stat-note">
          <b>统计口径说明</b>：已售份数 = 活动有效期内、使用活动价格且支付成功的订单数；待支付、已取消、超时关闭订单不计入；订单退款后如会员权益仍有效，则不释放名额。
        </div>
      </ElCard>

      <!-- 订单列表 -->
      <ElCard shadow="never" class="section-card">
        <template #header>
          <div class="card-header">
            <span>活动订单明细</span>
            <div class="actions">
              <ElSelect v-model="orderQuery.status" clearable placeholder="订单状态" size="small" style="width: 120px" @change="loadOrders">
                <ElOption label="待支付" value="0" />
                <ElOption label="已支付" value="1" />
                <ElOption label="已关闭" value="2" />
                <ElOption label="支付失败" value="3" />
                <ElOption label="已退款" value="4" />
              </ElSelect>
              <ElButton link type="primary" size="small" @click="loadOrders">刷新</ElButton>
            </div>
          </div>
        </template>
        <ElTable :data="orders.records" border stripe size="small">
          <template #empty><div class="empty-state">暂无活动订单</div></template>
          <ElTableColumn prop="orderNo" label="订单号" min-width="180" show-overflow-tooltip />
          <ElTableColumn prop="username" label="用户" width="120" show-overflow-tooltip />
          <ElTableColumn prop="title" label="商品标题" min-width="160" show-overflow-tooltip />
          <ElTableColumn label="原价" width="90">
            <template #default="{ row }">
              <span class="muted">¥{{ row.originalPriceYuan || row.amountYuan }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="活动价" width="90">
            <template #default="{ row }">
              <span class="price-text">¥{{ row.activityPriceYuan || row.amountYuan }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="优惠" width="80">
            <template #default="{ row }">
              <span class="discount-text">-¥{{ row.discountYuan || '0.00' }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="实付" width="90">
            <template #default="{ row }">
              <span class="price-text">¥{{ row.amountYuan }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="状态" width="90">
            <template #default="{ row }">
              <ElTag :type="orderStatusTagType(row.status)" size="small">{{ row.statusText }}</ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="paidTime" label="支付时间" width="160" />
          <ElTableColumn prop="createdTime" label="下单时间" width="160" />
        </ElTable>
        <div class="pagination-row">
          <span class="muted">共 {{ orders.total }} 条</span>
          <ElPagination
            v-model:current-page="orderQuery.current"
            v-model:page-size="orderQuery.size"
            layout="total, prev, pager, next"
            :total="orders.total"
            :page-sizes="[10, 20, 50]"
            @change="loadOrders"
          />
        </div>
      </ElCard>
    </template>

    <!-- 调整名额对话框 -->
    <ElDialog
      v-model="adjustVisible"
      title="调整活动名额"
      width="420px"
      append-to-body
    >
      <div v-if="adjustRow" class="adjust-form">
        <div class="adjust-row">
          <span class="label">套餐：</span>
          <span>{{ adjustRow.planName }}（{{ periodText(adjustRow.periodType) }}）</span>
        </div>
        <div class="adjust-row">
          <span class="label">当前名额：</span>
          <span>{{ adjustRow.quota > 0 ? adjustRow.quota + ' 份' : '不限量' }}</span>
        </div>
        <div class="adjust-row">
          <span class="label">已售 + 预占：</span>
          <span>{{ (Number(adjustRow.soldCount) || 0) + (Number(adjustRow.preoccupiedCount) || 0) }} 份</span>
        </div>
        <div class="adjust-row">
          <span class="label">新名额：</span>
          <ElInputNumber
            v-model="adjustQuota"
            :min="0"
            :step="10"
            controls-position="right"
            style="width: 200px"
          />
          <span class="muted small-text" style="margin-left: 8px">0=不限量</span>
        </div>
        <div class="adjust-row">
          <span class="label">备注：</span>
          <ElInput
            v-model="adjustRemark"
            type="textarea"
            :rows="2"
            placeholder="调整原因（可选，会记录到审计日志）"
            maxlength="200"
            show-word-limit
            style="width: 280px"
          />
        </div>
      </div>
      <template #footer>
        <ElButton @click="adjustVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="adjusting" @click="onAdjust">确认调整</ElButton>
      </template>
    </ElDialog>
  </ElDialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import {
  adjustPromotionPlanQuota,
  fetchPromotionActivityOrders,
  fetchPromotionActivityStats
} from '@/api/promotion'

defineOptions({ name: 'ActivityStatsDialog' })

const props = defineProps<{
  modelValue: boolean
  activity: Record<string, any> | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: v => emit('update:modelValue', v)
})

const loading = ref(false)
const stats = ref<any>(null)
const orders = reactive<any>({ records: [], total: 0 })
const orderQuery = reactive<any>({ current: 1, size: 20, status: '' })

const adjustVisible = ref(false)
const adjustRow = ref<any>(null)
const adjustQuota = ref(0)
const adjustRemark = ref('')
const adjusting = ref(false)

async function loadStats() {
  if (!props.activity?.id) return
  loading.value = true
  try {
    stats.value = await fetchPromotionActivityStats(props.activity.id)
  } catch (error: any) {
    ElMessage.error(error?.message || '活动统计加载失败')
    stats.value = null
  } finally {
    loading.value = false
  }
}

async function loadOrders() {
  if (!props.activity?.id) return
  try {
    const data = await fetchPromotionActivityOrders(props.activity.id, {
      current: orderQuery.current,
      size: orderQuery.size,
      status: orderQuery.status || undefined
    })
    Object.assign(orders, data)
  } catch (error: any) {
    ElMessage.error(error?.message || '活动订单加载失败')
  }
}

async function loadData() {
  await Promise.all([loadStats(), loadOrders()])
}

function periodText(periodType: string): string {
  return periodType === 'quarter' ? '季' : periodType === 'year' ? '年' : '月'
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
    default: return status
  }
}

function statusTagType(status: string): '' | 'success' | 'warning' | 'info' | 'danger' {
  switch (status) {
    case 'ongoing': return 'success'
    case 'pending': return 'warning'
    case 'ended':
    case 'closed': return 'info'
    case 'quota_full': return 'danger'
    default: return ''
  }
}

function orderStatusTagType(status: number): '' | 'success' | 'warning' | 'info' | 'danger' {
  switch (status) {
    case 1: return 'success'
    case 0: return 'warning'
    case 2: return 'info'
    case 3: return 'danger'
    case 4: return 'danger'
    default: return ''
  }
}

function isQuotaWarning(row: any): boolean {
  const quota = Number(row.quota) || 0
  if (quota <= 0) return false
  const sold = Number(row.soldCount) || 0
  const preoccupied = Number(row.preoccupiedCount) || 0
  return sold + preoccupied >= quota * 0.8
}

function quotaPercentage(row: any): number {
  const quota = Number(row.quota) || 0
  if (quota <= 0) return 0
  const sold = Number(row.soldCount) || 0
  const preoccupied = Number(row.preoccupiedCount) || 0
  return Math.min(100, Math.round(((sold + preoccupied) / quota) * 100))
}

function quotaStatus(row: any): '' | 'success' | 'warning' | 'exception' {
  const pct = quotaPercentage(row)
  if (pct >= 100) return 'exception'
  if (pct >= 80) return 'warning'
  return 'success'
}

function openAdjustQuota(row: any) {
  adjustRow.value = row
  adjustQuota.value = Number(row.quota) || 0
  adjustRemark.value = ''
  adjustVisible.value = true
}

async function onAdjust() {
  if (!adjustRow.value || !props.activity?.id) return
  const activityPlanId = adjustRow.value.activityPlanId
  const newQuota = adjustQuota.value
  const oldQuota = Number(adjustRow.value.quota) || 0
  if (newQuota < 0) {
    ElMessage.warning('名额不能为负数')
    return
  }
  // 二次确认
  try {
    await ElMessageBox.confirm(
      `确认将套餐「${adjustRow.value.planName}」的活动名额从 ${oldQuota > 0 ? oldQuota + ' 份' : '不限量'} 调整为 ${newQuota > 0 ? newQuota + ' 份' : '不限量'}？`,
      '调整名额确认',
      { type: 'warning', confirmButtonText: '确认调整', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  adjusting.value = true
  try {
    await adjustPromotionPlanQuota(props.activity.id, activityPlanId, newQuota, adjustRemark)
    adjustVisible.value = false
    await loadStats()
    await loadOrders()
  } catch (error: any) {
    ElMessage.error(error?.message || '名额调整失败')
  } finally {
    adjusting.value = false
  }
}

watch(
  () => props.modelValue,
  v => {
    if (v && props.activity?.id) {
      orderQuery.current = 1
      orderQuery.status = ''
      loadData()
    } else {
      stats.value = null
      orders.records = []
      orders.total = 0
    }
  }
)
</script>

<style scoped lang="scss">
.loading-state {
  padding: 60px 0;
  text-align: center;
  color: var(--el-text-color-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.metrics-grid .el-card {
  border-radius: 12px;
}

.metric-label {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.metric-value {
  font-size: 20px;
  font-weight: 600;
  margin-top: 4px;
  color: var(--el-text-color-primary);
}

.metric-sub {
  color: var(--el-text-color-secondary);
  font-size: 11px;
  margin-top: 4px;
  line-height: 1.4;
}

.price-text {
  color: var(--el-color-danger);
  font-weight: 600;
}

.discount-text {
  color: var(--el-color-success);
  font-weight: 600;
}

.muted {
  color: var(--el-text-color-secondary);
}

.small-text {
  font-size: 11px;
}

.section-card {
  border-radius: 14px;
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.empty-state {
  padding: 24px 0;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.stat-note {
  margin-top: 12px;
  padding: 10px 12px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
}

.stat-note b {
  color: var(--el-text-color-primary);
}

.quota-warning {
  color: var(--el-color-warning);
  font-weight: 600;
}

.pagination-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.adjust-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.adjust-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.adjust-row .label {
  width: 90px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  flex-shrink: 0;
  padding-top: 6px;
}

@media (max-width: 1100px) {
  .metrics-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .metrics-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
