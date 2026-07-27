<template>
  <div class="topbar">
    <button
      type="button"
      class="top-cs-btn"
      aria-label="联系 AI 客服小梦"
      title="AI 客服小梦"
      @click="emit('open-ai-cs')"
    >
      <span class="top-cs-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>
        </svg>
      </span>
      <span class="top-cs-pulse" aria-hidden="true"></span>
    </button>

    <div class="top-user-wrap">
      <button class="top-user" type="button" @click="emit('open-profile-center', 'overview')">
        <div class="avatar small avatar-img"></div>
        <div class="top-user-copy">
          <span class="top-user-name">{{ displayName }}</span>
          <em>{{ levelLabel }} · {{ sseLabel }}</em>
        </div>
        <b aria-hidden="true">v</b>
      </button>

      <div class="top-user-menu" role="menu" aria-label="用户菜单">
        <button type="button" role="menuitem" @click="emit('open-profile-center', 'overview')">个人中心</button>
        <button type="button" role="menuitem" @click="emit('open-profile-center', 'security')">账号安全</button>
        <button type="button" role="menuitem" @click="emit('open-profile-center', 'token')">Token 消耗</button>
        <button type="button" role="menuitem" class="danger" @click="emit('logout')">退出登录</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  user: { type: Object, default: () => ({}) },
  sseStatus: { type: String, default: 'disconnected' }
})

const emit = defineEmits(['logout', 'open-profile-center', 'open-ai-cs'])

const displayName = computed(() => props.user?.nickname || props.user?.username || props.user?.displayName || props.user?.name || '当前用户')
const levelLabel = computed(() => {
  if (props.user?.profileUnavailable) return '套餐状态未知'
  return props.user?.activePlan?.planName || props.user?.planName || props.user?.levelName || '套餐状态未知'
})
const sseLabel = computed(() => ({
  connected: '在线',
  connecting: '连接中',
  disconnected: '离线'
}[props.sseStatus] || '状态未知'))
</script>

<style scoped>
.topbar {
  position: fixed;
  right: 22px;
  top: 18px;
  display: flex;
  align-items: center;
  z-index: 30;
}

.top-user-wrap {
  position: relative;
}

.top-user {
  min-width: 220px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 12px 6px 8px;
  border: 1px solid rgba(219, 230, 248, 0.92);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 14px 34px rgba(31, 53, 94, 0.12);
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}

.top-user-wrap:hover .top-user,
.top-user-wrap:focus-within .top-user {
  transform: translateY(-1px);
  border-color: #c9daf7;
  box-shadow: 0 18px 38px rgba(31, 53, 94, 0.16);
}

.top-user-copy {
  min-width: 0;
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: flex-start;
}

.top-user-name {
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.top-user em {
  margin: 0;
  font-style: normal;
  color: #6f7d95;
  font-size: 12px;
  white-space: nowrap;
}

.top-user b {
  margin-left: auto;
  color: #8b98ad;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.top-user-menu {
  position: absolute;
  right: 0;
  top: calc(100% + 10px);
  min-width: 100%;
  background: #fff;
  border: 1px solid #e8eef8;
  border-radius: 14px;
  box-shadow: 0 18px 40px rgba(30, 52, 92, 0.14);
  padding: 8px;
  z-index: 20;
  opacity: 0;
  pointer-events: none;
  transform: translateY(-6px);
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.top-user-wrap:hover .top-user-menu,
.top-user-wrap:focus-within .top-user-menu {
  opacity: 1;
  pointer-events: auto;
  transform: translateY(0);
}

.top-user-menu button {
  width: 100%;
  text-align: left;
  white-space: nowrap;
  border: 0;
  background: transparent;
  padding: 10px 14px;
  border-radius: 10px;
  cursor: pointer;
  color: #1c2740;
  font-weight: 600;
}

.top-user-menu button:hover {
  background: #f2f7ff;
}

.top-user-menu button.danger {
  color: #ef4444;
}

.top-user-menu button.danger:hover {
  background: #fff5f5;
}

/* AI 客服按钮：位于用户板块左侧，圆角玻璃拟态 */
.top-cs-btn {
  position: relative;
  width: 44px;
  height: 44px;
  border: 1px solid rgba(219, 230, 248, 0.92);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 12px 30px rgba(31, 53, 94, 0.12);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #147dff;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease, color 0.2s ease;
  margin-right: 10px;
  flex-shrink: 0;
}

.top-cs-btn:hover {
  transform: translateY(-2px);
  border-color: #147dff;
  color: #0865f4;
  box-shadow: 0 16px 36px rgba(20, 125, 255, 0.22);
}

.top-cs-btn:active {
  transform: translateY(0);
}

.top-cs-btn:focus-visible {
  outline: 2px solid #147dff;
  outline-offset: 2px;
}

.top-cs-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 0;
}

/* 在线脉动指示：提示用户客服可联系 */
.top-cs-pulse {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.6);
  animation: top-cs-pulse-anim 2s infinite;
}

@keyframes top-cs-pulse-anim {
  0% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.55); }
  70% { box-shadow: 0 0 0 8px rgba(34, 197, 94, 0); }
  100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
}

@media (max-width: 768px) {
  .top-cs-btn {
    width: 40px;
    height: 40px;
    border-radius: 12px;
    margin-right: 8px;
  }
  .top-cs-icon svg {
    width: 18px;
    height: 18px;
  }
}
</style>
