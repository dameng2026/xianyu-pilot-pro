import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')
const sourcePath = path.join(root, 'src', 'pages', 'AutoReplyPage.vue')
const source = fs.readFileSync(sourcePath, 'utf8')

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

for (const expected of [
  'auto-reply-shell',
  'auto-reply-hero',
  'auto-reply-hero-main',
  'auto-reply-hero-side',
  'auto-reply-workspace',
  'auto-reply-account-panel',
  'auto-reply-product-panel',
  'auto-reply-strategy-panel',
  'auto-reply-summary-panel',
  'auto-reply-logic-panel',
  'auto-reply-impact-panel',
  'Auto Reply Console',
  'scopeOverviewCards',
  'selectedAccountSummary',
  'selectedProductSummary'
]) {
  assert(source.includes(expected), `AutoReplyPage should include: ${expected}`)
}

console.log('auto-reply-contract: ok')
