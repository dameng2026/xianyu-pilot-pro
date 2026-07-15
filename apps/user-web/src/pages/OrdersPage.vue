<template>
  <div>
    <div v-if="error" class="global-notice error">{{ error }}</div>
    <div v-if="accountsLoadError" class="global-notice error">账号筛选加载失败：{{ accountsLoadError }}</div>
    <div v-if="ordersLoadError" class="global-notice error">订单列表加载失败：{{ ordersLoadError }}</div>
    <div v-if="detailLoadError" class="global-notice error">订单详情加载失败：{{ detailLoadError }}</div>
    <div v-if="success" class="global-notice success">{{ success }}</div>

    <CardPanel title="订单筛选">
      <div class="toolbar wrap">
        <select v-model="query.accountId" class="input select" :disabled="!accountsAvailable" @change="search">
          <option value="">{{ accountsAvailable ? '全部账号' : '账号列表不可用' }}</option>
          <option v-for="account in accounts" :key="account.id" :value="String(account.id)">
            {{ accountName(account) }}
          </option>
        </select>
        <select v-model="query.status" class="input select" @change="search">
          <option value="">全部状态</option>
          <option value="0">待付款</option>
          <option value="1">已付款</option>
          <option value="2">待发货</option>
          <option value="3">已发货</option>
          <option value="4">已完成</option>
          <option value="5">已关闭</option>
        </select>
        <input v-model="query.keyword" class="input grow" placeholder="搜索订单号 / 买家 / 商品" @keyup.enter="search" />
        <AppButton type="primary" @click="search">查询</AppButton>
        <AppButton @click="resetFilters">重置</AppButton>
        <AppButton :loading="syncingList" :disabled="!accountsAvailable || !query.accountId" @click="syncAccountOrders">
          {{ syncingList ? '同步中...' : '同步当前账号真实订单' }}
        </AppButton>
      </div>
      <div class="sync-tip">
        列表默认优先展示本地已缓存订单；如需拉取闲鱼最新真实订单，请点击右侧“同步当前账号真实订单”。
      </div>
    </CardPanel>

    <CardPanel title="订单列表" style="margin-top: 16px">
      <div v-if="loading && !orders.length" class="table-loading" role="status" aria-live="polite">
        <div class="spinner"></div>
        <p class="subtle">{{ initialized ? '正在加载订单...' : '订单加载中，请稍候...' }}</p>
      </div>
      <EmptyState v-else-if="!ordersAvailable" icon="⚠" title="订单列表不可用" :description="ordersLoadError || '正在加载订单列表，请稍候。'" />
      <BaseTable v-else :columns="columns" :rows="rows" @row-click="selectOrder">
        <template #empty>
          <div class="table-empty">
            暂无订单
          </div>
        </template>
        <template #orderNo="{ row }">
          <div>
            <div class="strong">{{ row.externalOrderId || '-' }}</div>
            <div class="subtle">{{ row.createTimeText }}</div>
          </div>
        </template>
        <template #buyer="{ row }">
          <div>
            <div class="strong">{{ row.buyerName || '-' }}</div>
            <div class="subtle">{{ row.buyerId || '-' }}</div>
          </div>
        </template>
        <template #items="{ row }">
          <div class="goods-cell">
            <div v-for="(item, idx) in rowItemSlice(row)" :key="idx" class="goods-item">
              <img
                v-if="item.goodsImage && !failedImageUrls.has(item.goodsImage)"
                :src="item.goodsImage"
                class="goods-thumb"
                alt=""
                referrerpolicy="no-referrer"
                @error="onGoodsImageError($event, item)"
              />
              <div class="goods-info">
                <div class="goods-title">{{ item.goodsTitle || '-' }}<span v-if="item.externalGoodsId" class="goods-id-inline">（{{ item.externalGoodsId }}）</span></div>
              </div>
            </div>
            <div v-if="!rowItemSlice(row).length" class="subtle">{{ row.itemSummary }}</div>
          </div>
        </template>
        <template #quantity="{ row }">
          <div>
            <div class="strong">{{ row.quantityTotalText }}</div>
            <div class="subtle">{{ row.deliveryProgressText }}</div>
          </div>
        </template>
        <template #orderStatus="{ row }">
          <Badge :type="row.orderStatusBadge">{{ row.orderStatusText }}</Badge>
        </template>
        <template #delivery="{ row }">
          <div>
            <Badge :type="row.deliveryBadge">{{ row.deliveryStatusText }}</Badge>
            <div class="subtle" style="margin-top: 4px">{{ row.platformSyncTimeText }}</div>
          </div>
        </template>
        <template #op="{ row }">
          <div class="inline-actions">
            <button class="link" @click.stop="selectOrder(row)">查看详情</button>
            <button class="link" @click.stop="openManualDelivery(row)">手动发货</button>
            <button class="link" @click.stop="syncCurrentOrder(row)">
              {{ syncingOrderId === row.id ? '同步中...' : '同步' }}
            </button>
          </div>
        </template>
      </BaseTable>
      <Pagination v-if="ordersAvailable" :total="total" :current="query.current" :page-size="query.size" @page-change="goPage" />
    </CardPanel>

    <!-- 订单详情弹窗 -->
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

            <!-- 手动发货表单（内嵌展开） -->
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
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import CardPanel from '../components/CardPanel.vue'
import BaseTable from '../components/BaseTable.vue'
import Badge from '../components/Badge.vue'
import AppButton from '../components/AppButton.vue'
import Pagination from '../components/Pagination.vue'
import Icon from '../components/Icon.vue'
import EmptyState from '../components/EmptyState.vue'
import { getLiteAccounts } from '../api/accounts.js'
import { getOrderDetail, getOrders, manualDeliverOrder, syncOrder, syncOrders } from '../api/orders.js'
import { totalOf } from '../utils/apiData.js'
import { accountName } from '../utils/format.js'
import { buildManualDeliveryPayload, buildOrderDetailViewModel, buildOrderRowViewModel, buildOrdersQuery } from '../utils/orderPageState.js'

const accounts = ref([])
const orders = ref([])
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
// 首次加载是否已完成，区分“初始加载中”与“空结果”
const initialized = ref(false)

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

const columns = [
  { key: 'orderNo', title: '订单信息' },
  { key: 'buyer', title: '买家信息' },
  { key: 'items', title: '商品信息' },
  { key: 'quantity', title: '数量 / 进度' },
  { key: 'orderStatus', title: '订单状态' },
  { key: 'delivery', title: '发货状态' },
  { key: 'op', title: '操作' }
]

const rows = computed(() => orders.value.map(buildOrderRowViewModel))
const detailView = computed(() => (selected.value ? buildOrderDetailViewModel(selected.value) : null))

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
  return items.slice(0, 2)
}

// 记录加载失败的图片 URL，避免污染原数据（切换页码再回来时可重新尝试）
const failedImageUrls = reactive(new Set())
function onGoodsImageError(event, item) {
  // 封面图加载失败时记录 URL，仅显示文字（不修改原数据）
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
  loading.value = true
  try {
    const [accountResult, orderResult] = await Promise.allSettled([
      ensureAccountsLoaded(options.forceAccounts === true),
      getOrders(buildOrdersQuery({ ...query, sync }))
    ])
    if (accountResult.status === 'rejected') {
      accounts.value = []
      accountsAvailable.value = false
      accountsLoadError.value = accountResult.reason?.message || '账号列表加载失败'
      query.accountId = ''
    } else {
      accountsLoadError.value = ''
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
    await loadOrders({ keepSelectedId: selected.value.id, sync: false })
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
    await loadOrders({ keepSelectedId: row.id, sync: false })
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
  loadOrders({ keepSelectedId: null })
}

function goPage(page) {
  query.current = page
  loadOrders()
}

function onHeaderAction(event) {
  if (event.detail === 'orders-refresh') loadOrders()
}

onMounted(() => {
  window.addEventListener('xya-header-action', onHeaderAction)
  loadOrders()
})

onBeforeUnmount(() => {
  window.removeEventListener('xya-header-action', onHeaderAction)
})
</script>

<style scoped>
/* 订单详情弹窗 */
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

.order-modal-close .ui-icon {
  width: 20px;
}

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

.wrap {
  flex-wrap: wrap;
}

.select {
  max-width: 220px;
}

.grow {
  flex: 1 1 240px;
}

.sync-tip {
  margin-top: 10px;
  color: #6b7a90;
  font-size: 12px;
  line-height: 1.6;
}

.goods-cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.goods-item {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.goods-thumb {
  width: 40px;
  height: 40px;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid #e6ecf5;
  background: #f5f7fa;
  flex-shrink: 0;
}

.goods-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.goods-title {
  font-size: 13px;
  color: #2a3142;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 220px;
}

.goods-id-inline {
  font-size: 12px;
  color: #8893a7;
  font-weight: normal;
}

.goods-id {
  font-size: 11px;
  color: #8893a7;
  line-height: 1.2;
}

.detail-section {
  margin-bottom: 20px;
}

.detail-section:last-child {
  margin-bottom: 0;
}

.detail-grid {
  display: grid;
  gap: 0;
}

.detail-grid.cols-2 {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

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

.detail-value {
  color: #1e293b;
  font-size: 13px;
  font-weight: 500;
}

.detail-value.mono {
  font-family: "SF Mono", Monaco, "Cascadia Code", Consolas, monospace;
  font-size: 12px;
  word-break: break-all;
}

.detail-value .error-text {
  color: #dc2626;
}

.section-title {
  margin-bottom: 4px;
  font-weight: 600;
  font-size: 14px;
  color: #1e293b;
}

.item-list {
  display: grid;
  gap: 8px;
}

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

.inline-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.form-field {
  display: grid;
  gap: 6px;
  margin-bottom: 12px;
}

.textarea {
  width: 100%;
  min-height: 120px;
  padding: 10px 12px;
  border: 1px solid #d9e2f0;
  border-radius: 10px;
  resize: vertical;
}

.strong {
  font-weight: 600;
}

.success {
  background: #ecfdf3;
  color: #067647;
  border-color: #abefc6;
}

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
  border-top-color: #0d6bff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
