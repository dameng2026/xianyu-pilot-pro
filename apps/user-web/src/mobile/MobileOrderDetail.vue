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
          <span v-if="order.deliveryStatusText" :class="['m-status-pill', 'm-status-pill-soft', deliveryBadgeClass]">
            {{ order.deliveryStatusText }}
          </span>
        </div>
        <div class="m-status-row">
          <span class="m-status-label">订单号</span>
          <span class="m-status-value m-mono">{{ order.externalOrderId || '-' }}</span>
          <button class="m-copy-mini" @click="copyOrderNo" aria-label="复制订单号">
            <MIcon name="copy" :size="14" />
          </button>
        </div>
        <div class="m-status-row">
          <span class="m-status-label">创建时间</span>
          <span class="m-status-value">{{ order.createTimeText || '-' }}</span>
        </div>
        <div v-if="order.payTimeText" class="m-status-row">
          <span class="m-status-label">付款时间</span>
          <span class="m-status-value">{{ order.payTimeText }}</span>
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
          <span class="m-info-value">{{ order.deliveryStatusText || '-' }}</span>
        </div>
        <div class="m-info-row">
          <span class="m-info-label">发货进度</span>
          <span class="m-info-value">{{ order.deliveryProgressText || '-' }}</span>
        </div>
        <div v-if="order.shipTimeText" class="m-info-row">
          <span class="m-info-label">发货时间</span>
          <span class="m-info-value">{{ order.shipTimeText }}</span>
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
  const steps = [
    {
      title: '创建订单',
      time: o.createTimeText || '',
      done: !!o.createTimeText,
      active: !o.createTimeText
    },
    {
      title: '买家付款',
      time: o.payTimeText || '',
      done: !!o.payTimeText,
      active: !!o.createTimeText && !o.payTimeText
    },
    {
      title: '卖家发货',
      time: o.shipTimeText || '',
      done: !!o.shipTimeText,
      active: !!o.payTimeText && !o.shipTimeText
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
  padding: 12px 16px 0;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
}

.m-detail-loading {
  padding: 64px 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: #8c98ae;
  font-size: 13px;
}
.m-detail-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #e3e9f4;
  border-top-color: #0d6bff;
  border-radius: 50%;
  animation: m-spin 0.7s linear infinite;
}
@keyframes m-spin {
  to { transform: rotate(360deg); }
}

.m-detail-empty {
  padding: 64px 16px;
  text-align: center;
  color: #8c98ae;
}
.m-detail-empty-icon {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: linear-gradient(135deg, #ffe8e8, #ffd1d1);
  color: #ef4444;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 14px;
  opacity: 0.85;
}
.m-detail-empty-text {
  font-size: 15px;
  font-weight: 600;
  color: #5a6a85;
  margin-bottom: 14px;
}
.m-detail-empty-btn {
  display: inline-flex;
  align-items: center;
  height: 40px;
  padding: 0 22px;
  border: none;
  border-radius: 20px;
  background: linear-gradient(135deg, #0d6bff, #3b82f6);
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(13, 107, 255, 0.25);
}

.m-detail-notice {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 12px;
  margin-bottom: 12px;
  font-size: 13px;
  line-height: 1.5;
}
.m-detail-notice.success {
  background: #ecfdf3;
  color: #059669;
  border: 1px solid #bbf7d0;
}
.m-detail-notice.error {
  background: #fef2f2;
  color: #dc2626;
  border: 1px solid #fecaca;
}
.m-notice-close {
  margin-left: auto;
  border: none;
  background: transparent;
  color: inherit;
  cursor: pointer;
  padding: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.7;
}
.m-notice-close:active { opacity: 1; }

.m-detail-card {
  background: white;
  border-radius: 16px;
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: 0 2px 8px rgba(31, 53, 94, 0.04);
  border: 1px solid #f0f4fa;
}
.m-status-card {
  background: linear-gradient(135deg, #ffffff 0%, #f5f9ff 100%);
}

.m-card-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
}
.m-card-title-icon {
  color: #0d6bff;
  flex-shrink: 0;
}
.m-card-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: #15213d;
}
.m-card-empty {
  font-size: 13px;
  color: #9aa6bd;
  padding: 4px 0;
}

.m-status-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.m-status-pill {
  font-size: 12px;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 100px;
  background: #f1f5fb;
  color: #5a6a85;
}
.m-status-pill.completed { background: #e2f8ee; color: #0ea366; }
.m-status-pill.shipped { background: #e0f7fb; color: #0891b2; }
.m-status-pill.paid { background: #e8f1ff; color: #0d6bff; }
.m-status-pill.orange { background: #fff4e0; color: #e08a00; }
.m-status-pill.red { background: #ffe8e8; color: #dc2626; }
.m-status-pill.gray { background: #f1f5fb; color: #72809a; }
.m-status-pill-soft {
  background: rgba(255, 255, 255, 0.7);
  color: #5a6a85;
}

.m-status-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  font-size: 13px;
}
.m-status-label {
  color: #8c98ae;
  flex-shrink: 0;
  min-width: 70px;
}
.m-status-value {
  color: #15213d;
  font-weight: 500;
  word-break: break-all;
  flex: 1;
  min-width: 0;
}
.m-mono {
  font-family: 'SF Mono', Monaco, Consolas, monospace;
  font-size: 12px;
}
.m-copy-mini {
  width: 26px;
  height: 26px;
  border: none;
  background: #f1f5fb;
  color: #5a6a85;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  padding: 0;
}
.m-copy-mini:active {
  background: #e1e8f3;
}

.m-goods-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.m-goods-row {
  display: flex;
  gap: 12px;
}
.m-goods-thumb {
  width: 72px;
  height: 72px;
  border-radius: 12px;
  overflow: hidden;
  flex-shrink: 0;
  background: #f5f7fb;
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
  color: #c5cfe0;
  background: #f5f7fb;
}
.m-goods-meta {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
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
}
.m-goods-sub {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: #9aa6bd;
  flex-wrap: wrap;
}
.m-goods-spec {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  background: #f5f7fb;
  padding: 2px 6px;
  border-radius: 6px;
}
.m-goods-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 2px;
}
.m-goods-price {
  color: #ef4444;
  font-weight: 700;
  font-size: 14px;
}
.m-goods-qty {
  color: #8c98ae;
  font-size: 12px;
}

.m-info-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 7px 0;
  font-size: 13px;
  border-bottom: 1px solid #f5f7fb;
}
.m-info-row:last-child {
  border-bottom: none;
}
.m-info-label {
  color: #8c98ae;
  flex-shrink: 0;
  min-width: 80px;
}
.m-info-value {
  color: #15213d;
  font-weight: 500;
  word-break: break-all;
  flex: 1;
  min-width: 0;
}
.m-info-row-error .m-info-value {
  color: #dc2626;
}
.m-error-text {
  color: #dc2626 !important;
}
.m-info-row-total {
  padding-top: 12px;
  margin-top: 4px;
  border-top: 1px solid #f0f4fa;
  border-bottom: none;
  align-items: center;
}
.m-total-value {
  color: #ef4444 !important;
  font-weight: 800;
  font-size: 16px;
}

.m-delivery-content {
  margin-top: 10px;
}
.m-delivery-content-label {
  font-size: 12px;
  color: #8c98ae;
  margin-bottom: 6px;
}
.m-delivery-content-box {
  background: #f8faff;
  border: 1px solid #eef2fa;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 13px;
  color: #15213d;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.5;
}

.m-contact-btn {
  margin-top: 12px;
  width: 100%;
  height: 40px;
  border: 1px solid #dbeafe;
  background: #f0f7ff;
  color: #0d6bff;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}
.m-contact-btn:active {
  background: #e1efff;
}

.m-remark-text {
  font-size: 13px;
  color: #15213d;
  background: #f8faff;
  border-radius: 10px;
  padding: 10px 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
.m-remark-btn {
  margin-top: 10px;
  height: 32px;
  padding: 0 14px;
  border: 1px solid #e5e9f2;
  background: white;
  color: #5a6a85;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.m-remark-btn:active {
  background: #f5f7fb;
}

.m-timeline {
  position: relative;
  padding-left: 4px;
}
.m-timeline-item {
  position: relative;
  display: flex;
  gap: 12px;
  padding-bottom: 18px;
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
  background: #e5e9f2;
}
.m-timeline-item.done:not(:last-child)::before {
  background: #16bf78;
}
.m-timeline-dot {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: white;
  color: #16bf78;
  position: relative;
  z-index: 1;
}
.m-timeline-dot-inner {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 2px solid #c5cfe0;
  background: white;
}
.m-timeline-item.active .m-timeline-dot-inner {
  border-color: #0d6bff;
  background: #0d6bff;
  box-shadow: 0 0 0 4px rgba(13, 107, 255, 0.12);
}
.m-timeline-content {
  flex: 1;
  min-width: 0;
  padding-top: 0;
}
.m-timeline-title {
  font-size: 13px;
  font-weight: 600;
  color: #15213d;
  margin-bottom: 2px;
}
.m-timeline-item.active .m-timeline-title {
  color: #0d6bff;
}
.m-timeline-time {
  font-size: 12px;
  color: #8c98ae;
}
.m-timeline-hint {
  font-size: 12px;
  color: #9aa6bd;
}

.m-detail-actions {
  display: flex;
  gap: 8px;
  margin: 4px 0 16px;
  flex-wrap: wrap;
}
.m-action-btn {
  flex: 1;
  min-width: 100px;
  height: 44px;
  border: 1px solid #e5e9f2;
  border-radius: 14px;
  background: white;
  color: #5a6a85;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: all 0.15s;
  padding: 0 10px;
}
.m-action-btn:active:not(:disabled) {
  transform: scale(0.97);
}
.m-action-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.m-action-primary {
  background: linear-gradient(135deg, #0d6bff, #3b82f6);
  color: white;
  border: none;
  box-shadow: 0 4px 12px rgba(13, 107, 255, 0.3);
}

.m-spin {
  animation: m-spin 0.7s linear infinite;
}

.m-safe-bottom {
  height: 20px;
}

.m-remark-mask {
  position: fixed;
  inset: 0;
  background: rgba(21, 33, 61, 0.5);
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
  background: #f8faff;
  border-radius: 24px 24px 0 0;
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
  background: #dde5f0;
  border-radius: 2px;
  margin: 10px auto 0;
}
.m-remark-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px 6px;
}
.m-remark-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #15213d;
}
.m-remark-close {
  width: 30px;
  height: 30px;
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
.m-remark-close:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.m-remark-body {
  padding: 8px 16px 12px;
}
.m-remark-notice {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 12px;
  margin-bottom: 12px;
  background: #fef2f2;
  color: #dc2626;
  border: 1px solid #fecaca;
}
.m-remark-textarea {
  width: 100%;
  min-height: 120px;
  border: 1px solid #e5e9f2;
  border-radius: 12px;
  padding: 12px;
  font-size: 14px;
  color: #15213d;
  background: white;
  outline: none;
  resize: vertical;
  box-sizing: border-box;
  font-family: inherit;
  line-height: 1.5;
}
.m-remark-textarea::placeholder {
  color: #aeb9ca;
}
.m-remark-textarea:focus {
  border-color: #93c5fd;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}
.m-remark-textarea:disabled {
  background: #f5f7fb;
  color: #9aa6bd;
}
.m-remark-tip {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin: 8px 4px 0;
  font-size: 11px;
  color: #9aa6bd;
  line-height: 1.5;
}

.m-remark-footer {
  padding: 12px 16px 24px;
  display: flex;
  gap: 10px;
}
.m-remark-btn-cancel,
.m-remark-btn-submit {
  flex: 1;
  height: 44px;
  border: none;
  border-radius: 14px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0;
}
.m-remark-btn-cancel {
  background: white;
  color: #5a6a85;
  border: 1px solid #e5e9f2;
}
.m-remark-btn-submit {
  flex: 2;
  background: linear-gradient(135deg, #0d6bff, #3b82f6);
  color: white;
  box-shadow: 0 4px 12px rgba(13, 107, 255, 0.3);
}
.m-remark-btn-submit:disabled {
  opacity: 0.6;
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
  border-top-color: #fff;
  border-radius: 50%;
  animation: m-spin 0.7s linear infinite;
  display: inline-block;
}

@media (max-width: 380px) {
  .m-order-detail {
    padding: 10px 12px 0;
  }
  .m-action-btn {
    min-width: 0;
    flex-basis: 100%;
  }
}
</style>
