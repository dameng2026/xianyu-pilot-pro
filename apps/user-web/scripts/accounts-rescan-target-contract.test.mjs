import assert from 'node:assert/strict'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')
const source = fs.readFileSync(path.join(root, 'src', 'pages', 'AccountsPage.vue'), 'utf8')

assert(source.includes('const qrTargetAccount = computed('), 'AccountsPage should resolve the QR rescan target from qr.accountId')
assert(source.includes("qrTargetAccount?.nickname || qrTargetAccount?.displayName || qrTargetAccount?.externalUid || qr.accountId"), 'AccountsPage scan modal should display the qr target account instead of the currently selected drawer account')
assert(!source.includes("selected?.nickname || selected?.displayName || selected?.externalUid || qr.accountId"), 'AccountsPage scan modal should not use selected account text for rescan target display')

console.log('accounts-rescan-target-contract: ok')
