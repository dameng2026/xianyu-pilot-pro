<template>
  <div class="m-profile">
    <MobileUnavailableState v-if="overviewError" compact title="个人资料暂时无法加载" :description="overviewError" @retry="loadOverview" />
    <!-- 用户卡片 -->
    <div class="m-pro-hero">
      <div class="m-pro-avatar">
        <MIcon name="user" :size="32" />
      </div>
      <div class="m-pro-info">
        <div class="m-pro-name">{{ displayName }}</div>
        <div class="m-pro-desc">
          <MIcon name="crown" :size="12" /> {{ planName }}
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
    </div>

    <!-- 数据统计 -->
    <div class="m-pro-stats">
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
    <div class="m-section m-token-card">
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
          <div class="m-menu-icon" style="background:linear-gradient(135deg,#e8f1ff,#d0e2ff);color:#0d6bff">
            <MIcon name="user" :size="20" />
          </div>
          <div class="m-menu-info">
            <div class="m-menu-title">个人中心</div>
            <div class="m-menu-desc">账号资料与安全</div>
          </div>
          <MIcon name="chevronRight" :size="16" class="m-menu-arrow" />
        </div>
        <div class="m-menu-item" @click="$emit('navigate', 'settings-notify')">
          <div class="m-menu-icon" style="background:linear-gradient(135deg,#fff4e0,#ffe7c2);color:#ff9f22">
            <MIcon name="bell" :size="20" />
          </div>
          <div class="m-menu-info">
            <div class="m-menu-title">通知设置</div>
            <div class="m-menu-desc">消息与提醒配置</div>
          </div>
          <MIcon name="chevronRight" :size="16" class="m-menu-arrow" />
        </div>
        <div class="m-menu-item" @click="$emit('navigate', 'settings-ai-cs')">
          <div class="m-menu-icon" style="background:linear-gradient(135deg,#e2f8ee,#cdf2df);color:#16bf78">
            <MIcon name="settings" :size="20" />
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
          <div class="m-menu-icon" style="background:linear-gradient(135deg,#f0ebff,#e2d8ff);color:#8b5cf6">
            <MIcon name="lock" :size="20" />
          </div>
          <div class="m-menu-info">
            <div class="m-menu-title">修改密码</div>
            <div class="m-menu-desc">建议定期更换密码</div>
          </div>
          <MIcon name="chevronRight" :size="16" class="m-menu-arrow" />
        </div>
        <div class="m-menu-item" @click="$emit('navigate', 'profile-security')">
          <div class="m-menu-icon" :style="phoneVerificationState === true ? 'background:linear-gradient(135deg,#e2f8ee,#cdf2df);color:#16bf78' : 'background:linear-gradient(135deg,#fff4e0,#ffe7c2);color:#ff9f22'">
            <MIcon name="phone" :size="20" />
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
          <div class="m-menu-icon" :style="emailVerificationState === true ? 'background:linear-gradient(135deg,#e2f8ee,#cdf2df);color:#16bf78' : 'background:linear-gradient(135deg,#fff4e0,#ffe7c2);color:#ff9f22'">
            <MIcon name="mail" :size="20" />
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
          <div class="m-menu-icon" style="background:linear-gradient(135deg,#f0ebff,#e2d8ff);color:#8b5cf6">
            <MIcon name="help" :size="20" />
          </div>
          <div class="m-menu-info">
            <div class="m-menu-title">操作日志</div>
            <div class="m-menu-desc">查看系统操作记录</div>
          </div>
          <MIcon name="chevronRight" :size="16" class="m-menu-arrow" />
        </div>
        <div class="m-menu-item" @click="$emit('navigate', 'vip')">
          <div class="m-menu-icon" style="background:linear-gradient(135deg,#fff0d6,#ffe0a3);color:#f0a020">
            <MIcon name="rocket" :size="20" />
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
// 充值记录（最近 5 条，移动端只显示简要列表，完整记录跳转桌面版）
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
  // 支付成功后同步刷新充值记录
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

// 来源标签文案
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
  padding: 12px 16px 0;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
}

.m-pro-hero {
  background: linear-gradient(135deg, #e8f1ff 0%, #f0f5ff 100%);
  border-radius: 20px;
  padding: 18px;
  display: flex;
  align-items: flex-start;
  gap: 14px;
  margin-bottom: 14px;
}
.m-pro-avatar {
  width: 58px;
  height: 58px;
  border-radius: 50%;
  background: linear-gradient(135deg, #0d6bff, #3b9bff);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 6px 16px rgba(13,107,255,0.25);
  flex-shrink: 0;
}
.m-pro-info { flex: 1; min-width: 0; }
.m-pro-name {
  font-size: 20px;
  font-weight: 700;
  color: #15213d;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-pro-desc {
  font-size: 12px;
  color: #72809a;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 8px;
  max-width: 100%;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-pro-desc :deep(svg) { color: #f0a020; }
.m-pro-verify {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.m-pro-tag {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 10px;
  padding: 3px 7px;
  border-radius: 100px;
  font-weight: 500;
}
.m-pro-tag.ok {
  background: rgba(22,191,120,0.12);
  color: #16bf78;
}
.m-pro-tag.warn {
  background: rgba(255,159,34,0.12);
  color: #ff9f22;
}
.m-pro-tag.unknown { background: rgba(140, 152, 174, 0.16); color: #6f7c91; }

.m-pro-stats {
  background: white;
  border-radius: 18px;
  padding: 18px 8px;
  display: flex;
  align-items: center;
  justify-content: space-around;
  margin-bottom: 14px;
  border: 1px solid #f0f4fa;
  box-shadow: 0 2px 8px rgba(31,53,94,0.04);
}
.m-pro-stat {
  flex: 1;
  text-align: center;
  cursor: pointer;
  padding: 4px;
}
.m-pro-stat-val { font-size: 22px; font-weight: 800; color: #15213d; margin-bottom: 3px; }
.m-pro-stat-label { font-size: 12px; color: #8c98ae; }
.m-pro-stat-div {
  width: 1px;
  height: 32px;
  background: #e8edf5;
}

.m-section {
  background: white;
  border-radius: 20px;
  padding: 16px;
  margin-bottom: 14px;
  box-shadow: 0 2px 8px rgba(31,53,94,0.04);
  border: 1px solid #f0f4fa;
}
.m-section-header {
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.m-section-header h2 { margin: 0; font-size: 17px; font-weight: 700; color: #15213d; }
.m-section-action {
  background: none;
  border: none;
  color: #0d6bff;
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  gap: 2px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 100px;
}
.m-section-action:active { background: rgba(13,107,255,0.08); }

/* Token 卡片 */
.m-token-card {
  background: linear-gradient(135deg, #fff9e6 0%, #fff5d6 100%);
  border-color: #ffe7a3;
}
.m-token-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
}
.m-token-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.m-token-icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: linear-gradient(135deg, #ffb94a, #ff9500);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 4px 10px rgba(255,153,0,0.25);
}
.m-token-label { font-size: 12px; color: #8c6d20; margin-bottom: 2px; }
.m-token-val { font-size: 24px; font-weight: 800; color: #5b3f00; line-height: 1.1; }
.m-token-btn {
  background: linear-gradient(135deg, #ffb94a, #ff9500);
  color: white;
  border: none;
  border-radius: 100px;
  padding: 8px 18px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 10px rgba(255,153,0,0.3);
  flex-shrink: 0;
}
.m-token-btn:active { transform: scale(0.96); }
.m-token-plan {
  background: rgba(255,255,255,0.6);
  border-radius: 12px;
  padding: 10px 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.m-token-plan-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.m-token-plan-name {
  font-size: 13px;
  font-weight: 600;
  color: #5b3f00;
  overflow-wrap: anywhere;
}
.m-token-plan-expire {
  font-size: 11px;
  color: #8c6d20;
}
.m-token-renew {
  background: white;
  color: #ff9500;
  border: 1px solid #ffd699;
  border-radius: 100px;
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  flex-shrink: 0;
}

/* Token 流水 */
.m-ledger-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.m-ledger-empty { padding: 18px 0; color: #98a2b3; font-size: 13px; text-align: center; }
.m-ledger-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 4px;
  border-bottom: 1px solid #f4f7fc;
}
.m-ledger-item:last-child { border-bottom: none; }
.m-ledger-info { flex: 1; min-width: 0; }
.m-ledger-title {
  font-size: 13px;
  font-weight: 600;
  color: #15213d;
  margin-bottom: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-ledger-time { font-size: 11px; color: #b0bacb; }
.m-ledger-amount {
  font-size: 14px;
  font-weight: 700;
  flex-shrink: 0;
}
.m-ledger-amount.plus { color: #16bf78; }
.m-ledger-amount.minus { color: #ef4444; }

/* 充值记录列表 */
.m-recharge-list {
  display: flex;
  flex-direction: column;
}
.m-recharge-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid #f0f3f7;
}
.m-recharge-item:last-child { border-bottom: none; }
.m-recharge-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, #e8f7ef, #d4f0e0);
  color: #16bf78;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-recharge-info { flex: 1; min-width: 0; }
.m-recharge-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-recharge-time { font-size: 11px; color: #b0bacb; margin-top: 2px; }
.m-recharge-amount {
  font-size: 15px;
  font-weight: 700;
  color: #16bf78;
  flex-shrink: 0;
}

/* 菜单 */
.m-menu-list { display: flex; flex-direction: column; gap: 2px; }
.m-menu-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 4px;
  cursor: pointer;
  border-radius: 10px;
  transition: background 0.15s;
}
.m-menu-item:active { background: #f8faff; }
.m-menu-icon {
  width: 40px;
  height: 40px;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-menu-info { flex: 1; min-width: 0; }
.m-menu-title { font-size: 14px; font-weight: 600; color: #15213d; margin-bottom: 2px; }
.m-menu-desc {
  font-size: 12px;
  color: #8c98ae;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-menu-arrow { color: #c4cddb; flex-shrink: 0; }
.m-menu-status {
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 100px;
  font-weight: 600;
  flex-shrink: 0;
}
.m-menu-status.ok {
  background: rgba(22,191,120,0.12);
  color: #16bf78;
}
.m-menu-status.warn {
  background: rgba(255,159,34,0.12);
  color: #ff9f22;
}
.m-menu-status.unknown { background: #eef1f5; color: #6f7c91; }

@media (max-width: 480px) {
  .m-pro-stats {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    justify-content: stretch;
    padding: 8px;
  }
  .m-pro-stat {
    min-width: 0;
    padding: 12px 8px;
  }
  .m-pro-stat-div { display: none; }
  .m-pro-stat-val {
    font-size: 20px;
    overflow-wrap: anywhere;
  }
}

@media (max-width: 360px) {
  .m-token-plan {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }

  .m-token-renew {
    align-self: flex-start;
  }
}

/* 操作按钮 */
.m-pro-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 4px;
}
.m-btn {
  width: 100%;
  height: 48px;
  border-radius: 24px;
  border: none;
  font-size: 15px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  cursor: pointer;
  transition: transform 0.1s;
}
.m-btn:active { transform: scale(0.98); }
.m-btn-outline {
  background: white;
  color: #0d6bff;
  border: 1.5px solid #d4e4ff;
}
.m-btn-danger {
  background: #fff5f5;
  color: #ff5252;
  border: 1.5px solid #ffd1d1;
}

.m-safe-bottom { height: 80px; }
</style>
