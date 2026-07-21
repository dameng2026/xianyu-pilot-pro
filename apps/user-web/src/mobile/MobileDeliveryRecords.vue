<template>
  <div class="m-dr">
    <div class="m-dr-stats-grid">
      <div v-for="card in statCards" :key="card.key" class="m-dr-stat-card" @click="handleStatClick(card.key)">
        <div class="m-dr-stat-icon" :class="`m-dr-stat-icon-${card.color}`">
          <MIcon :name="card.icon" :size="20" />
        </div>
        <div class="m-dr-stat-info">
          <div class="m-dr-stat-title">{{ card.title }}</div>
          <div class="m-dr-stat-value">{{ statsLoading ? '—' : formatNumber(card.value) }}</div>
          <div class="m-dr-stat-desc" :class="`m-dr-stat-desc-${card.color}`">{{ card.desc }}</div>
        </div>
      </div>
    </div>

    <div class="m-dr-search-wrap">
      <div class="m-dr-search">
        <MIcon name="search" :size="18" class="m-dr-search-icon" />
        <input
          ref="searchInputRef"
          v-model="searchKeyword"
          type="text"
          class="m-dr-search-input"
          placeholder="搜索商品名称 / 订单号 / 买家"
          aria-label="搜索发货记录"
          @keyup.enter="handleSearch"
          @input="debouncedSearch"
        />
        <button v-if="searchKeyword" class="m-dr-search-clear" @click="clearSearch" aria-label="清空搜索">
          <MIcon name="x" :size="16" />
        </button>
      </div>
    </div>

    <div class="m-dr-filter-bar">
      <div class="m-dr-filter-grid">
        <button
          v-for="filter in filterOptions"
          :key="filter.key"
          class="m-dr-filter-chip"
          :class="{ 'm-dr-filter-chip-active': isFilterActive(filter) }"
          @click="openFilter(filter)"
        >
          <span>{{ getFilterLabel(filter) }}</span>
          <MIcon name="chevronDown" :size="14" />
        </button>
      </div>
    </div>

    <div class="m-dr-toolbar">
      <div class="m-dr-count">
        共 <b>{{ recordsLoading ? '—' : total }}</b> 条记录
      </div>
      <button v-if="hasFilters" class="m-dr-btn m-dr-btn-outline m-dr-btn-sm" @click="clearFilters">
        清除筛选
      </button>
    </div>

    <div v-if="recordsLoading && records.length === 0" class="m-dr-skeleton-list">
      <div v-for="i in 5" :key="i" class="m-dr-skeleton-card">
        <div class="m-dr-skeleton-img"></div>
        <div class="m-dr-skeleton-body">
          <div class="m-dr-skeleton-line m-dr-skeleton-title"></div>
          <div class="m-dr-skeleton-line m-dr-skeleton-meta"></div>
          <div class="m-dr-skeleton-tags">
            <div class="m-dr-skeleton-tag"></div>
            <div class="m-dr-skeleton-tag"></div>
          </div>
        </div>
      </div>
    </div>

    <MobileUnavailableState
      v-else-if="loadError"
      compact
      title="发货记录加载失败"
      :description="loadError"
      @retry="loadRecords"
    />

    <div v-else-if="records.length === 0" class="m-dr-empty">
      <div class="m-dr-empty-icon">
        <MIcon name="truck" :size="48" />
      </div>
      <div class="m-dr-empty-text">{{ hasFilters ? '暂无符合条件的记录' : '暂无发货记录' }}</div>
      <div class="m-dr-empty-desc">{{ hasFilters ? '请尝试调整筛选条件' : '系统将自动记录发货情况' }}</div>
      <button v-if="hasFilters" class="m-dr-btn m-dr-btn-primary m-dr-btn-sm" @click="clearFilters">清除筛选</button>
    </div>

    <div v-else class="m-dr-list">
      <div
        v-for="row in records"
        :key="row.id"
        class="m-dr-record-card"
        @click="showDetail(row)"
      >
        <div class="m-dr-record-img-wrap">
          <img
            v-if="row.goodsCoverPic"
            :src="row.goodsCoverPic"
            :alt="row.goodsTitleText"
            class="m-dr-record-img"
            referrerpolicy="no-referrer"
            @error="onImgError($event, row)"
          />
          <div v-else class="m-dr-record-img-placeholder">
            <MIcon name="bag" :size="24" />
          </div>
        </div>
        <div class="m-dr-record-body">
          <div class="m-dr-record-name" :title="row.goodsTitleText">{{ row.goodsTitleText || '未命名商品' }}</div>
          <div class="m-dr-record-meta">
            <span class="m-dr-record-order" :title="row.orderId">订单: {{ row.orderId || '-' }}</span>
            <span v-if="accountLabel(row)" class="m-dr-record-account">{{ accountLabel(row) }}</span>
          </div>
          <div class="m-dr-record-tags">
            <span class="m-dr-tag" :class="statusTagClass(row)">{{ row.deliveryStatusText }}</span>
            <span class="m-dr-tag m-dr-tag-light">{{ row.timingText }}</span>
            <span class="m-dr-tag m-dr-tag-gray">{{ row.deliveryModeText }}</span>
          </div>
          <div v-if="deliveryContentPreview(row)" class="m-dr-record-content">
            {{ deliveryContentPreview(row) }}
          </div>
          <div class="m-dr-record-footer">
            <span class="m-dr-record-time">{{ displayTime(row) }}</span>
            <span v-if="row.deliveryProgressText && row.deliveryProgressText !== '0 / 0'" class="m-dr-record-progress">
              {{ row.deliveryProgressText }}
            </span>
          </div>
        </div>
        <div class="m-dr-record-arrow">
          <MIcon name="chevronRight" :size="18" />
        </div>
      </div>

      <div v-if="loadingMore" class="m-dr-loading-more">加载中...</div>
      <div v-else-if="hasMore" class="m-dr-load-more">
        <button class="m-dr-btn m-dr-btn-outline" @click="loadMore">加载更多</button>
      </div>
      <div v-else-if="records.length > 0" class="m-dr-no-more">没有更多记录</div>
    </div>

    <div class="m-dr-safe-bottom"></div>

    <div v-if="activeFilter" class="m-dr-sheet-mask" @click="closeFilter"></div>
    <div v-if="activeFilter" class="m-dr-sheet" :class="{ 'm-dr-sheet-open': activeFilter }">
      <div class="m-dr-sheet-header">
        <h3>{{ activeFilter.title }}</h3>
        <button class="m-dr-sheet-close" @click="closeFilter" aria-label="关闭">
          <MIcon name="x" :size="20" />
        </button>
      </div>
      <div class="m-dr-sheet-body">
        <div v-if="activeFilter.key === 'account'" class="m-dr-sheet-search">
          <MIcon name="search" :size="16" class="m-dr-sheet-search-icon" />
          <input v-model="filterSearch" class="m-dr-sheet-search-input" placeholder="搜索账号" />
        </div>
        <div class="m-dr-sheet-options">
          <button
            v-for="opt in getFilterOptions(activeFilter)"
            :key="String(opt.value)"
            class="m-dr-sheet-option"
            :class="{ 'm-dr-sheet-option-active': isOptionSelected(activeFilter, opt) }"
            @click="selectFilterOption(activeFilter, opt)"
          >
            <span>{{ opt.label }}</span>
            <MIcon v-if="isOptionSelected(activeFilter, opt)" name="check" :size="18" class="m-dr-sheet-check" />
          </button>
        </div>
      </div>
      <div class="m-dr-sheet-footer">
        <button class="m-dr-btn m-dr-btn-outline" @click="resetFilter(activeFilter)">重置</button>
        <button class="m-dr-btn m-dr-btn-primary" @click="applyFilter">确定</button>
      </div>
    </div>

    <div v-if="detailVisible" class="m-dr-sheet-mask" @click="closeDetail"></div>
    <div v-if="detailVisible" class="m-dr-sheet m-dr-sheet-open m-dr-detail-sheet">
      <div class="m-dr-sheet-header">
        <h3>发货记录详情</h3>
        <button class="m-dr-sheet-close" @click="closeDetail" aria-label="关闭">
          <MIcon name="x" :size="20" />
        </button>
      </div>
      <div class="m-dr-sheet-body">
        <div v-if="detailLoading" class="m-dr-detail-loading">加载中...</div>
        <template v-else-if="detailView">
          <div class="m-dr-detail-goods">
            <img
              v-if="detailView.goodsCoverPic"
              :src="detailView.goodsCoverPic"
              :alt="detailView.goodsTitleText"
              class="m-dr-detail-thumb"
              referrerpolicy="no-referrer"
              @error="onImgError($event, detailView)"
            />
            <div v-else class="m-dr-detail-thumb-placeholder">
              <MIcon name="bag" :size="24" />
            </div>
            <div class="m-dr-detail-goods-info">
              <div class="m-dr-detail-goods-name">{{ detailView.goodsTitleText || '未命名商品' }}</div>
              <div class="m-dr-detail-goods-id">商品ID: {{ detailView.goodsIdText || '-' }}</div>
            </div>
          </div>

          <div class="m-dr-detail-grid">
            <div class="m-dr-detail-row">
              <span class="m-dr-detail-label">订单号</span>
              <span class="m-dr-detail-value">{{ detailView.orderId || '-' }}</span>
            </div>
            <div class="m-dr-detail-row">
              <span class="m-dr-detail-label">外部订单</span>
              <span class="m-dr-detail-value">{{ detailView.externalOrderIdText }}</span>
            </div>
            <div class="m-dr-detail-row">
              <span class="m-dr-detail-label">买家</span>
              <span class="m-dr-detail-value">
                {{ detailView.buyerNameText }}
                <span v-if="detailView.buyerIdText && detailView.buyerIdText !== '-'" class="muted">（{{ detailView.buyerIdText }}）</span>
              </span>
            </div>
            <div class="m-dr-detail-row">
              <span class="m-dr-detail-label">状态</span>
              <span class="m-dr-detail-value">
                <span class="m-dr-tag" :class="statusTagClass(detailView)">{{ detailView.deliveryStatusText }}</span>
              </span>
            </div>
            <div class="m-dr-detail-row">
              <span class="m-dr-detail-label">发货时机</span>
              <span class="m-dr-detail-value">{{ detailView.timingText }}</span>
            </div>
            <div class="m-dr-detail-row">
              <span class="m-dr-detail-label">发货方式</span>
              <span class="m-dr-detail-value">{{ detailView.deliveryModeText }}</span>
            </div>
            <div class="m-dr-detail-row">
              <span class="m-dr-detail-label">发货进度</span>
              <span class="m-dr-detail-value">{{ detailView.deliveryProgressText }}</span>
            </div>
            <div class="m-dr-detail-row">
              <span class="m-dr-detail-label">订单时间</span>
              <span class="m-dr-detail-value">{{ detailView.purchaseTimeText }}</span>
            </div>
            <div class="m-dr-detail-row">
              <span class="m-dr-detail-label">创建时间</span>
              <span class="m-dr-detail-value">{{ detailView.createdTimeText }}</span>
            </div>
            <div class="m-dr-detail-row">
              <span class="m-dr-detail-label">完成时间</span>
              <span class="m-dr-detail-value">{{ detailView.completedTimeText }}</span>
            </div>
          </div>

          <div class="m-dr-detail-block">
            <div class="m-dr-detail-block-title">发货内容</div>
            <div class="m-dr-detail-block-content">{{ detailView.deliveryContentText }}</div>
          </div>

          <div
            v-if="detailView.errorMessageText && detailView.errorMessageText !== '-'"
            class="m-dr-detail-block m-dr-detail-block-error"
          >
            <div class="m-dr-detail-block-title">失败原因</div>
            <div class="m-dr-detail-block-content">{{ detailView.errorMessageText }}</div>
          </div>

          <div
            v-if="detailView.resultText && detailView.resultText !== '-'"
            class="m-dr-detail-block"
          >
            <div class="m-dr-detail-block-title">结果</div>
            <div class="m-dr-detail-block-content">{{ detailView.resultText }}</div>
          </div>
        </template>
      </div>
      <div v-if="detailView && detailView.canRedeliver" class="m-dr-sheet-footer">
        <button class="m-dr-btn m-dr-btn-outline" @click="closeDetail">关闭</button>
        <button
          class="m-dr-btn m-dr-btn-primary"
          :disabled="retrying"
          @click="retryRecord(detailView)"
        >
          {{ retrying ? '重试中...' : '重新发货' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import MIcon from './MIcon.vue'
import MobileUnavailableState from './MobileUnavailableState.vue'
import {
  getDeliveryStats,
  getDeliveryRecords,
  getDeliveryRecordDetail,
  retryDeliveryRecord
} from '../api/autoDelivery.js'
import { getLiteAccounts } from '../api/accounts.js'
import { camelizeKeys, totalOf } from '../utils/apiData.js'
import {
  buildDeliveryRecordRowViewModel,
  buildDeliveryRecordDetailViewModel
} from '../utils/deliveryRecordsPageState.js'

defineEmits(['navigate', 'force-desktop', 'back'])

const searchInputRef = ref(null)
const statsLoading = ref(true)
const recordsLoading = ref(true)
const loadingMore = ref(false)
const loadError = ref('')
const stats = ref({
  todaySuccess: 0,
  todayFail: 0,
  pendingOrders: 0
})
const records = ref([])
const accounts = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const hasMore = ref(false)
const searchKeyword = ref('')
const filterSearch = ref('')
const filters = ref({
  accountId: '',
  status: '',
  timing: ''
})
const activeFilter = ref(null)
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailRecord = ref(null)
const retrying = ref(false)
let searchTimer = null

const statCards = computed(() => [
  { key: 'todaySuccess', title: '今日发货成功', value: stats.value.todaySuccess, desc: '今日成功', icon: 'shield', color: 'green' },
  { key: 'todayFail', title: '今日失败', value: stats.value.todayFail, desc: '需关注', icon: 'warning', color: 'orange' },
  { key: 'pendingOrders', title: '待处理订单', value: stats.value.pendingOrders, desc: '待处理', icon: 'clock', color: 'blue' }
])

const filterOptions = computed(() => [
  {
    key: 'account',
    title: '全部账号',
    options: [
      { value: '', label: '全部账号' },
      ...accounts.value.map(a => ({
        value: a.id,
        label: a.nickname || a.remark || a.username || `账号${a.id}`
      }))
    ]
  },
  {
    key: 'status',
    title: '全部状态',
    options: [
      { value: '', label: '全部状态' },
      { value: '0', label: '待处理' },
      { value: '1', label: '进行中' },
      { value: '2', label: '成功' },
      { value: '3', label: '失败' },
      { value: '6', label: '缺货' },
      { value: '7', label: '配置错误' }
    ]
  },
  {
    key: 'timing',
    title: '全部时机',
    options: [
      { value: '', label: '全部时机' },
      { value: 'after_payment', label: '付款后' },
      { value: 'after_receipt', label: '收货后' },
      { value: 'after_review', label: '评价后' }
    ]
  }
])

const hasFilters = computed(() => {
  return searchKeyword.value || Object.values(filters.value).some(v => v !== '')
})

const detailView = computed(() =>
  detailRecord.value ? buildDeliveryRecordDetailViewModel(detailRecord.value) : null
)

const STATUS_BADGE_TO_TAG = {
  green: 'm-dr-tag-green',
  red: 'm-dr-tag-red',
  orange: 'm-dr-tag-orange',
  blue: 'm-dr-tag-blue',
  gray: 'm-dr-tag-gray'
}

function formatNumber(num) {
  if (num == null || num === undefined || isNaN(num)) return 0
  return Number(num).toLocaleString()
}

function statusTagClass(row) {
  const badge = row?.deliveryBadge
  return STATUS_BADGE_TO_TAG[badge] || 'm-dr-tag-gray'
}

function accountLabel(row) {
  if (!row) return ''
  return row.accountName || row.accountNickname || row.xianyuAccountName || row.account?.nickname || ''
}

function displayTime(row) {
  if (!row) return '-'
  return row.purchaseTimeText && row.purchaseTimeText !== '-'
    ? row.purchaseTimeText
    : row.createdTimeText
}

function deliveryContentPreview(row) {
  if (!row) return ''
  const content = row.deliveryContent || row.content || ''
  if (!content) return ''
  const text = String(content).trim()
  if (!text) return ''
  return text.length > 48 ? text.slice(0, 48) + '…' : text
}

function getFilterLabel(filter) {
  const current = filters.value[filter.key]
  const opt = filter.options.find(o => String(o.value) === String(current))
  return opt ? opt.label : filter.title
}

function isFilterActive(filter) {
  return filters.value[filter.key] !== ''
}

function getFilterOptions(filter) {
  if (filter.key !== 'account' || !filterSearch.value) return filter.options
  const keyword = filterSearch.value.toLowerCase()
  return filter.options.filter(o => String(o.label).toLowerCase().includes(keyword))
}

function isOptionSelected(filter, opt) {
  return String(filters.value[filter.key]) === String(opt.value)
}

function selectFilterOption(filter, opt) {
  filters.value[filter.key] = opt.value
  applyFilter()
}

function resetFilter(filter) {
  if (filter) {
    filters.value[filter.key] = ''
  }
  applyFilter()
}

function openFilter(filter) {
  activeFilter.value = filter
  filterSearch.value = ''
  document.body.style.overflow = 'hidden'
}

function closeFilter() {
  activeFilter.value = null
  document.body.style.overflow = ''
}

function applyFilter() {
  closeFilter()
  page.value = 1
  loadRecords()
}

function clearFilters() {
  filters.value = { accountId: '', status: '', timing: '' }
  searchKeyword.value = ''
  page.value = 1
  loadRecords()
}

function handleSearch() {
  page.value = 1
  loadRecords()
}

function debouncedSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    handleSearch()
  }, 400)
}

function clearSearch() {
  searchKeyword.value = ''
  handleSearch()
  if (searchInputRef.value) searchInputRef.value.blur()
}

function handleStatClick(key) {
  if (key === 'todayFail') {
    filters.value.status = '3'
    applyFilter()
  } else if (key === 'pendingOrders') {
    filters.value.status = '0'
    applyFilter()
  } else if (key === 'todaySuccess') {
    filters.value.status = '2'
    applyFilter()
  }
}

function onImgError(event, row) {
  if (row && 'goodsCoverPic' in row) row.goodsCoverPic = ''
  const img = event?.target
  if (img && img.style) img.style.display = 'none'
}

function buildQueryParams() {
  const params = {
    current: page.value,
    size: pageSize.value
  }
  if (filters.value.accountId) params.accountId = filters.value.accountId
  if (filters.value.status) params.status = Number(filters.value.status)
  if (filters.value.timing) params.timing = filters.value.timing
  const keyword = (searchKeyword.value || '').trim()
  if (keyword) {
    // 全数字视为订单号，否则视为商品关键词
    if (/^\d+$/.test(keyword)) {
      params.orderKeyword = keyword
    } else {
      params.goodsKeyword = keyword
    }
  }
  return params
}

async function loadStats() {
  statsLoading.value = true
  try {
    const res = await getDeliveryStats()
    const data = res?.data || {}
    stats.value = {
      todaySuccess: data.todaySuccess ?? 0,
      todayFail: data.todayFail ?? 0,
      pendingOrders: data.pendingOrders ?? 0
    }
  } catch (e) {
    stats.value = { todaySuccess: 0, todayFail: 0, pendingOrders: 0 }
  } finally {
    statsLoading.value = false
  }
}

async function loadAccounts() {
  try {
    const res = await getLiteAccounts({ page: 1, pageSize: 100 })
    const data = res?.data
    const list = data?.records || data?.list || (Array.isArray(data) ? data : [])
    accounts.value = list
  } catch (e) {
    accounts.value = []
  }
}

async function loadRecords(append = false) {
  if (!append) {
    recordsLoading.value = true
  } else {
    loadingMore.value = true
  }
  loadError.value = ''
  try {
    const res = await getDeliveryRecords(buildQueryParams())
    const data = res?.data
    const list = Array.isArray(data) ? data : data?.records || data?.list || data?.rows || data?.items
    if (!Array.isArray(list)) throw new Error('发货记录响应格式异常')
    const camelList = camelizeKeys(list)
    const rows = camelList.map(buildDeliveryRecordRowViewModel)
    total.value = totalOf(res.data, rows.length)
    if (append) {
      records.value = [...records.value, ...rows]
    } else {
      records.value = rows
    }
    hasMore.value = records.value.length < total.value
  } catch (e) {
    loadError.value = e?.message || '请检查网络连接后重试'
    if (!append) records.value = []
  } finally {
    recordsLoading.value = false
    loadingMore.value = false
  }
}

async function loadMore() {
  if (loadingMore.value || !hasMore.value) return
  page.value++
  await loadRecords(true)
}

async function showDetail(row) {
  detailVisible.value = true
  detailLoading.value = true
  detailRecord.value = row ? buildDeliveryRecordRowViewModel(row) : null
  document.body.style.overflow = 'hidden'
  try {
    const res = await getDeliveryRecordDetail(row.id)
    if (!res?.data || typeof res.data !== 'object' || Array.isArray(res.data)) {
      throw new Error('发货记录详情响应格式异常')
    }
    detailRecord.value = camelizeKeys(res.data)
  } catch (e) {
    window.dispatchEvent(new CustomEvent('xya-toast', {
      detail: { message: e?.message || '加载详情失败', isError: true }
    }))
  } finally {
    detailLoading.value = false
  }
}

function closeDetail() {
  detailVisible.value = false
  detailRecord.value = null
  document.body.style.overflow = ''
}

async function retryRecord(row) {
  if (!row?.id || retrying.value) return
  retrying.value = true
  try {
    await retryDeliveryRecord(row.id)
    window.dispatchEvent(new CustomEvent('xya-toast', {
      detail: { message: `已请求重新发货记录 #${row.id}` }
    }))
    closeDetail()
    page.value = 1
    await Promise.all([loadStats(), loadRecords()])
  } catch (e) {
    window.dispatchEvent(new CustomEvent('xya-toast', {
      detail: { message: e?.message || '重新发货失败', isError: true }
    }))
  } finally {
    retrying.value = false
  }
}

async function loadData() {
  await Promise.all([loadStats(), loadAccounts()])
  await loadRecords()
}

onMounted(() => {
  loadData()
})

onBeforeUnmount(() => {
  if (searchTimer) clearTimeout(searchTimer)
  document.body.style.overflow = ''
})
</script>

<style scoped>
.m-dr {
  padding: 10px 16px 0;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
}

.m-dr-stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-bottom: 12px;
}

.m-dr-stat-card {
  background: white;
  border-radius: 14px;
  padding: 12px 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  box-shadow: 0 2px 8px rgba(31, 53, 94, 0.05);
  border: 1px solid #f0f4fa;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}
.m-dr-stat-card:active {
  transform: scale(0.98);
}

.m-dr-stat-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-dr-stat-icon-green {
  background: linear-gradient(135deg, #dcfce7, #bbf7d0);
  color: #16a34a;
}
.m-dr-stat-icon-orange {
  background: linear-gradient(135deg, #fef3c7, #fde68a);
  color: #f59e0b;
}
.m-dr-stat-icon-blue {
  background: linear-gradient(135deg, #dbeafe, #bfdbfe);
  color: #2563eb;
}

.m-dr-stat-info {
  flex: 1;
  min-width: 0;
  text-align: center;
}
.m-dr-stat-title {
  font-size: 11px;
  color: #72809a;
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.m-dr-stat-value {
  font-size: 20px;
  font-weight: 800;
  color: #15213d;
  line-height: 1.2;
}
.m-dr-stat-desc {
  font-size: 10px;
  font-weight: 500;
  margin-top: 2px;
}
.m-dr-stat-desc-green { color: #16a34a; }
.m-dr-stat-desc-orange { color: #f59e0b; }
.m-dr-stat-desc-blue { color: #2563eb; }

.m-dr-search-wrap {
  margin-bottom: 10px;
}
.m-dr-search {
  display: flex;
  align-items: center;
  gap: 8px;
  background: white;
  border: 1px solid #e7edf7;
  border-radius: 12px;
  padding: 0 14px;
  height: 46px;
}
.m-dr-search-icon {
  color: #8c98ae;
  flex-shrink: 0;
}
.m-dr-search-input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 14px;
  color: #15213d;
  background: transparent;
  min-width: 0;
}
.m-dr-search-input::placeholder {
  color: #b0bacb;
}
.m-dr-search-clear {
  width: 28px;
  height: 28px;
  border: none;
  background: #f0f4fa;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #8c98ae;
  cursor: pointer;
  flex-shrink: 0;
}

.m-dr-filter-bar {
  margin-bottom: 12px;
}
.m-dr-filter-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.m-dr-filter-chip {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 3px;
  background: #fff;
  border: 1px solid #e7ebf1;
  color: #63718a;
  padding: 0 9px;
  border-radius: 9px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  min-height: 40px;
  overflow: hidden;
}
.m-dr-filter-chip span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-dr-filter-chip-active {
  border-color: #1478f5;
  color: #1478f5;
  background: #f3f8ff;
}

.m-dr-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  gap: 10px;
}
.m-dr-count {
  font-size: 13px;
  color: #5a6a85;
}
.m-dr-count b {
  color: #15213d;
  font-weight: 700;
}

.m-dr-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: none;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  padding: 10px 16px;
  min-height: 40px;
}
.m-dr-btn:active { transform: scale(0.97); }
.m-dr-btn-primary {
  background: linear-gradient(135deg, #0d6bff, #2580ff);
  color: white;
  box-shadow: 0 4px 12px rgba(13, 107, 255, 0.25);
}
.m-dr-btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.m-dr-btn-outline {
  background: white;
  color: #5a6a85;
  border: 1px solid #e7edf7;
}
.m-dr-btn-sm {
  padding: 8px 14px;
  font-size: 12px;
  min-height: 36px;
}

.m-dr-skeleton-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.m-dr-skeleton-card {
  background: white;
  border-radius: 16px;
  padding: 12px;
  display: flex;
  gap: 12px;
  border: 1px solid #f0f4fa;
}
.m-dr-skeleton-img {
  width: 64px;
  height: 64px;
  border-radius: 10px;
  background: linear-gradient(90deg, #f4f7fc 25%, #e8edf5 50%, #f4f7fc 75%);
  background-size: 200% 100%;
  animation: m-dr-skeleton 1.5s infinite;
  flex-shrink: 0;
}
.m-dr-skeleton-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.m-dr-skeleton-line {
  height: 14px;
  border-radius: 4px;
  background: linear-gradient(90deg, #f4f7fc 25%, #e8edf5 50%, #f4f7fc 75%);
  background-size: 200% 100%;
  animation: m-dr-skeleton 1.5s infinite;
}
.m-dr-skeleton-title { width: 70%; }
.m-dr-skeleton-meta { width: 50%; height: 12px; }
.m-dr-skeleton-tags {
  display: flex;
  gap: 8px;
}
.m-dr-skeleton-tag {
  width: 60px;
  height: 20px;
  border-radius: 100px;
  background: linear-gradient(90deg, #f4f7fc 25%, #e8edf5 50%, #f4f7fc 75%);
  background-size: 200% 100%;
  animation: m-dr-skeleton 1.5s infinite;
}
@keyframes m-dr-skeleton {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.m-dr-empty {
  text-align: center;
  padding: 60px 20px;
}
.m-dr-empty-icon {
  width: 80px;
  height: 80px;
  margin: 0 auto 16px;
  border-radius: 50%;
  background: linear-gradient(135deg, #e8f1ff, #d4e4ff);
  color: #0d6bff;
  display: flex;
  align-items: center;
  justify-content: center;
}
.m-dr-empty-text {
  font-size: 16px;
  font-weight: 600;
  color: #15213d;
  margin-bottom: 6px;
}
.m-dr-empty-desc {
  font-size: 13px;
  color: #8c98ae;
  margin-bottom: 20px;
}

.m-dr-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.m-dr-record-card {
  background: #fff;
  border-radius: 16px;
  padding: 12px;
  display: flex;
  gap: 12px;
  box-shadow: 0 4px 14px rgba(31, 53, 94, 0.04);
  border: 1px solid #edf1f5;
  cursor: pointer;
  transition: transform 0.15s;
}
.m-dr-record-card:active { transform: scale(0.99); }

.m-dr-record-img-wrap {
  width: 70px;
  height: 70px;
  border-radius: 9px;
  overflow: hidden;
  flex-shrink: 0;
  background: #f4f7fc;
}
.m-dr-record-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.m-dr-record-img-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #b0bacb;
  background: linear-gradient(135deg, #f4f7fc, #eaf0fa);
}

.m-dr-record-body {
  flex: 1;
  min-width: 0;
}
.m-dr-record-name {
  font-size: 14px;
  font-weight: 700;
  color: #15213d;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  word-break: break-all;
  margin-bottom: 4px;
}
.m-dr-record-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
  flex-wrap: wrap;
}
.m-dr-record-order {
  font-size: 11px;
  color: #8c98ae;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 140px;
}
.m-dr-record-account {
  font-size: 11px;
  color: #5a6a85;
  background: #f0f4fa;
  padding: 2px 8px;
  border-radius: 100px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100px;
}
.m-dr-record-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}
.m-dr-tag {
  font-size: 10px;
  font-weight: 500;
  padding: 3px 8px;
  border-radius: 100px;
  white-space: nowrap;
}
.m-dr-tag-green {
  background: rgba(22, 163, 74, 0.1);
  color: #16a34a;
}
.m-dr-tag-red {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}
.m-dr-tag-orange {
  background: rgba(245, 158, 11, 0.1);
  color: #f59e0b;
}
.m-dr-tag-blue {
  background: rgba(37, 99, 235, 0.1);
  color: #2563eb;
}
.m-dr-tag-gray {
  background: rgba(140, 152, 174, 0.12);
  color: #7f8a9d;
}
.m-dr-tag-light {
  background: rgba(13, 107, 255, 0.08);
  color: #0d6bff;
}

.m-dr-record-content {
  font-size: 12px;
  color: #5a6a85;
  background: #f8fafc;
  border-radius: 8px;
  padding: 6px 8px;
  margin-bottom: 6px;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  word-break: break-all;
}

.m-dr-record-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.m-dr-record-time {
  font-size: 11px;
  color: #8c98ae;
}
.m-dr-record-progress {
  font-size: 11px;
  color: #5a6a85;
  font-weight: 600;
  background: #f0f4fa;
  padding: 2px 8px;
  border-radius: 100px;
}

.m-dr-record-arrow {
  display: flex;
  align-items: center;
  color: #c0c8d6;
  flex-shrink: 0;
}

.m-dr-loading-more,
.m-dr-load-more,
.m-dr-no-more {
  text-align: center;
  padding: 20px;
  font-size: 13px;
  color: #8c98ae;
}
.m-dr-load-more .m-dr-btn {
  padding: 8px 24px;
}

.m-dr-safe-bottom {
  height: calc(84px + env(safe-area-inset-bottom));
}

.m-dr-sheet-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 25, 50, 0.4);
  z-index: 200;
  backdrop-filter: blur(2px);
}

.m-dr-sheet {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  background: white;
  border-radius: 20px 20px 0 0;
  z-index: 201;
  transform: translateY(100%);
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  padding-bottom: env(safe-area-inset-bottom);
}
.m-dr-sheet-open {
  transform: translateY(0);
}
.m-dr-sheet-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #f0f4fa;
}
.m-dr-sheet-header h3 {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  color: #15213d;
}
.m-dr-sheet-close {
  width: 36px;
  height: 36px;
  border: none;
  background: #f5f7fb;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #5a6a85;
  cursor: pointer;
}
.m-dr-sheet-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}
.m-dr-sheet-search {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #f5f7fb;
  border-radius: 10px;
  padding: 0 12px;
  margin-bottom: 12px;
  height: 42px;
}
.m-dr-sheet-search-icon {
  color: #8c98ae;
  flex-shrink: 0;
}
.m-dr-sheet-search-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 14px;
}
.m-dr-sheet-options {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.m-dr-sheet-option {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 12px;
  border: none;
  background: transparent;
  border-radius: 10px;
  font-size: 15px;
  color: #15213d;
  cursor: pointer;
  text-align: left;
}
.m-dr-sheet-option:active { background: #f5f7fb; }
.m-dr-sheet-option-active {
  background: #eef4ff;
  color: #0d6bff;
  font-weight: 600;
}
.m-dr-sheet-check {
  color: #0d6bff;
  flex-shrink: 0;
}
.m-dr-sheet-footer {
  display: flex;
  gap: 10px;
  padding: 12px 20px 16px;
  border-top: 1px solid #f0f4fa;
}
.m-dr-sheet-footer .m-dr-btn {
  flex: 1;
}

.m-dr-detail-loading {
  text-align: center;
  padding: 40px 0;
  color: #8c98ae;
  font-size: 14px;
}

.m-dr-detail-goods {
  display: flex;
  gap: 12px;
  padding-bottom: 16px;
  border-bottom: 1px solid #f0f4fa;
  margin-bottom: 16px;
}
.m-dr-detail-thumb {
  width: 64px;
  height: 64px;
  border-radius: 10px;
  object-fit: cover;
  background: #f4f7fc;
  flex-shrink: 0;
}
.m-dr-detail-thumb-placeholder {
  width: 64px;
  height: 64px;
  border-radius: 10px;
  background: linear-gradient(135deg, #f4f7fc, #eaf0fa);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #b0bacb;
  flex-shrink: 0;
}
.m-dr-detail-goods-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.m-dr-detail-goods-name {
  font-size: 15px;
  font-weight: 700;
  color: #15213d;
  line-height: 1.4;
  margin-bottom: 4px;
  word-break: break-all;
}
.m-dr-detail-goods-id {
  font-size: 12px;
  color: #8c98ae;
}

.m-dr-detail-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 16px;
}
.m-dr-detail-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  font-size: 14px;
  line-height: 1.6;
}
.m-dr-detail-label {
  flex-shrink: 0;
  width: 80px;
  color: #72809a;
}
.m-dr-detail-value {
  flex: 1;
  color: #15213d;
  word-break: break-all;
}
.m-dr-detail-value .muted {
  color: #8c98ae;
}

.m-dr-detail-block {
  margin-bottom: 16px;
}
.m-dr-detail-block-title {
  font-size: 13px;
  font-weight: 600;
  color: #5a6a85;
  margin-bottom: 8px;
}
.m-dr-detail-block-content {
  font-size: 14px;
  color: #15213d;
  line-height: 1.6;
  background: #f8fafc;
  border: 1px solid #eef2fa;
  border-radius: 10px;
  padding: 12px;
  white-space: pre-wrap;
  word-break: break-word;
}
.m-dr-detail-block-error .m-dr-detail-block-title {
  color: #ef4444;
}
.m-dr-detail-block-error .m-dr-detail-block-content {
  background: #fff5f5;
  border-color: #ffd0d0;
  color: #b91c1c;
}

@media (max-width: 360px) {
  .m-dr { padding: 10px 12px 0; }
  .m-dr-stats-grid { gap: 6px; }
  .m-dr-stat-card { padding: 10px 6px; }
  .m-dr-stat-icon { width: 32px; height: 32px; }
  .m-dr-stat-value { font-size: 18px; }
  .m-dr-stat-title { font-size: 10px; }
  .m-dr-record-img-wrap { width: 60px; height: 60px; }
  .m-dr-filter-chip { font-size: 11px; padding: 0 6px; }
}
</style>
