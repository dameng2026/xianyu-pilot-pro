import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  clearSensitiveSessionData,
  createAuthSessionScope,
  createSessionPrivacyStore,
  purgeLegacySensitiveData,
} from '../src/utils/privacySession.js'

class MemoryStorage {
  #data = new Map()

  get length() { return this.#data.size }
  key(index) { return [...this.#data.keys()][index] ?? null }
  getItem(key) { return this.#data.has(String(key)) ? this.#data.get(String(key)) : null }
  setItem(key, value) { this.#data.set(String(key), String(value)) }
  removeItem(key) { this.#data.delete(String(key)) }
}

function jwt(payload) {
  const encode = value => Buffer.from(JSON.stringify(value)).toString('base64url')
  return `${encode({ alg: 'none', typ: 'JWT' })}.${encode(payload)}.`
}

const aliceToken = jwt({ iss: 'xya', tenant_id: 'tenant-a', sub: 'alice' })
const bobToken = jwt({ iss: 'xya', tenant_id: 'tenant-a', sub: 'bob' })
const otherTenantToken = jwt({ iss: 'xya', tenant_id: 'tenant-b', sub: 'alice' })

const aliceScope = createAuthSessionScope(aliceToken, 'alice')
assert.equal(aliceScope, createAuthSessionScope(aliceToken, 'alice'), 'the same tenant/user identity needs a stable cache scope')
assert.notEqual(aliceScope, createAuthSessionScope(bobToken, 'bob'), 'different users must never share a cache scope')
assert.notEqual(aliceScope, createAuthSessionScope(otherTenantToken, 'alice'), 'the same user name in another tenant must not share a cache scope')
assert.equal(aliceScope.includes('alice'), false, 'cache keys must not expose the user identifier')
assert.equal(aliceScope.includes(aliceToken), false, 'cache keys must never contain the bearer token')

const storage = new MemoryStorage()
let now = 1_000
let currentScope = aliceScope
const store = createSessionPrivacyStore('messages', {
  storage,
  ttlMs: 5_000,
  getScope: () => currentScope,
  now: () => now,
})

store.write({ body: 'private message' })
assert.deepEqual(store.read(), { body: 'private message' }, 'the current user can restore a fresh session cache')

currentScope = createAuthSessionScope(bobToken, 'bob')
assert.equal(store.read(), null, 'another user cannot read the previous user cache')

currentScope = aliceScope
now = 6_001
assert.equal(store.read(), null, 'expired sensitive cache data must not be restored')
assert.equal(storage.length, 0, 'expired sensitive cache data should be removed immediately')

storage.setItem('xya:sensitive:test', 'secret')
const legacyStorage = new MemoryStorage()
legacyStorage.setItem('xya:messages-page-cache:v1', 'legacy messages')
legacyStorage.setItem('xya:messages-page-accounts:v1', 'legacy accounts')
legacyStorage.setItem('xya_client_error_buffer', 'legacy errors')
legacyStorage.setItem('unrelated-preference', 'keep')
clearSensitiveSessionData({ sessionStorage: storage, localStorage: legacyStorage })
assert.equal(storage.length, 0, 'logout must clear every session-scoped sensitive cache')
assert.equal(legacyStorage.getItem('xya:messages-page-cache:v1'), null, 'logout must remove the legacy message cache')
assert.equal(legacyStorage.getItem('xya:messages-page-accounts:v1'), null, 'logout must remove the legacy account cache')
assert.equal(legacyStorage.getItem('xya_client_error_buffer'), null, 'logout must remove the legacy error buffer')
assert.equal(legacyStorage.getItem('unrelated-preference'), 'keep', 'logout must preserve unrelated preferences')

const upgradeStorage = new MemoryStorage()
upgradeStorage.setItem('xya:messages-page-cache:v1', 'legacy messages')
upgradeStorage.setItem('xya_client_error_buffer', 'legacy raw errors')
upgradeStorage.setItem('unrelated-preference', 'keep')
purgeLegacySensitiveData({ localStorage: upgradeStorage })
assert.equal(upgradeStorage.getItem('xya:messages-page-cache:v1'), null, 'upgrading must proactively remove legacy message data')
assert.equal(upgradeStorage.getItem('xya_client_error_buffer'), null, 'upgrading must proactively remove legacy raw error telemetry')
assert.equal(upgradeStorage.getItem('unrelated-preference'), 'keep', 'upgrade cleanup must preserve unrelated preferences')

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const messagesPage = fs.readFileSync(path.join(root, 'src', 'pages', 'MessagesPage.vue'), 'utf8')
const authSource = fs.readFileSync(path.join(root, 'src', 'utils', 'auth.js'), 'utf8')
assert.match(authSource, /if \(previousScope !== nextScope\) clearSensitiveSessionData\(\)/, 'login must clear orphaned sensitive data even when no previous token remains')
assert.match(messagesPage, /createSessionPrivacyStore\('messages-page-cache:v2'/, 'message bodies must use the scoped session cache')
assert.match(messagesPage, /createSessionPrivacyStore\('messages-page-accounts:v2'/, 'account snapshots must use the scoped session cache')
assert.doesNotMatch(messagesPage, /localStorage/, 'MessagesPage must not persist account or message data across browser sessions')
assert.doesNotMatch(messagesPage, /xya:messages-page-(?:cache|accounts):v1/, 'MessagesPage must never restore unscoped legacy caches')
assert.match(
  messagesPage,
  /Object\.prototype\.hasOwnProperty\.call\(nextAccounts, selectedAccountId\)/,
  'cache pruning must also expire the selected account identifier when its scoped account snapshot expires',
)

console.log('privacy-session: ok')
