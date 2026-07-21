const ACCOUNT_DETAIL_KEY = 'mobile_account_detail_id'
const PRODUCT_DETAIL_KEY = 'mobile_product_detail_id'

const routeStates = Object.freeze({
  dashboard: { tab: 'home', subPage: null },
  data: { tab: 'data', subPage: null },
  'data-detail': { tab: 'data', subPage: 'data-detail' },
  accounts: { tab: 'home', subPage: 'accounts' },
  'account-detail': { tab: 'home', subPage: 'account-detail' },
  products: { tab: 'home', subPage: 'products' },
  'product-detail': { tab: 'home', subPage: 'product-detail' },
  'product-publish': { tab: 'home', subPage: 'product-publish' },
  orders: { tab: 'orders', subPage: null },
  messages: { tab: 'home', subPage: 'messages' },
  'message-center': { tab: 'home', subPage: 'messages' },
  'chat-detail': { tab: 'home', subPage: 'chat-detail' },
  workflow: { tab: 'automation', subPage: null },
  'auto-delivery': { tab: 'automation', subPage: 'auto-delivery' },
  profile: { tab: 'profile', subPage: null }
})

const tabPages = Object.freeze({
  home: 'dashboard',
  data: 'data',
  automation: 'workflow',
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
  if (pageKey.startsWith('data-detail/')) {
    return { tab: 'data', subPage: 'data-detail' }
  }
  if (pageKey.startsWith('chat-detail/')) {
    return { tab: 'home', subPage: 'chat-detail' }
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
