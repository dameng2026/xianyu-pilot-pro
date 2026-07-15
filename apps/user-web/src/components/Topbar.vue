<template>
  <div class="topbar">
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

const emit = defineEmits(['logout', 'open-profile-center'])

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
</style>
