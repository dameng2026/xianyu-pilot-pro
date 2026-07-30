<template>
  <div class="m-dr">
    <!-- 顶部 Hero：KPI 大卡 -->
    <section class="m-dr-hero">
      <div class="m-dr-hero-head">
        <div class="m-dr-hero-badge">
          <span class="m-dr-hero-dot"></span>
          <span>发货追踪</span>
        </div>
        <h1 class="m-dr-hero-title">发货记录</h1>
        <p class="m-dr-hero-sub">订单发货全流程 · 可追溯 · 可重试</p>
      </div>
      <div class="m-dr-kpi-row">
        <template v-for="(card, idx) in statCards" :key="card.key">
          <div v-if="idx > 0" class="m-dr-kpi-divider"></div>
          <div class="m-dr-kpi-cell" @click="handleStatClick(card.key)">
            <div class="m-dr-kpi-value" :class="`m-dr-kpi-value--${card.color}`">{{ statsLoading ? '—' : formatNumber(card.value) }}</div>
            <div class="m-dr-kpi-label">{{ card.title }}</div>
          </div>
        </template>
      </div>
    </section>

    <!-- 搜索 -->
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

    <!-- 筛选 chips -->
    <div class="m-dr-filter-bar">
      <div class="m-dr-filter-grid">
        <button
          v-for="filter in filterOptions"
          :key="filter.key"
          type="button"
          class="m-dr-filter-chip"
          :class="{ 'm-dr-filter-chip--active': isFilterActive(filter) }"
          @click="openFilter(filter)"
        >
          <span>{{ getFilterLabel(filter) }}</span>
          <MIcon name="chevronDown" :size="14" />
        </button>
      </div>
    </div>

    <!-- 工具栏 -->
    <div class="m-dr-toolbar">
      <div class="m-dr-count">
        共 <b>{{ recordsLoading ? '—' : formatNumber(total) }}</b> 条记录
      </div>
      <button v-if="hasFilters" type="button" class="m-dr-btn m-dr-btn-outline m-dr-btn-sm" @click="clearFilters">
        清除筛选
      </button>
    </div>

    <!-- 骨架屏 -->
    <div v-if="recordsLoading && records.length === 0" class="m-dr-skeleton-list">
      <div v-for="i in 5" :key="i" class="m-dr-skeleton-item">
        <div class="m-dr-skeleton-rail">
          <div class="m-dr-skeleton-dot"></div>
          <div class="m-dr-skeleton-line"></div>
        </div>
        <div class="m-dr-skeleton-card">
          <div class="m-dr-skeleton-row">
            <div class="m-dr-skeleton-thumb"></div>
            <div class="m-dr-skeleton-body">
              <div class="m-dr-skeleton-line m-dr-skeleton-title"></div>
              <div class="m-dr-skeleton-line m-dr-skeleton-meta"></div>
            </div>
          </div>
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

    <!-- 空状态 -->
    <div v-else-if="records.length === 0" class="m-dr-empty">
      <div class="m-dr-empty-icon">
        <MIcon name="truck" :size="48" />
      </div>
      <div class="m-dr-empty-text">{{ hasFilters ? '暂无符合条件的记录' : '暂无发货记录' }}</div>
      <div class="m-dr-empty-desc">{{ hasFilters ? '请尝试调整筛选条件' : '系统将自动记录发货情况' }}</div>
      <button v-if="hasFilters" type="button" class="m-dr-btn m-dr-btn-primary m-dr-btn-sm" @click="clearFilters">清除筛选</button>
    </div>

    <!-- 时间线列表 -->
    <div v-else class="m-dr-timeline">
      <div
        v-for="row in records"
        :key="row.id"
        class="m-dr-tl-item"
      >
        <div class="m-dr-tl-rail">
          <div class="m-dr-tl-dot" :class="statusTagClass(row)"></div>
          <div class="m-dr-tl-line"></div>
        </div>
        <div class="m-dr-tl-content">
          <div class="m-dr-tl-time">{{ displayTime(row) }}</div>
          <div class="m-dr-tl-card" @click="showDetail(row)">
            <div class="m-dr-tl-card-head">
              <div class="m-dr-tl-card-img-wrap">
                <img
                  v-if="row.goodsCoverPic"
                  :src="row.goodsCoverPic"
                  :alt="row.goodsTitleText"
                  class="m-dr-tl-card-img"
                  referrerpolicy="no-referrer"
                  @error="onImgError($event, row)"
                />
                <div v-else class="m-dr-tl-card-img-placeholder">
                  <MIcon name="bag" :size="20" />
                </div>
              </div>
              <div class="m-dr-tl-card-info">
                <div class="m-dr-tl-card-name" :title="row.goodsTitleText">{{ row.goodsTitleText || '未命名商品' }}</div>
                <div class="m-dr-tl-card-order" :title="row.orderId">订单 {{ row.orderId || '-' }}</div>
              </div>
              <span class="m-dr-tag" :class="statusTagClass(row)">{{ row.deliveryStatusText }}</span>
            </div>
            <div class="m-dr-tl-card-tags">
              <span class="m-dr-tag m-dr-tag-light">{{ row.timingText }}</span>
              <span class="m-dr-tag m-dr-tag-gray">{{ row.deliveryModeText }}</span>
              <span v-if="accountLabel(row)" class="m-dr-tag m-dr-tag-blue">{{ accountLabel(row) }}</span>
            </div>
            <div v-if="deliveryContentPreview(row)" class="m-dr-tl-card-content">
              {{ deliveryContentPreview(row) }}
            </div>
            <div class="m-dr-tl-card-foot">
              <span v-if="row.deliveryProgressText && row.deliveryProgressText !== '0 / 0'" class="m-dr-tl-card-progress">
                进度 {{ row.deliveryProgressText }}
              </span>
              <span class="m-dr-tl-card-arrow">
                <MIcon name="chevronRight" :size="16" />
              </span>
            </div>
          </div>
        </div>
      </div>

      <div v-if="loadingMore" class="m-dr-loading-more">加载中...</div>
      <div v-else-if="hasMore" class="m-dr-load-more">
        <button type="button" class="m-dr-btn m-dr-btn-outline" @click="loadMore">加载更多</button>
      </div>
      <div v-else-if="records.length > 0" class="m-dr-no-more">没有更多记录</div>
    </div>

    <div class="m-dr-safe-bottom"></div>

    <!-- 筛选 sheet -->
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
            type="button"
            class="m-dr-sheet-option"
            :class="{ 'm-dr-sheet-option--active': isOptionSelected(activeFilter, opt) }"
            @click="selectFilterOption(activeFilter, opt)"
          >
            <span>{{ opt.label }}</span>
            <MIcon v-if="isOptionSelected(activeFilter, opt)" name="check" :size="18" class="m-dr-sheet-check" />
          </button>
        </div>
      </div>
      <div class="m-dr-sheet-footer">
        <button type="button" class="m-dr-btn m-dr-btn-outline" @click="resetFilter(activeFilter)">重置</button>
        <button type="button" class="m-dr-btn m-dr-btn-primary" @click="applyFilter">确定</button>
      </div>
    </div>

    <!-- 详情 sheet -->
    <div v-if="detailVisible" class="m-dr-sheet-mask" @click="closeDetail"></div>
    <div v-if="detailVisible" class="m-dr-sheet m-dr-sheet-open m-dr-detail-sheet">
      <div class="m-dr-sheet-header">
        <h3>发货记录详情</h3>
        <button class="m-dr-sheet-close" @click="closeDetail" aria-label="关闭">
          <MIcon name="x" :size="20" />
        </button>
      </div>
      <div class="m-dr-sheet-body">
        <div v-if="detailLoading" class="m-dr-detail-loading">
          <div class="m-dr-spinner"></div>
          <span>加载中...</span>
        </div>
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
                <span v-if="detailView.buyerIdText && detailView.buyerIdText !== '-'" class="m-dr-detail-muted">（{{ detailView.buyerIdText }}）</span>
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
            class="m-dr-detail-block m-dr-detail-block--error"
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
        <button type="button" class="m-dr-btn m-dr-btn-outline" @click="closeDetail">关闭</button>
        <button
          type="button"
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
/* === 根容器 === */
.m-dr {
  padding: var(--m-space-3) var(--m-space-3) 0;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
}

/* === Hero === */
.m-dr-hero {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-4);
  margin-bottom: var(--m-space-3);
  box-shadow: var(--m-shadow-xs);
}
.m-dr-hero-head {
  margin-bottom: var(--m-space-4);
}
.m-dr-hero-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-1);
  background: var(--m-color-info-bg);
  color: var(--m-color-info-text);
  padding: var(--m-space-1) var(--m-space-3);
  border-radius: var(--m-radius-pill);
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-semibold);
  margin-bottom: var(--m-space-3);
}
.m-dr-hero-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--m-radius-circle);
  background: var(--m-color-info);
  animation: m-dr-pulse 1.6s ease-in-out infinite;
}
@keyframes m-dr-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.85); }
}
.m-dr-hero-title {
  margin: 0 0 var(--m-space-1);
  font-size: var(--m-font-size-h1);
  font-weight: var(--m-font-weight-extrabold);
  color: var(--m-color-text-primary);
  line-height: var(--m-line-height-tight);
  letter-spacing: -0.3px;
}
.m-dr-hero-sub {
  margin: 0;
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}

/* === KPI 行 === */
.m-dr-kpi-row {
  display: flex;
  align-items: stretch;
  gap: var(--m-space-2);
  padding: var(--m-space-3);
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-lg);
}
.m-dr-kpi-cell {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--m-space-2) var(--m-space-1);
  cursor: pointer;
  transition: transform 0.15s;
}
.m-dr-kpi-cell:active {
  transform: scale(0.97);
}
.m-dr-kpi-value {
  font-size: var(--m-font-size-hero);
  font-weight: var(--m-font-weight-extrabold);
  color: var(--m-color-text-primary);
  line-height: var(--m-line-height-tight);
  font-variant-numeric: tabular-nums;
  margin-bottom: var(--m-space-1);
}
.m-dr-kpi-value--green {
  color: var(--m-color-success);
}
.m-dr-kpi-value--orange {
  color: var(--m-color-warning);
}
.m-dr-kpi-value--blue {
  color: var(--m-color-info);
}
.m-dr-kpi-label {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  font-weight: var(--m-font-weight-medium);
}
.m-dr-kpi-divider {
  width: 1px;
  background: var(--m-color-border-light);
  align-self: stretch;
  margin: var(--m-space-1) 0;
}

/* === 搜索 === */
.m-dr-search-wrap {
  margin-bottom: var(--m-space-3);
}
.m-dr-search {
  position: relative;
  display: flex;
  align-items: center;
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-lg);
  padding: 0 var(--m-space-4);
  height: 40px;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.m-dr-search:focus-within {
  border-color: var(--m-color-primary);
  box-shadow: 0 0 0 3px var(--m-color-primary-bg);
}
.m-dr-search-icon {
  color: var(--m-color-text-tertiary);
  flex-shrink: 0;
  margin-right: var(--m-space-2);
}
.m-dr-search-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: var(--m-font-size-body);
  color: var(--m-color-text-primary);
  font-family: var(--m-font-family);
  min-width: 0;
}
.m-dr-search-input::placeholder {
  color: var(--m-color-text-placeholder);
}
.m-dr-search-clear {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-tertiary);
  border-radius: var(--m-radius-circle);
  cursor: pointer;
  flex-shrink: 0;
  margin-left: var(--m-space-2);
  padding: 0;
}
.m-dr-search-clear:active {
  background: var(--m-color-border);
}

/* === 筛选 chips === */
.m-dr-filter-bar {
  margin-bottom: var(--m-space-3);
}
.m-dr-filter-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--m-space-2);
}
.m-dr-filter-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-1);
  height: 32px;
  padding: 0 var(--m-space-3);
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-secondary);
  font-weight: var(--m-font-weight-medium);
  cursor: pointer;
  transition: all 0.15s;
  font-family: var(--m-font-family);
  white-space: nowrap;
  overflow: hidden;
}
.m-dr-filter-chip span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-dr-filter-chip--active {
  background: var(--m-color-primary-bg);
  border-color: var(--m-color-primary);
  color: var(--m-color-primary);
}

/* === 工具栏 === */
.m-dr-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--m-space-3);
  padding: 0 var(--m-space-1);
}
.m-dr-count {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}
.m-dr-count b {
  color: var(--m-color-text-primary);
  font-weight: var(--m-font-weight-semibold);
  font-variant-numeric: tabular-nums;
}

/* === 按钮 === */
.m-dr-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-1);
  height: 36px;
  padding: 0 var(--m-space-4);
  border: 1px solid transparent;
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-medium);
  cursor: pointer;
  transition: all 0.15s;
  font-family: var(--m-font-family);
  background: transparent;
  color: var(--m-color-text-primary);
}
.m-dr-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.m-dr-btn-primary {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  border-color: var(--m-color-primary);
}
.m-dr-btn-primary:not(:disabled):active {
  background: var(--m-color-primary-active);
  border-color: var(--m-color-primary-active);
}
.m-dr-btn-outline {
  background: var(--m-color-bg-card);
  border-color: var(--m-color-border);
  color: var(--m-color-text-secondary);
}
.m-dr-btn-outline:not(:disabled):active {
  background: var(--m-color-bg-hover);
}
.m-dr-btn-sm {
  height: 28px;
  padding: 0 var(--m-space-3);
  font-size: var(--m-font-size-caption);
  border-radius: var(--m-radius-lg);
}

/* === 骨架屏 === */
.m-dr-skeleton-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-3);
}
.m-dr-skeleton-item {
  display: flex;
  gap: var(--m-space-3);
}
.m-dr-skeleton-rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 12px;
  flex-shrink: 0;
  padding-top: var(--m-space-2);
}
.m-dr-skeleton-dot {
  width: 10px;
  height: 10px;
  border-radius: var(--m-radius-circle);
  background: var(--m-color-bg-subtle);
  flex-shrink: 0;
}
.m-dr-skeleton-line {
  flex: 1;
  width: 2px;
  background: var(--m-color-bg-subtle);
  margin-top: var(--m-space-1);
  min-height: 60px;
}
.m-dr-skeleton-card {
  flex: 1;
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-3);
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
  box-shadow: var(--m-shadow-xs);
}
.m-dr-skeleton-row {
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
}
.m-dr-skeleton-thumb {
  width: 44px;
  height: 44px;
  border-radius: var(--m-radius-md);
  background: var(--m-color-bg-subtle);
  flex-shrink: 0;
}
.m-dr-skeleton-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
}
.m-dr-skeleton-line {
  height: 12px;
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-sm);
}
.m-dr-skeleton-title {
  width: 60%;
}
.m-dr-skeleton-meta {
  width: 40%;
  height: 10px;
}
.m-dr-skeleton-tags {
  display: flex;
  gap: var(--m-space-2);
}
.m-dr-skeleton-tag {
  width: 56px;
  height: 18px;
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-pill);
}
.m-dr-skeleton-card .m-dr-skeleton-line,
.m-dr-skeleton-card .m-dr-skeleton-thumb,
.m-dr-skeleton-card .m-dr-skeleton-tag,
.m-dr-skeleton-dot,
.m-dr-skeleton-line {
  background: var(--m-color-bg-subtle);
  animation: m-dr-pulse-soft 1.4s ease-in-out infinite;
}
@keyframes m-dr-pulse-soft {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* === 空状态 === */
.m-dr-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--m-space-10) var(--m-space-4);
  text-align: center;
}
.m-dr-empty-icon {
  width: 72px;
  height: 72px;
  border-radius: var(--m-radius-circle);
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: var(--m-space-4);
}
.m-dr-empty-text {
  font-size: var(--m-font-size-body);
  color: var(--m-color-text-primary);
  font-weight: var(--m-font-weight-medium);
  margin-bottom: var(--m-space-1);
}
.m-dr-empty-desc {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  margin-bottom: var(--m-space-4);
}

/* === 时间线列表 === */
.m-dr-timeline {
  display: flex;
  flex-direction: column;
}
.m-dr-tl-item {
  display: flex;
  gap: var(--m-space-3);
  align-items: stretch;
}
.m-dr-tl-rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 14px;
  flex-shrink: 0;
  padding-top: var(--m-space-3);
}
.m-dr-tl-dot {
  width: 10px;
  height: 10px;
  border-radius: var(--m-radius-circle);
  background: var(--m-color-text-disabled);
  flex-shrink: 0;
  border: 2px solid var(--m-color-bg-card);
  z-index: 1;
}
.m-dr-tl-dot.m-dr-tag-green {
  background: var(--m-color-success);
}
.m-dr-tl-dot.m-dr-tag-red {
  background: var(--m-color-danger);
}
.m-dr-tl-dot.m-dr-tag-orange {
  background: var(--m-color-warning);
}
.m-dr-tl-dot.m-dr-tag-blue {
  background: var(--m-color-info);
}
.m-dr-tl-dot.m-dr-tag-gray {
  background: var(--m-color-text-disabled);
}
.m-dr-tl-line {
  flex: 1;
  width: 2px;
  background: var(--m-color-border-light);
  margin-top: var(--m-space-1);
  min-height: 24px;
}
.m-dr-tl-item:last-child .m-dr-tl-line {
  display: none;
}
.m-dr-tl-content {
  flex: 1;
  min-width: 0;
  padding-bottom: var(--m-space-3);
}
.m-dr-tl-time {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  font-weight: var(--m-font-weight-medium);
  margin-bottom: var(--m-space-2);
  font-variant-numeric: tabular-nums;
}
.m-dr-tl-card {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-3);
  box-shadow: var(--m-shadow-xs);
  transition: transform 0.15s;
  cursor: pointer;
}
.m-dr-tl-card:active {
  transform: scale(0.99);
}
.m-dr-tl-card-head {
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
  margin-bottom: var(--m-space-2);
}
.m-dr-tl-card-img-wrap {
  width: 44px;
  height: 44px;
  border-radius: var(--m-radius-md);
  overflow: hidden;
  flex-shrink: 0;
  background: var(--m-color-bg-subtle);
  display: flex;
  align-items: center;
  justify-content: center;
}
.m-dr-tl-card-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.m-dr-tl-card-img-placeholder {
  color: var(--m-color-text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
}
.m-dr-tl-card-info {
  flex: 1;
  min-width: 0;
}
.m-dr-tl-card-name {
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  line-height: var(--m-line-height-tight);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: var(--m-space-1);
}
.m-dr-tl-card-order {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.m-dr-tl-card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-2);
}
.m-dr-tl-card-content {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-secondary);
  line-height: var(--m-line-height-base);
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-md);
  padding: var(--m-space-2) var(--m-space-3);
  margin-bottom: var(--m-space-2);
  word-break: break-all;
}
.m-dr-tl-card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--m-space-2);
}
.m-dr-tl-card-progress {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  font-variant-numeric: tabular-nums;
}
.m-dr-tl-card-arrow {
  color: var(--m-color-text-disabled);
  display: flex;
  align-items: center;
}

/* === 标签 === */
.m-dr-tag {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 var(--m-space-2);
  border-radius: var(--m-radius-sm);
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-medium);
  line-height: 1;
  white-space: nowrap;
}
.m-dr-tag-green {
  background: var(--m-color-success-bg);
  color: var(--m-color-success-text);
}
.m-dr-tag-red {
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger-text);
}
.m-dr-tag-orange {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning-text);
}
.m-dr-tag-blue {
  background: var(--m-color-info-bg);
  color: var(--m-color-info-text);
}
.m-dr-tag-gray {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
}
.m-dr-tag-light {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-tertiary);
}

/* === 加载更多 === */
.m-dr-loading-more,
.m-dr-no-more {
  text-align: center;
  padding: var(--m-space-4) 0;
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}
.m-dr-load-more {
  display: flex;
  justify-content: center;
  padding: var(--m-space-3) 0;
}
.m-dr-safe-bottom {
  height: var(--m-space-6);
}

/* === Sheet === */
.m-dr-sheet-mask {
  position: fixed;
  inset: 0;
  background: var(--m-mask-modal);
  z-index: 100;
  animation: m-dr-mask-in 0.2s ease-out;
}
@keyframes m-dr-mask-in {
  from { opacity: 0; }
  to { opacity: 1; }
}
.m-dr-sheet {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  max-height: 80vh;
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-xl) var(--m-radius-xl) 0 0;
  z-index: 101;
  display: flex;
  flex-direction: column;
  transform: translateY(100%);
  transition: transform 0.25s ease-out;
  box-shadow: var(--m-shadow-xs);
}
.m-dr-sheet-open {
  transform: translateY(0);
}
.m-dr-sheet-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-space-4);
  flex-shrink: 0;
}
.m-dr-sheet-header h3 {
  margin: 0;
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
}
.m-dr-sheet-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-tertiary);
  border-radius: var(--m-radius-circle);
  cursor: pointer;
  padding: 0;
}
.m-dr-sheet-close:active {
  background: var(--m-color-border);
}
.m-dr-sheet-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--m-space-4);
  -webkit-overflow-scrolling: touch;
}
.m-dr-sheet-search {
  position: relative;
  display: flex;
  align-items: center;
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-lg);
  padding: 0 var(--m-space-3);
  height: 36px;
  margin-bottom: var(--m-space-3);
}
.m-dr-sheet-search-icon {
  color: var(--m-color-text-tertiary);
  flex-shrink: 0;
  margin-right: var(--m-space-2);
}
.m-dr-sheet-search-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-primary);
  font-family: var(--m-font-family);
  min-width: 0;
}
.m-dr-sheet-search-input::placeholder {
  color: var(--m-color-text-placeholder);
}
.m-dr-sheet-options {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-1);
}
.m-dr-sheet-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: var(--m-space-3);
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-primary);
  cursor: pointer;
  transition: all 0.15s;
  font-family: var(--m-font-family);
  text-align: left;
}
.m-dr-sheet-option:active {
  background: var(--m-color-bg-hover);
}
.m-dr-sheet-option--active {
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
  font-weight: var(--m-font-weight-semibold);
}
.m-dr-sheet-check {
  color: var(--m-color-primary);
  flex-shrink: 0;
}
.m-dr-sheet-footer {
  display: flex;
  gap: var(--m-space-3);
  padding: var(--m-space-4);
  flex-shrink: 0;
}
.m-dr-sheet-footer .m-dr-btn {
  flex: 1;
}

/* === 详情 sheet === */
.m-dr-detail-sheet {
  max-height: 90vh;
}
.m-dr-detail-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--m-space-8) 0;
  gap: var(--m-space-3);
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-caption);
}
.m-dr-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--m-color-border);
  border-top-color: var(--m-color-primary);
  border-radius: var(--m-radius-circle);
  animation: m-dr-spin 0.8s linear infinite;
}
@keyframes m-dr-spin {
  to { transform: rotate(360deg); }
}
.m-dr-detail-goods {
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
  padding: var(--m-space-3);
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-lg);
  margin-bottom: var(--m-space-4);
}
.m-dr-detail-thumb {
  width: 56px;
  height: 56px;
  border-radius: var(--m-radius-md);
  object-fit: cover;
  flex-shrink: 0;
}
.m-dr-detail-thumb-placeholder {
  width: 56px;
  height: 56px;
  border-radius: var(--m-radius-md);
  background: var(--m-color-bg-card);
  color: var(--m-color-text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-dr-detail-goods-info {
  flex: 1;
  min-width: 0;
}
.m-dr-detail-goods-name {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  line-height: var(--m-line-height-tight);
  margin-bottom: var(--m-space-1);
  word-break: break-all;
}
.m-dr-detail-goods-id {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  font-variant-numeric: tabular-nums;
}
.m-dr-detail-grid {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-1);
  margin-bottom: var(--m-space-4);
}
.m-dr-detail-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--m-space-3);
  padding: var(--m-space-2) 0;
}
.m-dr-detail-label {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  flex-shrink: 0;
  min-width: 64px;
}
.m-dr-detail-value {
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-primary);
  text-align: right;
  word-break: break-all;
  font-variant-numeric: tabular-nums;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--m-space-1);
  flex: 1;
}
.m-dr-detail-muted {
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-caption);
}
.m-dr-detail-block {
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3);
  margin-bottom: var(--m-space-3);
}
.m-dr-detail-block-title {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  font-weight: var(--m-font-weight-semibold);
  margin-bottom: var(--m-space-2);
}
.m-dr-detail-block-content {
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-primary);
  line-height: var(--m-line-height-base);
  word-break: break-all;
  white-space: pre-wrap;
}
.m-dr-detail-block--error {
  background: var(--m-color-danger-bg);
}
.m-dr-detail-block--error .m-dr-detail-block-title {
  color: var(--m-color-danger-text);
}
.m-dr-detail-block--error .m-dr-detail-block-content {
  color: var(--m-color-danger-text);
}

/* === 响应式（窄屏）=== */
@media (max-width: 360px) {
  .m-dr {
    padding: var(--m-space-2) var(--m-space-2) 0;
  }
  .m-dr-hero {
    padding: var(--m-space-3);
  }
  .m-dr-kpi-row {
    padding: var(--m-space-2);
    gap: var(--m-space-1);
  }
  .m-dr-kpi-value {
    font-size: var(--m-font-size-h1);
  }
  .m-dr-filter-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .m-dr-tl-card {
    padding: var(--m-space-2);
  }
  .m-dr-tl-card-img-wrap {
    width: 40px;
    height: 40px;
  }
}
</style>
