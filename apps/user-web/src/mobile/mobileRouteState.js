const routeStates = Object.freeze({
  dashboard: { tab: 'home', subPage: null },
  data: { tab: 'home', subPage: 'data' },
  accounts: { tab: 'home', subPage: 'accounts' },
  products: { tab: 'home', subPage: 'products' },
  messages: { tab: 'message', subPage: null },
  'message-center': { tab: 'message', subPage: null },
  workflow: { tab: 'automation', subPage: null },
  profile: { tab: 'profile', subPage: null }
})

const tabPages = Object.freeze({
  home: 'dashboard',
  message: 'messages',
  automation: 'workflow',
  profile: 'profile'
})

export function resolveMobileRoute(pageKey) {
  return routeStates[pageKey] || routeStates.dashboard
}

export function pageForMobileTab(tab) {
  return tabPages[tab] || ''
}
