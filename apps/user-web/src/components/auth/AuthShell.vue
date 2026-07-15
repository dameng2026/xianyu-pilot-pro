<template>
  <div :class="['auth-shell', `auth-shell-${pageKey}`]">
    <header class="auth-topbar">
      <button type="button" class="brand brand-image auth-brand" @click="emit('navigate', 'dashboard')">
        <img src="/xya/brand/brand_004.png" class="brand-logo" alt="XianYuAssistant" />
      </button>
      <button type="button" class="auth-lang-switch" disabled title="当前仅提供简体中文界面">
        <AuthIcon class="auth-lang-icon" name="globe" />
        <span>简体中文</span>
        <AuthIcon class="auth-lang-arrow" name="chevronDown" />
      </button>
    </header>

    <main class="auth-main">
      <section class="auth-showcase">
        <div class="auth-copy">
          <h1>
            <span class="auth-title-lead">{{ titleLead }}</span>
            <span v-if="titleAccent || titleTail" class="auth-title-group">
              <span class="auth-title-accent">{{ titleAccent }}</span>
              <span v-if="titleTail" class="auth-title-tail">{{ titleTail }}</span>
            </span>
          </h1>
          <p>{{ description }}</p>
        </div>

        <div :class="['auth-feature-row', `auth-feature-row--${features.length}`]">
          <div v-for="item in features" :key="item.title" class="auth-feature-card">
            <AuthIcon class="auth-feature-icon" :name="item.icon" />
            <div>
              <strong>{{ item.title }}</strong>
              <small>{{ item.desc }}</small>
            </div>
          </div>
        </div>

        <div :class="['auth-visual', visualKind === 'security' ? 'auth-visual-security' : 'auth-visual-dashboard']">
          <img
            v-for="item in visualLayers"
            :key="item.key"
            :class="['auth-visual-layer', item.className]"
            :src="item.src"
            alt=""
          />
          <div v-if="visualKind === 'dashboard'" class="auth-visual-floor-grid"></div>
        </div>

        <div class="auth-stats-card">
          <template v-for="(item, index) in stats" :key="item.value">
            <div class="auth-stat-item">
              <AuthIcon class="auth-stat-icon" :name="item.icon" />
              <div>
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
      <span>XianYuAssistant · {{ resolvedCopyrightYear }} 构建</span>
      <span v-if="legalConfig.icpLicense">{{ legalConfig.icpLicense }}</span>
      <button type="button" class="footer-link" :disabled="!legalConfig.privacyUrl" @click="openDoc('隐私政策')">
        {{ legalConfig.privacyUrl ? '隐私政策' : '隐私政策（未配置）' }}
      </button>
      <button type="button" class="footer-link" :disabled="!legalConfig.termsUrl" @click="openDoc('用户协议')">
        {{ legalConfig.termsUrl ? '用户协议' : '用户协议（未配置）' }}
      </button>
      <span v-if="!legalDocumentsAvailable" class="auth-footer-status" role="status">协议链接未配置</span>
    </footer>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import AuthIcon from './AuthIcon.vue'
import { dashboardVisualLayers, forgotFeatures, loginFeatures, openLegalDoc, registerFeatures, securityVisualLayers, authStats } from './authContent.js'
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

const featureMap = {
  login: loginFeatures,
  register: registerFeatures,
  forgot: forgotFeatures
}

const features = computed(() => props.features || featureMap[props.pageKey] || loginFeatures)
const visualLayers = computed(() => (props.visualKind === 'security' ? securityVisualLayers : dashboardVisualLayers))
const stats = computed(() => props.stats || authStats)

function openDoc(title) {
  return openLegalDoc(title)
}

defineExpose({
  openDoc
})
</script>
