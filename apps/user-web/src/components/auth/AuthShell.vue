<template>
  <div :class="['auth-shell', `auth-shell-${pageKey}`, { 'motion-complete': motionReady, 'motion-running': motionRunning }]">
    <header class="auth-topbar">
      <button type="button" class="auth-brand" @click="emit('navigate', 'dashboard')">
        <img src="/xya/brand/brand_004.png" class="auth-brand-mark" alt="XianYuAssistant" />
      </button>
    </header>

    <main class="auth-main">
      <section class="auth-showcase">
        <div class="auth-copy">
          <h1 class="auth-hero-title">
            <span class="auth-title-lead">{{ titleLead }}</span>
            <span v-if="titleAccent || titleTail" class="auth-title-group">
              <span v-if="titleAccent" class="auth-title-accent">{{ titleAccent }}</span>
              <span v-if="titleTail" class="auth-title-tail">{{ titleTail }}</span>
            </span>
          </h1>
          <p class="auth-hero-desc">{{ description }}</p>
        </div>

        <div :class="['auth-feature-row', `auth-feature-row--${features.length}`]">
          <div v-for="item in features" :key="item.title" class="auth-feature-card">
            <AuthIcon class="auth-feature-icon" :name="item.icon" />
            <div class="auth-feature-text">
              <strong>{{ item.title }}</strong>
              <small>{{ item.desc }}</small>
            </div>
          </div>
        </div>

        <div class="auth-visual" :class="visualKind === 'security' ? 'auth-visual-security' : 'auth-visual-dashboard'">
          <img
            class="auth-illustration"
            :class="illustrationMotionClass"
            :src="visualKind === 'security' ? '/xya/auth/hero-security.png' : '/xya/auth/hero-ops.png'"
            alt=""
            draggable="false"
          />
        </div>

        <div class="auth-stats-card">
          <template v-for="(item, index) in stats" :key="item.value">
            <div class="auth-stat-item">
              <AuthIcon class="auth-stat-icon" :name="item.icon" />
              <div class="auth-stat-copy">
                <strong>{{ item.value }}</strong>
                <small>{{ item.label }}</small>
              </div>
            </div>
            <div v-if="index < stats.length - 1" class="auth-stat-divider"></div>
          </template>
        </div>
      </section>

      <section class="auth-panel">
        <div class="auth-panel-inner">
          <slot />
        </div>
      </section>
    </main>

    <footer class="auth-footer">
      <span>© {{ resolvedCopyrightYear }} XianYuAssistant 闲鱼助手 版权所有</span>
      <span v-if="legalConfig.icpLicense">{{ legalConfig.icpLicense }}</span>
      <button type="button" class="auth-footer-link" :disabled="!legalConfig.privacyUrl" @click="openDoc('隐私政策')">
        {{ legalConfig.privacyUrl ? '隐私政策' : '隐私政策（未配置）' }}
      </button>
      <button type="button" class="auth-footer-link" :disabled="!legalConfig.termsUrl" @click="openDoc('用户协议')">
        {{ legalConfig.termsUrl ? '用户协议' : '用户协议（未配置）' }}
      </button>
      <span v-if="!legalDocumentsAvailable" class="auth-footer-status" role="status">协议链接未配置</span>
    </footer>
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import AuthIcon from './AuthIcon.vue'
import { forgotFeatures, loginFeatures, openLegalDoc, registerFeatures, authStats } from './authContent.js'
import { getCopyrightYear } from '../../utils/appMeta.js'
import { hasRequiredLegalDocuments, LEGAL_CONFIG } from '../../utils/legalConfig.js'

const props = defineProps({
  pageKey: { type: String, required: true },
  titleLead: { type: String, required: true },
  titleAccent: { type: String, default: '' },
  titleTail: { type: String, default: '' },
  description: { type: String, required: true },
  visualKind: { type: String, default: 'dashboard' },
  features: { type: Array, default: null },
  stats: { type: Array, default: null },
  copyrightYear: { type: [String, Number], default: null },
  legalDescription: { type: String, default: '' }
})

const emit = defineEmits(['navigate'])
const resolvedCopyrightYear = computed(() => `${props.copyrightYear ?? getCopyrightYear()}`)
const legalConfig = LEGAL_CONFIG
const legalDocumentsAvailable = hasRequiredLegalDocuments(legalConfig)
const motionReady = ref(false)
const motionRunning = ref(false)

const featureMap = {
  login: loginFeatures,
  register: registerFeatures,
  forgot: forgotFeatures
}

const features = computed(() => props.features || featureMap[props.pageKey] || loginFeatures)
const stats = computed(() => props.stats || authStats)

// 根据 pageKey 选择对应的浮动动画类（与原 HTML 设计稿一致）
const illustrationMotionClass = computed(() => {
  switch (props.pageKey) {
    case 'login':
      // 密码登录页用 opsFloat（visualKind=dashboard）
      return props.visualKind === 'security' ? 'motion-secure' : 'motion-float'
    case 'register':
      return 'motion-register'
    case 'forgot':
      return 'motion-secure'
    default:
      return 'motion-float'
  }
})

function openDoc(title) {
  return openLegalDoc(title)
}

let motionTimer = null
onMounted(() => {
  // 立即标记动画开始（用于触发入场动画）
  requestAnimationFrame(() => {
    motionRunning.value = true
  })
  // 1.8s 后标记入场完成（与原 HTML 设计稿一致），触发持续浮动动画
  // motion-running 与 motion-complete 互斥，避免入场动画与浮动动画冲突
  motionTimer = setTimeout(() => {
    motionRunning.value = false
    motionReady.value = true
  }, 1800)
})

onBeforeUnmount(() => {
  if (motionTimer) {
    clearTimeout(motionTimer)
    motionTimer = null
  }
})

defineExpose({
  openDoc
})
</script>
