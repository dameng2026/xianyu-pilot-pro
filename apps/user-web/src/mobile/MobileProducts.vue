<template>
  <div class="m-products-page">
    <!-- ============ 顶部统计卡 ============ -->
    <div v-if="statsLoading" class="m-stats-skeleton">
      <div v-for="i in 4" :key="i" class="m-stat-card-skeleton"></div>
    </div>
    <div v-else class="m-stats-grid">
      <button
        v-for="card in statCards"
        :key="card.key"
        class="m-stat-card"
        :class="{ active: activeStatus === card.key }"
        @click="selectStatus(card.key)"
      >
        <div class="m-stat-icon" :style="{ background: card.iconBg }">
          <MIcon :name="card.icon" :size="20" :color="card.iconColor" />
        </div>
        <div class="m-stat-info">
          <div class="m-stat-label">{{ card.label }}</div>
          <div class="m-stat-value">{{ card.value }}</div>
        </div>
      </button>
    </div>

    <!-- ============ 状态 Tabs ============ -->
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
      </div>
    </div>

    <!-- ============ 工具栏：排序 ============ -->
    <div class="m-toolbar">
      <button class="m-toolbar-btn" :disabled="batchMode" @click="showSortMenu = true">
        <MIcon name="filter" :size="14" />
        <span>{{ currentSortLabel }}</span>
        <MIcon name="chevronDown" :size="12" />
      </button>
      <button
        v-if="!batchMode"
        class="m-toolbar-btn m-toolbar-batch"
        :disabled="!products.length"
        @click="enterBatchMode"
      >
        <MIcon name="check" :size="14" />
        <span>批量</span>
      </button>
    </div>

    <!-- ============ 列表 ============ -->
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

    <MobileUnavailableState
      v-else-if="loadError"
      compact
      title="商品加载失败"
      :description="loadError"
      @retry="loadProducts"
    />

    <div v-else-if="products.length === 0" class="m-empty-state">
      <div class="m-empty-icon">
        <MIcon name="bag" :size="48" />
      </div>
      <div class="m-empty-title">{{ searchKeyword ? '未找到相关商品' : '暂无商品' }}</div>
      <div class="m-empty-desc">
        {{ searchKeyword ? '尝试更换关键词或清除筛选条件' : '点击底部"发布"按钮发布第一个商品' }}
      </div>
      <div class="m-empty-actions">
        <button v-if="searchKeyword || activeStatus !== 'all'" class="m-empty-btn" @click="clearAllFilters">
          清除筛选
        </button>
        <button class="m-empty-btn m-empty-btn-primary" @click="goToPublish">
          <MIcon name="plus" :size="14" />
          发布商品
        </button>
      </div>
    </div>

    <div v-else class="m-product-list">
      <div
        v-for="prod in sortedProducts"
        :key="prod.id"
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
              :alt="prod.title"
              class="m-product-img"
              loading="lazy"
              @error="onImgError($event, prod)"
            />
            <div v-else class="m-product-cover-placeholder">
              <MIcon name="bag" :size="24" />
            </div>
            <span class="m-product-status-tag" :class="statusBadgeClass(prod)">{{ statusText(prod) }}</span>
          </div>
          <div class="m-product-info">
            <div class="m-product-name">{{ prod.title || '未命名商品' }}</div>
            <div class="m-product-price-row">
              <span class="m-product-price">¥{{ formatPrice(prod.soldPrice ?? prod.price) }}</span>
              <span v-if="Number(prod.quantity) <= 0" class="m-stock-tag m-stock-out">无货</span>
              <span v-else-if="Number(prod.quantity) <= 10" class="m-stock-tag m-stock-low">库存{{ prod.quantity }}</span>
            </div>
            <div class="m-product-meta-row">
              <span class="m-meta-chip">
                <MIcon name="trendingUp" :size="11" />
                想要 {{ Number(prod.wantCount) || 0 }}
              </span>
              <span class="m-meta-chip">
                <MIcon name="eye" :size="11" />
                曝光 {{ Number(prod.exposureCount) || 0 }}
              </span>
              <span v-if="prod.category" class="m-meta-chip m-meta-cat">{{ prod.category }}</span>
            </div>
          </div>
        </div>
        <div v-if="!batchMode" class="m-product-actions">
          <button
            class="m-toggle-switch"
            :class="{ on: isOnShelf(prod), loading: prod._toggling }"
            :disabled="prod._toggling"
            :aria-label="isOnShelf(prod) ? '下架商品' : '上架商品'"
            @click.stop="toggleOnShelf(prod)"
          >
            <span class="m-toggle-knob"></span>
          </button>
          <button class="m-product-more" aria-label="更多操作" @click.stop="showProductMenu = prod">
            <MIcon name="moreVertical" :size="18" />
          </button>
        </div>
      </div>
    </div>

    <!-- ============ 分页 ============ -->
    <div v-if="!loading && !loadError && products.length > 0" class="m-pagination">
      <span class="m-pagination-total">共 {{ total }} 条</span>
      <div class="m-pagination-pages">
        <button class="m-page-btn" :disabled="currentPage <= 1" aria-label="上一页" @click="goToPage(currentPage - 1)">
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
          aria-label="下一页"
          @click="goToPage(currentPage + 1)"
        >
          <MIcon name="chevronRight" :size="16" />
        </button>
      </div>
    </div>

    <!-- ============ 单商品操作菜单 ============ -->
    <div v-if="showProductMenu" class="m-menu-mask" @click="showProductMenu = null"></div>
    <div v-if="showProductMenu" class="m-action-menu">
      <div class="m-action-header">
        <div class="m-action-header-title">{{ showProductMenu.title || '未命名商品' }}</div>
      </div>
      <button class="m-action-item" @click="doViewDetail">
        <MIcon name="eye" :size="18" />
        <span>查看详情</span>
      </button>
      <button class="m-action-item" @click="doEditProduct">
        <MIcon name="edit" :size="18" />
        <span>编辑商品</span>
      </button>
      <button v-if="isOnShelf(showProductMenu)" class="m-action-item m-action-warn" @click="doQuickOffShelf">
        <MIcon name="arrowDown" :size="18" />
        <span>下架商品</span>
      </button>
      <button v-else class="m-action-item m-action-success" @click="doQuickOnShelf">
        <MIcon name="arrowUp" :size="18" />
        <span>上架商品</span>
      </button>
      <button class="m-action-item" @click="doPublishCopy">
        <MIcon name="copy" :size="18" />
        <span>复制发布新商品</span>
      </button>
      <button class="m-action-item m-action-danger" @click="doDeleteProduct">
        <MIcon name="trash" :size="18" />
        <span>删除商品</span>
      </button>
      <button class="m-action-item m-action-cancel" @click="showProductMenu = null">取消</button>
    </div>

    <!-- ============ 排序选择 ============ -->
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

    <!-- ============ 确认弹窗 ============ -->
    <div v-if="showConfirmDialog" class="m-dialog-mask" @click="cancelConfirm">
      <div class="m-dialog" @click.stop>
        <div class="m-dialog-title">{{ confirmDialog.title }}</div>
        <div class="m-dialog-msg">{{ confirmDialog.message }}</div>
        <div class="m-dialog-actions">
          <button class="m-dialog-btn m-dialog-btn-cancel" @click="cancelConfirm">取消</button>
          <button
            class="m-dialog-btn"
            :class="confirmDialog.danger ? 'm-dialog-btn-danger' : 'm-dialog-btn-confirm'"
            @click="confirmAction"
          >
            {{ confirmDialog.confirmText || '确定' }}
          </button>
        </div>
      </div>
    </div>

    <div class="m-safe-bottom"></div>

    <!-- ============ 批量操作工具栏 ============ -->
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
            {{ batchProgress.action }} {{ batchProgress.done }}/{{ batchProgress.total }}
          </template>
          <template v-else>已选 {{ selectedCount }} 件</template>
        </span>
      </div>
      <div v-if="batchProcessing" class="m-batch-progress-bar">
        <div class="m-batch-progress-fill" :style="{ width: progressPercent + '%' }"></div>
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
import { recordsOf, totalOf, unwrap } from '../utils/apiData.js'

const props = defineProps({
  searchMode: Boolean,
  searchKeyword: String
})

const emit = defineEmits(['navigate', 'force-desktop', 'back', 'open-detail', 'close-search'])

// ===== 后端 status 值（FE 视角）：0=在售 1=下架 2=已售 3=已删除 =====
const FE_STATUS_ON_SALE = 0
const FE_STATUS_OFF_SHELF = 1
const FE_STATUS_DELETED = 3

// ===== 状态 =====
const products = ref([])
const stats = ref({ total: 0, onSale: 0, offShelfOrDraft: 0, autoDeliveryOn: 0, autoReplyAccounts: 0 })
const loading = ref(false)
const statsLoading = ref(false)
const loadError = ref('')
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)
const activeStatus = ref('all')
const currentSort = ref('default')
const showSortMenu = ref(false)
const showProductMenu = ref(null)
const showConfirmDialog = ref(false)
const confirmDialog = ref({ title: '', message: '', confirmText: '确定', danger: false })
const pendingAction = ref(() => {})
const searchKeywordInternal = ref('')

// 批量模式
const batchMode = ref(false)
const selectedIds = ref(new Set())
const batchProcessing = ref(false)
const batchProgress = ref({ action: '', done: 0, total: 0 })

const sortOptions = [
  { key: 'default', label: '默认排序' },
  { key: 'newest', label: '最新创建' },
  { key: 'priceDesc', label: '价格从高到低' },
  { key: 'priceAsc', label: '价格从低到高' },
  { key: 'wantDesc', label: '想要数从高到低' },
  { key: 'exposureDesc', label: '曝光量从高到低' },
  { key: 'stockAsc', label: '库存从低到高' }
]

const statusTabs = computed(() => [
  { key: 'all', label: '全部', count: stats.value.total || 0 },
  { key: 'onSale', label: '上架中', count: stats.value.onSale || 0 },
  { key: 'offShelf', label: '下架中', count: stats.value.offShelfOrDraft || 0 }
])

const statCards = computed(() => [
  {
    key: 'all',
    label: '全部商品',
    value: stats.value.total || 0,
    icon: 'bag',
    iconBg: 'rgba(13,107,255,0.1)',
    iconColor: '#0d6bff'
  },
  {
    key: 'onSale',
    label: '上架中',
    value: stats.value.onSale || 0,
    icon: 'pieChart',
    iconBg: 'rgba(22,191,120,0.1)',
    iconColor: '#16bf78'
  },
  {
    key: 'offShelf',
    label: '下架中',
    value: stats.value.offShelfOrDraft || 0,
    icon: 'arrowDown',
    iconBg: 'rgba(140,152,174,0.12)',
    iconColor: '#8c98ae'
  },
  {
    key: 'autoDelivery',
    label: '自动发货',
    value: stats.value.autoDeliveryOn || 0,
    icon: 'truck',
    iconBg: 'rgba(139,92,246,0.1)',
    iconColor: '#8b5cf6'
  }
])

const currentSortLabel = computed(() => {
  const s = sortOptions.find(o => o.key === currentSort.value)
  return s ? s.label : '默认排序'
})

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

const visiblePages = computed(() => {
  const pages = []
  const tp = totalPages.value
  const cp = currentPage.value
  if (tp <= 5) {
    for (let i = 1; i <= tp; i++) pages.push(i)
  } else if (cp <= 3) {
    for (let i = 1; i <= 5; i++) pages.push(i)
  } else if (cp >= tp - 2) {
    for (let i = tp - 4; i <= tp; i++) pages.push(i)
  } else {
    for (let i = cp - 2; i <= cp + 2; i++) pages.push(i)
  }
  return pages
})

// 前端排序（基于已加载的当前页数据）
const sortedProducts = computed(() => {
  const list = [...products.value]
  const numKey = (p, k) => Number(p[k]) || 0
  switch (currentSort.value) {
    case 'newest':
      list.sort((a, b) => (b.id || 0) - (a.id || 0))
      break
    case 'priceDesc':
      list.sort((a, b) => numKey(b, 'soldPrice') - numKey(a, 'soldPrice'))
      break
    case 'priceAsc':
      list.sort((a, b) => numKey(a, 'soldPrice') - numKey(b, 'soldPrice'))
      break
    case 'wantDesc':
      list.sort((a, b) => numKey(b, 'wantCount') - numKey(a, 'wantCount'))
      break
    case 'exposureDesc':
      list.sort((a, b) => numKey(b, 'exposureCount') - numKey(a, 'exposureCount'))
      break
    case 'stockAsc':
      list.sort((a, b) => numKey(a, 'quantity') - numKey(b, 'quantity'))
      break
  }
  return list
})

// ===== 批量 =====
const selectedCount = computed(() => selectedIds.value.size)
const hasSelected = computed(() => selectedIds.value.size > 0)
const isAllSelected = computed(() => {
  const list = sortedProducts.value
  if (!list.length) return false
  return list.every(p => selectedIds.value.has(p.id))
})
const progressPercent = computed(() => {
  if (!batchProgress.value.total) return 0
  return Math.round((batchProgress.value.done / batchProgress.value.total) * 100)
})

watch(() => props.searchKeyword, (val) => {
  searchKeywordInternal.value = val || ''
  currentPage.value = 1
  clearBatchSelectionIfActive()
  loadProducts()
})

function onSearch(kw) {
  searchKeywordInternal.value = kw || ''
  currentPage.value = 1
  clearBatchSelectionIfActive()
  loadProducts()
}

defineExpose({ onSearch, refreshProduct })

// ===== 状态判断 =====
function isOnShelf(p) {
  // 后端 FE 视角：0=在售
  return Number(p.status) === FE_STATUS_ON_SALE
}

function isDeleted(p) {
  return Number(p.status) === FE_STATUS_DELETED
}

function statusText(p) {
  if (isDeleted(p)) return '已删除'
  if (isOnShelf(p)) return '上架中'
  return '已下架'
}

function statusBadgeClass(p) {
  if (isDeleted(p)) return 'm-tag-deleted'
  if (isOnShelf(p)) return 'm-tag-onshelf'
  return 'm-tag-offshelf'
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
}

function coverUrlOf(prod) {
  if (!prod) return ''
  return resolveTrustedMediaUrl(prod.coverPic || prod.imageUrl || '')
}

// ===== 导航 =====
function openDetail(prod) {
  emit('open-detail', prod)
}

function goToPublish() {
  emit('navigate', 'product-publish')
}

// ===== 菜单操作 =====
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

function doPublishCopy() {
  const p = showProductMenu.value
  showProductMenu.value = null
  if (!p) return
  // 复制发布：跳转到发布页（发布页会读取 sessionStorage 中的草稿，这里暂存标题作为预填）
  try {
    sessionStorage.setItem('mobile_publish_draft_title', p.title || '')
  } catch { /* sessionStorage 不可用时忽略 */ }
  emit('navigate', 'product-publish')
  showToast('已跳转到发布页，可复用商品信息')
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
  confirmDialog.value = {
    title: '删除商品',
    message: `确定要删除「${p.title || '该商品'}」吗？此操作仅删除本地记录，不影响闲鱼线上商品，且不可恢复。`,
    confirmText: '确认删除',
    danger: true
  }
  pendingAction.value = async () => {
    try {
      await deleteGoodsLocal(p.id)
      products.value = products.value.filter(x => x.id !== p.id)
      total.value = Math.max(0, total.value - 1)
      showToast('删除成功')
      await loadStats()
    } catch (e) {
      showToast(e?.message || '删除失败', 'error')
    }
    showConfirmDialog.value = false
  }
  showConfirmDialog.value = true
}

function cancelConfirm() {
  showConfirmDialog.value = false
  pendingAction.value = () => {}
}

function confirmAction() {
  const fn = pendingAction.value
  pendingAction.value = () => {}
  if (typeof fn === 'function') fn()
}

// ===== 上架/下架 =====
async function toggleOnShelf(prod) {
  if (prod._toggling) return
  const wasOnShelf = isOnShelf(prod)
  prod._toggling = true
  try {
    if (!prod.id) throw new Error('商品ID不存在')
    const accountId = prod.accountId
    if (wasOnShelf) {
      await offShelfItem({ id: prod.id, accountId })
      prod.status = FE_STATUS_OFF_SHELF
      showToast('已下架')
    } else {
      if (Number(prod.quantity) <= 0) {
        showToast('库存为0，无法上架', 'error')
        prod._toggling = false
        return
      }
      await republishItem({ id: prod.id, accountId })
      prod.status = FE_STATUS_ON_SALE
      showToast('已上架')
    }
    await loadStats()
  } catch (e) {
    showToast(e?.message || '操作失败', 'error')
  } finally {
    prod._toggling = false
  }
}

// ===== 批量操作 =====
function isSelected(prod) {
  return selectedIds.value.has(prod.id)
}

function toggleSelect(prod) {
  if (batchProcessing.value) return
  const next = new Set(selectedIds.value)
  if (next.has(prod.id)) next.delete(prod.id)
  else next.add(prod.id)
  selectedIds.value = next
}

function toggleSelectAll() {
  if (batchProcessing.value) return
  const list = sortedProducts.value
  if (isAllSelected.value) {
    const next = new Set(selectedIds.value)
    list.forEach(p => next.delete(p.id))
    selectedIds.value = next
  } else {
    const next = new Set(selectedIds.value)
    list.forEach(p => next.add(p.id))
    selectedIds.value = next
  }
}

function enterBatchMode() {
  batchMode.value = true
  selectedIds.value = new Set()
  batchProcessing.value = false
  batchProgress.value = { action: '', done: 0, total: 0 }
}

function exitBatchMode() {
  if (batchProcessing.value) return
  batchMode.value = false
  selectedIds.value = new Set()
}

async function runBatch(action, runnable) {
  const selectedProducts = sortedProducts.value.filter(p => selectedIds.value.has(p.id))
  if (!selectedProducts.length) {
    showToast('请先选择商品', 'error')
    return
  }
  batchProcessing.value = true
  batchProgress.value = { action, done: 0, total: selectedProducts.length }
  let success = 0
  let failed = 0
  for (const prod of selectedProducts) {
    try {
      await runnable(prod)
      success++
    } catch {
      failed++
    }
    batchProgress.value = { ...batchProgress.value, done: batchProgress.value.done + 1 }
  }
  batchProcessing.value = false
  batchProgress.value = { action: '', done: 0, total: 0 }
  showToast(failed === 0 ? `${action}完成，共处理 ${success} 件` : `${action}：成功 ${success} / 失败 ${failed}`, failed === 0 ? 'success' : 'error')
  await loadProducts()
  await loadStats()
  exitBatchMode()
}

async function batchOnShelf() {
  if (!hasSelected.value) {
    showToast('请先选择商品', 'error')
    return
  }
  await runBatch('批量上架', async (prod) => {
    if (isOnShelf(prod)) return
    if (Number(prod.quantity) <= 0) throw new Error('库存为0')
    await republishItem({ id: prod.id, accountId: prod.accountId })
  })
}

async function batchOffShelf() {
  if (!hasSelected.value) {
    showToast('请先选择商品', 'error')
    return
  }
  await runBatch('批量下架', async (prod) => {
    if (!isOnShelf(prod)) return
    await offShelfItem({ id: prod.id, accountId: prod.accountId })
  })
}

function batchDelete() {
  if (!hasSelected.value) {
    showToast('请先选择商品', 'error')
    return
  }
  confirmDialog.value = {
    title: '批量删除商品',
    message: `确定要删除选中的 ${selectedCount.value} 件商品吗？此操作仅删除本地记录，不可恢复。`,
    confirmText: '确认删除',
    danger: true
  }
  pendingAction.value = async () => {
    showConfirmDialog.value = false
    await runBatch('批量删除', async (prod) => {
      await deleteGoodsLocal(prod.id)
    })
  }
  showConfirmDialog.value = true
}

// ===== 筛选/排序 =====
function selectStatus(key) {
  activeStatus.value = key
  currentPage.value = 1
  clearBatchSelectionIfActive()
  loadProducts()
}

function selectSort(key) {
  currentSort.value = key
  showSortMenu.value = false
}

function clearAllFilters() {
  activeStatus.value = 'all'
  searchKeywordInternal.value = ''
  currentPage.value = 1
  emit('close-search')
  clearBatchSelectionIfActive()
  loadProducts()
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

// ===== 数据加载 =====
async function loadStats() {
  statsLoading.value = true
  try {
    const res = await getGoodsStats()
    const d = unwrap(res) || {}
    stats.value = {
      total: Number(d.total) || 0,
      onSale: Number(d.onSale) || 0,
      offShelfOrDraft: Number(d.offShelfOrDraft) || 0,
      autoDeliveryOn: Number(d.autoDeliveryOn) || 0,
      autoReplyAccounts: Number(d.autoReplyAccounts) || 0
    }
  } catch {
    stats.value = { total: 0, onSale: 0, offShelfOrDraft: 0, autoDeliveryOn: 0, autoReplyAccounts: 0 }
  } finally {
    statsLoading.value = false
  }
}

async function loadProducts() {
  loading.value = true
  loadError.value = ''
  try {
    // 后端参数：current/size/keyword/status/excludeStatus/accountId
    const params = {
      current: currentPage.value,
      size: pageSize.value
    }
    const kw = (searchKeywordInternal.value || '').trim()
    if (kw) params.keyword = kw
    if (activeStatus.value === 'onSale') params.status = FE_STATUS_ON_SALE
    else if (activeStatus.value === 'offShelf') params.status = FE_STATUS_OFF_SHELF
    // all 不传 status，但排除已删除（excludeStatus=3）
    if (activeStatus.value === 'all') params.excludeStatus = FE_STATUS_DELETED

    const res = await getGoods(params)
    products.value = recordsOf(res)
    total.value = totalOf(res, products.value.length)
  } catch (error) {
    products.value = []
    total.value = 0
    loadError.value = error?.message || '加载失败，请检查网络后重试'
  } finally {
    loading.value = false
  }
}

function refreshProduct(updated) {
  if (!updated) return
  const idx = products.value.findIndex(p => p.id === updated.id)
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

onMounted(() => {
  loadStats()
  loadProducts()
})
</script>

<style scoped>
.m-products-page {
  padding: 0 var(--m-space-3);
}

/* ===== 顶部统计卡 ===== */
.m-stats-grid,
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
  font-family: inherit;
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

.m-stat-value {
  font-size: var(--m-font-size-h1);
  font-weight: var(--m-font-weight-extrabold);
  color: var(--m-color-text-primary);
  line-height: 1;
}

/* ===== Tabs ===== */
.m-tabs-bar {
  margin-bottom: var(--m-space-2);
}

.m-tabs-scroll {
  display: flex;
  gap: var(--m-space-1);
  overflow-x: auto;
  scrollbar-width: none;
  padding-bottom: 2px;
}

.m-tabs-scroll::-webkit-scrollbar {
  display: none;
}

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
  font-family: inherit;
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

/* ===== 工具栏 ===== */
.m-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-space-2) 0 var(--m-space-3);
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
  font-family: inherit;
}

.m-toolbar-btn:active {
  background: var(--m-color-bg-hover);
}

.m-toolbar-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.m-toolbar-batch {
  background: var(--m-color-primary);
  border: none;
  color: var(--m-color-text-inverse);
  font-weight: var(--m-font-weight-semibold);
}

.m-toolbar-batch:active {
  background: var(--m-color-primary-active);
}

.m-toolbar-batch:disabled {
  background: var(--m-color-primary-bg-hover);
  opacity: 0.7;
}

/* ===== 列表 ===== */
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
  width: 88px;
  height: 88px;
  border-radius: var(--m-radius-lg);
  overflow: hidden;
  flex-shrink: 0;
  background: var(--m-color-bg-subtle);
  position: relative;
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

.m-product-status-tag {
  position: absolute;
  top: var(--m-space-1);
  left: var(--m-space-1);
  font-size: 10px;
  font-weight: var(--m-font-weight-semibold);
  padding: 2px 6px;
  border-radius: var(--m-radius-sm);
  color: #fff;
  backdrop-filter: blur(4px);
}

.m-tag-onshelf {
  background: rgba(22, 191, 120, 0.9);
}

.m-tag-offshelf {
  background: rgba(140, 152, 174, 0.9);
}

.m-tag-deleted {
  background: rgba(255, 71, 87, 0.9);
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

.m-stock-tag {
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-semibold);
  padding: 2px 6px;
  border-radius: var(--m-radius-sm);
}

.m-stock-low {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning-text);
}

.m-stock-out {
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger-text);
}

.m-product-meta-row {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  flex-wrap: wrap;
}

.m-meta-chip {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
  background: var(--m-color-bg-subtle);
  padding: 2px 6px;
  border-radius: var(--m-radius-sm);
}

.m-meta-cat {
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  background: var(--m-color-success);
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

/* ===== 分页 ===== */
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
  font-family: inherit;
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

/* ===== 骨架屏 ===== */
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
  width: 88px;
  height: 88px;
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

/* ===== 空状态 ===== */
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
  border: 1px solid var(--m-color-border);
  background: var(--m-color-bg-card);
  color: var(--m-color-text-secondary);
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-1);
  font-family: inherit;
}

.m-empty-btn-primary {
  background: var(--m-color-primary);
  border-color: var(--m-color-primary);
  color: var(--m-color-text-inverse);
}

/* ===== 菜单/底部弹窗 ===== */
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

.m-action-header {
  padding: var(--m-space-3) var(--m-space-4);
  border-bottom: 1px solid var(--m-color-border-light);
  margin-bottom: var(--m-space-1);
}

.m-action-header-title {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  font-family: inherit;
}

.m-action-item:active {
  background: var(--m-color-bg-hover);
}

.m-action-item.m-action-warn {
  color: var(--m-color-warning-text);
}

.m-action-item.m-action-success {
  color: var(--m-color-success-text);
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

.m-sheet-title {
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
  margin-bottom: var(--m-space-2);
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
  font-family: inherit;
}

.m-sheet-option.active {
  color: var(--m-color-primary);
  font-weight: var(--m-font-weight-semibold);
}

/* ===== 对话框 ===== */
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
  font-family: inherit;
}

.m-dialog-btn-cancel {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
}

.m-dialog-btn-confirm {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
}

.m-dialog-btn-danger {
  background: var(--m-color-danger);
  color: var(--m-color-text-inverse);
}

.m-safe-bottom {
  height: calc(var(--m-space-4) + var(--m-safe-area-bottom));
}

/* ===== 批量工具栏 ===== */
.m-batch-toolbar {
  position: fixed;
  left: var(--m-space-2);
  right: var(--m-space-2);
  bottom: calc(72px + var(--m-safe-area-bottom));
  background: var(--m-color-bg-elevated);
  border-radius: var(--m-radius-xl);
  box-shadow: var(--m-shadow-elevated);
  padding: var(--m-space-3);
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
  font-family: inherit;
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
  font-family: inherit;
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

/* ===== 全局 Toast（与详情页共用样式） ===== */
:global(.m-toast-global) {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) scale(0.9);
  background: rgba(21, 33, 61, 0.94);
  color: #fff;
  padding: 12px 20px;
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-body-sm);
  font-weight: 500;
  z-index: 9999;
  opacity: 0;
  pointer-events: none;
  transition: all 0.2s;
  max-width: 80%;
  text-align: center;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

:global(.m-toast-global.m-toast-show) {
  opacity: 1;
  transform: translate(-50%, -50%) scale(1);
}

:global(.m-toast-global.m-toast-error) {
  background: rgba(220, 38, 38, 0.94);
}

/* ===== 小屏适配 ===== */
@media (max-width: 360px) {
  .m-products-page {
    padding: 0 var(--m-space-2);
  }
  .m-stat-card {
    padding: var(--m-space-2);
    gap: var(--m-space-2);
  }
  .m-stat-icon {
    width: 38px;
    height: 38px;
  }
  .m-stat-value {
    font-size: 18px;
  }
  .m-product-cover {
    width: 76px;
    height: 76px;
  }
  .m-meta-chip {
    font-size: 10px;
  }
}
</style>
