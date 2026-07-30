<template>
  <Teleport to="body">
    <Transition name="m-ship-fade">
      <div v-if="visible" class="m-ship-mask" @click.self="handleClose">
        <Transition name="m-ship-slide">
          <div v-if="visible" class="m-ship-sheet" role="dialog" aria-modal="true">
            <div class="m-ship-handle"></div>

            <div class="m-ship-header">
              <h3>订单手动发货</h3>
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

              <!-- 发货来源切换 -->
              <div class="m-ship-field">
                <label class="m-ship-label">
                  发货来源
                  <span class="m-ship-required">*</span>
                </label>
                <div class="m-ship-tabs">
                  <button
                    type="button"
                    :class="['m-ship-tab', { active: form.deliverySource === 'custom' }]"
                    :disabled="submitting"
                    @click="switchSource('custom')"
                  >
                    自定义文本发货
                  </button>
                  <button
                    type="button"
                    :class="['m-ship-tab', { active: form.deliverySource === 'library' }]"
                    :disabled="submitting"
                    @click="switchSource('library')"
                  >
                    货源库发货
                  </button>
                </div>
              </div>

              <!-- 触发时机 -->
              <div class="m-ship-field">
                <label class="m-ship-label">
                  触发时机
                  <span class="m-ship-required">*</span>
                </label>
                <div class="m-ship-select-wrap">
                  <select v-model="form.deliveryTiming" class="m-ship-select" :disabled="submitting">
                    <option value="after_payment">付款后</option>
                    <option value="after_receipt">确认收货后</option>
                    <option value="after_review">评价后</option>
                  </select>
                  <MIcon name="chevronDown" :size="16" class="m-ship-select-arrow" />
                </div>
              </div>

              <!-- 发货数量 -->
              <div class="m-ship-field">
                <label class="m-ship-label">
                  发货数量
                  <span class="m-ship-required">*</span>
                </label>
                <input
                  v-model.number="form.quantityRequested"
                  type="number"
                  class="m-ship-input"
                  placeholder="请输入发货数量"
                  :disabled="submitting"
                  min="1"
                  autocomplete="off"
                />
              </div>

              <!-- 货源库发货：选择货源 -->
              <template v-if="form.deliverySource === 'library'">
                <div class="m-ship-field">
                  <label class="m-ship-label">
                    选择货源
                    <span class="m-ship-required">*</span>
                  </label>
                  <div v-if="sourcesLoading" class="m-ship-hint">货源加载中...</div>
                  <div v-else-if="sourcesLoadError" class="m-ship-hint m-ship-hint-error">
                    {{ sourcesLoadError }}
                  </div>
                  <div v-else>
                    <div class="m-ship-select-wrap">
                      <select v-model="form.sourceId" class="m-ship-select" :disabled="submitting" @change="onSourceSelect">
                        <option :value="null">请选择货源</option>
                        <option
                          v-for="src in deliverySources"
                          :key="src.id"
                          :value="src.id"
                          :disabled="isSourceDisabled(src)"
                        >
                          {{ sourceOptionLabel(src) }}
                        </option>
                      </select>
                      <MIcon name="chevronDown" :size="16" class="m-ship-select-arrow" />
                    </div>
                    <div v-if="selectedSource" class="m-ship-source-preview">
                      <div class="m-ship-source-row">
                        <span class="m-ship-source-label">发货方式：</span>
                        <span class="m-ship-source-value">{{ selectedSource.deliveryMode === 'card' ? '卡密发货' : '文本发货' }}</span>
                      </div>
                      <div v-if="selectedSource.deliveryMode === 'card'" class="m-ship-source-row">
                        <span class="m-ship-source-label">卡密库存：</span>
                        <span :class="['m-ship-source-value', { 'm-ship-hint-error': (selectedSource.cardRemainCount ?? 0) <= 0 }]">
                          剩余 {{ selectedSource.cardRemainCount ?? 0 }} 张
                          <span v-if="(selectedSource.cardRemainCount ?? 0) <= 0">（库存不足，无法发货）</span>
                        </span>
                      </div>
                      <div class="m-ship-source-row">
                        <span class="m-ship-source-label">货源内容：</span>
                        <span class="m-ship-source-value m-ship-source-content">{{ selectedSource.content || '（空）' }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </template>

              <!-- 自定义文本发货：发货内容 -->
              <template v-else>
                <div class="m-ship-field">
                  <label class="m-ship-label">
                    发货内容
                    <span class="m-ship-required">*</span>
                  </label>
                  <textarea
                    v-model.trim="form.deliveryContent"
                    class="m-ship-textarea"
                    placeholder="请输入发货文本、卡密内容或下载链接"
                    :disabled="submitting"
                    rows="5"
                    maxlength="2000"
                  ></textarea>
                </div>
              </template>

              <p class="m-ship-tip">
                <MIcon name="info" :size="12" />
                <span v-if="form.deliverySource === 'library'">
                  选中货源后由系统自动填充发货内容，卡密发货将自动从绑定卡密组认领一张并标记为已使用
                </span>
                <span v-else>提交后将以下发文本消息方式推送给买家，可在订单消息中查看</span>
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
import { getDeliverySources } from '../../api/autoDelivery.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  order: { type: Object, default: null }
})
const emit = defineEmits(['close', 'success'])

const form = reactive({
  // 'custom' = 自定义文本发货；'library' = 货源库发货
  deliverySource: 'custom',
  deliveryTiming: 'after_payment',
  deliveryContent: '',
  quantityRequested: 1,
  sourceId: null
})
const submitting = ref(false)
const errorMsg = ref('')
const successMsg = ref('')

// 货源库数据
const deliverySources = ref([])
const sourcesLoading = ref(false)
const sourcesLoadError = ref('')
const sourcesLoaded = ref(false)

const selectedSource = computed(() => {
  const id = Number(form.sourceId)
  if (!Number.isFinite(id) || id <= 0) return null
  return deliverySources.value.find(s => Number(s.id) === id) || null
})

const canSubmit = computed(() => {
  if (submitting.value) return false
  if (form.deliverySource === 'library') {
    const src = selectedSource.value
    if (!src) return false
    // 卡密发货库存不足时禁用提交
    if (src.deliveryMode === 'card' && Number(src.cardRemainCount ?? 0) <= 0) return false
    return true
  }
  // 自定义文本发货
  return !!(form.deliveryContent && form.deliveryContent.trim())
})

watch(() => props.visible, value => {
  if (value) {
    form.deliverySource = 'custom'
    form.deliveryTiming = 'after_payment'
    form.deliveryContent = ''
    form.quantityRequested = Number(props.order?.quantityRequested ?? props.order?.quantityTotal ?? 1) || 1
    form.sourceId = null
    errorMsg.value = ''
    successMsg.value = ''
    submitting.value = false
    // 不在此处预加载货源库，避免无谓请求；用户切换到"货源库发货"时再加载
  }
})

function switchSource(target) {
  if (form.deliverySource === target) return
  form.deliverySource = target
  form.sourceId = null
  errorMsg.value = ''
  if (target === 'library') {
    loadDeliverySourcesIfNeeded()
  }
}

function sourceOptionLabel(src) {
  const mode = src.deliveryMode === 'card' ? '卡密' : '文本'
  const title = src.title || `货源#${src.id}`
  if (src.deliveryMode === 'card') {
    const remain = Number(src.cardRemainCount ?? 0)
    return `${title}（${mode}，剩余 ${remain}）`
  }
  return `${title}（${mode}）`
}

function isSourceDisabled(src) {
  // 卡密发货且库存为 0 时禁用
  return src.deliveryMode === 'card' && Number(src.cardRemainCount ?? 0) <= 0
}

async function loadDeliverySourcesIfNeeded() {
  if (sourcesLoaded.value || sourcesLoading.value) return
  sourcesLoading.value = true
  sourcesLoadError.value = ''
  try {
    const res = await getDeliverySources({ current: 1, size: 200 })
    const data = res?.data
    const list = Array.isArray(data)
      ? data
      : (data && Array.isArray(data.records) ? data.records : [])
    deliverySources.value = list
    sourcesLoaded.value = true
  } catch (e) {
    deliverySources.value = []
    sourcesLoadError.value = e?.message || '货源库加载失败'
  } finally {
    sourcesLoading.value = false
  }
}

function onSourceSelect() {
  // 选择货源后清空错误提示，由后端推断发货内容
  errorMsg.value = ''
}

function handleClose() {
  if (submitting.value) return
  emit('close')
}

function buildPayload() {
  const qty = Math.max(Number(form.quantityRequested) || 1, 1)
  const payload = {
    deliveryTiming: String(form.deliveryTiming || 'after_payment').trim() || 'after_payment',
    quantityRequested: qty
  }
  if (form.deliverySource === 'library') {
    const id = Number(form.sourceId)
    if (Number.isFinite(id) && id > 0) {
      payload.sourceId = id
      return payload
    }
    return null
  }
  payload.deliveryMode = 'text'
  payload.deliveryContent = String(form.deliveryContent || '').trim()
  return payload
}

async function handleSubmit() {
  if (!props.order?.id) {
    errorMsg.value = '订单信息缺失，无法发货'
    return
  }

  // 货源库发货模式下的前置校验
  if (form.deliverySource === 'library') {
    const src = selectedSource.value
    if (!src) {
      errorMsg.value = '请先选择货源'
      return
    }
    if (src.deliveryMode === 'card' && Number(src.cardRemainCount ?? 0) <= 0) {
      errorMsg.value = `货源「${src.title || src.id}」卡密库存不足，无法发货。请先在卡密仓库补充库存后重试。`
      return
    }
  }

  const payload = buildPayload()
  if (!payload) {
    errorMsg.value = form.deliverySource === 'library' ? '请先选择货源' : '请填写发货内容'
    return
  }
  if (form.deliverySource === 'custom' && !payload.deliveryContent) {
    errorMsg.value = '请填写发货内容'
    return
  }

  submitting.value = true
  errorMsg.value = ''
  successMsg.value = ''
  try {
    await manualDeliverOrder(props.order.id, payload)
    successMsg.value = '发货任务已提交'
    // 货源库发货后刷新货源列表以反映最新卡密库存
    if (form.deliverySource === 'library') {
      sourcesLoaded.value = false
    }
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
  border-radius: var(--m-radius-xl) var(--m-radius-xl) 0 0;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--m-shadow-xs);
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
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-3) var(--m-space-4);
  margin-bottom: var(--m-space-2);
  box-shadow: var(--m-shadow-xs);
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

.m-ship-tabs {
  display: flex;
  gap: var(--m-space-2);
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-1);
}
.m-ship-tab {
  flex: 1;
  height: 38px;
  border: none;
  background: transparent;
  border-radius: var(--m-radius-md);
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-secondary);
  cursor: pointer;
  transition: all 0.15s;
  padding: 0;
}
.m-ship-tab.active {
  background: var(--m-color-bg-card);
  color: var(--m-color-primary);
  box-shadow: var(--m-shadow-card);
}
.m-ship-tab:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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
  min-height: 120px;
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

.m-ship-hint {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  padding: var(--m-space-2) var(--m-space-1);
}
.m-ship-hint-error {
  color: var(--m-color-danger-text);
}

.m-ship-source-preview {
  margin-top: var(--m-space-2);
  padding: var(--m-space-2) var(--m-space-3);
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-md);
  display: flex;
  flex-direction: column;
  gap: var(--m-space-1);
}
.m-ship-source-row {
  display: flex;
  align-items: flex-start;
  gap: var(--m-space-1);
  font-size: var(--m-font-size-caption);
  line-height: var(--m-line-height-base);
}
.m-ship-source-label {
  color: var(--m-color-text-tertiary);
  flex-shrink: 0;
  min-width: 64px;
}
.m-ship-source-value {
  color: var(--m-color-text-primary);
  flex: 1;
  word-break: break-all;
}
.m-ship-source-content {
  color: var(--m-color-text-secondary);
  white-space: pre-wrap;
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
