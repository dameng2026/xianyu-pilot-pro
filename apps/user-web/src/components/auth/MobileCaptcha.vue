<template>
  <div :class="['mobile-auth-human-check', { 'is-verified': verified }]">
    <div class="mobile-auth-human-check-head">
      <span>安全验证</span>
      <small>{{ hint }}</small>
    </div>
    <div class="mobile-auth-human-check-body">
      <label class="mobile-auth-field mobile-auth-field--captcha">
        <span class="mobile-auth-field-icon"><AuthIcon name="shield" /></span>
        <input
          :value="modelValue"
          type="text"
          maxlength="4"
          inputmode="text"
          autocomplete="off"
          placeholder="请输入图形验证码"
          @input="onInput"
          @blur="emit('blur')"
        />
      </label>
      <button
        type="button"
        class="mobile-auth-captcha-chip"
        :class="{ 'is-refreshing': refreshing }"
        :aria-label="verified ? '已通过安全验证' : '点击刷新图形验证码'"
        @click="refresh"
      >
        {{ verified ? '已验证✓' : code }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import AuthIcon from './AuthIcon.vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  hint: { type: String, default: '完成图形验证后才会提交请求' }
})

const emit = defineEmits(['update:modelValue', 'blur'])

const CAPTCHA_ALPHABET = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'
const VERIFIED_TTL = 2 * 60 * 1000 // 2 分钟内有效

const code = ref('')
const verified = ref(false)
const refreshing = ref(false)
let verifiedUntil = 0
let verifiedTimer = null

function randomCaptcha() {
  return Array.from({ length: 4 }, () =>
    CAPTCHA_ALPHABET[Math.floor(Math.random() * CAPTCHA_ALPHABET.length)]
  ).join('')
}

function refresh() {
  code.value = randomCaptcha()
  verified.value = false
  verifiedUntil = 0
  refreshing.value = true
  // 触发刷新动画
  setTimeout(() => { refreshing.value = false }, 350)
  // 清空用户输入（验证码已变）
  if (props.modelValue) emit('update:modelValue', '')
}

function onInput(e) {
  const val = e.target.value.toUpperCase()
  emit('update:modelValue', val)
  // 输入满 4 位时自动校验
  if (val.length === 4) {
    if (val === code.value) {
      verified.value = true
      verifiedUntil = Date.now() + VERIFIED_TTL
      if (verifiedTimer) clearTimeout(verifiedTimer)
      verifiedTimer = setTimeout(() => {
        // 过期后自动刷新
        if (Date.now() >= verifiedUntil) refresh()
      }, VERIFIED_TTL)
    } else {
      // 输入错误，不自动刷新，让用户自行点击刷新
      verified.value = false
    }
  } else {
    verified.value = false
  }
}

// 供父组件调用：校验当前验证码是否已通过
function validate() {
  if (verified.value && verifiedUntil > Date.now()) return true
  const input = (props.modelValue || '').trim().toUpperCase()
  if (!input) return false
  if (input !== code.value) return false
  verified.value = true
  verifiedUntil = Date.now() + VERIFIED_TTL
  return true
}

// 供父组件调用：重置验证码
function reset() {
  refresh()
}

onMounted(() => {
  refresh()
})

onBeforeUnmount(() => {
  if (verifiedTimer) clearTimeout(verifiedTimer)
})

defineExpose({ validate, reset, verified })
</script>
