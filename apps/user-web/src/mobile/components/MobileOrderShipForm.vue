<template>
  <Teleport to="body">
    <Transition name="m-ship-fade">
      <div v-if="visible" class="m-ship-mask" @click.self="handleClose">
        <Transition name="m-ship-slide">
          <div v-if="visible" class="m-ship-sheet" role="dialog" aria-modal="true">
            <div class="m-ship-handle"></div>

            <div class="m-ship-header">
              <h3>订单发货</h3>
              <button type="button" class="m-ship-close" :disabled="submitting" @click="handleClose">
                <MIcon name="x" :size="20" />
              </button>
            </div>

            <div v-if="order" class="m-ship-order-meta">
              <span class="m-ship-order-id">{{ order.externalOrderId || '-' }}</span>
              <span class="m-ship-order-buyer">{{ order.buyerName || '-' }}</span>
            </div>

            <div class="m-ship-body">
              <div v-if="errorMsg" class="m-ship-notice error" role="alert">
                <MIcon name="alertCircle" :size="14" />
                <span>{{ errorMsg }}</span>
              </div>
              <div v-if="successMsg" class="m-ship-notice success" role="status">
                <MIcon name="checkCircle" :size="14" />
                <span>{{ successMsg }}</span>
              </div>

              <div class="m-ship-field">
                <label class="m-ship-label">
                  物流公司
                  <span class="m-ship-required">*</span>
                </label>
                <div class="m-ship-select-wrap">
                  <select v-model="form.company" class="m-ship-select" :disabled="submitting">
                    <option value="" disabled>请选择物流公司</option>
                    <option v-for="item in LOGISTICS_COMPANIES" :key="item.code" :value="item.name">
                      {{ item.name }}
                    </option>
                  </select>
                  <MIcon name="chevronDown" :size="16" class="m-ship-select-arrow" />
                </div>
              </div>

              <div class="m-ship-field">
                <label class="m-ship-label">
                  物流单号
                  <span class="m-ship-required">*</span>
                </label>
                <input
                  v-model.trim="form.trackingNo"
                  type="text"
                  class="m-ship-input"
                  placeholder="请输入物流单号"
                  :disabled="submitting"
                  maxlength="64"
                  autocomplete="off"
                />
              </div>

              <div class="m-ship-field">
                <label class="m-ship-label">
                  发货备注
                  <span class="m-ship-optional">（可选）</span>
                </label>
                <textarea
                  v-model.trim="form.remark"
                  class="m-ship-textarea"
                  placeholder="可填写发货备注，如包裹特征、发货时间等"
                  :disabled="submitting"
                  rows="3"
                  maxlength="200"
                ></textarea>
              </div>

              <p class="m-ship-tip">
                <MIcon name="info" :size="12" />
                <span>提交后将通过手动发货接口推送物流信息，买家可在订单消息中查看</span>
              </p>
            </div>

            <div class="m-ship-footer">
              <button
                type="button"
                class="m-ship-btn m-ship-btn-cancel"
                :disabled="submitting"
                @click="handleClose"
              >
                取消
              </button>
              <button
                type="button"
                class="m-ship-btn m-ship-btn-submit"
                :disabled="!canSubmit || submitting"
                @click="handleSubmit"
              >
                <span v-if="submitting" class="m-ship-spinner"></span>
                <MIcon v-else name="send" :size="16" />
                <span>{{ submitting ? '提交中...' : '确认发货' }}</span>
              </button>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { reactive, ref, watch, computed } from 'vue'
import MIcon from '../MIcon.vue'
import { manualDeliverOrder } from '../../api/orders.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  order: { type: Object, default: null }
})
const emit = defineEmits(['close', 'success'])

// 常见物流公司列表（无服务端字典，前端内置；如后续后端提供物流公司字典接口可改为远程加载）
const LOGISTICS_COMPANIES = [
  { code: 'SF', name: '顺丰速运' },
  { code: 'ZTO', name: '中通快递' },
  { code: 'YTO', name: '圆通速递' },
  { code: 'STO', name: '申通快递' },
  { code: 'YD', name: '韵达快递' },
  { code: 'JD', name: '京东物流' },
  { code: 'EMS', name: 'EMS' },
  { code: 'POST', name: '中国邮政' },
  { code: 'TTK', name: '天天快递' },
  { code: 'BEST', name: '百世快递' },
  { code: 'HT', name: '百世快运' },
  { code: 'DBL', name: '德邦快递' },
  { code: 'JC', name: '极兔速递' },
  { code: 'UC', name: '优速快递' },
  { code: 'GTO', name: '国通快递' },
  { code: 'RFD', name: '如风达' },
  { code: 'FAST', name: '快捷快递' },
  { code: 'OTHER', name: '其他' }
]

const form = reactive({
  company: '',
  trackingNo: '',
  remark: ''
})
const submitting = ref(false)
const errorMsg = ref('')
const successMsg = ref('')

const canSubmit = computed(() => {
  return !!(form.company && form.trackingNo)
})

watch(() => props.visible, value => {
  if (value) {
    form.company = ''
    form.trackingNo = ''
    form.remark = ''
    errorMsg.value = ''
    successMsg.value = ''
    submitting.value = false
  }
})

function handleClose() {
  if (submitting.value) return
  emit('close')
}

function buildDeliveryContent() {
  const parts = [`物流公司：${form.company}`, `物流单号：${form.trackingNo}`]
  if (form.remark) parts.push(`备注：${form.remark}`)
  return parts.join('\n')
}

async function handleSubmit() {
  if (!props.order?.id) {
    errorMsg.value = '订单信息缺失，无法发货'
    return
  }
  if (!canSubmit.value) {
    errorMsg.value = '请填写物流公司和物流单号'
    return
  }
  submitting.value = true
  errorMsg.value = ''
  successMsg.value = ''
  try {
    // 后端 manual-delivery 接口字段为 { deliveryMode, deliveryTiming, deliveryContent, quantityRequested }
    // 移动端物流发货表单将物流公司+物流单号+备注拼接为 deliveryContent 文本，与 PC 端手动文本发货共用同一接口
    const payload = {
      deliveryMode: 'text',
      deliveryTiming: 'after_payment',
      deliveryContent: buildDeliveryContent(),
      quantityRequested: 1
    }
    await manualDeliverOrder(props.order.id, payload)
    successMsg.value = '发货任务已提交'
    // 给用户一个简短的成功提示后再关闭弹层
    setTimeout(() => {
      emit('success', { orderId: props.order.id, payload })
    }, 600)
  } catch (err) {
    errorMsg.value = err?.message || '提交发货失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.m-ship-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--m-mask-modal);
  z-index: 1100;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.m-ship-fade-enter-active,
.m-ship-fade-leave-active {
  transition: opacity 0.2s ease;
}
.m-ship-fade-enter-from,
.m-ship-fade-leave-to {
  opacity: 0;
}

.m-ship-sheet {
  width: 100%;
  max-width: 500px;
  background: var(--m-color-bg-page);
  border-radius: var(--m-radius-2xl) var(--m-radius-2xl) 0 0;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--m-shadow-elevated);
}
.m-ship-slide-enter-active,
.m-ship-slide-leave-active {
  transition: transform 0.3s ease;
}
.m-ship-slide-enter-from,
.m-ship-slide-leave-to {
  transform: translateY(100%);
}

.m-ship-handle {
  width: var(--m-space-10);
  height: 4px;
  background: var(--m-color-border);
  border-radius: var(--m-radius-sm);
  margin: var(--m-space-2) auto 0;
  flex-shrink: 0;
}

.m-ship-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-space-3) var(--m-space-5) var(--m-space-1);
  flex-shrink: 0;
}
.m-ship-header h3 {
  margin: 0;
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
}
.m-ship-close {
  width: var(--m-space-8);
  height: var(--m-space-8);
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
.m-ship-close:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.m-ship-order-meta {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  padding: 0 var(--m-space-5) var(--m-space-2);
  flex-shrink: 0;
}
.m-ship-order-id {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-secondary);
  font-family: var(--m-font-family-mono);
  background: var(--m-color-bg-subtle);
  padding: var(--m-space-1) var(--m-space-2);
  border-radius: var(--m-radius-md);
}
.m-ship-order-buyer {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}

.m-ship-body {
  flex: 1;
  overflow-y: auto;
  padding: 0 var(--m-space-4) var(--m-space-3);
}

.m-ship-notice {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  padding: var(--m-space-2) var(--m-space-3);
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-caption);
  margin-bottom: var(--m-space-3);
  line-height: var(--m-line-height-base);
}
.m-ship-notice.error {
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger-text);
  border: 1px solid var(--m-color-danger-border);
}
.m-ship-notice.success {
  background: var(--m-color-success-bg);
  color: var(--m-color-success-text);
  border: 1px solid var(--m-color-success-border);
}

.m-ship-field {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3) var(--m-space-4);
  margin-bottom: var(--m-space-2);
  box-shadow: var(--m-shadow-card);
}
.m-ship-label {
  display: block;
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  margin-bottom: var(--m-space-2);
}
.m-ship-required {
  color: var(--m-color-danger);
  margin-left: var(--m-space-1);
}
.m-ship-optional {
  color: var(--m-color-text-tertiary);
  font-weight: var(--m-font-weight-regular);
  font-size: var(--m-font-size-tiny);
  margin-left: var(--m-space-1);
}

.m-ship-select-wrap {
  position: relative;
}
.m-ship-select {
  width: 100%;
  height: 42px;
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-lg);
  background: var(--m-color-bg-card);
  padding: 0 var(--m-space-8) 0 var(--m-space-3);
  font-size: var(--m-font-size-body);
  color: var(--m-color-text-primary);
  outline: none;
  appearance: none;
  -webkit-appearance: none;
  cursor: pointer;
}
.m-ship-select:focus {
  border-color: var(--m-color-primary);
}
.m-ship-select:disabled {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-disabled);
  cursor: not-allowed;
}
.m-ship-select-arrow {
  position: absolute;
  right: var(--m-space-3);
  top: 50%;
  transform: translateY(-50%);
  color: var(--m-color-text-tertiary);
  pointer-events: none;
}

.m-ship-input {
  width: 100%;
  height: 42px;
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-lg);
  padding: 0 var(--m-space-3);
  font-size: var(--m-font-size-body);
  color: var(--m-color-text-primary);
  background: var(--m-color-bg-card);
  outline: none;
  box-sizing: border-box;
  font-family: var(--m-font-family-mono);
}
.m-ship-input::placeholder {
  color: var(--m-color-text-placeholder);
  font-family: inherit;
}
.m-ship-input:focus {
  border-color: var(--m-color-primary);
}
.m-ship-input:disabled {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-disabled);
  cursor: not-allowed;
}

.m-ship-textarea {
  width: 100%;
  min-height: 80px;
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-2) var(--m-space-3);
  font-size: var(--m-font-size-body);
  color: var(--m-color-text-primary);
  background: var(--m-color-bg-card);
  outline: none;
  resize: vertical;
  box-sizing: border-box;
  font-family: inherit;
  line-height: var(--m-line-height-base);
}
.m-ship-textarea::placeholder {
  color: var(--m-color-text-placeholder);
}
.m-ship-textarea:focus {
  border-color: var(--m-color-primary);
}
.m-ship-textarea:disabled {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-disabled);
  cursor: not-allowed;
}

.m-ship-tip {
  display: flex;
  align-items: flex-start;
  gap: var(--m-space-1);
  margin: var(--m-space-2) var(--m-space-1) 0;
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
  line-height: var(--m-line-height-base);
}

.m-ship-footer {
  padding: var(--m-space-3) var(--m-space-4) var(--m-space-6);
  background: var(--m-color-bg-page);
  display: flex;
  gap: var(--m-space-2);
  flex-shrink: 0;
}
.m-ship-btn {
  flex: 1;
  height: 46px;
  border: none;
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-1);
  transition: all 0.15s;
  padding: 0;
}
.m-ship-btn:active:not(:disabled) {
  transform: scale(0.97);
}
.m-ship-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.m-ship-btn-cancel {
  flex: 1;
  background: var(--m-color-bg-card);
  color: var(--m-color-text-secondary);
  border: 1px solid var(--m-color-border);
}
.m-ship-btn-submit {
  flex: 2;
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
}

.m-ship-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: var(--m-color-text-inverse);
  border-radius: var(--m-radius-circle);
  animation: m-ship-spin 0.7s linear infinite;
  display: inline-block;
}
@keyframes m-ship-spin {
  to { transform: rotate(360deg); }
}
</style>
