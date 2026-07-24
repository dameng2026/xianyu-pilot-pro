<template>
  <div v-if="visible" class="pay-mask" @click.self="emitClose">
    <div class="pay-dialog">
      <div v-if="!currentOrder && orderType === 'token'" class="token-modal-card">
        <button type="button" class="pay-close token-close-btn" aria-label="关闭充值弹窗" @click="emitClose">×</button>

        <div class="token-modal-header">
          <div class="token-modal-hero">
            <img class="token-modal-hero-image" src="/xya/payment-modal/hero-shield.png" alt="" />
          </div>
          <div class="token-modal-title-wrap">
            <strong>{{ title }}</strong>
            <span>{{ subtitle }}</span>
          </div>
        </div>

        <div v-if="error" class="pay-error token-error">{{ error }}</div>
        <div v-if="capabilityError" class="pay-error token-error" role="alert">
          {{ capabilityError }}
          <button type="button" class="pay-refresh-link" @click="reloadCapabilities">重新加载</button>
        </div>

        <section class="token-modal-section">
          <label class="token-modal-label">支付方式</label>
          <div class="method-option-list">
            <button
              v-for="method in normalizedMethods"
              :key="method.channelType"
              type="button"
              :class="['method-option-card', { active: paymentMethod === method.channelType }]"
              @click="paymentMethod = method.channelType"
            >
              <div class="method-option-main">
                <span class="method-option-icon-wrap">
                  <img class="method-option-icon" :src="paymentMethodIcon(method)" alt="" />
                </span>
                <span class="method-option-copy">
                  <b>{{ paymentMethodLabel(method) }}</b>
                  <small>{{ paymentMethodDesc(method) }}</small>
                </span>
              </div>
              <span class="method-option-check" :class="{ active: paymentMethod === method.channelType }" aria-hidden="true">
                <img v-if="paymentMethod === method.channelType" src="/xya/payment-modal/check-blue.svg" alt="" />
              </span>
            </button>
          </div>
        </section>

        <section class="token-modal-section">
          <label class="token-modal-label">Token 充值套餐</label>
          <div class="token-plan-list">
            <button
              v-for="tokenPlan in decoratedTokenPlans"
              :key="tokenPlan.id"
              type="button"
              :class="['token-plan-card', { active: selectedTokenPlanId === tokenPlan.id }]"
              @click="selectedTokenPlanId = tokenPlan.id"
            >
              <div class="token-plan-main">
                <span class="token-plan-icon-wrap" :class="tokenPlan.iconTone">
                  <img class="token-plan-icon" :src="tokenPlan.iconSrc" alt="" />
                </span>
                <span class="token-plan-copy">
                  <b>{{ tokenPlan.titleText }}</b>
                  <small>{{ tokenPlan.descText }}</small>
                </span>
              </div>
              <div class="token-plan-price-side">
                <em>{{ tokenPlan.priceText }}</em>
                <span class="token-plan-radio" :class="{ active: selectedTokenPlanId === tokenPlan.id }" aria-hidden="true">
                  <img v-if="selectedTokenPlanId === tokenPlan.id" src="/xya/payment-modal/check-blue.svg" alt="" />
                </span>
              </div>
            </button>
          </div>
        </section>

        <div class="token-amount-bar">
          <div class="token-amount-main">
            <span class="token-amount-icon-wrap">
              <img class="token-amount-icon" src="/xya/payment-modal/amount-bill.svg" alt="" />
            </span>
            <span class="token-amount-label">应付金额</span>
          </div>
          <strong>{{ amountText }}</strong>
        </div>

        <button
          type="button"
          class="confirm-pay-btn"
          :disabled="submitting || !paymentMethod || !canCreate"
          @click="createOrder"
        >
          <img class="confirm-pay-icon" src="/xya/payment-modal/shield-mini.svg" alt="" />
          <span>{{ submitting ? '正在创建订单...' : '确认支付' }}</span>
        </button>

        <p class="token-modal-footnote">
          <span class="token-modal-footnote-lock">🔒</span>
          <span>支付状态以服务端订单为准，请在提交前核对套餐与金额</span>
        </p>
      </div>

      <template v-else>
        <div class="pay-head">
          <div>
            <strong>{{ title }}</strong>
            <span>{{ fallbackSubtitle }}</span>
          </div>
          <button type="button" class="pay-close" @click="emitClose">×</button>
        </div>

        <div v-if="!currentOrder" class="pay-body">
          <div v-if="error" class="pay-error">{{ error }}</div>
          <div v-if="capabilityError" class="pay-error" role="alert">
            {{ capabilityError }}
            <button type="button" class="pay-refresh-link" @click="reloadCapabilities">重新加载</button>
          </div>
          <div class="pay-section">
            <label class="pay-label">支付方式</label>
            <div class="pay-methods" :class="{ single: orderType === 'vip' }">
              <button
                v-for="method in normalizedMethods"
                :key="method.channelType"
                type="button"
                :class="['pay-method', { active: paymentMethod === method.channelType }]"
                @click="paymentMethod = method.channelType"
              >
                <b>{{ paymentMethodLabel(method) }}</b>
                <span>{{ paymentMethodDesc(method) }}<em v-if="Number(method.sandbox || 0) === 1">沙箱</em></span>
              </button>
            </div>
          </div>

          <div v-if="orderType === 'token'" class="pay-section">
            <label class="pay-label">Token 充值套餐</label>
            <div class="pay-plan-list">
              <button
                v-for="tokenPlan in tokenPlans"
                :key="tokenPlan.id"
                type="button"
                :class="['pay-plan', { active: selectedTokenPlanId === tokenPlan.id }]"
                @click="selectedTokenPlanId = tokenPlan.id"
              >
                <b>{{ tokenPlan.planName }}</b>
                <span>{{ tokenPlan.tokenAmount }} Token<span v-if="tokenPlan.bonusToken"> + 赠送 {{ tokenPlan.bonusToken }}</span></span>
                <em>{{ tokenPlanPrice(tokenPlan) }}</em>
              </button>
            </div>
          </div>

          <div class="pay-summary">
            <span>应付金额</span>
            <strong>{{ amountText }}</strong>
          </div>
          <button type="button" class="pay-primary" :disabled="submitting || !paymentMethod || !canCreate" @click="createOrder">
            {{ submitting ? '正在创建订单...' : '确认支付' }}
          </button>
        </div>

        <div v-else-if="paid" class="pay-body pay-success-body">
          <div class="pay-success-icon">✓</div>
          <h3>支付成功</h3>
          <p>{{ currentOrder.title }} 已完成支付，即将自动刷新...</p>
        </div>

        <div v-else class="pay-body pay-status-body">
          <div v-if="error" class="pay-error">{{ error }}</div>
          <div class="pay-steps">
            <div class="pay-step active">
              <span>1</span>
              <b>{{ currentOrder.qrImage ? '二维码已生成' : '二维码不可用' }}</b>
            </div>
            <i></i>
            <div class="pay-step current">
              <span>2</span>
              <b>扫码支付</b>
            </div>
            <i></i>
            <div class="pay-step">
              <span>3</span>
              <b>自动到账</b>
            </div>
          </div>

          <div class="pay-main-grid">
            <div class="pay-qr-card">
              <img v-if="currentOrder.qrImage" class="real-qr" :src="currentOrder.qrImage" alt="支付二维码" />
              <div v-else class="qr-unavailable" role="alert">
                <strong>支付二维码不可用</strong>
                <span>订单未返回可扫描的二维码图片，请勿把此区域当作支付码。</span>
              </div>
              <p class="pay-qr-caption">{{ sandboxPayEnabled ? '沙箱订单不会真实扣款，可点击下方按钮完成模拟支付' : currentOrder.qrImage ? payCaption : '请取消订单并联系管理员检查支付配置' }}</p>
            </div>

            <div class="pay-order-panel">
              <div class="pay-flow-box">
                <h4>充值流程</h4>
                <ol>
                  <li>{{ currentOrder.qrImage ? '系统已生成支付二维码' : '订单已创建，但二维码图片不可用' }}</li>
                  <li>{{ sandboxPayEnabled ? '沙箱环境点击模拟支付完成测试' : '使用微信/支付宝扫码完成支付' }}</li>
                  <li>支付成功后自动刷新 Token 余额</li>
                </ol>
              </div>

              <div class="pay-order-meta">
                <h4>订单信息</h4>
                <div class="pay-order-row">
                  <span>订单编号：</span>
                  <b>{{ currentOrder.orderNo }}</b>
                </div>
                <div class="pay-order-row">
                  <span>Token 数量：</span>
                  <b>{{ currentOrder.tokenAmount ?? selectedTokenPlan?.tokenAmount ?? '—' }}</b>
                </div>
                <div class="pay-order-row">
                  <span>支付金额：</span>
                  <b>{{ currentOrder.amount || amountText }}</b>
                </div>
                <div class="pay-order-row status-row">
                  <span>当前状态：</span>
                  <em :class="{ paid: currentOrder.status === 1 }">{{ currentOrder.statusText || '状态未返回' }}</em>
                  <button type="button" class="pay-refresh-link" :disabled="refreshing" @click="refreshOrder">
                    <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2a6 6 0 1 1-4.24 10.24.75.75 0 0 1 1.06-1.06A4.5 4.5 0 1 0 8 3.5h-.72l1.13 1.13a.75.75 0 0 1-1.06 1.06L5.48 3.77A.75.75 0 0 1 5.47 2.7L7.35.84a.75.75 0 1 1 1.06 1.06L7.06 3.25H8Z" /></svg>
                    {{ refreshing ? '刷新中' : '刷新支付状态' }}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div class="pay-note-box">
            <div class="pay-note-icon">i</div>
            <div>
              <h4>说明</h4>
              <p>{{ sandboxPayEnabled ? '当前是沙箱测试订单，不会发生真实扣款；请使用“沙箱模拟支付成功”验证权益发放和回调后的刷新体验。' : currentOrder.qrImage ? '使用所选支付渠道扫码完成支付；若二维码过期，请关闭后重新创建订单。' : '当前订单缺少可扫描二维码，不能继续扫码支付，请取消订单并联系管理员。' }}</p>
              <p>支付成功后会自动轮询，支付失败或网络异常时也可点击“我已完成支付”手动刷新。</p>
              <p v-if="pollCount > 8" class="pay-warning">已经等待一段时间仍未到账，请确认支付是否完成，或联系人工客服并提供订单编号。</p>
            </div>
          </div>

          <div class="pay-actions">
            <button type="button" class="pay-secondary" :disabled="closing" @click="cancelOrder">{{ closing ? '取消中...' : '取消订单' }}</button>
            <button v-if="sandboxPayEnabled" type="button" class="pay-secondary sandbox" :disabled="refreshing" @click="mockPay">沙箱模拟支付成功</button>
            <button type="button" class="pay-primary outline" :disabled="refreshing" @click="refreshOrder">{{ refreshing ? '刷新中...' : '我已完成支付' }}</button>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import {
  closePaymentOrder,
  createPaymentOrder,
  getPaymentMethods,
  getPaymentOrder,
  getTokenRechargePlans,
  mockPayOrder
} from '../api/payment.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  orderType: { type: String, default: 'vip' },
  plan: { type: Object, default: null },
  targetType: { type: String, default: 'user_account' },
  targetId: { type: [Number, String], default: null },
  previewMethods: { type: Array, default: null },
  previewTokenPlans: { type: Array, default: null }
})
const emit = defineEmits(['close', 'paid'])

const methods = ref([])
const tokenPlans = ref([])
const paymentMethod = ref('')
const selectedTokenPlanId = ref(null)
const currentOrder = ref(null)
const submitting = ref(false)
const paid = ref(false)
const refreshing = ref(false)
const closing = ref(false)
const error = ref('')
const methodsLoaded = ref(false)
const plansLoaded = ref(false)
const methodsError = ref('')
const plansError = ref('')
const pollCount = ref(0)
let timer = null
let successTimer = null

const normalizedMethods = computed(() => {
  if (props.orderType !== 'token') return methods.value
  return methods.value.filter(method => method.channelType === 'wechat').slice(0, 1)
})

const selectedTokenPlan = computed(() => tokenPlans.value.find(item => item.id === selectedTokenPlanId.value))
const selectedMethod = computed(() => normalizedMethods.value.find(item => item.channelType === paymentMethod.value))
const sandboxPayEnabled = computed(() => Number(selectedMethod.value?.sandbox || currentOrder.value?.sandbox || 0) === 1 || currentOrder.value?.providerType === 'mock')
const payCaption = computed(() => paymentMethod.value === 'alipay' ? '请使用支付宝扫描二维码支付' : '请使用微信扫描二维码支付')
const title = computed(() => props.orderType === 'token' ? '扫码充值 Token' : '开通会员')
const subtitle = computed(() => props.orderType === 'token' ? '为账户充值 token 余额' : '支付成功后自动刷新会员权益')
const fallbackSubtitle = computed(() => props.orderType === 'token' ? '充值后自动更新 Token 余额' : '支付成功后自动刷新会员权益')
const capabilityError = computed(() => {
  const errors = [methodsError.value]
  if (props.orderType === 'token') errors.push(plansError.value)
  return errors.filter(Boolean).join('；')
})
const canCreate = computed(() => {
  if (!methodsLoaded.value || methodsError.value || !selectedMethod.value) return false
  if (props.orderType === 'vip') return !!props.plan?.id
  return plansLoaded.value && !plansError.value && !!selectedTokenPlan.value
})
const amountText = computed(() => {
  if (props.orderType === 'vip') {
    if (props.plan?.price) return props.plan.price
    return props.plan?.priceYuan === null || props.plan?.priceYuan === undefined ? '价格未配置' : `¥${formatMoney(props.plan.priceYuan)}`
  }
  const plan = selectedTokenPlan.value
  return plan ? tokenPlanPrice(plan) : '价格未配置'
})

const decoratedTokenPlans = computed(() => {
  return tokenPlans.value.map((plan, index) => {
    const toneMap = [
      { iconSrc: '/xya/payment-modal/plan-blue.svg', iconTone: 'blue' },
      { iconSrc: '/xya/payment-modal/plan-purple.svg', iconTone: 'purple' },
      { iconSrc: '/xya/payment-modal/plan-orange.svg', iconTone: 'orange' }
    ]
    const tone = toneMap[index] || toneMap[toneMap.length - 1]
    const hasTokenAmount = plan.tokenAmount !== null && plan.tokenAmount !== undefined
    const totalToken = hasTokenAmount ? Number(plan.tokenAmount) + Number(plan.bonusToken || 0) : null
    const titleText = plan.planName || (totalToken === null ? 'Token 数量未配置' : `${totalToken} Token`)
    const descText = plan.planDesc || plan.remark || '套餐说明未配置'
    return {
      ...plan,
      titleText,
      descText,
      priceText: tokenPlanPrice(plan),
      iconSrc: tone.iconSrc,
      iconTone: tone.iconTone
    }
  })
})

watch(() => props.visible, async value => {
  if (value) {
    currentOrder.value = null
    paid.value = false
    error.value = ''
    methodsError.value = ''
    plansError.value = ''
    pollCount.value = 0
    await Promise.all([loadMethods(), loadTokenPlans()])
  } else {
    stopPolling()
    clearSuccessTimer()
  }
}, { immediate: true })

watch(normalizedMethods, methodsValue => {
  if (!methodsValue.length) return
  if (!methodsValue.some(method => method.channelType === paymentMethod.value)) {
    paymentMethod.value = methodsValue[0]?.channelType || ''
  }
}, { immediate: true })

async function loadMethods() {
  methodsLoaded.value = false
  methodsError.value = ''
  methods.value = []
  paymentMethod.value = ''
  if (Array.isArray(props.previewMethods) && props.previewMethods.length) {
    methods.value = props.previewMethods
    methodsLoaded.value = true
    paymentMethod.value = normalizedMethods.value[0]?.channelType || ''
    return
  }
  try {
    const loadedMethods = await getPaymentMethods()
    if (!Array.isArray(loadedMethods)) throw new Error('支付方式响应格式异常')
    methods.value = loadedMethods
    methodsLoaded.value = true
    if (!normalizedMethods.value.length) methodsError.value = props.orderType === 'token' ? '未配置可用的微信支付方式' : '未配置可用的支付方式'
    paymentMethod.value = normalizedMethods.value[0]?.channelType || ''
  } catch (loadError) {
    methodsLoaded.value = true
    methodsError.value = loadError?.message || '支付方式加载失败'
  }
}

async function loadTokenPlans() {
  plansLoaded.value = props.orderType !== 'token'
  plansError.value = ''
  tokenPlans.value = []
  selectedTokenPlanId.value = null
  if (props.orderType !== 'token') return
  if (Array.isArray(props.previewTokenPlans) && props.previewTokenPlans.length) {
    tokenPlans.value = props.previewTokenPlans
    plansLoaded.value = true
    selectedTokenPlanId.value = tokenPlans.value[0]?.id || null
    return
  }
  try {
    const loadedPlans = await getTokenRechargePlans()
    if (!Array.isArray(loadedPlans)) throw new Error('Token 充值套餐响应格式异常')
    tokenPlans.value = loadedPlans
    plansLoaded.value = true
    if (!tokenPlans.value.length) plansError.value = '未配置可用的 Token 充值套餐'
    selectedTokenPlanId.value = tokenPlans.value[0]?.id || null
  } catch (loadError) {
    plansLoaded.value = true
    plansError.value = loadError?.message || 'Token 充值套餐加载失败'
  }
}

async function reloadCapabilities() {
  error.value = ''
  await Promise.all([loadMethods(), loadTokenPlans()])
}

async function createOrder() {
  if (!canCreate.value) return
  submitting.value = true
  error.value = ''
  try {
    const payload = {
      orderType: props.orderType,
      paymentMethod: paymentMethod.value,
      targetType: props.targetType,
      targetId: props.targetId
    }
    if (props.orderType === 'vip') {
      payload.planId = props.plan.id
      payload.periodType = props.plan.periodType  // 传递用户选择的计费周期 month/quarter/year
    } else {
      payload.tokenPlanId = selectedTokenPlanId.value
    }
    currentOrder.value = validateOrderSnapshot(await createPaymentOrder(payload))
    if (!currentOrder.value.qrImage && !sandboxPayEnabled.value) {
      error.value = '订单已创建，但服务端未返回可扫描的支付二维码；请取消订单并联系管理员检查支付配置。'
    }
    startPolling()
  } catch (err) {
    error.value = err?.message || '订单创建失败，请稍后重试或联系人工客服'
  } finally {
    submitting.value = false
  }
}

async function refreshOrder() {
  if (!currentOrder.value?.orderNo || refreshing.value) return
  refreshing.value = true
  error.value = ''
  try {
    pollCount.value += 1
    const orderNo = currentOrder.value.orderNo
    currentOrder.value = validateOrderSnapshot(await getPaymentOrder(orderNo), orderNo)
    if (currentOrder.value?.status === 1) {
      stopPolling()
      paid.value = true
      clearSuccessTimer()
      successTimer = setTimeout(() => emit('paid', currentOrder.value), 1500)
    } else if ([2, 3, 'failed', 'closed', 'expired'].includes(currentOrder.value?.status)) {
      stopPolling()
      error.value = currentOrder.value?.statusText || '订单已关闭或支付失败，请重新创建订单'
    }
  } catch (err) {
    error.value = err?.message || '支付状态刷新失败，请稍后重试'
  } finally {
    refreshing.value = false
  }
}

function startPolling() {
  stopPolling()
  timer = setInterval(refreshOrder, 2500)
}

function stopPolling() {
  if (timer) clearInterval(timer)
  timer = null
}

function clearSuccessTimer() {
  if (successTimer) clearTimeout(successTimer)
  successTimer = null
}

async function cancelOrder() {
  if (!currentOrder.value?.orderNo) return emitClose()
  closing.value = true
  try {
    await closePaymentOrder(currentOrder.value.orderNo)
    emitClose()
  } catch (err) {
    error.value = err?.message || '订单取消失败，订单状态未确认；请刷新状态后重试'
  } finally {
    closing.value = false
  }
}

async function mockPay() {
  if (!currentOrder.value?.orderNo || refreshing.value) return
  refreshing.value = true
  error.value = ''
  try {
    const orderNo = currentOrder.value.orderNo
    currentOrder.value = validateOrderSnapshot(await mockPayOrder(orderNo), orderNo)
    if (currentOrder.value?.status === 1) {
      stopPolling()
      paid.value = true
      clearSuccessTimer()
      successTimer = setTimeout(() => emit('paid', currentOrder.value), 1000)
    } else {
      await refreshOrder()
    }
  } catch (err) {
    error.value = err?.message || '沙箱模拟支付失败，请检查后台是否启用沙箱支付配置'
  } finally {
    refreshing.value = false
  }
}

function emitClose() {
  stopPolling()
  clearSuccessTimer()
  emit('close')
}

function isReadableConfigName(name) {
  if (!name) return false
  const str = String(name).trim()
  if (!str || str.length > 40) return false
  // 仅允许字母/数字/空格及常见命名标点，拒绝加密串、乱码或含异常符号的值
  return /^[\p{L}\p{N}\s\u00B7\u30FB\-_/()().、+]+$/u.test(str)
}

function paymentMethodLabel(method) {
  if (isReadableConfigName(method?.configName)) return String(method.configName).trim()
  if (method?.channelType === 'wechat') return '微信支付'
  if (method?.channelType === 'alipay') return '支付宝'
  return '支付方式'
}

function validateOrderSnapshot(order, expectedOrderNo = '') {
  if (!order || typeof order !== 'object' || Array.isArray(order)) {
    throw new Error('支付订单响应格式异常')
  }
  const orderNo = String(order.orderNo || '').trim()
  if (!orderNo) throw new Error('支付订单响应缺少订单编号')
  if (expectedOrderNo && orderNo !== String(expectedOrderNo)) {
    throw new Error('支付订单响应与当前订单不一致')
  }
  const status = Number(order.status)
  if (!Number.isInteger(status) || status < 0 || status > 4) {
    throw new Error('支付订单响应缺少有效状态')
  }
  return { ...order, orderNo, status }
}

function paymentMethodDesc(method) {
  if (Number(method.sandbox || 0) === 1) return '沙箱环境支付测试'
  if (method.description) return method.description
  if (method.providerType === 'yipay') return '易支付通道'
  if (method.providerType === 'official') return '官方接口'
  return '由后台支付配置提供'
}

function paymentMethodIcon(method) {
  return method.channelType === 'wechat'
    ? '/xya/payment-modal/wechat-pay.svg'
    : '/xya/payment-modal/shield-mini.svg'
}

function tokenPlanPrice(plan) {
  return plan?.priceYuan === null || plan?.priceYuan === undefined || plan?.priceYuan === ''
    ? '价格未配置'
    : `¥${formatMoney(plan.priceYuan)}`
}

function formatMoney(value) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '—'
  return Number.isInteger(num) ? String(num) : num.toFixed(2).replace(/\.00$/, '')
}

onBeforeUnmount(() => {
  stopPolling()
  clearSuccessTimer()
})
</script>

<style scoped>
.pay-mask {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(16, 28, 52, 0.5);
  backdrop-filter: blur(10px);
  overflow-y: auto;
}

.pay-dialog {
  width: 100%;
  max-width: 544px;
  margin: auto;
}

.token-modal-card,
.pay-head + .pay-body,
.pay-head + .pay-body + .pay-body,
.pay-head + .pay-body + .pay-body + .pay-body {
  background: #fff;
}

.token-modal-card {
  position: relative;
  width: 100%;
  padding: 24px 24px 18px;
  border-radius: 22px;
  background:
    radial-gradient(circle at 16% 18%, rgba(39, 117, 255, 0.08), transparent 28%),
    radial-gradient(circle at 82% 8%, rgba(39, 117, 255, 0.06), transparent 20%),
    linear-gradient(180deg, #ffffff 0%, #fefefe 100%);
  box-shadow: 0 28px 80px rgba(16, 37, 78, 0.24);
  border: 1px solid rgba(234, 239, 248, 0.94);
}

.token-modal-card::-webkit-scrollbar {
  width: 0;
  height: 0;
}

.token-close-btn {
  top: 22px;
  right: 22px;
  width: 40px;
  height: 40px;
  border-radius: 14px;
  background: linear-gradient(180deg, #ffffff 0%, #f4f7fc 100%);
  box-shadow: 0 10px 22px rgba(41, 65, 104, 0.12);
  color: #263654;
  font-size: 26px;
}

.token-modal-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding-right: 54px;
}

.token-modal-hero {
  flex: 0 0 118px;
  height: 90px;
  display: flex;
  align-items: center;
}

.token-modal-hero-image {
  width: 118px;
  max-width: 100%;
  object-fit: contain;
}

.token-modal-title-wrap {
  display: grid;
  gap: 6px;
}

.token-modal-title-wrap strong {
  font-size: 22px;
  line-height: 1.2;
  font-weight: 800;
  color: #1b2743;
}

.token-modal-title-wrap span {
  font-size: 14px;
  line-height: 1.55;
  color: #738099;
}

.token-error {
  margin-top: 14px;
}

.token-modal-section {
  margin-top: 18px;
}

.token-modal-label {
  display: block;
  margin-bottom: 12px;
  font-size: 16px;
  font-weight: 800;
  color: #1d2740;
}

.method-option-list,
.token-plan-list {
  display: grid;
  gap: 14px;
}

.method-option-card,
.token-plan-card {
  width: 100%;
  border: 1.5px solid #e5ebf5;
  border-radius: 16px;
  background: linear-gradient(180deg, #ffffff 0%, #fefefe 100%);
  cursor: pointer;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}

.method-option-card:hover,
.token-plan-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 14px 28px rgba(40, 73, 128, 0.08);
}

.method-option-card.active,
.token-plan-card.active {
  border-color: #7ea8ff;
  box-shadow: 0 0 0 2px rgba(36, 107, 255, 0.08), 0 14px 28px rgba(40, 73, 128, 0.08);
}

.method-option-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 14px 16px 18px;
}

.method-option-main,
.token-plan-main {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.method-option-icon-wrap,
.token-plan-icon-wrap {
  flex: 0 0 auto;
  width: 48px;
  height: 48px;
  border-radius: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.method-option-icon-wrap {
  background: linear-gradient(180deg, #effff3 0%, #ebfff0 100%);
}

.method-option-icon,
.token-plan-icon {
  width: 28px;
  height: 28px;
  object-fit: contain;
}

.method-option-copy,
.token-plan-copy {
  display: grid;
  gap: 4px;
  text-align: left;
  min-width: 0;
}

.method-option-copy b,
.token-plan-copy b {
  font-size: 15px;
  line-height: 1.2;
  color: #19233d;
  font-weight: 800;
}

.method-option-copy small,
.token-plan-copy small {
  font-size: 12px;
  line-height: 1.5;
  color: #7f8aa0;
}

.method-option-check,
.token-plan-radio {
  width: 24px;
  height: 24px;
  flex: 0 0 auto;
  border-radius: 50%;
  border: 1.5px solid #d5deec;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #fff;
}

.method-option-check.active,
.token-plan-radio.active {
  border-color: #236bff;
}

.method-option-check img,
.token-plan-radio img {
  width: 20px;
  height: 20px;
}

.token-plan-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 14px 14px 16px;
}

.token-plan-icon-wrap.blue {
  background: linear-gradient(180deg, #edf4ff 0%, #e4efff 100%);
}

.token-plan-icon-wrap.purple {
  background: linear-gradient(180deg, #f3edff 0%, #ece3ff 100%);
}

.token-plan-icon-wrap.orange {
  background: linear-gradient(180deg, #fff2de 0%, #ffe9c7 100%);
}

.token-plan-price-side {
  display: flex;
  align-items: center;
  gap: 14px;
  flex: 0 0 auto;
}

.token-plan-price-side em {
  font-style: normal;
  font-size: 20px;
  line-height: 1;
  color: #1b2743;
  font-weight: 800;
}

.token-amount-bar {
  margin-top: 16px;
  padding: 14px 16px;
  border-radius: 16px;
  background: linear-gradient(180deg, #eef5ff 0%, #e8f1ff 100%);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.token-amount-main {
  display: flex;
  align-items: center;
  gap: 12px;
}

.token-amount-icon-wrap {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.72);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.token-amount-icon {
  width: 24px;
  height: 24px;
}

.token-amount-label {
  font-size: 15px;
  line-height: 1.2;
  color: #24324f;
  font-weight: 700;
}

.token-amount-bar strong {
  font-size: 28px;
  line-height: 1;
  color: #236bff;
  font-weight: 900;
}

.confirm-pay-btn {
  width: 100%;
  margin-top: 18px;
  height: 46px;
  border: 0;
  border-radius: 14px;
  color: #fff;
  background: linear-gradient(180deg, #3783ff 0%, #1f69ff 100%);
  box-shadow: 0 16px 30px rgba(31, 105, 255, 0.24);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  cursor: pointer;
  font-size: 15px;
  font-weight: 800;
}

.confirm-pay-btn:disabled {
  opacity: 0.58;
  cursor: not-allowed;
  box-shadow: none;
}

.confirm-pay-icon {
  width: 18px;
  height: 18px;
}

.token-modal-footnote {
  margin: 12px 0 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 12px;
  color: #90a0b8;
  line-height: 1.4;
}

.token-modal-footnote-lock {
  font-size: 12px;
  line-height: 1;
}

.pay-head {
  display: flex;
  justify-content: center;
  align-items: flex-start;
  position: relative;
  padding: 24px 24px 10px;
  background: #fff;
  border-radius: 22px 22px 0 0;
}

.pay-head strong {
  display: block;
  font-size: 18px;
  line-height: 1.2;
  color: #111827;
  text-align: center;
  font-weight: 700;
}

.pay-head span {
  display: block;
  margin-top: 8px;
  color: #99a0aa;
  font-size: 12px;
  text-align: center;
}

.pay-close {
  position: absolute;
  right: 18px;
  top: 16px;
  border: 0;
  background: transparent;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  font-size: 28px;
  line-height: 1;
  cursor: pointer;
  color: #3b82ff;
}

.pay-body {
  padding: 12px 24px 24px;
  background: #fff;
}

.pay-section {
  margin-bottom: 18px;
}

.pay-label {
  display: block;
  font-weight: 700;
  color: #111827;
  margin-bottom: 12px;
  font-size: 14px;
}

.pay-methods {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
}

.pay-methods.single {
  grid-template-columns: 1fr;
}

.pay-method,
.pay-plan {
  border: 1px solid #e5e7ef;
  background: #fff;
  border-radius: 12px;
  padding: 14px 16px;
  text-align: left;
  cursor: pointer;
  transition: 0.2s ease;
}

.pay-method.active,
.pay-plan.active {
  border-color: #3b82ff;
  background: #f5f9ff;
  box-shadow: 0 6px 16px rgba(59, 130, 255, 0.08);
}

.pay-method b,
.pay-plan b {
  display: block;
  color: #111827;
  font-size: 14px;
  font-weight: 700;
}

.pay-method span,
.pay-plan span {
  display: block;
  color: #9ca3af;
  margin-top: 4px;
  font-size: 12px;
}

.pay-method span em {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: 999px;
  background: #fff7ed;
  color: #c2410c;
  font-style: normal;
  font-size: 11px;
}

.pay-plan-list {
  display: grid;
  gap: 12px;
}

.pay-plan {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: center;
  gap: 6px;
  min-height: 66px;
}

.pay-plan span {
  grid-column: 1 / 2;
}

.pay-plan em {
  grid-row: 1 / 3;
  grid-column: 2;
  font-style: normal;
  font-size: 18px;
  font-weight: 700;
  color: #111827;
}

.pay-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  background: #f6f8fc;
  border: 1px solid #e5e7ef;
  border-radius: 12px;
  margin: 18px 0 16px;
}

.pay-summary span {
  color: #6b7280;
  font-size: 14px;
}

.pay-summary strong {
  font-size: 22px;
  color: #1d4ed8;
  font-weight: 700;
}

.pay-primary {
  width: 100%;
  height: 44px;
  border: 0;
  border-radius: 12px;
  color: #fff;
  background: linear-gradient(180deg, #3b82ff, #1667ff);
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 10px 20px rgba(22, 103, 255, 0.2);
}

.pay-primary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.pay-primary.outline {
  width: auto;
  min-width: 128px;
  padding: 0 18px;
}

.pay-status-body {
  display: grid;
  gap: 14px;
  border-radius: 0 0 22px 22px;
}

.pay-steps {
  display: grid;
  grid-template-columns: 1fr auto 1fr auto 1fr;
  align-items: center;
  gap: 10px;
  padding: 8px 0 16px;
  margin-bottom: 2px;
}

.pay-steps i {
  height: 1px;
  background: #dbe2ee;
  display: block;
}

.pay-step {
  text-align: center;
  color: #98a2b3;
}

.pay-step span {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  border: 1px solid #cdd6e4;
  display: grid;
  place-items: center;
  margin: 0 auto 6px;
  background: #fff;
  font-size: 13px;
  font-weight: 600;
}

.pay-step b {
  display: block;
  font-size: 12px;
  font-weight: 400;
}

.pay-step.active span {
  background: #1d63ff;
  color: #fff;
  border-color: #1d63ff;
  box-shadow: 0 8px 16px rgba(29, 99, 255, 0.25);
}

.pay-step.current {
  color: #111827;
}

.pay-step.current span {
  background: #fff;
  color: #1d63ff;
  border-color: #1d63ff;
}

.pay-main-grid {
  display: grid;
  grid-template-columns: 174px minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

.pay-qr-card {
  display: grid;
  justify-items: center;
  gap: 12px;
  padding: 14px 12px 16px;
  border: 1px solid #e2e9f4;
  border-radius: 18px;
  background: #fff;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.65);
}

.real-qr {
  width: 154px;
  height: 154px;
  flex: none;
  border: 1px solid #e2e9f4;
  border-radius: 16px;
  padding: 10px;
  background: #fff;
}

.qr-unavailable {
  width: 154px;
  height: 154px;
  flex: none;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  border: 1px dashed #f2a7aa;
  border-radius: 16px;
  background: #fff7f7;
  color: #9b2c2c;
  text-align: center;
}

.qr-unavailable strong { font-size: 14px; }
.qr-unavailable span { font-size: 11px; line-height: 1.5; }

.pay-qr-caption {
  margin: 0;
  color: #6b7280;
  font-size: 12px;
  text-align: center;
  line-height: 1.5;
}

.pay-order-panel {
  display: grid;
  gap: 12px;
  min-width: 0;
}

.pay-flow-box,
.pay-order-meta,
.pay-note-box {
  border: 1px solid #e5e7ef;
  border-radius: 12px;
  background: #f9fbff;
}

.pay-flow-box {
  padding: 14px 16px;
}

.pay-flow-box h4,
.pay-order-meta h4 {
  margin: 0 0 10px;
  color: #111827;
  font-size: 14px;
  font-weight: 700;
}

.pay-flow-box ol {
  margin: 0;
  padding-left: 18px;
  color: #667085;
  line-height: 1.7;
  font-size: 12px;
}

.pay-order-meta {
  padding: 14px 16px 12px;
  background: linear-gradient(180deg, #ffffff, #f7f9ff);
}

.pay-order-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 24px;
  min-width: 0;
  color: #64748b;
  font-size: 12px;
}

.pay-order-row span {
  min-width: 72px;
  color: #94a3b8;
}

.pay-order-row b {
  color: #334155;
  font-weight: 400;
  min-width: 0;
  flex: 1;
  word-break: break-all;
  overflow-wrap: anywhere;
}

.pay-order-row em {
  width: max-content;
  font-style: normal;
  padding: 3px 10px;
  border-radius: 999px;
  background: #f4f7fb;
  color: #64748b;
  font-size: 12px;
  line-height: 18px;
}

.pay-order-row em.paid {
  background: #e8fff4;
  color: #0f9f62;
}

.status-row {
  justify-content: space-between;
  flex-wrap: wrap;
}

.pay-refresh-link {
  margin-left: auto;
  border: 0;
  background: transparent;
  color: #1d63ff;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 0;
  font-size: 12px;
  cursor: pointer;
}

.pay-refresh-link svg {
  width: 14px;
  height: 14px;
  fill: currentColor;
}

.pay-refresh-link:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.pay-note-box {
  display: grid;
  grid-template-columns: 16px 1fr;
  gap: 10px;
  align-items: start;
  padding: 14px 16px;
}

.pay-note-icon {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #eaf1ff;
  color: #1d63ff;
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 700;
  margin-top: 2px;
}

.pay-note-box h4 {
  margin: 0 0 4px;
  font-size: 13px;
  color: #111827;
}

.pay-note-box p {
  margin: 0;
  color: #667085;
  font-size: 12px;
  line-height: 1.7;
}

.pay-note-box p + p {
  margin-top: 2px;
}

.pay-actions {
  display: flex;
  justify-content: center;
  gap: 10px;
  padding-top: 2px;
}

.pay-secondary {
  border: 1px solid #d8e3f2;
  background: #fff;
  color: #334155;
  border-radius: 12px;
  padding: 0 18px;
  min-width: 88px;
  height: 40px;
  font-weight: 700;
  text-decoration: none;
  cursor: pointer;
}

.pay-secondary:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.pay-secondary.sandbox {
  border-color: #bfdbfe;
  color: #1d4ed8;
  background: #eff6ff;
}

.pay-success-body {
  text-align: center;
  padding: 48px 22px;
  display: grid;
  gap: 14px;
  justify-items: center;
  border-radius: 0 0 22px 22px;
}

.pay-success-icon {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: #ecfdf5;
  color: #059669;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36px;
  font-weight: 900;
}

.pay-success-body h3 {
  margin: 0;
  font-size: 22px;
  color: #17213d;
}

.pay-success-body p {
  margin: 0;
  color: #64738c;
}

.pay-error {
  border: 1px solid #fecaca;
  background: #fff7f7;
  color: #b42318;
  border-radius: 12px;
  padding: 10px 12px;
  margin-bottom: 12px;
  font-size: 13px;
  line-height: 1.6;
}

.pay-warning {
  color: #b54708 !important;
  font-weight: 600;
}

@media (max-height: 820px) {
  .pay-mask {
    align-items: flex-start;
    padding-top: 16px;
    padding-bottom: 16px;
  }

  .token-modal-card {
    max-height: calc(100vh - 32px);
    padding: 20px 20px 14px;
    border-radius: 20px;
    overflow-y: auto;
    scrollbar-width: none;
  }

  .token-close-btn {
    top: 18px;
    right: 18px;
  }

  .token-modal-header {
    gap: 14px;
    padding-right: 50px;
  }

  .token-modal-hero {
    flex-basis: 104px;
    height: 78px;
  }

  .token-modal-hero-image {
    width: 104px;
  }

  .token-modal-title-wrap strong {
    font-size: 20px;
  }

  .token-modal-title-wrap span {
    font-size: 13px;
  }

  .token-modal-section {
    margin-top: 16px;
  }

  .token-modal-label {
    margin-bottom: 10px;
  }

  .method-option-list,
  .token-plan-list {
    gap: 12px;
  }

  .method-option-card {
    padding: 14px 12px 14px 16px;
  }

  .token-plan-card {
    padding: 12px 12px 12px 14px;
  }

  .token-amount-bar {
    margin-top: 14px;
    padding: 12px 14px;
  }

  .token-amount-icon-wrap {
    width: 38px;
    height: 38px;
    border-radius: 12px;
  }

  .token-amount-bar strong {
    font-size: 24px;
  }

  .confirm-pay-btn {
    margin-top: 16px;
    height: 44px;
  }

  .token-modal-footnote {
    margin-top: 10px;
  }
}

@media (max-width: 640px) {
  .pay-mask {
    padding: 12px;
  }

  .token-modal-card {
    padding: 18px 16px 16px;
    border-radius: 18px;
  }

  .token-modal-header {
    align-items: flex-start;
    gap: 12px;
    padding-right: 44px;
  }

  .token-modal-hero {
    flex-basis: 88px;
    height: 68px;
  }

  .token-modal-hero-image {
    width: 88px;
  }

  .token-modal-title-wrap strong {
    font-size: 18px;
  }

  .token-modal-title-wrap span {
    font-size: 12px;
  }

  .method-option-card,
  .token-plan-card {
    padding: 14px 12px;
  }

  .token-plan-card {
    align-items: flex-start;
  }

  .token-plan-price-side {
    gap: 10px;
  }

  .token-plan-price-side em {
    font-size: 18px;
  }

  .token-amount-bar {
    padding: 12px 14px;
  }

  .token-amount-bar strong {
    font-size: 24px;
  }

  .pay-head,
  .pay-body {
    padding-left: 16px;
    padding-right: 16px;
  }

  .pay-methods,
  .pay-main-grid,
  .pay-actions {
    grid-template-columns: 1fr;
  }

  .pay-methods {
    grid-template-columns: 1fr;
  }

  .pay-main-grid {
    display: grid;
  }

  .pay-actions {
    display: grid;
  }
}
</style>
