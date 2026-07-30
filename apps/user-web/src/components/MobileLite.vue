<template>
  <div class="mobile-shell">
    <!-- 主顶栏 -->
    <header v-if="!subPage && !searchMode" class="m-topbar">
      <div class="m-topbar-inner">
        <button class="m-menu-btn" aria-label="菜单" @click="drawerOpen = true">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="4" y1="7" x2="20" y2="7"/>
            <line x1="4" y1="12" x2="14" y2="12"/>
            <line x1="4" y1="17" x2="17" y2="17"/>
          </svg>
        </button>
        <div class="m-brand-center" @click="switchTab('home')">
          <div class="m-brand-logo">
            <div class="m-brand-logo-inner"></div>
          </div>
          <span class="m-brand-name">闲鱼助手</span>
        </div>
        <div class="m-top-actions">
          <button v-if="canSearch" class="m-top-action-btn" aria-label="搜索" @click="toggleSearch">
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="11" cy="11" r="7"/>
              <line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
          </button>
          <button class="m-top-action-btn m-top-action-btn-profile" aria-label="我的" @click="switchTab('profile')">
            <div class="m-profile-dot"></div>
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
              <circle cx="12" cy="7" r="4"/>
            </svg>
          </button>
        </div>
      </div>
    </header>

    <!-- 搜索顶栏 -->
    <header v-else-if="searchMode" class="m-topbar m-topbar-search">
      <div class="m-topbar-inner">
        <button class="m-back-btn" aria-label="关闭搜索" @click="closeSearch">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
        </button>
        <div class="m-search-bar">
          <svg class="m-search-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="7"/>
            <line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input
            ref="searchInputRef"
            v-model="searchKeyword"
            type="text"
            class="m-search-input"
            :placeholder="searchPlaceholder"
            @input="onSearchInput"
          />
          <button v-if="searchKeyword" class="m-search-clear" aria-label="清空" @click="clearSearch">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="9"/>
              <line x1="15" y1="9" x2="9" y2="15"/>
              <line x1="9" y1="9" x2="15" y2="15"/>
            </svg>
          </button>
        </div>
      </div>
    </header>

    <!-- 子页面顶栏 -->
    <header v-else class="m-topbar m-topbar-sub">
      <div class="m-topbar-inner">
        <button class="m-back-btn" @click="handleSubBack">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
        </button>
        <div class="m-sub-title">{{ subPageTitle }}</div>
        <button v-if="subPage === 'accounts'" class="m-add-account-topbtn" aria-label="添加账号" @click="triggerAddAccount">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"/>
            <line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          <span>添加</span>
        </button>
        <button v-else-if="subPage === 'account-detail'" class="m-icon-btn-top" aria-label="更多操作" @click="triggerAccountDetailMore">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="1"/>
            <circle cx="19" cy="12" r="1"/>
            <circle cx="5" cy="12" r="1"/>
          </svg>
        </button>
        <button v-else-if="subPage === 'product-detail'" class="m-icon-btn-top" aria-label="保存" @click="triggerProductSave">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
            <polyline points="17 21 17 13 7 13 7 21"/>
            <polyline points="7 3 7 8 15 8"/>
          </svg>
        </button>
        <button v-else class="m-icon-btn-top" @click="goDesktop">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
            <line x1="8" y1="21" x2="16" y2="21"/>
            <line x1="12" y1="17" x2="12" y2="21"/>
          </svg>
        </button>
      </div>
    </header>

    <MaintenanceBanner />

    <!-- 抽屉遮罩 -->
    <div v-if="drawerOpen" class="m-drawer-mask" @click="drawerOpen = false"></div>
    
    <!-- 侧边抽屉 - 两栏布局（与PC版一致）+ iOS 18 级获奖级设计 -->
    <aside v-if="drawerOpen" class="m-drawer">
      <!-- 顶部用户区域 - 极简克制 -->
      <div class="m-drawer-top">
        <div class="m-drawer-header-bar">
          <button class="m-drawer-close" aria-label="关闭菜单" @click="drawerOpen = false">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
          <span class="m-drawer-header-title">菜单</span>
          <div class="m-drawer-header-spacer"></div>
        </div>
      </div>

      <!-- 两栏导航主体 -->
      <div class="m-drawer-body">
        <!-- 左栏：一级分类（与PC版一致） -->
        <nav class="m-drawer-primary">
          <button
            v-for="group in drawerGroups"
            :key="group.key"
            class="m-drawer-primary-item"
            :class="{ 'is-active': activeDrawerGroup === group.key }"
            @click="activeDrawerGroup = group.key"
          >
            <div class="m-drawer-primary-icon" :class="`icon-bg-${group.iconClass || group.key}`">
              <MIcon :name="group.icon" :size="20" />
            </div>
            <span class="m-drawer-primary-label">{{ group.title }}</span>
          </button>
        </nav>

        <!-- 右栏：二级菜单项 -->
        <div class="m-drawer-secondary">
          <div class="m-drawer-secondary-scroll">
            <!-- 用户卡片 - 右栏顶部 -->
            <div class="m-drawer-user-card" @click="onDrawerItem('profile')">
              <div class="m-drawer-avatar-wrap">
                <div class="m-drawer-avatar">
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                    <circle cx="12" cy="7" r="4"/>
                  </svg>
                </div>
                <div class="m-drawer-avatar-status"></div>
              </div>
              <div class="m-drawer-userinfo">
                <div class="m-drawer-username">{{ username }}</div>
                <div class="m-drawer-sub-row">
                  <span class="m-drawer-badge">PRO</span>
                  <span class="m-drawer-sub-text">专业版</span>
                </div>
              </div>
              <svg class="m-drawer-user-arrow" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 18 15 12 9 6"/>
              </svg>
            </div>

            <!-- 当前分组的二级菜单 - 网格布局（一行两个） -->
            <div class="m-drawer-section">
              <div class="m-drawer-section-title">{{ currentDrawerGroup?.title }}</div>
              <div class="m-drawer-secondary-grid">
                <button
                  v-for="item in currentDrawerGroup?.items"
                  :key="item.key"
                  class="m-drawer-secondary-item"
                  :class="{ 
                    'is-active': isDrawerItemActive(item.key),
                    'is-wip': item.wip
                  }"
                  @click="onDrawerItem(item.key)"
                >
                  <span class="m-drawer-secondary-label">{{ item.label }}</span>
                  <span v-if="item.wip" class="m-drawer-wip-badge">维护中</span>
                </button>
              </div>
            </div>

            <!-- 底部操作区 -->
            <div class="m-drawer-footer">
              <button class="m-drawer-footer-item" @click="goDesktop">
                <div class="m-drawer-footer-icon icon-bg-desktop">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
                    <line x1="8" y1="21" x2="16" y2="21"/>
                    <line x1="12" y1="17" x2="12" y2="21"/>
                  </svg>
                </div>
                <span>桌面版访问</span>
                <svg class="m-drawer-footer-chevron" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="9 18 15 12 9 6"/>
                </svg>
              </button>
              <button class="m-drawer-logout-btn" @click="emit('logout')">
                <span>退出登录</span>
              </button>
            </div>

            <div class="m-drawer-safe-bottom"></div>
          </div>
        </div>
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

    <!-- FAB 快速发布按钮 -->
    <button
      v-if="showFAB"
      class="m-fab-action"
      :aria-label="fabLabel"
      @click="onFABClick"
    >
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="12" y1="5" x2="12" y2="19"/>
        <line x1="5" y1="12" x2="19" y2="12"/>
      </svg>
    </button>

    <!-- AI 客服悬浮按钮 -->
    <button
      v-if="!subPage"
      type="button"
      class="m-cs-fab"
      aria-label="联系 AI 客服小梦"
      @click="openAiCs"
    >
      <span class="m-cs-fab-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>
        </svg>
      </span>
      <span class="m-cs-fab-pulse" aria-hidden="true"></span>
    </button>

    <AiCsPanel :visible="aiCsVisible" @close="aiCsVisible = false" />

    <!-- 底部 Tab 栏 - iOS 18 级毛玻璃精品 -->
    <nav v-if="!subPage" class="m-tabbar">
      <div class="m-tabbar-bg"></div>
      <div class="m-tabbar-inner">
        <button
          v-for="tab in bottomTabs"
          :key="tab.key"
          class="m-tab"
          :class="{ active: activeTab === tab.key, center: tab.center }"
          @click="switchTab(tab.key)"
        >
          <div v-if="tab.center" class="m-tab-center-wrap">
            <div class="m-tab-center-btn">
              <MIcon :name="tab.icon" :size="22" />
            </div>
            <span class="m-tab-center-label">{{ tab.label }}</span>
          </div>
          <template v-else>
            <div class="m-tab-icon">
              <MIcon :name="tab.icon" :size="20" />
            </div>
            <span class="m-tab-label">{{ tab.label }}</span>
          </template>
        </button>
      </div>
    </nav>

    <MToast />
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount, onMounted, computed, nextTick } from 'vue'
import '../mobile-responsive.css'
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

// 导航分组 - 与PC版完全一致（两栏布局）
const drawerGroups = [
  {
    key: 'overview',
    title: '概览',
    icon: 'home',
    iconClass: 'overview',
    items: [
      { key: 'dashboard', label: '导航面板' },
      { key: 'data', label: '数据面板' }
    ]
  },
  {
    key: 'accounts',
    title: '账号',
    icon: 'users',
    iconClass: 'accounts',
    items: [
      { key: 'accounts', label: '闲鱼账号' },
      { key: 'orders', label: '订单管理' },
      { key: 'refunds', label: '退款管理', wip: true },
      { key: 'reviews', label: '评价管理', wip: true },
      { key: 'fish-shop-data', label: '鱼小铺数据分析', wip: true }
    ]
  },
  {
    key: 'products',
    title: '商品',
    icon: 'bag',
    iconClass: 'products',
    items: [
      { key: 'products', label: '商品管理' },
      { key: 'product-publish', label: '商品发布' },
      { key: 'opportunity', label: '商机发掘' },
      { key: 'product-analytics', label: '商品数据分析', wip: true }
    ]
  },
  {
    key: 'messages',
    title: '消息',
    icon: 'messageCircle',
    iconClass: 'messages',
    items: [
      { key: 'messages', label: '在线消息' },
      { key: 'auto-reply', label: '自动回复', wip: true },
      { key: 'ai-cs-settings', label: 'AI客服配置' },
      { key: 'cs-knowledge', label: '客服知识库', wip: true }
    ]
  },
  {
    key: 'auto-delivery',
    title: '自动发货',
    icon: 'send',
    iconClass: 'delivery',
    items: [
      { key: 'auto-delivery', label: '自动发货' },
      { key: 'delivery-source-library', label: '货源库' },
      { key: 'card-warehouse', label: '卡密仓库', wip: true },
      { key: 'delivery-statement', label: '发货声明', wip: true },
      { key: 'delivery-records', label: '发货记录' }
    ]
  },
  {
    key: 'distribution',
    title: '分销管理',
    icon: 'link',
    iconClass: 'distribution',
    items: [
      { key: 'supply-mall', label: '货源商城' },
      { key: 'supply-center', label: '供货中心', wip: true },
      { key: 'platform-connect', label: '平台对接', wip: true }
    ]
  },
  {
    key: 'workflow',
    title: '工作流',
    icon: 'workflow',
    iconClass: 'workflow',
    items: [
      { key: 'workflow', label: '工作流' },
      { key: 'workflow-tasks', label: '工作流任务', wip: true },
      { key: 'product-drafts', label: '商品草稿箱', wip: true },
      { key: 'image-records', label: '图片生成记录' }
    ]
  },
  {
    key: 'marketing',
    title: '营销增长',
    icon: 'trendingUp',
    iconClass: 'marketing',
    items: [
      { key: 'growth-partner', label: '增长合伙人' },
      { key: 'invite-poster', label: '邀请海报', wip: true }
    ]
  },
  {
    key: 'system',
    title: '系统',
    icon: 'settings',
    iconClass: 'system',
    items: [
      { key: 'scheduled-tasks', label: '定时任务', wip: true },
      { key: 'notifications', label: '通知设置' },
      { key: 'slider-solve', label: '滑块求解', wip: true },
      { key: 'api-slider-solve', label: 'API滑块求解' },
      { key: 'operation-logs', label: '操作日志', wip: true },
      { key: 'feedback', label: '反馈建议', wip: true },
      { key: 'about', label: '关于我们', wip: true }
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
const userInfo = ref({ username: username.value, tokenBalance: '—', accountCount: '—', orderCount: '—' })
const selectedAccountId = ref(null)
const selectedProduct = ref(null)
const selectedDeliveryGoods = ref(null)
const selectedOrderId = ref(null)
const accountsListRef = ref(null)
const accountDetailRef = ref(null)
const productsListRef = ref(null)
const productDetailRef = ref(null)
const drawerOpen = ref(false)
const activeDrawerGroup = ref('overview')

const searchMode = ref(false)
const searchKeyword = ref('')
const searchInputRef = ref(null)
let searchDebounceTimer = null

const subPageTitle = computed(() => mobileSubPages[subPage.value] || '')

const currentDrawerGroup = computed(() => {
  return drawerGroups.find(g => g.key === activeDrawerGroup.value) || drawerGroups[0]
})

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
  emit('navigate', 'product-publish')
}

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

/* ============================================================
 * 闲鱼助手移动端主壳 - 严格对齐PC版设计系统
 * 主色: #0d6bff | 背景: #f6f9ff 浅蓝渐变 | 圆角: 16px
 * ============================================================ */

.mobile-shell {
  width: 100%;
  max-width: 100vw;
  min-height: 100vh;
  background: var(--m-color-bg-gradient);
  font-family: var(--m-font-family);
  color: var(--m-color-text-primary);
  font-size: 14px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizeLegibility;
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

/* ============ 顶栏 - PC版浅蓝渐变风格 ============ */
.m-topbar {
  position: sticky;
  top: 0;
  z-index: 100;
  background: linear-gradient(180deg, #f8fbff 0%, #f4f8ff 100%);
  padding: calc(10px + var(--m-safe-area-top)) 16px 10px;
  border-bottom: 1px solid transparent;
}

.m-topbar-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-height: 42px;
}

.m-topbar-sub {
  padding-left: 8px;
  padding-right: 16px;
}

.m-topbar-search {
  padding-left: 16px;
  padding-right: 16px;
}

.m-menu-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--m-radius-lg);
  border: none;
  background: rgba(255, 255, 255, 0.9);
  color: var(--m-color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.18s ease;
  -webkit-tap-highlight-color: transparent;
  box-shadow: 0 2px 6px rgba(31, 53, 94, 0.05);
}
.m-menu-btn:active {
  background: var(--m-color-primary-lighter);
  transform: scale(0.96);
}

.m-brand-center {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  flex: 1;
  justify-content: center;
  min-width: 0;
  -webkit-tap-highlight-color: transparent;
}
.m-brand-center:active {
  opacity: 0.85;
}

/* PC版品牌Logo - 双条渐变 */
.m-brand-logo {
  width: 32px;
  height: 32px;
  position: relative;
  flex-shrink: 0;
}

.m-brand-logo-inner {
  position: absolute;
  left: 13px;
  top: 0px;
  width: 10px;
  height: 34px;
  border-radius: 7px;
  background: linear-gradient(180deg, #0d7fff, #16b7ff);
  transform: rotate(42deg);
  box-shadow: 0 4px 12px rgba(13, 107, 255, 0.28);
}
.m-brand-logo-inner::after {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  width: 10px;
  height: 34px;
  border-radius: 7px;
  background: linear-gradient(180deg, #25a5ff, #0362f4);
  transform: rotate(-84deg);
  transform-origin: center;
}

.m-brand-name {
  font-size: 18px;
  font-weight: 800;
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
  width: 36px;
  height: 36px;
  border-radius: var(--m-radius-lg);
  border: none;
  background: rgba(255, 255, 255, 0.9);
  color: var(--m-color-text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.18s ease;
  position: relative;
  -webkit-tap-highlight-color: transparent;
  box-shadow: 0 2px 6px rgba(31, 53, 94, 0.05);
}
.m-top-action-btn:active {
  background: var(--m-color-bg-hover);
  color: var(--m-color-primary);
  transform: scale(0.96);
}

.m-top-action-btn-profile .m-profile-dot {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--m-color-success);
  border: 2px solid #FFFFFF;
  box-shadow: 0 0 0 1px rgba(22, 191, 120, 0.2);
}

.m-back-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.9);
  border: none;
  color: var(--m-color-primary);
  cursor: pointer;
  padding: 8px;
  border-radius: var(--m-radius-lg);
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  transition: all 0.18s ease;
  -webkit-tap-highlight-color: transparent;
  box-shadow: 0 2px 6px rgba(31, 53, 94, 0.05);
}
.m-back-btn:active {
  background: var(--m-color-primary-lighter);
  transform: scale(0.96);
}

.m-sub-title {
  flex: 1;
  text-align: center;
  font-size: 17px;
  font-weight: 700;
  color: var(--m-color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.m-icon-btn-top {
  width: 36px;
  height: 36px;
  border-radius: var(--m-radius-lg);
  border: none;
  background: rgba(255, 255, 255, 0.9);
  color: var(--m-color-text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.18s ease;
  -webkit-tap-highlight-color: transparent;
  box-shadow: 0 2px 6px rgba(31, 53, 94, 0.05);
}
.m-icon-btn-top:active {
  background: var(--m-color-bg-hover);
  color: var(--m-color-primary);
  transform: scale(0.96);
}

/* PC版主按钮样式 - 蓝渐变+阴影 */
.m-add-account-topbtn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: var(--m-color-primary-gradient);
  border: none;
  color: white;
  font-size: 13px;
  font-weight: 700;
  padding: 8px 14px;
  border-radius: var(--m-radius-lg);
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.18s ease;
  -webkit-tap-highlight-color: transparent;
  box-shadow: var(--m-color-primary-soft-glow);
}
.m-add-account-topbtn:active {
  transform: scale(0.96);
  opacity: 0.9;
}

.m-search-bar {
  flex: 1;
  display: flex;
  align-items: center;
  background: rgba(255, 255, 255, 0.95);
  border-radius: var(--m-radius-lg);
  padding: 0 14px;
  height: 38px;
  gap: 8px;
  border: 1px solid var(--m-color-border);
  box-shadow: 0 2px 6px rgba(31, 53, 94, 0.04);
  transition: all 0.18s ease;
}
.m-search-bar:focus-within {
  border-color: var(--m-color-primary);
  background: #FFFFFF;
  box-shadow: 0 0 0 3px rgba(13, 107, 255, 0.1);
}
.m-search-icon { color: var(--m-color-text-tertiary); flex-shrink: 0; }
.m-search-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 14px;
  color: var(--m-color-text-primary);
  min-width: 0;
  font-weight: 500;
}
.m-search-input::placeholder { color: var(--m-color-text-placeholder); }
.m-search-clear {
  border: none;
  background: none;
  color: var(--m-color-text-tertiary);
  padding: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  -webkit-tap-highlight-color: transparent;
}

/* ============ 抽屉菜单 - PC版毛玻璃+两栏布局 ============ */
.m-drawer-mask {
  position: fixed;
  inset: 0;
  background: rgba(20, 36, 58, 0.5);
  z-index: 200;
  animation: maskFadeIn 0.22s ease-out;
  -webkit-tap-highlight-color: transparent;
  backdrop-filter: blur(2px);
}
@keyframes maskFadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.m-drawer {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  width: min(350px, 92vw);
  background: rgba(255, 255, 255, 0.98);
  z-index: 201;
  display: flex;
  flex-direction: column;
  animation: drawerSlideIn 0.28s cubic-bezier(0.22, 0.61, 0.36, 1);
  box-shadow: var(--m-shadow-drawer);
  overflow: hidden;
  backdrop-filter: blur(20px);
}
@keyframes drawerSlideIn {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(0); }
}

.m-drawer-top {
  position: relative;
  padding-top: calc(16px + env(safe-area-inset-top));
  padding-bottom: 16px;
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
  flex-shrink: 0;
  border-bottom: 1px solid var(--m-color-border-light);
}

.m-drawer-header-bar {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 18px;
}

.m-drawer-close {
  width: 32px;
  height: 32px;
  border-radius: var(--m-radius-lg);
  border: none;
  background: rgba(255, 255, 255, 0.9);
  color: var(--m-color-text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.18s ease;
  -webkit-tap-highlight-color: transparent;
  box-shadow: 0 2px 6px rgba(31, 53, 94, 0.05);
}
.m-drawer-close:active {
  background: var(--m-color-bg-hover);
  color: var(--m-color-primary);
  transform: scale(0.96);
}

.m-drawer-header-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--m-color-text-primary);
}

.m-drawer-header-spacer {
  width: 32px;
  height: 32px;
}

.m-drawer-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* 左栏一级分类 - PC版彩色图标风格 */
.m-drawer-primary {
  width: 84px;
  flex-shrink: 0;
  background: linear-gradient(180deg, #f8fbff 0%, #f4f8ff 100%);
  display: flex;
  flex-direction: column;
  padding: 14px 8px;
  gap: 6px;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  border-right: 1px solid var(--m-color-border-light);
}

.m-drawer-primary-item {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 10px 4px 8px;
  background: transparent;
  border: none;
  border-radius: var(--m-radius-2xl);
  cursor: pointer;
  transition: all 0.2s ease;
  -webkit-tap-highlight-color: transparent;
  position: relative;
}

.m-drawer-primary-item.is-active {
  background: #FFFFFF;
  box-shadow: var(--m-shadow-sm);
}

.m-drawer-primary-item.is-active::before {
  content: '';
  position: absolute;
  left: -8px;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  height: 24px;
  background: var(--m-color-primary-gradient);
  border-radius: 0 4px 4px 0;
  box-shadow: 0 2px 8px rgba(13, 107, 255, 0.3);
}

.m-drawer-primary-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--m-radius-2xl);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.m-drawer-primary-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--m-color-text-tertiary);
  text-align: center;
  line-height: 1.2;
}

.m-drawer-primary-item.is-active .m-drawer-primary-label {
  color: var(--m-color-text-primary);
  font-weight: 700;
}

/* PC版彩色图标背景 - 与stat-icon一致 */
.icon-bg-overview {
  background: var(--m-color-primary-bg-solid);
  color: var(--m-color-primary);
}
.icon-bg-accounts {
  background: var(--m-color-violet-bg-solid);
  color: var(--m-color-violet);
}
.icon-bg-products {
  background: var(--m-color-emerald-bg-solid);
  color: var(--m-color-emerald);
}
.icon-bg-messages {
  background: var(--m-color-cyan-bg-solid);
  color: var(--m-color-cyan);
}
.icon-bg-delivery {
  background: var(--m-color-gold-bg-solid);
  color: var(--m-color-gold);
}
.icon-bg-distribution {
  background: var(--m-color-rose-bg-solid);
  color: var(--m-color-rose);
}
.icon-bg-workflow {
  background: var(--m-color-violet-bg-solid);
  color: var(--m-color-violet);
}
.icon-bg-marketing {
  background: var(--m-color-rose-bg-solid);
  color: var(--m-color-rose);
}
.icon-bg-system {
  background: #f0f3f8;
  color: var(--m-color-text-secondary);
}
.icon-bg-desktop {
  background: var(--m-color-primary-bg-solid);
  color: var(--m-color-primary);
}

/* 右栏二级菜单 */
.m-drawer-secondary {
  flex: 1;
  background: #FFFFFF;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.m-drawer-secondary-scroll {
  flex: 1;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: 18px;
}

.m-drawer-user-card {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  padding: 14px;
  border-radius: var(--m-radius-3xl);
  background: linear-gradient(135deg, #f8fbff 0%, #edf5ff 100%);
  border: 1px solid var(--m-color-border-light);
  margin-bottom: 18px;
  transition: all 0.2s ease;
  -webkit-tap-highlight-color: transparent;
  box-shadow: var(--m-shadow-xs);
}
.m-drawer-user-card:active {
  background: var(--m-color-bg-hover);
  transform: scale(0.98);
}

.m-drawer-avatar-wrap {
  position: relative;
  flex-shrink: 0;
}

.m-drawer-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: linear-gradient(135deg, #f7a94b, #2ebd8f);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
  border: 3px solid white;
  box-shadow: 0 4px 12px rgba(33, 49, 81, 0.12);
}

.m-drawer-avatar-status {
  position: absolute;
  bottom: 2px;
  right: 2px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--m-color-success);
  border: 2.5px solid #FFFFFF;
  box-shadow: 0 0 0 1px rgba(22, 191, 120, 0.3);
}

.m-drawer-userinfo {
  min-width: 0;
  flex: 1;
}

.m-drawer-username {
  font-size: 16px;
  font-weight: 700;
  color: var(--m-color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.3;
}

.m-drawer-sub-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 5px;
}

.m-drawer-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  background: linear-gradient(135deg, #ff982a 0%, #ffb03a 100%);
  color: white;
  font-size: 10px;
  font-weight: 700;
  border-radius: 6px;
  box-shadow: 0 2px 6px rgba(255, 152, 42, 0.25);
}

.m-drawer-sub-text {
  font-size: 12px;
  color: var(--m-color-text-tertiary);
  font-weight: 500;
}

.m-drawer-user-arrow {
  color: var(--m-color-text-quaternary);
  flex-shrink: 0;
}

.m-drawer-section {
  margin-bottom: 18px;
}

.m-drawer-section-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--m-color-text-tertiary);
  margin-bottom: 10px;
  padding-left: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.m-drawer-secondary-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.m-drawer-secondary-item {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 14px 10px;
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-2xl);
  cursor: pointer;
  transition: all 0.2s ease;
  min-height: 48px;
  -webkit-tap-highlight-color: transparent;
  position: relative;
}

.m-drawer-secondary-item:active {
  background: var(--m-color-bg-hover);
  border-color: var(--m-color-border);
  transform: scale(0.98);
}

.m-drawer-secondary-item.is-active {
  background: var(--m-color-primary-bg-solid);
  border-color: rgba(13, 107, 255, 0.25);
  box-shadow: 0 4px 12px rgba(13, 107, 255, 0.1);
}

.m-drawer-secondary-item.is-active .m-drawer-secondary-label {
  color: var(--m-color-primary);
  font-weight: 700;
}

.m-drawer-secondary-item.is-wip {
  opacity: 0.55;
}

.m-drawer-secondary-label {
  font-size: 13px;
  color: var(--m-color-text-primary);
  font-weight: 600;
  text-align: center;
}

.m-drawer-wip-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  display: inline-flex;
  align-items: center;
  padding: 2px 6px;
  background: linear-gradient(135deg, #ff982a 0%, #ffb03a 100%);
  color: white;
  font-size: 9px;
  font-weight: 700;
  border-radius: 6px;
  box-shadow: 0 2px 6px rgba(255, 152, 42, 0.3);
}

.m-drawer-footer {
  margin-top: 8px;
}

.m-drawer-footer-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border-light);
  border-radius: var(--m-radius-2xl);
  cursor: pointer;
  transition: all 0.2s ease;
  margin-bottom: 10px;
  -webkit-tap-highlight-color: transparent;
}

.m-drawer-footer-item:active {
  background: var(--m-color-bg-hover);
  transform: scale(0.98);
}

.m-drawer-footer-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--m-radius-2xl);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.m-drawer-footer-item span {
  flex: 1;
  font-size: 14px;
  color: var(--m-color-text-primary);
  font-weight: 600;
  text-align: left;
}

.m-drawer-footer-chevron {
  color: var(--m-color-text-quaternary);
  flex-shrink: 0;
}

.m-drawer-logout-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 14px;
  border-radius: var(--m-radius-2xl);
  border: 1px solid #ffd6d6;
  background: #fff8f8;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  color: var(--m-color-danger);
  transition: all 0.2s ease;
  -webkit-tap-highlight-color: transparent;
}

.m-drawer-logout-btn:active {
  background: var(--m-color-danger-bg-solid);
  border-color: rgba(255, 91, 97, 0.3);
  transform: scale(0.98);
}

.m-drawer-safe-bottom {
  height: calc(20px + env(safe-area-inset-bottom));
}

/* ============ 主内容区 ============ */
.m-content {
  flex: 1;
  width: 100%;
  min-width: 0;
  overflow-y: auto;
  overflow-x: hidden;
  -webkit-overflow-scrolling: touch;
  padding-bottom: calc(84px + env(safe-area-inset-bottom));
}
.m-content :deep(.m-safe-bottom) {
  display: none;
}

/* ============ FAB按钮 - PC版主按钮风格 ============ */
.m-fab-action {
  position: fixed;
  right: 16px;
  bottom: calc(92px + env(safe-area-inset-bottom));
  width: 52px;
  height: 52px;
  border-radius: var(--m-radius-3xl);
  border: none;
  background: var(--m-color-primary-gradient);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 48;
  transition: all 0.2s ease;
  box-shadow: var(--m-shadow-fab);
  -webkit-tap-highlight-color: transparent;
}
.m-fab-action:active {
  transform: scale(0.92);
}

/* ============ 底部Tab栏 - PC版毛玻璃风格 ============ */
.m-tabbar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 100;
  padding-bottom: max(0px, env(safe-area-inset-bottom));
  background: rgba(255, 255, 255, 0.92);
  border-top: 1px solid var(--m-color-border);
  backdrop-filter: var(--m-blur-tabbar);
  -webkit-backdrop-filter: var(--m-blur-tabbar);
}

.m-tabbar-bg {
  display: none;
}

.m-tabbar-inner {
  position: relative;
  display: flex;
  align-items: flex-start;
  justify-content: space-around;
  height: 60px;
  padding-top: 8px;
}

.m-tab {
  flex: 1;
  background: none;
  border: none;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  gap: 3px;
  padding: 4px 0;
  color: var(--m-color-text-tertiary);
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
  height: 100%;
  -webkit-tap-highlight-color: transparent;
}

.m-tab-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--m-color-text-tertiary);
  transition: all 0.2s ease;
}

.m-tab.active .m-tab-icon {
  color: var(--m-color-primary);
  transform: scale(1.08);
}

.m-tab-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--m-color-text-tertiary);
  transition: all 0.2s ease;
}

.m-tab.active .m-tab-label {
  color: var(--m-color-primary);
  font-weight: 700;
}

.m-tab.center {
  position: relative;
}

.m-tab-center-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-top: -24px;
}

.m-tab-center-btn {
  width: 48px;
  height: 48px;
  border-radius: var(--m-radius-3xl);
  background: var(--m-color-primary-gradient);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--m-shadow-fab);
  transition: all 0.2s ease;
  border: 3px solid rgba(255, 255, 255, 0.9);
}

.m-tab:active .m-tab-center-btn {
  transform: scale(0.92);
}

.m-tab-center-label {
  font-size: 10px;
  color: var(--m-color-text-tertiary);
  margin-top: 5px;
  font-weight: 600;
}

.m-tab.active .m-tab-center-label {
  color: var(--m-color-primary);
  font-weight: 700;
}

/* ============ AI客服FAB - PC版绿色风格 ============ */
.m-cs-fab {
  position: fixed;
  right: 16px;
  bottom: calc(156px + env(safe-area-inset-bottom));
  z-index: 50;
  width: 48px;
  height: 48px;
  border-radius: var(--m-radius-3xl);
  border: none;
  background: linear-gradient(135deg, #16bf78 0%, #0fa566 100%);
  color: #fff;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  padding: 0;
  box-shadow: 0 9px 18px rgba(22, 191, 120, 0.25), 0 4px 12px rgba(31, 53, 94, 0.1);
  -webkit-tap-highlight-color: transparent;
}

.m-cs-fab:active {
  transform: scale(0.92);
}

.m-cs-fab-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 0;
  position: relative;
  z-index: 1;
}

.m-cs-fab-pulse {
  position: absolute;
  top: 3px;
  right: 3px;
  width: 11px;
  height: 11px;
  border-radius: 50%;
  background: var(--m-color-danger);
  border: 2.5px solid #fff;
  z-index: 2;
  box-shadow: 0 0 0 1px rgba(255, 91, 97, 0.3);
}

/* ============ 响应式 ============ */
@media (max-width: 360px) {
  .m-topbar { padding-left: 12px; padding-right: 12px; }
  .m-drawer { width: min(330px, 94vw); }
  .m-brand-name { font-size: 16px; }
  .m-drawer-primary { width: 76px; }
  .m-drawer-secondary-grid { gap: 8px; }
}
</style>
