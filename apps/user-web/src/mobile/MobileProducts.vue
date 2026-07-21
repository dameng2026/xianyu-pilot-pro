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
      <div class="m-toolbar-left">
        <button class="m-toolbar-btn" :disabled="batchMode" @click="showSortMenu = true">
          <span>{{ currentSortLabel }}</span>
          <MIcon name="chevronDown" :size="14" />
        </button>
        <button class="m-toolbar-btn m-toolbar-filter" :disabled="batchMode" @click="showFilterSheet = true">
          <MIcon name="filter" :size="16" />
          <span>筛选</span>
          <span v-if="activeFilterCount > 0" class="m-filter-badge">{{ activeFilterCount }}</span>
        </button>
      </div>
      <button v-if="!batchMode" class="m-toolbar-btn m-toolbar-batch" :disabled="!filteredProducts.length" @click="enterBatchMode">
        <MIcon name="check" :size="14" />
        <span>批量操作</span>
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
        :class="{ 'm-batch-mode': batchMode, 'm-selected': isSelected(prod) }"
      >
        <button
          v-if="batchMode"
          class="m-batch-check"
          :class="{ checked: isSelected(prod) }"
          :aria-label="isSelected(prod) ? '取消选择' : '选择商品'"
          @click.stop="toggleSelect(prod)"
        >
          <MIcon v-if="isSelected(prod)" name="check" :size="14" color="#fff" />
        </button>
        <div class="m-product-main" @click="batchMode ? toggleSelect(prod) : openDetail(prod)">
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
        <div v-if="!batchMode" class="m-product-actions">
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

    <div v-if="batchMode" class="m-batch-toolbar">
      <div class="m-batch-toolbar-top">
        <button class="m-batch-select-all" :disabled="batchProcessing" @click="toggleSelectAll">
          <span class="m-batch-check-sm" :class="{ checked: isAllSelected }">
            <MIcon v-if="isAllSelected" name="check" :size="12" color="#fff" />
          </span>
          <span>{{ isAllSelected ? '取消全选' : '全选' }}</span>
        </button>
        <span class="m-batch-count">
          <template v-if="batchProcessing">
            {{ batchProgress.action }} {{ batchProgress.done }}/{{ batchProgress.total }} 已处理
          </template>
          <template v-else>已选 {{ selectedCount }} 件</template>
        </span>
      </div>
      <div v-if="batchProcessing" class="m-batch-progress-bar">
        <div class="m-batch-progress-fill" :style="{ width: progressPercent + '%' }"></div>
      </div>
      <div v-if="batchProcessing && batchProgress.current" class="m-batch-current">
        正在处理：{{ batchProgress.current }}
      </div>
      <div v-else class="m-batch-actions">
        <button class="m-batch-btn m-batch-on" :disabled="!hasSelected" @click="batchOnShelf">
          <MIcon name="arrowUp" :size="16" />
          <span>上架</span>
        </button>
        <button class="m-batch-btn m-batch-off" :disabled="!hasSelected" @click="batchOffShelf">
          <MIcon name="arrowDown" :size="16" />
          <span>下架</span>
        </button>
        <button class="m-batch-btn m-batch-del" :disabled="!hasSelected" @click="batchDelete">
          <MIcon name="trash" :size="16" />
          <span>删除</span>
        </button>
        <button class="m-batch-btn m-batch-cancel" @click="exitBatchMode">取消</button>
      </div>
    </div>
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

// 批量模式状态
const batchMode = ref(false)
const selectedIds = ref(new Set())
const batchProcessing = ref(false)
const batchProgress = ref({ action: '', done: 0, total: 0, current: '' })

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

// 批量模式计算属性
const selectedCount = computed(() => selectedIds.value.size)
const hasSelected = computed(() => selectedIds.value.size > 0)
const isAllSelected = computed(() => {
  const list = filteredProducts.value
  if (!list.length) return false
  return list.every(p => selectedIds.value.has(p.id || p.itemId))
})
const progressPercent = computed(() => {
  if (!batchProgress.value.total) return 0
  return Math.round((batchProgress.value.done / batchProgress.value.total) * 100)
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
  clearBatchSelectionIfActive()
})

function onSearch(kw) {
  searchKeywordInternal.value = kw || ''
  currentPage.value = 1
  clearBatchSelectionIfActive()
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
  const p = showProductMenu.value
  showProductMenu.value = null
  if (p) {
    showToast('已为您打开商品详情')
    openDetail(p)
  }
}

function doUpdateStock() {
  const p = showProductMenu.value
  showProductMenu.value = null
  if (p) {
    showToast('已为您打开商品详情，可在详情页调整库存')
    openDetail(p)
  }
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

// ===== 批量操作 =====
function productId(prod) {
  return prod.id || prod.itemId
}

function isSelected(prod) {
  return selectedIds.value.has(productId(prod))
}

function toggleSelect(prod) {
  if (batchProcessing.value) return
  const id = productId(prod)
  const next = new Set(selectedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selectedIds.value = next
}

function toggleSelectAll() {
  if (batchProcessing.value) return
  const list = filteredProducts.value
  if (isAllSelected.value) {
    // 仅取消当前可见列表的选择，保留其它页面的选择（如果存在）
    const next = new Set(selectedIds.value)
    list.forEach(p => next.delete(productId(p)))
    selectedIds.value = next
  } else {
    const next = new Set(selectedIds.value)
    list.forEach(p => next.add(productId(p)))
    selectedIds.value = next
  }
}

function enterBatchMode() {
  batchMode.value = true
  selectedIds.value = new Set()
  batchProcessing.value = false
  batchProgress.value = { action: '', done: 0, total: 0, current: '' }
}

function exitBatchMode() {
  if (batchProcessing.value) return
  batchMode.value = false
  selectedIds.value = new Set()
  batchProgress.value = { action: '', done: 0, total: 0, current: '' }
}

async function runBatch(action, runnable) {
  const selectedProducts = filteredProducts.value.filter(p => selectedIds.value.has(productId(p)))
  if (!selectedProducts.length) {
    showToast('请先选择商品', 'error')
    return
  }
  batchProcessing.value = true
  batchProgress.value = {
    action,
    done: 0,
    total: selectedProducts.length,
    current: ''
  }
  let success = 0
  let failed = 0
  for (const prod of selectedProducts) {
    batchProgress.value = {
      ...batchProgress.value,
      current: (prod.name || prod.title || '未命名商品').slice(0, 20)
    }
    try {
      await runnable(prod)
      success++
    } catch {
      failed++
      // 单个失败不中断后续
    }
    batchProgress.value = {
      ...batchProgress.value,
      done: batchProgress.value.done + 1
    }
  }
  batchProcessing.value = false
  batchProgress.value = { action: '', done: 0, total: 0, current: '' }
  if (failed === 0) {
    showToast(`${action}完成，共处理 ${success} 件`)
  } else {
    showToast(`${action}完成：成功 ${success} / 失败 ${failed}`, 'error')
  }
  // 刷新列表与统计
  try {
    await loadProducts()
    await loadStats()
  } catch {
    // 刷新失败不阻塞退出批量模式
  }
  exitBatchMode()
}

async function batchOnShelf() {
  if (batchProcessing.value) return
  if (!hasSelected.value) {
    showToast('请先选择商品', 'error')
    return
  }
  await runBatch('批量上架', async (prod) => {
    if (isOnShelf(prod)) return // 已上架跳过
    if (prod.stock <= 0) throw new Error('库存为0，无法上架')
    const id = prod.id || prod.itemId
    const accountId = prod.accountId || prod.xianyuAccountId
    if (!id) throw new Error('商品ID不存在')
    await republishItem({ id, accountId })
  })
}

async function batchOffShelf() {
  if (batchProcessing.value) return
  if (!hasSelected.value) {
    showToast('请先选择商品', 'error')
    return
  }
  await runBatch('批量下架', async (prod) => {
    if (!isOnShelf(prod)) return // 已下架跳过
    const id = prod.id || prod.itemId
    const accountId = prod.accountId || prod.xianyuAccountId
    if (!id) throw new Error('商品ID不存在')
    await offShelfItem({ id, accountId })
  })
}

function batchDelete() {
  if (batchProcessing.value) return
  if (!hasSelected.value) {
    showToast('请先选择商品', 'error')
    return
  }
  showConfirmDialog.value = {
    title: '批量删除商品',
    message: `确定要删除选中的 ${selectedCount.value} 件商品吗？此操作仅删除本地记录，不可恢复。`
  }
  confirmAction.value = async () => {
    showConfirmDialog.value = null
    await runBatch('批量删除', async (prod) => {
      const id = prod.id || prod.itemId
      if (!id) throw new Error('商品ID不存在')
      await deleteGoodsLocal(id)
    })
  }
}

function selectFilter(key) {
  activeFilter.value = key
  activeStatus.value = key === 'all' ? 'all' : key
  currentPage.value = 1
  clearBatchSelectionIfActive()
}

function selectStatus(key) {
  activeStatus.value = key
  activeFilter.value = key
  currentPage.value = 1
  clearBatchSelectionIfActive()
}

function selectSort(key) {
  currentSort.value = key
  showSortMenu.value = false
  currentPage.value = 1
  clearBatchSelectionIfActive()
}

function resetFilters() {
  filterStatus.value = ''
}

function applyFilters() {
  showFilterSheet.value = false
  currentPage.value = 1
  clearBatchSelectionIfActive()
}

function clearAllFilters() {
  activeFilter.value = 'all'
  activeStatus.value = 'all'
  filterStatus.value = ''
  searchKeywordInternal.value = ''
  currentPage.value = 1
  emit('close-search')
  clearBatchSelectionIfActive()
}

function goToPage(p) {
  if (p < 1 || p > totalPages.value) return
  currentPage.value = p
  loadProducts()
  clearBatchSelectionIfActive()
  nextTick(() => {
    const list = document.querySelector('.m-product-list')
    if (list) list.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

function clearBatchSelectionIfActive() {
  if (batchMode.value && selectedIds.value.size > 0) {
    selectedIds.value = new Set()
  }
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
  padding: 0 var(--m-space-3);
}

.m-stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--m-space-2);
  padding: var(--m-space-3) 0;
}

.m-stats-skeleton {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--m-space-2);
  padding: var(--m-space-3) 0;
}

.m-stat-card-skeleton {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-xl);
  height: 80px;
  animation: m-skeleton-pulse 1.5s ease-in-out infinite;
}

.m-stat-card {
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-3);
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;
  box-shadow: var(--m-shadow-card);
}

.m-stat-card:active {
  transform: scale(0.98);
}

.m-stat-card.active {
  border-color: var(--m-color-primary);
  background: var(--m-color-primary-bg);
  box-shadow: var(--m-shadow-elevated);
}

.m-stat-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--m-radius-lg);
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
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  margin-bottom: var(--m-space-1);
}

.m-stat-value-row {
  display: flex;
  align-items: baseline;
  gap: var(--m-space-2);
}

.m-stat-value {
  font-size: var(--m-font-size-h1);
  font-weight: var(--m-font-weight-extrabold);
  color: var(--m-color-text-primary);
  line-height: 1;
}

.m-stat-trend {
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-semibold);
  display: inline-flex;
  align-items: center;
  gap: 1px;
  color: var(--m-color-success);
}

.m-stat-trend.m-trend-down {
  color: var(--m-color-danger);
}

.m-tabs-bar {
  position: relative;
  margin-bottom: var(--m-space-2);
}

.m-tabs-scroll {
  display: flex;
  gap: var(--m-space-1);
  overflow-x: auto;
  scrollbar-width: none;
  padding-bottom: 2px;
}

.m-tabs-scroll::-webkit-scrollbar { display: none; }

.m-tab-item {
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-1);
  padding: var(--m-space-2) var(--m-space-4);
  background: transparent;
  border: none;
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-medium);
  color: var(--m-color-text-secondary);
  cursor: pointer;
  position: relative;
  white-space: nowrap;
  border-radius: var(--m-radius-md);
  transition: all 0.15s;
}

.m-tab-item.active {
  color: var(--m-color-primary);
  font-weight: var(--m-font-weight-semibold);
}

.m-tab-item.active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 24px;
  height: 2px;
  background: var(--m-color-primary);
  border-radius: var(--m-radius-sm);
}

.m-tab-count {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}

.m-tab-item.active .m-tab-count {
  color: var(--m-color-primary);
}

.m-tab-more {
  color: var(--m-color-text-secondary);
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
  background: var(--m-color-bg-elevated);
  border-radius: var(--m-radius-lg);
  box-shadow: var(--m-shadow-elevated);
  padding: var(--m-space-2);
  z-index: 20;
  min-width: 140px;
}

.m-more-tab-item {
  width: 100%;
  padding: var(--m-space-2) var(--m-space-3);
  background: transparent;
  border: none;
  font-size: var(--m-font-size-body);
  color: var(--m-color-text-primary);
  text-align: left;
  border-radius: var(--m-radius-md);
  cursor: pointer;
}

.m-more-tab-item:active {
  background: var(--m-color-bg-hover);
}

.m-more-tab-item.active {
  color: var(--m-color-primary);
  background: var(--m-color-primary-bg);
  font-weight: var(--m-font-weight-semibold);
}

.m-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-space-2) 0 var(--m-space-3);
}

.m-toolbar-left {
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-2);
}

.m-toolbar-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-1);
  padding: var(--m-space-2) var(--m-space-3);
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-pill);
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}

.m-toolbar-btn:active {
  background: var(--m-color-bg-hover);
}

.m-toolbar-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.m-toolbar-filter {
  gap: var(--m-space-2);
}

.m-toolbar-batch {
  background: var(--m-color-primary);
  border: none;
  color: var(--m-color-text-inverse);
  font-weight: var(--m-font-weight-semibold);
  gap: var(--m-space-1);
}

.m-toolbar-batch:active {
  background: var(--m-color-primary-active);
}

.m-toolbar-batch:disabled {
  background: var(--m-color-primary-bg-hover);
  color: var(--m-color-text-inverse);
  opacity: 0.7;
}

.m-filter-badge {
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-semibold);
  border-radius: var(--m-radius-pill);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.m-product-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
}

.m-product-item {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-3);
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
  border: 1px solid var(--m-color-border-light);
  box-shadow: var(--m-shadow-card);
  transition: background 0.15s, border-color 0.15s;
}

.m-product-item.m-batch-mode {
  padding: var(--m-space-2) var(--m-space-3);
}

.m-product-item.m-selected {
  background: var(--m-color-primary-bg);
  border-color: var(--m-color-primary);
  box-shadow: var(--m-shadow-elevated);
}

.m-batch-check {
  width: 22px;
  height: 22px;
  border-radius: var(--m-radius-sm);
  border: 2px solid var(--m-color-border);
  background: var(--m-color-bg-card);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  padding: 0;
  transition: all 0.15s;
}

.m-batch-check.checked {
  background: var(--m-color-primary);
  border-color: var(--m-color-primary);
}

.m-batch-check-sm {
  width: 18px;
  height: 18px;
  border-radius: var(--m-radius-sm);
  border: 2px solid var(--m-color-border);
  background: var(--m-color-bg-card);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  flex-shrink: 0;
}

.m-batch-check-sm.checked {
  background: var(--m-color-primary);
  border-color: var(--m-color-primary);
}

.m-product-main {
  flex: 1;
  min-width: 0;
  display: flex;
  gap: var(--m-space-3);
  cursor: pointer;
}

.m-product-cover {
  width: 80px;
  height: 80px;
  border-radius: var(--m-radius-lg);
  overflow: hidden;
  flex-shrink: 0;
  background: var(--m-color-bg-subtle);
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
  color: var(--m-color-text-disabled);
  background: var(--m-color-bg-subtle);
}

.m-product-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
  padding: 2px 0;
}

.m-product-name {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
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
  gap: var(--m-space-2);
}

.m-product-price {
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-extrabold);
  color: var(--m-color-danger-text);
}

.m-product-meta-row {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  flex-wrap: wrap;
}

.m-product-stock {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}

.m-product-stock.m-stock-low {
  color: var(--m-color-warning-text);
}

.m-product-stock.m-stock-warning {
  color: var(--m-color-danger-text);
  font-weight: var(--m-font-weight-semibold);
}

.m-product-status-badge {
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-semibold);
  padding: 3px var(--m-space-2);
  border-radius: var(--m-radius-pill);
}

.m-badge-onshelf {
  background: var(--m-color-success-bg);
  color: var(--m-color-success);
}

.m-badge-offshelf {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-tertiary);
}

.m-badge-soldout {
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger);
}

.m-badge-disabled {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-tertiary);
}

.m-product-actions {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--m-space-2);
  flex-shrink: 0;
}

.m-toggle-switch {
  width: 44px;
  height: 26px;
  border-radius: var(--m-radius-pill);
  background: var(--m-color-border);
  border: none;
  position: relative;
  cursor: pointer;
  transition: background 0.2s;
  padding: 0;
}

.m-toggle-switch.on {
  background: var(--m-color-primary);
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
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-circle);
  box-shadow: var(--m-shadow-card);
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
  border-radius: var(--m-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--m-color-text-tertiary);
  cursor: pointer;
}

.m-product-more:active {
  background: var(--m-color-bg-hover);
}

.m-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-space-4) 0;
}

.m-pagination-total {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}

.m-pagination-pages {
  display: flex;
  gap: var(--m-space-2);
}

.m-page-btn {
  min-width: 32px;
  height: 32px;
  padding: 0 var(--m-space-2);
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-md);
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-secondary);
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
  background: var(--m-color-primary);
  border-color: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  font-weight: var(--m-font-weight-semibold);
}

.m-list-skeleton {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
  padding: var(--m-space-1) 0;
}

.m-list-item-skeleton {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-3);
  display: flex;
  gap: var(--m-space-3);
}

.m-skeleton-img {
  width: 80px;
  height: 80px;
  border-radius: var(--m-radius-lg);
  background: var(--m-color-bg-subtle);
  animation: m-skeleton-pulse 1.5s ease-in-out infinite;
}

.m-skeleton-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
  padding: var(--m-space-2) 0;
}

.m-skeleton-line {
  height: 12px;
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-sm);
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
  padding: 60px var(--m-space-5);
}

.m-empty-icon {
  width: 88px;
  height: 88px;
  margin: 0 auto var(--m-space-4);
  border-radius: var(--m-radius-circle);
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-disabled);
  display: flex;
  align-items: center;
  justify-content: center;
}

.m-empty-title {
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  margin-bottom: var(--m-space-2);
}

.m-empty-desc {
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-tertiary);
  margin-bottom: var(--m-space-5);
}

.m-empty-actions {
  display: flex;
  gap: var(--m-space-2);
  justify-content: center;
}

.m-empty-btn {
  padding: var(--m-space-2) var(--m-space-5);
  border-radius: var(--m-radius-pill);
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  border: none;
}

.m-empty-btn-secondary {
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border);
  color: var(--m-color-text-secondary);
}

.m-menu-mask {
  position: fixed;
  inset: 0;
  background: var(--m-mask-drawer);
  z-index: 200;
}

.m-action-menu {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: var(--m-color-bg-elevated);
  border-radius: var(--m-radius-2xl) var(--m-radius-2xl) 0 0;
  padding: var(--m-space-2) var(--m-space-3) calc(var(--m-space-3) + var(--m-safe-area-bottom));
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
  gap: var(--m-space-3);
  padding: var(--m-space-3) var(--m-space-4);
  background: transparent;
  border: none;
  font-size: var(--m-font-size-h3);
  color: var(--m-color-text-primary);
  cursor: pointer;
  border-radius: var(--m-radius-lg);
  text-align: left;
}

.m-action-item:active {
  background: var(--m-color-bg-hover);
}

.m-action-item.m-action-warn {
  color: var(--m-color-warning-text);
}

.m-action-item.m-action-danger {
  color: var(--m-color-danger-text);
}

.m-action-item.m-action-cancel {
  justify-content: center;
  color: var(--m-color-text-tertiary);
  font-weight: var(--m-font-weight-medium);
  border-top: 1px solid var(--m-color-border-light);
  margin-top: var(--m-space-1);
  border-radius: 0;
}

.m-bottom-sheet {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: var(--m-color-bg-elevated);
  border-radius: var(--m-radius-2xl) var(--m-radius-2xl) 0 0;
  padding: var(--m-space-2) var(--m-space-4) calc(var(--m-space-4) + var(--m-safe-area-bottom));
  z-index: 201;
  animation: m-slide-up 0.25s ease;
}

.m-sheet-handle {
  width: 36px;
  height: 4px;
  background: var(--m-color-border);
  border-radius: var(--m-radius-sm);
  margin: 0 auto var(--m-space-3);
}

.m-sheet-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--m-space-4);
}

.m-sheet-title {
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
}

.m-sheet-reset {
  background: none;
  border: none;
  color: var(--m-color-primary);
  font-size: var(--m-font-size-body);
  cursor: pointer;
  padding: var(--m-space-1) var(--m-space-2);
}

.m-sheet-option {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-space-3) 0;
  background: transparent;
  border: none;
  font-size: var(--m-font-size-h3);
  color: var(--m-color-text-primary);
  cursor: pointer;
  border-bottom: 1px solid var(--m-color-border-light);
  text-align: left;
}

.m-sheet-option.active {
  color: var(--m-color-primary);
  font-weight: var(--m-font-weight-semibold);
}

.m-filter-content {
  max-height: 50vh;
  overflow-y: auto;
}

.m-filter-group {
  margin-bottom: var(--m-space-5);
}

.m-filter-label {
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-secondary);
  margin-bottom: var(--m-space-2);
}

.m-filter-options {
  display: flex;
  flex-wrap: wrap;
  gap: var(--m-space-2);
}

.m-filter-chip {
  padding: var(--m-space-2) var(--m-space-4);
  background: var(--m-color-bg-hover);
  border: 1px solid transparent;
  border-radius: var(--m-radius-pill);
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-secondary);
  cursor: pointer;
}

.m-filter-chip.active {
  background: var(--m-color-primary-bg);
  border-color: var(--m-color-primary);
  color: var(--m-color-primary);
  font-weight: var(--m-font-weight-semibold);
}

.m-sheet-footer {
  display: flex;
  gap: var(--m-space-2);
  padding-top: var(--m-space-4);
}

.m-sheet-btn {
  flex: 1;
  padding: 13px;
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  border: none;
}

.m-sheet-btn-cancel {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
}

.m-sheet-btn-confirm {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
}

.m-dialog-mask {
  position: fixed;
  inset: 0;
  background: var(--m-mask-modal);
  z-index: 300;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--m-space-5);
}

.m-dialog {
  background: var(--m-color-bg-elevated);
  border-radius: var(--m-radius-2xl);
  padding: var(--m-space-6);
  width: 100%;
  max-width: 320px;
}

.m-dialog-title {
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
  margin-bottom: var(--m-space-2);
}

.m-dialog-msg {
  font-size: var(--m-font-size-body);
  color: var(--m-color-text-secondary);
  line-height: var(--m-line-height-relaxed);
  margin-bottom: var(--m-space-5);
}

.m-dialog-actions {
  display: flex;
  gap: var(--m-space-2);
}

.m-dialog-btn {
  flex: 1;
  padding: var(--m-space-3);
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  border: none;
}

.m-dialog-btn-cancel {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
}

.m-dialog-btn-confirm {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
}

.m-safe-bottom { height: calc(var(--m-space-4) + var(--m-safe-area-bottom)); }

/* ===== 批量操作工具栏 ===== */
.m-batch-toolbar {
  position: fixed;
  left: var(--m-space-2);
  right: var(--m-space-2);
  bottom: calc(72px + var(--m-safe-area-bottom));
  background: var(--m-color-bg-elevated);
  border-radius: var(--m-radius-xl);
  box-shadow: var(--m-shadow-elevated);
  padding: var(--m-space-3) var(--m-space-3) calc(var(--m-space-3) + var(--m-safe-area-bottom));
  z-index: 150;
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
  animation: m-batch-slide-up 0.25s ease;
}

@keyframes m-batch-slide-up {
  from { transform: translateY(100%); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

.m-batch-toolbar-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--m-space-2);
}

.m-batch-select-all {
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-2);
  background: none;
  border: none;
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-primary);
  cursor: pointer;
  padding: var(--m-space-1);
  font-weight: var(--m-font-weight-medium);
}

.m-batch-select-all:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.m-batch-count {
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-secondary);
  font-weight: var(--m-font-weight-semibold);
}

.m-batch-progress-bar {
  width: 100%;
  height: 4px;
  background: var(--m-color-border-light);
  border-radius: var(--m-radius-sm);
  overflow: hidden;
}

.m-batch-progress-fill {
  height: 100%;
  background: var(--m-color-primary);
  transition: width 0.25s ease;
  border-radius: var(--m-radius-sm);
}

.m-batch-current {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.m-batch-actions {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--m-space-2);
}

.m-batch-btn {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  padding: var(--m-space-2) var(--m-space-1);
  background: var(--m-color-bg-hover);
  border: 1px solid transparent;
  border-radius: var(--m-radius-md);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  cursor: pointer;
  transition: all 0.15s;
}

.m-batch-btn:active:not(:disabled) {
  transform: scale(0.97);
}

.m-batch-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.m-batch-on {
  background: var(--m-color-success-bg);
  color: var(--m-color-success);
}

.m-batch-off {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning-text);
}

.m-batch-del {
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger);
}

.m-batch-cancel {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
}

@media (max-width: 360px) {
  .m-products-page { padding: 0 var(--m-space-2); }
  .m-stat-card { padding: var(--m-space-2); gap: var(--m-space-2); }
  .m-stat-icon { width: 38px; height: 38px; }
  .m-stat-value { font-size: 18px; }
  .m-product-cover { width: 72px; height: 72px; }
}
</style>
