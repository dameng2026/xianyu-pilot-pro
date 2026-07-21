<template>
  <div class="m-profile-ledger">
    <!-- 类型筛选 -->
    <div class="m-ledger-filters">
      <button
        v-for="opt in filterOptions"
        :key="opt.value"
        class="m-ledger-filter"
        :class="{ active: activeFilter === opt.value }"
        @click="setFilter(opt.value)"
      >
        {{ opt.label }}
      </button>
    </div>

    <!-- 错误状态 -->
    <MobileUnavailableState
      v-if="loadError"
      compact
      title="Token 流水暂时不可用"
      :description="loadError"
      @retry="loadLedger(1)"
    />

    <!-- 加载中 -->
    <div v-if="loading && records.length === 0" class="m-ledger-loading">
      <MIcon name="refresh" :size="20" />
      <span>正在加载…</span>
    </div>

    <!-- 列表 -->
    <div v-if="filteredRecords.length > 0" class="m-ledger-list">
      <div
        v-for="row in filteredRecords"
        :key="row.id"
        class="m-ledger-item"
      >
        <div class="m-ledger-top">
          <span class="m-ledger-type-tag" :class="changeTypeClass(row.changeType)">
            {{ changeTypeLabel(row.changeType) }}
          </span>
          <span class="m-ledger-amount" :class="amountClass(row.changeAmount)">
            {{ formatAmount(row.changeAmount) }}
          </span>
        </div>
        <div class="m-ledger-mid">
          <span class="m-ledger-module">{{ refTypeLabel(row.refType) }}</span>
          <span class="m-ledger-time">{{ formatTime(row.createdTime) }}</span>
        </div>
        <div v-if="row.afterBalance != null" class="m-ledger-balance">
          余额 {{ formatNumber(row.afterBalance) }}
        </div>
        <div v-if="row.remark" class="m-ledger-remark">{{ row.remark }}</div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!loading && !loadError" class="m-ledger-empty">
      <MIcon name="coins" :size="40" />
      <p>{{ activeFilter === 'all' ? '暂无 Token 流水' : '当前筛选下暂无记录' }}</p>
    </div>

    <!-- 分页 -->
    <div v-if="totalPages > 1" class="m-ledger-pager">
      <button
        class="m-ledger-page-btn"
        :disabled="current <= 1 || loading"
        @click="loadLedger(current - 1)"
      >
        <MIcon name="chevronLeft" :size="14" />
      </button>
      <span class="m-ledger-page-info">
        {{ current }} / {{ totalPages }}
        <span class="m-ledger-page-total">（共 {{ total }} 条）</span>
      </span>
      <button
        class="m-ledger-page-btn"
        :disabled="current >= totalPages || loading"
        @click="loadLedger(current + 1)"
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
import { getTokenLedger } from '../api/profile.js'

const filterOptions = [
  { value: 'all', label: '全部' },
  { value: 'consume', label: '消费' },
  { value: 'recharge', label: '充值' },
  { value: 'refund', label: '退款' }
]

const activeFilter = ref('all')
const records = ref([])
const current = ref(1)
const size = ref(10)
const total = ref(0)
const loading = ref(false)
const loadError = ref('')

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / size.value)))

const filteredRecords = computed(() => {
  if (activeFilter.value === 'all') return records.value
  return records.value.filter(row => matchFilter(row, activeFilter.value))
})

function matchFilter(row, filter) {
  const type = String(row.changeType || '').toLowerCase()
  if (filter === 'recharge') return type === 'recharge'
  if (filter === 'refund') return type === 'refund'
  // consume：所有非充值、非退款的负向变动
  return type !== 'recharge' && type !== 'refund'
}

function setFilter(value) {
  if (activeFilter.value === value) return
  activeFilter.value = value
  // 切换筛选时回到第 1 页，确保看到的是符合条件的首批数据
  if (current.value !== 1) {
    loadLedger(1)
  }
}

function nullableNumber(value) {
  if (value === null || value === undefined || value === '') return null
  const num = Number(value)
  return Number.isFinite(num) ? num : null
}

function formatNumber(value) {
  if (value === null || value === undefined || value === '') return '—'
  const n = Number(value)
  return Number.isFinite(n) ? n.toLocaleString('zh-CN') : '—'
}

function formatAmount(value) {
  const num = nullableNumber(value)
  if (num === null) return '—'
  const prefix = num > 0 ? '+' : ''
  return `${prefix}${num.toLocaleString('zh-CN')}`
}

function amountClass(value) {
  const num = nullableNumber(value)
  if (num === null) return ''
  return num >= 0 ? 'plus' : 'minus'
}

function changeTypeLabel(type) {
  const map = {
    recharge: '充值',
    ai_charge: 'AI扣费',
    ai_image_charge: '生图扣费',
    deduct: '消耗',
    deduct_image: '生图',
    deduct_rewrite: '改写',
    deduct_chat: '对话',
    refund: '退款',
    admin_adjust: '管理员调整',
    system: '系统'
  }
  return map[type] || type || '操作'
}

function changeTypeClass(type) {
  if (!type) return 'orange'
  const t = String(type).toLowerCase()
  if (t === 'recharge' || t === 'refund') return 'green'
  if (t === 'ai_charge' || t === 'ai_image_charge' || t.startsWith('deduct')) return 'red'
  return 'orange'
}

function refTypeLabel(type) {
  if (!type) return '—'
  const map = {
    ai_usage: 'AI 调用',
    payment_order: '支付订单',
    payment: '支付订单',
    image_gen: 'AI 生图',
    admin: '管理员',
    system: '系统',
    auto_delivery: '自动发货',
    auto_reply: '在线消息',
    workflow: '工作流',
    product_publish: '发布商品',
    opportunity: '商机发掘',
    polish: '润色',
    rag_chat: 'AI客服',
    rewrite: '改写'
  }
  return map[type] || type
}

function formatTime(value) {
  if (!value) return ''
  const d = new Date(value)
  if (isNaN(d.getTime())) return String(value).slice(0, 16)
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadLedger(page = 1) {
  loading.value = true
  loadError.value = ''
  try {
    const res = await getTokenLedger({ current: page, size: size.value })
    const data = res?.data
    if (!data || typeof data !== 'object' || Array.isArray(data) || !Array.isArray(data.records)) {
      throw new Error('Token 流水响应格式异常')
    }
    records.value = data.records.map((record, index) => {
      const changeAmount = nullableNumber(record.changeAmount ?? record.amount ?? record.changeValue)
      const beforeBalance = nullableNumber(record.beforeBalance ?? record.balanceBefore ?? record.prevBalance)
      const afterBalance = nullableNumber(record.afterBalance ?? record.balanceAfter ?? record.nextBalance)
      return {
        ...record,
        id: record.id ?? `${page}-${index}`,
        createdTime: record.createdTime || record.createTime || record.changeTime || record.time || '',
        changeType: record.changeType || record.type || '',
        refType: record.refType || record.sourceType || record.source || '',
        changeAmount,
        beforeBalance,
        afterBalance,
        remark: record.remark || record.description || record.desc || ''
      }
    })
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
  loadLedger(1)
})
</script>

<style scoped>
.m-profile-ledger {
  padding: 12px 16px 0;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
}

.m-ledger-filters {
  display: flex;
  background: white;
  border-radius: 12px;
  padding: 4px;
  margin-bottom: 12px;
  gap: 4px;
  box-shadow: 0 2px 8px rgba(31,53,94,0.04);
  border: 1px solid #f0f4fa;
  overflow-x: auto;
}
.m-ledger-filter {
  flex: 1;
  border: none;
  background: transparent;
  color: #8c98ae;
  font-size: 13px;
  font-weight: 600;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s;
  min-width: 0;
}
.m-ledger-filter.active {
  background: linear-gradient(135deg, #0d6bff, #2580ff);
  color: white;
  box-shadow: 0 2px 8px rgba(13,107,255,0.25);
}

.m-ledger-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 40px 0;
  color: #8c98ae;
  font-size: 13px;
}
.m-ledger-loading :deep(svg) {
  animation: mLedgerSpin 1.2s linear infinite;
}
@keyframes mLedgerSpin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.m-ledger-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.m-ledger-item {
  background: white;
  border-radius: 14px;
  padding: 12px 14px;
  box-shadow: 0 2px 8px rgba(31,53,94,0.04);
  border: 1px solid #f0f4fa;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.m-ledger-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.m-ledger-type-tag {
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  font-weight: 600;
  padding: 3px 9px;
  border-radius: 100px;
  background: #eef1f5;
  color: #6f7c91;
}
.m-ledger-type-tag.green {
  background: rgba(22,191,120,0.12);
  color: #16bf78;
}
.m-ledger-type-tag.red {
  background: rgba(239,68,68,0.1);
  color: #ef4444;
}
.m-ledger-type-tag.orange {
  background: rgba(255,159,34,0.12);
  color: #ff9f22;
}
.m-ledger-amount {
  font-size: 16px;
  font-weight: 800;
  flex-shrink: 0;
}
.m-ledger-amount.plus { color: #16bf78; }
.m-ledger-amount.minus { color: #ef4444; }

.m-ledger-mid {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  font-size: 12px;
  color: #8c98ae;
}
.m-ledger-module {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
  flex: 1;
}
.m-ledger-time {
  flex-shrink: 0;
  font-size: 11px;
  color: #b0bacb;
}

.m-ledger-balance {
  font-size: 12px;
  color: #5a6a85;
}

.m-ledger-remark {
  font-size: 12px;
  color: #8c98ae;
  background: #f5f8ff;
  border-radius: 8px;
  padding: 6px 8px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.m-ledger-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 60px 0;
  color: #b0bacb;
}
.m-ledger-empty :deep(svg) { color: #d4dce8; }
.m-ledger-empty p {
  margin: 0;
  font-size: 13px;
}

.m-ledger-pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 16px 0;
}
.m-ledger-page-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 1px solid #e1e8f3;
  background: white;
  color: #15213d;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
}
.m-ledger-page-btn:disabled {
  color: #c4cddb;
  background: #f5f7fb;
  cursor: not-allowed;
}
.m-ledger-page-btn:not(:disabled):active { background: #f0f4fa; }
.m-ledger-page-info {
  font-size: 13px;
  color: #15213d;
  font-weight: 600;
}
.m-ledger-page-total {
  font-size: 11px;
  color: #8c98ae;
  font-weight: 400;
}

.m-safe-bottom { height: 60px; }
</style>
