<template>
  <div class="m-profile-security">
    <!-- Tab 切换 -->
    <div class="m-sec-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="m-sec-tab"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        <MIcon :name="tab.icon" :size="16" />
        <span>{{ tab.label }}</span>
      </button>
    </div>

    <!-- 顶部提示 -->
    <div v-if="notice.text" class="m-sec-notice" :class="notice.type" role="status">
      <MIcon :name="noticeIcon" :size="14" />
      <span>{{ notice.text }}</span>
    </div>

    <!-- 修改密码 -->
    <form v-if="activeTab === 'password'" class="m-sec-form" @submit.prevent="submitPassword">
      <div class="m-sec-card">
        <div class="m-sec-card-head">
          <h3>修改密码</h3>
          <p>新密码至少 8 位，修改成功后建议重新登录。</p>
        </div>
        <label class="m-sec-field">
          <span class="m-sec-label">当前密码</span>
          <input
            v-model.trim="passwordForm.oldPassword"
            type="password"
            autocomplete="current-password"
            placeholder="请输入当前密码"
            class="m-sec-input"
          />
        </label>
        <label class="m-sec-field">
          <span class="m-sec-label">新密码</span>
          <input
            v-model.trim="passwordForm.newPassword"
            type="password"
            autocomplete="new-password"
            placeholder="至少 8 位"
            class="m-sec-input"
          />
        </label>
        <label class="m-sec-field">
          <span class="m-sec-label">确认新密码</span>
          <input
            v-model.trim="passwordForm.confirmPassword"
            type="password"
            autocomplete="new-password"
            placeholder="再次输入新密码"
            class="m-sec-input"
          />
        </label>
        <button type="submit" class="m-sec-submit" :disabled="saving">
          {{ saving ? '提交中…' : '保存新密码' }}
        </button>
      </div>
    </form>

    <!-- 手机绑定 -->
    <form v-else-if="activeTab === 'phone'" class="m-sec-form" @submit.prevent="submitPhone">
      <div class="m-sec-card">
        <div class="m-sec-card-head">
          <h3>手机绑定</h3>
          <p>先获取验证码，再提交绑定。验证码有效期 5 分钟。</p>
        </div>
        <div class="m-sec-current">
          <span class="m-sec-current-label">当前手机号</span>
          <span class="m-sec-current-value">{{ currentPhoneDisplay }}</span>
        </div>
        <label class="m-sec-field">
          <span class="m-sec-label">新手机号</span>
          <input
            v-model.trim="phoneForm.phone"
            type="tel"
            maxlength="11"
            placeholder="请输入 11 位手机号"
            class="m-sec-input"
          />
        </label>
        <div class="m-sec-code-row">
          <label class="m-sec-field m-sec-code-field">
            <span class="m-sec-label">验证码</span>
            <input
              v-model.trim="phoneForm.code"
              type="text"
              inputmode="numeric"
              maxlength="6"
              placeholder="请输入验证码"
              class="m-sec-input"
            />
          </label>
          <button
            type="button"
            class="m-sec-code-btn"
            :disabled="phoneCountdown > 0 || sendingCode"
            @click="sendCode('phone')"
          >
            {{ phoneCountdown > 0 ? `${phoneCountdown}s 后重试` : (sendingCode ? '发送中…' : '获取验证码') }}
          </button>
        </div>
        <button type="submit" class="m-sec-submit" :disabled="saving">
          {{ saving ? '提交中…' : '绑定手机号' }}
        </button>
      </div>
    </form>

    <!-- 邮箱绑定 -->
    <form v-else class="m-sec-form" @submit.prevent="submitEmail">
      <div class="m-sec-card">
        <div class="m-sec-card-head">
          <h3>邮箱绑定</h3>
          <p>先获取验证码，再提交绑定。验证码有效期 5 分钟。</p>
        </div>
        <div class="m-sec-current">
          <span class="m-sec-current-label">当前邮箱</span>
          <span class="m-sec-current-value">{{ currentEmailDisplay }}</span>
        </div>
        <label class="m-sec-field">
          <span class="m-sec-label">新邮箱</span>
          <input
            v-model.trim="emailForm.email"
            type="email"
            placeholder="请输入邮箱地址"
            class="m-sec-input"
          />
        </label>
        <div class="m-sec-code-row">
          <label class="m-sec-field m-sec-code-field">
            <span class="m-sec-label">验证码</span>
            <input
              v-model.trim="emailForm.code"
              type="text"
              inputmode="numeric"
              maxlength="6"
              placeholder="请输入验证码"
              class="m-sec-input"
            />
          </label>
          <button
            type="button"
            class="m-sec-code-btn"
            :disabled="emailCountdown > 0 || sendingCode"
            @click="sendCode('email')"
          >
            {{ emailCountdown > 0 ? `${emailCountdown}s 后重试` : (sendingCode ? '发送中…' : '获取验证码') }}
          </button>
        </div>
        <button type="submit" class="m-sec-submit" :disabled="saving">
          {{ saving ? '提交中…' : '绑定邮箱' }}
        </button>
      </div>
    </form>

    <div class="m-safe-bottom"></div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import MIcon from './MIcon.vue'
import {
  getProfileOverview,
  sendProfileCode,
  changeProfilePassword,
  changeProfilePhone,
  changeProfileEmail
} from '../api/profile.js'

const emit = defineEmits(['updated', 'force-desktop'])

const tabs = [
  { key: 'password', label: '修改密码', icon: 'lock' },
  { key: 'phone', label: '手机绑定', icon: 'phone' },
  { key: 'email', label: '邮箱绑定', icon: 'mail' }
]

const activeTab = ref('password')
const saving = ref(false)
const sendingCode = ref(false)
const overview = ref({})

const passwordForm = reactive({ oldPassword: '', newPassword: '', confirmPassword: '' })
const phoneForm = reactive({ phone: '', code: '' })
const emailForm = reactive({ email: '', code: '' })

const notice = reactive({ text: '', type: 'info' })
let noticeTimer = null

const phoneCountdown = ref(0)
const emailCountdown = ref(0)
let phoneTimer = null
let emailTimer = null

const noticeIcon = computed(() => {
  if (notice.type === 'success') return 'checkCircle'
  if (notice.type === 'error' || notice.type === 'warn') return 'warning'
  return 'info'
})

const currentPhoneDisplay = computed(() => overview.value.phone || overview.value.maskedPhone || '未绑定')
const currentEmailDisplay = computed(() => overview.value.email || overview.value.maskedEmail || '未绑定')

function showNotice(text, type = 'info') {
  notice.text = text
  notice.type = type
  if (noticeTimer) clearTimeout(noticeTimer)
  noticeTimer = setTimeout(() => { notice.text = '' }, 4200)
}

async function loadOverview() {
  try {
    const res = await getProfileOverview()
    if (res?.data && typeof res.data === 'object' && !Array.isArray(res.data)) {
      overview.value = res.data
    }
  } catch {
    // 静默失败：当前手机/邮箱显示为占位，不影响修改流程
  }
}

function startCountdown(type) {
  const seconds = 60
  if (type === 'phone') {
    phoneCountdown.value = seconds
    phoneTimer = setInterval(() => {
      phoneCountdown.value -= 1
      if (phoneCountdown.value <= 0) {
        clearInterval(phoneTimer)
        phoneTimer = null
      }
    }, 1000)
  } else {
    emailCountdown.value = seconds
    emailTimer = setInterval(() => {
      emailCountdown.value -= 1
      if (emailCountdown.value <= 0) {
        clearInterval(emailTimer)
        emailTimer = null
      }
    }, 1000)
  }
}

async function submitPassword() {
  if (!passwordForm.oldPassword || !passwordForm.newPassword) {
    return showNotice('请完整填写密码信息', 'warn')
  }
  if (passwordForm.newPassword.length < 8) {
    return showNotice('新密码至少 8 位', 'warn')
  }
  if (passwordForm.newPassword !== passwordForm.confirmPassword) {
    return showNotice('两次输入的新密码不一致', 'warn')
  }
  saving.value = true
  try {
    await changeProfilePassword({
      oldPassword: passwordForm.oldPassword,
      newPassword: passwordForm.newPassword
    })
    Object.assign(passwordForm, { oldPassword: '', newPassword: '', confirmPassword: '' })
    await loadOverview()
    showNotice('密码已修改', 'success')
    emit('updated')
  } catch (error) {
    showNotice(error?.message || '密码修改失败', 'error')
  } finally {
    saving.value = false
  }
}

async function sendCode(type) {
  const target = type === 'phone' ? phoneForm.phone : emailForm.email
  if (!target) {
    return showNotice(type === 'phone' ? '请先输入手机号' : '请先输入邮箱', 'warn')
  }
  if (type === 'phone' && !/^1\d{10}$/.test(target)) {
    return showNotice('请输入正确的 11 位手机号', 'warn')
  }
  if (type === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(target)) {
    return showNotice('请输入正确的邮箱地址', 'warn')
  }
  sendingCode.value = true
  try {
    const res = await sendProfileCode({
      targetType: type,
      target,
      purpose: type === 'phone' ? 'change_phone' : 'change_email'
    })
    const debugCode = res?.data?.debugCode
    const suffix = debugCode ? `，开发验证码：${debugCode}` : ''
    showNotice(`验证码已发送${suffix}`, 'success')
    startCountdown(type)
  } catch (error) {
    showNotice(error?.message || '验证码发送失败', 'error')
  } finally {
    sendingCode.value = false
  }
}

async function submitPhone() {
  if (!phoneForm.phone || !phoneForm.code) {
    return showNotice('请填写手机号和验证码', 'warn')
  }
  saving.value = true
  try {
    await changeProfilePhone({ phone: phoneForm.phone, code: phoneForm.code })
    Object.assign(phoneForm, { phone: '', code: '' })
    await loadOverview()
    showNotice('手机号已更新', 'success')
    emit('updated')
  } catch (error) {
    showNotice(error?.message || '手机号修改失败', 'error')
  } finally {
    saving.value = false
  }
}

async function submitEmail() {
  if (!emailForm.email || !emailForm.code) {
    return showNotice('请填写邮箱和验证码', 'warn')
  }
  saving.value = true
  try {
    await changeProfileEmail({ email: emailForm.email, code: emailForm.code })
    Object.assign(emailForm, { email: '', code: '' })
    await loadOverview()
    showNotice('邮箱已更新', 'success')
    emit('updated')
  } catch (error) {
    showNotice(error?.message || '邮箱修改失败', 'error')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadOverview()
})

onBeforeUnmount(() => {
  if (noticeTimer) clearTimeout(noticeTimer)
  if (phoneTimer) clearInterval(phoneTimer)
  if (emailTimer) clearInterval(emailTimer)
})
</script>

<style scoped>
.m-profile-security {
  padding: var(--m-space-3) var(--m-space-4) 0;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
}

/* === Tab 切换 === */
.m-sec-tabs {
  display: flex;
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-1);
  margin-bottom: var(--m-space-3);
  gap: var(--m-space-1);
  box-shadow: var(--m-shadow-xs);
}
.m-sec-tab {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  padding: var(--m-space-3) var(--m-space-2);
  border-radius: var(--m-radius-lg);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-1);
  transition: all 0.18s;
  min-width: 0;
}
.m-sec-tab span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-sec-tab.active {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  box-shadow: var(--m-shadow-xs);
}

/* === 顶部提示 === */
.m-sec-notice {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  padding: var(--m-space-3);
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-body-sm);
  margin-bottom: var(--m-space-3);
}
.m-sec-notice.info {
  background: var(--m-color-info-bg);
  color: var(--m-color-info-text);
}
.m-sec-notice.success {
  background: var(--m-color-success-bg);
  color: var(--m-color-success-text);
}
.m-sec-notice.warn {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning-text);
}
.m-sec-notice.error {
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger-text);
}

/* === 表单 === */
.m-sec-form {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-3);
}

.m-sec-card {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-4);
  box-shadow: var(--m-shadow-xs);
}
.m-sec-card-head { margin-bottom: var(--m-space-4); }
.m-sec-card-head h3 {
  margin: 0 0 var(--m-space-1);
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
}
.m-sec-card-head p {
  margin: 0;
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  line-height: var(--m-line-height-base);
}

.m-sec-current {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-space-3);
  background: var(--m-color-primary-bg);
  border-radius: var(--m-radius-lg);
  margin-bottom: var(--m-space-4);
  gap: var(--m-space-3);
}
.m-sec-current-label {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  flex-shrink: 0;
}
.m-sec-current-value {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
  text-align: right;
}

.m-sec-field {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-1);
  margin-bottom: var(--m-space-3);
}
.m-sec-label {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-secondary);
  font-weight: var(--m-font-weight-semibold);
}
.m-sec-input {
  width: 100%;
  height: 44px;
  border-radius: var(--m-radius-lg);
  border: none;
  background: var(--m-color-bg-subtle);
  padding: 0 var(--m-space-4);
  font-size: var(--m-font-size-h3);
  color: var(--m-color-text-primary);
  outline: none;
  box-sizing: border-box;
  transition: background 0.15s;
}
.m-sec-input::placeholder { color: var(--m-color-text-placeholder); }
.m-sec-input:focus {
  background: var(--m-color-bg-card);
  box-shadow: inset 0 0 0 2px var(--m-color-primary);
}

.m-sec-code-row {
  display: flex;
  gap: var(--m-space-2);
  align-items: flex-end;
}
.m-sec-code-field {
  flex: 1;
  margin-bottom: var(--m-space-3);
  min-width: 0;
}
.m-sec-code-btn {
  height: 44px;
  border: none;
  background: var(--m-color-bg-card);
  color: var(--m-color-primary);
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  border-radius: var(--m-radius-lg);
  padding: 0 var(--m-space-4);
  cursor: pointer;
  flex-shrink: 0;
  white-space: nowrap;
  margin-bottom: var(--m-space-3);
  box-shadow: var(--m-shadow-xs);
}
.m-sec-code-btn:disabled {
  color: var(--m-color-text-disabled);
  background: var(--m-color-bg-subtle);
  cursor: not-allowed;
  box-shadow: none;
}
.m-sec-code-btn:not(:disabled):active {
  background: var(--m-color-primary-bg);
}

.m-sec-submit {
  width: 100%;
  height: 48px;
  border-radius: var(--m-radius-lg);
  border: none;
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  margin-top: var(--m-space-1);
  box-shadow: var(--m-shadow-xs);
}
.m-sec-submit:disabled {
  background: var(--m-color-text-disabled);
  cursor: not-allowed;
  box-shadow: none;
}
.m-sec-submit:not(:disabled):active { transform: scale(0.98); }

.m-safe-bottom { height: 60px; }
</style>
