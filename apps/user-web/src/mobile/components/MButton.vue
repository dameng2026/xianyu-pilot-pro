<template>
  <button
    class="m-btn"
    :class="btnClass"
    :disabled="disabled || loading"
    @click="handleClick"
  >
    <span v-if="loading" class="m-btn-loading"></span>
    <slot v-if="!loading" name="icon"></slot>
    <span class="m-btn-text"><slot /></span>
  </button>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  type: { type: String, default: 'secondary' },
  size: { type: String, default: 'md' },
  disabled: { type: Boolean, default: false },
  loading: { type: Boolean, default: false }
})

const emit = defineEmits(['click'])

const btnClass = computed(() => [
  `m-btn--${props.type}`,
  `m-btn--${props.size}`
])

function handleClick(e) {
  if (props.disabled || props.loading) return
  emit('click', e)
}
</script>

<style scoped>
.m-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px solid #e7edf7;
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s ease;
  white-space: nowrap;
  background: #fff;
  color: #365071;
  font-weight: 600;
  box-shadow: 0 2px 6px rgba(31, 53, 94, .03);
}

/* 尺寸 */
.m-btn--sm { 
  height: 32px; 
  padding: 0 12px; 
  font-size: 13px; 
  border-radius: 7px;
}
.m-btn--md { 
  height: 40px; 
  padding: 0 16px; 
  font-size: 14px; 
  border-radius: 8px;
}
.m-btn--lg { 
  height: 44px; 
  padding: 0 20px; 
  font-size: 15px; 
  border-radius: 8px;
  font-weight: 700;
}

/* 主按钮 - PC版蓝渐变+阴影 */
.m-btn--primary {
  background: linear-gradient(90deg, #0865f4, #147dff);
  border-color: #0865f4;
  color: #fff;
  box-shadow: 0 9px 18px rgba(13, 107, 255, .20);
}
.m-btn--primary:active { 
  transform: scale(0.96);
  opacity: 0.9;
}

/* 次要按钮 - 白底边框 */
.m-btn--secondary {
  background: #fff;
  color: #365071;
  border-color: #e7edf7;
}
.m-btn--secondary:active { 
  background: #f8fbff;
  transform: scale(0.98);
}

/* 边框按钮 */
.m-btn--outline {
  background: transparent;
  color: #365071;
  border-color: #e7edf7;
  box-shadow: none;
}
.m-btn--outline:active { 
  background: #f0f5ff; 
  transform: scale(0.98);
}

/* 危险按钮 */
.m-btn--danger {
  background: #fff8f8;
  color: #ef4444;
  border-color: #ffd6d6;
  box-shadow: none;
}
.m-btn--danger:active { 
  background: #fff0f1;
  transform: scale(0.98);
}

/* 警告按钮 */
.m-btn--warn {
  background: #fff8ea;
  color: #d97706;
  border-color: #ffe1b0;
  box-shadow: none;
}
.m-btn--warn:active {
  background: #fff5e6;
  transform: scale(0.98);
}

/* 成功按钮 */
.m-btn--success {
  background: #ecfff6;
  color: #0e9f6e;
  border-color: #c7f3df;
  box-shadow: none;
}
.m-btn--success:active {
  background: #e9fbf3;
  transform: scale(0.98);
}

/* 文字按钮 */
.m-btn--text {
  background: transparent;
  color: #0d6bff;
  border: none;
  padding: 0 8px;
  box-shadow: none;
}
.m-btn--text:active { 
  opacity: 0.7; 
}

/* 药丸按钮 */
.m-btn--pill {
  background: linear-gradient(90deg, #0865f4, #147dff);
  color: #fff;
  border-radius: 999px;
  border-color: #0865f4;
  box-shadow: 0 9px 18px rgba(13, 107, 255, .20);
}
.m-btn--pill:active { 
  transform: scale(0.96);
}

/* 状态 */
.m-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none !important;
}

.m-btn-loading {
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: m-btn-spin 0.8s linear infinite;
}

@keyframes m-btn-spin {
  to { transform: rotate(360deg); }
}
</style>
