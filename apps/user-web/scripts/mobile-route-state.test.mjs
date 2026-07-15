import assert from 'node:assert/strict'
import { pageForMobileTab, resolveMobileRoute } from '../src/mobile/mobileRouteState.js'

const deepLinkCases = [
  ['dashboard', { tab: 'home', subPage: null }],
  ['data', { tab: 'home', subPage: 'data' }],
  ['accounts', { tab: 'home', subPage: 'accounts' }],
  ['products', { tab: 'home', subPage: 'products' }],
  ['messages', { tab: 'message', subPage: null }],
  ['message-center', { tab: 'message', subPage: null }],
  ['workflow', { tab: 'automation', subPage: null }],
  ['profile', { tab: 'profile', subPage: null }]
]

for (const [page, expected] of deepLinkCases) {
  assert.deepEqual(resolveMobileRoute(page), expected, `${page} should open its matching mobile view`)
}

assert.deepEqual(resolveMobileRoute('unknown'), { tab: 'home', subPage: null })
assert.equal(pageForMobileTab('home'), 'dashboard')
assert.equal(pageForMobileTab('message'), 'messages')
assert.equal(pageForMobileTab('profile'), 'profile')
assert.equal(pageForMobileTab('automation'), 'workflow')

console.log('mobile route state checks passed')
