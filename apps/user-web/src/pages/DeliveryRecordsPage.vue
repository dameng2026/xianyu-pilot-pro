<template>
  <div class="dr-page">
    <!-- Toast 通知 -->
    <div v-if="error" class="dr-toast dr-toast-error">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>
      {{ error }}
    </div>
    <div v-if="recordsLoadError" class="dr-toast dr-toast-error">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>
      发货记录加载失败：{{ recordsLoadError }}
    </div>
    <div v-if="detailLoadError" class="dr-toast dr-toast-error">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>
      发货详情加载失败：{{ detailLoadError }}
    </div>
    <div v-if="sessionsLoadError" class="dr-toast dr-toast-error">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>
      声明会话加载失败：{{ sessionsLoadError }}
    </div>
    <div v-if="success" class="dr-toast dr-toast-success">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
      </svg>
      {{ success }}
    </div>

    <!-- 页面操作栏（标题由外层 App.vue 提供，这里仅保留操作按钮） -->
    <div class="dr-header dr-header-actions-only">
      <div class="dr-header-actions">
        <button class="dr-header-btn" @click="handleRefresh">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12a9 9 0 11-6.219-8.56"/>
          </svg>
          刷新
        </button>
        <button class="dr-header-btn" :disabled="!recordsAvailable || selectedIds.length === 0" @click="batchRetry">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
          </svg>
          重试选中 ({{ selectedIds.length }})
        </button>
        <button class="dr-header-btn dr-header-btn-primary" :disabled="!recordsAvailable" @click="exportCsv">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          导出 CSV
        </button>
      </div>
    </div>

    <!-- 信息横幅 -->
    <div class="dr-banner">
      <div class="dr-banner-icon">📦</div>
      <div class="dr-banner-content">
        <div class="dr-banner-title">完整追踪每一笔发货</div>
        <p class="dr-banner-desc">
          记录所有自动发货任务的执行明细，包括付款后发货、收货后赠送、好评后赠送。失败记录可手动重试，支持导出 CSV 用于数据分析。
        </p>
      </div>
      <div class="dr-banner-stats">
        <div class="dr-stat-item dr-stat-green">
          <b>{{ statValue(successCount) }}</b>
          <span>成功</span>
        </div>
        <div class="dr-stat-item dr-stat-blue">
          <b>{{ statValue(pendingCount) }}</b>
          <span>待处理</span>
        </div>
        <div class="dr-stat-item" :class="failCount > 0 ? 'dr-stat-red' : 'dr-stat-gray'">
          <b>{{ statValue(failCount) }}</b>
          <span>失败</span>
        </div>
        <div class="dr-stat-item dr-stat-orange">
          <b>{{ waitingCount }}</b>
          <span>待确认</span>
        </div>
      </div>
    </div>

    <!-- 顶层标签切换 -->
    <div class="dr-tabs">
      <button
        class="dr-tab"
        :class="{ active: activeTab === 'records' }"
        @click="switchTab('records')"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>
        </svg>
        发货记录
      </button>
      <button
        class="dr-tab"
        :class="{ active: activeTab === 'sessions' }"
        @click="switchTab('sessions')"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
        等待确认
        <span v-if="waitingCount > 0" class="dr-tab-badge">{{ waitingCount }}</span>
      </button>
    </div>

    <!-- ============ 等待确认（声明会话） ============ -->
    <template v-if="activeTab === 'sessions'">
      <div class="dr-card">
        <div class="dr-card-header">
          <span class="dr-card-title">筛选条件</span>
        </div>
        <div class="dr-toolbar dr-toolbar-wrap">
          <select v-model="sessionQuery.status" class="dr-select dr-select-narrow">
            <option value="">全部状态</option>
            <option value="declaring">发送中</option>
            <option value="waiting">等待买家确认</option>
            <option value="confirmed">已确认</option>
            <option value="cancelled">已取消</option>
          </select>
          <button class="dr-btn dr-btn-primary" @click="searchSessions">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            搜索
          </button>
          <button class="dr-btn" @click="resetSessionFilters">重置</button>
        </div>
      </div>

      <div class="dr-card" style="margin-top: 16px">
        <div class="dr-card-header">
          <span class="dr-card-title">声明会话列表</span>
        </div>
        <div v-if="sessionsLoading" class="dr-loading">
          <div class="dr-loading-spinner"></div>
          <span>声明会话加载中...</span>
        </div>
        <EmptyState
          v-else-if="!sessionsAvailable"
          icon="⚠"
          title="声明会话不可用"
          :description="sessionsLoadError || '正在加载声明会话，请稍候。'"
        />
        <BaseTable
          v-else
          :columns="sessionColumns"
          :rows="sessionRows"
          :row-key="row => row.id"
        >
          <template #status="{ row }">
            <span class="dr-badge" :class="'dr-badge-' + row.statusBadgeType">{{ row.statusText }}</span>
          </template>
          <template #goodsTitle="{ row }">
            <span class="dr-cell-ellipsis" :title="row.goodsTitle || ''">{{ row.goodsTitle || '-' }}</span>
          </template>
          <template #statementContent="{ row }">
            <span class="dr-cell-ellipsis" :title="row.statementContent || ''">{{ row.statementContent || '-' }}</span>
          </template>
          <template #sentAt="{ row }">
            {{ row.sentAtText }}
          </template>
          <template #confirmedAt="{ row }">
            {{ row.confirmedAtText }}
          </template>
          <template #op="{ row }">
            <div class="dr-inline-actions">
              <button
                v-if="row.status === 'waiting'"
                class="dr-link dr-link-primary"
                @click.stop="confirmSession(row)"
              >确认发货</button>
              <button
                v-if="row.status === 'waiting'"
                class="dr-link dr-link-danger"
                @click.stop="cancelSession(row)"
              >取消订单</button>
              <button class="dr-link" @click.stop="viewStatement(row)">查看声明</button>
            </div>
          </template>
        </BaseTable>
        <Pagination
          v-if="sessionsAvailable"
          :total="sessionsTotal"
          :current="sessionQuery.current"
          :page-size="sessionQuery.size"
          @page-change="goSessionPage"
        />
      </div>

      <div v-if="statementView" class="dr-card" style="margin-top: 16px">
        <div class="dr-card-header">
          <span class="dr-card-title">声明文案详情</span>
          <button class="dr-card-close" @click="closeStatementView">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="dr-detail-grid">
          <div><b>会话 ID：</b> {{ statementView.id || '-' }}</div>
          <div><b>订单号：</b> {{ statementView.orderId || '-' }}</div>
          <div><b>商品：</b> {{ statementView.goodsTitle || '-' }}</div>
          <div><b>买家：</b> {{ statementView.buyerNick || statementView.buyerId || '-' }}</div>
          <div><b>状态：</b>
            <span class="dr-badge" :class="'dr-badge-' + (SESSION_STATUS_BADGE[statementView.status] || 'info')">{{ statementView.statusText || statementView.status || '-' }}</span>
          </div>
          <div><b>发送时间：</b> {{ statementView.sentAtText || '-' }}</div>
        </div>
        <div class="dr-panel-block">
          <div class="dr-section-title">声明文案</div>
          <div class="dr-content-box">{{ statementView.statementContent || '-' }}</div>
        </div>
      </div>
    </template>

    <!-- ============ 发货记录 ============ -->
    <template v-else>
      <div class="dr-card">
        <div class="dr-card-header">
          <span class="dr-card-title">筛选条件</span>
        </div>
        <div class="dr-toolbar dr-toolbar-wrap">
          <select v-model="query.status" class="dr-select dr-select-narrow">
            <option value="">全部状态</option>
            <option value="0">待处理</option>
            <option value="1">进行中</option>
            <option value="2">成功</option>
            <option value="3">失败</option>
            <option value="6">缺货</option>
            <option value="7">配置错误</option>
          </select>
          <select v-model="query.timing" class="dr-select dr-select-narrow">
            <option value="">全部时机</option>
            <option value="after_payment">付款后</option>
            <option value="after_receipt">收货后</option>
            <option value="after_review">评价后</option>
          </select>
          <select v-model="query.deliveryMode" class="dr-select dr-select-narrow">
            <option value="">全部方式</option>
            <option value="text">文本</option>
            <option value="card">卡密</option>
          </select>
          <input v-model="query.goodsKeyword" class="dr-input dr-input-grow" placeholder="商品关键词" />
          <input v-model="query.buyerKeyword" class="dr-input dr-input-grow" placeholder="买家关键词" />
          <input v-model="query.orderKeyword" class="dr-input dr-input-grow" placeholder="订单号 / 外部订单号" />
          <button class="dr-btn dr-btn-primary" @click="search">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            搜索
          </button>
          <button class="dr-btn" @click="resetFilters">重置</button>
        </div>
      </div>

      <div class="dr-card" style="margin-top: 16px">
        <div class="dr-card-header">
          <span class="dr-card-count">共 {{ total }} 条</span>
        </div>
        <div v-if="loading" class="dr-loading">
          <div class="dr-loading-spinner"></div>
          <span>发货记录加载中...</span>
        </div>
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
            <span class="dr-badge" :class="'dr-badge-' + badgeType(row.deliveryBadge)">{{ row.deliveryStatusText }}</span>
          </template>
          <template #goods="{ row }">
            <div class="dr-goods-cell">
              <img
                v-if="row.goodsCoverPic"
                :src="row.goodsCoverPic"
                :alt="row.goodsTitleText"
                class="dr-goods-thumb"
                loading="lazy"
                referrerpolicy="no-referrer"
                @error="onGoodsThumbError"
              />
              <span class="dr-goods-name" :title="row.goodsTitleText">{{ row.goodsTitleText }}</span>
            </div>
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
            <span class="dr-cell-ellipsis" :title="row.errorMessage || ''">{{ row.errorMessage || '-' }}</span>
          </template>
          <template #op="{ row }">
            <div class="dr-inline-actions">
              <button class="dr-link dr-link-primary" @click.stop="showDetail(row)">详情</button>
              <button v-if="row.canRedeliver" class="dr-link" @click.stop="redeliver(row.id)">重新发货</button>
            </div>
          </template>
        </BaseTable>
        <Pagination v-if="recordsAvailable" :total="total" :current="query.current" :page-size="query.size" @page-change="goPage" />
      </div>

      <div v-if="detailView" class="dr-card" style="margin-top: 16px">
        <div class="dr-card-header">
          <span class="dr-card-title">发货记录详情</span>
          <button class="dr-card-close" @click="detail = null">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="dr-detail-grid dr-delivery-detail-grid">
          <div><b>记录 ID：</b> {{ detailView.id || '-' }}</div>
          <div><b>订单号：</b> {{ detailView.orderId || '-' }}</div>
          <div><b>外部订单号：</b> {{ detailView.externalOrderIdText }}</div>
          <div><b>商品 ID：</b> {{ detailView.goodsIdText }}</div>
          <div class="dr-detail-goods-row"><b>商品：</b>
            <div class="dr-goods-cell">
              <img
                v-if="detailView.goodsCoverPic"
                :src="detailView.goodsCoverPic"
                :alt="detailView.goodsTitleText"
                class="dr-goods-thumb"
                referrerpolicy="no-referrer"
                @error="onGoodsThumbError"
              />
              <span class="dr-goods-name">{{ detailView.goodsTitleText }}</span>
            </div>
          </div>
          <div><b>买家用户：</b> {{ detailView.buyerNameText }} <span v-if="detailView.buyerIdText && detailView.buyerIdText !== '-'" class="dr-muted">（{{ detailView.buyerIdText }}）</span></div>
          <div><b>卖家用户：</b> {{ detailView.sellerNameText }}</div>
          <div><b>购买时间：</b> {{ detailView.purchaseTimeText }}</div>
          <div><b>状态：</b> <span class="dr-badge" :class="'dr-badge-' + badgeType(detailView.deliveryBadge)">{{ detailView.deliveryStatusText }}</span></div>
          <div><b>进度：</b> {{ detailView.deliveryProgressText }}</div>
          <div><b>时机：</b> {{ detailView.timingText }}</div>
          <div><b>方式：</b> {{ detailView.deliveryModeText }}</div>
          <div><b>创建时间：</b> {{ detailView.createdTimeText }}</div>
          <div><b>完成时间：</b> {{ detailView.completedTimeText }}</div>
          <div><b>平台同步：</b> {{ detailView.platformSyncTimeText }}</div>
          <div><b>结果：</b> {{ detailView.resultText }}</div>
        </div>

        <div class="dr-panel-block">
          <div class="dr-section-title">发货内容</div>
          <div class="dr-content-box">{{ detailView.deliveryContentText }}</div>
        </div>

        <div v-if="detailView.errorMessageText && detailView.errorMessageText !== '-'" class="dr-panel-block">
          <div class="dr-section-title">错误信息</div>
          <div class="dr-content-box dr-content-box-error">{{ detailView.errorMessageText }}</div>
        </div>

        <div class="dr-inline-actions" style="margin-top: 16px">
          <button v-if="detailView.canRedeliver" class="dr-btn dr-btn-primary" @click="redeliver(detailView.id)">重新发货</button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import BaseTable from '../components/BaseTable.vue'
import Pagination from '../components/Pagination.vue'
import EmptyState from '../components/EmptyState.vue'
import {
  cancelDeliveryStatementSession,
  confirmDeliveryStatementSession,
  getDeliveryRecordDetail,
  getDeliveryRecords,
  listDeliveryStatementSessions,
  retryDeliveryRecord
} from '../api/autoDelivery.js'
import { camelizeKeys, totalOf } from '../utils/apiData.js'
import {
  buildDeliveryRecordDetailViewModel,
  buildDeliveryRecordRowViewModel
} from '../utils/deliveryRecordsPageState.js'

const records = ref([])
const total = ref(0)
const selectedIds = ref([])
const detail = ref(null)
const error = ref('')
const success = ref('')
const recordsLoadError = ref('')
const detailLoadError = ref('')
const sessionsLoadError = ref('')
const recordsAvailable = ref(false)
const loading = ref(false)

const activeTab = ref('records')

const sessions = ref([])
const sessionsTotal = ref(0)
const sessionsAvailable = ref(false)
const sessionsLoading = ref(false)
const statementView = ref(null)
const sessionQuery = reactive({
  status: '',
  current: 1,
  size: 20
})

const sessionColumns = [
  { key: 'id', title: 'ID' },
  { key: 'orderId', title: '订单号' },
  { key: 'goodsTitle', title: '商品' },
  { key: 'buyerNick', title: '买家' },
  { key: 'status', title: '状态' },
  { key: 'sentAt', title: '声明发送时间' },
  { key: 'confirmedAt', title: '确认/取消时间' },
  { key: 'statementContent', title: '声明文案' },
  { key: 'op', title: '操作' }
]

const SESSION_STATUS_TEXT = {
  declaring: '发送中',
  waiting: '等待买家确认',
  confirmed: '已确认',
  cancelled: '已取消'
}

const SESSION_STATUS_BADGE = {
  declaring: 'blue',
  waiting: 'orange',
  confirmed: 'green',
  cancelled: 'red'
}

function formatDateTime(value) {
  if (!value) return '-'
  const str = String(value).replace('T', ' ').replace(/\..*$/, '')
  return str || '-'
}

const sessionRows = computed(() =>
  sessions.value.map(row => {
    const r = camelizeKeys(row)
    return {
      ...r,
      statusText: SESSION_STATUS_TEXT[r.status] || r.status || '-',
      statusBadgeType: SESSION_STATUS_BADGE[r.status] || 'info',
      sentAtText: formatDateTime(r.sentAt),
      confirmedAtText: formatDateTime(r.confirmedAt || r.cancelledAt)
    }
  })
)

const waitingCount = computed(() =>
  sessions.value.filter(s => {
    const r = camelizeKeys(s)
    return r.status === 'waiting'
  }).length
)

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

const columns = [
  { key: 'id', title: 'ID' },
  { key: 'orderId', title: '订单号' },
  { key: 'goods', title: '商品' },
  { key: 'buyerNameText', title: '买家' },
  { key: 'sellerNameText', title: '卖家' },
  { key: 'timing', title: '时机' },
  { key: 'mode', title: '方式' },
  { key: 'status', title: '状态' },
  { key: 'progress', title: '进度' },
  { key: 'errorMessage', title: '错误' },
  { key: 'purchaseTimeText', title: '订单时间' },
  { key: 'op', title: '操作' }
]

const rows = computed(() => records.value.map(buildDeliveryRecordRowViewModel))
const detailView = computed(() => (detail.value ? buildDeliveryRecordDetailViewModel(detail.value) : null))

const successCount = computed(() => rows.value.filter(r => r.deliveryBadge === 'success' || r.deliveryBadge === 'green').length)
const pendingCount = computed(() => rows.value.filter(r => r.deliveryBadge === 'processing' || r.deliveryBadge === 'pending' || r.deliveryBadge === 'blue' || r.deliveryBadge === 'info').length)
const failCount = computed(() => rows.value.filter(r => r.deliveryBadge === 'fail' || r.deliveryBadge === 'error' || r.deliveryBadge === 'red').length)

function statValue(v) {
  return v ?? 0
}

function badgeType(type) {
  const map = {
    success: 'green',
    green: 'green',
    fail: 'red',
    error: 'red',
    red: 'red',
    pending: 'blue',
    processing: 'blue',
    blue: 'blue',
    info: 'blue',
    warn: 'orange',
    warning: 'orange',
    orange: 'orange'
  }
  return map[type] || 'info'
}

function clearNotice() {
  error.value = ''
  success.value = ''
  recordsLoadError.value = ''
  detailLoadError.value = ''
  sessionsLoadError.value = ''
}

function onGoodsThumbError(event) {
  const img = event?.target
  if (img && img.style) img.style.display = 'none'
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

function handleRefresh() {
  if (activeTab.value === 'sessions') {
    loadSessions()
  } else {
    load()
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

async function redeliver(id) {
  if (!recordsAvailable.value) {
    error.value = '发货记录列表不可用，无法确认要重新发货的记录'
    return
  }
  clearNotice()
  try {
    await retryDeliveryRecord(id)
    success.value = `已请求重新发货记录 #${id}`
    await load()
    if (detail.value?.id === id) {
      await showDetail(detail.value)
    }
  } catch (requestError) {
    error.value = requestError.message || '重新发货失败'
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
  const EXPORT_MAX_LIMIT = 2000
  const EXPORT_PAGE_SIZE = 100
  const totalCount = total.value || 0
  if (totalCount > EXPORT_MAX_LIMIT) {
    error.value = `当前共 ${totalCount} 条记录，超过单次导出上限 ${EXPORT_MAX_LIMIT} 条，请添加筛选条件缩小范围后再导出`
    return
  }
  try {
    success.value = '正在准备导出数据...'
    const exportRows = []
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
      if (pageRecords.length < EXPORT_PAGE_SIZE) break
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

    const headers = ['ID', '订单号', '商品', '买家', '卖家', '时机', '方式', '状态', '进度', '错误', '订单时间']
    const lines = [
      headers.join(','),
      ...exportRows.map(row => ([
        row.id,
        row.orderId,
        row.goodsTitleText,
        row.buyerNameText,
        row.sellerNameText,
        row.timingText,
        row.deliveryModeText,
        row.deliveryStatusText,
        row.deliveryProgressText,
        row.errorMessage || '',
        row.purchaseTimeText
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

// ============================================================
// 声明会话相关函数
// ============================================================

function switchTab(tab) {
  if (activeTab.value === tab) return
  activeTab.value = tab
  clearNotice()
  if (tab === 'sessions' && !sessionsAvailable.value && !sessionsLoading.value) {
    loadSessions()
  }
}

async function loadSessions() {
  clearNotice()
  sessionsLoadError.value = ''
  sessionsAvailable.value = false
  sessions.value = []
  sessionsTotal.value = 0
  statementView.value = null
  sessionsLoading.value = true
  try {
    const res = await listDeliveryStatementSessions({
      status: sessionQuery.status || undefined,
      current: sessionQuery.current,
      size: sessionQuery.size
    })
    const data = res?.data
    const list = Array.isArray(data) ? data : data?.list || data?.records || data?.rows || data?.items
    if (!Array.isArray(list)) throw new Error('声明会话响应格式异常')
    sessions.value = list
    sessionsTotal.value = totalOf(res.data, sessions.value.length)
    sessionsAvailable.value = true
    return true
  } catch (requestError) {
    sessionsLoadError.value = requestError?.message || '加载声明会话失败'
    return false
  } finally {
    sessionsLoading.value = false
  }
}

function searchSessions() {
  sessionQuery.current = 1
  loadSessions()
}

function resetSessionFilters() {
  sessionQuery.status = ''
  sessionQuery.current = 1
  loadSessions()
}

function goSessionPage(page) {
  sessionQuery.current = page
  loadSessions()
}

function viewStatement(row) {
  statementView.value = row
}

function closeStatementView() {
  statementView.value = null
}

async function confirmSession(row) {
  clearNotice()
  if (!window.confirm(`确认发货？将立即为订单 ${row.orderId || ''} 触发自动发货流程`)) return
  try {
    await confirmDeliveryStatementSession(row.id)
    success.value = `已确认会话 #${row.id}，已触发发货`
    await loadSessions()
  } catch (requestError) {
    error.value = requestError.message || '确认会话失败'
  }
}

async function cancelSession(row) {
  clearNotice()
  if (!window.confirm(`取消订单 ${row.orderId || ''} 的发货声明？将通知买家转人工客服，且不会发货`)) return
  try {
    await cancelDeliveryStatementSession(row.id)
    success.value = `已取消会话 #${row.id}，已通知买家`
    await loadSessions()
  } catch (requestError) {
    error.value = requestError.message || '取消会话失败'
  }
}

onMounted(() => {
  load()
})

onBeforeUnmount(() => {
})
</script>

<style scoped>
.dr-page {
  width: 100%;
  min-width: 0;
  padding: 20px 24px 48px;
  background: linear-gradient(180deg, #f8fafc 0%, #f5f7fb 100%);
  min-height: 100%;
}

/* Toast 通知 */
.dr-toast {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-radius: 10px;
  margin-bottom: 16px;
  font-size: 14px;
  font-weight: 500;
  animation: drSlideIn 0.3s ease;
}

@keyframes drSlideIn {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.dr-toast-success {
  background: linear-gradient(135deg, #ecfdf3 0%, #d1fae5 100%);
  color: #065f46;
  border: 1px solid #6ee7b7;
}

.dr-toast-error {
  background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
  color: #991b1b;
  border: 1px solid #fca5a5;
}

/* 页面头部 */
.dr-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.dr-header-actions-only {
  justify-content: flex-end;
  margin-bottom: 14px;
}

.dr-title {
  font-size: 24px;
  font-weight: 700;
  color: #101828;
  margin: 0 0 6px 0;
  letter-spacing: -0.5px;
}

.dr-subtitle {
  font-size: 14px;
  color: #667085;
  margin: 0;
}

.dr-header-actions {
  display: flex;
  gap: 10px;
}

.dr-header-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 16px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475467;
  cursor: pointer;
  transition: all 0.2s ease;
}

.dr-header-btn:hover:not(:disabled) {
  border-color: #0d6bff;
  color: #0d6bff;
  background: #f0f7ff;
}

.dr-header-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.dr-header-btn-primary {
  background: linear-gradient(135deg, #0d6bff 0%, #0052d9 100%);
  border-color: transparent;
  color: #fff;
  box-shadow: 0 2px 8px rgba(13, 107, 255, 0.25);
}

.dr-header-btn-primary:hover:not(:disabled) {
  background: linear-gradient(135deg, #2b7fff 0%, #0062f5 100%);
  color: #fff;
  box-shadow: 0 4px 12px rgba(13, 107, 255, 0.35);
  transform: translateY(-1px);
}

/* 信息横幅 */
.dr-banner {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 20px 24px;
  background: linear-gradient(135deg, #f0f7ff 0%, #eff6ff 50%, #eef2ff 100%);
  border: 1px solid #bfdbfe;
  border-radius: 16px;
  margin-bottom: 20px;
}

.dr-banner-icon {
  font-size: 40px;
  flex-shrink: 0;
}

.dr-banner-content {
  flex: 1;
  min-width: 0;
}

.dr-banner-title {
  font-size: 16px;
  font-weight: 700;
  color: #1e40af;
  margin-bottom: 6px;
}

.dr-banner-desc {
  font-size: 13px;
  color: #4b5563;
  margin: 0;
  line-height: 1.6;
}

.dr-banner-stats {
  display: flex;
  gap: 16px;
  flex-shrink: 0;
}

.dr-stat-item {
  text-align: center;
  padding: 12px 16px;
  background: #fff;
  border-radius: 12px;
  min-width: 72px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

.dr-stat-item b {
  display: block;
  font-size: 22px;
  font-weight: 700;
  color: #101828;
  line-height: 1.2;
}

.dr-stat-item span {
  display: block;
  font-size: 12px;
  color: #667085;
  margin-top: 2px;
}

.dr-stat-green b { color: #059669; }
.dr-stat-green { background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%); }
.dr-stat-blue b { color: #0d6bff; }
.dr-stat-blue { background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); }
.dr-stat-red b { color: #dc2626; }
.dr-stat-red { background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%); }
.dr-stat-orange b { color: #ea580c; }
.dr-stat-orange { background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%); }
.dr-stat-gray b { color: #6b7280; }
.dr-stat-gray { background: #f9fafb; }

/* Tabs */
.dr-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 20px;
  background: #fff;
  padding: 6px;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}

.dr-tab {
  position: relative;
  background: transparent;
  border: none;
  padding: 10px 18px;
  font-size: 14px;
  font-weight: 600;
  color: #667085;
  cursor: pointer;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-radius: 8px;
}

.dr-tab:hover {
  color: #0d6bff;
  background: #f0f7ff;
}

.dr-tab.active {
  color: #0d6bff;
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
  box-shadow: 0 1px 3px rgba(13,107,255,0.1);
}

.dr-tab-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 10px;
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  box-shadow: 0 2px 4px rgba(239,68,68,0.3);
}

/* Card */
.dr-card {
  background: #fff;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  overflow: hidden;
}

.dr-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #f1f5f9;
}

.dr-card-title {
  font-size: 15px;
  font-weight: 700;
  color: #101828;
}

.dr-card-count {
  font-size: 13px;
  color: #667085;
  font-weight: 500;
}

.dr-card-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: #667085;
  cursor: pointer;
  transition: all 0.15s ease;
}

.dr-card-close:hover {
  background: #f1f5f9;
  color: #dc2626;
}

/* Toolbar */
.dr-toolbar {
  display: flex;
  gap: 10px;
  padding: 16px 20px;
  align-items: center;
}

.dr-toolbar-wrap {
  flex-wrap: wrap;
}

.dr-select {
  padding: 9px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  font-size: 14px;
  color: #334155;
  background: #fff;
  cursor: pointer;
  transition: all 0.15s ease;
  outline: none;
}

.dr-select:focus {
  border-color: #0d6bff;
  box-shadow: 0 0 0 3px rgba(13,107,255,0.1);
}

.dr-select-narrow {
  min-width: 130px;
}

.dr-input {
  padding: 9px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  font-size: 14px;
  color: #334155;
  background: #fff;
  transition: all 0.15s ease;
  outline: none;
}

.dr-input:focus {
  border-color: #0d6bff;
  box-shadow: 0 0 0 3px rgba(13,107,255,0.1);
}

.dr-input::placeholder {
  color: #94a3b8;
}

.dr-input-grow {
  flex: 1;
  min-width: 160px;
}

.dr-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 9px 16px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475467;
  cursor: pointer;
  transition: all 0.2s ease;
}

.dr-btn:hover:not(:disabled) {
  border-color: #0d6bff;
  color: #0d6bff;
  background: #f0f7ff;
}

.dr-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.dr-btn-primary {
  background: linear-gradient(135deg, #0d6bff 0%, #0052d9 100%);
  border-color: transparent;
  color: #fff;
  box-shadow: 0 2px 6px rgba(13,107,255,0.2);
}

.dr-btn-primary:hover:not(:disabled) {
  background: linear-gradient(135deg, #2b7fff 0%, #0062f5 100%);
  color: #fff;
  box-shadow: 0 4px 10px rgba(13,107,255,0.3);
  transform: translateY(-1px);
}

/* Loading */
.dr-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  gap: 16px;
  color: #667085;
  font-size: 14px;
}

.dr-loading-spinner {
  width: 36px;
  height: 36px;
  border: 3px solid #e2e8f0;
  border-top-color: #0d6bff;
  border-radius: 50%;
  animation: drSpin 0.8s linear infinite;
}

@keyframes drSpin {
  to { transform: rotate(360deg); }
}

.dr-spin {
  animation: drSpin 1s linear infinite;
}

/* Badge */
.dr-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.4;
}

.dr-badge-green {
  background: #ecfdf5;
  color: #065f46;
}

.dr-badge-red {
  background: #fef2f2;
  color: #991b1b;
}

.dr-badge-blue {
  background: #eff6ff;
  color: #1e40af;
}

.dr-badge-orange {
  background: #fff7ed;
  color: #9a3412;
}

.dr-badge-info {
  background: #f1f5f9;
  color: #475569;
}

/* Links */
.dr-link {
  background: none;
  border: none;
  padding: 0;
  font-size: 13px;
  font-weight: 600;
  color: #667085;
  cursor: pointer;
  transition: color 0.15s ease;
}

.dr-link:hover {
  color: #0d6bff;
}

.dr-link-primary {
  color: #0d6bff;
}

.dr-link-primary:hover {
  color: #0052d9;
  text-decoration: underline;
}

.dr-link-danger {
  color: #dc2626;
}

.dr-link-danger:hover {
  color: #b91c1c;
}

/* Cells */
.dr-cell-ellipsis {
  display: inline-block;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dr-goods-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.dr-goods-thumb {
  width: 44px;
  height: 44px;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  flex-shrink: 0;
}

.dr-goods-name {
  display: inline-block;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: middle;
  font-weight: 500;
  color: #334155;
}

.dr-inline-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

/* Detail */
.dr-detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px 24px;
  padding: 20px;
}

.dr-detail-grid b {
  color: #475569;
  font-weight: 600;
}

.dr-delivery-detail-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.dr-detail-goods-row {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  grid-column: 1 / -1;
}

.dr-detail-goods-row b {
  flex-shrink: 0;
}

.dr-detail-goods-row .dr-goods-name {
  max-width: none;
  white-space: normal;
}

.dr-muted {
  color: #94a3b8;
  font-weight: 400;
}

.dr-panel-block {
  padding: 0 20px 20px;
}

.dr-section-title {
  margin-bottom: 10px;
  font-weight: 700;
  color: #334155;
  font-size: 14px;
}

.dr-content-box {
  min-height: 64px;
  padding: 14px 16px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #f8fafc;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 14px;
  line-height: 1.6;
  color: #334155;
}

.dr-content-box-compact {
  min-height: auto;
}

.dr-content-box-error {
  background: #fef2f2;
  border-color: #fecaca;
  color: #991b1b;
}

.dr-form-field {
  display: grid;
  gap: 8px;
  padding: 0 20px;
  margin-top: 16px;
}

.dr-form-field:first-child {
  margin-top: 0;
  padding-top: 4px;
}

.dr-form-field label {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
}

/* Responsive */
@media (max-width: 1200px) {
  .dr-banner {
    flex-wrap: wrap;
  }

  .dr-banner-stats {
    width: 100%;
    justify-content: center;
  }

  .dr-delivery-detail-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .dr-header {
    flex-direction: column;
    gap: 12px;
  }

  .dr-header-actions {
    width: 100%;
    flex-wrap: wrap;
  }

  .dr-banner {
    flex-direction: column;
    text-align: center;
  }

  .dr-detail-grid,
  .dr-delivery-detail-grid {
    grid-template-columns: 1fr;
  }

  .dr-tabs {
    overflow-x: auto;
  }
}
</style>
