import { clearAuth, getToken } from './auth.js'

let eventSource = null
let reconnectTimer = null
let connecting = false
let reconnectAttempts = 0
let keepAliveTimer = null
let lastMessageTime = 0
let currentSseStatus = 'disconnected'

const apiBaseUrl = import.meta.env.VITE_API_BASE || '/api'
const MAX_RECONNECT_DELAY = 10000      // 最大重连间隔 10s
const KEEPALIVE_INTERVAL = 25000       // 每 25s 检查一次连接活性
const STALE_THRESHOLD = 90000          // 90s 无消息才认为断连（容忍服务端注释心跳）
const MAX_RECONNECT_ATTEMPTS = 20      // 最大重连次数，超过后停止重连避免无限堆积错误

function publishSseStatus(onStatus, status) {
  currentSseStatus = status
  onStatus?.(status)
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('xya-sse-status', { detail: status }))
  }
}

export function getSseStatus() {
  return currentSseStatus
}

function resolveSseBaseUrl() {
  if (typeof window === 'undefined') return apiBaseUrl.replace(/\/$/, '')
  try {
    return new URL(apiBaseUrl, window.location.origin).toString().replace(/\/$/, '')
  } catch {
    return apiBaseUrl.startsWith('http') ? apiBaseUrl.replace(/\/$/, '') : window.location.origin + apiBaseUrl
  }
}

function scheduleReconnect(onEvent, onStatus) {
  // 先清除已有定时器，避免 onerror 多次触发导致重复重连
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  const token = getToken()
  if (!token) {
    publishSseStatus(onStatus, 'disconnected')
    return
  }
  // 超过最大重连次数则停止重连，避免控制台无限堆积错误日志
  if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
    console.warn(`[SSE] 已达最大重连次数(${MAX_RECONNECT_ATTEMPTS})，停止重连`)
    publishSseStatus(onStatus, 'disconnected')
    return
  }
  const delay = Math.min(MAX_RECONNECT_DELAY, 1000 * Math.pow(2, reconnectAttempts))
  reconnectAttempts += 1
  reconnectTimer = window.setTimeout(() => connectSse(onEvent, onStatus), delay)
}

function startKeepAlive(onEvent, onStatus) {
  stopKeepAlive()
  keepAliveTimer = window.setInterval(() => {
    const now = Date.now()
    // 如果 EventSource 存在但长时间没收到消息，主动重连
    if (eventSource && lastMessageTime > 0 && (now - lastMessageTime) > STALE_THRESHOLD) {
      console.warn('[SSE] 连接疑似断连（最后一次消息在', Math.round((now - lastMessageTime) / 1000), '秒前），主动重连')
      publishSseStatus(onStatus, 'reconnecting')
      closeSse(false)
      scheduleReconnect(onEvent, onStatus)
    }
  }, KEEPALIVE_INTERVAL)
}

function stopKeepAlive() {
  if (keepAliveTimer) {
    clearInterval(keepAliveTimer)
    keepAliveTimer = null
  }
}

async function createSseTicket(token) {
  const sseBaseUrl = resolveSseBaseUrl()
  const res = await fetch(`${sseBaseUrl}/sse/ticket`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  })
  if (!res.ok) {
    // 401 时清除 token 并派发事件，避免带过期 token 无限重连
    if (res.status === 401) {
      clearAuth()
      window.dispatchEvent(new CustomEvent('xya-auth-expired', { detail: { message: '登录已过期，请重新登录' } }))
    }
    throw new Error(`SSE ticket request failed: HTTP ${res.status}`)
  }
  const body = await res.json()
  const ticket = body?.data?.ticket || body?.ticket
  if (!ticket) throw new Error('SSE ticket missing')
  return ticket
}

function cleanupSse() {
  // 清理 EventSource 和定时器，但不重置重连计数器（与 closeSse 区别）
  stopKeepAlive()
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
}

export async function connectSse(onEvent, onStatus) {
  // 清理旧连接，但保留 reconnectAttempts 计数器（重连时不可归零）
  cleanupSse()
  const token = getToken()
  if (!token || connecting) return null

  connecting = true
  lastMessageTime = Date.now()
  publishSseStatus(onStatus, 'connecting')
  try {
    const ticket = await createSseTicket(token)
    // 竞态保护：ticket 请求期间用户可能已登出或重新登录
    // 若 token 已不存在（登出），放弃建立连接
    if (!getToken()) {
      publishSseStatus(onStatus, 'disconnected')
      return null
    }
    const sseBaseUrl = resolveSseBaseUrl()
    const url = `${sseBaseUrl}/sse/subscribe?ticket=${encodeURIComponent(ticket)}`
    eventSource = new EventSource(url)

    eventSource.onopen = () => {
      reconnectAttempts = 0
      lastMessageTime = Date.now()
      publishSseStatus(onStatus, 'connected')
      startKeepAlive(onEvent, onStatus)
    }

    eventSource.onmessage = event => {
      lastMessageTime = Date.now()
      if (!event.data) return
      try {
        onEvent?.(JSON.parse(event.data))
      } catch {
        onEvent?.(event.data)
      }
    }

    eventSource.onerror = () => {
      publishSseStatus(onStatus, 'disconnected')
      stopKeepAlive()
      closeSse(false)
      scheduleReconnect(onEvent, onStatus)
    }

    return eventSource
  } catch (e) {
    publishSseStatus(onStatus, 'disconnected')
    // 401 已在 createSseTicket 中处理，不再无限重连
    if (e?.message?.includes('HTTP 401')) {
      return null
    }
    scheduleReconnect(onEvent, onStatus)
    return null
  } finally {
    connecting = false
  }
}

export function closeSse(clearTimer = true) {
  stopKeepAlive()
  if (clearTimer && reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
  // 仅在主动关闭时重置重连计数器（clearTimer=true 表示外部调用，而非 onerror 重连流程）
  if (clearTimer) {
    reconnectAttempts = 0
  }
}
