<template>
  <div class="rates-page">
    <!-- 页面标题区域 -->
    <div class="page-header-bar">
      <div class="page-header-left">
        <h1 class="page-title">评价管理</h1>
        <p class="page-subtitle">集中查看买家评价并对未评价订单进行卖家评价（仅鱼小铺账号可用）</p>
      </div>
      <div class="page-header-right">
        <div class="sync-status">
          <span v-if="syncing" class="sync-badge syncing">同步中...</span>
          <span v-else-if="lastSyncTime" class="sync-badge done">最后更新：{{ formatTime(lastSyncTime) }}</span>
          <span v-else class="sync-badge none">尚未同步</span>
        </div>
        <AppButton :loading="syncing" :disabled="!accountsAvailable || !accounts.length" class="btn-refresh" @click="onRefreshClick">
          <span class="refresh-icon">↻</span>
          {{ syncing ? '刷新中...' : '刷新' }}
        </AppButton>
      </div>
    </div>

    <!-- 全局提示 -->
    <div v-if="globalError" class="global-notice error">{{ globalError }}</div>
    <div v-if="globalSuccess" class="global-notice success">{{ globalSuccess }}</div>
    <div v-if="accountsLoadError" class="global-notice error">账号列表加载失败：{{ accountsLoadError }}</div>
    <div v-if="!accountsAvailable && !accountsLoading" class="global-notice warn">
      当前没有可用的鱼小铺账号，评价管理功能仅对鱼小铺账号开放。
    </div>

    <!-- 概览卡片 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon-circle blue"><span class="stat-icon-svg">📄</span></div>
        <div class="stat-info">
          <div class="stat-label">评价记录总数</div>
          <div class="stat-value">{{ formatNumber(overview.total) }}</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon-circle orange"><span class="stat-icon-svg">⏳</span></div>
        <div class="stat-info">
          <div class="stat-label">待评价</div>
          <div class="stat-value">{{ formatNumber(overview.pending) }}</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon-circle green"><span class="stat-icon-svg">✅</span></div>
        <div class="stat-info">
          <div class="stat-label">已评价</div>
          <div class="stat-value">{{ formatNumber(overview.done) }}</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon-circle gray"><span class="stat-icon-svg">🕒</span></div>
        <div class="stat-info">
          <div class="stat-label">最近同步</div>
          <div class="stat-value text-sm">{{ overview.lastSyncTime ? formatTime(overview.lastSyncTime) : '尚未同步' }}</div>
        </div>
      </div>
    </div>

    <!-- 筛选区域 -->
    <div class="filter-bar">
      <div class="filter-title">评价筛选</div>
      <div class="filter-row">
        <select v-model="query.accountId" class="filter-select" :disabled="!accountsAvailable" @change="onFilterChange">
          <option value="">{{ accountsAvailable ? '全部账号' : '账号列表不可用' }}</option>
          <option v-for="account in accounts" :key="account.id" :value="String(account.id)">
            {{ accountName(account) }}
          </option>
        </select>
        <select v-model="query.category" class="filter-select" @change="onFilterChange">
          <option value="all">全部状态</option>
          <option value="pending">待评价</option>
          <option value="done">已评价</option>
        </select>
        <div class="filter-search">
          <input v-model="query.keyword" class="search-input" placeholder="搜索订单号 / 商品ID / 商品标题 / 买家昵称" @keyup.enter="onFilterChange" />
          <span class="search-icon">🔍</span>
        </div>
        <AppButton type="primary" class="btn-query" @click="onFilterChange">查询</AppButton>
        <AppButton class="btn-reset" @click="resetFilters">重置</AppButton>
      </div>
      <div class="filter-tip">
        列表默认优先展示本地已缓存评价；如需拉取闲鱼最新评价，请点击右上角"刷新"。
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="listLoading && !items.length" class="loading-state">
      <div class="spinner"></div>
      <div>正在加载缓存数据...</div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!items.length && !listLoading" class="empty-state">
      <div class="empty-icon">📭</div>
      <div class="empty-text">{{ emptyText }}</div>
      <AppButton v-if="!items.length && accountsAvailable" type="primary" @click="onRefreshClick">立即同步</AppButton>
    </div>

    <!-- 评价列表 -->
    <div v-else class="rates-table-wrap">
      <table class="rates-table">
        <thead>
          <tr>
            <th class="col-account">所属账号</th>
            <th class="col-buyer">买家信息</th>
            <th class="col-item">商品信息</th>
            <th class="col-order">订单号</th>
            <th class="col-status">订单状态</th>
            <th class="col-finish">完成时间</th>
            <th class="col-buyer-rate">买家评价</th>
            <th class="col-seller-rate">卖家评价</th>
            <th class="col-rate-status">评价状态</th>
            <th class="col-action">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="`${item.accountId}-${item.externalOrderId}`">
            <td class="col-account">
              <div class="account-cell">
                <span class="account-name">{{ item.accountNickname || `账号#${item.accountId}` }}</span>
              </div>
            </td>
            <td class="col-buyer">
              <div class="buyer-cell">
                <img v-if="item.buyerIcon" :src="item.buyerIcon" class="buyer-avatar" alt="买家头像" @error="onAvatarError" />
                <div v-else class="buyer-avatar placeholder">👤</div>
                <span class="buyer-nick">{{ item.buyerNick || '匿名买家' }}</span>
              </div>
            </td>
            <td class="col-item">
              <div class="item-cell">
                <img v-if="item.itemPicUrl" :src="item.itemPicUrl" class="item-pic" alt="商品图" @error="onItemImageError" />
                <div v-else class="item-pic placeholder">📦</div>
                <div class="item-info">
                  <div class="item-title" :title="item.itemTitle || ''">{{ item.itemTitle || '未知商品' }}</div>
                  <div class="item-id">ID: {{ item.externalItemId || '-' }}</div>
                </div>
              </div>
            </td>
            <td class="col-order">
              <span class="order-id" :title="item.externalOrderId">{{ item.externalOrderId }}</span>
            </td>
            <td class="col-status">
              <span class="status-tag" :class="statusClass(item.orderStatus)">{{ item.orderStatus || '-' }}</span>
            </td>
            <td class="col-finish">
              <span v-if="item.finishTime">{{ formatTime(item.finishTime) }}</span>
              <span v-else class="text-muted">-</span>
            </td>
            <td class="col-buyer-rate">
              <div v-if="item.buyerRateContent || item.buyerRateLevel" class="rate-content">
                <div class="rate-level-row">
                  <span class="rate-level" :class="rateLevelClass(item.buyerRateLevel)">等级 {{ item.buyerRateLevel || '?' }}</span>
                </div>
                <div v-if="item.buyerRateContent" class="rate-text" :title="item.buyerRateContent">{{ item.buyerRateContent }}</div>
                <div v-if="item.buyerRateTime" class="rate-time">{{ formatTime(item.buyerRateTime) }}</div>
              </div>
              <span v-else class="text-muted">未评价</span>
            </td>
            <td class="col-seller-rate">
              <div v-if="item.hasSellerRate" class="rate-content">
                <div class="rate-level-row">
                  <span class="rate-level seller" :class="rateLevelClass(item.sellerRateLevel)">等级 {{ item.sellerRateLevel || '?' }}</span>
                </div>
                <div v-if="item.sellerRateContent" class="rate-text" :title="item.sellerRateContent">{{ item.sellerRateContent }}</div>
                <div v-if="item.sellerRateTime" class="rate-time">{{ formatTime(item.sellerRateTime) }}</div>
              </div>
              <span v-else class="text-muted">未评价</span>
            </td>
            <td class="col-rate-status">
              <span v-if="item.hasSellerRate" class="rate-status-tag done">已评价</span>
              <span v-else-if="item.rateReviewable" class="rate-status-tag pending">待评价</span>
              <span v-else class="rate-status-tag unavailable">不可评价</span>
            </td>
            <td class="col-action">
              <AppButton v-if="canRate(item)" type="primary" size="small" @click="openRateDialog(item)">评价</AppButton>
              <AppButton v-else-if="item.hasSellerRate" size="small" disabled>已评价</AppButton>
              <span v-else class="text-muted text-sm">不可评价</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 分页 -->
    <div v-if="total > 0" class="pagination-wrap">
      <Pagination
        :current="query.page"
        :total="total"
        :page-size="query.pageSize"
        @change="onPageChange"
      />
    </div>

    <!-- 评价弹窗 -->
    <div v-if="dialogVisible" class="rate-dialog-mask" @click.self="closeRateDialog">
      <div class="rate-dialog">
        <div class="dialog-header">
          <h3 class="dialog-title">评价订单</h3>
          <button class="dialog-close" @click="closeRateDialog">×</button>
        </div>
        <div class="dialog-body">
          <!-- 订单基本信息 -->
          <div class="dialog-order-info">
            <div class="dialog-info-row">
              <span class="info-label">所属账号：</span>
              <span class="info-value">{{ currentRateItem?.accountNickname || `账号#${currentRateItem?.accountId}` }}</span>
            </div>
            <div class="dialog-info-row">
              <span class="info-label">买家昵称：</span>
              <span class="info-value">{{ currentRateItem?.buyerNick || '匿名买家' }}</span>
            </div>
            <div class="dialog-info-row">
              <span class="info-label">商品标题：</span>
              <span class="info-value">{{ currentRateItem?.itemTitle || '未知商品' }}</span>
            </div>
            <div class="dialog-info-row">
              <span class="info-label">订单号：</span>
              <span class="info-value">{{ currentRateItem?.externalOrderId }}</span>
            </div>
            <div v-if="currentRateItem?.itemPicUrl" class="dialog-info-row">
              <span class="info-label">商品封面：</span>
              <img :src="currentRateItem.itemPicUrl" class="dialog-item-pic" alt="商品图" @error="onDialogImageError" />
            </div>
          </div>

          <!-- 评价等级 -->
          <div class="dialog-section">
            <div class="section-label">评价等级 <span class="required">*</span></div>
            <div class="rate-level-cards">
              <div class="rate-level-card" :class="{ selected: dialogForm.rate === 1, confirmed: true }" @click="selectRateLevel(1)">
                <div class="rate-level-icon good">👍</div>
                <div class="rate-level-name">好评</div>
                <div class="rate-level-desc">rate=1（已确认）</div>
              </div>
              <div class="rate-level-card" :class="{ selected: dialogForm.rate === 0, disabled: true }" @click="selectRateLevel(0)">
                <div class="rate-level-icon neutral">😐</div>
                <div class="rate-level-name">中评</div>
                <div class="rate-level-desc">未确认映射</div>
              </div>
              <div class="rate-level-card" :class="{ selected: dialogForm.rate === -1, disabled: true }" @click="selectRateLevel(-1)">
                <div class="rate-level-icon bad">👎</div>
                <div class="rate-level-name">差评</div>
                <div class="rate-level-desc">未确认映射</div>
              </div>
            </div>
            <div v-if="rateLevelWarning" class="rate-level-warning">{{ rateLevelWarning }}</div>
          </div>

          <!-- 匿名评价 -->
          <div class="dialog-section">
            <div class="section-label">匿名评价</div>
            <label class="anonymous-toggle">
              <input v-model="dialogForm.anonymous" type="checkbox" :disabled="submitting" />
              <span class="toggle-text">{{ dialogForm.anonymous ? '已选择匿名' : '不匿名（显示卖家信息）' }}</span>
            </label>
          </div>

          <!-- 评价内容 -->
          <div class="dialog-section">
            <div class="section-label">评价内容</div>
            <textarea
              v-model="dialogForm.feedback"
              class="feedback-input"
              :disabled="submitting"
              placeholder="请输入评价内容（选填，最多 500 字）"
              maxlength="500"
              rows="4"
            ></textarea>
            <div class="feedback-count">{{ dialogForm.feedback.length }} / 500</div>
          </div>
        </div>
        <div class="dialog-footer">
          <AppButton :disabled="submitting" @click="closeRateDialog">取消</AppButton>
          <AppButton type="primary" :loading="submitting" :disabled="!canSubmit" @click="submitRate">确认评价</AppButton>
        </div>
        <div v-if="dialogError" class="dialog-error">{{ dialogError }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import AppButton from '../components/AppButton.vue'
import Pagination from '../components/Pagination.vue'
import {
  getRates,
  syncRates,
  getRateSyncStatus,
  getRateOverview,
  createRate,
  getRateFishShopAccounts,
} from '../api/rates'

// ============================================================
// 响应式状态
// ============================================================

const accounts = ref([])
const accountsLoading = ref(false)
const accountsLoadError = ref('')
const accountsAvailable = computed(() => accounts.value.length > 0)

const items = ref([])
const total = ref(0)
const listLoading = ref(false)

const overview = reactive({
  total: 0,
  pending: 0,
  done: 0,
  lastSyncTime: null,
})

const query = reactive({
  accountId: '',
  category: 'all',
  keyword: '',
  page: 1,
  pageSize: 20,
})

const syncing = ref(false)
const lastSyncTime = ref(null)
const cacheExpired = ref(false)

const globalError = ref('')
const globalSuccess = ref('')

// 评价弹窗状态
const dialogVisible = ref(false)
const currentRateItem = ref(null)
const dialogForm = reactive({
  rate: 1,
  feedback: '',
  anonymous: true,
})
const submitting = ref(false)
const dialogError = ref('')
const rateLevelWarning = ref('')

// 轮询定时器
let pollTimer = null
let visibilityHandler = null
let focusHandler = null

// ============================================================
// 计算属性
// ============================================================

const canSubmit = computed(() => {
  // 仅当等级已确认（好评=1）时可提交
  if (dialogForm.rate !== 1) return false
  if (dialogForm.feedback.length > 500) return false
  return true
})

const emptyText = computed(() => {
  if (!accountsAvailable.value) return '当前没有可用的鱼小铺账号'
  if (listLoading.value) return '正在加载...'
  if (syncing.value) return '正在同步评价数据...'
  if (query.keyword) return '没有匹配的评价记录'
  if (query.category === 'pending') return '没有待评价的订单'
  if (query.category === 'done') return '没有已评价的订单'
  return '暂无评价记录，请点击"刷新"同步闲鱼数据'
})

// ============================================================
// 账号管理
// ============================================================

function accountName(account) {
  if (!account) return ''
  if (account.nickname) return account.nickname
  if (account.external_uid) return `账号${account.external_uid.slice(-6)}`
  return `账号#${account.id}`
}

async function loadAccounts() {
  accountsLoading.value = true
  accountsLoadError.value = ''
  try {
    const res = await getRateFishShopAccounts()
    accounts.value = res?.data?.accounts || []
  } catch (e) {
    accountsLoadError.value = e?.message || '未知错误'
    accounts.value = []
  } finally {
    accountsLoading.value = false
  }
}

// ============================================================
// 列表查询（缓存优先）
// ============================================================

async function loadList() {
  listLoading.value = true
  try {
    const params = {
      category: query.category,
      page: query.page,
      pageSize: query.pageSize,
    }
    if (query.accountId) params.accountId = Number(query.accountId)
    if (query.keyword && query.keyword.trim()) params.keyword = query.keyword.trim()
    const res = await getRates(params)
    items.value = res?.data?.items || []
    total.value = res?.data?.total || 0
  } catch (e) {
    // 不清空已有数据，避免闪烁
    globalError.value = `评价列表加载失败：${e?.message || '未知错误'}`
    setTimeout(() => { globalError.value = '' }, 5000)
  } finally {
    listLoading.value = false
  }
}

async function loadOverview() {
  try {
    const params = {}
    if (query.accountId) params.accountId = Number(query.accountId)
    const res = await getRateOverview(params.accountId)
    overview.total = res?.data?.total || 0
    overview.pending = res?.data?.pending || 0
    overview.done = res?.data?.done || 0
    overview.lastSyncTime = res?.data?.lastSyncTime || null
  } catch {
    // 概览加载失败不阻塞
  }
}

async function loadSyncStatus() {
  try {
    const params = {}
    if (query.accountId) params.accountId = Number(query.accountId)
    const res = await getRateSyncStatus(params.accountId)
    syncing.value = !!res?.data?.isSyncing
    lastSyncTime.value = res?.data?.lastSyncTime || null
    cacheExpired.value = !!res?.data?.cacheExpired

    // 缓存过期且未在同步时，触发后台刷新（不阻塞页面）
    if (cacheExpired.value && !syncing.value && accountsAvailable.value) {
      triggerBackgroundSync()
    }
  } catch {
    // 状态查询失败不阻塞
  }
}

// ============================================================
// 同步触发
// ============================================================

async function triggerBackgroundSync() {
  if (syncing.value) return
  syncing.value = true
  try {
    const data = {}
    if (query.accountId) data.accountId = Number(query.accountId)
    await syncRates(data)
    // 同步完成后刷新数据（无闪烁合并）
    await Promise.all([loadList(), loadOverview(), loadSyncStatus()])
  } catch (e) {
    // 后台同步失败不阻塞，保留旧缓存
    globalError.value = `后台同步失败：${e?.message || '未知错误'}`
    setTimeout(() => { globalError.value = '' }, 5000)
    await loadSyncStatus()
  }
}

async function onRefreshClick() {
  if (syncing.value) return
  if (!accountsAvailable.value) {
    globalError.value = '当前没有可用的鱼小铺账号'
    setTimeout(() => { globalError.value = '' }, 3000)
    return
  }
  syncing.value = true
  try {
    const data = {}
    if (query.accountId) data.accountId = Number(query.accountId)
    const res = await syncRates(data)
    if (res?.data?.alreadyRunning) {
      globalSuccess.value = '该账号正在同步中，请稍后刷新查看'
    } else {
      globalSuccess.value = '同步已完成'
    }
    setTimeout(() => { globalSuccess.value = '' }, 3000)
    await Promise.all([loadList(), loadOverview(), loadSyncStatus()])
  } catch (e) {
    globalError.value = `刷新失败：${e?.message || '未知错误'}`
    setTimeout(() => { globalError.value = '' }, 5000)
    await loadSyncStatus()
  } finally {
    syncing.value = false
  }
}

// ============================================================
// 筛选与分页
// ============================================================

function onFilterChange() {
  query.page = 1
  loadList()
  loadOverview()
}

function resetFilters() {
  query.accountId = ''
  query.category = 'all'
  query.keyword = ''
  query.page = 1
  loadList()
  loadOverview()
}

function onPageChange(page) {
  query.page = page
  loadList()
}

// ============================================================
// 评价弹窗
// ============================================================

function canRate(item) {
  // 仅当未评价且 rateReviewable=1 时显示评价按钮
  return !item.hasSellerRate && item.rateReviewable
}

function openRateDialog(item) {
  if (!canRate(item)) return
  currentRateItem.value = item
  dialogForm.rate = 1  // 默认好评（唯一已确认等级）
  dialogForm.feedback = ''
  dialogForm.anonymous = true
  dialogError.value = ''
  rateLevelWarning.value = ''
  dialogVisible.value = true
}

function closeRateDialog() {
  if (submitting.value) return  // 提交中不允许关闭
  dialogVisible.value = false
  currentRateItem.value = null
  dialogError.value = ''
  rateLevelWarning.value = ''
}

function selectRateLevel(level) {
  if (submitting.value) return
  dialogForm.rate = level
  dialogError.value = ''
  // 仅好评（rate=1）已确认，中评/差评未确认
  if (level === 1) {
    rateLevelWarning.value = ''
  } else {
    rateLevelWarning.value = '当前评价等级的真实 rate 值尚未通过真实接口样本确认，暂不可提交。仅好评（rate=1）已确认可用。'
  }
}

async function submitRate() {
  if (submitting.value) return
  if (!canSubmit.value) {
    if (dialogForm.rate !== 1) {
      dialogError.value = '当前评价等级未确认映射，仅支持好评（rate=1）。'
    }
    return
  }
  const item = currentRateItem.value
  if (!item) return

  submitting.value = true
  dialogError.value = ''
  try {
    await createRate({
      accountId: Number(item.accountId),
      orderId: String(item.externalOrderId),
      rate: 1,  // 仅提交已确认的好评
      feedback: dialogForm.feedback.trim(),
      anonymous: !!dialogForm.anonymous,
    })
    globalSuccess.value = '评价已提交'
    setTimeout(() => { globalSuccess.value = '' }, 3000)
    dialogVisible.value = false
    currentRateItem.value = null
    // 刷新列表与概览
    await Promise.all([loadList(), loadOverview(), loadSyncStatus()])
  } catch (e) {
    // 失败后保留用户输入
    dialogError.value = e?.message || '创建评价失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

// ============================================================
// 格式化与工具
// ============================================================

function formatNumber(n) {
  if (n === null || n === undefined) return '0'
  return Number(n).toLocaleString('zh-CN')
}

function formatTime(time) {
  if (!time) return '-'
  try {
    const d = new Date(time)
    if (isNaN(d.getTime())) return String(time)
    const yyyy = d.getFullYear()
    const mm = String(d.getMonth() + 1).padStart(2, '0')
    const dd = String(d.getDate()).padStart(2, '0')
    const hh = String(d.getHours()).padStart(2, '0')
    const mi = String(d.getMinutes()).padStart(2, '0')
    return `${yyyy}-${mm}-${dd} ${hh}:${mi}`
  } catch {
    return String(time)
  }
}

function statusClass(status) {
  if (!status) return ''
  const s = String(status)
  if (s.includes('成功') || s.includes('完成')) return 'success'
  if (s.includes('退款') || s.includes('关闭')) return 'danger'
  if (s.includes('发货') || s.includes('进行')) return 'warning'
  return 'info'
}

function rateLevelClass(level) {
  // 注意：列表响应中的 rate=-1 不能直接认定为差评（需求第十七节）
  // 这里仅做展示标记，不作语义判定
  if (level === null || level === undefined) return 'unknown'
  const lv = String(level)
  if (lv === '1') return 'good'
  return 'unknown'
}

function onAvatarError(e) {
  e.target.style.display = 'none'
}

function onItemImageError(e) {
  e.target.style.display = 'none'
}

function onDialogImageError(e) {
  e.target.style.display = 'none'
}

// ============================================================
// 轮询与可见性控制（需求第九节）
// ============================================================

const POLL_INTERVAL = 60 * 1000  // 60秒轮询一次

function startPolling() {
  stopPolling()
  pollTimer = setInterval(async () => {
    // 浏览器标签页隐藏时降低或暂停前台轮询
    if (document.hidden) return
    await loadSyncStatus()
    // 同步完成后无闪烁合并更新页面
    if (!syncing.value) {
      await loadList()
      await loadOverview()
    }
  }, POLL_INTERVAL)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function onVisibilityChange() {
  if (!document.hidden) {
    // 页面重新获得焦点时，如果数据已过期，立即触发一次刷新
    loadSyncStatus().then(() => {
      if (cacheExpired.value && !syncing.value && accountsAvailable.value) {
        triggerBackgroundSync()
      }
    })
  }
}

function onFocus() {
  onVisibilityChange()
}

// ============================================================
// 生命周期
// ============================================================

onMounted(async () => {
  await loadAccounts()
  // 缓存优先：立即展示本地数据，不等待网络完成
  await Promise.all([loadList(), loadOverview(), loadSyncStatus()])
  // 启动轮询
  startPolling()
  visibilityHandler = onVisibilityChange
  focusHandler = onFocus
  document.addEventListener('visibilitychange', visibilityHandler)
  window.addEventListener('focus', focusHandler)
})

onBeforeUnmount(() => {
  stopPolling()
  if (visibilityHandler) {
    document.removeEventListener('visibilitychange', visibilityHandler)
  }
  if (focusHandler) {
    window.removeEventListener('focus', focusHandler)
  }
})

// 切换账号时刷新同步状态
watch(() => query.accountId, () => {
  loadSyncStatus()
})
</script>

<style scoped>
.rates-page {
  padding: 20px;
  max-width: 1600px;
  margin: 0 auto;
}

.page-header-bar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  padding: 16px 20px;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.page-title {
  margin: 0 0 6px 0;
  font-size: 20px;
  font-weight: 600;
  color: #1f2937;
}

.page-subtitle {
  margin: 0;
  font-size: 13px;
  color: #6b7280;
}

.page-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.sync-status {
  font-size: 13px;
}

.sync-badge {
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
}

.sync-badge.syncing {
  background: #fef3c7;
  color: #92400e;
}

.sync-badge.done {
  background: #ecfdf5;
  color: #065f46;
}

.sync-badge.none {
  background: #f3f4f6;
  color: #6b7280;
}

.btn-refresh .refresh-icon {
  margin-right: 4px;
}

.global-notice {
  padding: 10px 14px;
  border-radius: 8px;
  margin-bottom: 12px;
  font-size: 14px;
}

.global-notice.error {
  background: #fef2f2;
  color: #991b1b;
  border: 1px solid #fecaca;
}

.global-notice.success {
  background: #f0fdf4;
  color: #166534;
  border: 1px solid #bbf7d0;
}

.global-notice.warn {
  background: #fffbeb;
  color: #92400e;
  border: 1px solid #fde68a;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.stat-icon-circle {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.stat-icon-circle.blue { background: #dbeafe; }
.stat-icon-circle.orange { background: #fed7aa; }
.stat-icon-circle.green { background: #d1fae5; }
.stat-icon-circle.gray { background: #f3f4f6; }

.stat-label {
  font-size: 13px;
  color: #6b7280;
}

.stat-value {
  font-size: 22px;
  font-weight: 600;
  color: #1f2937;
  margin-top: 4px;
}

.stat-value.text-sm {
  font-size: 13px;
  font-weight: 500;
}

.filter-bar {
  padding: 16px 20px;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  margin-bottom: 16px;
}

.filter-title {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 12px;
}

.filter-row {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.filter-select {
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 14px;
  background: #fff;
  min-width: 140px;
  cursor: pointer;
}

.filter-select:disabled {
  background: #f9fafb;
  cursor: not-allowed;
}

.filter-search {
  position: relative;
  flex: 1;
  min-width: 220px;
}

.search-input {
  width: 100%;
  padding: 8px 32px 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 14px;
}

.search-icon {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: #9ca3af;
}

.btn-query,
.btn-reset,
.btn-sync {
  padding: 8px 16px;
}

.filter-tip {
  margin-top: 10px;
  font-size: 12px;
  color: #9ca3af;
}

.loading-state,
.empty-state {
  padding: 60px 20px;
  text-align: center;
  background: #fff;
  border-radius: 10px;
  color: #6b7280;
}

.spinner {
  width: 36px;
  height: 36px;
  border: 3px solid #e5e7eb;
  border-top-color: #3b82f6;
  border-radius: 50%;
  margin: 0 auto 12px;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.empty-text {
  margin-bottom: 16px;
  font-size: 14px;
}

.rates-table-wrap {
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  overflow-x: auto;
}

.rates-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.rates-table th {
  padding: 12px 10px;
  text-align: left;
  font-weight: 600;
  color: #374151;
  background: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
  white-space: nowrap;
}

.rates-table td {
  padding: 12px 10px;
  border-bottom: 1px solid #f3f4f6;
  vertical-align: middle;
}

.rates-table tr:hover td {
  background: #f9fafb;
}

.col-account { min-width: 120px; }
.col-buyer { min-width: 140px; }
.col-item { min-width: 200px; }
.col-order { min-width: 140px; }
.col-status { min-width: 100px; }
.col-finish { min-width: 130px; }
.col-buyer-rate { min-width: 180px; }
.col-seller-rate { min-width: 180px; }
.col-rate-status { min-width: 90px; }
.col-action { min-width: 90px; }

.account-name {
  font-weight: 500;
  color: #1f2937;
}

.buyer-cell,
.item-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.buyer-avatar,
.item-pic {
  width: 36px;
  height: 36px;
  border-radius: 6px;
  object-fit: cover;
  flex-shrink: 0;
}

.buyer-avatar.placeholder,
.item-pic.placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f3f4f6;
  font-size: 18px;
}

.buyer-nick {
  color: #374151;
  font-size: 13px;
}

.item-info {
  flex: 1;
  min-width: 0;
}

.item-title {
  font-size: 13px;
  color: #1f2937;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 160px;
}

.item-id {
  font-size: 11px;
  color: #9ca3af;
  margin-top: 2px;
}

.order-id {
  font-family: monospace;
  font-size: 12px;
  color: #4b5563;
}

.status-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.status-tag.success { background: #d1fae5; color: #065f46; }
.status-tag.danger { background: #fee2e2; color: #991b1b; }
.status-tag.warning { background: #fef3c7; color: #92400e; }
.status-tag.info { background: #dbeafe; color: #1e40af; }

.rate-content {
  font-size: 12px;
}

.rate-level-row {
  margin-bottom: 4px;
}

.rate-level {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 11px;
  background: #f3f4f6;
  color: #6b7280;
}

.rate-level.good { background: #d1fae5; color: #065f46; }
.rate-level.seller { background: #dbeafe; color: #1e40af; }

.rate-text {
  color: #374151;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 160px;
}

.rate-time {
  font-size: 11px;
  color: #9ca3af;
}

.text-muted {
  color: #9ca3af;
}

.text-sm {
  font-size: 12px;
}

.rate-status-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.rate-status-tag.done { background: #d1fae5; color: #065f46; }
.rate-status-tag.pending { background: #fef3c7; color: #92400e; }
.rate-status-tag.unavailable { background: #f3f4f6; color: #9ca3af; }

.pagination-wrap {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}

/* 评价弹窗 */
.rate-dialog-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.rate-dialog {
  background: #fff;
  border-radius: 12px;
  width: 90%;
  max-width: 560px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #e5e7eb;
}

.dialog-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.dialog-close {
  border: none;
  background: none;
  font-size: 24px;
  color: #9ca3af;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}

.dialog-body {
  padding: 20px;
  overflow-y: auto;
  flex: 1;
}

.dialog-order-info {
  background: #f9fafb;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 20px;
}

.dialog-info-row {
  display: flex;
  margin-bottom: 8px;
  font-size: 13px;
}

.dialog-info-row:last-child {
  margin-bottom: 0;
}

.info-label {
  color: #6b7280;
  width: 80px;
  flex-shrink: 0;
}

.info-value {
  color: #1f2937;
  flex: 1;
  word-break: break-all;
}

.dialog-item-pic {
  width: 60px;
  height: 60px;
  border-radius: 6px;
  object-fit: cover;
}

.dialog-section {
  margin-bottom: 20px;
}

.section-label {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 10px;
}

.required {
  color: #ef4444;
}

.rate-level-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.rate-level-card {
  border: 2px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
}

.rate-level-card:hover {
  border-color: #93c5fd;
}

.rate-level-card.selected {
  border-color: #3b82f6;
  background: #eff6ff;
}

.rate-level-card.disabled {
  opacity: 0.6;
}

.rate-level-icon {
  font-size: 24px;
  margin-bottom: 4px;
}

.rate-level-name {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
}

.rate-level-desc {
  font-size: 11px;
  color: #9ca3af;
  margin-top: 2px;
}

.rate-level-warning {
  margin-top: 8px;
  padding: 8px 10px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 6px;
  font-size: 12px;
  color: #92400e;
}

.anonymous-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.anonymous-toggle input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.toggle-text {
  font-size: 13px;
  color: #374151;
}

.feedback-input {
  width: 100%;
  padding: 10px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 14px;
  font-family: inherit;
  resize: vertical;
  box-sizing: border-box;
}

.feedback-input:focus {
  outline: none;
  border-color: #3b82f6;
}

.feedback-count {
  text-align: right;
  font-size: 12px;
  color: #9ca3af;
  margin-top: 4px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 20px;
  border-top: 1px solid #e5e7eb;
}

.dialog-error {
  padding: 10px 20px;
  background: #fef2f2;
  color: #991b1b;
  font-size: 13px;
  border-top: 1px solid #fecaca;
}

@media (max-width: 768px) {
  .rates-page {
    padding: 12px;
  }
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .filter-row {
    flex-direction: column;
    align-items: stretch;
  }
  .filter-select,
  .filter-search {
    width: 100%;
  }
  .rate-level-cards {
    grid-template-columns: 1fr;
  }
}
</style>
