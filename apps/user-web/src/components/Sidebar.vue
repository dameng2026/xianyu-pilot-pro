<template>
  <aside class="sidebar">
    <div class="brand brand-image" @click="$emit('navigate', 'dashboard')">
      <img src="/xya/brand/brand_004.png" alt="XianYuAssistant 闲鱼助手" class="brand-logo" />
    </div>
    <nav class="nav-scroll">
      <div v-for="group in groups" :key="group.title" class="nav-group">
        <div class="nav-title">{{ group.title }}</div>
        <button
          v-for="item in group.items"
          :key="item.key"
          :class="['nav-item', { active: isActive(item.key), child: item.child }]"
          @click="$emit('navigate', item.key)"
        >
          <span class="nav-icon"><Icon :name="item.icon" /></span>
          <span>{{ item.label }}</span>
          <span v-if="item.badge" class="nav-badge">{{ item.badge }}</span>
        </button>
      </div>
    </nav>
    <button type="button" class="side-user side-user-button" @click="$emit('open-profile-center', 'overview')">
      <div class="avatar avatar-img"></div>
      <div class="side-user-main">
        <strong>{{ displayName }}</strong>
        <span>{{ levelLabel }}</span>
      </div>
      <span class="online-dot" :class="connectionTone"></span>
      <span class="online-text">{{ connectionLabel }}</span>
    </button>
    <div class="version">© {{ copyrightYear }} XianYuAssistant<br />v{{ APP_VERSION }}</div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { navGroups } from '../data/nav.js'
import Icon from './Icon.vue'
import { APP_VERSION, getCopyrightYear } from '../utils/appMeta.js'

defineEmits(['navigate', 'open-profile-center'])

const props = defineProps({
  active: { type: String, required: true },
  user: { type: Object, default: () => ({}) },
  connectionStatus: { type: String, default: 'unknown' }
})

const groups = navGroups
const displayName = computed(() => props.user?.nickname || props.user?.username || props.user?.displayName || props.user?.name || '当前用户')
const levelLabel = computed(() => {
  if (props.user?.profileUnavailable) return '套餐状态未知'
  return props.user?.activePlan?.planName || props.user?.planName || props.user?.levelName || '套餐状态未知'
})
const connectionLabel = computed(() => ({
  connected: '消息通道在线',
  connecting: '消息通道连接中',
  disconnected: '消息通道离线'
}[props.connectionStatus] || '消息通道状态未知'))
const connectionTone = computed(() => ({
  connected: 'connected',
  connecting: 'connecting',
  disconnected: 'disconnected'
}[props.connectionStatus] || 'unknown'))
const copyrightYear = getCopyrightYear()

function isActive(key) {
  if (props.active.startsWith('settings-') && props.active !== 'settings-notify' && key === 'settings-ai-cs') return true
  if (props.active === 'account-vip' && key === 'accounts') return true
  return props.active === key
}
</script>

<style scoped>
.side-user-button {
  width: 100%;
  border: 0;
  text-align: left;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease, background 0.18s ease;
}

.side-user-button:hover {
  background: #eef4ff;
  border-color: #d7e4fa;
  box-shadow: 0 12px 24px rgba(31, 53, 94, 0.08);
  transform: translateY(-1px);
}

.side-user-button:focus-visible {
  outline: 2px solid #3b82f6;
  outline-offset: 2px;
}

.online-dot.connecting {
  background: #f59e0b;
}

.online-dot.disconnected {
  background: #ef4444;
}

.online-dot.unknown {
  background: #94a3b8;
}
</style>
