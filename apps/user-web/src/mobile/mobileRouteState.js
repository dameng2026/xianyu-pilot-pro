const ACCOUNT_DETAIL_KEY = 'mobile_account_detail_id'
const PRODUCT_DETAIL_KEY = 'mobile_product_detail_id'
const AUTO_DELIVERY_CONFIG_KEY = 'mobile_auto_delivery_config_id'
const ORDER_DETAIL_KEY = 'mobile_order_detail_id'

const routeStates = Object.freeze({
  dashboard: { tab: 'home', subPage: null },
  data: { tab: 'data', subPage: null },
  'data-detail': { tab: 'data', subPage: 'data-detail' },
  accounts: { tab: 'home', subPage: 'accounts' },
  'account-detail': { tab: 'home', subPage: 'account-detail' },
  products: { tab: 'products', subPage: 'products' },
  'product-detail': { tab: 'home', subPage: 'product-detail' },
  'product-publish': { tab: 'product-publish', subPage: 'product-publish' },
  opportunity: { tab: 'home', subPage: 'opportunity' },
  orders: { tab: 'orders', subPage: null },
  'order-detail': { tab: 'orders', subPage: 'order-detail' },
  messages: { tab: 'home', subPage: 'messages' },
  'message-center': { tab: 'home', subPage: 'messages' },
  notifications: { tab: 'home', subPage: 'notifications' },
  // @deprecated chat-detail 已废弃，聊天详情统一在 MobileMessages 内查看。
  // 保留 key 仅为向后兼容：旧路由会自动重定向到 messages 子页。
  'chat-detail': { tab: 'home', subPage: 'messages' },
  workflow: { tab: 'automation', subPage: null },
  'auto-delivery': { tab: 'automation', subPage: 'auto-delivery' },
  'auto-delivery-config': { tab: 'automation', subPage: 'auto-delivery-config' },
  'delivery-records': { tab: 'automation', subPage: 'delivery-records' },
  'delivery-source-library': { tab: 'automation', subPage: 'delivery-source-library' },
  profile: { tab: 'profile', subPage: null },
  'profile-security': { tab: 'profile', subPage: 'profile-security' },
  'profile-ledger': { tab: 'profile', subPage: 'profile-ledger' },
  'profile-recharge': { tab: 'profile', subPage: 'profile-recharge' }
})

const tabPages = Object.freeze({
  home: 'dashboard',
  data: 'data',
  automation: 'workflow',
  products: 'products',
  'product-publish': 'product-publish',
  orders: 'orders',
  profile: 'profile'
})

function resolveRouteFromKey(pageKey) {
  if (!pageKey) return routeStates.dashboard
  if (pageKey.startsWith('account-detail/')) {
    const id = pageKey.split('/')[1] || null
    if (id) setMobileAccountDetailId(id)
    return { tab: 'home', subPage: 'account-detail' }
  }
  if (pageKey.startsWith('product-detail/')) {
    const id = pageKey.split('/')[1] || null
    if (id) setMobileProductDetailId(id)
    return { tab: 'home', subPage: 'product-detail' }
  }
  if (pageKey.startsWith('auto-delivery-config/')) {
    const id = pageKey.split('/')[1] || null
    if (id) setMobileAutoDeliveryConfigId(id)
    return { tab: 'automation', subPage: 'auto-delivery-config' }
  }
  if (pageKey.startsWith('order-detail/')) {
    const id = pageKey.split('/')[1] || null
    if (id) setMobileOrderDetailId(id)
    return { tab: 'orders', subPage: 'order-detail' }
  }
  if (pageKey.startsWith('data-detail/')) {
    return { tab: 'data', subPage: 'data-detail' }
  }
  // @deprecated chat-detail/* 已废弃，重定向到 messages 子页
  if (pageKey.startsWith('chat-detail/')) {
    return { tab: 'home', subPage: 'messages' }
  }
  return routeStates[pageKey] || routeStates.dashboard
}

export function resolveMobileRoute(pageKey) {
  return resolveRouteFromKey(pageKey)
}

export function pageForMobileTab(tab) {
  return tabPages[tab] || ''
}

export function getMobileAccountDetailId() {
  try {
    return sessionStorage.getItem(ACCOUNT_DETAIL_KEY)
  } catch (e) {
    return null
  }
}

export function setMobileAccountDetailId(id) {
  try {
    if (id) {
      sessionStorage.setItem(ACCOUNT_DETAIL_KEY, String(id))
    } else {
      sessionStorage.removeItem(ACCOUNT_DETAIL_KEY)
    }
  } catch (e) {}
}

export function getMobileProductDetailId() {
  try {
    return sessionStorage.getItem(PRODUCT_DETAIL_KEY)
  } catch (e) {
    return null
  }
}

export function setMobileProductDetailId(id) {
  try {
    if (id) {
      sessionStorage.setItem(PRODUCT_DETAIL_KEY, String(id))
    } else {
      sessionStorage.removeItem(PRODUCT_DETAIL_KEY)
    }
  } catch (e) {}
}

export function getMobileAutoDeliveryConfigId() {
  try {
    return sessionStorage.getItem(AUTO_DELIVERY_CONFIG_KEY)
  } catch (e) {
    return null
  }
}

export function setMobileAutoDeliveryConfigId(id) {
  try {
    if (id) {
      sessionStorage.setItem(AUTO_DELIVERY_CONFIG_KEY, String(id))
    } else {
      sessionStorage.removeItem(AUTO_DELIVERY_CONFIG_KEY)
    }
  } catch (e) {}
}

export function getMobileOrderDetailId() {
  try {
    return sessionStorage.getItem(ORDER_DETAIL_KEY)
  } catch (e) {
    return null
  }
}

export function setMobileOrderDetailId(id) {
  try {
    if (id) {
      sessionStorage.setItem(ORDER_DETAIL_KEY, String(id))
    } else {
      sessionStorage.removeItem(ORDER_DETAIL_KEY)
    }
  } catch (e) {}
}
