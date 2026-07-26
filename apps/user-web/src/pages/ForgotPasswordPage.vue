<template>
  <AuthShell
    v-if="!isMobile"
    page-key="forgot"
    title-lead="安全找回账号，"
    title-accent="快速恢复登录"
    description="通过已绑定邮箱完成后台身份校验后重置密码；步骤结果会在页面中明确反馈。"
    visual-kind="security"
    legal-description="该页面用于说明 XianYuAssistant 账号找回、身份校验与密码重置相关规则。"
    @navigate="emit('navigate', $event)"
  >
    <div class="auth-panel-heading auth-panel-heading-center">
      <h2>忘记密码</h2>
      <p>
        <AuthIcon class="auth-safe-inline" name="shield" />
        <span>请通过已绑定邮箱完成身份验证</span>
      </p>
    </div>

    <div v-if="error" class="form-error" role="alert" aria-live="assertive">{{ error }}</div>
    <div v-else-if="success" class="form-success" role="status" aria-live="polite">{{ success }}</div>

    <div v-if="authCapabilityLoading" class="auth-capability-note" role="status">
      正在确认密码找回能力...
    </div>
    <div v-else-if="passwordResetCapability.devOnly" class="auth-capability-note development" role="status">
      {{ authCapabilities.securityNotice }}
    </div>

    <form class="auth-form" @submit.prevent="submitReset">
      <label class="auth-field auth-field-stack">
        <div class="auth-field-row">
          <AuthIcon class="auth-field-icon" name="mail" />
          <input
            v-model.trim="form.email"
            type="email"
            autocomplete="email"
            placeholder="邮箱"
          />
        </div>
        <small>请输入绑定账号的邮箱</small>
      </label>

      <AuthCaptcha
        ref="pcCaptchaRef"
        v-model="pcCaptcha"
        hint="验证通过后才可获取重置验证码"
      />

      <label class="auth-field auth-field-stack">
        <div class="auth-field-row auth-field-with-action">
          <AuthIcon class="auth-field-icon" name="code" />
          <input
            v-model.trim="form.code"
            type="text"
            maxlength="6"
            inputmode="numeric"
            autocomplete="one-time-code"
            placeholder="邮箱验证码"
          />
          <button
            type="button"
            class="auth-inline-link auth-inline-link-boxed"
            :disabled="!emailValid || countdown > 0 || sendingCode"
            :title="emailValid ? '获取邮箱验证码' : '请输入有效邮箱后获取验证码'"
            @click="sendCode"
          >
            {{ sendingCode ? '发送中...' : countdown > 0 ? `${countdown}s 后重试` : '获取验证码' }}
          </button>
        </div>
        <small>请输入邮箱验证码</small>
      </label>

      <label class="auth-field auth-field-stack">
        <div class="auth-field-row auth-field-with-action">
          <AuthIcon class="auth-field-icon" name="lock" />
          <input
            v-model="form.newPassword"
            :type="showNewPwd ? 'text' : 'password'"
            maxlength="32"
            autocomplete="new-password"
            placeholder="新密码"
          />
          <button type="button" class="auth-eye-btn" @click="showNewPwd = !showNewPwd">
            <AuthIcon :name="showNewPwd ? 'eyeOff' : 'eye'" />
          </button>
        </div>
        <small>请设置 8-32 位，且包含字母和数字</small>
      </label>

      <label class="auth-field auth-field-stack">
        <div class="auth-field-row auth-field-with-action">
          <AuthIcon class="auth-field-icon" name="lock" />
          <input
            v-model="form.confirmNewPassword"
            :type="showConfirmPwd ? 'text' : 'password'"
            maxlength="32"
            autocomplete="new-password"
            placeholder="确认新密码"
          />
          <button type="button" class="auth-eye-btn" @click="showConfirmPwd = !showConfirmPwd">
            <AuthIcon :name="showConfirmPwd ? 'eyeOff' : 'eye'" />
          </button>
        </div>
        <small>请再次输入新密码</small>
      </label>

      <button
        class="auth-submit"
        type="submit"
        :disabled="loading || !resetFormValid"
        :title="resetFormValid ? '提交密码重置' : '请完整填写邮箱、验证码和一致的新密码'"
      >
        {{ loading ? '重置中...' : '重置密码' }}
      </button>
    </form>

    <div class="auth-back-link auth-back-link-tight">
      <button type="button" class="auth-text-link auth-link-strong" @click="emit('navigate', 'login')">
        <AuthIcon class="auth-inline-icon" name="arrowLeft" />
        <span>返回登录</span>
      </button>
    </div>

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
      <button type="button" class="auth-social-btn" @click="emit('navigate', 'login')">
        <AuthIcon class="auth-social-icon" name="lock" />
        <span>密码登录</span>
      </button>
    </div>

    <div class="auth-safe-tip auth-safe-tip-spaced">
      <AuthIcon class="auth-safe-inline" name="shield" />
      <span>密码重置后，您的账号将根据最新凭据重新校验，安全可追溯</span>
    </div>
  </AuthShell>

  <MobileAuthShell
    v-else
    page-key="forgot"
    :hero-title="mobileHeroTitle"
    :hero-desc="mobileHeroDesc"
    :heading="mobileHeading"
    :subheading="mobileSubheading"
    @navigate="emit('navigate', $event)"
  >
    <div v-if="error" class="mobile-auth-form-error" role="alert" aria-live="assertive">{{ error }}</div>
    <div v-else-if="success" class="mobile-auth-form-success" role="status" aria-live="polite">{{ success }}</div>

    <div v-if="authCapabilityLoading" class="mobile-auth-capability-note" role="status">
      正在确认密码找回能力...
    </div>
    <div v-else-if="passwordResetCapability.devOnly" class="mobile-auth-capability-note development" role="status">
      {{ authCapabilities.securityNotice }}
    </div>

    <form class="mobile-auth-form" @submit.prevent="submitReset">
        <label class="mobile-auth-field">
          <span class="mobile-auth-field-icon"><AuthIcon name="mail" /></span>
          <input
            v-model.trim="form.email"
            type="email"
            autocomplete="email"
            placeholder="请输入注册邮箱"
          />
        </label>

        <MobileCaptcha
          ref="resetCaptchaRef"
          v-model="resetCaptcha"
          hint="验证通过后才可获取重置验证码"
        />

        <label class="mobile-auth-field mobile-auth-field--code">
          <span class="mobile-auth-field-icon"><AuthIcon name="code" /></span>
          <input
            v-model.trim="form.code"
            type="text"
            maxlength="6"
            inputmode="numeric"
            autocomplete="one-time-code"
            placeholder="请输入邮箱验证码"
          />
          <button
            type="button"
            class="mobile-auth-code-button"
            :disabled="!emailLoginCapability.available || !emailValid || countdown > 0 || sendingCode"
            @click="sendCode"
          >
            {{ sendingCode ? '发送中...' : countdown > 0 ? `${countdown}s 后重试` : '获取验证码' }}
          </button>
        </label>

        <label class="mobile-auth-field">
          <span class="mobile-auth-field-icon"><AuthIcon name="lock" /></span>
          <input
            v-model="form.newPassword"
            :type="showNewPwd ? 'text' : 'password'"
            maxlength="32"
            autocomplete="new-password"
            placeholder="请输入新密码"
          />
          <button type="button" class="mobile-auth-eye-btn" @click="showNewPwd = !showNewPwd">
            <AuthIcon :name="showNewPwd ? 'eyeOff' : 'eye'" />
          </button>
        </label>

        <label class="mobile-auth-field">
          <span class="mobile-auth-field-icon"><AuthIcon name="lock" /></span>
          <input
            v-model="form.confirmNewPassword"
            :type="showConfirmPwd ? 'text' : 'password'"
            maxlength="32"
            autocomplete="new-password"
            placeholder="请再次输入新密码"
          />
          <button type="button" class="mobile-auth-eye-btn" @click="showConfirmPwd = !showConfirmPwd">
            <AuthIcon :name="showConfirmPwd ? 'eyeOff' : 'eye'" />
          </button>
        </label>

        <button
          class="mobile-auth-primary-button"
          type="submit"
          :disabled="loading || !resetFormValid"
        >
          {{ loading ? '重置中...' : '重置密码' }}
        </button>
      </form>

    <template #footer-actions>
      <button
        type="button"
        class="mobile-auth-back-link"
        @click="emit('navigate', 'login')"
      >
        ← 返回登录
      </button>
    </template>
  </MobileAuthShell>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { resetPassword as resetPasswordApi, sendEmailCode, verifyResetCode } from '../api/auth.js'
import AuthIcon from '../components/auth/AuthIcon.vue'
import AuthShell from '../components/auth/AuthShell.vue'
import MobileAuthShell from '../components/auth/MobileAuthShell.vue'
import MobileCaptcha from '../components/auth/MobileCaptcha.vue'
import { friendlyError } from '../utils/friendlyError.js'
import { useAuthCapabilities } from '../utils/useAuthCapabilities.js'

const emit = defineEmits(['navigate', 'login-success'])

const {
  authCapabilities,
  authCapabilityLoading,
  authCapabilityError,
  refreshAuthCapabilities,
} = useAuthCapabilities()
const passwordResetCapability = computed(() => authCapabilities.value.passwordReset)
const emailLoginCapability = computed(() => authCapabilities.value.emailVerification)
const authUnavailableMessage = computed(() => authCapabilityError.value || passwordResetCapability.value.reason)
const authSupportMessage = computed(() => {
  const support = String(authCapabilities.value.supportMessage || '').trim()
  return support && support !== authUnavailableMessage.value ? support : ''
})

const form = reactive({
  email: '',
  code: '',
  newPassword: '',
  confirmNewPassword: ''
})

const loading = ref(false)
const sendingCode = ref(false)
const error = ref('')
const success = ref('')
const showNewPwd = ref(false)
const showConfirmPwd = ref(false)
const countdown = ref(0)
const emailValid = computed(() => isEmail(form.email.trim()))
const resetFormValid = computed(() => (
  emailValid.value
  && /^\d{4,6}$/.test(form.code.trim())
  && isValidPassword(form.newPassword)
  && form.newPassword === form.confirmNewPassword
))
let timer = null

// 移动端图形验证码
const resetCaptchaRef = ref(null)
const resetCaptcha = ref('')

// 移动端检测
const isMobile = ref(false)
function updateMobileDetection() {
  isMobile.value = window.matchMedia?.('(max-width: 900px)').matches || /Mobi|Android|iPhone|iPad|iPod/i.test(navigator.userAgent)
}

const mobileHeroTitle = computed(() => '找回密码')
const mobileHeroDesc = computed(() => '验证邮箱后重新设置登录密码')
const mobileHeading = computed(() => '邮箱找回密码')
const mobileSubheading = computed(() => '验证身份后重新设置登录密码')

function isEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
}

function isValidPassword(value) {
  return /^(?=.*[A-Za-z])(?=.*\d).{8,32}$/.test(value)
}

function startCountdown() {
  if (timer) clearInterval(timer)
  countdown.value = 60
  timer = setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0) {
      clearInterval(timer)
      timer = null
      countdown.value = 0
    }
  }, 1000)
}

async function sendCode() {
  error.value = ''
  success.value = ''

  // 仅在用户点击「获取验证码」时校验后端 capability，避免阻塞表单显示
  if (!passwordResetCapability.value.available) {
    error.value = passwordResetCapability.value.reason || '密码重置服务暂不可用'
    return
  }
  if (!emailLoginCapability.value.available) {
    error.value = emailLoginCapability.value.reason || '邮箱验证码服务暂不可用'
    return
  }

  if (!isEmail(form.email.trim())) {
    error.value = '请输入正确的邮箱'
    return
  }

  // 图形验证码校验（PC + 移动端）
  const captchaRef = isMobile.value ? resetCaptchaRef.value : pcCaptchaRef.value
  if (captchaRef && !captchaRef.validate()) {
    error.value = '请先完成图形验证'
    return
  }

  sendingCode.value = true
  try {
    const response = await sendEmailCode({ email: form.email.trim() })
    if (passwordResetCapability.value.devOnly && response?.data?.devCode) form.code = response.data.devCode
    startCountdown()
    success.value = passwordResetCapability.value.devOnly
      ? '本地开发验证码已生成并填入，未发送真实邮件'
      : '验证码已发送，请注意查收'
  } catch (err) {
    error.value = friendlyError(err, '验证码发送失败，请稍后重试')
  } finally {
    sendingCode.value = false
  }
}

async function submitReset() {
  error.value = ''
  success.value = ''

  if (!isEmail(form.email.trim())) {
    error.value = '请输入正确的邮箱'
    return
  }
  if (!/^\d{4,6}$/.test(form.code.trim())) {
    error.value = '请输入正确的邮箱验证码'
    return
  }
  if (!isValidPassword(form.newPassword)) {
    error.value = '密码需为 8-32 位，且至少包含字母和数字'
    return
  }
  if (form.newPassword !== form.confirmNewPassword) {
    error.value = '两次输入的新密码不一致'
    return
  }

  // 图形验证码校验（PC + 移动端）
  const captchaRef = isMobile.value ? resetCaptchaRef.value : pcCaptchaRef.value
  if (captchaRef && !captchaRef.validate()) {
    error.value = '请先完成图形验证'
    return
  }

  loading.value = true
  try {
    await verifyResetCode({ email: form.email.trim(), emailCode: form.code.trim() })
    await resetPasswordApi({
      email: form.email.trim(),
      emailCode: form.code.trim(),
      newPassword: form.newPassword
    })
    success.value = '密码重置成功，请使用新密码登录'
    setTimeout(() => emit('navigate', 'login'), 1200)
  } catch (err) {
    error.value = friendlyError(err, '重置失败，请稍后重试')
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
  if (timer) clearInterval(timer)
  window.removeEventListener('resize', updateMobileDetection)
})
</script>
