<template>
  <div class="m-products">
    <div class="m-page-header">
      <h1>商品管理</h1>
      <p class="m-page-sub">商品列表与状态查看</p>
    </div>

    <div class="m-prod-filter">
      <div class="m-prod-filter-scroll">
        <button
          class="m-prod-chip"
          :class="{ 'm-prod-chip-active': selectedAccountId === null }"
          @click="selectAccount(null)"
        >
          全部账号
        </button>
        <button
          v-for="acc in accounts"
          :key="acc.id"
          class="m-prod-chip"
          :class="{ 'm-prod-chip-active': selectedAccountId === acc.id }"
          @click="selectAccount(acc.id)"
        >
          {{ acc.nickname || acc.remark || acc.username || `账号${acc.id}` }}
        </button>
      </div>
    </div>

    <MobileUnavailableState v-if="accountsLoadError" compact title="账号筛选暂时不可用" :description="accountsLoadError" @retry="loadAccounts" />

    <div v-if="loading" class="m-loading">加载中...</div>

    <MobileUnavailableState v-else-if="loadError" title="商品数据暂时无法加载" :description="loadError" @retry="loadProducts" />

    <div v-else-if="products.length === 0" class="m-empty">
      <div class="m-empty-icon">
        <MIcon name="bag" :size="48" />
      </div>
      <div class="m-empty-text">暂无商品</div>
      <div class="m-empty-desc">当账号同步商品后会在这里显示</div>
    </div>

    <div v-else class="m-prod-list">
      <div v-for="prod in products" :key="prod.id || prod.itemId" class="m-prod-card">
        <div class="m-prod-cover">
          <img
            v-if="prod.coverPic"
            :src="prod.coverPic"
            :alt="prod.name"
            class="m-prod-img"
            @error="onImgError($event, prod)"
          />
          <div v-else class="m-prod-cover-placeholder">
            <MIcon name="bag" :size="28" />
          </div>
        </div>
        <div class="m-prod-body">
          <div class="m-prod-name">{{ prod.name || '未命名商品' }}</div>
          <div class="m-prod-price-row">
            <span class="m-prod-price">¥{{ formatPrice(prod.price) }}</span>
            <span class="m-prod-status" :class="statusClass(prod.statusCode)">
              {{ statusText(prod.statusCode) }}
            </span>
          </div>
          <div class="m-prod-meta">
            <span class="m-prod-stock">库存 {{ prod.stock != null ? prod.stock : '—' }}</span>
            <span
              class="m-prod-delivery"
              :class="deliveryClass(prod.deliveryOn)"
            >
              <MIcon name="truck" :size="12" />
              {{ deliveryText(prod.deliveryOn) }}
            </span>
          </div>
          <div class="m-prod-stats">
            <span class="m-prod-stat">
              <MIcon name="eye" :size="12" />{{ metricValue(prod.exposureCount) }}
            </span>
            <span class="m-prod-stat">
              <MIcon name="chart" :size="12" />{{ metricValue(prod.viewCount) }}
            </span>
            <span class="m-prod-stat">
              <MIcon name="heart" :size="12" />{{ metricValue(prod.wantCount) }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <div class="m-prod-tip">
      <MIcon name="warning" :size="16" />
      <span>商品发布、编辑等复杂操作建议在PC端完成</span>
      <button class="m-tip-btn" @click="$emit('force-desktop')">进入桌面版</button>
    </div>

    <div class="m-safe-bottom"></div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import MIcon from './MIcon.vue'
import MobileUnavailableState from './MobileUnavailableState.vue'
import { getGoods } from '../api/goods.js'
import { getLiteAccounts } from '../api/accounts.js'

defineEmits(['navigate', 'force-desktop', 'back'])

const products = ref([])
const accounts = ref([])
const selectedAccountId = ref(null)
const loading = ref(true)
const loadError = ref('')
const accountsLoadError = ref('')

async function loadAccounts() {
  accountsLoadError.value = ''
  try {
    const res = await getLiteAccounts({ page: 1, pageSize: 100 })
    const data = res?.data
    const list = data?.records || data?.list || (Array.isArray(data) ? data : null)
    if (!Array.isArray(list)) throw new Error('账号列表响应格式异常')
    accounts.value = list
  } catch (error) {
    accounts.value = []
    accountsLoadError.value = error?.message || '无法获取账号列表，当前只能查看全部账号。'
  }
}

async function loadProducts() {
  loading.value = true
  loadError.value = ''
  try {
    const params = { page: 1, pageSize: 20 }
    if (selectedAccountId.value != null) {
      params.xianyuAccountId = selectedAccountId.value
    }
    const res = await getGoods(params)
    const data = res?.data
    if (data?.records) {
      products.value = data.records
    } else if (data?.list) {
      products.value = data.list
    } else if (Array.isArray(data)) {
      products.value = data
    } else {
      throw new Error('商品列表响应格式异常')
    }
  } catch (error) {
    products.value = []
    loadError.value = error?.message || '请检查网络连接后重试。'
  } finally {
    loading.value = false
  }
}

function selectAccount(id) {
  if (selectedAccountId.value === id) return
  selectedAccountId.value = id
  loadProducts()
}

function formatPrice(price) {
  if (price == null || price === '') return '—'
  const num = Number(price)
  if (isNaN(num)) return price
  return Number.isInteger(num) ? String(num) : num.toFixed(2)
}

function metricValue(value) {
  return value === null || value === undefined || value === '' ? '—' : value
}

function deliveryText(value) {
  if (value === null || value === undefined || value === '') return '状态未知'
  if (value === true || Number(value) === 1) return '已配置'
  if (value === false || Number(value) === 0) return '未配置'
  return '状态未知'
}

function deliveryClass(value) {
  if (value === null || value === undefined || value === '') return 'm-prod-delivery-unknown'
  if (value === true || Number(value) === 1) return 'm-prod-delivery-on'
  if (value === false || Number(value) === 0) return 'm-prod-delivery-off'
  return 'm-prod-delivery-unknown'
}

function statusText(code) {
  if (code === 1) return '在售'
  if (code === 3) return '已删除'
  if (code === 0) return '下架'
  return '未知'
}

function statusClass(code) {
  if (code === 1) return 'm-prod-status-on'
  if (code === 3) return 'm-prod-status-del'
  if (code === 0) return 'm-prod-status-off'
  return 'm-prod-status-off'
}

function onImgError(e, prod) {
  prod.coverPic = ''
}

onMounted(async () => {
  await loadAccounts()
  await loadProducts()
})
</script>

<style scoped>
.m-products {
  padding: 12px 16px 0;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
}
.m-page-header { margin-bottom: 16px; }
.m-page-header h1 { margin: 0 0 4px; font-size: 26px; font-weight: 800; color: #15213d; }
.m-page-sub { margin: 0; font-size: 13px; color: #8c98ae; }

.m-prod-filter {
  margin-bottom: 14px;
  margin-left: -16px;
  margin-right: -16px;
  padding-left: 16px;
  padding-right: 16px;
  overflow-x: auto;
  overflow-y: hidden;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.m-prod-filter::-webkit-scrollbar { display: none; }
.m-prod-filter-scroll {
  display: inline-flex;
  gap: 8px;
  white-space: nowrap;
}
.m-prod-chip {
  flex-shrink: 0;
  background: white;
  border: 1px solid #e0e6f0;
  color: #5a6a85;
  padding: 7px 14px;
  border-radius: 100px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}
.m-prod-chip:active { transform: scale(0.96); }
.m-prod-chip-active {
  background: linear-gradient(135deg, #0d6bff, #2580ff);
  color: white;
  border-color: transparent;
  box-shadow: 0 4px 12px rgba(13, 107, 255, 0.25);
}

.m-empty {
  text-align: center;
  padding: 60px 20px;
}
.m-empty-icon {
  width: 80px;
  height: 80px;
  margin: 0 auto 16px;
  border-radius: 50%;
  background: linear-gradient(135deg, #e8f1ff, #d4e4ff);
  color: #0d6bff;
  display: flex;
  align-items: center;
  justify-content: center;
}
.m-empty-text { font-size: 16px; font-weight: 600; color: #15213d; margin-bottom: 6px; }
.m-empty-desc { font-size: 13px; color: #8c98ae; }

.m-loading { text-align: center; padding: 40px; color: #8c98ae; font-size: 14px; }

.m-prod-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.m-prod-card {
  background: white;
  border-radius: 16px;
  padding: 12px;
  display: flex;
  gap: 12px;
  box-shadow: 0 2px 8px rgba(31, 53, 94, 0.05);
  border: 1px solid #f0f4fa;
}
.m-prod-cover {
  width: 80px;
  height: 80px;
  border-radius: 12px;
  overflow: hidden;
  flex-shrink: 0;
  background: #f4f7fc;
}
.m-prod-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.m-prod-cover-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #b0bacb;
  background: linear-gradient(135deg, #f4f7fc, #eaf0fa);
}
.m-prod-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.m-prod-name {
  font-size: 14px;
  font-weight: 600;
  color: #15213d;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  word-break: break-all;
}
.m-prod-price-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.m-prod-price {
  font-size: 16px;
  font-weight: 800;
  color: #ff5b2e;
}
.m-prod-status {
  font-size: 11px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 100px;
  flex-shrink: 0;
}
.m-prod-status-on {
  background: rgba(22, 191, 120, 0.12);
  color: #16bf78;
}
.m-prod-status-off {
  background: rgba(255, 159, 34, 0.12);
  color: #ff9f22;
}
.m-prod-status-del {
  background: rgba(140, 152, 174, 0.15);
  color: #8c98ae;
}
.m-prod-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.m-prod-stock {
  font-size: 12px;
  color: #8c98ae;
}
.m-prod-delivery {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 100px;
  font-weight: 500;
}
.m-prod-delivery :deep(svg) { flex-shrink: 0; }
.m-prod-delivery-on {
  background: rgba(22, 191, 120, 0.1);
  color: #16bf78;
}
.m-prod-delivery-off {
  background: rgba(255, 159, 34, 0.1);
  color: #ff9f22;
}
.m-prod-delivery-unknown {
  background: rgba(140, 152, 174, 0.12);
  color: #7f8a9d;
}
.m-prod-stats {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 2px;
}
.m-prod-stat {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  color: #8c98ae;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-prod-stat :deep(svg) { color: #b0bacb; flex-shrink: 0; }

@media (max-width: 360px) {
  .m-prod-stats {
    gap: 6px;
    justify-content: space-between;
  }

  .m-prod-stat {
    flex: 1 1 0;
  }
}

.m-prod-tip {
  margin-top: 20px;
  background: #f8faff;
  border-radius: 14px;
  padding: 12px 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #72809a;
}
.m-prod-tip :deep(svg) { color: #ff9f22; flex-shrink: 0; }
.m-tip-btn {
  margin-left: auto;
  background: linear-gradient(135deg, #0d6bff, #2580ff);
  color: white;
  border: none;
  border-radius: 100px;
  padding: 6px 14px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  flex-shrink: 0;
}

.m-safe-bottom { height: 80px; }
</style>
