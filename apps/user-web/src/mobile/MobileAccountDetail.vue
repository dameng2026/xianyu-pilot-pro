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

    <div v-if="showFaceVerifyModal" class="m-modal-overlay" @click="closeFaceVerifyModal">
      <div class="m-face-modal" @click.stop>
        <div class="m-face-header">
          <h3>人脸验证提醒</h3>
          <button class="m-face-close" @click="closeFaceVerifyModal">
            <MIcon name="x" :size="20" />
          </button>
        </div>
        <div class="m-face-body">
          <div v-if="faceVerifyLoading" class="m-face-loading">
            <div class="m-qr-spinner"></div>
            <p>正在加载验证提醒...</p>
          </div>
          <div v-else-if="faceVerifyError" class="m-face-error">
            <MIcon name="alertCircle" :size="36" class="m-qr-error-icon" />
            <p>{{ faceVerifyError }}</p>
          </div>
          <div v-else-if="faceVerifyItems.length === 0" class="m-face-empty">
            <MIcon name="shieldCheck" :size="40" class="m-face-empty-icon" />
            <p>暂无待处理的人机验证</p>
            <span>当前账号最近没有新的验证提醒</span>
          </div>
          <div v-else class="m-face-list">
            <article
              v-for="item in faceVerifyItems"
              :key="item.id"
              class="m-face-item"
              :class="{ read: Number(item.readFlag) === 1 }"
            >
              <div class="m-face-item-head">
                <strong>{{ item.title || '人机验证提醒' }}</strong>
                <span class="m-face-badge" :class="Number(item.readFlag) === 1 ? 'm-face-badge-read' : 'm-face-badge-pending'">
                  {{ Number(item.readFlag) === 1 ? '已读' : '待处理' }}
                </span>
              </div>
              <p class="m-face-item-content">{{ item.content || '请尽快回到闲鱼完成验证。' }}</p>
              <div class="m-face-item-foot">
                <span class="m-face-item-time">{{ item.createdTime || item.time || '' }}</span>
                <button
                  class="m-face-mark-btn"
                  :disabled="faceVerifyMarkingId === item.id || Number(item.readFlag) === 1"
                  @click="markFaceVerificationRead(item)"
                >
                  {{ faceVerifyMarkingId === item.id ? '处理中...' : (Number(item.readFlag) === 1 ? '已标记' : '标记已读') }}
                </button>
              </div>
            </article>
          </div>
        </div>
        <div class="m-face-footer">
          <button class="m-face-btn m-face-btn-cancel" @click="closeFaceVerifyModal">关闭</button>
          <button class="m-face-btn m-face-btn-refresh" :disabled="faceVerifyLoading" @click="faceVerify">刷新</button>
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
  updateAccountCookie,
  checkAccountAuth,
  getAccountFaceVerifications,
  markAccountFaceVerificationRead
} from '../api/accounts.js'
import { refreshItems } from '../api/items.js'
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

const showFaceVerifyModal = ref(false)
const faceVerifyLoading = ref(false)
const faceVerifyError = ref('')
const faceVerifyItems = ref([])
const faceVerifyMarkingId = ref(null)

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

async function handleDiagnosisClick(type) {
  if (!account.value?.id) return
  if (type === 'ws') {
    showToast('消息连接的启停与诊断请在桌面端进行', 'info')
    return
  }
  if (type === 'cookie' || type === 'verify') {
    showToast('正在校验登录状态...', 'info')
    try {
      const res = await checkAccountAuth(account.value.id)
      const data = res?.data || res || {}
      const message = data.loginStatusMessage || data.login_status_message
      const usable = data.usable === true
      const cookieStatus = Number(data.cookieStatus ?? data.cookie_status)
      if (type === 'cookie') {
        if (message) {
          showToast(message, usable ? 'success' : 'error')
        } else if (cookieStatus === 1) {
          showToast('Cookie 有效，可正常同步商品和接收消息', 'success')
        } else if (cookieStatus === 0) {
          showToast('Cookie 已失效，请重新扫码登录', 'error')
        } else if (cookieStatus === 2) {
          showToast('Cookie 即将过期，建议重新扫码', 'info')
        } else {
          showToast('Cookie 状态未知，请刷新资料后重试', 'info')
        }
      } else {
        const needVerify = account.value.needVerify || account.value.needFaceVerify
        if (needVerify) {
          showToast(message || '账号需要完成人脸/人机验证，请前往闲鱼 APP 处理', 'info')
        } else if (usable) {
          showToast('账号验证通过，可正常进行发布等操作', 'success')
        } else {
          showToast(message || '账号验证未通过，请重新登录', 'error')
        }
      }
      await loadAccount()
    } catch (error) {
      showToast(error?.message || '登录校验失败', 'error')
    }
  }
}

function viewFullProfile() {
  const acc = account.value
  if (!acc) return
  const userId = acc.externalUid || acc.unb || acc.uid
  if (!userId) {
    showToast('未获取到闲鱼用户ID，无法打开主页', 'error')
    return
  }
  const url = `https://www.goofish.com/personal?userId=${userId}`
  window.open(url, '_blank', 'noopener,noreferrer')
}

async function markFaceVerificationRead(item) {
  if (!item?.id || faceVerifyMarkingId.value) return
  faceVerifyMarkingId.value = item.id
  try {
    await markAccountFaceVerificationRead(item.id)
    item.readFlag = 1
    showToast('已标记已读', 'success')
  } catch (error) {
    showToast(error?.message || '标记已读失败', 'error')
  } finally {
    faceVerifyMarkingId.value = null
  }
}

function closeFaceVerifyModal() {
  showFaceVerifyModal.value = false
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

async function syncProducts() {
  if (!account.value?.id) return
  showToast('正在提交同步任务...', 'info')
  try {
    await refreshItems({ xianyuAccountId: Number(account.value.id) })
    showToast('已开始同步，请稍后查看商品列表', 'success')
  } catch (error) {
    showToast(error?.message || '同步请求失败', 'error')
  }
}

function goAutoDelivery() {
  emit('navigate', 'auto-delivery')
}

async function faceVerify() {
  if (!account.value?.id) return
  showFaceVerifyModal.value = true
  faceVerifyLoading.value = true
  faceVerifyError.value = ''
  faceVerifyItems.value = []
  faceVerifyMarkingId.value = null
  try {
    const res = await getAccountFaceVerifications({ accountId: account.value.id, current: 1, size: 20 })
    const data = res?.data || res
    let records = []
    if (Array.isArray(data)) {
      records = data
    } else if (data && typeof data === 'object') {
      for (const key of ['records', 'items', 'list', 'rows']) {
        if (Array.isArray(data[key])) {
          records = data[key]
          break
        }
      }
    }
    faceVerifyItems.value = records
    if (records.length === 0) {
      showToast('暂无人脸验证任务', 'info')
    }
  } catch (error) {
    faceVerifyError.value = error?.message || '加载人脸验证提醒失败'
    showToast(faceVerifyError.value, 'error')
  } finally {
    faceVerifyLoading.value = false
  }
}

function openMessageGuard() {
  showToast('消息守护配置请在桌面端进行', 'info')
}

function openMoreMenu() {
  showMoreMenu.value = true
}

function setAsCurrent() {
  showMoreMenu.value = false
  showToast('当前账号由系统自动选择，暂不支持手动设置', 'info')
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
  if (showQrModal.value || showMoreMenu.value || showEditNoteModal.value || showCookieModal.value || showConfirmDialog.value || showFaceVerifyModal.value) {
    document.body.style.overflow = ''
  }
})

defineExpose({ openMoreMenu })
</script>

<style scoped>
.m-account-detail {
  padding: var(--m-space-3) var(--m-space-4) 0;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
}

.m-expired-notice {
  background: var(--m-color-warning-bg);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3) var(--m-space-4);
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
  margin-bottom: var(--m-space-3);
  cursor: pointer;
  color: var(--m-color-warning-text);
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-medium);
}
.m-expired-notice :deep(svg) { flex-shrink: 0; }
.m-expired-notice span { flex: 1; }
.m-notice-arrow { margin-left: auto; }

.m-profile-card {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-4);
  box-shadow: var(--m-shadow-card);
  border: 1px solid var(--m-color-border-light);
  margin-bottom: var(--m-space-3);
}
.m-profile-header {
  display: flex;
  gap: var(--m-space-4);
  align-items: flex-start;
}
.m-profile-avatar {
  width: 64px;
  height: 64px;
  border-radius: var(--m-radius-circle);
  overflow: hidden;
  flex-shrink: 0;
  background: var(--m-color-bg-subtle);
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
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
}
.m-profile-info {
  flex: 1;
  min-width: 0;
}
.m-profile-name-row {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-2);
}
.m-profile-name {
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
}
.m-profile-current-tag {
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-semibold);
  padding: var(--m-space-1) var(--m-space-2);
  border-radius: var(--m-radius-sm);
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
  flex-shrink: 0;
}
.m-profile-uid-row {
  display: flex;
  align-items: center;
  gap: var(--m-space-1);
  margin-bottom: var(--m-space-2);
}
.m-profile-uid {
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-tertiary);
}
.m-uid-copy-btn {
  width: 22px;
  height: 22px;
  border-radius: var(--m-radius-sm);
  border: none;
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
}
.m-profile-status-row {
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
}
.m-profile-status {
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-1);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-semibold);
}
.m-status-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--m-radius-circle);
}
.m-dot-green { background: var(--m-color-success); }
.m-dot-red { background: var(--m-color-danger); }
.m-dot-orange { background: var(--m-color-warning); }
.m-dot-gray { background: var(--m-color-text-tertiary); }
.m-status-green { color: var(--m-color-success); }
.m-status-red { color: var(--m-color-danger); }
.m-status-orange { color: var(--m-color-warning); }
.m-status-gray { color: var(--m-color-text-tertiary); }
.m-profile-ws {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-secondary);
}
.m-ws-online { color: var(--m-color-success); }
.m-ws-offline { color: var(--m-color-text-tertiary); }
.m-ws-unknown { color: var(--m-color-text-secondary); }

.m-detail-card {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-4);
  box-shadow: var(--m-shadow-card);
  border: 1px solid var(--m-color-border);
  margin-bottom: var(--m-space-3);
}
.m-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--m-space-4);
}
.m-card-title {
  margin: 0;
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
}
.m-card-link {
  border: none;
  background: none;
  color: var(--m-color-primary);
  font-size: var(--m-font-size-caption);
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
  padding: var(--m-space-3) 0;
  cursor: pointer;
}
.m-diagnosis-item:active {
  background: var(--m-color-bg-hover);
  margin: 0 calc(var(--m-space-4) * -1);
  padding-left: var(--m-space-4);
  padding-right: var(--m-space-4);
}
.m-diagnosis-left {
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
  flex: 1;
  min-width: 0;
}
.m-diagnosis-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--m-radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-diag-green { background: var(--m-color-success-bg); color: var(--m-color-success); }
.m-diag-red { background: var(--m-color-danger-bg); color: var(--m-color-danger); }
.m-diag-orange { background: var(--m-color-warning-bg); color: var(--m-color-warning); }
.m-diag-unknown { background: var(--m-color-bg-subtle); color: var(--m-color-text-secondary); }
.m-diagnosis-info {
  flex: 1;
  min-width: 0;
}
.m-diagnosis-name {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  margin-bottom: var(--m-space-1);
}
.m-diagnosis-desc {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-diagnosis-right {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  flex-shrink: 0;
}
.m-diagnosis-badge {
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-semibold);
  padding: var(--m-space-1) var(--m-space-2);
  border-radius: var(--m-radius-pill);
}
.m-diagnosis-arrow {
  color: var(--m-color-text-disabled);
}
.m-diagnosis-divider {
  height: 1px;
  background: var(--m-color-border-light);
}

.m-profile-stats {
  display: flex;
  align-items: center;
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-md);
  padding: var(--m-space-3) 0;
  margin-bottom: 0;
}
.m-profile-stat {
  flex: 1;
  text-align: center;
}
.m-profile-stat-val {
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-extrabold);
  color: var(--m-color-text-primary);
  margin-bottom: var(--m-space-1);
}
.m-profile-stat-label {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}
.m-profile-stat-divider {
  width: 1px;
  height: 28px;
  background: var(--m-color-border);
}

.m-profile-extra {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0;
  margin-bottom: var(--m-space-3);
  padding-top: var(--m-space-3);
  border-top: 1px solid var(--m-color-border-light);
}
.m-extra-row {
  min-width: 0;
  padding: 0 var(--m-space-1);
  text-align: center;
}
.m-extra-label, .m-extra-val {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-extra-label { font-size: var(--m-font-size-tiny); color: var(--m-color-text-tertiary); }
.m-extra-val { margin-top: var(--m-space-1); font-size: var(--m-font-size-caption); font-weight: var(--m-font-weight-semibold); color: var(--m-color-text-primary); }
.m-credit-excellent { color: var(--m-color-success); }
.m-credit-good { color: var(--m-color-primary); }
.m-credit-poor { color: var(--m-color-warning); }

.m-profile-id {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  text-align: center;
  padding-top: var(--m-space-3);
  border-top: 1px solid var(--m-color-border-light);
}

.m-quick-actions-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-2);
}
.m-quick-action-item {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  min-height: 42px;
  padding: var(--m-space-2) var(--m-space-3);
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-md);
  cursor: pointer;
  text-align: left;
}
.m-quick-action-item:active {
  background: var(--m-color-bg-subtle);
}
.m-quick-action-item:disabled {
  opacity: 0.6;
  pointer-events: none;
}
.m-quick-action-icon {
  width: 28px;
  height: 28px;
  border-radius: var(--m-radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-quick-action-name {
  flex: 1;
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
}
.m-quick-action-status {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}
.m-quick-action-arrow {
  color: var(--m-color-text-disabled);
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
  .m-profile-extra { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--m-space-3) 0; }
}

.m-safe-bottom { height: calc(var(--m-space-12) + var(--m-space-8) + var(--m-safe-area-bottom)); }

.m-detail-skeleton {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-3);
}
.m-skeleton-profile {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-4);
  display: flex;
  gap: var(--m-space-4);
}
.m-skeleton-avatar-lg {
  width: 64px;
  height: 64px;
  border-radius: var(--m-radius-circle);
  background: linear-gradient(90deg, var(--m-color-bg-subtle) 25%, var(--m-color-border-light) 50%, var(--m-color-bg-subtle) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  flex-shrink: 0;
}
.m-skeleton-profile-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
  padding-top: var(--m-space-2);
}
.m-skeleton-card {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-4);
  display: flex;
  flex-direction: column;
  gap: var(--m-space-3);
}
.m-skeleton-line {
  height: 14px;
  border-radius: var(--m-radius-sm);
  background: linear-gradient(90deg, var(--m-color-bg-subtle) 25%, var(--m-color-border-light) 50%, var(--m-color-bg-subtle) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
.m-skeleton-line-xl { width: 50%; height: var(--m-space-5); }
.m-skeleton-line-lg { width: 40%; }
.m-skeleton-line-md { width: 30%; }
.m-skeleton-line-sm { width: 70%; }
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.m-not-found {
  text-align: center;
  padding: calc(var(--m-space-10) * 2) var(--m-space-5);
}
.m-not-found-icon {
  width: 80px;
  height: 80px;
  margin: 0 auto var(--m-space-4);
  border-radius: var(--m-radius-circle);
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger);
  display: flex;
  align-items: center;
  justify-content: center;
}
.m-not-found-text {
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  margin-bottom: var(--m-space-5);
}
.m-not-found-btn {
  padding: var(--m-space-3) var(--m-space-8);
  border-radius: var(--m-radius-pill);
  border: none;
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
}

.m-menu-overlay {
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
.m-more-menu {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-2xl) var(--m-radius-2xl) 0 0;
  width: 100%;
  max-width: 500px;
  padding: var(--m-space-3);
  padding-bottom: calc(var(--m-space-3) + var(--m-safe-area-bottom));
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
  gap: var(--m-space-3);
  padding: var(--m-space-4);
  border: none;
  background: none;
  font-size: var(--m-font-size-h3);
  color: var(--m-color-text-primary);
  cursor: pointer;
  border-radius: var(--m-radius-lg);
}
.m-more-item:active {
  background: var(--m-color-bg-subtle);
}
.m-more-item :deep(svg) { color: var(--m-color-text-secondary); }
.m-more-item-danger {
  color: var(--m-color-danger);
}
.m-more-item-danger :deep(svg) { color: var(--m-color-danger); }
.m-more-item-cancel {
  justify-content: center;
  color: var(--m-color-text-tertiary);
  font-weight: var(--m-font-weight-medium);
  margin-top: var(--m-space-2);
  background: var(--m-color-bg-subtle);
}
.m-more-divider {
  height: 1px;
  background: var(--m-color-border-light);
  margin: var(--m-space-2) 0;
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
.m-edit-modal, .m-cookie-modal, .m-confirm-modal, .m-qr-modal {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-2xl);
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
  padding: var(--m-space-4);
  border-bottom: 1px solid var(--m-color-border-light);
}
.m-edit-header h3, .m-cookie-header h3, .m-qr-header h3 {
  margin: 0;
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
}
.m-cookie-close, .m-qr-close {
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
}
.m-edit-body, .m-cookie-body {
  padding: var(--m-space-4);
}
.m-edit-input {
  width: 100%;
  height: 44px;
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-lg);
  padding: 0 var(--m-space-4);
  font-size: var(--m-font-size-body);
  color: var(--m-color-text-primary);
  box-sizing: border-box;
  outline: none;
}
.m-edit-input:focus {
  border-color: var(--m-color-primary);
}
.m-cookie-warning {
  display: flex;
  align-items: center;
  gap: var(--m-space-1);
  font-size: var(--m-font-size-caption);
  color: var(--m-color-warning-text);
  margin: 0 0 var(--m-space-3);
}
.m-cookie-textarea {
  width: 100%;
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3);
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-primary);
  box-sizing: border-box;
  outline: none;
  resize: vertical;
  font-family: inherit;
}
.m-cookie-textarea:focus {
  border-color: var(--m-color-primary);
}
.m-edit-footer, .m-cookie-footer {
  display: flex;
  gap: var(--m-space-3);
  padding: var(--m-space-4);
  border-top: 1px solid var(--m-color-border-light);
}
.m-edit-btn, .m-cookie-btn {
  flex: 1;
  height: 44px;
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  border: none;
}
.m-edit-btn-cancel, .m-cookie-btn-cancel {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
}
.m-edit-btn-confirm, .m-cookie-btn-confirm {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
}

.m-qr-loading, .m-qr-error {
  padding: var(--m-space-10) var(--m-space-5);
  text-align: center;
}
.m-qr-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--m-color-border);
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
  padding: var(--m-space-3) var(--m-space-6);
  border-radius: var(--m-radius-pill);
  border: none;
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
}
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
  border: 2px solid var(--m-color-border-light);
  border-radius: var(--m-radius-lg);
}
.m-qr-code {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.m-qr-tip {
  margin: 0 0 var(--m-space-2);
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
}
.m-qr-status {
  margin: 0;
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}

.m-confirm-modal {
  padding: var(--m-space-6);
  text-align: center;
  max-width: 320px;
}
.m-confirm-icon {
  width: 56px;
  height: 56px;
  border-radius: var(--m-radius-circle);
  margin: 0 auto var(--m-space-4);
  display: flex;
  align-items: center;
  justify-content: center;
}
.m-confirm-icon-warning {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning-text);
}
.m-confirm-icon-danger {
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger);
}
.m-confirm-title {
  margin: 0 0 var(--m-space-2);
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
}
.m-confirm-desc {
  margin: 0 0 var(--m-space-5);
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-secondary);
  line-height: var(--m-line-height-base);
}
.m-confirm-btns {
  display: flex;
  gap: var(--m-space-3);
}
.m-confirm-btn {
  flex: 1;
  height: 44px;
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  border: none;
}
.m-confirm-btn-cancel {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
}
.m-confirm-btn-primary {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
}
.m-confirm-btn-danger {
  background: var(--m-color-danger);
  color: var(--m-color-text-inverse);
}

.m-toast {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  padding: var(--m-space-3) var(--m-space-6);
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-medium);
  z-index: 2000;
  animation: toastIn 0.2s ease;
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
.m-toast-info {
  background: var(--m-color-text-secondary);
  color: var(--m-color-text-inverse);
}

.m-face-modal {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-2xl);
  width: 100%;
  max-width: 380px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  animation: fadeIn 0.2s ease;
}
.m-face-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-space-4);
  border-bottom: 1px solid var(--m-color-border-light);
}
.m-face-header h3 {
  margin: 0;
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
}
.m-face-close {
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
}
.m-face-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--m-space-4);
}
.m-face-loading, .m-face-error, .m-face-empty {
  text-align: center;
  padding: var(--m-space-8) var(--m-space-5);
}
.m-face-loading p, .m-face-error p {
  margin: var(--m-space-3) 0 0;
  font-size: var(--m-font-size-body);
  color: var(--m-color-text-secondary);
}
.m-face-empty-icon {
  color: var(--m-color-success);
  margin-bottom: var(--m-space-2);
}
.m-face-empty p {
  margin: 0 0 var(--m-space-1);
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
}
.m-face-empty span {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}
.m-face-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-3);
}
.m-face-item {
  background: var(--m-color-bg-hover);
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3);
}
.m-face-item.read {
  background: var(--m-color-bg-subtle);
  opacity: 0.7;
}
.m-face-item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--m-space-2);
  gap: var(--m-space-2);
}
.m-face-item-head strong {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-face-badge {
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-semibold);
  padding: var(--m-space-1) var(--m-space-2);
  border-radius: var(--m-radius-pill);
  flex-shrink: 0;
}
.m-face-badge-pending {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning);
}
.m-face-badge-read {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-tertiary);
}
.m-face-item-content {
  margin: 0 0 var(--m-space-2);
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-secondary);
  line-height: var(--m-line-height-base);
}
.m-face-item-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--m-space-2);
}
.m-face-item-time {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-disabled);
}
.m-face-mark-btn {
  border: none;
  background: none;
  color: var(--m-color-primary);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  padding: var(--m-space-1) var(--m-space-2);
}
.m-face-mark-btn:disabled {
  color: var(--m-color-text-disabled);
  cursor: not-allowed;
}
.m-face-footer {
  display: flex;
  gap: var(--m-space-3);
  padding: var(--m-space-4);
  border-top: 1px solid var(--m-color-border-light);
}
.m-face-btn {
  flex: 1;
  height: 44px;
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  border: none;
}
.m-face-btn-cancel {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
}
.m-face-btn-refresh {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
}
.m-face-btn-refresh:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
