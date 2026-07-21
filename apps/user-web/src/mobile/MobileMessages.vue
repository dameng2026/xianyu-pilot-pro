<template>
  <div class="m-msg" :class="{ 'm-msg-chat-open': activeChat }">
    <!-- 会话列表视图 -->
    <template v-if="!activeChat">
      <div class="m-page-header">
        <h1>消息</h1>
        <p class="m-page-sub">买家会话与消息通知</p>
      </div>

      <!-- 账号筛选 -->
      <div v-if="accounts.length > 1" class="m-account-chips">
        <button
          class="m-chip"
          :class="{ active: selectedAccountId === '' }"
          @click="selectAccount('')"
        >
          全部账号
        </button>
        <button
          v-for="acc in accounts"
          :key="acc.id"
          class="m-chip"
          :class="{ active: selectedAccountId === String(acc.id) }"
          @click="selectAccount(String(acc.id))"
        >
          <span class="m-chip-dot" :class="{ online: acc.wsStatus === 'online' }"></span>
          {{ acc.remark || acc.nickname || acc.uid || `账号${acc.id}` }}
        </button>
      </div>

      <label class="m-msg-search">
        <MIcon name="search" :size="20" />
        <input v-model="searchKeyword" type="search" placeholder="搜索买家、商品或消息内容" aria-label="搜索会话" />
      </label>

      <!-- 会话筛选 Tab -->
      <div class="m-filter-tabs">
        <button
          v-for="tab in filterTabs"
          :key="tab.key"
          class="m-filter-tab"
          :class="{ active: filterType === tab.key }"
          @click="filterType = tab.key"
        >
          {{ tab.label }}
          <span v-if="tab.count > 0" class="m-filter-count">{{ tab.count }}</span>
        </button>
      </div>

      <!-- 保留天数提示 -->
      <div v-if="retentionNotice" class="m-retention-notice">
        <MIcon name="info" :size="14" />
        <span>{{ retentionNotice }}</span>
      </div>

      <!-- 加载状态 -->
      <div v-if="loading" class="m-loading" role="status" aria-live="polite">
        <div class="m-loading-spinner"></div>
        <span>正在加载会话...</span>
      </div>

      <MobileUnavailableState v-else-if="loadError" title="会话列表暂时无法加载" :description="loadError" @retry="reloadConversations" />

      <!-- 空状态 -->
      <div v-else-if="filteredConversations.length === 0" class="m-empty">
        <div class="m-empty-icon">
          <MIcon name="chat" :size="48" />
        </div>
        <div class="m-empty-text">{{ emptyText }}</div>
        <div class="m-empty-desc">当买家发来消息时，会在这里显示</div>
      </div>

      <!-- 会话列表 -->
      <div v-else class="m-msg-list">
	        <div
	            v-for="conv in filteredConversations"
          :key="getConversationIdentityKey(conv) || conv.id || conv.sid"
          class="m-msg-item"
          @click="openConversation(conv)"
        >
          <div class="m-msg-avatar" :class="{ 'is-robot': conv.botEnabled }">
            <MIcon :name="conv.botEnabled ? 'bot' : 'user'" :size="22" />
            <span v-if="conv.unreadCount > 0" class="m-msg-dot"></span>
          </div>
          <div class="m-msg-body">
            <div class="m-msg-top">
              <span class="m-msg-name">{{ resolvePeerName(conv) }}</span>
              <span class="m-msg-time">{{ formatTime(conv.lastMessageTime || conv.updatedAt) }}</span>
            </div>
	            <div class="m-msg-bottom">
	              <span class="m-msg-preview">
	                <span v-if="conv.lastIsAutoReply" class="m-ai-badge inline">AI</span>
	                {{ conv.lastMessage || conv.lastContent || conv.product || '暂无消息内容' }}
	              </span>
	              <span v-if="conv.unreadCount > 0" class="m-msg-badge">{{ conv.unreadCount > 99 ? '99+' : conv.unreadCount }}</span>
	              <span v-else-if="isCompleted(conv)" class="m-msg-status m-msg-status-done">已完成</span>
	            </div>
            <div v-if="conv.goodsTitle || conv.product" class="m-msg-goods">
              <MIcon name="bag" :size="12" /> {{ conv.goodsTitle || conv.product }}
            </div>
          </div>
        </div>
        <div class="m-msg-list-total">共 {{ filteredConversations.length }} 条会话</div>
      </div>

      <div class="m-msg-tip">
        <MIcon name="shield" :size="16" />
        <span>复杂消息操作建议在桌面版进行</span>
        <button class="m-tip-btn" @click="$emit('force-desktop')">桌面版</button>
      </div>
    </template>

    <!-- 聊天详情视图 -->
    <template v-else>
      <div class="m-chat-header">
        <button class="m-chat-back" @click="closeChat">
          <MIcon name="chevronLeft" :size="22" />
        </button>
        <div class="m-chat-title">
          <div class="m-chat-name">{{ resolvePeerName(activeChat) }}</div>
          <div v-if="activeChat.goodsTitle || activeChat.product" class="m-chat-goods">
            <MIcon name="bag" :size="11" /> {{ activeChat.goodsTitle || activeChat.product }}
          </div>
        </div>
        <button class="m-chat-more" @click="$emit('force-desktop')">
          <MIcon name="desktop" :size="18" />
        </button>
      </div>

      <div class="m-chat-product-card">
        <div class="m-chat-product-thumb"><MIcon name="bag" :size="26" /></div>
        <div class="m-chat-product-main">
          <strong>{{ activeChat.goodsTitle || activeChat.product || '关联商品' }}</strong>
          <span>ID：{{ activeChat.xyGoodsId || activeChat.goodsId || '--' }}</span>
        </div>
        <div class="m-chat-product-actions">
          <button type="button" class="m-chat-product-secondary" @click="$emit('force-desktop')">查看商品</button>
          <button type="button" class="m-chat-product-primary" @click="$emit('force-desktop')">发送商品</button>
        </div>
      </div>

      <div ref="chatBoxRef" class="m-chat-body">
        <div class="m-chat-day-divider"><span>今天</span></div>
        <div v-if="chatLoading" class="m-chat-loading" role="status" aria-live="polite">
          <div class="m-loading-spinner"></div>
          <span>正在加载消息...</span>
        </div>
        <MobileUnavailableState v-else-if="chatError" compact title="消息记录暂时无法加载" :description="chatError" @retry="loadChatMessages" />
        <div v-else-if="chatMessages.length === 0" class="m-chat-empty">
          <MIcon name="chat" :size="40" />
          <span>暂无消息记录</span>
        </div>
        <div v-else class="m-chat-list">
          <div
            v-for="msg in chatMessages"
            :key="msg.id || msg.uuid || msg.pnmId"
            class="m-bubble"
            :class="isOutgoing(msg) ? 'out' : 'in'"
	          >
	            <div v-if="!isOutgoing(msg)" class="m-bubble-avatar">
	              <MIcon name="user" :size="18" />
	            </div>
	            <div class="m-bubble-content">
	              <div v-if="msg.isAutoReply" class="m-ai-row" :class="{ out: isOutgoing(msg) }">
	                <span class="m-ai-badge">AI 自动回复</span>
	              </div>
	              <div v-if="msg.imageUrl" class="m-bubble-image-wrap">
	                <img :src="msg.imageUrl" class="m-bubble-image" alt="聊天图片" @click="previewImage(msg.imageUrl)" />
	              </div>
	              <div v-else-if="msg.mediaBlocked" class="m-bubble-media-blocked" role="status">图片地址不受信任，已阻止加载</div>
	              <div v-if="msg.content || msg.text || msg.msgContent || msg.displayText" class="m-bubble-text">{{ msg.content || msg.text || msg.displayText || msg.msgContent }}</div>
	              <div class="m-bubble-time">{{ formatTime(msg.createdAt || msg.timestamp || msg.sendTime || msg.messageTime) }}</div>
	              <div v-if="msg.sendStatus === 'sending'" class="m-bubble-send-state">发送中...</div>
	              <div v-else-if="msg.sendStatus === 'failed'" class="m-bubble-send-state failed">发送失败，请复制内容后重试</div>
	            </div>
	            <div v-if="isOutgoing(msg)" class="m-bubble-avatar out-avatar">
	              <MIcon name="user" :size="18" />
            </div>
          </div>
        </div>
      </div>

      <div class="m-chat-quick-actions">
        <button type="button" @click="$emit('force-desktop')"><MIcon name="image" :size="18" /><span>发送图片</span></button>
        <button type="button" @click="$emit('force-desktop')"><MIcon name="link" :size="18" /><span>发送商品链接</span></button>
        <button
          type="button"
          :class="conversationAutoReplyStatusClass"
          :disabled="aiSwitchLoading || !activeChat"
          @click="toggleConversationAutoReplyState"
        >
          <MIcon name="power" :size="18" />
          <span>{{ conversationAutoReplyButtonText }}</span>
        </button>
      </div>

      <div class="m-chat-compose">
        <div v-if="sendError" class="m-chat-send-error" role="alert">{{ sendError }}</div>
        <button type="button" class="m-chat-attach" @click="$emit('force-desktop')"><MIcon name="plus" :size="20" /></button>
        <textarea
          v-model="draft"
          rows="2"
          placeholder="输入消息，Enter 发送&#10;Shift+Enter 换行"
          :disabled="!!chatError"
          @keydown.enter.exact.prevent="sendCurrentMessage"
        ></textarea>
        <button class="m-chat-send" :disabled="!draft.trim() || sending || !!chatError" @click="sendCurrentMessage">发送</button>
      </div>
    </template>

    <div class="m-safe-bottom"></div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import MIcon from './MIcon.vue'
import MobileUnavailableState from './MobileUnavailableState.vue'
import { getLiteAccounts } from '../api/accounts.js'
import { onlineConversations, messageContext, markConversationRead } from '../api/messages.js'
import { sendMessage } from '../api/websocket.js'
import { getRetentionInfo } from '../api/system.js'
import { openTrustedMediaUrl, resolveTrustedMediaUrl } from '../utils/safeMediaUrl.js'
import {
  toggleConversationAutoReply,
  getConversationAutoReplyStatus,
} from '../api/autoReplyScope.js'
import {
  extractMessageDisplayText,
  findConversationMatchIndex,
  findPreservedConversation,
  getConversationIdentityKey,
  getConversationRecordId,
  isSameConversationByPayload,
  matchesAccountSelection,
  mergeConversationSnapshots,
  parseMessageTimestamp
} from '../utils/messagesPageState.js'

defineEmits(['force-desktop', 'navigate'])

const accounts = ref([])
const conversations = ref([])
const loading = ref(true)
const loadError = ref('')
const selectedAccountId = ref('')
const filterType = ref('all')
const searchKeyword = ref('')

const activeChat = ref(null)
const chatMessages = ref([])
const chatLoading = ref(false)
const chatError = ref('')
const chatBoxRef = ref(null)
const draft = ref('')
const sending = ref(false)
const sendError = ref('')
// 会话级自动回复状态（V1.13 引入，支持人工干预暂停/手动关闭/自动恢复）
// autoReplyPaused: 0=运行中 1=已暂停
// autoReplyManualDisabled: 0=可自动恢复 1=手动关闭（禁止自动恢复，仅用户手动开启）
// runningEnabled: 综合考虑账号级/全局开关 + 会话级暂停后的实际运行状态
const conversationAutoReplyState = ref({
  autoReplyPaused: 0,
  autoReplyManualDisabled: 0,
  lastManualReplyAt: 0,
  lastAutoReplyAt: 0,
  effectiveEnabled: null,
  runningEnabled: null,
  pausedReason: '',
})
const aiSwitchLoading = ref(false)
let pollingTimer = null

// 数据保留策略提示文案（chatMessageCleanupEnabled && retentionDays>0 时展示）
const retentionNotice = ref('')
async function loadRetentionNotice() {
  try {
    const info = await getRetentionInfo()
    if (info && info.chatMessageCleanupEnabled && info.retentionDays > 0) {
      retentionNotice.value = `聊天记录保留 ${info.retentionDays} 天，更早的消息打开会话后可自动加载`
    } else {
      retentionNotice.value = ''
    }
  } catch {
    retentionNotice.value = ''
  }
}

// 本地已读状态管理：记录每个会话用户最后查看时的最新消息时间
// 当服务端轮询返回的会话最后消息时间 <= 本地记录时间时，强制 unreadCount = 0
// 这样无需依赖闲鱼服务端，用户读完消息后小红点立即消失，只有再来新消息才再次显示未读
const READ_STATE_STORAGE_KEY = 'xya-mobile-msg-read-state-v1'

function loadReadStateFromStorage() {
  try {
    const raw = localStorage.getItem(READ_STATE_STORAGE_KEY)
    if (raw) {
      const data = JSON.parse(raw)
      if (data && typeof data === 'object') {
        const map = new Map()
        Object.entries(data).forEach(([key, value]) => {
          const num = Number(value)
          if (Number.isFinite(num) && num > 0) map.set(key, num)
        })
        return map
      }
    }
  } catch {}
  return new Map()
}

function persistReadState(state) {
  try {
    const obj = {}
    state.forEach((value, key) => { obj[key] = value })
    localStorage.setItem(READ_STATE_STORAGE_KEY, JSON.stringify(obj))
  } catch {}
}

const readState = loadReadStateFromStorage()

function getConversationLastMessageTime(conv) {
  return parseMessageTimestamp(
    conv?.lastMessageTime ?? conv?.updatedAt ?? conv?.messageTime ?? conv?.createdAt ?? 0
  )
}

function applyLocalReadState(conv) {
  const convKey = getConversationIdentityKey(conv)
  if (!convKey) return conv
  const lastReadTime = readState.get(convKey)
  if (!lastReadTime) return conv
  const lastMsgTime = getConversationLastMessageTime(conv)
  if (!lastMsgTime) return conv
  // 本地已读时间 >= 会话最后消息时间：会话已被用户查看过且没有新消息
  if (lastReadTime >= lastMsgTime && Number(conv.unreadCount || 0) > 0) {
    return { ...conv, unreadCount: 0 }
  }
  return conv
}

function markConversationReadLocally(conv) {
  const convKey = getConversationIdentityKey(conv)
  if (!convKey) return
  const lastMsgTime = getConversationLastMessageTime(conv) || Date.now()
  readState.set(convKey, lastMsgTime)
  persistReadState(readState)
}

const filterTabs = computed(() => [
  { key: 'all', label: '全部', count: conversations.value.length },
  { key: 'unreplied', label: '未读', count: conversations.value.filter(c => Number(c.unreadCount || 0) > 0).length },
  { key: 'inProgress', label: '进行中', count: conversations.value.filter(c => !isCompleted(c)).length },
  { key: 'completed', label: '已结束', count: conversations.value.filter(c => isCompleted(c)).length }
])

const emptyText = computed(() => {
  if (filterType.value === 'unreplied') return '暂无未回复消息'
  if (filterType.value === 'inProgress') return '暂无进行中会话'
  if (filterType.value === 'completed') return '暂无已完成会话'
  if (filterType.value === 'robot') return '暂无机器人会话'
  return '暂无新消息'
})

const filteredConversations = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()
  return conversations.value.filter(c => {
    if (filterType.value === 'unreplied' && Number(c.unreadCount || 0) <= 0) return false
    if (filterType.value === 'inProgress' && isCompleted(c)) return false
    if (filterType.value === 'completed' && !isCompleted(c)) return false
    if (!keyword) return true
    return [resolvePeerName(c), c.lastMessage, c.lastContent, c.product, c.goodsTitle]
      .some(value => String(value || '').toLowerCase().includes(keyword))
  })
})

function isCompleted(c) {
  return ['completed', 'closed', 'transferred'].includes(c.sessionStatus) || c.closed === true
}

// 会话级自动回复按钮文案（3态：运行中/人工暂停/手动关闭）
const conversationAutoReplyButtonText = computed(() => {
  if (aiSwitchLoading.value) return '处理中...'
  if (!activeChat.value) return '自动回复'
  const state = conversationAutoReplyState.value
  if (state.autoReplyManualDisabled === 1) return '手动关闭·点击开启'
  if (state.autoReplyPaused === 1) return '人工暂停中·点击开启'
  if (state.runningEnabled === true) return '运行中·点击关闭'
  if (state.runningEnabled === false) return '已关闭·点击开启'
  return '自动回复'
})

// 会话级自动回复状态对应的样式 class
const conversationAutoReplyStatusClass = computed(() => {
  const state = conversationAutoReplyState.value
  if (state.autoReplyManualDisabled === 1) return 'm-auto-reply-disabled'
  if (state.autoReplyPaused === 1) return 'm-auto-reply-paused'
  if (state.runningEnabled === true) return 'm-auto-reply-running'
  return 'm-auto-reply-unknown'
})

// 加载会话级自动回复状态（V1.13 引入）
async function loadConversationAutoReplyStatus() {
  const conv = activeChat.value
  if (!conv) {
    conversationAutoReplyState.value = {
      autoReplyPaused: 0,
      autoReplyManualDisabled: 0,
      lastManualReplyAt: 0,
      lastAutoReplyAt: 0,
      effectiveEnabled: null,
      runningEnabled: null,
      pausedReason: '',
    }
    return
  }
  const accountId = Number(conv.xianyuAccountId || conv.accountId || selectedAccountId.value || 0)
  if (!accountId) return
  try {
    const params = { accountId }
    if (conv.sid) params.sid = conv.sid
    if (conv.peerUserId) params.peerUserId = conv.peerUserId
    const res = await getConversationAutoReplyStatus(params)
    const data = res?.data?.data || res?.data
    if (data && typeof data === 'object' && !Array.isArray(data)) {
      conversationAutoReplyState.value = {
        autoReplyPaused: Number(data.autoReplyPaused ?? data.auto_reply_paused ?? 0),
        autoReplyManualDisabled: Number(data.autoReplyManualDisabled ?? data.auto_reply_manual_disabled ?? 0),
        lastManualReplyAt: Number(data.lastManualReplyAt ?? data.last_manual_reply_at ?? 0),
        lastAutoReplyAt: Number(data.lastAutoReplyAt ?? data.last_auto_reply_at ?? 0),
        effectiveEnabled: data.effectiveEnabled ?? data.effective_enabled ?? null,
        runningEnabled: data.runningEnabled ?? data.running_enabled ?? null,
        pausedReason: data.pausedReason || data.paused_reason || '',
      }
    }
  } catch (e) {
    // 会话级状态加载失败不阻塞主流程
    console.warn('[Mobile MSG] loadConversationAutoReplyStatus failed:', e)
  }
}

// 切换会话级自动回复开关
async function toggleConversationAutoReplyState() {
  if (aiSwitchLoading.value) return
  const conv = activeChat.value
  if (!conv) {
    sendError.value = '请先选择会话'
    return
  }
  const accountId = Number(conv.xianyuAccountId || conv.accountId || selectedAccountId.value || 0)
  if (!accountId) {
    sendError.value = '账号信息缺失，无法切换自动回复'
    return
  }
  aiSwitchLoading.value = true
  sendError.value = ''
  try {
    const state = conversationAutoReplyState.value
    const currentRunning = state.runningEnabled === true
    const newValue = !currentRunning
    const payload = { accountId, enabled: newValue }
    if (conv.sid) payload.sid = conv.sid
    if (conv.peerUserId) payload.peerUserId = conv.peerUserId
    await toggleConversationAutoReply(payload)
    await loadConversationAutoReplyStatus()
  } catch (e) {
    sendError.value = e?.message || '自动回复开关更新失败'
  } finally {
    aiSwitchLoading.value = false
  }
}

function normalizeSid(value) {
  const raw = String(value || '').trim()
  if (!raw) return ''
  const sid = raw.startsWith('sid:') ? raw.slice(4) : raw
  return sid.endsWith('@goofish') ? sid.slice(0, -8) : sid
}

function normalizePeerUserId(value) {
  const raw = String(value || '').trim()
  if (!raw || raw.startsWith('sid:')) return ''
  return raw.endsWith('@goofish') ? raw.slice(0, -8) : raw
}

function messageIdentity(message) {
  const pnmId = String(message?.pnmId || message?.messageUid || message?.uuid || '').trim()
  if (pnmId) return `pnm:${pnmId}`
  const id = String(message?.id || '').trim()
  if (id && !id.startsWith('temp_')) return `id:${id}`
  const sid = normalizeSid(message?.sid || message?.sId || '')
  const direction = String(message?.direction || '').toUpperCase()
  const sender = normalizePeerUserId(message?.senderUserId || message?.fromUserId || '')
  const receiver = normalizePeerUserId(message?.receiverUserId || message?.toUserId || '')
  const content = String(message?.content || message?.text || message?.displayText || message?.msgContent || '').trim()
  const messageTime = Number(message?.messageTime || message?.createdAt || message?.timestamp || message?.sendTime || 0)
  return `fallback:${sid}:${direction}:${sender}:${receiver}:${messageTime}:${content}`
}

function dedupeMessages(list) {
  const seen = new Set()
  return (Array.isArray(list) ? list : []).filter(item => {
    const key = messageIdentity(item)
    if (!key || seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function isSameConversation(conv, payload) {
  return isSameConversationByPayload(conv, payload)
}

function resolvePeerName(c) {
  return c.peerUserName || c.buyerName || c.peerName || c.peerNick || (c.peerUserId ? `买家${String(c.peerUserId).slice(-4)}` : '买家')
}

function mapConversationItem(item, fallbackAccountId) {
  return {
    ...item,
    xianyuAccountId: Number(item.xianyuAccountId || item.accountId || fallbackAccountId || 0) || undefined,
    sid: normalizeSid(item.sid || item.sId || item.sessionId || item.conversationId || item.id),
    peerUserId: normalizePeerUserId(item.peerUserId || item.peerExternalUid || item.externalBuyerId || ''),
    lastIsAutoReply: Boolean(item.lastIsAutoReply || item.isAutoReply || item.is_auto_reply),
    botEnabled: Boolean(item.botEnabled || item.hasAiReply || item.lastIsAutoReply)
  }
}

async function fetchConversationBatch(accountId) {
  const res = await onlineConversations(accountId, { pageSize: 100 })
  const list = res?.data?.records || (Array.isArray(res?.data) ? res.data : null)
  if (!Array.isArray(list)) throw new Error('会话列表响应格式异常')
  return list.map(item => mapConversationItem(item, accountId))
}

async function loadAccounts() {
  try {
    const res = await getLiteAccounts({ page: 1, pageSize: 50 })
    const data = res?.data
    const list = data?.records || data?.list || (Array.isArray(data) ? data : null)
    if (!Array.isArray(list)) throw new Error('账号列表响应格式异常')
    accounts.value = list
    return true
  } catch (error) {
    accounts.value = []
    loadError.value = error?.message || '账号列表不可用，无法确定要加载哪些会话。'
    return false
  }
}

async function loadConversations() {
  loading.value = true
  loadError.value = ''
  try {
    const accountIds = selectedAccountId.value
      ? [Number(selectedAccountId.value)]
      : accounts.value
          .map(account => Number(account?.id || 0))
          .filter(accountId => accountId > 0)
    const batches = await Promise.all(accountIds.map(accountId => fetchConversationBatch(accountId)))
    const merged = mergeConversationSnapshots(batches.flat()).filter(item => getConversationIdentityKey(item))
    // 应用本地已读状态：用户已经查看过且没有新消息的会话，强制 unreadCount = 0
    // 防止服务端轮询返回的滞后 unreadCount 覆盖本地已读状态
    conversations.value = merged.map(item => applyLocalReadState(item))
    if (activeChat.value) {
      const nextActive = findPreservedConversation(conversations.value, activeChat.value)
      if (nextActive) {
        activeChat.value = { ...activeChat.value, ...nextActive }
      }
    }
  } catch (error) {
    conversations.value = []
    loadError.value = error?.message || '请检查网络连接后重试。'
  } finally {
    loading.value = false
  }
}

function selectAccount(accId) {
  if (selectedAccountId.value === accId) return
  selectedAccountId.value = accId
  loadConversations()
  if (activeChat.value) {
    closeChat()
  }
  startPolling()
}

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const msgDay = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const diffDays = Math.floor((today - msgDay) / (1000 * 60 * 60 * 24))
  if (diffDays === 0) {
    return `${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`
  }
  if (diffDays === 1) return '昨天'
  if (diffDays < 7) return `${diffDays}天前`
  return `${d.getMonth()+1}/${d.getDate()}`
}

async function openConversation(conv) {
  activeChat.value = conv
  chatMessages.value = []
  chatLoading.value = true
  await nextTick()
  await loadChatMessages()
  // 立即在本地标记为已读（无需依赖服务端 markConversationRead 成功）
  // 这样用户读完消息后小红点立即消失，只有再来新消息才再次显示未读
  markConversationReadLocally(conv)
  if (Number(conv.unreadCount || 0) > 0) {
    conv.unreadCount = 0
    conversations.value = conversations.value.map(item =>
      isSameConversation(item, conv) ? { ...item, unreadCount: 0 } : item
    )
    activeChat.value = { ...activeChat.value, unreadCount: 0 }
  }
  // 异步通知服务端（失败不影响本地已读状态，本地已记录已读时间）
  try {
    const recordId = getConversationRecordId(conv)
    if (recordId) {
      await markConversationRead(recordId).catch(() => {})
    }
  } catch {}
  // 加载会话级自动回复状态（V1.13 引入）
  loadConversationAutoReplyStatus().catch(() => {})
}

async function reloadConversations() {
  loading.value = true
  loadError.value = ''
  const accountsLoaded = await loadAccounts()
  if (!accountsLoaded) {
    loading.value = false
    return
  }
  await loadConversations()
  if (!loadError.value) startPolling()
}

async function loadChatMessages() {
  const conv = activeChat.value
  if (!conv) return
  chatLoading.value = true
  chatError.value = ''
  try {
    const sid = normalizeSid(conv.sid)
    const peerUserId = normalizePeerUserId(conv.peerUserId || conv.peerExternalUid || conv.externalBuyerId || '')
    const basePayload = {
      xianyuAccountId: Number(conv.xianyuAccountId || conv.accountId || selectedAccountId.value),
      sid,
      sId: sid,
      sessionId: sid,
      peerUserId,
      limit: 50,
      offset: 0
    }
    let res = await messageContext(basePayload)
    let nextMessages = normalizeMessages(res?.data)
    if (!nextMessages.length && peerUserId) {
      res = await messageContext({ ...basePayload, sid: '', sId: '', sessionId: '' })
      nextMessages = normalizeMessages(res?.data)
    }
    chatMessages.value = dedupeMessages(nextMessages)
  } catch (error) {
    chatMessages.value = []
    chatError.value = error?.message || '请检查网络连接后重试。'
  } finally {
    chatLoading.value = false
    await nextTick()
    scrollToBottom()
  }
}

function normalizeMessages(data) {
  if (!data) return []
  const list = Array.isArray(data)
    ? data
    : Array.isArray(data.records)
      ? data.records
      : Array.isArray(data.list)
        ? data.list
        : Array.isArray(data.messages)
          ? data.messages
          : []
  return list.map(item => {
    const rawMediaUrl = item.imageUrl || item.mediaUrl || item.url || item.media?.url || ''
    const imageUrl = resolveTrustedMediaUrl(rawMediaUrl)
    return {
      ...item,
      xianyuAccountId: Number(item.xianyuAccountId || item.accountId || 0) || undefined,
      accountId: Number(item.accountId || item.xianyuAccountId || 0) || undefined,
      sid: normalizeSid(item.sid || item.sId || item.sessionId || item.conversationId || ''),
      peerUserId: normalizePeerUserId(item.peerUserId || item.peerExternalUid || item.externalBuyerId || item.senderUserId || item.receiverUserId || ''),
      content: extractMessageDisplayText(item),
      text: extractMessageDisplayText(item),
      imageUrl,
      mediaBlocked: Boolean(rawMediaUrl) && !imageUrl,
      messageTime: Number(item.messageTime || item.createdAt || item.timestamp || item.sendTime || 0),
      isAutoReply: Number(item.isAutoReply ?? item.is_auto_reply ?? 0)
    }
  })
}

function upsertConversationFromEvent(payload) {
  const sid = normalizeSid(payload.sId || payload.sid || payload.sessionId || payload.conversationId || '')
  if (!sid) return
  const accountId = Number(payload.accountId || payload.xianyuAccountId || activeChat.value?.xianyuAccountId || selectedAccountId.value || 0) || undefined
  const peerUserId = normalizePeerUserId(
    payload.peerUserId || payload.peerExternalUid || payload.senderUserId || payload.receiverUserId || ''
  )
  const preview = extractMessageDisplayText(payload)
  const payloadTime = parseMessageTimestamp(payload.messageTime || payload.timestamp || payload.sendTime || Date.now())
  const nextConversation = {
    ...payload,
    xianyuAccountId: accountId,
    sid,
    peerUserId,
    lastMessage: preview,
    lastContent: preview,
    lastMessageTime: payloadTime,
    updatedAt: payloadTime,
    lastIsAutoReply: Boolean(payload.isAutoReply || payload.is_auto_reply),
    botEnabled: Boolean(payload.isAutoReply || payload.is_auto_reply || payload.botEnabled),
  }
  const incomingUnread = String(payload.direction || '').toUpperCase() === 'IN'
  const isActiveChat = isSameConversation(activeChat.value, nextConversation)
  // 检查本地已读状态：如果新消息时间 <= 最后查看时间，则视为已读
  // （通常只有 WS 推送延迟的旧消息才会命中此条件，避免旧消息触发未读小红点）
  const convKey = getConversationIdentityKey(nextConversation)
  const lastReadTime = convKey ? readState.get(convKey) : 0
  const isReadByLocal = Boolean(lastReadTime && payloadTime && payloadTime <= lastReadTime)

  const existingIndex = findConversationMatchIndex(conversations.value, nextConversation)
  if (existingIndex >= 0) {
    const existing = conversations.value[existingIndex]
    let nextUnreadCount
    if (isActiveChat || isReadByLocal) {
      nextUnreadCount = 0
    } else if (incomingUnread) {
      nextUnreadCount = Math.max(Number(existing.unreadCount || 0), Number(nextConversation.unreadCount || 0)) + 1
    } else {
      nextUnreadCount = Number(existing.unreadCount || 0)
    }
    const merged = {
      ...existing,
      ...nextConversation,
      unreadCount: nextUnreadCount,
    }
    conversations.value = [merged, ...conversations.value.filter((_, index) => index !== existingIndex)]
  } else {
    let nextUnreadCount
    if (isReadByLocal) {
      nextUnreadCount = 0
    } else if (incomingUnread) {
      nextUnreadCount = 1
    } else {
      nextUnreadCount = 0
    }
    conversations.value = [{ ...nextConversation, unreadCount: nextUnreadCount }, ...conversations.value]
  }
}

function onSse(event) {
  const detail = event?.detail
  const data = detail?.payload || detail || {}
  const eventType = detail?.type || data.type || data.event || 'message'

  // 会话级自动回复状态变更事件（V1.13 引入）
  if (eventType === 'conversation_auto_reply_state') {
    if (!matchesAccountSelection(selectedAccountId.value, data)) return
    if (activeChat.value && isSameConversation(activeChat.value, data)) {
      conversationAutoReplyState.value = {
        autoReplyPaused: Number(data.autoReplyPaused ?? 0),
        autoReplyManualDisabled: Number(data.autoReplyManualDisabled ?? 0),
        lastManualReplyAt: Number(data.lastManualReplyAt ?? 0),
        lastAutoReplyAt: Number(data.lastAutoReplyAt ?? 0),
        effectiveEnabled: data.effectiveEnabled ?? null,
        runningEnabled: data.runningEnabled ?? null,
        pausedReason: data.pausedReason || '',
      }
    }
    return
  }

  if (!matchesAccountSelection(selectedAccountId.value, data)) return
  const normalized = normalizeMessages([data])[0]
  if (!normalized) return
  loadError.value = ''
  if (activeChat.value && isSameConversation(activeChat.value, data)) {
    chatMessages.value = dedupeMessages([...chatMessages.value, normalized])
    activeChat.value = { ...activeChat.value, unreadCount: 0 }
    // 用户当前正在查看该会话，新消息视为已读，更新本地已读时间
    // 避免用户离开后会话又显示未读小红点
    const convKey = getConversationIdentityKey(activeChat.value)
    const payloadTime = parseMessageTimestamp(data.messageTime || data.timestamp || data.sendTime || Date.now())
    if (convKey && payloadTime) {
      readState.set(convKey, payloadTime)
      persistReadState(readState)
    }
    nextTick(() => scrollToBottom())
  }
  upsertConversationFromEvent(data)
}

async function pollLatestMessages() {
  await loadConversations()
  if (activeChat.value?.sid || activeChat.value?.peerUserId) {
    await loadChatMessages()
  }
}

function startPolling() {
  stopPolling()
  pollingTimer = setInterval(() => {
    pollLatestMessages().catch(() => {})
  }, 3000)
}

function stopPolling() {
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
  }
}

function isOutgoing(msg) {
  const dir = String(msg.direction || msg.msgDirection || '').toUpperCase()
  if (dir === 'OUT' || dir === 'SEND') return true
  if (dir === 'IN' || dir === 'RECV') return false
  return msg.fromSelf === true || msg.self === true || msg.isSelf === true
}

function scrollToBottom() {
  if (chatBoxRef.value) {
    chatBoxRef.value.scrollTop = chatBoxRef.value.scrollHeight
  }
}

function previewImage(url) {
  openTrustedMediaUrl(url)
}

async function sendCurrentMessage() {
  const text = draft.value.trim()
  if (!text || sending.value) return
  const conv = activeChat.value
  if (!conv) return
  sendError.value = ''
  sending.value = true
  const accId = Number(conv.xianyuAccountId || conv.accountId || selectedAccountId.value)
  const tempId = `temp_${Date.now()}`
  const optimistic = {
    id: tempId,
    content: text,
    direction: 'OUT',
    createdAt: new Date().toISOString(),
    sendStatus: 'sending'
  }
  chatMessages.value.push(optimistic)
  draft.value = ''
  await nextTick()
  scrollToBottom()
  try {
    const res = await sendMessage({
      xianyuAccountId: accId,
      cid: conv.sid,
      sid: conv.sid,
      sId: conv.sid,
      sessionId: conv.sid,
      toId: conv.peerUserId,
      peerUserId: conv.peerUserId,
      text,
      content: text,
      message: text,
      xyGoodsId: conv.xyGoodsId || conv.goodsId || '',
      msgType: 'text'
    })
    const ack = res?.data
    if (!ack || typeof ack !== 'object' || Array.isArray(ack)) throw new Error('消息发送响应格式异常')
    const acknowledged = String(ack.uuid || ack.id || '').trim() || ack.message === 'Sent' || ack.success === true
    if (!acknowledged) throw new Error('消息发送响应未确认发送成功')
    if (ack.sid != null && String(ack.sid) !== String(conv.sid)) throw new Error('消息发送响应会话不一致')
    const realUuid = String(ack.uuid || ack.id || '').trim()
    const target = chatMessages.value.find(m => m.id === tempId)
    if (target) {
      target.id = realUuid || tempId
      target.sendStatus = 'sent'
    }
  } catch (error) {
    const target = chatMessages.value.find(m => m.id === tempId)
    if (target) target.sendStatus = 'failed'
    sendError.value = error?.message || '消息发送失败，请检查连接后重试。'
  } finally {
    sending.value = false
    await nextTick()
    scrollToBottom()
  }
}

function closeChat() {
  activeChat.value = null
  chatMessages.value = []
  chatError.value = ''
  sendError.value = ''
  draft.value = ''
  // 重置会话级自动回复状态
  conversationAutoReplyState.value = {
    autoReplyPaused: 0,
    autoReplyManualDisabled: 0,
    lastManualReplyAt: 0,
    lastAutoReplyAt: 0,
    effectiveEnabled: null,
    runningEnabled: null,
    pausedReason: '',
  }
}

onMounted(async () => {
  loadRetentionNotice()
  const accountsLoaded = await loadAccounts()
  if (accountsLoaded) {
    await loadConversations()
  } else {
    loading.value = false
  }
  window.addEventListener('xya-sse-event', onSse)
  if (accountsLoaded && !loadError.value) startPolling()
})

onBeforeUnmount(() => {
  window.removeEventListener('xya-sse-event', onSse)
  stopPolling()
})
</script>

<style scoped>
.m-msg {
  padding: 12px 16px 0;
  display: flex;
  flex-direction: column;
  min-height: calc(100vh - 120px);
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
}
.m-msg.m-msg-chat-open {
  position: fixed;
  inset: 0;
  z-index: 200;
  height: 100dvh;
  min-height: 0;
  padding: env(safe-area-inset-top) 16px 0;
  overflow: hidden;
  background: #f5f8ff;
}
.m-page-header { margin-bottom: 14px; }
.m-page-header h1 { margin: 0 0 4px; font-size: 26px; font-weight: 800; color: #15213d; }
.m-page-sub { margin: 0; font-size: 13px; color: #8c98ae; }

.m-account-chips {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  overflow-y: hidden;
  padding-bottom: 10px;
  margin-left: -16px;
  margin-right: -16px;
  padding-left: 16px;
  padding-right: 16px;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.m-account-chips::-webkit-scrollbar { display: none; }
.m-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: white;
  border: 1px solid #e8edf5;
  color: #51607a;
  font-size: 13px;
  font-weight: 500;
  padding: 7px 14px;
  border-radius: 100px;
  white-space: nowrap;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.15s;
}
.m-chip.active {
  background: linear-gradient(135deg, #0d6bff, #2580ff);
  color: white;
  border-color: transparent;
  box-shadow: 0 4px 10px rgba(13,107,255,0.25);
}
.m-chip-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #c4cddb;
  flex-shrink: 0;
}
.m-chip-dot.online { background: #16bf78; box-shadow: 0 0 0 2px rgba(22,191,120,0.18); }

.m-msg-search {
  height: 48px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 14px;
  margin-bottom: 14px;
  border: 1px solid #e7ebf2;
  border-radius: 14px;
  background: #f8faff;
  color: #8b98ad;
}
.m-msg-search input {
  width: 100%;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: #172445;
  font-size: 15px;
}
.m-msg-search input::placeholder { color: #8b98ad; }
.m-filter-tabs {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 9px;
  margin-bottom: 16px;
}
.m-filter-tab {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  min-height: 46px;
  background: #fff;
  border: 1px solid #e6ebf2;
  border-radius: 14px;
  color: #62708b;
  font-size: 14px;
  font-weight: 600;
  padding: 7px 4px;
  cursor: pointer;
  white-space: nowrap;
}
.m-filter-tab.active {
  background: #1478f5;
  border-color: #1478f5;
  color: #fff;
  box-shadow: 0 6px 14px rgba(20, 120, 245, 0.2);
}
.m-filter-count { font-size: 12px; font-weight: 500; }
.m-filter-tab:not(.active) .m-filter-count { color: #7d8aa2; }

.m-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 50px 20px;
  color: #8c98ae;
  font-size: 13px;
}
.m-loading-spinner {
  width: 28px;
  height: 28px;
  border: 3px solid #e8edf5;
  border-top-color: #0d6bff;
  border-radius: 50%;
  animation: m-spin 0.8s linear infinite;
}
@keyframes m-spin { to { transform: rotate(360deg); } }

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

.m-msg-list {
  background: #fff;
  border-radius: 16px;
  border: 1px solid #edf0f5;
  overflow: hidden;
  box-shadow: 0 4px 16px rgba(31, 53, 94, 0.035);
}
.m-msg-item {
  display: flex;
  gap: 13px;
  padding: 16px 14px;
  border-bottom: 1px solid #edf1f5;
  cursor: pointer;
}
.m-msg-item:active { background: #f8faff; }
.m-msg-list-total {
  padding: 14px;
  text-align: center;
  color: #8c98ae;
  font-size: 13px;
}

.m-msg-avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: linear-gradient(135deg, #e8f1ff, #d4e4ff);
  color: #0d6bff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  position: relative;
}
.m-msg-avatar.is-robot {
  background: linear-gradient(135deg, #f0ebff, #e2d8ff);
  color: #8b5cf6;
}
.m-msg-dot {
  position: absolute;
  top: 0;
  right: 0;
  width: 10px;
  height: 10px;
  background: #ff5252;
  border: 2px solid white;
  border-radius: 50%;
}
.m-msg-body { flex: 1; min-width: 0; }
.m-msg-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}
.m-msg-name { font-size: 15px; font-weight: 600; color: #15213d; max-width: 60%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.m-msg-time { font-size: 11px; color: #b0bacb; flex-shrink: 0; }
.m-msg-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.m-msg-preview {
  font-size: 13px;
  color: #8c98ae;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-ai-row {
  display: flex;
  margin-bottom: 4px;
}
.m-ai-row.out {
  justify-content: flex-end;
}
.m-ai-badge {
  display: inline-flex;
  align-items: center;
  height: 18px;
  padding: 0 7px;
  border-radius: 999px;
  background: rgba(22, 163, 74, 0.12);
  color: #15803d;
  font-size: 10px;
  font-weight: 700;
  line-height: 18px;
  white-space: nowrap;
}
.m-ai-badge.inline {
  margin-right: 6px;
  vertical-align: middle;
}
.m-msg-badge {
  min-width: 20px;
  height: 20px;
  border-radius: 10px;
  background: #ff5252;
  color: white;
  font-size: 11px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 6px;
  flex-shrink: 0;
}
.m-msg-status {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 100px;
  flex-shrink: 0;
}
.m-msg-status-done {
  background: #f0f4fa;
  color: #72809a;
}
.m-msg-goods {
  font-size: 11px;
  color: #0d6bff;
  margin-top: 6px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: rgba(13,107,255,0.08);
  padding: 3px 8px;
  border-radius: 6px;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.m-msg-tip {
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
.m-msg-tip :deep(svg) { color: #8b5cf6; flex-shrink: 0; }
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

/* 聊天详情视图 */
.m-chat-header {
  position: sticky;
  top: 0;
  z-index: 10;
  background: rgba(245, 248, 255, 0.95);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  padding: 10px 4px 10px 0;
  display: flex;
  align-items: center;
  gap: 10px;
  border-bottom: 1px solid rgba(231, 237, 247, 0.7);
  margin: -12px -16px 0;
  padding-left: 8px;
  padding-right: 12px;
}
.m-chat-back {
  background: none;
  border: none;
  color: #15213d;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
}
.m-chat-back:active { background: rgba(13,107,255,0.08); }
.m-chat-title { flex: 1; min-width: 0; }
.m-chat-name {
  font-size: 16px;
  font-weight: 700;
  color: #15213d;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-chat-goods {
  font-size: 11px;
  color: #0d6bff;
  margin-top: 2px;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-chat-more {
  background: none;
  border: none;
  color: #72809a;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
}
.m-chat-more:active { background: rgba(13,107,255,0.08); }

.m-chat-product-card {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr);
  gap: 10px;
  margin: 12px 0 0;
  padding: 12px;
  background: #fff;
  border: 1px solid #e7edf8;
  border-radius: 10px;
  box-shadow: 0 4px 14px rgba(31, 53, 94, 0.06);
}
.m-chat-product-thumb {
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: #edf4ff;
  color: #1677ff;
}
.m-chat-product-main { min-width: 0; }
.m-chat-product-main strong, .m-chat-product-main span { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.m-chat-product-main strong { color: #15213d; font-size: 14px; }
.m-chat-product-main span { margin-top: 6px; color: #8c98ae; font-size: 12px; }
.m-chat-product-actions { grid-column: 2; display: flex; gap: 8px; }
.m-chat-product-actions button { min-width: 0; height: 32px; border-radius: 8px; padding: 0 10px; font-size: 12px; font-weight: 600; }
.m-chat-product-secondary { border: 1px solid #e2eaf7; background: #f5f8ff; color: #31527f; }
.m-chat-product-primary { border: 1px solid #1677ff; background: #1677ff; color: #fff; }
.m-chat-body {
  flex: 1;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: 14px 0;
  min-height: 300px;
}
.m-chat-day-divider { display: flex; align-items: center; gap: 12px; margin: 2px 0 16px; color: #94a1b8; font-size: 12px; }
.m-chat-day-divider::before, .m-chat-day-divider::after { content: ''; flex: 1; height: 1px; background: #dfe6f2; }
.m-chat-loading, .m-chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 60px 20px;
  color: #b0bacb;
  font-size: 13px;
}
.m-chat-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 0 4px;
}
.m-bubble {
  display: flex;
  gap: 8px;
  align-items: flex-end;
  max-width: 100%;
}
.m-bubble.in { justify-content: flex-start; }
.m-bubble.out { justify-content: flex-end; }
.m-bubble-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, #e8f1ff, #d4e4ff);
  color: #0d6bff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-bubble-avatar.out-avatar {
  background: linear-gradient(135deg, #0d6bff, #2580ff);
  color: white;
}
.m-bubble-content {
  max-width: 75%;
  padding: 9px 12px;
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.45;
  word-wrap: break-word;
  overflow-wrap: break-word;
}
.m-bubble.in .m-bubble-content {
  background: white;
  color: #15213d;
  border: 1px solid #eef2fa;
  border-bottom-left-radius: 4px;
}
.m-bubble.out .m-bubble-content {
  background: linear-gradient(135deg, #0d6bff, #2580ff);
  color: white;
  border-bottom-right-radius: 4px;
}
.m-bubble-text { white-space: pre-wrap; }
.m-bubble-image-wrap { margin-bottom: 4px; }
.m-bubble-media-blocked {
  margin-bottom: 4px;
  color: #9a5b00;
  font-size: 12px;
}
.m-bubble-image {
  max-width: 100%;
  max-height: 200px;
  border-radius: 10px;
  display: block;
  cursor: pointer;
}
.m-bubble-time {
  font-size: 10px;
  margin-top: 4px;
  opacity: 0.7;
}
.m-bubble.in .m-bubble-time { color: #b0bacb; }
.m-bubble.out .m-bubble-time { color: rgba(255,255,255,0.8); }
.m-bubble-send-state { margin-top: 3px; font-size: 10px; opacity: .8; }
.m-bubble-send-state.failed { color: #fff; font-weight: 700; opacity: 1; }

.m-chat-quick-actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  padding: 8px 0 10px;
}
.m-chat-quick-actions button {
  display: inline-flex;
  min-width: 0;
  min-height: 36px;
  align-items: center;
  justify-content: center;
  gap: 5px;
  border: 1px solid #e7edf8;
  border-radius: 8px;
  background: #fff;
  color: #24507e;
  font-size: 11px;
  font-weight: 600;
}
.m-chat-quick-actions span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.m-chat-quick-actions :deep(svg) { color: #1677ff; flex: 0 0 auto; }
/* 会话级自动回复按钮3态样式（V1.13 引入） */
.m-chat-quick-actions button.m-auto-reply-running {
  border-color: #b7ebd4;
  background: #e6f9ef;
  color: #228c52;
}
.m-chat-quick-actions button.m-auto-reply-running :deep(svg) { color: #228c52; }
.m-chat-quick-actions button.m-auto-reply-paused {
  border-color: #ffe2b4;
  background: #fff7e6;
  color: #d68a1a;
}
.m-chat-quick-actions button.m-auto-reply-paused :deep(svg) { color: #d68a1a; }
.m-chat-quick-actions button.m-auto-reply-disabled {
  border-color: #f5c2c2;
  background: #fdecec;
  color: #d64545;
}
.m-chat-quick-actions button.m-auto-reply-disabled :deep(svg) { color: #d64545; }
.m-chat-quick-actions button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.m-chat-compose {
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr) auto;
  gap: 8px;
  align-items: end;
  margin: 0 -16px;
  padding: 10px 12px max(10px, env(safe-area-inset-bottom));
  background: #fff;
  border-top: 1px solid #e7edf8;
}
.m-chat-send-error { grid-column: 1 / -1; color: #c9363e; font-size: 11px; line-height: 1.4; }
.m-chat-attach {
  width: 30px;
  height: 30px;
  margin-bottom: 7px;
  padding: 0;
  border: 1px solid #9eb0cb;
  border-radius: 50%;
  background: #fff;
  color: #61718d;
}
.m-chat-compose textarea {
  width: 100%;
  min-height: 50px;
  max-height: 88px;
  box-sizing: border-box;
  resize: none;
  border: 1px solid #e3eaf5;
  border-radius: 8px;
  padding: 9px 10px;
  color: #15213d;
  font: inherit;
  font-size: 13px;
  line-height: 1.45;
  outline: none;
}
.m-chat-compose textarea:focus { border-color: #1677ff; }
.m-msg-chat-open .m-chat-header {
  position: static;
  flex: 0 0 auto;
  margin: 0 -16px;
}
.m-msg-chat-open .m-chat-body {
  min-height: 0;
  overscroll-behavior: contain;
}
.m-msg-chat-open .m-chat-compose {
  position: static;
  flex: 0 0 auto;
}
.m-msg-chat-open .m-safe-bottom { display: none; }
.m-chat-send {
  min-width: 56px;
  height: 38px;
  border-radius: 8px;
  border: none;
  background: linear-gradient(135deg, #0d6bff, #2580ff);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  box-shadow: 0 4px 10px rgba(13,107,255,0.3);
  transition: transform 0.1s;
}
.m-chat-send:active { transform: scale(0.95); }
.m-chat-send:disabled {
  background: #d4ddea;
  box-shadow: none;
  cursor: not-allowed;
}

.m-safe-bottom { height: 80px; }

.m-retention-notice {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 8px 0 0;
  padding: 6px 10px;
  background: rgba(13, 107, 255, 0.08);
  border-radius: 8px;
  font-size: 12px;
  color: #0d6bff;
  line-height: 1.4;
}
</style>
