<template>
  <Transition name="m-pay-fade">
    <div v-if="visible" class="m-pay-mask" @click.self="emitClose">
      <Transition name="m-pay-sheet">
        <div v-if="visible" class="m-pay-sheet" role="dialog" aria-modal="true">
          <!-- 顶部栏 -->
          <header class="m-pay-topbar">
            <button type="button" class="m-pay-topbar-back" aria-label="返回" @click="emitClose">
              <MIcon name="x" :size="20" />
            </button>
            <strong>{{ topbarTitle }}</strong>
            <span class="m-pay-topbar-placeholder"></span>
          </header>

          <div class="m-pay-body">
            <!-- 错误提示 -->
            <div v-if="error" class="m-pay-error" role="alert">
              <MIcon name="alertCircle" :size="14" />
              <span>{{ error }}</span>
            </div>
            <div v-if="capabilityError" class="m-pay-error" role="alert">
              <MIcon name="alertCircle" :size="14" />
              <span>{{ capabilityError }}</span>
              <button type="button" class="m-pay-error-link" @click="reloadCapabilities">重新加载</button>
            </div>

            <!-- 阶段 1：选择套餐与支付方式 -->
            <template v-if="!currentOrder && !paid">
              <div class="m-pay-hero">
                <div class="m-pay-hero-icon">
                  <MIcon name="coins" :size="26" />
                </div>
                <div class="m-pay-hero-copy">
                  <strong>Token 充值</strong>
                  <span>为账户充值 Token 余额，支付后自动到账</span>
                </div>
              </div>

              <section class="m-pay-section">
                <label class="m-pay-section-label">支付方式</label>
                <div class="m-pay-methods">
                  <button
                    v-for="method in normalizedMethods"
                    :key="method.channelType"
                    type="button"
                    :class="['m-pay-method', { active: paymentMethod === method.channelType }]"
                    @click="paymentMethod = method.channelType"
                  >
                    <span class="m-pay-method-icon" :class="method.channelType">
                      <MIcon :name="method.channelType === 'alipay' ? 'dollar' : 'coins'" :size="18" />
                    </span>
                    <span class="m-pay-method-copy">
                      <b>{{ paymentMethodLabel(method) }}</b>
                      <small>{{ paymentMethodDesc(method) }}</small>
                    </span>
                    <span class="m-pay-method-radio" :class="{ active: paymentMethod === method.channelType }">
                      <MIcon v-if="paymentMethod === method.channelType" name="check" :size="12" />
                    </span>
                  </button>
                </div>
              </section>

              <section class="m-pay-section">
                <label class="m-pay-section-label">充值套餐</label>
                <div class="m-pay-plans">
                  <button
                    v-for="tokenPlan in tokenPlans"
                    :key="tokenPlan.id"
                    type="button"
                    :class="['m-pay-plan', { active: selectedTokenPlanId === tokenPlan.id }]"
                    @click="selectedTokenPlanId = tokenPlan.id"
                  >
                    <div class="m-pay-plan-main">
                      <b>{{ tokenPlan.planName || tokenPlanLabel(tokenPlan) }}</b>
                      <small>
                        {{ formatTokenAmount(tokenPlan.tokenAmount) }} Token
                        <span v-if="Number(tokenPlan.bonusToken || 0) > 0" class="m-pay-plan-bonus">
                          +赠送 {{ formatTokenAmount(tokenPlan.bonusToken) }}
                        </span>
                      </small>
                    </div>
                    <div class="m-pay-plan-side">
                      <em>{{ tokenPlanPrice(tokenPlan) }}</em>
                      <span class="m-pay-plan-radio" :class="{ active: selectedTokenPlanId === tokenPlan.id }">
                        <MIcon v-if="selectedTokenPlanId === tokenPlan.id" name="check" :size="12" />
                      </span>
                    </div>
                  </button>
                </div>
                <div v-if="plansLoaded && !tokenPlans.length && !plansError" class="m-pay-empty">
                  暂无可用充值套餐
                </div>
              </section>

              <div class="m-pay-summary">
                <span class="m-pay-summary-label">
                  <MIcon name="dollar" :size="14" /> 应付金额
                </span>
                <strong class="m-pay-summary-value">{{ amountText }}</strong>
              </div>

              <button
                type="button"
                class="m-pay-primary"
                :disabled="submitting || !paymentMethod || !canCreate"
                @click="createOrder"
              >
                {{ submitting ? '正在创建订单...' : '确认支付' }}
              </button>

              <p class="m-pay-footnote">
                <MIcon name="shield" :size="12" />
                <span>支付状态以服务端订单为准，请在提交前核对套餐与金额</span>
              </p>
            </template>

            <!-- 阶段 2：扫码支付 -->
            <template v-else-if="currentOrder && !paid">
              <div class="m-pay-steps">
                <div class="m-pay-step active">
                  <span class="m-pay-step-num">1</span>
                  <b>{{ currentOrder.qrImage ? '二维码已生成' : '二维码不可用' }}</b>
                </div>
                <i class="m-pay-step-line"></i>
                <div class="m-pay-step current">
                  <span class="m-pay-step-num">2</span>
                  <b>扫码支付</b>
                </div>
                <i class="m-pay-step-line"></i>
                <div class="m-pay-step">
                  <span class="m-pay-step-num">3</span>
                  <b>自动到账</b>
                </div>
              </div>

              <div class="m-pay-qr-card">
                <div v-if="currentOrder.qrImage" class="m-pay-qr-wrap">
                  <img class="m-pay-qr" :src="currentOrder.qrImage" alt="支付二维码" />
                  <p class="m-pay-qr-hint">长按二维码识别支付</p>
                </div>
                <div v-else class="m-pay-qr-unavailable" role="alert">
                  <MIcon name="alertCircle" :size="28" />
                  <strong>支付二维码不可用</strong>
                  <span>订单未返回可扫描的二维码图片</span>
                </div>
                <p class="m-pay-qr-caption">
                  {{ sandboxPayEnabled ? '沙箱订单不会真实扣款，可点击下方模拟支付完成测试' : payCaption }}
                </p>
              </div>

              <div class="m-pay-order-meta">
                <div class="m-pay-order-row">
                  <span>订单编号</span>
                  <b>{{ currentOrder.orderNo }}</b>
                </div>
                <div class="m-pay-order-row">
                  <span>Token 数量</span>
                  <b>{{ currentOrder.tokenAmount ?? selectedTokenPlan?.tokenAmount ?? '—' }}</b>
                </div>
                <div class="m-pay-order-row">
                  <span>支付金额</span>
                  <b>{{ currentOrder.amount || amountText }}</b>
                </div>
                <div class="m-pay-order-row">
                  <span>当前状态</span>
                  <em :class="{ paid: currentOrder.status === 1 }">{{ currentOrder.statusText || '状态未返回' }}</em>
                </div>
              </div>

              <div class="m-pay-note">
                <MIcon name="info" :size="14" />
                <p>
                  {{ sandboxPayEnabled
                    ? '当前是沙箱测试订单，不会发生真实扣款；可使用“沙箱模拟支付成功”验证权益发放。'
                    : currentOrder.qrImage
                      ? '使用所选支付渠道扫码完成支付；二维码过期请关闭后重新创建订单。'
                      : '当前订单缺少可扫描二维码，请取消订单并联系管理员。' }}
                </p>
                <p v-if="pollCount > 8" class="m-pay-warning">
                  已等待较长时间仍未到账，请确认支付是否完成，或联系人工客服并提供订单编号。
                </p>
              </div>

              <div class="m-pay-actions">
                <button type="button" class="m-pay-secondary" :disabled="closing" @click="cancelOrder">
                  {{ closing ? '取消中...' : '取消订单' }}
                </button>
                <button
                  v-if="sandboxPayEnabled"
                  type="button"
                  class="m-pay-secondary sandbox"
                  :disabled="refreshing"
                  @click="mockPay"
                >
                  沙箱模拟支付
                </button>
                <button type="button" class="m-pay-primary outline" :disabled="refreshing" @click="refreshOrder">
                  <MIcon name="refresh" :size="14" />
                  {{ refreshing ? '刷新中...' : '我已完成支付' }}
                </button>
              </div>
            </template>

            <!-- 阶段 3：支付成功 -->
            <template v-else>
              <div class="m-pay-success">
                <div class="m-pay-success-icon">
                  <MIcon name="check" :size="40" />
                </div>
                <h3>支付成功</h3>
                <p>{{ currentOrder?.title || 'Token 充值' }} 已完成支付，即将自动刷新余额...</p>
              </div>
            </template>
          </div>
        </div>
      </Transition>
    </div>
  </Transition>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import MIcon from '../MIcon.vue'
import {
  closePaymentOrder,
  createPaymentOrder,
  getPaymentMethods,
  getPaymentOrder,
  getTokenRechargePlans,
  mockPayOrder
} from '../../api/payment.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  orderType: { type: String, default: 'token' },
  targetType: { type: String, default: 'user_account' },
  targetId: { type: [Number, String], default: null }
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
  // Token 充值仅展示微信支付（与 PC 端逻辑保持一致）
  return methods.value.filter(method => method.channelType === 'wechat').slice(0, 1)
})

const selectedTokenPlan = computed(() => tokenPlans.value.find(item => item.id === selectedTokenPlanId.value))
const selectedMethod = computed(() => normalizedMethods.value.find(item => item.channelType === paymentMethod.value))
const sandboxPayEnabled = computed(() =>
  Number(selectedMethod.value?.sandbox || currentOrder.value?.sandbox || 0) === 1
  || currentOrder.value?.providerType === 'mock'
)
const payCaption = computed(() =>
  paymentMethod.value === 'alipay' ? '请使用支付宝扫描二维码支付' : '请使用微信扫描二维码支付'
)
const topbarTitle = computed(() => {
  if (paid.value) return '支付成功'
  if (currentOrder.value) return '扫码支付'
  return 'Token 充值'
})

const capabilityError = computed(() => {
  const errors = [methodsError.value]
  if (props.orderType === 'token') errors.push(plansError.value)
  return errors.filter(Boolean).join('；')
})

const canCreate = computed(() => {
  if (!methodsLoaded.value || methodsError.value || !selectedMethod.value) return false
  if (props.orderType === 'vip') return false
  return plansLoaded.value && !plansError.value && !!selectedTokenPlan.value
})

const amountText = computed(() => {
  const plan = selectedTokenPlan.value
  return plan ? tokenPlanPrice(plan) : '价格未配置'
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
  try {
    const loadedMethods = await getPaymentMethods()
    if (!Array.isArray(loadedMethods)) throw new Error('支付方式响应格式异常')
    methods.value = loadedMethods
    methodsLoaded.value = true
    if (!normalizedMethods.value.length) {
      methodsError.value = props.orderType === 'token' ? '未配置可用的微信支付方式' : '未配置可用的支付方式'
    }
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
    if (props.orderType === 'token') payload.tokenPlanId = selectedTokenPlanId.value
    currentOrder.value = validateOrderSnapshot(await createPaymentOrder(payload))
    if (!currentOrder.value.qrImage && !sandboxPayEnabled.value) {
      error.value = '订单已创建，但服务端未返回可扫描的支付二维码；请取消订单并联系管理员。'
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

function isReadableConfigName(name) {
  if (!name) return false
  const str = String(name).trim()
  if (!str || str.length > 40) return false
  return /^[\p{L}\p{N}\s\u00B7\u30FB\-_/()().、+]+$/u.test(str)
}

function paymentMethodLabel(method) {
  if (isReadableConfigName(method?.configName)) return String(method.configName).trim()
  if (method?.channelType === 'wechat') return '微信支付'
  if (method?.channelType === 'alipay') return '支付宝'
  return '支付方式'
}

function paymentMethodDesc(method) {
  if (Number(method.sandbox || 0) === 1) return '沙箱环境支付测试'
  if (method.description) return method.description
  if (method.providerType === 'yipay') return '易支付通道'
  if (method.providerType === 'official') return '官方接口'
  return '由后台支付配置提供'
}

function tokenPlanLabel(plan) {
  const total = Number(plan.tokenAmount || 0) + Number(plan.bonusToken || 0)
  return total > 0 ? `${total} Token` : 'Token 套餐'
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

function formatTokenAmount(value) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '—'
  return num.toLocaleString()
}

onBeforeUnmount(() => {
  stopPolling()
  clearSuccessTimer()
})
</script>

<style scoped>
.m-pay-mask {
  position: fixed;
  inset: 0;
  z-index: 1200;
  background: var(--m-mask-modal);
  backdrop-filter: blur(6px);
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}

.m-pay-sheet {
  width: 100%;
  max-height: 92vh;
  background: var(--m-color-bg-page);
  border-radius: var(--m-radius-2xl) var(--m-radius-2xl) 0 0;
  box-shadow: var(--m-shadow-elevated);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.m-pay-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-space-3) var(--m-space-4);
  background: var(--m-color-bg-card);
  border-bottom: 1px solid var(--m-color-border-light);
  flex-shrink: 0;
}

.m-pay-topbar strong {
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
}

.m-pay-topbar-back,
.m-pay-topbar-placeholder {
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--m-radius-circle);
  border: 0;
  background: transparent;
  color: var(--m-color-text-secondary);
  cursor: pointer;
}

.m-pay-topbar-back:active {
  background: var(--m-color-bg-hover);
}

.m-pay-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--m-space-4);
  display: flex;
  flex-direction: column;
  gap: var(--m-space-4);
}

.m-pay-error {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  padding: var(--m-space-3) var(--m-space-3);
  border-radius: var(--m-radius-lg);
  background: var(--m-color-danger-bg);
  border: 1px solid var(--m-color-danger-border);
  color: var(--m-color-danger-text);
  font-size: var(--m-font-size-caption);
  line-height: var(--m-line-height-base);
}

.m-pay-error-link {
  margin-left: auto;
  border: 0;
  background: transparent;
  color: var(--m-color-primary);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  padding: 0;
}

.m-pay-hero {
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
  padding: var(--m-space-4);
  border-radius: var(--m-radius-xl);
  background: var(--m-color-warning-bg);
  border: 1px solid var(--m-color-warning-border);
}

.m-pay-hero-icon {
  width: 46px;
  height: 46px;
  border-radius: var(--m-radius-xl);
  background: var(--m-color-warning);
  color: var(--m-color-text-inverse);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: var(--m-shadow-card);
}

.m-pay-hero-copy strong {
  display: block;
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-warning-text);
  margin-bottom: var(--m-space-1);
}

.m-pay-hero-copy span {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-warning-text);
  line-height: var(--m-line-height-base);
}

.m-pay-section {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-3);
}

.m-pay-section-label {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
}

.m-pay-methods,
.m-pay-plans {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-3);
}

.m-pay-method,
.m-pay-plan {
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
  padding: var(--m-space-3);
  border-radius: var(--m-radius-xl);
  border: 1.5px solid var(--m-color-border);
  background: var(--m-color-bg-card);
  cursor: pointer;
  text-align: left;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
  width: 100%;
}

.m-pay-method.active,
.m-pay-plan.active {
  border-color: var(--m-color-primary);
  box-shadow: 0 0 0 2px var(--m-color-primary-bg);
}

.m-pay-method-icon {
  width: 38px;
  height: 38px;
  border-radius: var(--m-radius-lg);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: var(--m-color-success-bg);
  color: var(--m-color-success);
}

.m-pay-method-icon.alipay {
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
}

.m-pay-method-copy {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--m-space-1);
}

.m-pay-method-copy b {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
}

.m-pay-method-copy small {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}

.m-pay-method-radio,
.m-pay-plan-radio {
  width: 20px;
  height: 20px;
  border-radius: var(--m-radius-circle);
  border: 1.5px solid var(--m-color-border);
  background: var(--m-color-bg-card);
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--m-color-text-inverse);
}

.m-pay-method-radio.active,
.m-pay-plan-radio.active {
  border-color: var(--m-color-primary);
  background: var(--m-color-primary);
}

.m-pay-plan {
  justify-content: space-between;
}

.m-pay-plan-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--m-space-1);
}

.m-pay-plan-main b {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.m-pay-plan-main small {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}

.m-pay-plan-bonus {
  color: var(--m-color-warning-text);
  font-weight: var(--m-font-weight-semibold);
  margin-left: var(--m-space-1);
}

.m-pay-plan-side {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  flex-shrink: 0;
}

.m-pay-plan-side em {
  font-style: normal;
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
}

.m-pay-empty {
  padding: var(--m-space-4) 0;
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-body-sm);
  text-align: center;
}

.m-pay-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-space-3) var(--m-space-4);
  border-radius: var(--m-radius-xl);
  background: var(--m-color-warning-bg);
  border: 1px solid var(--m-color-warning-border);
}

.m-pay-summary-label {
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-2);
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-warning-text);
  font-weight: var(--m-font-weight-semibold);
}

.m-pay-summary-value {
  font-size: var(--m-font-size-h1);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-warning-text);
  line-height: 1;
}

.m-pay-primary {
  width: 100%;
  height: 48px;
  border: 0;
  border-radius: var(--m-radius-xl);
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-bold);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-2);
}

.m-pay-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  box-shadow: none;
}

.m-pay-primary:active:not(:disabled) {
  transform: scale(0.98);
}

.m-pay-primary.outline {
  width: auto;
  flex: 1;
  background: var(--m-color-bg-card);
  color: var(--m-color-primary);
  border: 1.5px solid var(--m-color-primary);
  box-shadow: none;
}

.m-pay-footnote {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-2);
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  margin: 0;
}

.m-pay-steps {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  padding: var(--m-space-2) var(--m-space-1) var(--m-space-1);
}

.m-pay-step {
  flex: 1;
  text-align: center;
  color: var(--m-color-text-tertiary);
}

.m-pay-step-num {
  width: 26px;
  height: 26px;
  border-radius: var(--m-radius-circle);
  border: 1px solid var(--m-color-border);
  display: grid;
  place-items: center;
  margin: 0 auto var(--m-space-1);
  background: var(--m-color-bg-card);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-semibold);
}

.m-pay-step b {
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-regular);
  display: block;
}

.m-pay-step.active .m-pay-step-num {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  border-color: var(--m-color-primary);
}

.m-pay-step.current {
  color: var(--m-color-text-primary);
}

.m-pay-step.current .m-pay-step-num {
  background: var(--m-color-bg-card);
  color: var(--m-color-primary);
  border-color: var(--m-color-primary);
}

.m-pay-step-line {
  flex: 0 0 16px;
  height: 1px;
  background: var(--m-color-border);
}

.m-pay-qr-card {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-4);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--m-space-3);
  border: 1px solid var(--m-color-border-light);
}

.m-pay-qr-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--m-space-2);
}

.m-pay-qr {
  width: 200px;
  height: 200px;
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-2);
  background: var(--m-color-bg-card);
  object-fit: contain;
  -webkit-user-select: none;
  user-select: none;
}

.m-pay-qr-hint {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  margin: 0;
}

.m-pay-qr-unavailable {
  width: 200px;
  height: 200px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-2);
  border: 1px dashed var(--m-color-danger-border);
  border-radius: var(--m-radius-xl);
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger-text);
  text-align: center;
  padding: var(--m-space-3);
}

.m-pay-qr-unavailable strong {
  font-size: var(--m-font-size-body-sm);
}

.m-pay-qr-unavailable span {
  font-size: var(--m-font-size-caption);
  line-height: var(--m-line-height-base);
}

.m-pay-qr-caption {
  margin: 0;
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-secondary);
  text-align: center;
  line-height: var(--m-line-height-base);
}

.m-pay-order-meta {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-3) var(--m-space-4);
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
  border: 1px solid var(--m-color-border-light);
}

.m-pay-order-row {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  font-size: var(--m-font-size-caption);
  min-width: 0;
}

.m-pay-order-row span {
  color: var(--m-color-text-tertiary);
  min-width: 64px;
  flex-shrink: 0;
}

.m-pay-order-row b {
  color: var(--m-color-text-primary);
  font-weight: var(--m-font-weight-medium);
  flex: 1;
  min-width: 0;
  overflow-wrap: anywhere;
}

.m-pay-order-row em {
  font-style: normal;
  padding: var(--m-space-1) var(--m-space-3);
  border-radius: var(--m-radius-pill);
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
  font-size: var(--m-font-size-caption);
}

.m-pay-order-row em.paid {
  background: var(--m-color-success-bg);
  color: var(--m-color-success-text);
}

.m-pay-note {
  display: flex;
  gap: var(--m-space-2);
  padding: var(--m-space-3) var(--m-space-4);
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-xl);
  border: 1px solid var(--m-color-border-light);
  color: var(--m-color-text-secondary);
}

.m-pay-note p {
  margin: 0;
  font-size: var(--m-font-size-caption);
  line-height: var(--m-line-height-relaxed);
}

.m-pay-note p + p {
  margin-top: var(--m-space-1);
}

.m-pay-warning {
  color: var(--m-color-warning-text) !important;
  font-weight: var(--m-font-weight-semibold);
}

.m-pay-actions {
  display: flex;
  gap: var(--m-space-3);
  align-items: stretch;
}

.m-pay-secondary {
  flex: 0 0 auto;
  min-width: 92px;
  height: 44px;
  border-radius: var(--m-radius-lg);
  border: 1px solid var(--m-color-border);
  background: var(--m-color-bg-card);
  color: var(--m-color-text-primary);
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  padding: 0 var(--m-space-3);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.m-pay-secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.m-pay-secondary.sandbox {
  border-color: var(--m-color-warning-border);
  color: var(--m-color-warning-text);
  background: var(--m-color-warning-bg);
}

.m-pay-success {
  text-align: center;
  padding: var(--m-space-10) var(--m-space-5);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--m-space-3);
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-xl);
  border: 1px solid var(--m-color-border-light);
}

.m-pay-success-icon {
  width: 68px;
  height: 68px;
  border-radius: var(--m-radius-circle);
  background: var(--m-color-success-bg);
  color: var(--m-color-success);
  display: flex;
  align-items: center;
  justify-content: center;
}

.m-pay-success h3 {
  margin: 0;
  font-size: var(--m-font-size-h1);
  color: var(--m-color-text-primary);
  font-weight: var(--m-font-weight-bold);
}

.m-pay-success p {
  margin: 0;
  color: var(--m-color-text-secondary);
  font-size: var(--m-font-size-body-sm);
  line-height: var(--m-line-height-base);
}

.m-pay-fade-enter-active,
.m-pay-fade-leave-active {
  transition: opacity 0.22s ease;
}

.m-pay-fade-enter-from,
.m-pay-fade-leave-to {
  opacity: 0;
}

.m-pay-sheet-enter-active,
.m-pay-sheet-leave-active {
  transition: transform 0.26s cubic-bezier(0.22, 0.61, 0.36, 1);
}

.m-pay-sheet-enter-from,
.m-pay-sheet-leave-to {
  transform: translateY(100%);
}

@media (max-width: 360px) {
  .m-pay-body {
    padding: var(--m-space-3);
  }

  .m-pay-qr {
    width: 180px;
    height: 180px;
  }

  .m-pay-qr-unavailable {
    width: 180px;
    height: 180px;
  }

  .m-pay-actions {
    flex-wrap: wrap;
  }

  .m-pay-secondary {
    flex: 1;
    min-width: 0;
  }
}
</style>
