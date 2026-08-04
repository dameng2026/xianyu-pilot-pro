<template>
  <div class="m-accounts">
    <div v-if="!noticeDismissed" class="m-notice">
      <MIcon name="speaker" :size="16" />
      <span>账号状态正常为上线，建议每天手动或自动刷新资料保持账号活跃。</span>
      <button class="m-notice-close" @click="dismissNotice">
        <MIcon name="close" :size="14" />
      </button>
    </div>

    <div class="m-action-bar">
      <button class="m-action-btn m-action-primary" @click="onAddAccountClick">
        <MIcon name="userPlus" :size="16" />
        <span>添加账号</span>
      </button>
      <button
        class="m-action-btn m-action-secondary"
        :class="{ 'm-action-active': batchMode }"
        :disabled="accounts.length === 0 || batchBusy"
        @click="toggleBatchMode"
      >
        <MIcon name="checkCircle" :size="16" />
        <span>{{ batchMode ? '退出批量' : '批量操作' }}</span>
      </button>
    </div>

    <div v-if="batchMode" class="m-batch-info">
      <span v-if="batchBusy">{{ batchProgressText }}</span>
      <span v-else>已选 {{ selectedIds.length }} / {{ accounts.length }} 个账号</span>
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
      <div
        v-for="acc in accounts"
        :key="acc.id"
        class="m-acc-card"
        :class="{ 'm-acc-card-batch': batchMode, 'm-acc-card-selected': batchMode && selectedIds.includes(acc.id) }"
        @click="onCardClick(acc)"
      >
        <div v-if="batchMode" class="m-acc-checkbox" :class="{ 'm-acc-checkbox-checked': selectedIds.includes(acc.id) }" @click.stop="toggleSelect(acc.id)">
          <MIcon v-if="selectedIds.includes(acc.id)" name="check" :size="14" />
        </div>
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

        <div v-if="cookieExpireText(acc)" class="m-acc-cookie-warn" :class="cookieExpireClass(acc)">
          <MIcon name="alertCircle" :size="14" />
          <span>{{ cookieExpireText(acc) }}</span>
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

        <div v-if="!batchMode" class="m-acc-actions" @click.stop>
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

    <div class="m-safe-bottom" :class="{ 'm-safe-bottom-batch': batchMode }"></div>

    <div v-if="batchMode" class="m-batch-toolbar">
      <button class="m-batch-btn m-batch-btn-select" :disabled="batchBusy" @click="toggleSelectAll">
        <MIcon :name="allSelected ? 'checkCircle' : 'circle'" :size="18" />
        <span>{{ allSelected ? '取消全选' : '全选' }}</span>
      </button>
      <div class="m-batch-actions">
        <button class="m-batch-btn m-batch-btn-enable" :disabled="batchBusy || selectedIds.length === 0" @click="batchUpdate(false)">
          <MIcon name="power" :size="16" />
          <span>启用</span>
        </button>
        <button class="m-batch-btn m-batch-btn-disable" :disabled="batchBusy || selectedIds.length === 0" @click="batchUpdate(true)">
          <MIcon name="stop" :size="16" />
          <span>停用</span>
        </button>
        <button class="m-batch-btn m-batch-btn-delete" :disabled="batchBusy || selectedIds.length === 0" @click="batchDelete">
          <MIcon name="trash" :size="16" />
          <span>删除</span>
        </button>
      </div>
      <button class="m-batch-btn m-batch-btn-cancel" :disabled="batchBusy" @click="exitBatchMode">
        <MIcon name="x" :size="16" />
        <span>取消</span>
      </button>
    </div>

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

    <div v-if="showAddSheet" class="m-sheet-overlay" @click="closeAddSheet">
      <div class="m-add-sheet" @click.stop>
        <div class="m-sheet-header">
          <h3>添加闲鱼账号</h3>
          <button class="m-sheet-close" @click="closeAddSheet">
            <MIcon name="x" :size="20" />
          </button>
        </div>
        <div class="m-add-sheet-content">
          <button class="m-add-option" @click="chooseQrLogin">
            <div class="m-add-option-icon m-add-option-icon-qr">
              <MIcon name="scanQr" :size="24" />
            </div>
            <div class="m-add-option-info">
              <div class="m-add-option-name">扫码登录</div>
              <div class="m-add-option-desc">使用闲鱼APP扫码，推荐方式</div>
            </div>
            <MIcon name="chevronRight" :size="18" class="m-add-option-arrow" />
          </button>
          <button class="m-add-option" @click="openManualModal">
            <div class="m-add-option-icon m-add-option-icon-cookie">
              <MIcon name="cookie" :size="24" />
            </div>
            <div class="m-add-option-info">
              <div class="m-add-option-name">手动 Cookie 添加</div>
              <div class="m-add-option-desc">从浏览器复制 Cookie 粘贴</div>
            </div>
            <MIcon name="chevronRight" :size="18" class="m-add-option-arrow" />
          </button>
        </div>
      </div>
    </div>

    <div v-if="showManualModal" class="m-modal-overlay" @click="closeManualModal">
      <div class="m-manual-modal" @click.stop>
        <div class="m-qr-header">
          <h3>手动 Cookie 添加</h3>
          <button class="m-qr-close" @click="closeManualModal">
            <MIcon name="x" :size="20" />
          </button>
        </div>
        <div class="m-manual-body">
          <p class="m-cookie-tip">
            <MIcon name="info" :size="14" />
            <span>请粘贴从闲鱼页面复制的完整 Cookie，须包含 <code>unb</code> 字段</span>
          </p>
          <div class="m-form-row">
            <label class="m-form-label">Cookie 内容</label>
            <textarea
              v-model="manual.cookie"
              class="m-form-textarea"
              placeholder="cookie_unb=xxx; _m_h5_tk=xxx; ..."
              rows="5"
              :disabled="submitting"
            ></textarea>
          </div>
          <div v-if="manualError" class="m-form-error">
            <MIcon name="alertCircle" :size="14" />
            <span>{{ manualError }}</span>
          </div>
          <div v-else-if="manualWarning" class="m-form-warning">
            <MIcon name="alertTriangle" :size="14" />
            <span>{{ manualWarning }}</span>
          </div>
          <div v-if="manualParsed" class="m-form-parsed">
            <div class="m-parsed-row">
              <span class="m-parsed-label">解析身份（unb）</span>
              <span class="m-parsed-val">{{ manualParsed.unb }}</span>
            </div>
            <div class="m-parsed-row">
              <span class="m-parsed-label">签名 Token（_m_h5_tk）</span>
              <span class="m-parsed-val">{{ manualParsed.mH5Tk }}</span>
            </div>
            <div class="m-parsed-row">
              <span class="m-parsed-label">字段总数</span>
              <span class="m-parsed-val">{{ manualParsed.parsedCount }}</span>
            </div>
          </div>
          <div class="m-form-row">
            <label class="m-form-label">账号备注（可选）</label>
            <input
              v-model="manual.accountNote"
              type="text"
              class="m-form-input"
              placeholder="例如：备用账号A"
              maxlength="50"
              :disabled="submitting"
            />
          </div>
        </div>
        <div class="m-manual-footer">
          <button class="m-sheet-btn m-sheet-btn-reset" :disabled="submitting" @click="closeManualModal">取消</button>
          <button class="m-sheet-btn m-sheet-btn-confirm" :disabled="submitting || !manual.cookie" @click="submitManualCookie">
            {{ submitting ? '提交中...' : '添加账号' }}
          </button>
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
import { getAccounts, getAccountSummary, refreshAccountProfile as apiRefreshProfile, createAccountByCookie, updateAccount, deleteAccount } from '../api/accounts.js'
import { generateQrLogin, getQrLoginStatus, cleanupQrLogin } from '../api/qrlogin.js'
import { getStoreLimitStatus } from '../api/feature-switch.js'
import { accountCookieLabel, accountCookieStatus, accountWsConnectionState } from '../utils/accountAuth.js'
import { validateCookie, extractKeyFields, maskKeyFields } from '../utils/cookie.js'
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

// 批量操作相关
const batchMode = ref(false)
const selectedIds = ref([])
const batchBusy = ref(false)
const batchProgressText = ref('')

// 添加账号相关
const showAddSheet = ref(false)
const showManualModal = ref(false)
const manual = reactive({
  cookie: '',
  accountNote: ''
})
const manualError = ref('')
const manualWarning = ref('')
const submitting = ref(false)

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

const allSelected = computed(() => {
  return accounts.value.length > 0 && selectedIds.value.length === accounts.value.length
})

const manualParsed = computed(() => {
  if (!manual.cookie || manual.cookie.trim().length < 10) return null
  const result = validateCookie(manual.cookie)
  if (!result.valid) return null
  const fields = extractKeyFields(manual.cookie)
  const masked = maskKeyFields(fields)
  return {
    unb: masked.unb,
    mH5Tk: masked.mH5Tk,
    parsedCount: masked.parsedCount
  }
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

// ===== 批量操作 =====
function toggleBatchMode() {
  if (batchMode.value) {
    exitBatchMode()
  } else {
    batchMode.value = true
    selectedIds.value = []
  }
}

function exitBatchMode() {
  batchMode.value = false
  selectedIds.value = []
  batchBusy.value = false
  batchProgressText.value = ''
}

function toggleSelect(id) {
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) {
    selectedIds.value.splice(idx, 1)
  } else {
    selectedIds.value.push(id)
  }
}

function toggleSelectAll() {
  if (allSelected.value) {
    selectedIds.value = []
  } else {
    selectedIds.value = accounts.value.map(a => a.id)
  }
}

function onCardClick(acc) {
  if (batchMode.value) {
    toggleSelect(acc.id)
  } else {
    openDetail(acc)
  }
}

async function batchUpdate(disabled) {
  if (batchBusy.value || selectedIds.value.length === 0) return
  const action = disabled ? '停用' : '启用'
  const ids = [...selectedIds.value]
  batchBusy.value = true
  let success = 0
  let failed = 0
  for (let i = 0; i < ids.length; i++) {
    const id = ids[i]
    batchProgressText.value = `${action}中 ${i + 1}/${ids.length}`
    try {
      await updateAccount(id, { disabled })
      success++
    } catch (e) {
      failed++
      console.warn(`批量${action}账号 ${id} 失败:`, e)
    }
  }
  batchBusy.value = false
  batchProgressText.value = ''
  if (failed === 0) {
    showToast(`已${action} ${success} 个账号`, 'success')
  } else {
    showToast(`${action}完成：成功 ${success}、失败 ${failed}`, 'error')
  }
  await reload()
  selectedIds.value = selectedIds.value.filter(id => accounts.value.some(a => a.id === id))
}

async function batchDelete() {
  if (batchBusy.value || selectedIds.value.length === 0) return
  if (!window.confirm(`确定要删除选中的 ${selectedIds.value.length} 个账号吗？删除后不可恢复。`)) return
  const ids = [...selectedIds.value]
  batchBusy.value = true
  let success = 0
  let failed = 0
  for (let i = 0; i < ids.length; i++) {
    const id = ids[i]
    batchProgressText.value = `删除中 ${i + 1}/${ids.length}`
    try {
      await deleteAccount(id)
      success++
    } catch (e) {
      failed++
      console.warn(`批量删除账号 ${id} 失败:`, e)
    }
  }
  batchBusy.value = false
  batchProgressText.value = ''
  if (failed === 0) {
    showToast(`已删除 ${success} 个账号`, 'success')
  } else {
    showToast(`删除完成：成功 ${success}、失败 ${failed}`, 'error')
  }
  await reload()
  selectedIds.value = selectedIds.value.filter(id => accounts.value.some(a => a.id === id))
  if (selectedIds.value.length === 0 && accounts.value.length === 0) {
    exitBatchMode()
  }
}

// ===== Cookie 过期倒计时 =====
function resolveCookieExpireTime(acc) {
  if (!acc) return null
  // 兼容多种字段命名（后端 entity: tokenExpireTime / admin VO: cookieExpiredTime）
  const raw = acc.tokenExpireTime || acc.cookieExpiredTime || acc.cookieExpireTime || acc.expireTime
  if (!raw) return null
  const date = new Date(raw)
  return isNaN(date.getTime()) ? null : date
}

function cookieExpireText(acc) {
  const expireDate = resolveCookieExpireTime(acc)
  if (!expireDate) return ''
  const diffMs = expireDate.getTime() - Date.now()
  if (diffMs <= 0) return 'Cookie 已过期，请重新登录'
  const diffDays = Math.floor(diffMs / (24 * 60 * 60 * 1000))
  const diffHours = Math.floor(diffMs / (60 * 60 * 1000))
  if (diffDays >= 1) return `Cookie 将在 ${diffDays} 天后过期`
  if (diffHours >= 1) return `Cookie 将在 ${diffHours} 小时后过期`
  return 'Cookie 即将过期，请尽快重新登录'
}

function cookieExpireClass(acc) {
  const expireDate = resolveCookieExpireTime(acc)
  if (!expireDate) return ''
  const diffMs = expireDate.getTime() - Date.now()
  if (diffMs <= 0) return 'm-acc-cookie-warn-danger'
  const diffDays = diffMs / (24 * 60 * 60 * 1000)
  if (diffDays <= 1) return 'm-acc-cookie-warn-danger'
  if (diffDays <= 7) return 'm-acc-cookie-warn-warning'
  return ''
}

// ===== 添加账号方式选择 =====
function closeAddSheet() {
  showAddSheet.value = false
}

function chooseQrLogin() {
  showAddSheet.value = false
  startAddAccount()
}

function openManualModal() {
  showAddSheet.value = false
  void ensureCanAddStore().then(allowed => {
    if (!allowed) return
    manual.cookie = ''
    manual.accountNote = ''
    manualError.value = ''
    manualWarning.value = ''
    submitting.value = false
    showManualModal.value = true
    document.body.style.overflow = 'hidden'
  })
}

function closeManualModal() {
  if (submitting.value) return
  showManualModal.value = false
  document.body.style.overflow = ''
}

async function submitManualCookie() {
  if (submitting.value) return
  const result = validateCookie(manual.cookie)
  if (!result.valid) {
    manualError.value = result.error
    manualWarning.value = ''
    return
  }
  manualError.value = ''
  manualWarning.value = result.warning || ''
  submitting.value = true
  try {
    const fields = extractKeyFields(manual.cookie)
    await createAccountByCookie({
      accountNote: manual.accountNote?.trim() || null,
      cookie: manual.cookie.trim(),
      extractedUnb: fields.unb || null,
      extractedMH5Tk: fields.mH5Tk || null,
    })
    showToast('账号添加成功', 'success')
    showManualModal.value = false
    document.body.style.overflow = ''
    await reload()
  } catch (error) {
    if (error?.data?.errorCode === 'STORE_LIMIT_REACHED') {
      await showStoreLimitUpgradeDialog(error.data)
      return
    }
    manualError.value = error?.message || '添加失败，请检查 Cookie 是否有效'
  } finally {
    submitting.value = false
  }
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

async function startAddAccount() {
  if (!await ensureCanAddStore()) return
  qrLoginAccount.value = null
  generateQr()
}

/**
 * 主「添加账号」按钮：先校验店铺数量上限，未超限再打开添加方式选择。
 */
async function onAddAccountClick() {
  if (!await ensureCanAddStore()) return
  showAddSheet.value = true
}

/**
 * 店铺数量已达上限弹窗引导（移动端）：确认后前往会员中心升级。
 */
async function showStoreLimitUpgradeDialog(status) {
  const limit = Number(status?.limit ?? 0)
  const count = Number(status?.accountCount ?? 0)
  const levelName = status?.levelName || '普通用户'
  const message = status?.message
    || `当前会员等级（${levelName}）最多绑定 ${limit} 个闲鱼店铺，您已绑定 ${count} 个。\n\n升级 VIP 后可解除店铺数量限制，继续添加更多店铺。`
  const confirmed = window.confirm(`${message}\n\n点击"确定"前往会员中心升级，点击"取消"返回。`)
  if (confirmed) emit('navigate', 'vip')
}

/**
 * 添加店铺前校验（移动端）：店铺数量已满时弹窗引导升级。
 */
async function ensureCanAddStore() {
  try {
    const status = await getStoreLimitStatus()
    if (status?.unlimited === true || Number(status?.limit ?? 0) <= 0) return true
    const count = Number(status?.accountCount ?? 0)
    if (count >= Number(status.limit)) {
      await showStoreLimitUpgradeDialog(status)
      return false
    }
    return true
  } catch {
    return true
  }
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
      } else if (status === 'error') {
        qrError.value = data?.message || '登录失败，请重试'
        stopQrPolling()
        if (data?.errorCode === 'STORE_LIMIT_REACHED') {
          closeQrModal()
          await showStoreLimitUpgradeDialog(data)
        }
      }
    } catch (e) {
      if (e?.data?.errorCode === 'STORE_LIMIT_REACHED') {
        stopQrPolling()
        closeQrModal()
        await showStoreLimitUpgradeDialog(e.data)
        return
      }
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
  if (showFilterSheet.value || showQrModal.value || showAddSheet.value || showManualModal.value) {
    document.body.style.overflow = ''
  }
})

defineExpose({ startAddAccount })
</script>

<style scoped>
.m-accounts {
  padding: var(--m-space-3);
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
  background: var(--m-color-bg-page);
}

.m-notice {
  min-height: 36px;
  box-sizing: border-box;
  background: var(--m-color-primary-bg);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-2) var(--m-space-3);
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-3);
  font-size: var(--m-font-size-caption);
  color: var(--m-color-primary);
  line-height: 1.4;
}
.m-notice :deep(svg) { flex-shrink: 0; margin-top: 1px; }
.m-notice span { flex: 1; }
.m-notice-close {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border-radius: var(--m-radius-circle);
  border: none;
  background: transparent;
  color: var(--m-color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
  opacity: 0.7;
  transition: opacity var(--m-duration-fast);
}
.m-notice-close:active { opacity: 1; }

.m-action-bar {
  display: flex;
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-3);
}
.m-action-btn {
  flex: 1;
  height: 44px;
  border-radius: var(--m-radius-xl);
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-1-5);
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  padding: 0 var(--m-space-3);
  transition: all var(--m-duration-fast);
}
.m-action-btn:active {
  transform: scale(0.97);
}
.m-action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.m-action-primary {
  background: var(--m-color-primary-gradient);
  color: var(--m-color-text-inverse);
  box-shadow: var(--m-color-primary-soft-glow);
  border-color: transparent;
}
.m-action-secondary {
  background: var(--m-color-bg-card);
  color: var(--m-color-text-secondary);
  border: 1px solid var(--m-color-border);
  box-shadow: var(--m-shadow-card);
}
.m-action-secondary:disabled {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-disabled);
  border-color: var(--m-color-border);
}
.m-action-active {
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
  border-color: transparent;
  box-shadow: var(--m-shadow-card);
}

.m-batch-info {
  background: var(--m-color-primary-bg);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-2) var(--m-space-3);
  margin-bottom: var(--m-space-3);
  font-size: var(--m-font-size-caption);
  color: var(--m-color-primary);
  font-weight: var(--m-font-weight-medium);
  text-align: center;
}

.m-stats-card {
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-4) var(--m-space-2);
  display: flex;
  align-items: center;
  box-shadow: var(--m-shadow-card);
  margin-bottom: var(--m-space-3);
}
.m-stat-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--m-space-1);
  padding: var(--m-space-2) var(--m-space-1);
  border-radius: var(--m-radius-lg);
  cursor: pointer;
  transition: background var(--m-duration-fast);
}
.m-stat-item:active {
  background: var(--m-color-bg-hover);
}
.m-stat-active {
  background: var(--m-color-primary-bg) !important;
}
.m-stat-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--m-radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
}
.m-stat-icon-blue { background: #edf5ff; color: var(--m-color-primary); }
.m-stat-icon-green { background: #e9fbf3; color: var(--m-color-success); }
.m-stat-icon-orange { background: #fff5e6; color: var(--m-color-warning); }
.m-stat-icon-purple { background: #f4efff; color: var(--m-color-purple); }
.m-stat-icon-pink { background: #fff0f1; color: var(--m-color-danger); }
.m-stat-val { 
  font-size: var(--m-font-size-h1); 
  font-weight: var(--m-font-weight-bold); 
  color: var(--m-color-text-primary); 
  line-height: 1.1;
  font-family: var(--m-font-family-number);
}
.m-stat-label { font-size: var(--m-font-size-caption); color: var(--m-color-text-tertiary); }
.m-stat-divider {
  width: 1px;
  height: 32px;
  background: var(--m-color-border-light);
  flex-shrink: 0;
}

.m-search-bar {
  display: flex;
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-3);
}
.m-search-input-wrap {
  flex: 1;
  position: relative;
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-xl);
  display: flex;
  align-items: center;
  padding: 0 var(--m-space-3);
  height: 40px;
  box-shadow: var(--m-shadow-card);
}
.m-search-icon {
  color: var(--m-color-text-tertiary);
  flex-shrink: 0;
  margin-right: var(--m-space-2);
}
.m-search-input {
  flex: 1;
  border: none;
  outline: none;
  font-size: var(--m-font-size-body);
  color: var(--m-color-text-primary);
  background: transparent;
  min-width: 0;
}
.m-search-input::placeholder {
  color: var(--m-color-text-placeholder);
}
.m-search-clear {
  width: 20px;
  height: 20px;
  border-radius: var(--m-radius-circle);
  border: none;
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  padding: 0;
  margin-left: var(--m-space-2);
}
.m-filter-btn {
  height: 40px;
  padding: 0 var(--m-space-3);
  border-radius: var(--m-radius-xl);
  border: 1px solid var(--m-color-border);
  background: var(--m-color-bg-card);
  color: var(--m-color-text-secondary);
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-medium);
  display: flex;
  align-items: center;
  gap: var(--m-space-1);
  cursor: pointer;
  flex-shrink: 0;
  box-shadow: var(--m-shadow-card);
}
.m-filter-btn :deep(svg) { color: var(--m-color-text-secondary); }

.m-quick-filters {
  display: flex;
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-3);
  overflow-x: auto;
  padding-bottom: 2px;
}
.m-quick-filters::-webkit-scrollbar { display: none; }
.m-quick-filter {
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-1);
  min-height: 32px;
  padding: var(--m-space-1) var(--m-space-3);
  border-radius: var(--m-radius-lg);
  border: 1px solid var(--m-color-border);
  background: var(--m-color-bg-card);
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-medium);
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  box-shadow: var(--m-shadow-card);
  transition: all var(--m-duration-fast);
}
.m-quick-filter:active { transform: scale(0.97); }
.m-quick-filter-active {
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
}

.m-skeleton-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-3);
}
.m-skeleton-card {
  pointer-events: none;
}
.m-skeleton-avatar {
  width: 48px;
  height: 48px;
  border-radius: var(--m-radius-circle);
  background: linear-gradient(90deg, var(--m-color-bg-subtle) 25%, var(--m-color-border-light) 50%, var(--m-color-bg-subtle) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  flex-shrink: 0;
}
.m-skeleton-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
  padding-left: var(--m-space-3);
}
.m-skeleton-line {
  height: 12px;
  border-radius: var(--m-radius-sm);
  background: linear-gradient(90deg, var(--m-color-bg-subtle) 25%, var(--m-color-border-light) 50%, var(--m-color-bg-subtle) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
.m-skeleton-line-lg { width: 60%; }
.m-skeleton-line-sm { width: 40%; }
.m-skeleton-tags {
  display: flex;
  gap: var(--m-space-2);
}
.m-skeleton-tag {
  width: 48px;
  height: 20px;
  border-radius: var(--m-radius-pill);
  background: linear-gradient(90deg, var(--m-color-bg-subtle) 25%, var(--m-color-border-light) 50%, var(--m-color-bg-subtle) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.m-empty-state {
  text-align: center;
  padding: 60px var(--m-space-5);
}
.m-empty-icon {
  width: 72px;
  height: 72px;
  margin: 0 auto var(--m-space-4);
  border-radius: var(--m-radius-circle);
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
}
.m-empty-text { 
  font-size: var(--m-font-size-h2); 
  font-weight: var(--m-font-weight-semibold); 
  color: var(--m-color-text-primary); 
  margin-bottom: var(--m-space-2); 
}
.m-empty-desc { 
  font-size: var(--m-font-size-body-sm); 
  color: var(--m-color-text-tertiary); 
  margin-bottom: var(--m-space-5); 
}
.m-empty-btn {
  padding: var(--m-space-2-5) var(--m-space-6);
  border-radius: var(--m-radius-pill);
  border: none;
  background: var(--m-color-primary-gradient);
  color: var(--m-color-text-inverse);
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  box-shadow: var(--m-color-primary-soft-glow);
  transition: all var(--m-duration-fast);
}
.m-empty-btn:active { transform: scale(0.97); }

.m-acc-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-3);
}
.m-acc-card {
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-xl);
  padding: var(--m-space-4);
  box-shadow: var(--m-shadow-card);
  cursor: pointer;
  transition: all var(--m-duration-fast);
}
.m-acc-card:active {
  transform: scale(0.98);
}
.m-acc-card-batch {
  position: relative;
  padding-left: 44px;
}
.m-acc-card-selected {
  background: var(--m-color-primary-bg);
  box-shadow: var(--m-shadow-sm);
}
.m-acc-checkbox {
  position: absolute;
  top: var(--m-space-4);
  left: var(--m-space-3);
  width: 22px;
  height: 22px;
  border-radius: var(--m-radius-md);
  border: 2px solid var(--m-color-border);
  background: var(--m-color-bg-card);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all var(--m-duration-fast);
  color: var(--m-color-text-inverse);
}
.m-acc-checkbox:active {
  transform: scale(0.9);
}
.m-acc-checkbox-checked {
  background: var(--m-color-primary);
  border-color: var(--m-color-primary);
}
.m-acc-header {
  display: flex;
  align-items: flex-start;
  gap: var(--m-space-3);
  margin-bottom: var(--m-space-3);
}
.m-acc-avatar {
  width: 44px;
  height: 44px;
  border-radius: var(--m-radius-circle);
  overflow: hidden;
  flex-shrink: 0;
  background: var(--m-color-bg-subtle);
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
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
}
.m-acc-info {
  flex: 1;
  min-width: 0;
}
.m-acc-name-row {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-1);
}
.m-acc-name {
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-acc-current-tag {
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-semibold);
  padding: 2px var(--m-space-2);
  border-radius: var(--m-radius-md);
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
  flex-shrink: 0;
}
.m-acc-uid-row {
  display: flex;
  align-items: center;
  gap: var(--m-space-1);
}
.m-acc-uid {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-uid-copy {
  width: 20px;
  height: 20px;
  border-radius: var(--m-radius-md);
  border: none;
  background: transparent;
  color: var(--m-color-text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
  flex-shrink: 0;
  transition: all var(--m-duration-fast);
}
.m-uid-copy:active {
  background: var(--m-color-bg-hover);
  color: var(--m-color-primary);
}
.m-acc-status-badge {
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-medium);
  padding: var(--m-space-0-5) var(--m-space-2);
  border-radius: var(--m-radius-pill);
  flex-shrink: 0;
}
.m-status-green { background: var(--m-color-success-bg); color: var(--m-color-success-text); }
.m-status-orange { background: var(--m-color-warning-bg); color: var(--m-color-warning-text); }
.m-status-red { background: var(--m-color-danger-bg); color: var(--m-color-danger-text); }
.m-status-gray { background: var(--m-color-bg-subtle); color: var(--m-color-text-tertiary); }
.m-status-unknown { background: var(--m-color-bg-subtle); color: var(--m-color-text-secondary); }

.m-acc-cookie-warn {
  display: flex;
  align-items: center;
  gap: var(--m-space-1-5);
  padding: var(--m-space-2) var(--m-space-3);
  border-radius: var(--m-radius-lg);
  margin-bottom: var(--m-space-3);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-medium);
}
.m-acc-cookie-warn :deep(svg) {
  flex-shrink: 0;
}
.m-acc-cookie-warn-warning {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning-text);
}
.m-acc-cookie-warn-danger {
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger-text);
}

.m-acc-connection {
  display: flex;
  align-items: center;
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3) var(--m-space-2);
  margin-bottom: var(--m-space-3);
}
.m-acc-conn-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--m-space-1);
}
.m-acc-conn-label {
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-text-tertiary);
}
.m-acc-conn-val {
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-medium);
  display: flex;
  align-items: center;
  gap: var(--m-space-1);
}
.m-acc-conn-time { color: var(--m-color-text-secondary); font-weight: var(--m-font-weight-regular); }
.m-conn-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--m-radius-circle);
}
.m-dot-green { background: var(--m-color-success); }
.m-dot-red { background: var(--m-color-danger); }
.m-dot-orange { background: var(--m-color-warning); }
.m-dot-gray { background: var(--m-color-text-tertiary); }
.m-dot-unknown { background: var(--m-color-text-disabled); }
.m-conn-green { color: var(--m-color-success-text); }
.m-conn-red { color: var(--m-color-danger-text); }
.m-conn-orange { color: var(--m-color-warning-text); }
.m-conn-gray { color: var(--m-color-text-tertiary); }
.m-conn-unknown { color: var(--m-color-text-secondary); }
.m-acc-conn-divider {
  width: 1px;
  height: 20px;
  background: var(--m-color-border);
  flex-shrink: 0;
}

.m-acc-actions {
  display: flex;
  align-items: center;
}
.m-acc-action {
  flex: 1;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  min-height: 36px;
  gap: var(--m-space-1);
  border: none;
  background: transparent;
  color: var(--m-color-primary);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-medium);
  cursor: pointer;
  padding: var(--m-space-1);
  border-radius: var(--m-radius-lg);
  transition: background var(--m-duration-fast);
}
.m-acc-action:active {
  background: var(--m-color-bg-hover);
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
  height: 20px;
  background: var(--m-color-border-light);
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
  padding: var(--m-space-4);
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}
.m-load-more-btn {
  text-align: center;
  padding: var(--m-space-3);
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-primary);
  font-weight: var(--m-font-weight-medium);
  cursor: pointer;
}

.m-safe-bottom { height: 90px; }
.m-safe-bottom-batch { height: 100px; }

.m-sheet-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--m-mask-modal);
  z-index: 1000;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.m-filter-sheet,
.m-add-sheet {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-2xl) var(--m-radius-2xl) 0 0;
  width: 100%;
  max-width: 500px;
  max-height: 75vh;
  display: flex;
  flex-direction: column;
  animation: slideUp 0.3s var(--m-ease-out);
}
@keyframes slideUp {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}
.m-sheet-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-space-5) var(--m-space-4) var(--m-space-4);
}
.m-sheet-header h3 {
  margin: 0;
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
}
.m-sheet-close {
  width: 32px;
  height: 32px;
  border-radius: var(--m-radius-circle);
  border: none;
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
  transition: all var(--m-duration-fast);
}
.m-sheet-close:active { background: var(--m-color-bg-hover); }
.m-sheet-content {
  flex: 1;
  overflow-y: auto;
  padding: 0 var(--m-space-4) var(--m-space-4);
}
.m-filter-group {
  margin-bottom: var(--m-space-5);
}
.m-filter-label {
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-medium);
  color: var(--m-color-text-primary);
  margin-bottom: var(--m-space-3);
}
.m-filter-options {
  display: flex;
  flex-wrap: wrap;
  gap: var(--m-space-2);
}
.m-filter-opt {
  padding: var(--m-space-2) var(--m-space-4);
  border-radius: var(--m-radius-lg);
  border: 1px solid var(--m-color-border-light);
  background: var(--m-color-bg-card);
  color: var(--m-color-text-secondary);
  font-size: var(--m-font-size-body-sm);
  cursor: pointer;
  transition: all var(--m-duration-fast);
}
.m-filter-opt:active { transform: scale(0.97); }
.m-filter-opt-active {
  background: var(--m-color-primary-bg);
  border-color: transparent;
  color: var(--m-color-primary);
}
.m-sheet-footer {
  display: flex;
  gap: var(--m-space-3);
  padding: var(--m-space-4);
  padding-bottom: calc(var(--m-space-4) + var(--m-safe-area-bottom));
  border-top: 1px solid var(--m-color-border-light);
}
.m-sheet-btn {
  flex: 1;
  height: 44px;
  border-radius: var(--m-radius-xl);
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  border: none;
  transition: all var(--m-duration-fast);
}
.m-sheet-btn:active { transform: scale(0.98); }
.m-sheet-btn-reset {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
}
.m-sheet-btn-confirm {
  background: var(--m-color-primary-gradient);
  color: var(--m-color-text-inverse);
  box-shadow: var(--m-color-primary-soft-glow);
}

.m-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--m-mask-modal);
  z-index: 1100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--m-space-5);
}
.m-qr-modal,
.m-manual-modal {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-2xl);
  width: 100%;
  max-width: 340px;
  overflow: hidden;
  animation: fadeIn 0.2s var(--m-ease-out);
}
.m-manual-modal {
  max-width: 420px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
}
@keyframes fadeIn {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}
.m-qr-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-space-4);
}
.m-qr-header h3 {
  margin: 0;
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
}
.m-qr-close {
  width: 32px;
  height: 32px;
  border-radius: var(--m-radius-circle);
  border: none;
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
  transition: all var(--m-duration-fast);
}
.m-qr-close:active { background: var(--m-color-bg-hover); }
.m-qr-loading, .m-qr-error {
  padding: var(--m-space-10) var(--m-space-5);
  text-align: center;
}
.m-qr-spinner {
  width: 36px;
  height: 36px;
  border: 3px solid var(--m-color-border-light);
  border-top-color: var(--m-color-primary);
  border-radius: var(--m-radius-circle);
  margin: 0 auto var(--m-space-4);
  animation: spin 1s linear infinite;
}
.m-qr-error-icon {
  color: var(--m-color-warning);
  margin-bottom: var(--m-space-3);
}
.m-qr-loading p, .m-qr-error p {
  margin: 0;
  font-size: var(--m-font-size-body);
  color: var(--m-color-text-secondary);
}
.m-qr-retry {
  margin-top: var(--m-space-4);
  padding: var(--m-space-2) var(--m-space-6);
  border-radius: var(--m-radius-pill);
  border: none;
  background: var(--m-color-primary-gradient);
  color: var(--m-color-text-inverse);
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  box-shadow: var(--m-color-primary-soft-glow);
  transition: all var(--m-duration-fast);
}
.m-qr-retry:active { transform: scale(0.97); }
.m-qr-content {
  padding: var(--m-space-5);
  text-align: center;
}
.m-qr-code-wrap {
  width: 200px;
  height: 200px;
  margin: 0 auto var(--m-space-4);
  padding: var(--m-space-3);
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-xl);
}
.m-qr-code {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.m-qr-tip {
  margin: 0 0 var(--m-space-1-5);
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-medium);
  color: var(--m-color-text-primary);
}
.m-qr-status {
  margin: 0;
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}

.m-toast {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  padding: var(--m-space-3) var(--m-space-6);
  border-radius: var(--m-radius-xl);
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-medium);
  z-index: 2000;
  animation: toastIn 0.2s var(--m-ease-out);
}
@keyframes toastIn {
  from { opacity: 0; transform: translate(-50%, -50%) scale(0.9); }
  to { opacity: 1; transform: translate(-50%, -50%) scale(1); }
}
.m-toast-success {
  background: var(--m-color-success);
  color: var(--m-color-text-inverse);
}
.m-toast-error {
  background: var(--m-color-danger);
  color: var(--m-color-text-inverse);
}

.m-batch-toolbar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 999;
  background: var(--m-color-bg-card);
  border-top: 1px solid var(--m-color-border-light);
  padding: var(--m-space-3) var(--m-space-3) calc(var(--m-space-3) + var(--m-safe-area-bottom));
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  max-width: 100%;
}
.m-batch-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-medium);
  padding: var(--m-space-1) var(--m-space-1);
  border-radius: var(--m-radius-lg);
  flex-shrink: 0;
  min-width: 48px;
  color: var(--m-color-text-secondary);
  transition: background var(--m-duration-fast), opacity var(--m-duration-fast);
}
.m-batch-btn:active:not(:disabled) {
  background: var(--m-color-bg-hover);
}
.m-batch-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.m-batch-btn-select {
  color: var(--m-color-primary);
}
.m-batch-actions {
  flex: 1;
  display: flex;
  justify-content: space-around;
  gap: var(--m-space-1);
}
.m-batch-btn-enable {
  color: var(--m-color-success);
}
.m-batch-btn-disable {
  color: var(--m-color-warning-text);
}
.m-batch-btn-delete {
  color: var(--m-color-danger);
}
.m-batch-btn-cancel {
  color: var(--m-color-text-secondary);
}

.m-add-sheet-content {
  padding: var(--m-space-2) var(--m-space-4) var(--m-space-5);
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
}
.m-add-option {
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
  width: 100%;
  padding: var(--m-space-4) var(--m-space-3);
  border-radius: var(--m-radius-xl);
  border: none;
  background: var(--m-color-bg-subtle);
  cursor: pointer;
  text-align: left;
  transition: all var(--m-duration-fast);
}
.m-add-option:active {
  transform: scale(0.98);
  background: var(--m-color-bg-hover);
}
.m-add-option-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--m-radius-xl);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-add-option-icon-qr {
  background: #edf5ff;
  color: var(--m-color-primary);
}
.m-add-option-icon-cookie {
  background: #fff5e6;
  color: var(--m-color-warning-text);
}
.m-add-option-info {
  flex: 1;
  min-width: 0;
}
.m-add-option-name {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  margin-bottom: 2px;
}
.m-add-option-desc {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}
.m-add-option-arrow {
  color: var(--m-color-text-quaternary);
  flex-shrink: 0;
}

.m-manual-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--m-space-4);
}
.m-cookie-tip {
  display: flex;
  align-items: flex-start;
  gap: var(--m-space-1-5);
  background: var(--m-color-primary-bg);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3);
  margin: 0 0 var(--m-space-4);
  font-size: var(--m-font-size-caption);
  color: var(--m-color-primary);
  line-height: var(--m-line-height-base);
}
.m-cookie-tip :deep(svg) {
  flex-shrink: 0;
  margin-top: 1px;
}
.m-cookie-tip code {
  background: rgba(22, 93, 255, 0.1);
  padding: 1px var(--m-space-1);
  border-radius: var(--m-radius-xs);
  font-family: var(--m-font-family-mono);
  font-size: 11px;
}
.m-form-row {
  margin-bottom: var(--m-space-4);
}
.m-form-label {
  display: block;
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-medium);
  color: var(--m-color-text-secondary);
  margin-bottom: var(--m-space-2);
}
.m-form-textarea,
.m-form-input {
  width: 100%;
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3);
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-primary);
  background: var(--m-color-bg-subtle);
  outline: none;
  transition: all var(--m-duration-fast);
  box-sizing: border-box;
  font-family: inherit;
}
.m-form-textarea {
  font-family: var(--m-font-family-mono);
  font-size: var(--m-font-size-caption);
  resize: vertical;
  min-height: 100px;
  line-height: var(--m-line-height-base);
  word-break: break-all;
}
.m-form-textarea:focus,
.m-form-input:focus {
  border-color: var(--m-color-primary);
  background: var(--m-color-bg-card);
  box-shadow: 0 0 0 3px rgba(22, 93, 255, 0.1);
}
.m-form-textarea:disabled,
.m-form-input:disabled {
  background: var(--m-color-bg-hover);
  color: var(--m-color-text-tertiary);
  cursor: not-allowed;
}
.m-form-error,
.m-form-warning {
  display: flex;
  align-items: flex-start;
  gap: var(--m-space-1-5);
  padding: var(--m-space-2) var(--m-space-3);
  border-radius: var(--m-radius-lg);
  margin: calc(-1 * var(--m-space-2)) 0 var(--m-space-3);
  font-size: var(--m-font-size-caption);
  line-height: var(--m-line-height-base);
}
.m-form-error {
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger-text);
}
.m-form-warning {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning-text);
}
.m-form-error :deep(svg),
.m-form-warning :deep(svg) {
  flex-shrink: 0;
  margin-top: 1px;
}
.m-form-parsed {
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3);
  margin: calc(-1 * var(--m-space-2)) 0 var(--m-space-3);
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
}
.m-parsed-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: var(--m-font-size-caption);
  gap: var(--m-space-2);
}
.m-parsed-label {
  color: var(--m-color-text-tertiary);
  flex-shrink: 0;
}
.m-parsed-val {
  color: var(--m-color-text-primary);
  font-weight: var(--m-font-weight-medium);
  font-family: var(--m-font-family-mono);
  font-size: 11px;
  word-break: break-all;
  text-align: right;
}
.m-manual-footer {
  display: flex;
  gap: var(--m-space-3);
  padding: var(--m-space-4);
  padding-bottom: calc(var(--m-space-4) + var(--m-safe-area-bottom));
  border-top: 1px solid var(--m-color-border-light);
}

@media (max-width: 380px) {
  .m-stat-val { font-size: 18px; }
  .m-stat-label { font-size: var(--m-font-size-tiny); }
  .m-stat-icon { width: 28px; height: 28px; }
  .m-filter-btn span { display: none; }
  .m-filter-btn { padding: 0 var(--m-space-3); }
}
</style>
