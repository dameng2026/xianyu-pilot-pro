export function accountCookieStatus(account) {
  const status = Number(account?.cookieStatus ?? account?.cookie_status)
  return Number.isNaN(status) ? null : status
}

export function accountLoginCode(account) {
  return account?.loginStatusCode || account?.login_status_code || ''
}

export function accountLoginMessage(account) {
  return account?.loginStatusMessage || account?.login_status_message || ''
}

export function accountWsConnectionState(account, wsState) {
  if (wsState && Object.prototype.hasOwnProperty.call(wsState, 'connected')) {
    return typeof wsState.connected === 'boolean' ? wsState.connected : null
  }
  if (account && Object.prototype.hasOwnProperty.call(account, 'wsConnected')) {
    return typeof account.wsConnected === 'boolean' ? account.wsConnected : null
  }
  const rawStatus = account?.wsStatus ?? account?.ws_status
  if (rawStatus === null || rawStatus === undefined || rawStatus === '') return null
  const status = Number(rawStatus)
  return Number.isNaN(status) ? null : status === 1
}

export function accountWsConnected(account, wsState) {
  return accountWsConnectionState(account, wsState) === true
}

export function resolveAccountAuthDisplayState(account, wsState = null) {
  const wsConnectionState = accountWsConnectionState(account, wsState)
  const cookieStatus = accountCookieStatus(account)
  const loginStatusCode = accountLoginCode(account)
  const rawUsable = typeof account?.authUsable === 'boolean'
    ? account.authUsable
    : cookieStatus === 1 && loginStatusCode === 'OK'
  const wsConnected = wsConnectionState === true
  // usable 用于账号选择/WS 启动判断：Cookie 预检通过 或 WS 已在线都算可用
  const usable = rawUsable || wsConnected
  return {
    usable,
    authKnown: typeof account?.authUsable === 'boolean' || cookieStatus !== null || Boolean(loginStatusCode) || wsConnected,
    wsConnected,
    wsConnectionState,
    // Cookie 状态独立反映真实预检结果，不被 WS 状态覆盖。
    // 这样 Cookie 失效（cookieStatus=0）时即使 WS 仍显示在线缓存，也会正确显示"失效/需验证"。
    cookieStatus,
    loginStatusCode,
    loginStatusMessage: rawUsable
      ? '账号登录状态正常'
      : accountLoginMessage(account),
  }
}

export function accountAuthUsable(account, wsState = null) {
  return resolveAccountAuthDisplayState(account, wsState).usable
}

// 明确判断账号 Cookie 是否已失效（cookieStatus=0 失效/需验证 或 cookieStatus=2 已过期）。
// 用于页面 UI gating（发布商品/搜索商品前阻断 + 提示），与 accountAuthUsable 互补：
// accountAuthUsable 还会考虑 WS 在线缓存，而本函数只看真实 Cookie 预检结果。
export function isAccountCookieExpired(account, wsState = null) {
  const { cookieStatus } = resolveAccountAuthDisplayState(account, wsState)
  return cookieStatus === 0 || cookieStatus === 2
}

export function pickPreferredAccount(accounts, preferredId = null) {
  const list = Array.isArray(accounts) ? accounts : []
  if (!list.length) return null

  const preferredKey = String(preferredId ?? '').trim()
  const preferredAccount = preferredKey
    ? list.find(account => String(account?.id ?? '') === preferredKey) || null
    : null

  if (preferredAccount && accountAuthUsable(preferredAccount)) {
    return preferredAccount
  }

  const firstUsableAccount = list.find(accountAuthUsable) || null
  if (firstUsableAccount) {
    return firstUsableAccount
  }

  return preferredAccount || list[0] || null
}

export function resolveAccountAutoReplyScopeEnabled(globalEnabled, accountScopes, accountId) {
  const key = String(accountId ?? '').trim()
  if (!key || !globalEnabled) return false
  const scopes = accountScopes && typeof accountScopes === 'object' ? accountScopes : {}
  if (!Object.prototype.hasOwnProperty.call(scopes, key)) return true
  return scopes[key] === true
}

export function shouldAttemptAccountWebSocketStart(account, wsState) {
  if (!accountAuthUsable(account, wsState)) return false
  if (typeof wsState?.connected === 'boolean' && wsState.connected) return false
  return true
}

export function accountCookieLabel(account, wsState = null) {
  const { cookieStatus: status, loginStatusCode: code } = resolveAccountAuthDisplayState(account, wsState)
  if (status === null || status === undefined) return '状态未知'
  if (status === 2) return '已过期'
  if (status === 0) {
    if (code === 'VERIFYING') return '验证中'
    if (code === 'COOKIE_UPDATED') return '待校验'
    if (code === 'COOKIE_TOKEN_MISSING') return '缺少令牌'
    if (code === 'AUTH_MISSING') return '未登录'
    if (code === 'CAPTCHA_FAILED') return '滑块失败'
    if (code === 'SESSION_EXPIRED') return '需重新登录'
    return '失效/需验证'
  }
  return '正常'
}

export function accountCookieBadgeType(account, wsState = null) {
  const { cookieStatus: status, loginStatusCode: code } = resolveAccountAuthDisplayState(account, wsState)
  if (status === null || status === undefined) return 'gray'
  if (status === 2) return 'orange'
  if (status === 0 && (code === 'COOKIE_UPDATED' || code === 'VERIFYING')) return 'orange'
  if (status === 0) return 'red'
  return 'green'
}

export function accountLoginHint(account, wsState = null) {
  const { authKnown, loginStatusMessage, usable } = resolveAccountAuthDisplayState(account, wsState)
  if (!authKnown) return '账号登录状态未知，请刷新后确认'
  return loginStatusMessage || (usable ? '账号登录状态正常' : '请重新登录闲鱼账号')
}
