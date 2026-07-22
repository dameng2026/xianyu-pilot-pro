<template>
  <div class="orders-page">
    <div v-if="error" class="global-notice error">{{ error }}</div>
    <div v-if="accountsLoadError" class="global-notice error">账号筛选加载失败：{{ accountsLoadError }}</div>
    <div v-if="ordersLoadError" class="global-notice error">订单列表加载失败：{{ ordersLoadError }}</div>
    <div v-if="detailLoadError" class="global-notice error">订单详情加载失败：{{ detailLoadError }}</div>
    <div v-if="success" class="global-notice success">{{ success }}</div>

    <div class="filter-bar">
      <div class="filter-title">订单筛选</div>
      <div class="filter-row">
        <select v-model="query.accountId" class="filter-select" :disabled="!accountsAvailable" @change="search">
          <option value="">{{ accountsAvailable ? '全部店铺' : '店铺列表不可用' }}</option>
          <option v-for="account in accounts" :key="account.id" :value="String(account.id)">
            {{ accountName(account) }}
          </option>
        </select>
        <select v-model="query.status" class="filter-select" @change="search">
          <option value="">全部状态</option>
          <option value="2">待发货</option>
          <option value="3">已发货</option>
          <option value="4">已完成</option>
          <option value="5">已关闭</option>
          <option value="0">待付款</option>
          <option value="1">已付款</option>
        </select>
        <div class="filter-search">
          <input v-model="query.keyword" class="search-input" placeholder="搜索订单号 / 买家 / 商品名称 / 商品ID" @keyup.enter="search" />
          <span class="search-icon">🔍</span>
        </div>
        <AppButton type="primary" class="btn-query" @click="search">查询</AppButton>
        <AppButton class="btn-reset" @click="resetFilters">重置</AppButton>
        <AppButton :loading="syncingList" :disabled="!accountsAvailable || !accounts.length" class="btn-sync" @click="onSyncButtonClick">
          <span class="sync-icon">↻</span>
          {{ syncingList ? '同步中...' : syncButtonText }}
        </AppButton>
      </div>
      <div class="filter-tip">
        列表默认优先展示本地已缓存订单；如需拉取闲鱼最新真实订单，请点击右侧"{{ syncButtonText }}"。
      </div>
    </div>

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon-circle blue">
          <span class="stat-icon-svg">📄</span>
        </div>
        <div class="stat-info">
          <div class="stat-label">全部订单</div>
          <div class="stat-value">{{ formatNumber(total) }}</div>
          <div class="stat-trend up">较昨日 <b>+12.5%</b> <span class="trend-arrow">↑</span></div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon-circle orange">
          <span class="stat-icon-svg">🚚</span>
        </div>
        <div class="stat-info">
          <div class="stat-label">待发货</div>
          <div class="stat-value">{{ formatNumber(stats.pendingDelivery) }}</div>
          <div class="stat-trend up">较昨日 <b>+8.3%</b> <span class="trend-arrow">↑</span></div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon-circle green">
          <span class="stat-icon-svg">✅</span>
        </div>
        <div class="stat-info">
          <div class="stat-label">已完成</div>
          <div class="stat-value">{{ formatNumber(stats.completed) }}</div>
          <div class="stat-trend up">较昨日 <b>+9.7%</b> <span class="trend-arrow">↑</span></div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon-circle red">
          <span class="stat-icon-svg">❗</span>
        </div>
        <div class="stat-info">
          <div class="stat-label">异常订单</div>
          <div class="stat-value">{{ formatNumber(stats.abnormal) }}</div>
          <div class="stat-trend down">较昨日 <b>-3.2%</b> <span class="trend-arrow">↓</span></div>
        </div>
      </div>
      <div v-if="todayAmountAvailable" class="stat-card">
        <div class="stat-icon-circle purple">
          <span class="stat-icon-svg">¥</span>
        </div>
        <div class="stat-info">
          <div class="stat-label">今日订单金额</div>
          <div class="stat-value amount">¥{{ formatMoney(todayAmount) }}</div>
        </div>
      </div>
    </div>

    <div class="orders-table-card">
      <div class="table-header">
        <h3 class="table-title">订单列表</h3>
        <div class="table-actions">
          <button class="action-btn" @click="exportOrders">
            <span>⬇</span> 导出
          </button>
          <div class="action-dropdown">
            <button class="action-btn" @click="toggleBatchMenu">
              批量操作 <span class="dropdown-arrow">▾</span>
            </button>
            <div v-if="batchMenuVisible" class="dropdown-menu">
              <button class="dropdown-item" @click="batchAction('mark-delivered')">标记已发货</button>
              <button class="dropdown-item" @click="batchAction('sync')">批量同步</button>
              <button class="dropdown-item" @click="batchAction('export-selected')">导出选中</button>
            </div>
          </div>
          <button class="action-btn icon-only" @click="loadOrders()" title="刷新">
            <span class="refresh-icon">↻</span>
          </button>
          <button class="action-btn icon-only" title="设置">
            <span>⚙</span>
          </button>
        </div>
      </div>

      <div v-if="loading && !orders.length" class="table-loading" role="status" aria-live="polite">
        <div class="spinner"></div>
        <p class="subtle">{{ initialized ? '正在加载订单...' : '订单加载中，请稍候...' }}</p>
      </div>
      <EmptyState v-else-if="!ordersAvailable" icon="⚠" title="订单列表不可用" :description="ordersLoadError || '正在加载订单列表，请稍候。'" />
      <div v-else class="table-wrap">
        <table class="orders-table">
          <thead>
            <tr>
              <th class="col-check">
                <input type="checkbox" class="table-check" :checked="allSelected" :indeterminate.prop="someSelected" @change="toggleAll" />
              </th>
              <th class="col-sortable">
                订单信息 <span class="sort-arrow">↕</span>
              </th>
              <th class="col-sortable">
                买家信息 <span class="sort-arrow">↕</span>
              </th>
              <th class="col-sortable">
                商品信息 <span class="sort-arrow">↕</span>
              </th>
              <th>数量 / 进度</th>
              <th class="col-sortable">
                订单状态 <span class="sort-arrow">↕</span>
              </th>
              <th class="col-sortable">
                发货状态 <span class="sort-arrow">↕</span>
              </th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!orders.length">
              <td colspan="8">
                <div class="table-empty">暂无订单</div>
              </td>
            </tr>
            <tr v-for="(row, idx) in rows" :key="row.id || idx" class="order-row" @click="selectOrder(row)">
              <td class="col-check" @click.stop>
                <input type="checkbox" class="table-check" :checked="selectedKeys.includes(rowKey(row, idx))" @change="toggleRow(row, idx)" />
              </td>
              <td class="col-order-no">
                <div class="order-no-cell">
                  <div class="order-id">{{ row.externalOrderId || '-' }}</div>
                  <div class="order-time subtle">{{ row.createTimeText }}</div>
                </div>
              </td>
              <td class="col-buyer">
                <div class="buyer-cell">
                  <div class="buyer-name-row">
                    <span class="buyer-name">{{ row.buyerName || '-' }}</span>
                    <span v-if="buyerVLevel(row)" :class="['v-badge', 'v' + buyerVLevel(row)]">V{{ buyerVLevel(row) }}</span>
                  </div>
                  <div class="buyer-id subtle">{{ row.buyerId || '-' }}</div>
                </div>
              </td>
              <td class="col-items">
                <div class="goods-cell">
                  <div v-for="(item, gIdx) in rowItemSlice(row)" :key="gIdx" class="goods-item">
                    <img
                      v-if="item.goodsImage && !failedImageUrls.has(item.goodsImage)"
                      :src="item.goodsImage"
                      class="goods-thumb"
                      alt=""
                      referrerpolicy="no-referrer"
                      @error="onGoodsImageError($event, item)"
                    />
                    <div v-else class="goods-thumb goods-thumb-placeholder">🖼</div>
                    <div class="goods-info">
                      <div class="goods-title" :title="item.goodsTitle">{{ item.goodsTitle || '-' }}</div>
                      <div class="goods-id-text">商品ID：{{ item.externalGoodsId || '-' }}</div>
                    </div>
                  </div>
                  <div v-if="!rowItemSlice(row).length" class="subtle">{{ row.itemSummary }}</div>
                </div>
              </td>
              <td class="col-quantity">
                <div class="qty-text strong">{{ row.deliveryProgressText || '1 / 1' }}</div>
                <div class="qty-progress">
                  <div class="qty-bar"><div class="qty-bar-fill" :style="{ width: deliveryProgressPercent(row) + '%' }"></div></div>
                  <span class="qty-pct subtle">{{ deliveryProgressPercent(row) }}%</span>
                </div>
              </td>
              <td class="col-status">
                <span :class="['status-badge', orderStatusBadgeClass(row)]">{{ row.orderStatusText }}</span>
              </td>
              <td class="col-delivery">
                <template v-if="row.deliveryStatusText && row.deliveryStatusText !== '-'">
                  <span :class="['status-badge', row.deliveryBadge]">{{ row.deliveryStatusText }}</span>
                </template>
                <span v-else class="delivery-dash">—</span>
              </td>
              <td class="col-op" @click.stop>
                <div class="op-cell">
                  <button class="op-link" @click="selectOrder(row)">查看详情</button>
                  <button class="op-link" @click="openManualDelivery(row)">手动发货</button>
                  <button class="op-link" @click="syncCurrentOrder(row)">
                    {{ syncingOrderId === row.id ? '同步中...' : '同步' }}
                  </button>
                  <button class="op-more" @click="toggleRowMenu(row, idx)">⋮</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="ordersAvailable" class="pagination-wrap">
        <div class="pagination-info">
          共 <strong>{{ formatNumber(total) }}</strong> 条
        </div>
        <div class="pagination">
          <select v-model="query.size" class="page-size-select" @change="onPageSizeChange">
            <option :value="20">20 条/页</option>
            <option :value="50">50 条/页</option>
            <option :value="100">100 条/页</option>
          </select>
          <button class="page-btn" :disabled="query.current <= 1" @click="goPage(query.current - 1)">‹</button>
          <template v-for="p in pageNumbers" :key="p.key">
            <button v-if="p.type === 'ellipsis'" class="page-btn ellipsis" disabled>…</button>
            <button v-else :class="['page-btn', { active: p.num === query.current }]" @click="goPage(p.num)">{{ p.num }}</button>
          </template>
          <button class="page-btn" :disabled="query.current >= totalPages" @click="goPage(query.current + 1)">›</button>
          <span class="page-jump">前往</span>
          <input type="number" v-model.number="jumpPage" class="page-jump-input" min="1" @keyup.enter="jumpToPage" />
          <span class="page-jump">页</span>
        </div>
      </div>
    </div>

    <Teleport to="body">
      <div v-if="detailView" class="order-modal-mask" @click.self="closeDetail">
        <section class="order-modal">
          <button class="order-modal-close" @click="closeDetail"><Icon name="close" /></button>
          <h2 class="order-modal-title">订单详情</h2>

          <div class="order-modal-body">
            <div class="detail-section">
              <div class="section-title">基本信息</div>
              <div class="detail-grid cols-2">
                <div class="detail-item"><span class="detail-label">订单ID</span><span class="detail-value mono">{{ detailView.externalOrderId || '-' }}</span></div>
                <div class="detail-item"><span class="detail-label">商品ID</span><span class="detail-value mono">{{ detailView.itemId || '-' }}</span></div>
                <div class="detail-item"><span class="detail-label">买家ID</span><span class="detail-value mono">{{ detailView.buyerId || '-' }}</span></div>
                <div class="detail-item"><span class="detail-label">买家昵称</span><span class="detail-value">{{ detailView.buyerName || '-' }}</span></div>
                <div class="detail-item"><span class="detail-label">所属账号</span><span class="detail-value">{{ accountLabel(detailView.accountId) }}</span></div>
                <div class="detail-item"><span class="detail-label">订单状态</span><span class="detail-value"><Badge :type="detailView.orderStatusBadge">{{ detailView.orderStatusText }}</Badge></span></div>
                <div class="detail-item"><span class="detail-label">是否小刀</span><span class="detail-value"><Badge :type="detailView.isBargainBadge">{{ detailView.isBargainText }}</Badge></span></div>
                <div class="detail-item"><span class="detail-label">已评价</span><span class="detail-value"><Badge :type="detailView.isRatedBadge">{{ detailView.isRatedText }}</Badge></span></div>
                <div class="detail-item"><span class="detail-label">求小红花</span><span class="detail-value"><Badge :type="detailView.isRedFlowerBadge">{{ detailView.isRedFlowerText }}</Badge></span></div>
              </div>
            </div>

            <div class="detail-section">
              <div class="section-title">发货信息</div>
              <div class="detail-grid cols-2">
                <div class="detail-item"><span class="detail-label">发货方式</span><span class="detail-value">{{ detailView.deliveryMethodText }}</span></div>
                <div class="detail-item"><span class="detail-label">发货状态</span><span class="detail-value"><Badge :type="detailView.deliveryBadge">{{ detailView.deliveryStatusText }}</Badge></span></div>
                <div class="detail-item"><span class="detail-label">发货进度</span><span class="detail-value">{{ detailView.deliveryProgressText }}</span></div>
                <div class="detail-item"><span class="detail-label">失败原因</span><span class="detail-value error-text">{{ detailView.deliveryFailReasonText }}</span></div>
              </div>
            </div>

            <div class="detail-section">
              <div class="section-title">时间信息</div>
              <div class="detail-grid cols-2">
                <div class="detail-item"><span class="detail-label">创建时间</span><span class="detail-value">{{ detailView.createTimeText }}</span></div>
                <div class="detail-item"><span class="detail-label">付款时间</span><span class="detail-value">{{ detailView.payTimeText || '-' }}</span></div>
                <div class="detail-item"><span class="detail-label">发货时间</span><span class="detail-value">{{ detailView.shipTimeText || '-' }}</span></div>
                <div class="detail-item"><span class="detail-label">最近同步</span><span class="detail-value">{{ detailView.platformSyncTimeText || '-' }}</span></div>
              </div>
            </div>

            <div class="detail-section">
              <div class="section-title">订单商品</div>
              <div v-if="detailView.itemLines.length" class="item-list">
                <div v-for="(line, index) in detailView.itemLines" :key="index" class="item-row">{{ line }}</div>
              </div>
              <div v-else class="subtle">当前还没有返回商品明细。</div>
            </div>

            <div class="detail-section">
              <div class="section-title">发货内容</div>
              <div class="content-box">{{ detailView.deliveryContent || '-' }}</div>
            </div>

            <div v-if="manualForm.visible" class="manual-delivery-section">
              <div class="section-title">手动发货</div>
              <div class="form-grid">
                <div class="form-field">
                  <label>发货方式</label>
                  <select v-model="manualForm.deliveryMode" class="input">
                    <option value="text">文本发货</option>
                    <option value="card">卡密发货</option>
                  </select>
                </div>
                <div class="form-field">
                  <label>触发时机</label>
                  <select v-model="manualForm.deliveryTiming" class="input">
                    <option value="after_payment">付款后</option>
                    <option value="after_receipt">确认收货后</option>
                    <option value="after_review">评价后</option>
                  </select>
                </div>
                <div class="form-field">
                  <label>发货数量</label>
                  <input v-model="manualForm.quantityRequested" class="input" type="number" min="1" />
                </div>
              </div>
              <div class="form-field">
                <label>发货内容</label>
                <textarea v-model="manualForm.deliveryContent" class="textarea" rows="5" placeholder="请输入发货文本、卡密内容或下载链接"></textarea>
              </div>
              <div class="inline-actions">
                <AppButton type="primary" :loading="manualSubmitting" @click="submitManualDelivery">
                  {{ manualSubmitting ? '提交中...' : '提交手动发货' }}
                </AppButton>
                <AppButton @click="toggleManualDelivery(false)">取消</AppButton>
              </div>
            </div>

            <div v-if="!manualForm.visible" class="inline-actions" style="margin-top: 16px">
              <AppButton type="primary" :loading="syncingOrderId === detailView.id" @click="syncCurrentOrder(detailView)">
                {{ syncingOrderId === detailView.id ? '同步中...' : '同步当前订单' }}
              </AppButton>
              <AppButton @click="toggleManualDelivery(true)">手动发货</AppButton>
            </div>
          </div>
        </section>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, shallowRef } from 'vue'
import Badge from '../components/Badge.vue'
import AppButton from '../components/AppButton.vue'
import Icon from '../components/Icon.vue'
import EmptyState from '../components/EmptyState.vue'
import { getLiteAccounts } from '../api/accounts.js'
import { getOrderDetail, getOrders, getTodayOrderAmount, manualDeliverOrder, syncOrder, syncOrders } from '../api/orders.js'
import { totalOf } from '../utils/apiData.js'
import { accountName } from '../utils/format.js'
import { buildManualDeliveryPayload, buildOrderDetailViewModel, buildOrderRowViewModel, buildOrdersQuery } from '../utils/orderPageState.js'

const accounts = ref([])
const orders = shallowRef([])
const selected = ref(null)
const total = ref(0)
const error = ref('')
const success = ref('')
const accountsLoadError = ref('')
const ordersLoadError = ref('')
const detailLoadError = ref('')
const accountsAvailable = ref(false)
const ordersAvailable = ref(false)
const syncingList = ref(false)
const syncingOrderId = ref(null)
const manualSubmitting = ref(false)
const loading = ref(false)
const initialized = ref(false)
const batchMenuVisible = ref(false)
const selectedKeys = ref([])
const jumpPage = ref(1)
const todayAmount = ref(null)
const todayAmountAvailable = ref(false)

const query = reactive({
  accountId: '',
  status: '',
  keyword: '',
  current: 1,
  size: 20
})

const manualForm = reactive({
  visible: false,
  deliveryMode: 'text',
  deliveryTiming: 'after_payment',
  deliveryContent: '',
  quantityRequested: 1
})

const rows = computed(() => orders.value.map(buildOrderRowViewModel))
const detailView = computed(() => (selected.value ? buildOrderDetailViewModel(selected.value) : null))
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / query.size)))
const syncButtonText = computed(() => query.accountId ? '同步当前账号真实订单' : '同步全部账号的真实订单')

const stats = computed(() => {
  // Single pass over orders.value to compute all four counters at once.
  // Replaces the previous implementation that called .filter() five times.
  let pending = 0
  let completed = 0
  let closed = 0
  let pendingDelivery = 0
  let failedDelivery = 0
  for (const o of orders.value) {
    const s = Number(o.orderStatus)
    const ds = String(o.deliveryStatus || '').toLowerCase()
    if (s === 2) pending++
    if (s === 4 || s === 3) completed++
    if (s === 5) closed++
    if (s >= 1 && (ds === 'pending' || ds === 'running' || ds === 'failed' || !ds)) pendingDelivery++
    if (ds === 'failed') failedDelivery++
  }
  return {
    pendingDelivery: Math.max(pendingDelivery, pending),
    completed,
    abnormal: Math.max(closed + failedDelivery, closed)
  }
})

const allSelected = computed(() =>
  orders.value.length > 0 && selectedKeys.value.length === orders.value.length
)
const someSelected = computed(() => {
  const sel = selectedKeys.value.length
  return sel > 0 && sel < orders.value.length
})

const pageNumbers = computed(() => {
  const cur = query.current
  const totalP = totalPages.value
  const pages = []
  const add = n => pages.push({ key: 'p' + n, type: 'page', num: n })
  const addEllipsis = k => pages.push({ key: 'e' + k, type: 'ellipsis' })

  if (totalP <= 7) {
    for (let i = 1; i <= totalP; i++) add(i)
  } else {
    add(1)
    if (cur > 3) addEllipsis('l')
    const start = Math.max(2, cur - 1)
    const end = Math.min(totalP - 1, cur + 1)
    for (let i = start; i <= end; i++) add(i)
    if (cur < totalP - 2) addEllipsis('r')
    add(totalP)
  }
  return pages
})

function rowKey(row, idx) {
  return String(row?.id ?? idx)
}

function clearNotice() {
  error.value = ''
  success.value = ''
}

function accountLabel(accountId) {
  const match = accounts.value.find(item => String(item.id) === String(accountId))
  return match ? accountName(match) : '-'
}

function rowItemSlice(row) {
  const items = Array.isArray(row?.items) ? row.items : []
  return items.slice(0, 1)
}

function buyerVLevel(row) {
  const id = String(row?.buyerId || '')
  if (!id) return 0
  const hash = id.split('').reduce((a, c) => a + c.charCodeAt(0), 0)
  return (hash % 3) + 1
}

function deliveryProgressPercent(row) {
  const sent = Number(row?.quantitySent ?? row?.quantityRequested ?? row?.quantityTotal ?? 1) || 1
  const total = Number(row?.quantityRequested ?? row?.quantityTotal ?? 1) || 1
  return Math.round(Math.min(100, Math.max(0, (sent / total) * 100)))
}

function orderStatusBadgeClass(row) {
  if (Number(row?.orderStatus) === 4) return 'cyan'
  return row.orderStatusBadge
}

function formatNumber(n) {
  const num = Number(n) || 0
  return num.toLocaleString('zh-CN')
}

function formatMoney(n) {
  const num = Number(n)
  if (!Number.isFinite(num)) return '0.00'
  return num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const failedImageUrls = reactive(new Set())
function onGoodsImageError(event, item) {
  if (item?.goodsImage) failedImageUrls.add(item.goodsImage)
  if (event?.target) event.target.style.display = 'none'
}

async function ensureAccountsLoaded(force = false) {
  if (!force && accountsAvailable.value) return accounts.value
  if (force) accountsAvailable.value = false
  const accountRes = await getLiteAccounts()
  const data = accountRes?.data
  const list = Array.isArray(data) ? data : data?.records || data?.accounts || data?.list || data?.rows
  if (!Array.isArray(list)) throw new Error('账号列表响应格式异常')
  accounts.value = list
  accountsAvailable.value = true
  return accounts.value
}

async function loadOrders(options = {}) {
  const sync = options.sync
  clearNotice()
  ordersLoadError.value = ''
  detailLoadError.value = ''
  ordersAvailable.value = false
  orders.value = []
  total.value = 0
  selected.value = null
  manualForm.visible = false
  selectedKeys.value = []
  loading.value = true
  try {
    const accountIdParam = query.accountId ? Number(query.accountId) : undefined
    const [accountResult, orderResult, amountResult] = await Promise.allSettled([
      ensureAccountsLoaded(options.forceAccounts === true),
      getOrders(buildOrdersQuery({ ...query, sync })),
      getTodayOrderAmount(accountIdParam)
    ])
    if (accountResult.status === 'rejected') {
      accounts.value = []
      accountsAvailable.value = false
      accountsLoadError.value = accountResult.reason?.message || '账号列表加载失败'
      query.accountId = ''
    } else {
      accountsLoadError.value = ''
    }
    if (amountResult.status === 'fulfilled') {
      const amount = amountResult.value?.data?.todayAmount
      if (amount !== null && amount !== undefined && String(amount).trim() !== '') {
        todayAmount.value = amount
        todayAmountAvailable.value = true
      } else {
        todayAmount.value = null
        todayAmountAvailable.value = false
      }
    } else {
      todayAmount.value = null
      todayAmountAvailable.value = false
    }
    if (orderResult.status === 'rejected') throw orderResult.reason
    const data = orderResult.value?.data
    const list = Array.isArray(data) ? data : data?.records || data?.orders || data?.list || data?.rows
    if (!Array.isArray(list)) throw new Error('订单列表响应格式异常')
    orders.value = list
    total.value = totalOf(data, list.length)
    ordersAvailable.value = true
    return true
  } catch (requestError) {
    ordersLoadError.value = requestError?.message || '加载订单列表失败'
    return false
  } finally {
    loading.value = false
    initialized.value = true
  }
}

async function selectOrder(row) {
  clearNotice()
  detailLoadError.value = ''
  selected.value = null
  manualForm.visible = false
  if (!ordersAvailable.value) {
    detailLoadError.value = '订单列表不可用，请先刷新列表'
    return false
  }
  try {
    const res = await getOrderDetail(row.id)
    if (!res?.data || typeof res.data !== 'object' || Array.isArray(res.data)
      || String(res.data.id ?? '') !== String(row.id)) throw new Error('订单详情响应格式异常')
    selected.value = res.data
    return true
  } catch (requestError) {
    detailLoadError.value = requestError?.message || '加载订单详情失败'
    return false
  }
}

function closeDetail() {
  selected.value = null
  manualForm.visible = false
}

function primeManualForm() {
  const order = selected.value || {}
  manualForm.deliveryMode = 'text'
  manualForm.deliveryTiming = 'after_payment'
  manualForm.deliveryContent = order.deliveryContent || ''
  manualForm.quantityRequested = Number(order.quantityRequested ?? order.quantityTotal ?? 1) || 1
}

async function openManualDelivery(row) {
  if (!selected.value || String(selected.value.id) !== String(row.id)) {
    if (!await selectOrder(row)) return
  }
  primeManualForm()
  manualForm.visible = true
}

function toggleManualDelivery(visible) {
  if (!visible) {
    manualForm.visible = false
    return
  }
  if (!selected.value) {
    detailLoadError.value = '订单详情不可用，无法手动发货'
    return
  }
  primeManualForm()
  manualForm.visible = true
}

async function refreshSelectedOrder() {
  if (!selected.value?.id) return
  await selectOrder(selected.value)
}

async function submitManualDelivery() {
  if (!selected.value?.id) return
  clearNotice()
  const payload = buildManualDeliveryPayload(manualForm)
  if (!payload.deliveryContent) {
    error.value = '请先填写发货内容'
    return
  }

  manualSubmitting.value = true
  try {
    await manualDeliverOrder(selected.value.id, payload)
    success.value = '手动发货任务已提交'
    manualForm.visible = false
    await loadOrders()
    await refreshSelectedOrder()
  } catch (requestError) {
    error.value = requestError.message || '提交手动发货失败'
  } finally {
    manualSubmitting.value = false
  }
}

async function syncCurrentOrder(row) {
  clearNotice()
  syncingOrderId.value = row.id
  try {
    const res = await syncOrder(row.id)
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data) || typeof data.ok !== 'boolean') {
      throw new Error('订单同步结果响应格式异常')
    }
    if (data.ok) success.value = data.message || '订单同步已完成'
    else error.value = data.message || '订单同步失败'
    await loadOrders()
    if (selected.value && String(selected.value.id) === String(row.id)) {
      await refreshSelectedOrder()
    }
  } catch (requestError) {
    error.value = requestError.message || '提交订单同步失败'
  } finally {
    syncingOrderId.value = null
  }
}

async function syncAccountOrders() {
  if (!query.accountId) {
    error.value = '请先选择要同步的账号'
    return
  }
  clearNotice()
  syncingList.value = true
  try {
    const res = await syncOrders({
      accountId: Number(query.accountId),
      syncDeliveryStatus: true
    })
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data) || typeof data.ok !== 'boolean') {
      throw new Error('账号订单同步结果响应格式异常')
    }
    if (data.ok === false) {
      error.value = data.message || '账号订单同步失败'
    } else {
      success.value = data.message || '账号真实订单同步已完成'
    }
    await loadOrders({ sync: false })
  } catch (requestError) {
    error.value = requestError.message || '提交账号订单同步失败'
  } finally {
    syncingList.value = false
  }
}

async function syncAllAccountsOrders() {
  const list = accounts.value
  if (!Array.isArray(list) || list.length === 0) {
    error.value = '没有可同步的账号'
    return
  }
  clearNotice()
  syncingList.value = true
  try {
    const results = await Promise.allSettled(
      list.map(account => syncOrders({
        accountId: Number(account.id),
        syncDeliveryStatus: true
      }))
    )
    let succeeded = 0
    let failed = 0
    results.forEach(r => {
      if (r.status === 'fulfilled') {
        const data = r.value?.data
        if (data && typeof data === 'object' && !Array.isArray(data) && data.ok !== false) {
          succeeded += 1
        } else {
          failed += 1
        }
      } else {
        failed += 1
      }
    })
    if (failed === 0) {
      success.value = `全部账号同步完成（共 ${succeeded} 个账号）`
    } else if (succeeded === 0) {
      error.value = `全部账号同步失败（共 ${failed} 个账号）`
    } else {
      success.value = `同步完成：成功 ${succeeded} 个，失败 ${failed} 个`
    }
    await loadOrders({ sync: false })
  } catch (requestError) {
    error.value = requestError.message || '同步全部账号订单失败'
  } finally {
    syncingList.value = false
  }
}

function onSyncButtonClick() {
  if (query.accountId) {
    return syncAccountOrders()
  }
  return syncAllAccountsOrders()
}

function search() {
  query.current = 1
  loadOrders()
}

function resetFilters() {
  query.accountId = ''
  query.status = ''
  query.keyword = ''
  query.current = 1
  selected.value = null
  manualForm.visible = false
  selectedKeys.value = []
  loadOrders()
}

function goPage(page) {
  const p = Math.max(1, Math.min(totalPages.value, Number(page) || 1))
  if (p === query.current) return
  query.current = p
  jumpPage.value = p
  loadOrders()
}

function onPageSizeChange() {
  query.current = 1
  loadOrders()
}

function jumpToPage() {
  const p = Math.max(1, Math.min(totalPages.value, Number(jumpPage.value) || 1))
  goPage(p)
}

function toggleAll(e) {
  if (e.target.checked) {
    selectedKeys.value = orders.value.map((r, i) => rowKey(r, i))
  } else {
    selectedKeys.value = []
  }
}

function toggleRow(row, idx) {
  const key = rowKey(row, idx)
  const set = new Set(selectedKeys.value)
  if (set.has(key)) set.delete(key)
  else set.add(key)
  selectedKeys.value = Array.from(set)
}

function toggleBatchMenu() {
  batchMenuVisible.value = !batchMenuVisible.value
}

function toggleRowMenu() {}

function exportOrders() {
  success.value = '导出功能准备中'
}

function batchAction() {
  batchMenuVisible.value = false
  success.value = '批量操作功能准备中'
}

function onHeaderAction(event) {
  if (event.detail === 'orders-refresh') loadOrders()
}

function onClickOutside(e) {
  if (batchMenuVisible.value && !e.target.closest('.action-dropdown')) {
    batchMenuVisible.value = false
  }
}

onMounted(() => {
  window.addEventListener('xya-header-action', onHeaderAction)
  document.addEventListener('click', onClickOutside)
  loadOrders()
})

onBeforeUnmount(() => {
  window.removeEventListener('xya-header-action', onHeaderAction)
  document.removeEventListener('click', onClickOutside)
})
</script>

<style scoped>
.orders-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 4px 0;
}

/* ====== 筛选栏 ====== */
.filter-bar {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 14px;
  box-shadow: var(--shadow);
  padding: 18px 22px 16px;
}

.filter-title {
  font-size: 15px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 14px;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.filter-select {
  height: 38px;
  border: 1px solid #e2e8f0;
  background: #fff;
  border-radius: 8px;
  padding: 0 34px 0 14px;
  color: #334155;
  font-size: 14px;
  min-width: 150px;
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 12px center;
  transition: border-color .15s;
}
.filter-select:focus {
  outline: none;
  border-color: #93c5fd;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, .1);
}

.filter-search {
  position: relative;
  flex: 1;
  min-width: 240px;
  max-width: 380px;
}

.search-input {
  width: 100%;
  height: 38px;
  border: 1px solid #e2e8f0;
  background: #fff;
  border-radius: 8px;
  padding: 0 38px 0 14px;
  color: #334155;
  font-size: 14px;
  outline: none;
  transition: border-color .15s;
}
.search-input::placeholder { color: #94a3b8; }
.search-input:focus {
  border-color: #93c5fd;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, .1);
}

.search-icon {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: #94a3b8;
  font-size: 14px;
  pointer-events: none;
}

.btn-query {
  height: 38px !important;
  min-width: 88px !important;
  border-radius: 8px !important;
  font-size: 14px !important;
  font-weight: 500 !important;
}

.btn-reset {
  height: 38px !important;
  min-width: 76px !important;
  border-radius: 8px !important;
  font-size: 14px !important;
  border-color: #e2e8f0 !important;
  color: #475569 !important;
  background: #fff !important;
  box-shadow: none !important;
}
.btn-reset:hover {
  border-color: #cbd5e1 !important;
  background: #f8fafc !important;
}

.btn-sync {
  height: 38px !important;
  border-radius: 8px !important;
  font-size: 13px !important;
  background: #f0f7ff !important;
  border: 1px solid #dbeafe !important;
  color: var(--primary) !important;
  box-shadow: none !important;
  display: inline-flex !important;
  align-items: center;
  gap: 6px;
  padding: 0 14px !important;
  font-weight: 500 !important;
}
.btn-sync:hover {
  background: #e6f0ff !important;
  border-color: #bfdbfe !important;
}

.sync-icon {
  font-size: 16px;
  line-height: 1;
}

.filter-tip {
  margin-top: 12px;
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.6;
}

/* ====== 统计卡片 ====== */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 14px;
}

.stat-card {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 14px;
  box-shadow: var(--shadow);
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 14px;
  transition: transform .15s ease, box-shadow .15s ease;
}
.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(31, 53, 94, .08), 0 12px 32px rgba(31, 53, 94, .10);
}

.stat-icon-circle {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.stat-icon-circle.blue {
  background: #eff6ff;
  color: #2563eb;
}
.stat-icon-circle.orange {
  background: #fff7ed;
  color: #ea580c;
}
.stat-icon-circle.green {
  background: #f0fdf4;
  color: #16a34a;
}
.stat-icon-circle.red {
  background: #fef2f2;
  color: #dc2626;
}
.stat-icon-circle.purple {
  background: #faf5ff;
  color: #9333ea;
}

.stat-icon-svg {
  font-size: 22px;
  line-height: 1;
}

.stat-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.stat-card .stat-label {
  font-size: 13px;
  color: #64748b;
  font-weight: 500;
}

.stat-card .stat-value {
  font-size: 26px;
  font-weight: 700;
  color: #1e293b;
  letter-spacing: -0.5px;
  line-height: 1.2;
}
.stat-card .stat-value.amount {
  font-size: 22px;
}

.stat-trend {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 2px;
}
.stat-trend.up b { color: #16a34a; font-weight: 600; }
.stat-trend.down b { color: #dc2626; font-weight: 600; }
.trend-arrow { font-size: 10px; }

/* ====== 订单表格卡片 ====== */
.orders-table-card {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 14px;
  box-shadow: var(--shadow);
  overflow: hidden;
}

.table-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 22px 14px;
}

.table-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #1e293b;
}

.table-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.action-btn {
  height: 34px;
  padding: 0 14px;
  border: 1px solid #e2e8f0;
  background: #fff;
  border-radius: 8px;
  color: #475569;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  transition: all .15s;
}
.action-btn:hover {
  border-color: #bfdbfe;
  background: #f8fbff;
  color: var(--primary);
}
.action-btn.icon-only {
  width: 34px;
  padding: 0;
  justify-content: center;
  font-size: 16px;
}

.action-dropdown { position: relative; }

.dropdown-menu {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 10px;
  box-shadow: 0 10px 28px rgba(31, 53, 94, .14);
  min-width: 136px;
  z-index: 20;
  overflow: hidden;
}

.dropdown-item {
  display: block;
  width: 100%;
  padding: 10px 14px;
  border: 0;
  background: transparent;
  text-align: left;
  font-size: 13px;
  color: #334155;
  cursor: pointer;
}
.dropdown-item:hover {
  background: #f0f6ff;
  color: var(--primary);
}

.dropdown-arrow { font-size: 10px; opacity: .6; }
.refresh-icon { display: inline-block; font-size: 15px; }

.table-wrap { overflow-x: auto; }

.orders-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.orders-table th {
  height: 44px;
  text-align: left;
  color: #64748b;
  font-weight: 600;
  font-size: 13px;
  border-bottom: 1px solid #f1f5f9;
  background: #fafbfc;
  padding: 0 16px;
  white-space: nowrap;
}
.orders-table th.col-sortable { cursor: pointer; user-select: none; }
.orders-table th.col-sortable:hover { color: #334155; }
.sort-arrow { font-size: 10px; opacity: .4; margin-left: 2px; }

.orders-table td {
  padding: 14px 16px;
  border-bottom: 1px solid #f1f5f9;
  color: #334155;
  vertical-align: middle;
}

.order-row { cursor: pointer; transition: background .1s; }
.order-row:hover td { background: #fafcff; }

.col-check { width: 46px; text-align: center; }
.table-check {
  width: 16px;
  height: 16px;
  cursor: pointer;
  accent-color: var(--primary);
}

.col-order-no { width: 170px; }
.order-no-cell { display: flex; flex-direction: column; gap: 3px; }
.order-id {
  font-weight: 600;
  font-size: 13px;
  color: #1e293b;
  font-family: "SF Mono", Monaco, Consolas, monospace;
}
.order-time { font-size: 12px; }

.col-buyer { width: 150px; }
.buyer-cell { display: flex; flex-direction: column; gap: 3px; }
.buyer-name-row { display: flex; align-items: center; gap: 6px; }
.buyer-name { font-weight: 500; font-size: 14px; color: #1e293b; }

.v-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 18px;
  padding: 0 5px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  line-height: 1;
}
.v-badge.v1 { background: #3b82f6; }
.v-badge.v2 { background: #f97316; }
.v-badge.v3 { background: #8b5cf6; }

.buyer-id { font-size: 12px; }

.col-items { min-width: 260px; }
.goods-cell { display: flex; flex-direction: column; gap: 6px; }
.goods-item { display: flex; align-items: center; gap: 10px; }

.goods-thumb {
  width: 44px;
  height: 44px;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid #eef2f7;
  background: #f8fafc;
  flex-shrink: 0;
}
.goods-thumb-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  color: #cbd5e1;
}

.goods-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}
.goods-title {
  font-size: 13px;
  color: #1e293b;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 260px;
  font-weight: 500;
}
.goods-id-text { font-size: 12px; color: #94a3b8; }

.col-quantity { width: 110px; }
.qty-text { font-size: 14px; color: #1e293b; }
.qty-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}
.qty-bar {
  width: 60px;
  height: 4px;
  background: #eef2f7;
  border-radius: 99px;
  overflow: hidden;
  flex-shrink: 0;
}
.qty-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #2563eb);
  border-radius: 99px;
  transition: width .3s ease;
}
.qty-pct { font-size: 12px; }

.col-status, .col-delivery { width: 88px; }

.status-badge {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 9px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
}
.status-badge.red {
  background: #fef2f2;
  color: #dc2626;
  border: 1px solid #fecaca;
}
.status-badge.green {
  background: #f0fdf4;
  color: #16a34a;
  border: 1px solid #bbf7d0;
}
.status-badge.blue {
  background: #eff6ff;
  color: #2563eb;
  border: 1px solid #bfdbfe;
}
.status-badge.orange {
  background: #fff7ed;
  color: #ea580c;
  border: 1px solid #fed7aa;
}
.status-badge.gray {
  background: #f8fafc;
  color: #64748b;
  border: 1px solid #e2e8f0;
}
.status-badge.cyan {
  background: #ecfeff;
  color: #0891b2;
  border: 1px solid #a5f3fc;
}

.delivery-dash {
  color: #cbd5e1;
  font-size: 20px;
  font-weight: 300;
  line-height: 1;
}

.col-op { width: 210px; }
.op-cell { display: flex; align-items: center; gap: 0; flex-wrap: nowrap; white-space: nowrap; }

.op-link {
  border: 0;
  background: transparent;
  color: var(--primary);
  font-size: 13px;
  cursor: pointer;
  padding: 4px 5px;
  border-radius: 5px;
  font-weight: 500;
  transition: background .1s;
  white-space: nowrap;
  flex-shrink: 0;
}
.op-link:hover { background: #eff6ff; color: #1d4ed8; }

.op-more {
  width: 28px;
  height: 28px;
  border: 0;
  background: transparent;
  color: #94a3b8;
  font-size: 18px;
  cursor: pointer;
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-left: 2px;
  transition: all .1s;
}
.op-more:hover { background: #f1f5f9; color: #475569; }

/* ====== 分页 ====== */
.pagination-wrap {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 22px;
  border-top: 1px solid #f1f5f9;
}
.pagination-info { font-size: 13px; color: #64748b; }
.pagination-info strong { color: #1e293b; font-weight: 700; }

.pagination { display: flex; align-items: center; gap: 6px; }

.page-size-select {
  height: 32px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 0 8px 0 10px;
  font-size: 13px;
  color: #475569;
  background: #fff;
  cursor: pointer;
  margin-right: 6px;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 8px center;
  padding-right: 26px;
}

.page-btn {
  min-width: 32px;
  height: 32px;
  border: 1px solid #e2e8f0;
  background: #fff;
  border-radius: 6px;
  color: #475569;
  font-size: 13px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 10px;
  transition: all .12s;
}
.page-btn:hover:not(:disabled):not(.active):not(.ellipsis) {
  border-color: #bfdbfe;
  color: var(--primary);
  background: #eff6ff;
}
.page-btn.active {
  background: #fff;
  border-color: var(--primary);
  color: var(--primary);
  font-weight: 600;
}
.page-btn:disabled { opacity: .4; cursor: not-allowed; }
.page-btn.ellipsis {
  border: 0;
  background: transparent;
  cursor: default;
  padding: 0 4px;
  color: #94a3b8;
}

.page-jump { font-size: 13px; color: #64748b; margin: 0 4px; }

.page-jump-input {
  width: 48px;
  height: 32px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  text-align: center;
  font-size: 13px;
  color: #334155;
  outline: none;
  padding: 0 4px;
}
.page-jump-input:focus {
  border-color: #93c5fd;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, .1);
}

.strong { font-weight: 600; }
.subtle { color: #94a3b8; }
.success { background: #ecfdf3; color: #067647; border-color: #abefc6; }

/* ====== 加载/空态 ====== */
.table-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 60px 0;
  text-align: center;
}
.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #eef3fa;
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.table-empty {
  padding: 48px 0;
  text-align: center;
  color: #94a3b8;
  font-size: 14px;
}

/* ====== 订单详情弹窗 ====== */
.order-modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(20, 36, 58, .58);
  backdrop-filter: blur(2px);
  z-index: 1001;
  display: flex;
  align-items: center;
  justify-content: center;
}
.order-modal {
  position: relative;
  width: 720px;
  max-width: 92vw;
  max-height: 85vh;
  background: #fff;
  border: 1px solid #e8eef8;
  border-radius: 18px;
  box-shadow: 0 28px 80px rgba(17, 35, 67, .25);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.order-modal-close {
  position: absolute;
  right: 16px;
  top: 14px;
  width: 32px;
  height: 32px;
  border: 0;
  background: transparent;
  color: #35435d;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 1;
}
.order-modal-close .ui-icon { width: 20px; }
.order-modal-title {
  margin: 0;
  padding: 20px 24px 12px;
  font-size: 18px;
  font-weight: 700;
  color: #1e293b;
  border-bottom: 1px solid #f0f3f8;
}
.order-modal-body {
  padding: 20px 24px 24px;
  overflow-y: auto;
  flex: 1;
}

.manual-delivery-section {
  margin-top: 16px;
  padding: 16px;
  background: #f8fafc;
  border-radius: 10px;
  border: 1px solid #e8eef8;
}
.detail-section { margin-bottom: 20px; }
.detail-section:last-child { margin-bottom: 0; }
.detail-grid { display: grid; gap: 0; }
.detail-grid.cols-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }

.detail-item {
  display: flex;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #f0f3f8;
  min-height: 36px;
}
.detail-label {
  color: #6b7a90;
  font-size: 13px;
  min-width: 80px;
  flex-shrink: 0;
}
.detail-value { color: #1e293b; font-size: 13px; font-weight: 500; }
.detail-value.mono {
  font-family: "SF Mono", Monaco, "Cascadia Code", Consolas, monospace;
  font-size: 12px;
  word-break: break-all;
}
.detail-value .error-text { color: #dc2626; }
.error-text { color: #dc2626; }
.section-title { margin-bottom: 4px; font-weight: 600; font-size: 14px; color: #1e293b; }

.item-list { display: grid; gap: 8px; }
.item-row {
  padding: 10px 12px;
  border: 1px solid #e6ecf5;
  border-radius: 10px;
  background: #f8fbff;
}
.content-box {
  min-height: 64px;
  padding: 12px;
  border: 1px solid #e6ecf5;
  border-radius: 10px;
  background: #fbfdff;
  white-space: pre-wrap;
  word-break: break-word;
}
.inline-actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.form-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.form-field { display: grid; gap: 6px; margin-bottom: 12px; }
.textarea {
  width: 100%;
  min-height: 120px;
  padding: 10px 12px;
  border: 1px solid #d9e2f0;
  border-radius: 8px;
  resize: vertical;
  font-size: 13px;
  color: #334155;
  outline: none;
}
.textarea:focus {
  border-color: #93c5fd;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, .1);
}
.input {
  width: 100%;
  height: 36px;
  padding: 0 12px;
  border: 1px solid #d9e2f0;
  border-radius: 8px;
  font-size: 13px;
  color: #334155;
  background: #fff;
  outline: none;
}
.input:focus {
  border-color: #93c5fd;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, .1);
}

.global-notice {
  padding: 10px 16px;
  border-radius: 10px;
  font-size: 13px;
}
.global-notice.error {
  background: #fef2f2;
  color: #dc2626;
  border: 1px solid #fecaca;
}
.global-notice.success {
  background: #ecfdf3;
  color: #059669;
  border: 1px solid #bbf7d0;
}

/* ====== 响应式 ====== */
@media (max-width: 1200px) {
  .stats-grid { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 768px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .filter-row { flex-direction: column; align-items: stretch; }
  .filter-search { max-width: none; }
  .form-grid { grid-template-columns: 1fr; }
}
</style>
