import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const readMobile = file => fs.readFileSync(path.join(root, 'src', 'mobile', file), 'utf8')

const messages = readMobile('MobileMessages.vue')
assert.match(messages, /messageContext/)
assert.match(messages, /sendMessage\(/)
assert.match(messages, /openTrustedMediaUrl\(url\)/)
assert.match(messages, /MobileUnavailableState/)
assert.match(messages, /m-chat-product-card/)
assert.match(messages, /m-chat-quick-actions/)
assert.match(messages, /m-chat-compose/)

const accounts = readMobile('MobileAccounts.vue')
for (const pattern of [/getAccounts\(/, /getAccountSummary\(/, /apiRefreshProfile/, /refreshProfile\(/, /m-stats-card/, /m-search-bar/, /m-quick-filters/, /m-acc-card/]) {
  assert.match(accounts, pattern)
}

const detail = readMobile('MobileAccountDetail.vue')
for (const pattern of [/getAccountDetail\(/, /m-expired-notice/, /m-profile-card/, /m-diagnosis-list/, /m-profile-stats/, /m-quick-actions-grid/]) {
  assert.match(detail, pattern)
}

console.log('mobile-visual-restoration-contract: ok')
