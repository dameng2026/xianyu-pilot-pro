<template>
  <div class="fsb-page">
    <section class="fsb-hero">
      <div class="fsb-hero-copy">
        <h2>流量分布</h2>
        <p>
          查看鱼小铺账号的浏览流量构成：来源分布、商品分布、时间分布与地域分布，
          帮助判断流量从哪来、哪些商品更受欢迎、买家活跃时段与地域特征。
        </p>
      </div>
    </section>

    <section class="fsb-toolbar card">
      <label class="fsb-field">
        <span>账号</span>
        <select v-model="accountId">
          <option value="">请选择账号</option>
          <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
            {{ acc.nickname || acc.accountName || `账号 ${acc.id}` }}{{ acc.fishShopUser ? '' : '（非鱼小铺）' }}
          </option>
        </select>
      </label>
      <div class="fsb-dates">
        <button
          v-for="opt in dateOptions"
          :key="opt.value"
          type="button"
          class="fsb-date-btn"
          :class="{ active: dateType === opt.value }"
          @click="dateType = opt.value"
        >
          {{ opt.label }}
        </button>
      </div>
      <div v-if="dateType === 'customDate'" class="fsb-custom">
        <input v-model="customStart" type="date" />
        <span>至</span>
        <input v-model="customEnd" type="date" />
      </div>
      <button type="button" class="fsb-primary-btn" :disabled="loading || !accountId" @click="loadData">
        {{ loading ? '加载中…' : '查询' }}
      </button>
    </section>

    <div v-if="loadError" class="fsb-error">{{ loadError }}</div>

    <section v-if="data" class="fsb-grid">
      <DistributionCard title="来源分布" :items="data.sceneSourceList" />
      <DistributionCard title="商品分布" :items="data.itemCateList" wide />
      <DistributionCard title="时间分布" :items="data.buyerActiveList" />
      <DistributionCard title="地域分布" :items="data.buyerProvinceList" wide />
    </section>

    <section v-else-if="!loading && !accountId" class="fsb-empty card">请先选择一个鱼小铺账号查询流量分布。</section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { getAccounts } from '../api/accounts.js'
import { getFishShopBrowseSummary } from '../api/fishShopData.js'

const DistributionCard = {
  props: {
    title: { type: String, required: true },
    items: { type: Array, default: () => [] },
    wide: { type: Boolean, default: false },
  },
  template: `
    <div class="fsb-card card">
      <h3>{{ title }}</h3>
      <div class="fsb-card-list">
        <div v-for="(item, idx) in items" :key="idx" class="fsb-bar-row">
          <span class="fsb-bar-label" :title="item.profileVal">{{ item.profileVal }}</span>
          <div class="fsb-bar-track">
            <div class="fsb-bar-fill" :style="{ width: Math.min(100, Math.max(0, (item.usrRatio || 0) * 100)) + '%' }"></div>
          </div>
          <span class="fsb-bar-value">{{ item.usrRatioFormat || '—' }}</span>
        </div>
        <p v-if="!items.length" class="fsb-empty-tip">暂无数据</p>
      </div>
    </div>
  `,
}

const accounts = ref([])
const accountId = ref('')
const dateType = ref('recent7d')
const customStart = ref('')
const customEnd = ref('')
const loading = ref(false)
const loadError = ref('')
const data = ref(null)

const dateOptions = [
  { value: 'recent1d', label: '近1天' },
  { value: 'recent7d', label: '近7天' },
  { value: 'recent30d', label: '近30天' },
  { value: 'customDate', label: '自定义' },
]

function toCompactDate(value) {
  return String(value || '').replace(/-/g, '')
}

async function loadAccounts() {
  try {
    const res = await getAccounts({ current: 1, size: 100 })
    accounts.value = Array.isArray(res?.data) ? res.data : (res?.data?.records || [])
    if (accounts.value.length === 1) accountId.value = accounts.value[0].id
  } catch (e) {
    loadError.value = e?.message || '账号列表加载失败'
  }
}

async function loadData() {
  if (!accountId.value) return
  loadError.value = ''
  let dateRange = ''
  if (dateType.value === 'customDate') {
    if (!customStart.value || !customEnd.value) {
      loadError.value = '请选择开始日期和结束日期'
      return
    }
    if (customStart.value > customEnd.value) {
      loadError.value = '开始日期不能晚于结束日期'
      return
    }
    dateRange = `${toCompactDate(customStart.value)}|${toCompactDate(customEnd.value)}`
  }
  loading.value = true
  try {
    const res = await getFishShopBrowseSummary({
      accountId: Number(accountId.value),
      dateType: dateType.value,
      dateRange,
    })
    const payload = res?.data || {}
    if (payload.invalidAccount) {
      loadError.value = '所选账号不是鱼小铺账号或不存在'
      data.value = null
      return
    }
    const raw = payload.data || {}
    // Python 返回 data.data = { code, data: {...分布}, extendInfo, msg }，需要再解一层
    const inner = raw && typeof raw === 'object' && raw.data && typeof raw.data === 'object'
      ? raw.data
      : raw
    data.value = inner || null
  } catch (e) {
    loadError.value = e?.message || '流量分布获取失败，请稍后重试'
    data.value = null
  } finally {
    loading.value = false
  }
}

onMounted(loadAccounts)
</script>

<style scoped>
.fsb-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 4px;
}

.fsb-hero {
  padding: 18px 20px;
  background: linear-gradient(135deg, #06b6d4 0%, #1f6feb 100%);
  border-radius: 14px;
  color: #fff;
}

.fsb-hero-copy h2 {
  margin: 0 0 6px;
  font-size: 20px;
}

.fsb-hero-copy p {
  margin: 0;
  max-width: 800px;
  font-size: 13px;
  line-height: 1.7;
  opacity: 0.94;
}

.card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
}

.fsb-toolbar {
  display: flex;
  align-items: flex-end;
  gap: 14px;
  padding: 14px 16px;
  flex-wrap: wrap;
}

.fsb-field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 200px;
}

.fsb-field > span {
  font-size: 12px;
  color: #6b7280;
}

.fsb-field select {
  height: 36px;
  padding: 0 10px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 13px;
  background: #fff;
  color: #111827;
  outline: none;
}

.fsb-dates {
  display: flex;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  overflow: hidden;
}

.fsb-date-btn {
  border: none;
  background: #fff;
  color: #6b7280;
  padding: 8px 12px;
  font-size: 13px;
  cursor: pointer;
}

.fsb-date-btn.active {
  background: #1f6feb;
  color: #fff;
}

.fsb-custom {
  display: flex;
  align-items: center;
  gap: 8px;
}

.fsb-custom input {
  height: 36px;
  padding: 0 8px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 13px;
}

.fsb-primary-btn {
  height: 36px;
  padding: 0 18px;
  border: none;
  border-radius: 8px;
  background: #1f6feb;
  color: #fff;
  font-size: 13px;
  cursor: pointer;
}

.fsb-primary-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.fsb-error {
  color: #dc2626;
  font-size: 13px;
  padding: 0 4px;
}

.fsb-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.fsb-card {
  padding: 16px;
}

.fsb-card h3 {
  margin: 0 0 12px;
  font-size: 14px;
  color: #111827;
}

.fsb-card-list {
  max-height: 260px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.fsb-bar-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.fsb-bar-label {
  width: 72px;
  flex-shrink: 0;
  font-size: 12px;
  color: #6b7280;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fsb-bar-track {
  flex: 1;
  height: 16px;
  background: #f3f4f6;
  border-radius: 999px;
  overflow: hidden;
}

.fsb-bar-fill {
  height: 100%;
  background: #1f6feb;
  border-radius: 999px;
  transition: width 0.2s ease;
}

.fsb-bar-value {
  width: 56px;
  flex-shrink: 0;
  text-align: right;
  font-size: 12px;
  color: #374151;
}

.fsb-empty {
  padding: 40px 20px;
  text-align: center;
  color: #6b7280;
  font-size: 14px;
}

.fsb-empty-tip {
  text-align: center;
  color: #9ca3af;
  font-size: 13px;
}

@media (max-width: 900px) {
  .fsb-grid {
    grid-template-columns: 1fr;
  }
}
</style>
