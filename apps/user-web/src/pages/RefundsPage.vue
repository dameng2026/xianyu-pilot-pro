<template>
  <div class="refunds-page">
    <div v-if="notice.text" class="global-notice" :class="notice.type">{{ notice.text }}</div>

    <!-- 顶部筛选区 -->
    <div class="filter-bar">
      <div class="filter-title">退款筛选</div>
      <div class="filter-row">
        <select
          v-model="selectedAccountId"
          class="filter-select"
          :disabled="!fishShopAccountsAvailable"
          @change="onAccountChange"
        >
          <option value="">{{ fishShopAccountsAvailable ? '全部账号' : '账号列表加载中...' }}</option>
          <option v-for="account in fishShopAccounts" :key="account.id" :value="String(account.id)">
            {{ accountLabel(account) }}
          </option>
        </select>

        <AppButton
          type="primary"
          :loading="syncing"
          :disabled="!canSync"
          class="btn-sync"
          @click="onSyncClick"
        >
          <span class="sync-icon">↻</span>
          {{ syncing ? '同步中...' : syncButtonText }}
        </AppButton>

        <AppButton
          class="btn-refresh"
          :disabled="loading"
          @click="loadRefunds(true)"
        >
          <span class="refresh-icon">↻</span>
          刷新列表
        </AppButton>
      </div>

      <div class="filter-tip">
        <template v-if="syncStatus.lastSyncTime">
          上次更新：{{ formatTime(syncStatus.lastSyncTime) }}
          <span v-if="syncStatus.isSyncing" class="sync-status syncing">· 同步中</span>
          <span v-else-if="syncStatus.cacheExpired" class="sync-status expired">· 数据可能已过期，建议刷新</span>
          <span v-else class="sync-status fresh">· 数据为最新</span>
        </template>
        <template v-else>
          {{ fishShopAccounts.length ? '尚未同步退款数据，请点击右侧"同步退款"' : '当前账号下暂无鱼小铺账号' }}
        </template>
      </div>
    </div>

    <!-- 分类标签 -->
    <div class="category-tabs">
      <button
        v-for="tab in categoryTabs"
        :key="tab.key"
        type="button"
        :class="['tab-item', { active: selectedCategory === tab.key }]"
        @click="onCategoryChange(tab.key)"
      >
        {{ tab.label }}
        <span v-if="tab.unavailable" class="tab-tag" title="缺少真实接口映射">未映射</span>
      </button>
    </div>

    <!-- 表格卡片 -->
    <div class="refunds-table-card">
      <div class="table-header">
        <h3 class="table-title">
          退款列表
          <span v-if="total > 0" class="table-count">共 {{ formatNumber(total) }} 条</span>
        </h3>
      </div>

      <!-- 加载中（首次） -->
      <div v-if="loading && !items.length" class="table-loading" role="status" aria-live="polite">
        <div class="spinner"></div>
        <p class="subtle">{{ initialized ? '正在加载退款...' : '退款数据加载中，请稍候...' }}</p>
      </div>

      <!-- 普通账号提示 -->
      <EmptyState
        v-else-if="isNormalAccountSelected"
        icon="⚠"
        title="当前闲鱼账号不支持退款管理"
        description="只有鱼小铺账号可以使用退款管理功能。请在账号选择中切换为鱼小铺账号，或选择「全部账号」查看所有鱼小铺账号的退款。"
      />

      <!-- 退运费分类未映射 -->
      <EmptyState
        v-else-if="categoryUnavailable"
        variant="dev"
        icon="🚧"
        title="退运费分类暂未确认接口映射"
        :description="categoryUnavailableReason || '当前样本中没有确认退运费对应的 queryCode 或 orderStatus，暂不展示数据。'"
      />

      <!-- 部分账号同步失败 -->
      <div v-if="partialSyncFailed.length" class="partial-failed-notice">
        <span class="warn-icon">⚠</span>
        以下账号同步失败，已展示其他账号数据：
        <strong>{{ partialSyncFailed.join('、') }}</strong>
      </div>

      <!-- 空数据 -->
      <EmptyState
        v-else-if="!items.length && initialized"
        :icon="emptyIcon"
        :title="emptyTitle"
        :description="emptyDescription"
      />

      <!-- 表格 -->
      <div v-else-if="items.length" class="table-wrap">
        <table class="refunds-table">
          <thead>
            <tr>
              <th>所属账号</th>
              <th>商品信息</th>
              <th class="col-num">件数</th>
              <th class="col-money">退款金额</th>
              <th>退款类型</th>
              <th>退款状态</th>
              <th>退款原因</th>
              <th>客服介入</th>
              <th>物流信息</th>
              <th class="col-time">退款申请时间</th>
              <th class="col-op">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in items" :key="row.id || row.externalRefundId || idx" class="refund-row">
              <td class="col-account">
                <div class="account-cell">
                  <div class="account-name">{{ row.accountNickname || '账号 ' + row.accountId }}</div>
                  <div class="account-id subtle">ID: {{ row.accountId }}</div>
                </div>
              </td>
              <td class="col-item">
                <div class="goods-cell">
                  <img
                    v-if="row.itemPicUrl"
                    :src="row.itemPicUrl"
                    class="goods-thumb"
                    alt=""
                    referrerpolicy="no-referrer"
                    @error="onImageError($event)"
                  />
                  <div v-else class="goods-thumb goods-thumb-placeholder">🖼</div>
                  <div class="goods-info">
                    <div class="goods-title" :title="row.itemTitle || ''">{{ row.itemTitle || '-' }}</div>
                    <div v-if="row.itemInfoLines" class="goods-spec">{{ row.itemInfoLines }}</div>
                    <div class="goods-ids subtle">
                      <span v-if="row.externalItemId">商品ID：{{ row.externalItemId }}</span>
                      <span v-if="row.externalOrderId">订单ID：{{ row.externalOrderId }}</span>
                    </div>
                  </div>
                </div>
              </td>
              <td class="col-num">{{ formatBuyNum(row.buyNum) }}</td>
              <td class="col-money">
                <div class="refund-fee">{{ formatMoney(row.refundFee) }}</div>
                <div v-if="row.auctionPrice" class="auction-price subtle">单价 {{ formatMoney(row.auctionPrice) }}</div>
              </td>
              <td>
                <span :class="['status-badge', orderStatusBadgeClass(row.orderStatus)]">
                  {{ row.orderStatus || '-' }}
                </span>
              </td>
              <td>
                <div class="refund-status">
                  <div v-if="row.refundStatus" class="refund-status-main">{{ row.refundStatus }}</div>
                  <div v-else class="subtle">-</div>
                  <div v-if="row.refundStatusDesc" class="refund-status-desc subtle">{{ row.refundStatusDesc }}</div>
                  <div v-if="row.orderSimpleRemark" class="refund-status-remark subtle">{{ row.orderSimpleRemark }}</div>
                </div>
              </td>
              <td class="col-reason">
                <span v-if="row.refundReason" :title="row.refundReason">{{ row.refundReason }}</span>
                <span v-else class="subtle">-</span>
              </td>
              <td>
                <span v-if="row.csStatus" :class="['cs-badge', csBadgeClass(row.csStatus)]">{{ row.csStatus }}</span>
                <span v-else class="subtle">-</span>
              </td>
              <td class="col-logistics">
                <template v-if="row.logisticsCompany || row.logisticsMailNo">
                  <div v-if="row.logisticsCompany" class="logistics-company">{{ row.logisticsCompany }}</div>
                  <div v-if="row.logisticsMailNo" class="logistics-no subtle" :title="row.logisticsMailNo">
                    {{ row.logisticsMailNo }}
                  </div>
                  <div v-if="row.consignTime" class="logistics-time subtle">{{ formatTime(row.consignTime) }}</div>
                </template>
                <span v-else class="subtle">暂无物流信息</span>
              </td>
              <td class="col-time">
                <div v-if="row.refundCreateTime">{{ formatTime(row.refundCreateTime) }}</div>
                <div v-else-if="row.commonCreateTime" class="subtle">{{ formatTime(row.commonCreateTime) }}</div>
                <div v-else class="subtle">-</div>
              </td>
              <td class="col-op">
                <div class="op-cell">
                  <button
                    v-if="hasButton(row, 'viewRefundDetail')"
                    type="button"
                    class="op-link"
                    @click="onViewDetail(row)"
                  >
查看详情
</button>
                  <button
                    v-if="hasButton(row, 'applyDisputePage')"
                    type="button"
                    class="op-link op-warn"
                    @click="onApplyDispute(row)"
                  >
我要维权
</button>
                  <button
                    v-if="hasButton(row, 'agreeRefundApply')"
                    type="button"
                    class="op-link op-primary"
                    :disabled="agreeingRefundId === row.externalRefundId"
                    @click="onAgreeRefund(row)"
                  >
                    {{ agreeingRefundId === row.externalRefundId ? '处理中...' : '同意退款' }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 分页 -->
      <div v-if="items.length && total > 0" class="pagination-wrap">
        <Pagination
          :total="total"
          :current="query.page"
          :page-size="query.pageSize"
          :sizes="[10, 20, 50, 100]"
          @page-change="onPageChange"
          @size-change="onPageSizeChange"
        />
      </div>
    </div>

    <!-- 同意退款确认弹窗 -->
    <Teleport to="body">
      <div v-if="agreeModal.visible" class="refund-modal-mask" @click.self="closeAgreeModal">
        <section class="refund-modal">
          <button class="refund-modal-close" type="button" @click="closeAgreeModal">×</button>
          <h2 class="refund-modal-title">{{ agreeModal.title || '确认同意退款' }}</h2>
          <div class="refund-modal-body">
            <div class="agree-warn-banner">
              <span class="warn-icon">⚠</span>
              <span>同意退款属于资金操作，可能立即退款给买家。请仔细确认以下信息。</span>
            </div>

            <div class="agree-detail">
              <div class="agree-row">
                <span class="agree-label">退款ID：</span>
                <span class="agree-value mono">{{ agreeModal.refundId || '-' }}</span>
              </div>
              <div class="agree-row">
                <span class="agree-label">所属账号：</span>
                <span class="agree-value">{{ agreeModal.accountLabel || '-' }}</span>
              </div>
              <div v-if="agreeModal.itemTitle" class="agree-row">
                <span class="agree-label">商品：</span>
                <span class="agree-value">{{ agreeModal.itemTitle }}</span>
              </div>
              <div v-if="agreeModal.refundFee" class="agree-row">
                <span class="agree-label">退款金额：</span>
                <span class="agree-value refund-fee-strong">{{ formatMoney(agreeModal.refundFee) }}</span>
              </div>
              <div v-if="agreeModal.riskDesc" class="agree-row">
                <span class="agree-label">风险说明：</span>
                <span class="agree-value risk-text">{{ agreeModal.riskDesc }}</span>
              </div>
              <div v-if="agreeModal.confirmText" class="agree-row">
                <span class="agree-label">确认内容：</span>
                <span class="agree-value">{{ agreeModal.confirmText }}</span>
              </div>
            </div>
          </div>
          <div class="refund-modal-footer">
            <AppButton type="ghost" :disabled="agreeModal.submitting" @click="closeAgreeModal">取消</AppButton>
            <AppButton
              type="primary"
              :loading="agreeModal.submitting"
              :disabled="agreeModal.submitting"
              @click="confirmAgreeRefund"
            >
{{ agreeModal.submitButtonText || '确认同意退款' }}
</AppButton>
          </div>
        </section>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, shallowRef } from 'vue'
import AppButton from '../components/AppButton.vue'
import EmptyState from '../components/EmptyState.vue'
import Pagination from '../components/Pagination.vue'
import {
  getRefunds,
  getRefundSyncStatus,
  syncRefunds,
  agreeRefund,
  getRefundFishShopAccounts,
} from '../api/refunds.js'
import { accountName } from '../utils/format.js'
import {
  saveRefundListState,
  consumeRefundListState,
} from '../utils/refundListState.js'

// 路由跳转事件（App.vue 监听 navigate，调用 navigate() 切换 hash）
const emit = defineEmits(['navigate'])

// ============================================================
// 分类标签定义
// ============================================================
// 仅 ALL 有真实 queryCode；其他标签按 orderStatus 精确筛选；退运费暂无可靠映射。
const categoryTabs = [
  { key: 'all', label: '全部订单', unavailable: false },
  { key: 'unshipped', label: '未发货退款', unavailable: false },
  { key: 'shipped', label: '已发货退款', unavailable: false },
  { key: 'return', label: '退货退款', unavailable: false },
  { key: 'freight', label: '退运费', unavailable: true },
]

// ============================================================
// 状态
// ============================================================
const fishShopAccounts = ref([])
const fishShopAccountsAvailable = ref(false)
const fishShopAccountsError = ref('')

// 选中的账号ID：'' 表示全部账号
const selectedAccountId = ref('')

// 选中的分类
const selectedCategory = ref('all')

const items = shallowRef([])
const total = ref(0)
const loading = ref(false)
const initialized = ref(false)
const syncing = ref(false)
const notice = reactive({ text: '', type: 'info' })

// 同步状态
const syncStatus = reactive({
  hasCache: false,
  isSyncing: false,
  lastSyncTime: null,
  lastSyncStatus: null,
  cacheExpired: true,
  accountCount: 0,
})

// 部分账号同步失败列表（账号名）
const partialSyncFailed = ref([])

// 分页
const query = reactive({
  page: 1,
  pageSize: 20,
})

// 同意退款弹窗
const agreeModal = reactive({
  visible: false,
  refundId: '',
  accountId: null,
  accountLabel: '',
  itemTitle: '',
  refundFee: '',
  riskDesc: '',
  confirmText: '',
  title: '',
  submitButtonText: '',
  submitting: false,
})

// 正在处理同意退款的 refundId（防止重复点击）
const agreeingRefundId = ref('')

// 轮询定时器
let syncStatusPollTimer = null

// ============================================================
// 计算属性
// ============================================================
const selectedAccountIdNum = computed(() => {
  const id = Number(selectedAccountId.value)
  return Number.isFinite(id) && id > 0 ? id : null
})

// 是否选中了普通账号（不在鱼小铺列表中说明是普通账号——但本页面只列出鱼小铺账号，所以这种情况不会发生；
// 此字段保留为 false，后端会再次校验）
const isNormalAccountSelected = computed(() => false)

const canSync = computed(() => fishShopAccounts.value.length > 0 && !syncing.value)

const syncButtonText = computed(() => {
  if (selectedAccountIdNum.value) return '同步当前账号'
  return '同步全部账号'
})

const categoryUnavailable = computed(() => {
  if (selectedCategory.value !== 'freight') return false
  // 退运费分类暂无可靠映射
  return true
})

const categoryUnavailableReason = computed(() => {
  if (selectedCategory.value === 'freight') {
    return '退运费分类尚未确认接口映射，暂不显示数据。如需支持，请补充真实请求样本中的 queryCode 或 orderStatus。'
  }
  return ''
})

const emptyIcon = computed(() => {
  if (syncStatus.isSyncing && !items.value.length) return '⏳'
  if (selectedAccountIdNum.value) return '∅'
  return '∅'
})

const emptyTitle = computed(() => {
  if (syncStatus.isSyncing && !items.value.length) return '正在首次同步退款数据...'
  if (!fishShopAccounts.value.length) return '暂无鱼小铺账号'
  if (selectedAccountIdNum.value) return '当前账号暂无退款记录'
  return '暂无退款记录'
})

const emptyDescription = computed(() => {
  if (syncStatus.isSyncing && !items.value.length) return '首次同步可能需要一些时间，请稍后刷新查看。'
  if (!fishShopAccounts.value.length) return '当前账号下没有鱼小铺账号，无法使用退款管理功能。'
  if (selectedAccountIdNum.value) return '当前账号在所选分类下没有退款记录。'
  return '所有鱼小铺账号在所选分类下暂无退款记录。'
})

// ============================================================
// 工具方法
// ============================================================
function accountLabel(account) {
  if (!account) return '-'
  return accountName(account) || `账号 ${account.id || ''}`
}

function formatNumber(n) {
  const num = Number(n) || 0
  return num.toLocaleString('zh-CN')
}

function formatMoney(value) {
  if (value === null || value === undefined || value === '') return '—'
  // 后端返回字符串形式以避免精度丢失，前端使用字符串转十进制再格式化
  const s = String(value).trim()
  if (!s) return '—'
  // 移除非数字字符（保留小数点和负号）
  const cleaned = s.replace(/[^0-9.-]/g, '')
  if (!cleaned || cleaned === '-' || cleaned === '.') return '—'
  const num = Number(cleaned)
  if (!Number.isFinite(num)) return String(value)
  return `¥${num.toFixed(2)}`
}

function formatBuyNum(value) {
  if (value === null || value === undefined || value === '') return '—'
  const s = String(value).trim()
  const n = parseInt(s, 10)
  if (!Number.isFinite(n) || n < 0) return s
  return String(n)
}

function formatTime(value) {
  if (!value) return '-'
  if (typeof value === 'number') {
    const d = new Date(value)
    return Number.isNaN(d.getTime()) ? '-' : d.toLocaleString('zh-CN', { hour12: false })
  }
  return String(value).replace('T', ' ').replace(/\.\d+$/, '')
}

function orderStatusBadgeClass(orderStatus) {
  if (!orderStatus) return 'gray'
  const s = String(orderStatus)
  if (s.includes('未发货')) return 'orange'
  if (s.includes('已发货')) return 'blue'
  if (s.includes('退货')) return 'purple'
  if (s.includes('完成') || s.includes('成功')) return 'green'
  if (s.includes('失败') || s.includes('拒绝')) return 'red'
  return 'gray'
}

function csBadgeClass(csStatus) {
  if (!csStatus) return 'gray'
  const s = String(csStatus).toLowerCase()
  if (s.includes('in') || s.includes('active') || s.includes('介入')) return 'red'
  if (s.includes('no') || s.includes('none') || s.includes('无')) return 'gray'
  return 'blue'
}

function showNotice(text, type = 'info') {
  notice.text = text
  notice.type = type
  if (showNotice._timer) clearTimeout(showNotice._timer)
  showNotice._timer = setTimeout(() => {
    notice.text = ''
  }, 4500)
}

// ============================================================
// 操作按钮判断（根据 rightVO.btnList）
// ============================================================
function hasButton(row, code) {
  if (!row || !Array.isArray(row.rightButtons)) return false
  return row.rightButtons.some(btn => {
    if (!btn || typeof btn !== 'object') return false
    return btn.code === code
  })
}

function findButton(row, code) {
  if (!row || !Array.isArray(row.rightButtons)) return null
  return row.rightButtons.find(btn => btn && btn.code === code) || null
}

// 安全打开外部 URL（仅允许闲鱼/阿里官方域名）
const TRUSTED_REFUND_HOSTS = [
  'goofish.com',
  'www.goofish.com',
  'seller.goofish.com',
  'h5api.m.goofish.com',
  'taobao.com',
  'www.taobao.com',
  'trade.taobao.com',
  'alibaba.com',
  'www.alibaba.com',
  'alipay.com',
  'www.alipay.com',
  'm.alipay.com',
]

function isSafeRefundUrl(url) {
  if (!url || typeof url !== 'string') return false
  const lower = url.toLowerCase().trim()
  // 拒绝危险协议
  if (lower.startsWith('javascript:') || lower.startsWith('data:') || lower.startsWith('file:') || lower.startsWith('vbscript:')) {
    return false
  }
  let parsed
  try {
    parsed = new URL(url)
  } catch {
    return false
  }
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return false
  const host = (parsed.hostname || '').toLowerCase()
  if (!host) return false
  return TRUSTED_REFUND_HOSTS.some(trusted => host === trusted || host.endsWith('.' + trusted))
}

function openExternalUrl(url) {
  if (!isSafeRefundUrl(url)) {
    showNotice('链接不在允许的官方域名内，已拒绝打开', 'error')
    return
  }
  try {
    const opened = window.open(url, '_blank', 'noopener,noreferrer')
    if (!opened) {
      showNotice('浏览器拦截了新窗口，请允许弹窗后重试', 'warn')
    } else {
      try { opened.opener = null } catch { /* noopener already isolates */ }
    }
  } catch {
    showNotice('链接打开失败，请稍后重试', 'error')
  }
}

// ============================================================
// 加载账号列表
// ============================================================
async function loadFishShopAccounts(force = false) {
  if (!force && fishShopAccountsAvailable.value) return
  try {
    const res = await getRefundFishShopAccounts()
    const data = res?.data || {}
    const list = Array.isArray(data.accounts) ? data.accounts : []
    fishShopAccounts.value = list
    fishShopAccountsAvailable.value = true
    fishShopAccountsError.value = ''
  } catch (err) {
    fishShopAccountsError.value = err?.message || '加载账号列表失败'
    showNotice('加载鱼小铺账号列表失败：' + (err?.message || '未知错误'), 'error')
  }
}

// ============================================================
// 加载退款列表（缓存优先）
// ============================================================
async function loadRefunds(_forceRefresh = false) {
  loading.value = true
  try {
    const params = {
      category: selectedCategory.value,
      page: query.page,
      pageSize: query.pageSize,
    }
    if (selectedAccountIdNum.value) {
      params.accountId = selectedAccountIdNum.value
    }
    const res = await getRefunds(params)
    const data = res?.data || {}
    // 退运费分类未映射
    if (data.categoryUnavailable) {
      items.value = []
      total.value = 0
      initialized.value = true
      return
    }
    items.value = Array.isArray(data.items) ? data.items : []
    total.value = Number(data.total) || 0
    initialized.value = true
  } catch (err) {
    showNotice('加载退款列表失败：' + (err?.message || '未知错误'), 'error')
    // 保留旧数据不清空
  } finally {
    loading.value = false
  }
}

// ============================================================
// 加载同步状态
// ============================================================
async function loadSyncStatus() {
  try {
    const params = {}
    if (selectedAccountIdNum.value) {
      params.accountId = selectedAccountIdNum.value
    }
    const res = await getRefundSyncStatus(params)
    const data = res?.data || {}
    syncStatus.hasCache = !!data.hasCache
    syncStatus.isSyncing = !!data.isSyncing
    syncStatus.lastSyncTime = data.lastSyncTime || null
    syncStatus.lastSyncStatus = data.lastSyncStatus || null
    syncStatus.cacheExpired = !!data.cacheExpired
    syncStatus.accountCount = Number(data.accountCount) || 0
  } catch {
    // 静默失败，不阻塞页面
  }
}

// ============================================================
// 同步触发
// ============================================================
async function onSyncClick() {
  if (syncing.value) return
  if (!fishShopAccounts.value.length) {
    showNotice('当前账号下没有鱼小铺账号，无法同步', 'warn')
    return
  }
  syncing.value = true
  partialSyncFailed.value = []
  try {
    const payload = {}
    if (selectedAccountIdNum.value) {
      payload.accountId = selectedAccountIdNum.value
    }
    const res = await syncRefunds(payload)
    const data = res?.data || {}
    if (data.alreadyRunning) {
      showNotice('当前账号正在同步中，请稍后刷新查看', 'info')
    } else if (data.ok === false) {
      showNotice(data.error || '同步失败', 'error')
    } else {
      const msg = buildSyncSuccessMessage(data)
      showNotice(msg, 'success')
    }
    // 立即刷新状态，然后重新加载列表
    await loadSyncStatus()
    await loadRefunds(true)
  } catch (err) {
    showNotice('同步失败：' + (err?.message || '未知错误'), 'error')
  } finally {
    syncing.value = false
  }
}

function buildSyncSuccessMessage(data) {
  if (selectedAccountIdNum.value) {
    const parts = ['同步完成']
    if (Number.isFinite(data.total)) parts.push(`共 ${data.total} 条`)
    if (Number.isFinite(data.new)) parts.push(`新增 ${data.new} 条`)
    if (Number.isFinite(data.updated)) parts.push(`更新 ${data.updated} 条`)
    return parts.join('，')
  }
  // 全部账号
  const parts = ['同步已触发']
  if (Number.isFinite(data.total)) parts.push(`合计 ${data.total} 条`)
  return parts.join('，')
}

// ============================================================
// 操作：查看详情
// ============================================================
// 需求第二节：退款列表点击"查看详情"进入项目内部详情页，不再默认跳转外部闲鱼详情。
// 需求第三节：进入详情必须能确定 所属账号 + orderId + refundId + 列表摘要；
//            同一订单可能有多次退款，必须以 refundId 定位当前退款。
// 需求第三节：返回列表时恢复 账号筛选 / 分类 / 页码 / 滚动位置。
function onViewDetail(row) {
  const accountId = row?.accountId
  const orderId = row?.externalOrderId
  const refundId = row?.externalRefundId
  if (!accountId || !orderId || !refundId) {
    showNotice('该退款记录缺少必要参数，无法打开详情', 'warn')
    return
  }

  // 保存列表筛选状态，供 RefundDetailPage 返回时恢复
  saveRefundListState({
    selectedAccountId: selectedAccountId.value,
    category: selectedCategory.value,
    page: query.page,
    pageSize: query.pageSize,
    scrollTop: typeof window === 'undefined' ? 0 : Math.max(0, window.scrollY || 0),
  })

  // 跳转到内部 refund-detail 路由（不带外部闲鱼链接）
  // 路由形态：refund-detail/{accountId}/{orderId}/{refundId}
  emit('navigate', `refund-detail/${accountId}/${encodeURIComponent(orderId)}/${encodeURIComponent(refundId)}`)
}

// ============================================================
// 操作：我要维权
// ============================================================
function onApplyDispute(row) {
  const btn = findButton(row, 'applyDisputePage')
  const url = btn?.clickEvent?.data?.url
  if (!url) {
    showNotice('该退款记录未返回有效的维权链接', 'warn')
    return
  }
  openExternalUrl(url)
}

// ============================================================
// 操作：同意退款
// ============================================================
async function onAgreeRefund(row) {
  if (agreeingRefundId.value) return
  const btn = findButton(row, 'agreeRefundApply')
  if (!btn) {
    showNotice('当前退款记录不支持同意退款操作', 'warn')
    return
  }

  // 构造确认弹窗内容（优先使用服务端返回的文案）
  const doubleCheck = btn.clickEvent?.doubleCheck || btn.clickEvent?.data || {}
  const refundId = row.externalRefundId
  if (!refundId) {
    showNotice('退款ID缺失，无法发起同意退款', 'error')
    return
  }

  agreeModal.refundId = String(refundId)
  agreeModal.accountId = row.accountId
  agreeModal.accountLabel = row.accountNickname || `账号 ${row.accountId}`
  agreeModal.itemTitle = row.itemTitle || ''
  agreeModal.refundFee = row.refundFee || ''
  agreeModal.riskDesc = doubleCheck.riskDesc || doubleCheck.riskDescription || '同意退款后可能立即退款给买家，此操作不可撤销。'
  agreeModal.confirmText = doubleCheck.confirmText || doubleCheck.content || ''
  agreeModal.title = doubleCheck.title || '确认同意退款'
  agreeModal.submitButtonText = doubleCheck.confirmButtonText || doubleCheck.buttonText || '确认同意退款'
  agreeModal.submitting = false
  agreeModal.visible = true
}

async function confirmAgreeRefund() {
  if (agreeModal.submitting) return
  if (!agreeModal.refundId || !agreeModal.accountId) {
    showNotice('参数缺失，无法同意退款', 'error')
    closeAgreeModal()
    return
  }

  agreeModal.submitting = true
  agreeingRefundId.value = String(agreeModal.refundId)

  try {
    const res = await agreeRefund(agreeModal.refundId, { accountId: agreeModal.accountId })
    const data = res?.data || {}
    if (data.ok === false) {
      showNotice(data.error || '同意退款失败', 'error')
    } else {
      showNotice(data.message || '同意退款请求已提交', 'success')
      closeAgreeModal()
      // 定向刷新该账号：重新加载列表 + 同步状态
      await loadSyncStatus()
      await loadRefunds(true)
    }
  } catch (err) {
    showNotice('同意退款失败：' + (err?.message || '未知错误'), 'error')
    // 失败时不改变本地状态（需求第二十三节）
  } finally {
    agreeModal.submitting = false
    agreeingRefundId.value = ''
  }
}

function closeAgreeModal() {
  if (agreeModal.submitting) return // 提交中不允许关闭
  agreeModal.visible = false
}

// ============================================================
// 事件处理
// ============================================================
function onAccountChange() {
  query.page = 1
  // 切换账号时立即查询本地缓存
  loadRefunds(true)
  loadSyncStatus()
}

function onCategoryChange(category) {
  if (selectedCategory.value === category) return
  selectedCategory.value = category
  query.page = 1
  // 切换分类时仅查询本地缓存（不触发闲鱼请求）
  loadRefunds(true)
}

function onPageChange(page) {
  query.page = page
  loadRefunds(true)
}

function onPageSizeChange(size) {
  query.pageSize = size
  query.page = 1
  loadRefunds(true)
}

function onImageError(event) {
  if (event?.target) event.target.style.display = 'none'
}

// ============================================================
// 缓存过期自动刷新策略（需求第十六节）
// ============================================================
function startSyncStatusPolling() {
  stopSyncStatusPolling()
  // 每 30 秒检查一次同步状态，缓存过期时触发后台刷新
  syncStatusPollTimer = setInterval(async () => {
    if (document.hidden) return // 页面不可见时不轮询
    await loadSyncStatus()
    // 如果缓存已过期且当前没有同步任务，触发后台刷新
    if (syncStatus.cacheExpired && !syncStatus.isSyncing && !syncing.value && fishShopAccounts.value.length) {
      // 后台刷新，不显示同步状态
      try {
        const payload = {}
        if (selectedAccountIdNum.value) {
          payload.accountId = selectedAccountIdNum.value
        }
        await syncRefunds(payload)
        await loadSyncStatus()
        await loadRefunds(true)
      } catch {
        // 后台刷新失败静默处理
      }
    }
  }, 30000)
}

function stopSyncStatusPolling() {
  if (syncStatusPollTimer) {
    clearInterval(syncStatusPollTimer)
    syncStatusPollTimer = null
  }
}

function onPageVisibilityChange() {
  if (document.hidden) {
    stopSyncStatusPolling()
  } else {
    // 页面重新可见时，立即检查一次并恢复轮询
    loadSyncStatus()
    startSyncStatusPolling()
  }
}

// ============================================================
// 生命周期
// ============================================================
onMounted(async () => {
  // 从详情页返回时恢复筛选状态（需求第三节：恢复账号筛选、分类、页码、滚动位置）
  // consumeRefundListState 会清除状态，避免重复恢复
  const savedState = consumeRefundListState()
  if (savedState) {
    selectedAccountId.value = savedState.selectedAccountId || ''
    selectedCategory.value = savedState.category || 'all'
    query.page = savedState.page > 0 ? savedState.page : 1
    query.pageSize = savedState.pageSize > 0 ? savedState.pageSize : 20
  }

  await loadFishShopAccounts()
  await loadSyncStatus()
  await loadRefunds(true)

  // 首次进入页面，如果完全没有缓存，触发首次同步
  if (!syncStatus.hasCache && !syncStatus.isSyncing && fishShopAccounts.value.length) {
    onSyncClick()
  }

  startSyncStatusPolling()
  document.addEventListener('visibilitychange', onPageVisibilityChange)

  // 恢复滚动位置（在 DOM 渲染后执行）
  if (savedState && savedState.scrollTop > 0) {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        try {
          window.scrollTo({ top: savedState.scrollTop, left: 0, behavior: 'instant' })
        } catch {
          window.scrollTo(0, savedState.scrollTop)
        }
      })
    })
  }
})

onBeforeUnmount(() => {
  stopSyncStatusPolling()
  document.removeEventListener('visibilitychange', onPageVisibilityChange)
})
</script>

<style scoped>
.refunds-page { padding: 0 0 24px; }

.global-notice {
  padding: 10px 14px;
  border-radius: 10px;
  margin-bottom: 12px;
  font-size: 13px;
  line-height: 1.6;
}
.global-notice.info { background: #eef5ff; color: #1d3958; border: 1px solid #cfe0ff; }
.global-notice.success { background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; }
.global-notice.warn { background: #fffbeb; color: #92400e; border: 1px solid #fde68a; }
.global-notice.error { background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }

/* 筛选区 */
.filter-bar {
  background: #fff;
  border: 1px solid #e4ebf5;
  border-radius: 14px;
  padding: 18px 20px;
  margin-bottom: 16px;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.03);
}
.filter-title { font-size: 15px; font-weight: 600; color: #16213e; margin-bottom: 12px; }
.filter-row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.filter-select {
  height: 36px;
  border: 1px solid #e4ebf5;
  border-radius: 8px;
  background: #fff;
  color: #526079;
  padding: 0 12px;
  font-size: 13px;
  min-width: 220px;
  cursor: pointer;
}
.filter-select:disabled { background: #f5f7fa; cursor: not-allowed; }
.btn-sync, .btn-refresh { height: 36px; }
.sync-icon, .refresh-icon { display: inline-block; margin-right: 4px; }
.filter-tip {
  margin-top: 10px;
  font-size: 12px;
  color: #758198;
}
.sync-status.syncing { color: #2563eb; }
.sync-status.expired { color: #d97706; }
.sync-status.fresh { color: #059669; }

/* 分类标签 */
.category-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.tab-item {
  position: relative;
  padding: 8px 16px;
  border: 1px solid #e4ebf5;
  border-radius: 20px;
  background: #fff;
  color: #526079;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}
.tab-item:hover { border-color: #c7d6f5; background: #f6faff; }
.tab-item.active {
  background: var(--primary, #2563eb);
  color: #fff;
  border-color: var(--primary, #2563eb);
}
.tab-tag {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: 8px;
  background: #fef3c7;
  color: #92400e;
  font-size: 10px;
  font-weight: 600;
}
.tab-item.active .tab-tag { background: rgba(255,255,255,0.25); color: #fff; }

/* 表格卡片 */
.refunds-table-card {
  background: #fff;
  border: 1px solid #e4ebf5;
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.03);
}
.table-header {
  padding: 16px 20px;
  border-bottom: 1px solid #f0f4fa;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.table-title { margin: 0; font-size: 15px; font-weight: 600; color: #16213e; }
.table-count { margin-left: 8px; font-size: 12px; font-weight: 400; color: #758198; }

.table-loading {
  padding: 60px 20px;
  text-align: center;
}
.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #e4ebf5;
  border-top-color: var(--primary, #2563eb);
  border-radius: 50%;
  margin: 0 auto 12px;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.subtle { color: #758198; font-size: 12px; }

.partial-failed-notice {
  padding: 10px 20px;
  background: #fffbeb;
  color: #92400e;
  font-size: 13px;
  border-bottom: 1px solid #fde68a;
}
.partial-failed-notice .warn-icon { margin-right: 6px; }

.table-wrap { overflow-x: auto; }
.refunds-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.refunds-table thead th {
  padding: 12px 14px;
  text-align: left;
  background: #f8fafc;
  color: #526079;
  font-weight: 600;
  font-size: 12px;
  border-bottom: 1px solid #e4ebf5;
  white-space: nowrap;
}
.refunds-table tbody td {
  padding: 14px;
  border-bottom: 1px solid #f0f4fa;
  vertical-align: top;
  color: #16213e;
}
.refund-row:hover { background: #f8fbff; }
.col-num, .col-money { text-align: right; }
.col-time { white-space: nowrap; }
.col-op { white-space: nowrap; }

.col-account .account-name { font-weight: 500; color: #16213e; }
.col-account .account-id { margin-top: 2px; }

.goods-cell { display: flex; gap: 10px; align-items: flex-start; min-width: 240px; }
.goods-thumb {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  object-fit: cover;
  background: #f5f7fa;
  flex: 0 0 auto;
}
.goods-thumb-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #9ca3af;
  font-size: 18px;
}
.goods-info { flex: 1; min-width: 0; }
.goods-title {
  font-weight: 500;
  color: #16213e;
  margin-bottom: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 280px;
}
.goods-spec { color: #758198; font-size: 12px; margin-bottom: 2px; }
.goods-ids { display: flex; gap: 8px; flex-wrap: wrap; }

.refund-fee { font-weight: 600; color: #dc2626; font-size: 14px; }
.auction-price { margin-top: 2px; }

.refund-status-main { font-weight: 500; color: #16213e; }
.refund-status-desc { margin-top: 2px; }
.refund-status-remark { margin-top: 2px; }

.col-reason { max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.logistics-company { font-weight: 500; }
.logistics-no { margin-top: 2px; }
.logistics-time { margin-top: 2px; }

/* 状态徽章 */
.status-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
}
.status-badge.gray { background: #f3f4f6; color: #4b5563; }
.status-badge.orange { background: #fff7ed; color: #c2410c; }
.status-badge.blue { background: #eff6ff; color: #1d4ed8; }
.status-badge.purple { background: #faf5ff; color: #7e22ce; }
.status-badge.green { background: #ecfdf5; color: #059669; }
.status-badge.red { background: #fef2f2; color: #dc2626; }

.cs-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
}
.cs-badge.gray { background: #f3f4f6; color: #6b7280; }
.cs-badge.red { background: #fef2f2; color: #dc2626; }
.cs-badge.blue { background: #eff6ff; color: #2563eb; }

/* 操作按钮 */
.op-cell { display: flex; gap: 6px; flex-wrap: wrap; }
.op-link {
  background: none;
  border: none;
  color: var(--primary, #2563eb);
  font-size: 12px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: background 0.15s;
}
.op-link:hover:not(:disabled) { background: #eff6ff; }
.op-link:disabled { opacity: 0.5; cursor: not-allowed; }
.op-link.op-primary { color: #dc2626; font-weight: 500; }
.op-link.op-primary:hover:not(:disabled) { background: #fef2f2; }
.op-link.op-warn { color: #d97706; }
.op-link.op-warn:hover:not(:disabled) { background: #fffbeb; }

/* 分页 */
.pagination-wrap {
  padding: 14px 20px;
  border-top: 1px solid #f0f4fa;
  display: flex;
  justify-content: flex-end;
}

/* 同意退款确认弹窗 */
.refund-modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: 20px;
}
.refund-modal {
  background: #fff;
  border-radius: 14px;
  width: 100%;
  max-width: 520px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 50px rgba(0,0,0,0.2);
}
.refund-modal-close {
  position: absolute;
  top: 14px;
  right: 16px;
  background: none;
  border: none;
  font-size: 22px;
  color: #9ca3af;
  cursor: pointer;
  line-height: 1;
}
.refund-modal-close:hover { color: #4b5563; }
.refund-modal-title {
  margin: 0;
  padding: 18px 24px;
  font-size: 16px;
  font-weight: 600;
  color: #16213e;
  border-bottom: 1px solid #f0f4fa;
  position: relative;
}
.refund-modal-body {
  padding: 20px 24px;
  overflow-y: auto;
  flex: 1;
}
.agree-warn-banner {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 12px 14px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
  color: #92400e;
  font-size: 13px;
  margin-bottom: 16px;
}
.agree-warn-banner .warn-icon { flex: 0 0 auto; }
.agree-detail { font-size: 13px; }
.agree-row { display: flex; padding: 6px 0; border-bottom: 1px dashed #f0f4fa; }
.agree-row:last-child { border-bottom: none; }
.agree-label {
  width: 80px;
  color: #758198;
  flex: 0 0 80px;
}
.agree-value { color: #16213e; flex: 1; word-break: break-all; }
.agree-value.mono { font-family: 'Consolas', 'Monaco', monospace; font-size: 12px; }
.refund-fee-strong { color: #dc2626; font-weight: 600; font-size: 15px; }
.risk-text { color: #dc2626; }
.refund-modal-footer {
  padding: 14px 24px;
  border-top: 1px solid #f0f4fa;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

/* 响应式 */
@media (max-width: 768px) {
  .filter-row { flex-direction: column; align-items: stretch; }
  .filter-select { width: 100%; min-width: 0; }
  .btn-sync, .btn-refresh { width: 100%; }
  .refunds-table { font-size: 12px; }
  .refunds-table thead th, .refunds-table tbody td { padding: 8px; }
  .goods-cell { min-width: 160px; }
  .goods-title { max-width: 140px; }
}
</style>
