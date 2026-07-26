<template>
  <AuthShell
    v-if="!isMobile"
    page-key="register"
    title-lead="快速注册，"
    title-accent="开启智能运营"
    description="XianYuAssistant 闲鱼助手，专为闲鱼商家打造的智能化运营平台，助力商品管理、数据分析与自动化运营，提升效率，增长业绩。"
    legal-description="该页面用于说明 XianYuAssistant 注册、邮箱校验与账号创建相关规则。"
    @navigate="emit('navigate', $event)"
  >
    <div class="auth-panel-heading auth-panel-heading-tabs">
      <div class="auth-tabs auth-tabs-split">
        <button type="button" class="active">立即注册</button>
        <button type="button" @click="emit('navigate', 'login')">已有账号？去登录</button>
      </div>
    </div>

    <div v-if="errorMsg" ref="errorMsgRef" class="form-error" role="alert" aria-live="assertive">{{ errorMsg }}</div>

    <div v-if="authCapabilityLoading" class="auth-capability-note" role="status">
      正在确认注册能力...
    </div>
    <div v-else-if="selfRegistrationCapability.devOnly" class="auth-capability-note development" role="status">
      {{ authCapabilities.securityNotice }}
    </div>

    <form class="auth-form" @submit.prevent="submitRegister">
        <label class="auth-field auth-field-with-action" :class="{ 'has-error': fieldErrors.email }">
          <AuthIcon class="auth-field-icon" name="mail" />
          <input
            v-model.trim="form.email"
            type="email"
            autocomplete="email"
            placeholder="邮箱"
            aria-invalid="!!fieldErrors.email"
            @blur="blurEmail"
          />
          <button v-if="form.email" type="button" class="auth-clear-btn" @click="form.email = ''">
            <AuthIcon name="close" />
          </button>
        </label>
        <span v-if="fieldErrors.email" class="auth-field-error">{{ fieldErrors.email }}</span>

        <AuthCaptcha
          ref="pcRegisterCaptchaRef"
          v-model="pcRegisterCaptcha"
          hint="验证通过后才可获取注册验证码"
        />

        <label class="auth-field auth-field-with-action" :class="{ 'has-error': fieldErrors.emailCode }">
          <AuthIcon class="auth-field-icon" name="code" />
          <input
            v-model.trim="form.emailCode"
            type="text"
            maxlength="6"
            autocomplete="one-time-code"
            placeholder="邮箱验证码"
            aria-invalid="!!fieldErrors.emailCode"
            @blur="blurEmailCode"
          />
          <button
            type="button"
            class="auth-inline-link auth-inline-link-boxed"
            :disabled="!emailLoginCapability.available || !emailValid || emailSending || emailCountdown > 0"
            aria-label="获取注册邮箱验证码"
            :title="emailValid ? '获取邮箱验证码' : '请输入有效邮箱后获取验证码'"
            @click="sendEmail"
          >
            {{ emailSending ? '发送中...' : emailCountdown > 0 ? `${emailCountdown}s 后重试` : '获取验证码' }}
          </button>
        </label>
        <span v-if="fieldErrors.emailCode" class="auth-field-error">{{ fieldErrors.emailCode }}</span>

        <label class="auth-field auth-field-with-action" :class="{ 'has-error': fieldErrors.password }">
          <AuthIcon class="auth-field-icon" name="lock" />
          <input
            v-model="form.password"
            :type="showPwd ? 'text' : 'password'"
            maxlength="32"
            autocomplete="new-password"
            placeholder="设置密码（8-32位，字母+数字组合）"
            aria-invalid="!!fieldErrors.password"
            @blur="blurPassword"
          />
          <button type="button" class="auth-eye-btn" @click="showPwd = !showPwd">
            <AuthIcon :name="showPwd ? 'eyeOff' : 'eye'" />
          </button>
        </label>
        <span v-if="fieldErrors.password" class="auth-field-error">{{ fieldErrors.password }}</span>

        <label class="auth-field auth-field-with-action" :class="{ 'has-error': fieldErrors.confirmPassword }">
          <AuthIcon class="auth-field-icon" name="lock" />
          <input
            v-model="form.confirmPassword"
            :type="showConfirmPwd ? 'text' : 'password'"
            maxlength="32"
            autocomplete="new-password"
            placeholder="确认密码"
            aria-invalid="!!fieldErrors.confirmPassword"
            @blur="blurConfirmPassword"
          />
          <button type="button" class="auth-eye-btn" @click="showConfirmPwd = !showConfirmPwd">
            <AuthIcon :name="showConfirmPwd ? 'eyeOff' : 'eye'" />
          </button>
        </label>
        <span v-if="fieldErrors.confirmPassword" class="auth-field-error">{{ fieldErrors.confirmPassword }}</span>

        <label class="auth-field">
          <AuthIcon class="auth-field-icon" name="user" />
          <input
            v-model.trim="form.inviteCode"
            type="text"
            maxlength="40"
            placeholder="邀请码（可选）"
          />
        </label>

        <div class="auth-agreement">
          <label class="auth-check auth-check-register auth-check-agreement" :class="{ 'has-error': fieldErrors.agreed }">
            <input v-model="form.agreed" type="checkbox" :disabled="!legalDocumentsAvailable" @change="blurAgreed" />
            <span>
              我已阅读并同意
              <button type="button" class="auth-text-link" :disabled="!legalConfig.termsUrl" @click="openDoc('用户协议')">《用户协议》</button>
              和
              <button type="button" class="auth-text-link" :disabled="!legalConfig.privacyUrl" @click="openDoc('隐私政策')">《隐私政策》</button>
            </span>
          </label>
          <span v-if="fieldErrors.agreed" class="auth-field-error">{{ fieldErrors.agreed }}</span>
          <p v-if="!legalDocumentsAvailable" class="auth-legal-unavailable" role="status">
            用户协议或隐私政策链接未配置，当前无法完成注册，请联系部署方。
          </p>
        </div>

        <button class="auth-submit" type="submit" :disabled="loading || !legalDocumentsAvailable">
          {{ loading ? '注册中...' : '立即注册' }}
        </button>
      </form>

      <div class="auth-divider">
        <span></span>
        <em>其他注册方式</em>
        <span></span>
      </div>

      <div class="auth-social-grid auth-social-grid--3">
        <button type="button" class="auth-social-btn" disabled aria-disabled="true" title="微信注册暂未开放">
          <AuthIcon class="auth-social-icon auth-social-icon-wechat" name="wechat" />
          <span>微信注册（暂未开放）</span>
        </button>
        <button type="button" class="auth-social-btn" disabled aria-disabled="true" title="QQ 注册暂未开放">
          <AuthIcon class="auth-social-icon auth-social-icon-qq" name="qq" />
          <span>QQ注册（暂未开放）</span>
        </button>
        <button type="button" class="auth-social-btn" @click="emit('navigate', 'login')">
          <AuthIcon class="auth-social-icon" name="lock" />
          <span>密码登录</span>
        </button>
      </div>
  </AuthShell>

  <MobileAuthShell
    v-else
    page-key="register"
    :hero-title="mobileHeroTitle"
    :hero-desc="mobileHeroDesc"
    :heading="mobileHeading"
    :subheading="mobileSubheading"
    @navigate="emit('navigate', $event)"
  >
    <div v-if="errorMsg" class="mobile-auth-form-error" role="alert" aria-live="assertive">{{ errorMsg }}</div>

    <div v-if="authCapabilityLoading" class="mobile-auth-capability-note" role="status">
      正在确认注册能力...
    </div>
    <div v-else-if="selfRegistrationCapability.devOnly" class="mobile-auth-capability-note development" role="status">
      {{ authCapabilities.securityNotice }}
    </div>

    <form class="mobile-auth-form" @submit.prevent="submitRegister">
        <label class="mobile-auth-field">
          <span class="mobile-auth-field-icon"><AuthIcon name="mail" /></span>
          <input
            v-model.trim="form.email"
            type="email"
            autocomplete="email"
            placeholder="请输入邮箱"
          />
        </label>

        <MobileCaptcha
          ref="registerCaptchaRef"
          v-model="registerCaptcha"
          hint="验证通过后才可获取注册验证码"
        />

        <label class="mobile-auth-field mobile-auth-field--code">
          <span class="mobile-auth-field-icon"><AuthIcon name="code" /></span>
          <input
            v-model.trim="form.emailCode"
            type="text"
            maxlength="6"
            inputmode="numeric"
            autocomplete="one-time-code"
            placeholder="请输入邮箱验证码"
          />
          <button
            type="button"
            class="mobile-auth-code-button"
            :disabled="!emailValid || emailSending || emailCountdown > 0"
            @click="sendEmail"
          >
            {{ emailSending ? '发送中...' : emailCountdown > 0 ? `${emailCountdown}s 后重试` : '获取验证码' }}
          </button>
        </label>

        <label class="mobile-auth-field">
          <span class="mobile-auth-field-icon"><AuthIcon name="lock" /></span>
          <input
            v-model="form.password"
            :type="showPwd ? 'text' : 'password'"
            maxlength="32"
            autocomplete="new-password"
            placeholder="请输入密码（8-32位，字母+数字）"
          />
          <button type="button" class="mobile-auth-eye-btn" @click="showPwd = !showPwd">
            <AuthIcon :name="showPwd ? 'eyeOff' : 'eye'" />
          </button>
        </label>

        <label class="mobile-auth-field">
          <span class="mobile-auth-field-icon"><AuthIcon name="lock" /></span>
          <input
            v-model="form.confirmPassword"
            :type="showConfirmPwd ? 'text' : 'password'"
            maxlength="32"
            autocomplete="new-password"
            placeholder="请再次输入密码"
          />
          <button type="button" class="mobile-auth-eye-btn" @click="showConfirmPwd = !showConfirmPwd">
            <AuthIcon :name="showConfirmPwd ? 'eyeOff' : 'eye'" />
          </button>
        </label>

        <label class="mobile-auth-field">
          <span class="mobile-auth-field-icon"><AuthIcon name="user" /></span>
          <input
            v-model.trim="form.inviteCode"
            type="text"
            maxlength="40"
            placeholder="邀请码（可选）"
          />
        </label>

        <label class="mobile-auth-agreement">
          <input v-model="form.agreed" type="checkbox" :disabled="!legalDocumentsAvailable" />
          <span>
            我已阅读并同意
            <button type="button" class="mobile-auth-text-link" :disabled="!legalConfig.termsUrl" @click="openDoc('用户协议')">《用户协议》</button>
            和
            <button type="button" class="mobile-auth-text-link" :disabled="!legalConfig.privacyUrl" @click="openDoc('隐私政策')">《隐私政策》</button>
          </span>
        </label>
        <p v-if="!legalDocumentsAvailable" class="mobile-auth-legal-unavailable" role="status">
          用户协议或隐私政策链接未配置，当前无法完成注册。
        </p>

        <button
          class="mobile-auth-primary-button"
          type="submit"
          :disabled="loading || !legalDocumentsAvailable"
        >
          {{ loading ? '注册中...' : '完成注册' }}
        </button>
      </form>

    <template #footer-actions>
      <div class="mobile-auth-divider"><span>已有账号？</span></div>
      <button
        type="button"
        class="mobile-auth-secondary-button"
        @click="emit('navigate', 'login')"
      >
        返回登录
      </button>
    </template>
  </MobileAuthShell>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { register, sendEmailCode } from '../api/auth.js'
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
const selfRegistrationCapability = computed(() => authCapabilities.value.selfRegistration)
const emailLoginCapability = computed(() => authCapabilities.value.emailVerification)
const authUnavailableMessage = computed(() => authCapabilityError.value || selfRegistrationCapability.value.reason)
const authSupportMessage = computed(() => {
  const support = String(authCapabilities.value.supportMessage || '').trim()
  return support && support !== authUnavailableMessage.value ? support : ''
})

const form = reactive({
  email: '',
  emailCode: '',
  password: '',
  confirmPassword: '',
  inviteCode: '',
  agreed: false
})

const showPwd = ref(false)
const showConfirmPwd = ref(false)
const loading = ref(false)
const emailSending = ref(false)
const emailCountdown = ref(0)
const errorMsg = ref('')
const errorMsgRef = ref(null)
const emailValid = computed(() => validateEmail(form.email))
const legalConfig = LEGAL_CONFIG
const legalDocumentsAvailable = hasRequiredLegalDocuments(legalConfig)
let emailTimer = null

// 移动端图形验证码
const registerCaptchaRef = ref(null)
const registerCaptcha = ref('')

// PC 端图形验证码
const pcRegisterCaptchaRef = ref(null)
const pcRegisterCaptcha = ref('')

// 字段级失焦校验
const fieldErrors = reactive({
  email: '',
  emailCode: '',
  password: '',
  confirmPassword: '',
  agreed: ''
})

// 移动端检测
const isMobile = ref(false)
function updateMobileDetection() {
  isMobile.value = window.matchMedia?.('(max-width: 900px)').matches || /Mobi|Android|iPhone|iPad|iPod/i.test(navigator.userAgent)
}

const mobileHeroTitle = computed(() => '创建账号')
const mobileHeroDesc = computed(() => '验证邮箱并设置密码')
const mobileHeading = computed(() => '邮箱验证码注册')
const mobileSubheading = computed(() => '完成安全验证后获取邮箱验证码')

function showToast(message, type = 'info') {
  if (typeof window === 'undefined' || !window.dispatchEvent) return
  window.dispatchEvent(new CustomEvent('xya-toast', {
    detail: { message, isError: type === 'error' || type === 'warning' }
  }))
}

function blurEmail() {
  if (!form.email) {
    fieldErrors.email = ''
    return
  }
  fieldErrors.email = validateEmail(form.email) ? '' : '邮箱格式不正确'
}

function blurEmailCode() {
  fieldErrors.emailCode = form.emailCode.trim() ? '' : '请输入邮箱验证码'
}

function blurPassword() {
  if (!form.password) {
    fieldErrors.password = ''
    return
  }
  fieldErrors.password = validatePassword(form.password) ? '' : '密码需为 8-32 位，且包含字母和数字'
  if (form.confirmPassword && form.confirmPassword !== form.password) {
    fieldErrors.confirmPassword = '两次输入的密码不一致'
  } else if (form.confirmPassword) {
    fieldErrors.confirmPassword = ''
  }
}

function blurConfirmPassword() {
  if (!form.confirmPassword) {
    fieldErrors.confirmPassword = ''
    return
  }
  fieldErrors.confirmPassword = form.confirmPassword === form.password ? '' : '两次输入的密码不一致'
}

function blurAgreed() {
  fieldErrors.agreed = form.agreed ? '' : '请先阅读并同意用户协议和隐私政策'
}

function scrollToError() {
  const fieldErr = document.querySelector('.auth-field-error')
  if (fieldErr && typeof fieldErr.scrollIntoView === 'function') {
    fieldErr.scrollIntoView({ behavior: 'smooth', block: 'center' })
    return
  }
  const el = errorMsgRef.value
  if (el && typeof el.scrollIntoView === 'function') {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

function openDoc(title) {
  const result = openLegalDoc(title)
  if (!result.opened) errorMsg.value = result.message
}

function validateEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
}

function validatePassword(password) {
  return /^(?=.*[A-Za-z])(?=.*\d).{8,32}$/.test(password)
}

function validateForm() {
  if (!legalDocumentsAvailable) return '用户协议或隐私政策链接未配置，当前无法完成注册'
  if (!validateEmail(form.email)) return '请输入正确的邮箱'
  if (!form.emailCode.trim()) return '请输入邮箱验证码'
  if (!validatePassword(form.password)) return '密码需为 8-32 位，且包含字母和数字'
  if (form.password !== form.confirmPassword) return '两次输入的密码不一致'
  if (!form.agreed) return '请先阅读并同意用户协议和隐私政策'
  return ''
}

async function sendEmail() {
  if (emailSending.value || emailCountdown.value > 0) return
  errorMsg.value = ''

  // 仅在用户点击「获取验证码」时校验后端 capability，避免阻塞表单显示
  if (!selfRegistrationCapability.value.available) {
    errorMsg.value = selfRegistrationCapability.value.reason || '自助注册暂不可用'
    return
  }
  if (!emailLoginCapability.value.available) {
    errorMsg.value = emailLoginCapability.value.reason || '邮箱验证码服务暂不可用'
    return
  }

  if (!validateEmail(form.email)) {
    errorMsg.value = '请先输入正确邮箱'
    return
  }

  // 图形验证码校验（PC + 移动端）
  const captchaRef = isMobile.value ? registerCaptchaRef.value : pcRegisterCaptchaRef.value
  if (captchaRef && !captchaRef.validate()) {
    errorMsg.value = '请先完成图形验证'
    return
  }

  emailSending.value = true
  try {
    const res = await sendEmailCode({ email: form.email })
    if (res?.data?.devCode) form.emailCode = res.data.devCode

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

async function submitRegister() {
  blurEmail()
  blurEmailCode()
  blurPassword()
  blurConfirmPassword()
  blurAgreed()
  errorMsg.value = validateForm()
  if (errorMsg.value || loading.value) {
    if (errorMsg.value) {
      showToast(errorMsg.value, 'error')
      requestAnimationFrame(scrollToError)
    }
    return
  }

  // 图形验证码校验（PC + 移动端）
  const captchaRef = isMobile.value ? registerCaptchaRef.value : pcRegisterCaptchaRef.value
  if (captchaRef && !captchaRef.validate()) {
    errorMsg.value = '请先完成图形验证'
    showToast(errorMsg.value, 'error')
    requestAnimationFrame(scrollToError)
    return
  }

  loading.value = true
  try {
    const res = await register({
      email: form.email.trim(),
      password: form.password,
      emailCode: form.emailCode.trim(),
      inviteCode: form.inviteCode.trim() || undefined
    })
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data) || !String(data.token || '').trim()) {
      throw new Error('注册响应缺少有效登录凭证，请返回登录页重试')
    }
    emit('login-success', data)
  } catch (error) {
    errorMsg.value = friendlyError(error, '注册失败，请稍后重试')
    showToast(errorMsg.value, 'error')
    requestAnimationFrame(scrollToError)
  } finally {
    loading.value = false
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
