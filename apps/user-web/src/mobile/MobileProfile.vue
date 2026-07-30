<template>
  <div class="m-profile">
    <MobileUnavailableState v-if="overviewError" compact title="个人资料暂时无法加载" :description="overviewError" @retry="loadOverview" />
    
    <!-- 用户信息卡片 -->
    <div class="m-pro-hero-card">
      <div class="m-pro-hero">
        <div class="m-pro-avatar">
          <MIcon name="user" :size="28" />
        </div>
        <div class="m-pro-info">
          <div class="m-pro-name">{{ displayName }}</div>
          <div class="m-pro-desc">
            <span class="m-pro-plan-badge">
              <MIcon name="crown" :size="12" /> {{ planName }}
            </span>
          </div>
        </div>
      </div>
      <div class="m-pro-verify">
        <span class="m-pro-tag" :class="verificationClass(emailVerificationState)">
          <MIcon name="mail" :size="10" /> {{ verificationText(emailVerificationState, '邮箱') }}
        </span>
        <span class="m-pro-tag" :class="verificationClass(phoneVerificationState)">
          <MIcon name="phone" :size="10" /> {{ verificationText(phoneVerificationState, '手机') }}
        </span>
      </div>
    </div>

    <!-- 数据统计 -->
    <div class="m-pro-stats-card">
      <div class="m-pro-stat" @click="$emit('navigate', 'accounts')">
        <div class="m-pro-stat-val">{{ metricText(stats.xianyuAccountCount) }}</div>
        <div class="m-pro-stat-label">闲鱼账号</div>
      </div>
      <div class="m-pro-stat-div"></div>
      <div class="m-pro-stat" @click="$emit('navigate', 'products')">
        <div class="m-pro-stat-val">{{ metricText(stats.goodsCount) }}</div>
        <div class="m-pro-stat-label">商品</div>
      </div>
      <div class="m-pro-stat-div"></div>
      <div class="m-pro-stat" @click="$emit('navigate', 'orders')">
        <div class="m-pro-stat-val">{{ metricText(stats.orderCount) }}</div>
        <div class="m-pro-stat-label">订单</div>
      </div>
      <div class="m-pro-stat-div"></div>
      <div class="m-pro-stat" @click="$emit('tab-change', 'message')">
        <div class="m-pro-stat-val">{{ metricText(stats.conversationCount) }}</div>
        <div class="m-pro-stat-label">会话</div>
      </div>
    </div>

    <!-- Token 余额卡片 -->
    <div class="m-token-card">
      <div class="m-token-header">
        <div class="m-token-left">
          <div class="m-token-icon">
            <MIcon name="coins" :size="20" />
          </div>
          <div>
            <div class="m-token-label">Token 余额</div>
            <div class="m-token-val">{{ formatNumber(overview.tokenBalance) }}</div>
          </div>
        </div>
        <button class="m-token-btn" @click="paymentVisible = true">充值</button>
      </div>
      <div v-if="overview.activePlan" class="m-token-plan">
        <div class="m-token-plan-info">
          <span class="m-token-plan-name">{{ overview.activePlan.planName || '当前套餐' }}</span>
          <span v-if="overview.activePlan.expireTime || overview.expireTime" class="m-token-plan-expire">
            到期 {{ formatDateOnly(overview.activePlan.expireTime || overview.expireTime) }}
          </span>
        </div>
        <button class="m-token-renew" @click="paymentVisible = true">续费</button>
      </div>
    </div>

    <!-- 最近 Token 流水 -->
    <MobileUnavailableState v-if="ledgerError" compact title="Token 流水暂时不可用" :description="ledgerError" @retry="loadTokenLedger" />
    <div v-if="tokenLedger.length > 0" class="m-section">
      <div class="m-section-header">
        <h2>Token 流水</h2>
        <button class="m-section-action" @click="$emit('navigate', 'profile-ledger')">
          全部<MIcon name="chevronRight" :size="12" />
        </button>
      </div>
      <div class="m-ledger-list">
        <div
          v-for="log in tokenLedger"
          :key="log.id || log.createdTime"
          class="m-ledger-item"
        >
          <div class="m-ledger-info">
            <div class="m-ledger-title">{{ log.actionName || log.action_type || 'Token 操作' }}</div>
            <div class="m-ledger-time">{{ formatTime(log.createdTime || log.createdAt) }}</div>
          </div>
          <div class="m-ledger-amount" :class="{ plus: isPositive(log), minus: !isPositive(log) }">
            {{ formatAmount(log) }}
          </div>
        </div>
      </div>
    </div>
    <div v-else-if="!ledgerError" class="m-section">
      <div class="m-section-header"><h2>Token 流水</h2></div>
      <div class="m-ledger-empty">暂无 Token 流水</div>
    </div>

    <!-- 最近充值记录 -->
    <MobileUnavailableState v-if="rechargeError" compact title="充值记录暂时不可用" :description="rechargeError" @retry="loadRechargeRecords" />
    <div v-if="rechargeRecords.length > 0" class="m-section">
      <div class="m-section-header">
        <h2>充值记录</h2>
        <button class="m-section-action" @click="$emit('navigate', 'profile-recharge')">
          全部<MIcon name="chevronRight" :size="12" />
        </button>
      </div>
      <div class="m-recharge-list">
        <div
          v-for="row in rechargeRecords"
          :key="row.id"
          class="m-recharge-item"
        >
          <div class="m-recharge-icon">
            <MIcon name="coins" :size="18" />
          </div>
          <div class="m-recharge-info">
            <div class="m-recharge-title">{{ rechargeSourceLabel(row.source) }}</div>
            <div class="m-recharge-time">{{ formatTime(row.createdTime) }}</div>
          </div>
          <div class="m-recharge-amount">+{{ formatNumber(row.tokenAmount) }}</div>
        </div>
      </div>
    </div>
    <div v-else-if="!rechargeError && !rechargeLoading" class="m-section">
      <div class="m-section-header">
        <h2>充值记录</h2>
        <button class="m-section-action" @click="$emit('navigate', 'profile-recharge')">
          全部<MIcon name="chevronRight" :size="12" />
        </button>
      </div>
      <div class="m-ledger-empty">暂无充值记录</div>
    </div>

    <!-- 账号设置 -->
    <div class="m-section">
      <div class="m-section-header">
        <h2>账号设置</h2>
      </div>
      <div class="m-menu-list">
        <div class="m-menu-item" @click="openDesktopProfile('overview')">
          <div class="m-menu-icon m-menu-icon--primary">
            <MIcon name="user" :size="18" />
          </div>
          <div class="m-menu-info">
            <div class="m-menu-title">个人中心</div>
            <div class="m-menu-desc">账号资料与安全</div>
          </div>
          <MIcon name="chevronRight" :size="16" class="m-menu-arrow" />
        </div>
        <div class="m-menu-item" @click="$emit('navigate', 'settings-notify')">
          <div class="m-menu-icon m-menu-icon--warning">
            <MIcon name="bell" :size="18" />
          </div>
          <div class="m-menu-info">
            <div class="m-menu-title">通知设置</div>
            <div class="m-menu-desc">消息与提醒配置</div>
          </div>
          <MIcon name="chevronRight" :size="16" class="m-menu-arrow" />
        </div>
        <div class="m-menu-item" @click="$emit('navigate', 'settings-ai-cs')">
          <div class="m-menu-icon m-menu-icon--success">
            <MIcon name="settings" :size="18" />
          </div>
          <div class="m-menu-info">
            <div class="m-menu-title">系统设置</div>
            <div class="m-menu-desc">AI客服、商品操作与关于</div>
          </div>
          <MIcon name="chevronRight" :size="16" class="m-menu-arrow" />
        </div>
      </div>
    </div>

    <!-- 安全设置 -->
    <div class="m-section">
      <div class="m-section-header">
        <h2>安全设置</h2>
      </div>
      <div class="m-menu-list">
        <div class="m-menu-item" @click="$emit('navigate', 'profile-security')">
          <div class="m-menu-icon m-menu-icon--purple">
            <MIcon name="lock" :size="18" />
          </div>
          <div class="m-menu-info">
            <div class="m-menu-title">修改密码</div>
            <div class="m-menu-desc">建议定期更换密码</div>
          </div>
          <MIcon name="chevronRight" :size="16" class="m-menu-arrow" />
        </div>
        <div class="m-menu-item" @click="$emit('navigate', 'profile-security')">
          <div class="m-menu-icon" :class="phoneVerificationState === true ? 'm-menu-icon--success' : 'm-menu-icon--warning'">
            <MIcon name="phone" :size="18" />
          </div>
          <div class="m-menu-info">
            <div class="m-menu-title">手机绑定</div>
            <div class="m-menu-desc">{{ bindingText(maskedPhone, phoneVerificationState) }}</div>
          </div>
          <span class="m-menu-status" :class="verificationClass(phoneVerificationState)">
            {{ verificationStatusText(phoneVerificationState) }}
          </span>
        </div>
        <div class="m-menu-item" @click="$emit('navigate', 'profile-security')">
          <div class="m-menu-icon" :class="emailVerificationState === true ? 'm-menu-icon--success' : 'm-menu-icon--warning'">
            <MIcon name="mail" :size="18" />
          </div>
          <div class="m-menu-info">
            <div class="m-menu-title">邮箱绑定</div>
            <div class="m-menu-desc">{{ bindingText(maskedEmail, emailVerificationState) }}</div>
          </div>
          <span class="m-menu-status" :class="verificationClass(emailVerificationState)">
            {{ verificationStatusText(emailVerificationState) }}
          </span>
        </div>
      </div>
    </div>

    <!-- 其他 -->
    <div class="m-section">
      <div class="m-section-header">
        <h2>其他</h2>
      </div>
      <div class="m-menu-list">
        <div class="m-menu-item" @click="$emit('navigate', 'logs')">
          <div class="m-menu-icon m-menu-icon--purple">
            <MIcon name="help" :size="18" />
          </div>
          <div class="m-menu-info">
            <div class="m-menu-title">操作日志</div>
            <div class="m-menu-desc">查看系统操作记录</div>
          </div>
          <MIcon name="chevronRight" :size="16" class="m-menu-arrow" />
        </div>
        <div class="m-menu-item" @click="$emit('navigate', 'vip')">
          <div class="m-menu-icon m-menu-icon--warning">
            <MIcon name="rocket" :size="18" />
          </div>
          <div class="m-menu-info">
            <div class="m-menu-title">会员中心</div>
            <div class="m-menu-desc">查看套餐与权益</div>
          </div>
          <MIcon name="chevronRight" :size="16" class="m-menu-arrow" />
        </div>
      </div>
    </div>

    <!-- 操作按钮 -->
    <div class="m-pro-actions">
      <button class="m-btn m-btn-danger" @click="$emit('logout')">
        <MIcon name="logout" :size="18" />退出登录
      </button>
    </div>

    <div class="m-safe-bottom"></div>
    <MobilePaymentModal :visible="paymentVisible" order-type="token" @close="paymentVisible = false" @paid="handleTokenPaid" />
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import MIcon from './MIcon.vue'
import MobileUnavailableState from './MobileUnavailableState.vue'
import MobilePaymentModal from './components/MobilePaymentModal.vue'
import { getProfileOverview, getRechargeRecords, getTokenLedger } from '../api/profile.js'
import { getCachedUsername } from '../utils/auth.js'

const props = defineProps({
  user: { type: Object, default: () => ({}) }
})
const emit = defineEmits(['navigate', 'logout', 'force-desktop', 'tab-change'])

const overview = ref({})
const tokenLedger = ref([])
const overviewError = ref('')
const ledgerError = ref('')
const paymentVisible = ref(false)
const rechargeRecords = ref([])
const rechargeError = ref('')
const rechargeLoading = ref(false)

const displayName = computed(() => overview.value.nickname || overview.value.username || props.user?.username || getCachedUsername() || '当前用户')

const planName = computed(() => overview.value.activePlan?.planName || '套餐状态未知')

const stats = computed(() => overview.value.stats || {})
const phoneVerificationState = computed(() => booleanState(overview.value.phoneVerified))
const emailVerificationState = computed(() => booleanState(overview.value.emailVerified))

const maskedPhone = computed(() => {
  const p = overview.value.phone || overview.value.maskedPhone
  if (!p) return ''
  return p
})

const maskedEmail = computed(() => {
  const e = overview.value.email || overview.value.maskedEmail
  if (!e) return ''
  return e
})

function openDesktopProfile(profileTab) {
  emit('force-desktop', { page: 'profile', profileTab })
}

async function handleTokenPaid() {
  paymentVisible.value = false
  await loadOverview()
  loadRechargeRecords()
}

function formatNumber(n) {
  if (n == null) return '—'
  if (typeof n === 'number') {
    return n.toLocaleString()
  }
  return String(n)
}

function metricText(value) {
  return value === null || value === undefined ? '—' : value
}

function booleanState(value) {
  if (value === true || value === 1 || value === '1') return true
  if (value === false || value === 0 || value === '0') return false
  return null
}

function verificationClass(value) {
  return { ok: value === true, warn: value === false, unknown: value === null }
}

function verificationText(value, label) {
  if (value === true) return `${label}已验证`
  if (value === false) return label === '手机' ? '手机未绑定' : '邮箱未验证'
  return `${label}状态未知`
}

function verificationStatusText(value) {
  if (value === true) return '已验证'
  if (value === false) return '未验证'
  return '未知'
}

function bindingText(maskedValue, state) {
  if (maskedValue) return maskedValue
  if (state === false) return '未绑定'
  return '状态未知'
}

function formatDateOnly(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  if (isNaN(d.getTime())) return ''
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`
}

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  if (isNaN(d.getTime())) return ''
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const msgDay = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const diffDays = Math.floor((today - msgDay) / (1000 * 60 * 60 * 24))
  if (diffDays === 0) {
    return `今天 ${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`
  }
  if (diffDays === 1) return '昨天'
  if (diffDays < 7) return `${diffDays}天前`
  return `${d.getMonth()+1}/${d.getDate()}`
}

function isPositive(log) {
  const amount = Number(log.changeAmount ?? log.amount)
  return amount > 0
}

function formatAmount(log) {
  const rawAmount = log.changeAmount ?? log.amount
  if (rawAmount === null || rawAmount === undefined || rawAmount === '' || !Number.isFinite(Number(rawAmount))) return '—'
  const amount = Number(rawAmount)
  const prefix = amount > 0 ? '+' : ''
  return `${prefix}${amount}`
}

async function loadOverview() {
  overviewError.value = ''
  try {
    const res = await getProfileOverview()
    if (!res?.data || typeof res.data !== 'object' || Array.isArray(res.data)
      || typeof res.data.phoneVerified !== 'boolean'
      || typeof res.data.emailVerified !== 'boolean'
      || !res.data.stats || typeof res.data.stats !== 'object' || Array.isArray(res.data.stats)) {
      throw new Error('个人资料响应格式异常')
    }
    overview.value = res.data
  } catch (error) {
    overview.value = {}
    overviewError.value = error?.message || '请检查网络连接后重试。'
  }
}

async function loadTokenLedger() {
  ledgerError.value = ''
  try {
    const res = await getTokenLedger({ current: 1, size: 5 })
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data) || !Array.isArray(data.records)) {
      throw new Error('Token 流水响应格式异常')
    }
    const total = Number(data.total)
    if (!Number.isFinite(total) || total < data.records.length) throw new Error('Token 流水总数响应格式异常')
    const records = data.records
    tokenLedger.value = records
  } catch (error) {
    tokenLedger.value = []
    ledgerError.value = error?.message || '请检查网络连接后重试。'
  }
}

function rechargeSourceLabel(source) {
  if (!source) return '—'
  const map = {
    alipay: '支付宝',
    wechat: '微信支付',
    admin: '后台手动',
    system: '系统赠送',
    plan: '套餐购买',
    manual: '手动充值'
  }
  return map[String(source).toLowerCase()] || source
}

async function loadRechargeRecords() {
  rechargeLoading.value = true
  rechargeError.value = ''
  try {
    const res = await getRechargeRecords({ current: 1, size: 5 })
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data) || !Array.isArray(data.records)) {
      throw new Error('充值记录响应格式异常')
    }
    rechargeRecords.value = data.records.map((record, index) => ({
      ...record,
      id: record.id ?? `r-${index}`,
      createdTime: record.createdTime || record.createTime || record.time || '',
      orderNo: record.orderNo || record.paymentOrderId || '',
      tokenAmount: Number(record.tokenAmount ?? record.amount ?? (record.tokens || 0)),
      source: record.source || record.channel || '',
      remark: record.remark || record.description || ''
    }))
  } catch (error) {
    rechargeRecords.value = []
    rechargeError.value = error?.message || '请检查网络连接后重试。'
  } finally {
    rechargeLoading.value = false
  }
}

onMounted(() => {
  loadOverview()
  loadTokenLedger()
  loadRechargeRecords()
})
</script>

<style scoped>
.m-profile {
  padding: var(--m-space-3);
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
  background: var(--m-color-bg-page);
}

/* === 用户信息卡片 === */
.m-pro-hero-card {
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-5);
  margin-bottom: var(--m-space-3);
  box-shadow: var(--m-shadow-card);
}
.m-pro-hero {
  display: flex;
  align-items: center;
  gap: var(--m-space-4);
  margin-bottom: var(--m-space-4);
}
.m-pro-avatar {
  width: 56px;
  height: 56px;
  border-radius: var(--m-radius-circle);
  background: var(--m-color-primary-bg-solid);
  color: var(--m-color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-pro-info { flex: 1; min-width: 0; }
.m-pro-name {
  font-size: var(--m-font-size-h1);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
  margin-bottom: var(--m-space-1-5);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-pro-desc {
  display: flex;
  align-items: center;
}
.m-pro-plan-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-1);
  font-size: var(--m-font-size-caption);
  color: var(--m-color-warning);
  background: var(--m-color-warning-bg-solid);
  padding: var(--m-space-1) var(--m-space-2);
  border-radius: var(--m-radius-md);
  font-weight: var(--m-font-weight-medium);
}
.m-pro-plan-badge :deep(svg) { color: var(--m-color-warning); }
.m-pro-verify {
  display: flex;
  flex-wrap: wrap;
  gap: var(--m-space-2);
}
.m-pro-tag {
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-1);
  font-size: var(--m-font-size-caption);
  padding: var(--m-space-1) var(--m-space-2);
  border-radius: var(--m-radius-md);
  font-weight: var(--m-font-weight-medium);
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
}
.m-pro-tag.ok {
  background: var(--m-color-success-bg-solid);
  color: var(--m-color-emerald-dark);
}
.m-pro-tag.warn {
  background: var(--m-color-warning-bg-solid);
  color: var(--m-color-warning-text);
}
.m-pro-tag.unknown {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-tertiary);
}

/* === 数据统计卡片 === */
.m-pro-stats-card {
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-4) var(--m-space-2);
  display: flex;
  align-items: center;
  justify-content: space-around;
  margin-bottom: var(--m-space-3);
  box-shadow: var(--m-shadow-card);
}
.m-pro-stat {
  flex: 1;
  text-align: center;
  cursor: pointer;
  padding: var(--m-space-1);
  border-radius: var(--m-radius-md);
  transition: background var(--m-duration-fast);
}
.m-pro-stat:active {
  background: var(--m-color-bg-hover);
}
.m-pro-stat-val {
  font-size: var(--m-font-size-h1);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
  margin-bottom: var(--m-space-1);
  font-family: var(--m-font-family-number);
}
.m-pro-stat-label {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}
.m-pro-stat-div {
  width: 1px;
  height: var(--m-space-8);
  background: var(--m-color-border);
}

/* === 通用区块卡片 === */
.m-section {
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-4);
  margin-bottom: var(--m-space-3);
  box-shadow: var(--m-shadow-card);
}
.m-section-header {
  margin-bottom: var(--m-space-3);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.m-section-header h2 {
  margin: 0;
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
}
.m-section-action {
  background: none;
  border: none;
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-caption);
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-0-5);
  cursor: pointer;
  padding: var(--m-space-1) var(--m-space-1);
  border-radius: var(--m-radius-md);
  transition: all var(--m-duration-fast);
}
.m-section-action:active { background: var(--m-color-bg-hover); color: var(--m-color-primary); }

/* === Token 卡片 === */
.m-token-card {
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-5);
  margin-bottom: var(--m-space-3);
  box-shadow: var(--m-shadow-card);
}
.m-token-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--m-space-3);
  margin-bottom: var(--m-space-4);
}
.m-token-left {
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
}
.m-token-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--m-radius-lg);
  background: var(--m-color-primary-bg-solid);
  color: var(--m-color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-token-label {
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-secondary);
  margin-bottom: var(--m-space-0-5);
  font-weight: var(--m-font-weight-medium);
}
.m-token-val {
  font-size: var(--m-font-size-hero-sm);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
  line-height: var(--m-line-height-tight);
  font-family: var(--m-font-family-number);
}
.m-token-btn {
  background: var(--m-color-primary-gradient);
  color: var(--m-color-text-inverse);
  border: none;
  border-radius: var(--m-radius-pill);
  padding: var(--m-space-2) var(--m-space-5);
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  flex-shrink: 0;
  transition: all var(--m-duration-fast);
  box-shadow: var(--m-color-primary-soft-glow);
}
.m-token-btn:active { transform: scale(0.96); opacity: 0.9; }
.m-token-plan {
  background: var(--m-color-bg-subtle);
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3) var(--m-space-4);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.m-token-plan-info {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-0-5);
  min-width: 0;
}
.m-token-plan-name {
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  overflow-wrap: anywhere;
}
.m-token-plan-expire {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}
.m-token-renew {
  background: transparent;
  color: var(--m-color-primary);
  border: 1px solid var(--m-color-primary);
  border-radius: var(--m-radius-pill);
  padding: var(--m-space-1) var(--m-space-3);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  flex-shrink: 0;
  transition: all var(--m-duration-fast);
}
.m-token-renew:active { background: var(--m-color-primary-gradient); color: var(--m-color-text-inverse); border-color: transparent; }

/* === Token 流水 === */
.m-ledger-list {
  display: flex;
  flex-direction: column;
}
.m-ledger-empty {
  padding: var(--m-space-6) 0;
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-body-sm);
  text-align: center;
}
.m-ledger-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--m-space-3);
  padding: var(--m-space-3) var(--m-space-1);
  border-bottom: 1px solid var(--m-color-border);
}
.m-ledger-item:last-child { border-bottom: none; }
.m-ledger-info { flex: 1; min-width: 0; }
.m-ledger-title {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-medium);
  color: var(--m-color-text-primary);
  margin-bottom: var(--m-space-0-5);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-ledger-time {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}
.m-ledger-amount {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  flex-shrink: 0;
  font-family: var(--m-font-family-number);
}
.m-ledger-amount.plus { color: var(--m-color-emerald-dark); }
.m-ledger-amount.minus { color: var(--m-color-rose-dark); }

/* === 充值记录 === */
.m-recharge-list {
  display: flex;
  flex-direction: column;
}
.m-recharge-item {
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
  padding: var(--m-space-3) 0;
  border-bottom: 1px solid var(--m-color-border);
}
.m-recharge-item:last-child { border-bottom: none; }
.m-recharge-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--m-radius-lg);
  background: var(--m-color-emerald-bg-solid);
  color: var(--m-color-emerald);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-recharge-info { flex: 1; min-width: 0; }
.m-recharge-title {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-medium);
  color: var(--m-color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-recharge-time {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  margin-top: var(--m-space-0-5);
}
.m-recharge-amount {
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-emerald-dark);
  flex-shrink: 0;
  font-family: var(--m-font-family-number);
}

/* === 菜单列表 === */
.m-menu-list {
  display: flex;
  flex-direction: column;
}
.m-menu-item {
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
  padding: var(--m-space-3) var(--m-space-1);
  cursor: pointer;
  border-radius: var(--m-radius-lg);
  transition: background var(--m-duration-fast);
}
.m-menu-item:active { background: var(--m-color-bg-hover); }
.m-menu-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--m-radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-menu-icon--primary {
  background: var(--m-color-primary-bg-solid);
  color: var(--m-color-primary);
}
.m-menu-icon--warning {
  background: var(--m-color-warning-bg-solid);
  color: var(--m-color-warning);
}
.m-menu-icon--success {
  background: var(--m-color-emerald-bg-solid);
  color: var(--m-color-emerald);
}
.m-menu-icon--purple {
  background: var(--m-color-violet-bg-solid);
  color: var(--m-color-violet);
}
.m-menu-info { flex: 1; min-width: 0; }
.m-menu-title {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-medium);
  color: var(--m-color-text-primary);
  margin-bottom: var(--m-space-0-5);
}
.m-menu-desc {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-menu-arrow {
  color: var(--m-color-text-quaternary);
  flex-shrink: 0;
}
.m-menu-status {
  font-size: var(--m-font-size-caption);
  padding: var(--m-space-0-5) var(--m-space-2);
  border-radius: var(--m-radius-md);
  font-weight: var(--m-font-weight-medium);
  flex-shrink: 0;
}
.m-menu-status.ok {
  background: var(--m-color-emerald-bg-solid);
  color: var(--m-color-emerald-dark);
}
.m-menu-status.warn {
  background: var(--m-color-warning-bg-solid);
  color: var(--m-color-warning-text);
}
.m-menu-status.unknown {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
}

@media (max-width: 480px) {
  .m-pro-stats-card {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    justify-content: stretch;
    padding: var(--m-space-3) var(--m-space-2);
    gap: var(--m-space-2);
  }
  .m-pro-stat {
    min-width: 0;
    padding: var(--m-space-2) var(--m-space-2);
  }
  .m-pro-stat-div { display: none; }
  .m-pro-stat-val {
    font-size: var(--m-font-size-h2);
    overflow-wrap: anywhere;
  }
}

@media (max-width: 360px) {
  .m-token-plan {
    flex-direction: column;
    align-items: stretch;
    gap: var(--m-space-3);
  }
  .m-token-renew {
    align-self: flex-start;
  }
}

/* === 操作按钮 === */
.m-pro-actions {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-3);
  padding-bottom: var(--m-space-4);
}
.m-btn {
  width: 100%;
  height: 48px;
  border-radius: var(--m-radius-xl);
  border: none;
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-semibold);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-2);
  cursor: pointer;
  transition: all var(--m-duration-fast);
}
.m-btn:active { transform: scale(0.98); }
.m-btn-danger {
  background: var(--m-color-bg-card);
  color: var(--m-color-rose);
  border: 1px solid var(--m-color-rose);
  box-shadow: var(--m-shadow-card);
}

.m-safe-bottom { height: 80px; }
</style>
