<template>
  <AuthShell
    page-key="register"
    title-lead="快速注册，"
    title-accent="开启智能运营"
    description="创建账号后可使用部署方已启用的管理能力；实际可用功能取决于后台服务与部署配置。"
    legal-description="该页面用于说明 XianYuAssistant 注册、邮箱校验与账号创建相关规则。"
    @navigate="emit('navigate', $event)"
  >
    <div class="auth-panel-heading auth-panel-heading-tabs">
      <div class="auth-tabs auth-tabs-split">
        <button type="button" class="active">立即注册</button>
        <button type="button" @click="emit('navigate', 'login')">已有账号？去登录</button>
      </div>
    </div>

    <div v-if="errorMsg" class="form-error" role="alert" aria-live="assertive">{{ errorMsg }}</div>

    <div v-if="authCapabilityLoading" class="auth-capability-card" role="status">
      <h3>正在确认注册能力</h3>
      <p>确认完成前不会显示或提交注册表单。</p>
    </div>
    <div v-else-if="!selfRegistrationCapability.available" class="auth-capability-card unavailable" role="status">
      <h3>自助注册暂不可用</h3>
      <p>{{ authUnavailableMessage }}</p>
      <p v-if="authSupportMessage">{{ authSupportMessage }}</p>
      <div class="auth-capability-actions">
        <button v-if="authCapabilityError" type="button" class="auth-text-link" @click="refreshAuthCapabilities">重新检查</button>
        <button type="button" class="auth-text-link auth-link-strong" @click="emit('navigate', 'login')">返回密码登录</button>
      </div>
    </div>

    <template v-else>
    <div v-if="selfRegistrationCapability.devOnly" class="auth-capability-note development" role="status">
      {{ authCapabilities.securityNotice }}
    </div>
    <form class="auth-form" @submit.prevent="submitRegister">
      <label class="auth-field auth-field-with-action">
        <AuthIcon class="auth-field-icon" name="mail" />
        <input
          v-model.trim="form.email"
          type="email"
          autocomplete="email"
          placeholder="邮箱"
        />
        <button v-if="form.email" type="button" class="auth-clear-btn" @click="form.email = ''">
          <AuthIcon name="close" />
        </button>
      </label>

      <label class="auth-field auth-field-with-action">
        <AuthIcon class="auth-field-icon" name="code" />
        <input
          v-model.trim="form.emailCode"
          type="text"
          maxlength="6"
          autocomplete="one-time-code"
          placeholder="邮箱验证码"
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

      <label class="auth-field auth-field-with-action">
        <AuthIcon class="auth-field-icon" name="lock" />
        <input
          v-model="form.password"
          :type="showPwd ? 'text' : 'password'"
          maxlength="32"
          autocomplete="new-password"
          placeholder="设置密码（8-32位，字母+数字组合）"
        />
        <button type="button" class="auth-eye-btn" @click="showPwd = !showPwd">
          <AuthIcon :name="showPwd ? 'eyeOff' : 'eye'" />
        </button>
      </label>

      <label class="auth-field auth-field-with-action">
        <AuthIcon class="auth-field-icon" name="lock" />
        <input
          v-model="form.confirmPassword"
          :type="showConfirmPwd ? 'text' : 'password'"
          maxlength="32"
          autocomplete="new-password"
          placeholder="确认密码"
        />
        <button type="button" class="auth-eye-btn" @click="showConfirmPwd = !showConfirmPwd">
          <AuthIcon :name="showConfirmPwd ? 'eyeOff' : 'eye'" />
        </button>
      </label>

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
        <label class="auth-check auth-check-register auth-check-agreement">
          <input v-model="form.agreed" type="checkbox" :disabled="!legalDocumentsAvailable" />
          <span>
            我已阅读并同意
            <button type="button" class="auth-text-link" :disabled="!legalConfig.termsUrl" @click="openDoc('用户协议')">《用户协议》</button>
            和
            <button type="button" class="auth-text-link" :disabled="!legalConfig.privacyUrl" @click="openDoc('隐私政策')">《隐私政策》</button>
          </span>
        </label>
        <p v-if="!legalDocumentsAvailable" class="auth-legal-unavailable" role="status">
          用户协议或隐私政策链接未配置，当前无法完成注册，请联系部署方。
        </p>
      </div>

      <button class="auth-submit" type="submit" :disabled="loading || !selfRegistrationCapability.available || !legalDocumentsAvailable">
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
    </template>
  </AuthShell>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { register, sendEmailCode } from '../api/auth.js'
import AuthIcon from '../components/auth/AuthIcon.vue'
import AuthShell from '../components/auth/AuthShell.vue'
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
const emailValid = computed(() => validateEmail(form.email))
const legalConfig = LEGAL_CONFIG
const legalDocumentsAvailable = hasRequiredLegalDocuments(legalConfig)
let emailTimer = null

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

  if (!selfRegistrationCapability.value.available || !emailLoginCapability.value.available) return

  if (!validateEmail(form.email)) {
    errorMsg.value = '请先输入正确邮箱'
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
  if (!selfRegistrationCapability.value.available) return
  errorMsg.value = validateForm()
  if (errorMsg.value || loading.value) return

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
  } finally {
    loading.value = false
  }
}

onMounted(refreshAuthCapabilities)

onUnmounted(() => {
  if (emailTimer) clearInterval(emailTimer)
})
</script>
