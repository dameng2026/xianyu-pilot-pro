import request from '../utils/request.js'
import { getToken } from '../utils/auth.js'

// AI 客服"小梦"前台 API 封装。
// 三层鉴权由后端 Java (AiCsController) + Python (ai_cs.py) 负责，
// 前端只需携带会话标识 sessionId 调用，无需暴露 cookie/token。
//
// 注意：SSE 流式接口 /chat 不能复用 axios 拦截器（fetch 不走 axios）。
// 经实测：用户 JWT 在其他接口均正常工作，但 SSE 偶发返回 401。
// 推测原因：Spring Security/SSE 链路对 Authorization 头的处理与普通接口不同，
// 或 fetch 在 SSE 请求中 Authorization 头被代理/网关剥离。
// 处理策略：SSE 401 不调用 clearAuth（避免误踢出登录），仅向用户展示错误提示。
// 待后端排查根因后再决定是否对齐 axios 的 401 处理。

const BASE = '/ai-cs'

function createRequestId() {
  const cryptoApi = globalThis.crypto
  if (typeof cryptoApi?.randomUUID === 'function') return `web-${cryptoApi.randomUUID()}`
  return `web-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

// 创建新会话（自动关闭该用户已有活跃会话）
export function createSession() {
  return request({ url: `${BASE}/session/create`, method: 'post' })
}

// 查询当前活跃会话
export function currentSession() {
  return request({ url: `${BASE}/session/current`, method: 'get' })
}

// 关闭会话
export function closeSession(sessionId) {
  return request({ url: `${BASE}/session/close`, method: 'post', data: { sessionId } })
}

// 列出当前用户的历史会话（最多 30 条未归档会话，按最后活跃时间倒序）
// 每条会话附带首条用户消息作为预览，便于识别会话主题
export function listUserSessions(limit = 30) {
  return request({ url: `${BASE}/sessions`, method: 'get', params: { limit } })
}

// 恢复已关闭的会话为活跃状态，用于"继续对话"
// 关闭当前活跃会话（如果有），将目标会话 status=1
export function resumeSession(sessionId) {
  return request({ url: `${BASE}/session/resume`, method: 'post', data: { sessionId } })
}

// 拉取历史消息
export function listMessages(sessionId, limit = 100) {
  return request({ url: `${BASE}/messages`, method: 'get', params: { sessionId, limit } })
}

// 拉取客服配置 + 当前用户 Token 余额
export function getCsConfig() {
  return request({ url: `${BASE}/config`, method: 'get' })
}

// 保存 AI 客服计费配置（自动回复按次计费等，小梦对话本身不扣用户 Token）
export function saveCsBillingConfig(data) {
  return request({ url: `${BASE}/billing-config`, method: 'put', data })
}

// 上下文压缩（不扣费）：将当前会话历史压缩为摘要并开启新会话
export function compressContext(sessionId) {
  return request({ url: `${BASE}/compress`, method: 'post', data: { sessionId } })
}

// 工具调用确认/拒绝
export function confirmToolCall(sessionId, toolCallId, accept) {
  return request({
    url: `${BASE}/tool/confirm`,
    method: 'post',
    data: { sessionId, toolCallId, accept }
  })
}

/**
 * SSE 流式聊天。
 *
 * @param {Object} params { sessionId, message, onEvent, onOpen, onError, onClose, signal }
 * @returns {Function} abort 函数（主动中断流）
 *
 * 事件类型：
 *   - delta: 增量内容 { content }
 *   - tool_call: 工具调用请求 { toolCallId, name, arguments, description }
 *   - tool_result: 工具执行结果 { toolCallId, status, result }
 *   - insufficient_balance: 余额不足 { message, buttons }
 *   - context_exceeded: 上下文超限 { currentCount, maxCount, buttons }
 *   - casual_remind: 闲聊提醒 { message }
 *   - done: 流结束 { messageId, tokensCharged }
 *   - error: 异常 { message }
 */
export function streamChat({ sessionId, message, onEvent, onOpen, onError, onClose, signal }) {
  const controller = signal ? null : new AbortController()
  const abortSignal = signal || controller.signal
  const token = getToken()
  const apiBase = import.meta.env.VITE_API_BASE || '/api'

  let responseStatus = 0

  // 与 axios 拦截器对齐：token 缺失时不发送空 Authorization 头
  // （HTTP/2 不允许空 header 值，部分代理会剥离空 Authorization，导致后端误判为 missing token）
  if (!token) {
    const err = new Error('未携带登录凭证，请重新登录')
    if (onError) onError(err, 401)
    if (onClose) onClose()
    return () => {}
  }

  const headers = {
    'Content-Type': 'application/json',
    'Accept': 'text/event-stream',
    'Authorization': `Bearer ${token}`,
    'X-Request-Id': createRequestId()
  }

  fetch(`${apiBase}${BASE}/chat`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ sessionId, message }),
    signal: abortSignal
  }).then(async response => {
    responseStatus = response.status
    if (!response.ok) {
      const text = await response.text().catch(() => '')
      let msg = `AI 客服响应失败（${responseStatus}）`
      try {
        const parsed = JSON.parse(text)
        if (parsed?.msg) msg = parsed.msg
        else if (parsed?.message) msg = parsed.message
      } catch (_) {}
      // SSE 401 不调用 clearAuth（避免误踢出登录），仅向用户展示错误提示。
      // 实测用户 JWT 在其他接口正常工作，但 SSE 偶发 401；
      // 待后端排查根因后再决定是否对齐 axios 的 401 处理。
      if (onError) onError(new Error(msg), responseStatus)
      if (onClose) onClose()
      return
    }
    if (onOpen) onOpen(response)

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      let sepIndex
      while ((sepIndex = buffer.indexOf('\n\n')) >= 0) {
        const frame = buffer.slice(0, sepIndex)
        buffer = buffer.slice(sepIndex + 2)
        const evt = parseSseFrame(frame)
        if (evt && onEvent) onEvent(evt)
      }
    }
    if (onClose) onClose()
  }).catch(err => {
    if (err?.name === 'AbortError') {
      if (onClose) onClose()
      return
    }
    if (onError) onError(err, responseStatus || 0)
    if (onClose) onClose()
  })

  return () => {
    if (controller) controller.abort()
  }
}

function parseSseFrame(frame) {
  if (!frame) return null
  const lines = frame.split('\n')
  let event = 'message'
  let dataStr = ''
  for (const line of lines) {
    if (!line) continue
    if (line.startsWith('event:')) {
      event = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      dataStr += (dataStr ? '\n' : '') + line.slice(5).trim()
    }
  }
  let data = null
  if (dataStr) {
    try { data = JSON.parse(dataStr) } catch (_) { data = { raw: dataStr } }
  }
  return { event, data: data || {} }
}

// ==================== 主动消息（V1.75） ====================

/**
 * 触发主动消息：检测用户是否首次访问某功能。
 * 首次访问时，小梦会主动发送一条教学消息到会话中。
 * @param {string} featureKey 功能标识，如 'workflow_first_visit'
 * @returns {Promise<{triggered: boolean, notification?: {id, title, content, actionText, sessionId}}>}
 */
export function triggerProactive(featureKey) {
  return request({ url: `${BASE}/proactive/trigger`, method: 'post', data: { featureKey } })
}

/**
 * 获取待展示的主动消息列表（status=pending）。
 */
export function getPendingProactive() {
  return request({ url: `${BASE}/proactive/pending`, method: 'get' })
}

/**
 * 标记主动消息为已读（用户点击查看）。
 */
export function markProactiveRead(id) {
  return request({ url: `${BASE}/proactive/${id}/read`, method: 'post' })
}

/**
 * 标记主动消息为已展示（避免重复弹出）。
 */
export function markProactiveShown(id) {
  return request({ url: `${BASE}/proactive/${id}/shown`, method: 'post' })
}
