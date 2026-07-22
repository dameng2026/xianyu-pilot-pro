<template>
  <div class="m-orders">
    <div class="m-page-header">
      <h1>订单管理</h1>
      <p class="m-page-sub">实时查看和管理您的闲鱼订单</p>
    </div>

    <div class="m-stat-grid">
      <div class="m-stat-card" @click="filterByStatus('')">
        <div class="m-stat-icon m-stat-blue">
          <MIcon name="fileText" :size="24" />
        </div>
        <div class="m-stat-info">
          <div class="m-stat-label">全部订单</div>
          <div class="m-stat-value">{{ formatNumber(stats.total) }}</div>
        </div>
      </div>
      <div class="m-stat-card" @click="filterByStatus('2')">
        <div class="m-stat-icon m-stat-orange">
          <MIcon name="truck" :size="24" />
        </div>
        <div class="m-stat-info">
          <div class="m-stat-label">待发货</div>
          <div class="m-stat-value">{{ formatNumber(stats.pending) }}</div>
        </div>
      </div>
      <div class="m-stat-card" @click="filterByStatus('4')">
        <div class="m-stat-icon m-stat-green">
          <MIcon name="checkCircle" :size="24" />
        </div>
        <div class="m-stat-info">
          <div class="m-stat-label">已完成</div>
          <div class="m-stat-value">{{ formatNumber(stats.completed) }}</div>
        </div>
      </div>
      <div class="m-stat-card" @click="filterByStatus('5')">
        <div class="m-stat-icon m-stat-red">
          <MIcon name="xCircle" :size="24" />
        </div>
        <div class="m-stat-info">
          <div class="m-stat-label">已关闭</div>
          <div class="m-stat-value">{{ formatNumber(stats.closed) }}</div>
        </div>
      </div>
    </div>

    <div class="m-search-section">
      <div class="m-search-bar">
        <MIcon name="search" :size="18" class="m-search-icon" />
        <input
          v-model="searchKeyword"
          type="text"
          class="m-search-input"
          placeholder="搜索订单号、买家或商品"
          @input="debouncedSearch"
        />
        <button v-if="searchKeyword" class="m-search-clear" @click="clearSearch">
          <MIcon name="x" :size="16" />
        </button>
      </div>
    </div>

    <div class="m-status-tabs">
      <button
        v-for="tab in statusTabs"
        :key="tab.value"
        class="m-status-tab"
        :class="{ active: activeStatus === tab.value }"
        @click="switchStatus(tab.value)"
      >
        {{ tab.label }}
        <span v-if="tab.count > 0" class="m-tab-count">{{ tab.count }}</span>
      </button>
    </div>

    <div v-if="loading && !orders.length" class="m-loading">加载中...</div>

    <MobileUnavailableState v-else-if="loadError" title="订单加载失败" :description="loadError" @retry="loadOrders" />

    <div v-else-if="!orders.length" class="m-empty">
      <div class="m-empty-icon">
        <MIcon name="fileText" :size="48" />
      </div>
      <div class="m-empty-text">暂无订单</div>
      <div class="m-empty-desc">{{ searchKeyword || activeStatus ? '没有符合条件的订单' : '还没有订单数据，同步后查看' }}</div>
      <button class="m-empty-btn" @click="syncOrders">
        <MIcon name="refreshCw" :size="18" />
        同步订单
      </button>
    </div>

    <template v-else>
      <div class="m-order-list">
        <div
          v-for="order in orders"
          :key="order.id"
          class="m-order-card"
          @click="openDetail(order)"
        >
          <div class="m-order-header">
            <span class="m-order-id">{{ order.externalOrderId || '-' }}</span>
            <span :class="['m-status-badge', statusBadgeClass(order)]">
              {{ orderStatusText(order) }}
            </span>
          </div>

          <div class="m-order-time">{{ createTimeText(order) }}</div>

          <div class="m-order-goods">
            <div class="m-goods-image-wrap">
              <img
                v-if="firstGoodsImage(order) && !failedImages.has(firstGoodsImage(order))"
                :src="firstGoodsImage(order)"
                class="m-goods-image"
                alt=""
                referrerpolicy="no-referrer"
                @error="onImageError($event, order)"
              />
              <div v-else class="m-goods-image m-goods-placeholder">
                <MIcon name="image" :size="28" />
              </div>
            </div>
            <div class="m-goods-info">
              <div class="m-goods-title">{{ firstGoodsTitle(order) || '-' }}</div>
              <div class="m-goods-meta">
                <span class="m-buyer-name">{{ order.buyerName || '-' }}</span>
              </div>
              <div class="m-progress-row">
                <div class="m-progress">
                  <div class="m-progress-bar" :style="{ width: deliveryProgress(order) + '%' }"></div>
                </div>
                <span class="m-progress-text">{{ deliveryProgressText(order) }}</span>
              </div>
            </div>
          </div>

          <div class="m-order-footer">
            <div class="m-order-price">
              <span class="m-price-label">实付</span>
              <span class="m-price-value">¥{{ formatMoney(order.totalAmount) }}</span>
            </div>
            <div class="m-order-actions" @click.stop>
              <button v-if="canSync(order)" class="m-action-btn" @click="syncOrder(order)">
                <MIcon name="refreshCw" :size="16" />
              </button>
              <button v-if="canDeliver(order)" class="m-action-btn m-action-primary" @click="openDelivery(order)">
                发货
              </button>
              <button v-if="canRepurchase(order)" class="m-action-btn" @click="repurchase(order)">
                <MIcon name="repeat" :size="16" />
              </button>
            </div>
          </div>
        </div>
      </div>

      <div v-if="hasMore" class="m-load-more">
        <button class="m-load-btn" :disabled="loadingMore" @click="loadMore">
          {{ loadingMore ? '加载中...' : '加载更多' }}
        </button>
      </div>
    </template>

    <MobileOrderShipForm
      :visible="shipFormVisible"
      :order="shipOrder"
      @close="closeShipForm"
      @success="handleShipSuccess"
    />

    <div class="m-safe-bottom"></div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import MIcon from './MIcon.vue'
import MobileUnavailableState from './MobileUnavailableState.vue'
import MobileOrderShipForm from './components/MobileOrderShipForm.vue'
import { getOrders, syncOrder as apiSyncOrder, syncOrders as apiSyncOrders } from '../api/orders.js'
import { toast } from './toast.js'

const emit = defineEmits(['navigate', 'force-desktop', 'back'])

const loading = ref(true)
const loadingMore = ref(false)
const loadError = ref('')
const searchKeyword = ref('')
const activeStatus = ref('')
const orders = ref([])
const failedImages = reactive(new Set())
const syncing = ref(false)
const shipFormVisible = ref(false)
const shipOrder = ref(null)

const query = reactive({
  current: 1,
  size: 20,
  status: '',
  keyword: '',
  accountId: ''
})

// 注意：stats 中的 pending/completed/closed/shipped 仅基于当前页订单列表统计，
// 不是服务端聚合值。当列表被状态筛选或关键字过滤时，这些数字仅反映当前页的样本。
// 如需服务端聚合，需后端提供 /orders/stats 接口；当前接口仅返回 total。
const stats = reactive({
  total: 0,
  pending: 0,
  completed: 0,
  closed: 0,
  shipped: 0
})

const statusTabs = computed(() => [
  { label: '全部', value: '', count: stats.total },
  { label: '待发货', value: '2', count: stats.pending },
  { label: '已发货', value: '3', count: stats.shipped },
  { label: '已完成', value: '4', count: stats.completed },
  { label: '已关闭', value: '5', count: stats.closed }
])

const hasMore = computed(() => {
  return orders.value.length < stats.total
})

let searchTimer = null
function debouncedSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    query.keyword = searchKeyword.value
    query.current = 1
    loadOrders()
  }, 300)
}

function clearSearch() {
  searchKeyword.value = ''
  query.keyword = ''
  query.current = 1
  loadOrders()
}

function switchStatus(value) {
  if (activeStatus.value === value) return
  activeStatus.value = value
  query.status = value
  query.current = 1
  loadOrders()
}

function filterByStatus(status) {
  activeStatus.value = status
  query.status = status
  query.current = 1
  loadOrders()
}

function formatNumber(n) {
  if (n === null || n === undefined) return '0'
  return Number(n).toLocaleString()
}

function formatMoney(n) {
  if (n === null || n === undefined || isNaN(Number(n))) return '0.00'
  return Number(n).toFixed(2)
}

const ORDER_STATUS_TEXT = {
  0: '待付款',
  1: '已付款',
  2: '待发货',
  3: '已发货',
  4: '已完成',
  5: '已关闭'
}

function orderStatusText(order) {
  // 优先使用后端预格式化字段，回退到本地映射
  if (order?.orderStatusText) return order.orderStatusText
  return ORDER_STATUS_TEXT[Number(order?.orderStatus)] || '未知状态'
}

function formatDateTime(dt) {
  if (!dt) return '-'
  const d = new Date(dt)
  if (isNaN(d.getTime())) return '-'
  const now = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  const time = `${pad(d.getHours())}:${pad(d.getMinutes())}`
  if (d.toDateString() === now.toDateString()) return `今天 ${time}`
  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  if (d.toDateString() === yesterday.toDateString()) return `昨天 ${time}`
  return `${d.getMonth() + 1}月${d.getDate()}日 ${time}`
}

function createTimeText(order) {
  // 优先使用后端预格式化字段，回退到本地格式化
  if (order?.createTimeText) return order.createTimeText
  return formatDateTime(order?.createTime || order?.createdTime)
}

function deliveryProgressText(order) {
  // 优先使用后端预格式化字段，回退到本地计算
  if (order?.deliveryProgressText) return order.deliveryProgressText
  const sent = Number(order?.quantitySent || 0)
  const total = Number(order?.quantityRequested || order?.quantityTotal || 1) || 1
  return `${sent}/${total}`
}

function firstGoodsItem(order) {
  if (!order) return {}
  const items = order.orderItems || order.goodsItems || order.items || []
  return items[0] || {}
}

function firstGoodsImage(order) {
  const item = firstGoodsItem(order)
  return item.imageUrl
    || item.goodsImage
    || item.picUrl
    || item.coverImage
    || item.thumbUrl
    || item.itemPic
    || (Array.isArray(item.images) && item.images[0])
    || order.goodsImage
    || ''
}

function firstGoodsTitle(order) {
  const item = firstGoodsItem(order)
  return item.goodsTitle || item.title || item.itemTitle || order.goodsTitle || ''
}

function onImageError(e, order) {
  const img = firstGoodsImage(order)
  if (img) failedImages.add(img)
  e.target.style.display = 'none'
}

function statusBadgeClass(order) {
  const s = Number(order?.orderStatus)
  if (s === 4) return 'completed'
  if (s === 3) return 'shipped'
  if (s === 1) return 'paid'
  if (s === 0 || s === 2) return 'orange'
  if (s === 5) return 'red'
  return 'gray'
}

function deliveryProgress(order) {
  const text = deliveryProgressText(order)
  const match = text.match(/(\d+)\s*\/\s*(\d+)/)
  if (!match) return 100
  const [, delivered, total] = match
  const t = Number(total) || 1
  const d = Number(delivered) || 0
  return Math.min(100, Math.round((d / t) * 100))
}

function canSync(_order) {
  return true
}

function canDeliver(order) {
  return Number(order.orderStatus) === 2
}

function canRepurchase(order) {
  return Number(order.orderStatus) === 4 || Number(order.orderStatus) === 5
}

async function loadOrders(append = false) {
  if (!append) {
    loading.value = true
    orders.value = []
  } else {
    loadingMore.value = true
  }
  loadError.value = ''

  try {
    const res = await getOrders({
      current: query.current,
      size: query.size,
      status: query.status || undefined,
      keyword: query.keyword || undefined
    })
    const data = res?.data || {}
    const list = data.records || data.list || data.rows || []
    const total = Number(data.total || 0)

    if (append) {
      orders.value = [...orders.value, ...list]
    } else {
      orders.value = list
    }

    stats.total = total
    calculateStats(list, total)
  } catch (e) {
    loadError.value = e?.message || '加载失败，请稍后重试'
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

function calculateStats(list, _total) {
  let pending = 0, completed = 0, closed = 0, shipped = 0
  list.forEach(o => {
    const s = Number(o.orderStatus)
    if (s === 2) pending++
    if (s === 3) shipped++
    if (s === 4) completed++
    if (s === 5) closed++
  })
  if (query.current === 1 && !query.status && !query.keyword) {
    stats.pending = pending
    stats.shipped = shipped
    stats.completed = completed
    stats.closed = closed
  }
}

async function loadMore() {
  if (loadingMore.value || !hasMore.value) return
  query.current++
  await loadOrders(true)
}

function openDetail(order) {
  if (!order?.id) return
  emit('navigate', 'order-detail', { id: order.id })
}

async function syncOrder(order) {
  if (syncing.value) return
  syncing.value = true
  try {
    await apiSyncOrder(order.id)
    toast.success('订单同步成功')
    await loadOrders()
  } catch (e) {
    console.error('同步失败', e)
    toast.error(e?.message || '订单同步失败，请稍后重试')
  } finally {
    syncing.value = false
  }
}

async function syncOrders() {
  if (syncing.value) return
  syncing.value = true
  try {
    await apiSyncOrders({})
    toast.success('订单批量同步成功')
    query.current = 1
    await loadOrders()
  } catch (e) {
    console.error('同步失败', e)
    toast.error(e?.message || '批量同步失败，请稍后重试')
  } finally {
    syncing.value = false
  }
}

function openDelivery(order) {
  if (!order) return
  shipOrder.value = order
  shipFormVisible.value = true
}

function closeShipForm() {
  shipFormVisible.value = false
  shipOrder.value = null
}

async function handleShipSuccess() {
  closeShipForm()
  await loadOrders()
}

function repurchase(_order) {
  emit('force-desktop', 'products')
}

onMounted(() => {
  loadOrders()
})
</script>

<style scoped>
.m-orders {
  padding: var(--m-space-3) var(--m-space-4) 0;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
}

.m-page-header {
  margin-bottom: var(--m-space-3);
}
.m-page-header h1 {
  margin: 0 0 var(--m-space-1);
  font-size: var(--m-font-size-h1);
  font-weight: var(--m-font-weight-extrabold);
  color: var(--m-color-text-primary);
  line-height: var(--m-line-height-tight);
}
.m-page-sub {
  margin: 0;
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-tertiary);
  line-height: var(--m-line-height-base);
}

.m-stat-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-3);
}
.m-stat-card {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-3);
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  box-shadow: var(--m-shadow-card);
  border: 1px solid var(--m-color-border-light);
  cursor: pointer;
  transition: transform 0.15s;
}
.m-stat-card:active {
  transform: scale(0.97);
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
.m-stat-blue { background: var(--m-color-primary-bg); color: var(--m-color-primary); }
.m-stat-green { background: var(--m-color-success-bg); color: var(--m-color-success); }
.m-stat-orange { background: var(--m-color-warning-bg); color: var(--m-color-warning); }
.m-stat-red { background: var(--m-color-danger-bg); color: var(--m-color-danger); }
.m-stat-info { flex: 1; min-width: 0; }
.m-stat-label { font-size: var(--m-font-size-caption); color: var(--m-color-text-tertiary); margin-bottom: 2px; }
.m-stat-value {
  font-size: var(--m-font-size-h1);
  font-weight: var(--m-font-weight-extrabold);
  color: var(--m-color-text-primary);
  line-height: var(--m-line-height-tight);
  font-variant-numeric: tabular-nums;
}

.m-search-section {
  margin-bottom: var(--m-space-3);
}
.m-search-bar {
  display: flex;
  align-items: center;
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-lg);
  padding: 0 var(--m-space-3);
  height: 44px;
  box-shadow: var(--m-shadow-card);
  border: 1px solid var(--m-color-border-light);
  gap: var(--m-space-2);
}
.m-search-icon {
  color: var(--m-color-text-tertiary);
  flex-shrink: 0;
}
.m-search-input {
  flex: 1;
  border: none;
  outline: none;
  font-size: var(--m-font-size-body);
  color: var(--m-color-text-primary);
  background: transparent;
  min-width: 0;
}
.m-search-input::placeholder {
  color: var(--m-color-text-placeholder);
}
.m-search-clear {
  width: 24px;
  height: 24px;
  border-radius: var(--m-radius-circle);
  border: none;
  background: var(--m-color-border-light);
  color: var(--m-color-text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  padding: 0;
}

.m-status-tabs {
  display: flex;
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-3);
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  padding-bottom: 2px;
}
.m-status-tabs::-webkit-scrollbar {
  display: none;
}
.m-status-tab {
  flex-shrink: 0;
  height: 34px;
  padding: 0 var(--m-space-3);
  border: none;
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-md);
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-tertiary);
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 5px;
}
.m-status-tab.active {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
}
.m-tab-count {
  background: rgba(255,255,255,0.25);
  padding: 0 var(--m-space-2);
  border-radius: var(--m-radius-md);
  font-size: var(--m-font-size-tiny);
  min-width: 18px;
  text-align: center;
}
.m-status-tab:not(.active) .m-tab-count {
  background: var(--m-color-bg-hover);
  color: var(--m-color-text-secondary);
}

.m-loading {
  padding: var(--m-space-12) 0;
  text-align: center;
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-body);
}

.m-empty {
  padding: var(--m-space-12) var(--m-space-4);
  text-align: center;
  color: var(--m-color-text-tertiary);
}
.m-empty-icon {
  width: 80px;
  height: 80px;
  border-radius: var(--m-radius-circle);
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto var(--m-space-3);
  opacity: 0.7;
}
.m-empty-text {
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-secondary);
  margin-bottom: var(--m-space-2);
}
.m-empty-desc {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  line-height: var(--m-line-height-relaxed);
  margin-bottom: var(--m-space-4);
}
.m-empty-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-2);
  height: 40px;
  padding: 0 var(--m-space-5);
  border: none;
  border-radius: var(--m-radius-pill);
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  box-shadow: var(--m-shadow-card);
}

.m-order-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-3);
}

.m-order-card {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-4);
  box-shadow: var(--m-shadow-card);
  border: 1px solid var(--m-color-border-light);
  cursor: pointer;
  transition: transform 0.15s;
}
.m-order-card:active {
  transform: scale(0.98);
}

.m-order-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--m-space-1);
}
.m-order-id {
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
  font-family: var(--m-font-family-mono);
}
.m-status-badge {
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-semibold);
  padding: 3px var(--m-space-2);
  border-radius: var(--m-radius-md);
}
.status-orange { background: var(--m-color-warning-bg); color: var(--m-color-warning-text); }
.status-completed { background: var(--m-color-success-bg); color: var(--m-color-success-text); }
.status-shipped { background: var(--m-color-cyan-bg); color: var(--m-color-cyan); }
.status-paid { background: var(--m-color-info-bg); color: var(--m-color-info-text); }
.status-red { background: var(--m-color-danger-bg); color: var(--m-color-danger-text); }
.status-gray { background: var(--m-color-bg-subtle); color: var(--m-color-text-tertiary); }
.m-status-lg {
  font-size: var(--m-font-size-body-sm);
  padding: 5px var(--m-space-3);
  border-radius: var(--m-radius-md);
}

.m-order-time {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  margin-bottom: var(--m-space-3);
}

.m-order-goods {
  display: flex;
  gap: var(--m-space-3);
  margin-bottom: var(--m-space-3);
}
.m-goods-image-wrap {
  width: 72px;
  height: 72px;
  border-radius: var(--m-radius-lg);
  overflow: hidden;
  flex-shrink: 0;
  background: var(--m-color-bg-hover);
}
.m-goods-lg {
  width: 80px;
  height: 80px;
}
.m-goods-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.m-goods-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--m-color-text-disabled);
  background: var(--m-color-bg-hover);
}
.m-goods-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
.m-goods-title {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin-bottom: var(--m-space-1);
}
.m-goods-lg {
  font-size: var(--m-font-size-h3);
  -webkit-line-clamp: 2;
}
.m-goods-meta {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  margin-bottom: var(--m-space-2);
}

.m-progress-row {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
}
.m-progress {
  flex: 1;
  height: 6px;
  background: var(--m-color-border-light);
  border-radius: var(--m-radius-pill);
  overflow: hidden;
}
.m-progress-bar {
  height: 100%;
  background: var(--m-color-primary);
  border-radius: var(--m-radius-pill);
  transition: width 0.3s ease;
}
.m-progress-text {
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}

.m-order-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: var(--m-space-3);
  border-top: 1px solid var(--m-color-border-light);
}
.m-order-price {
  display: flex;
  align-items: baseline;
  gap: var(--m-space-1);
}
.m-price-label {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}
.m-price-value {
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-extrabold);
  color: var(--m-color-danger-text);
  font-variant-numeric: tabular-nums;
}

.m-order-actions {
  display: flex;
  gap: var(--m-space-2);
}
.m-action-btn {
  height: 32px;
  padding: 0 var(--m-space-3);
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-md);
  background: var(--m-color-bg-card);
  color: var(--m-color-text-secondary);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: var(--m-space-1);
  transition: all 0.15s;
}
.m-action-btn:active {
  transform: scale(0.95);
}
.m-action-primary {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  border: none;
}

.m-load-more {
  padding: var(--m-space-4) 0;
  text-align: center;
}
.m-load-btn {
  height: 40px;
  padding: 0 var(--m-space-6);
  border: none;
  border-radius: var(--m-radius-pill);
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
}
.m-load-btn:disabled {
  opacity: 0.6;
}

.m-modal-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--m-mask-modal);
  z-index: 1000;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  animation: fadeIn 0.2s ease;
}
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.m-detail-sheet {
  width: 100%;
  max-width: 500px;
  background: var(--m-color-bg-page);
  border-radius: var(--m-radius-2xl) var(--m-radius-2xl) 0 0;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  animation: slideUp 0.3s ease;
}
@keyframes slideUp {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}

.m-sheet-handle {
  width: 40px;
  height: 4px;
  background: var(--m-color-border);
  border-radius: var(--m-radius-sm);
  margin: var(--m-space-2) auto 0;
  flex-shrink: 0;
}

.m-sheet-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-space-3) var(--m-space-5);
  flex-shrink: 0;
}
.m-sheet-header h3 {
  margin: 0;
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
}
.m-sheet-close {
  width: 32px;
  height: 32px;
  border-radius: var(--m-radius-circle);
  border: none;
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
}

.m-sheet-body {
  flex: 1;
  overflow-y: auto;
  padding: 0 var(--m-space-4) var(--m-space-4);
}

.m-detail-status-row {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-4);
}
.m-detail-id {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  font-family: var(--m-font-family-mono);
}

.m-detail-section {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-4);
  margin-bottom: var(--m-space-3);
  box-shadow: var(--m-shadow-card);
}
.m-detail-title {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
  margin-bottom: var(--m-space-3);
}

.m-detail-goods {
  display: flex;
  gap: var(--m-space-3);
}

.m-detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--m-space-3);
}
.m-detail-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.m-detail-label {
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
}
.m-detail-value {
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-primary);
  font-weight: var(--m-font-weight-medium);
  word-break: break-all;
}
.m-mono {
  font-family: var(--m-font-family-mono);
  font-size: var(--m-font-size-caption);
}
.m-price-text {
  color: var(--m-color-danger-text);
  font-weight: var(--m-font-weight-bold);
  font-size: var(--m-font-size-h3);
}

.m-sheet-footer {
  padding: var(--m-space-3) var(--m-space-4) var(--m-space-6);
  background: var(--m-color-bg-page);
  display: flex;
  gap: var(--m-space-2);
  flex-shrink: 0;
}
.m-sheet-btn {
  flex: 1;
  height: 46px;
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-lg);
  background: var(--m-color-bg-card);
  color: var(--m-color-text-secondary);
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-2);
  transition: all 0.15s;
}
.m-sheet-btn:active {
  transform: scale(0.97);
}
.m-sheet-btn-primary {
  flex: 2;
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  border: none;
}

.m-safe-bottom {
  height: calc(var(--m-space-4) + var(--m-safe-area-bottom));
}

@media (max-width: 380px) {
  .m-stat-grid {
    gap: var(--m-space-2);
  }
  .m-stat-card {
    padding: var(--m-space-3);
  }
  .m-stat-icon {
    width: 40px;
    height: 40px;
  }
  .m-stat-value {
    font-size: 18px;
  }
  .m-order-card {
    padding: var(--m-space-3);
  }
  .m-goods-image-wrap {
    width: 64px;
    height: 64px;
  }
}
</style>
