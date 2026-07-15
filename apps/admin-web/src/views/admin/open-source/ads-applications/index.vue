<template>
  <div class="admin-page">
    <ElCard shadow="never" class="filter-card">
      <div class="page-title-row">
        <div>
          <h2>开源版广告申请审核</h2>
          <p>处理来自开源版的轮播广告与文字广告申请，查看支付、素材、联系人与自动上架结果。</p>
        </div>
        <div class="toolbar-actions">
          <ElButton :loading="loading" @click="loadList">刷新</ElButton>
        </div>
      </div>

      <div v-if="listState === 'ready' || listState === 'empty'" class="summary-grid">
        <div class="summary-card">
          <strong>{{ page.total }}</strong>
          <span>申请总数</span>
        </div>
        <div class="summary-card">
          <strong>{{ pendingReviewCount }}</strong>
          <span>待审核</span>
        </div>
        <div class="summary-card">
          <strong>{{ pendingPaymentCount }}</strong>
          <span>待支付</span>
        </div>
        <div class="summary-card">
          <strong>{{ onlineCount }}</strong>
          <span>投放中</span>
        </div>
      </div>

      <div class="filter-row">
        <ElInput
          v-model="query.keyword"
          placeholder="搜索申请编号 / 标题 / 联系人"
          clearable
          style="width: 280px"
          @keyup.enter="search"
        />
        <ElSelect
          v-model="query.positionType"
          placeholder="全部广告位"
          clearable
          style="width: 180px"
          @change="search"
        >
          <ElOption label="首页轮播广告" value="home_carousel" />
          <ElOption label="首页文字广告" value="sidebar_text" />
        </ElSelect>
        <ElSelect
          v-model="query.status"
          placeholder="全部状态"
          clearable
          style="width: 180px"
          @change="search"
        >
          <ElOption v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </ElSelect>
        <ElButton type="primary" @click="search">查询</ElButton>
        <ElButton @click="reset">重置</ElButton>
      </div>
    </ElCard>

    <ElCard shadow="never" class="table-card">
      <AdminDataState
        v-if="listState === 'loading'"
        state="loading"
        title="正在加载广告申请"
        :retryable="false"
      />
      <AdminDataState
        v-else-if="listState === 'error'"
        state="error"
        title="广告申请暂时不可用"
        description="请求失败，不能将当前状态解释为没有申请。"
        @retry="loadList"
      />
      <AdminDataState
        v-else-if="listState === 'empty'"
        state="empty"
        title="暂无广告申请"
        description="查询已成功完成，当前筛选条件下没有记录。"
        :retryable="false"
      />
      <ElTable v-else :data="page.records" stripe style="width: 100%">
        <OpenSourceAdApplicationTableColumn label="申请信息" min-width="260">
          <template #default="{ row }">
            <div class="title-cell">
              <img v-if="row.creativeImageUrl" :src="row.creativeImageUrl" alt="" class="creative-thumb" />
              <div class="title-copy">
                <strong>{{ row.title || row.planTitle || '-' }}</strong>
                <span>{{ row.applicationNo || `#${row.id}` }}</span>
              </div>
            </div>
          </template>
        </OpenSourceAdApplicationTableColumn>

        <OpenSourceAdApplicationTableColumn label="广告位 / 套餐" min-width="220">
          <template #default="{ row }">
            <div class="stack-cell">
              <strong>{{ row.positionLabel || positionLabel(row.positionType) }}</strong>
              <span>{{ row.planTitle || row.planCode || '-' }}</span>
            </div>
          </template>
        </OpenSourceAdApplicationTableColumn>

        <OpenSourceAdApplicationTableColumn label="联系人" min-width="220">
          <template #default="{ row }">
            <div class="stack-cell">
              <strong>{{ row.contactValue || row.contact || row.contactName || '-' }}</strong>
              <span>{{ row.landingUrl || '-' }}</span>
            </div>
          </template>
        </OpenSourceAdApplicationTableColumn>

        <OpenSourceAdApplicationTableColumn label="支付状态" width="180" align="center">
          <template #default="{ row }">
            <div class="stack-cell center">
              <ElTag :type="paymentTagType(row.paymentStatus)">{{ row.paymentStatusLabel || '-' }}</ElTag>
              <span>{{ row.paymentAmountYuan ? `￥${row.paymentAmountYuan}` : '-' }}</span>
            </div>
          </template>
        </OpenSourceAdApplicationTableColumn>

        <OpenSourceAdApplicationTableColumn label="申请状态" width="140" align="center">
          <template #default="{ row }">
            <ElTag :type="statusTagType(row.status)">{{ row.statusLabel || statusLabel(row.status) }}</ElTag>
          </template>
        </OpenSourceAdApplicationTableColumn>

        <OpenSourceAdApplicationTableColumn label="更新时间" width="180" align="center" prop="updatedTime" />

        <OpenSourceAdApplicationTableColumn label="操作" width="220" align="center" fixed="right">
          <template #default="{ row }">
            <ElButton size="small" type="primary" link @click="openDetail(row.id)">详情</ElButton>
            <ElButton size="small" type="success" link @click="openReview(row)">处理</ElButton>
          </template>
        </OpenSourceAdApplicationTableColumn>
      </ElTable>

      <div v-if="listState === 'ready'" class="pagination-wrap">
        <ElPagination
          v-model:current-page="query.current"
          v-model:page-size="query.size"
          layout="total, sizes, prev, pager, next, jumper"
          :total="page.total"
          @change="loadList"
        />
      </div>
    </ElCard>

    <ElDrawer v-model="detailVisible" title="申请详情" size="760px">
      <AdminDataState
        v-if="detailState === 'loading'"
        state="loading"
        title="正在加载申请详情"
        :retryable="false"
        compact
      />
      <AdminDataState
        v-else-if="detailState === 'error'"
        state="error"
        title="申请详情暂时不可用"
        description="详情请求失败，请重试。"
        compact
        @retry="retryDetail"
      />
      <template v-else-if="currentDetail">
        <div v-if="currentDetail.creativeImageUrl" class="detail-cover">
          <img :src="currentDetail.creativeImageUrl" alt="创意图" />
        </div>

        <ElDescriptions :column="1" border>
          <ElDescriptionsItem label="申请编号">{{ currentDetail.applicationNo || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="站点">{{ currentDetail.siteName || currentDetail.siteCode || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="广告位">{{ currentDetail.positionLabel || positionLabel(currentDetail.positionType) }}</ElDescriptionsItem>
          <ElDescriptionsItem label="套餐">{{ currentDetail.planTitle || currentDetail.planCode || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="广告标题">{{ currentDetail.title || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="跳转链接">{{ currentDetail.landingUrl || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="联系人">{{ currentDetail.contactValue || currentDetail.contact || currentDetail.contactName || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="支付订单号">{{ currentDetail.paymentOrderNo || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="支付状态">
            <ElTag :type="paymentTagType(currentDetail.paymentStatus)">{{ currentDetail.paymentStatusLabel || '-' }}</ElTag>
          </ElDescriptionsItem>
          <ElDescriptionsItem label="支付金额">{{ currentDetail.paymentAmountYuan ? `￥${currentDetail.paymentAmountYuan}` : '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="支付方式">{{ paymentMethodLabel(currentDetail.paymentMethod) }}</ElDescriptionsItem>
          <ElDescriptionsItem label="当前状态">
            <ElTag :type="statusTagType(currentDetail.status)">{{ currentDetail.statusLabel || statusLabel(currentDetail.status) }}</ElTag>
          </ElDescriptionsItem>
          <ElDescriptionsItem label="处理说明">{{ currentDetail.statusMessage || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="上架记录">
            {{ currentDetail.publishedRecordType || '-' }} / {{ currentDetail.publishedRecordId || '-' }}
          </ElDescriptionsItem>
          <ElDescriptionsItem label="处理人">{{ currentDetail.reviewerUsername || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="处理时间">{{ currentDetail.reviewedTime || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="创建时间">{{ currentDetail.createdTime || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="更新时间">{{ currentDetail.updatedTime || '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="补充备注">{{ currentDetail.remark || '-' }}</ElDescriptionsItem>
        </ElDescriptions>
      </template>
      <div v-else class="drawer-state">暂无详情</div>
    </ElDrawer>

    <ElDialog v-model="reviewVisible" title="处理广告申请" width="620px" destroy-on-close>
      <ElForm ref="reviewFormRef" :model="reviewForm" :rules="reviewRules" label-width="100px" label-position="right">
        <ElFormItem label="处理状态" prop="status">
          <ElSelect v-model="reviewForm.status">
            <ElOption v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
        </ElFormItem>
        <ElAlert
          v-if="reviewForm.status === 'approved' || reviewForm.status === 'online'"
          type="warning"
          :closable="false"
          title="只有支付成功的申请才能通过或上架，若未支付后端会自动拦截。"
        />
        <ElFormItem label="处理说明" prop="statusMessage">
          <ElInput
            v-model="reviewForm.statusMessage"
            type="textarea"
            :rows="5"
            maxlength="255"
            show-word-limit
            placeholder="填写审核意见、上架说明或拒绝原因"
          />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="reviewVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="reviewSaving" @click="submitReview">保存处理结果</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElTableColumn } from 'element-plus'
import type { FormInstance, FormRules, TagProps } from 'element-plus'
import {
  getOpenSourceAdApplicationDetail,
  getOpenSourceAdApplications,
  updateOpenSourceAdApplicationStatus,
  type OpenSourceAdApplicationItem,
  type OpenSourceAdApplicationPage,
  type OpenSourceAdApplicationQuery,
  type OpenSourceAdApplicationStatus,
  type OpenSourceAdPositionType,
} from '@/api/open-source-ads'

defineOptions({ name: 'AdminOpenSourceAdApplicationsPage' })

const OpenSourceAdApplicationTableColumn: typeof ElTableColumn<OpenSourceAdApplicationItem> = ElTableColumn

const loading = ref(false)
const listState = ref<'loading' | 'ready' | 'empty' | 'error'>('loading')
const detailState = ref<'idle' | 'loading' | 'ready' | 'error'>('idle')
const detailTargetId = ref<number | null>(null)
const detailVisible = ref(false)
const reviewVisible = ref(false)
const reviewSaving = ref(false)
const currentDetail = ref<OpenSourceAdApplicationItem | null>(null)
const reviewTargetId = ref<number | null>(null)
const reviewFormRef = ref<FormInstance>()

const page = reactive<OpenSourceAdApplicationPage>({
  records: [],
  current: 1,
  size: 20,
  total: 0,
})

const query = reactive<OpenSourceAdApplicationQuery>({
  current: 1,
  size: 20,
  keyword: '',
  status: '',
  positionType: '',
})

const reviewForm = reactive<{
  status: OpenSourceAdApplicationStatus
  statusMessage: string
}>({
  status: 'pending',
  statusMessage: '',
})

const statusOptions: Array<{ label: string; value: OpenSourceAdApplicationStatus }> = [
  { label: '待支付', value: 'pending_payment' },
  { label: '待审核', value: 'pending' },
  { label: '已通过', value: 'approved' },
  { label: '已拒绝', value: 'rejected' },
  { label: '投放中', value: 'online' },
  { label: '已下线', value: 'offline' },
]

const reviewRules: FormRules = {
  status: [{ required: true, message: '请选择处理状态', trigger: 'change' }],
  statusMessage: [{ required: true, message: '请输入处理说明', trigger: 'blur' }],
}

const pendingReviewCount = computed(() =>
  page.records.filter(item => item.status === 'pending').length
)
const pendingPaymentCount = computed(() =>
  page.records.filter(item => item.status === 'pending_payment').length
)
const onlineCount = computed(() =>
  page.records.filter(item => item.status === 'online').length
)

function positionLabel(positionType: OpenSourceAdPositionType) {
  return positionType === 'home_carousel' ? '首页轮播广告' : '首页文字广告'
}

function statusLabel(status: OpenSourceAdApplicationStatus) {
  switch (status) {
    case 'pending_payment':
      return '待支付'
    case 'approved':
      return '已通过'
    case 'rejected':
      return '已拒绝'
    case 'online':
      return '投放中'
    case 'offline':
      return '已下线'
    default:
      return '待审核'
  }
}

function statusTagType(status: OpenSourceAdApplicationStatus): TagProps['type'] {
  switch (status) {
    case 'approved':
      return 'success'
    case 'online':
      return 'primary'
    case 'rejected':
      return 'danger'
    case 'offline':
      return 'info'
    case 'pending_payment':
      return 'warning'
    default:
      return 'warning'
  }
}

function paymentTagType(status?: string): TagProps['type'] {
  switch (String(status || '').toLowerCase()) {
    case 'paid':
      return 'success'
    case 'closed':
    case 'expired':
      return 'info'
    case 'failed':
      return 'danger'
    default:
      return 'warning'
  }
}

function paymentMethodLabel(method?: string) {
  const value = String(method || '').toLowerCase()
  if (value === 'alipay') return '支付宝'
  if (value === 'wechat') return '微信支付'
  return '-'
}

async function loadList() {
  loading.value = true
  listState.value = 'loading'
  try {
    const res = await getOpenSourceAdApplications({ ...query })
    page.records = res.records
    page.current = Number(res.current ?? query.current ?? 1)
    page.size = Number(res.size ?? query.size ?? 20)
    page.total = res.total
    listState.value = page.records.length > 0 ? 'ready' : 'empty'
  } catch {
    page.records = []
    page.total = 0
    listState.value = 'error'
  } finally {
    loading.value = false
  }
}

function search() {
  query.current = 1
  loadList()
}

function reset() {
  query.keyword = ''
  query.status = ''
  query.positionType = ''
  query.current = 1
  query.size = 20
  loadList()
}

async function openDetail(id: number) {
  detailVisible.value = true
  detailState.value = 'loading'
  detailTargetId.value = id
  currentDetail.value = null
  try {
    currentDetail.value = await getOpenSourceAdApplicationDetail(id)
    detailState.value = 'ready'
  } catch {
    detailState.value = 'error'
  }
}

function retryDetail() {
  if (detailTargetId.value) void openDetail(detailTargetId.value)
}

function openReview(row: OpenSourceAdApplicationItem) {
  reviewTargetId.value = row.id
  reviewForm.status = row.status || 'pending'
  reviewForm.statusMessage = row.statusMessage || ''
  reviewVisible.value = true
}

async function submitReview() {
  const valid = await reviewFormRef.value?.validate().catch(() => false)
  if (!valid || !reviewTargetId.value) return
  reviewSaving.value = true
  try {
    await updateOpenSourceAdApplicationStatus(
      reviewTargetId.value,
      reviewForm.status,
      reviewForm.statusMessage.trim()
    )
    ElMessage.success('处理结果已保存')
    reviewVisible.value = false
    await loadList()
    if (detailVisible.value && currentDetail.value?.id === reviewTargetId.value) {
      currentDetail.value = await getOpenSourceAdApplicationDetail(reviewTargetId.value)
    }
  } catch (error: any) {
    ElMessage.error(error?.message || '保存处理结果失败')
  } finally {
    reviewSaving.value = false
  }
}

onMounted(() => loadList())
</script>

<style scoped>
.admin-page { padding: 4px; }
.filter-card, .table-card { border-radius: 18px; }
.page-title-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}
.page-title-row h2 { margin: 0 0 6px; font-size: 22px; font-weight: 800; }
.page-title-row p { margin: 0; color: var(--art-gray-500); max-width: 760px; }
.toolbar-actions { display: flex; align-items: center; gap: 10px; }
.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-top: 18px;
}
.summary-card {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 16px;
  padding: 16px 18px;
  background: linear-gradient(180deg, #fbfdff 0%, #f5f8ff 100%);
}
.summary-card strong {
  display: block;
  color: #17315c;
  font-size: 22px;
  line-height: 1.2;
}
.summary-card span {
  display: block;
  margin-top: 8px;
  color: var(--art-gray-500);
  font-size: 12px;
}
.filter-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 18px;
}
.title-cell {
  display: flex;
  align-items: center;
  gap: 12px;
}
.creative-thumb {
  width: 82px;
  height: 62px;
  border-radius: 12px;
  object-fit: cover;
  border: 1px solid var(--el-border-color-lighter);
}
.title-copy,
.stack-cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
.stack-cell.center {
  align-items: center;
}
.title-copy strong,
.stack-cell strong {
  color: #17315c;
  font-size: 14px;
  line-height: 1.4;
}
.title-copy span,
.stack-cell span {
  color: var(--art-gray-500);
  font-size: 12px;
  line-height: 1.6;
  word-break: break-all;
}
.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 18px;
}
.drawer-state {
  padding: 40px 0;
  color: var(--art-gray-500);
  text-align: center;
}
.detail-cover {
  margin-bottom: 18px;
  border-radius: 18px;
  overflow: hidden;
  border: 1px solid var(--el-border-color-lighter);
}
.detail-cover img {
  width: 100%;
  max-height: 280px;
  object-fit: cover;
  display: block;
}
@media (max-width: 1100px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 720px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
