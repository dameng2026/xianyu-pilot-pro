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
  padding: 12px 16px 0;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
}

.m-sec-tabs {
  display: flex;
  background: white;
  border-radius: 14px;
  padding: 4px;
  margin-bottom: 12px;
  gap: 4px;
  box-shadow: 0 2px 8px rgba(31,53,94,0.04);
  border: 1px solid #f0f4fa;
}
.m-sec-tab {
  flex: 1;
  border: none;
  background: transparent;
  color: #8c98ae;
  font-size: 13px;
  font-weight: 600;
  padding: 10px 6px;
  border-radius: 10px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  transition: all 0.18s;
  min-width: 0;
}
.m-sec-tab span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-sec-tab.active {
  background: linear-gradient(135deg, #0d6bff, #2580ff);
  color: white;
  box-shadow: 0 4px 12px rgba(13,107,255,0.25);
}

.m-sec-notice {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 12px;
  font-size: 13px;
  margin-bottom: 12px;
  border: 1px solid transparent;
}
.m-sec-notice.info {
  background: #eef4ff;
  color: #0d6bff;
  border-color: #d4e4ff;
}
.m-sec-notice.success {
  background: rgba(22,191,120,0.1);
  color: #16bf78;
  border-color: rgba(22,191,120,0.25);
}
.m-sec-notice.warn {
  background: rgba(255,159,34,0.1);
  color: #ff9f22;
  border-color: rgba(255,159,34,0.25);
}
.m-sec-notice.error {
  background: rgba(239,68,68,0.1);
  color: #ef4444;
  border-color: rgba(239,68,68,0.25);
}

.m-sec-form { display: flex; flex-direction: column; gap: 12px; }

.m-sec-card {
  background: white;
  border-radius: 18px;
  padding: 18px 16px;
  box-shadow: 0 2px 8px rgba(31,53,94,0.04);
  border: 1px solid #f0f4fa;
}
.m-sec-card-head { margin-bottom: 14px; }
.m-sec-card-head h3 {
  margin: 0 0 4px;
  font-size: 17px;
  font-weight: 700;
  color: #15213d;
}
.m-sec-card-head p {
  margin: 0;
  font-size: 12px;
  color: #8c98ae;
  line-height: 1.5;
}

.m-sec-current {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: #f5f8ff;
  border-radius: 10px;
  margin-bottom: 14px;
  gap: 10px;
}
.m-sec-current-label {
  font-size: 12px;
  color: #8c98ae;
  flex-shrink: 0;
}
.m-sec-current-value {
  font-size: 14px;
  font-weight: 600;
  color: #15213d;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
  text-align: right;
}

.m-sec-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
}
.m-sec-label {
  font-size: 12px;
  color: #5a6a85;
  font-weight: 600;
}
.m-sec-input {
  width: 100%;
  height: 44px;
  border-radius: 12px;
  border: 1px solid #e1e8f3;
  background: #f8faff;
  padding: 0 14px;
  font-size: 15px;
  color: #15213d;
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.15s, background 0.15s;
}
.m-sec-input::placeholder { color: #b0bacb; }
.m-sec-input:focus {
  border-color: #0d6bff;
  background: white;
}

.m-sec-code-row {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}
.m-sec-code-field {
  flex: 1;
  margin-bottom: 12px;
  min-width: 0;
}
.m-sec-code-btn {
  height: 44px;
  border: 1px solid #d4e4ff;
  background: white;
  color: #0d6bff;
  font-size: 13px;
  font-weight: 600;
  border-radius: 12px;
  padding: 0 14px;
  cursor: pointer;
  flex-shrink: 0;
  white-space: nowrap;
  margin-bottom: 12px;
}
.m-sec-code-btn:disabled {
  color: #b0bacb;
  background: #f5f7fb;
  border-color: #eef2fa;
  cursor: not-allowed;
}
.m-sec-code-btn:not(:disabled):active {
  background: #eef4ff;
}

.m-sec-submit {
  width: 100%;
  height: 48px;
  border-radius: 24px;
  border: none;
  background: linear-gradient(135deg, #0d6bff, #2580ff);
  color: white;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  margin-top: 6px;
  box-shadow: 0 6px 16px rgba(13,107,255,0.25);
}
.m-sec-submit:disabled {
  background: #c4cddb;
  box-shadow: none;
  cursor: not-allowed;
}
.m-sec-submit:not(:disabled):active { transform: scale(0.98); }

.m-safe-bottom { height: 60px; }
</style>
