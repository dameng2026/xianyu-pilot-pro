<template>
  <Teleport to="body">
    <div
      v-if="state.visible"
      class="global-confirm-mask"
      @click.self="handleMaskClick"
      @keydown="handleKeydown"
    >
      <section
        ref="dialogRef"
        class="global-confirm-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="global-confirm-title"
        :aria-describedby="state.description ? 'global-confirm-description' : undefined"
        tabindex="-1"
      >
        <button
          ref="closeRef"
          class="global-confirm-close"
          type="button"
          aria-label="关闭弹窗"
          @click="cancel"
        >
          <Icon name="close" />
        </button>

        <!-- 警告图标（仅 confirm/alert 类型） -->
        <div v-if="state.type !== 'prompt'" class="global-confirm-icon" :class="{ dangerous: state.dangerous }">
          <Icon :name="state.dangerous ? 'warning' : 'help'" />
        </div>

        <h2 id="global-confirm-title">{{ state.title }}</h2>

        <p v-if="state.description" id="global-confirm-description" class="global-confirm-desc">{{ state.description }}</p>

        <!-- prompt 输入框 -->
        <div v-if="state.type === 'prompt'" class="global-confirm-input-wrap">
          <input
            ref="inputRef"
            v-model="state.value"
            type="text"
            class="global-confirm-input"
            :placeholder="state.placeholder"
            :aria-label="state.placeholder || state.title"
            @keydown.enter="handlePromptEnter"
          />
        </div>

        <div class="global-confirm-actions">
          <AppButton v-if="state.type !== 'alert'" ref="cancelRef" @click="cancel">取消</AppButton>
          <AppButton
            ref="confirmRef"
            :type="confirmBtnType"
            @click="doConfirm"
          >
            {{ state.type === 'prompt' ? '确定' : (state.confirmText || '确认') }}
          </AppButton>
        </div>
      </section>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useConfirmState } from '../composables/confirmState.js'
import Icon from './Icon.vue'
import AppButton from './AppButton.vue'

const { state, cancel, doConfirm } = useConfirmState()
const dialogRef = ref(null)
const inputRef = ref(null)
const closeRef = ref(null)
const cancelRef = ref(null)
const confirmRef = ref(null)
let returnFocusTarget = null

const confirmBtnType = computed(() => {
  if (state.dangerous) return 'danger'
  return 'primary'
})

function handleMaskClick() {
  if (state.type !== 'alert') cancel()
}

function focusableElements() {
  if (!dialogRef.value) return []
  return [...dialogRef.value.querySelectorAll(
    'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href], [tabindex]:not([tabindex="-1"])'
  )].filter(element => !element.hasAttribute('hidden'))
}

function elementOf(target) {
  return target?.$el || target || null
}

function handlePromptEnter(event) {
  if (event.isComposing) return
  event.preventDefault()
  doConfirm()
}

function handleKeydown(event) {
  if (event.key === 'Escape') {
    event.preventDefault()
    cancel()
    return
  }
  if (event.key !== 'Tab') return

  const elements = focusableElements()
  if (elements.length === 0) {
    event.preventDefault()
    dialogRef.value?.focus()
    return
  }

  const first = elements[0]
  const last = elements[elements.length - 1]
  const activeElement = document.activeElement
  const focusIsOutsideSequence = activeElement === dialogRef.value || !dialogRef.value?.contains(activeElement)
  if (event.shiftKey && (activeElement === first || focusIsOutsideSequence)) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && (activeElement === last || focusIsOutsideSequence)) {
    event.preventDefault()
    first.focus()
  }
}

watch(
  () => state.visible,
  async visible => {
    if (visible) {
      if (!returnFocusTarget?.isConnected) {
        returnFocusTarget = document.activeElement
      }

      await nextTick()
      if (!state.visible) return

      const target = state.type === 'prompt'
        ? inputRef.value
        : state.dangerous
          ? elementOf(cancelRef.value) || elementOf(closeRef.value)
          : elementOf(confirmRef.value)
      target?.focus?.()
      return
    }

    await nextTick()
    // A queued request may already have opened another dialog. In that case,
    // keep the original focus target until the complete FIFO session closes.
    if (state.visible) return

    const target = returnFocusTarget
    returnFocusTarget = null
    if (target?.isConnected) target.focus?.()
  },
  { flush: 'post' }
)
</script>

<style scoped>
.global-confirm-mask {
  position: fixed;
  inset: 0;
  background: rgba(20, 36, 58, .58);
  backdrop-filter: blur(2px);
  z-index: 1001;
  display: flex;
  align-items: center;
  justify-content: center;
}

.global-confirm-modal {
  position: relative;
  width: 420px;
  background: #fff;
  border: 1px solid #e8eef8;
  border-radius: 18px;
  box-shadow: 0 28px 80px rgba(17, 35, 67, .25);
  padding: 40px 36px 28px;
  text-align: center;
  color: #18223d;
}

.global-confirm-close {
  position: absolute;
  right: 20px;
  top: 18px;
  width: 32px;
  height: 32px;
  border: 0;
  background: transparent;
  color: #35435d;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.global-confirm-close .ui-icon {
  width: 20px;
}

.global-confirm-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  margin: 0 auto 18px;
  border-radius: 50%;
  background: #f0f7ff;
}

.global-confirm-icon.dangerous {
  background: #fef2f2;
}

.global-confirm-icon .ui-icon {
  width: 32px;
  height: 32px;
}

.global-confirm-modal h2 {
  margin: 0 0 12px;
  font-size: 18px;
  font-weight: 700;
  color: #1e293b;
  text-align: center;
}

.global-confirm-desc {
  margin: 0 0 28px;
  font-size: 13px;
  line-height: 1.8;
  white-space: pre-wrap;
  color: #64748b;
  text-align: center;
}

.global-confirm-input-wrap {
  margin: 0 0 24px;
}

.global-confirm-input {
  width: 100%;
  height: 42px;
  padding: 0 14px;
  border: 1px solid #dce2ed;
  border-radius: 8px;
  font-size: 14px;
  color: #1e293b;
  outline: none;
  box-sizing: border-box;
  transition: border-color .2s;
}

.global-confirm-input:focus {
  border-color: #0865f4;
  box-shadow: 0 0 0 3px rgba(8, 101, 244, .1);
}

.global-confirm-input::placeholder {
  color: #94a3b8;
}

.global-confirm-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.global-confirm-actions .app-btn {
  min-width: 120px;
  height: 40px;
  font-size: 14px;
}
</style>
