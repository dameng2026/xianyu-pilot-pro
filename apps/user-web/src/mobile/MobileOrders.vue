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
              {{ order.orderStatusText || '未知状态' }}
            </span>
          </div>

          <div class="m-order-time">{{ order.createTimeText || '-' }}</div>

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
                <span class="m-progress-text">{{ order.deliveryProgressText || '1/1' }}</span>
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
        <button class="m-load-btn" @click="loadMore" :disabled="loadingMore">
          {{ loadingMore ? '加载中...' : '加载更多' }}
        </button>
      </div>
    </template>

    <Teleport to="body">
      <div v-if="detailOrder" class="m-modal-mask" @click.self="closeDetail">
        <div class="m-detail-sheet">
          <div class="m-sheet-handle"></div>
          <div class="m-sheet-header">
            <h3>订单详情</h3>
            <button class="m-sheet-close" @click="closeDetail">
              <MIcon name="x" :size="20" />
            </button>
          </div>

          <div class="m-sheet-body">
            <div class="m-detail-status-row">
              <span :class="['m-status-badge', 'm-status-lg', statusBadgeClass(detailOrder)]">
                {{ detailOrder.orderStatusText || '未知状态' }}
              </span>
              <span class="m-detail-id">{{ detailOrder.externalOrderId || '-' }}</span>
            </div>

            <div class="m-detail-section">
              <div class="m-detail-title">商品信息</div>
              <div class="m-detail-goods">
                <div class="m-goods-image-wrap m-goods-lg">
                  <img
                    v-if="firstGoodsImage(detailOrder) && !failedImages.has(firstGoodsImage(detailOrder))"
                    :src="firstGoodsImage(detailOrder)"
                    class="m-goods-image"
                    alt=""
                    referrerpolicy="no-referrer"
                    @error="onImageError($event, detailOrder)"
                  />
                  <div v-else class="m-goods-image m-goods-placeholder">
                    <MIcon name="image" :size="32" />
                  </div>
                </div>
                <div class="m-goods-info">
                  <div class="m-goods-title m-goods-lg">{{ firstGoodsTitle(detailOrder) || '-' }}</div>
                  <div class="m-goods-meta">
                    <span>商品ID: {{ firstGoodsId(detailOrder) || '-' }}</span>
                  </div>
                </div>
              </div>
            </div>

            <div class="m-detail-section">
              <div class="m-detail-title">订单信息</div>
              <div class="m-detail-grid">
                <div class="m-detail-item">
                  <span class="m-detail-label">买家昵称</span>
                  <span class="m-detail-value">{{ detailOrder.buyerName || '-' }}</span>
                </div>
                <div class="m-detail-item">
                  <span class="m-detail-label">买家ID</span>
                  <span class="m-detail-value m-mono">{{ detailOrder.buyerId || '-' }}</span>
                </div>
                <div class="m-detail-item">
                  <span class="m-detail-label">订单金额</span>
                  <span class="m-detail-value m-price-text">¥{{ formatMoney(detailOrder.totalAmount) }}</span>
                </div>
                <div class="m-detail-item">
                  <span class="m-detail-label">创建时间</span>
                  <span class="m-detail-value">{{ detailOrder.createTimeText || '-' }}</span>
                </div>
                <div class="m-detail-item">
                  <span class="m-detail-label">发货状态</span>
                  <span class="m-detail-value">{{ detailOrder.deliveryStatusText || '-' }}</span>
                </div>
                <div class="m-detail-item">
                  <span class="m-detail-label">发货进度</span>
                  <span class="m-detail-value">{{ detailOrder.deliveryProgressText || '-' }}</span>
                </div>
              </div>
            </div>
          </div>

          <div class="m-sheet-footer">
            <button v-if="canSync(detailOrder)" class="m-sheet-btn" @click="doSyncDetail">
              <MIcon name="refreshCw" :size="18" />
              同步
            </button>
            <button v-if="canDeliver(detailOrder)" class="m-sheet-btn m-sheet-btn-primary" @click="doDeliverDetail">
              <MIcon name="truck" :size="18" />
              手动发货
            </button>
            <button v-if="canRepurchase(detailOrder)" class="m-sheet-btn" @click="repurchase(detailOrder)">
              <MIcon name="repeat" :size="18" />
              再次购买
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <div class="m-safe-bottom"></div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import MIcon from './MIcon.vue'
import MobileUnavailableState from './MobileUnavailableState.vue'
import { getOrders, syncOrder as apiSyncOrder, syncOrders as apiSyncOrders } from '../api/orders.js'

const emit = defineEmits(['navigate', 'force-desktop', 'back'])

const loading = ref(true)
const loadingMore = ref(false)
const loadError = ref('')
const searchKeyword = ref('')
const activeStatus = ref('')
const orders = ref([])
const detailOrder = ref(null)
const failedImages = reactive(new Set())
const syncing = ref(false)

const query = reactive({
  current: 1,
  size: 20,
  status: '',
  keyword: '',
  accountId: ''
})

const stats = reactive({
  total: 0,
  pending: 0,
  completed: 0,
  closed: 0
})

const statusTabs = computed(() => [
  { label: '全部', value: '', count: stats.total },
  { label: '待发货', value: '2', count: stats.pending },
  { label: '已发货', value: '3', count: 0 },
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

function firstGoodsId(order) {
  const item = firstGoodsItem(order)
  return item.externalGoodsId || item.itemId || item.goodsId || ''
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
  const text = order.deliveryProgressText || '1/1'
  const match = text.match(/(\d+)\s*\/\s*(\d+)/)
  if (!match) return 100
  const [, delivered, total] = match
  const t = Number(total) || 1
  const d = Number(delivered) || 0
  return Math.min(100, Math.round((d / t) * 100))
}

function canSync(order) {
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

function calculateStats(list, total) {
  let pending = 0, completed = 0, closed = 0
  list.forEach(o => {
    const s = Number(o.orderStatus)
    if (s === 2) pending++
    if (s === 4) completed++
    if (s === 5) closed++
  })
  if (query.current === 1 && !query.status && !query.keyword) {
    stats.pending = pending
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
  detailOrder.value = order
}

function closeDetail() {
  detailOrder.value = null
}

async function syncOrder(order) {
  if (syncing.value) return
  syncing.value = true
  try {
    await apiSyncOrder(order.id)
    await loadOrders()
  } catch (e) {
    console.error('同步失败', e)
  } finally {
    syncing.value = false
  }
}

async function syncOrders() {
  if (syncing.value) return
  syncing.value = true
  try {
    await apiSyncOrders({})
    query.current = 1
    await loadOrders()
  } catch (e) {
    console.error('同步失败', e)
  } finally {
    syncing.value = false
  }
}

function doSyncDetail() {
  if (detailOrder.value) {
    syncOrder(detailOrder.value)
    closeDetail()
  }
}

function doDeliverDetail() {
  closeDetail()
  emit('force-desktop', 'orders')
}

function openDelivery(order) {
  emit('force-desktop', 'orders')
}

function repurchase(order) {
  closeDetail()
  emit('force-desktop', 'products')
}

onMounted(() => {
  loadOrders()
})
</script>

<style scoped>
.m-orders {
  padding: 12px 16px 0;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
}

.m-page-header {
  margin-bottom: 14px;
}
.m-page-header h1 {
  margin: 0 0 4px;
  font-size: 24px;
  font-weight: 800;
  color: #15213d;
  line-height: 1.2;
}
.m-page-sub {
  margin: 0;
  font-size: 13px;
  color: #8c98ae;
  line-height: 1.5;
}

.m-stat-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 14px;
}
.m-stat-card {
  background: white;
  border-radius: 16px;
  padding: 14px;
  display: flex;
  align-items: center;
  gap: 10px;
  box-shadow: 0 2px 8px rgba(31, 53, 94, 0.05);
  border: 1px solid #f0f4fa;
  cursor: pointer;
  transition: transform 0.15s;
}
.m-stat-card:active {
  transform: scale(0.97);
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
.m-stat-blue { background: linear-gradient(135deg, #e8f1ff, #d4e4ff); color: #0d6bff; }
.m-stat-green { background: linear-gradient(135deg, #e2f8ee, #cdf2df); color: #16bf78; }
.m-stat-orange { background: linear-gradient(135deg, #fff4e0, #ffe7c2); color: #ff9f22; }
.m-stat-red { background: linear-gradient(135deg, #ffe8e8, #ffd1d1); color: #ef4444; }
.m-stat-info { flex: 1; min-width: 0; }
.m-stat-label { font-size: 12px; color: #8c98ae; margin-bottom: 2px; }
.m-stat-value {
  font-size: 20px;
  font-weight: 800;
  color: #15213d;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}

.m-search-section {
  margin-bottom: 12px;
}
.m-search-bar {
  display: flex;
  align-items: center;
  background: white;
  border-radius: 14px;
  padding: 0 14px;
  height: 44px;
  box-shadow: 0 2px 8px rgba(31, 53, 94, 0.04);
  border: 1px solid #f0f4fa;
  gap: 10px;
}
.m-search-icon {
  color: #8c98ae;
  flex-shrink: 0;
}
.m-search-input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 14px;
  color: #15213d;
  background: transparent;
  min-width: 0;
}
.m-search-input::placeholder {
  color: #aeb9ca;
}
.m-search-clear {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: none;
  background: #eef2f8;
  color: #8c98ae;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  padding: 0;
}

.m-status-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
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
  padding: 0 14px;
  border: none;
  background: #f1f5fb;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  color: #72809a;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 5px;
}
.m-status-tab.active {
  background: linear-gradient(135deg, #0d6bff, #3b82f6);
  color: white;
  box-shadow: 0 3px 10px rgba(13, 107, 255, 0.25);
}
.m-tab-count {
  background: rgba(255,255,255,0.25);
  padding: 0 6px;
  border-radius: 8px;
  font-size: 11px;
  min-width: 18px;
  text-align: center;
}
.m-status-tab:not(.active) .m-tab-count {
  background: #e1e8f3;
  color: #5a6a85;
}

.m-loading {
  padding: 48px 0;
  text-align: center;
  color: #8c98ae;
  font-size: 14px;
}

.m-empty {
  padding: 48px 16px;
  text-align: center;
  color: #8c98ae;
}
.m-empty-icon {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: linear-gradient(135deg, #e8f1ff, #d4e4ff);
  color: #0d6bff;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 14px;
  opacity: 0.7;
}
.m-empty-text {
  font-size: 16px;
  font-weight: 600;
  color: #5a6a85;
  margin-bottom: 6px;
}
.m-empty-desc {
  font-size: 12px;
  color: #9aa6bd;
  line-height: 1.6;
  margin-bottom: 16px;
}
.m-empty-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 40px;
  padding: 0 20px;
  border: none;
  border-radius: 20px;
  background: linear-gradient(135deg, #0d6bff, #3b82f6);
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(13, 107, 255, 0.25);
}

.m-order-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.m-order-card {
  background: white;
  border-radius: 18px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(31, 53, 94, 0.04);
  border: 1px solid #f0f4fa;
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
  margin-bottom: 4px;
}
.m-order-id {
  font-size: 13px;
  font-weight: 700;
  color: #15213d;
  font-family: 'SF Mono', Monaco, monospace;
}
.m-status-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 8px;
}
.status-orange { background: #fff4e0; color: #e08a00; }
.status-completed { background: #e2f8ee; color: #0ea366; }
.status-shipped { background: #e0f7fb; color: #0891b2; }
.status-paid { background: #e8f1ff; color: #0d6bff; }
.status-red { background: #ffe8e8; color: #dc2626; }
.status-gray { background: #f1f5fb; color: #72809a; }
.m-status-lg {
  font-size: 13px;
  padding: 5px 14px;
  border-radius: 10px;
}

.m-order-time {
  font-size: 12px;
  color: #9aa6bd;
  margin-bottom: 12px;
}

.m-order-goods {
  display: flex;
  gap: 12px;
  margin-bottom: 14px;
}
.m-goods-image-wrap {
  width: 72px;
  height: 72px;
  border-radius: 12px;
  overflow: hidden;
  flex-shrink: 0;
  background: #f5f7fb;
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
  color: #c5cfe0;
  background: #f5f7fb;
}
.m-goods-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
.m-goods-title {
  font-size: 14px;
  font-weight: 600;
  color: #15213d;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin-bottom: 4px;
}
.m-goods-lg {
  font-size: 15px;
  -webkit-line-clamp: 2;
}
.m-goods-meta {
  font-size: 12px;
  color: #8c98ae;
  margin-bottom: 8px;
}

.m-progress-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.m-progress {
  flex: 1;
  height: 6px;
  background: #eef2f8;
  border-radius: 100px;
  overflow: hidden;
}
.m-progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #0d6bff, #3b82f6);
  border-radius: 100px;
  transition: width 0.3s ease;
}
.m-progress-text {
  font-size: 11px;
  color: #8c98ae;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}

.m-order-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 12px;
  border-top: 1px solid #f0f4fa;
}
.m-order-price {
  display: flex;
  align-items: baseline;
  gap: 4px;
}
.m-price-label {
  font-size: 12px;
  color: #8c98ae;
}
.m-price-value {
  font-size: 18px;
  font-weight: 800;
  color: #ef4444;
  font-variant-numeric: tabular-nums;
}

.m-order-actions {
  display: flex;
  gap: 8px;
}
.m-action-btn {
  height: 32px;
  padding: 0 14px;
  border: 1px solid #e5e9f2;
  border-radius: 10px;
  background: white;
  color: #5a6a85;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: all 0.15s;
}
.m-action-btn:active {
  transform: scale(0.95);
}
.m-action-primary {
  background: linear-gradient(135deg, #0d6bff, #3b82f6);
  color: white;
  border: none;
  box-shadow: 0 3px 8px rgba(13, 107, 255, 0.25);
}

.m-load-more {
  padding: 16px 0;
  text-align: center;
}
.m-load-btn {
  height: 40px;
  padding: 0 24px;
  border: none;
  border-radius: 20px;
  background: #f1f5fb;
  color: #5a6a85;
  font-size: 13px;
  font-weight: 600;
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
  background: rgba(21, 33, 61, 0.5);
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
  background: #f8faff;
  border-radius: 24px 24px 0 0;
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
  background: #dde5f0;
  border-radius: 2px;
  margin: 10px auto 0;
  flex-shrink: 0;
}

.m-sheet-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  flex-shrink: 0;
}
.m-sheet-header h3 {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  color: #15213d;
}
.m-sheet-close {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: none;
  background: #f1f5fb;
  color: #72809a;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
}

.m-sheet-body {
  flex: 1;
  overflow-y: auto;
  padding: 0 16px 16px;
}

.m-detail-status-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}
.m-detail-id {
  font-size: 12px;
  color: #8c98ae;
  font-family: 'SF Mono', Monaco, monospace;
}

.m-detail-section {
  background: white;
  border-radius: 16px;
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: 0 2px 8px rgba(31, 53, 94, 0.04);
}
.m-detail-title {
  font-size: 14px;
  font-weight: 700;
  color: #15213d;
  margin-bottom: 12px;
}

.m-detail-goods {
  display: flex;
  gap: 12px;
}

.m-detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.m-detail-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.m-detail-label {
  font-size: 11px;
  color: #8c98ae;
}
.m-detail-value {
  font-size: 13px;
  color: #15213d;
  font-weight: 500;
  word-break: break-all;
}
.m-mono {
  font-family: 'SF Mono', Monaco, monospace;
  font-size: 12px;
}
.m-price-text {
  color: #ef4444;
  font-weight: 700;
  font-size: 15px;
}

.m-sheet-footer {
  padding: 12px 16px 24px;
  background: #f8faff;
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}
.m-sheet-btn {
  flex: 1;
  height: 46px;
  border: 1px solid #e5e9f2;
  border-radius: 14px;
  background: white;
  color: #5a6a85;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: all 0.15s;
}
.m-sheet-btn:active {
  transform: scale(0.97);
}
.m-sheet-btn-primary {
  flex: 2;
  background: linear-gradient(135deg, #0d6bff, #3b82f6);
  color: white;
  border: none;
  box-shadow: 0 4px 12px rgba(13, 107, 255, 0.3);
}

.m-safe-bottom {
  height: 20px;
}

@media (max-width: 380px) {
  .m-stat-grid {
    gap: 8px;
  }
  .m-stat-card {
    padding: 12px;
  }
  .m-stat-icon {
    width: 40px;
    height: 40px;
  }
  .m-stat-value {
    font-size: 18px;
  }
  .m-order-card {
    padding: 14px;
  }
  .m-goods-image-wrap {
    width: 64px;
    height: 64px;
  }
}
</style>
