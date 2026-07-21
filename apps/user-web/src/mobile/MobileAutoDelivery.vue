<template>
  <div class="m-ad">
    <!-- 顶部 Hero -->
    <section class="m-ad-hero">
      <div class="m-ad-hero-head">
        <div class="m-ad-hero-badge">
          <span class="m-ad-hero-dot"></span>
          <span>自动发货</span>
        </div>
        <h1 class="m-ad-hero-title">自动发货管理</h1>
        <p class="m-ad-hero-sub">付款后自动处理订单发货</p>
      </div>
      <div class="m-ad-hero-kpi" @click="filterEnabled">
        <div class="m-ad-hero-kpi-icon m-ad-hero-kpi-icon--primary">
          <MIcon name="bag" :size="22" />
        </div>
        <div class="m-ad-hero-kpi-info">
          <div class="m-ad-hero-kpi-label">已启用自动发货</div>
          <div class="m-ad-hero-kpi-value">{{ statsLoading ? '—' : formatNumber(stats.enabledGoods) }}</div>
          <div class="m-ad-hero-kpi-sub">全部商品</div>
        </div>
        <MIcon name="chevronRight" :size="20" class="m-ad-hero-kpi-arrow" />
      </div>
    </section>

    <!-- 统计 2×2 -->
    <div class="m-ad-stat-grid">
      <div v-for="card in statCards" :key="card.key" class="m-ad-stat-card" @click="handleStatClick(card.key)">
        <div class="m-ad-stat-icon" :class="`m-ad-stat-icon--${card.color}`">
          <MIcon :name="card.icon" :size="20" />
        </div>
        <div class="m-ad-stat-info">
          <div class="m-ad-stat-title">{{ card.title }}</div>
          <div class="m-ad-stat-value" :class="`m-ad-stat-value--${card.color}`">{{ statsLoading ? '—' : formatNumber(card.value) }}</div>
          <div class="m-ad-stat-desc">{{ card.desc }}</div>
        </div>
      </div>
    </div>

    <!-- 提示 -->
    <div class="m-ad-notice">
      <div class="m-ad-notice-icon">
        <MIcon name="info" :size="16" />
      </div>
      <div class="m-ad-notice-text">
        <b>付款后发货</b>会在系统定时扫描自动执行；<b>确认收货后赠送</b>和<b>好评后赠送</b>可在发货记录页手动触发，也可接入 E店易插件自动化。
      </div>
    </div>

    <!-- 搜索 -->
    <div class="m-ad-search-wrap">
      <div class="m-ad-search">
        <MIcon name="search" :size="18" class="m-ad-search-icon" />
        <input
          ref="searchInputRef"
          v-model="searchKeyword"
          type="text"
          class="m-ad-search-input"
          placeholder="搜索商品名称 / ID"
          aria-label="搜索商品"
          @keyup.enter="handleSearch"
          @input="debouncedSearch"
        />
        <button v-if="searchKeyword" class="m-ad-search-clear" @click="clearSearch" aria-label="清空搜索">
          <MIcon name="x" :size="16" />
        </button>
      </div>
    </div>

    <!-- 筛选 -->
    <div class="m-ad-filter-bar">
      <div class="m-ad-filter-grid">
        <button
          v-for="filter in filterOptions"
          :key="filter.key"
          class="m-ad-filter-chip"
          :class="{ 'm-ad-filter-chip--active': isFilterActive(filter) }"
          @click="openFilter(filter)"
        >
          <span>{{ getFilterLabel(filter) }}</span>
          <MIcon name="chevronDown" :size="14" />
        </button>
      </div>
    </div>

    <!-- 工具栏 -->
    <div class="m-ad-toolbar">
      <div class="m-ad-count">
        共 <b>{{ productsLoading ? '—' : total }}</b> 个商品
      </div>
      <div class="m-ad-toolbar-actions">
        <button class="m-ad-btn m-ad-btn-primary m-ad-btn-sm" @click="toggleBatchMode">
          {{ batchMode ? '取消批量' : '批量设置' }}
        </button>
        <button class="m-ad-btn m-ad-btn-outline m-ad-btn-sm" @click="goToSourceLibrary">
          货源库
        </button>
      </div>
    </div>

    <!-- 批量栏 -->
    <div v-if="batchMode" class="m-ad-batch-bar">
      <label class="m-ad-batch-select-all">
        <input type="checkbox" :checked="isAllSelected" @change="toggleSelectAll" />
        <span>全选当前页</span>
      </label>
      <span class="m-ad-batch-count">已选 {{ selectedIds.size }} 个</span>
      <button class="m-ad-btn m-ad-btn-primary m-ad-btn-sm" :disabled="selectedIds.size === 0 || batchLoading" @click="openBatchAction">
        {{ batchLoading ? '处理中...' : '批量操作' }}
      </button>
    </div>

    <!-- 加载骨架 -->
    <div v-if="productsLoading && products.length === 0" class="m-ad-skeleton-list">
      <div v-for="i in 5" :key="i" class="m-ad-skeleton-card">
        <div class="m-ad-skeleton-img"></div>
        <div class="m-ad-skeleton-body">
          <div class="m-ad-skeleton-line m-ad-skeleton-title"></div>
          <div class="m-ad-skeleton-line m-ad-skeleton-meta"></div>
          <div class="m-ad-skeleton-tags">
            <div class="m-ad-skeleton-tag"></div>
            <div class="m-ad-skeleton-tag"></div>
          </div>
        </div>
      </div>
    </div>

    <MobileUnavailableState v-else-if="loadError" compact title="数据加载失败" :description="loadError" @retry="loadData" />

    <!-- 空状态 -->
    <div v-else-if="products.length === 0" class="m-ad-empty">
      <div class="m-ad-empty-icon">
        <MIcon name="bag" :size="48" />
      </div>
      <div class="m-ad-empty-text">{{ hasFilters ? '暂无符合条件的商品' : '暂无自动发货商品' }}</div>
      <div class="m-ad-empty-desc">{{ hasFilters ? '请尝试调整筛选条件' : '请先同步商品或前往商品管理配置' }}</div>
      <button v-if="hasFilters" class="m-ad-btn m-ad-btn-primary m-ad-btn-sm" @click="clearFilters">清除筛选</button>
      <button v-else class="m-ad-btn m-ad-btn-primary m-ad-btn-sm" @click="goToProducts">前往商品管理</button>
    </div>

    <!-- 商品列表（行式卡片） -->
    <div v-else class="m-ad-list">
      <div
        v-for="prod in products"
        :key="prod.id"
        class="m-ad-product-card"
        :class="{ 'm-ad-product-card--batch': batchMode }"
      >
        <div v-if="batchMode" class="m-ad-product-check">
          <input type="checkbox" :checked="selectedIds.has(prod.id)" @change="toggleSelect(prod.id)" :aria-label="`选择商品 ${prod.name}`" />
        </div>
        <div class="m-ad-product-img-wrap" @click="goToProductDetail(prod)">
          <img v-if="prod.coverPic" :src="prod.coverPic" :alt="prod.name" class="m-ad-product-img" @error="onImgError($event, prod)" />
          <div v-else class="m-ad-product-img-placeholder">
            <MIcon name="bag" :size="24" />
          </div>
        </div>
        <div class="m-ad-product-body">
          <div class="m-ad-product-top">
            <div class="m-ad-product-info">
              <div class="m-ad-product-name" @click="goToConfig(prod)" :title="prod.name">{{ prod.name || '未命名商品' }}</div>
              <div class="m-ad-product-meta">
                <span class="m-ad-product-id" @click="copyId(prod)" role="button" tabindex="0" aria-label="复制商品ID">ID: {{ prod.id }}</span>
                <span class="m-ad-product-price" :class="{ 'm-ad-price--abnormal': isAbnormalPrice(prod) }">¥{{ formatPrice(prod.price) }}</span>
              </div>
              <div class="m-ad-product-tags">
                <span class="m-ad-tag m-ad-tag--success">{{ getDeliveryModeLabel(prod) }}</span>
                <span v-if="getConfigStatus(prod) === 'unconfigured'" class="m-ad-tag m-ad-tag--neutral">未配置</span>
                <span v-else-if="getConfigStatus(prod) === 'abnormal'" class="m-ad-tag m-ad-tag--danger">配置异常</span>
                <span v-else-if="prod.sourceName" class="m-ad-tag m-ad-tag--info">货源：{{ prod.sourceName }}</span>
              </div>
            </div>
            <div class="m-ad-product-right">
              <div class="m-ad-stock-badge" :class="stockClass(prod)" @click="goToStock(prod)">
                <span>{{ stockLabel(prod) }}</span>
                <strong>{{ formatStock(prod) }}</strong>
              </div>
              <button class="m-ad-config-btn" @click="goToConfig(prod)" :aria-label="`配置商品 ${prod.name}`">配置</button>
              <button
                class="m-ad-switch"
                :class="{ 'm-ad-switch--on': prod.deliveryEnabled, 'm-ad-switch--loading': prod.switchLoading }"
                :disabled="prod.switchLoading"
                @click="toggleDelivery(prod)"
                role="switch"
                :aria-checked="prod.deliveryEnabled ? 'true' : 'false'"
                :aria-label="prod.deliveryEnabled ? '关闭自动发货' : '开启自动发货'"
              >
                <span class="m-ad-switch-knob"></span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <div v-if="loadingMore" class="m-ad-loading-more">加载中...</div>
      <div v-else-if="hasMore" class="m-ad-load-more">
        <button class="m-ad-btn m-ad-btn-outline" @click="loadMore">加载更多</button>
      </div>
      <div v-else-if="products.length > 0" class="m-ad-no-more">没有更多商品</div>
    </div>

    <div class="m-ad-safe-bottom"></div>

    <!-- 筛选 Sheet -->
    <div v-if="activeFilter" class="m-ad-sheet-mask" @click="closeFilter"></div>
    <div v-if="activeFilter" class="m-ad-sheet" :class="{ 'm-ad-sheet--open': activeFilter }">
      <div class="m-ad-sheet-handle"></div>
      <div class="m-ad-sheet-header">
        <h3>{{ activeFilter.title }}</h3>
        <button class="m-ad-sheet-close" @click="closeFilter" aria-label="关闭">
          <MIcon name="x" :size="20" />
        </button>
      </div>
      <div class="m-ad-sheet-body">
        <div class="m-ad-sheet-search" v-if="activeFilter.key === 'account'">
          <MIcon name="search" :size="16" class="m-ad-sheet-search-icon" />
          <input v-model="filterSearch" class="m-ad-sheet-search-input" placeholder="搜索账号" />
        </div>
        <div class="m-ad-sheet-options">
          <button
            v-for="opt in getFilterOptions(activeFilter)"
            :key="opt.value"
            class="m-ad-sheet-option"
            :class="{ 'm-ad-sheet-option--active': isOptionSelected(activeFilter, opt) }"
            @click="selectFilterOption(activeFilter, opt)"
          >
            <span>{{ opt.label }}</span>
            <MIcon v-if="isOptionSelected(activeFilter, opt)" name="check" :size="18" class="m-ad-sheet-check" />
          </button>
        </div>
      </div>
      <div class="m-ad-sheet-footer">
        <button class="m-ad-btn m-ad-btn-outline" @click="resetFilter(activeFilter)">重置</button>
        <button class="m-ad-btn m-ad-btn-primary" @click="applyFilter">确定</button>
      </div>
    </div>

    <!-- 批量操作 Sheet -->
    <div v-if="showBatchDialog" class="m-ad-sheet-mask" @click.self="showBatchDialog = false"></div>
    <div v-if="showBatchDialog" class="m-ad-sheet m-ad-sheet--open">
      <div class="m-ad-sheet-handle"></div>
      <div class="m-ad-sheet-header">
        <h3>批量操作</h3>
        <button class="m-ad-sheet-close" @click="showBatchDialog = false" aria-label="关闭">
          <MIcon name="x" :size="20" />
        </button>
      </div>
      <div class="m-ad-sheet-body">
        <div class="m-ad-batch-hint">将对 <b>{{ selectedIds.size }}</b> 个商品执行操作</div>
        <div class="m-ad-form-row">
          <label>操作类型</label>
          <select v-model="batchActionForm.action" class="m-ad-select">
            <option value="enable">批量启用</option>
            <option value="disable">批量关闭</option>
          </select>
        </div>
      </div>
      <div class="m-ad-sheet-footer">
        <button class="m-ad-btn m-ad-btn-outline" @click="showBatchDialog = false">取消</button>
        <button class="m-ad-btn m-ad-btn-primary" :disabled="batchLoading" @click="executeBatchAction">
          {{ batchLoading ? '执行中...' : '确认执行' }}
        </button>
      </div>
    </div>

    <!-- 帮助 Sheet -->
    <div v-if="showHelp" class="m-ad-sheet-mask" @click="showHelp = false"></div>
    <div v-if="showHelp" class="m-ad-sheet m-ad-sheet--open" style="height: 70vh;">
      <div class="m-ad-sheet-handle"></div>
      <div class="m-ad-sheet-header">
        <h3>自动发货帮助</h3>
        <button class="m-ad-sheet-close" @click="showHelp = false" aria-label="关闭">
          <MIcon name="x" :size="20" />
        </button>
      </div>
      <div class="m-ad-sheet-body m-ad-help-body">
        <div class="m-ad-help-section">
          <h4>发货方式说明</h4>
          <ul>
            <li><b>付款后发货</b>：买家付款后系统自动发送发货内容</li>
            <li><b>确认收货后赠送</b>：买家确认收货后可手动触发赠送</li>
            <li><b>好评后赠送</b>：买家好评后可手动触发赠送</li>
          </ul>
        </div>
        <div class="m-ad-help-section">
          <h4>配置步骤</h4>
          <ol>
            <li>在货源库准备好发货内容或卡密</li>
            <li>点击商品卡片的"配置"按钮</li>
            <li>选择发货模式并绑定货源</li>
            <li>开启自动发货开关</li>
          </ol>
        </div>
        <div class="m-ad-help-section">
          <h4>注意事项</h4>
          <p>• 未配置货源的商品无法开启自动发货</p>
          <p>• 库存不足时请及时补充，否则发货会失败</p>
          <p>• 建议先使用测试账号验证发货内容</p>
        </div>
      </div>
    </div>
  </div>
</template>


<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import MIcon from './MIcon.vue'
import MobileUnavailableState from './MobileUnavailableState.vue'
import { getDeliveryStats, batchSetDeliveryRules, toggleGoodsDeliveryConfig, batchGetGoodsDeliveryConfigs } from '../api/autoDelivery.js'
import { getGoods } from '../api/goods.js'
import { getLiteAccounts } from '../api/accounts.js'
import { globalConfirm } from '../composables/confirmState.js'

const emit = defineEmits(['navigate', 'force-desktop', 'back'])

const searchInputRef = ref(null)
const statsLoading = ref(true)
const productsLoading = ref(true)
const loadingMore = ref(false)
const loadError = ref('')
const stats = ref({
  todaySuccess: 0,
  todayFail: 0,
  pendingOrders: 0,
  lowStockGoods: 0,
  enabledGoods: 0
})
const products = ref([])
const accounts = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const hasMore = ref(false)
const searchKeyword = ref('')
const filterSearch = ref('')
const filters = ref({
  accountId: '',
  deliveryMode: '',
  configStatus: '',
  goodsStatus: ''
})
const activeFilter = ref(null)
const batchMode = ref(false)
const selectedIds = ref(new Set())
const batchLoading = ref(false)
const showBatchDialog = ref(false)
const batchActionForm = ref({
  action: 'enable'
})
const showHelp = ref(false)
let searchTimer = null

const statCards = computed(() => [
  { key: 'todaySuccess', title: '今日发货成功', value: stats.value.todaySuccess, desc: '今日', icon: 'shield', color: 'green' },
  { key: 'todayFail', title: '今日失败', value: stats.value.todayFail, desc: '今日', icon: 'warning', color: 'orange' },
  { key: 'pendingOrders', title: '待处理订单', value: stats.value.pendingOrders, desc: '待处理', icon: 'clock', color: 'blue' },
  { key: 'lowStockGoods', title: '库存不足', value: stats.value.lowStockGoods, desc: '需关注', icon: 'warning', color: 'orange' }
])

const filterOptions = computed(() => [
  { key: 'account', title: '全部账号', options: [{ value: '', label: '全部账号' }, ...accounts.value.map(a => ({ value: a.id, label: a.nickname || a.remark || a.username || `账号${a.id}` }))] },
  { key: 'deliveryMode', title: '发货方式', options: [
    { value: '', label: '全部发货方式' },
    { value: 'payDelivery', label: '付款后发货' },
    { value: 'confirmDelivery', label: '确认收货后赠送' },
    { value: 'reviewDelivery', label: '好评后赠送' }
  ]},
  { key: 'configStatus', title: '配置状态', options: [
    { value: '', label: '全部配置状态' },
    { value: 'configured', label: '已配置' },
    { value: 'unconfigured', label: '未配置' },
    { value: 'abnormal', label: '配置异常' },
    { value: 'lowStock', label: '库存不足' }
  ]},
  { key: 'goodsStatus', title: '商品状态', options: [
    { value: '', label: '全部商品' },
    { value: '1', label: '上架中' },
    { value: '0', label: '下架中' }
  ]}
])

const hasFilters = computed(() => {
  return searchKeyword.value || Object.values(filters.value).some(v => v !== '')
})

const isAllSelected = computed(() => {
  return products.value.length > 0 && products.value.every(p => selectedIds.value.has(p.id))
})

const deliveryModeLabels = {
  payDelivery: '付款后发货',
  confirmDelivery: '确认收货后赠送',
  reviewDelivery: '好评后赠送'
}

function formatNumber(num) {
  if (num == null || num === undefined || isNaN(num)) return 0
  return Number(num).toLocaleString()
}

function formatPrice(price) {
  if (price == null || price === '') return '—'
  const num = Number(price)
  if (isNaN(num)) return price
  return Number.isInteger(num) ? String(num) : num.toFixed(2)
}

function formatStock(prod) {
  if (prod.stock == null || prod.stock === undefined) return '—'
  const stock = Number(prod.stock)
  if (isNaN(stock)) return '—'
  if (stock >= 10000) return (stock / 10000).toFixed(stock >= 100000 ? 0 : 1) + 'w'
  return String(stock)
}

function isAbnormalPrice(prod) {
  return prod.price != null && Number(prod.price) <= 0
}

function getDeliveryModeLabel(prod) {
  if (prod.deliveryMode && deliveryModeLabels[prod.deliveryMode]) {
    return deliveryModeLabels[prod.deliveryMode]
  }
  return '未设置发货方式'
}

function getConfigStatus(prod) {
  if (prod._configUnavailable) return 'abnormal'
  if (!prod._config) return 'unconfigured'
  if (prod.stock != null && Number(prod.stock) <= 0) return 'lowStock'
  return 'configured'
}

function stockClass(prod) {
  const status = getConfigStatus(prod)
  if (status === 'lowStock') return 'm-ad-stock-low'
  if (prod._config && prod.deliveryEnabled) return 'm-ad-stock-ok'
  return 'm-ad-stock-unknown'
}

function stockLabel(prod) {
  const status = getConfigStatus(prod)
  if (status === 'lowStock') return '库存不足'
  if (prod._config && prod.deliveryEnabled) return '库存充足'
  return '库存状态'
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
  return filter.options.filter(o => o.label.toLowerCase().includes(keyword))
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
  } else {
    filters.value = { accountId: '', deliveryMode: '', configStatus: '', goodsStatus: '' }
    searchKeyword.value = ''
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
  loadProducts()
}

function clearFilters() {
  filters.value = { accountId: '', deliveryMode: '', configStatus: '', goodsStatus: '' }
  searchKeyword.value = ''
  applyFilter()
}

function handleSearch() {
  page.value = 1
  loadProducts()
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

function toggleBatchMode() {
  batchMode.value = !batchMode.value
  if (!batchMode.value) {
    selectedIds.value.clear()
    showBatchDialog.value = false
  }
}

function toggleSelect(id) {
  if (selectedIds.value.has(id)) {
    selectedIds.value.delete(id)
  } else {
    selectedIds.value.add(id)
  }
}

function toggleSelectAll() {
  if (isAllSelected.value) {
    products.value.forEach(p => selectedIds.value.delete(p.id))
  } else {
    products.value.forEach(p => selectedIds.value.add(p.id))
  }
}

function openBatchAction() {
  showBatchDialog.value = true
}

async function executeBatchAction() {
  if (selectedIds.value.size === 0) return
  batchLoading.value = true
  try {
    const ids = Array.from(selectedIds.value)
    const enabled = batchActionForm.value.action === 'enable'
    await batchSetDeliveryRules({
      goodsIds: ids,
      action: batchActionForm.value.action,
      enabled: enabled ? 1 : 0
    })
    window.dispatchEvent(new CustomEvent('xya-toast', { detail: { message: `批量${enabled ? '启用' : '关闭'}成功` } }))
    showBatchDialog.value = false
    toggleBatchMode()
    await Promise.all([loadStats(), loadProducts()])
  } catch (e) {
    window.dispatchEvent(new CustomEvent('xya-toast', { detail: { message: e?.message || '批量操作失败', isError: true } }))
  } finally {
    batchLoading.value = false
  }
}

async function loadStats() {
  statsLoading.value = true
  try {
    const res = await getDeliveryStats()
    const data = res?.data || {}
    stats.value = {
      todaySuccess: data.todaySuccess ?? 0,
      todayFail: data.todayFail ?? 0,
      pendingOrders: data.pendingOrders ?? 0,
      lowStockGoods: data.lowStockGoods ?? 0,
      enabledGoods: data.enabledGoods ?? 0
    }
  } catch (e) {
    stats.value = { todaySuccess: 0, todayFail: 0, pendingOrders: 0, lowStockGoods: 0, enabledGoods: 0 }
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

async function loadProducts(append = false) {
  if (!append) {
    productsLoading.value = true
  } else {
    loadingMore.value = true
  }
  loadError.value = ''
  try {
    const params = {
      page: page.value,
      pageSize: pageSize.value
    }
    if (filters.value.accountId) params.xianyuAccountId = filters.value.accountId
    if (searchKeyword.value) params.keyword = searchKeyword.value
    const res = await getGoods(params)
    const data = res?.data
    let list = data?.records || data?.list || (Array.isArray(data) ? data : [])
    total.value = data?.total || list.length
    const goodsIds = list.map(g => g.id).filter(id => id != null)
    let configsMap = {}
    if (goodsIds.length > 0) {
      try {
        const cfgRes = await batchGetGoodsDeliveryConfigs(goodsIds)
        configsMap = cfgRes?.data || {}
      } catch (e) {
        configsMap = {}
      }
    }
    list = list.map(g => {
      const cfg = configsMap[g.id]
      return {
        ...g,
        _config: cfg || null,
        _configUnavailable: false,
        deliveryEnabled: cfg?.payDelivery?.enabled === 1 || cfg?.confirmDelivery?.enabled === 1 || cfg?.reviewDelivery?.enabled === 1,
        deliveryMode: cfg?.payDelivery?.enabled === 1 ? 'payDelivery' : (cfg?.confirmDelivery?.enabled === 1 ? 'confirmDelivery' : (cfg?.reviewDelivery?.enabled === 1 ? 'reviewDelivery' : null)),
        sourceName: cfg?.sourceName || cfg?.sourceTitle || null,
        stock: g.stock ?? cfg?.stock ?? null,
        switchLoading: false
      }
    })
    if (filters.value.configStatus) {
      list = list.filter(p => {
        const status = getConfigStatus(p)
        return status === filters.value.configStatus
      })
    }
    if (filters.value.deliveryMode) {
      list = list.filter(p => p.deliveryMode === filters.value.deliveryMode)
    }
    if (append) {
      products.value = [...products.value, ...list]
    } else {
      products.value = list
    }
    hasMore.value = products.value.length < total.value
  } catch (e) {
    loadError.value = e?.message || '请检查网络连接后重试'
    if (!append) products.value = []
  } finally {
    productsLoading.value = false
    loadingMore.value = false
  }
}

async function loadMore() {
  if (loadingMore.value || !hasMore.value) return
  page.value++
  await loadProducts(true)
}

async function loadData() {
  await Promise.all([loadStats(), loadAccounts()])
  await loadProducts()
}

async function toggleDelivery(prod) {
  if (prod.switchLoading) return
  const originalState = prod.deliveryEnabled
  if (!originalState) {
    const status = getConfigStatus(prod)
    if (status === 'unconfigured') {
      window.dispatchEvent(new CustomEvent('xya-toast', { detail: { message: '请先完成自动发货配置', isError: true } }))
      goToConfig(prod)
      return
    }
    if (status === 'lowStock') {
      const confirmed = await globalConfirm.confirm('库存不足', '当前商品库存不足，是否仍要开启自动发货？', '继续开启')
      if (!confirmed) return
    }
  } else {
    const confirmed = await globalConfirm.confirm('关闭自动发货', '关闭后，新订单将不再自动发货，是否继续？', '确认关闭')
    if (!confirmed) return
  }
  prod.switchLoading = true
  prod.deliveryEnabled = !originalState
  try {
    const timing = prod.deliveryMode || 'payDelivery'
    await toggleGoodsDeliveryConfig(prod.id, timing, prod.deliveryEnabled ? 1 : 0)
    window.dispatchEvent(new CustomEvent('xya-toast', { detail: { message: prod.deliveryEnabled ? '已开启自动发货' : '已关闭自动发货' } }))
    await loadStats()
  } catch (e) {
    prod.deliveryEnabled = originalState
    window.dispatchEvent(new CustomEvent('xya-toast', { detail: { message: e?.message || '操作失败，请重试', isError: true } }))
  } finally {
    prod.switchLoading = false
  }
}

function goToConfig(prod) {
  emit('navigate', 'auto-delivery-config', { productId: prod.id })
  window.dispatchEvent(new CustomEvent('xya-open-delivery-config', { detail: { goodsId: prod.id } }))
}

function goToProductDetail(prod) {
  emit('navigate', 'product-detail', { id: prod.id })
}

function goToProducts() {
  emit('navigate', 'products')
}

function goToSourceLibrary() {
  emit('navigate', 'delivery-source-library')
}

function goToStock(prod) {
  emit('navigate', 'product-detail', { id: prod.id })
}

function handleStatClick(key) {
  if (key === 'lowStockGoods') {
    filters.value.configStatus = 'lowStock'
    applyFilter()
  }
}

function filterEnabled() {
  filters.value.configStatus = 'configured'
  applyFilter()
}

function onImgError(e, prod) {
  prod.coverPic = ''
}

async function copyId(prod) {
  try {
    await navigator.clipboard.writeText(String(prod.id))
    window.dispatchEvent(new CustomEvent('xya-toast', { detail: { message: 'ID 已复制' } }))
  } catch (e) {
    window.dispatchEvent(new CustomEvent('xya-toast', { detail: { message: '复制失败', isError: true } }))
  }
}

function focusSearch() {
  if (searchInputRef.value) {
    searchInputRef.value.focus()
  }
}

function openHelp() {
  showHelp.value = true
  document.body.style.overflow = 'hidden'
}

defineExpose({ focusSearch, openHelp })

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
.m-ad {
  padding: var(--m-space-3) var(--m-space-3) 0;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
}

/* === Hero === */
.m-ad-hero {
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-4);
  margin-bottom: var(--m-space-3);
  box-shadow: var(--m-shadow-card);
}
.m-ad-hero-head {
  margin-bottom: var(--m-space-4);
}
.m-ad-hero-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-1);
  background: var(--m-color-success-bg);
  color: var(--m-color-success-text);
  padding: var(--m-space-1) var(--m-space-3);
  border-radius: var(--m-radius-pill);
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-semibold);
  margin-bottom: var(--m-space-3);
  border: 1px solid var(--m-color-success-border);
}
.m-ad-hero-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--m-radius-circle);
  background: var(--m-color-success);
  animation: m-ad-pulse 1.6s ease-in-out infinite;
}
@keyframes m-ad-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.85); }
}
.m-ad-hero-title {
  margin: 0 0 var(--m-space-1);
  font-size: var(--m-font-size-h1);
  font-weight: var(--m-font-weight-extrabold);
  color: var(--m-color-text-primary);
  line-height: var(--m-line-height-tight);
  letter-spacing: -0.3px;
}
.m-ad-hero-sub {
  margin: 0;
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}
.m-ad-hero-kpi {
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
  padding: var(--m-space-3);
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-lg);
  cursor: pointer;
  transition: transform 0.15s;
}
.m-ad-hero-kpi:active {
  transform: scale(0.99);
}
.m-ad-hero-kpi-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--m-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-ad-hero-kpi-icon--primary {
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
}
.m-ad-hero-kpi-info {
  flex: 1;
  min-width: 0;
}
.m-ad-hero-kpi-label {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  font-weight: var(--m-font-weight-medium);
}
.m-ad-hero-kpi-value {
  font-size: var(--m-font-size-h1);
  font-weight: var(--m-font-weight-extrabold);
  color: var(--m-color-text-primary);
  line-height: var(--m-line-height-tight);
  font-variant-numeric: tabular-nums;
}
.m-ad-hero-kpi-sub {
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
}
.m-ad-hero-kpi-arrow {
  color: var(--m-color-text-disabled);
  flex-shrink: 0;
}

/* === 统计 2×2 === */
.m-ad-stat-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--m-space-3);
  margin-bottom: var(--m-space-3);
}
.m-ad-stat-card {
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3);
  box-shadow: var(--m-shadow-card);
  display: flex;
  align-items: flex-start;
  gap: var(--m-space-3);
  cursor: pointer;
  transition: transform 0.15s;
}
.m-ad-stat-card:active {
  transform: scale(0.98);
}
.m-ad-stat-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--m-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-ad-stat-icon--green {
  background: var(--m-color-success-bg);
  color: var(--m-color-success);
}
.m-ad-stat-icon--orange {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning);
}
.m-ad-stat-icon--blue {
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
}
.m-ad-stat-info {
  flex: 1;
  min-width: 0;
}
.m-ad-stat-title {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  font-weight: var(--m-font-weight-medium);
}
.m-ad-stat-value {
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-extrabold);
  color: var(--m-color-text-primary);
  line-height: var(--m-line-height-tight);
  font-variant-numeric: tabular-nums;
  margin-top: 2px;
}
.m-ad-stat-value--green {
  color: var(--m-color-success-text);
}
.m-ad-stat-value--orange {
  color: var(--m-color-warning-text);
}
.m-ad-stat-value--blue {
  color: var(--m-color-primary);
}
.m-ad-stat-desc {
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
  margin-top: 2px;
}

/* === 提示 === */
.m-ad-notice {
  display: flex;
  align-items: flex-start;
  gap: var(--m-space-2);
  padding: var(--m-space-3);
  background: var(--m-color-info-bg);
  border: 1px solid var(--m-color-info-border);
  border-radius: var(--m-radius-lg);
  margin-bottom: var(--m-space-3);
}
.m-ad-notice-icon {
  color: var(--m-color-info-text);
  flex-shrink: 0;
  margin-top: 1px;
}
.m-ad-notice-text {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-secondary);
  line-height: var(--m-line-height-base);
}
.m-ad-notice-text b {
  color: var(--m-color-info-text);
  font-weight: var(--m-font-weight-semibold);
}

/* === 搜索 === */
.m-ad-search-wrap {
  margin-bottom: var(--m-space-3);
}
.m-ad-search {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-2) var(--m-space-3);
}
.m-ad-search:focus-within {
  border-color: var(--m-color-primary);
  box-shadow: 0 0 0 3px var(--m-color-primary-bg);
}
.m-ad-search-icon {
  color: var(--m-color-text-tertiary);
  flex-shrink: 0;
}
.m-ad-search-input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-primary);
  font-family: inherit;
}
.m-ad-search-input::placeholder {
  color: var(--m-color-text-placeholder);
}
.m-ad-search-clear {
  background: transparent;
  border: none;
  color: var(--m-color-text-tertiary);
  cursor: pointer;
  padding: var(--m-space-1);
  border-radius: var(--m-radius-circle);
  display: flex;
  align-items: center;
  justify-content: center;
}
.m-ad-search-clear:active {
  background: var(--m-color-bg-subtle);
}

/* === 筛选 === */
.m-ad-filter-bar {
  margin-bottom: var(--m-space-3);
}
.m-ad-filter-grid {
  display: flex;
  gap: var(--m-space-2);
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  padding-bottom: 2px;
}
.m-ad-filter-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-1);
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-pill);
  padding: var(--m-space-1) var(--m-space-3);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-medium);
  color: var(--m-color-text-secondary);
  cursor: pointer;
  white-space: nowrap;
  font-family: inherit;
  transition: all 0.15s;
}
.m-ad-filter-chip--active {
  background: var(--m-color-primary-bg);
  border-color: var(--m-color-primary);
  color: var(--m-color-primary);
}

/* === 工具栏 === */
.m-ad-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--m-space-2);
}
.m-ad-count {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}
.m-ad-count b {
  color: var(--m-color-text-primary);
  font-weight: var(--m-font-weight-bold);
}
.m-ad-toolbar-actions {
  display: flex;
  gap: var(--m-space-2);
}

/* === 按钮 === */
.m-ad-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-1);
  border: none;
  border-radius: var(--m-radius-md);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s;
  padding: var(--m-space-2) var(--m-space-3);
}
.m-ad-btn-sm {
  padding: var(--m-space-1) var(--m-space-2);
  font-size: var(--m-font-size-tiny);
}
.m-ad-btn-primary {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
}
.m-ad-btn-primary:active {
  background: var(--m-color-primary-active);
}
.m-ad-btn-primary:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.m-ad-btn-outline {
  background: var(--m-color-bg-card);
  color: var(--m-color-primary);
  border: 1px solid var(--m-color-primary);
}
.m-ad-btn-outline:active {
  background: var(--m-color-primary-bg);
}

/* === 批量栏 === */
.m-ad-batch-bar {
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
  padding: var(--m-space-2) var(--m-space-3);
  background: var(--m-color-primary-bg);
  border-radius: var(--m-radius-md);
  margin-bottom: var(--m-space-3);
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-secondary);
}
.m-ad-batch-select-all {
  display: flex;
  align-items: center;
  gap: var(--m-space-1);
  cursor: pointer;
  font-weight: var(--m-font-weight-medium);
}
.m-ad-batch-count {
  flex: 1;
  color: var(--m-color-primary);
  font-weight: var(--m-font-weight-semibold);
}

/* === 骨架屏 === */
.m-ad-skeleton-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-3);
}
.m-ad-skeleton-card {
  display: flex;
  gap: var(--m-space-3);
  padding: var(--m-space-3);
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-lg);
}
.m-ad-skeleton-img {
  width: 56px;
  height: 56px;
  border-radius: var(--m-radius-md);
  background: var(--m-color-bg-subtle);
  flex-shrink: 0;
  animation: m-ad-shimmer 1.5s ease-in-out infinite;
}
.m-ad-skeleton-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
}
.m-ad-skeleton-line {
  height: 12px;
  border-radius: var(--m-radius-sm);
  background: var(--m-color-bg-subtle);
  animation: m-ad-shimmer 1.5s ease-in-out infinite;
}
.m-ad-skeleton-title {
  width: 60%;
}
.m-ad-skeleton-meta {
  width: 40%;
}
.m-ad-skeleton-tags {
  display: flex;
  gap: var(--m-space-2);
}
.m-ad-skeleton-tag {
  height: 18px;
  width: 60px;
  border-radius: var(--m-radius-pill);
  background: var(--m-color-bg-subtle);
  animation: m-ad-shimmer 1.5s ease-in-out infinite;
}
@keyframes m-ad-shimmer {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

/* === 空状态 === */
.m-ad-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--m-space-12) var(--m-space-4);
  gap: var(--m-space-2);
}
.m-ad-empty-icon {
  color: var(--m-color-text-disabled);
  margin-bottom: var(--m-space-2);
}
.m-ad-empty-text {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-secondary);
}
.m-ad-empty-desc {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  margin-bottom: var(--m-space-2);
}

/* === 商品列表（行式卡片） === */
.m-ad-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
}
.m-ad-product-card {
  display: flex;
  gap: var(--m-space-3);
  padding: var(--m-space-3);
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-lg);
  box-shadow: var(--m-shadow-card);
  transition: transform 0.15s;
}
.m-ad-product-card:active {
  transform: scale(0.99);
}
.m-ad-product-card--batch {
  border-color: var(--m-color-primary);
}
.m-ad-product-check {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}
.m-ad-product-check input {
  width: 18px;
  height: 18px;
  accent-color: var(--m-color-primary);
  cursor: pointer;
}
.m-ad-product-img-wrap {
  width: 56px;
  height: 56px;
  border-radius: var(--m-radius-md);
  overflow: hidden;
  flex-shrink: 0;
  background: var(--m-color-bg-subtle);
  cursor: pointer;
}
.m-ad-product-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.m-ad-product-img-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--m-color-text-disabled);
}
.m-ad-product-body {
  flex: 1;
  min-width: 0;
}
.m-ad-product-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--m-space-2);
}
.m-ad-product-info {
  flex: 1;
  min-width: 0;
}
.m-ad-product-name {
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}
.m-ad-product-meta {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  margin-top: 2px;
}
.m-ad-product-id {
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
  cursor: pointer;
  font-variant-numeric: tabular-nums;
}
.m-ad-product-price {
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-secondary);
  font-weight: var(--m-font-weight-semibold);
  font-variant-numeric: tabular-nums;
}
.m-ad-price--abnormal {
  color: var(--m-color-danger-text);
}
.m-ad-product-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--m-space-1);
  margin-top: var(--m-space-1);
}
.m-ad-tag {
  display: inline-flex;
  align-items: center;
  padding: 1px var(--m-space-2);
  border-radius: var(--m-radius-pill);
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-medium);
}
.m-ad-tag--success {
  background: var(--m-color-success-bg);
  color: var(--m-color-success-text);
}
.m-ad-tag--neutral {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-tertiary);
}
.m-ad-tag--danger {
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger-text);
}
.m-ad-tag--info {
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
}
.m-ad-product-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: var(--m-space-1);
  flex-shrink: 0;
}
.m-ad-stock-badge {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--m-space-1) var(--m-space-2);
  border-radius: var(--m-radius-md);
  cursor: pointer;
  min-width: 56px;
}
.m-ad-stock-badge span {
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-medium);
}
.m-ad-stock-badge strong {
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-bold);
  font-variant-numeric: tabular-nums;
}
.m-ad-stock-ok {
  background: var(--m-color-success-bg);
  color: var(--m-color-success-text);
}
.m-ad-stock-low {
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger-text);
}
.m-ad-stock-unknown {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-tertiary);
}
.m-ad-config-btn {
  border: 1px solid var(--m-color-primary);
  background: var(--m-color-bg-card);
  color: var(--m-color-primary);
  border-radius: var(--m-radius-md);
  padding: var(--m-space-1) var(--m-space-2);
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  font-family: inherit;
}
.m-ad-config-btn:active {
  background: var(--m-color-primary-bg);
}

/* === Switch 开关 === */
.m-ad-switch {
  position: relative;
  width: 40px;
  height: 22px;
  border: none;
  background: var(--m-color-text-disabled);
  border-radius: var(--m-radius-pill);
  cursor: pointer;
  transition: background 0.2s;
  flex-shrink: 0;
  padding: 0;
}
.m-ad-switch--on {
  background: var(--m-color-success);
}
.m-ad-switch--loading {
  opacity: 0.5;
  cursor: not-allowed;
}
.m-ad-switch:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.m-ad-switch-knob {
  position: absolute;
  width: 18px;
  height: 18px;
  left: 2px;
  top: 2px;
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-circle);
  transition: transform 0.2s;
  box-shadow: var(--m-shadow-card);
}
.m-ad-switch--on .m-ad-switch-knob {
  transform: translateX(18px);
}

/* === 加载更多 === */
.m-ad-loading-more,
.m-ad-no-more {
  text-align: center;
  padding: var(--m-space-4);
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}
.m-ad-load-more {
  display: flex;
  justify-content: center;
  padding: var(--m-space-3);
}

/* === 底部安全区 === */
.m-ad-safe-bottom {
  height: 80px;
}

/* === Sheet === */
.m-ad-sheet-mask {
  position: fixed;
  inset: 0;
  background: var(--m-mask-modal);
  z-index: 1000;
}
.m-ad-sheet {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  max-width: 480px;
  margin: 0 auto;
  max-height: 85vh;
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-2xl) var(--m-radius-2xl) 0 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  z-index: 1001;
  transform: translateY(100%);
  transition: transform 0.3s ease;
}
.m-ad-sheet--open {
  transform: translateY(0);
}
.m-ad-sheet-handle {
  width: 36px;
  height: 4px;
  background: var(--m-color-border);
  border-radius: var(--m-radius-pill);
  margin: var(--m-space-2) auto var(--m-space-1);
  flex-shrink: 0;
}
.m-ad-sheet-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-space-2) var(--m-space-4) var(--m-space-3);
  border-bottom: 1px solid var(--m-color-border-light);
  flex-shrink: 0;
}
.m-ad-sheet-header h3 {
  margin: 0;
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
}
.m-ad-sheet-close {
  background: transparent;
  border: none;
  color: var(--m-color-text-tertiary);
  cursor: pointer;
  padding: var(--m-space-1);
  border-radius: var(--m-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
}
.m-ad-sheet-close:active {
  background: var(--m-color-bg-subtle);
}
.m-ad-sheet-body {
  flex: 1;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: var(--m-space-4);
}
.m-ad-sheet-search {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-md);
  padding: var(--m-space-2) var(--m-space-3);
  margin-bottom: var(--m-space-3);
}
.m-ad-sheet-search-icon {
  color: var(--m-color-text-tertiary);
  flex-shrink: 0;
}
.m-ad-sheet-search-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-primary);
  font-family: inherit;
}
.m-ad-sheet-search-input::placeholder {
  color: var(--m-color-text-placeholder);
}
.m-ad-sheet-options {
  display: flex;
  flex-direction: column;
}
.m-ad-sheet-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-space-3);
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--m-color-border-light);
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-primary);
  cursor: pointer;
  font-family: inherit;
  text-align: left;
}
.m-ad-sheet-option:active {
  background: var(--m-color-bg-subtle);
}
.m-ad-sheet-option--active {
  color: var(--m-color-primary);
  font-weight: var(--m-font-weight-semibold);
}
.m-ad-sheet-check {
  color: var(--m-color-primary);
}
.m-ad-sheet-footer {
  display: flex;
  gap: var(--m-space-3);
  padding: var(--m-space-3) var(--m-space-4);
  border-top: 1px solid var(--m-color-border-light);
  flex-shrink: 0;
}
.m-ad-sheet-footer .m-ad-btn {
  flex: 1;
}

/* === 批量表单 === */
.m-ad-batch-hint {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-secondary);
  margin-bottom: var(--m-space-3);
}
.m-ad-batch-hint b {
  color: var(--m-color-primary);
  font-weight: var(--m-font-weight-bold);
}
.m-ad-form-row {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
}
.m-ad-form-row label {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  font-weight: var(--m-font-weight-medium);
}
.m-ad-select {
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-md);
  padding: var(--m-space-2) var(--m-space-3);
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-primary);
  background: var(--m-color-bg-card);
  font-family: inherit;
}

/* === 帮助 === */
.m-ad-help-body h4 {
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  margin: 0 0 var(--m-space-2);
}
.m-ad-help-section {
  margin-bottom: var(--m-space-4);
}
.m-ad-help-section ul,
.m-ad-help-section ol {
  margin: 0;
  padding-left: var(--m-space-5);
}
.m-ad-help-section li {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-secondary);
  line-height: var(--m-line-height-relaxed);
}
.m-ad-help-section p {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-secondary);
  line-height: var(--m-line-height-relaxed);
  margin: var(--m-space-1) 0;
}

/* === 响应式 === */
@media (max-width: 360px) {
  .m-ad {
    padding: var(--m-space-2) var(--m-space-2) 0;
  }
  .m-ad-hero {
    padding: var(--m-space-3);
  }
  .m-ad-stat-grid {
    gap: var(--m-space-2);
  }
  .m-ad-stat-value {
    font-size: var(--m-font-size-h3);
  }
  .m-ad-product-img-wrap {
    width: 48px;
    height: 48px;
  }
}
</style>
