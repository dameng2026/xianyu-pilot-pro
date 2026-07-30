<template>
  <div :class="['mobile-auth-shell', `mobile-auth-${pageKey}`]" ref="shellRef">
    <div class="mobile-auth-stage" ref="stageRef">
      <div class="mobile-auth-canvas" ref="canvasRef">
        <img class="mobile-auth-bg-upper" src="/xya/auth/mobile-reference.png" alt="" aria-hidden="true" draggable="false" />
        <img class="mobile-auth-bg-lower" src="/xya/auth/mobile-clean-lower.png" alt="" aria-hidden="true" draggable="false" />

        <div class="mobile-auth-reveal-mask mask-brand" aria-hidden="true"></div>
        <div class="mobile-auth-reveal-mask mask-title" aria-hidden="true"></div>
        <div class="mobile-auth-reveal-mask mask-hero" aria-hidden="true"></div>
        <div class="mobile-auth-reveal-mask mask-section-title" aria-hidden="true"></div>
        <div class="mobile-auth-reveal-mask mask-card mask-card-1" aria-hidden="true"></div>
        <div class="mobile-auth-reveal-mask mask-card mask-card-2" aria-hidden="true"></div>
        <div class="mobile-auth-reveal-mask mask-card mask-card-3" aria-hidden="true"></div>
        <div class="mobile-auth-reveal-mask mask-card mask-card-4" aria-hidden="true"></div>

        <header class="mobile-auth-brand">
          <button type="button" class="mobile-auth-brand-btn" @click="emit('navigate', 'dashboard')">
            <img src="/xya/brand/brand_004.png" class="mobile-auth-brand-mark" alt="XianYuAssistant" />
          </button>
        </header>

        <section class="mobile-auth-card" aria-label="认证表单">
          <div
            v-if="showTabs"
            class="mobile-auth-tabs"
            role="tablist"
            aria-label="登录方式"
            :data-mode="tabsMode"
          >
            <button
              v-for="tab in tabs"
              :key="tab.key"
              type="button"
              role="tab"
              :class="['mobile-auth-tab', { 'is-active': activeTab === tab.key }]"
              :aria-selected="activeTab === tab.key"
              :disabled="tab.disabled"
              @click="emit('tab-change', tab.key)"
            >
              {{ tab.label }}
            </button>
            <span class="mobile-auth-tab-indicator" aria-hidden="true"></span>
          </div>

          <div v-if="heading" class="mobile-auth-heading">
            <h2>{{ heading }}</h2>
            <p v-if="subheading">{{ subheading }}</p>
          </div>

          <div class="mobile-auth-panel">
            <slot />
          </div>

          <div v-if="$slots['footer-actions']" class="mobile-auth-footer-actions">
            <slot name="footer-actions" />
          </div>
        </section>
      </div>
    </div>

    <footer class="mobile-auth-page-footer">
      <p>© {{ resolvedCopyrightYear }} 闲鱼助手 ・ <span v-if="legalConfig.icpLicense">{{ legalConfig.icpLicense }}</span></p>
    </footer>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { getCopyrightYear } from '../../utils/appMeta.js'
import { LEGAL_CONFIG } from '../../utils/legalConfig.js'

const props = defineProps({
  pageKey: { type: String, required: true },
  heroTitle: { type: String, default: '欢迎登录' },
  heroDesc: { type: String, default: '登录后进入工作台' },
  heading: { type: String, default: '' },
  subheading: { type: String, default: '' },
  showTabs: { type: Boolean, default: false },
  tabs: { type: Array, default: () => [] },
  activeTab: { type: String, default: '' },
  copyrightYear: { type: [String, Number], default: null }
})

const emit = defineEmits(['navigate', 'tab-change'])
const resolvedCopyrightYear = computed(() => `${props.copyrightYear ?? getCopyrightYear()}`)
const legalConfig = LEGAL_CONFIG

const DESIGN_WIDTH = 941
const DESIGN_HEIGHT = 1672

const shellRef = ref(null)
const stageRef = ref(null)
const canvasRef = ref(null)

// 根据视口宽高和 card 实际高度计算 scale，确保 canvas 完全可见且 card 不被裁剪
// - 测量 card 的实际高度，动态调整 canvas 高度
// - 取宽度和高度方向较小的 scale，保证 canvas 完全可见
// - 使用 layout viewport（document.documentElement.clientWidth/clientHeight）而非 visual
//   viewport（window.innerWidth/innerHeight），避免移动端键盘弹出时 visual viewport 缩小
//   导致 scale 减小、页面被缩成一团并出现大片空白
function fitCanvas() {
  const stage = stageRef.value
  const canvas = canvasRef.value
  if (!stage) return

  // 键盘弹出保护：当 visual viewport 明显小于 layout viewport 时（典型为软键盘弹出），
  // 跳过本次重算，保持原有 scale，避免页面被缩小。
  if (typeof window !== 'undefined' && window.visualViewport
          && document.documentElement) {
    const layoutH = document.documentElement.clientHeight
    if (layoutH > 0 && window.visualViewport.height < layoutH - 80) {
      return
    }
  }

  // 1. 测量 card 的实际高度，动态调整 canvas 高度
  //    不同页面（login/register/forgot-password）的 card 内容不同，高度不同
  //    需要确保 card 完全在 canvas 范围内，否则 card 底部按钮会被裁剪
  let canvasHeight = DESIGN_HEIGHT
  if (canvas) {
    const card = canvas.querySelector('.mobile-auth-card')
    if (card) {
      const cardTop = parseInt(getComputedStyle(card).top, 10) || 700
      const cardHeight = card.offsetHeight
      const cardBottom = cardTop + cardHeight
      // canvas 最小高度 = 设计稿高度 1672px；如果 card 超出，则扩展 canvas 高度
      canvasHeight = Math.max(DESIGN_HEIGHT, cardBottom + 20)
    }
    canvas.style.height = canvasHeight + 'px'
  }

  // 2. 计算 scale，使用 layout viewport 尺寸（键盘弹出时不变）
  const docEl = typeof document !== 'undefined' ? document.documentElement : null
  const rawVw = docEl ? docEl.clientWidth : DESIGN_WIDTH
  const rawVh = docEl ? docEl.clientHeight : DESIGN_HEIGHT
  const vw = rawVw > 0 ? rawVw : DESIGN_WIDTH
  const vh = rawVh > 0 ? rawVh : DESIGN_HEIGHT

  const scaleByWidth = vw / DESIGN_WIDTH
  const scaleByHeight = vh / canvasHeight
  const scale = Math.min(scaleByWidth, scaleByHeight)

  stage.style.setProperty('--mobile-auth-scale', String(scale))
  // 3. 设置 stage 高度 = canvas 高度 * scale
  stage.style.height = (canvasHeight * scale) + 'px'
}

const tabsMode = computed(() => {
  if (!props.tabs || !props.activeTab) return 'account'
  const first = props.tabs[0]?.key || 'account'
  return props.activeTab === first ? first : (props.tabs[1]?.key || 'email')
})

watch(() => [props.activeTab, props.tabs, props.heading, props.subheading], () => {
  nextTick(fitCanvas)
}, { deep: true })

let resizeObserver = null
function onResize() {
  fitCanvas()
}

onMounted(() => {
  nextTick(fitCanvas)
  if (typeof window !== 'undefined') {
    window.addEventListener('resize', onResize, { passive: true })
    window.addEventListener('orientationchange', onResize, { passive: true })
  }
  if (typeof ResizeObserver !== 'undefined' && stageRef.value) {
    resizeObserver = new ResizeObserver(() => fitCanvas())
    resizeObserver.observe(stageRef.value)
  }
})

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('resize', onResize)
    window.removeEventListener('orientationchange', onResize)
  }
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
})
</script>
