<template>
  <div v-if="visible" class="maintenance-banner" role="status" aria-live="polite">
    <span class="maintenance-banner__icon" aria-hidden="true">🔧</span>
    <div class="maintenance-banner__body">
      <strong class="maintenance-banner__title">{{ title }}</strong>
      <span class="maintenance-banner__text">{{ displayText }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { getMaintenanceStatus } from '../api/maintenance'

const DEFAULT_MESSAGE = '项目正在更新中，期间部分功能可能暂时不可用，属于正常情况，预计一小时内结束。'
const POLL_INTERVAL_MS = 60_000

const visible = ref(false)
const message = ref(null)
const until = ref(null)

let pollTimer = null

const title = '系统更新中'
const displayText = computed(() => {
  const text = message.value || DEFAULT_MESSAGE
  if (until.value) {
    const formatted = formatUntil(until.value)
    if (formatted) return `${text}（预计 ${formatted} 结束）`
  }
  return text
})

function formatUntil(raw) {
  try {
    const d = new Date(raw)
    if (Number.isNaN(d.getTime())) return ''
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
  } catch {
    return ''
  }
}

async function refresh() {
  const status = await getMaintenanceStatus()
  visible.value = status.enabled
  message.value = status.message
  until.value = status.until
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(refresh, POLL_INTERVAL_MS)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function onRouteChange() {
  refresh()
}

onMounted(() => {
  refresh()
  startPolling()
  window.addEventListener('hashchange', onRouteChange)
})

onBeforeUnmount(() => {
  stopPolling()
  window.removeEventListener('hashchange', onRouteChange)
})
</script>

<style scoped>
.maintenance-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 16px;
  background: linear-gradient(90deg, #fff7e6 0%, #fff1db 100%);
  border-bottom: 1px solid #ffd591;
  color: #874d00;
  font-size: 13px;
  line-height: 1.5;
  z-index: 100;
}

.maintenance-banner__icon {
  font-size: 16px;
  flex-shrink: 0;
}

.maintenance-banner__body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.maintenance-banner__title {
  font-weight: 600;
  font-size: 13px;
}

.maintenance-banner__text {
  font-size: 12px;
  opacity: 0.85;
  word-break: break-word;
}

@media (max-width: 768px) {
  .maintenance-banner {
    padding: 6px 12px;
    font-size: 12px;
  }
  .maintenance-banner__title {
    font-size: 12px;
  }
  .maintenance-banner__text {
    font-size: 11px;
  }
}
</style>
