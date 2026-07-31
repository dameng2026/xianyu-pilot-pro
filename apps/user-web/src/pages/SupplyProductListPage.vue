<template>
  <div class="supply-list-page">
    <!-- 页头 -->
    <div class="spl-header">
      <div class="spl-header-left">
        <button type="button" class="spl-back-btn" @click="emit('navigate', 'supply-center')">
          <svg viewBox="0 0 16 16" width="16" height="16" fill="none">
            <path d="M10 4L6 8L10 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          返回
        </button>
        <h2 class="spl-title">我的货源</h2>
      </div>
      <button type="button" class="spl-upload-btn" @click="emit('navigate', 'supply-center-products-new')">
        <svg viewBox="0 0 16 16" width="14" height="14" fill="none">
          <path d="M8 3V13M3 8H13" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
        上传货源
      </button>
    </div>

    <!-- 筛选 tab -->
    <div class="spl-tabs">
      <button
        v-for="tab in auditTabs"
        :key="tab.value"
        type="button"
        :class="['spl-tab', { active: activeTab === tab.value }]"
        @click="switchTab(tab.value)"
      >
        {{ tab.label }}
        <span v-if="tab.count != null" class="spl-tab-count">{{ tab.count }}</span>
      </button>
    </div>

    <!-- 列表 -->
    <div class="spl-content-card">
      <div v-if="loading" class="spl-loading">加载中...</div>
      <div v-else-if="products.length === 0" class="spl-empty">
        <svg viewBox="0 0 64 64" width="56" height="56" fill="none">
          <rect x="12" y="16" width="40" height="36" rx="4" stroke="#cbd5e1" stroke-width="2"/>
          <path d="M20 28H44M20 36H36" stroke="#cbd5e1" stroke-width="2" stroke-linecap="round"/>
          <path d="M24 12V20M40 12V20" stroke="#cbd5e1" stroke-width="2" stroke-linecap="round"/>
        </svg>
        <p class="spl-empty-text">{{ emptyText }}</p>
        <button type="button" class="spl-empty-btn" @click="emit('navigate', 'supply-center-products-new')">去上传货源</button>
      </div>
      <div v-else class="spl-table-wrap">
        <table class="spl-table">
          <thead>
            <tr>
              <th class="col-title">商品标题</th>
              <th class="col-type">类型</th>
              <th class="col-price">价格</th>
              <th class="col-stock">库存</th>
              <th class="col-audit">审核状态</th>
              <th class="col-status">上架状态</th>
              <th class="col-actions">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in products" :key="item.id">
              <td class="col-title">
                <div class="spl-product-cell">
                  <div class="spl-product-cover" :style="coverStyle(item)"></div>
                  <div class="spl-product-info">
                    <div class="spl-product-title">{{ item.title || '未命名货源' }}</div>
                    <div v-if="item.subtitle" class="spl-product-sub">{{ item.subtitle }}</div>
                  </div>
                </div>
              </td>
              <td class="col-type">
                <span :class="['spl-type-tag', productTypeClass(item)]">{{ productTypeLabel(item) }}</span>
              </td>
              <td class="col-price">
                <span class="spl-price-text">¥{{ formatPrice(item.price) }}</span>
              </td>
              <td class="col-stock">{{ stockDisplay(item) }}</td>
              <td class="col-audit">
                <span :class="['spl-audit-tag', auditClass(item.auditStatus)]">{{ auditLabel(item.auditStatus) }}</span>
              </td>
              <td class="col-status">
                <span :class="['spl-status-dot', item.listed ? 'on' : 'off']"></span>
                {{ item.listed ? '已上架' : '未上架' }}
              </td>
              <td class="col-actions">
                <div class="spl-action-btns">
                  <button type="button" class="spl-act-btn spl-act-edit" @click="handleEdit(item)">编辑</button>
                  <button
                    v-if="canOnline(item)"
                    type="button"
                    class="spl-act-btn spl-act-online"
                    :disabled="actionLoading === item.id"
                    @click="handleOnline(item)"
                  >上架</button>
                  <button
                    v-if="item.listed"
                    type="button"
                    class="spl-act-btn spl-act-offline"
                    :disabled="actionLoading === item.id"
                    @click="handleOffline(item)"
                  >下架</button>
                  <button
                    v-if="canDelete(item)"
                    type="button"
                    class="spl-act-btn spl-act-delete"
                    :disabled="actionLoading === item.id"
                    @click="handleDelete(item)"
                  >删除</button>
                  <button type="button" class="spl-act-btn spl-act-stats" @click="handleStats(item)">统计</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 分页 -->
      <div v-if="totalPages > 1" class="spl-pagination">
        <button class="spl-page-btn" :disabled="pageNum === 1" @click="goToPage(pageNum - 1)">上一页</button>
        <template v-for="(p, idx) in pageNumbers" :key="idx">
          <span v-if="p === '...'" class="spl-page-dots">...</span>
          <button v-else :class="['spl-page-btn', { active: pageNum === p }]" @click="goToPage(p)">{{ p }}</button>
        </template>
        <button class="spl-page-btn" :disabled="pageNum === totalPages" @click="goToPage(pageNum + 1)">下一页</button>
        <span class="spl-page-info">共 {{ totalPages }} 页，{{ totalItems }} 条</span>
      </div>
    </div>

    <!-- 统计弹窗 -->
    <div v-if="statsModalVisible" class="spl-modal-mask" @click.self="statsModalVisible = false">
      <div class="spl-modal-dialog">
        <div class="spl-modal-header">
          <h3 class="spl-modal-title">货源统计</h3>
          <button type="button" class="spl-modal-close" @click="statsModalVisible = false">×</button>
        </div>
        <div class="spl-modal-body">
          <div v-if="statsLoading" class="spl-modal-empty">加载中...</div>
          <div v-else-if="statsData">
            <div class="spl-stats-grid">
              <div class="spl-stats-cell">
                <div class="spl-stats-label">总销量</div>
                <div class="spl-stats-value">{{ statsData.totalSales ?? 0 }}<span>笔</span></div>
              </div>
              <div class="spl-stats-cell">
                <div class="spl-stats-label">总收入</div>
                <div class="spl-stats-value">¥{{ formatMoney(statsData.totalIncome) }}</div>
              </div>
              <div class="spl-stats-cell">
                <div class="spl-stats-label">浏览量</div>
                <div class="spl-stats-value">{{ statsData.viewCount ?? 0 }}<span>次</span></div>
              </div>
              <div class="spl-stats-cell">
                <div class="spl-stats-label">转化率</div>
                <div class="spl-stats-value">{{ formatRate(statsData.conversionRate) }}<span>%</span></div>
              </div>
            </div>
          </div>
          <div v-else class="spl-modal-empty">暂无统计数据</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  getSupplyProducts,
  onlineSupplyProduct,
  offlineSupplyProduct,
  deleteSupplyProduct,
  getSupplyProductStats
} from '../api/supply.js'

const emit = defineEmits(['navigate'])

const activeTab = ref('all')
const products = ref([])
const loading = ref(false)
const pageNum = ref(1)
const pageSize = 20
const totalPages = ref(1)
const totalItems = ref(0)
const actionLoading = ref(null)

const auditTabs = computed(() => [
  { value: 'all', label: '全部', count: null },
  { value: 'pending', label: '待审核', count: null },
  { value: 'approved', label: '已通过', count: null },
  { value: 'rejected', label: '已驳回', count: null }
])

const emptyText = computed(() => {
  if (activeTab.value === 'all') return '暂无货源，点击下方按钮上传第一件货源'
  if (activeTab.value === 'pending') return '暂无待审核的货源'
  if (activeTab.value === 'approved') return '暂无已通过审核的货源'
  if (activeTab.value === 'rejected') return '暂无被驳回的货源'
  return '暂无货源'
})

const pageNumbers = computed(() => {
  const total = totalPages.value
  const cur = pageNum.value
  const arr = []
  if (total <= 7) {
    for (let i = 1; i <= total; i++) arr.push(i)
  } else {
    arr.push(1)
    if (cur > 4) arr.push('...')
    const start = Math.max(2, cur - 1)
    const end = Math.min(total - 1, cur + 1)
    for (let i = start; i <= end; i++) arr.push(i)
    if (cur < total - 3) arr.push('...')
    arr.push(total)
  }
  return arr
})

function switchTab(value) {
  if (activeTab.value === value) return
  activeTab.value = value
  pageNum.value = 1
  loadProducts()
}

async function loadProducts() {
  loading.value = true
  try {
    const params = { page: pageNum.value, size: pageSize }
    if (activeTab.value !== 'all') params.auditStatus = activeTab.value
    const res = await getSupplyProducts(params)
    const data = res?.data || res || {}
    const list = Array.isArray(data) ? data : (data.records || data.list || data.items || [])
    // 后端返回 snake_case 字段，前端统一兼容
    products.value = list.map(normalizeProduct)
    totalPages.value = Number(data.totalPages || data.pages || Math.ceil((Number(data.total ?? list.length)) / pageSize)) || 1
    totalItems.value = Number(data.total ?? data.totalCount ?? list.length) || 0
  } catch (e) {
    console.error('[supply-list] 加载货源失败', e)
    products.value = []
    totalPages.value = 1
    totalItems.value = 0
  } finally {
    loading.value = false
  }
}

// 后端返回 snake_case 字段（jdbcTemplate.queryForList），前端归一化为 camelCase
function normalizeProduct(item) {
  if (!item || typeof item !== 'object') return item
  return {
    ...item,
    productType: item.productType ?? item.product_type,
    auditStatus: item.auditStatus ?? item.audit_status,
    auditReason: item.auditReason ?? item.audit_reason,
    coverUrl: item.coverUrl ?? item.cover_url,
    priceCent: item.priceCent ?? item.price_cent,
    cardGroupId: item.cardGroupId ?? item.card_group_id,
    boughtCount: item.boughtCount ?? item.bought_count,
    createdTime: item.createdTime ?? item.created_time,
    updatedTime: item.updatedTime ?? item.updated_time,
    // status=1 表示已上架，0 表示未上架
    listed: Number(item.listed ?? item.status) === 1,
    // 兼容字段
    price: item.price ?? item.price_cent,
    totalSales: item.totalSales ?? item.bought_count
  }
}

function goToPage(n) {
  if (n < 1 || n > totalPages.value || n === pageNum.value) return
  pageNum.value = n
  loadProducts()
}

function productTypeLabel(item) {
  const t = item.productType || item.type
  if (t === 'text') return '文本'
  if (t === 'card') return '卡密'
  return '其他'
}
function productTypeClass(item) {
  const t = item.productType || item.type
  if (t === 'text') return 'spl-type-text'
  if (t === 'card') return 'spl-type-card'
  return 'spl-type-other'
}
function auditLabel(status) {
  const map = { pending: '待审核', approved: '已通过', rejected: '已驳回' }
  return map[status] || '未知'
}
function auditClass(status) {
  const map = { pending: 'audit-pending', approved: 'audit-approved', rejected: 'audit-rejected' }
  return map[status] || 'audit-unknown'
}
function canOnline(item) {
  return item.auditStatus === 'approved' && !item.listed
}
function canDelete(item) {
  return Number(item.totalSales ?? item.salesCount ?? 0) === 0
}
function stockDisplay(item) {
  const t = item.productType || item.type
  if (t === 'text') return '∞'
  // 卡密商品优先使用后端返回的实际库存 actualStock
  const s = Number(item.actualStock ?? item.stock ?? 0)
  return Number.isFinite(s) ? String(s) : '0'
}
function coverStyle(item) {
  const url = item.coverUrl || ''
  if (url) return { backgroundImage: `url(${url})`, backgroundSize: 'cover', backgroundPosition: 'center' }
  return { background: 'linear-gradient(135deg, #e2e8f0, #cbd5e1)' }
}
function formatPrice(price) {
  // 后端 price_cent 为分，normalizeProduct 已映射到 price 字段
  const cents = Number(price ?? 0)
  if (!Number.isFinite(cents)) return '0.00'
  return (cents / 100).toFixed(2)
}
function formatMoney(n) {
  const num = Number(n ?? 0)
  return Number.isFinite(num) ? num.toFixed(2) : '0.00'
}
function formatRate(n) {
  const num = Number(n ?? 0)
  return Number.isFinite(num) ? num.toFixed(1) : '0.0'
}

function handleEdit(item) {
  emit('navigate', `supply-center-products-edit/${item.id}`)
}

async function handleOnline(item) {
  if (actionLoading.value) return
  actionLoading.value = item.id
  try {
    await onlineSupplyProduct(item.id)
    item.listed = true
  } catch (e) {
    alert(e?.message || '上架失败，请稍后重试')
  } finally {
    actionLoading.value = null
  }
}

async function handleOffline(item) {
  if (actionLoading.value) return
  actionLoading.value = item.id
  try {
    await offlineSupplyProduct(item.id)
    item.listed = false
  } catch (e) {
    alert(e?.message || '下架失败，请稍后重试')
  } finally {
    actionLoading.value = null
  }
}

async function handleDelete(item) {
  if (!confirm(`确定要删除货源「${item.title || ''}」吗？此操作不可撤销。`)) return
  if (actionLoading.value) return
  actionLoading.value = item.id
  try {
    await deleteSupplyProduct(item.id)
    products.value = products.value.filter(p => p.id !== item.id)
    totalItems.value = Math.max(0, totalItems.value - 1)
  } catch (e) {
    alert(e?.message || '删除失败，请稍后重试')
  } finally {
    actionLoading.value = null
  }
}

// 统计弹窗
const statsModalVisible = ref(false)
const statsLoading = ref(false)
const statsData = ref(null)

async function handleStats(item) {
  statsModalVisible.value = true
  statsLoading.value = true
  statsData.value = null
  try {
    const res = await getSupplyProductStats(item.id)
    statsData.value = res?.data || res || null
  } catch (e) {
    statsData.value = null
  } finally {
    statsLoading.value = false
  }
}

onMounted(loadProducts)
</script>

<style scoped>
.supply-list-page {
  width: 100%;
  min-height: 100%;
  box-sizing: border-box;
  padding: 4px;
}

/* 页头 */
.spl-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
  gap: 12px;
  flex-wrap: wrap;
}
.spl-header-left {
  display: flex;
  align-items: center;
  gap: 14px;
}
.spl-back-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 34px;
  padding: 0 12px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #64748b;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}
.spl-back-btn:hover {
  border-color: #4f7cff;
  color: #4f7cff;
}
.spl-title {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  margin: 0;
}
.spl-upload-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 40px;
  padding: 0 18px;
  border-radius: 12px;
  border: none;
  background: linear-gradient(90deg, #0865f4, #147dff);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  box-shadow: 0 4px 10px rgba(13, 107, 255, 0.25);
}
.spl-upload-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 14px rgba(13, 107, 255, 0.35);
}

/* tabs */
.spl-tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.spl-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #64748b;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}
.spl-tab:hover {
  border-color: #c7d2fe;
  color: #4f7cff;
}
.spl-tab.active {
  background: #4f7cff;
  border-color: #4f7cff;
  color: #fff;
}
.spl-tab-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.25);
  font-size: 11px;
  font-weight: 700;
}
.spl-tab:not(.active) .spl-tab-count {
  background: #f1f5f9;
  color: #94a3b8;
}

/* 内容卡片 */
.spl-content-card {
  background: #fff;
  border-radius: 16px;
  border: 1px solid #e8edf5;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  padding: 8px;
  overflow: hidden;
}

.spl-loading,
.spl-empty {
  padding: 56px 20px;
  text-align: center;
  color: #94a3b8;
  font-size: 14px;
}
.spl-empty svg {
  margin-bottom: 12px;
}
.spl-empty-text {
  margin: 0 0 14px;
  font-size: 14px;
  color: #64748b;
}
.spl-empty-btn {
  height: 36px;
  padding: 0 18px;
  border-radius: 10px;
  border: none;
  background: linear-gradient(90deg, #0865f4, #147dff);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}
.spl-empty-btn:hover {
  box-shadow: 0 4px 12px rgba(13, 107, 255, 0.3);
}

/* 表格 */
.spl-table-wrap {
  overflow-x: auto;
}
.spl-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.spl-table thead th {
  padding: 12px 14px;
  text-align: left;
  font-weight: 600;
  color: #94a3b8;
  font-size: 12px;
  border-bottom: 1px solid #f1f5f9;
  white-space: nowrap;
  background: #f8fafc;
}
.spl-table tbody td {
  padding: 14px;
  border-bottom: 1px solid #f1f5f9;
  vertical-align: middle;
  color: #1e293b;
}
.spl-table tbody tr:hover {
  background: #f8fafc;
}
.spl-table tbody tr:last-child td {
  border-bottom: none;
}

.col-title { min-width: 220px; }
.col-type, .col-audit, .col-status { text-align: center; }
.col-price, .col-stock { text-align: center; white-space: nowrap; }
.col-actions { min-width: 200px; }

.spl-product-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}
.spl-product-cover {
  width: 44px;
  height: 44px;
  border-radius: 8px;
  flex-shrink: 0;
  background-color: #e2e8f0;
}
.spl-product-info {
  min-width: 0;
}
.spl-product-title {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 240px;
}
.spl-product-sub {
  font-size: 11px;
  color: #94a3b8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 240px;
}

.spl-type-tag {
  display: inline-flex;
  padding: 3px 10px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 600;
}
.spl-type-text { background: rgba(79, 124, 255, 0.1); color: #4f7cff; }
.spl-type-card { background: rgba(245, 158, 11, 0.1); color: #f59e0b; }
.spl-type-other { background: #f1f5f9; color: #64748b; }

.spl-price-text {
  font-size: 14px;
  font-weight: 700;
  color: #ff3b30;
}

.spl-audit-tag {
  display: inline-flex;
  padding: 3px 10px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 600;
}
.audit-pending { background: rgba(245, 158, 11, 0.1); color: #f59e0b; }
.audit-approved { background: rgba(16, 185, 129, 0.1); color: #10b981; }
.audit-rejected { background: rgba(239, 68, 68, 0.1); color: #ef4444; }
.audit-unknown { background: #f1f5f9; color: #64748b; }

.spl-status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 4px;
  vertical-align: middle;
}
.spl-status-dot.on { background: #10b981; }
.spl-status-dot.off { background: #cbd5e1; }

.spl-action-btns {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.spl-act-btn {
  height: 28px;
  padding: 0 10px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475569;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.spl-act-btn:hover:not(:disabled) {
  border-color: #c7d2fe;
}
.spl-act-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.spl-act-edit:hover:not(:disabled) { color: #4f7cff; border-color: #4f7cff; }
.spl-act-online:hover:not(:disabled) { color: #10b981; border-color: #10b981; }
.spl-act-offline:hover:not(:disabled) { color: #f59e0b; border-color: #f59e0b; }
.spl-act-delete:hover:not(:disabled) { color: #ef4444; border-color: #ef4444; }
.spl-act-stats:hover:not(:disabled) { color: #8b5cf6; border-color: #8b5cf6; }

/* 分页 */
.spl-pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 16px 12px 8px;
  flex-wrap: wrap;
}
.spl-page-btn {
  min-width: 34px;
  height: 34px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475569;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
  padding: 0 12px;
}
.spl-page-btn:hover:not(:disabled) {
  border-color: #c7d2fe;
  color: #4f7cff;
}
.spl-page-btn.active {
  background: #4f7cff;
  color: #fff;
  border-color: #4f7cff;
  font-weight: 600;
}
.spl-page-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.spl-page-dots {
  color: #94a3b8;
  font-size: 13px;
  padding: 0 4px;
}
.spl-page-info {
  font-size: 12px;
  color: #94a3b8;
  margin-left: 10px;
}

/* 弹窗 */
.spl-modal-mask {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(16, 28, 52, 0.5);
  backdrop-filter: blur(8px);
}
.spl-modal-dialog {
  width: 100%;
  max-width: 480px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 20px 50px rgba(15, 23, 42, 0.18);
  overflow: hidden;
}
.spl-modal-header {
  position: relative;
  padding: 18px 20px 14px;
  border-bottom: 1px solid #f1f5f9;
}
.spl-modal-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
  text-align: center;
}
.spl-modal-close {
  position: absolute;
  right: 14px;
  top: 14px;
  width: 26px;
  height: 26px;
  border: none;
  background: transparent;
  font-size: 22px;
  color: #94a3b8;
  cursor: pointer;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.spl-modal-close:hover {
  background: #f1f5f9;
  color: #475569;
}
.spl-modal-body {
  padding: 20px;
}
.spl-modal-empty {
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
  padding: 24px 0;
}
.spl-stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}
.spl-stats-cell {
  padding: 14px;
  background: #f8fafc;
  border-radius: 10px;
  text-align: center;
}
.spl-stats-label {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 6px;
}
.spl-stats-value {
  font-size: 20px;
  font-weight: 800;
  color: #0f172a;
}
.spl-stats-value span {
  font-size: 12px;
  font-weight: 500;
  color: #64748b;
  margin-left: 2px;
}

@media (max-width: 768px) {
  .col-type, .col-stock { display: none; }
  .spl-stats-grid { grid-template-columns: 1fr; }
}
</style>
