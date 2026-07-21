<template>
  <div class="m-products-page">
    <div v-if="statsLoading" class="m-stats-skeleton">
      <div v-for="i in 6" :key="i" class="m-stat-card-skeleton"></div>
    </div>
    <div v-else class="m-stats-grid">
      <button
        v-for="card in statCards"
        :key="card.key"
        class="m-stat-card"
        :class="{ active: activeFilter === card.key }"
        @click="selectFilter(card.key)"
      >
        <div class="m-stat-icon" :style="{ background: card.iconBg }">
          <MIcon :name="card.icon" :size="20" :color="card.iconColor" />
        </div>
        <div class="m-stat-info">
          <div class="m-stat-label">{{ card.label }}</div>
          <div class="m-stat-value-row">
            <span class="m-stat-value">{{ card.value }}</span>
            <span v-if="card.trend" class="m-stat-trend" :class="card.trendClass">
              <MIcon :name="card.trendIcon" :size="10" />
              {{ card.trend }}
            </span>
          </div>
        </div>
      </button>
    </div>

    <div class="m-tabs-bar">
      <div class="m-tabs-scroll">
        <button
          v-for="tab in statusTabs"
          :key="tab.key"
          class="m-tab-item"
          :class="{ active: activeStatus === tab.key }"
          @click="selectStatus(tab.key)"
        >
          {{ tab.label }}
          <span v-if="tab.count != null" class="m-tab-count">{{ tab.count }}</span>
        </button>
        <button class="m-tab-item m-tab-more" @click="showMoreTabs = !showMoreTabs">
          更多
          <MIcon name="chevronDown" :size="14" :class="{ rotated: showMoreTabs }" />
        </button>
      </div>
      <div v-if="showMoreTabs" class="m-more-tabs-panel">
        <button
          v-for="tab in moreStatusTabs"
          :key="tab.key"
          class="m-more-tab-item"
          :class="{ active: activeStatus === tab.key }"
          @click="selectStatus(tab.key); showMoreTabs = false"
        >
          {{ tab.label }}
        </button>
      </div>
    </div>

    <div class="m-toolbar">
      <button class="m-toolbar-btn" @click="showSortMenu = true">
        <span>{{ currentSortLabel }}</span>
        <MIcon name="chevronDown" :size="14" />
      </button>
      <button class="m-toolbar-btn m-toolbar-filter" @click="showFilterSheet = true">
        <MIcon name="filter" :size="16" />
        <span>筛选</span>
        <span v-if="activeFilterCount > 0" class="m-filter-badge">{{ activeFilterCount }}</span>
      </button>
    </div>

    <div v-if="loading" class="m-list-skeleton">
      <div v-for="i in 5" :key="i" class="m-list-item-skeleton">
        <div class="m-skeleton-img"></div>
        <div class="m-skeleton-info">
          <div class="m-skeleton-line w-70"></div>
          <div class="m-skeleton-line w-40"></div>
          <div class="m-skeleton-line w-50"></div>
        </div>
      </div>
    </div>

    <MobileUnavailableState v-else-if="loadError" compact title="加载失败" :description="loadError" @retry="loadProducts" />

    <div v-else-if="filteredProducts.length === 0" class="m-empty-state">
      <div class="m-empty-icon">
        <MIcon name="bag" :size="48" />
      </div>
      <div class="m-empty-title">{{ searchKeyword ? '未找到相关商品' : '暂无商品' }}</div>
      <div class="m-empty-desc">{{ searchKeyword ? '尝试更换关键词或清除筛选条件' : '点击右上角加号发布您的第一个商品' }}</div>
      <div class="m-empty-actions">
        <button v-if="searchKeyword || activeFilter !== 'all'" class="m-empty-btn m-empty-btn-secondary" @click="clearAllFilters">
          清除筛选
        </button>
      </div>
    </div>

    <div v-else class="m-product-list">
      <div
        v-for="prod in filteredProducts"
        :key="prod.id || prod.itemId"
        class="m-product-item"
      >
        <div class="m-product-main" @click="openDetail(prod)">
          <div class="m-product-cover">
            <img
              v-if="coverUrlOf(prod)"
              :src="coverUrlOf(prod)"
              :alt="prod.name || prod.title"
              class="m-product-img"
              @error="onImgError($event, prod)"
              loading="lazy"
            />
            <div v-else class="m-product-cover-placeholder">
              <MIcon name="bag" :size="24" />
            </div>
          </div>
          <div class="m-product-info">
            <div class="m-product-name">{{ prod.name || prod.title || '未命名商品' }}</div>
            <div class="m-product-price-row">
              <span class="m-product-price">¥{{ formatPrice(prod.price ?? prod.soldPrice) }}</span>
            </div>
            <div class="m-product-meta-row">
              <span
                class="m-product-stock"
                :class="{
                  'm-stock-warning': prod.stock <= 0,
                  'm-stock-low': prod.stock > 0 && prod.stock <= (prod.lowStockThreshold || 10)
                }"
              >
                库存 {{ prod.stock != null ? prod.stock : '—' }}
              </span>
              <span class="m-product-status-badge" :class="statusBadgeClass(prod)">
                {{ statusText(prod) }}
              </span>
            </div>
          </div>
        </div>
        <div class="m-product-actions">
          <button
            class="m-toggle-switch"
            :class="{
              on: isOnShelf(prod),
              disabled: isSwitchDisabled(prod),
              loading: prod._toggling
            }"
            :disabled="isSwitchDisabled(prod) || prod._toggling"
            @click.stop="toggleOnShelf(prod)"
            :aria-label="isOnShelf(prod) ? '下架商品' : '上架商品'"
          >
            <span class="m-toggle-knob"></span>
          </button>
          <button class="m-product-more" @click.stop="showProductMenu = prod" aria-label="更多操作">
            <MIcon name="moreVertical" :size="18" />
          </button>
        </div>
      </div>
    </div>

    <div v-if="!loading && !loadError && filteredProducts.length > 0" class="m-pagination">
      <span class="m-pagination-total">共 {{ total }} 条</span>
      <div class="m-pagination-pages">
        <button
          class="m-page-btn"
          :disabled="currentPage <= 1"
          @click="goToPage(currentPage - 1)"
          aria-label="上一页"
        >
          <MIcon name="chevronLeft" :size="16" />
        </button>
        <button
          v-for="p in visiblePages"
          :key="p"
          class="m-page-btn"
          :class="{ active: p === currentPage }"
          @click="goToPage(p)"
        >
          {{ p }}
        </button>
        <button
          class="m-page-btn"
          :disabled="currentPage >= totalPages"
          @click="goToPage(currentPage + 1)"
          aria-label="下一页"
        >
          <MIcon name="chevronRight" :size="16" />
        </button>
      </div>
    </div>

    <div v-if="showProductMenu" class="m-menu-mask" @click="showProductMenu = null"></div>
    <div v-if="showProductMenu" class="m-action-menu">
      <button class="m-action-item" @click="doViewDetail">
        <MIcon name="eye" :size="18" />
        <span>查看详情</span>
      </button>
      <button class="m-action-item" @click="doEditProduct">
        <MIcon name="edit" :size="18" />
        <span>编辑商品</span>
      </button>
      <button class="m-action-item" @click="doCopyProduct">
        <MIcon name="copy" :size="18" />
        <span>复制商品</span>
      </button>
      <button class="m-action-item" @click="doUpdateStock">
        <MIcon name="database" :size="18" />
        <span>调整库存</span>
      </button>
      <button v-if="isOnShelf(showProductMenu)" class="m-action-item m-action-warn" @click="doQuickOffShelf">
        <MIcon name="arrowDown" :size="18" />
        <span>快速下架</span>
      </button>
      <button v-else class="m-action-item" @click="doQuickOnShelf">
        <MIcon name="arrowUp" :size="18" />
        <span>快速上架</span>
      </button>
      <button class="m-action-item m-action-danger" @click="doDeleteProduct">
        <MIcon name="trash" :size="18" />
        <span>删除商品</span>
      </button>
      <button class="m-action-item m-action-cancel" @click="showProductMenu = null">
        取消
      </button>
    </div>

    <div v-if="showSortMenu" class="m-menu-mask" @click="showSortMenu = false"></div>
    <div v-if="showSortMenu" class="m-bottom-sheet">
      <div class="m-sheet-handle"></div>
      <div class="m-sheet-title">排序方式</div>
      <button
        v-for="sort in sortOptions"
        :key="sort.key"
        class="m-sheet-option"
        :class="{ active: currentSort === sort.key }"
        @click="selectSort(sort.key)"
      >
        <span>{{ sort.label }}</span>
        <MIcon v-if="currentSort === sort.key" name="check" :size="18" color="#0d6bff" />
      </button>
    </div>

    <div v-if="showFilterSheet" class="m-menu-mask" @click="showFilterSheet = false"></div>
    <div v-if="showFilterSheet" class="m-bottom-sheet m-filter-sheet">
      <div class="m-sheet-handle"></div>
      <div class="m-sheet-header">
        <div class="m-sheet-title">筛选条件</div>
        <button class="m-sheet-reset" @click="resetFilters">重置</button>
      </div>
      <div class="m-filter-content">
        <div class="m-filter-group">
          <div class="m-filter-label">商品状态</div>
          <div class="m-filter-options">
            <button
              v-for="opt in filterStatusOptions"
              :key="opt.key"
              class="m-filter-chip"
              :class="{ active: filterStatus === opt.key }"
              @click="filterStatus = opt.key"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>
      </div>
      <div class="m-sheet-footer">
        <button class="m-sheet-btn m-sheet-btn-cancel" @click="showFilterSheet = false">取消</button>
        <button class="m-sheet-btn m-sheet-btn-confirm" @click="applyFilters">确定</button>
      </div>
    </div>

    <div v-if="showConfirmDialog" class="m-dialog-mask" @click="showConfirmDialog = null">
      <div class="m-dialog" @click.stop>
        <div class="m-dialog-title">{{ confirmDialog.title }}</div>
        <div class="m-dialog-msg">{{ confirmDialog.message }}</div>
        <div class="m-dialog-actions">
          <button class="m-dialog-btn m-dialog-btn-cancel" @click="cancelConfirm">取消</button>
          <button class="m-dialog-btn m-dialog-btn-confirm" @click="confirmAction">确定</button>
        </div>
      </div>
    </div>

    <div class="m-safe-bottom"></div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import MIcon from './MIcon.vue'
import MobileUnavailableState from './MobileUnavailableState.vue'
import { getGoods, getGoodsStats, deleteGoodsLocal } from '../api/goods.js'
import { offShelfItem, republishItem } from '../api/items.js'
import { resolveTrustedMediaUrl } from '../utils/safeMediaUrl.js'

const props = defineProps({
  searchMode: Boolean,
  searchKeyword: String
})

const emit = defineEmits(['navigate', 'force-desktop', 'back', 'open-detail', 'close-search'])

const products = ref([])
const stats = ref({ total: 0, onShelf: 0, offShelf: 0, lowStock: 0, soldOut: 0, disabled: 0 })
const loading = ref(false)
const statsLoading = ref(false)
const loadError = ref('')
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)
const activeStatus = ref('all')
const activeFilter = ref('all')
const currentSort = ref('default')
const filterStatus = ref('')
const showSortMenu = ref(false)
const showFilterSheet = ref(false)
const showMoreTabs = ref(false)
const showProductMenu = ref(null)
const showConfirmDialog = ref(null)
const confirmAction = ref(() => {})
const searchKeywordInternal = ref('')

const sortOptions = [
  { key: 'default', label: '默认排序' },
  { key: 'newest', label: '创建时间从新到旧' },
  { key: 'oldest', label: '创建时间从旧到新' },
  { key: 'priceAsc', label: '价格从低到高' },
  { key: 'priceDesc', label: '价格从高到低' },
  { key: 'stockAsc', label: '库存从低到高' },
  { key: 'salesDesc', label: '销量从高到低' }
]

const statusTabs = computed(() => [
  { key: 'all', label: '全部', count: stats.value.total || 0 },
  { key: 'onShelf', label: '上架中', count: stats.value.onShelf || 0 },
  { key: 'offShelf', label: '下架中', count: stats.value.offShelf || 0 }
])

const moreStatusTabs = computed(() => [
  { key: 'lowStock', label: '库存预警' },
  { key: 'soldOut', label: '已售罄' },
  { key: 'disabled', label: '已禁用' }
])

const filterStatusOptions = [
  { key: '', label: '全部' },
  { key: 'onShelf', label: '上架中' },
  { key: 'offShelf', label: '下架中' },
  { key: 'soldOut', label: '已售罄' }
]

const statCards = computed(() => [
  { key: 'all', label: '全部商品', value: stats.value.total || 0, trend: '', icon: 'bag', iconBg: 'rgba(13,107,255,0.1)', iconColor: '#0d6bff', trendClass: '', trendIcon: 'arrowUp' },
  { key: 'onShelf', label: '上架中', value: stats.value.onShelf || 0, trend: '', icon: 'pieChart', iconBg: 'rgba(22,191,120,0.1)', iconColor: '#16bf78', trendClass: '', trendIcon: 'arrowUp' },
  { key: 'offShelf', label: '下架中', value: stats.value.offShelf || 0, trend: null, icon: 'arrowDown', iconBg: 'rgba(140,152,174,0.12)', iconColor: '#8c98ae', trendClass: '', trendIcon: 'arrowDown' },
  { key: 'lowStock', label: '库存预警', value: stats.value.lowStock || 0, trend: null, icon: 'alertTriangle', iconBg: 'rgba(255,159,34,0.12)', iconColor: '#ff9f22', trendClass: '', trendIcon: 'alertTriangle' },
  { key: 'soldOut', label: '已售罄', value: stats.value.soldOut || 0, trend: null, icon: 'xCircle', iconBg: 'rgba(255,71,87,0.1)', iconColor: '#ff4757', trendClass: '', trendIcon: 'xCircle' },
  { key: 'disabled', label: '已禁用', value: stats.value.disabled || 0, trend: stats.value.disabled > 0 ? String(stats.value.disabled) : null, icon: 'lock', iconBg: 'rgba(255,71,87,0.1)', iconColor: '#ff4757', trendClass: 'm-trend-down', trendIcon: 'arrowUp' }
])

const currentSortLabel = computed(() => {
  const s = sortOptions.find(o => o.key === currentSort.value)
  return s ? s.label : '默认排序'
})

const activeFilterCount = computed(() => {
  let count = 0
  if (filterStatus.value) count++
  return count
})

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

const visiblePages = computed(() => {
  const pages = []
  const tp = totalPages.value
  const cp = currentPage.value
  if (tp <= 5) {
    for (let i = 1; i <= tp; i++) pages.push(i)
  } else {
    if (cp <= 3) {
      for (let i = 1; i <= 5; i++) pages.push(i)
    } else if (cp >= tp - 2) {
      for (let i = tp - 4; i <= tp; i++) pages.push(i)
    } else {
      for (let i = cp - 2; i <= cp + 2; i++) pages.push(i)
    }
  }
  return pages
})

const filteredProducts = computed(() => {
  let list = [...products.value]
  const kw = searchKeywordInternal.value?.toLowerCase()
  if (kw) {
    list = list.filter(p => {
      const name = (p.name || p.title || '').toLowerCase()
      const id = String(p.id || p.itemId || '').toLowerCase()
      return name.includes(kw) || id.includes(kw)
    })
  }
  const key = activeFilter.value
  if (key === 'onShelf') list = list.filter(p => isOnShelf(p))
  else if (key === 'offShelf') list = list.filter(p => !isOnShelf(p) && !isDisabled(p) && p.stock > 0)
  else if (key === 'lowStock') list = list.filter(p => p.stock > 0 && p.stock <= (p.lowStockThreshold || 10))
  else if (key === 'soldOut') list = list.filter(p => p.stock <= 0)
  else if (key === 'disabled') list = list.filter(p => isDisabled(p))

  if (filterStatus.value === 'onShelf') list = list.filter(p => isOnShelf(p))
  else if (filterStatus.value === 'offShelf') list = list.filter(p => !isOnShelf(p) && !isDisabled(p))
  else if (filterStatus.value === 'soldOut') list = list.filter(p => p.stock <= 0)

  switch (currentSort.value) {
    case 'newest': list.sort((a, b) => (b.createTime || 0) - (a.createTime || 0)); break
    case 'oldest': list.sort((a, b) => (a.createTime || 0) - (b.createTime || 0)); break
    case 'priceAsc': list.sort((a, b) => (a.price || 0) - (b.price || 0)); break
    case 'priceDesc': list.sort((a, b) => (b.price || 0) - (a.price || 0)); break
    case 'stockAsc': list.sort((a, b) => (a.stock || 0) - (b.stock || 0)); break
    case 'salesDesc': list.sort((a, b) => (b.sales || b.soldCount || 0) - (a.sales || a.soldCount || 0)); break
  }
  return list
})

watch(() => props.searchKeyword, (val) => {
  searchKeywordInternal.value = val || ''
})

function onSearch(kw) {
  searchKeywordInternal.value = kw || ''
  currentPage.value = 1
}

defineExpose({
  onSearch,
  refreshProduct
})

function isOnShelf(p) {
  return p.status === 1 || p.onShelf === true || p.statusCode === 1
}

function isDisabled(p) {
  return p.status === 3 || p.disabled === true || p.statusCode === 3
}

function isSwitchDisabled(p) {
  return isDisabled(p)
}

function statusText(p) {
  if (isDisabled(p)) return '已禁用'
  if (p.stock <= 0) return '已售罄'
  if (isOnShelf(p)) return '上架中'
  return '下架中'
}

function statusBadgeClass(p) {
  if (isDisabled(p)) return 'm-badge-disabled'
  if (p.stock <= 0) return 'm-badge-soldout'
  if (isOnShelf(p)) return 'm-badge-onshelf'
  return 'm-badge-offshelf'
}

function formatPrice(price) {
  if (price == null || price === '') return '—'
  const num = Number(price)
  if (isNaN(num)) return String(price)
  return Number.isInteger(num) ? String(num) : num.toFixed(2)
}

function onImgError(e, prod) {
  prod.coverPic = ''
  prod.imageUrl = ''
  prod.mainImage = ''
}

// 清洗商品封面图 URL：过滤脏数据/历史格式及非白名单域名
function coverUrlOf(prod) {
  if (!prod) return ''
  return resolveTrustedMediaUrl(prod.coverPic || prod.imageUrl || prod.mainImage || '')
}

function openDetail(prod) {
  emit('open-detail', prod)
}

function doViewDetail() {
  const p = showProductMenu.value
  showProductMenu.value = null
  if (p) openDetail(p)
}

function doEditProduct() {
  const p = showProductMenu.value
  showProductMenu.value = null
  if (p) openDetail(p)
}

function doCopyProduct() {
  showProductMenu.value = null
  showToast('复制商品功能请在桌面端使用')
}

function doUpdateStock() {
  showProductMenu.value = null
  showToast('库存调整请在详情页或桌面端操作')
}

function doQuickOffShelf() {
  const p = showProductMenu.value
  showProductMenu.value = null
  if (p) toggleOnShelf(p)
}

function doQuickOnShelf() {
  const p = showProductMenu.value
  showProductMenu.value = null
  if (p) toggleOnShelf(p)
}

function doDeleteProduct() {
  const p = showProductMenu.value
  showProductMenu.value = null
  if (!p) return
  showConfirmDialog.value = {
    title: '删除商品',
    message: '确定要删除该商品吗？删除后不可恢复。'
  }
  confirmAction.value = async () => {
    try {
      const id = p.id || p.itemId
      if (id) await deleteGoodsLocal(id)
      products.value = products.value.filter(x => (x.id || x.itemId) !== id)
      stats.value.total = Math.max(0, (stats.value.total || 0) - 1)
      total.value = Math.max(0, total.value - 1)
      showToast('删除成功')
    } catch (e) {
      showToast(e?.message || '删除失败', 'error')
    }
    showConfirmDialog.value = null
  }
}

function cancelConfirm() {
  showConfirmDialog.value = null
  confirmAction.value = () => {}
}

async function toggleOnShelf(prod) {
  if (prod._toggling) return
  const prev = isOnShelf(prod)
  prod._toggling = true
  try {
    const id = prod.id || prod.itemId
    const accountId = prod.accountId || prod.xianyuAccountId
    if (!id) throw new Error('商品ID不存在')
    if (prev) {
      await offShelfItem({ id, accountId })
      prod.status = 0
      prod.onShelf = false
      prod.statusCode = 0
      stats.value.onShelf = Math.max(0, (stats.value.onShelf || 0) - 1)
      stats.value.offShelf = (stats.value.offShelf || 0) + 1
      showToast('已下架')
    } else {
      if (prod.stock <= 0) {
        showToast('库存为0，无法上架', 'error')
        prod._toggling = false
        return
      }
      await republishItem({ id, accountId })
      prod.status = 1
      prod.onShelf = true
      prod.statusCode = 1
      stats.value.offShelf = Math.max(0, (stats.value.offShelf || 0) - 1)
      stats.value.onShelf = (stats.value.onShelf || 0) + 1
      showToast('已上架')
    }
  } catch (e) {
    showToast(e?.message || '操作失败', 'error')
  } finally {
    prod._toggling = false
  }
}

function selectFilter(key) {
  activeFilter.value = key
  activeStatus.value = key === 'all' ? 'all' : key
  currentPage.value = 1
}

function selectStatus(key) {
  activeStatus.value = key
  activeFilter.value = key
  currentPage.value = 1
}

function selectSort(key) {
  currentSort.value = key
  showSortMenu.value = false
  currentPage.value = 1
}

function resetFilters() {
  filterStatus.value = ''
}

function applyFilters() {
  showFilterSheet.value = false
  currentPage.value = 1
}

function clearAllFilters() {
  activeFilter.value = 'all'
  activeStatus.value = 'all'
  filterStatus.value = ''
  searchKeywordInternal.value = ''
  currentPage.value = 1
  emit('close-search')
}

function goToPage(p) {
  if (p < 1 || p > totalPages.value) return
  currentPage.value = p
  loadProducts()
  nextTick(() => {
    const list = document.querySelector('.m-product-list')
    if (list) list.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

async function loadStats() {
  statsLoading.value = true
  try {
    const res = await getGoodsStats()
    const d = res?.data || {}
    stats.value = {
      total: d.total || d.totalCount || 0,
      onShelf: d.onShelf || d.onlineCount || d.listingCount || 0,
      offShelf: d.offShelf || d.offlineCount || d.delistingCount || 0,
      lowStock: d.lowStock || d.warningCount || 0,
      soldOut: d.soldOut || d.outOfStockCount || 0,
      disabled: d.disabled || d.bannedCount || 0
    }
  } catch {
    stats.value = { total: 0, onShelf: 0, offShelf: 0, lowStock: 0, soldOut: 0, disabled: 0 }
  } finally {
    statsLoading.value = false
  }
}

async function loadProducts() {
  loading.value = true
  loadError.value = ''
  try {
    const params = {
      page: currentPage.value,
      pageSize: pageSize.value
    }
    const res = await getGoods(params)
    const data = res?.data
    if (data?.records) {
      products.value = data.records
      total.value = data.total || data.totalCount || data.records.length
    } else if (data?.list) {
      products.value = data.list
      total.value = data.total || data.list.length
    } else if (Array.isArray(data)) {
      products.value = data
      total.value = data.length
    } else {
      products.value = []
      total.value = 0
    }
  } catch (error) {
    products.value = []
    loadError.value = error?.message || '加载失败，请检查网络后重试'
  } finally {
    loading.value = false
  }
}

function refreshProduct(updated) {
  if (!updated) return
  const id = updated.id || updated.itemId
  const idx = products.value.findIndex(p => (p.id || p.itemId) === id)
  if (idx >= 0) {
    products.value[idx] = { ...products.value[idx], ...updated }
  }
}

let toastTimer = null
function showToast(msg, type = 'success') {
  let el = document.querySelector('.m-toast-global')
  if (!el) {
    el = document.createElement('div')
    el.className = 'm-toast-global'
    document.body.appendChild(el)
  }
  el.textContent = msg
  el.className = `m-toast-global m-toast-${type} m-toast-show`
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    el.className = 'm-toast-global'
  }, 2000)
}

function goToPublish() {
  emit('navigate', 'product-publish')
}

onMounted(() => {
  loadStats()
  loadProducts()
})
</script>

<style scoped>
.m-products-page {
  padding: 0 12px;
}

.m-stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  padding: 12px 0;
}

.m-stats-skeleton {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  padding: 12px 0;
}

.m-stat-card-skeleton {
  background: white;
  border-radius: 16px;
  height: 80px;
  animation: m-skeleton-pulse 1.5s ease-in-out infinite;
}

.m-stat-card {
  background: white;
  border: 1px solid #eef2f8;
  border-radius: 16px;
  padding: 14px;
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;
  box-shadow: 0 2px 8px rgba(31,53,94,0.04);
}

.m-stat-card:active {
  transform: scale(0.98);
}

.m-stat-card.active {
  border-color: #0d6bff;
  background: linear-gradient(135deg, #f0f6ff, #e8f1ff);
  box-shadow: 0 4px 16px rgba(13,107,255,0.12);
}

.m-stat-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.m-stat-info {
  flex: 1;
  min-width: 0;
}

.m-stat-label {
  font-size: 12px;
  color: #72809a;
  margin-bottom: 4px;
}

.m-stat-value-row {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.m-stat-value {
  font-size: 20px;
  font-weight: 800;
  color: #15213d;
  line-height: 1;
}

.m-stat-trend {
  font-size: 11px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 1px;
  color: #16bf78;
}

.m-stat-trend.m-trend-down {
  color: #ff4757;
}

.m-tabs-bar {
  position: relative;
  margin-bottom: 10px;
}

.m-tabs-scroll {
  display: flex;
  gap: 4px;
  overflow-x: auto;
  scrollbar-width: none;
  padding-bottom: 2px;
}

.m-tabs-scroll::-webkit-scrollbar { display: none; }

.m-tab-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 10px 16px;
  background: transparent;
  border: none;
  font-size: 14px;
  font-weight: 500;
  color: #5a6a85;
  cursor: pointer;
  position: relative;
  white-space: nowrap;
  border-radius: 10px;
  transition: all 0.15s;
}

.m-tab-item.active {
  color: #0d6bff;
  font-weight: 600;
}

.m-tab-item.active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 24px;
  height: 3px;
  background: #0d6bff;
  border-radius: 2px;
}

.m-tab-count {
  font-size: 12px;
  color: #94a3b8;
}

.m-tab-item.active .m-tab-count {
  color: #0d6bff;
}

.m-tab-more {
  color: #5a6a85;
}

.m-tab-more :deep(svg) {
  transition: transform 0.2s;
}

.m-tab-more :deep(svg).rotated {
  transform: rotate(180deg);
}

.m-more-tabs-panel {
  position: absolute;
  top: 100%;
  right: 0;
  background: white;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(31,53,94,0.12);
  padding: 8px;
  z-index: 20;
  min-width: 140px;
}

.m-more-tab-item {
  width: 100%;
  padding: 10px 14px;
  background: transparent;
  border: none;
  font-size: 14px;
  color: #1e293b;
  text-align: left;
  border-radius: 8px;
  cursor: pointer;
}

.m-more-tab-item:active {
  background: #f1f5f9;
}

.m-more-tab-item.active {
  color: #0d6bff;
  background: #eef4ff;
  font-weight: 600;
}

.m-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0 12px;
}

.m-toolbar-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 8px 14px;
  background: white;
  border: 1px solid #e7edf7;
  border-radius: 100px;
  font-size: 13px;
  color: #5a6a85;
  cursor: pointer;
  transition: all 0.15s;
}

.m-toolbar-btn:active {
  background: #f5f7fb;
}

.m-toolbar-filter {
  gap: 6px;
}

.m-filter-badge {
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  background: #0d6bff;
  color: white;
  font-size: 11px;
  font-weight: 600;
  border-radius: 9px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.m-product-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.m-product-item {
  background: white;
  border-radius: 16px;
  padding: 12px;
  display: flex;
  align-items: center;
  gap: 12px;
  border: 1px solid #f0f4fa;
  box-shadow: 0 2px 8px rgba(31,53,94,0.04);
}

.m-product-main {
  flex: 1;
  min-width: 0;
  display: flex;
  gap: 12px;
  cursor: pointer;
}

.m-product-cover {
  width: 80px;
  height: 80px;
  border-radius: 12px;
  overflow: hidden;
  flex-shrink: 0;
  background: #f4f7fc;
}

.m-product-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.m-product-cover-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #b0bacb;
  background: linear-gradient(135deg, #f4f7fc, #eaf0fa);
}

.m-product-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 2px 0;
}

.m-product-name {
  font-size: 14px;
  font-weight: 600;
  color: #15213d;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  word-break: break-all;
}

.m-product-price-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.m-product-price {
  font-size: 17px;
  font-weight: 800;
  color: #ff4757;
}

.m-product-meta-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.m-product-stock {
  font-size: 12px;
  color: #8c98ae;
}

.m-product-stock.m-stock-low {
  color: #ff9f22;
}

.m-product-stock.m-stock-warning {
  color: #ff4757;
  font-weight: 600;
}

.m-product-status-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 100px;
}

.m-badge-onshelf {
  background: rgba(22,191,120,0.12);
  color: #16bf78;
}

.m-badge-offshelf {
  background: rgba(140,152,174,0.12);
  color: #6b7a94;
}

.m-badge-soldout {
  background: rgba(255,71,87,0.1);
  color: #ff4757;
}

.m-badge-disabled {
  background: rgba(140,152,174,0.15);
  color: #8c98ae;
}

.m-product-actions {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.m-toggle-switch {
  width: 44px;
  height: 26px;
  border-radius: 13px;
  background: #e2e8f0;
  border: none;
  position: relative;
  cursor: pointer;
  transition: background 0.2s;
  padding: 0;
}

.m-toggle-switch.on {
  background: #0d6bff;
}

.m-toggle-switch.disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.m-toggle-switch.loading {
  opacity: 0.7;
  pointer-events: none;
}

.m-toggle-knob {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 20px;
  height: 20px;
  background: white;
  border-radius: 50%;
  box-shadow: 0 1px 3px rgba(0,0,0,0.15);
  transition: transform 0.2s;
}

.m-toggle-switch.on .m-toggle-knob {
  transform: translateX(18px);
}

.m-product-more {
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  cursor: pointer;
}

.m-product-more:active {
  background: #f1f5f9;
}

.m-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 0;
}

.m-pagination-total {
  font-size: 12px;
  color: #8c98ae;
}

.m-pagination-pages {
  display: flex;
  gap: 6px;
}

.m-page-btn {
  min-width: 32px;
  height: 32px;
  padding: 0 8px;
  background: white;
  border: 1px solid #e7edf7;
  border-radius: 8px;
  font-size: 13px;
  color: #5a6a85;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.m-page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.m-page-btn.active {
  background: #0d6bff;
  border-color: #0d6bff;
  color: white;
  font-weight: 600;
}

.m-list-skeleton {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 4px 0;
}

.m-list-item-skeleton {
  background: white;
  border-radius: 16px;
  padding: 12px;
  display: flex;
  gap: 12px;
}

.m-skeleton-img {
  width: 80px;
  height: 80px;
  border-radius: 12px;
  background: #f0f4fa;
  animation: m-skeleton-pulse 1.5s ease-in-out infinite;
}

.m-skeleton-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 8px 0;
}

.m-skeleton-line {
  height: 12px;
  background: #f0f4fa;
  border-radius: 6px;
  animation: m-skeleton-pulse 1.5s ease-in-out infinite;
}

.m-skeleton-line.w-70 { width: 70%; }
.m-skeleton-line.w-40 { width: 40%; }
.m-skeleton-line.w-50 { width: 50%; }

@keyframes m-skeleton-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.m-empty-state {
  text-align: center;
  padding: 60px 20px;
}

.m-empty-icon {
  width: 88px;
  height: 88px;
  margin: 0 auto 16px;
  border-radius: 50%;
  background: linear-gradient(135deg, #f0f4fa, #e7edf7);
  color: #b0bacb;
  display: flex;
  align-items: center;
  justify-content: center;
}

.m-empty-title {
  font-size: 16px;
  font-weight: 600;
  color: #15213d;
  margin-bottom: 6px;
}

.m-empty-desc {
  font-size: 13px;
  color: #8c98ae;
  margin-bottom: 20px;
}

.m-empty-actions {
  display: flex;
  gap: 10px;
  justify-content: center;
}

.m-empty-btn {
  padding: 10px 20px;
  border-radius: 100px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: none;
}

.m-empty-btn-secondary {
  background: white;
  border: 1px solid #e7edf7;
  color: #5a6a85;
}

.m-menu-mask {
  position: fixed;
  inset: 0;
  background: rgba(15,25,50,0.4);
  z-index: 200;
}

.m-action-menu {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: white;
  border-radius: 20px 20px 0 0;
  padding: 8px 12px calc(12px + env(safe-area-inset-bottom));
  z-index: 201;
  animation: m-slide-up 0.25s ease;
}

@keyframes m-slide-up {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}

.m-action-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: transparent;
  border: none;
  font-size: 15px;
  color: #1e293b;
  cursor: pointer;
  border-radius: 12px;
  text-align: left;
}

.m-action-item:active {
  background: #f5f7fb;
}

.m-action-item.m-action-warn {
  color: #ff9f22;
}

.m-action-item.m-action-danger {
  color: #ff4757;
}

.m-action-item.m-action-cancel {
  justify-content: center;
  color: #8c98ae;
  font-weight: 500;
  border-top: 1px solid #f0f4fa;
  margin-top: 4px;
  border-radius: 0;
}

.m-bottom-sheet {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: white;
  border-radius: 20px 20px 0 0;
  padding: 8px 16px calc(16px + env(safe-area-inset-bottom));
  z-index: 201;
  animation: m-slide-up 0.25s ease;
}

.m-sheet-handle {
  width: 36px;
  height: 4px;
  background: #e2e8f0;
  border-radius: 2px;
  margin: 0 auto 12px;
}

.m-sheet-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.m-sheet-title {
  font-size: 16px;
  font-weight: 700;
  color: #15213d;
}

.m-sheet-reset {
  background: none;
  border: none;
  color: #0d6bff;
  font-size: 14px;
  cursor: pointer;
  padding: 4px 8px;
}

.m-sheet-option {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 0;
  background: transparent;
  border: none;
  font-size: 15px;
  color: #1e293b;
  cursor: pointer;
  border-bottom: 1px solid #f5f7fb;
  text-align: left;
}

.m-sheet-option.active {
  color: #0d6bff;
  font-weight: 600;
}

.m-filter-content {
  max-height: 50vh;
  overflow-y: auto;
}

.m-filter-group {
  margin-bottom: 20px;
}

.m-filter-label {
  font-size: 13px;
  font-weight: 600;
  color: #5a6a85;
  margin-bottom: 10px;
}

.m-filter-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.m-filter-chip {
  padding: 8px 16px;
  background: #f5f7fb;
  border: 1px solid transparent;
  border-radius: 100px;
  font-size: 13px;
  color: #5a6a85;
  cursor: pointer;
}

.m-filter-chip.active {
  background: #eef4ff;
  border-color: #0d6bff;
  color: #0d6bff;
  font-weight: 600;
}

.m-sheet-footer {
  display: flex;
  gap: 10px;
  padding-top: 16px;
}

.m-sheet-btn {
  flex: 1;
  padding: 13px;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  border: none;
}

.m-sheet-btn-cancel {
  background: #f1f5f9;
  color: #5a6a85;
}

.m-sheet-btn-confirm {
  background: linear-gradient(135deg, #0d6bff, #3b9bff);
  color: white;
}

.m-dialog-mask {
  position: fixed;
  inset: 0;
  background: rgba(15,25,50,0.5);
  z-index: 300;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.m-dialog {
  background: white;
  border-radius: 20px;
  padding: 24px;
  width: 100%;
  max-width: 320px;
}

.m-dialog-title {
  font-size: 17px;
  font-weight: 700;
  color: #15213d;
  margin-bottom: 8px;
}

.m-dialog-msg {
  font-size: 14px;
  color: #5a6a85;
  line-height: 1.6;
  margin-bottom: 20px;
}

.m-dialog-actions {
  display: flex;
  gap: 10px;
}

.m-dialog-btn {
  flex: 1;
  padding: 12px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  border: none;
}

.m-dialog-btn-cancel {
  background: #f1f5f9;
  color: #5a6a85;
}

.m-dialog-btn-confirm {
  background: linear-gradient(135deg, #0d6bff, #3b9bff);
  color: white;
}

.m-safe-bottom { height: calc(20px + env(safe-area-inset-bottom)); }

@media (max-width: 360px) {
  .m-products-page { padding: 0 8px; }
  .m-stat-card { padding: 10px; gap: 8px; }
  .m-stat-icon { width: 38px; height: 38px; }
  .m-stat-value { font-size: 18px; }
  .m-product-cover { width: 72px; height: 72px; }
}
</style>
