<template>
  <div class="m-order-detail">
    <div v-if="loading && !order" class="m-detail-loading">
      <div class="m-detail-spinner"></div>
      <span>订单加载中...</span>
    </div>

    <MobileUnavailableState
      v-else-if="loadError && !order"
      title="订单加载失败"
      :description="loadError"
      @retry="loadOrder"
    />

    <div v-else-if="!order" class="m-detail-empty">
      <div class="m-detail-empty-icon">
        <MIcon name="xCircle" :size="48" />
      </div>
      <div class="m-detail-empty-text">订单不存在或已被删除</div>
      <button class="m-detail-empty-btn" @click="emit('back')">返回订单列表</button>
    </div>

    <template v-else>
      <div v-if="notice" class="m-detail-notice" :class="noticeType">
        <MIcon :name="noticeType === 'success' ? 'checkCircle' : 'alertCircle'" :size="16" />
        <span>{{ notice }}</span>
        <button class="m-notice-close" @click="notice = ''">
          <MIcon name="x" :size="14" />
        </button>
      </div>

      <div class="m-detail-card m-status-card">
        <div class="m-status-top">
          <span :class="['m-status-pill', statusBadgeClass]">{{ orderStatusText }}</span>
          <span v-if="deliveryStatusText" :class="['m-status-pill', 'm-status-pill-soft', deliveryBadgeClass]">
            {{ deliveryStatusText }}
          </span>
        </div>
        <div class="m-status-row">
          <span class="m-status-label">订单号</span>
          <span class="m-status-value m-mono">{{ order.externalOrderId || '-' }}</span>
          <button class="m-copy-mini" aria-label="复制订单号" @click="copyOrderNo">
            <MIcon name="copy" :size="14" />
          </button>
        </div>
        <div class="m-status-row">
          <span class="m-status-label">创建时间</span>
          <span class="m-status-value">{{ createTimeText }}</span>
        </div>
        <div v-if="payTimeText" class="m-status-row">
          <span class="m-status-label">付款时间</span>
          <span class="m-status-value">{{ payTimeText }}</span>
        </div>
      </div>

      <div class="m-detail-card">
        <div class="m-card-title-row">
          <MIcon name="shoppingBag" :size="16" class="m-card-title-icon" />
          <h3 class="m-card-title">商品信息</h3>
        </div>
        <div v-if="itemList.length" class="m-goods-list">
          <div v-for="(item, idx) in itemList" :key="idx" class="m-goods-row">
            <div class="m-goods-thumb">
              <img
                v-if="itemImageUrl(item) && !failedImages.has(itemImageUrl(item))"
                :src="itemImageUrl(item)"
                class="m-goods-img"
                alt=""
                referrerpolicy="no-referrer"
                @error="onImageError($event, item)"
              />
              <div v-else class="m-goods-img m-goods-img-placeholder">
                <MIcon name="image" :size="22" />
              </div>
            </div>
            <div class="m-goods-meta">
              <div class="m-goods-title">{{ item.goodsTitle || item.title || '-' }}</div>
              <div class="m-goods-sub">
                <span v-if="item.externalGoodsId || item.itemId" class="m-goods-id">
                  ID：{{ item.externalGoodsId || item.itemId }}
                </span>
                <span v-if="itemSpec(item)" class="m-goods-spec">
                  <MIcon name="tag" :size="11" />
                  {{ itemSpec(item) }}
                </span>
              </div>
              <div class="m-goods-bottom">
                <span class="m-goods-price">¥{{ formatMoney(item.goodsPrice ?? item.price) }}</span>
                <span class="m-goods-qty">x{{ Math.max(Number(item.goodsCount) || 1, 1) }}</span>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="m-card-empty">暂无商品明细</div>
      </div>

      <div class="m-detail-card">
        <div class="m-card-title-row">
          <MIcon name="user" :size="16" class="m-card-title-icon" />
          <h3 class="m-card-title">买家信息</h3>
        </div>
        <div class="m-info-row">
          <span class="m-info-label">买家昵称</span>
          <span class="m-info-value">{{ order.buyerName || '-' }}</span>
        </div>
        <div class="m-info-row">
          <span class="m-info-label">买家ID</span>
          <span class="m-info-value m-mono">{{ order.buyerId || '-' }}</span>
        </div>
        <button class="m-contact-btn" @click="contactBuyer">
          <MIcon name="messageCircle" :size="16" />
          <span>联系买家</span>
        </button>
      </div>

      <div class="m-detail-card">
        <div class="m-card-title-row">
          <MIcon name="truck" :size="16" class="m-card-title-icon" />
          <h3 class="m-card-title">物流信息</h3>
        </div>
        <div class="m-info-row">
          <span class="m-info-label">发货方式</span>
          <span class="m-info-value">{{ deliveryMethodText }}</span>
        </div>
        <div class="m-info-row">
          <span class="m-info-label">发货状态</span>
          <span class="m-info-value">{{ deliveryStatusText || '-' }}</span>
        </div>
        <div class="m-info-row">
          <span class="m-info-label">发货进度</span>
          <span class="m-info-value">{{ deliveryProgressText || '-' }}</span>
        </div>
        <div v-if="shipTimeText" class="m-info-row">
          <span class="m-info-label">发货时间</span>
          <span class="m-info-value">{{ shipTimeText }}</span>
        </div>
        <div v-if="order.deliveryFailReason" class="m-info-row m-info-row-error">
          <span class="m-info-label">失败原因</span>
          <span class="m-info-value m-error-text">{{ order.deliveryFailReason }}</span>
        </div>
        <div v-if="order.deliveryContent" class="m-delivery-content">
          <div class="m-delivery-content-label">发货内容</div>
          <div class="m-delivery-content-box">{{ order.deliveryContent }}</div>
        </div>
      </div>

      <div class="m-detail-card">
        <div class="m-card-title-row">
          <MIcon name="fileText" :size="16" class="m-card-title-icon" />
          <h3 class="m-card-title">金额明细</h3>
        </div>
        <div class="m-info-row">
          <span class="m-info-label">商品金额</span>
          <span class="m-info-value">¥{{ formatMoney(order.itemAmount ?? order.goodsAmount) }}</span>
        </div>
        <div class="m-info-row">
          <span class="m-info-label">运费</span>
          <span class="m-info-value">¥{{ formatMoney(order.shippingFee ?? order.freight) }}</span>
        </div>
        <div class="m-info-row m-info-row-total">
          <span class="m-info-label">实付金额</span>
          <span class="m-info-value m-total-value">¥{{ formatMoney(order.totalAmount) }}</span>
        </div>
      </div>

      <div class="m-detail-card">
        <div class="m-card-title-row">
          <MIcon name="clock" :size="16" class="m-card-title-icon" />
          <h3 class="m-card-title">订单时间线</h3>
        </div>
        <div class="m-timeline">
          <div
            v-for="(step, idx) in timeline"
            :key="idx"
            class="m-timeline-item"
            :class="{ done: step.done, active: step.active }"
          >
            <div class="m-timeline-dot">
              <MIcon v-if="step.done" name="checkCircle" :size="16" />
              <span v-else class="m-timeline-dot-inner"></span>
            </div>
            <div class="m-timeline-content">
              <div class="m-timeline-title">{{ step.title }}</div>
              <div v-if="step.time" class="m-timeline-time">{{ step.time }}</div>
              <div v-else-if="step.hint" class="m-timeline-hint">{{ step.hint }}</div>
            </div>
          </div>
        </div>
      </div>

      <div class="m-detail-card">
        <div class="m-card-title-row">
          <MIcon name="edit" :size="16" class="m-card-title-icon" />
          <h3 class="m-card-title">订单备注</h3>
        </div>
        <div v-if="order.remark || order.sellerRemark" class="m-remark-text">{{ order.remark || order.sellerRemark }}</div>
        <div v-else class="m-card-empty">暂无备注</div>
        <button class="m-remark-btn" @click="openRemarkEditor">
          <MIcon name="edit" :size="14" />
          <span>{{ (order.remark || order.sellerRemark) ? '修改备注' : '添加备注' }}</span>
        </button>
      </div>

      <div class="m-detail-actions">
        <button class="m-action-btn" :disabled="syncing" @click="syncOrder">
          <MIcon name="refreshCw" :size="16" :class="{ 'm-spin': syncing }" />
          <span>{{ syncing ? '同步中...' : '同步订单' }}</span>
        </button>
        <button v-if="canDeliver" class="m-action-btn m-action-primary" @click="openShipForm">
          <MIcon name="send" :size="16" />
          <span>手动发货</span>
        </button>
        <button class="m-action-btn" @click="copyOrderNo">
          <MIcon name="copy" :size="16" />
          <span>复制订单号</span>
        </button>
      </div>

      <div class="m-safe-bottom"></div>
    </template>

    <MobileOrderShipForm
      :visible="shipFormVisible"
      :order="order"
      @close="closeShipForm"
      @success="handleShipSuccess"
    />

    <Teleport to="body">
      <Transition name="m-remark-fade">
        <div v-if="remarkFormVisible" class="m-remark-mask" @click.self="closeRemarkEditor">
          <Transition name="m-remark-slide">
            <div v-if="remarkFormVisible" class="m-remark-sheet" role="dialog" aria-modal="true">
              <div class="m-remark-handle"></div>
              <div class="m-remark-header">
                <h3>{{ (order && (order.remark || order.sellerRemark)) ? '修改备注' : '添加备注' }}</h3>
                <button type="button" class="m-remark-close" :disabled="remarkSubmitting" @click="closeRemarkEditor">
                  <MIcon name="x" :size="20" />
                </button>
              </div>
              <div class="m-remark-body">
                <div v-if="remarkError" class="m-remark-notice error">
                  <MIcon name="alertCircle" :size="14" />
                  <span>{{ remarkError }}</span>
                </div>
                <textarea
                  v-model.trim="remarkValue"
                  class="m-remark-textarea"
                  placeholder="请输入订单备注（仅自己可见）"
                  rows="5"
                  maxlength="500"
                  :disabled="remarkSubmitting"
                ></textarea>
                <div class="m-remark-tip">
                  <MIcon name="info" :size="12" />
                  <span>备注将保存到订单 sellerRemark 字段，仅卖家可见</span>
                </div>
              </div>
              <div class="m-remark-footer">
                <button type="button" class="m-remark-btn-cancel" :disabled="remarkSubmitting" @click="closeRemarkEditor">
                  取消
                </button>
                <button
                  type="button"
                  class="m-remark-btn-submit"
                  :disabled="remarkSubmitting"
                  @click="submitRemark"
                >
                  <span v-if="remarkSubmitting" class="m-remark-spinner"></span>
                  <span>{{ remarkSubmitting ? '保存中...' : '保存' }}</span>
                </button>
              </div>
            </div>
          </Transition>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import MIcon from './MIcon.vue'
import MobileUnavailableState from './MobileUnavailableState.vue'
import MobileOrderShipForm from './components/MobileOrderShipForm.vue'
import { getOrderDetail, updateOrder, syncOrder as apiSyncOrder } from '../api/orders.js'

const props = defineProps({
  orderId: [String, Number]
})
const emit = defineEmits(['navigate', 'force-desktop', 'back'])

const order = ref(null)
const loading = ref(false)
const loadError = ref('')
const syncing = ref(false)
const notice = ref('')
const noticeType = ref('success')
const failedImages = reactive(new Set())

const shipFormVisible = ref(false)
const remarkFormVisible = ref(false)
const remarkValue = ref('')
const remarkSubmitting = ref(false)
const remarkError = ref('')

const ORDER_STATUS_TEXT = {
  0: '待付款',
  1: '已付款',
  2: '待发货',
  3: '已发货',
  4: '已完成',
  5: '已关闭'
}

const DELIVERY_METHOD_TEXT = {
  manual_text: '手动文本发货',
  manual_card: '手动卡密发货',
  auto_text: '自动文本发货',
  auto_card: '自动卡密发货'
}

const orderStatusText = computed(() => {
  if (!order.value) return '-'
  if (order.value.orderStatusText) return order.value.orderStatusText
  return ORDER_STATUS_TEXT[Number(order.value.orderStatus)] || '未知状态'
})

const statusBadgeClass = computed(() => {
  const s = Number(order.value?.orderStatus)
  if (s === 4) return 'completed'
  if (s === 3) return 'shipped'
  if (s === 1) return 'paid'
  if (s === 0 || s === 2) return 'orange'
  if (s === 5) return 'red'
  return 'gray'
})

const deliveryBadgeClass = computed(() => {
  const ds = String(order.value?.deliveryStatus || '').toLowerCase()
  if (ds === 'success' || ds === 'done') return 'completed'
  if (ds === 'running') return 'shipped'
  if (ds === 'failed') return 'red'
  if (ds === 'pending' || ds === 'partial') return 'orange'
  return 'gray'
})

const deliveryMethodText = computed(() => {
  if (!order.value) return '-'
  const m = order.value.deliveryMethod
  return DELIVERY_METHOD_TEXT[m] || m || '-'
})

const DELIVERY_STATUS_TEXT = {
  pending: '待发货',
  running: '发货中',
  partial: '部分发货',
  success: '已发货',
  failed: '发货失败',
  done: '已完成'
}

function formatDateTime(dt) {
  if (!dt) return ''
  const d = new Date(dt)
  if (isNaN(d.getTime())) return ''
  const now = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  const time = `${pad(d.getHours())}:${pad(d.getMinutes())}`
  if (d.toDateString() === now.toDateString()) return `今天 ${time}`
  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  if (d.toDateString() === yesterday.toDateString()) return `昨天 ${time}`
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${time}`
}

const createTimeText = computed(() => {
  if (!order.value) return '-'
  if (order.value.createTimeText) return order.value.createTimeText
  return formatDateTime(order.value.createTime || order.value.createdTime) || '-'
})

const payTimeText = computed(() => {
  if (!order.value) return ''
  if (order.value.payTimeText) return order.value.payTimeText
  return formatDateTime(order.value.payTime)
})

const shipTimeText = computed(() => {
  if (!order.value) return ''
  if (order.value.shipTimeText) return order.value.shipTimeText
  return formatDateTime(order.value.shipTime)
})

const deliveryStatusText = computed(() => {
  if (!order.value) return ''
  if (order.value.deliveryStatusText) return order.value.deliveryStatusText
  const ds = String(order.value.deliveryStatus || '').toLowerCase()
  return DELIVERY_STATUS_TEXT[ds] || ds || ''
})

const deliveryProgressText = computed(() => {
  if (!order.value) return ''
  if (order.value.deliveryProgressText) return order.value.deliveryProgressText
  const sent = Number(order.value.quantitySent || 0)
  const total = Number(order.value.quantityRequested || order.value.quantityTotal || 1) || 1
  return `${sent}/${total}`
})

const itemList = computed(() => {
  if (!order.value) return []
  const items = order.value.orderItems || order.value.goodsItems || order.value.items || []
  return Array.isArray(items) ? items : []
})

const canDeliver = computed(() => {
  return Number(order.value?.orderStatus) === 2
})

const timeline = computed(() => {
  if (!order.value) return []
  const o = order.value
  const status = Number(o.orderStatus)
  const createT = formatDateTime(o.createTime || o.createdTime)
  const payT = formatDateTime(o.payTime)
  const shipT = formatDateTime(o.shipTime)
  const steps = [
    {
      title: '创建订单',
      time: createT,
      done: !!createT,
      active: !createT
    },
    {
      title: '买家付款',
      time: payT,
      done: !!payT,
      active: !!createT && !payT
    },
    {
      title: '卖家发货',
      time: shipT,
      done: !!shipT,
      active: !!payT && !shipT
    },
    {
      title: '确认收货',
      time: '',
      hint: status >= 4 ? '已确认收货' : '待买家确认收货',
      done: status >= 4,
      active: status === 3
    },
    {
      title: '买家评价',
      time: '',
      hint: o.isRated ? '已评价' : '待买家评价',
      done: !!o.isRated && status >= 4,
      active: status === 4 && !o.isRated
    }
  ]
  return steps
})

function formatMoney(n) {
  const num = Number(n)
  if (!Number.isFinite(num)) return '0.00'
  return num.toFixed(2)
}

function itemImageUrl(item) {
  return item?.imageUrl
    || item?.goodsImage
    || item?.picUrl
    || item?.coverImage
    || item?.thumbUrl
    || item?.itemPic
    || (Array.isArray(item?.images) && item.images[0])
    || ''
}

function itemSpec(item) {
  if (item?.specSummary) return item.specSummary
  const parts = [item?.specName, item?.specValue].filter(Boolean)
  if (parts.length === 2) return `${parts[0]}: ${parts[1]}`
  return parts[0] || ''
}

function onImageError(e, item) {
  const url = itemImageUrl(item)
  if (url) failedImages.add(url)
  if (e?.target) e.target.style.display = 'none'
}

function showNotice(message, type = 'success') {
  notice.value = message
  noticeType.value = type
  if (noticeTimer) clearTimeout(noticeTimer)
  noticeTimer = setTimeout(() => {
    notice.value = ''
  }, 2800)
}

let noticeTimer = null

async function loadOrder() {
  const id = props.orderId
  if (!id) {
    loadError.value = '订单 ID 缺失'
    return
  }
  loading.value = true
  loadError.value = ''
  try {
    const res = await getOrderDetail(id)
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new Error('订单详情响应格式异常')
    }
    order.value = data
  } catch (e) {
    loadError.value = e?.message || '加载订单详情失败'
  } finally {
    loading.value = false
  }
}

async function syncOrder() {
  if (!order.value?.id || syncing.value) return
  syncing.value = true
  try {
    const res = await apiSyncOrder(order.value.id)
    const data = res?.data
    if (data && typeof data === 'object' && !Array.isArray(data) && typeof data.ok === 'boolean') {
      if (data.ok) {
        showNotice(data.message || '订单同步已完成', 'success')
      } else {
        showNotice(data.message || '订单同步失败', 'error')
      }
    } else {
      showNotice('订单同步已完成', 'success')
    }
    await loadOrder()
  } catch (e) {
    showNotice(e?.message || '订单同步失败', 'error')
  } finally {
    syncing.value = false
  }
}

function copyOrderNo() {
  const text = order.value?.externalOrderId
  if (!text) {
    showNotice('订单号为空，无法复制', 'error')
    return
  }
  if (navigator?.clipboard?.writeText) {
    navigator.clipboard.writeText(String(text))
      .then(() => showNotice('订单号已复制', 'success'))
      .catch(() => fallbackCopy(String(text)))
  } else {
    fallbackCopy(String(text))
  }
}

function fallbackCopy(text) {
  try {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    showNotice('订单号已复制', 'success')
  } catch {
    showNotice('复制失败，请手动选择订单号复制', 'error')
  }
}

function contactBuyer() {
  const buyerId = order.value?.buyerId
  if (buyerId) {
    emit('navigate', 'messages', { buyerId })
  } else {
    emit('navigate', 'messages')
  }
}

function openShipForm() {
  if (!order.value) return
  shipFormVisible.value = true
}

function closeShipForm() {
  shipFormVisible.value = false
}

async function handleShipSuccess() {
  closeShipForm()
  showNotice('发货任务已提交', 'success')
  await loadOrder()
}

function openRemarkEditor() {
  if (!order.value) return
  remarkValue.value = order.value.sellerRemark || order.value.remark || ''
  remarkError.value = ''
  remarkFormVisible.value = true
}

function closeRemarkEditor() {
  if (remarkSubmitting.value) return
  remarkFormVisible.value = false
  remarkError.value = ''
}

async function submitRemark() {
  if (!order.value?.id) {
    remarkError.value = '订单信息缺失，无法保存备注'
    return
  }
  remarkSubmitting.value = true
  remarkError.value = ''
  try {
    await updateOrder(order.value.id, {
      sellerRemark: remarkValue.value || '',
      remark: remarkValue.value || ''
    })
    order.value = {
      ...order.value,
      sellerRemark: remarkValue.value,
      remark: remarkValue.value
    }
    remarkFormVisible.value = false
    showNotice('备注已保存', 'success')
  } catch (e) {
    remarkError.value = e?.message || '保存备注失败，请稍后重试'
  } finally {
    remarkSubmitting.value = false
  }
}

watch(() => props.orderId, (newId, oldId) => {
  if (newId && String(newId) !== String(oldId ?? '')) {
    order.value = null
    loadOrder()
  }
})

onMounted(() => {
  loadOrder()
})
</script>

<style scoped>
.m-order-detail {
  padding: var(--m-space-3) var(--m-space-4) 0;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
}

/* === 加载 / 空状态 === */
.m-detail-loading {
  padding: var(--m-space-8) 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--m-space-3);
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-body-sm);
}
.m-detail-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--m-color-border-light);
  border-top-color: var(--m-color-primary);
  border-radius: var(--m-radius-circle);
  animation: m-spin 0.7s linear infinite;
}
@keyframes m-spin {
  to { transform: rotate(360deg); }
}

.m-detail-empty {
  padding: var(--m-space-8) var(--m-space-4);
  text-align: center;
  color: var(--m-color-text-tertiary);
}
.m-detail-empty-icon {
  width: 80px;
  height: 80px;
  border-radius: var(--m-radius-circle);
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto var(--m-space-3);
  opacity: 0.85;
}
.m-detail-empty-text {
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-secondary);
  margin-bottom: var(--m-space-3);
}
.m-detail-empty-btn {
  display: inline-flex;
  align-items: center;
  height: 40px;
  padding: 0 var(--m-space-5);
  border: none;
  border-radius: var(--m-radius-pill);
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
}

/* === 通知条 === */
.m-detail-notice {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  padding: var(--m-space-2) var(--m-space-3);
  border-radius: var(--m-radius-lg);
  margin-bottom: var(--m-space-3);
  font-size: var(--m-font-size-body-sm);
  line-height: var(--m-line-height-base);
}
.m-detail-notice.success {
  background: var(--m-color-success-bg);
  color: var(--m-color-success-text);
  border: 1px solid var(--m-color-success-border);
}
.m-detail-notice.error {
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger-text);
  border: 1px solid var(--m-color-danger-border);
}
.m-notice-close {
  margin-left: auto;
  border: none;
  background: transparent;
  color: inherit;
  cursor: pointer;
  padding: var(--m-space-1);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.7;
}
.m-notice-close:active { opacity: 1; }

/* === 详情卡片 === */
.m-detail-card {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-4);
  margin-bottom: var(--m-space-3);
  box-shadow: var(--m-shadow-card);
  border: 1px solid var(--m-color-border-light);
}
.m-status-card {
  background: var(--m-color-bg-card);
  border-color: var(--m-color-info-border);
}

.m-card-title-row {
  display: flex;
  align-items: center;
  gap: var(--m-space-1);
  margin-bottom: var(--m-space-3);
}
.m-card-title-icon {
  color: var(--m-color-primary);
  flex-shrink: 0;
}
.m-card-title {
  margin: 0;
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
}
.m-card-empty {
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-tertiary);
  padding: var(--m-space-1) 0;
}

/* === 状态徽章 === */
.m-status-top {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-3);
  flex-wrap: wrap;
}
.m-status-pill {
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-semibold);
  padding: var(--m-space-1) var(--m-space-3);
  border-radius: var(--m-radius-pill);
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
}
.m-status-pill.completed { background: var(--m-color-success-bg); color: var(--m-color-success-text); }
.m-status-pill.shipped { background: var(--m-color-cyan-bg); color: var(--m-color-cyan); }
.m-status-pill.paid { background: var(--m-color-info-bg); color: var(--m-color-info-text); }
.m-status-pill.orange { background: var(--m-color-warning-bg); color: var(--m-color-warning-text); }
.m-status-pill.red { background: var(--m-color-danger-bg); color: var(--m-color-danger-text); }
.m-status-pill.gray { background: var(--m-color-bg-subtle); color: var(--m-color-text-secondary); }
.m-status-pill-soft {
  background: var(--m-color-bg-card);
  color: var(--m-color-text-secondary);
}

/* === 状态行（左标签右值） === */
.m-status-row {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  padding: var(--m-space-1) 0;
  font-size: var(--m-font-size-body-sm);
}
.m-status-label {
  color: var(--m-color-text-tertiary);
  flex-shrink: 0;
  min-width: 70px;
}
.m-status-value {
  color: var(--m-color-text-primary);
  font-weight: var(--m-font-weight-medium);
  word-break: break-all;
  flex: 1;
  min-width: 0;
}
.m-mono {
  font-family: var(--m-font-family-mono);
  font-size: var(--m-font-size-caption);
}
.m-copy-mini {
  width: 26px;
  height: 26px;
  border: none;
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
  border-radius: var(--m-radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  padding: 0;
}
.m-copy-mini:active {
  background: var(--m-color-bg-hover);
}

/* === 商品列表 === */
.m-goods-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-3);
}
.m-goods-row {
  display: flex;
  gap: var(--m-space-3);
}
.m-goods-thumb {
  width: 72px;
  height: 72px;
  border-radius: var(--m-radius-lg);
  overflow: hidden;
  flex-shrink: 0;
  background: var(--m-color-bg-subtle);
}
.m-goods-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.m-goods-img-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--m-color-text-disabled);
  background: var(--m-color-bg-subtle);
}
.m-goods-meta {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--m-space-1);
}
.m-goods-title {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  line-height: var(--m-line-height-tight);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.m-goods-sub {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
  flex-wrap: wrap;
}
.m-goods-spec {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  background: var(--m-color-bg-subtle);
  padding: 2px var(--m-space-1);
  border-radius: var(--m-radius-sm);
}
.m-goods-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 2px;
}
.m-goods-price {
  color: var(--m-color-danger-text);
  font-weight: var(--m-font-weight-bold);
  font-size: var(--m-font-size-body);
}
.m-goods-qty {
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-caption);
}

/* === 信息行（左标签右值） === */
.m-info-row {
  display: flex;
  align-items: flex-start;
  gap: var(--m-space-3);
  padding: 7px 0;
  font-size: var(--m-font-size-body-sm);
  border-bottom: 1px solid var(--m-color-border-light);
}
.m-info-row:last-child {
  border-bottom: none;
}
.m-info-label {
  color: var(--m-color-text-tertiary);
  flex-shrink: 0;
  min-width: 80px;
}
.m-info-value {
  color: var(--m-color-text-primary);
  font-weight: var(--m-font-weight-medium);
  word-break: break-all;
  flex: 1;
  min-width: 0;
}
.m-info-row-error .m-info-value {
  color: var(--m-color-danger-text);
}
.m-error-text {
  color: var(--m-color-danger-text) !important;
}
.m-info-row-total {
  padding-top: var(--m-space-3);
  margin-top: var(--m-space-1);
  border-top: 1px solid var(--m-color-border-light);
  border-bottom: none;
  align-items: center;
}
.m-total-value {
  color: var(--m-color-danger-text) !important;
  font-weight: var(--m-font-weight-extrabold);
  font-size: var(--m-font-size-h3);
}

/* === 发货内容展示 === */
.m-delivery-content {
  margin-top: var(--m-space-2);
}
.m-delivery-content-label {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  margin-bottom: var(--m-space-1);
}
.m-delivery-content-box {
  background: var(--m-color-bg-subtle);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-md);
  padding: var(--m-space-2) var(--m-space-3);
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  line-height: var(--m-line-height-base);
}

.m-contact-btn {
  margin-top: var(--m-space-3);
  width: 100%;
  height: 40px;
  border: 1px solid var(--m-color-info-border);
  background: var(--m-color-info-bg);
  color: var(--m-color-primary);
  border-radius: var(--m-radius-md);
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-1);
}
.m-contact-btn:active {
  background: var(--m-color-primary-bg-hover);
}

.m-remark-text {
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-primary);
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-md);
  padding: var(--m-space-2) var(--m-space-3);
  line-height: var(--m-line-height-base);
  white-space: pre-wrap;
  word-break: break-word;
}
.m-remark-btn {
  margin-top: var(--m-space-2);
  height: 32px;
  padding: 0 var(--m-space-3);
  border: 1px solid var(--m-color-border);
  background: var(--m-color-bg-card);
  color: var(--m-color-text-secondary);
  border-radius: var(--m-radius-md);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-1);
}
.m-remark-btn:active {
  background: var(--m-color-bg-hover);
}

/* === 时间线 === */
.m-timeline {
  position: relative;
  padding-left: var(--m-space-1);
}
.m-timeline-item {
  position: relative;
  display: flex;
  gap: var(--m-space-3);
  padding-bottom: var(--m-space-4);
}
.m-timeline-item:last-child {
  padding-bottom: 0;
}
.m-timeline-item:not(:last-child)::before {
  content: '';
  position: absolute;
  left: 7px;
  top: 18px;
  bottom: 0;
  width: 2px;
  background: var(--m-color-border);
}
.m-timeline-item.done:not(:last-child)::before {
  background: var(--m-color-success);
}
.m-timeline-dot {
  width: 16px;
  height: 16px;
  border-radius: var(--m-radius-circle);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--m-color-bg-card);
  color: var(--m-color-success);
  position: relative;
  z-index: 1;
}
.m-timeline-dot-inner {
  width: 10px;
  height: 10px;
  border-radius: var(--m-radius-circle);
  border: 2px solid var(--m-color-text-disabled);
  background: var(--m-color-bg-card);
}
.m-timeline-item.active .m-timeline-dot-inner {
  border-color: var(--m-color-primary);
  background: var(--m-color-primary);
  box-shadow: 0 0 0 4px var(--m-color-primary-bg);
}
.m-timeline-content {
  flex: 1;
  min-width: 0;
  padding-top: 0;
}
.m-timeline-title {
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  margin-bottom: 2px;
}
.m-timeline-item.active .m-timeline-title {
  color: var(--m-color-primary);
}
.m-timeline-time {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}
.m-timeline-hint {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}

/* === 底部操作按钮区（非固定） === */
.m-detail-actions {
  display: flex;
  gap: var(--m-space-2);
  margin: var(--m-space-1) 0 var(--m-space-4);
  flex-wrap: wrap;
}
.m-action-btn {
  flex: 1;
  min-width: 100px;
  height: 44px;
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-md);
  background: var(--m-color-bg-card);
  color: var(--m-color-text-secondary);
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-1);
  transition: all 0.15s;
  padding: 0 var(--m-space-2);
}
.m-action-btn:active:not(:disabled) {
  transform: scale(0.97);
}
.m-action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.m-action-primary {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  border: none;
}

.m-spin {
  animation: m-spin 0.7s linear infinite;
}

.m-safe-bottom {
  height: var(--m-space-5);
}

/* === 备注编辑 Sheet === */
.m-remark-mask {
  position: fixed;
  inset: 0;
  background: var(--m-mask-modal);
  z-index: 1100;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.m-remark-fade-enter-active,
.m-remark-fade-leave-active {
  transition: opacity 0.2s ease;
}
.m-remark-fade-enter-from,
.m-remark-fade-leave-to {
  opacity: 0;
}

.m-remark-sheet {
  width: 100%;
  max-width: 500px;
  background: var(--m-color-bg-page);
  border-radius: var(--m-radius-2xl) var(--m-radius-2xl) 0 0;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}
.m-remark-slide-enter-active,
.m-remark-slide-leave-active {
  transition: transform 0.3s ease;
}
.m-remark-slide-enter-from,
.m-remark-slide-leave-to {
  transform: translateY(100%);
}

.m-remark-handle {
  width: 40px;
  height: 4px;
  background: var(--m-color-border);
  border-radius: var(--m-radius-pill);
  margin: var(--m-space-2) auto 0;
}
.m-remark-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-space-3) var(--m-space-5) var(--m-space-1);
}
.m-remark-header h3 {
  margin: 0;
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
}
.m-remark-close {
  width: 30px;
  height: 30px;
  border-radius: var(--m-radius-circle);
  border: none;
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
}
.m-remark-close:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.m-remark-body {
  padding: var(--m-space-2) var(--m-space-4) var(--m-space-3);
}
.m-remark-notice {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  padding: var(--m-space-2) var(--m-space-3);
  border-radius: var(--m-radius-md);
  font-size: var(--m-font-size-caption);
  margin-bottom: var(--m-space-3);
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger-text);
  border: 1px solid var(--m-color-danger-border);
}
.m-remark-textarea {
  width: 100%;
  min-height: 120px;
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3);
  font-size: var(--m-font-size-body);
  color: var(--m-color-text-primary);
  background: var(--m-color-bg-card);
  outline: none;
  resize: vertical;
  box-sizing: border-box;
  font-family: inherit;
  line-height: var(--m-line-height-base);
}
.m-remark-textarea::placeholder {
  color: var(--m-color-text-placeholder);
}
.m-remark-textarea:focus {
  border-color: var(--m-color-primary);
  box-shadow: 0 0 0 3px var(--m-color-primary-bg);
}
.m-remark-textarea:disabled {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-tertiary);
}
.m-remark-tip {
  display: flex;
  align-items: flex-start;
  gap: var(--m-space-1);
  margin: var(--m-space-2) var(--m-space-1) 0;
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
  line-height: var(--m-line-height-base);
}

.m-remark-footer {
  padding: var(--m-space-3) var(--m-space-4) var(--m-space-6);
  display: flex;
  gap: var(--m-space-3);
}
.m-remark-btn-cancel,
.m-remark-btn-submit {
  flex: 1;
  height: 44px;
  border: none;
  border-radius: var(--m-radius-md);
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-1);
  padding: 0;
}
.m-remark-btn-cancel {
  background: var(--m-color-bg-card);
  color: var(--m-color-text-secondary);
  border: 1px solid var(--m-color-border);
}
.m-remark-btn-submit {
  flex: 2;
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
}
.m-remark-btn-submit:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.m-remark-btn-cancel:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.m-remark-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: var(--m-color-text-inverse);
  border-radius: var(--m-radius-circle);
  animation: m-spin 0.7s linear infinite;
  display: inline-block;
}

@media (max-width: 380px) {
  .m-order-detail {
    padding: var(--m-space-2) var(--m-space-3) 0;
  }
  .m-action-btn {
    min-width: 0;
    flex-basis: 100%;
  }
}
</style>
