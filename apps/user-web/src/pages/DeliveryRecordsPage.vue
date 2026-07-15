<template>
  <div>
    <div v-if="error" class="global-notice error">{{ error }}</div>
    <div v-if="recordsLoadError" class="global-notice error">发货记录加载失败：{{ recordsLoadError }}</div>
    <div v-if="detailLoadError" class="global-notice error">发货详情加载失败：{{ detailLoadError }}</div>
    <div v-if="success" class="global-notice success">{{ success }}</div>

    <CardPanel title="发货记录筛选">
      <div class="toolbar wrap">
        <select v-model="query.status" class="input narrow">
          <option value="">全部状态</option>
          <option value="0">待处理</option>
          <option value="1">进行中</option>
          <option value="2">成功</option>
          <option value="3">失败</option>
          <option value="6">缺货</option>
          <option value="7">配置错误</option>
        </select>
        <select v-model="query.timing" class="input narrow">
          <option value="">全部时机</option>
          <option value="after_payment">付款后</option>
          <option value="after_receipt">收货后</option>
          <option value="after_review">评价后</option>
        </select>
        <select v-model="query.deliveryMode" class="input narrow">
          <option value="">全部方式</option>
          <option value="text">文本</option>
          <option value="card">卡密</option>
        </select>
        <input v-model="query.goodsKeyword" class="input grow" placeholder="商品关键词" />
        <input v-model="query.buyerKeyword" class="input grow" placeholder="买家关键词" />
        <input v-model="query.orderKeyword" class="input grow" placeholder="订单号 / 外部订单号" />
        <AppButton type="primary" @click="search">搜索</AppButton>
        <AppButton @click="resetFilters">重置</AppButton>
        <AppButton :disabled="!recordsAvailable || selectedIds.length === 0" @click="batchRetry">
          重试选中 ({{ selectedIds.length }})
        </AppButton>
        <AppButton :disabled="!recordsAvailable" @click="exportCsv">导出 CSV</AppButton>
      </div>
    </CardPanel>

    <CardPanel title="发货记录" style="margin-top: 16px">
      <div v-if="loading" class="table-loading" role="status">发货记录加载中...</div>
      <EmptyState v-else-if="!recordsAvailable" icon="⚠" title="发货记录不可用" :description="recordsLoadError || '正在加载发货记录，请稍候。'" />
      <BaseTable
        v-else
        v-model:selected-keys="selectedIds"
        :columns="columns"
        :rows="rows"
        :row-key="row => row.id"
        selectable
        @row-click="showDetail"
      >
        <template #status="{ row }">
          <Badge :type="row.deliveryBadge">{{ row.deliveryStatusText }}</Badge>
        </template>
        <template #timing="{ row }">
          {{ row.timingText }}
        </template>
        <template #mode="{ row }">
          {{ row.deliveryModeText }}
        </template>
        <template #progress="{ row }">
          {{ row.deliveryProgressText }}
        </template>
        <template #errorMessage="{ row }">
          <span class="cell-ellipsis" :title="row.errorMessage || ''">{{ row.errorMessage || '-' }}</span>
        </template>
        <template #op="{ row }">
          <div class="inline-actions">
            <button class="link" @click.stop="showDetail(row)">详情</button>
            <button v-if="row.canRetry" class="link" @click.stop="retry(row.id)">重试</button>
            <button v-if="row.canScheduleRedelivery" class="link" @click.stop="openSchedule(row)">安排重新发货</button>
          </div>
        </template>
      </BaseTable>
      <Pagination v-if="recordsAvailable" :total="total" :current="query.current" :page-size="query.size" @page-change="goPage" />
    </CardPanel>

    <CardPanel v-if="detailView" title="发货记录详情" style="margin-top: 16px">
      <div class="detail-grid delivery-record-detail-grid">
        <div><b>记录 ID：</b> {{ detailView.id || '-' }}</div>
        <div><b>订单号：</b> {{ detailView.orderId || '-' }}</div>
        <div><b>商品：</b> {{ detailView.goodsTitleText }}</div>
        <div><b>买家：</b> {{ detailView.buyerNameText }}</div>
        <div><b>状态：</b> {{ detailView.deliveryStatusText }}</div>
        <div><b>进度：</b> {{ detailView.deliveryProgressText }}</div>
        <div><b>时机：</b> {{ detailView.timingText }}</div>
        <div><b>方式：</b> {{ detailView.deliveryModeText }}</div>
        <div><b>创建时间：</b> {{ detailView.createdTimeText }}</div>
        <div><b>完成时间：</b> {{ detailView.completedTimeText }}</div>
        <div><b>平台同步：</b> {{ detailView.platformSyncTimeText }}</div>
        <div><b>结果：</b> {{ detailView.resultText }}</div>
      </div>

      <div class="panel-block">
        <div class="section-title">发货内容</div>
        <div class="content-box">{{ detailView.deliveryContentText }}</div>
      </div>

      <div class="panel-block">
        <div class="section-title">错误信息</div>
        <div class="content-box">{{ detailView.errorMessageText }}</div>
      </div>

      <div class="inline-actions">
        <AppButton v-if="detailView.canRetry" @click="retry(detailView.id)">重试当前记录</AppButton>
        <AppButton v-if="detailView.canScheduleRedelivery" @click="openSchedule(detailView)">安排重新发货</AppButton>
      </div>
    </CardPanel>

    <CardPanel v-if="redeliveryTarget" title="安排重新发货" style="margin-top: 16px">
      <div class="form-field">
        <label>记录</label>
        <div class="content-box compact">
          #{{ redeliveryTarget.id }} / {{ redeliveryTarget.goodsTitleText || redeliveryTarget.goodsTitle || '-' }}
        </div>
      </div>
      <div class="form-field">
        <label>Cron 表达式</label>
        <input v-model="redeliveryForm.cronExpression" class="input" placeholder="0 0/15 * * * ?" />
      </div>
      <div class="inline-actions">
        <AppButton type="primary" :loading="scheduling" @click="submitScheduleRedelivery">
          {{ scheduling ? '安排中...' : '创建重新发货任务' }}
        </AppButton>
        <AppButton @click="closeSchedule">取消</AppButton>
      </div>
    </CardPanel>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import CardPanel from '../components/CardPanel.vue'
import BaseTable from '../components/BaseTable.vue'
import Badge from '../components/Badge.vue'
import AppButton from '../components/AppButton.vue'
import Pagination from '../components/Pagination.vue'
import EmptyState from '../components/EmptyState.vue'
import { getDeliveryRecordDetail, getDeliveryRecords, retryDeliveryRecord, scheduleRedelivery } from '../api/autoDelivery.js'
import { camelizeKeys, totalOf } from '../utils/apiData.js'
import {
  buildDeliveryRecordDetailViewModel,
  buildDeliveryRecordRowViewModel,
  buildScheduleRedeliveryPayload
} from '../utils/deliveryRecordsPageState.js'

const records = ref([])
const total = ref(0)
const selectedIds = ref([])
const detail = ref(null)
const redeliveryTarget = ref(null)
const error = ref('')
const success = ref('')
const recordsLoadError = ref('')
const detailLoadError = ref('')
const recordsAvailable = ref(false)
const loading = ref(false)
const scheduling = ref(false)

const query = reactive({
  status: '',
  timing: '',
  deliveryMode: '',
  goodsKeyword: '',
  buyerKeyword: '',
  orderKeyword: '',
  current: 1,
  size: 20
})

const redeliveryForm = reactive({
  cronExpression: '0 0/15 * * * ?'
})

const columns = [
  { key: 'id', title: 'ID' },
  { key: 'orderId', title: '订单号' },
  { key: 'goodsTitleText', title: '商品' },
  { key: 'buyerNameText', title: '买家' },
  { key: 'timing', title: '时机' },
  { key: 'mode', title: '方式' },
  { key: 'status', title: '状态' },
  { key: 'progress', title: '进度' },
  { key: 'errorMessage', title: '错误' },
  { key: 'createdTimeText', title: '创建时间' },
  { key: 'op', title: '操作' }
]

const rows = computed(() => records.value.map(buildDeliveryRecordRowViewModel))
const detailView = computed(() => (detail.value ? buildDeliveryRecordDetailViewModel(detail.value) : null))

function clearNotice() {
  error.value = ''
  success.value = ''
}

function buildQuery() {
  return {
    status: query.status === '' ? undefined : Number(query.status),
    timing: query.timing || undefined,
    deliveryMode: query.deliveryMode || undefined,
    goodsKeyword: query.goodsKeyword || undefined,
    buyerKeyword: query.buyerKeyword || undefined,
    orderKeyword: query.orderKeyword || undefined,
    current: query.current,
    size: query.size
  }
}

async function load() {
  clearNotice()
  recordsLoadError.value = ''
  detailLoadError.value = ''
  recordsAvailable.value = false
  records.value = []
  total.value = 0
  selectedIds.value = []
  detail.value = null
  redeliveryTarget.value = null
  loading.value = true
  try {
    const res = await getDeliveryRecords(buildQuery())
    const data = res?.data
    const list = Array.isArray(data) ? data : data?.records || data?.list || data?.rows || data?.items
    if (!Array.isArray(list)) throw new Error('发货记录响应格式异常')
    records.value = camelizeKeys(list)
    total.value = totalOf(res.data, records.value.length)
    recordsAvailable.value = true
    return true
  } catch (requestError) {
    recordsLoadError.value = requestError?.message || '加载发货记录失败'
    return false
  } finally {
    loading.value = false
  }
}

async function showDetail(row) {
  clearNotice()
  detailLoadError.value = ''
  detail.value = null
  if (!recordsAvailable.value) {
    detailLoadError.value = '发货记录列表不可用，请先刷新列表'
    return false
  }
  try {
    const res = await getDeliveryRecordDetail(row.id)
    if (!res?.data || typeof res.data !== 'object' || Array.isArray(res.data)) throw new Error('发货记录详情响应格式异常')
    detail.value = camelizeKeys(res.data)
    return true
  } catch (requestError) {
    detailLoadError.value = requestError?.message || '加载发货记录详情失败'
    return false
  }
}

async function retry(id) {
  if (!recordsAvailable.value) {
    error.value = '发货记录列表不可用，无法确认要重试的记录'
    return
  }
  clearNotice()
  try {
    await retryDeliveryRecord(id)
    success.value = `已请求重试记录 #${id}`
    await load()
    if (detail.value?.id === id) {
      await showDetail(detail.value)
    }
  } catch (requestError) {
    error.value = requestError.message || '重试发货记录失败'
  }
}

async function batchRetry() {
  if (!recordsAvailable.value || !selectedIds.value.length) return
  clearNotice()
  let successCount = 0
  let failedCount = 0

  for (const id of selectedIds.value) {
    try {
      await retryDeliveryRecord(id)
      successCount += 1
    } catch {
      failedCount += 1
    }
  }

  if (successCount) {
    success.value = `已请求重试 ${successCount} 条记录${failedCount ? `，${failedCount} 条失败` : ''}`
  } else if (failedCount) {
    error.value = `${failedCount} 条记录重试失败`
  }

  await load()
}

function openSchedule(row) {
  redeliveryTarget.value = row
  redeliveryForm.cronExpression = '0 0/15 * * * ?'
}

function closeSchedule() {
  redeliveryTarget.value = null
}

async function submitScheduleRedelivery() {
  if (!redeliveryTarget.value?.id) return
  clearNotice()
  const payload = buildScheduleRedeliveryPayload(redeliveryForm)
  if (!payload.cronExpression) {
    error.value = 'Cron 表达式必填'
    return
  }

  scheduling.value = true
  try {
    await scheduleRedelivery(redeliveryTarget.value.id, payload)
    success.value = `已为记录 #${redeliveryTarget.value.id} 创建重新发货任务`
    redeliveryTarget.value = null
    await load()
  } catch (requestError) {
    error.value = requestError.message || '创建重新发货任务失败'
  } finally {
    scheduling.value = false
  }
}

function search() {
  query.current = 1
  load()
}

function resetFilters() {
  query.status = ''
  query.timing = ''
  query.deliveryMode = ''
  query.goodsKeyword = ''
  query.buyerKeyword = ''
  query.orderKeyword = ''
  query.current = 1
  load()
}

function goPage(page) {
  query.current = page
  load()
}

function escapeCsv(value) {
  return `"${String(value ?? '').replaceAll('"', '""')}"`
}

async function exportCsv() {
  clearNotice()
  if (!recordsAvailable.value) {
    error.value = '发货记录列表不可用，请先重试加载后再导出'
    return
  }
  const EXPORT_MAX_LIMIT = 2000   // 单次导出最大条数，防止浏览器内存压力
  const EXPORT_PAGE_SIZE = 100    // 分页拉取每页大小（后端 PageUtils 限制 max=100）
  const totalCount = total.value || 0
  if (totalCount > EXPORT_MAX_LIMIT) {
    error.value = `当前共 ${totalCount} 条记录，超过单次导出上限 ${EXPORT_MAX_LIMIT} 条，请添加筛选条件缩小范围后再导出`
    return
  }
  try {
    success.value = '正在准备导出数据...'
    const exportRows = []
    // 总数为 0 时也尝试拉取一页（可能 total 尚未加载）
    const targetCount = Math.max(totalCount, query.size)
    const totalPages = Math.max(1, Math.ceil(targetCount / EXPORT_PAGE_SIZE))
    for (let page = 1; page <= totalPages; page++) {
      const res = await getDeliveryRecords({
        ...buildQuery(),
        current: page,
        size: EXPORT_PAGE_SIZE
      })
      const data = res?.data
      const list = Array.isArray(data) ? data : data?.records || data?.list || data?.rows || data?.items
      if (!Array.isArray(list)) throw new Error('发货记录导出响应格式异常')
      const pageRecords = camelizeKeys(list).map(buildDeliveryRecordRowViewModel)
      exportRows.push(...pageRecords)
      if (pageRecords.length < EXPORT_PAGE_SIZE) break  // 已到末页
      if (exportRows.length >= EXPORT_MAX_LIMIT) {
        exportRows.length = EXPORT_MAX_LIMIT
        break
      }
      success.value = `正在导出 ${exportRows.length} / ${targetCount} 条...`
    }
    if (!exportRows.length) {
      error.value = '没有可导出的发货记录'
      return
    }

    const headers = ['ID', '订单号', '商品', '买家', '时机', '方式', '状态', '进度', '错误', '创建时间']
    const lines = [
      headers.join(','),
      ...exportRows.map(row => ([
        row.id,
        row.orderId,
        row.goodsTitleText,
        row.buyerNameText,
        row.timingText,
        row.deliveryModeText,
        row.deliveryStatusText,
        row.deliveryProgressText,
        row.errorMessage || '',
        row.createdTimeText
      ]).map(escapeCsv).join(','))
    ]

    const blob = new Blob(['\uFEFF' + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `delivery-records-${Date.now()}.csv`
    link.click()
    URL.revokeObjectURL(url)
    success.value = `已导出 ${exportRows.length} 条发货记录`
  } catch (requestError) {
    error.value = requestError.message || '导出发货记录失败'
  }
}

function onHeaderAction(event) {
  if (event.detail === 'delivery-records-refresh') load()
  if (event.detail === 'delivery-records-retry') batchRetry()
  if (event.detail === 'delivery-records-export') exportCsv()
}

onMounted(() => {
  window.addEventListener('xya-header-action', onHeaderAction)
  load()
})

onBeforeUnmount(() => {
  window.removeEventListener('xya-header-action', onHeaderAction)
})
</script>

<style scoped>
.wrap {
  flex-wrap: wrap;
}

.narrow {
  max-width: 160px;
}

.grow {
  flex: 1 1 180px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 16px;
}

.panel-block {
  margin-top: 16px;
}

.section-title {
  margin-bottom: 8px;
  font-weight: 600;
}

.content-box {
  min-height: 56px;
  padding: 12px;
  border: 1px solid #e6ecf5;
  border-radius: 10px;
  background: #fbfdff;
  white-space: pre-wrap;
  word-break: break-word;
}

.content-box.compact {
  min-height: auto;
}

.cell-ellipsis {
  display: inline-block;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.inline-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.form-field {
  display: grid;
  gap: 6px;
  margin-bottom: 12px;
}

.success {
  background: #ecfdf3;
  color: #067647;
  border-color: #abefc6;
}
</style>
