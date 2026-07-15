import assert from 'node:assert/strict'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')
const source = fs.readFileSync(path.join(root, 'src', 'pages', 'AccountsPage.vue'), 'utf8')

assert(source.includes('async function refreshAccountAfterQrConfirmed'), 'AccountsPage should refresh auth/ws state after QR confirmation')
assert(source.includes("const confirmedAccountId = Number(data.accountId || qr.accountId || 0)"), 'QR confirmation should keep the confirmed account id before closing the modal')
assert(source.includes("await refreshAccountAfterQrConfirmed(confirmedAccountId, { pollWs: isRescan })"), 'Rescan flow should immediately refresh the confirmed account auth/ws state')

console.log('accounts-qr-refresh-contract: ok')
