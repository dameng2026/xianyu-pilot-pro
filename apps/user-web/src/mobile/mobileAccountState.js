const STORAGE_KEY = 'mobile_account_list_state'
const NOTICE_KEY = 'mobile_account_notice_dismissed'
const SCROLL_KEY = 'mobile_account_scroll_top'

const defaultState = {
  keyword: '',
  statusFilter: '',
  wsFilter: '',
  cookieFilter: '',
  sortBy: 'latest',
  currentPage: 1
}

export function getAccountListState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      return { ...defaultState, ...JSON.parse(raw) }
    }
  } catch (e) {}
  return { ...defaultState }
}

export function updateAccountListState(partial) {
  try {
    const current = getAccountListState()
    const next = { ...current, ...partial }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  } catch (e) {}
}

export function saveAccountListScrollTop(scrollTop) {
  try {
    sessionStorage.setItem(SCROLL_KEY, String(scrollTop || 0))
  } catch (e) {}
}

export function getAccountListScrollTop() {
  try {
    const v = sessionStorage.getItem(SCROLL_KEY)
    return v ? parseInt(v, 10) || 0 : 0
  } catch (e) {
    return 0
  }
}

export function dismissAccountNotice() {
  try {
    localStorage.setItem(NOTICE_KEY, '1')
  } catch (e) {}
}

export function isAccountNoticeDismissed() {
  try {
    return localStorage.getItem(NOTICE_KEY) === '1'
  } catch (e) {
    return false
  }
}
