<template>
  <div class="m-profile-recharge">
    <!-- 错误状态 -->
    <MobileUnavailableState
      v-if="loadError"
      compact
      title="充值记录暂时不可用"
      :description="loadError"
      @retry="loadRecharge(1)"
    />

    <!-- 加载中 -->
    <div v-if="loading && records.length === 0" class="m-recharge-loading">
      <MIcon name="refresh" :size="20" />
      <span>正在加载…</span>
    </div>

    <!-- 列表 -->
    <div v-if="records.length > 0" class="m-recharge-list">
      <div
        v-for="row in records"
        :key="row.id"
        class="m-recharge-item"
      >
        <div class="m-recharge-head">
          <div class="m-recharge-icon">
            <MIcon name="coins" :size="18" />
          </div>
          <div class="m-recharge-source">
            <span class="m-recharge-source-tag">{{ sourceLabel(row.source) }}</span>
            <span class="m-recharge-status-tag" :class="statusClass(row.status)">
              {{ statusLabel(row.status) }}
            </span>
          </div>
          <div class="m-recharge-amount">+{{ formatNumber(row.tokenAmount) }}</div>
        </div>
        <div class="m-recharge-meta">
          <div class="m-recharge-time">{{ formatTime(row.createdTime) }}</div>
          <div v-if="row.orderNo" class="m-recharge-order">
            <span class="m-recharge-order-label">订单号</span>
            <span class="m-recharge-order-value">{{ row.orderNo }}</span>
          </div>
        </div>
        <div v-if="row.remark" class="m-recharge-remark">{{ row.remark }}</div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!loading && !loadError" class="m-recharge-empty">
      <MIcon name="coins" :size="40" />
      <p>暂无充值记录</p>
    </div>

    <!-- 分页 -->
    <div v-if="totalPages > 1" class="m-recharge-pager">
      <button
        class="m-recharge-page-btn"
        :disabled="current <= 1 || loading"
        @click="loadRecharge(current - 1)"
      >
        <MIcon name="chevronLeft" :size="14" />
      </button>
      <span class="m-recharge-page-info">
        {{ current }} / {{ totalPages }}
        <span class="m-recharge-page-total">（共 {{ total }} 条）</span>
      </span>
      <button
        class="m-recharge-page-btn"
        :disabled="current >= totalPages || loading"
        @click="loadRecharge(current + 1)"
      >
        <MIcon name="chevronRight" :size="14" />
      </button>
    </div>

    <div class="m-safe-bottom"></div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import MIcon from './MIcon.vue'
import MobileUnavailableState from './MobileUnavailableState.vue'
import { getRechargeRecords } from '../api/profile.js'

const records = ref([])
const current = ref(1)
const size = ref(10)
const total = ref(0)
const loading = ref(false)
const loadError = ref('')

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / size.value)))

function nullableNumber(value) {
  if (value === null || value === undefined || value === '') return 0
  const num = Number(value)
  return Number.isFinite(num) ? num : 0
}

function formatNumber(value) {
  if (value === null || value === undefined || value === '') return '0'
  const n = Number(value)
  return Number.isFinite(n) ? n.toLocaleString('zh-CN') : '0'
}

function sourceLabel(source) {
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

function statusLabel(status) {
  if (!status) return '成功'
  const s = String(status).toLowerCase()
  if (s === 'success' || s === 'paid' || s === 'completed' || s === '1' || s === 'ok') return '成功'
  if (s === 'pending' || s === 'processing' || s === 'waiting') return '处理中'
  if (s === 'failed' || s === 'error' || s === 'cancelled' || s === 'canceled') return '失败'
  return '成功'
}

function statusClass(status) {
  const label = statusLabel(status)
  if (label === '成功') return 'success'
  if (label === '处理中') return 'pending'
  if (label === '失败') return 'failed'
  return 'success'
}

function formatTime(value) {
  if (!value) return ''
  const d = new Date(value)
  if (isNaN(d.getTime())) return String(value).slice(0, 16)
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadRecharge(page = 1) {
  loading.value = true
  loadError.value = ''
  try {
    const res = await getRechargeRecords({ current: page, size: size.value })
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data) || !Array.isArray(data.records)) {
      throw new Error('充值记录响应格式异常')
    }
    records.value = data.records.map((record, index) => ({
      ...record,
      id: record.id ?? `r-${page}-${index}`,
      createdTime: record.createdTime || record.createTime || record.time || '',
      orderNo: record.orderNo || record.paymentOrderId || '',
      tokenAmount: nullableNumber(record.tokenAmount ?? record.amount ?? record.tokens),
      beforeBalance: nullableNumber(record.beforeBalance ?? record.balanceBefore),
      afterBalance: nullableNumber(record.afterBalance ?? record.balanceAfter),
      source: record.source || record.channel || '',
      status: record.status || record.payStatus || '',
      remark: record.remark || record.description || ''
    }))
    total.value = Number(data.total) || 0
    current.value = Number(data.current) || page
    size.value = Number(data.size) || size.value
  } catch (error) {
    records.value = []
    total.value = 0
    loadError.value = error?.message || '请检查网络连接后重试。'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadRecharge(1)
})
</script>

<style scoped>
.m-profile-recharge {
  padding: var(--m-space-3) var(--m-space-4) 0;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
}

/* === 加载中 === */
.m-recharge-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--m-space-2);
  padding: var(--m-space-10) 0;
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-body-sm);
}
.m-recharge-loading :deep(svg) {
  animation: mRechargeSpin 1.2s linear infinite;
}
@keyframes mRechargeSpin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* === 充值记录列表 === */
.m-recharge-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-3);
}
.m-recharge-item {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3) var(--m-space-4);
  box-shadow: var(--m-shadow-card);
  border: 1px solid var(--m-color-border-light);
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
}

.m-recharge-head {
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
}
.m-recharge-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--m-radius-md);
  background: var(--m-color-success-bg);
  color: var(--m-color-success);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-recharge-source {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: var(--m-space-1);
  align-items: center;
}
.m-recharge-source-tag {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
}
.m-recharge-status-tag {
  display: inline-flex;
  align-items: center;
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-semibold);
  padding: var(--m-space-1) var(--m-space-2);
  border-radius: var(--m-radius-pill);
}
.m-recharge-status-tag.success {
  background: var(--m-color-success-bg);
  color: var(--m-color-success-text);
}
.m-recharge-status-tag.pending {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning-text);
}
.m-recharge-status-tag.failed {
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger-text);
}
.m-recharge-amount {
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-extrabold);
  color: var(--m-color-success-text);
  flex-shrink: 0;
}

.m-recharge-meta {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-1);
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}
.m-recharge-time {
  font-size: var(--m-font-size-caption);
}
.m-recharge-order {
  display: flex;
  align-items: center;
  gap: var(--m-space-1);
  font-size: var(--m-font-size-caption);
  min-width: 0;
}
.m-recharge-order-label {
  color: var(--m-color-text-tertiary);
  flex-shrink: 0;
}
.m-recharge-order-value {
  color: var(--m-color-text-secondary);
  font-family: var(--m-font-family-mono);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.m-recharge-remark {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-md);
  padding: var(--m-space-2) var(--m-space-2);
  line-height: var(--m-line-height-base);
  overflow-wrap: anywhere;
}

/* === 空状态 === */
.m-recharge-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--m-space-3);
  padding: var(--m-space-12) 0;
  color: var(--m-color-text-tertiary);
}
.m-recharge-empty :deep(svg) { color: var(--m-color-text-disabled); }
.m-recharge-empty p {
  margin: 0;
  font-size: var(--m-font-size-body-sm);
}

/* === 分页 === */
.m-recharge-pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-3);
  padding: var(--m-space-4) 0;
}
.m-recharge-page-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--m-radius-circle);
  border: 1px solid var(--m-color-border);
  background: var(--m-color-bg-card);
  color: var(--m-color-text-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
}
.m-recharge-page-btn:disabled {
  color: var(--m-color-text-disabled);
  background: var(--m-color-bg-subtle);
  cursor: not-allowed;
}
.m-recharge-page-btn:not(:disabled):active { background: var(--m-color-bg-hover); }
.m-recharge-page-info {
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-primary);
  font-weight: var(--m-font-weight-semibold);
}
.m-recharge-page-total {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  font-weight: var(--m-font-weight-regular);
}

.m-safe-bottom { height: 60px; }
</style>
