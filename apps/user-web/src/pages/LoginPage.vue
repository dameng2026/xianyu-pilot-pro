<template>
  <AuthShell
    v-if="!isMobile"
    page-key="login"
    title-lead="让闲鱼运营"
    title-accent="更简单、"
    title-tail="更智能"
    description="XianYuAssistant 闲鱼助手，专为闲鱼商家打造的智能化运营平台，助力商品管理、数据分析与自动化运营，提升效率，增长业绩。"
    legal-description="该页面用于说明 XianYuAssistant 登录、身份验证与账号安全相关规则。"
    @navigate="emit('navigate', $event)"
  >
    <nav class="auth-tabs auth-tabs-split" aria-label="登录方式">
      <button type="button" :class="{ active: tab === 'password' }" @click="switchTab('password')">密码登录</button>
      <button
        type="button"
        :class="{ active: tab === 'email' }"
        :title="emailLoginCapability.available ? '邮箱验证码登录' : emailLoginCapability.reason"
        @click="switchTab('email')"
      >
        邮箱验证码登录{{ emailLoginCapability.devOnly ? '（仅本地开发）' : '' }}
      </button>
    </nav>

    <div v-if="authCapabilityLoading" class="auth-capability-note" role="status">
      正在确认当前部署的登录能力，确认前所有提交入口保持关闭。
    </div>
    <div v-else-if="authCapabilityError" class="auth-capability-note unavailable" role="alert">
      <span>{{ authCapabilityError }}</span>
      <button type="button" class="auth-text-link" @click="refreshAuthCapabilities">重新检查</button>
    </div>
    <div v-else-if="!emailLoginCapability.available" class="auth-capability-note" role="status">
      {{ emailLoginCapability.reason }} {{ authCapabilities.supportMessage }}
    </div>
    <div v-else-if="emailLoginCapability.devOnly" class="auth-capability-note development" role="status">
      {{ authCapabilities.securityNotice }}
    </div>

    <div v-if="errorMsg" class="form-error" role="alert" aria-live="assertive">{{ errorMsg }}</div>

    <form class="auth-form" @submit.prevent="handleLogin">
      <template v-if="tab === 'password'">
        <label class="auth-field">
          <AuthIcon class="auth-field-icon" name="user" />
          <input
            v-model.trim="username"
            type="text"
            autocomplete="username"
            placeholder="手机号 / 账号"
          />
        </label>

        <label class="auth-field auth-field-with-action">
          <AuthIcon class="auth-field-icon" name="lock" />
          <input
            v-model="password"
            :type="showPwd ? 'text' : 'password'"
            autocomplete="current-password"
            placeholder="密码"
          />
          <button type="button" class="auth-eye-btn" @click="showPwd = !showPwd">
            <AuthIcon :name="showPwd ? 'eyeOff' : 'eye'" />
          </button>
        </label>

        <AuthCaptcha
          ref="pcPasswordCaptchaRef"
          v-model="pcPasswordCaptcha"
          hint="完成图形验证后才会提交登录请求"
        />
      </template>

      <template v-else>
        <label class="auth-field">
          <AuthIcon class="auth-field-icon" name="mail" />
          <input
            v-model.trim="email"
            type="email"
            autocomplete="email"
            placeholder="请输入邮箱"
          />
        </label>

        <AuthCaptcha
          ref="pcEmailCaptchaRef"
          v-model="pcEmailCaptcha"
          hint="验证通过后才可获取邮箱验证码"
        />

        <label class="auth-field auth-field-with-action">
          <AuthIcon class="auth-field-icon" name="code" />
          <input
            v-model.trim="emailCode"
            type="text"
            maxlength="6"
            autocomplete="one-time-code"
            placeholder="请输入邮箱验证码"
          />
          <button
            type="button"
            class="auth-inline-link auth-inline-link-boxed"
            :disabled="!emailLoginCapability.available || !isEmailValid || emailSending || emailCountdown > 0"
            :title="isEmailValid ? '获取邮箱验证码' : '请输入有效邮箱后获取验证码'"
            @click="sendEmail"
          >
            {{ emailSending ? '发送中...' : emailCountdown > 0 ? `${emailCountdown}s 后重试` : '获取验证码' }}
          </button>
        </label>
        <p class="auth-field-help">
          {{ emailLoginCapability.available
            ? (isEmailValid ? '邮箱格式有效，可以获取验证码。' : '请输入有效的邮箱后获取验证码。')
            : emailLoginCapability.reason }}
        </p>
      </template>

      <div class="auth-inline-row">
        <label class="auth-check">
          <input v-model="remember" type="checkbox" />
          <span>记住登录</span>
        </label>
        <button
          type="button"
          class="auth-inline-link"
          :title="passwordResetCapability.available ? '找回密码' : passwordResetCapability.reason"
          @click="emit('navigate', 'forgot-password')"
        >
          忘记密码？
        </button>
      </div>

      <button class="auth-submit" type="submit" :disabled="loading || authCapabilityLoading || !activeLoginCapability.available || !legalDocumentsAvailable">
        {{ loading ? '登录中...' : tab === 'password' ? '登录' : '立即登录' }}
      </button>
    </form>

    <div class="auth-divider">
      <span></span>
      <em>其他登录方式</em>
      <span></span>
    </div>

    <div class="auth-social-grid auth-social-grid--3">
      <button type="button" class="auth-social-btn" disabled aria-disabled="true" title="微信登录暂未开放">
        <AuthIcon class="auth-social-icon auth-social-icon-wechat" name="wechat" />
        <span>微信登录（暂未开放）</span>
      </button>
      <button type="button" class="auth-social-btn" disabled aria-disabled="true" title="QQ 登录暂未开放">
        <AuthIcon class="auth-social-icon auth-social-icon-qq" name="qq" />
        <span>QQ登录（暂未开放）</span>
      </button>
      <button
        type="button"
        class="auth-social-btn"
        :disabled="tab === 'password' && !emailLoginCapability.available"
        :title="tab === 'password' ? emailLoginCapability.reason : passwordLoginCapability.reason"
        @click="switchTab(tab === 'password' ? 'email' : 'password')"
      >
        <AuthIcon class="auth-social-icon" :name="tab === 'password' ? 'mail' : 'lock'" />
        <span>{{ tab === 'password' ? '邮箱验证码登录' : '密码登录' }}</span>
      </button>
    </div>

    <div class="auth-inline-center">
      <span>还没有账号？</span>
      <button
        type="button"
        class="auth-text-link auth-link-strong"
        :title="selfRegistrationCapability.available ? '注册新账号' : selfRegistrationCapability.reason"
        @click="emit('navigate', 'register')"
      >
        <span>立即注册</span>
        <AuthIcon class="auth-inline-icon" name="chevronRight" />
      </button>
    </div>

    <div class="auth-agreement">
      <label class="auth-check auth-check-agreement">
        <input v-model="agreed" type="checkbox" :disabled="!legalDocumentsAvailable" />
        <span>
          我已阅读并同意
          <button type="button" class="auth-text-link" :disabled="!legalConfig.termsUrl" @click="openDoc('用户协议')">《用户协议》</button>
          和
          <button type="button" class="auth-text-link" :disabled="!legalConfig.privacyUrl" @click="openDoc('隐私政策')">《隐私政策》</button>
        </span>
      </label>
      <p v-if="!legalDocumentsAvailable" class="auth-legal-unavailable" role="status">
        用户协议或隐私政策链接未配置，当前无法完成登录，请联系部署方。
      </p>
    </div>
  </AuthShell>

  <MobileAuthShell
    v-else
    page-key="login"
    :hero-title="mobileHeroTitle"
    :hero-desc="mobileHeroDesc"
    :heading="mobileHeading"
    :subheading="mobileSubheading"
    show-tabs
    :tabs="mobileTabs"
    :active-tab="tab"
    @navigate="emit('navigate', $event)"
    @tab-change="switchTab"
  >
    <div v-if="authCapabilityLoading" class="mobile-auth-capability-note" role="status">
      正在确认当前部署的登录能力...
    </div>
    <div v-else-if="authCapabilityError" class="mobile-auth-capability-note unavailable" role="alert">
      <span>{{ authCapabilityError }}</span>
      <button type="button" class="mobile-auth-text-link" @click="refreshAuthCapabilities">重新检查</button>
    </div>

    <div v-if="errorMsg" class="mobile-auth-form-error" role="alert" aria-live="assertive">{{ errorMsg }}</div>

    <form class="mobile-auth-form" @submit.prevent="handleLogin">
      <template v-if="tab === 'password'">
        <label class="mobile-auth-field">
          <span class="mobile-auth-field-icon"><AuthIcon name="user" /></span>
          <input
            v-model.trim="username"
            type="text"
            autocomplete="username"
            placeholder="请输入账号"
          />
        </label>

        <label class="mobile-auth-field">
          <span class="mobile-auth-field-icon"><AuthIcon name="lock" /></span>
          <input
            v-model="password"
            :type="showPwd ? 'text' : 'password'"
            autocomplete="current-password"
            placeholder="请输入密码"
          />
          <button type="button" class="mobile-auth-eye-btn" @click="showPwd = !showPwd">
            <AuthIcon :name="showPwd ? 'eyeOff' : 'eye'" />
          </button>
        </label>

        <MobileCaptcha
          ref="passwordCaptchaRef"
          v-model="passwordCaptcha"
          hint="完成图形验证后才会提交登录请求"
        />

        <div class="mobile-auth-form-links mobile-auth-form-links--right">
          <button
            type="button"
            class="mobile-auth-link-button"
            @click="emit('navigate', 'forgot-password')"
          >
            忘记密码？
          </button>
        </div>
      </template>

      <template v-else>
        <label class="mobile-auth-field">
          <span class="mobile-auth-field-icon"><AuthIcon name="mail" /></span>
          <input
            v-model.trim="email"
            type="email"
            autocomplete="email"
            placeholder="请输入邮箱"
          />
        </label>

        <MobileCaptcha
          ref="emailCaptchaRef"
          v-model="emailCaptcha"
          hint="验证通过后才可获取邮箱验证码"
        />

        <label class="mobile-auth-field mobile-auth-field--code">
          <span class="mobile-auth-field-icon"><AuthIcon name="code" /></span>
          <input
            v-model.trim="emailCode"
            type="text"
            maxlength="6"
            inputmode="numeric"
            autocomplete="one-time-code"
            placeholder="请输入邮箱验证码"
          />
          <button
            type="button"
            class="mobile-auth-code-button"
            :disabled="!isEmailValid || emailSending || emailCountdown > 0"
            @click="sendEmail"
          >
            {{ emailSending ? '发送中...' : emailCountdown > 0 ? `${emailCountdown}s 后重试` : '获取验证码' }}
          </button>
        </label>

        <div class="mobile-auth-form-links">
          <button
            type="button"
            class="mobile-auth-link-button"
            @click="emit('navigate', 'register')"
          >
            立即注册
          </button>
          <button
            type="button"
            class="mobile-auth-link-button"
            @click="emit('navigate', 'forgot-password')"
          >
            忘记密码？
          </button>
        </div>
      </template>

      <button
        class="mobile-auth-primary-button"
        type="submit"
        :disabled="loading || authCapabilityLoading"
      >
        {{ loading ? '登录中...' : '立即登录' }}
      </button>
    </form>

    <template #footer-actions>
      <div class="mobile-auth-divider"><span>还没有账号？</span></div>
      <button
        type="button"
        class="mobile-auth-secondary-button"
        :title="selfRegistrationCapability.available ? '注册新账号' : selfRegistrationCapability.reason"
        @click="emit('navigate', 'register')"
      >
        立即注册
      </button>
    </template>
  </MobileAuthShell>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { login, sendEmailCode } from '../api/auth.js'
import AuthIcon from '../components/auth/AuthIcon.vue'
import AuthCaptcha from '../components/auth/AuthCaptcha.vue'
import AuthShell from '../components/auth/AuthShell.vue'
import MobileAuthShell from '../components/auth/MobileAuthShell.vue'
import MobileCaptcha from '../components/auth/MobileCaptcha.vue'
import { friendlyError } from '../utils/friendlyError.js'
import { openLegalDoc } from '../components/auth/authContent.js'
import { hasRequiredLegalDocuments, LEGAL_CONFIG } from '../utils/legalConfig.js'
import { useAuthCapabilities } from '../utils/useAuthCapabilities.js'

const emit = defineEmits(['navigate', 'login-success'])

const {
  authCapabilities,
  authCapabilityLoading,
  authCapabilityError,
  refreshAuthCapabilities,
} = useAuthCapabilities()
const passwordLoginCapability = computed(() => authCapabilities.value.passwordLogin)
const emailLoginCapability = computed(() => authCapabilities.value.emailVerification)
const selfRegistrationCapability = computed(() => authCapabilities.value.selfRegistration)
const passwordResetCapability = computed(() => authCapabilities.value.passwordReset)
const activeLoginCapability = computed(() => tab.value === 'email'
  ? emailLoginCapability.value
  : passwordLoginCapability.value)

const tab = ref('password')
const username = ref('')
const password = ref('')
const email = ref('')
const emailCode = ref('')
const showPwd = ref(false)
const remember = ref(true)
const agreed = ref(false)
const loading = ref(false)
const errorMsg = ref('')
const emailSending = ref(false)
const emailCountdown = ref(0)
const isEmailValid = computed(() => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim()))
const legalConfig = LEGAL_CONFIG
const legalDocumentsAvailable = hasRequiredLegalDocuments(legalConfig)
let emailTimer = null

// 移动端图形验证码
const passwordCaptchaRef = ref(null)
const emailCaptchaRef = ref(null)
const passwordCaptcha = ref('')
const emailCaptcha = ref('')

// PC 端图形验证码
const pcPasswordCaptchaRef = ref(null)
const pcEmailCaptchaRef = ref(null)
const pcPasswordCaptcha = ref('')
const pcEmailCaptcha = ref('')

// 移动端检测
const isMobile = ref(false)
function updateMobileDetection() {
  isMobile.value = window.matchMedia?.('(max-width: 900px)').matches || /Mobi|Android|iPhone|iPad|iPod/i.test(navigator.userAgent)
}

const mobileHeroTitle = computed(() => tab.value === 'password' ? '欢迎登录' : '邮箱登录')
const mobileHeroDesc = computed(() => tab.value === 'password' ? '登录后进入工作台' : '输入邮箱并完成安全验证')
const mobileHeading = computed(() => tab.value === 'password' ? '欢迎登录' : '邮箱登录')
const mobileSubheading = computed(() => tab.value === 'password' ? '登录后进入工作台' : '输入邮箱并完成安全验证')
const mobileTabs = computed(() => [
  { key: 'password', label: '账号登录' },
  { key: 'email', label: '邮箱登录' }
])

function openDoc(title) {
  const result = openLegalDoc(title)
  if (!result.opened) errorMsg.value = result.message
}

function ensureAgreed() {
  if (!legalDocumentsAvailable) {
    errorMsg.value = '用户协议或隐私政策链接未配置，当前无法完成登录'
    return false
  }
  if (!agreed.value) {
    errorMsg.value = '请先阅读并同意用户协议和隐私政策'
    return false
  }
  return true
}

function switchTab(nextTab) {
  // 允许自由切换 tab，仅作为视图切换；表单提交时才校验能力
  tab.value = nextTab
  errorMsg.value = ''
}

async function handleLogin() {
  if (loading.value) return
  errorMsg.value = ''

  if (!activeLoginCapability.value.available) return

  if (!ensureAgreed()) return

  if (tab.value === 'password') {
    if (!username.value.trim()) {
      errorMsg.value = '请输入邮箱或账号'
      return
    }
    if (!password.value) {
      errorMsg.value = '请输入密码'
      return
    }
    // 图形验证码校验（PC + 移动端）
    const captchaRef = isMobile.value ? passwordCaptchaRef.value : pcPasswordCaptchaRef.value
    if (captchaRef && !captchaRef.validate()) {
      errorMsg.value = '请先完成图形验证'
      return
    }
  } else {
    if (!emailLoginCapability.value.available) return
    if (!isEmailValid.value) {
      errorMsg.value = '请输入正确的邮箱'
      return
    }
    if (!emailCode.value.trim()) {
      errorMsg.value = '请输入邮箱验证码'
      return
    }
    // 图形验证码校验（PC + 移动端）
    const captchaRef = isMobile.value ? emailCaptchaRef.value : pcEmailCaptchaRef.value
    if (captchaRef && !captchaRef.validate()) {
      errorMsg.value = '请先完成图形验证'
      return
    }
  }

  loading.value = true
  try {
    const payload = tab.value === 'password'
      ? { username: username.value.trim(), password: password.value }
      : { email: email.value.trim(), emailCode: emailCode.value.trim() }

    const res = await login(payload)
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data) || !String(data.token || '').trim()) {
      throw new Error('登录响应缺少有效凭证，请稍后重试')
    }
    emit('login-success', data)
  } catch (error) {
    errorMsg.value = friendlyError(error, '登录失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

async function sendEmail() {
  if (emailSending.value || emailCountdown.value > 0) return
  errorMsg.value = ''

  // 仅在用户点击「获取验证码」时校验后端 capability，避免阻塞表单显示
  if (!emailLoginCapability.value.available) {
    errorMsg.value = emailLoginCapability.value.reason || '邮箱验证码服务暂不可用'
    return
  }

  if (!isEmailValid.value) {
    errorMsg.value = '请先输入正确邮箱'
    return
  }

  // 图形验证码校验（PC + 移动端）
  const captchaRef = isMobile.value ? emailCaptchaRef.value : pcEmailCaptchaRef.value
  if (captchaRef && !captchaRef.validate()) {
    errorMsg.value = '请先完成图形验证'
    return
  }

  emailSending.value = true
  try {
    const response = await sendEmailCode({ email: email.value.trim() })
    if (emailLoginCapability.value.devOnly && response?.data?.devCode) emailCode.value = response.data.devCode
    emailCountdown.value = 60
    if (emailTimer) clearInterval(emailTimer)
    emailTimer = setInterval(() => {
      emailCountdown.value -= 1
      if (emailCountdown.value <= 0) {
        clearInterval(emailTimer)
        emailTimer = null
        emailCountdown.value = 0
      }
    }, 1000)
  } catch (error) {
    errorMsg.value = friendlyError(error, '验证码发送失败，请稍后重试')
  } finally {
    emailSending.value = false
  }
}

onMounted(() => {
  refreshAuthCapabilities()
  updateMobileDetection()
  window.addEventListener('resize', updateMobileDetection, { passive: true })
})

onUnmounted(() => {
  if (emailTimer) clearInterval(emailTimer)
  window.removeEventListener('resize', updateMobileDetection)
})
</script>
