<template>
  <div class="supply-center-page">
    <!-- 顶部渐变横幅 -->
    <section class="sc-banner">
      <div class="sc-banner-left">
        <div class="sc-banner-avatar">
          <svg viewBox="0 0 80 80" width="64" height="64">
            <defs>
              <clipPath id="scAvClip"><circle cx="40" cy="40" r="34"/></clipPath>
              <linearGradient id="scAvBg" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#dbeafe"/>
                <stop offset="100%" stop-color="#bfdbfe"/>
              </linearGradient>
            </defs>
            <circle cx="40" cy="40" r="38" fill="#fff"/>
            <circle cx="40" cy="40" r="36" fill="url(#scAvBg)" clip-path="url(#scAvClip)"/>
            <ellipse cx="40" cy="34" rx="14" ry="16" fill="#f5d5b0"/>
            <path d="M25 28c0-10 7-18 15-18s15 8 15 18c0 3-1 5-2 6-1-4-4-8-13-8s-12 4-13 8c-1-1-2-3-2-6z" fill="#3a2a1c"/>
            <ellipse cx="34" cy="36" rx="2" ry="2.5" fill="#2a1e14"/>
            <ellipse cx="46" cy="36" rx="2" ry="2.5" fill="#2a1e14"/>
            <path d="M32 42c3 2 13 2 16 0" stroke="#c97b6a" stroke-width="1.2" stroke-linecap="round" fill="none"/>
          </svg>
        </div>
        <div class="sc-banner-info">
          <h2 class="sc-banner-title">供货中心</h2>
          <p class="sc-banner-desc">{{ greeting }}，{{ displayName }}！在这里管理你的供货商品、查看收入与审核状态</p>
        </div>
      </div>
      <div class="sc-banner-illustration" aria-hidden="true">
        <svg viewBox="0 0 200 120" width="200" height="120">
          <ellipse cx="100" cy="110" rx="70" ry="5" fill="#1e3a8a" opacity="0.08"/>
          <path d="M40 50 L60 30 L80 50 L100 25 L120 50 L140 35 L160 50" stroke="#fff" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round" opacity="0.9"/>
          <circle cx="100" cy="25" r="4" fill="#fff" opacity="0.8"/>
          <circle cx="60" cy="30" r="3" fill="#fff" opacity="0.6"/>
          <circle cx="140" cy="35" r="3" fill="#fff" opacity="0.6"/>
          <rect x="30" y="70" width="140" height="30" rx="6" fill="#fff" opacity="0.25"/>
          <rect x="40" y="78" width="30" height="14" rx="3" fill="#fff" opacity="0.4"/>
          <rect x="80" y="78" width="30" height="14" rx="3" fill="#fff" opacity="0.3"/>
          <rect x="120" y="78" width="30" height="14" rx="3" fill="#fff" opacity="0.35"/>
        </svg>
      </div>
    </section>

    <div v-if="loadError" class="sc-error-tip">
      <svg viewBox="0 0 20 20" width="18" height="18" fill="none">
        <circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="1.5"/>
        <path d="M10 6V11M10 14V14.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
      </svg>
      <span>{{ loadError }}</span>
      <button type="button" class="sc-retry-btn" @click="loadAll">重新加载</button>
    </div>

    <!-- 彩色统计卡片 -->
    <div class="sc-stats-row">
      <article class="sc-stat-card sc-stat-blue">
        <div class="sc-stat-icon-wrap">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none">
            <path d="M3 7L12 3L21 7L12 11L3 7Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
            <path d="M3 12L12 16L21 12" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
            <path d="M3 17L12 21L21 17" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
          </svg>
        </div>
        <div class="sc-stat-body">
          <div class="sc-stat-label">已上传货源</div>
          <div class="sc-stat-value"><strong>{{ formatNumber(stats.uploadedCount) }}</strong><em>件</em></div>
          <div class="sc-stat-sub">{{ stats.approvedCount }} 件已通过审核</div>
        </div>
      </article>

      <article class="sc-stat-card sc-stat-green">
        <div class="sc-stat-icon-wrap">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none">
            <path d="M3 17l6-6 4 4 8-9" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M17 4h4v4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <div class="sc-stat-body">
          <div class="sc-stat-label">今日收入</div>
          <div class="sc-stat-value"><strong>¥{{ formatMoney(stats.todayIncome) }}</strong></div>
          <div class="sc-stat-sub">今日 {{ stats.todaySales }} 笔订单</div>
        </div>
      </article>

      <article class="sc-stat-card sc-stat-orange">
        <div class="sc-stat-icon-wrap">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none">
            <rect x="2" y="5" width="20" height="14" rx="2" stroke="currentColor" stroke-width="1.8"/>
            <line x1="2" y1="10" x2="22" y2="10" stroke="currentColor" stroke-width="1.8"/>
            <circle cx="17" cy="15" r="1.2" fill="currentColor"/>
          </svg>
        </div>
        <div class="sc-stat-body">
          <div class="sc-stat-label">可用余额</div>
          <div class="sc-stat-value"><strong>¥{{ formatMoney(stats.availableBalance) }}</strong></div>
          <div class="sc-stat-sub">可随时提现</div>
        </div>
      </article>

      <article class="sc-stat-card sc-stat-purple">
        <div class="sc-stat-icon-wrap">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none">
            <rect x="4" y="3" width="16" height="18" rx="2" stroke="currentColor" stroke-width="1.8"/>
            <path d="M8 8H16M8 12H16M8 16H12" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
          </svg>
        </div>
        <div class="sc-stat-body">
          <div class="sc-stat-label">冻结余额</div>
          <div class="sc-stat-value"><strong>¥{{ formatMoney(stats.frozenBalance) }}</strong></div>
          <div class="sc-stat-sub">待订单完成后解冻</div>
        </div>
      </article>
    </div>

    <!-- 待办提醒 -->
    <div v-if="stats.pendingAudit > 0" class="sc-todo-reminder" role="alert">
      <div class="sc-todo-icon">
        <svg viewBox="0 0 20 20" width="18" height="18" fill="none">
          <circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="1.5"/>
          <path d="M10 6V11M10 14V14.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
        </svg>
      </div>
      <div class="sc-todo-text">
        有 <strong>{{ stats.pendingAudit }}</strong> 件货源正在审核中，审核通过后将自动上架到商城
      </div>
      <button type="button" class="sc-todo-link" @click="scrollToMyProducts">查看货源</button>
    </div>

    <!-- 快捷操作 -->
    <div class="sc-quick-actions">
      <h3 class="sc-section-title">快捷操作</h3>
      <div class="sc-action-grid">
        <button type="button" class="sc-action-card sc-action-blue" @click="emit('navigate', 'supply-center-products-new')">
          <div class="sc-action-icon">
            <svg viewBox="0 0 24 24" width="28" height="28" fill="none">
              <path d="M12 5V19M5 12H19" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>
            </svg>
          </div>
          <div class="sc-action-text">
            <div class="sc-action-name">上传货源</div>
            <div class="sc-action-desc">添加文本或卡密货源</div>
          </div>
        </button>

        <button type="button" class="sc-action-card sc-action-orange" @click="emit('navigate', 'delivery-mall')">
          <div class="sc-action-icon">
            <svg viewBox="0 0 24 24" width="28" height="28" fill="none">
              <path d="M7 22C8.1 22 9 21.1 9 20C9 18.9 8.1 18 7 18C5.9 18 5 18.9 5 20C5 21.1 5.9 22 7 22Z" stroke="currentColor" stroke-width="1.8"/>
              <path d="M17 22C18.1 22 19 21.1 19 20C19 18.9 18.1 18 17 18C15.9 18 15 18.9 15 20C15 21.1 15.9 22 17 22Z" stroke="currentColor" stroke-width="1.8"/>
              <path d="M3 3H5L5.4 5M7 13H17L19 7H5.4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </div>
          <div class="sc-action-text">
            <div class="sc-action-name">货源商城</div>
            <div class="sc-action-desc">浏览全平台货源</div>
          </div>
        </button>

        <button type="button" class="sc-action-card sc-action-green" @click="scrollToMyProducts">
          <div class="sc-action-icon">
            <svg viewBox="0 0 24 24" width="28" height="28" fill="none">
              <path d="M3 7L12 3L21 7L12 11L3 7Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
              <path d="M3 12L12 16L21 12M3 17L12 21L21 17" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
            </svg>
          </div>
          <div class="sc-action-text">
            <div class="sc-action-name">我的货源</div>
            <div class="sc-action-desc">管理已上传的货源</div>
          </div>
        </button>
      </div>
    </div>

    <!-- 收入流水趋势图 -->
    <div class="sc-chart-card">
      <div class="sc-chart-header">
        <h3 class="sc-section-title">收入流水趋势</h3>
        <span class="sc-chart-tag">近7天</span>
      </div>
      <div class="sc-chart-body">
        <div class="sc-chart-empty">
          <svg viewBox="0 0 48 48" width="48" height="48" fill="none">
            <path d="M8 36L18 26L26 30L40 14" stroke="#cbd5e1" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M40 14H34M40 14V20" stroke="#cbd5e1" stroke-width="2" stroke-linecap="round"/>
          </svg>
          <p class="sc-chart-empty-text">收入流水趋势图将在 Phase 2 上线后可用</p>
          <p class="sc-chart-empty-sub">届时可查看每日/每周/每月的收入走势与订单详情</p>
        </div>
      </div>
    </div>

    <!-- 我的货源（直接展示在首页） -->
    <section id="my-products-section" class="sc-my-products">
      <div class="sc-section-header">
        <div class="sc-section-header-left">
          <h3 class="sc-section-title">我的货源</h3>
          <span class="sc-section-count">{{ products.length }} 件</span>
        </div>
        <div class="sc-section-header-right">
          <div class="sc-product-tabs">
            <button
              v-for="tab in productTabs"
              :key="tab.value"
              type="button"
              :class="['sc-prod-tab', { active: activeTab === tab.value }]"
              @click="switchTab(tab.value)"
            >
              {{ tab.label }}
            </button>
          </div>
          <button type="button" class="sc-view-all-btn" @click="emit('navigate', 'supply-center-products')">
            查看全部
            <svg viewBox="0 0 16 16" width="14" height="14" fill="none">
              <path d="M6 4L10 8L6 12" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </div>
      </div>

      <div v-if="productsLoading" class="sc-prod-loading">
        <div v-for="i in 3" :key="i" class="sc-prod-skeleton">
          <div class="sc-prod-skeleton-cover"></div>
          <div class="sc-prod-skeleton-body">
            <div class="sc-skel-line skel-title"></div>
            <div class="sc-skel-line skel-sub"></div>
            <div class="sc-skel-tags">
              <div class="sc-skel-tag"></div>
              <div class="sc-skel-tag"></div>
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="filteredProducts.length === 0" class="sc-prod-empty">
        <svg viewBox="0 0 64 64" width="56" height="56" fill="none">
          <rect x="12" y="16" width="40" height="36" rx="4" stroke="#cbd5e1" stroke-width="2"/>
          <path d="M20 28H44M20 36H36" stroke="#cbd5e1" stroke-width="2" stroke-linecap="round"/>
          <path d="M24 12V20M40 12V20" stroke="#cbd5e1" stroke-width="2" stroke-linecap="round"/>
        </svg>
        <p class="sc-prod-empty-text">{{ emptyText }}</p>
        <button type="button" class="sc-prod-empty-btn" @click="emit('navigate', 'supply-center-products-new')">
          <svg viewBox="0 0 16 16" width="14" height="14" fill="none">
            <path d="M8 3V13M3 8H13" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          </svg>
          去上传货源
        </button>
      </div>

      <div v-else class="sc-prod-list">
        <article v-for="item in filteredProducts.slice(0, 6)" :key="item.id" class="sc-prod-card" @click="handleEdit(item)">
          <div class="sc-prod-cover" :style="coverStyle(item)">
            <span :class="['sc-prod-type-badge', item.productType === 'card' ? 'card' : 'text']">
              {{ item.productType === 'card' ? '卡密' : '文本' }}
            </span>
          </div>
          <div class="sc-prod-body">
            <div class="sc-prod-title-row">
              <h4 class="sc-prod-title">{{ item.title || '未命名货源' }}</h4>
              <span :class="['sc-prod-audit', auditClass(item.auditStatus)]">{{ auditLabel(item.auditStatus) }}</span>
            </div>
            <p v-if="item.subtitle" class="sc-prod-subtitle">{{ item.subtitle }}</p>
            <div class="sc-prod-meta">
              <span class="sc-prod-price">¥{{ formatPrice(item.price) }}</span>
              <span class="sc-prod-stock">
                <svg v-if="item.productType === 'card'" viewBox="0 0 24 24" width="12" height="12" fill="none">
                  <rect x="3" y="7" width="18" height="13" rx="2" stroke="currentColor" stroke-width="1.5"/>
                  <path d="M8 7V5C8 3.9 8.9 3 10 3H14C15.1 3 16 3.9 16 5V7" stroke="currentColor" stroke-width="1.5"/>
                </svg>
                {{ stockDisplay(item) }}{{ item.productType === 'card' ? '张' : '' }}
              </span>
              <span class="sc-prod-sales">已售 {{ item.boughtCount || 0 }}</span>
            </div>
            <div class="sc-prod-status-row">
              <span :class="['sc-prod-status', item.listed ? 'online' : 'offline']">
                <span class="sc-prod-status-dot"></span>
                {{ item.listed ? '已上架' : '未上架' }}
              </span>
              <div class="sc-prod-actions" @click.stop>
                <button
                  v-if="canOnline(item)"
                  type="button"
                  class="sc-prod-act-btn online"
                  :disabled="actionLoading === item.id"
                  @click="handleOnline(item)"
                >上架</button>
                <button
                  v-if="item.listed"
                  type="button"
                  class="sc-prod-act-btn offline"
                  :disabled="actionLoading === item.id"
                  @click="handleOffline(item)"
                >下架</button>
                <button type="button" class="sc-prod-act-btn" @click="handleEdit(item)">编辑</button>
              </div>
            </div>
            <div v-if="item.auditStatus === 'rejected' && item.auditReason" class="sc-prod-reject-reason">
              <svg viewBox="0 0 16 16" width="12" height="12" fill="none">
                <circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.3"/>
                <path d="M8 5V8.5M8 10.5V11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
              驳回原因：{{ item.auditReason }}
            </div>
          </div>
        </article>
      </div>

      <div v-if="filteredProducts.length > 6" class="sc-prod-more">
        <button type="button" class="sc-prod-more-btn" @click="emit('navigate', 'supply-center-products')">
          查看全部 {{ filteredProducts.length }} 件货源
          <svg viewBox="0 0 16 16" width="14" height="14" fill="none">
            <path d="M6 4L10 8L6 12" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import {
  getSupplyDashboard,
  getSupplyProducts,
  onlineSupplyProduct,
  offlineSupplyProduct
} from '../api/supply.js'

const props = defineProps({
  user: { type: Object, default: () => ({}) }
})
const emit = defineEmits(['navigate'])

const stats = ref({
  uploadedCount: 0,
  approvedCount: 0,
  pendingAudit: 0,
  todayIncome: 0,
  todaySales: 0,
  availableBalance: 0,
  frozenBalance: 0
})
const loadError = ref('')
const products = ref([])
const productsLoading = ref(false)
const activeTab = ref('all')
const actionLoading = ref(null)

const productTabs = computed(() => [
  { value: 'all', label: '全部' },
  { value: 'pending', label: '待审核' },
  { value: 'approved', label: '已通过' },
  { value: 'rejected', label: '已驳回' }
])

const filteredProducts = computed(() => {
  if (activeTab.value === 'all') return products.value
  return products.value.filter(p => p.auditStatus === activeTab.value)
})

const emptyText = computed(() => {
  if (activeTab.value === 'all') return '暂无货源，点击下方按钮上传第一件货源'
  if (activeTab.value === 'pending') return '暂无待审核的货源'
  if (activeTab.value === 'approved') return '暂无已通过审核的货源'
  if (activeTab.value === 'rejected') return '暂无被驳回的货源'
  return '暂无货源'
})

const displayName = computed(() => props.user?.nickname || props.user?.username || '供货商')
const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '凌晨好'
  if (h < 12) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

function formatNumber(n) {
  const num = Number(n ?? 0)
  if (!Number.isFinite(num)) return '0'
  return num.toLocaleString('zh-CN')
}

function formatMoney(n) {
  const num = Number(n ?? 0)
  if (!Number.isFinite(num)) return '0.00'
  return num.toFixed(2)
}

function formatPrice(price) {
  const cents = Number(price ?? 0)
  if (!Number.isFinite(cents)) return '0.00'
  return (cents / 100).toFixed(2)
}

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
    listed: Number(item.listed ?? item.status) === 1,
    price: item.price ?? item.price_cent
  }
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
function stockDisplay(item) {
  const t = item.productType || item.type
  if (t === 'text') return '∞'
  const s = Number(item.actualStock ?? item.stock ?? 0)
  return Number.isFinite(s) ? String(s) : '0'
}
function coverStyle(item) {
  const url = item.coverUrl || ''
  if (url) return { backgroundImage: `url(${url})`, backgroundSize: 'cover', backgroundPosition: 'center' }
  return { background: 'linear-gradient(135deg, #dbeafe, #bfdbfe)' }
}

function switchTab(value) {
  if (activeTab.value === value) return
  activeTab.value = value
}

function scrollToMyProducts() {
  nextTick(() => {
    const el = document.getElementById('my-products-section')
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
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

async function loadDashboard() {
  try {
    const res = await getSupplyDashboard()
    const data = res?.data || res || {}
    stats.value = {
      uploadedCount: Number(data.uploadedCount ?? data.uploaded_count ?? 0),
      approvedCount: Number(data.onlineCount ?? data.approvedCount ?? data.approved_count ?? 0),
      pendingAudit: Number(data.pendingAuditCount ?? data.pendingAudit ?? data.pending_audit ?? 0),
      todayIncome: Number(data.todayIncomeCent ?? data.todayIncome ?? 0) / 100,
      todaySales: Number(data.todaySales ?? data.today_sales ?? 0),
      availableBalance: Number(data.availableBalanceCent ?? data.availableBalance ?? 0) / 100,
      frozenBalance: Number(data.frozenBalanceCent ?? data.frozenBalance ?? 0) / 100
    }
  } catch (e) {
    loadError.value = e?.message || '供货中心数据加载失败，请稍后重试'
  }
}

async function loadProducts() {
  productsLoading.value = true
  try {
    const res = await getSupplyProducts({ page: 1, size: 50 })
    const data = res?.data || res || {}
    const list = Array.isArray(data) ? data : (data.records || data.list || data.items || [])
    products.value = list.map(normalizeProduct)
  } catch (e) {
    console.error('[supply-center] 加载货源列表失败', e)
    products.value = []
  } finally {
    productsLoading.value = false
  }
}

async function loadAll() {
  loadError.value = ''
  await Promise.all([loadDashboard(), loadProducts()])
}

onMounted(loadAll)
</script>

<style scoped>
.supply-center-page {
  width: 100%;
  min-height: 100%;
  box-sizing: border-box;
  padding: 4px;
}

/* 横幅 */
.sc-banner {
  background: linear-gradient(120deg, #1e40af 0%, #2563eb 40%, #4f7cff 100%);
  border-radius: 20px;
  padding: 28px 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 20px;
  position: relative;
  overflow: hidden;
  box-shadow: 0 8px 24px rgba(37, 99, 235, 0.2);
}
.sc-banner::before {
  content: '';
  position: absolute;
  top: -60px;
  right: -40px;
  width: 200px;
  height: 200px;
  border-radius: 50%;
  background: rgba(255,255,255,0.06);
}
.sc-banner::after {
  content: '';
  position: absolute;
  bottom: -80px;
  left: 30%;
  width: 160px;
  height: 160px;
  border-radius: 50%;
  background: rgba(255,255,255,0.04);
}
.sc-banner-left {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
  min-width: 0;
  position: relative;
  z-index: 1;
}
.sc-banner-avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.15);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: 2px solid rgba(255, 255, 255, 0.3);
}
.sc-banner-info {
  min-width: 0;
}
.sc-banner-title {
  font-size: 24px;
  font-weight: 800;
  color: #fff;
  margin: 0 0 6px;
  line-height: 1.2;
  letter-spacing: -0.3px;
}
.sc-banner-desc {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.85);
  margin: 0;
  line-height: 1.5;
}
.sc-banner-illustration {
  flex-shrink: 0;
  position: relative;
  z-index: 1;
}
@media (max-width: 768px) {
  .sc-banner {
    flex-direction: column;
    align-items: flex-start;
    padding: 24px 20px;
    border-radius: 16px;
  }
  .sc-banner-illustration {
    display: none;
  }
}

/* 错误提示 */
.sc-error-tip {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 12px;
  color: #ef4444;
  font-size: 13px;
  margin-bottom: 20px;
}
.sc-error-tip svg {
  flex-shrink: 0;
}
.sc-retry-btn {
  margin-left: auto;
  height: 32px;
  padding: 0 14px;
  border-radius: 10px;
  border: 1px solid #ef4444;
  background: #fff;
  color: #ef4444;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}
.sc-retry-btn:hover {
  background: #ef4444;
  color: #fff;
}

/* 统计卡片 */
.sc-stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-bottom: 20px;
}
@media (max-width: 1200px) {
  .sc-stats-row { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 540px) {
  .sc-stats-row { grid-template-columns: repeat(2, 1fr); gap: 10px; }
}

.sc-stat-card {
  background: #fff;
  border-radius: 16px;
  padding: 18px 20px;
  border: 1px solid #e8edf5;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  display: flex;
  align-items: flex-start;
  gap: 14px;
  transition: transform 0.25s cubic-bezier(0.4,0,0.2,1), box-shadow 0.25s;
}
.sc-stat-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08);
}
.sc-stat-icon-wrap {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.sc-stat-blue .sc-stat-icon-wrap { background: linear-gradient(135deg, rgba(79, 124, 255, 0.12), rgba(79, 124, 255, 0.06)); color: #4f7cff; }
.sc-stat-green .sc-stat-icon-wrap { background: linear-gradient(135deg, rgba(16, 185, 129, 0.12), rgba(16, 185, 129, 0.06)); color: #10b981; }
.sc-stat-orange .sc-stat-icon-wrap { background: linear-gradient(135deg, rgba(245, 158, 11, 0.12), rgba(245, 158, 11, 0.06)); color: #f59e0b; }
.sc-stat-purple .sc-stat-icon-wrap { background: linear-gradient(135deg, rgba(139, 92, 246, 0.12), rgba(139, 92, 246, 0.06)); color: #8b5cf6; }

.sc-stat-body {
  flex: 1;
  min-width: 0;
}
.sc-stat-label {
  font-size: 12px;
  color: #94a3b8;
  font-weight: 600;
  margin-bottom: 4px;
}
.sc-stat-value {
  display: flex;
  align-items: baseline;
  gap: 2px;
  margin-bottom: 4px;
}
.sc-stat-value strong {
  font-size: 22px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1.2;
  letter-spacing: -0.5px;
}
.sc-stat-value em {
  font-size: 13px;
  font-weight: 500;
  color: #64748b;
  font-style: normal;
  margin-left: 2px;
}
.sc-stat-sub {
  font-size: 11px;
  color: #94a3b8;
  line-height: 1.4;
}

/* 待办提醒 */
.sc-todo-reminder {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
  background: linear-gradient(135deg, #fef3c7, #fde68a);
  border: 1px solid #fcd34d;
  border-radius: 14px;
  margin-bottom: 20px;
  animation: slideDown 0.3s ease;
}
@keyframes slideDown {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}
.sc-todo-icon {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: rgba(217, 119, 6, 0.2);
  color: #92400e;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.sc-todo-text {
  flex: 1;
  font-size: 13px;
  color: #92400e;
  line-height: 1.5;
}
.sc-todo-text strong {
  font-weight: 800;
}
.sc-todo-link {
  height: 32px;
  padding: 0 14px;
  border-radius: 10px;
  border: none;
  background: #92400e;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  flex-shrink: 0;
}
.sc-todo-link:hover {
  background: #78350f;
  transform: scale(1.02);
}

/* 快捷操作 */
.sc-quick-actions {
  margin-bottom: 20px;
}
.sc-section-title {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
  margin: 0 0 14px;
  letter-spacing: -0.2px;
}
.sc-action-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
@media (max-width: 768px) {
  .sc-action-grid { grid-template-columns: 1fr; }
}
.sc-action-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 20px;
  background: #fff;
  border: 1px solid #e8edf5;
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4,0,0.2,1);
  text-align: left;
  font-family: inherit;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}
.sc-action-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08);
}
.sc-action-icon {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.sc-action-blue .sc-action-icon { background: linear-gradient(135deg, #dbeafe, #bfdbfe); color: #2563eb; }
.sc-action-green .sc-action-icon { background: linear-gradient(135deg, #d1fae5, #a7f3d0); color: #059669; }
.sc-action-orange .sc-action-icon { background: linear-gradient(135deg, #fed7aa, #fdba74); color: #ea580c; }
.sc-action-text {
  flex: 1;
  min-width: 0;
}
.sc-action-name {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 2px;
}
.sc-action-desc {
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.4;
}

/* 趋势图卡片 */
.sc-chart-card {
  background: #fff;
  border-radius: 16px;
  border: 1px solid #e8edf5;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  overflow: hidden;
  margin-bottom: 20px;
}
.sc-chart-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #f1f5f9;
}
.sc-chart-tag {
  padding: 4px 10px;
  border-radius: 8px;
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.1), rgba(139, 92, 246, 0.05));
  color: #8b5cf6;
  font-size: 11px;
  font-weight: 700;
}
.sc-chart-body {
  padding: 36px 20px;
}
.sc-chart-empty {
  text-align: center;
}
.sc-chart-empty-text {
  font-size: 14px;
  font-weight: 600;
  color: #64748b;
  margin: 12px 0 4px;
}
.sc-chart-empty-sub {
  font-size: 12px;
  color: #94a3b8;
  margin: 0;
}

/* ===== 我的货源区域 ===== */
.sc-my-products {
  background: #fff;
  border-radius: 20px;
  border: 1px solid #e8edf5;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  overflow: hidden;
}
.sc-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px 14px;
  border-bottom: 1px solid #f1f5f9;
  gap: 12px;
  flex-wrap: wrap;
}
.sc-section-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.sc-section-header-left .sc-section-title {
  margin-bottom: 0;
}
.sc-section-count {
  padding: 2px 8px;
  border-radius: 6px;
  background: #f1f5f9;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
}
.sc-section-header-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

/* 商品筛选 tabs */
.sc-product-tabs {
  display: flex;
  gap: 4px;
  background: #f8fafc;
  padding: 3px;
  border-radius: 10px;
}
.sc-prod-tab {
  padding: 6px 14px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  font-family: inherit;
}
.sc-prod-tab:hover {
  color: #4f7cff;
}
.sc-prod-tab.active {
  background: #fff;
  color: #4f7cff;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.sc-view-all-btn {
  display: flex;
  align-items: center;
  gap: 2px;
  height: 32px;
  padding: 0 12px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  font-family: inherit;
}
.sc-view-all-btn:hover {
  border-color: #4f7cff;
  color: #4f7cff;
}

/* 骨架屏 */
.sc-prod-loading {
  padding: 12px;
}
.sc-prod-skeleton {
  display: flex;
  gap: 12px;
  padding: 12px;
  border-radius: 12px;
}
.sc-prod-skeleton-cover {
  width: 80px;
  height: 80px;
  border-radius: 12px;
  background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  flex-shrink: 0;
}
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
.sc-prod-skeleton-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 4px;
}
.sc-skel-line {
  height: 14px;
  border-radius: 4px;
  background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
.skel-title { width: 70%; height: 16px; }
.skel-sub { width: 40%; height: 12px; }
.sc-skel-tags {
  display: flex;
  gap: 6px;
  margin-top: auto;
}
.sc-skel-tag {
  width: 50px;
  height: 20px;
  border-radius: 6px;
  background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}

/* 空状态 */
.sc-prod-empty {
  padding: 48px 20px;
  text-align: center;
}
.sc-prod-empty svg {
  margin-bottom: 12px;
  opacity: 0.6;
}
.sc-prod-empty-text {
  margin: 0 0 16px;
  font-size: 14px;
  color: #64748b;
}
.sc-prod-empty-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 40px;
  padding: 0 20px;
  border-radius: 12px;
  border: none;
  background: linear-gradient(90deg, #0865f4, #147dff);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 4px 12px rgba(13, 107, 255, 0.25);
  font-family: inherit;
}
.sc-prod-empty-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(13, 107, 255, 0.35);
}

/* 商品卡片列表 */
.sc-prod-list {
  padding: 8px;
}
.sc-prod-card {
  display: flex;
  gap: 12px;
  padding: 12px;
  border-radius: 14px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}
.sc-prod-card:hover {
  background: #f8fafc;
  border-color: #e2e8f0;
}
.sc-prod-card + .sc-prod-card {
  border-top: 1px solid #f1f5f9;
}
.sc-prod-card:hover + .sc-prod-card {
  border-top-color: transparent;
}
.sc-prod-cover {
  width: 80px;
  height: 80px;
  border-radius: 12px;
  flex-shrink: 0;
  background-color: #e2e8f0;
  position: relative;
  overflow: hidden;
}
.sc-prod-type-badge {
  position: absolute;
  top: 6px;
  left: 6px;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 10px;
  font-weight: 700;
  backdrop-filter: blur(8px);
}
.sc-prod-type-badge.text {
  background: rgba(79, 124, 255, 0.9);
  color: #fff;
}
.sc-prod-type-badge.card {
  background: rgba(245, 158, 11, 0.9);
  color: #fff;
}
.sc-prod-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.sc-prod-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}
.sc-prod-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  margin: 0;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
}
.sc-prod-audit {
  flex-shrink: 0;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 10px;
  font-weight: 700;
  white-space: nowrap;
}
.audit-pending { background: rgba(245, 158, 11, 0.1); color: #f59e0b; }
.audit-approved { background: rgba(16, 185, 129, 0.1); color: #10b981; }
.audit-rejected { background: rgba(239, 68, 68, 0.1); color: #ef4444; }
.audit-unknown { background: #f1f5f9; color: #64748b; }

.sc-prod-subtitle {
  font-size: 12px;
  color: #94a3b8;
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sc-prod-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 2px;
}
.sc-prod-price {
  font-size: 16px;
  font-weight: 800;
  color: #ff3b30;
}
.sc-prod-stock {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  color: #94a3b8;
}
.sc-prod-stock svg {
  opacity: 0.7;
}
.sc-prod-sales {
  font-size: 11px;
  color: #94a3b8;
}

.sc-prod-status-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: auto;
  padding-top: 4px;
}
.sc-prod-status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  font-weight: 600;
}
.sc-prod-status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}
.sc-prod-status.online { color: #10b981; }
.sc-prod-status.online .sc-prod-status-dot { background: #10b981; box-shadow: 0 0 0 2px rgba(16,185,129,0.15); }
.sc-prod-status.offline { color: #94a3b8; }
.sc-prod-status.offline .sc-prod-status-dot { background: #cbd5e1; }

.sc-prod-actions {
  display: flex;
  gap: 4px;
}
.sc-prod-act-btn {
  height: 26px;
  padding: 0 10px;
  border-radius: 7px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475569;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  font-family: inherit;
}
.sc-prod-act-btn:hover:not(:disabled) {
  border-color: #c7d2fe;
}
.sc-prod-act-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.sc-prod-act-btn.online { color: #10b981; border-color: rgba(16,185,129,0.3); }
.sc-prod-act-btn.online:hover:not(:disabled) { background: rgba(16,185,129,0.06); border-color: #10b981; }
.sc-prod-act-btn.offline { color: #f59e0b; border-color: rgba(245,158,11,0.3); }
.sc-prod-act-btn.offline:hover:not(:disabled) { background: rgba(245,158,11,0.06); border-color: #f59e0b; }
.sc-prod-act-btn:not(.online):not(.offline):hover:not(:disabled) {
  color: #4f7cff;
  border-color: #4f7cff;
}

.sc-prod-reject-reason {
  display: flex;
  align-items: flex-start;
  gap: 4px;
  margin-top: 6px;
  padding: 6px 10px;
  background: #fef2f2;
  border-radius: 8px;
  font-size: 11px;
  color: #ef4444;
  line-height: 1.4;
}
.sc-prod-reject-reason svg {
  flex-shrink: 0;
  margin-top: 1px;
}

/* 查看更多 */
.sc-prod-more {
  padding: 8px 16px 16px;
  text-align: center;
}
.sc-prod-more-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 36px;
  padding: 0 20px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #4f7cff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  font-family: inherit;
}
.sc-prod-more-btn:hover {
  background: #f0f5ff;
  border-color: #4f7cff;
}

@media (max-width: 540px) {
  .sc-section-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }
  .sc-section-header-right {
    width: 100%;
    justify-content: space-between;
  }
  .sc-prod-cover {
    width: 68px;
    height: 68px;
  }
  .sc-prod-meta {
    gap: 8px;
    flex-wrap: wrap;
  }
}
</style>
