<template>
  <div class="mobile-shell">
    <header v-if="!subPage && !searchMode" class="m-topbar">
      <button class="m-menu-btn" @click="drawerOpen = true" aria-label="菜单">
        <MIcon name="menu" :size="22" />
      </button>
      <div class="m-brand-center" @click="switchTab('home')">
        <div class="m-brand-mark">
          <span></span>
          <span></span>
        </div>
        <span class="m-brand-name">闲鱼助手</span>
      </div>
      <div class="m-top-actions">
        <button v-if="canSearch" class="m-top-action-btn" @click="toggleSearch" aria-label="搜索">
          <MIcon name="search" :size="20" />
        </button>
        <button class="m-top-action-btn" @click="switchTab('profile')" aria-label="我的">
          <MIcon name="user" :size="20" />
        </button>
      </div>
    </header>

    <header v-else-if="searchMode" class="m-topbar m-topbar-search">
      <button class="m-back-btn" @click="closeSearch" aria-label="关闭搜索">
        <MIcon name="chevronLeft" :size="22" />
      </button>
      <div class="m-search-bar">
        <MIcon name="search" :size="16" class="m-search-icon" />
        <input
          ref="searchInputRef"
          v-model="searchKeyword"
          type="text"
          class="m-search-input"
          :placeholder="searchPlaceholder"
          @input="onSearchInput"
        />
        <button v-if="searchKeyword" class="m-search-clear" @click="clearSearch" aria-label="清空">
          <MIcon name="xCircle" :size="16" />
        </button>
      </div>
    </header>

    <header v-else class="m-topbar m-topbar-sub">
      <button class="m-back-btn" @click="handleSubBack">
        <MIcon name="chevronLeft" :size="22" />
        <span>返回</span>
      </button>
      <div class="m-sub-title">{{ subPageTitle }}</div>
      <button v-if="subPage === 'accounts'" class="m-add-account-topbtn" @click="triggerAddAccount" aria-label="添加账号">
        <MIcon name="plus" :size="16" />
        <span>添加</span>
      </button>
      <button v-else-if="subPage === 'account-detail'" class="m-icon-btn-top" @click="triggerAccountDetailMore" aria-label="更多操作">
        <MIcon name="moreVertical" :size="22" />
      </button>
      <button v-else-if="subPage === 'product-detail'" class="m-icon-btn-top" @click="triggerProductSave" aria-label="保存">
        <MIcon name="save" :size="20" />
      </button>
      <button v-else class="m-desktop-btn" @click="goDesktop">
        <MIcon name="desktop" :size="20" />
      </button>
    </header>

    <div v-if="drawerOpen" class="m-drawer-mask" @click="drawerOpen = false"></div>
    <aside v-if="drawerOpen" class="m-drawer">
      <div class="m-drawer-header">
        <div class="m-drawer-user">
          <div class="m-drawer-avatar">
            <MIcon name="user" :size="24" />
          </div>
          <div class="m-drawer-userinfo">
            <div class="m-drawer-username">{{ username }}</div>
            <div class="m-drawer-sub">闲鱼智能助手</div>
          </div>
        </div>
        <button class="m-drawer-close" @click="drawerOpen = false" aria-label="关闭菜单">
          <MIcon name="close" :size="20" />
        </button>
      </div>
      <div class="m-drawer-content">
        <div v-for="group in drawerGroups" :key="group.title" class="m-drawer-group">
          <div class="m-drawer-group-title">{{ group.title }}</div>
          <button
            v-for="item in group.items"
            :key="item.key"
            class="m-drawer-item"
            :class="{ active: isDrawerItemActive(item.key) }"
            @click="onDrawerItem(item.key)"
          >
            <div class="m-drawer-item-icon" :style="{ background: item.iconBg }">
              <MIcon :name="item.icon" :size="18" :color="item.iconColor" />
            </div>
            <span class="m-drawer-item-label">{{ item.label }}</span>
            <MIcon name="chevronRight" :size="16" class="m-drawer-item-arrow" />
          </button>
        </div>
      </div>
      <div class="m-drawer-footer">
        <button class="m-drawer-foot-btn" @click="goDesktop">
          <MIcon name="desktop" :size="16" />
          <span>切换到桌面版</span>
        </button>
        <button class="m-drawer-foot-btn m-drawer-foot-danger" @click="emit('logout')">
          <MIcon name="logOut" :size="16" />
          <span>退出登录</span>
        </button>
      </div>
    </aside>

    <main ref="contentRef" class="m-content">
      <MobileHome
        v-if="!subPage && activeTab === 'home'"
        @navigate="onNavigate"
        @logout="emit('logout')"
        @force-desktop="goDesktop"
        @tab-change="switchTab"
      />
      <MobileData
        v-else-if="!subPage && activeTab === 'data'"
        @navigate="onSubNavigate"
        @force-desktop="goDesktop"
        @back="backToMain"
      />
      <MobileDataDetail
        v-else-if="subPage === 'data-detail'"
        @navigate="onSubNavigate"
        @force-desktop="goDesktop"
        @back="backToData"
      />
      <MobileProducts
        v-else-if="subPage === 'products'"
        ref="productsListRef"
        :search-mode="searchMode"
        :search-keyword="searchKeyword"
        @navigate="onSubNavigate"
        @force-desktop="goDesktop"
        @back="backToMain"
        @open-detail="openProductDetail"
        @close-search="closeSearch"
      />
      <MobileProductDetail
        v-else-if="subPage === 'product-detail'"
        ref="productDetailRef"
        :product="selectedProduct"
        @navigate="onSubNavigate"
        @force-desktop="goDesktop"
        @back="backToProducts"
        @updated="onProductUpdated"
      />
      <MobileProductPublish
        v-else-if="subPage === 'product-publish'"
        @navigate="onSubNavigate"
        @force-desktop="goDesktop"
        @back="backToProducts"
      />
      <MobileAccounts
        v-else-if="subPage === 'accounts'"
        ref="accountsListRef"
        @navigate="onSubNavigate"
        @force-desktop="goDesktop"
        @back="backToMain"
        @open-detail="openAccountDetail"
      />
      <MobileAccountDetail
        v-else-if="subPage === 'account-detail'"
        ref="accountDetailRef"
        :account-id="selectedAccountId"
        @navigate="onSubNavigate"
        @force-desktop="goDesktop"
        @back="backToAccounts"
        @refresh-list="refreshAccountsList"
      />
      <MobileMessages
        v-else-if="subPage === 'messages'"
        @navigate="onSubNavigate"
        @force-desktop="goDesktop"
      />
      <MobileChatDetail
        v-else-if="subPage === 'chat-detail'"
        @navigate="onSubNavigate"
        @force-desktop="goDesktop"
        @back="backToMessages"
      />
      <MobileAutoDelivery
        v-else-if="subPage === 'auto-delivery'"
        @navigate="onSubNavigate"
        @force-desktop="goDesktop"
        @back="backToWorkflow"
      />
      <MobileOrders
        v-else-if="!subPage && activeTab === 'orders'"
        @navigate="onNavigate"
        @force-desktop="goDesktop"
        @back="backToMain"
      />
      <MobileAutomation
        v-else-if="!subPage && activeTab === 'automation'"
        @navigate="onNavigate"
        @force-desktop="goDesktop"
      />
      <MobileProfile
        v-else-if="!subPage && activeTab === 'profile'"
        :user="userInfo"
        @navigate="onNavigate"
        @logout="emit('logout')"
        @force-desktop="goDesktop"
        @tab-change="switchTab"
      />
    </main>

    <button
      v-if="showFAB"
      class="m-fab-action"
      @click="onFABClick"
      :aria-label="fabLabel"
    >
      <MIcon :name="fabIcon" :size="26" />
    </button>

    <nav v-if="!subPage" class="m-tabbar">
      <button
        v-for="tab in bottomTabs"
        :key="tab.key"
        class="m-tab"
        :class="{ active: activeTab === tab.key, center: tab.center }"
        @click="switchTab(tab.key)"
      >
        <div v-if="tab.center" class="m-tab-center-btn">
          <MIcon :name="tab.icon" :size="24" />
        </div>
        <template v-else>
          <MIcon :name="tab.icon" :size="22" />
          <span>{{ tab.label }}</span>
        </template>
      </button>
    </nav>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount, onMounted, computed, nextTick } from 'vue'
import MIcon from '../mobile/MIcon.vue'
import MobileHome from '../mobile/MobileHome.vue'
import MobileMessages from '../mobile/MobileMessages.vue'
import MobileAutomation from '../mobile/MobileAutomation.vue'
import MobileProfile from '../mobile/MobileProfile.vue'
import MobileProducts from '../mobile/MobileProducts.vue'
import MobileProductDetail from '../mobile/MobileProductDetail.vue'
import MobileProductPublish from '../mobile/MobileProductPublish.vue'
import MobileAccounts from '../mobile/MobileAccounts.vue'
import MobileAccountDetail from '../mobile/MobileAccountDetail.vue'
import MobileData from '../mobile/MobileData.vue'
import MobileDataDetail from '../mobile/MobileDataDetail.vue'
import MobileAutoDelivery from '../mobile/MobileAutoDelivery.vue'
import MobileOrders from '../mobile/MobileOrders.vue'
import MobileChatDetail from '../mobile/MobileChatDetail.vue'
import { getCachedUsername } from '../utils/auth.js'
import { currentUser } from '../api/system.js'
import { pageForMobileTab, resolveMobileRoute, getMobileAccountDetailId, setMobileAccountDetailId, getMobileProductDetailId, setMobileProductDetailId } from '../mobile/mobileRouteState.js'

const emit = defineEmits(['navigate', 'logout', 'force-desktop'])

const bottomTabs = [
  { key: 'home', label: '首页', icon: 'home' },
  { key: 'data', label: '数据面板', icon: 'pieChart' },
  { key: 'automation', label: '快速开始', icon: 'plus', center: true },
  { key: 'orders', label: '订单管理', icon: 'shoppingCart' },
  { key: 'profile', label: '我的', icon: 'user' }
]

const drawerGroups = [
  {
    title: '工作台',
    items: [
      { key: 'dashboard', label: '首页概览', icon: 'home', iconBg: 'rgba(13,107,255,0.1)', iconColor: '#0d6bff' },
      { key: 'data', label: '数据看板', icon: 'pieChart', iconBg: 'rgba(145,88,255,0.1)', iconColor: '#9158ff' },
      { key: 'products', label: '商品管理', icon: 'bag', iconBg: 'rgba(22,191,120,0.1)', iconColor: '#16bf78' },
      { key: 'orders', label: '订单管理', icon: 'shoppingCart', iconBg: 'rgba(255,124,67,0.1)', iconColor: '#ff7c43' }
    ]
  },
  {
    title: '账号与消息',
    items: [
      { key: 'accounts', label: '账号管理', icon: 'users', iconBg: 'rgba(13,107,255,0.1)', iconColor: '#0d6bff' },
      { key: 'messages', label: '在线消息', icon: 'messageCircle', iconBg: 'rgba(22,191,120,0.1)', iconColor: '#16bf78' }
    ]
  },
  {
    title: '自动化',
    items: [
      { key: 'workflow', label: '自动化工作流', icon: 'bot', iconBg: 'rgba(145,88,255,0.1)', iconColor: '#9158ff' },
      { key: 'auto-delivery', label: '自动发货', icon: 'send', iconBg: 'rgba(255,159,34,0.1)', iconColor: '#ff9f22' }
    ]
  }
]

const mobileSubPages = {
  products: '商品管理',
  'product-detail': '商品详情',
  'product-publish': '发布宝贝',
  accounts: '账号管理',
  'account-detail': '账号详情',
  'data-detail': '数据详情',
  messages: '在线消息',
  'chat-detail': '聊天详情',
  'auto-delivery': '自动发货'
}

const activeTab = ref('home')
const subPage = ref(null)
const contentRef = ref(null)
const username = ref(getCachedUsername() || '未登录用户')
const userInfo = ref({ username: username.value })
const selectedAccountId = ref(null)
const selectedProduct = ref(null)
const accountsListRef = ref(null)
const accountDetailRef = ref(null)
const productsListRef = ref(null)
const productDetailRef = ref(null)
const drawerOpen = ref(false)

const searchMode = ref(false)
const searchKeyword = ref('')
const searchInputRef = ref(null)
let searchDebounceTimer = null

const subPageTitle = computed(() => mobileSubPages[subPage.value] || '')

const canSearch = computed(() => {
  return subPage.value === 'products'
})

const searchPlaceholder = computed(() => {
  if (subPage.value === 'products') return '搜索商品名称、ID'
  return '搜索'
})

const showFAB = computed(() => {
  return subPage.value === 'products' || (!subPage && activeTab.value === 'home')
})

const fabIcon = computed(() => 'plus')
const fabLabel = computed(() => subPage.value === 'products' ? '发布商品' : '快速发布')

function onFABClick() {
  if (subPage.value === 'products') {
    emit('navigate', 'product-publish')
  } else {
    emit('navigate', 'product-publish')
  }
}

async function loadUser() {
  try {
    const res = await currentUser()
    if (res?.data) {
      userInfo.value = { ...userInfo.value, ...res.data }
      username.value = res.data.username || username.value
    }
  } catch {
  }
}

function switchTab(key) {
  if (key === 'automation') {
    emit('navigate', 'workflow')
    return
  }
  const pageKey = pageForMobileTab(key)
  if (pageKey) {
    emit('navigate', pageKey)
    return
  }
  if (activeTab.value === key && !subPage.value) return
  activeTab.value = key
  subPage.value = null
  searchMode.value = false
  drawerOpen.value = false
  nextTick(() => {
    if (contentRef.value) contentRef.value.scrollTop = 0
  })
}

function goDesktop(target) {
  drawerOpen.value = false
  emit('force-desktop', target)
}

function onNavigate(pageKey) {
  drawerOpen.value = false
  if (mobileSubPages[pageKey] || bottomTabs.some(t => pageForMobileTab(t.key) === pageKey)) {
    emit('navigate', pageKey)
    return
  }
  emit('navigate', pageKey)
}

function onSubNavigate(pageKey) {
  if (mobileSubPages[pageKey] || bottomTabs.some(t => pageForMobileTab(t.key) === pageKey)) {
    emit('navigate', pageKey)
    return
  }
  emit('navigate', pageKey)
}

function onDrawerItem(pageKey) {
  drawerOpen.value = false
  emit('navigate', pageKey)
}

function isDrawerItemActive(key) {
  if (subPage.value === key) return true
  if (!subPage.value) {
    const tabPage = pageForMobileTab(activeTab.value)
    return tabPage === key
  }
  return false
}

function backToMain() {
  emit('navigate', 'dashboard')
}

function backToWorkflow() {
  emit('navigate', 'workflow')
}

function backToProducts() {
  setMobileProductDetailId(null)
  selectedProduct.value = null
  emit('navigate', 'products')
}

function backToData() {
  emit('navigate', 'data')
}

function backToAccounts() {
  setMobileAccountDetailId(null)
  emit('navigate', 'accounts')
}

function backToMessages() {
  emit('navigate', 'messages')
}

function openAccountDetail(accountId) {
  selectedAccountId.value = accountId
  setMobileAccountDetailId(accountId)
  emit('navigate', `account-detail/${accountId}`)
}

function openProductDetail(prod) {
  selectedProduct.value = prod
  const id = prod?.id || prod?.itemId
  if (id) setMobileProductDetailId(id)
  emit('navigate', `product-detail/${id}`)
}

function onProductUpdated(updated) {
  if (productsListRef.value?.refreshProduct) {
    productsListRef.value.refreshProduct(updated)
  }
}

function triggerAddAccount() {
  if (accountsListRef.value?.startAddAccount) {
    accountsListRef.value.startAddAccount()
  }
}

function triggerAccountDetailMore() {
  if (accountDetailRef.value?.openMoreMenu) {
    accountDetailRef.value.openMoreMenu()
  }
}

function triggerProductSave() {
  if (productDetailRef.value?.handleSave) {
    productDetailRef.value.handleSave()
  }
}

function refreshAccountsList() {
  if (accountsListRef.value?.loadAccounts) {
    accountsListRef.value.loadAccounts()
  }
}

function handleSubBack() {
  if (searchMode.value) {
    closeSearch()
    return
  }
  if (subPage.value === 'product-detail') {
    backToProducts()
  } else if (subPage.value === 'product-publish') {
    backToProducts()
  } else if (subPage.value === 'account-detail') {
    backToAccounts()
  } else if (subPage.value === 'auto-delivery') {
    backToWorkflow()
  } else if (subPage.value === 'data-detail') {
    backToData()
  } else if (subPage.value === 'chat-detail') {
    backToMessages()
  } else if (subPage.value === 'messages') {
    backToMain()
  } else if (subPage.value === 'products' || subPage.value === 'accounts') {
    backToMain()
  } else {
    backToMain()
  }
}

function toggleSearch() {
  searchMode.value = true
  nextTick(() => {
    searchInputRef.value?.focus()
  })
}

function closeSearch() {
  searchMode.value = false
  searchKeyword.value = ''
  if (productsListRef.value?.onSearch) {
    productsListRef.value.onSearch('')
  }
}

function clearSearch() {
  searchKeyword.value = ''
  if (productsListRef.value?.onSearch) {
    productsListRef.value.onSearch('')
  }
  nextTick(() => {
    searchInputRef.value?.focus()
  })
}

function onSearchInput() {
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
  }
  searchDebounceTimer = setTimeout(() => {
    doSearch()
  }, 300)
}

function doSearch() {
  if (productsListRef.value?.onSearch) {
    productsListRef.value.onSearch(searchKeyword.value)
  }
}

function currentHashPage() {
  const hash = location.hash || '#/dashboard'
  return hash.replace(/^#\/?/, '') || 'dashboard'
}

function syncRouteState() {
  const currentPage = currentHashPage()
  const { tab, subPage: nextSubPage } = resolveMobileRoute(currentPage)
  activeTab.value = tab
  subPage.value = nextSubPage
  searchMode.value = false

  if (currentPage.startsWith('account-detail/')) {
    const id = currentPage.split('/')[1]
    if (id) {
      selectedAccountId.value = id
      setMobileAccountDetailId(id)
    }
  } else {
    const savedId = getMobileAccountDetailId()
    if (savedId && !selectedAccountId.value) {
      selectedAccountId.value = savedId
    }
  }

  if (currentPage.startsWith('product-detail/')) {
    const id = currentPage.split('/')[1]
    if (id) {
      setMobileProductDetailId(id)
    }
  } else {
    const savedPId = getMobileProductDetailId()
    if (savedPId && !selectedProduct.value) {
      selectedProduct.value = { id: savedPId, itemId: savedPId }
    }
  }

  nextTick(() => {
    if (contentRef.value) contentRef.value.scrollTop = 0
  })
}

onMounted(() => {
  loadUser()
  syncRouteState()
  window.addEventListener('hashchange', syncRouteState)
})

onBeforeUnmount(() => {
  window.removeEventListener('hashchange', syncRouteState)
  if (searchDebounceTimer) clearTimeout(searchDebounceTimer)
})
</script>

<style scoped>
.mobile-shell {
  width: 100%;
  max-width: 100vw;
  min-height: 100vh;
  background: linear-gradient(180deg, #f5f8ff 0%, #f0f5ff 100%);
  display: flex;
  flex-direction: column;
  position: relative;
  overflow-x: hidden;
}
.mobile-shell > header,
.mobile-shell > main,
.mobile-shell > nav {
  width: 100%;
  min-width: 0;
  max-width: 100%;
  box-sizing: border-box;
}

.m-topbar {
  position: sticky;
  top: 0;
  z-index: 50;
  background: rgba(245, 248, 255, 0.92);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  padding: calc(12px + env(safe-area-inset-top)) 16px 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(231, 237, 247, 0.5);
  gap: 10px;
}

.m-topbar-sub {
  padding: calc(10px + env(safe-area-inset-top)) 8px 10px 4px;
}

.m-topbar-search {
  padding: calc(10px + env(safe-area-inset-top)) 12px 10px;
  gap: 8px;
}

.m-menu-btn {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  border: none;
  background: white;
  color: #15213d;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(31,53,94,0.06);
  flex-shrink: 0;
}
.m-menu-btn:active { background: #f0f4fa; }

.m-brand-center {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  flex: 1;
  justify-content: center;
  min-width: 0;
}
.m-brand-mark {
  width: 32px;
  height: 32px;
  position: relative;
  flex-shrink: 0;
}
.m-brand-mark span {
  position: absolute;
  left: 12px;
  top: -2px;
  width: 10px;
  height: 34px;
  border-radius: 6px;
  background: linear-gradient(180deg, #0d7fff, #16b7ff);
  transform: rotate(42deg);
  box-shadow: 0 4px 12px rgba(13,107,255,0.25);
}
.m-brand-mark span + span {
  transform: rotate(-42deg);
  background: linear-gradient(180deg, #25a5ff, #0362f4);
}
.m-brand-name {
  font-size: 17px;
  font-weight: 800;
  color: #15213d;
  letter-spacing: -0.2px;
}

.m-top-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.m-top-action-btn {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  border: none;
  background: white;
  color: #15213d;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(31,53,94,0.06);
}
.m-top-action-btn:active { background: #f0f4fa; }

.m-back-btn {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  background: none;
  border: none;
  color: #15213d;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  padding: 6px 8px;
  border-radius: 100px;
  flex-shrink: 0;
}
.m-back-btn:active { background: rgba(13,107,255,0.08); }

.m-sub-title {
  flex: 1;
  text-align: center;
  font-size: 17px;
  font-weight: 700;
  color: #15213d;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.m-desktop-btn,
.m-icon-btn-top {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  border: none;
  background: white;
  color: #15213d;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(31,53,94,0.06);
  flex-shrink: 0;
}
.m-desktop-btn:active,
.m-icon-btn-top:active { background: #f0f4fa; }

.m-add-account-topbtn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: linear-gradient(135deg, #0d6bff, #2580ff);
  border: none;
  color: white;
  font-size: 13px;
  font-weight: 600;
  padding: 8px 14px;
  border-radius: 100px;
  cursor: pointer;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(13,107,255,0.3);
}
.m-add-account-topbtn:active { transform: scale(0.96); }

.m-search-bar {
  flex: 1;
  display: flex;
  align-items: center;
  background: white;
  border-radius: 100px;
  padding: 0 14px;
  height: 40px;
  gap: 8px;
  box-shadow: 0 2px 8px rgba(31,53,94,0.06);
  border: 1px solid #eef2fa;
}
.m-search-icon { color: #94a3b8; flex-shrink: 0; }
.m-search-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 15px;
  color: #15213d;
  min-width: 0;
}
.m-search-input::placeholder { color: #94a3b8; }
.m-search-clear {
  border: none;
  background: none;
  color: #94a3b8;
  padding: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.m-drawer-mask {
  position: fixed;
  inset: 0;
  background: rgba(15,25,50,0.4);
  z-index: 200;
  animation: fadeIn 0.2s ease;
}
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

.m-drawer {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  width: 290px;
  max-width: 82vw;
  background: white;
  z-index: 201;
  display: flex;
  flex-direction: column;
  animation: slideInLeft 0.25s ease;
  box-shadow: 4px 0 24px rgba(15,25,50,0.12);
}
@keyframes slideInLeft { from { transform: translateX(-100%); } to { transform: translateX(0); } }

.m-drawer-header {
  padding: calc(16px + env(safe-area-inset-top)) 20px 20px;
  background: linear-gradient(135deg, #0d6bff 0%, #2580ff 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.m-drawer-user {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  flex: 1;
}
.m-drawer-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: rgba(255,255,255,0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-drawer-userinfo {
  min-width: 0;
  flex: 1;
}
.m-drawer-username {
  font-size: 17px;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.m-drawer-sub {
  font-size: 12px;
  opacity: 0.8;
  margin-top: 2px;
}
.m-drawer-close {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: rgba(255,255,255,0.15);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
}
.m-drawer-close:active { background: rgba(255,255,255,0.25); }

.m-drawer-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
}
.m-drawer-group {
  margin-bottom: 16px;
}
.m-drawer-group-title {
  font-size: 12px;
  font-weight: 600;
  color: #8c98ae;
  padding: 8px 12px 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.m-drawer-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: transparent;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  text-align: left;
  transition: background 0.15s;
}
.m-drawer-item:active { background: #f5f7fb; }
.m-drawer-item.active {
  background: #eef4ff;
}
.m-drawer-item.active .m-drawer-item-label {
  color: #0d6bff;
  font-weight: 600;
}
.m-drawer-item-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-drawer-item-label {
  flex: 1;
  font-size: 15px;
  color: #1e293b;
}
.m-drawer-item-arrow {
  color: #c0c8d6;
  flex-shrink: 0;
}

.m-drawer-footer {
  padding: 12px;
  border-top: 1px solid #f0f4fa;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
}
.m-drawer-foot-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  border-radius: 12px;
  border: none;
  background: #f5f7fb;
  color: #5a6a85;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
}
.m-drawer-foot-btn:active { background: #e7edf7; }
.m-drawer-foot-btn.m-drawer-foot-danger {
  color: #ff4757;
  background: rgba(255,71,87,0.08);
}
.m-drawer-foot-btn.m-drawer-foot-danger:active { background: rgba(255,71,87,0.12); }

.m-content {
  flex: 1;
  width: 100%;
  min-width: 0;
  overflow-y: auto;
  overflow-x: hidden;
  -webkit-overflow-scrolling: touch;
  padding-bottom: calc(76px + env(safe-area-inset-bottom));
}
.m-content :deep(.m-safe-bottom) {
  display: none;
}

.m-fab-action {
  position: fixed;
  right: 20px;
  bottom: calc(92px + env(safe-area-inset-bottom));
  width: 56px;
  height: 56px;
  border-radius: 50%;
  border: none;
  background: linear-gradient(135deg, #0d7fff 0%, #3b9bff 50%, #5eb5ff 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 8px 28px rgba(13,127,255,0.45), 0 4px 12px rgba(13,127,255,0.25);
  z-index: 48;
  transition: all 0.2s;
}
.m-fab-action::before {
  content: '';
  position: absolute;
  inset: -4px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(13,127,255,0.3), rgba(94,181,255,0.3));
  z-index: -1;
  animation: fabPulse 2s ease-in-out infinite;
}
@keyframes fabPulse {
  0%, 100% { transform: scale(1); opacity: 0.6; }
  50% { transform: scale(1.15); opacity: 0; }
}
.m-fab-action:active {
  transform: scale(0.92);
}

.m-tabbar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(255,255,255,0.96);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-top: 1px solid rgba(231,237,247,0.7);
  padding: 6px 0 max(8px, env(safe-area-inset-bottom));
  display: flex;
  align-items: flex-end;
  justify-content: space-around;
  z-index: 100;
  box-shadow: 0 -4px 20px rgba(31,53,94,0.05);
  height: 64px;
  box-sizing: content-box;
}
.m-tab {
  flex: 1;
  background: none;
  border: none;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  padding: 6px 0 4px;
  color: #9aa7bc;
  font-size: 10px;
  font-weight: 500;
  cursor: pointer;
  transition: color 0.2s;
  position: relative;
  height: 100%;
}
.m-tab :deep(svg) { transition: transform 0.2s; }
.m-tab.active {
  color: #0d6bff;
}
.m-tab.active :deep(svg) {
  transform: scale(1.08);
}
.m-tab.center {
  position: relative;
}
.m-tab-center-btn {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  background: linear-gradient(135deg, #0d7fff, #3b9bff);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 6px 20px rgba(13,107,255,0.4);
  margin-bottom: 12px;
  position: relative;
  top: -14px;
}
.m-tab.center span {
  display: none;
}

@media (max-width: 360px) {
  .m-topbar { padding-left: 10px; padding-right: 10px; }
  .m-brand-name { font-size: 15px; }
  .m-top-action-btn,
  .m-menu-btn { width: 36px; height: 36px; }
  .m-drawer { width: 270px; }
}
</style>
