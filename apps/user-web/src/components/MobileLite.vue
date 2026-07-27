<template>
  <div class="mobile-shell">
    <header v-if="!subPage && !searchMode" class="m-topbar">
      <button class="m-menu-btn" aria-label="菜单" @click="drawerOpen = true">
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
        <button v-if="canSearch" class="m-top-action-btn" aria-label="搜索" @click="toggleSearch">
          <MIcon name="search" :size="20" />
        </button>
        <button class="m-top-action-btn" aria-label="我的" @click="switchTab('profile')">
          <MIcon name="user" :size="20" />
        </button>
      </div>
    </header>

    <header v-else-if="searchMode" class="m-topbar m-topbar-search">
      <button class="m-back-btn" aria-label="关闭搜索" @click="closeSearch">
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
        <button v-if="searchKeyword" class="m-search-clear" aria-label="清空" @click="clearSearch">
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
      <button v-if="subPage === 'accounts'" class="m-add-account-topbtn" aria-label="添加账号" @click="triggerAddAccount">
        <MIcon name="plus" :size="16" />
        <span>添加</span>
      </button>
      <button v-else-if="subPage === 'account-detail'" class="m-icon-btn-top" aria-label="更多操作" @click="triggerAccountDetailMore">
        <MIcon name="moreVertical" :size="22" />
      </button>
      <button v-else-if="subPage === 'product-detail'" class="m-icon-btn-top" aria-label="保存" @click="triggerProductSave">
        <MIcon name="save" :size="20" />
      </button>
      <button v-else class="m-desktop-btn" @click="goDesktop">
        <MIcon name="desktop" :size="20" />
      </button>
    </header>

    <MaintenanceBanner />

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
        <button class="m-drawer-close" aria-label="关闭菜单" @click="drawerOpen = false">
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
      <MobileOpportunity
        v-else-if="subPage === 'opportunity'"
        @navigate="onSubNavigate"
        @force-desktop="goDesktop"
        @back="backToMain"
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
      <MobileNotifications
        v-else-if="subPage === 'notifications'"
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
      <MobileAutoDeliveryConfig
        v-else-if="subPage === 'auto-delivery-config'"
        :goods-id="selectedDeliveryGoodsId"
        :product="selectedDeliveryGoods"
        @navigate="onSubNavigate"
        @force-desktop="goDesktop"
        @back="backToAutoDelivery"
        @saved="onDeliveryConfigSaved"
      />
      <MobileDeliverySourceLibrary
        v-else-if="subPage === 'delivery-source-library'"
        @navigate="onSubNavigate"
        @force-desktop="goDesktop"
        @back="backToWorkflow"
      />
      <MobileDeliveryRecords
        v-else-if="subPage === 'delivery-records'"
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
      <MobileOrderDetail
        v-else-if="subPage === 'order-detail'"
        :order-id="selectedOrderId"
        @navigate="onSubNavigate"
        @force-desktop="goDesktop"
        @back="backToOrders"
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
      <MobileProfileSecurity
        v-else-if="subPage === 'profile-security'"
        @navigate="onSubNavigate"
        @force-desktop="goDesktop"
        @updated="onProfileSecurityUpdated"
      />
      <MobileProfileLedger
        v-else-if="subPage === 'profile-ledger'"
        @navigate="onSubNavigate"
        @force-desktop="goDesktop"
      />
      <MobileProfileRecharge
        v-else-if="subPage === 'profile-recharge'"
        @navigate="onSubNavigate"
        @force-desktop="goDesktop"
      />
      <MobileApiSliderSolve
        v-else-if="subPage === 'api-slider-solve'"
        @navigate="onSubNavigate"
        @force-desktop="goDesktop"
        @back="backToMain"
      />
    </main>

    <button
      v-if="showFAB"
      class="m-fab-action"
      :aria-label="fabLabel"
      @click="onFABClick"
    >
      <MIcon :name="fabIcon" :size="26" />
    </button>

    <button
      v-if="!subPage"
      type="button"
      class="m-cs-fab"
      aria-label="联系 AI 客服小梦"
      @click="openAiCs"
    >
      <span class="m-cs-fab-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>
        </svg>
      </span>
      <span class="m-cs-fab-pulse" aria-hidden="true"></span>
    </button>

    <AiCsPanel :visible="aiCsVisible" @close="aiCsVisible = false" />

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

    <MToast />
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount, onMounted, computed, nextTick } from 'vue'
import MIcon from '../mobile/MIcon.vue'
import MaintenanceBanner from './MaintenanceBanner.vue'
import AiCsPanel from './AiCsPanel.vue'
import MobileHome from '../mobile/MobileHome.vue'
import MobileMessages from '../mobile/MobileMessages.vue'
import MobileNotifications from '../mobile/MobileNotifications.vue'
import MobileAutomation from '../mobile/MobileAutomation.vue'
import MobileProfile from '../mobile/MobileProfile.vue'
import MobileProfileSecurity from '../mobile/MobileProfileSecurity.vue'
import MobileProfileLedger from '../mobile/MobileProfileLedger.vue'
import MobileProfileRecharge from '../mobile/MobileProfileRecharge.vue'
import MobileProducts from '../mobile/MobileProducts.vue'
import MobileProductDetail from '../mobile/MobileProductDetail.vue'
import MobileProductPublish from '../mobile/MobileProductPublish.vue'
import MobileAccounts from '../mobile/MobileAccounts.vue'
import MobileAccountDetail from '../mobile/MobileAccountDetail.vue'
import MobileData from '../mobile/MobileData.vue'
import MobileDataDetail from '../mobile/MobileDataDetail.vue'
import MobileAutoDelivery from '../mobile/MobileAutoDelivery.vue'
import MobileAutoDeliveryConfig from '../mobile/MobileAutoDeliveryConfig.vue'
import MobileDeliveryRecords from '../mobile/MobileDeliveryRecords.vue'
import MobileDeliverySourceLibrary from '../mobile/MobileDeliverySourceLibrary.vue'
import MobileOrders from '../mobile/MobileOrders.vue'
import MobileOrderDetail from '../mobile/MobileOrderDetail.vue'
import MobileOpportunity from '../mobile/MobileOpportunity.vue'
import MobileChatDetail from '../mobile/MobileChatDetail.vue'
import MobileApiSliderSolve from '../mobile/MobileApiSliderSolve.vue'
import MToast from '../mobile/components/MToast.vue'
import { getCachedUsername } from '../utils/auth.js'
import { currentUser } from '../api/system.js'
import { pageForMobileTab, resolveMobileRoute, getMobileAccountDetailId, setMobileAccountDetailId, getMobileProductDetailId, setMobileProductDetailId, getMobileAutoDeliveryConfigId, setMobileAutoDeliveryConfigId, getMobileOrderDetailId, setMobileOrderDetailId } from '../mobile/mobileRouteState.js'

const emit = defineEmits(['navigate', 'logout', 'force-desktop'])

const bottomTabs = [
  { key: 'home', label: '首页', icon: 'home' },
  { key: 'products', label: '商品', icon: 'bag' },
  { key: 'product-publish', label: '发布', icon: 'plus', center: true },
  { key: 'orders', label: '订单', icon: 'shoppingCart' },
  { key: 'profile', label: '我的', icon: 'user' }
]

const drawerGroups = [
  {
    title: '工作台',
    items: [
      { key: 'dashboard', label: '首页概览', icon: 'home', iconBg: 'rgba(51,128,255,0.1)', iconColor: '#3380ff' },
      { key: 'data', label: '数据看板', icon: 'pieChart', iconBg: 'rgba(139,92,246,0.1)', iconColor: '#8b5cf6' },
      { key: 'data-detail', label: '数据详情', icon: 'chart', iconBg: 'rgba(139,92,246,0.1)', iconColor: '#8b5cf6' }
    ]
  },
  {
    title: '商品与订单',
    items: [
      { key: 'products', label: '商品管理', icon: 'bag', iconBg: 'rgba(22,191,120,0.1)', iconColor: '#16bf78' },
      { key: 'product-publish', label: '发布商品', icon: 'edit', iconBg: 'rgba(22,191,120,0.1)', iconColor: '#16bf78' },
      { key: 'orders', label: '订单管理', icon: 'shoppingCart', iconBg: 'rgba(255,124,67,0.1)', iconColor: '#ff7c43' },
      { key: 'order-detail', label: '订单详情', icon: 'fileText', iconBg: 'rgba(255,124,67,0.1)', iconColor: '#ff7c43' },
      { key: 'opportunity', label: '商机发掘', icon: 'zap', iconBg: 'rgba(255,159,34,0.1)', iconColor: '#ff9f22' }
    ]
  },
  {
    title: '账号与消息',
    items: [
      { key: 'accounts', label: '账号管理', icon: 'users', iconBg: 'rgba(51,128,255,0.1)', iconColor: '#3380ff' },
      { key: 'account-detail', label: '账号详情', icon: 'user', iconBg: 'rgba(51,128,255,0.1)', iconColor: '#3380ff' },
      { key: 'messages', label: '在线消息', icon: 'messageCircle', iconBg: 'rgba(22,191,120,0.1)', iconColor: '#16bf78' },
      { key: 'notifications', label: '消息中心', icon: 'bell', iconBg: 'rgba(255,159,34,0.1)', iconColor: '#ff9f22' }
    ]
  },
  {
    title: '自动化',
    items: [
      { key: 'workflow', label: '工作流', icon: 'workflow', iconBg: 'rgba(139,92,246,0.1)', iconColor: '#8b5cf6' },
      { key: 'auto-delivery', label: '自动发货', icon: 'send', iconBg: 'rgba(255,159,34,0.1)', iconColor: '#ff9f22' },
      { key: 'auto-delivery-config', label: '自动发货配置', icon: 'settings', iconBg: 'rgba(255,159,34,0.1)', iconColor: '#ff9f22' },
      { key: 'delivery-source-library', label: '货源库', icon: 'folder', iconBg: 'rgba(139,92,246,0.1)', iconColor: '#8b5cf6' },
      { key: 'delivery-records', label: '发货记录', icon: 'truck', iconBg: 'rgba(255,159,34,0.1)', iconColor: '#ff9f22' }
    ]
  },
  {
    title: '个人',
    items: [
      { key: 'profile-security', label: '安全设置', icon: 'shield', iconBg: 'rgba(51,128,255,0.1)', iconColor: '#3380ff' },
      { key: 'profile-ledger', label: 'Token 流水', icon: 'coins', iconBg: 'rgba(255,159,34,0.1)', iconColor: '#ff9f22' },
      { key: 'profile-recharge', label: '充值记录', icon: 'dollar', iconBg: 'rgba(22,191,120,0.1)', iconColor: '#16bf78' },
      { key: 'api-slider-solve', label: 'API滑块求解', icon: 'link', iconBg: 'rgba(51,128,255,0.1)', iconColor: '#3380ff' }
    ]
  }
]

const mobileSubPages = {
  products: '商品管理',
  'product-detail': '商品详情',
  'product-publish': '发布宝贝',
  opportunity: '商机发掘',
  accounts: '账号管理',
  'account-detail': '账号详情',
  'data-detail': '数据详情',
  messages: '在线消息',
  'chat-detail': '聊天详情',
  notifications: '消息中心',
  'auto-delivery': '自动发货',
  'auto-delivery-config': '配置自动发货',
  'delivery-records': '发货记录',
  'delivery-source-library': '货源库',
  'order-detail': '订单详情',
  'profile-security': '账号安全',
  'profile-ledger': 'Token 流水',
  'profile-recharge': '充值记录',
  'api-slider-solve': 'API滑块求解'
}

const activeTab = ref('home')
const subPage = ref(null)
const contentRef = ref(null)
const username = ref(getCachedUsername() || '未登录用户')
const userInfo = ref({ username: username.value })
const selectedAccountId = ref(null)
const selectedProduct = ref(null)
const selectedDeliveryGoods = ref(null)
const selectedOrderId = ref(null)
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

const selectedDeliveryGoodsId = computed(() => {
  return selectedDeliveryGoods.value?.id
    || getMobileAutoDeliveryConfigId()
    || null
})

const canSearch = computed(() => {
  return subPage.value === 'products'
})

const searchPlaceholder = computed(() => {
  if (subPage.value === 'products') return '搜索商品名称、ID'
  return '搜索'
})

const showFAB = computed(() => {
  return subPage.value === 'products' || (!subPage.value && activeTab.value === 'home')
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

// AI 客服"小梦"面板可见性（仅在不显示底部 tab 的子页面时不出现 FAB）
const aiCsVisible = ref(false)
function openAiCs() {
  aiCsVisible.value = true
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

function onSubNavigate(pageKey, payload) {
  if (pageKey === 'auto-delivery-config') {
    const id = payload?.productId
    if (id) {
      selectedDeliveryGoods.value = { id }
      setMobileAutoDeliveryConfigId(id)
    }
    emit('navigate', 'auto-delivery-config')
    return
  }
  if (pageKey === 'product-detail' && payload?.id) {
    selectedProduct.value = selectedProduct.value || { id: payload.id, itemId: payload.id }
    setMobileProductDetailId(payload.id)
    emit('navigate', `product-detail/${payload.id}`)
    return
  }
  if (pageKey === 'order-detail' && payload?.id) {
    selectedOrderId.value = payload.id
    setMobileOrderDetailId(payload.id)
    emit('navigate', `order-detail/${payload.id}`)
    return
  }
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

function backToProfile() {
  emit('navigate', 'profile')
}

function onProfileSecurityUpdated() {
  // 安全信息更新后，MobileProfile 在重新挂载时会自动重新加载 overview
}

function backToWorkflow() {
  emit('navigate', 'workflow')
}

function backToAutoDelivery() {
  setMobileAutoDeliveryConfigId(null)
  selectedDeliveryGoods.value = null
  emit('navigate', 'auto-delivery')
}

function onDeliveryConfigSaved() {
  // 保存成功后由 back 事件触发返回到 auto-delivery，MobileAutoDelivery 在 onMounted 中会重新加载
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

function backToOrders() {
  setMobileOrderDetailId(null)
  selectedOrderId.value = null
  emit('navigate', 'orders')
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
  } else if (subPage.value === 'order-detail') {
    backToOrders()
  } else if (subPage.value === 'auto-delivery') {
    backToWorkflow()
  } else if (subPage.value === 'auto-delivery-config') {
    backToAutoDelivery()
  } else if (subPage.value === 'delivery-source-library') {
    backToWorkflow()
  } else if (subPage.value === 'delivery-records') {
    backToWorkflow()
  } else if (subPage.value === 'data-detail') {
    backToData()
  } else if (subPage.value === 'chat-detail') {
    backToMessages()
  } else if (subPage.value === 'messages') {
    backToMain()
  } else if (subPage.value === 'notifications') {
    backToMain()
  } else if (subPage.value === 'profile-security' || subPage.value === 'profile-ledger' || subPage.value === 'profile-recharge') {
    backToProfile()
  } else if (subPage.value === 'api-slider-solve') {
    backToMain()
  } else if (subPage.value === 'products' || subPage.value === 'accounts' || subPage.value === 'opportunity') {
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

  if (currentPage.startsWith('auto-delivery-config/')) {
    const id = currentPage.split('/')[1]
    if (id) {
      selectedDeliveryGoods.value = { id }
      setMobileAutoDeliveryConfigId(id)
    }
  } else if (currentPage === 'auto-delivery-config') {
    const savedGoodsId = getMobileAutoDeliveryConfigId()
    if (savedGoodsId && !selectedDeliveryGoods.value) {
      selectedDeliveryGoods.value = { id: savedGoodsId }
    }
  } else {
    // 离开配置页时不清空 sessionStorage，仅在显式返回时清理（backToAutoDelivery）
  }

  if (currentPage.startsWith('order-detail/')) {
    const id = currentPage.split('/')[1]
    if (id) {
      selectedOrderId.value = id
      setMobileOrderDetailId(id)
    }
  } else {
    const savedOrderId = getMobileOrderDetailId()
    if (savedOrderId && !selectedOrderId.value) {
      selectedOrderId.value = savedOrderId
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
@import '../mobile/tokens.css';
.mobile-shell {
  width: 100%;
  max-width: 100vw;
  min-height: 100vh;
  background: var(--m-color-bg-page);
  font-family: var(--m-font-family);
  color: var(--m-color-text-primary);
  font-size: var(--m-font-size-body);
  line-height: var(--m-line-height-base);
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
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  padding: calc(var(--m-space-3) + var(--m-safe-area-top)) var(--m-space-4) 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--m-color-border-light);
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
  width: var(--m-space-10);
  height: var(--m-space-10);
  border-radius: var(--m-radius-lg);
  border: none;
  background: var(--m-color-bg-card);
  color: var(--m-color-text-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: var(--m-shadow-card);
  flex-shrink: 0;
}
.m-menu-btn:active { background: var(--m-color-bg-subtle); }

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
  box-shadow: 0 4px 12px rgba(51,128,255,0.25);
}
.m-brand-mark span + span {
  transform: rotate(-42deg);
  background: linear-gradient(180deg, #25a5ff, #0362f4);
}
.m-brand-name {
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-extrabold);
  color: var(--m-color-text-primary);
  letter-spacing: -0.2px;
}

.m-top-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.m-top-action-btn {
  width: var(--m-space-10);
  height: var(--m-space-10);
  border-radius: var(--m-radius-lg);
  border: none;
  background: var(--m-color-bg-card);
  color: var(--m-color-text-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: var(--m-shadow-card);
}
.m-top-action-btn:active { background: var(--m-color-bg-subtle); }

.m-back-btn {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  background: none;
  border: none;
  color: var(--m-color-text-primary);
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-semibold);
  cursor: pointer;
  padding: 6px 8px;
  border-radius: var(--m-radius-pill);
  flex-shrink: 0;
}
.m-back-btn:active { background: var(--m-color-primary-bg); }

.m-sub-title {
  flex: 1;
  text-align: center;
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-bold);
  color: var(--m-color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.m-desktop-btn,
.m-icon-btn-top {
  width: var(--m-space-10);
  height: var(--m-space-10);
  border-radius: var(--m-radius-lg);
  border: none;
  background: var(--m-color-bg-card);
  color: var(--m-color-text-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: var(--m-shadow-card);
  flex-shrink: 0;
}
.m-desktop-btn:active,
.m-icon-btn-top:active { background: var(--m-color-bg-subtle); }

.m-add-account-topbtn {
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-1);
  background: linear-gradient(135deg, #3380ff, #2580ff);
  border: none;
  color: var(--m-color-text-inverse);
  font-size: var(--m-font-size-body-sm);
  font-weight: var(--m-font-weight-semibold);
  padding: 8px 14px;
  border-radius: var(--m-radius-pill);
  cursor: pointer;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(51,128,255,0.3);
}
.m-add-account-topbtn:active { transform: scale(0.96); }

.m-search-bar {
  flex: 1;
  display: flex;
  align-items: center;
  background: var(--m-color-bg-card);
  border-radius: var(--m-radius-pill);
  padding: 0 14px;
  height: var(--m-space-10);
  gap: var(--m-space-2);
  box-shadow: var(--m-shadow-card);
  border: 1px solid var(--m-color-border-light);
}
.m-search-icon { color: var(--m-color-text-tertiary); flex-shrink: 0; }
.m-search-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: var(--m-font-size-h3);
  color: var(--m-color-text-primary);
  min-width: 0;
}
.m-search-input::placeholder { color: var(--m-color-text-tertiary); }
.m-search-clear {
  border: none;
  background: none;
  color: var(--m-color-text-tertiary);
  padding: var(--m-space-1);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.m-drawer-mask {
  position: fixed;
  inset: 0;
  background: var(--m-mask-drawer);
  z-index: 200;
  animation: fadeIn 0.2s ease;
}
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

.m-drawer {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  width: 300px;
  max-width: 82vw;
  background: var(--m-color-bg-card);
  z-index: 201;
  display: flex;
  flex-direction: column;
  animation: slideInLeft 0.25s ease;
  box-shadow: var(--m-shadow-elevated);
}
@keyframes slideInLeft { from { transform: translateX(-100%); } to { transform: translateX(0); } }

.m-drawer-header {
  padding: calc(16px + env(safe-area-inset-top)) 20px 20px;
  background: linear-gradient(135deg, #3380ff 0%, #2580ff 100%);
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
  font-size: var(--m-font-size-caption);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-tertiary);
  padding: var(--m-space-2) var(--m-space-3) 6px;
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
.m-drawer-item:active { background: var(--m-color-bg-hover); }
.m-drawer-item.active {
  background: var(--m-color-primary-bg);
}
.m-drawer-item.active .m-drawer-item-label {
  color: var(--m-color-primary);
  font-weight: var(--m-font-weight-semibold);
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
  font-size: var(--m-font-size-h3);
  color: var(--m-color-text-primary);
}
.m-drawer-item-arrow {
  color: var(--m-color-text-disabled);
  flex-shrink: 0;
}

.m-drawer-footer {
  padding: var(--m-space-3);
  border-top: 1px solid var(--m-color-border-light);
  display: flex;
  flex-direction: column;
  gap: var(--m-space-2);
  padding-bottom: calc(var(--m-space-3) + var(--m-safe-area-bottom));
}
.m-drawer-foot-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-2);
  padding: var(--m-space-3);
  border-radius: var(--m-radius-lg);
  border: 1px solid var(--m-color-border);
  background: var(--m-color-bg-card);
  color: var(--m-color-text-secondary);
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-medium);
  cursor: pointer;
}
.m-drawer-foot-btn:active { background: var(--m-color-bg-subtle); }
.m-drawer-foot-btn.m-drawer-foot-danger {
  color: var(--m-color-danger);
  background: var(--m-color-danger-bg);
  border-color: var(--m-color-danger-border);
}
.m-drawer-foot-btn.m-drawer-foot-danger:active { background: var(--m-color-danger-bg); }

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
  border-top: 1px solid var(--m-color-border-light);
  padding: 6px 0 max(8px, var(--m-safe-area-bottom));
  display: flex;
  align-items: flex-end;
  justify-content: space-around;
  z-index: 100;
  box-shadow: var(--m-shadow-tabbar);
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
  color: var(--m-color-text-tertiary);
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-medium);
  cursor: pointer;
  transition: color 0.2s;
  position: relative;
  height: 100%;
}
.m-tab :deep(svg) { transition: transform 0.2s; }
.m-tab.active {
  color: var(--m-color-primary);
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
  border-radius: var(--m-radius-circle);
  background: linear-gradient(135deg, #0d7fff, #3b9bff);
  color: var(--m-color-text-inverse);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--m-shadow-fab);
  margin-bottom: var(--m-space-3);
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

/* AI 客服悬浮按钮：独立 FAB，不修改 .m-topbar / .m-tabbar / .m-drawer */
.m-cs-fab {
  position: fixed;
  right: 16px;
  bottom: 84px; /* 位于底部 tab 之上 */
  z-index: 50;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: none;
  background: linear-gradient(135deg, #147dff 0%, #0865f4 100%);
  color: #fff;
  box-shadow: 0 8px 24px rgba(20, 125, 255, 0.4), 0 2px 8px rgba(31, 53, 94, 0.16);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  padding: 0;
}

.m-cs-fab:active {
  transform: scale(0.92);
}

.m-cs-fab-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 0;
}

.m-cs-fab-pulse {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #22c55e;
  border: 2px solid #fff;
  box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.6);
  animation: m-cs-fab-pulse-anim 2s infinite;
}

@keyframes m-cs-fab-pulse-anim {
  0% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.55); }
  70% { box-shadow: 0 0 0 8px rgba(34, 197, 94, 0); }
  100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
}
</style>
