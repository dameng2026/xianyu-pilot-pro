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

      <div ref="chatBoxRef" class="m-chat-body">
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

      <div class="m-chat-input">
        <div v-if="sendError" class="m-chat-send-error" role="alert">{{ sendError }}</div>
        <input
          v-model="draft"
          type="text"
          placeholder="输入消息..."
          :disabled="!!chatError"
          @keyup.enter="sendCurrentMessage"
        />
        <button class="m-chat-send" :disabled="!draft.trim() || sending || !!chatError" @click="sendCurrentMessage">
          <MIcon name="send" :size="18" />
        </button>
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
import { openTrustedMediaUrl, resolveTrustedMediaUrl } from '../utils/safeMediaUrl.js'
import {
  extractMessageDisplayText,
  findConversationMatchIndex,
  findPreservedConversation,
  getConversationIdentityKey,
  getConversationRecordId,
  isSameConversationByPayload,
  matchesAccountSelection,
  mergeConversationSnapshots
} from '../utils/messagesPageState.js'

defineEmits(['force-desktop', 'navigate'])

const accounts = ref([])
const conversations = ref([])
const loading = ref(true)
const loadError = ref('')
const selectedAccountId = ref('')
const filterType = ref('all')

const activeChat = ref(null)
const chatMessages = ref([])
const chatLoading = ref(false)
const chatError = ref('')
const chatBoxRef = ref(null)
const draft = ref('')
const sending = ref(false)
const sendError = ref('')
let pollingTimer = null

const filterTabs = computed(() => [
  { key: 'all', label: '全部', count: conversations.value.length },
  { key: 'unreplied', label: '未回复', count: conversations.value.filter(c => Number(c.unreadCount || 0) > 0).length },
  { key: 'inProgress', label: '进行中', count: conversations.value.filter(c => !isCompleted(c)).length },
  { key: 'completed', label: '已完成', count: conversations.value.filter(c => isCompleted(c)).length },
  { key: 'robot', label: '机器人', count: conversations.value.filter(c => !!c.botEnabled).length }
])

const emptyText = computed(() => {
  if (filterType.value === 'unreplied') return '暂无未回复消息'
  if (filterType.value === 'inProgress') return '暂无进行中会话'
  if (filterType.value === 'completed') return '暂无已完成会话'
  if (filterType.value === 'robot') return '暂无机器人会话'
  return '暂无新消息'
})

const filteredConversations = computed(() => {
  return conversations.value.filter(c => {
    if (filterType.value === 'unreplied') return Number(c.unreadCount || 0) > 0
    if (filterType.value === 'inProgress') return !isCompleted(c)
    if (filterType.value === 'completed') return isCompleted(c)
    if (filterType.value === 'robot') return !!c.botEnabled
    return true
  })
})

function isCompleted(c) {
  return ['completed', 'closed', 'transferred'].includes(c.sessionStatus) || c.closed === true
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
    conversations.value = merged
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
  if (conv.unreadCount > 0) {
    try {
      const recordId = getConversationRecordId(conv)
      if (!recordId) throw new Error('当前会话缺少服务端记录编号')
      await markConversationRead(recordId)
      conv.unreadCount = 0
      conversations.value = conversations.value.map(item =>
        isSameConversation(item, conv) ? { ...item, unreadCount: 0 } : item
      )
      activeChat.value = { ...activeChat.value, unreadCount: 0 }
    } catch (readError) {
      chatError.value = readError?.message || '会话已打开，但已读状态同步失败'
    }
  }
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
  const nextConversation = {
    ...payload,
    xianyuAccountId: accountId,
    sid,
    peerUserId,
    lastMessage: preview,
    lastContent: preview,
    lastMessageTime: Number(payload.messageTime || Date.now()),
    updatedAt: Number(payload.messageTime || Date.now()),
    lastIsAutoReply: Boolean(payload.isAutoReply || payload.is_auto_reply),
    botEnabled: Boolean(payload.isAutoReply || payload.is_auto_reply || payload.botEnabled),
  }
  const incomingUnread = String(payload.direction || '').toUpperCase() === 'IN'
  const existingIndex = findConversationMatchIndex(conversations.value, nextConversation)
  if (existingIndex >= 0) {
    const existing = conversations.value[existingIndex]
    const merged = {
      ...existing,
      ...nextConversation,
      unreadCount: isSameConversation(activeChat.value, nextConversation)
        ? 0
        : Math.max(Number(existing.unreadCount || 0), Number(nextConversation.unreadCount || 0)) + (incomingUnread ? 1 : 0),
    }
    conversations.value = [merged, ...conversations.value.filter((_, index) => index !== existingIndex)]
  } else {
    conversations.value = [{ ...nextConversation, unreadCount: incomingUnread ? 1 : 0 }, ...conversations.value]
  }
}

function onSse(event) {
  const data = event?.detail?.payload || event?.detail || {}
  if (!matchesAccountSelection(selectedAccountId.value, data)) return
  const normalized = normalizeMessages([data])[0]
  if (!normalized) return
  loadError.value = ''
  if (activeChat.value && isSameConversation(activeChat.value, data)) {
    chatMessages.value = dedupeMessages([...chatMessages.value, normalized])
    activeChat.value = { ...activeChat.value, unreadCount: 0 }
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
}

onMounted(async () => {
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

.m-filter-tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 12px;
  margin-left: -16px;
  margin-right: -16px;
  padding-left: 16px;
  padding-right: 16px;
  overflow-x: auto;
  overflow-y: hidden;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.m-filter-tabs::-webkit-scrollbar { display: none; }
.m-filter-tab {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: transparent;
  border: none;
  color: #72809a;
  font-size: 13px;
  font-weight: 500;
  padding: 6px 12px;
  border-radius: 100px;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  transition: all 0.15s;
}
.m-filter-tab.active {
  background: rgba(13,107,255,0.1);
  color: #0d6bff;
  font-weight: 600;
}
.m-filter-count {
  background: rgba(13,107,255,0.12);
  color: #0d6bff;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 100px;
  font-weight: 600;
}
.m-filter-tab.active .m-filter-count {
  background: #0d6bff;
  color: white;
}

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
  background: white;
  border-radius: 18px;
  border: 1px solid #f0f4fa;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(31,53,94,0.04);
}
.m-msg-item {
  display: flex;
  gap: 12px;
  padding: 14px 16px;
  border-bottom: 1px solid #f4f7fc;
  cursor: pointer;
  transition: background 0.15s;
}
.m-msg-item:last-child { border-bottom: none; }
.m-msg-item:active { background: #f8faff; }

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

.m-chat-body {
  flex: 1;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: 14px 0;
  min-height: 300px;
}
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

.m-chat-input {
  position: sticky;
  bottom: 0;
  background: white;
  border-top: 1px solid #eef2fa;
  padding: 8px 10px max(8px, env(safe-area-inset-bottom));
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin: 0 -16px;
  padding-left: 12px;
  padding-right: 12px;
}
.m-chat-send-error {
  flex: 0 0 100%;
  color: #c9363e;
  font-size: 11px;
  line-height: 1.4;
}
.m-chat-input input {
  flex: 1;
  height: 38px;
  border: 1px solid #e8edf5;
  border-radius: 100px;
  padding: 0 16px;
  font-size: 14px;
  background: #f8faff;
  outline: none;
  transition: border-color 0.15s;
}
.m-chat-input input:focus { border-color: #0d6bff; background: white; }
.m-msg-chat-open .m-chat-header {
  position: static;
  flex: 0 0 auto;
  margin: 0 -16px;
}
.m-msg-chat-open .m-chat-body {
  min-height: 0;
  overscroll-behavior: contain;
}
.m-msg-chat-open .m-chat-input {
  position: static;
  flex: 0 0 auto;
}
.m-msg-chat-open .m-safe-bottom { display: none; }
.m-chat-send {
  width: 38px;
  height: 38px;
  border-radius: 50%;
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
</style>
