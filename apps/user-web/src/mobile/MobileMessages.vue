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
          <button v-if="activeChat.xyGoodsId || activeChat.goodsId" type="button" class="m-chat-product-secondary" @click="$emit('navigate', 'product-detail', { id: activeChat.xyGoodsId || activeChat.goodsId })">查看商品</button>
          <button type="button" class="m-chat-product-primary" @click="openProductLinkPicker">发送商品</button>
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
        <button type="button" @click="openImageUploader"><MIcon name="image" :size="18" /><span>发送图片</span></button>
        <button type="button" @click="openProductLinkPicker"><MIcon name="link" :size="18" /><span>发送商品链接</span></button>
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
        <button type="button" class="m-chat-quick-reply-btn" aria-label="快捷回复" @click="openQuickReply"><MIcon name="reply" :size="18" /></button>
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

    <!-- 移动端图片上传弹层 -->
    <MobileImageUploader
      :visible="imageUploaderVisible"
      :account-id="currentAccountId"
      @close="closeImageUploader"
      @send="handleSendImages"
    />

    <!-- 移动端商品链接选择器弹层 -->
    <MobileProductLinkPicker
      :visible="productLinkPickerVisible"
      :account-id="currentAccountId"
      @close="closeProductLinkPicker"
      @select="handleSelectProduct"
    />

    <!-- 快捷回复模板底部弹层 -->
    <div v-if="showQuickReplySheet" class="m-quick-reply-mask" @click="showQuickReplySheet = false">
      <div class="m-quick-reply-sheet" @click.stop>
        <div class="m-quick-reply-header">
          <span>快捷回复</span>
          <button class="m-quick-reply-close" aria-label="关闭" @click="showQuickReplySheet = false">
            <MIcon name="x" :size="20" />
          </button>
        </div>
        <div class="m-quick-reply-body">
          <div v-if="quickReplyLoading" class="m-quick-reply-loading">加载中...</div>
          <div v-else-if="quickReplyTemplates.length === 0" class="m-quick-reply-empty">暂无快捷回复模板</div>
          <div v-else class="m-quick-reply-list">
            <button
              v-for="tpl in quickReplyTemplates"
              :key="tpl.id"
              class="m-quick-reply-item"
              @click="insertQuickReply(tpl)"
            >
              <div class="m-quick-reply-item-title">{{ tpl.title || '未命名' }}</div>
              <div class="m-quick-reply-item-content">{{ tpl.content || '' }}</div>
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="m-safe-bottom"></div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import MIcon from './MIcon.vue'
import MobileUnavailableState from './MobileUnavailableState.vue'
import MobileImageUploader from './components/MobileImageUploader.vue'
import MobileProductLinkPicker from './components/MobileProductLinkPicker.vue'
import { getLiteAccounts } from '../api/accounts.js'
import { onlineConversations, messageContext, markConversationRead } from '../api/messages.js'
import { sendMessage, sendImageMessage } from '../api/websocket.js'
import { getRetentionInfo } from '../api/system.js'
import { openTrustedMediaUrl, resolveTrustedMediaUrl } from '../utils/safeMediaUrl.js'
import {
  toggleConversationAutoReply,
  getConversationAutoReplyStatus,
} from '../api/autoReplyScope.js'
import { listQuickReplyTemplates } from '../api/quickReply.js'
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
  } catch { /* localStorage 解析失败时回退到空 Map */ }
  return new Map()
}

function persistReadState(state) {
  try {
    const obj = {}
    state.forEach((value, key) => { obj[key] = value })
    localStorage.setItem(READ_STATE_STORAGE_KEY, JSON.stringify(obj))
  } catch { /* localStorage 写入失败时忽略，本地已读状态非关键路径 */ }
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
  // 后端 /msg/online/conversations 返回 { conversations: [...], hasMore, nextCursor }
  // 兼容 records / 数组 等其他可能格式
  const list = res?.data?.conversations || res?.data?.records || (Array.isArray(res?.data) ? res.data : null)
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
  } catch { /* 服务端已读回执失败时不影响本地状态 */ }
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
  // 关闭弹层
  imageUploaderVisible.value = false
  productLinkPickerVisible.value = false
  showQuickReplySheet.value = false
}

// ---- 图片发送 ----
const imageUploaderVisible = ref(false)
const productLinkPickerVisible = ref(false)

// ---- 快捷回复模板 ----
const showQuickReplySheet = ref(false)
const quickReplyTemplates = ref([])
const quickReplyLoading = ref(false)

const currentAccountId = computed(() => {
  const conv = activeChat.value
  return Number(conv?.xianyuAccountId || conv?.accountId || selectedAccountId.value || 0)
})

function openImageUploader() {
  if (!activeChat.value) {
    sendError.value = '请先选择会话'
    return
  }
  if (!currentAccountId.value) {
    sendError.value = '账号信息缺失，无法上传图片'
    return
  }
  sendError.value = ''
  imageUploaderVisible.value = true
}

function closeImageUploader() {
  imageUploaderVisible.value = false
}

async function handleSendImages(imageUrls) {
  imageUploaderVisible.value = false
  if (!Array.isArray(imageUrls) || !imageUrls.length) return
  const conv = activeChat.value
  if (!conv) return
  const accId = currentAccountId.value
  if (!accId) {
    sendError.value = '账号信息缺失，无法发送图片'
    return
  }
  const receiverId = normalizePeerUserId(
    conv.peerUserId || conv.peerExternalUid || conv.externalBuyerId || ''
  ) || normalizeSid(conv.sid || conv.sId || '')
  if (!receiverId) {
    sendError.value = '当前会话缺少接收方标识'
    return
  }
  sending.value = true
  sendError.value = ''
  // 逐张发送：每张图片一条消息（与 PC 端 sendImage 行为一致）
  const optimisticIds = []
  for (const imageUrl of imageUrls) {
    const tempId = `temp_image_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
    const trustedUrl = resolveTrustedMediaUrl(imageUrl)
    const optimistic = {
      id: tempId,
      content: '[图片]',
      text: '[图片]',
      imageUrl: trustedUrl,
      direction: 'OUT',
      createdAt: new Date().toISOString(),
      sendStatus: 'sending',
    }
    chatMessages.value.push(optimistic)
    optimisticIds.push({ tempId, imageUrl })
  }
  await nextTick()
  scrollToBottom()
  try {
    for (const { tempId, imageUrl } of optimisticIds) {
      try {
        const res = await sendImageMessage({
          xianyuAccountId: accId,
          cid: conv.sid,
          sid: conv.sid,
          sId: conv.sid,
          sessionId: conv.sid,
          toId: receiverId,
          peerUserId: receiverId,
          imageUrl,
          xyGoodsId: conv.xyGoodsId || conv.goodsId || '',
        })
        const ack = res?.data
        if (!ack || typeof ack !== 'object' || Array.isArray(ack)) throw new Error('图片发送响应格式异常')
        const acknowledged = String(ack.uuid || ack.id || '').trim() || ack.message === 'Sent' || ack.success === true
        if (!acknowledged) throw new Error('图片发送响应未确认发送成功')
        if (ack.sid != null && String(ack.sid) !== String(conv.sid)) throw new Error('图片发送响应会话不一致')
        const realUuid = String(ack.uuid || ack.id || '').trim()
        const target = chatMessages.value.find(m => m.id === tempId)
        if (target) {
          target.id = realUuid || tempId
          target.sendStatus = 'sent'
        }
      } catch (e) {
        const target = chatMessages.value.find(m => m.id === tempId)
        if (target) target.sendStatus = 'failed'
        sendError.value = e?.message || '图片发送失败'
      }
    }
  } finally {
    sending.value = false
    await nextTick()
    scrollToBottom()
  }
}

// ---- 商品链接 ----
function openProductLinkPicker() {
  if (!activeChat.value) {
    sendError.value = '请先选择会话'
    return
  }
  if (!currentAccountId.value) {
    sendError.value = '账号信息缺失，无法选择商品'
    return
  }
  sendError.value = ''
  productLinkPickerVisible.value = true
}

function closeProductLinkPicker() {
  productLinkPickerVisible.value = false
}

// ---- 快捷回复模板 ----
async function loadQuickReplyTemplates() {
  quickReplyLoading.value = true
  try {
    const res = await listQuickReplyTemplates({ current: 1, size: 100 })
    const data = res?.data || res || {}
    quickReplyTemplates.value = data.records || data.list || data.items || (Array.isArray(data) ? data : [])
  } catch {
    quickReplyTemplates.value = []
  } finally {
    quickReplyLoading.value = false
  }
}

async function openQuickReply() {
  if (!activeChat.value) {
    sendError.value = '请先选择会话'
    return
  }
  showQuickReplySheet.value = true
  if (quickReplyTemplates.value.length === 0) {
    await loadQuickReplyTemplates()
  }
}

function insertQuickReply(template) {
  const content = template?.content || ''
  if (!content) return
  draft.value = draft.value ? `${draft.value}\n${content}` : content
  showQuickReplySheet.value = false
}

function handleSelectProduct(product) {
  productLinkPickerVisible.value = false
  if (!product) return
  // 优先使用商品链接；若无 itemId 则把商品标题作为文本插入
  if (product.link) {
    draft.value = draft.value ? `${draft.value}\n${product.link}` : product.link
  } else if (product.title) {
    draft.value = draft.value ? `${draft.value}\n${product.title}` : product.title
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
  padding: var(--m-space-3) var(--m-space-4) 0;
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
  padding: env(safe-area-inset-top) var(--m-space-4) 0;
  overflow: hidden;
  background: var(--m-color-bg-page);
}
.m-page-header { margin-bottom: var(--m-space-3); }
.m-page-header h1 { margin: 0 0 var(--m-space-1); font-size: var(--m-font-size-h1); font-weight: var(--m-font-weight-extrabold); color: var(--m-color-text-primary); }
.m-page-sub { margin: 0; font-size: var(--m-font-size-body-sm); color: var(--m-color-text-tertiary); }

.m-account-chips {
  display: flex;
  gap: var(--m-space-2);
  overflow-x: auto;
  overflow-y: hidden;
  padding-bottom: var(--m-space-2);
  margin-left: calc(-1 * var(--m-space-4));
  margin-right: calc(-1 * var(--m-space-4));
  padding-left: var(--m-space-4);
  padding-right: var(--m-space-4);
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.m-account-chips::-webkit-scrollbar { display: none; }
.m-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-1);
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border);
  color: var(--m-color-text-secondary);
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-medium);
  padding: var(--m-space-2) var(--m-space-3);
  border-radius: var(--m-radius-pill);
  white-space: nowrap;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.15s;
}
.m-chip.active {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  border-color: transparent;
  box-shadow: var(--m-shadow-fab);
}
.m-chip-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--m-radius-circle);
  background: var(--m-color-text-disabled);
  flex-shrink: 0;
}
.m-chip-dot.online { background: var(--m-color-success); box-shadow: 0 0 0 2px var(--m-color-success-bg); }

.m-msg-search {
  height: 48px;
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  padding: 0 var(--m-space-3);
  margin-bottom: var(--m-space-3);
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-lg);
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-tertiary);
}
.m-msg-search input {
  width: 100%;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--m-color-text-primary);
  font-size: var(--m-font-size-h3);
}
.m-msg-search input::placeholder { color: var(--m-color-text-placeholder); }
.m-filter-tabs {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-4);
}
.m-filter-tab {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-1);
  min-height: 46px;
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-lg);
  color: var(--m-color-text-secondary);
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-semibold);
  padding: var(--m-space-2) var(--m-space-1);
  cursor: pointer;
  white-space: nowrap;
}
.m-filter-tab.active {
  background: var(--m-color-primary);
  border-color: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  box-shadow: var(--m-shadow-fab);
}
.m-filter-count { font-size: var(--m-font-size-caption); font-weight: var(--m-font-weight-medium); }
.m-filter-tab:not(.active) .m-filter-count { color: var(--m-color-text-tertiary); }

.m-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--m-space-2);
  padding: 50px var(--m-space-5);
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-body-sm);
}
.m-loading-spinner {
  width: 28px;
  height: 28px;
  border: 3px solid var(--m-color-border);
  border-top-color: var(--m-color-primary);
  border-radius: var(--m-radius-circle);
  animation: m-spin 0.8s linear infinite;
}
@keyframes m-spin { to { transform: rotate(360deg); } }

.m-empty {
  text-align: center;
  padding: 60px var(--m-space-5);
}
.m-empty-icon {
  width: 80px;
  height: 80px;
  margin: 0 auto var(--m-space-4);
  border-radius: var(--m-radius-circle);
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
}
.m-empty-text { font-size: var(--m-font-size-h2); font-weight: var(--m-font-weight-semibold); color: var(--m-color-text-primary); margin-bottom: var(--m-space-1); }
.m-empty-desc { font-size: var(--m-font-size-body-sm); color: var(--m-color-text-tertiary); }

.m-msg-list {
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-xl);
  border: 1px solid var(--m-color-border-light);
  overflow: hidden;
  box-shadow: var(--m-shadow-card);
}
.m-msg-item {
  display: flex;
  gap: var(--m-space-3);
  padding: var(--m-space-4) var(--m-space-3);
  border-bottom: 1px solid var(--m-color-border-light);
  cursor: pointer;
}
.m-msg-item:active { background: var(--m-color-bg-hover); }
.m-msg-list-total {
  padding: var(--m-space-3);
  text-align: center;
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-body-sm);
}

.m-msg-avatar {
  width: 44px;
  height: 44px;
  border-radius: var(--m-radius-circle);
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  position: relative;
}
.m-msg-avatar.is-robot {
  background: var(--m-color-purple-bg);
  color: var(--m-color-purple);
}
.m-msg-dot {
  position: absolute;
  top: 0;
  right: 0;
  width: 10px;
  height: 10px;
  background: var(--m-color-danger);
  border: 2px solid var(--m-color-bg-card);
  border-radius: var(--m-radius-circle);
}
.m-msg-body { flex: 1; min-width: 0; }
.m-msg-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--m-space-1);
}
.m-msg-name { font-size: var(--m-font-size-h3); font-weight: var(--m-font-weight-semibold); color: var(--m-color-text-primary); max-width: 60%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.m-msg-time { font-size: var(--m-font-size-tiny); color: var(--m-color-text-tertiary); flex-shrink: 0; }
.m-msg-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--m-space-2);
}
.m-msg-preview {
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-tertiary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-ai-row {
  display: flex;
  margin-bottom: var(--m-space-1);
}
.m-ai-row.out {
  justify-content: flex-end;
}
.m-ai-badge {
  display: inline-flex;
  align-items: center;
  height: 18px;
  padding: 0 var(--m-space-2);
  border-radius: var(--m-radius-pill);
  background: var(--m-color-success-bg);
  color: var(--m-color-success-text);
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-bold);
  line-height: 18px;
  white-space: nowrap;
}
.m-ai-badge.inline {
  margin-right: var(--m-space-1);
  vertical-align: middle;
}
.m-msg-badge {
  min-width: 20px;
  height: 20px;
  border-radius: var(--m-radius-pill);
  background: var(--m-color-danger);
  color: var(--m-color-text-inverse);
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-semibold);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 var(--m-space-1);
  flex-shrink: 0;
}
.m-msg-status {
  font-size: var(--m-font-size-tiny);
  padding: 2px var(--m-space-2);
  border-radius: var(--m-radius-pill);
  flex-shrink: 0;
}
.m-msg-status-done {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
}
.m-msg-goods {
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-primary);
  margin-top: var(--m-space-1);
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-1);
  background: var(--m-color-primary-bg);
  padding: 3px var(--m-space-2);
  border-radius: var(--m-radius-sm);
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.m-msg-tip {
  margin-top: var(--m-space-5);
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3) var(--m-space-3);
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-secondary);
}
.m-msg-tip :deep(svg) { color: var(--m-color-purple); flex-shrink: 0; }
.m-tip-btn {
  margin-left: auto;
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  border: none;
  border-radius: var(--m-radius-pill);
  padding: var(--m-space-1) var(--m-space-3);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  flex-shrink: 0;
}

/* 聊天详情视图 */
.m-chat-header {
  position: sticky;
  top: 0;
  z-index: 10;
  background: rgba(245, 246, 247, 0.95);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  padding: var(--m-space-2) var(--m-space-1) var(--m-space-2) 0;
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  border-bottom: 1px solid var(--m-color-border-light);
  margin: calc(-1 * var(--m-space-3)) calc(-1 * var(--m-space-4)) 0;
  padding-left: var(--m-space-2);
  padding-right: var(--m-space-3);
}
.m-chat-back {
  background: none;
  border: none;
  color: var(--m-color-text-primary);
  width: 36px;
  height: 36px;
  border-radius: var(--m-radius-circle);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
}
.m-chat-back:active { background: var(--m-color-primary-bg); }
.m-chat-title { flex: 1; min-width: 0; }
.m-chat-name {
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-chat-goods {
  font-size: var(--m-font-size-tiny);
  color: var(--m-color-primary);
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
  color: var(--m-color-text-secondary);
  width: 32px;
  height: 32px;
  border-radius: var(--m-radius-circle);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
}
.m-chat-more:active { background: var(--m-color-primary-bg); }

.m-chat-product-card {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr);
  gap: var(--m-space-2);
  margin: var(--m-space-3) 0 0;
  padding: var(--m-space-3);
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-md);
  box-shadow: var(--m-shadow-elevated);
}
.m-chat-product-thumb {
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--m-radius-md);
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
}
.m-chat-product-main { min-width: 0; }
.m-chat-product-main strong, .m-chat-product-main span { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.m-chat-product-main strong { color: var(--m-color-text-primary); font-size: var(--m-font-size-body); }
.m-chat-product-main span { margin-top: var(--m-space-1); color: var(--m-color-text-tertiary); font-size: var(--m-font-size-caption); }
.m-chat-product-actions { grid-column: 2; display: flex; gap: var(--m-space-2); }
.m-chat-product-actions button { min-width: 0; height: 32px; border-radius: var(--m-radius-md); padding: 0 var(--m-space-2); font-size: var(--m-font-size-caption); font-weight: var(--m-font-weight-semibold); }
.m-chat-product-secondary { border: 1px solid var(--m-color-border); background: var(--m-color-bg-subtle); color: var(--m-color-text-secondary); }
.m-chat-product-primary { border: 1px solid var(--m-color-primary); background: var(--m-color-primary); color: var(--m-color-text-inverse); }
.m-chat-body {
  flex: 1;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: var(--m-space-3) 0;
  min-height: 300px;
}
.m-chat-day-divider { display: flex; align-items: center; gap: var(--m-space-3); margin: 2px 0 var(--m-space-4); color: var(--m-color-text-tertiary); font-size: var(--m-font-size-caption); }
.m-chat-day-divider::before, .m-chat-day-divider::after { content: ''; flex: 1; height: 1px; background: var(--m-color-border); }
.m-chat-loading, .m-chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--m-space-2);
  padding: 60px var(--m-space-5);
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-body-sm);
}
.m-chat-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
  padding: 0 var(--m-space-1);
}
.m-bubble {
  display: flex;
  gap: var(--m-space-2);
  align-items: flex-end;
  max-width: 100%;
}
.m-bubble.in { justify-content: flex-start; }
.m-bubble.out { justify-content: flex-end; }
.m-bubble-avatar {
  width: 28px;
  height: 28px;
  border-radius: var(--m-radius-circle);
  background: var(--m-color-primary-bg);
  color: var(--m-color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-bubble-avatar.out-avatar {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
}
.m-bubble-content {
  max-width: 75%;
  padding: var(--m-space-2) var(--m-space-3);
  border-radius: var(--m-radius-lg);
  font-size: var(--m-font-size-body);
  line-height: var(--m-line-height-base);
  word-wrap: break-word;
  overflow-wrap: break-word;
}
.m-bubble.in .m-bubble-content {
  background: var(--m-color-bg-card);
  color: var(--m-color-text-primary);
  border: 1px solid var(--m-color-border-light);
  border-bottom-left-radius: var(--m-radius-sm);
}
.m-bubble.out .m-bubble-content {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  border-bottom-right-radius: var(--m-radius-sm);
}
.m-bubble-text { white-space: pre-wrap; }
.m-bubble-image-wrap { margin-bottom: var(--m-space-1); }
.m-bubble-media-blocked {
  margin-bottom: var(--m-space-1);
  color: var(--m-color-warning-text);
  font-size: var(--m-font-size-caption);
}
.m-bubble-image {
  max-width: 100%;
  max-height: 200px;
  border-radius: var(--m-radius-md);
  display: block;
  cursor: pointer;
}
.m-bubble-time {
  font-size: var(--m-font-size-tiny);
  margin-top: var(--m-space-1);
  opacity: 0.7;
}
.m-bubble.in .m-bubble-time { color: var(--m-color-text-tertiary); }
.m-bubble.out .m-bubble-time { color: rgba(255, 255, 255, 0.8); }
.m-bubble-send-state { margin-top: 3px; font-size: var(--m-font-size-tiny); opacity: .8; }
.m-bubble-send-state.failed { color: var(--m-color-text-inverse); font-weight: var(--m-font-weight-bold); opacity: 1; }

.m-chat-quick-actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--m-space-2);
  padding: var(--m-space-2) 0 var(--m-space-2);
}
.m-chat-quick-actions button {
  display: inline-flex;
  min-width: 0;
  min-height: 36px;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-1);
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-md);
  background: var(--m-color-bg-card);
  color: var(--m-color-text-secondary);
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-semibold);
}
.m-chat-quick-actions span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.m-chat-quick-actions :deep(svg) { color: var(--m-color-primary); flex: 0 0 auto; }
/* 会话级自动回复按钮3态样式（V1.13 引入） */
.m-chat-quick-actions button.m-auto-reply-running {
  border-color: var(--m-color-success-border);
  background: var(--m-color-success-bg);
  color: var(--m-color-success-text);
}
.m-chat-quick-actions button.m-auto-reply-running :deep(svg) { color: var(--m-color-success-text); }
.m-chat-quick-actions button.m-auto-reply-paused {
  border-color: var(--m-color-warning-border);
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning-text);
}
.m-chat-quick-actions button.m-auto-reply-paused :deep(svg) { color: var(--m-color-warning-text); }
.m-chat-quick-actions button.m-auto-reply-disabled {
  border-color: var(--m-color-danger-border);
  background: var(--m-color-danger-bg);
  color: var(--m-color-danger-text);
}
.m-chat-quick-actions button.m-auto-reply-disabled :deep(svg) { color: var(--m-color-danger-text); }
.m-chat-quick-actions button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.m-chat-compose {
  display: grid;
  grid-template-columns: 30px 30px minmax(0, 1fr) auto;
  gap: var(--m-space-2);
  align-items: end;
  margin: 0 calc(-1 * var(--m-space-4));
  padding: var(--m-space-2) var(--m-space-3) max(var(--m-space-2), env(safe-area-inset-bottom));
  background: var(--m-color-bg-card);
  border-top: 1px solid var(--m-color-border);
}
.m-chat-send-error { grid-column: 1 / -1; color: var(--m-color-danger-text); font-size: var(--m-font-size-tiny); line-height: var(--m-line-height-base); }
.m-chat-attach {
  width: 30px;
  height: 30px;
  margin-bottom: var(--m-space-2);
  padding: 0;
  border: 1px solid var(--m-color-text-tertiary);
  border-radius: var(--m-radius-circle);
  background: var(--m-color-bg-card);
  color: var(--m-color-text-secondary);
}
.m-chat-compose textarea {
  width: 100%;
  min-height: 50px;
  max-height: 88px;
  box-sizing: border-box;
  resize: none;
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-md);
  padding: var(--m-space-2) var(--m-space-2);
  color: var(--m-color-text-primary);
  font: inherit;
  font-size: var(--m-font-size-body-sm);
  line-height: var(--m-line-height-base);
  outline: none;
}
.m-chat-compose textarea:focus { border-color: var(--m-color-primary); }
.m-msg-chat-open .m-chat-header {
  position: static;
  flex: 0 0 auto;
  margin: 0 calc(-1 * var(--m-space-4));
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
  border-radius: var(--m-radius-md);
  border: none;
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  box-shadow: var(--m-shadow-fab);
  transition: transform 0.1s;
}
.m-chat-send:active { transform: scale(0.95); }
.m-chat-send:disabled {
  background: var(--m-color-text-disabled);
  box-shadow: none;
  cursor: not-allowed;
}

.m-safe-bottom { height: 80px; }

.m-retention-notice {
  display: flex;
  align-items: center;
  gap: var(--m-space-1);
  margin: var(--m-space-2) 0 0;
  padding: var(--m-space-1) var(--m-space-2);
  background: var(--m-color-info-bg);
  border-radius: var(--m-radius-md);
  font-size: var(--m-font-size-caption);
  color: var(--m-color-info-text);
  line-height: var(--m-line-height-base);
}

/* 快捷回复按钮（输入框内） */
.m-chat-quick-reply-btn {
  width: 30px;
  height: 30px;
  margin-bottom: var(--m-space-2);
  padding: 0;
  border: 1px solid var(--m-color-text-tertiary);
  border-radius: var(--m-radius-circle);
  background: var(--m-color-bg-card);
  color: var(--m-color-text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
}
.m-chat-quick-reply-btn:active { background: var(--m-color-primary-bg); color: var(--m-color-primary); }

/* 快捷回复模板底部弹层 */
.m-quick-reply-mask {
  position: fixed;
  inset: 0;
  background: var(--m-mask-modal);
  z-index: 250;
  display: flex;
  align-items: flex-end;
}
.m-quick-reply-sheet {
  background: var(--m-color-bg-elevated);
  border-radius: var(--m-radius-2xl) var(--m-radius-2xl) 0 0;
  width: 100%;
  max-height: 60vh;
  display: flex;
  flex-direction: column;
}
.m-quick-reply-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--m-space-4);
  border-bottom: 1px solid var(--m-color-border-light);
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-bold);
}
.m-quick-reply-close {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--m-color-text-tertiary);
  padding: var(--m-space-1);
  display: flex;
  align-items: center;
  justify-content: center;
}
.m-quick-reply-body {
  flex: 1;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: var(--m-space-3);
}
.m-quick-reply-loading,
.m-quick-reply-empty {
  text-align: center;
  padding: var(--m-space-8) var(--m-space-4);
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-body);
}
.m-quick-reply-list {
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
}
.m-quick-reply-item {
  text-align: left;
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3);
  cursor: pointer;
}
.m-quick-reply-item:active { background: var(--m-color-bg-hover); }
.m-quick-reply-item-title {
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  margin-bottom: var(--m-space-1);
}
.m-quick-reply-item-content {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
