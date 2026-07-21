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
  background: rgba(16, 22, 38, 0.55);
  backdrop-filter: blur(6px);
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}

.m-pay-sheet {
  width: 100%;
  max-height: 92vh;
  background: #f5f7fb;
  border-radius: 22px 22px 0 0;
  box-shadow: 0 -12px 40px rgba(16, 28, 58, 0.18);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.m-pay-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  background: #fff;
  border-bottom: 1px solid #eef1f6;
  flex-shrink: 0;
}

.m-pay-topbar strong {
  font-size: 16px;
  font-weight: 700;
  color: #15213d;
}

.m-pay-topbar-back,
.m-pay-topbar-placeholder {
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  border: 0;
  background: transparent;
  color: #5b6478;
  cursor: pointer;
}

.m-pay-topbar-back:active {
  background: #f1f4f9;
}

.m-pay-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.m-pay-error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 12px;
  background: #fff5f5;
  border: 1px solid #ffd1d1;
  color: #b42318;
  font-size: 12px;
  line-height: 1.5;
}

.m-pay-error-link {
  margin-left: auto;
  border: 0;
  background: transparent;
  color: #1d63ff;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  padding: 0;
}

.m-pay-hero {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-radius: 16px;
  background: linear-gradient(135deg, #fff9e6 0%, #fff5d6 100%);
  border: 1px solid #ffe7a3;
}

.m-pay-hero-icon {
  width: 46px;
  height: 46px;
  border-radius: 14px;
  background: linear-gradient(135deg, #ffb94a, #ff9500);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 4px 10px rgba(255, 153, 0, 0.25);
}

.m-pay-hero-copy strong {
  display: block;
  font-size: 16px;
  font-weight: 700;
  color: #5b3f00;
  margin-bottom: 3px;
}

.m-pay-hero-copy span {
  font-size: 12px;
  color: #8c6d20;
  line-height: 1.5;
}

.m-pay-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.m-pay-section-label {
  font-size: 14px;
  font-weight: 700;
  color: #15213d;
}

.m-pay-methods,
.m-pay-plans {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.m-pay-method,
.m-pay-plan {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  border-radius: 14px;
  border: 1.5px solid #e5ebf5;
  background: #fff;
  cursor: pointer;
  text-align: left;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
  width: 100%;
}

.m-pay-method.active,
.m-pay-plan.active {
  border-color: #ff9500;
  box-shadow: 0 0 0 2px rgba(255, 149, 0, 0.1);
}

.m-pay-method-icon {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: linear-gradient(135deg, #effff3, #ebfff0);
  color: #16bf78;
}

.m-pay-method-icon.alipay {
  background: linear-gradient(135deg, #e8f3ff, #d4eaff);
  color: #1677ff;
}

.m-pay-method-copy {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.m-pay-method-copy b {
  font-size: 14px;
  font-weight: 700;
  color: #15213d;
}

.m-pay-method-copy small {
  font-size: 11px;
  color: #8c98ae;
}

.m-pay-method-radio,
.m-pay-plan-radio {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 1.5px solid #d5deec;
  background: #fff;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}

.m-pay-method-radio.active,
.m-pay-plan-radio.active {
  border-color: #ff9500;
  background: #ff9500;
}

.m-pay-plan {
  justify-content: space-between;
}

.m-pay-plan-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.m-pay-plan-main b {
  font-size: 14px;
  font-weight: 700;
  color: #15213d;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.m-pay-plan-main small {
  font-size: 11px;
  color: #8c98ae;
}

.m-pay-plan-bonus {
  color: #ff9500;
  font-weight: 600;
  margin-left: 4px;
}

.m-pay-plan-side {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.m-pay-plan-side em {
  font-style: normal;
  font-size: 16px;
  font-weight: 800;
  color: #15213d;
}

.m-pay-empty {
  padding: 18px 0;
  color: #98a2b3;
  font-size: 13px;
  text-align: center;
}

.m-pay-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-radius: 14px;
  background: linear-gradient(135deg, #fff9e6, #fff5d6);
  border: 1px solid #ffe7a3;
}

.m-pay-summary-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #8c6d20;
  font-weight: 600;
}

.m-pay-summary-value {
  font-size: 22px;
  font-weight: 800;
  color: #ff9500;
  line-height: 1;
}

.m-pay-primary {
  width: 100%;
  height: 48px;
  border: 0;
  border-radius: 14px;
  background: linear-gradient(135deg, #ffb94a, #ff9500);
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 8px 18px rgba(255, 149, 0, 0.28);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.m-pay-primary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  box-shadow: none;
}

.m-pay-primary:active:not(:disabled) {
  transform: scale(0.98);
}

.m-pay-primary.outline {
  width: auto;
  flex: 1;
  background: #fff;
  color: #ff9500;
  border: 1.5px solid #ffd699;
  box-shadow: none;
}

.m-pay-footnote {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 11px;
  color: #98a2b3;
  margin: 0;
}

.m-pay-steps {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 4px 2px;
}

.m-pay-step {
  flex: 1;
  text-align: center;
  color: #98a2b3;
}

.m-pay-step-num {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  border: 1px solid #cdd6e4;
  display: grid;
  place-items: center;
  margin: 0 auto 4px;
  background: #fff;
  font-size: 12px;
  font-weight: 600;
}

.m-pay-step b {
  font-size: 11px;
  font-weight: 400;
  display: block;
}

.m-pay-step.active .m-pay-step-num {
  background: #ff9500;
  color: #fff;
  border-color: #ff9500;
}

.m-pay-step.current {
  color: #15213d;
}

.m-pay-step.current .m-pay-step-num {
  background: #fff;
  color: #ff9500;
  border-color: #ff9500;
}

.m-pay-step-line {
  flex: 0 0 16px;
  height: 1px;
  background: #dbe2ee;
}

.m-pay-qr-card {
  background: #fff;
  border-radius: 16px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  border: 1px solid #eef1f6;
}

.m-pay-qr-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.m-pay-qr {
  width: 200px;
  height: 200px;
  border: 1px solid #e2e9f4;
  border-radius: 14px;
  padding: 8px;
  background: #fff;
  object-fit: contain;
  -webkit-user-select: none;
  user-select: none;
}

.m-pay-qr-hint {
  font-size: 12px;
  color: #8c98ae;
  margin: 0;
}

.m-pay-qr-unavailable {
  width: 200px;
  height: 200px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px dashed #f2a7aa;
  border-radius: 14px;
  background: #fff7f7;
  color: #9b2c2c;
  text-align: center;
  padding: 12px;
}

.m-pay-qr-unavailable strong {
  font-size: 13px;
}

.m-pay-qr-unavailable span {
  font-size: 11px;
  line-height: 1.5;
}

.m-pay-qr-caption {
  margin: 0;
  font-size: 12px;
  color: #6b7280;
  text-align: center;
  line-height: 1.5;
}

.m-pay-order-meta {
  background: #fff;
  border-radius: 14px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  border: 1px solid #eef1f6;
}

.m-pay-order-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  min-width: 0;
}

.m-pay-order-row span {
  color: #94a3b8;
  min-width: 64px;
  flex-shrink: 0;
}

.m-pay-order-row b {
  color: #334155;
  font-weight: 500;
  flex: 1;
  min-width: 0;
  overflow-wrap: anywhere;
}

.m-pay-order-row em {
  font-style: normal;
  padding: 2px 10px;
  border-radius: 999px;
  background: #f4f7fb;
  color: #64748b;
  font-size: 11px;
}

.m-pay-order-row em.paid {
  background: #e8fff4;
  color: #0f9f62;
}

.m-pay-note {
  display: flex;
  gap: 8px;
  padding: 12px 14px;
  background: #fff;
  border-radius: 14px;
  border: 1px solid #eef1f6;
  color: #667085;
}

.m-pay-note p {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
}

.m-pay-note p + p {
  margin-top: 4px;
}

.m-pay-warning {
  color: #b54708 !important;
  font-weight: 600;
}

.m-pay-actions {
  display: flex;
  gap: 10px;
  align-items: stretch;
}

.m-pay-secondary {
  flex: 0 0 auto;
  min-width: 92px;
  height: 44px;
  border-radius: 12px;
  border: 1px solid #d8e3f2;
  background: #fff;
  color: #334155;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  padding: 0 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.m-pay-secondary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.m-pay-secondary.sandbox {
  border-color: #ffd699;
  color: #ff9500;
  background: #fff9e6;
}

.m-pay-success {
  text-align: center;
  padding: 40px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  background: #fff;
  border-radius: 16px;
  border: 1px solid #eef1f6;
}

.m-pay-success-icon {
  width: 68px;
  height: 68px;
  border-radius: 50%;
  background: #ecfdf5;
  color: #059669;
  display: flex;
  align-items: center;
  justify-content: center;
}

.m-pay-success h3 {
  margin: 0;
  font-size: 20px;
  color: #15213d;
  font-weight: 700;
}

.m-pay-success p {
  margin: 0;
  color: #64738c;
  font-size: 13px;
  line-height: 1.5;
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
    padding: 12px;
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
