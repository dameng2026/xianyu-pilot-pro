import assert from 'node:assert/strict'

import {
  accountAuthUsable,
  accountCookieBadgeType,
  accountCookieLabel,
  isAccountCookieExpired,
  resolveAccountAutoReplyScopeEnabled,
  resolveAccountAuthDisplayState,
  shouldAttemptAccountWebSocketStart
} from '../src/utils/accountAuth.js'

async function run(name, fn) {
  try {
    await fn()
    console.log(`ok - ${name}`)
  } catch (error) {
    console.error(`not ok - ${name}`)
    throw error
  }
}

await run('inherits the global auto-reply switch when the account has no explicit override', async () => {
  assert.equal(resolveAccountAutoReplyScopeEnabled(true, {}, 1), true)
  assert.equal(resolveAccountAutoReplyScopeEnabled(false, {}, 1), false)
})

await run('respects explicit account-level auto-reply overrides', async () => {
  assert.equal(resolveAccountAutoReplyScopeEnabled(true, { 1: true }, 1), true)
  assert.equal(resolveAccountAutoReplyScopeEnabled(true, { 1: false }, 1), false)
})

await run('only auto-starts websocket for usable accounts that are not already connected', async () => {
  const usableAccount = { cookieStatus: 1, loginStatusCode: 'OK' }
  const invalidAccount = { cookieStatus: 0, loginStatusCode: 'COOKIE_EXPIRED' }

  assert.equal(accountAuthUsable(usableAccount), true)
  assert.equal(shouldAttemptAccountWebSocketStart(usableAccount, { connected: false }), true)
  assert.equal(shouldAttemptAccountWebSocketStart(usableAccount, { connected: true }), false)
  assert.equal(shouldAttemptAccountWebSocketStart(invalidAccount, { connected: false }), false)
  assert.equal(shouldAttemptAccountWebSocketStart(null, { connected: false }), false)
})

await run('cookie status stays FAILED when websocket is online but cookie is actually expired (UI gating must reflect real probe result)', async () => {
  // Bug 回归测试：用户 cookie 已失效、WS 也已终止，但闲鱼账号页面仍显示正常。
  // 根因：UI 把"WS 在线缓存"作为 cookie 健康的依据，导致 cookie 实际失效时仍显示"正常"，
  // 用户必须点击发布/搜索才被动发现问题。
  // 修复方向：cookieStatus 独立反映真实预检结果，不被 WS 状态覆盖。
  const laggedAccount = {
    cookieStatus: 0,
    loginStatusCode: 'COOKIE_EXPIRED',
    loginStatusMessage: 'Cookie 已失效，请重新登录闲鱼账号',
  }

  const display = resolveAccountAuthDisplayState(laggedAccount, { connected: true })

  // Cookie 状态必须保持 0（失效），不能被 WS 在线覆盖为 1
  assert.equal(display.cookieStatus, 0)
  assert.equal(display.loginStatusCode, 'COOKIE_EXPIRED')
  assert.equal(isAccountCookieExpired(laggedAccount, { connected: true }), true)
  // UI 文案必须反映"失效"，不能因为 WS 在线就显示"正常"
  assert.equal(accountCookieLabel(laggedAccount, { connected: true }), '失效/需验证')
  assert.equal(accountCookieBadgeType(laggedAccount, { connected: true }), 'red')
  // accountAuthUsable 仍可以综合 WS 在线判断为 true（用于 WS 启动判断），
  // 但 isAccountCookieExpired 必须独立返回 true（用于发布/搜索前的 UI gating）
  assert.equal(accountAuthUsable(laggedAccount, { connected: true }), true)
})

await run('isAccountCookieExpired returns false for healthy cookies and null for unknown status', async () => {
  assert.equal(isAccountCookieExpired({ cookieStatus: 1, loginStatusCode: 'OK' }), false)
  assert.equal(isAccountCookieExpired({ cookieStatus: 0, loginStatusCode: 'COOKIE_EXPIRED' }), true)
  assert.equal(isAccountCookieExpired({ cookieStatus: 2 }), true)
  assert.equal(isAccountCookieExpired({ cookieStatus: null }), false)
  assert.equal(isAccountCookieExpired({}), false)
  assert.equal(isAccountCookieExpired(null), false)
})

console.log('account-auth-state: ok')
