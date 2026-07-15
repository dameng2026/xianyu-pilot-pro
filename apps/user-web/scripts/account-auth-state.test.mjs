import assert from 'node:assert/strict'

import {
  accountAuthUsable,
  accountCookieBadgeType,
  accountCookieLabel,
  accountLoginHint,
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

await run('treats websocket-online accounts as display-healthy even when stale cookie fields lag behind', async () => {
  const laggedAccount = {
    cookieStatus: 0,
    loginStatusCode: 'COOKIE_EXPIRED',
    loginStatusMessage: 'Cookie 已失效，请重新登录闲鱼账号',
  }

  const display = resolveAccountAuthDisplayState(laggedAccount, { connected: true })

  assert.equal(display.usable, true)
  assert.equal(display.cookieStatus, 1)
  assert.equal(display.loginStatusCode, 'OK')
  assert.equal(accountCookieLabel(laggedAccount, { connected: true }), '正常')
  assert.equal(accountCookieBadgeType(laggedAccount, { connected: true }), 'green')
  assert.equal(accountLoginHint(laggedAccount, { connected: true }), '账号登录状态正常')
})

console.log('account-auth-state: ok')
