<template>
  <div class="m-accounts">
    <div v-if="!noticeDismissed" class="m-notice">
      <MIcon name="speaker" :size="16" />
      <span>账号状态正常为上线，建议每天手动或自动刷新资料保持账号活跃。</span>
      <button class="m-notice-close" @click="dismissNotice">
        <MIcon name="close" :size="14" />
      </button>
    </div>

    <div class="m-stats-card">
      <div class="m-stat-item" @click="applyQuickFilter('normal')" :class="{ 'm-stat-active': activeQuickFilter === 'normal' }">
        <div class="m-stat-icon m-stat-icon-blue">
          <MIcon name="users" :size="18" />
        </div>
        <div class="m-stat-val">{{ metricText(summary.total) }}</div>
        <div class="m-stat-label">账号总数</div>
      </div>
      <div class="m-stat-divider"></div>
      <div class="m-stat-item" @click="applyQuickFilter('normal')" :class="{ 'm-stat-active': activeQuickFilter === 'normal' }">
        <div class="m-stat-icon m-stat-icon-green">
          <MIcon name="shieldCheck" :size="18" />
        </div>
        <div class="m-stat-val">{{ metricText(summary.normal) }}</div>
        <div class="m-stat-label">正常账号</div>
      </div>
      <div class="m-stat-divider"></div>
      <div class="m-stat-item" @click="applyQuickFilter('needVerify')" :class="{ 'm-stat-active': activeQuickFilter === 'needVerify' }">
        <div class="m-stat-icon m-stat-icon-orange">
          <MIcon name="shieldAlert" :size="18" />
        </div>
        <div class="m-stat-val">{{ metricText(summary.needVerify) }}</div>
        <div class="m-stat-label">需验证</div>
      </div>
      <div class="m-stat-divider"></div>
      <div class="m-stat-item" @click="applyQuickFilter('wsOnline')" :class="{ 'm-stat-active': activeQuickFilter === 'wsOnline' }">
        <div class="m-stat-icon m-stat-icon-purple">
          <MIcon name="wifi" :size="18" />
        </div>
        <div class="m-stat-val">{{ metricText(summary.wsOnline) }}</div>
        <div class="m-stat-label">WS在线</div>
      </div>
      <div class="m-stat-divider"></div>
      <div class="m-stat-item" @click="applyQuickFilter('cookieError')" :class="{ 'm-stat-active': activeQuickFilter === 'cookieError' }">
        <div class="m-stat-icon m-stat-icon-pink">
          <MIcon name="xCircle" :size="18" />
        </div>
        <div class="m-stat-val">{{ metricText(summary.cookieError) }}</div>
        <div class="m-stat-label">Cookie异常</div>
      </div>
    </div>

    <div class="m-search-bar">
      <div class="m-search-input-wrap">
        <MIcon name="search" :size="16" class="m-search-icon" />
        <input
          v-model="searchKeyword"
          type="text"
          class="m-search-input"
          placeholder="搜索昵称 / UID / 备注"
          @input="debouncedSearch"
          @keyup.enter="doSearch"
        />
        <button v-if="searchKeyword" class="m-search-clear" @click="clearSearch">
          <MIcon name="x" :size="14" />
        </button>
      </div>
      <button class="m-filter-btn" @click="showFilterSheet = true">
        <MIcon name="filter" :size="16" />
        <span>筛选</span>
      </button>
    </div>

    <div class="m-quick-filters">
      <button class="m-quick-filter" :class="{ 'm-quick-filter-active': !statusFilter && !wsFilter && !cookieFilter }" @click="clearAllFilters">
        <span>全部状态</span>
        <MIcon name="chevronDown" :size="12" />
      </button>
      <button class="m-quick-filter" :class="{ 'm-quick-filter-active': wsFilter }" @click="cycleWsFilter">
        <span>WS状态</span>
        <MIcon name="chevronDown" :size="12" />
      </button>
      <button class="m-quick-filter" :class="{ 'm-quick-filter-active': cookieFilter }" @click="cycleCookieFilter">
        <span>Cookie状态</span>
        <MIcon name="chevronDown" :size="12" />
      </button>
      <button class="m-quick-filter" :class="{ 'm-quick-filter-active': sortBy !== 'latest' }" @click="cycleSort">
        <span>{{ sortLabels[sortBy] || '最新' }}</span>
        <MIcon name="chevronDown" :size="12" />
      </button>
    </div>

    <div v-if="loading && accounts.length === 0" class="m-skeleton-list">
      <div v-for="i in 3" :key="i" class="m-acc-card m-skeleton-card">
        <div class="m-skeleton-avatar"></div>
        <div class="m-skeleton-body">
          <div class="m-skeleton-line m-skeleton-line-lg"></div>
          <div class="m-skeleton-line m-skeleton-line-sm"></div>
          <div class="m-skeleton-tags">
            <div class="m-skeleton-tag"></div>
            <div class="m-skeleton-tag"></div>
          </div>
        </div>
      </div>
    </div>

    <MobileUnavailableState v-else-if="loadError && accounts.length === 0" title="账号数据加载失败" :description="loadError" @retry="reload" />

    <div v-else-if="accounts.length === 0 && !loading" class="m-empty-state">
      <div class="m-empty-icon">
        <MIcon :name="hasActiveFilters ? 'search' : 'userPlus'" :size="48" />
      </div>
      <div class="m-empty-text">{{ hasActiveFilters ? '没有符合当前条件的账号' : '暂无闲鱼账号' }}</div>
      <div class="m-empty-desc">{{ hasActiveFilters ? '请尝试调整筛选条件' : '点击右上角添加账号开始使用' }}</div>
      <button v-if="hasActiveFilters" class="m-empty-btn" @click="clearAllFilters">清除筛选</button>
    </div>

    <div v-else class="m-acc-list">
      <div v-for="acc in accounts" :key="acc.id" class="m-acc-card" @click="openDetail(acc)">
        <div class="m-acc-header">
          <div class="m-acc-avatar">
            <img
              v-if="avatarUrlOf(acc)"
              :src="avatarUrlOf(acc)"
              :alt="accountName(acc)"
              class="m-acc-avatar-img"
              @error="onAvatarError($event, acc)"
            />
            <div v-else class="m-acc-avatar-placeholder">
              <MIcon name="user" :size="26" />
            </div>
          </div>
          <div class="m-acc-info">
            <div class="m-acc-name-row">
              <span class="m-acc-name">{{ accountName(acc) }}</span>
              <span v-if="isCurrentAccount(acc)" class="m-acc-current-tag">当前账号</span>
            </div>
            <div class="m-acc-uid-row">
              <span class="m-acc-uid">UID：{{ displayUid(acc) }}</span>
              <button class="m-uid-copy" @click.stop="copyUid(acc)">
                <MIcon name="copy" :size="12" />
              </button>
            </div>
          </div>
          <span class="m-acc-status-badge" :class="accountStatusClass(acc)">
            {{ accountStatusText(acc) }}
          </span>
        </div>

        <div class="m-acc-connection">
          <div class="m-acc-conn-item">
            <span class="m-acc-conn-label">WS状态</span>
            <span class="m-acc-conn-val" :class="wsStatusClass(acc)">
              <span class="m-conn-dot" :class="wsDotClass(acc)"></span>
              {{ wsStatusText(acc) }}
            </span>
          </div>
          <div class="m-acc-conn-divider"></div>
          <div class="m-acc-conn-item">
            <span class="m-acc-conn-label">Cookie状态</span>
            <span class="m-acc-conn-val" :class="cookieStatusClass(acc)">
              <span class="m-conn-dot" :class="cookieDotClass(acc)"></span>
              {{ cookieStatusText(acc) }}
            </span>
          </div>
          <div class="m-acc-conn-divider"></div>
          <div class="m-acc-conn-item">
            <span class="m-acc-conn-label">更新时间</span>
            <span class="m-acc-conn-val m-acc-conn-time">{{ formatTime(acc.lastSyncTime || acc.updatedAt || acc.createdAt) }}</span>
          </div>
        </div>

        <div class="m-acc-actions" @click.stop>
          <button class="m-acc-action" @click="openDetail(acc)">
            <MIcon name="eye" :size="16" />
            <span>查看详情</span>
          </button>
          <div class="m-acc-action-divider"></div>
          <button class="m-acc-action" :class="{ 'm-acc-action-loading': refreshingIds[acc.id] }" :disabled="refreshingIds[acc.id]" @click="refreshProfile(acc)">
            <MIcon name="refresh" :size="16" :class="{ 'm-icon-spin': refreshingIds[acc.id] }" />
            <span>{{ refreshingIds[acc.id] ? '刷新中' : '刷新资料' }}</span>
          </button>
          <div class="m-acc-action-divider"></div>
          <button class="m-acc-action" @click="startQrLoginForAccount(acc)">
            <MIcon name="scanQr" :size="16" />
            <span>重新扫码</span>
          </button>
        </div>
      </div>

      <div v-if="loadingMore" class="m-load-more">加载中...</div>
      <div v-else-if="hasMore" class="m-load-more-btn" @click="loadMore">加载更多</div>
      <div v-else-if="accounts.length > 0" class="m-no-more">没有更多账号</div>
    </div>

    <div class="m-safe-bottom"></div>

    <div v-if="showFilterSheet" class="m-sheet-overlay" @click="showFilterSheet = false">
      <div class="m-filter-sheet" @click.stop>
        <div class="m-sheet-header">
          <h3>筛选条件</h3>
          <button class="m-sheet-close" @click="showFilterSheet = false">
            <MIcon name="x" :size="20" />
          </button>
        </div>
        <div class="m-sheet-content">
          <div class="m-filter-group">
            <div class="m-filter-label">账号状态</div>
            <div class="m-filter-options">
              <button
                v-for="opt in statusOptions"
                :key="opt.value"
                class="m-filter-opt"
                :class="{ 'm-filter-opt-active': tempStatusFilter === opt.value }"
                @click="tempStatusFilter = opt.value"
              >{{ opt.label }}</button>
            </div>
          </div>
          <div class="m-filter-group">
            <div class="m-filter-label">WebSocket状态</div>
            <div class="m-filter-options">
              <button
                v-for="opt in wsOptions"
                :key="opt.value"
                class="m-filter-opt"
                :class="{ 'm-filter-opt-active': tempWsFilter === opt.value }"
                @click="tempWsFilter = opt.value"
              >{{ opt.label }}</button>
            </div>
          </div>
          <div class="m-filter-group">
            <div class="m-filter-label">Cookie状态</div>
            <div class="m-filter-options">
              <button
                v-for="opt in cookieOptions"
                :key="opt.value"
                class="m-filter-opt"
                :class="{ 'm-filter-opt-active': tempCookieFilter === opt.value }"
                @click="tempCookieFilter = opt.value"
              >{{ opt.label }}</button>
            </div>
          </div>
        </div>
        <div class="m-sheet-footer">
          <button class="m-sheet-btn m-sheet-btn-reset" @click="resetTempFilters">重置</button>
          <button class="m-sheet-btn m-sheet-btn-confirm" @click="applyFilters">确定</button>
        </div>
      </div>
    </div>

    <div v-if="showQrModal" class="m-modal-overlay" @click="closeQrModal">
      <div class="m-qr-modal" @click.stop>
        <div class="m-qr-header">
          <h3>{{ qrLoginAccount ? '重新扫码登录' : '添加闲鱼账号' }}</h3>
          <button class="m-qr-close" @click="closeQrModal">
            <MIcon name="x" :size="20" />
          </button>
        </div>
        <div v-if="qrLoading" class="m-qr-loading">
          <div class="m-qr-spinner"></div>
          <p>正在生成二维码...</p>
        </div>
        <div v-else-if="qrError" class="m-qr-error">
          <MIcon name="alertCircle" :size="48" class="m-qr-error-icon" />
          <p>{{ qrError }}</p>
          <button class="m-qr-retry" @click="generateQr">重新生成</button>
        </div>
        <div v-else-if="qrCode" class="m-qr-content">
          <div class="m-qr-code-wrap">
            <img :src="qrCode" alt="扫码登录" class="m-qr-code" />
          </div>
          <p class="m-qr-tip">请使用闲鱼APP扫码登录</p>
          <p class="m-qr-status">{{ qrStatusText }}</p>
        </div>
      </div>
    </div>

    <div v-if="toast.show" class="m-toast" :class="'m-toast-' + toast.type">
      {{ toast.message }}
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import MIcon from './MIcon.vue'
import MobileUnavailableState from './MobileUnavailableState.vue'
import { getAccounts, getAccountSummary, refreshAccountProfile as apiRefreshProfile } from '../api/accounts.js'
import { generateQrLogin, getQrLoginStatus, cleanupQrLogin } from '../api/qrlogin.js'
import { accountCookieLabel, accountCookieStatus, accountWsConnectionState } from '../utils/accountAuth.js'
import { resolveTrustedMediaUrl } from '../utils/safeMediaUrl.js'
import {
  getAccountListState,
  updateAccountListState,
  saveAccountListScrollTop,
  getAccountListScrollTop,
  dismissAccountNotice,
  isAccountNoticeDismissed
} from './mobileAccountState.js'

const emit = defineEmits(['navigate', 'force-desktop', 'back', 'open-detail', 'refresh-list'])

const savedState = getAccountListState()

const accounts = ref([])
const loading = ref(false)
const loadingMore = ref(false)
const loadError = ref('')
const searchKeyword = ref(savedState.keyword || '')
const statusFilter = ref(savedState.statusFilter || '')
const wsFilter = ref(savedState.wsFilter || '')
const cookieFilter = ref(savedState.cookieFilter || '')
const sortBy = ref(savedState.sortBy || 'latest')
const currentPage = ref(savedState.currentPage || 1)
const pageSize = ref(20)
const total = ref(0)
const hasMore = ref(false)
const noticeDismissed = ref(isAccountNoticeDismissed())
const activeQuickFilter = ref('')

const summary = reactive({
  total: null,
  normal: null,
  needVerify: null,
  wsOnline: null,
  cookieError: null
})

const showFilterSheet = ref(false)
const tempStatusFilter = ref('')
const tempWsFilter = ref('')
const tempCookieFilter = ref('')

const showQrModal = ref(false)
const qrLoading = ref(false)
const qrError = ref('')
const qrCode = ref('')
const qrSessionId = ref('')
const qrStatusText = ref('等待扫码...')
const qrLoginAccount = ref(null)
let qrPollTimer = null

const refreshingIds = reactive({})

const toast = reactive({
  show: false,
  message: '',
  type: 'success'
})
let toastTimer = null

const contentRef = ref(null)
let searchTimer = null

const sortLabels = {
  latest: '最新',
  earliest: '最早',
  newest: '最近添加',
  name: '昵称排序'
}

const statusOptions = [
  { value: '', label: '全部' },
  { value: 'normal', label: '正常' },
  { value: 'needVerify', label: '需验证' },
  { value: 'disabled', label: '已停用' },
  { value: 'expired', label: '登录失效' }
]

const wsOptions = [
  { value: '', label: '全部' },
  { value: 'online', label: '在线' },
  { value: 'offline', label: '离线' },
  { value: 'connecting', label: '连接中' }
]

const cookieOptions = [
  { value: '', label: '全部' },
  { value: 'normal', label: '正常' },
  { value: 'warning', label: '即将过期' },
  { value: 'error', label: '已过期' }
]

const hasActiveFilters = computed(() => {
  return searchKeyword.value || statusFilter.value || wsFilter.value || cookieFilter.value || sortBy.value !== 'latest'
})

function showToast(message, type = 'success') {
  toast.message = message
  toast.type = type
  toast.show = true
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toast.show = false
  }, 2500)
}

function metricText(value) {
  return value === null || value === undefined ? '—' : value
}

function accountName(acc) {
  if (!acc) return '未知账号'
  return acc.name || acc.nickname || acc.displayName || acc.accountNote || `账号${acc.id || ''}`
}

function displayUid(acc) {
  if (!acc) return '-'
  return acc.uid || acc.externalUid || acc.unb || '-'
}

function isCurrentAccount(acc) {
  return acc?.isCurrent === true || acc?.isDefault === true
}

function accountStatusText(acc) {
  if (!acc) return '未知'
  if (acc.disabled) return '已停用'
  const cs = accountCookieStatus(acc)
  if (cs === 0) return '登录失效'
  if (acc.needVerify || acc.needFaceVerify) return '需验证'
  const ws = accountWsConnectionState(acc)
  if (ws === true && (cs === 1 || cs === 2)) return '正常'
  if (cs === 2) return '需验证'
  return '正常'
}

function accountStatusClass(acc) {
  if (!acc) return 'm-status-unknown'
  if (acc.disabled) return 'm-status-gray'
  const cs = accountCookieStatus(acc)
  if (cs === 0) return 'm-status-red'
  if (acc.needVerify || acc.needFaceVerify || cs === 2) return 'm-status-orange'
  return 'm-status-green'
}

function cookieStatusText(acc) {
  if (!acc) return '未知'
  return accountCookieLabel(acc)
}

function cookieStatusClass(acc) {
  if (!acc) return 'm-conn-unknown'
  const cs = accountCookieStatus(acc)
  if (cs === null) return 'm-conn-unknown'
  if (cs === 0) return 'm-conn-red'
  if (cs === 2) return 'm-conn-orange'
  return 'm-conn-green'
}

function cookieDotClass(acc) {
  return cookieStatusClass(acc).replace('m-conn-', 'm-dot-')
}

function wsStatusText(acc) {
  const state = accountWsConnectionState(acc)
  if (state === true) return '在线'
  if (state === false) return '离线'
  if (state === 'connecting') return '连接中'
  return '未知'
}

function wsStatusClass(acc) {
  const state = accountWsConnectionState(acc)
  if (state === true) return 'm-conn-green'
  if (state === false) return 'm-conn-gray'
  return 'm-conn-unknown'
}

function wsDotClass(acc) {
  return wsStatusClass(acc).replace('m-conn-', 'm-dot-')
}

function formatTime(timeStr) {
  if (!timeStr) return '--'
  try {
    const date = new Date(timeStr)
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hour = String(date.getHours()).padStart(2, '0')
    const minute = String(date.getMinutes()).padStart(2, '0')
    return `${month}-${day} ${hour}:${minute}`
  } catch {
    return '--'
  }
}

function onAvatarError(e, acc) {
  if (acc) {
    acc.avatarUrl = ''
    acc.avatar = ''
  }
}

// 清洗头像 URL：过滤历史脏格式 {avatar=http://...} 及非白名单域名，
// 返回空字符串时模板会切换到占位图标
function avatarUrlOf(acc) {
  if (!acc) return ''
  return resolveTrustedMediaUrl(acc.avatarUrl || acc.avatar || '')
}

function debouncedSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    doSearch()
  }, 300)
}

function doSearch() {
  currentPage.value = 1
  activeQuickFilter.value = ''
  updateAccountListState({
    keyword: searchKeyword.value,
    currentPage: 1
  })
  loadAccounts(true)
}

function clearSearch() {
  searchKeyword.value = ''
  doSearch()
}

function applyQuickFilter(filter) {
  if (activeQuickFilter.value === filter) {
    activeQuickFilter.value = ''
    statusFilter.value = ''
    wsFilter.value = ''
    cookieFilter.value = ''
  } else {
    activeQuickFilter.value = filter
    switch (filter) {
      case 'normal':
        statusFilter.value = 'normal'
        wsFilter.value = ''
        cookieFilter.value = ''
        break
      case 'needVerify':
        statusFilter.value = 'needVerify'
        wsFilter.value = ''
        cookieFilter.value = ''
        break
      case 'wsOnline':
        wsFilter.value = 'online'
        statusFilter.value = ''
        cookieFilter.value = ''
        break
      case 'cookieError':
        cookieFilter.value = 'error'
        statusFilter.value = ''
        wsFilter.value = ''
        break
    }
  }
  currentPage.value = 1
  updateAccountListState({
    statusFilter: statusFilter.value,
    wsFilter: wsFilter.value,
    cookieFilter: cookieFilter.value,
    currentPage: 1
  })
  loadAccounts(true)
}

function cycleWsFilter() {
  const values = ['', 'online', 'offline']
  const idx = values.indexOf(wsFilter.value)
  wsFilter.value = values[(idx + 1) % values.length]
  activeQuickFilter.value = ''
  currentPage.value = 1
  updateAccountListState({ wsFilter: wsFilter.value, currentPage: 1 })
  loadAccounts(true)
}

function cycleCookieFilter() {
  const values = ['', 'normal', 'warning', 'error']
  const idx = values.indexOf(cookieFilter.value)
  cookieFilter.value = values[(idx + 1) % values.length]
  activeQuickFilter.value = ''
  currentPage.value = 1
  updateAccountListState({ cookieFilter: cookieFilter.value, currentPage: 1 })
  loadAccounts(true)
}

function cycleSort() {
  const values = ['latest', 'earliest', 'newest', 'name']
  const idx = values.indexOf(sortBy.value)
  sortBy.value = values[(idx + 1) % values.length]
  currentPage.value = 1
  updateAccountListState({ sortBy: sortBy.value, currentPage: 1 })
  loadAccounts(true)
}

function clearAllFilters() {
  searchKeyword.value = ''
  statusFilter.value = ''
  wsFilter.value = ''
  cookieFilter.value = ''
  sortBy.value = 'latest'
  activeQuickFilter.value = ''
  currentPage.value = 1
  updateAccountListState({
    keyword: '',
    statusFilter: '',
    wsFilter: '',
    cookieFilter: '',
    sortBy: 'latest',
    currentPage: 1
  })
  loadAccounts(true)
}

function openFilterSheet() {
  tempStatusFilter.value = statusFilter.value
  tempWsFilter.value = wsFilter.value
  tempCookieFilter.value = cookieFilter.value
  showFilterSheet.value = true
  document.body.style.overflow = 'hidden'
}

function resetTempFilters() {
  tempStatusFilter.value = ''
  tempWsFilter.value = ''
  tempCookieFilter.value = ''
}

function applyFilters() {
  statusFilter.value = tempStatusFilter.value
  wsFilter.value = tempWsFilter.value
  cookieFilter.value = tempCookieFilter.value
  activeQuickFilter.value = ''
  currentPage.value = 1
  showFilterSheet.value = false
  document.body.style.overflow = ''
  updateAccountListState({
    statusFilter: statusFilter.value,
    wsFilter: wsFilter.value,
    cookieFilter: cookieFilter.value,
    currentPage: 1
  })
  loadAccounts(true)
}

function dismissNotice() {
  noticeDismissed.value = true
  dismissAccountNotice()
}

function copyUid(acc) {
  const uid = displayUid(acc)
  if (uid && uid !== '-') {
    navigator.clipboard.writeText(uid).then(() => {
      showToast('UID已复制', 'success')
    }).catch(() => {
      showToast('复制失败', 'error')
    })
  }
}

function openDetail(acc) {
  updateAccountListState({ scrollTop: window.scrollY })
  emit('open-detail', acc.id)
}

async function refreshProfile(acc) {
  if (refreshingIds[acc.id]) return
  refreshingIds[acc.id] = true
  try {
    await apiRefreshProfile(acc.id)
    showToast('资料刷新成功', 'success')
    await loadAccounts(true)
    emit('refresh-list')
  } catch (error) {
    showToast(error?.message || '刷新失败', 'error')
  } finally {
    delete refreshingIds[acc.id]
  }
}

async function loadSummary() {
  try {
    const res = await getAccountSummary()
    const data = res?.data || res
    summary.total = data?.total ?? data?.totalCount ?? null
    summary.normal = data?.normal ?? data?.online ?? null
    summary.needVerify = data?.needVerify ?? data?.needAuth ?? null
    summary.wsOnline = data?.wsOnline ?? data?.websocketOnline ?? null
    summary.cookieError = data?.cookieError ?? data?.cookieInvalid ?? null
  } catch (e) {
    console.warn('加载账号统计失败', e)
  }
}

async function loadAccounts(reset = false) {
  if (reset) {
    loading.value = true
    loadError.value = ''
  } else {
    loadingMore.value = true
  }

  try {
    const params = {
      current: currentPage.value,
      size: pageSize.value,
      keyword: searchKeyword.value || undefined
    }
    if (statusFilter.value) params.status = statusFilter.value
    if (wsFilter.value) params.wsStatus = wsFilter.value
    if (cookieFilter.value) params.cookieStatus = cookieFilter.value
    if (sortBy.value && sortBy.value !== 'latest') params.sortBy = sortBy.value

    const res = await getAccounts(params)
    const data = res?.data
    let list = []
    if (data?.records) list = data.records
    else if (data?.list) list = data.list
    else if (Array.isArray(data)) list = data

    if (reset) {
      accounts.value = list
    } else {
      accounts.value = [...accounts.value, ...list]
    }

    total.value = Number(data?.total ?? data?.totalCount ?? list.length)
    hasMore.value = accounts.value.length < total.value
    loadError.value = ''
  } catch (error) {
    loadError.value = error?.message || '请检查网络连接后重试。'
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

function loadMore() {
  if (loadingMore.value || !hasMore.value) return
  currentPage.value++
  updateAccountListState({ currentPage: currentPage.value })
  loadAccounts(false)
}

async function reload() {
  currentPage.value = 1
  await Promise.all([loadSummary(), loadAccounts(true)])
}

function startAddAccount() {
  qrLoginAccount.value = null
  generateQr()
}

function startQrLoginForAccount(acc) {
  qrLoginAccount.value = acc
  generateQr()
}

async function generateQr() {
  stopQrPolling()
  showQrModal.value = true
  qrLoading.value = true
  qrError.value = ''
  qrCode.value = ''
  qrStatusText.value = '等待扫码...'
  document.body.style.overflow = 'hidden'

  try {
    const res = await generateQrLogin({
      accountId: qrLoginAccount.value?.id
    })
    const data = res?.data || res
    if (data?.qrCode) {
      qrCode.value = data.qrCode
      qrSessionId.value = data.sessionId || data.token
      qrLoading.value = false
      startQrPolling()
    } else {
      throw new Error('二维码生成失败')
    }
  } catch (error) {
    qrLoading.value = false
    qrError.value = error?.message || '二维码生成失败，请重试'
  }
}

function startQrPolling() {
  if (qrPollTimer) clearInterval(qrPollTimer)
  let pollCount = 0
  qrPollTimer = setInterval(async () => {
    pollCount++
    try {
      const res = await getQrLoginStatus(qrSessionId.value)
      const data = res?.data || res
      const status = data?.status
      if (status === 'scanned') {
        qrStatusText.value = '已扫码，请在手机上确认'
      } else if (status === 'confirmed' || status === 'success') {
        qrStatusText.value = '登录成功！'
        stopQrPolling()
        setTimeout(() => {
          closeQrModal()
          showToast('登录成功', 'success')
          reload()
        }, 1000)
      } else if (status === 'expired' || status === 'timeout') {
        qrError.value = '二维码已过期，请重新生成'
        stopQrPolling()
      } else if (status === 'canceled') {
        qrError.value = '登录已取消'
        stopQrPolling()
      }
    } catch (e) {
      if (pollCount > 30) {
        qrError.value = '二维码已过期，请重新生成'
        stopQrPolling()
      }
    }
  }, 2000)
}

function stopQrPolling() {
  if (qrPollTimer) {
    clearInterval(qrPollTimer)
    qrPollTimer = null
  }
}

function closeQrModal() {
  stopQrPolling()
  try { cleanupQrLogin() } catch {}
  showQrModal.value = false
  qrCode.value = ''
  qrSessionId.value = ''
  qrLoginAccount.value = null
  document.body.style.overflow = ''
}

function restoreScrollPosition() {
  const savedScroll = getAccountListScrollTop()
  if (savedScroll > 0) {
    nextTick(() => {
      window.scrollTo(0, savedScroll)
    })
  }
}

function handleScroll() {
  saveAccountListScrollTop(window.scrollY)
}

onMounted(async () => {
  await Promise.all([loadSummary(), loadAccounts(true)])
  restoreScrollPosition()
  window.addEventListener('scroll', handleScroll, { passive: true })
})

onBeforeUnmount(() => {
  stopQrPolling()
  window.removeEventListener('scroll', handleScroll)
  if (showFilterSheet.value || showQrModal.value) {
    document.body.style.overflow = ''
  }
})

defineExpose({ startAddAccount })
</script>

<style scoped>
.m-accounts {
  padding: 10px 12px 0;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
  background: #f8faff;
}

.m-notice {
  min-height: 38px;
  box-sizing: border-box;
  background: #eaf4ff;
  border: 1px solid #d9eaff;
  border-radius: 8px;
  padding: 8px 10px;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  font-size: 11px;
  color: #2563eb;
  line-height: 1.4;
}
.m-notice :deep(svg) { flex-shrink: 0; margin-top: 1px; }
.m-notice span { flex: 1; }
.m-notice-close {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: none;
  background: rgba(37, 99, 235, 0.1);
  color: #2563eb;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
}

.m-stats-card {
  background: #fff;
  border-radius: 10px;
  padding: 10px 4px;
  display: flex;
  align-items: center;
  box-shadow: 0 3px 12px rgba(31, 53, 94, 0.05);
  border: 1px solid #e8eef7;
  margin-bottom: 10px;
}
.m-stat-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 4px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.2s;
}
.m-stat-item:active {
  background: #f4f7fc;
}
.m-stat-active {
  background: #f0f7ff !important;
}
.m-stat-icon {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.m-stat-icon-blue { background: linear-gradient(135deg, #e8f1ff, #d4e4ff); color: #0d6bff; }
.m-stat-icon-green { background: linear-gradient(135deg, #e2f8ee, #cdf2df); color: #16bf78; }
.m-stat-icon-orange { background: linear-gradient(135deg, #fff4e0, #ffe7c2); color: #ff9f22; }
.m-stat-icon-purple { background: linear-gradient(135deg, #f0ebff, #e3daff); color: #7c3aed; }
.m-stat-icon-pink { background: linear-gradient(135deg, #ffe8f0, #ffd4e3); color: #ec4899; }
.m-stat-val { font-size: 20px; font-weight: 800; color: #15213d; line-height: 1.1; }
.m-stat-label { font-size: 11px; color: #8c98ae; }
.m-stat-divider {
  width: 1px;
  height: 36px;
  background: #f0f4fa;
  flex-shrink: 0;
}

.m-search-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}
.m-search-input-wrap {
  flex: 1;
  position: relative;
  background: white;
  border-radius: 12px;
  border: 1px solid #f0f4fa;
  display: flex;
  align-items: center;
  padding: 0 12px;
  height: 42px;
}
.m-search-icon {
  color: #8c98ae;
  flex-shrink: 0;
  margin-right: 8px;
}
.m-search-input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 14px;
  color: #15213d;
  background: transparent;
  min-width: 0;
}
.m-search-input::placeholder {
  color: #b0bbd0;
}
.m-search-clear {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: none;
  background: #f0f4fa;
  color: #8c98ae;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  padding: 0;
  margin-left: 8px;
}
.m-filter-btn {
  height: 42px;
  padding: 0 14px;
  border-radius: 12px;
  border: 1px solid #e0e8f5;
  background: white;
  color: #475569;
  font-size: 13px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  flex-shrink: 0;
}
.m-filter-btn :deep(svg) { color: #64748b; }

.m-quick-filters {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  overflow-x: auto;
  padding-bottom: 2px;
}
.m-quick-filters::-webkit-scrollbar { display: none; }
.m-quick-filter {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 30px;
  padding: 4px 10px;
  border-radius: 8px;
  border: 1px solid #e5ebf5;
  background: white;
  color: #64748b;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
}
.m-quick-filter-active {
  background: #e8f1ff;
  border-color: #bfdbfe;
  color: #0d6bff;
}

.m-skeleton-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.m-skeleton-card {
  pointer-events: none;
}
.m-skeleton-avatar {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  background: linear-gradient(90deg, #f0f4fa 25%, #e8edf5 50%, #f0f4fa 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  flex-shrink: 0;
}
.m-skeleton-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-left: 12px;
}
.m-skeleton-line {
  height: 14px;
  border-radius: 4px;
  background: linear-gradient(90deg, #f0f4fa 25%, #e8edf5 50%, #f0f4fa 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
.m-skeleton-line-lg { width: 60%; }
.m-skeleton-line-sm { width: 40%; }
.m-skeleton-tags {
  display: flex;
  gap: 6px;
}
.m-skeleton-tag {
  width: 50px;
  height: 20px;
  border-radius: 100px;
  background: linear-gradient(90deg, #f0f4fa 25%, #e8edf5 50%, #f0f4fa 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.m-empty-state {
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
.m-empty-desc { font-size: 13px; color: #8c98ae; margin-bottom: 20px; }
.m-empty-btn {
  padding: 10px 24px;
  border-radius: 100px;
  border: none;
  background: linear-gradient(135deg, #0d6bff, #2580ff);
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.m-acc-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.m-acc-card {
  background: white;
  border-radius: 14px;
  padding: 14px;
  box-shadow: 0 2px 8px rgba(31, 53, 94, 0.05);
  border: 1px solid #f0f4fa;
  cursor: pointer;
  transition: transform 0.15s;
}
.m-acc-card:active {
  transform: scale(0.98);
}
.m-acc-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
}
.m-acc-avatar {
  width: 46px;
  height: 46px;
  border-radius: 50%;
  overflow: hidden;
  flex-shrink: 0;
  background: #f4f7fc;
}
.m-acc-avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.m-acc-avatar-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #e8f1ff, #d4e4ff);
  color: #0d6bff;
}
.m-acc-info {
  flex: 1;
  min-width: 0;
}
.m-acc-name-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}
.m-acc-name {
  font-size: 15px;
  font-weight: 700;
  color: #15213d;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-acc-current-tag {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
  background: #e8f1ff;
  color: #0d6bff;
  flex-shrink: 0;
}
.m-acc-uid-row {
  display: flex;
  align-items: center;
  gap: 4px;
}
.m-acc-uid {
  font-size: 12px;
  color: #8c98ae;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-uid-copy {
  width: 20px;
  height: 20px;
  border-radius: 4px;
  border: none;
  background: transparent;
  color: #8c98ae;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
  flex-shrink: 0;
}
.m-uid-copy:hover {
  background: #f4f7fc;
  color: #0d6bff;
}
.m-acc-status-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 100px;
  flex-shrink: 0;
}
.m-status-green { background: rgba(22, 191, 120, 0.12); color: #16bf78; }
.m-status-orange { background: rgba(255, 159, 34, 0.12); color: #ff9f22; }
.m-status-red { background: rgba(255, 82, 82, 0.12); color: #ff5252; }
.m-status-gray { background: rgba(140, 152, 174, 0.15); color: #8c98ae; }
.m-status-unknown { background: rgba(140, 152, 174, 0.15); color: #64748b; }

.m-acc-connection {
  display: flex;
  align-items: center;
  background: transparent;
  border-top: 1px solid #eef2f7;
  border-bottom: 1px solid #eef2f7;
  border-radius: 0;
  padding: 8px 0;
  margin-bottom: 8px;
}
.m-acc-conn-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}
.m-acc-conn-label {
  font-size: 11px;
  color: #8c98ae;
}
.m-acc-conn-val {
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 4px;
}
.m-acc-conn-time { color: #64748b; font-weight: 500; }
.m-conn-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.m-dot-green { background: #16bf78; }
.m-dot-red { background: #ff5252; }
.m-dot-orange { background: #ff9f22; }
.m-dot-gray { background: #8c98ae; }
.m-dot-unknown { background: #b0bbd0; }
.m-conn-green { color: #16bf78; }
.m-conn-red { color: #ff5252; }
.m-conn-orange { color: #ff9f22; }
.m-conn-gray { color: #8c98ae; }
.m-conn-unknown { color: #64748b; }
.m-acc-conn-divider {
  width: 1px;
  height: 24px;
  background: #e5ebf5;
  flex-shrink: 0;
}

.m-acc-actions {
  display: flex;
  align-items: center;
  border-top: 0;
  padding-top: 6px;
  margin-top: 0;
}
.m-acc-action {
  flex: 1;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  min-height: 30px;
  gap: 4px;
  border: none;
  background: transparent;
  color: #1677ff;
  font-size: 11px;
  cursor: pointer;
  padding: 4px;
  border-radius: 8px;
}
.m-acc-action:active {
  background: #f4f7fc;
}
.m-acc-action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.m-acc-action-loading {
  pointer-events: none;
}
.m-acc-action-divider {
  width: 1px;
  height: 24px;
  background: #f0f4fa;
  flex-shrink: 0;
}
.m-icon-spin {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.m-load-more, .m-no-more {
  text-align: center;
  padding: 16px;
  font-size: 12px;
  color: #8c98ae;
}
.m-load-more-btn {
  text-align: center;
  padding: 12px;
  font-size: 13px;
  color: #0d6bff;
  font-weight: 500;
  cursor: pointer;
}

.m-safe-bottom { height: 100px; }

.m-sheet-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 1000;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.m-filter-sheet {
  background: white;
  border-radius: 20px 20px 0 0;
  width: 100%;
  max-width: 500px;
  max-height: 70vh;
  display: flex;
  flex-direction: column;
  animation: slideUp 0.3s ease;
}
@keyframes slideUp {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}
.m-sheet-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid #f0f4fa;
}
.m-sheet-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #15213d;
}
.m-sheet-close {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: none;
  background: #f4f7fc;
  color: #64748b;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
}
.m-sheet-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}
.m-filter-group {
  margin-bottom: 20px;
}
.m-filter-label {
  font-size: 13px;
  font-weight: 600;
  color: #15213d;
  margin-bottom: 10px;
}
.m-filter-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.m-filter-opt {
  padding: 8px 16px;
  border-radius: 100px;
  border: 1px solid #e5ebf5;
  background: white;
  color: #64748b;
  font-size: 13px;
  cursor: pointer;
}
.m-filter-opt-active {
  background: #e8f1ff;
  border-color: #bfdbfe;
  color: #0d6bff;
}
.m-sheet-footer {
  display: flex;
  gap: 12px;
  padding: 16px;
  border-top: 1px solid #f0f4fa;
  padding-bottom: calc(16px + env(safe-area-inset-bottom, 0px));
}
.m-sheet-btn {
  flex: 1;
  height: 44px;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  border: none;
}
.m-sheet-btn-reset {
  background: #f4f7fc;
  color: #64748b;
}
.m-sheet-btn-confirm {
  background: linear-gradient(135deg, #0d6bff, #2580ff);
  color: white;
}

.m-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  z-index: 1100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}
.m-qr-modal {
  background: white;
  border-radius: 20px;
  width: 100%;
  max-width: 320px;
  overflow: hidden;
  animation: fadeIn 0.2s ease;
}
@keyframes fadeIn {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}
.m-qr-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid #f0f4fa;
}
.m-qr-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #15213d;
}
.m-qr-close {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: none;
  background: #f4f7fc;
  color: #64748b;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
}
.m-qr-loading, .m-qr-error {
  padding: 40px 20px;
  text-align: center;
}
.m-qr-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #e5ebf5;
  border-top-color: #0d6bff;
  border-radius: 50%;
  margin: 0 auto 16px;
  animation: spin 1s linear infinite;
}
.m-qr-error-icon {
  color: #ff9f22;
  margin-bottom: 12px;
}
.m-qr-loading p, .m-qr-error p {
  margin: 0;
  font-size: 14px;
  color: #64748b;
}
.m-qr-retry {
  margin-top: 16px;
  padding: 10px 24px;
  border-radius: 100px;
  border: none;
  background: linear-gradient(135deg, #0d6bff, #2580ff);
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}
.m-qr-content {
  padding: 20px;
  text-align: center;
}
.m-qr-code-wrap {
  width: 200px;
  height: 200px;
  margin: 0 auto 16px;
  padding: 12px;
  background: white;
  border: 2px solid #f0f4fa;
  border-radius: 12px;
}
.m-qr-code {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.m-qr-tip {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
  color: #15213d;
}
.m-qr-status {
  margin: 0;
  font-size: 12px;
  color: #8c98ae;
}

.m-toast {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  padding: 12px 24px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 500;
  z-index: 2000;
  animation: toastIn 0.2s ease;
}
@keyframes toastIn {
  from { opacity: 0; transform: translate(-50%, -50%) scale(0.9); }
  to { opacity: 1; transform: translate(-50%, -50%) scale(1); }
}
.m-toast-success {
  background: rgba(22, 191, 120, 0.95);
  color: white;
}
.m-toast-error {
  background: rgba(255, 82, 82, 0.95);
  color: white;
}

@media (max-width: 380px) {
  .m-stat-val { font-size: 17px; }
  .m-stat-label { font-size: 10px; }
  .m-stat-icon { width: 32px; height: 32px; }
  .m-acc-actions { font-size: 11px; }
  .m-filter-btn span { display: none; }
  .m-filter-btn { padding: 0 12px; }
}
</style>
