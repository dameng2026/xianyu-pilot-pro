<template>
  <div ref="rootRef" class="m-notif">
    <div class="m-page-header">
      <div class="m-page-title-row">
        <div class="m-page-title-main">
          <h1>消息中心</h1>
          <p class="m-page-sub">系统通知、告警与事件集中查看</p>
        </div>
        <div class="m-sse-badge" :class="sseBadgeClass">
          <span class="m-sse-dot"></span>
          <span>{{ sseStatusText }}</span>
        </div>
      </div>
    </div>

    <div class="m-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        class="m-tab"
        :class="{ active: activeTab === tab.key }"
        @click="switchTab(tab.key)"
      >
        <span>{{ tab.label }}</span>
        <span v-if="tab.count > 0" class="m-tab-count">{{ tab.count }}</span>
      </button>
    </div>

    <div class="m-action-bar">
      <button
        type="button"
        class="m-action-btn"
        :disabled="unreadCount === 0 || markingAllRead"
        @click="markAllRead"
      >
        <MIcon name="checkCircle" :size="14" />
        <span>{{ markingAllRead ? '处理中...' : '全部标记已读' }}</span>
      </button>
      <button
        type="button"
        class="m-action-btn"
        :disabled="refreshing"
        @click="refresh"
      >
        <MIcon name="refreshCw" :size="14" :class="{ rotating: refreshing }" />
        <span>刷新</span>
      </button>
    </div>

    <div class="m-pull-indicator" :style="pullIndicatorStyle">
      <MIcon name="refreshCw" :size="16" :class="{ rotating: refreshing }" />
      <span>{{ pullText }}</span>
    </div>

    <div v-if="loading && notifications.length === 0" class="m-loading">
      <div class="m-loading-spinner"></div>
      <span>正在加载通知...</span>
    </div>

    <MobileUnavailableState
      v-else-if="loadError && notifications.length === 0"
      title="通知列表暂时无法加载"
      :description="loadError"
      @retry="refresh"
    />

    <div v-else-if="filteredNotifications.length === 0" class="m-empty">
      <div class="m-empty-icon">
        <MIcon name="bell" :size="48" />
      </div>
      <div class="m-empty-text">{{ emptyText }}</div>
      <div class="m-empty-desc">新通知会实时推送到这里</div>
    </div>

    <div v-else class="m-notif-list">
      <div
        v-for="item in filteredNotifications"
        :key="item.id"
        class="m-notif-card"
        :class="{ 'm-notif-unread': !item.read, 'm-notif-expanded': expandedId === item.id }"
        @click="toggleExpand(item)"
      >
        <div class="m-notif-icon" :style="{ background: item.iconBg }">
          <MIcon :name="item.icon" :size="20" :style="{ color: item.color }" />
        </div>
        <div class="m-notif-body">
          <div class="m-notif-head">
            <span class="m-notif-title">{{ item.title }}</span>
            <span v-if="!item.read" class="m-notif-dot" aria-label="未读"></span>
          </div>
          <div class="m-notif-content">{{ item.content || '暂无内容' }}</div>
          <div class="m-notif-meta">
            <span class="m-notif-tag" :style="{ background: item.tagBg, color: item.color }">{{ item.typeLabel }}</span>
            <span class="m-notif-time">{{ item.timeText }}</span>
          </div>
          <div v-if="expandedId === item.id" class="m-notif-detail">
            <div v-if="item.detail" class="m-notif-detail-text">{{ item.detail }}</div>
            <div class="m-notif-detail-meta">
              <span>来源：{{ item.sourceLabel }}</span>
              <span v-if="item.fullTime">时间：{{ item.fullTime }}</span>
            </div>
          </div>
        </div>
        <MIcon name="chevronDown" :size="16" class="m-notif-chevron" :class="{ rotated: expandedId === item.id }" />
      </div>

      <div v-if="!noMore && notifications.length > 0" class="m-load-more" @click="loadMore">
        <MIcon name="refreshCw" :size="14" :class="{ rotating: loadingMore }" />
        <span v-if="loadingMore">加载中...</span>
        <span v-else-if="loadMoreError">{{ loadMoreError }}</span>
        <span v-else>点击或上拉加载更多</span>
      </div>
      <div v-else-if="notifications.length > 0 && !loading" class="m-no-more">
        <span class="m-no-more-line"></span>
        <span>没有更多了</span>
        <span class="m-no-more-line"></span>
      </div>
    </div>

    <div class="m-safe-bottom"></div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import MIcon from './MIcon.vue'
import MobileUnavailableState from './MobileUnavailableState.vue'
import { getNavigationNotifications } from '../api/navigation.js'
import { recordsOfOrThrow } from '../utils/apiData.js'
import { getSseStatus } from '../utils/sse.js'

defineEmits(['navigate', 'force-desktop'])

const PAGE_SIZE = 20

const tabsConfig = [
  { key: 'all', label: '全部' },
  { key: 'unread', label: '未读' },
  { key: 'alert', label: '告警' },
  { key: 'event', label: '事件' }
]

const notifications = ref([])
const loading = ref(true)
const loadingMore = ref(false)
const refreshing = ref(false)
const markingAllRead = ref(false)
const loadError = ref('')
const loadMoreError = ref('')
const noMore = ref(false)
const currentPage = ref(1)
const activeTab = ref('all')
const expandedId = ref(null)
const rootRef = ref(null)
const sseStatus = ref(getSseStatus())

// Pull-to-refresh state
const pulling = ref(false)
const pullDistance = ref(0)
let touchStartY = 0
let touchActive = false
let scrollParentEl = null

const unreadCount = computed(() => notifications.value.filter(n => !n.read).length)

const tabs = computed(() => tabsConfig.map(tab => ({
  ...tab,
  count: tab.key === 'all' ? 0 : countByTab(tab.key)
})))

function countByTab(key) {
  if (key === 'unread') return unreadCount.value
  return notifications.value.filter(n => n.category === key).length
}

const filteredNotifications = computed(() => {
  if (activeTab.value === 'all') return notifications.value
  if (activeTab.value === 'unread') return notifications.value.filter(n => !n.read)
  return notifications.value.filter(n => n.category === activeTab.value)
})

const emptyText = computed(() => {
  if (activeTab.value === 'unread') return '暂无未读通知'
  if (activeTab.value === 'alert') return '暂无告警通知'
  if (activeTab.value === 'event') return '暂无事件通知'
  return '暂无通知'
})

const sseStatusText = computed(() => {
  const status = sseStatus.value
  if (status === 'connected') return '实时'
  if (status === 'connecting') return '连接中'
  if (status === 'reconnecting') return '重连中'
  return '离线'
})

const sseBadgeClass = computed(() => {
  const status = sseStatus.value
  if (status === 'connected') return 'm-sse-online'
  if (status === 'connecting' || status === 'reconnecting') return 'm-sse-connecting'
  return 'm-sse-offline'
})

const pullText = computed(() => {
  if (refreshing.value) return '正在刷新...'
  if (pullDistance.value >= 60) return '释放立即刷新'
  if (pulling.value) return '下拉刷新'
  return ''
})

const pullIndicatorStyle = computed(() => ({
  height: pullDistance.value + 'px',
  opacity: pullDistance.value > 0 || refreshing.value ? 1 : 0
}))

function switchTab(key) {
  if (activeTab.value === key) return
  activeTab.value = key
  expandedId.value = null
}

function noticePalette(type) {
  const t = String(type || '').toLowerCase()
  if (['error', 'fail', 'failed', 'critical'].includes(t)) {
    return { icon: 'alertTriangle', color: '#ef4444', iconBg: 'linear-gradient(135deg, #fee2e2, #fecaca)', tagBg: '#fee2e2' }
  }
  if (['warning', 'warn', 'pending', 'alert'].includes(t)) {
    return { icon: 'alertTriangle', color: '#f59e0b', iconBg: 'linear-gradient(135deg, #fef3c7, #fde68a)', tagBg: '#fef3c7' }
  }
  if (['success', 'delivery', 'shipping'].includes(t)) {
    return { icon: 'checkCircle', color: '#16bf78', iconBg: 'linear-gradient(135deg, #dcfce7, #bbf7d0)', tagBg: '#dcfce7' }
  }
  if (['order', 'bag', 'trade'].includes(t)) {
    return { icon: 'bag', color: '#0d6bff', iconBg: 'linear-gradient(135deg, #dbeafe, #bfdbfe)', tagBg: '#dbeafe' }
  }
  if (['ai', 'bot', 'reply'].includes(t)) {
    return { icon: 'bot', color: '#8b5cf6', iconBg: 'linear-gradient(135deg, #ede9fe, #ddd6fe)', tagBg: '#ede9fe' }
  }
  if (['account', 'cookie'].includes(t)) {
    return { icon: 'user', color: '#ec4899', iconBg: 'linear-gradient(135deg, #fdf2f8, #fce7f3)', tagBg: '#fce7f3' }
  }
  if (t === 'workflow') {
    return { icon: 'workflow', color: '#8b5cf6', iconBg: 'linear-gradient(135deg, #f0ebff, #e2d8ff)', tagBg: '#f0ebff' }
  }
  if (['message', 'chat'].includes(t)) {
    return { icon: 'messageCircle', color: '#06b6d4', iconBg: 'linear-gradient(135deg, #cffafe, #a5f3fc)', tagBg: '#cffafe' }
  }
  return { icon: 'bell', color: '#0d6bff', iconBg: 'linear-gradient(135deg, #e8f1ff, #dbeafe)', tagBg: '#e8f1ff' }
}

function getCategory(type) {
  const t = String(type || '').toLowerCase()
  if (['warning', 'warn', 'error', 'fail', 'failed', 'critical', 'alert'].includes(t)) return 'alert'
  if (['order', 'bag', 'trade', 'delivery', 'shipping', 'account', 'cookie', 'workflow', 'message', 'chat', 'ai', 'bot', 'reply'].includes(t)) return 'event'
  return 'info'
}

function getTypeLabel(type) {
  const t = String(type || '').toLowerCase()
  if (t === 'success') return '成功'
  if (t === 'warning' || t === 'warn' || t === 'pending' || t === 'alert') return '告警'
  if (t === 'error' || t === 'fail' || t === 'failed' || t === 'critical') return '错误'
  if (t === 'order' || t === 'bag' || t === 'trade') return '订单'
  if (t === 'delivery' || t === 'shipping') return '发货'
  if (t === 'account' || t === 'cookie') return '账号'
  if (t === 'workflow') return '工作流'
  if (t === 'ai' || t === 'bot') return 'AI'
  if (t === 'message' || t === 'chat' || t === 'reply') return '消息'
  if (t === 'info') return '通知'
  return t || '通知'
}

function formatTime(value) {
  if (!value) return ''
  const d = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(d.getTime())) return ''
  const now = new Date()
  const diff = (now - d) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}天前`
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${month}-${day}`
}

function formatFullTime(value) {
  if (!value) return ''
  const d = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(d.getTime())) return ''
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function normalizeNotification(raw, source = 'api') {
  if (!raw || typeof raw !== 'object') return null
  const type = raw.type || raw.category || raw.eventType || 'info'
  const palette = noticePalette(type)
  const readRaw = raw.read ?? raw.isRead ?? raw.readStatus ?? raw.read_status
  const read = readRaw === true || readRaw === 'read' || readRaw === 1
  const time = raw.createTime || raw.createdAt || raw.time || raw.created_at || raw.timestamp || new Date().toISOString()
  const content = raw.content || raw.message || raw.desc || raw.description || ''
  const detail = raw.detail || raw.extra || raw.description || ''
  return {
    id: raw.id || `tmp-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    title: raw.title || getTypeLabel(type),
    content,
    detail,
    type,
    typeLabel: getTypeLabel(type),
    category: getCategory(type),
    icon: raw.icon || palette.icon,
    color: palette.color,
    iconBg: palette.iconBg,
    tagBg: palette.tagBg,
    time,
    timeText: formatTime(time),
    fullTime: formatFullTime(time),
    read,
    source: raw.source || source,
    sourceLabel: (raw.source || source) === 'sse' ? '实时推送' : '系统'
  }
}

function mapSseEventType(rawType) {
  const t = String(rawType || '').toLowerCase()
  if (t.includes('cookie')) return 'cookie'
  if (t.includes('delivery')) return 'delivery'
  if (t.includes('order')) return 'order'
  if (t.includes('account')) return 'account'
  if (t.includes('workflow')) return 'workflow'
  if (t === 'message' || t.includes('message')) return 'message'
  if (t.includes('error') || t.includes('fail')) return 'error'
  if (t.includes('warning') || t.includes('warn')) return 'warning'
  if (t.includes('success')) return 'success'
  return 'info'
}

function formatEventTitle(rawType, detail) {
  const t = String(rawType || '')
  const lower = t.toLowerCase()
  if (lower.includes('cookie')) return 'Cookie 状态更新'
  if (lower.includes('delivery')) return '自动发货通知'
  if (lower.includes('order')) return '订单状态变更'
  if (lower.includes('account')) return '账号状态变更'
  if (lower.includes('workflow')) return '工作流执行通知'
  if (lower === 'message') {
    const dir = String(detail?.direction || '').toUpperCase()
    return dir === 'OUT' ? '消息已发送' : '收到新消息'
  }
  if (lower.includes('error') || lower.includes('fail')) return '系统异常'
  if (lower.includes('warning') || lower.includes('warn')) return '系统告警'
  if (lower.includes('success')) return '操作成功'
  return t || '系统通知'
}

// Internal SSE event types that should not surface as notifications
const NON_NOTIFICATION_TYPES = new Set([
  'conversation_auto_reply_state',
  'sse_heartbeat',
  'ping',
  'pong',
  'keepalive'
])

function onSseEvent(event) {
  const detail = event?.detail || {}
  const rawType = detail.type || detail.eventType
  if (!rawType) return
  if (NON_NOTIFICATION_TYPES.has(String(rawType).toLowerCase())) return
  const mappedType = mapSseEventType(rawType)
  const time = detail.time || detail.createdAt || detail.timestamp || new Date().toISOString()
  const notif = normalizeNotification({
    id: detail.id || `sse-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    title: detail.title || formatEventTitle(rawType, detail),
    content: detail.message || detail.content || detail.text || '',
    detail: detail.detail || detail.extra || '',
    type: mappedType,
    time,
    read: false,
    source: 'sse'
  }, 'sse')
  if (!notif) return
  // Dedupe by id (in case SSE resends)
  const exists = notifications.value.some(n => n.id === notif.id)
  if (exists) return
  notifications.value.unshift(notif)
  // Cap to 200 to avoid memory bloat
  if (notifications.value.length > 200) {
    notifications.value.length = 200
  }
}

function onSseStatus(event) {
  sseStatus.value = String(event?.detail || 'disconnected')
}

async function fetchPage(page) {
  const params = {
    page,
    pageSize: PAGE_SIZE,
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE
  }
  const res = await getNavigationNotifications(params)
  const records = recordsOfOrThrow(res?.data, '通知列表响应格式异常')
  return Array.isArray(records) ? records : []
}

async function loadNotifications() {
  loading.value = true
  loadError.value = ''
  loadMoreError.value = ''
  noMore.value = false
  currentPage.value = 1
  expandedId.value = null
  try {
    const records = await fetchPage(1)
    const normalized = records.map(r => normalizeNotification(r, 'api')).filter(Boolean)
    // Preserve any SSE-pushed notifications at the top
    const sseItems = notifications.value.filter(n => n.source === 'sse')
    notifications.value = [...sseItems, ...normalized]
    if (records.length < PAGE_SIZE) {
      noMore.value = true
    }
  } catch (error) {
    loadError.value = error?.message || '请检查网络连接后重试。'
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  if (loadingMore.value || noMore.value || loading.value || refreshing.value) return
  loadingMore.value = true
  loadMoreError.value = ''
  try {
    const nextPage = currentPage.value + 1
    const records = await fetchPage(nextPage)
    if (records.length === 0) {
      noMore.value = true
      return
    }
    const normalized = records.map(r => normalizeNotification(r, 'api')).filter(Boolean)
    // Dedupe by id
    const existingIds = new Set(notifications.value.map(n => n.id))
    const newItems = normalized.filter(n => !existingIds.has(n.id))
    notifications.value = [...notifications.value, ...newItems]
    currentPage.value = nextPage
    if (records.length < PAGE_SIZE) {
      noMore.value = true
    }
  } catch (error) {
    loadMoreError.value = error?.message || '加载失败，点击重试'
  } finally {
    loadingMore.value = false
  }
}

async function refresh() {
  if (refreshing.value) return
  refreshing.value = true
  try {
    await loadNotifications()
  } finally {
    refreshing.value = false
  }
}

function toggleExpand(item) {
  if (expandedId.value === item.id) {
    expandedId.value = null
    return
  }
  expandedId.value = item.id
  // Mark as read on expand (local-only; no backend API)
  if (!item.read) {
    item.read = true
  }
}

function markAllRead() {
  if (unreadCount.value === 0 || markingAllRead.value) return
  markingAllRead.value = true
  // Local-only mark as read (no backend API available)
  notifications.value = notifications.value.map(n => ({ ...n, read: true }))
  setTimeout(() => { markingAllRead.value = false }, 400)
}

// ---- Pull-to-refresh ----
function findScrollParent() {
  let el = rootRef.value?.parentElement
  while (el && el !== document.body) {
    const style = window.getComputedStyle(el)
    if ((style.overflowY === 'auto' || style.overflowY === 'scroll') && el.scrollHeight > el.clientHeight) {
      return el
    }
    el = el.parentElement
  }
  return null
}

function onTouchStart(e) {
  if (refreshing.value) {
    touchActive = false
    return
  }
  const scrollEl = scrollParentEl
  // Only enable pull when starting at the top of the scroll container
  if (!scrollEl || scrollEl.scrollTop > 0) {
    touchStartY = 0
    touchActive = false
    return
  }
  const touch = e.touches[0]
  touchStartY = touch.clientY
  touchActive = true
}

function onTouchMove(e) {
  if (!touchActive || refreshing.value) return
  const touch = e.touches[0]
  const deltaY = touch.clientY - touchStartY
  if (deltaY > 0) {
    pulling.value = true
    pullDistance.value = Math.min(80, deltaY * 0.5)
    if (e.cancelable) e.preventDefault()
  } else if (pulling.value) {
    pulling.value = false
    pullDistance.value = 0
  }
}

async function onTouchEnd() {
  if (!touchActive) return
  touchActive = false
  if (!pulling.value) return
  const shouldRefresh = pullDistance.value >= 60
  pulling.value = false
  if (shouldRefresh) {
    refreshing.value = true
    pullDistance.value = 40
    try {
      await refresh()
    } finally {
      refreshing.value = false
      pullDistance.value = 0
    }
  } else {
    pullDistance.value = 0
  }
}

function onScroll() {
  const el = scrollParentEl
  if (!el) return
  if (loading.value || loadingMore.value || noMore.value || refreshing.value) return
  const distanceToBottom = el.scrollHeight - el.scrollTop - el.clientHeight
  if (distanceToBottom < 100) {
    loadMore()
  }
}

onMounted(async () => {
  scrollParentEl = findScrollParent()
  if (scrollParentEl) {
    scrollParentEl.addEventListener('scroll', onScroll, { passive: true })
  }
  if (rootRef.value) {
    rootRef.value.addEventListener('touchstart', onTouchStart, { passive: true })
    rootRef.value.addEventListener('touchmove', onTouchMove, { passive: false })
    rootRef.value.addEventListener('touchend', onTouchEnd, { passive: true })
    rootRef.value.addEventListener('touchcancel', onTouchEnd, { passive: true })
  }
  window.addEventListener('xya-sse-event', onSseEvent)
  window.addEventListener('xya-sse-status', onSseStatus)
  await loadNotifications()
})

onBeforeUnmount(() => {
  if (scrollParentEl) {
    scrollParentEl.removeEventListener('scroll', onScroll)
    scrollParentEl = null
  }
  if (rootRef.value) {
    rootRef.value.removeEventListener('touchstart', onTouchStart)
    rootRef.value.removeEventListener('touchmove', onTouchMove)
    rootRef.value.removeEventListener('touchend', onTouchEnd)
    rootRef.value.removeEventListener('touchcancel', onTouchEnd)
  }
  window.removeEventListener('xya-sse-event', onSseEvent)
  window.removeEventListener('xya-sse-status', onSseStatus)
})
</script>

<style scoped>
.m-notif {
  padding: var(--m-space-3) var(--m-space-4) 0;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow-x: hidden;
}

.m-page-header { margin-bottom: 14px; }
.m-page-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}
.m-page-title-main { min-width: 0; flex: 1; }
.m-page-header h1 { margin: 0 0 var(--m-space-1); font-size: var(--m-font-size-h1); font-weight: var(--m-font-weight-extrabold); color: var(--m-color-text-primary); }
.m-page-sub { margin: 0; font-size: var(--m-font-size-body-sm); color: var(--m-color-text-tertiary); }

.m-sse-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  border-radius: var(--m-radius-pill);
  font-size: 11px;
  font-weight: var(--m-font-weight-semibold);
  flex-shrink: 0;
}
.m-sse-dot {
  width: 7px;
  height: 7px;
  border-radius: var(--m-radius-circle);
  flex-shrink: 0;
}
.m-sse-online {
  background: var(--m-color-success-bg);
  color: var(--m-color-success);
}
.m-sse-online .m-sse-dot {
  background: var(--m-color-success);
  box-shadow: 0 0 0 3px rgba(22,191,120,0.18);
  animation: m-sse-pulse 1.8s ease-in-out infinite;
}
.m-sse-connecting {
  background: var(--m-color-warning-bg);
  color: var(--m-color-warning);
}
.m-sse-connecting .m-sse-dot { background: var(--m-color-warning); }
.m-sse-offline {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-secondary);
}
.m-sse-offline .m-sse-dot { background: var(--m-color-text-tertiary); }
@keyframes m-sse-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.m-tabs {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 6px;
  margin-bottom: var(--m-space-3);
  padding: 5px;
  background: var(--m-color-bg-subtle);
  border-radius: var(--m-radius-xl);
}
.m-tab {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: var(--m-space-2) var(--m-space-1);
  border: 0;
  border-radius: var(--m-radius-lg);
  background: transparent;
  color: var(--m-color-text-secondary);
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  transition: background 0.18s ease, color 0.18s ease, box-shadow 0.18s ease;
  min-width: 0;
}
.m-tab.active {
  background: var(--m-color-bg-card);
  color: var(--m-color-primary);
  box-shadow: var(--m-shadow-xs);
}
.m-tab-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 6px;
  border-radius: var(--m-radius-pill);
  background: var(--m-color-danger);
  color: var(--m-color-text-inverse);
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-bold);
  line-height: 1;
}
.m-tab:not(.active) .m-tab-count {
  background: var(--m-color-text-disabled);
  color: var(--m-color-text-secondary);
}

.m-action-bar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--m-space-2);
  margin-bottom: 10px;
}
.m-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 7px var(--m-space-3);
  border: 0;
  border-radius: var(--m-radius-lg);
  background: var(--m-color-bg-card);
  color: var(--m-color-text-secondary);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  box-shadow: var(--m-shadow-xs);
  transition: background 0.15s ease, color 0.15s ease, box-shadow 0.15s ease;
}
.m-action-btn:hover:not(:disabled) {
  background: var(--m-color-bg-hover);
  color: var(--m-color-text-primary);
}
.m-action-btn:active:not(:disabled) {
  transform: translateY(1px);
}
.m-action-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.m-pull-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  overflow: hidden;
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-caption);
  transition: opacity 0.2s ease;
}

.m-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: var(--m-space-12) var(--m-space-4);
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-body-sm);
}
.m-loading-spinner {
  width: 26px;
  height: 26px;
  border-radius: var(--m-radius-circle);
  border: 2.5px solid var(--m-color-border);
  border-top-color: var(--m-color-primary);
  animation: m-spin 0.8s linear infinite;
}
@keyframes m-spin {
  to { transform: rotate(360deg); }
}

.m-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 56px var(--m-space-4) var(--m-space-10);
  color: var(--m-color-text-tertiary);
  text-align: center;
}
.m-empty-icon {
  width: 84px;
  height: 84px;
  border-radius: var(--m-radius-circle);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-disabled);
}
.m-empty-text {
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-secondary);
}
.m-empty-desc {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}

.m-notif-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-bottom: var(--m-space-3);
}
.m-notif-card {
  position: relative;
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr) 18px;
  gap: var(--m-space-3);
  align-items: flex-start;
  padding: 14px 14px var(--m-space-3);
  border-radius: var(--m-radius-xl);
  background: var(--m-color-bg-card);
  border: 0;
  box-shadow: var(--m-shadow-xs);
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.m-notif-card:active {
  transform: scale(0.99);
}
.m-notif-unread {
  background: var(--m-color-bg-card);
  box-shadow: var(--m-shadow-xs);
}
.m-notif-expanded {
  box-shadow: var(--m-shadow-xs);
}
.m-notif-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--m-radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-notif-body {
  min-width: 0;
}
.m-notif-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: var(--m-space-1);
}
.m-notif-title {
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}
.m-notif-unread .m-notif-title {
  color: var(--m-color-primary);
}
.m-notif-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--m-radius-circle);
  background: var(--m-color-danger);
  flex-shrink: 0;
  box-shadow: 0 0 0 3px rgba(255, 82, 82, 0.18);
}
.m-notif-content {
  font-size: var(--m-font-size-body-sm);
  color: var(--m-color-text-secondary);
  line-height: var(--m-line-height-base);
  margin-bottom: var(--m-space-2);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
}
.m-notif-expanded .m-notif-content {
  -webkit-line-clamp: unset;
  overflow: visible;
}
.m-notif-meta {
  display: flex;
  align-items: center;
  gap: var(--m-space-2);
  flex-wrap: wrap;
}
.m-notif-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px var(--m-space-2);
  border-radius: var(--m-radius-sm);
  font-size: 11px;
  font-weight: var(--m-font-weight-bold);
  line-height: var(--m-line-height-base);
}
.m-notif-time {
  font-size: 11px;
  color: var(--m-color-text-tertiary);
}
.m-notif-detail {
  margin-top: 10px;
  padding: 10px var(--m-space-3);
  border-radius: var(--m-radius-lg);
  background: var(--m-color-bg-hover);
  border: 0;
}
.m-notif-detail-text {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-secondary);
  line-height: var(--m-line-height-relaxed);
  word-break: break-word;
  margin-bottom: 6px;
}
.m-notif-detail-meta {
  display: flex;
  flex-direction: column;
  gap: 3px;
  font-size: 11px;
  color: var(--m-color-text-tertiary);
}
.m-notif-chevron {
  align-self: center;
  color: var(--m-color-text-disabled);
  transition: transform 0.2s ease, color 0.2s ease;
  flex-shrink: 0;
}
.m-notif-chevron.rotated {
  transform: rotate(180deg);
  color: var(--m-color-primary);
}

.m-load-more {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 14px;
  margin-top: var(--m-space-1);
  border-radius: var(--m-radius-lg);
  background: var(--m-color-bg-hover);
  color: var(--m-color-text-secondary);
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  transition: background 0.15s ease;
}
.m-load-more:active {
  background: var(--m-color-bg-subtle);
}

.m-no-more {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: var(--m-space-4);
  color: var(--m-color-text-disabled);
  font-size: 11px;
}
.m-no-more-line {
  width: 32px;
  height: 1px;
  background: var(--m-color-border);
}

.m-safe-bottom {
  height: var(--m-space-6);
}

.rotating {
  animation: m-spin 0.9s linear infinite;
}

@media (max-width: 380px) {
  .m-notif { padding: 10px var(--m-space-3) 0; }
  .m-page-header h1 { font-size: var(--m-font-size-h2); }
  .m-notif-card {
    grid-template-columns: 36px minmax(0, 1fr) 16px;
    gap: 10px;
    padding: var(--m-space-3) var(--m-space-3) 10px;
    border-radius: var(--m-radius-xl);
  }
  .m-notif-icon { width: 36px; height: 36px; border-radius: var(--m-radius-lg); }
  .m-notif-title { font-size: var(--m-font-size-body-sm); }
  .m-notif-content { font-size: var(--m-font-size-caption); }
  .m-tab { font-size: var(--m-font-size-caption); padding: 7px 2px; }
  .m-action-btn { padding: 6px 10px; font-size: 11px; }
}
</style>