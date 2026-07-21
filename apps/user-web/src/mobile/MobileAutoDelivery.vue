<template>
  <div class="m-ad">
    <div class="m-ad-stats-grid">
      <div v-for="card in statCards" :key="card.key" class="m-ad-stat-card" @click="handleStatClick(card.key)">
        <div class="m-ad-stat-icon" :class="`m-ad-stat-icon-${card.color}`">
          <MIcon :name="card.icon" :size="20" />
        </div>
        <div class="m-ad-stat-info">
          <div class="m-ad-stat-title">{{ card.title }}</div>
          <div class="m-ad-stat-value">{{ statsLoading ? '—' : formatNumber(card.value) }}</div>
          <div class="m-ad-stat-desc" :class="`m-ad-stat-desc-${card.color}`">{{ card.desc }}</div>
        </div>
      </div>
    </div>

    <div class="m-ad-enabled-card" @click="filterEnabled">
      <div class="m-ad-enabled-icon">
        <MIcon name="bag" :size="22" />
      </div>
      <div class="m-ad-enabled-info">
        <div class="m-ad-enabled-title">已启用自动发货</div>
        <div class="m-ad-enabled-value">{{ statsLoading ? '—' : formatNumber(stats.enabledGoods) }}</div>
        <div class="m-ad-enabled-desc">全部商品</div>
      </div>
      <div class="m-ad-enabled-arrow">
        <MIcon name="chevronRight" :size="20" />
      </div>
    </div>

    <div class="m-ad-notice">
      <div class="m-ad-notice-icon">
        <MIcon name="info" :size="18" />
      </div>
      <div class="m-ad-notice-text">
        <b>付款后发货</b>会在系统定时扫描自动执行；<b>确认收货后赠送</b>和<b>好评后赠送</b>可在发货记录页手动触发，也可接入 E店易插件自动化。
      </div>
    </div>

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

    <div class="m-ad-filter-bar">
      <div class="m-ad-filter-grid">
        <button
          v-for="filter in filterOptions"
          :key="filter.key"
          class="m-ad-filter-chip"
          :class="{ 'm-ad-filter-chip-active': isFilterActive(filter) }"
          @click="openFilter(filter)"
        >
          <span>{{ getFilterLabel(filter) }}</span>
          <MIcon name="chevronDown" :size="14" />
        </button>
      </div>
    </div>

    <div class="m-ad-toolbar">
      <div class="m-ad-count">
        共 <b>{{ productsLoading ? '—' : total }}</b> 个商品
      </div>
      <div class="m-ad-toolbar-actions">
        <button class="m-ad-btn m-ad-btn-primary" @click="toggleBatchMode">
          {{ batchMode ? '取消批量' : '批量设置' }}
        </button>
        <button class="m-ad-btn m-ad-btn-outline" @click="goToSourceLibrary">
          货源库
        </button>
      </div>
    </div>

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

    <div v-else-if="products.length === 0" class="m-ad-empty">
      <div class="m-ad-empty-icon">
        <MIcon name="bag" :size="48" />
      </div>
      <div class="m-ad-empty-text">{{ hasFilters ? '暂无符合条件的商品' : '暂无自动发货商品' }}</div>
      <div class="m-ad-empty-desc">{{ hasFilters ? '请尝试调整筛选条件' : '请先同步商品或前往商品管理配置' }}</div>
      <button v-if="hasFilters" class="m-ad-btn m-ad-btn-primary m-ad-btn-sm" @click="clearFilters">清除筛选</button>
      <button v-else class="m-ad-btn m-ad-btn-primary m-ad-btn-sm" @click="goToProducts">前往商品管理</button>
    </div>

    <div v-else class="m-ad-list">
      <div
        v-for="prod in products"
        :key="prod.id"
        class="m-ad-product-card"
        :class="{ 'm-ad-product-batch': batchMode }"
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
                <span class="m-ad-product-price" :class="{ 'm-ad-price-special': isAbnormalPrice(prod) }">¥{{ formatPrice(prod.price) }}</span>
              </div>
              <div class="m-ad-product-tags">
                <span class="m-ad-tag m-ad-tag-green">{{ getDeliveryModeLabel(prod) }}</span>
                <span v-if="getConfigStatus(prod) === 'unconfigured'" class="m-ad-tag m-ad-tag-gray">未配置</span>
                <span v-else-if="getConfigStatus(prod) === 'abnormal'" class="m-ad-tag m-ad-tag-red">配置异常</span>
                <span v-else-if="prod.sourceName" class="m-ad-tag m-ad-tag-light">货源：{{ prod.sourceName }}</span>
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
                :class="{ 'm-ad-switch-on': prod.deliveryEnabled, 'm-ad-switch-loading': prod.switchLoading }"
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

    <div v-if="activeFilter" class="m-ad-sheet-mask" @click="closeFilter"></div>
    <div v-if="activeFilter" class="m-ad-sheet" :class="{ 'm-ad-sheet-open': activeFilter }">
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
            :class="{ 'm-ad-sheet-option-active': isOptionSelected(activeFilter, opt) }"
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

    <div v-if="showBatchDialog" class="m-ad-sheet-mask" @click.self="showBatchDialog = false"></div>
    <div v-if="showBatchDialog" class="m-ad-sheet m-ad-sheet-open">
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

    <div v-if="showHelp" class="m-ad-sheet-mask" @click="showHelp = false"></div>
    <div v-if="showHelp" class="m-ad-sheet m-ad-sheet-open" style="height: 70vh;">
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
.m-ad {
  padding: 10px 16px 0;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
}

.m-ad-stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 10px;
}

.m-ad-stat-card {
  background: white;
  border-radius: 16px;
  padding: 14px;
  display: flex;
  align-items: center;
  gap: 12px;
  box-shadow: 0 2px 8px rgba(31, 53, 94, 0.05);
  border: 1px solid #f0f4fa;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}
.m-ad-stat-card:active {
  transform: scale(0.98);
}

.m-ad-stat-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-ad-stat-icon-green {
  background: linear-gradient(135deg, #dcfce7, #bbf7d0);
  color: #16a34a;
}
.m-ad-stat-icon-orange {
  background: linear-gradient(135deg, #fef3c7, #fde68a);
  color: #f59e0b;
}
.m-ad-stat-icon-blue {
  background: linear-gradient(135deg, #dbeafe, #bfdbfe);
  color: #2563eb;
}

.m-ad-stat-info {
  flex: 1;
  min-width: 0;
}
.m-ad-stat-title {
  font-size: 12px;
  color: #72809a;
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.m-ad-stat-value {
  font-size: 22px;
  font-weight: 800;
  color: #15213d;
  line-height: 1.2;
}
.m-ad-stat-desc {
  font-size: 11px;
  font-weight: 500;
  margin-top: 2px;
}
.m-ad-stat-desc-green { color: #16a34a; }
.m-ad-stat-desc-orange { color: #f59e0b; }
.m-ad-stat-desc-blue { color: #2563eb; }

.m-ad-enabled-card {
  background: white;
  border-radius: 16px;
  padding: 14px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  box-shadow: 0 2px 8px rgba(31, 53, 94, 0.05);
  border: 1px solid #f0f4fa;
  margin-bottom: 12px;
  cursor: pointer;
  transition: transform 0.15s;
}
.m-ad-enabled-card:active { transform: scale(0.99); }

.m-ad-enabled-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: linear-gradient(135deg, #dbeafe, #bfdbfe);
  color: #2563eb;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-ad-enabled-info { flex: 1; }
.m-ad-enabled-title {
  font-size: 14px;
  font-weight: 600;
  color: #15213d;
}
.m-ad-enabled-value {
  font-size: 22px;
  font-weight: 800;
  color: #15213d;
  line-height: 1.2;
}
.m-ad-enabled-desc {
  font-size: 11px;
  color: #16a34a;
  font-weight: 500;
}
.m-ad-enabled-arrow {
  color: #b0bacb;
  flex-shrink: 0;
}

.m-ad-notice {
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 12px;
  padding: 12px 14px;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 14px;
}
.m-ad-notice-icon {
  color: #f59e0b;
  flex-shrink: 0;
  margin-top: 1px;
}
.m-ad-notice-text {
  font-size: 12px;
  color: #92400e;
  line-height: 1.6;
  flex: 1;
}
.m-ad-notice-text b {
  font-weight: 600;
}

.m-ad-search-wrap {
  margin-bottom: 12px;
}
.m-ad-search {
  display: flex;
  align-items: center;
  gap: 8px;
  background: white;
  border: 1px solid #e7edf7;
  border-radius: 12px;
  padding: 0 14px;
  height: 48px;
}
.m-ad-search-icon {
  color: #8c98ae;
  flex-shrink: 0;
}
.m-ad-search-input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 14px;
  color: #15213d;
  background: transparent;
  min-width: 0;
}
.m-ad-search-input::placeholder {
  color: #b0bacb;
}
.m-ad-search-clear {
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

.m-ad-filter-bar { margin-bottom: 16px; }
.m-ad-filter-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}
.m-ad-filter-chip {
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
  min-height: 42px;
  overflow: hidden;
}
.m-ad-filter-chip span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-ad-filter-chip-active {
  border-color: #1478f5;
  color: #1478f5;
  background: #f3f8ff;
}

.m-ad-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  gap: 10px;
}
.m-ad-count {
  font-size: 13px;
  color: #5a6a85;
}
.m-ad-count b {
  color: #15213d;
  font-weight: 700;
}
.m-ad-toolbar-actions {
  display: flex;
  gap: 8px;
}

.m-ad-btn {
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
.m-ad-btn:active { transform: scale(0.97); }
.m-ad-btn-primary {
  background: linear-gradient(135deg, #0d6bff, #2580ff);
  color: white;
  box-shadow: 0 4px 12px rgba(13, 107, 255, 0.25);
}
.m-ad-btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.m-ad-btn-outline {
  background: white;
  color: #5a6a85;
  border: 1px solid #e7edf7;
}
.m-ad-btn-sm {
  padding: 8px 14px;
  font-size: 12px;
  min-height: 36px;
}

.m-ad-batch-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #eef4ff;
  border-radius: 12px;
  padding: 10px 14px;
  margin-bottom: 12px;
}
.m-ad-batch-select-all {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #15213d;
  cursor: pointer;
}
.m-ad-batch-count {
  font-size: 12px;
  color: #0d6bff;
  font-weight: 600;
  flex: 1;
}

.m-ad-skeleton-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.m-ad-skeleton-card {
  background: white;
  border-radius: 16px;
  padding: 12px;
  display: flex;
  gap: 12px;
  border: 1px solid #f0f4fa;
}
.m-ad-skeleton-img {
  width: 64px;
  height: 64px;
  border-radius: 10px;
  background: linear-gradient(90deg, #f4f7fc 25%, #e8edf5 50%, #f4f7fc 75%);
  background-size: 200% 100%;
  animation: m-ad-skeleton 1.5s infinite;
  flex-shrink: 0;
}
.m-ad-skeleton-body { flex: 1; display: flex; flex-direction: column; gap: 8px; }
.m-ad-skeleton-line {
  height: 14px;
  border-radius: 4px;
  background: linear-gradient(90deg, #f4f7fc 25%, #e8edf5 50%, #f4f7fc 75%);
  background-size: 200% 100%;
  animation: m-ad-skeleton 1.5s infinite;
}
.m-ad-skeleton-title { width: 70%; }
.m-ad-skeleton-meta { width: 40%; height: 12px; }
.m-ad-skeleton-tags { display: flex; gap: 8px; }
.m-ad-skeleton-tag {
  width: 70px;
  height: 20px;
  border-radius: 100px;
  background: linear-gradient(90deg, #f4f7fc 25%, #e8edf5 50%, #f4f7fc 75%);
  background-size: 200% 100%;
  animation: m-ad-skeleton 1.5s infinite;
}
@keyframes m-ad-skeleton {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.m-ad-empty {
  text-align: center;
  padding: 60px 20px;
}
.m-ad-empty-icon {
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
.m-ad-empty-text { font-size: 16px; font-weight: 600; color: #15213d; margin-bottom: 6px; }
.m-ad-empty-desc { font-size: 13px; color: #8c98ae; margin-bottom: 20px; }

.m-ad-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.m-ad-product-card {
  background: #fff;
  border-radius: 16px;
  padding: 11px;
  display: flex;
  gap: 10px;
  box-shadow: 0 4px 14px rgba(31, 53, 94, 0.04);
  border: 1px solid #edf1f5;
}
.m-ad-product-batch { padding-left: 8px; }

.m-ad-product-check {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}
.m-ad-product-check input {
  width: 20px;
  height: 20px;
  accent-color: #0d6bff;
}

.m-ad-product-img-wrap {
  width: 70px;
  height: 70px;
  border-radius: 9px;
  overflow: hidden;
  flex-shrink: 0;
  background: #f4f7fc;
  cursor: pointer;
}
.m-ad-product-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.m-ad-product-img-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #b0bacb;
  background: linear-gradient(135deg, #f4f7fc, #eaf0fa);
}

.m-ad-product-body { flex: 1; min-width: 0; }
.m-ad-product-top {
  display: flex;
  gap: 10px;
}
.m-ad-product-info { flex: 1; min-width: 0; }
.m-ad-product-name {
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
  cursor: pointer;
  margin-bottom: 4px;
}
.m-ad-product-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}
.m-ad-product-id {
  font-size: 11px;
  color: #8c98ae;
  cursor: pointer;
}
.m-ad-product-id:active { color: #0d6bff; }
.m-ad-product-price {
  font-size: 15px;
  font-weight: 700;
  color: #16a34a;
}
.m-ad-price-special { color: #ef4444; }
.m-ad-product-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.m-ad-tag {
  font-size: 10px;
  font-weight: 500;
  padding: 3px 8px;
  border-radius: 100px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 120px;
}
.m-ad-tag-green {
  background: rgba(22, 163, 74, 0.1);
  color: #16a34a;
}
.m-ad-tag-gray {
  background: rgba(140, 152, 174, 0.12);
  color: #7f8a9d;
}
.m-ad-tag-red {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}
.m-ad-tag-light {
  background: rgba(13, 107, 255, 0.08);
  color: #0d6bff;
}

.m-ad-product-right {
  display: grid;
  grid-template-columns: auto auto;
  align-items: center;
  justify-items: end;
  column-gap: 10px;
  row-gap: 8px;
  flex-shrink: 0;
}
.m-ad-stock-badge {
  grid-column: 1 / -1;
  padding: 5px 9px;
  border-radius: 8px;
  text-align: center;
  min-width: 76px;
  cursor: pointer;
}
.m-ad-stock-badge span {
  display: block;
  font-size: 10px;
  font-weight: 500;
}
.m-ad-stock-badge strong {
  display: block;
  font-size: 13px;
  font-weight: 700;
}
.m-ad-stock-ok {
  background: rgba(22, 163, 74, 0.1);
  color: #16a34a;
}
.m-ad-stock-low {
  background: rgba(245, 158, 11, 0.1);
  color: #f59e0b;
}
.m-ad-stock-unknown {
  background: rgba(140, 152, 174, 0.1);
  color: #7f8a9d;
}

.m-ad-config-btn {
  background: none;
  border: none;
  color: #0d6bff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  padding: 4px 0;
}

.m-ad-switch {
  width: 44px;
  height: 26px;
  border-radius: 13px;
  background: #e7edf7;
  border: none;
  position: relative;
  cursor: pointer;
  transition: background 0.2s;
  padding: 0;
  flex-shrink: 0;
}
.m-ad-switch:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.m-ad-switch-on {
  background: linear-gradient(135deg, #0d6bff, #2580ff);
}
.m-ad-switch-knob {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
  transition: transform 0.2s;
}
.m-ad-switch-on .m-ad-switch-knob {
  transform: translateX(18px);
}

.m-ad-loading-more,
.m-ad-load-more,
.m-ad-no-more {
  text-align: center;
  padding: 20px;
  font-size: 13px;
  color: #8c98ae;
}
.m-ad-load-more .m-ad-btn {
  padding: 8px 24px;
}

.m-ad-safe-bottom {
  height: calc(84px + env(safe-area-inset-bottom));
}

.m-ad-sheet-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 25, 50, 0.4);
  z-index: 200;
  backdrop-filter: blur(2px);
}

.m-ad-sheet {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  background: white;
  border-radius: 20px 20px 0 0;
  z-index: 201;
  transform: translateY(100%);
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  padding-bottom: env(safe-area-inset-bottom);
}
.m-ad-sheet-open {
  transform: translateY(0);
}
.m-ad-sheet-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #f0f4fa;
}
.m-ad-sheet-header h3 {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  color: #15213d;
}
.m-ad-sheet-close {
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
.m-ad-sheet-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}
.m-ad-sheet-search {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #f5f7fb;
  border-radius: 10px;
  padding: 0 12px;
  margin-bottom: 12px;
  height: 42px;
}
.m-ad-sheet-search-icon { color: #8c98ae; flex-shrink: 0; }
.m-ad-sheet-search-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 14px;
}
.m-ad-sheet-options {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.m-ad-sheet-option {
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
.m-ad-sheet-option:active { background: #f5f7fb; }
.m-ad-sheet-option-active {
  background: #eef4ff;
  color: #0d6bff;
  font-weight: 600;
}
.m-ad-sheet-check { color: #0d6bff; flex-shrink: 0; }
.m-ad-sheet-footer {
  display: flex;
  gap: 10px;
  padding: 12px 20px 16px;
  border-top: 1px solid #f0f4fa;
}
.m-ad-sheet-footer .m-ad-btn { flex: 1; }

.m-ad-batch-hint {
  font-size: 14px;
  color: #5a6a85;
  margin-bottom: 16px;
}
.m-ad-batch-hint b { color: #0d6bff; font-weight: 700; }
.m-ad-form-row {
  margin-bottom: 16px;
}
.m-ad-form-row label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #15213d;
  margin-bottom: 8px;
}
.m-ad-select {
  width: 100%;
  height: 44px;
  border: 1px solid #e7edf7;
  border-radius: 10px;
  padding: 0 12px;
  font-size: 14px;
  color: #15213d;
  background: white;
  outline: none;
}

.m-ad-help-body {
  font-size: 14px;
  color: #5a6a85;
  line-height: 1.7;
}
.m-ad-help-section {
  margin-bottom: 20px;
}
.m-ad-help-section h4 {
  margin: 0 0 10px;
  font-size: 15px;
  font-weight: 700;
  color: #15213d;
}
.m-ad-help-section ul,
.m-ad-help-section ol {
  margin: 0;
  padding-left: 20px;
}
.m-ad-help-section li {
  margin-bottom: 6px;
}
.m-ad-help-section p {
  margin: 0 0 6px;
}

@media (max-width: 360px) {
  .m-ad { padding: 10px 12px 0; }
  .m-ad-stats-grid { gap: 8px; }
  .m-ad-stat-card { padding: 12px; gap: 10px; }
  .m-ad-stat-icon { width: 40px; height: 40px; }
  .m-ad-stat-value { font-size: 20px; }
  .m-ad-product-img-wrap { width: 56px; height: 56px; }
  .m-ad-stock-badge { min-width: 58px; padding: 3px 8px; }
  .m-ad-stock-badge strong { font-size: 12px; }
}

@media (min-width: 430px) {
  .m-ad-stats-grid { gap: 12px; }
  .m-ad-stat-card { padding: 16px; }
}
</style>
