<template>
  <aside class="sidebar">
    <div class="brand brand-image" @click="$emit('navigate', 'dashboard')">
      <img src="/xya/brand/brand_004.png" alt="xianyu-pilot-pro 闲鱼助手" class="brand-logo" />
    </div>
    <div class="nav-scroll">
      <div v-for="cat in categories" :key="cat.key" class="nav-group">
        <button
          :class="['nav-cat', { active: isCategoryActive(cat.key), expanded: expandedKey === cat.key }]"
          @click="toggleCategory(cat.key)"
        >
          <span class="nav-cat-icon"><Icon :name="cat.icon" /></span>
          <span class="nav-cat-title">{{ cat.title }}</span>
        </button>
        <Transition name="nav-expand">
          <div v-if="expandedKey === cat.key" class="nav-sub">
            <button
              v-for="item in cat.items"
              :key="item.key"
              :class="['nav-sub-item', { active: isActive(item.key), maintenance: item.maintenance }]"
              @click="handleNavClick(item)"
            >
              <span v-if="item.icon" class="nav-sub-icon"><Icon :name="item.icon" /></span>
              <span class="nav-sub-label">{{ item.label }}</span>
              <span v-if="item.maintenance" class="maintenance-badge">维护中</span>
            </button>
          </div>
        </Transition>
      </div>
    </div>
    <button type="button" class="side-user side-user-button" @click="$emit('open-profile-center', 'overview')">
      <div class="avatar-wrapper">
        <div class="avatar avatar-img"></div>
        <span class="online-dot" :class="connectionTone"></span>
      </div>
      <div class="side-user-main">
        <strong class="user-name">{{ displayName }}</strong>
        <span class="user-plan">{{ levelLabel }}</span>
      </div>
    </button>
    <div class="version">© {{ copyrightYear }} xianyu-pilot-pro<br />v{{ APP_VERSION }}</div>
  </aside>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { navCategories } from '../data/nav.js'
import Icon from './Icon.vue'
import { APP_VERSION, getCopyrightYear } from '../utils/appMeta.js'

const emit = defineEmits(['navigate', 'open-profile-center'])

const props = defineProps({
  active: { type: String, required: true },
  user: { type: Object, default: () => ({}) },
  connectionStatus: { type: String, default: 'unknown' }
})

const categories = navCategories

function findCategoryByKey(key) {
  for (const cat of categories) {
    if (cat.items.some(item => item.key === key)) {
      return cat.key
    }
  }
  return 'overview'
}

const expandedKey = ref(findCategoryByKey(props.active))

watch(() => props.active, (newKey) => {
  expandedKey.value = findCategoryByKey(newKey)
})

function toggleCategory(key) {
  // 手风琴模式：点击分类时，总是切换到该分类展开，其他分类收起
  // 再次点击同一分类则收起（如果当前页面不在此分类下）
  if (expandedKey.value === key) {
    if (findCategoryByKey(props.active) !== key) {
      expandedKey.value = ''
    }
  } else {
    expandedKey.value = key
  }
}

function isCategoryActive(key) {
  return findCategoryByKey(props.active) === key
}

function handleNavClick(item) {
  emit('navigate', item.key)
}

const displayName = computed(() => props.user?.nickname || props.user?.username || props.user?.displayName || props.user?.name || '当前用户')
const levelLabel = computed(() => {
  if (props.user?.profileUnavailable) return '套餐状态未知'
  const plan = props.user?.activePlan
  return plan?.planName || props.user?.planName || props.user?.levelName || (plan?.planCode === 'normal' ? '普通用户' : '套餐状态未知')
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
  if (props.active === 'account-vip' && key === 'accounts') return true
  return props.active === key
}
</script>

<style scoped>
.side-user-button {
  width: 100%;
  height: auto;
  min-height: 56px;
  border: 1px solid #e8eef6;
  border-radius: 12px;
  background: #f8fafc;
  text-align: left;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  margin: 4px 8px 0;
  transition: all 0.2s ease;
}

.side-user-button:hover {
  background: #eef4ff;
  border-color: #d7e4fa;
  box-shadow: 0 4px 12px rgba(31, 53, 94, 0.06);
}

.side-user-button:focus-visible {
  outline: 2px solid #3b82f6;
  outline-offset: 2px;
}

.avatar-wrapper {
  position: relative;
  flex-shrink: 0;
}

.avatar {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: linear-gradient(135deg, #0c8a71, #f2b75b);
  flex-shrink: 0;
}

.avatar-img {
  background-image: radial-gradient(circle at 50% 36%, #38342f 0 11%, transparent 12%), radial-gradient(circle at 50% 58%, #f0b071 0 25%, transparent 26%), linear-gradient(135deg, #0c8a71, #f2b75b);
  background-size: cover;
  background-position: center;
}

.online-dot {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #18c785;
  border: 2px solid #f8fafc;
  box-shadow: 0 0 0 0 rgba(24, 199, 133, 0.4);
}

.online-dot.connected {
  background: #22c55e;
  box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.15);
}

.online-dot.connecting {
  background: #f59e0b;
  box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.15);
}

.online-dot.disconnected {
  background: #ef4444;
  box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.15);
}

.online-dot.unknown {
  background: #94a3b8;
  box-shadow: 0 0 0 2px rgba(148, 163, 184, 0.15);
}

.side-user-main {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
  flex: 1;
  min-width: 0;
  gap: 2px;
}

.user-name {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-plan {
  font-size: 11px;
  color: #64748b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.version {
  font-size: 10px;
  line-height: 1.5;
  color: #94a3b8;
  text-align: center;
  padding: 8px 8px 10px;
  white-space: nowrap;
}

.nav-scroll {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  margin: 8px 0;
  padding-right: 4px;
  scrollbar-width: thin;
  scrollbar-color: #d1d9e6 transparent;
}

.nav-scroll::-webkit-scrollbar {
  width: 4px;
}

.nav-scroll::-webkit-scrollbar-track {
  background: transparent;
}

.nav-scroll::-webkit-scrollbar-thumb {
  background: #d1d9e6;
  border-radius: 2px;
}

.nav-scroll::-webkit-scrollbar-thumb:hover {
  background: #b8c4d6;
}

.nav-group {
  margin-bottom: 2px;
}

.nav-cat {
  width: 100%;
  border: 0;
  background: transparent;
  border-radius: 10px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  cursor: pointer;
  color: #475569;
  transition: all 0.2s ease;
  position: relative;
}

.nav-cat:hover {
  background: #f1f5ff;
  color: #0d6bff;
}

.nav-cat.active {
  background: linear-gradient(135deg, #e8f0ff, #f5f8ff);
  color: #0d6bff;
}

.nav-cat.expanded {
  color: #0d6bff;
}

.nav-cat-icon {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.nav-cat-icon :deep(.ui-icon) {
  width: 18px;
  height: 18px;
  stroke-width: 2;
}

.nav-cat-icon :deep(.ui-icon-img) {
  width: 20px;
  height: 20px;
}

.nav-cat-title {
  flex: 1;
  font-size: 14px;
  font-weight: 500;
  text-align: left;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.nav-cat.active .nav-cat-title {
  font-weight: 600;
}

.nav-sub {
  overflow: hidden;
  padding: 2px 0 6px;
  margin-left: 10px;
}

.nav-sub-item {
  width: calc(100% - 4px);
  border: 0;
  background: transparent;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px 8px 12px;
  margin: 2px 0 2px 4px;
  color: #64748b;
  font-size: 13px;
  font-weight: 400;
  text-align: left;
  cursor: pointer;
  transition: all 0.18s ease;
  white-space: nowrap;
  overflow: hidden;
}

.nav-sub-item:hover {
  background: #f1f5f9;
  color: #334155;
}

.nav-sub-item.active {
  background: #eff6ff;
  color: #0d6bff;
  font-weight: 500;
}

.nav-sub-item.maintenance {
  color: #94a3b8;
  cursor: default;
}

.nav-sub-item.maintenance:hover {
  background: transparent;
  color: #94a3b8;
}

.nav-sub-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
}

.nav-sub-icon {
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  opacity: 0.7;
  transition: opacity 0.2s ease;
}

.nav-sub-icon :deep(.ui-icon) {
  width: 14px;
  height: 14px;
}

.nav-sub-icon :deep(.ui-icon-img) {
  width: 16px;
  height: 16px;
}

.nav-sub-item:hover .nav-sub-icon,
.nav-sub-item.active .nav-sub-icon {
  opacity: 1;
}

.maintenance-badge {
  flex-shrink: 0;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  background: #fef3c7;
  color: #d97706;
  font-weight: 500;
  letter-spacing: 0.2px;
}

/* 展开/收起动画 */
.nav-expand-enter-active {
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

.nav-expand-leave-active {
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

.nav-expand-enter-from {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}

.nav-expand-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}

.nav-expand-enter-to,
.nav-expand-leave-from {
  opacity: 1;
  max-height: 400px;
}
</style>
