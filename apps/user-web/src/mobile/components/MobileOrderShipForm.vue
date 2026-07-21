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
  background: rgba(21, 33, 61, 0.5);
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
  background: #f8faff;
  border-radius: 24px 24px 0 0;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
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
  width: 40px;
  height: 4px;
  background: #dde5f0;
  border-radius: 2px;
  margin: 10px auto 0;
  flex-shrink: 0;
}

.m-ship-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px 6px;
  flex-shrink: 0;
}
.m-ship-header h3 {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  color: #15213d;
}
.m-ship-close {
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
.m-ship-close:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.m-ship-order-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 20px 10px;
  flex-shrink: 0;
}
.m-ship-order-id {
  font-size: 12px;
  color: #5a6a85;
  font-family: 'SF Mono', Monaco, monospace;
  background: #eef2f8;
  padding: 4px 10px;
  border-radius: 8px;
}
.m-ship-order-buyer {
  font-size: 12px;
  color: #8c98ae;
}

.m-ship-body {
  flex: 1;
  overflow-y: auto;
  padding: 0 16px 12px;
}

.m-ship-notice {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 12px;
  margin-bottom: 12px;
  line-height: 1.5;
}
.m-ship-notice.error {
  background: #fef2f2;
  color: #dc2626;
  border: 1px solid #fecaca;
}
.m-ship-notice.success {
  background: #ecfdf3;
  color: #059669;
  border: 1px solid #bbf7d0;
}

.m-ship-field {
  background: white;
  border-radius: 14px;
  padding: 12px 14px;
  margin-bottom: 10px;
  box-shadow: 0 1px 4px rgba(31, 53, 94, 0.04);
}
.m-ship-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #15213d;
  margin-bottom: 8px;
}
.m-ship-required {
  color: #ef4444;
  margin-left: 2px;
}
.m-ship-optional {
  color: #9aa6bd;
  font-weight: 400;
  font-size: 11px;
  margin-left: 2px;
}

.m-ship-select-wrap {
  position: relative;
}
.m-ship-select {
  width: 100%;
  height: 42px;
  border: 1px solid #e5e9f2;
  border-radius: 10px;
  background: #fff;
  padding: 0 36px 0 12px;
  font-size: 14px;
  color: #15213d;
  outline: none;
  appearance: none;
  -webkit-appearance: none;
  cursor: pointer;
}
.m-ship-select:focus {
  border-color: #93c5fd;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}
.m-ship-select:disabled {
  background: #f5f7fb;
  color: #9aa6bd;
  cursor: not-allowed;
}
.m-ship-select-arrow {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: #9aa6bd;
  pointer-events: none;
}

.m-ship-input {
  width: 100%;
  height: 42px;
  border: 1px solid #e5e9f2;
  border-radius: 10px;
  padding: 0 12px;
  font-size: 14px;
  color: #15213d;
  background: #fff;
  outline: none;
  box-sizing: border-box;
  font-family: 'SF Mono', Monaco, monospace;
}
.m-ship-input::placeholder {
  color: #aeb9ca;
  font-family: inherit;
}
.m-ship-input:focus {
  border-color: #93c5fd;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}
.m-ship-input:disabled {
  background: #f5f7fb;
  color: #9aa6bd;
  cursor: not-allowed;
}

.m-ship-textarea {
  width: 100%;
  min-height: 80px;
  border: 1px solid #e5e9f2;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 14px;
  color: #15213d;
  background: #fff;
  outline: none;
  resize: vertical;
  box-sizing: border-box;
  font-family: inherit;
  line-height: 1.5;
}
.m-ship-textarea::placeholder {
  color: #aeb9ca;
}
.m-ship-textarea:focus {
  border-color: #93c5fd;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}
.m-ship-textarea:disabled {
  background: #f5f7fb;
  color: #9aa6bd;
  cursor: not-allowed;
}

.m-ship-tip {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin: 8px 4px 0;
  font-size: 11px;
  color: #9aa6bd;
  line-height: 1.5;
}

.m-ship-footer {
  padding: 12px 16px 24px;
  background: #f8faff;
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}
.m-ship-btn {
  flex: 1;
  height: 46px;
  border: none;
  border-radius: 14px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
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
  background: white;
  color: #5a6a85;
  border: 1px solid #e5e9f2;
}
.m-ship-btn-submit {
  flex: 2;
  background: linear-gradient(135deg, #0d6bff, #3b82f6);
  color: white;
  box-shadow: 0 4px 12px rgba(13, 107, 255, 0.3);
}

.m-ship-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: m-ship-spin 0.7s linear infinite;
  display: inline-block;
}
@keyframes m-ship-spin {
  to { transform: rotate(360deg); }
}
</style>
