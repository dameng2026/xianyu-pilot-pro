<template>
  <div class="m-account-detail">
    <div v-if="loading && !account" class="m-detail-skeleton">
      <div class="m-skeleton-profile">
        <div class="m-skeleton-avatar-lg"></div>
        <div class="m-skeleton-profile-info">
          <div class="m-skeleton-line m-skeleton-line-xl"></div>
          <div class="m-skeleton-line m-skeleton-line-md"></div>
        </div>
      </div>
      <div class="m-skeleton-card">
        <div class="m-skeleton-line m-skeleton-line-lg"></div>
        <div class="m-skeleton-line m-skeleton-line-sm"></div>
        <div class="m-skeleton-line m-skeleton-line-sm"></div>
      </div>
      <div class="m-skeleton-card">
        <div class="m-skeleton-line m-skeleton-line-lg"></div>
        <div class="m-skeleton-line m-skeleton-line-sm"></div>
        <div class="m-skeleton-line m-skeleton-line-sm"></div>
        <div class="m-skeleton-line m-skeleton-line-sm"></div>
      </div>
    </div>

    <MobileUnavailableState v-else-if="loadError && !account" title="账号加载失败" :description="loadError" @retry="loadAccount" />

    <div v-else-if="!account" class="m-not-found">
      <div class="m-not-found-icon">
        <MIcon name="xCircle" :size="48" />
      </div>
      <div class="m-not-found-text">账号不存在或已被删除</div>
      <button class="m-not-found-btn" @click="$emit('back')">返回账号列表</button>
    </div>

    <template v-else>
      <div v-if="isLoginExpired" class="m-expired-notice" @click="startQrLogin">
        <MIcon name="alertTriangle" :size="18" />
        <span>登录已失效，点击重新扫码登录</span>
        <MIcon name="chevronRight" :size="16" class="m-notice-arrow" />
      </div>

      <div class="m-profile-card">
        <div class="m-profile-header">
          <div class="m-profile-avatar">
            <img
              v-if="avatarUrl"
              :src="avatarUrl"
              :alt="accountName(account)"
              class="m-profile-avatar-img"
              @error="onAvatarError"
            />
            <div v-else class="m-profile-avatar-placeholder">
              <MIcon name="user" :size="32" />
            </div>
          </div>
          <div class="m-profile-info">
            <div class="m-profile-name-row">
              <span class="m-profile-name">{{ accountName(account) }}</span>
              <span v-if="isCurrentAccount" class="m-profile-current-tag">当前账号</span>
            </div>
            <div class="m-profile-uid-row">
              <span class="m-profile-uid">UID：{{ displayUid(account) }}</span>
              <button class="m-uid-copy-btn" @click="copyUid">
                <MIcon name="copy" :size="12" />
              </button>
            </div>
            <div class="m-profile-status-row">
              <span class="m-profile-status" :class="accountStatusClass(account)">
                <span class="m-status-dot" :class="accountStatusDotClass(account)"></span>
                {{ accountStatusText(account) }}
              </span>
              <span class="m-profile-ws" :class="wsStatusClass(account)">
                {{ wsStatusText(account) }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div class="m-detail-card">
        <div class="m-card-header">
          <h3 class="m-card-title">连接诊断</h3>
        </div>
        <div class="m-diagnosis-list">
          <div class="m-diagnosis-item" @click="handleDiagnosisClick('cookie')">
            <div class="m-diagnosis-left">
              <div class="m-diagnosis-icon" :class="cookieStatusClass(account)">
                <MIcon :name="cookieStatusIcon(account)" :size="18" />
              </div>
              <div class="m-diagnosis-info">
                <div class="m-diagnosis-name">Cookie状态</div>
                <div class="m-diagnosis-desc">{{ cookieStatusDesc(account) }}</div>
              </div>
            </div>
            <div class="m-diagnosis-right">
              <span class="m-diagnosis-badge" :class="cookieStatusClass(account)">{{ cookieStatusText(account) }}</span>
              <MIcon name="chevronRight" :size="16" class="m-diagnosis-arrow" />
            </div>
          </div>
          <div class="m-diagnosis-divider"></div>
          <div class="m-diagnosis-item" @click="handleDiagnosisClick('verify')">
            <div class="m-diagnosis-left">
              <div class="m-diagnosis-icon" :class="verifyStatusClass(account)">
                <MIcon :name="verifyStatusIcon(account)" :size="18" />
              </div>
              <div class="m-diagnosis-info">
                <div class="m-diagnosis-name">账号验证</div>
                <div class="m-diagnosis-desc">{{ verifyStatusDesc(account) }}</div>
              </div>
            </div>
            <div class="m-diagnosis-right">
              <span class="m-diagnosis-badge" :class="verifyStatusClass(account)">{{ verifyStatusText(account) }}</span>
              <MIcon name="chevronRight" :size="16" class="m-diagnosis-arrow" />
            </div>
          </div>
          <div class="m-diagnosis-divider"></div>
          <div class="m-diagnosis-item" @click="handleDiagnosisClick('ws')">
            <div class="m-diagnosis-left">
              <div class="m-diagnosis-icon" :class="wsDiagnosisClass(account)">
                <MIcon name="wifi" :size="18" />
              </div>
              <div class="m-diagnosis-info">
                <div class="m-diagnosis-name">消息连接</div>
                <div class="m-diagnosis-desc">{{ wsDiagnosisDesc(account) }}</div>
              </div>
            </div>
            <div class="m-diagnosis-right">
              <span class="m-diagnosis-badge" :class="wsDiagnosisClass(account)">{{ wsDiagnosisText(account) }}</span>
              <MIcon name="chevronRight" :size="16" class="m-diagnosis-arrow" />
            </div>
          </div>
        </div>
      </div>

      <div class="m-detail-card">
        <div class="m-card-header">
          <h3 class="m-card-title">闲鱼主页资料</h3>
          <button class="m-card-link" @click="viewFullProfile">查看完整资料</button>
        </div>
        <div class="m-profile-stats">
          <div class="m-profile-stat">
            <div class="m-profile-stat-val">{{ profileData.fans ?? '--' }}</div>
            <div class="m-profile-stat-label">粉丝</div>
          </div>
          <div class="m-profile-stat-divider"></div>
          <div class="m-profile-stat">
            <div class="m-profile-stat-val">{{ profileData.following ?? '--' }}</div>
            <div class="m-profile-stat-label">关注</div>
          </div>
          <div class="m-profile-stat-divider"></div>
          <div class="m-profile-stat">
            <div class="m-profile-stat-val">{{ profileData.ratingCount ?? '--' }}</div>
            <div class="m-profile-stat-label">评价</div>
          </div>
        </div>
        <div class="m-profile-extra">
          <div class="m-extra-row">
            <span class="m-extra-label">买家等级</span>
            <span class="m-extra-val">{{ profileData.buyerLevel ?? '--' }}</span>
          </div>
          <div class="m-extra-row">
            <span class="m-extra-label">信用分</span>
            <span class="m-extra-val" :class="creditClass(profileData.creditScore)">{{ profileData.creditScore ?? '--' }}</span>
          </div>
          <div class="m-extra-row">
            <span class="m-extra-label">注册时间</span>
            <span class="m-extra-val">{{ registerTimeText(account) }}</span>
          </div>
          <div class="m-extra-row">
            <span class="m-extra-label">信用状态</span>
            <span class="m-extra-val" :class="creditStatusClass(profileData.creditLevel)">{{ profileData.creditLevel ?? '--' }}</span>
          </div>
        </div>
        <div class="m-profile-id">
          账号ID：{{ accountName(account) }}
        </div>
      </div>

      <div class="m-detail-card">
        <div class="m-card-header">
          <h3 class="m-card-title">快捷操作</h3>
        </div>
        <div class="m-quick-actions-grid">
          <button class="m-quick-action-item" @click="editCookie">
            <div class="m-quick-action-icon" style="background: linear-gradient(135deg, #fef3c7, #fde68a); color: #d97706;">
              <MIcon name="cookie" :size="20" />
            </div>
            <span class="m-quick-action-name">编辑Cookie</span>
            <MIcon name="chevronRight" :size="14" class="m-quick-action-arrow" />
          </button>
          <button class="m-quick-action-item" :class="{ 'm-action-loading': refreshing }" :disabled="refreshing" @click="refreshProfileAction">
            <div class="m-quick-action-icon" style="background: linear-gradient(135deg, #dbeafe, #bfdbfe); color: #2563eb;">
              <MIcon name="refresh" :size="20" :class="{ 'm-icon-spin': refreshing }" />
            </div>
            <span class="m-quick-action-name">刷新资料</span>
            <MIcon name="chevronRight" :size="14" class="m-quick-action-arrow" />
          </button>
          <button class="m-quick-action-item" @click="syncProducts">
            <div class="m-quick-action-icon" style="background: linear-gradient(135deg, #d1fae5, #a7f3d0); color: #059669;">
              <MIcon name="sync" :size="20" />
            </div>
            <span class="m-quick-action-name">同步商品</span>
            <MIcon name="chevronRight" :size="14" class="m-quick-action-arrow" />
          </button>
          <button class="m-quick-action-item" @click="goAutoDelivery">
            <div class="m-quick-action-icon" style="background: linear-gradient(135deg, #fce7f3, #fbcfe8); color: #db2777;">
              <MIcon name="truck2" :size="20" />
            </div>
            <span class="m-quick-action-name">自动发货</span>
            <MIcon name="chevronRight" :size="14" class="m-quick-action-arrow" />
          </button>
          <button class="m-quick-action-item" @click="startQrLogin">
            <div class="m-quick-action-icon" style="background: linear-gradient(135deg, #e0e7ff, #c7d2fe); color: #4f46e5;">
              <MIcon name="scanQr" :size="20" />
            </div>
            <span class="m-quick-action-name">重新扫码</span>
            <MIcon name="chevronRight" :size="14" class="m-quick-action-arrow" />
          </button>
          <button class="m-quick-action-item" @click="faceVerify">
            <div class="m-quick-action-icon" style="background: linear-gradient(135deg, #f3e8ff, #e9d5ff); color: #9333ea;">
              <MIcon name="faceVerify" :size="20" />
            </div>
            <span class="m-quick-action-name">人脸验证</span>
            <MIcon name="chevronRight" :size="14" class="m-quick-action-arrow" />
          </button>
        </div>
        <button class="m-quick-action-item m-quick-action-full" @click="openMessageGuard">
          <div class="m-quick-action-icon" style="background: linear-gradient(135deg, #cffafe, #a5f3fc); color: #0891b2;">
            <MIcon name="messageGuard" :size="20" />
          </div>
          <span class="m-quick-action-name">消息守护</span>
          <span class="m-quick-action-status">{{ messageGuardStatus }}</span>
          <MIcon name="chevronRight" :size="14" class="m-quick-action-arrow" />
        </button>
      </div>

      <div class="m-safe-bottom"></div>
    </template>

    <div v-if="showMoreMenu" class="m-menu-overlay" @click="showMoreMenu = false">
      <div class="m-more-menu" @click.stop>
        <button class="m-more-item" @click="setAsCurrent">
          <MIcon name="userCheck" :size="18" />
          <span>设为当前账号</span>
        </button>
        <button class="m-more-item" @click="editNote">
          <MIcon name="edit2" :size="18" />
          <span>编辑备注</span>
        </button>
        <button class="m-more-item" @click="refreshConnection">
          <MIcon name="refresh" :size="18" />
          <span>刷新连接</span>
        </button>
        <div class="m-more-divider"></div>
        <button class="m-more-item m-more-item-danger" @click="disableAccount">
          <MIcon name="power2" :size="18" />
          <span>停用账号</span>
        </button>
        <button class="m-more-item m-more-item-danger" @click="deleteAccountConfirm">
          <MIcon name="trash2" :size="18" />
          <span>删除账号</span>
        </button>
        <button class="m-more-item m-more-item-cancel" @click="showMoreMenu = false">
          取消
        </button>
      </div>
    </div>

    <div v-if="showEditNoteModal" class="m-modal-overlay" @click="showEditNoteModal = false">
      <div class="m-edit-modal" @click.stop>
        <div class="m-edit-header">
          <h3>编辑账号备注</h3>
        </div>
        <div class="m-edit-body">
          <input v-model="noteText" type="text" class="m-edit-input" placeholder="输入账号备注" maxlength="50" />
        </div>
        <div class="m-edit-footer">
          <button class="m-edit-btn m-edit-btn-cancel" @click="showEditNoteModal = false">取消</button>
          <button class="m-edit-btn m-edit-btn-confirm" @click="saveNote">保存</button>
        </div>
      </div>
    </div>

    <div v-if="showCookieModal" class="m-modal-overlay" @click="showCookieModal = false">
      <div class="m-cookie-modal" @click.stop>
        <div class="m-cookie-header">
          <h3>编辑Cookie</h3>
          <button class="m-cookie-close" @click="showCookieModal = false">
            <MIcon name="x" :size="20" />
          </button>
        </div>
        <div class="m-cookie-body">
          <p class="m-cookie-warning">
            <MIcon name="alertTriangle" :size="16" />
            Cookie属于敏感信息，请勿泄露给他人
          </p>
          <textarea v-model="cookieText" class="m-cookie-textarea" placeholder="粘贴Cookie内容" rows="6"></textarea>
        </div>
        <div class="m-cookie-footer">
          <button class="m-cookie-btn m-cookie-btn-cancel" @click="showCookieModal = false">取消</button>
          <button class="m-cookie-btn m-cookie-btn-confirm" @click="saveCookie">保存</button>
        </div>
      </div>
    </div>

    <div v-if="showQrModal" class="m-modal-overlay" @click="closeQrModal">
      <div class="m-qr-modal" @click.stop>
        <div class="m-qr-header">
          <h3>扫码登录</h3>
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

    <div v-if="showConfirmDialog" class="m-modal-overlay" @click="showConfirmDialog = false">
      <div class="m-confirm-modal" @click.stop>
        <div class="m-confirm-icon" :class="confirmDialog.danger ? 'm-confirm-icon-danger' : 'm-confirm-icon-warning'">
          <MIcon :name="confirmDialog.danger ? 'alertTriangle' : 'alertCircle'" :size="28" />
        </div>
        <h3 class="m-confirm-title">{{ confirmDialog.title }}</h3>
        <p class="m-confirm-desc">{{ confirmDialog.message }}</p>
        <div class="m-confirm-btns">
          <button class="m-confirm-btn m-confirm-btn-cancel" @click="showConfirmDialog = false">取消</button>
          <button class="m-confirm-btn" :class="confirmDialog.danger ? 'm-confirm-btn-danger' : 'm-confirm-btn-primary'" @click="executeConfirmAction">确定</button>
        </div>
      </div>
    </div>

    <div v-if="toast.show" class="m-toast" :class="'m-toast-' + toast.type">
      {{ toast.message }}
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import MIcon from './MIcon.vue'
import MobileUnavailableState from './MobileUnavailableState.vue'
import {
  getAccountDetail,
  refreshAccountProfile as apiRefreshProfile,
  updateAccount,
  deleteAccount as apiDeleteAccount,
  updateAccountCookie
} from '../api/accounts.js'
import { generateQrLogin, getQrLoginStatus, cleanupQrLogin } from '../api/qrlogin.js'
import { accountCookieLabel, accountCookieStatus, accountWsConnectionState } from '../utils/accountAuth.js'
import { resolveTrustedMediaUrl } from '../utils/safeMediaUrl.js'

const props = defineProps({
  accountId: {
    type: [String, Number],
    required: true
  }
})

const emit = defineEmits(['navigate', 'force-desktop', 'back', 'refresh-list'])

const account = ref(null)
const loading = ref(false)
const loadError = ref('')
const refreshing = ref(false)
const profileData = reactive({
  fans: null,
  following: null,
  ratingCount: null,
  buyerLevel: null,
  creditScore: null,
  creditLevel: null
})

const showMoreMenu = ref(false)
const showEditNoteModal = ref(false)
const noteText = ref('')
const showCookieModal = ref(false)
const cookieText = ref('')

const showQrModal = ref(false)
const qrLoading = ref(false)
const qrError = ref('')
const qrCode = ref('')
const qrSessionId = ref('')
const qrStatusText = ref('等待扫码...')
let qrPollTimer = null

const showConfirmDialog = ref(false)
const confirmDialog = reactive({
  title: '',
  message: '',
  danger: false,
  action: null
})

const toast = reactive({
  show: false,
  message: '',
  type: 'success'
})
let toastTimer = null

const messageGuardStatus = ref('未开启')

const isCurrentAccount = computed(() => {
  return account.value?.isCurrent === true || account.value?.isDefault === true
})

const isLoginExpired = computed(() => {
  if (!account.value) return false
  const cs = accountCookieStatus(account.value)
  return cs === 0 || account.value.needVerify === true
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

function accountName(acc) {
  if (!acc) return '未知账号'
  return acc.name || acc.nickname || acc.displayName || acc.accountNote || `账号${acc.id || ''}`
}

function displayUid(acc) {
  if (!acc) return '-'
  return acc.uid || acc.externalUid || acc.unb || '-'
}

function onAvatarError() {
  if (account.value) {
    account.value.avatarUrl = ''
    account.value.avatar = ''
  }
}

// 清洗头像 URL：过滤脏数据/历史格式及非白名单域名，避免 <img> 加载脏 URL 失败
const avatarUrl = computed(() => {
  const acc = account.value
  if (!acc) return ''
  return resolveTrustedMediaUrl(acc.avatarUrl || acc.avatar || '')
})

function copyUid() {
  const uid = displayUid(account.value)
  if (uid && uid !== '-') {
    navigator.clipboard.writeText(uid).then(() => {
      showToast('UID已复制', 'success')
    }).catch(() => {
      showToast('复制失败', 'error')
    })
  }
}

function accountStatusText(acc) {
  if (!acc) return '未知'
  if (acc.disabled) return '已停用'
  const cs = accountCookieStatus(acc)
  if (cs === 0) return '登录失效'
  if (acc.needVerify || acc.needFaceVerify) return '需验证'
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

function accountStatusDotClass(acc) {
  return accountStatusClass(acc).replace('m-status-', 'm-dot-')
}

function cookieStatusText(acc) {
  if (!acc) return '未知'
  return accountCookieLabel(acc)
}

function cookieStatusClass(acc) {
  if (!acc) return 'm-diag-unknown'
  const cs = accountCookieStatus(acc)
  if (cs === null) return 'm-diag-unknown'
  if (cs === 0) return 'm-diag-red'
  if (cs === 2) return 'm-diag-orange'
  return 'm-diag-green'
}

function cookieStatusIcon(acc) {
  const cs = accountCookieStatus(acc)
  if (cs === 1) return 'shieldCheck'
  if (cs === 0 || cs === 2) return 'shieldAlert'
  return 'shield'
}

function cookieStatusDesc(acc) {
  const cs = accountCookieStatus(acc)
  if (cs === 1) return '有效、未过期，账号验证可正常访问'
  if (cs === 2) return 'Cookie即将过期，建议重新扫码'
  if (cs === 0) return 'Cookie已失效，请重新扫码登录'
  return 'Cookie状态未知'
}

function verifyStatusText(acc) {
  if (!acc) return '未知'
  if (acc.needVerify || acc.needFaceVerify) return '待验证'
  if (acc.verified === false) return '未验证'
  return '已验证'
}

function verifyStatusClass(acc) {
  if (!acc) return 'm-diag-unknown'
  if (acc.needVerify || acc.needFaceVerify || acc.verified === false) return 'm-diag-orange'
  return 'm-diag-green'
}

function verifyStatusIcon(acc) {
  if (acc?.needVerify || acc?.needFaceVerify || acc?.verified === false) return 'shieldAlert'
  return 'userCheck'
}

function verifyStatusDesc(acc) {
  if (!acc) return '验证状态未知'
  if (acc.needVerify || acc.needFaceVerify) return '需要完成人脸验证才能正常操作'
  if (acc.verified === false) return '账号尚未完成验证'
  return '验证通过，可正常进行发布等操作'
}

function wsStatusText(acc) {
  const state = accountWsConnectionState(acc)
  if (state === true) return 'WS在线'
  if (state === false) return 'WS离线'
  return '状态未知'
}

function wsStatusClass(acc) {
  const state = accountWsConnectionState(acc)
  if (state === true) return 'm-ws-online'
  if (state === false) return 'm-ws-offline'
  return 'm-ws-unknown'
}

function wsDiagnosisText(acc) {
  const state = accountWsConnectionState(acc)
  if (state === true) return '正常'
  if (state === false) return '离线'
  if (state === 'connecting') return '连接中'
  return '不稳定'
}

function wsDiagnosisClass(acc) {
  const state = accountWsConnectionState(acc)
  if (state === true) return 'm-diag-green'
  if (state === false) return 'm-diag-red'
  if (state === 'connecting') return 'm-diag-orange'
  return 'm-diag-orange'
}

function wsDiagnosisDesc(acc) {
  const state = accountWsConnectionState(acc)
  if (state === true) return '消息连接正常，可实时接收消息'
  if (state === false) return '消息连接已断开，无法接收消息'
  if (state === 'connecting') return '正在建立消息连接...'
  return '偶有断连，建议开启消息守护保障接收'
}

function registerTimeText(acc) {
  if (!acc?.registerTime && !acc?.createdAt) return '--'
  try {
    const date = new Date(acc.registerTime || acc.createdAt)
    const now = new Date()
    const diffMs = now - date
    const years = Math.floor(diffMs / (365 * 24 * 60 * 60 * 1000))
    const months = Math.floor((diffMs % (365 * 24 * 60 * 60 * 1000)) / (30 * 24 * 60 * 60 * 1000))
    if (years > 0) return `${years}年${months}个月`
    return `${months}个月`
  } catch {
    return '--'
  }
}

function creditClass(score) {
  const num = Number(score)
  if (isNaN(num)) return ''
  if (num >= 70) return 'm-credit-excellent'
  if (num >= 60) return 'm-credit-good'
  return 'm-credit-poor'
}

function creditStatusClass(level) {
  if (!level) return ''
  if (level.includes('极好') || level.includes('优秀')) return 'm-credit-excellent'
  if (level.includes('良好') || level.includes('较好')) return 'm-credit-good'
  return 'm-credit-poor'
}

function handleDiagnosisClick(type) {
  if (type === 'cookie') {
    showToast('Cookie管理功能开发中', 'info')
  } else if (type === 'verify') {
    showToast('人脸验证功能开发中', 'info')
  } else if (type === 'ws') {
    showToast('消息守护配置开发中', 'info')
  }
}

function viewFullProfile() {
  showToast('完整资料页开发中', 'info')
}

function editCookie() {
  cookieText.value = ''
  showCookieModal.value = true
}

async function saveCookie() {
  if (!cookieText.value.trim()) {
    showToast('请输入Cookie内容', 'error')
    return
  }
  try {
    await updateAccountCookie(props.accountId, cookieText.value.trim())
    showCookieModal.value = false
    showToast('Cookie已更新', 'success')
    await loadAccount()
    emit('refresh-list')
  } catch (error) {
    showToast(error?.message || '保存失败', 'error')
  }
}

async function refreshProfileAction() {
  if (refreshing.value || !account.value) return
  refreshing.value = true
  try {
    await apiRefreshProfile(account.value.id)
    showToast('资料刷新成功', 'success')
    await loadAccount()
    emit('refresh-list')
  } catch (error) {
    showToast(error?.message || '刷新失败', 'error')
  } finally {
    refreshing.value = false
  }
}

function syncProducts() {
  showToast('商品同步功能开发中', 'info')
}

function goAutoDelivery() {
  emit('navigate', 'auto-delivery')
}

function faceVerify() {
  showToast('人脸验证功能开发中', 'info')
}

function openMessageGuard() {
  showToast('消息守护功能开发中', 'info')
}

function openMoreMenu() {
  showMoreMenu.value = true
}

function setAsCurrent() {
  showMoreMenu.value = false
  showToast('设为当前账号功能开发中', 'info')
}

function editNote() {
  showMoreMenu.value = false
  noteText.value = account.value?.accountNote || ''
  showEditNoteModal.value = true
}

async function saveNote() {
  try {
    await updateAccount(props.accountId, { accountNote: noteText.value })
    showEditNoteModal.value = false
    showToast('备注已保存', 'success')
    await loadAccount()
    emit('refresh-list')
  } catch (error) {
    showToast(error?.message || '保存失败', 'error')
  }
}

function refreshConnection() {
  showMoreMenu.value = false
  showToast('正在刷新连接...', 'success')
  loadAccount()
}

function disableAccount() {
  showMoreMenu.value = false
  confirmDialog.title = '停用账号'
  confirmDialog.message = '停用后将终止该账号的自动任务和消息连接，确定要停用吗？'
  confirmDialog.danger = true
  confirmDialog.action = async () => {
    try {
      await updateAccount(props.accountId, { disabled: true })
      showToast('账号已停用', 'success')
      emit('back')
      emit('refresh-list')
    } catch (error) {
      showToast(error?.message || '停用失败', 'error')
    }
  }
  showConfirmDialog.value = true
}

function deleteAccountConfirm() {
  showMoreMenu.value = false
  confirmDialog.title = '删除账号'
  confirmDialog.message = '删除后将无法恢复，该账号的同步任务、自动发货和消息连接都会停止，确定要删除吗？'
  confirmDialog.danger = true
  confirmDialog.action = async () => {
    try {
      await apiDeleteAccount(props.accountId)
      showToast('账号已删除', 'success')
      emit('back')
      emit('refresh-list')
    } catch (error) {
      showToast(error?.message || '删除失败', 'error')
    }
  }
  showConfirmDialog.value = true
}

function executeConfirmAction() {
  if (confirmDialog.action) {
    confirmDialog.action()
  }
  showConfirmDialog.value = false
}

async function loadAccount() {
  loading.value = true
  loadError.value = ''
  try {
    const res = await getAccountDetail(props.accountId)
    const data = res?.data || res
    if (!data) {
      throw new Error('账号不存在')
    }
    account.value = data
    profileData.fans = data.fans ?? data.followerCount ?? null
    profileData.following = data.following ?? data.followingCount ?? null
    profileData.ratingCount = data.ratingCount ?? data.evaluationCount ?? null
    profileData.buyerLevel = data.buyerLevel ? `Lv.${data.buyerLevel}` : null
    profileData.creditScore = data.creditScore ?? data.sesameScore ?? null
    profileData.creditLevel = data.creditLevel ?? data.creditStatus ?? null
    messageGuardStatus.value = data.messageGuardEnabled ? '已开启' : '未开启'
  } catch (error) {
    loadError.value = error?.message || '加载失败'
    account.value = null
  } finally {
    loading.value = false
  }
}

function startQrLogin() {
  showMoreMenu.value = false
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
      accountId: props.accountId
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
          loadAccount()
          emit('refresh-list')
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
  document.body.style.overflow = ''
}

watch(() => props.accountId, () => {
  if (props.accountId) {
    loadAccount()
  }
})

onMounted(() => {
  if (props.accountId) {
    loadAccount()
  }
})

onBeforeUnmount(() => {
  stopQrPolling()
  if (showQrModal.value || showMoreMenu.value || showEditNoteModal.value || showCookieModal.value || showConfirmDialog.value) {
    document.body.style.overflow = ''
  }
})

defineExpose({ openMoreMenu })
</script>

<style scoped>
.m-account-detail {
  padding: 12px 16px 0;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
}

.m-expired-notice {
  background: linear-gradient(135deg, #fff7ed, #ffedd5);
  border-radius: 10px;
  padding: 12px 14px;
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  cursor: pointer;
  color: #c2410c;
  font-size: 13px;
  font-weight: 500;
}
.m-expired-notice :deep(svg) { flex-shrink: 0; }
.m-expired-notice span { flex: 1; }
.m-notice-arrow { margin-left: auto; }

.m-profile-card {
  background: white;
  border-radius: 14px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(31, 53, 94, 0.05);
  border: 1px solid #f0f4fa;
  margin-bottom: 12px;
}
.m-profile-header {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}
.m-profile-avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  overflow: hidden;
  flex-shrink: 0;
  background: #f4f7fc;
}
.m-profile-avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.m-profile-avatar-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #e8f1ff, #d4e4ff);
  color: #0d6bff;
}
.m-profile-info {
  flex: 1;
  min-width: 0;
}
.m-profile-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.m-profile-name {
  font-size: 17px;
  font-weight: 700;
  color: #15213d;
}
.m-profile-current-tag {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
  background: #e8f1ff;
  color: #0d6bff;
  flex-shrink: 0;
}
.m-profile-uid-row {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 8px;
}
.m-profile-uid {
  font-size: 13px;
  color: #8c98ae;
}
.m-uid-copy-btn {
  width: 22px;
  height: 22px;
  border-radius: 4px;
  border: none;
  background: #f4f7fc;
  color: #8c98ae;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
}
.m-profile-status-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.m-profile-status {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 600;
}
.m-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.m-dot-green { background: #16bf78; }
.m-dot-red { background: #ff5252; }
.m-dot-orange { background: #ff9f22; }
.m-dot-gray { background: #8c98ae; }
.m-status-green { color: #16bf78; }
.m-status-red { color: #ff5252; }
.m-status-orange { color: #ff9f22; }
.m-status-gray { color: #8c98ae; }
.m-profile-ws {
  font-size: 12px;
  color: #64748b;
}
.m-ws-online { color: #16bf78; }
.m-ws-offline { color: #8c98ae; }
.m-ws-unknown { color: #64748b; }

.m-detail-card {
  background: #fff;
  border-radius: 10px;
  padding: 14px;
  box-shadow: 0 3px 12px rgba(31, 53, 94, 0.05);
  border: 1px solid #e7edf8;
  margin-bottom: 10px;
}
.m-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.m-card-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: #15213d;
}
.m-card-link {
  border: none;
  background: none;
  color: #0d6bff;
  font-size: 12px;
  cursor: pointer;
  padding: 0;
}

.m-diagnosis-list {
  display: flex;
  flex-direction: column;
}
.m-diagnosis-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0;
  cursor: pointer;
}
.m-diagnosis-item:active {
  background: #f8faff;
  margin: 0 -16px;
  padding-left: 16px;
  padding-right: 16px;
}
.m-diagnosis-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}
.m-diagnosis-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-diag-green { background: rgba(22, 191, 120, 0.12); color: #16bf78; }
.m-diag-red { background: rgba(255, 82, 82, 0.12); color: #ff5252; }
.m-diag-orange { background: rgba(255, 159, 34, 0.12); color: #ff9f22; }
.m-diag-unknown { background: rgba(140, 152, 174, 0.15); color: #64748b; }
.m-diagnosis-info {
  flex: 1;
  min-width: 0;
}
.m-diagnosis-name {
  font-size: 14px;
  font-weight: 600;
  color: #15213d;
  margin-bottom: 2px;
}
.m-diagnosis-desc {
  font-size: 12px;
  color: #8c98ae;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-diagnosis-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.m-diagnosis-badge {
  font-size: 12px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 100px;
}
.m-diagnosis-arrow {
  color: #b0bbd0;
}
.m-diagnosis-divider {
  height: 1px;
  background: #f4f7fc;
}

.m-profile-stats {
  display: flex;
  align-items: center;
  background: #fff;
  border: 1px solid #edf1f7;
  border-radius: 8px;
  padding: 10px 0;
  margin-bottom: 0;
}
.m-profile-stat {
  flex: 1;
  text-align: center;
}
.m-profile-stat-val {
  font-size: 16px;
  font-weight: 800;
  color: #15213d;
  margin-bottom: 2px;
}
.m-profile-stat-label {
  font-size: 11px;
  color: #8c98ae;
}
.m-profile-stat-divider {
  width: 1px;
  height: 28px;
  background: #e5ebf5;
}

.m-profile-extra {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0;
  margin-bottom: 12px;
  padding-top: 10px;
  border-top: 1px solid #edf1f7;
}
.m-extra-row {
  min-width: 0;
  padding: 0 5px;
  text-align: center;
}
.m-extra-label, .m-extra-val {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-extra-label { font-size: 10px; color: #8c98ae; }
.m-extra-val { margin-top: 4px; font-size: 12px; font-weight: 600; color: #15213d; }
.m-credit-excellent { color: #16bf78; }
.m-credit-good { color: #0d6bff; }
.m-credit-poor { color: #ff9f22; }

.m-profile-id {
  font-size: 12px;
  color: #8c98ae;
  text-align: center;
  padding-top: 12px;
  border-top: 1px solid #f4f7fc;
}

.m-quick-actions-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 8px;
}
.m-quick-action-item {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 42px;
  padding: 9px 10px;
  background: #fff;
  border: 1px solid #e7edf8;
  border-radius: 8px;
  cursor: pointer;
  text-align: left;
}
.m-quick-action-item:active {
  background: #f4f7fc;
}
.m-quick-action-item:disabled {
  opacity: 0.6;
  pointer-events: none;
}
.m-quick-action-icon {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-quick-action-name {
  flex: 1;
  font-size: 13px;
  font-weight: 600;
  color: #15213d;
}
.m-quick-action-status {
  font-size: 11px;
  color: #8c98ae;
}
.m-quick-action-arrow {
  color: #b0bbd0;
  flex-shrink: 0;
}
.m-quick-action-full {
  width: 100%;
}
.m-action-loading {
  pointer-events: none;
}
.m-icon-spin {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@media (max-width: 360px) {
  .m-profile-extra { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 0; }
}

.m-safe-bottom { height: 100px; }

.m-detail-skeleton {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.m-skeleton-profile {
  background: white;
  border-radius: 14px;
  padding: 16px;
  display: flex;
  gap: 14px;
}
.m-skeleton-avatar-lg {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: linear-gradient(90deg, #f0f4fa 25%, #e8edf5 50%, #f0f4fa 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  flex-shrink: 0;
}
.m-skeleton-profile-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 8px;
}
.m-skeleton-card {
  background: white;
  border-radius: 14px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.m-skeleton-line {
  height: 14px;
  border-radius: 4px;
  background: linear-gradient(90deg, #f0f4fa 25%, #e8edf5 50%, #f0f4fa 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
.m-skeleton-line-xl { width: 50%; height: 20px; }
.m-skeleton-line-lg { width: 40%; }
.m-skeleton-line-md { width: 30%; }
.m-skeleton-line-sm { width: 70%; }
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.m-not-found {
  text-align: center;
  padding: 80px 20px;
}
.m-not-found-icon {
  width: 80px;
  height: 80px;
  margin: 0 auto 16px;
  border-radius: 50%;
  background: #fee2e2;
  color: #ef4444;
  display: flex;
  align-items: center;
  justify-content: center;
}
.m-not-found-text {
  font-size: 16px;
  font-weight: 600;
  color: #15213d;
  margin-bottom: 20px;
}
.m-not-found-btn {
  padding: 12px 32px;
  border-radius: 100px;
  border: none;
  background: linear-gradient(135deg, #0d6bff, #2580ff);
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.m-menu-overlay {
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
.m-more-menu {
  background: white;
  border-radius: 20px 20px 0 0;
  width: 100%;
  max-width: 500px;
  padding: 12px;
  padding-bottom: calc(12px + env(safe-area-inset-bottom, 0px));
  animation: slideUp 0.3s ease;
}
@keyframes slideUp {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}
.m-more-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border: none;
  background: none;
  font-size: 15px;
  color: #15213d;
  cursor: pointer;
  border-radius: 12px;
}
.m-more-item:active {
  background: #f4f7fc;
}
.m-more-item :deep(svg) { color: #64748b; }
.m-more-item-danger {
  color: #ef4444;
}
.m-more-item-danger :deep(svg) { color: #ef4444; }
.m-more-item-cancel {
  justify-content: center;
  color: #8c98ae;
  font-weight: 500;
  margin-top: 8px;
  background: #f4f7fc;
}
.m-more-divider {
  height: 1px;
  background: #f4f7fc;
  margin: 8px 0;
}

.m-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 1100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}
.m-edit-modal, .m-cookie-modal, .m-confirm-modal, .m-qr-modal {
  background: white;
  border-radius: 20px;
  width: 100%;
  max-width: 360px;
  animation: fadeIn 0.2s ease;
}
@keyframes fadeIn {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}
.m-edit-header, .m-cookie-header, .m-qr-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid #f0f4fa;
}
.m-edit-header h3, .m-cookie-header h3, .m-qr-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #15213d;
}
.m-cookie-close, .m-qr-close {
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
.m-edit-body, .m-cookie-body {
  padding: 16px;
}
.m-edit-input {
  width: 100%;
  height: 44px;
  border: 1px solid #e5ebf5;
  border-radius: 12px;
  padding: 0 14px;
  font-size: 14px;
  color: #15213d;
  box-sizing: border-box;
  outline: none;
}
.m-edit-input:focus {
  border-color: #0d6bff;
}
.m-cookie-warning {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #f59e0b;
  margin: 0 0 12px;
}
.m-cookie-textarea {
  width: 100%;
  border: 1px solid #e5ebf5;
  border-radius: 12px;
  padding: 12px;
  font-size: 13px;
  color: #15213d;
  box-sizing: border-box;
  outline: none;
  resize: vertical;
  font-family: inherit;
}
.m-cookie-textarea:focus {
  border-color: #0d6bff;
}
.m-edit-footer, .m-cookie-footer {
  display: flex;
  gap: 10px;
  padding: 16px;
  border-top: 1px solid #f0f4fa;
}
.m-edit-btn, .m-cookie-btn {
  flex: 1;
  height: 44px;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  border: none;
}
.m-edit-btn-cancel, .m-cookie-btn-cancel {
  background: #f4f7fc;
  color: #64748b;
}
.m-edit-btn-confirm, .m-cookie-btn-confirm {
  background: linear-gradient(135deg, #0d6bff, #2580ff);
  color: white;
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

.m-confirm-modal {
  padding: 24px;
  text-align: center;
  max-width: 320px;
}
.m-confirm-icon {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  margin: 0 auto 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.m-confirm-icon-warning {
  background: #fef3c7;
  color: #d97706;
}
.m-confirm-icon-danger {
  background: #fee2e2;
  color: #ef4444;
}
.m-confirm-title {
  margin: 0 0 8px;
  font-size: 17px;
  font-weight: 700;
  color: #15213d;
}
.m-confirm-desc {
  margin: 0 0 20px;
  font-size: 13px;
  color: #64748b;
  line-height: 1.5;
}
.m-confirm-btns {
  display: flex;
  gap: 10px;
}
.m-confirm-btn {
  flex: 1;
  height: 44px;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  border: none;
}
.m-confirm-btn-cancel {
  background: #f4f7fc;
  color: #64748b;
}
.m-confirm-btn-primary {
  background: linear-gradient(135deg, #0d6bff, #2580ff);
  color: white;
}
.m-confirm-btn-danger {
  background: linear-gradient(135deg, #ef4444, #f87171);
  color: white;
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
.m-toast-info {
  background: rgba(100, 116, 139, 0.95);
  color: white;
}
</style>
