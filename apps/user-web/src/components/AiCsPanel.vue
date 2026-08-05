<template>
  <Teleport to="body">
    <Transition name="ai-cs-slide">
      <aside
        v-show="visible"
        class="ai-cs-panel"
        role="dialog"
        aria-modal="false"
        aria-labelledby="ai-cs-title"
      >
        <span class="ai-cs-panel-border" aria-hidden="true"></span>

        <header class="ai-cs-header">
          <div class="ai-cs-header-main">
            <div class="ai-cs-avatar-wrap">
              <img class="ai-cs-avatar" :src="avatar" alt="" />
              <span class="ai-cs-status-dot" :class="{ online: ready, busy: streaming }"></span>
            </div>
            <div class="ai-cs-header-text">
              <strong id="ai-cs-title" class="ai-cs-title">小梦 🌙</strong>
              <span class="ai-cs-balance">
                Token 余额：<em>{{ balanceText }}</em>
              </span>
            </div>
          </div>

          <div class="ai-cs-header-actions">
            <button
              type="button"
              class="ai-cs-icon-btn"
              :disabled="loadingSession || historyLoading"
              :title="historyLoading ? '加载中...' : '历史会话'"
              @click="onToggleHistory"
            >
              <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                <path d="M12 8v5l3 2M3 12a9 9 0 1 0 18 0 9 9 0 0 0-18 0z" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
            <button
              type="button"
              class="ai-cs-icon-btn"
              :disabled="compressing || !sessionId"
              :title="compressing ? '压缩中...' : '压缩上下文'"
              @click="onCompress"
            >
              <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                <path d="M4 7h16M6 12h12M4 17h16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </button>
            <button
              type="button"
              class="ai-cs-icon-btn"
              :disabled="loadingSession"
              title="开启新会话"
              @click="onNewSession"
            >
              <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                <path d="M12 5v14M5 12h14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </button>
            <button
              type="button"
              class="ai-cs-close"
              aria-label="关闭"
              @click="emit('close')"
            >
              <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
                <path d="M6 6l12 12M18 6 6 18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </button>
          </div>
        </header>

        <div ref="messagesRef" class="ai-cs-messages" tabindex="0">
          <!-- 历史会话面板（覆盖在消息列表之上） -->
          <Transition name="ai-cs-history-fade">
            <div v-if="historyVisible" class="ai-cs-history-panel">
              <div class="ai-cs-history-header">
                <strong>历史会话</strong>
                <span class="ai-cs-history-count">{{ historyList.length }} 条</span>
                <button
                  type="button"
                  class="ai-cs-history-close"
                  :disabled="historyLoading"
                  @click="historyVisible = false"
                  aria-label="关闭历史会话"
                >
                  <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
                    <path d="M6 6l12 12M18 6 6 18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                  </svg>
                </button>
              </div>

              <div v-if="historyLoading" class="ai-cs-history-loading">
                <div class="ai-cs-loading-spinner" aria-hidden="true"></div>
                <span>加载历史会话...</span>
              </div>
              <div v-else-if="historyError" class="ai-cs-history-error">
                {{ historyError }}
                <button type="button" class="ai-cs-history-retry" @click="loadHistory">重试</button>
              </div>
              <div v-else-if="historyList.length === 0" class="ai-cs-history-empty">
                暂无历史会话
              </div>
              <div v-else class="ai-cs-history-list">
                <button
                  v-for="s in historyList"
                  :key="s.id"
                  type="button"
                  class="ai-cs-history-item"
                  :class="{
                    active: s.id === sessionId,
                    closed: !s.isActive,
                    resuming: resumingSessionId === s.id
                  }"
                  :disabled="resumingSessionId === s.id || loadingSession"
                  @click="onSelectHistorySession(s)"
                >
                  <div class="ai-cs-history-item-head">
                    <span class="ai-cs-history-status" :class="s.isActive ? 'active' : 'closed'">
                      {{ s.isActive ? '进行中' : '已结束' }}
                    </span>
                    <span class="ai-cs-history-meta">{{ s.messageCount || 0 }} 条消息</span>
                    <span class="ai-cs-history-time">{{ formatHistoryTime(s.lastActiveTime || s.createdTime) }}</span>
                  </div>
                  <div class="ai-cs-history-preview">
                    {{ s.firstUserMessagePreview || (s.compressedSummaryPreview ? '[已压缩] ' + s.compressedSummaryPreview : '暂无消息预览') }}
                  </div>
                  <div v-if="resumingSessionId === s.id" class="ai-cs-history-resuming">
                    <div class="ai-cs-loading-spinner" aria-hidden="true"></div>
                    <span>恢复中...</span>
                  </div>
                </button>
              </div>
            </div>
          </Transition>

          <div v-if="loadingSession" class="ai-cs-loading">
            <div class="ai-cs-loading-spinner" aria-hidden="true"></div>
            <span>正在连接小梦...</span>
          </div>

          <template v-else>
            <div
              v-for="msg in messages"
              :key="msg.id"
              class="ai-cs-msg-row"
              :class="`msg-${msg.role}`"
            >
              <img
                v-if="msg.role === 'assistant'"
                class="ai-cs-msg-avatar"
                :src="avatar"
                alt=""
              />

              <div class="ai-cs-msg-body">
                <div v-if="msg.type === 'casual_remind'" class="ai-cs-casual">
                  <span class="ai-cs-casual-icon" aria-hidden="true">i</span>
                  <span>{{ msg.content }}</span>
                </div>

                <div v-else-if="msg.type === 'insufficient_balance'" class="ai-cs-insufficient">
                  <p>{{ msg.content }}</p>
                  <button type="button" class="ai-cs-recharge-btn" @click="onRecharge">
                    立即充值
                  </button>
                </div>

                <div
                  v-else-if="msg.type === 'tool_call'"
                  class="ai-cs-tool-card"
                  :class="`tool-${msg.status}`"
                >
                  <div class="ai-cs-tool-head">
                    <span class="ai-cs-tool-badge">工具</span>
                    <strong>{{ msg.name }}</strong>
                    <span v-if="msg.status === 'executed'" class="ai-cs-tool-status-text executed">已执行</span>
                    <span v-else-if="msg.status === 'failed'" class="ai-cs-tool-status-text failed">执行失败</span>
                    <span v-else-if="msg.status === 'rejected'" class="ai-cs-tool-status-text rejected">已拒绝</span>
                    <span v-else-if="msg.status === 'accepted'" class="ai-cs-tool-status-text accepted">执行中</span>
                  </div>
                  <p v-if="msg.description" class="ai-cs-tool-desc">{{ msg.description }}</p>
                  <pre v-if="msg.argumentsText && msg.expanded" class="ai-cs-tool-args">{{ msg.argumentsText }}</pre>

                  <!-- 二维码图片（create_qr_login 工具结果） -->
                  <div v-if="msg.qrImage" class="ai-cs-tool-qr">
                    <img :src="msg.qrImage" alt="扫码登录二维码" class="ai-cs-qr-img" />
                    <span class="ai-cs-qr-tip">请使用闲鱼 App 扫描二维码完成登录</span>
                  </div>

                  <div v-if="msg.status === 'pending'" class="ai-cs-tool-actions">
                    <button type="button" class="ai-cs-tool-btn accept" @click="onToolConfirm(msg, true)">
                      同意执行
                    </button>
                    <button type="button" class="ai-cs-tool-btn reject" @click="onToolConfirm(msg, false)">
                      拒绝
                    </button>
                  </div>

                  <button
                    v-if="msg.resultText"
                    type="button"
                    class="ai-cs-tool-toggle"
                    @click="msg.expanded = !msg.expanded"
                  >
                    {{ msg.expanded ? '收起详情' : '查看详情' }}
                  </button>
                  <div v-if="msg.resultText && msg.expanded" class="ai-cs-tool-result">
                    <pre>{{ msg.resultText }}</pre>
                  </div>
                </div>

                <div v-else class="ai-cs-msg-bubble" :class="msg.role">
                  <span class="ai-cs-msg-text" v-html="renderContent(msg.content)"></span>
                </div>

                <time v-if="msg.type !== 'tool_call'" class="ai-cs-msg-time">
                  {{ formatTime(msg.timestamp) }}
                </time>
              </div>
            </div>

            <div v-if="streaming" class="ai-cs-msg-row msg-assistant">
              <img class="ai-cs-msg-avatar" :src="avatar" alt="" />
              <div class="ai-cs-typing" aria-label="小梦正在输入">
                <span></span><span></span><span></span>
              </div>
            </div>
          </template>
        </div>

        <div class="ai-cs-input-area">
          <textarea
            ref="inputRef"
            v-model="input"
            class="ai-cs-input"
            placeholder="输入消息，Enter 发送，Shift+Enter 换行"
            rows="1"
            maxlength="2000"
            :disabled="!ready || streaming"
            @keydown.enter.exact.prevent="onSend"
            @input="autoResize"
          ></textarea>
          <button
            type="button"
            class="ai-cs-send"
            :disabled="!canSend"
            @click="onSend"
          >
            <svg v-if="streaming" viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
              <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor"/>
            </svg>
            <svg v-else viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
              <path d="M3 12l18-8-8 18-2-7-8-3z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
            </svg>
            <span>{{ streaming ? '生成中' : '发送' }}</span>
          </button>
        </div>

        <Transition name="ai-cs-fade">
          <div
            v-if="contextExceeded"
            class="ai-cs-modal-mask"
            role="dialog"
            aria-modal="true"
            aria-labelledby="ai-cs-ctx-title"
          >
            <div class="ai-cs-modal">
              <div class="ai-cs-modal-icon" aria-hidden="true">!</div>
              <h3 id="ai-cs-ctx-title">上下文已超限</h3>
              <p>
                当前会话已达到 {{ contextExceeded.maxCount }} 条上下文上限，
                建议开启新会话或压缩历史以继续对话。
              </p>
              <div class="ai-cs-modal-actions">
                <button
                  type="button"
                  class="ai-cs-modal-btn primary"
                  :disabled="loadingSession"
                  @click="onNewSession"
                >
                  开启新会话
                </button>
                <button
                  type="button"
                  class="ai-cs-modal-btn"
                  :disabled="compressing"
                  @click="onCompress"
                >
                  {{ compressing ? '压缩中...' : '压缩上下文' }}
                </button>
              </div>
            </div>
          </div>
        </Transition>
      </aside>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import {
  closeSession,
  compressContext,
  confirmToolCall,
  createSession,
  currentSession,
  getCsConfig,
  listMessages,
  listUserSessions,
  resumeSession,
  streamChat
} from '../api/aiCs.js'
import { getAiBillingBalance } from '../api/aiBilling.js'

const props = defineProps({
  visible: { type: Boolean, default: false }
})
const emit = defineEmits(['close'])

const AVATAR = '/xya/chat_ui_assets/chat_ui_assets_023.png'
const avatar = AVATAR

const messagesRef = ref(null)
const inputRef = ref(null)
const messages = ref([])
const input = ref('')
const sessionId = ref(null)
const sessionToken = ref('')
const balance = ref(0)
const ready = ref(false)
const loadingSession = ref(false)
const streaming = ref(false)
const compressing = ref(false)
const casualRemindShown = ref(false)
const contextExceeded = ref(null)

// 历史会话面板
const historyVisible = ref(false)
const historyLoading = ref(false)
const historyError = ref('')
const historyList = ref([])
const resumingSessionId = ref(null)

let abortStream = null
let msgSeq = 0

const balanceText = computed(() => {
  const v = Number(balance.value) || 0
  if (v <= 0) return '0'
  return v.toLocaleString()
})

const canSend = computed(
  () => ready.value && !streaming.value && input.value.trim().length > 0
)

function genId() {
  msgSeq += 1
  return `m-${Date.now()}-${msgSeq}`
}

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  const hh = d.getHours().toString().padStart(2, '0')
  const mm = d.getMinutes().toString().padStart(2, '0')
  return `${hh}:${mm}`
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function renderContent(content) {
  if (!content) return ''
  return escapeHtml(content).replace(/\n/g, '<br />')
}

function autoResize() {
  const el = inputRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}

function resetInput() {
  input.value = ''
  nextTick(() => {
    const el = inputRef.value
    if (el) el.style.height = 'auto'
  })
}

function scrollToBottom() {
  nextTick(() => {
    const el = messagesRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

function pushMessage(msg) {
  messages.value.push(msg)
  scrollToBottom()
}

function formatJsonLike(value) {
  if (value == null || value === '') return ''
  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
      try {
        return JSON.stringify(JSON.parse(trimmed), null, 2)
      } catch (_) {
        return value
      }
    }
    return value
  }
  try {
    return JSON.stringify(value, null, 2)
  } catch (_) {
    return String(value)
  }
}

async function initSession() {
  loadingSession.value = true
  ready.value = false
  messages.value = []
  sessionId.value = null
  sessionToken.value = ''
  casualRemindShown.value = false
  // 注意：额度提醒去重改为 localStorage 按日记录，不再在 initSession 中重置
  contextExceeded.value = null

  try {
    const [balRes, existing] = await Promise.all([
      getAiBillingBalance().catch((e) => {
        // 余额拉取失败时打印诊断信息，避免静默吞掉异常导致 0 余额误导用户
        console.warn('[AiCsPanel] 拉取 Token 余额失败：', e?.message || e)
        return null
      }),
      currentSession().catch((e) => {
        console.warn('[AiCsPanel] 查询当前会话失败：', e?.message || e)
        return null
      })
    ])
    // 直接读取 /ai-billing/balance 返回的 tokenBalance（与个人中心同源）
    const bal = Number(balRes?.tokenBalance ?? balRes?.balance ?? 0)
    if (Number.isFinite(bal)) balance.value = bal

    let session = (existing && existing.data && existing.data.sessionId) ? existing.data : (existing && existing.sessionId ? existing : null)
    if (!session) {
      const created = await createSession()
      session = created?.data || created
    }

    sessionId.value = session.sessionId
    sessionToken.value = session.sessionToken || ''

    const welcome =
      session.welcomeMessage || '你好，我是小梦，有什么可以帮你的吗？'
    pushMessage({
      id: genId(),
      role: 'assistant',
      type: 'text',
      content: welcome,
      timestamp: Date.now()
    })

    try {
      const historyRes = await listMessages(session.sessionId, 50)
      const history = historyRes?.data || historyRes
      if (Array.isArray(history?.messages) && history.messages.length) {
        for (const m of history.messages) {
          messages.value.push(normalizeHistoryMessage(m))
        }
        scrollToBottom()
      }
    } catch (_) {}

    ready.value = true
  } catch (err) {
    pushMessage({
      id: genId(),
      role: 'system',
      type: 'text',
      content: `连接小梦失败：${err?.message || '未知错误'}`,
      timestamp: Date.now()
    })
  } finally {
    loadingSession.value = false
  }
}

function normalizeHistoryMessage(m) {
  const role = m.role === 'user' ? 'user' : 'assistant'
  return {
    id: m.id || m.messageId || genId(),
    role,
    type: 'text',
    content: m.content || m.text || '',
    timestamp: m.createdAt || m.timestamp || Date.now()
  }
}

async function onSend() {
  if (!canSend.value) return
  const text = input.value.trim()
  if (!text) return

  pushMessage({
    id: genId(),
    role: 'user',
    type: 'text',
    content: text,
    timestamp: Date.now()
  })

  resetInput()
  await runStream(text)
}

async function runStream(text) {
  if (!sessionId.value) return
  streaming.value = true

  const assistantMsg = {
    id: genId(),
    role: 'assistant',
    type: 'text',
    content: '',
    timestamp: Date.now()
  }
  pushMessage(assistantMsg)

  // 60 秒超时保护：防止 SSE 流永久挂起
  const streamTimeout = setTimeout(() => {
    if (abortStream) {
      try { abortStream() } catch (_) {}
      abortStream = null
    }
    streaming.value = false
    if (!assistantMsg.content) {
      assistantMsg.content = '小梦响应超时，请重试。'
    } else {
      assistantMsg.content += '\n\n小梦响应超时，请重试。'
    }
    scrollToBottom()
  }, 60000)

  abortStream = streamChat({
    sessionId: sessionId.value,
    message: text,
    onEvent: (evt) => handleEvent(evt, assistantMsg),
    onError: (err, status) => {
      streaming.value = false
      abortStream = null
      // 网络层错误：替换空气泡为友好错误提示，避免堆叠 [出错] 前缀
      const errMsg = err?.message || '网络异常'
      const friendly = friendlyErrorMessage(errMsg, status)
      if (!assistantMsg.content) {
        assistantMsg.content = friendly
      } else {
        assistantMsg.content = `${assistantMsg.content}\n\n${friendly}`
      }
      // SSE 401 不再踢出登录：UserJwtAuthFilter 已修复 ASYNC 分发误判问题，
      // 真实 401 极少见；此处仅在 402/insufficient_balance 时刷新余额并展示充值卡片
      if (status === 402 || /insufficient_balance|余额不足/i.test(errMsg)) {
        refreshBalance().then(() => {
          if (balance.value <= 0) {
            pushMessage({
              id: genId(),
              role: 'assistant',
              type: 'insufficient_balance',
              content: 'Token 余额不足，请充值后继续。',
              timestamp: Date.now()
            })
          }
        })
      } else if (/余额|balance|insufficient/i.test(errMsg)) {
        // 仅在错误信息明显指向余额时刷新一次余额（不直接清零，避免 48026 被误清零）
        refreshBalance()
      }
      scrollToBottom()
    },
    onClose: () => {
      clearTimeout(streamTimeout)
      streaming.value = false
      abortStream = null
      refreshBalance()
      // 流结束：若 AI 气泡仍为空且无待确认工具调用，替换为"服务不在线"友好提示
      if (!assistantMsg.content && !hasToolCallPending()) {
        const idx = messages.value.findIndex((m) => m.id === assistantMsg.id)
        if (idx >= 0) {
          // 替换为系统提示消息，而不是删除（让用户看到反馈）
          messages.value[idx] = {
            id: assistantMsg.id,
            role: 'system',
            type: 'text',
            content: '小梦暂时不在线，请稍后重试。若问题持续，可点击右上角刷新会话。',
            timestamp: Date.now()
          }
          scrollToBottom()
        }
      }
    }
  })
}

function handleEvent(evt, assistantMsg) {
  const { event, data } = evt || {}
  const type = data?.type || event
  switch (event) {
    case 'connected':
      // 连接建立成功，无需特殊处理
      break
    case 'delta':
    case 'content': {
      assistantMsg.content += data.content || ''
      scrollToBottom()
      break
    }
    case 'tool_call': {
      // 兼容两种负载：直接字段或嵌套 toolCall
      const payload = data.toolCall || data
      pushMessage({
        id: genId(),
        role: 'assistant',
        type: 'tool_call',
        toolCallId: payload.toolCallId || payload.tool_call_id || 0,
        name: payload.name || payload.tool || '',
        argumentsText: formatJsonLike(payload.arguments),
        description: data.description || payload.description || data.message || '',
        status: 'pending',
        resultText: '',
        expanded: false,
        timestamp: Date.now()
      })
      break
    }
    case 'tool_result': {
      // 查询类工具自动执行后直接发送 tool_result（前面没有 tool_call 事件）
      // 此时需要新建一条消息展示结果；若已有对应 tool_call 消息则更新它
      const found = messages.value.find(
        (m) => m.type === 'tool_call' && m.toolCallId === data.toolCallId
      )
      // 提取二维码图片 data（create_qr_login 工具返回）
      let qrImage = ''
      if (data.result && typeof data.result === 'object') {
        const qrField = data.result.qrImage || (data.result.data && data.result.data.qrImage) || ''
        if (qrField && typeof qrField === 'string' && qrField.length > 100) {
          qrImage = qrField
        }
      }
      if (found) {
        found.status = data.status || 'executed'
        found.resultText = formatJsonLike(data.result)
        if (qrImage) found.qrImage = qrImage
      } else {
        // 自动执行的查询工具：直接展示为已完成的工具卡片（默认折叠）
        const msg = {
          id: genId(),
          role: 'assistant',
          type: 'tool_call',
          toolCallId: data.toolCallId || 0,
          name: data.tool || '',
          argumentsText: '',
          description: data.message || '查询完成',
          status: data.status || 'executed',
          resultText: formatJsonLike(data.result),
          expanded: false,
          timestamp: Date.now()
        }
        if (qrImage) msg.qrImage = qrImage
        pushMessage(msg)
      }
      break
    }
    case 'insufficient_balance': {
      pushMessage({
        id: genId(),
        role: 'assistant',
        type: 'insufficient_balance',
        content: data.message || 'Token 余额不足，请充值后继续。',
        timestamp: Date.now()
      })
      // 后端主动告知余额不足时，刷新一次以获取真实余额（不直接清零，避免假阴性）
      refreshBalance()
      break
    }
    case 'context_exceeded': {
      contextExceeded.value = {
        currentCount: data.currentCount,
        maxCount: data.maxCount
      }
      break
    }
    case 'casual_remind': {
      if (!casualRemindShown.value) {
        casualRemindShown.value = true
        pushMessage({
          id: genId(),
          role: 'assistant',
          type: 'casual_remind',
          content:
            data.message ||
            '已闲聊多次，建议创建任务让我帮你处理具体业务哦。',
          timestamp: Date.now()
        })
      }
      break
    }
    case 'done': {
      if (typeof data.tokensCharged === 'number' && data.tokensCharged > 0) {
        balance.value = Math.max(0, balance.value - data.tokensCharged)
      }
      // 流正常结束：若 AI 没有任何内容（既无文本也无工具调用），给出友好提示
      if (!assistantMsg.content && !hasToolCallPending()) {
        pushMessage({
          id: genId(),
          role: 'system',
          type: 'text',
          content: '小梦暂时没有可回复的内容，请稍后重试或换一种问法。',
          timestamp: Date.now()
        })
      }
      break
    }
    case 'error': {
      const errMsg = data.message || '请求失败'
      // 把错误信息替换为友好提示（避免在空气泡末尾追加 [出错]）
      assistantMsg.content = assistantMsg.content
        ? `${assistantMsg.content}\n\n${errMsg}`
        : errMsg
      scrollToBottom()
      break
    }
    case 'message':
    default: {
      // 兼容无 event 行的默认事件（旧协议：data.type 分发）
      if (type === 'delta' || type === 'content') {
        assistantMsg.content += data.content || ''
        scrollToBottom()
      } else if (type === 'done') {
        if (typeof data.tokensCharged === 'number' && data.tokensCharged > 0) {
          balance.value = Math.max(0, balance.value - data.tokensCharged)
        }
      } else if (type === 'error') {
        const errMsg = data.message || '请求失败'
        assistantMsg.content = assistantMsg.content
          ? `${assistantMsg.content}\n\n${errMsg}`
          : errMsg
        scrollToBottom()
      }
      break
    }
  }
}

function hasToolCallPending() {
  return messages.value.some(m => m.type === 'tool_call' && m.status === 'pending')
}

// 将底层错误消息转换为用户友好的中文提示
// status 为 HTTP 状态码（0 表示网络层错误，无响应）
function friendlyErrorMessage(rawMsg, status) {
  const msg = String(rawMsg || '')
  // 优先按状态码判定，避免正则误匹配（旧版正则 /auth/i 会把 "authority" 之类也命中）
  if (status === 401) return '登录已过期，请刷新页面后重新登录。'
  if (status === 402) return 'Token 余额不足，请充值后继续。'
  if (status === 503) return 'AI 客服服务暂时不可用，请稍后重试。'
  if (status === 500 || status === 502 || status === 504) return '服务器暂时异常，请稍后重试。'
  if (status === 0 || /timeout|超时|aborted|abort/i.test(msg)) return '请求超时或网络异常，小梦暂时无法响应，请稍后重试。'
  if (/网络|network|fetch/i.test(msg)) return '网络连接异常，请检查网络后重试。'
  return `小梦暂时无法响应：${msg}`
}

async function onToolConfirm(msg, accept) {
  if (!sessionId.value) return
  // toolCallId 为 null/undefined/0 都视为异常（后端未生成真实记录）
  // 给出明确反馈，避免用户点确认按钮无响应
  if (!msg.toolCallId) {
    msg.status = 'failed'
    msg.resultText = '工具调用记录异常（toolCallId 缺失），请重新提问'
    return
  }
  msg.status = accept ? 'accepted' : 'rejected'
  try {
    const res = await confirmToolCall(sessionId.value, msg.toolCallId, accept)
    // 更新工具卡片状态（executed/failed/rejected）
    if (res && typeof res === 'object') {
      msg.status = res.status || (accept ? 'executed' : 'rejected')
      if (res.result) {
        msg.resultText = formatJsonLike(res.result)
        // 提取二维码图片（create_qr_login 工具返回）
        const qrField = res.result.qrImage || (res.result.data && res.result.data.qrImage) || ''
        if (qrField && typeof qrField === 'string' && qrField.length > 100) {
          msg.qrImage = qrField
        }
      }
      // 后端生成自然语言摘要，作为新的 assistant 消息展示
      if (res.summary) {
        pushMessage({
          id: genId(),
          role: 'assistant',
          type: 'text',
          content: res.summary,
          timestamp: Date.now()
        })
        scrollToBottom()
      }
      // 执行操作可能扣费，刷新余额
      refreshBalance()
    }
  } catch (e) {
    console.warn('[AiCsPanel] 工具确认失败：', e?.message || e)
    msg.status = 'pending'
    pushMessage({
      id: genId(),
      role: 'system',
      type: 'text',
      content: '工具确认失败，请重试。',
      timestamp: Date.now()
    })
  }
}

async function onNewSession() {
  contextExceeded.value = null
  if (sessionId.value) {
    try {
      await closeSession(sessionId.value)
    } catch (_) {}
  }
  await initSession()
}

// ==================== 历史会话 ====================

function formatHistoryTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  if (isNaN(d.getTime())) return ''
  const now = new Date()
  const diff = (now - d) / 1000 // 秒
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400 && d.getDate() === now.getDate()) {
    const hh = d.getHours().toString().padStart(2, '0')
    const mm = d.getMinutes().toString().padStart(2, '0')
    return `今天 ${hh}:${mm}`
  }
  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  if (d.getDate() === yesterday.getDate() && d.getMonth() === yesterday.getMonth()) {
    const hh = d.getHours().toString().padStart(2, '0')
    const mm = d.getMinutes().toString().padStart(2, '0')
    return `昨天 ${hh}:${mm}`
  }
  const y = d.getFullYear()
  const m = (d.getMonth() + 1).toString().padStart(2, '0')
  const dd = d.getDate().toString().padStart(2, '0')
  const hh = d.getHours().toString().padStart(2, '0')
  const mm = d.getMinutes().toString().padStart(2, '0')
  return `${y}-${m}-${dd} ${hh}:${mm}`
}

async function onToggleHistory() {
  if (historyVisible.value) {
    historyVisible.value = false
    return
  }
  historyVisible.value = true
  await loadHistory()
}

async function loadHistory() {
  historyLoading.value = true
  historyError.value = ''
  try {
    const res = await listUserSessions(30)
    const list = res?.data || res || []
    historyList.value = Array.isArray(list) ? list : []
  } catch (e) {
    historyError.value = e?.message || '加载失败'
    historyList.value = []
  } finally {
    historyLoading.value = false
  }
}

// 选择历史会话：
// - 若是当前活跃会话：直接关闭历史面板（无需切换）
// - 若是已关闭会话：调用 resume 恢复，然后加载消息
async function onSelectHistorySession(s) {
  if (!s || !s.id) return
  // 已是当前会话：仅关闭历史面板
  if (s.id === sessionId.value) {
    historyVisible.value = false
    return
  }
  // 中断当前流
  abortCurrentStream()
  resumingSessionId.value = s.id
  try {
    if (s.isActive) {
      // 活跃会话但非当前会话：理论上不应出现（每用户仅一个活跃会话），保险起见直接切换
      await switchToSession(s.id)
    } else {
      // 已关闭会话：调用 resume 恢复为活跃
      await resumeSession(s.id)
      await switchToSession(s.id)
    }
    historyVisible.value = false
  } catch (e) {
    pushMessage({
      id: genId(),
      role: 'system',
      type: 'text',
      content: `恢复会话失败：${e?.message || '未知错误'}`,
      timestamp: Date.now()
    })
  } finally {
    resumingSessionId.value = null
  }
}

// 切换到指定会话：拉取该会话的消息并展示
async function switchToSession(targetSessionId) {
  loadingSession.value = true
  ready.value = false
  messages.value = []
  casualRemindShown.value = false
  contextExceeded.value = null
  try {
    sessionId.value = targetSessionId
    // 拉取历史消息
    const historyRes = await listMessages(targetSessionId, 100)
    const history = historyRes?.data || historyRes
    if (Array.isArray(history?.messages) && history.messages.length) {
      for (const m of history.messages) {
        messages.value.push(normalizeHistoryMessage(m))
      }
    } else if (Array.isArray(history)) {
      // 直接返回数组的情况
      for (const m of history) {
        messages.value.push(normalizeHistoryMessage(m))
      }
    }
    ready.value = true
    scrollToBottom()
    // 刷新余额（恢复会话可能涉及扣费上下文变化）
    refreshBalance()
  } catch (e) {
    pushMessage({
      id: genId(),
      role: 'system',
      type: 'text',
      content: `加载会话消息失败：${e?.message || '未知错误'}`,
      timestamp: Date.now()
    })
    ready.value = true
  } finally {
    loadingSession.value = false
  }
}

async function onCompress() {
  if (!sessionId.value || compressing.value) return
  compressing.value = true
  try {
    const res = await compressContext(sessionId.value)
    contextExceeded.value = null
    pushMessage({
      id: genId(),
      role: 'assistant',
      type: 'text',
      content: res?.summary || '上下文已压缩，可以继续对话。',
      timestamp: Date.now()
    })
    if (res?.sessionId) {
      sessionId.value = res.sessionId
    }
  } catch (e) {
    console.warn('[AiCsPanel] 上下文压缩失败：', e?.message || e)
    pushMessage({
      id: genId(),
      role: 'system',
      type: 'text',
      content: '上下文压缩失败，请稍后重试。',
      timestamp: Date.now()
    })
  } finally {
    compressing.value = false
  }
}

function onRecharge() {
  window.dispatchEvent(new CustomEvent('xya-open-payment'))
}

async function refreshBalance() {
  // 直接调用 /ai-billing/balance（与个人中心一致），避免 /ai-cs/config 的 try/catch 把异常吞掉返回 0
  try {
    const bal = await getAiBillingBalance()
    const next = Number(bal?.tokenBalance ?? bal?.balance ?? 0)
    if (Number.isFinite(next)) balance.value = next
  } catch (e) {
    console.warn('[AiCsPanel] 刷新 Token 余额失败：', e?.message || e)
  }
}

function abortCurrentStream() {
  if (abortStream) {
    try {
      abortStream()
    } catch (_) {}
    abortStream = null
  }
  streaming.value = false
}

watch(
  () => props.visible,
  async (visible) => {
    if (visible) {
      // 首次打开：初始化会话；后续展开（路由切换自动收起后）：保留历史，仅刷新余额
      if (!sessionId.value) {
        await initSession()
      } else {
        ready.value = true
        loadingSession.value = false
        refreshBalance()
        nextTick(() => {
          inputRef.value?.focus()
          scrollToBottom()
        })
      }
    } else {
      abortCurrentStream()
    }
  }
)

onBeforeUnmount(() => {
  abortCurrentStream()
})
</script>

<style scoped>
.ai-cs-panel {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: 420px;
  max-width: 100vw;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(20px) saturate(160%);
  -webkit-backdrop-filter: blur(20px) saturate(160%);
  border-top-left-radius: 24px;
  border-bottom-left-radius: 24px;
  box-shadow: -20px 0 60px rgba(17, 35, 67, 0.18);
  z-index: 1100;
  overflow: hidden;
}

.ai-cs-panel-border {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 1px;
  background: linear-gradient(
    to bottom,
    rgba(13, 107, 255, 0.45) 0%,
    rgba(49, 134, 255, 0.15) 50%,
    rgba(13, 107, 255, 0.45) 100%
  );
  pointer-events: none;
  z-index: 1;
}

.ai-cs-slide-enter-active,
.ai-cs-slide-leave-active {
  transition: transform 0.32s cubic-bezier(0.4, 0, 0.2, 1),
    opacity 0.32s ease;
}
.ai-cs-slide-enter-from,
.ai-cs-slide-leave-to {
  transform: translateX(110%);
  opacity: 0;
}

.ai-cs-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px;
  background: linear-gradient(135deg, rgba(237, 245, 255, 0.7), rgba(220, 234, 255, 0.5));
  border-bottom: 1px solid rgba(220, 232, 248, 0.7);
  position: relative;
  z-index: 2;
}

.ai-cs-header-main {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.ai-cs-avatar-wrap {
  position: relative;
  flex-shrink: 0;
}

.ai-cs-avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  object-fit: cover;
  background: linear-gradient(135deg, #cfe1ff, #0d6bff);
  border: 2px solid #fff;
  box-shadow: 0 6px 16px rgba(13, 107, 255, 0.28);
}

.ai-cs-status-dot {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 11px;
  height: 11px;
  border-radius: 50%;
  background: #c4cad5;
  border: 2px solid #fff;
  transition: background 0.2s;
}
.ai-cs-status-dot.online {
  background: #2ebd8f;
}
.ai-cs-status-dot.busy {
  background: #f7a94b;
}

.ai-cs-header-text {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.ai-cs-title {
  font-size: 16px;
  font-weight: 700;
  color: #16213e;
  letter-spacing: 0.5px;
  white-space: nowrap;
}

.ai-cs-balance {
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
}
.ai-cs-balance em {
  font-style: normal;
  font-weight: 600;
  color: #0d6bff;
}

.ai-cs-header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.ai-cs-icon-btn {
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.6);
  color: #35435d;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s, color 0.2s, transform 0.15s;
}
.ai-cs-icon-btn:hover:not(:disabled) {
  background: #fff;
  color: #0d6bff;
  transform: translateY(-1px);
}
.ai-cs-icon-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.ai-cs-close {
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.6);
  color: #35435d;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
}
.ai-cs-close:hover {
  background: #fee;
  color: #ef4444;
}

.ai-cs-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px 18px 12px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  scroll-behavior: smooth;
  position: relative;
}

/* 历史会话面板：覆盖在消息列表之上 */
.ai-cs-history-panel {
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  z-index: 5;
  display: flex;
  flex-direction: column;
  padding: 0;
}

.ai-cs-history-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 18px 12px;
  border-bottom: 1px solid rgba(220, 232, 248, 0.7);
  font-size: 14px;
  color: #16213e;
  flex-shrink: 0;
}
.ai-cs-history-header strong {
  font-size: 15px;
  font-weight: 700;
  color: #16213e;
}
.ai-cs-history-count {
  font-size: 12px;
  color: #64748b;
  background: rgba(241, 245, 249, 0.9);
  padding: 2px 8px;
  border-radius: 999px;
  margin-right: auto;
}
.ai-cs-history-close {
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #64748b;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
}
.ai-cs-history-close:hover:not(:disabled) {
  background: rgba(148, 163, 184, 0.15);
  color: #1e293b;
}
.ai-cs-history-close:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.ai-cs-history-loading,
.ai-cs-history-empty,
.ai-cs-history-error {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #64748b;
  font-size: 13px;
  padding: 24px;
  text-align: center;
}
.ai-cs-history-retry {
  border: 1px solid rgba(13, 107, 255, 0.4);
  background: transparent;
  color: #0d6bff;
  padding: 5px 14px;
  border-radius: 999px;
  font-size: 12px;
  cursor: pointer;
  margin-top: 4px;
}
.ai-cs-history-retry:hover {
  background: rgba(13, 107, 255, 0.08);
}

.ai-cs-history-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 10px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.ai-cs-history-list::-webkit-scrollbar {
  width: 6px;
}
.ai-cs-history-list::-webkit-scrollbar-thumb {
  background: rgba(13, 107, 255, 0.18);
  border-radius: 999px;
}

.ai-cs-history-item {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border: 1px solid rgba(220, 232, 248, 0.9);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  text-align: left;
  transition: background 0.15s, border-color 0.15s, transform 0.1s;
  font-family: inherit;
}
.ai-cs-history-item:hover:not(:disabled) {
  background: rgba(248, 251, 255, 0.95);
  border-color: rgba(13, 107, 255, 0.3);
  transform: translateY(-1px);
}
.ai-cs-history-item:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}
.ai-cs-history-item.active {
  border-color: rgba(13, 107, 255, 0.5);
  background: linear-gradient(135deg, rgba(237, 245, 255, 0.95), rgba(220, 234, 255, 0.7));
  border-left: 3px solid #0d6bff;
}
.ai-cs-history-item.closed {
  background: rgba(248, 250, 252, 0.6);
}
.ai-cs-history-item.resuming {
  border-color: rgba(13, 107, 255, 0.4);
  background: rgba(237, 245, 255, 0.5);
}

.ai-cs-history-item-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: #64748b;
}
.ai-cs-history-status {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}
.ai-cs-history-status.active {
  background: rgba(46, 189, 143, 0.14);
  color: #2ebd8f;
}
.ai-cs-history-status.closed {
  background: rgba(148, 163, 184, 0.18);
  color: #64748b;
}
.ai-cs-history-meta {
  color: #475569;
}
.ai-cs-history-time {
  margin-left: auto;
  color: #94a3b8;
  font-size: 11px;
  white-space: nowrap;
}

.ai-cs-history-preview {
  font-size: 12.5px;
  color: #334155;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  word-break: break-word;
}

.ai-cs-history-resuming {
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 12px;
  color: #0d6bff;
}

/* 历史面板淡入淡出 */
.ai-cs-history-fade-enter-active,
.ai-cs-history-fade-leave-active {
  transition: opacity 0.22s ease;
}
.ai-cs-history-fade-enter-from,
.ai-cs-history-fade-leave-to {
  opacity: 0;
}
.ai-cs-messages::-webkit-scrollbar {
  width: 6px;
}
.ai-cs-messages::-webkit-scrollbar-thumb {
  background: rgba(13, 107, 255, 0.18);
  border-radius: 999px;
}
.ai-cs-messages::-webkit-scrollbar-thumb:hover {
  background: rgba(13, 107, 255, 0.32);
}

.ai-cs-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #64748b;
  font-size: 13px;
  padding: 24px 4px;
}

.ai-cs-loading-spinner {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid rgba(13, 107, 255, 0.2);
  border-top-color: #0d6bff;
  animation: ai-cs-spin 0.8s linear infinite;
}
@keyframes ai-cs-spin {
  to {
    transform: rotate(360deg);
  }
}

.ai-cs-msg-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  max-width: 100%;
}
.ai-cs-msg-row.msg-user {
  flex-direction: row-reverse;
}
.ai-cs-msg-row.msg-system .ai-cs-msg-body {
  max-width: 100%;
}

.ai-cs-msg-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
  background: linear-gradient(135deg, #cfe1ff, #0d6bff);
  border: 1.5px solid #fff;
  box-shadow: 0 4px 10px rgba(13, 107, 255, 0.22);
}

.ai-cs-msg-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: 78%;
}
.msg-user .ai-cs-msg-body {
  align-items: flex-end;
}

.ai-cs-msg-bubble {
  padding: 10px 14px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.65;
  word-break: break-word;
  white-space: normal;
}
.ai-cs-msg-bubble.assistant {
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(220, 232, 248, 0.9);
  border-top-left-radius: 6px;
  color: #1e293b;
  box-shadow: 0 4px 14px rgba(17, 35, 67, 0.06);
}
.ai-cs-msg-bubble.user {
  background: linear-gradient(135deg, #0865f4, #147dff);
  color: #fff;
  border-top-right-radius: 6px;
  box-shadow: 0 6px 16px rgba(8, 101, 244, 0.25);
}
.ai-cs-msg-bubble.system {
  background: rgba(255, 240, 240, 0.85);
  border: 1px solid rgba(239, 68, 68, 0.25);
  color: #b91c1c;
  font-size: 13px;
  border-radius: 10px;
}

.ai-cs-msg-text {
  display: inline;
}

.ai-cs-msg-time {
  font-size: 11px;
  color: #94a3b8;
  margin: 0 4px;
}

.ai-cs-casual {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: linear-gradient(90deg, rgba(255, 247, 230, 0.95), rgba(255, 241, 219, 0.9));
  border: 1px solid rgba(255, 213, 145, 0.7);
  border-radius: 10px;
  font-size: 12.5px;
  color: #874d00;
  line-height: 1.5;
}
.ai-cs-casual-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #f7a94b;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  font-style: italic;
  flex-shrink: 0;
}

.ai-cs-insufficient {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 14px;
  background: rgba(255, 240, 240, 0.85);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 14px;
  max-width: 88%;
}
.ai-cs-insufficient p {
  margin: 0;
  font-size: 13px;
  color: #b91c1c;
  line-height: 1.55;
}
.ai-cs-recharge-btn {
  align-self: flex-start;
  border: 0;
  padding: 7px 16px;
  border-radius: 999px;
  background: linear-gradient(135deg, #ff7a59, #ff5a36);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 6px 14px rgba(255, 90, 54, 0.3);
  transition: transform 0.15s, box-shadow 0.15s;
}
.ai-cs-recharge-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 18px rgba(255, 90, 54, 0.4);
}

.ai-cs-tool-card {
  padding: 12px 14px;
  background: rgba(248, 251, 255, 0.92);
  border: 1px solid rgba(13, 107, 255, 0.35);
  border-left: 3px solid #0d6bff;
  border-radius: 12px;
  max-width: 92%;
  display: flex;
  flex-direction: column;
  gap: 8px;
  box-shadow: 0 6px 18px rgba(13, 107, 255, 0.1);
}
.ai-cs-tool-card.tool-rejected {
  border-color: rgba(148, 163, 184, 0.4);
  border-left-color: #94a3b8;
  background: rgba(248, 250, 252, 0.9);
}
.ai-cs-tool-card.tool-accepted {
  border-color: rgba(46, 189, 143, 0.4);
  border-left-color: #2ebd8f;
}

.ai-cs-tool-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ai-cs-tool-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(13, 107, 255, 0.12);
  color: #0d6bff;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.3px;
}
.ai-cs-tool-head strong {
  font-size: 13.5px;
  color: #1e293b;
}

.ai-cs-tool-desc {
  margin: 0;
  font-size: 12.5px;
  color: #475569;
  line-height: 1.55;
}

.ai-cs-tool-args {
  margin: 0;
  padding: 8px 10px;
  background: rgba(13, 107, 255, 0.06);
  border: 1px solid rgba(13, 107, 255, 0.12);
  border-radius: 8px;
  font-size: 11.5px;
  line-height: 1.5;
  color: #334155;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 160px;
  overflow-y: auto;
  font-family: 'SF Mono', 'Menlo', 'Consolas', monospace;
}

.ai-cs-tool-actions {
  display: flex;
  gap: 8px;
  margin-top: 2px;
}
.ai-cs-tool-btn {
  flex: 0 0 auto;
  border: 0;
  padding: 6px 16px;
  border-radius: 999px;
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}
.ai-cs-tool-btn.accept {
  background: linear-gradient(135deg, #0865f4, #147dff);
  color: #fff;
  box-shadow: 0 4px 12px rgba(8, 101, 244, 0.28);
}
.ai-cs-tool-btn.reject {
  background: rgba(148, 163, 184, 0.18);
  color: #475569;
}
.ai-cs-tool-btn:hover {
  transform: translateY(-1px);
}

.ai-cs-tool-status {
  font-size: 12px;
  color: #2ebd8f;
  font-weight: 500;
}
.ai-cs-tool-status.rejected {
  color: #94a3b8;
}

/* 工具状态文本（头部右侧徽章） */
.ai-cs-tool-status-text {
  margin-left: auto;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.3px;
}
.ai-cs-tool-status-text.executed {
  background: rgba(46, 189, 143, 0.14);
  color: #2ebd8f;
}
.ai-cs-tool-status-text.failed {
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
}
.ai-cs-tool-status-text.rejected {
  background: rgba(148, 163, 184, 0.18);
  color: #64748b;
}
.ai-cs-tool-status-text.accepted {
  background: rgba(13, 107, 255, 0.12);
  color: #0d6bff;
}

/* 查看/收起详情按钮 */
/* 二维码图片（create_qr_login 工具结果） */
.ai-cs-tool-qr {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 12px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
}
.ai-cs-qr-img {
  width: 200px;
  height: 200px;
  object-fit: contain;
  border-radius: 8px;
  border: 1px solid rgba(220, 232, 248, 0.8);
}
.ai-cs-qr-tip {
  font-size: 12px;
  color: #64748b;
  text-align: center;
  line-height: 1.5;
}

.ai-cs-tool-toggle {
  align-self: flex-start;
  border: 0;
  background: transparent;
  padding: 2px 8px;
  font-size: 11.5px;
  color: #0d6bff;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.ai-cs-tool-toggle:hover {
  color: #0865f4;
}

/* executed/failed 卡片状态色 */
.ai-cs-tool-card.tool-executed {
  border-color: rgba(46, 189, 143, 0.35);
  border-left-color: #2ebd8f;
}
.ai-cs-tool-card.tool-failed {
  border-color: rgba(239, 68, 68, 0.3);
  border-left-color: #ef4444;
  background: rgba(254, 242, 242, 0.9);
}

.ai-cs-tool-result {
  margin-top: 4px;
  padding-top: 8px;
  border-top: 1px dashed rgba(148, 163, 184, 0.3);
}
.ai-cs-tool-result-label {
  display: block;
  font-size: 11px;
  color: #94a3b8;
  margin-bottom: 4px;
}
.ai-cs-tool-result pre {
  margin: 0;
  padding: 8px 10px;
  background: rgba(13, 107, 255, 0.05);
  border-radius: 8px;
  font-size: 11.5px;
  line-height: 1.5;
  color: #334155;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 200px;
  overflow-y: auto;
  font-family: 'SF Mono', 'Menlo', 'Consolas', monospace;
}

.ai-cs-typing {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(220, 232, 248, 0.9);
  border-radius: 16px;
  border-top-left-radius: 6px;
  box-shadow: 0 4px 14px rgba(17, 35, 67, 0.06);
}
.ai-cs-typing span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #0d6bff;
  opacity: 0.5;
  animation: ai-cs-bounce 1.2s infinite ease-in-out;
}
.ai-cs-typing span:nth-child(2) {
  animation-delay: 0.2s;
}
.ai-cs-typing span:nth-child(3) {
  animation-delay: 0.4s;
}
@keyframes ai-cs-bounce {
  0%, 80%, 100% {
    transform: scale(0.6);
    opacity: 0.4;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

.ai-cs-input-area {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 14px 18px 18px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0), rgba(255, 255, 255, 0.92) 30%);
  border-top: 1px solid rgba(220, 232, 248, 0.7);
  position: relative;
  z-index: 2;
}

.ai-cs-input {
  flex: 1;
  resize: none;
  max-height: 120px;
  padding: 10px 14px;
  border: 1px solid rgba(220, 232, 248, 0.9);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.85);
  font-size: 14px;
  line-height: 1.5;
  color: #1e293b;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
  font-family: inherit;
}
.ai-cs-input:focus {
  border-color: #0865f4;
  box-shadow: 0 0 0 3px rgba(8, 101, 244, 0.12);
}
.ai-cs-input::placeholder {
  color: #94a3b8;
}
.ai-cs-input:disabled {
  background: rgba(248, 250, 252, 0.7);
  cursor: not-allowed;
}

.ai-cs-send {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 18px;
  border: 0;
  border-radius: 14px;
  background: linear-gradient(135deg, #0865f4, #147dff);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 8px 18px rgba(8, 101, 244, 0.28);
  transition: transform 0.15s, box-shadow 0.15s, opacity 0.15s;
}
.ai-cs-send:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 10px 22px rgba(8, 101, 244, 0.36);
}
.ai-cs-send:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  box-shadow: none;
}

.ai-cs-modal-mask {
  position: absolute;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  z-index: 10;
}

.ai-cs-modal {
  width: 100%;
  max-width: 320px;
  padding: 24px 22px 22px;
  background: #fff;
  border-radius: 18px;
  text-align: center;
  box-shadow: 0 24px 60px rgba(17, 35, 67, 0.3);
  animation: ai-cs-modal-pop 0.28s cubic-bezier(0.4, 0, 0.2, 1);
}
@keyframes ai-cs-modal-pop {
  from {
    transform: scale(0.92);
    opacity: 0;
  }
  to {
    transform: scale(1);
    opacity: 1;
  }
}

.ai-cs-modal-icon {
  width: 48px;
  height: 48px;
  margin: 0 auto 14px;
  border-radius: 50%;
  background: linear-gradient(135deg, #fff1db, #ffd591);
  color: #b45309;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: 800;
  font-style: italic;
}

.ai-cs-modal h3 {
  margin: 0 0 10px;
  font-size: 17px;
  font-weight: 700;
  color: #16213e;
}
.ai-cs-modal p {
  margin: 0 0 18px;
  font-size: 13px;
  line-height: 1.65;
  color: #64748b;
}

.ai-cs-modal-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.ai-cs-modal-btn {
  padding: 10px 18px;
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 12px;
  background: #fff;
  color: #475569;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, transform 0.15s;
}
.ai-cs-modal-btn:hover:not(:disabled) {
  background: #f8fafc;
  transform: translateY(-1px);
}
.ai-cs-modal-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.ai-cs-modal-btn.primary {
  background: linear-gradient(135deg, #0865f4, #147dff);
  border-color: transparent;
  color: #fff;
  box-shadow: 0 8px 18px rgba(8, 101, 244, 0.28);
}
.ai-cs-modal-btn.primary:hover:not(:disabled) {
  background: linear-gradient(135deg, #0759db, #126fe8);
}

.ai-cs-fade-enter-active,
.ai-cs-fade-leave-active {
  transition: opacity 0.22s ease;
}
.ai-cs-fade-enter-from,
.ai-cs-fade-leave-to {
  opacity: 0;
}

@media (max-width: 480px) {
  .ai-cs-panel {
    width: 100vw;
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
  }
  .ai-cs-msg-body {
    max-width: 82%;
  }
  .ai-cs-header {
    padding: 14px 16px;
  }
  .ai-cs-input-area {
    padding: 12px 14px 16px;
  }
}
</style>
